#!/usr/bin/env python3
"""
Поиск арбитражных возможностей на Base DEX
Сравнивает цены одинаковых пар токенов в разных пулах
"""

import requests
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

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


def get_pools(limit: int = 200) -> Optional[List[Dict]]:
    """Получить максимум пулов для анализа"""
    try:
        pools = []
        for page in range(1, 6):  # Первые 5 страниц
            url = f"{GECKOTERMINAL_API}/networks/{NETWORK}/pools?page={page}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and data['data']:
                    pools.extend(data['data'])
                else:
                    break
            else:
                break
        return pools[:limit]
    except:
        return None


def get_pool_price(address: str) -> Optional[float]:
    """Получить текущую цену из пула"""
    result = rpc_call("eth_call", [{"to": address, "data": SLOT0_ABI}, "latest"])

    if not result or result == "0x":
        return None

    try:
        data = result[2:]
        if len(data) < 64:
            return None

        sqrt_price_x96 = int(data[0:64], 16)

        if sqrt_price_x96 == 0:
            return None

        # Вычисляем цену
        sqrt_price = sqrt_price_x96 / (2 ** 96)
        price = sqrt_price ** 2

        return price
    except:
        return None


def parse_fee_from_name(pool_name: str) -> float:
    """Извлечь комиссию из названия пула"""
    if '0.01%' in pool_name:
        return 0.0001
    elif '0.05%' in pool_name:
        return 0.0005
    elif '0.3%' in pool_name or '0.30%' in pool_name:
        return 0.003
    elif '1%' in pool_name:
        return 0.01
    else:
        return 0.003  # По умолчанию 0.3%


