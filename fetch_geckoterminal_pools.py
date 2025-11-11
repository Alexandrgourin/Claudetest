#!/usr/bin/env python3
"""
Получение всех DeFi пулов на Base через GeckoTerminal API

API Documentation: https://apiguide.geckoterminal.com/
Base URL: https://api.geckoterminal.com/api/v2/
Rate Limit: 30 calls/minute
"""

import requests
import json
import time
from typing import Dict, List, Optional
from collections import defaultdict

# GeckoTerminal API
API_BASE = "https://api.geckoterminal.com/api/v2"
NETWORK = "base"

# Rate limiting
CALLS_PER_MINUTE = 30
DELAY_BETWEEN_CALLS = 60 / CALLS_PER_MINUTE + 0.1  # ~2.1 seconds

def api_call(endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
    """Make API call with rate limiting"""
    url = f"{API_BASE}{endpoint}"

    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; DeFi-Research-Bot/1.0)"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            print(f"  ⚠️  Rate limit hit, waiting 60s...")
            time.sleep(60)
            return api_call(endpoint, params)
        else:
            print(f"  ❌ Error {response.status_code}: {response.text[:100]}")
            return None

    except Exception as e:
        print(f"  ❌ Exception: {e}")
        return None

def get_networks() -> List[Dict]:
    """Get list of all supported networks"""
    print("📡 Получаю список поддерживаемых сетей...")

    data = api_call("/networks")

    if data and "data" in data:
        networks = data["data"]
        print(f"  ✅ Найдено {len(networks)} сетей")

        # Ищем Base
        for network in networks:
            attrs = network.get("attributes", {})
            if attrs.get("identifier") == NETWORK:
                print(f"\n  🎯 Base network найдена:")
                print(f"     Name: {attrs.get('name')}")
                print(f"     ID: {attrs.get('identifier')}")
                print(f"     Chain ID: {attrs.get('coingecko_asset_platform_id')}")

        return networks

    return []

def get_trending_pools(limit: int = 100) -> List[Dict]:
    """Get trending pools on Base"""
    print(f"\n📊 Получаю топ {limit} трендовых пулов на Base...")

    pools = []
    page = 1

    while len(pools) < limit:
        print(f"  Страница {page}...")

        data = api_call(f"/networks/{NETWORK}/trending_pools", {"page": page})

        if not data or "data" not in data:
            break

        page_pools = data["data"]
        if not page_pools:
            break

        pools.extend(page_pools)
        print(f"  ✅ Получено {len(page_pools)} пулов (всего: {len(pools)})")

        page += 1
        time.sleep(DELAY_BETWEEN_CALLS)

        if len(page_pools) < 10:  # Последняя страница
            break

    return pools[:limit]

def get_new_pools(limit: int = 100) -> List[Dict]:
    """Get newly created pools on Base"""
    print(f"\n🆕 Получаю последние {limit} новых пулов на Base...")

    pools = []
    page = 1

    while len(pools) < limit:
        print(f"  Страница {page}...")

        data = api_call(f"/networks/{NETWORK}/new_pools", {"page": page})

        if not data or "data" not in data:
            break

        page_pools = data["data"]
        if not page_pools:
            break

        pools.extend(page_pools)
        print(f"  ✅ Получено {len(page_pools)} пулов (всего: {len(pools)})")

        page += 1
        time.sleep(DELAY_BETWEEN_CALLS)

        if len(page_pools) < 10:
            break

    return pools[:limit]

def get_top_pools(limit: int = 100) -> List[Dict]:
    """Get top pools by volume/liquidity on Base"""
    print(f"\n💰 Получаю топ {limit} пулов по объему на Base...")

    pools = []
    page = 1

    while len(pools) < limit:
        print(f"  Страница {page}...")

        data = api_call(f"/networks/{NETWORK}/pools", {"page": page})

        if not data or "data" not in data:
            break

        page_pools = data["data"]
        if not page_pools:
            break

        pools.extend(page_pools)
        print(f"  ✅ Получено {len(page_pools)} пулов (всего: {len(pools)})")

        page += 1
        time.sleep(DELAY_BETWEEN_CALLS)

        if len(page_pools) < 10:
            break

    return pools[:limit]

def search_pools_by_token(token: str) -> List[Dict]:
    """Search pools containing specific token"""
    print(f"\n🔍 Поиск пулов с токеном: {token}...")

    data = api_call("/search/pools", {"query": token, "network": NETWORK})

    if data and "data" in data:
        pools = data["data"]
        print(f"  ✅ Найдено {len(pools)} пулов")
        return pools

    return []

