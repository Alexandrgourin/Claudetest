#!/usr/bin/env python3
"""
Глубокий анализ всех Lending протоколов на Base через DefiLlama API

Собираем:
1. TVL breakdown по активам
2. APY для lending/borrowing
3. Supported assets
4. Contract addresses
5. Historical TVL data
6. Fees и revenue
7. Все доступные метрики
"""

import requests
import json
import time
from typing import Dict, List, Optional
from collections import defaultdict

# DefiLlama API
API_BASE = "https://api.llama.fi"
YIELDS_API = "https://yields.llama.fi"
CHAIN = "Base"

def api_call(url: str, timeout: int = 15) -> Optional[Dict]:
    """Make API call with error handling"""
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"  ⚠️  Status {response.status_code}")
            return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

def get_protocol_detailed_info(slug: str) -> Optional[Dict]:
    """Get very detailed protocol information"""
    print(f"  📊 Получаю детальные данные для {slug}...")

    url = f"{API_BASE}/protocol/{slug}"
    data = api_call(url)

    if not data:
        return None

    # Извлекаем важную информацию
    info = {
        "slug": slug,
        "name": data.get("name"),
        "symbol": data.get("symbol"),
        "category": data.get("category"),
        "chains": data.get("chains", []),
        "tvl": data.get("tvl"),
        "chainTvls": data.get("chainTvls", {}),
        "mcap": data.get("mcap"),
        "twitter": data.get("twitter"),
        "url": data.get("url"),
        "description": data.get("description"),
        "audits": data.get("audits"),
        "audit_links": data.get("audit_links"),
        "gecko_id": data.get("gecko_id"),
        "cmcId": data.get("cmcId"),
        "listedAt": data.get("listedAt"),
        "raises": data.get("raises"),
        "metrics": data.get("metrics", {}),
    }

    # TVL breakdown для Base
    if "chainTvls" in data and CHAIN in data["chainTvls"]:
        base_data = data["chainTvls"][CHAIN]
        if "tvl" in base_data:
            tvl_history = base_data["tvl"]
            if tvl_history:
                # Берем последнее значение
                latest = tvl_history[-1]
                info["base_tvl_current"] = latest.get("totalLiquidityUSD", 0) if isinstance(latest, dict) else latest[1] if isinstance(latest, list) else 0
                info["base_tvl_history_points"] = len(tvl_history)

    # Token breakdown
    if "tokensInUsd" in data:
        info["tokens_breakdown"] = data["tokensInUsd"]

    if "currentChainTvls" in data:
        info["current_chain_tvls"] = data["currentChainTvls"]

    return info

def get_yields_data(protocol_slug: str = None) -> List[Dict]:
    """Get APY/yields data from yields.llama.fi"""
    print(f"\n📈 Получаю данные о доходности (APY)...")

    url = f"{YIELDS_API}/pools"
    data = api_call(url, timeout=30)

    if not data or "data" not in data:
        return []

    pools = data["data"]

    # Фильтруем только Base и Lending
    base_lending_pools = []

    for pool in pools:
        if pool.get("chain") == CHAIN:
            # Проверяем что это lending
            project = pool.get("project", "").lower()
            if any(keyword in project for keyword in ["aave", "compound", "morpho", "euler", "lending", "radiant", "moonwell"]):
                base_lending_pools.append({
                    "pool_id": pool.get("pool"),
                    "project": pool.get("project"),
                    "symbol": pool.get("symbol"),
                    "apy": pool.get("apy"),
                    "apyBase": pool.get("apyBase"),
                    "apyReward": pool.get("apyReward"),
                    "tvl": pool.get("tvlUsd"),
                    "exposure": pool.get("exposure"),
                    "pool_meta": pool.get("poolMeta"),
                    "underlyingTokens": pool.get("underlyingTokens"),
                    "rewardTokens": pool.get("rewardTokens"),
                })

    print(f"  ✅ Найдено {len(base_lending_pools)} lending пулов на Base")

    return base_lending_pools

