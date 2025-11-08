#!/usr/bin/env python3
"""
Детальный скан ценовых различий между DEX на Base
Показывает ВСЕ расхождения, даже если они не выгодны для арбитража
"""

import requests
from typing import Dict, List, Optional
from collections import defaultdict

GECKOTERMINAL_API = "https://api.geckoterminal.com/api/v2"
RETH_NODE_URL = "http://80.209.241.37:8545/"
NETWORK = "base"
SLOT0_ABI = "0x3850c7bd"


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


def get_pools(limit: int = 200) -> Optional[List[Dict]]:
    try:
        pools = []
        for page in range(1, 6):
            url = f"{GECKOTERMINAL_API}/networks/{NETWORK}/pools?page={page}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and data['data']:
                    pools.extend(data['data'])
                else:
                    break
        return pools[:limit]
    except:
        return None


def get_pool_price(address: str) -> Optional[float]:
    result = rpc_call("eth_call", [{"to": address, "data": SLOT0_ABI}, "latest"])
    if not result or result == "0x":
        return None
    try:
        data = result[2:]
        sqrt_price_x96 = int(data[0:64], 16)
        if sqrt_price_x96 == 0:
            return None
        sqrt_price = sqrt_price_x96 / (2 ** 96)
        return sqrt_price ** 2
    except:
        return None


def parse_fee(name: str) -> float:
    for fee_str, fee_val in [('0.01%', 0.0001), ('0.05%', 0.0005), ('0.3%', 0.003),
                             ('0.30%', 0.003), ('1%', 0.01), ('0.7%', 0.007), ('0.15%', 0.0015)]:
        if fee_str in name:
            return fee_val
    return 0.003


def normalize_pair(name: str) -> str:
    for fee in ['0.01%', '0.05%', '0.3%', '0.30%', '1%', '0.7%', '0.15%']:
        name = name.replace(fee, '').strip()
    return name


def format_num(num: float) -> str:
    if num >= 1_000_000:
        return f"${num/1_000_000:.2f}M"
    elif num >= 1_000:
        return f"${num/1_000:.0f}K"
    else:
        return f"${num:.0f}"


