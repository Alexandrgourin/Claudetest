#!/usr/bin/env python3
"""
Получение lending протоколов на Base через DefiLlama API

Ищем протоколы которые:
1. Работают на Base
2. Категория: Lending, CDP
3. Имеют TVL для flashloans
"""

import requests
import json
import time
from typing import Dict, List, Optional
from collections import defaultdict

# DefiLlama API
API_BASE = "https://api.llama.fi"
CHAIN = "Base"

def api_call(endpoint: str) -> Optional[Dict]:
    """Make API call to DefiLlama"""
    url = f"{API_BASE}{endpoint}"

    try:
        response = requests.get(url, timeout=15)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"  ❌ Error {response.status_code}: {response.text[:100]}")
            return None

    except Exception as e:
        print(f"  ❌ Exception: {e}")
        return None

def get_all_protocols() -> List[Dict]:
    """Get all DeFi protocols"""
    print("📡 Получаю все DeFi протоколы...")

    data = api_call("/protocols")

    if data:
        print(f"  ✅ Найдено {len(data)} протоколов")
        return data

    return []

def get_protocol_details(slug: str) -> Optional[Dict]:
    """Get detailed info about specific protocol"""
    data = api_call(f"/protocol/{slug}")
    return data

def filter_base_lending_protocols(protocols: List[Dict]) -> List[Dict]:
    """Filter protocols on Base with Lending category"""
    print(f"\n🔍 Фильтрую lending протоколы на {CHAIN}...")

    lending_protocols = []

    for protocol in protocols:
        # Проверяем что работает на Base
        chains = protocol.get("chains", [])
        if CHAIN not in chains:
            continue

        # Проверяем категорию
        category = protocol.get("category", "")
        if category not in ["Lending", "CDP"]:
            continue

        lending_protocols.append(protocol)

    print(f"  ✅ Найдено {len(lending_protocols)} lending протоколов на {CHAIN}")

    return lending_protocols

def analyze_protocol_flashloan_support(protocol: Dict) -> Dict:
    """Analyze if protocol likely supports flashloans"""
    name = protocol.get("name", "").lower()
    slug = protocol.get("slug", "")

    # Известные протоколы с flashloan поддержкой
    flashloan_protocols = [
        "aave",
        "compound",
        "morpho",
        "euler",
        "radiant",
        "balancer",
        "uniswap"
    ]

    has_flashloan = any(fp in name for fp in flashloan_protocols)

    return {
        "likely_has_flashloan": has_flashloan,
        "confidence": "high" if has_flashloan else "unknown"
    }

def get_base_tvl_for_protocol(protocol_slug: str) -> Optional[float]:
    """Get TVL specifically for Base chain"""
    details = get_protocol_details(protocol_slug)

    if not details:
        return None

    # Ищем TVL для Base в chainTvls
    chain_tvls = details.get("chainTvls", {})
    base_tvl_data = chain_tvls.get(CHAIN, {})

    if base_tvl_data:
        # Берем последнее значение TVL
        tvl_values = base_tvl_data.get("tvl", [])
        if tvl_values:
            # Последнее значение - это [timestamp, tvl]
            return tvl_values[-1]["totalLiquidityUSD"] if isinstance(tvl_values[-1], dict) else tvl_values[-1][1]

    return None

