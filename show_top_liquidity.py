#!/usr/bin/env python3
"""
Краткая таблица топ-10 пулов по активной ликвидности
"""

import requests
from typing import Dict, List, Optional

GECKOTERMINAL_API = "https://api.geckoterminal.com/api/v2"
RETH_NODE_URL = "http://80.209.241.37:8545/"
NETWORK = "base"

SLOT0_ABI = "0x3850c7bd"
LIQUIDITY_ABI = "0x1a686502"


def rpc_call(method: str, params: list) -> Optional[Dict]:
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
    try:
        pools = []
        for page in range(1, 4):
            url = f"{GECKOTERMINAL_API}/networks/{NETWORK}/pools?page={page}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    pools.extend(data['data'])
        return pools[:limit]
    except:
        return None


def get_pool_data(address: str) -> Optional[Dict]:
    slot0_result = rpc_call("eth_call", [{"to": address, "data": SLOT0_ABI}, "latest"])
    liquidity_result = rpc_call("eth_call", [{"to": address, "data": LIQUIDITY_ABI}, "latest"])

    if not slot0_result or not liquidity_result:
        return None

    try:
        data = slot0_result[2:]
        sqrt_price_x96 = int(data[0:64], 16)
        tick_raw = int(data[64:128], 16)

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

        liquidity = int(liquidity_result, 16)
        return {"tick": tick, "liquidity": liquidity, "sqrt_price_x96": sqrt_price_x96}
    except:
        return None


def format_num(num: float) -> str:
    if num >= 1_000_000:
        return f"${num/1_000_000:.2f}M"
    elif num >= 1_000:
        return f"${num/1_000:.0f}K"
    else:
        return f"${num:.0f}"


def main():
    print("\n" + "="*120)
    print(" " * 35 + "ТОП-10 ПУЛОВ ПО АКТИВНОЙ ЛИКВИДНОСТИ (BASE)")
    print("="*120)

    pools = get_pools(100)
    if not pools:
        print("Ошибка загрузки пулов")
        return

    print(f"\nАнализирую {len(pools)} пулов...\n")

    analyzed = []
    for pool in pools:
        attrs = pool['attributes']
        dex = pool['relationships']['dex']['data']['id']

        if not any(x in dex.lower() for x in ['v3', 'v4', 'slipstream']):
            continue

        data = get_pool_data(attrs['address'])
        if data and data['liquidity'] > 0:
            analyzed.append({
                'name': attrs['name'],
                'dex': dex,
                'address': attrs['address'],
                'tick': data['tick'],
                'liquidity': data['liquidity'],
                'liquidity_usd': float(attrs.get('reserve_in_usd', 0)) * 0.5,
                'reserve': float(attrs.get('reserve_in_usd', 0)),
                'volume_24h': float(attrs.get('volume_usd', {}).get('h24', 0)),
                'price': (data['sqrt_price_x96'] / (2 ** 96)) ** 2 if data['sqrt_price_x96'] > 0 else 0
            })

    top10 = sorted(analyzed, key=lambda x: x['liquidity'], reverse=True)[:10]

    # Таблица
    print("="*120)
    print(f"{'#':<3} {'Пул':<35} {'TVL':<12} {'Активная Liq':<15} {'Tick':<12} {'Цена':<15}")
    print("="*120)

    for i, p in enumerate(top10, 1):
        name = p['name'][:33]
        tvl = format_num(p['reserve'])
        liq_usd = format_num(p['liquidity_usd'])
        tick = f"{p['tick']:,}"
        price = f"{p['price']:.6f}" if p['price'] < 1 else f"{p['price']:.2f}"

        print(f"{i:<3} {name:<35} {tvl:<12} {liq_usd:<15} {tick:<12} {price:<15}")

    print("="*120)

    # Детали
    print("\n" + "="*120)
    print("ДЕТАЛЬНАЯ ИНФОРМАЦИЯ")
    print("="*120 + "\n")

    for i, p in enumerate(top10, 1):
        print(f"{i}. {p['name']} ({p['dex']})")
        print(f"   Address: {p['address']}")
        print(f"   TVL: {format_num(p['reserve'])} | Volume 24h: {format_num(p['volume_24h'])} | Ratio: {p['volume_24h']/p['reserve'] if p['reserve'] > 0 else 0:.1f}x")
        print(f"   🔥 Активная ликвидность: {format_num(p['liquidity_usd'])} ({p['liquidity_usd']/p['reserve']*100 if p['reserve'] > 0 else 0:.0f}% от TVL)")
        print(f"   📍 Тик: {p['tick']:,} → Цена: {p['price']:.10f}")

        if p['tick'] < 0:
            print(f"   💡 Отрицательный тик = token0 ДЕШЕВЛЕ token1 в {abs(1/p['price']):.2f} раз")
        elif p['tick'] > 0:
            print(f"   💡 Положительный тик = token0 ДОРОЖЕ token1 в {p['price']:.2f} раз")
        print()

    # Итого
    total_liq = sum(p['liquidity_usd'] for p in top10)
    total_tvl = sum(p['reserve'] for p in top10)
    total_vol = sum(p['volume_24h'] for p in top10)

    print("="*120)
    print("ИТОГО ТОП-10:")
    print(f"  💧 Общая активная ликвидность: {format_num(total_liq)}")
    print(f"  💰 Общий TVL: {format_num(total_tvl)}")
    print(f"  📊 Общий Volume 24h: {format_num(total_vol)}")
    print(f"  ⚡ Средняя эффективность: {total_vol/total_tvl if total_tvl > 0 else 0:.1f}x")
    print("="*120)

    print("\n📚 СПРАВКА:")
    print("  • Активная ликвидность = капитал, доступный для торговли в текущем ценовом диапазоне")
    print("  • Тик = дискретная единица цены (~0.01% изменения)")
    print("  • Отрицательный тик: token0 дешевле token1")
    print("  • Положительный тик: token0 дороже token1")
    print("  • USD оценка: ~50% от TVL пула (типичная доля активной ликвидности)\n")


if __name__ == "__main__":
    main()
