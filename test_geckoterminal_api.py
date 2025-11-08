#!/usr/bin/env python3
"""
Тестовый скрипт для работы с GeckoTerminal API
Получение данных о самых ликвидных пулах на Base
"""

import requests
import json
from datetime import datetime

BASE_URL = "https://api.geckoterminal.com/api/v2"
NETWORK = "base"

def get_pools(sort_by=None, page=1, limit=10):
    """
    Получить список пулов на Base

    Параметры сортировки (sort_by):
    - h24_volume_usd_desc - по объему торгов за 24 часа (по убыванию)
    - h24_tx_count_desc - по количеству транзакций за 24 часа
    - h6_volume_usd_desc - по объему за 6 часов
    - h1_volume_usd_desc - по объему за 1 час
    - None - по умолчанию (скорее всего по ликвидности)
    """
    url = f"{BASE_URL}/networks/{NETWORK}/pools"
    params = {"page": page}

    if sort_by:
        params["sort"] = sort_by

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Ошибка при запросе: {e}")
        return None

def format_number(num):
    """Форматировать число с разделителями"""
    try:
        return f"{float(num):,.2f}"
    except:
        return str(num)

def format_large_number(num):
    """Форматировать большие числа (миллионы, тысячи)"""
    try:
        num = float(num)
        if num >= 1_000_000:
            return f"${num/1_000_000:.2f}M"
        elif num >= 1_000:
            return f"${num/1_000:.2f}K"
        else:
            return f"${num:.2f}"
    except:
        return str(num)

def print_pool_info(pool, index):
    """Вывести информацию о пуле"""
    attrs = pool["attributes"]

    print(f"\n{index}. {attrs['name']}")
    print(f"   Address: {attrs['address']}")
    print(f"   DEX: {pool['relationships']['dex']['data']['id']}")
    print(f"   Reserve (TVL): {format_large_number(attrs['reserve_in_usd'])}")

    # Объемы торгов
    volume = attrs.get('volume_usd', {})
    print(f"   Volume:")
    print(f"      24h: {format_large_number(volume.get('h24', 0))}")
    print(f"      6h:  {format_large_number(volume.get('h6', 0))}")
    print(f"      1h:  {format_large_number(volume.get('h1', 0))}")

    # Транзакции за 24 часа
    tx = attrs.get('transactions', {}).get('h24', {})
    total_tx = tx.get('buys', 0) + tx.get('sells', 0)
    print(f"   Transactions 24h: {total_tx:,} (Buys: {tx.get('buys', 0):,}, Sells: {tx.get('sells', 0):,})")

    # Изменение цены
    price_change = attrs.get('price_change_percentage', {})
    print(f"   Price Change:")
    print(f"      24h: {price_change.get('h24', 'N/A')}%")
    print(f"      6h:  {price_change.get('h6', 'N/A')}%")
    print(f"      1h:  {price_change.get('h1', 'N/A')}%")

    # Цены токенов
    print(f"   Base Token Price: ${format_number(attrs.get('base_token_price_usd', 0))}")
    print(f"   Quote Token Price: ${format_number(attrs.get('quote_token_price_usd', 0))}")

def main():
    print("=" * 80)
    print("GeckoTerminal API - Анализ ликвидных пулов на Base")
    print("=" * 80)

    # Тест 1: Топ пулов по объему торгов за 24 часа
    print("\n" + "=" * 80)
    print("1. ТОП-5 ПУЛОВ ПО ОБЪЕМУ ТОРГОВ ЗА 24 ЧАСА")
    print("=" * 80)

    data = get_pools(sort_by="h24_volume_usd_desc", page=1)
    if data and 'data' in data:
        for i, pool in enumerate(data['data'][:5], 1):
            print_pool_info(pool, i)

    # Тест 2: Топ пулов по количеству транзакций
    print("\n" + "=" * 80)
    print("2. ТОП-5 ПУЛОВ ПО КОЛИЧЕСТВУ ТРАНЗАКЦИЙ ЗА 24 ЧАСА")
    print("=" * 80)

    data = get_pools(sort_by="h24_tx_count_desc", page=1)
    if data and 'data' in data:
        for i, pool in enumerate(data['data'][:5], 1):
            print_pool_info(pool, i)

    # Тест 3: Топ пулов по объему за 1 час (самые активные сейчас)
    print("\n" + "=" * 80)
    print("3. ТОП-5 САМЫХ АКТИВНЫХ ПУЛОВ ЗА ПОСЛЕДНИЙ ЧАС")
    print("=" * 80)

    data = get_pools(sort_by="h1_volume_usd_desc", page=1)
    if data and 'data' in data:
        for i, pool in enumerate(data['data'][:5], 1):
            print_pool_info(pool, i)

    # Тест 4: Пулы по умолчанию (вероятно по ликвидности)
    print("\n" + "=" * 80)
    print("4. ТОП-5 ПУЛОВ ПО УМОЛЧАНИЮ (предположительно по ликвидности)")
    print("=" * 80)

    data = get_pools(page=1)
    if data and 'data' in data:
        pools_with_reserve = [(pool, float(pool['attributes']['reserve_in_usd']))
                               for pool in data['data'][:20]]
        pools_with_reserve.sort(key=lambda x: x[1], reverse=True)

        for i, (pool, reserve) in enumerate(pools_with_reserve[:5], 1):
            print_pool_info(pool, i)

    # Статистика по доступным параметрам сортировки
    print("\n" + "=" * 80)
    print("ДОСТУПНЫЕ ПАРАМЕТРЫ СОРТИРОВКИ:")
    print("=" * 80)
    print("""
Параметры для sort= в API запросе:

1. h24_volume_usd_desc    - По объему торгов за 24 часа (убывание)
2. h24_tx_count_desc      - По количеству транзакций за 24 часа (убывание)
3. h6_volume_usd_desc     - По объему торгов за 6 часов (убывание)
4. h1_volume_usd_desc     - По объему торгов за 1 час (убывание)
5. m5_volume_usd_desc     - По объему торгов за 5 минут (убывание)

Примечание: Параметр reserve_usd_desc может не поддерживаться напрямую,
но можно отсортировать результаты локально по полю reserve_in_usd.

Пример запроса:
GET https://api.geckoterminal.com/api/v2/networks/base/pools?sort=h24_volume_usd_desc&page=1
    """)

    print("\n" + "=" * 80)
    print("Тестирование завершено!")
    print("=" * 80)

if __name__ == "__main__":
    main()