def get_fees_revenue(slug: str) -> Optional[Dict]:
    """Get fees and revenue data"""
    # DefiLlama fees API
    url = f"https://api.llama.fi/overview/fees/{slug}"
    data = api_call(url)

    if data:
        return {
            "total_fees": data.get("totalDataChart", []),
            "protocols": data.get("protocols", [])
        }

    return None

def analyze_protocol_deeply(slug: str, name: str) -> Dict:
    """Deep analysis of single protocol"""
    print(f"\n{'='*80}")
    print(f"🔍 Глубокий анализ: {name}")
    print(f"{'='*80}")

    result = {
        "slug": slug,
        "name": name,
        "detailed_info": None,
        "fees_revenue": None,
        "analysis": {}
    }

    # 1. Детальная информация о протоколе
    detailed = get_protocol_detailed_info(slug)
    if detailed:
        result["detailed_info"] = detailed

        # Анализ
        base_tvl = detailed.get("base_tvl_current", 0)
        total_tvl = detailed.get("tvl", 0)

        # TVL может быть списком, берем последнее значение
        if isinstance(total_tvl, list) and total_tvl:
            total_tvl = total_tvl[-1].get("totalLiquidityUSD", 0) if isinstance(total_tvl[-1], dict) else total_tvl[-1][1] if isinstance(total_tvl[-1], list) else 0
        elif not isinstance(total_tvl, (int, float)):
            total_tvl = 0

        if total_tvl > 0:
            base_share = (base_tvl / total_tvl) * 100
            result["analysis"]["base_tvl_share"] = f"{base_share:.2f}%"

        result["analysis"]["has_audit"] = bool(detailed.get("audits") or detailed.get("audit_links"))
        result["analysis"]["has_token"] = bool(detailed.get("gecko_id") or detailed.get("symbol"))
        result["analysis"]["social_presence"] = bool(detailed.get("twitter"))

        print(f"  TVL на Base: ${base_tvl:,.0f}")
        print(f"  TVL всего: ${total_tvl:,.0f}")
        if detailed.get("audits"):
            print(f"  Аудиты: {len(detailed['audits'])}")
        if detailed.get("twitter"):
            print(f"  Twitter: @{detailed['twitter']}")

    time.sleep(0.5)  # Rate limiting

    return result