def normalize_pair(name: str) -> str:
    """Нормализовать название пары (убрать комиссии)"""
    # Убираем процентные комиссии
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
    print("=" * 120)
    print(" " * 40 + "ПОИСК АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ НА BASE")
    print("=" * 120)
    print()

    print("📊 Загрузка пулов...")
    pools = get_pools(200)

    if not pools:
        print("❌ Не удалось загрузить пулы")
        return

    print(f"✅ Загружено {len(pools)} пулов")
    print()
    print("🔍 Анализ цен в пулах...")
    print()

    # Группируем пулы по парам токенов
    pairs = defaultdict(list)

    for pool in pools:
        attrs = pool['attributes']
        dex = pool['relationships']['dex']['data']['id']

        name = attrs['name']
        normalized_pair = normalize_pair(name)
        address = attrs['address']
        reserve = float(attrs.get('reserve_in_usd', 0))
        volume_24h = float(attrs.get('volume_usd', {}).get('h24', 0))
        fee = parse_fee_from_name(name)

        # Получаем цену из ноды
        price = get_pool_price(address)

        if price and price > 0 and reserve > 1000:  # Только пулы с ликвидностью > $1K
            pairs[normalized_pair].append({
                'name': name,
                'dex': dex,
                'address': address,
                'price': price,
                'fee': fee,
                'reserve': reserve,
                'volume_24h': volume_24h
            })

    print(f"✅ Проанализировано {len(pairs)} уникальных пар токенов")
    print()

    # Ищем арбитражные возможности
    arbitrage_opportunities = []

    for pair_name, pool_list in pairs.items():
        if len(pool_list) < 2:
            continue  # Нужно минимум 2 пула для арбитража

        # Сортируем по цене
        pool_list_sorted = sorted(pool_list, key=lambda x: x['price'])

        # Сравниваем самую низкую и самую высокую цену
        cheapest = pool_list_sorted[0]
        most_expensive = pool_list_sorted[-1]

        # Вычисляем разницу цен
        price_diff_percent = ((most_expensive['price'] - cheapest['price']) / cheapest['price']) * 100

        # Вычисляем суммарные комиссии
        total_fees = (cheapest['fee'] + most_expensive['fee']) * 100  # В процентах

        # Потенциальная прибыль = разница цен - комиссии
        net_profit_percent = price_diff_percent - total_fees

        # Только если прибыль > 0.05% (учитывая gas)
        if net_profit_percent > 0.05:
            # Минимальная ликвидность определяет макс размер сделки
            min_reserve = min(cheapest['reserve'], most_expensive['reserve'])

            arbitrage_opportunities.append({
                'pair': pair_name,
                'buy_pool': cheapest,
                'sell_pool': most_expensive,
                'price_diff_percent': price_diff_percent,
                'total_fees_percent': total_fees,
                'net_profit_percent': net_profit_percent,
                'min_reserve': min_reserve
            })

    # Сортируем по прибыли
    arbitrage_opportunities.sort(key=lambda x: x['net_profit_percent'], reverse=True)

    # Выводим результаты
    if not arbitrage_opportunities:
        print("=" * 120)
        print("❌ АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ НЕ НАЙДЕНО")
        print("=" * 120)
        print()
        print("Это нормально! Рынок эффективен, арбитражные боты быстро выравнивают цены.")
        print("Попробуйте:")
        print("  • Анализировать в моменты высокой волатильности")
        print("  • Искать среди менее ликвидных токенов")
        print("  • Рассмотреть flash loans для увеличения размера сделки")
    else:
        print("=" * 120)
        print(f"🎯 НАЙДЕНО {len(arbitrage_opportunities)} АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ!")
        print("=" * 120)
        print()

        for i, opp in enumerate(arbitrage_opportunities[:20], 1):  # Топ-20
            print(f"{'─' * 120}")
            print(f"#{i}. {opp['pair']}")
            print(f"{'─' * 120}")

            print(f"\n💰 ПРИБЫЛЬ:")
            print(f"   Разница цен:      {opp['price_diff_percent']:.3f}%")
            print(f"   Комиссии:         {opp['total_fees_percent']:.3f}%")
            print(f"   🔥 Чистая прибыль: {opp['net_profit_percent']:.3f}%")

            print(f"\n📍 КУПИТЬ ЗДЕСЬ (дешевле):")
            buy = opp['buy_pool']
            print(f"   DEX:      {buy['dex']}")
            print(f"   Pool:     {buy['name']}")
            print(f"   Address:  {buy['address']}")
            print(f"   Цена:     {buy['price']:.10f}")
            print(f"   Комиссия: {buy['fee']*100:.2f}%")
            print(f"   TVL:      {format_num(buy['reserve'])}")
            print(f"   Volume:   {format_num(buy['volume_24h'])}")

            print(f"\n📍 ПРОДАТЬ ЗДЕСЬ (дороже):")
            sell = opp['sell_pool']
            print(f"   DEX:      {sell['dex']}")
            print(f"   Pool:     {sell['name']}")
            print(f"   Address:  {sell['address']}")
            print(f"   Цена:     {sell['price']:.10f}")
            print(f"   Комиссия: {sell['fee']*100:.2f}%")
            print(f"   TVL:      {format_num(sell['reserve'])}")
            print(f"   Volume:   {format_num(sell['volume_24h'])}")

            print(f"\n💡 СТРАТЕГИЯ:")
            print(f"   1. Купить на {buy['dex'][:20]}")
            print(f"   2. Продать на {sell['dex'][:20]}")
            print(f"   3. Прибыль: {opp['net_profit_percent']:.3f}%")
            print(f"   4. Макс размер сделки: {format_num(opp['min_reserve'] * 0.1)} (10% от меньшей ликвидности)")

            # Оценка потенциальной прибыли
            max_trade_size = opp['min_reserve'] * 0.1
            potential_profit = max_trade_size * (opp['net_profit_percent'] / 100)

            print(f"   5. Потенциальная прибыль: {format_num(potential_profit)}")

            print()

        # Статистика
        print("=" * 120)
        print("📊 СТАТИСТИКА АРБИТРАЖА")
        print("=" * 120)
        print()

        total_opportunities = len(arbitrage_opportunities)
        avg_profit = sum(o['net_profit_percent'] for o in arbitrage_opportunities) / total_opportunities
        max_profit_opp = arbitrage_opportunities[0]

        print(f"  Всего возможностей:        {total_opportunities}")
        print(f"  Средняя прибыль:           {avg_profit:.3f}%")
        print(f"  Максимальная прибыль:      {max_profit_opp['net_profit_percent']:.3f}% ({max_profit_opp['pair']})")
        print()

        # Группировка по DEX
        dex_pairs = defaultdict(int)
        for opp in arbitrage_opportunities:
            dex_pair = f"{opp['buy_pool']['dex'].split('-')[0]} → {opp['sell_pool']['dex'].split('-')[0]}"
            dex_pairs[dex_pair] += 1

        print("  Популярные пары DEX для арбитража:")
        for dex_pair, count in sorted(dex_pairs.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"    {dex_pair}: {count} возможностей")

    print()
    print("=" * 120)
    print("⚠️  ВАЖНЫЕ ЗАМЕЧАНИЯ:")
    print("=" * 120)
    print("""
  1. Gas costs НЕ учтены в расчетах (обычно $0.50-2.00 на Base)
  2. Проскальзывание может уменьшить прибыль на больших объемах
  3. Цены меняются быстро - возможность может исчезнуть за секунды
  4. Нужен быстрый исполнитель (MEV bot, flash loan)
  5. Рассмотрите использование flash loans для увеличения капитала
  6. Проверьте актуальность цен перед исполнением
  7. На практике боты уже выполняют большинство арбитражей
    """)
    print("=" * 120)


if __name__ == "__main__":
    main()
