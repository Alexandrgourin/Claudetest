#!/usr/bin/env python3
"""
Топ-10 пулов по активной ликвидности на Base с переводом в USD
"""

import requests
from typing import Dict, List, Optional
from datetime import datetime

# Конфигурация
GECKOTERMINAL_API = "https://api.geckoterminal.com/api/v2"
RETH_NODE_URL = "http://80.209.241.37:8545/"
NETWORK = "base"

SLOT0_ABI = "0x3850c7bd"
LIQUIDITY_ABI = "0x1a686502"


def rpc_call(method: str, params: list) -> Optional[Dict]:
    """JSON-RPC запрос к reth ноде"""
    try:
        response = requests.post(
            RETH_NODE_URL,
            json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
            timeout=10
        )
        result = response.json()
        return result.get("result") if "error" not in result else None
    except:
        return None


def get_pools(limit: int = 100) -> Optional[List[Dict]]:
    """Получить список пулов"""
    try:
        pools = []
        for page in range(1, 4):  # Получаем несколько страниц
            url = f"{GECKOTERMINAL_API}/networks/{NETWORK}/pools?page={page}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    pools.extend(data['data'])
                    if len(pools) >= limit:
                        break

        return pools[:limit]
    except:
        return None


def get_pool_slot0(address: str) -> Optional[Dict]:
    """Получить slot0 пула"""
    result = rpc_call("eth_call", [{"to": address, "data": SLOT0_ABI}, "latest"])
    if not result or result == "0x":
        return None

    try:
        data = result[2:]
        if len(data) < 128:
            return None

        sqrt_price_x96 = int(data[0:64], 16)
        tick_raw = int(data[64:128], 16)

        # Декодирование signed int24
        MAX_INT24 = 8388607
        if tick_raw > MAX_INT24:
            if tick_raw > 2**255:
                tick = tick_raw - 2**256
            else:
                tick = tick_raw

            if tick < -887272 or tick > 887272:
                tick_24bit = tick_raw & 0xFFFFFF
                tick = tick_24bit - 2**24 if tick_24bit > MAX_INT24 else tick_24bit
        else:
            tick = tick_raw

        return {"sqrtPriceX96": sqrt_price_x96, "tick": tick}
    except:
        return None


def get_pool_liquidity(address: str) -> Optional[int]:
    """Получить активную ликвидность"""
    result = rpc_call("eth_call", [{"to": address, "data": LIQUIDITY_ABI}, "latest"])
    if not result or result == "0x":
        return None
    try:
        return int(result, 16)
    except:
        return None


def calculate_liquidity_usd(liquidity: int, sqrt_price_x96: int, reserve_usd: float) -> float:
    """
    Вычислить приблизительную стоимость активной ликвидности в USD

    Для Uniswap V3: L = sqrt(x * y)
    где x - количество token0, y - количество token1

    Цена: price = (sqrtPriceX96 / 2^96)^2

    Упрощенная формула:
    Используем reserve_usd как оценку полной ликвидности
    и пропорционально рассчитываем активную часть
    """
    if liquidity == 0 or sqrt_price_x96 == 0:
        return 0

    try:
        # Вычисляем цену из sqrtPriceX96
        sqrt_price = sqrt_price_x96 / (2 ** 96)
        price = sqrt_price ** 2

        # Для упрощения используем liquidity напрямую
        # L измеряется в "единицах ликвидности"
        # Переводим в USD используя цену и reserve как базу

        # Упрощенная оценка: берем корень из ликвидности и нормализуем
        # Это приблизительная оценка, точная требует знания decimals токенов
        liquidity_normalized = liquidity / (10 ** 18)

        # Используем reserve_usd как ориентир для масштаба
        # В реальности нужно учитывать price range и decimals
        liquidity_usd = liquidity_normalized * (price ** 0.25) * 0.1

        return liquidity_usd
    except:
        return 0


def format_number(num: float) -> str:
    """Форматировать число"""
    if num >= 1_000_000_000:
        return f"${num/1_000_000_000:.2f}B"
    elif num >= 1_000_000:
        return f"${num/1_000_000:.2f}M"
    elif num >= 1_000:
        return f"${num/1_000:.2f}K"
    else:
        return f"${num:.2f}"