def main():
    print("🚀 Глубокий анализ Lending протоколов на Base через DefiLlama")
    print("=" * 80)

    # 1. Загружаем список протоколов из предыдущего анализа
    print("\n📂 Загружаю список lending протоколов...")

    try:
        with open("base_lending_protocols.json", "r") as f:
            lending_data = json.load(f)
            protocols = lending_data.get("protocols", [])
    except:
        print("❌ Файл base_lending_protocols.json не найден")
        return

    print(f"  ✅ Загружено {len(protocols)} протоколов")

    # 2. Получаем APY данные для всех
    yields_data = get_yields_data()

    # Группируем по проектам
    yields_by_project = defaultdict(list)
    for pool in yields_data:
        project = pool["project"].lower()
        yields_by_project[project].append(pool)

    # 3. Глубокий анализ топ-20 протоколов
    print(f"\n{'='*80}")
    print("📊 ДЕТАЛЬНЫЙ АНАЛИЗ ТОП-20 ПРОТОКОЛОВ")
    print(f"{'='*80}")

    # Сортируем по TVL на Base
    protocols_sorted = sorted(
        [p for p in protocols if p.get("tvl_base")],
        key=lambda x: x.get("tvl_base", 0),
        reverse=True
    )[:20]

    detailed_results = []

    for i, protocol in enumerate(protocols_sorted, 1):
        slug = protocol["slug"]
        name = protocol["name"]

        print(f"\n{i}. {name} (${protocol.get('tvl_base', 0):,.0f} TVL)")

        # Глубокий анализ
        analysis = analyze_protocol_deeply(slug, name)

        # Добавляем APY данные
        project_key = slug.replace("-", "").replace(" ", "").lower()
        if project_key in yields_by_project:
            analysis["yields"] = yields_by_project[project_key]
            print(f"  APY пулов: {len(yields_by_project[project_key])}")

            # Показываем топ пулы по APY
            top_pools = sorted(yields_by_project[project_key], key=lambda x: x.get("apy", 0), reverse=True)[:3]
            for pool in top_pools:
                print(f"    • {pool['symbol']}: {pool.get('apy', 0):.2f}% APY (TVL: ${pool.get('tvl', 0):,.0f})")

        detailed_results.append(analysis)

    # 4. Сохраняем все результаты
    print(f"\n{'='*80}")
    print("💾 Сохраняю детальные результаты...")
    print(f"{'='*80}")

    output = {
        "chain": CHAIN,
        "total_protocols_analyzed": len(detailed_results),
        "yields_pools_found": len(yields_data),
        "timestamp": time.time(),
        "protocols": detailed_results,
        "yields_summary": {
            "total_pools": len(yields_data),
            "by_project": {k: len(v) for k, v in yields_by_project.items()},
            "all_pools": yields_data
        }
    }

    with open("base_lending_deep_analysis.json", "w") as f:
        json.dump(output, f, indent=2)

    print("✅ Сохранено в base_lending_deep_analysis.json")

    # 5. Итоговая статистика
    print(f"\n{'='*80}")
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print(f"{'='*80}\n")

    # Подсчет протоколов с аудитами
    audited = sum(1 for r in detailed_results if r.get("analysis", {}).get("has_audit"))
    with_token = sum(1 for r in detailed_results if r.get("analysis", {}).get("has_token"))
    with_social = sum(1 for r in detailed_results if r.get("analysis", {}).get("social_presence"))

    print(f"Проанализировано протоколов: {len(detailed_results)}")
    print(f"С аудитами: {audited}/{len(detailed_results)} ({audited/len(detailed_results)*100:.0f}%)")
    print(f"С токенами: {with_token}/{len(detailed_results)} ({with_token/len(detailed_results)*100:.0f}%)")
    print(f"С Twitter: {with_social}/{len(detailed_results)} ({with_social/len(detailed_results)*100:.0f}%)")

    print(f"\nAPY пулов найдено: {len(yields_data)}")

    if yields_data:
        avg_apy = sum(p.get("apy", 0) for p in yields_data) / len(yields_data)
        max_apy_pool = max(yields_data, key=lambda x: x.get("apy", 0))

        print(f"Средний APY: {avg_apy:.2f}%")
        print(f"Максимальный APY: {max_apy_pool.get('apy', 0):.2f}% ({max_apy_pool.get('project')} - {max_apy_pool.get('symbol')})")

    # Топ проекты по количеству пулов
    print(f"\n📊 Топ проектов по количеству пулов:")
    top_projects = sorted(yields_by_project.items(), key=lambda x: len(x[1]), reverse=True)[:5]
    for project, pools in top_projects:
        total_tvl = sum(p.get("tvl", 0) for p in pools)
        avg_apy = sum(p.get("apy", 0) for p in pools) / len(pools) if pools else 0
        print(f"  • {project}: {len(pools)} пулов, ${total_tvl:,.0f} TVL, {avg_apy:.2f}% avg APY")

    # Рекомендации для flashloan
    print(f"\n{'='*80}")
    print("🎯 РЕКОМЕНДАЦИИ ДЛЯ FLASHLOAN СТРАТЕГИИ")
    print(f"{'='*80}\n")

    print("Лучшие протоколы для ликвидаций:")
    for i, protocol in enumerate(protocols_sorted[:5], 1):
        name = protocol["name"]
        tvl = protocol.get("tvl_base", 0)
        flashloan = "✅" if protocol.get("flashloan_likely") else "❓"

        # Находим APY данные
        project_key = protocol["slug"].replace("-", "").replace(" ", "").lower()
        pool_count = len(yields_by_project.get(project_key, []))

        print(f"{i}. {name}")
        print(f"   TVL: ${tvl:,.0f}")
        print(f"   Flashloan: {flashloan}")
        print(f"   APY пулов: {pool_count}")

        if protocol.get("flashloan_likely"):
            print(f"   💡 Рекомендуется для liquidation hunting!")
        print()

    print("\n✅ Анализ завершен!")

if __name__ == "__main__":
    main()
