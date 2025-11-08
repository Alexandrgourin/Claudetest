#!/usr/bin/env python3
"""
Детальный анализ концентрированной ликвидности в топ-10 пулах Base Network
Использует GeckoTerminal API + reth ноду для получения on-chain данных
"""

import requests
import json
from typing import Dict, List, Optional
from datetime import datetime

# Конфигурация
GECKOTERMINAL_API = "https://api.geckoterminal.com/api/v2"
RETH_NODE_URL = "http://80.209.241.37:8545/"
NETWORK = "base"

# ABI сигнатуры
SLOT0_ABI = "0x3850c7bd"  # slot0()
LIQUIDITY_ABI = "0x1a686502"  # liquidity()
TOKEN0_ABI = "0x0dfe1681"  # token0()
TOKEN1_ABI = "0xd21220a7"  # token1()


def rpc_call(method: str, params: list, request_id: int = 1) -> Optional[Dict]:
    """Выполнить JSON-RPC запрос к reth ноде"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": request_id
    }

    try:
        response = requests.post(RETH_NODE_URL, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()

        if "error" in result:
            return None

        return result.get("result")
    except:
        return None


def get_top_pools_by_volume(limit: int = 10) -> Optional[List[Dict]]:
    """Получить топ пулы по объему торгов"""
    try:
        url = f"{GECKOTERMINAL_API}/networks/{NETWORK}/pools?page=1"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if 'data' not in data:
            return None

        pools = sorted(
            data['data'],
            key=lambda x: float(x['attributes'].get('volume_usd', {}).get('h24', 0)),
            reverse=True
        )

        return pools[:limit]
    except:
        return None


def get_pool_slot0(pool_address: str) -> Optional[Dict]:
    """Получить slot0 пула"""
    call_data = {"to": pool_address, "data": SLOT0_ABI}
    result = rpc_call("eth_call", [call_data, "latest"])

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


def get_pool_liquidity(pool_address: str) -> Optional[int]:
    """Получить текущую активную ликвидность"""
    call_data = {"to": pool_address, "data": LIQUIDITY_ABI}
    result = rpc_call("eth_call", [call_data, "latest"])

    if not result or result == "0x":
        return None

    try:
        return int(result, 16)
    except:
        return None


def calculate_price_from_sqrt(sqrt_price_x96: int) -> float:
    """Вычислить цену из sqrtPriceX96"""
    if sqrt_price_x96 == 0:
        return 0
    sqrt_price = sqrt_price_x96 / (2 ** 96)
    return sqrt_price ** 2


def calculate_price_from_tick(tick: int) -> float:
    """Вычислить цену из тика"""
    return 1.0001 ** tick


def format_number(num: float, prefix: str = "$") -> str:
    """Форматировать число"""
    if num >= 1_000_000_000:
        return f"{prefix}{num/1_000_000_000:.2f}B"
    elif num >= 1_000_000:
        return f"{prefix}{num/1_000_000:.2f}M"
    elif num >= 1_000:
        return f"{prefix}{num/1_000:.2f}K"
    else:
        return f"{prefix}{num:.2f}"


def format_liquidity(liquidity: int) -> str:
    """Форматировать значение ликвидности"""
    if liquidity >= 10**24:
        return f"{liquidity/10**24:.2f}e24"
    elif liquidity >= 10**21:
        return f"{liquidity/10**21:.2f}e21"
    elif liquidity >= 10**18:
        return f"{liquidity/10**18:.2f}e18"
    else:
        return f"{liquidity:,}"


def print_separator(char: str = "=", length: int = 90):
    """Печать разделителя"""
    print(char * length)


def main():
    print_separator()
    print("  ДЕТАЛЬНЫЙ АНАЛИЗ КОНЦЕНТРИРОВАННОЙ ЛИКВИДНОСТИ - BASE NETWORK")
    print_separator()
    print(f"  Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  RPC Endpoint: {RETH_NODE_URL}")
    print_separator()
    print()

    # Получение пулов
    print("📊 Загрузка топ-10 пулов по объему торгов за 24 часа...")
    pools = get_top_pools_by_volume(10)

    if not pools:
        print("❌ Не удалось получить данные о пулах")
        return

    print(f"✅ Получено {len(pools)} пулов\n")

    # Анализ каждого пула
    results = []

    for i, pool in enumerate(pools, 1):
        attrs = pool['attributes']
        pool_address = attrs['address']
        pool_name = attrs['name']
        dex = pool['relationships']['dex']['data']['id']

        volume_24h = float(attrs.get('volume_usd', {}).get('h24', 0))
        reserve = float(attrs.get('reserve_in_usd', 0))

        print(f"[{i}/10] Анализ пула: {pool_name}")
        print(f"      DEX: {dex}")
        print(f"      Address: {pool_address}")

        # Проверка типа пула
        is_v3 = any(x in dex.lower() for x in ['v3', 'v4', 'slipstream'])

        if not is_v3:
            print(f"      ⚠ Пул V2 (не поддерживает концентрированную ликвидность)\n")
            continue

        # Получение данных из ноды
        slot0 = get_pool_slot0(pool_address)
        liquidity = get_pool_liquidity(pool_address)

        if slot0 and liquidity:
            tick = slot0['tick']
            sqrt_price_x96 = slot0['sqrtPriceX96']

            price_sqrt = calculate_price_from_sqrt(sqrt_price_x96)
            price_tick = calculate_price_from_tick(tick)

            result = {
                'rank': i,
                'name': pool_name,
                'dex': dex,
                'address': pool_address,
                'reserve': reserve,
                'volume_24h': volume_24h,
                'tick': tick,
                'liquidity': liquidity,
                'price_sqrt': price_sqrt,
                'price_tick': price_tick,
                'sqrt_price_x96': sqrt_price_x96
            }
            results.append(result)

            print(f"      ✅ Данные получены")
        else:
            print(f"      ❌ Не удалось получить данные из ноды")

        print()

    # Вывод результатов
    print_separator()
    print("  РЕЗУЛЬТАТЫ АНАЛИЗА")
    print_separator()
    print()

    for r in results:
        print(f"#{r['rank']}. {r['name']}")
        print(f"    DEX: {r['dex']}")
        print(f"    ────────────────────────────────────────────────────────────────")
        print(f"    📊 Рыночные данные:")
        print(f"       Reserve (TVL):    {format_number(r['reserve'])}")
        print(f"       Volume 24h:       {format_number(r['volume_24h'])}")
        print(f"       Volume/TVL Ratio: {(r['volume_24h']/r['reserve'] if r['reserve'] > 0 else 0):.2f}x")
        print()
        print(f"    🎯 Данные из ноды:")
        print(f"       Current Tick:     {r['tick']:,}")
        print(f"       SqrtPriceX96:     {r['sqrt_price_x96']:,}")
        print(f"       Price (sqrt):     {r['price_sqrt']:.10f}")
        print(f"       Price (tick):     {r['price_tick']:.10f}")
        print()
        print(f"    💧 Ликвидность:")
        print(f"       Active Liquidity: {format_liquidity(r['liquidity'])}")
        print(f"       Liquidity Value:  ~{format_number(r['reserve'] * 0.5)}")  # Упрощенная оценка
        print()

    # Сводная статистика
    print_separator()
    print("  СВОДНАЯ СТАТИСТИКА")
    print_separator()
    print()

    total_volume = sum(r['volume_24h'] for r in results)
    total_reserve = sum(r['reserve'] for r in results)
    avg_liquidity = sum(r['liquidity'] for r in results) / len(results) if results else 0

    print(f"  Всего проанализировано пулов: {len(results)}")
    print(f"  Общий объем торгов за 24ч:    {format_number(total_volume)}")
    print(f"  Общая ликвидность (TVL):      {format_number(total_reserve)}")
    print(f"  Средняя активная ликвидность: {format_liquidity(int(avg_liquidity))}")
    print()

    # Топ-3 по ликвидности
    top_liquidity = sorted(results, key=lambda x: x['liquidity'], reverse=True)[:3]
    print("  🏆 Топ-3 пула по активной ликвидности:")
    for i, r in enumerate(top_liquidity, 1):
        print(f"     {i}. {r['name']} - {format_liquidity(r['liquidity'])}")
    print()

    # Топ-3 по эффективности (Volume/TVL)
    top_efficiency = sorted(results, key=lambda x: x['volume_24h']/x['reserve'] if x['reserve'] > 0 else 0, reverse=True)[:3]
    print("  ⚡ Топ-3 пула по эффективности (Volume/TVL):")
    for i, r in enumerate(top_efficiency, 1):
        ratio = r['volume_24h']/r['reserve'] if r['reserve'] > 0 else 0
        print(f"     {i}. {r['name']} - {ratio:.2f}x")
    print()

    print_separator()
    print()


if __name__ == "__main__":
    main()