def explain_tick(tick: int, sqrt_price_x96: int) -> str:
    """Объяснить что означает тик"""
    price_from_tick = 1.0001 ** tick
    price_from_sqrt = (sqrt_price_x96 / (2 ** 96)) ** 2 if sqrt_price_x96 > 0 else 0

    # Диапазон одного тика (0.01% изменения)
    tick_spacing = 0.0001  # 0.01%

    explanation = f"""
    Текущий тик: {tick:,}

    📍 Что это значит:
    • Цена (из тика): {price_from_tick:.10f}
    • Цена (из sqrtPrice): {price_from_sqrt:.10f}
    • Один тик = ~0.01% изменения цены
    • Диапазон тика: ±{tick_spacing * 100}%

    🎯 Интерпретация:
    """

    if tick < 0:
        explanation += f"    • Отрицательный тик ({tick:,}) означает, что token0 дешевле token1\n"
        explanation += f"    • Чем более отрицательный тик, тем дешевле token0\n"
    elif tick > 0:
        explanation += f"    • Положительный тик ({tick:,}) означает, что token0 дороже token1\n"
        explanation += f"    • Чем больше тик, тем дороже token0\n"
    else:
        explanation += f"    • Тик = 0 означает, что цена токенов примерно равна\n"

    return explanation


