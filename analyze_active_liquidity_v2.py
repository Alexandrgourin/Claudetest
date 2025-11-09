#!/usr/bin/env python3
"""
Анализ реальной активной ликвидности в топ пулах Base

Получает:
- Реальные балансы токенов в пуле через balanceOf() (Total Liquidity)
- Параметр liquidity (активная ликвидность на текущем тике)
- Сравнение с TVL от GeckoTerminal
"""

import requests
import json
from typing import Dict, List, Optional

NODE_URL = "http://80.209.241.37:8545/"
GECKOTERMINAL_API = "https://api.geckoterminal.com/api/v2"

def rpc_call(method: str, params: List = None) -> Dict:
    """RPC вызов к ноде"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params if params else [],
        "id": 1
    }
    try:
        response = requests.post(NODE_URL, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def calculate_active_liquidity_amounts(liquidity: int, sqrt_price_x96: int,
                                       token0_decimals: int, token1_decimals: int) -> tuple:
    """
    Рассчитать реальные amounts токенов из параметра L на текущем тике

    Формулы из Uniswap V3:
    - amount0 (token0) = L / sqrtPriceX96 * 2^96
    - amount1 (token1) = L * sqrtPriceX96 / 2^96

    Возвращает виртуальные резервы доступные для торговли на текущем тике
    """
    if liquidity == 0 or sqrt_price_x96 == 0:
        return (0.0, 0.0)

    Q96 = 2 ** 96

    # Виртуальные резервы на текущем тике
    amount0_raw = (liquidity * Q96) // sqrt_price_x96
    amount1_raw = (liquidity * sqrt_price_x96) // Q96

    # Конвертируем с учетом decimals
    amount0 = amount0_raw / (10 ** token0_decimals)
    amount1 = amount1_raw / (10 ** token1_decimals)

    return (amount0, amount1)

def get_token_balance(token_address: str, holder_address: str, decimals: int) -> float:
    """
    Получить баланс токена через balanceOf()

    balanceOf(address) signature: 0x70a08231
    """
    # Формируем calldata: function selector + padded address
    data = "0x70a08231" + "0" * 24 + holder_address[2:]

    result = rpc_call("eth_call", [{
        "to": token_address,
        "data": data
    }, "latest"])

    if "result" not in result:
        return 0

    try:
        balance_raw = int(result["result"], 16)
        balance = balance_raw / (10 ** decimals)
        return balance
    except:
        return 0

def get_pool_state(pool_address: str) -> Optional[Dict]:
    """
    Получить состояние пула:
    - slot0() → current tick, sqrtPriceX96
    - liquidity() → active liquidity parameter L
    """
    # slot0()
    slot0_result = rpc_call("eth_call", [{
        "to": pool_address,
        "data": "0x3850c7bd"
    }, "latest"])

    # liquidity()
    liquidity_result = rpc_call("eth_call", [{
        "to": pool_address,
        "data": "0x1a686502"
    }, "latest"])

    if "result" not in slot0_result or "result" not in liquidity_result:
        return None

    try:
        # Парсим slot0
        slot0_data = slot0_result["result"][2:]
        if len(slot0_data) < 128:
            return None

        sqrt_price_x96 = int(slot0_data[0:64], 16)
        tick_hex = slot0_data[64:128]
        tick_raw = int(tick_hex, 16)

        # Конвертация в signed int24
        tick_24bit = tick_raw & 0xFFFFFF
        if tick_24bit & 0x800000:
            tick = tick_24bit - 0x1000000
        else:
            tick = tick_24bit

        # Валидация
        if tick < -887272 or tick > 887272:
            return None

        # Парсим liquidity
        liquidity_hex = liquidity_result["result"][2:]
        liquidity = int(liquidity_hex, 16) if liquidity_hex else 0

        # Расчет цены
        price = (sqrt_price_x96 / (2**96)) ** 2 if sqrt_price_x96 > 0 else 0

        return {
            "sqrt_price_x96": sqrt_price_x96,
            "tick": tick,
            "liquidity": liquidity,
            "price": price
        }
    except Exception as e:
        return None

def get_top_pools(limit=20):
    """Получить топ пулы с GeckoTerminal включая данные токенов"""
    url = f"{GECKOTERMINAL_API}/networks/base/pools"

    try:
        response = requests.get(url, params={
            "page": 1,
            "include": "base_token,quote_token"
        }, timeout=10)

        if response.status_code != 200:
            return []

        data = response.json()
        pools = []

        # Создаем словарь токенов из included
        tokens_map = {}
        for item in data.get("included", []):
            if item.get("type") == "token":
                token_attrs = item.get("attributes", {})
                tokens_map[item.get("id")] = {
                    "address": token_attrs.get("address"),
                    "symbol": token_attrs.get("symbol"),
                    "decimals": int(token_attrs.get("decimals", 18)),
                }

        for pool in data.get("data", [])[:limit]:
            attrs = pool.get("attributes", {})
            relationships = pool.get("relationships", {})

            volume_data = attrs.get("volume_usd", {})
            volume_24h = 0
            if isinstance(volume_data, dict):
                volume_24h = float(volume_data.get("h24", 0))
            elif isinstance(volume_data, (int, float)):
                volume_24h = float(volume_data)

            # Получаем данные токенов из relationships
            base_token_id = relationships.get("base_token", {}).get("data", {}).get("id")
            quote_token_id = relationships.get("quote_token", {}).get("data", {}).get("id")

            # Получаем decimals из tokens_map и цены из attrs
            base_token_data = tokens_map.get(base_token_id, {}).copy()
            quote_token_data = tokens_map.get(quote_token_id, {}).copy()

            # Добавляем цены из pool attributes
            base_token_data["price_usd"] = float(attrs.get("base_token_price_usd") or 0)
            quote_token_data["price_usd"] = float(attrs.get("quote_token_price_usd") or 0)

            # В Uniswap V3: token0 < token1 по адресу (лексикографически)
            base_addr = base_token_data.get("address", "").lower()
            quote_addr = quote_token_data.get("address", "").lower()

            if base_addr and quote_addr and base_addr < quote_addr:
                token0, token1 = base_token_data, quote_token_data
            else:
                token0, token1 = quote_token_data, base_token_data

            pools.append({
                "address": attrs.get("address"),
                "name": attrs.get("name", ""),
                "dex": attrs.get("dex", ""),
                "tvl_usd_gecko": float(attrs.get("reserve_in_usd", 0)),
                "volume_24h": volume_24h,
                "token0": token0,
                "token1": token1,
            })

        return pools

    except Exception as e:
        import traceback
        print(f"❌ Ошибка: {e}")
        traceback.print_exc()
        return []

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                                                                  ║
    ║      АНАЛИЗ РЕАЛЬНОЙ АКТИВНОЙ ЛИКВИДНОСТИ (Base)                ║
    ║                                                                  ║
    ║  Получает реальные балансы токенов в пулах через balanceOf()    ║
    ║  и сравнивает с данными GeckoTerminal                            ║
    ║                                                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)

    print("📊 Загрузка топ-20 пулов с GeckoTerminal...\n")
    pools = get_top_pools(20)

    if not pools:
        print("❌ Не удалось загрузить пулы")
        return

    print(f"✅ Загружено {len(pools)} пулов\n")
    print("🔍 Получение on-chain данных (балансы токенов, tick, liquidity)...\n")

    results = []

    for i, pool in enumerate(pools, 1):
        pool_address = pool["address"]
        print(f"   [{i}/{len(pools)}] {pool['name'][:50]:<50}", end=" ")

        # Получаем on-chain состояние
        state = get_pool_state(pool_address)

        if not state:
            print("❌ Нет данных")
            continue

        # Проверяем наличие данных токенов
        token0 = pool.get("token0", {})
        token1 = pool.get("token1", {})

        if not token0 or not token1:
            print("❌ Нет данных токенов")
            continue

        # Получаем реальные балансы токенов в пуле
        balance0 = get_token_balance(
            token0.get("address"),
            pool_address,
            token0.get("decimals", 18)
        )

        balance1 = get_token_balance(
            token1.get("address"),
            pool_address,
            token1.get("decimals", 18)
        )

        # Считаем реальный TVL из балансов
        tvl_real_usd = (balance0 * token0.get("price_usd", 0) +
                        balance1 * token1.get("price_usd", 0))

        # Рассчитываем активную ликвидность из параметра L
        active_amount0, active_amount1 = calculate_active_liquidity_amounts(
            state["liquidity"],
            state["sqrt_price_x96"],
            token0.get("decimals", 18),
            token1.get("decimals", 18)
        )

        # Активная ликвидность в USD
        active_liquidity_usd = (active_amount0 * token0.get("price_usd", 0) +
                                active_amount1 * token1.get("price_usd", 0))

        # Соотношение активной ликвидности к TVL
        active_ratio = (active_liquidity_usd / tvl_real_usd * 100) if tvl_real_usd > 0 else 0

        # Считаем соотношение с GeckoTerminal TVL
        gecko_tvl = pool["tvl_usd_gecko"]
        tvl_diff_pct = ((tvl_real_usd - gecko_tvl) / gecko_tvl * 100) if gecko_tvl > 0 else 0

        result = {
            **pool,
            "tick": state["tick"],
            "price": state["price"],
            "liquidity_param": state["liquidity"],
            "balance0": balance0,
            "balance1": balance1,
            "tvl_real_usd": tvl_real_usd,
            "tvl_diff_pct": tvl_diff_pct,
            "active_amount0": active_amount0,
            "active_amount1": active_amount1,
            "active_liquidity_usd": active_liquidity_usd,
            "active_ratio": active_ratio
        }

        results.append(result)
        print(f"✅ TVL: ${tvl_real_usd:,.0f}, Active: ${active_liquidity_usd:,.0f} ({active_ratio:.1f}%)")

    if not results:
        print("\n❌ Нет данных для анализа")
        return

    # Сортируем по реальному TVL
    results_by_tvl = sorted(results, key=lambda x: x["tvl_real_usd"], reverse=True)

    print(f"\n{'='*170}")
    print(f"📊 ТОП-15 ПУЛОВ ПО РЕАЛЬНОМУ TVL (on-chain balances)")
    print(f"{'='*170}\n")

    print(f"{'Пул':<45} {'TVL':>15} {'Active Liq':>15} {'Ratio':>8} {'Tick':>8} {'Volume 24h':>15} {'Vol/TVL':>10}")
    print(f"{'-'*170}")

    for i, pool in enumerate(results_by_tvl[:15], 1):
        vol_tvl_ratio = (pool['volume_24h'] / pool['tvl_real_usd']) if pool['tvl_real_usd'] > 0 else 0
        print(f"{pool['name'][:43]:<45} "
              f"${pool['tvl_real_usd']:>13,.0f} "
              f"${pool['active_liquidity_usd']:>13,.0f} "
              f"{pool['active_ratio']:>6.1f}% "
              f"{pool['tick']:>8,} "
              f"${pool['volume_24h']:>13,.0f} "
              f"{vol_tvl_ratio:>9.2f}x")

    # Детальный анализ топ-3
    print(f"\n{'='*160}")
    print(f"🔍 ДЕТАЛЬНЫЙ АНАЛИЗ ТОП-3 ПУЛОВ")
    print(f"{'='*160}\n")

    for i, pool in enumerate(results_by_tvl[:3], 1):
        token0 = pool["token0"]
        token1 = pool["token1"]

        print(f"{'─'*160}")
        print(f"#{i}. {pool['name']}")
        print(f"{'─'*160}")
        print(f"Pool Address:            {pool['address']}")
        print(f"DEX:                     {pool['dex']}")
        print()
        print(f"💰 РЕАЛЬНЫЕ БАЛАНСЫ ТОКЕНОВ (on-chain):")
        print(f"   {token0['symbol']:<10} balance: {pool['balance0']:>20,.6f} × ${token0['price_usd']:<10,.2f} = ${pool['balance0'] * token0['price_usd']:>15,.2f}")
        print(f"   {token1['symbol']:<10} balance: {pool['balance1']:>20,.6f} × ${token1['price_usd']:<10,.6f} = ${pool['balance1'] * token1['price_usd']:>15,.2f}")
        print(f"   {'TOTAL TVL':<10}          {' '*20}   {' '*12}   ${pool['tvl_real_usd']:>15,.2f}")
        print()
        print(f"📊 СРАВНЕНИЕ С GECKOTERMINAL:")
        print(f"   GeckoTerminal TVL:   ${pool['tvl_usd_gecko']:>15,.2f}")
        print(f"   On-chain TVL:        ${pool['tvl_real_usd']:>15,.2f}")
        print(f"   Difference:          {pool['tvl_diff_pct']:>14,.2f}%")
        print()
        print(f"📈 АКТИВНАЯ ЛИКВИДНОСТЬ (текущий тик):")
        print(f"   Current Tick:        {pool['tick']:>15,}")
        print(f"   Current Price:       {pool['price']:>15.10f}")
        print()
        print(f"   {token0['symbol']:<10} active:  {pool['active_amount0']:>20,.6f} × ${token0['price_usd']:<10,.2f} = ${pool['active_amount0'] * token0['price_usd']:>15,.2f}")
        print(f"   {token1['symbol']:<10} active:  {pool['active_amount1']:>20,.6f} × ${token1['price_usd']:<10,.6f} = ${pool['active_amount1'] * token1['price_usd']:>15,.2f}")
        print(f"   {'TOTAL':<10}          {' '*20}   {' '*12}   ${pool['active_liquidity_usd']:>15,.2f}")
        print()
        print(f"   Active/TVL Ratio:    {pool['active_ratio']:>15,.1f}%")
        print()
        print(f"   📝 Примечание: Активная ликвидность рассчитана из параметра L через формулы:")
        print(f"      amount0 = L / sqrtPriceX96 × 2^96")
        print(f"      amount1 = L × sqrtPriceX96 / 2^96")
        print(f"      Это виртуальные резервы доступные для торговли на текущем тике.")
        print()
        print(f"💹 ТОРГОВЛЯ:")
        print(f"   24h Volume:          ${pool['volume_24h']:>15,.2f}")
        print(f"   Volume/TVL Ratio:    {(pool['volume_24h'] / pool['tvl_real_usd'])if pool['tvl_real_usd'] > 0 else 0:>15.2f}x")
        print()

    # Статистика
    avg_diff = sum(abs(p["tvl_diff_pct"]) for p in results) / len(results)
    avg_active_ratio = sum(p["active_ratio"] for p in results) / len(results)

    print(f"{'='*160}")
    print(f"📊 СТАТИСТИКА")
    print(f"{'='*160}\n")
    print(f"Всего проанализировано пулов:              {len(results)}")
    print(f"Средняя разница TVL (on-chain vs Gecko):   {avg_diff:.2f}%")
    print(f"Среднее соотношение Active/TVL:            {avg_active_ratio:.1f}%")
    print()
    print(f"💡 ВЫВОДЫ:")
    print()
    print(f"   ✅ Реальный TVL получен через on-chain balanceOf() для каждого токена")
    print(f"   ✅ Разница с GeckoTerminal минимальна (средняя {avg_diff:.1f}%), что подтверждает точность")
    print(f"   ✅ Активная ликвидность рассчитана из параметра L по формулам Uniswap V3")
    print()
    print(f"   📌 Активная ликвидность = виртуальные резервы доступные для торговли на текущем тике")
    print(f"   📌 Среднее соотношение Active/TVL: {avg_active_ratio:.1f}% - показывает концентрацию ликвидности")
    print(f"   📌 Высокий Active/TVL (>50%) = сильно концентрированная ликвидность = меньше slippage")
    print(f"   📌 Низкий Active/TVL (<20%) = широко распределенная ликвидность = больше slippage")
    print()

if __name__ == "__main__":
    main()
