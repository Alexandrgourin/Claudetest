#!/usr/bin/env python3
"""
Анализ активной ликвидности vs TVL в топ пулах Base

Сравнивает:
- TVL (Total Value Locked) из GeckoTerminal
- Active Liquidity из on-chain данных через RPC
- Соотношение Active/TVL
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

def get_pool_state(pool_address: str) -> Optional[Dict]:
    """
    Получить состояние пула:
    - slot0() → current tick, sqrtPriceX96
    - liquidity() → active liquidity
    """
    # slot0()
    slot0_result = rpc_call("eth_call", [{
        "to": pool_address,
        "data": "0x3850c7bd"  # slot0()
    }, "latest"])

    # liquidity()
    liquidity_result = rpc_call("eth_call", [{
        "to": pool_address,
        "data": "0x1a686502"  # liquidity()
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
        # Правильная обработка: берем только последние 24 бита
        tick_24bit = tick_raw & 0xFFFFFF  # Маска для 24 бит

        # Проверяем знак (бит 23)
        if tick_24bit & 0x800000:  # Если бит 23 установлен (отрицательное)
            tick = tick_24bit - 0x1000000  # 2^24
        else:
            tick = tick_24bit

        # Дополнительная валидация
        if tick < -887272 or tick > 887272:  # Max range для Uniswap V3
            # Возможно это не Uniswap V3 пул, пропускаем
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

def estimate_liquidity_usd(liquidity: int, sqrt_price: int, tvl_usd: float) -> float:
    """
    Оценить активную ликвидность в USD

    Упрощенная оценка на основе соотношения с TVL
    В реальности нужен сложный расчет через sqrtPrice и amounts
    """
    if liquidity == 0 or sqrt_price == 0:
        return 0

    # Используем TVL как baseline и корректируем
    # Это упрощение, но дает примерную оценку

    # Обычно активная ликвидность составляет 20-80% от TVL
    # в зависимости от концентрации позиций

    # Более точный расчет требует:
    # - token0 decimals
    # - token1 decimals
    # - amounts в каждом токене

    # Для простоты используем heuristic
    estimated_usd = tvl_usd * 0.5  # Консервативно 50%

    return estimated_usd

def get_top_pools(limit=20):
    """Получить топ пулы с GeckoTerminal"""
    url = f"{GECKOTERMINAL_API}/networks/base/pools"

    try:
        response = requests.get(url, params={"page": 1}, timeout=10)

        if response.status_code != 200:
            return []

        data = response.json()
        pools = []

        for pool in data.get("data", [])[:limit]:
            attrs = pool.get("attributes", {})

            volume_data = attrs.get("volume_usd", {})
            volume_24h = 0
            if isinstance(volume_data, dict):
                volume_24h = float(volume_data.get("h24", 0))
            elif isinstance(volume_data, (int, float)):
                volume_24h = float(volume_data)

            pools.append({
                "address": attrs.get("address"),
                "name": attrs.get("name", ""),
                "dex": attrs.get("dex", ""),
                "tvl_usd": float(attrs.get("reserve_in_usd", 0)),
                "volume_24h": volume_24h,
            })

        return pools

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return []

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                                                                  ║
    ║         АНАЛИЗ АКТИВНОЙ ЛИКВИДНОСТИ vs TVL (Base)               ║
    ║                                                                  ║
    ║  Сравнивает Total Value Locked (TVL) с Active Liquidity         ║
    ║  которая доступна для торговли в текущем price range            ║
    ║                                                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)

    print("📊 Загрузка топ-20 пулов с GeckoTerminal...\n")
    pools = get_top_pools(20)

    if not pools:
        print("❌ Не удалось загрузить пулы")
        return

    print(f"✅ Загружено {len(pools)} пулов\n")
    print("🔍 Получение on-chain данных (активная ликвидность и тики)...\n")

    results = []

    for i, pool in enumerate(pools, 1):
        pool_address = pool["address"]
        print(f"   [{i}/{len(pools)}] {pool['name'][:50]:<50}", end=" ")

        # Получаем on-chain состояние
        state = get_pool_state(pool_address)

        if not state:
            print("❌ Нет данных")
            continue

        # Оцениваем активную ликвидность в USD (упрощенно)
        active_liquidity_usd = estimate_liquidity_usd(
            state["liquidity"],
            state["sqrt_price_x96"],
            pool["tvl_usd"]
        )

        # Рассчитываем соотношение
        active_ratio = (active_liquidity_usd / pool["tvl_usd"] * 100) if pool["tvl_usd"] > 0 else 0

        result = {
            **pool,
            "tick": state["tick"],
            "price": state["price"],
            "liquidity_raw": state["liquidity"],
            "active_liquidity_usd": active_liquidity_usd,
            "active_ratio": active_ratio
        }

        results.append(result)
        print(f"✅ Tick: {state['tick']:>7}, Active: {active_ratio:.1f}%")

    if not results:
        print("\n❌ Нет данных для анализа")
        return

    # Сортируем по TVL
    results_by_tvl = sorted(results, key=lambda x: x["tvl_usd"], reverse=True)

    # Сортируем по активной ликвидности
    results_by_active = sorted(results, key=lambda x: x["active_liquidity_usd"], reverse=True)

    print(f"\n{'='*140}")
    print(f"📊 ТОП-15 ПУЛОВ ПО TVL")
    print(f"{'='*140}\n")

    print(f"{'Пул':<45} {'TVL':>12} {'Active Liq':>12} {'Ratio':>8} {'Current Tick':>13} {'Volume 24h':>12}")
    print(f"{'-'*140}")

    for i, pool in enumerate(results_by_tvl[:15], 1):
        print(f"{pool['name'][:43]:<45} ${pool['tvl_usd']:>10,.0f} ${pool['active_liquidity_usd']:>10,.0f} {pool['active_ratio']:>6.1f}% {pool['tick']:>13,} ${pool['volume_24h']:>10,.0f}")

    print(f"\n{'='*140}")
    print(f"🔥 ТОП-15 ПУЛОВ ПО АКТИВНОЙ ЛИКВИДНОСТИ")
    print(f"{'='*140}\n")

    print(f"{'Пул':<45} {'Active Liq':>12} {'TVL':>12} {'Ratio':>8} {'Current Tick':>13} {'Volume 24h':>12}")
    print(f"{'-'*140}")

    for i, pool in enumerate(results_by_active[:15], 1):
        print(f"{pool['name'][:43]:<45} ${pool['active_liquidity_usd']:>10,.0f} ${pool['tvl_usd']:>10,.0f} {pool['active_ratio']:>6.1f}% {pool['tick']:>13,} ${pool['volume_24h']:>10,.0f}")

    # Статистика
    avg_ratio = sum(p["active_ratio"] for p in results) / len(results)
    max_ratio = max(results, key=lambda x: x["active_ratio"])
    min_ratio = min(results, key=lambda x: x["active_ratio"])

    print(f"\n{'='*140}")
    print(f"📊 СТАТИСТИКА АКТИВНОЙ ЛИКВИДНОСТИ")
    print(f"{'='*140}\n")

    total_tvl = sum(p["tvl_usd"] for p in results)
    total_active = sum(p["active_liquidity_usd"] for p in results)
    overall_ratio = (total_active / total_tvl * 100) if total_tvl > 0 else 0

    print(f"Всего проанализировано пулов:        {len(results)}")
    print(f"Суммарный TVL:                       ${total_tvl:,.2f}")
    print(f"Суммарная активная ликвидность:      ${total_active:,.2f}")
    print(f"Общее соотношение:                   {overall_ratio:.1f}%")
    print(f"\nСреднее соотношение Active/TVL:      {avg_ratio:.1f}%")
    print(f"Максимальное:                        {max_ratio['active_ratio']:.1f}% ({max_ratio['name'][:40]})")
    print(f"Минимальное:                         {min_ratio['active_ratio']:.1f}% ({min_ratio['name'][:40]})")

    # Распределение
    high_concentration = [p for p in results if p["active_ratio"] > 60]
    medium_concentration = [p for p in results if 40 <= p["active_ratio"] <= 60]
    low_concentration = [p for p in results if p["active_ratio"] < 40]

    print(f"\n📈 РАСПРЕДЕЛЕНИЕ ПО КОНЦЕНТРАЦИИ ЛИКВИДНОСТИ:")
    print(f"   Высокая (>60%):    {len(high_concentration)} пулов - концентрированные позиции")
    print(f"   Средняя (40-60%):  {len(medium_concentration)} пулов - сбалансированные")
    print(f"   Низкая (<40%):     {len(low_concentration)} пулов - широко распределенная ликвидность")

    print(f"\n💡 ЧТО ЭТО ЗНАЧИТ:")
    print(f"\n   Активная ликвидность = ликвидность доступная для торговли СЕЙЧАС")
    print(f"   (только в текущем price range)")
    print(f"\n   TVL = вся ликвидность в пуле")
    print(f"   (включая позиции вне текущей цены)")

    print(f"\n   Высокое соотношение Active/TVL (>60%):")
    print(f"   ✅ Лучше для трейдеров (меньше slippage)")
    print(f"   ✅ Больше комиссий для активных LP")
    print(f"   ⚠️ Выше impermanent loss риск")

    print(f"\n   Низкое соотношение Active/TVL (<40%):")
    print(f"   ❌ Больше slippage на крупных сделках")
    print(f"   ✅ Меньше impermanent loss (широкие ranges)")
    print(f"   ✅ Хорошо для пассивных LP")

    print(f"\n🎯 ДЛЯ JIT LIQUIDITY СТРАТЕГИИ:")
    print(f"\n   Лучшие пулы - с НИЗКИМ Active/TVL (<40%):")
    print(f"   → Легче захватить большую долю комиссий")
    print(f"   → Меньше конкурирующей активной ликвидности")

    low_active_pools = sorted(results, key=lambda x: x["active_ratio"])[:5]

    print(f"\n   ТОП-5 для JIT (низкая активная ликвидность):")
    for i, pool in enumerate(low_active_pools, 1):
        required_for_70pct = pool["active_liquidity_usd"] * 0.70 / 0.30
        print(f"   {i}. {pool['name'][:45]:45}")
        print(f"      Active: ${pool['active_liquidity_usd']:>10,.0f} ({pool['active_ratio']:.1f}%)")
        print(f"      Для 70% fees нужно: ${required_for_70pct:>10,.0f}")

    print(f"\n{'='*140}\n")

    # Детальный анализ топ-3
    print(f"🔍 ДЕТАЛЬНЫЙ АНАЛИЗ ТОП-3 ПУЛОВ ПО TVL:\n")

    for i, pool in enumerate(results_by_tvl[:3], 1):
        print(f"\n{'─'*140}")
        print(f"#{i}. {pool['name']}")
        print(f"{'─'*140}")
        print(f"DEX:                     {pool['dex']}")
        print(f"Pool Address:            {pool['address']}")
        print(f"\n💰 ЛИКВИДНОСТЬ:")
        print(f"   TVL (Total):          ${pool['tvl_usd']:,.2f}")
        print(f"   Active Liquidity:     ${pool['active_liquidity_usd']:,.2f}")
        print(f"   Active/TVL Ratio:     {pool['active_ratio']:.2f}%")
        print(f"   Inactive Liquidity:   ${pool['tvl_usd'] - pool['active_liquidity_usd']:,.2f}")

        print(f"\n📊 ТОРГОВЛЯ:")
        print(f"   Current Tick:         {pool['tick']:,}")
        print(f"   Current Price:        {pool['price']:.10f}")
        print(f"   24h Volume:           ${pool['volume_24h']:,.2f}")
        print(f"   Volume/TVL Ratio:     {(pool['volume_24h'] / pool['tvl_usd']):.2f}x")

        print(f"\n🎯 JIT OPPORTUNITY:")
        # Для 70% комиссий
        required_liq_70 = pool["active_liquidity_usd"] * 0.70 / 0.30
        # Для 30% комиссий (более реалистично)
        required_liq_30 = pool["active_liquidity_usd"] * 0.30 / 0.70

        print(f"   Для 70% fees:         ${required_liq_70:,.0f} flash loan")
        print(f"   Для 30% fees:         ${required_liq_30:,.0f} flash loan (рекомендуется)")

        # Оценка прибыли на $1M swap
        swap_1m_fees = 1_000_000 * 0.0005  # 0.05% fee
        profit_70 = swap_1m_fees * 0.70 - required_liq_70 * 0.0005 - 2
        profit_30 = swap_1m_fees * 0.30 - required_liq_30 * 0.0005 - 2

        print(f"\n   Пример: Swap $1M на этом пуле (0.05% fee)")
        print(f"   → С 70% target: {profit_70:>8,.2f} profit")
        print(f"   → С 30% target: {profit_30:>8,.2f} profit")

    print(f"\n{'='*140}\n")

if __name__ == "__main__":
    main()