def main():
    print("=" * 90)
    print("  ТОП-10 ПУЛОВ ПО АКТИВНОЙ ЛИКВИДНОСТИ НА BASE (С ПЕРЕВОДОМ В USD)")
    print("=" * 90)
    print(f"  Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 90)
    print()

    print("📊 Загрузка пулов с Base Network...")
    pools = get_pools(100)

    if not pools:
        print("❌ Не удалось получить данные о пулах")
        return

    print(f"✅ Получено {len(pools)} пулов, начинаю анализ...")
    print()

    # Анализируем пулы
    analyzed_pools = []

    for i, pool in enumerate(pools, 1):
        if i % 10 == 0:
            print(f"   Проанализировано {i}/{len(pools)} пулов...")

        attrs = pool['attributes']
        dex = pool['relationships']['dex']['data']['id']

        # Только V3 пулы
        if not any(x in dex.lower() for x in ['v3', 'v4', 'slipstream']):
            continue

        address = attrs['address']
        name = attrs['name']
        reserve = float(attrs.get('reserve_in_usd', 0))
        volume_24h = float(attrs.get('volume_usd', {}).get('h24', 0))

        # Получаем on-chain данные
        slot0 = get_pool_slot0(address)
        liquidity = get_pool_liquidity(address)

        if slot0 and liquidity and liquidity > 0:
            tick = slot0['tick']
            sqrt_price_x96 = slot0['sqrtPriceX96']

            # Вычисляем ликвидность в USD
            liquidity_usd = calculate_liquidity_usd(liquidity, sqrt_price_x96, reserve)

            # Альтернативная оценка: используем reserve как базу
            # Предполагаем что активная ликвидность это примерно reserve * коэффициент
            liquidity_usd_estimate = reserve * 0.5  # ~50% от TVL обычно активно

            analyzed_pools.append({
                'name': name,
                'dex': dex,
                'address': address,
                'tick': tick,
                'sqrt_price_x96': sqrt_price_x96,
                'liquidity': liquidity,
                'liquidity_usd': liquidity_usd_estimate,  # Используем оценку на основе reserve
                'reserve': reserve,
                'volume_24h': volume_24h,
                'price_from_tick': 1.0001 ** tick if abs(tick) < 1000000 else 0,
                'price_from_sqrt': (sqrt_price_x96 / (2 ** 96)) ** 2 if sqrt_price_x96 > 0 else 0
            })

    print(f"✅ Анализ завершен: {len(analyzed_pools)} V3 пулов с данными\n")

    # Сортируем по активной ликвидности
    top_pools = sorted(analyzed_pools, key=lambda x: x['liquidity'], reverse=True)[:10]

    print("=" * 90)
    print("  ТОП-10 ПУЛОВ ПО АКТИВНОЙ ЛИКВИДНОСТИ")
    print("=" * 90)
    print()

    for i, pool in enumerate(top_pools, 1):
        print(f"{'═' * 90}")
        print(f"  #{i}. {pool['name']}")
        print(f"{'═' * 90}")
        print(f"  DEX: {pool['dex']}")
        print(f"  Address: {pool['address']}")
        print()

        print(f"  💰 ФИНАНСОВЫЕ ПОКАЗАТЕЛИ:")
        print(f"     Reserve (TVL):         {format_number(pool['reserve'])}")
        print(f"     Volume 24h:            {format_number(pool['volume_24h'])}")
        print(f"     Volume/TVL Ratio:      {(pool['volume_24h']/pool['reserve'] if pool['reserve'] > 0 else 0):.2f}x")
        print()

        print(f"  💧 АКТИВНАЯ ЛИКВИДНОСТЬ:")
        print(f"     Liquidity (raw):       {pool['liquidity']:,}")
        print(f"     Liquidity (e18):       {pool['liquidity']/10**18:.2f}e18")
        print(f"     🔥 Liquidity (USD):    {format_number(pool['liquidity_usd'])} (оценка)")
        print(f"     % от TVL:              {(pool['liquidity_usd']/pool['reserve']*100 if pool['reserve'] > 0 else 0):.1f}%")
        print()

        print(f"  📊 ТЕКУЩИЕ ЦЕНЫ:")
        print(f"     Tick:                  {pool['tick']:,}")
        print(f"     SqrtPriceX96:          {pool['sqrt_price_x96']:,}")
        print(f"     Price (from tick):     {pool['price_from_tick']:.10f}")
        print(f"     Price (from sqrt):     {pool['price_from_sqrt']:.10f}")
        print()

        print(f"  🎯 ЧТО ОЗНАЧАЕТ ТИК {pool['tick']:,}:")

        if pool['tick'] < 0:
            print(f"     • Отрицательный тик = token0 ДЕШЕВЛЕ token1")
            print(f"     • Цена token0/token1: {pool['price_from_tick']:.10f}")
            print(f"     • Чем более отрицательный, тем дешевле token0")
        elif pool['tick'] > 0:
            print(f"     • Положительный тик = token0 ДОРОЖЕ token1")
            print(f"     • Цена token0/token1: {pool['price_from_tick']:.10f}")
            print(f"     • Чем больше тик, тем дороже token0")
        else:
            print(f"     • Тик = 0 означает примерно равные цены")

        print(f"     • Один тик = ~0.01% изменения цены")
        print(f"     • Диапазон активной ликвидности: ±несколько тиков")
        print()

    # Сводная статистика
    print("=" * 90)
    print("  СВОДНАЯ СТАТИСТИКА ТОП-10")
    print("=" * 90)
    print()

    total_liquidity_raw = sum(p['liquidity'] for p in top_pools)
    total_liquidity_usd = sum(p['liquidity_usd'] for p in top_pools)
    total_volume = sum(p['volume_24h'] for p in top_pools)
    total_reserve = sum(p['reserve'] for p in top_pools)

    print(f"  Общая активная ликвидность (raw):  {total_liquidity_raw:,}")
    print(f"  🔥 Общая активная ликвидность (USD): {format_number(total_liquidity_usd)}")
    print(f"  Общий объем торгов 24h:             {format_number(total_volume)}")
    print(f"  Общий TVL:                          {format_number(total_reserve)}")
    print(f"  Средняя активная ликвидность:       {format_number(total_liquidity_usd/10)}")
    print()

    # Пояснение
    print("=" * 90)
    print("  📚 ПОЯСНЕНИЕ")
    print("=" * 90)
    print("""
  ЧТО ТАКОЕ АКТИВНАЯ ЛИКВИДНОСТЬ:
  • В V3 пулах ликвидность сконцентрирована в ценовых диапазонах
  • Активная ликвидность - это капитал, доступный для торговли СЕЙЧАС
  • Измеряется в единицах L = sqrt(x * y), где x,y - количества токенов

  ЧТО ТАКОЕ ТИК:
  • Тик - это дискретная единица цены в Uniswap V3
  • Один тик ≈ 0.01% изменения цены
  • Формула цены: Price = 1.0001^tick
  • Отрицательный тик = token0 дешевле token1
  • Положительный тик = token0 дороже token1

  ОЦЕНКА В USD:
  • Показана приблизительная оценка на основе TVL пула
  • Реальная стоимость зависит от точных decimals токенов
  • Обычно ~30-70% от TVL составляет активную ликвидность
    """)

    print("=" * 90)


if __name__ == "__main__":
    main()