def main():
    print("\n" + "=" * 120)
    print(" " * 30 + "ДЕТАЛЬНЫЙ АНАЛИЗ ЦЕНОВЫХ РАСХОЖДЕНИЙ МЕЖДУ DEX")
    print("=" * 120)
    print()

    print("📊 Загрузка пулов...")
    pools = get_pools(200)

    if not pools:
        print("❌ Ошибка загрузки")
        return

    print(f"✅ Загружено {len(pools)} пулов\n")
    print("🔍 Получение цен из блокчейна через reth ноду...")
    print()

    # Собираем данные
    pairs = defaultdict(list)
    processed = 0

    for pool in pools:
        attrs = pool['attributes']
        dex = pool['relationships']['dex']['data']['id']
        name = attrs['name']
        normalized = normalize_pair(name)
        address = attrs['address']
        reserve = float(attrs.get('reserve_in_usd', 0))
        volume = float(attrs.get('volume_usd', {}).get('h24', 0))

        if reserve < 500:  # Пропускаем совсем мелкие пулы
            continue

        price = get_pool_price(address)
        processed += 1

        if processed % 20 == 0:
            print(f"   Обработано {processed} пулов...")

        if price and price > 0:
            pairs[normalized].append({
                'name': name,
                'dex': dex,
                'address': address,
                'price': price,
                'fee': parse_fee(name),
                'reserve': reserve,
                'volume': volume
            })

    print(f"\n✅ Получены цены для {len(pairs)} уникальных пар\n")

    # Анализируем различия
    price_differences = []

    for pair_name, pool_list in pairs.items():
        if len(pool_list) < 2:
            continue

        pool_list_sorted = sorted(pool_list, key=lambda x: x['price'])
        cheapest = pool_list_sorted[0]
        expensive = pool_list_sorted[-1]

        price_diff = ((expensive['price'] - cheapest['price']) / cheapest['price']) * 100
        total_fees = (cheapest['fee'] + expensive['fee']) * 100
        net_profit = price_diff - total_fees

        price_differences.append({
            'pair': pair_name,
            'pools': pool_list_sorted,
            'cheapest': cheapest,
            'expensive': expensive,
            'price_diff_percent': price_diff,
            'total_fees': total_fees,
            'net_profit': net_profit,
            'count': len(pool_list)
        })

    # Сортируем по разнице цен
    price_differences.sort(key=lambda x: x['price_diff_percent'], reverse=True)

    # Выводим ТОП-30
    print("=" * 120)
    print("📊 ТОП-30 ПАР С НАИБОЛЬШИМИ ЦЕНОВЫМИ РАСХОЖДЕНИЯМИ")
    print("=" * 120)
    print()

    print(f"{'Пара':<40} {'Пулов':<7} {'Разница':<10} {'Комиссии':<10} {'Прибыль':<10} {'Статус':<15}")
    print("-" * 120)

    arbitrage_count = 0

    for i, diff in enumerate(price_differences[:30], 1):
        pair = diff['pair'][:38]
        pools_count = diff['count']
        price_diff = f"{diff['price_diff_percent']:.3f}%"
        fees = f"{diff['total_fees']:.3f}%"
        net = f"{diff['net_profit']:.3f}%"

        if diff['net_profit'] > 0.01:  # Очень низкий порог
            status = "🔥 ВОЗМОЖЕН!"
            arbitrage_count += 1
        elif diff['net_profit'] > -0.1:
            status = "⚡ Близко"
        else:
            status = "❌ Нет"

        print(f"{pair:<40} {pools_count:<7} {price_diff:<10} {fees:<10} {net:<10} {status:<15}")

    print("=" * 120)
    print()

    # Детали по прибыльным
    if arbitrage_count > 0:
        print("=" * 120)
        print(f"🎯 ДЕТАЛИ ПО {arbitrage_count} ПОТЕНЦИАЛЬНЫМ ВОЗМОЖНОСТЯМ")
        print("=" * 120)
        print()

        for diff in price_differences:
            if diff['net_profit'] <= 0.01:
                continue

            print(f"{'─' * 120}")
            print(f"📍 {diff['pair']}")
            print(f"{'─' * 120}")

            print(f"\n💰 ЭКОНОМИКА:")
            print(f"   Разница цен:       {diff['price_diff_percent']:.4f}%")
            print(f"   Комиссии DEX:      {diff['total_fees']:.4f}%")
            print(f"   🔥 Чистая прибыль: {diff['net_profit']:.4f}%")

            buy = diff['cheapest']
            sell = diff['expensive']

            print(f"\n📊 ГДЕ КУПИТЬ (дешевле):")
            print(f"   {buy['name']}")
            print(f"   DEX:     {buy['dex']}")
            print(f"   Цена:    {buy['price']:.12f}")
            print(f"   TVL:     {format_num(buy['reserve'])} | Vol: {format_num(buy['volume'])}")

            print(f"\n📊 ГДЕ ПРОДАТЬ (дороже):")
            print(f"   {sell['name']}")
            print(f"   DEX:     {sell['dex']}")
            print(f"   Цена:    {sell['price']:.12f}")
            print(f"   TVL:     {format_num(sell['reserve'])} | Vol: {format_num(sell['volume'])}")

            # Показываем все пулы этой пары
            if diff['count'] > 2:
                print(f"\n📋 ВСЕ {diff['count']} ПУЛОВ ЭТОЙ ПАРЫ:")
                for j, pool in enumerate(diff['pools'], 1):
                    print(f"   {j}. {pool['dex'][:30]:<30} | Цена: {pool['price']:.12f} | Fee: {pool['fee']*100:.2f}% | TVL: {format_num(pool['reserve'])}")

            min_reserve = min(buy['reserve'], sell['reserve'])
            safe_size = min_reserve * 0.05  # 5% от меньшей ликвидности
            potential_profit = safe_size * (diff['net_profit'] / 100)

            print(f"\n💡 РАСЧЕТ:")
            print(f"   Безопасный размер сделки: {format_num(safe_size)} (5% от {format_num(min_reserve)})")
            print(f"   Потенциальная прибыль:    {format_num(potential_profit)}")
            print(f"   Gas cost (оценка):        $1.00")
            print(f"   Чистая прибыль:           {format_num(max(0, potential_profit - 1))}")

            print()

    # Анализ по DEX
    print("=" * 120)
    print("📈 АНАЛИЗ ЭФФЕКТИВНОСТИ DEX")
    print("=" * 120)
    print()

    dex_prices = defaultdict(lambda: {'count': 0, 'avg_price_pos': 0})

    for diff in price_differences:
        for pool in diff['pools']:
            dex_prices[pool['dex']]['count'] += 1

    print("ТОП DEX по количеству пулов:")
    for dex, stats in sorted(dex_prices.items(), key=lambda x: x[1]['count'], reverse=True)[:10]:
        print(f"  {dex[:50]:<50} - {stats['count']} пулов")

    print()
    print("=" * 120)
    print("💡 ВЫВОДЫ И РЕКОМЕНДАЦИИ")
    print("=" * 120)
    print()

    if arbitrage_count > 0:
        print(f"✅ Найдено {arbitrage_count} потенциальных возможностей для арбитража!")
        print()
        print("   Однако учтите:")
        print("   • Прибыль очень маленькая (<0.5% обычно)")
        print("   • Gas costs (~$1) могут съесть всю прибыль на малых суммах")
        print("   • Нужна быстрая исполнительная инфраструктура")
        print("   • Цены могут измениться за секунды")
        print()
        print("   Для прибыльного арбитража нужно:")
        print("   1. Использовать flash loans для увеличения размера сделки")
        print("   2. Автоматизировать через MEV bot")
        print("   3. Мониторить мемпул для опережения других ботов")
        print("   4. Оптимизировать gas costs")
    else:
        print("❌ Прямых арбитражных возможностей не найдено")
        print()
        print("   Это означает что:")
        print("   • Рынок эффективен, боты работают хорошо")
        print("   • Ликвидность хорошо распределена между DEX")
        print("   • Арбитражеры быстро выравнивают цены")
        print()
        print("   Альтернативные стратегии:")
        print("   1. Мониторить менее ликвидные токены")
        print("   2. Искать возможности во время волатильности")
        print("   3. Рассмотреть трехсторонний арбитраж (triangular)")
        print("   4. MEV - опережать большие сделки")

    print()
    print("=" * 120)


if __name__ == "__main__":
    main()