def main():
    print("🚀 DefiLlama API - Поиск Lending протоколов на Base")
    print("=" * 80)

    # 1. Получаем все протоколы
    all_protocols = get_all_protocols()

    if not all_protocols:
        print("❌ Не удалось получить протоколы")
        return

    # 2. Фильтруем lending на Base
    lending_protocols = filter_base_lending_protocols(all_protocols)

    if not lending_protocols:
        print("❌ Не найдено lending протоколов на Base")
        return

    # 3. Сортируем по TVL
    lending_protocols.sort(key=lambda x: x.get("tvl", 0), reverse=True)

    # 4. Получаем детальную информацию
    print(f"\n📊 Топ {len(lending_protocols)} Lending протоколов на Base:")
    print("=" * 80)

    detailed_protocols = []

    for i, protocol in enumerate(lending_protocols, 1):
        name = protocol.get("name")
        slug = protocol.get("slug")
        category = protocol.get("category")
        tvl = protocol.get("tvl", 0)

        print(f"\n{i}. {name}")
        print(f"   Категория: {category}")
        print(f"   TVL (общий): ${tvl:,.0f}")
        print(f"   Slug: {slug}")

        # Получаем TVL для Base
        print(f"   Получаю TVL для Base...", end=" ")
        base_tvl = get_base_tvl_for_protocol(slug)

        if base_tvl:
            print(f"${base_tvl:,.0f}")
        else:
            print("н/д")

        # Проверяем поддержку flashloan
        flashloan_info = analyze_protocol_flashloan_support(protocol)

        if flashloan_info["likely_has_flashloan"]:
            print(f"   Flashloan: ✅ Вероятно поддерживается ({flashloan_info['confidence']})")
        else:
            print(f"   Flashloan: ❓ Неизвестно")

        # Добавляем URL
        url = protocol.get("url", "")
        if url:
            print(f"   URL: {url}")

        detailed_protocols.append({
            "name": name,
            "slug": slug,
            "category": category,
            "tvl_total": tvl,
            "tvl_base": base_tvl,
            "url": url,
            "flashloan_likely": flashloan_info["likely_has_flashloan"],
            "flashloan_confidence": flashloan_info["confidence"]
        })

        time.sleep(0.5)  # Rate limiting

    # 5. Сохраняем результаты
    print(f"\n💾 Сохраняю результаты...")

    with open("base_lending_protocols.json", "w") as f:
        json.dump({
            "chain": CHAIN,
            "total_protocols": len(detailed_protocols),
            "timestamp": time.time(),
            "protocols": detailed_protocols
        }, f, indent=2)

    print(f"  ✅ Сохранено в base_lending_protocols.json")

    # 6. Итоговая статистика
    print(f"\n{'='*80}")
    print("📈 ИТОГОВАЯ СТАТИСТИКА")
    print(f"{'='*80}\n")

    flashloan_protocols = [p for p in detailed_protocols if p["flashloan_likely"]]
    total_tvl = sum(p["tvl_base"] or 0 for p in detailed_protocols)

    print(f"Всего lending протоколов на Base: {len(detailed_protocols)}")
    print(f"С поддержкой flashloan: {len(flashloan_protocols)}")
    print(f"Общий TVL на Base: ${total_tvl:,.0f}")

    print(f"\n🎯 РЕКОМЕНДУЕМЫЕ ПРОТОКОЛЫ ДЛЯ FLASHLOAN:")
    print("-" * 80)

    for protocol in flashloan_protocols:
        tvl = protocol["tvl_base"] or protocol["tvl_total"]
        print(f"  • {protocol['name']:<20} TVL: ${tvl:>15,.0f}   {protocol['url']}")

    # 7. Получаем конкретные адреса для AAVE
    print(f"\n{'='*80}")
    print("🔍 ПОЛУЧЕНИЕ АДРЕСОВ КОНТРАКТОВ AAVE V3 НА BASE")
    print(f"{'='*80}\n")

    print("AAVE V3 на Base:")
    print("  Pool (основной контракт):        0xA238Dd80C259a72e81d7e4664a9801593F98d1c5")
    print("  PoolDataProvider:                 0x2d8A3C5677189723C4cB8873CfC9C8976FDF38Ac")
    print("  Oracle:                           0x2Cc0Fc26eD4563A5ce5e8bdcfe1A2878676Ae156")
    print("  ACLManager:                       0x43955b0899Ab7232E3a454cf84AedD22Ad46FD33")

    print("\nДругие lending протоколы можно найти через:")
    print("  - DefiLlama TVL API")
    print("  - Официальную документацию протоколов")
    print("  - Block explorers (BaseScan)")

    print(f"\n{'='*80}")
    print("✅ ГОТОВО!")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