def analyze_pool_data(pools: List[Dict]) -> Dict:
    """Analyze pool data structure"""
    print("\n📋 Анализирую структуру данных пулов...")

    if not pools:
        return {}

    # Берем первый пул для анализа
    sample_pool = pools[0]

    print("\n🔍 Пример структуры пула:")
    print(json.dumps(sample_pool, indent=2)[:1000])
    print("...\n")

    # Группируем пулы по DEX
    dex_pools = defaultdict(list)
    token_pairs = defaultdict(int)

    for pool in pools:
        attrs = pool.get("attributes", {})
        relationships = pool.get("relationships", {})

        dex_id = relationships.get("dex", {}).get("data", {}).get("id", "unknown")
        dex_pools[dex_id].append(pool)

        name = attrs.get("name", "")
        token_pairs[name] += 1

    print(f"📊 Статистика пулов:")
    print(f"  Всего пулов: {len(pools)}")
    print(f"  Уникальных DEX: {len(dex_pools)}")
    print(f"  Уникальных пар: {len(token_pairs)}")

    print(f"\n💱 Топ DEX по количеству пулов:")
    for dex, pools_list in sorted(dex_pools.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
        print(f"  {dex}: {len(pools_list)} пулов")

    return {
        "total_pools": len(pools),
        "dex_count": len(dex_pools),
        "dex_pools": dict(dex_pools),
        "token_pairs": dict(token_pairs)
    }

def extract_pool_info(pool: Dict) -> Dict:
    """Extract useful information from pool data"""
    attrs = pool.get("attributes", {})
    relationships = pool.get("relationships", {})

    return {
        "address": attrs.get("address"),
        "name": attrs.get("name"),
        "dex_id": relationships.get("dex", {}).get("data", {}).get("id"),
        "base_token_symbol": attrs.get("base_token_symbol"),
        "quote_token_symbol": attrs.get("quote_token_symbol"),
        "base_token_address": attrs.get("base_token_price_native_currency"),
        "pool_created_at": attrs.get("pool_created_at"),
        "reserve_in_usd": attrs.get("reserve_in_usd"),
        "volume_usd_24h": attrs.get("volume_usd", {}).get("h24"),
        "price_change_24h": attrs.get("price_change_percentage", {}).get("h24"),
        "transactions_24h": attrs.get("transactions", {}).get("h24", {}).get("buys", 0) +
                           attrs.get("transactions", {}).get("h24", {}).get("sells", 0),
    }

def save_pools_data(pools: List[Dict], filename: str):
    """Save pools data to JSON file"""
    print(f"\n💾 Сохраняю данные в {filename}...")

    pool_info = [extract_pool_info(pool) for pool in pools]

    with open(filename, 'w') as f:
        json.dump({
            "total": len(pool_info),
            "timestamp": time.time(),
            "network": NETWORK,
            "pools": pool_info
        }, f, indent=2)

    print(f"  ✅ Сохранено {len(pool_info)} пулов")

def main():
    print("🚀 GeckoTerminal API - Получение DeFi пулов на Base")
    print("=" * 80)

    # 1. Проверяем доступность сети
    get_networks()

    # 2. Получаем топ пулы
    top_pools = get_top_pools(limit=50)

    if top_pools:
        analyze_pool_data(top_pools)
        save_pools_data(top_pools, "base_top_pools.json")

    # 3. Получаем трендовые пулы
    trending_pools = get_trending_pools(limit=30)

    if trending_pools:
        save_pools_data(trending_pools, "base_trending_pools.json")

    # 4. Поиск пулов с конкретными токенами
    important_tokens = ["WETH", "USDC", "cbBTC", "AAVE", "USDT"]

    print("\n" + "=" * 80)
    print("🔍 Поиск пулов для важных токенов:")
    print("=" * 80)

    all_token_pools = {}

    for token in important_tokens:
        pools = search_pools_by_token(token)
        all_token_pools[token] = pools

        if pools:
            print(f"\n  💎 {token} - найдено {len(pools)} пулов:")
            for pool in pools[:5]:  # Показываем топ 5
                info = extract_pool_info(pool)
                reserve = float(info['reserve_in_usd']) if info['reserve_in_usd'] else 0
                print(f"    {info['address'][:10]}... | {info['name']:<30} | ${reserve:>15,.0f}")

        time.sleep(DELAY_BETWEEN_CALLS)

    # Сохраняем все результаты
    save_pools_data(
        [pool for pools in all_token_pools.values() for pool in pools],
        "base_important_tokens_pools.json"
    )

    print("\n" + "=" * 80)
    print("✅ ГОТОВО!")
    print("=" * 80)
    print("\nСозданные файлы:")
    print("  1. base_top_pools.json - топ пулы по объему")
    print("  2. base_trending_pools.json - трендовые пулы")
    print("  3. base_important_tokens_pools.json - пулы с важными токенами")

    print("\n📊 Доступные данные для каждого пула:")
    print("  - address: адрес пула")
    print("  - name: название пары (например WETH/USDC)")
    print("  - dex_id: название DEX (Uniswap, Aerodrome, etc)")
    print("  - reserve_in_usd: ликвидность в USD")
    print("  - volume_usd_24h: объем за 24 часа")
    print("  - price_change_24h: изменение цены за 24 часа (%)")
    print("  - transactions_24h: количество транзакций")
    print("  - base/quote_token: информация о токенах в паре")

if __name__ == "__main__":
    main()
