#!/usr/bin/env python3
"""
Анализ объемов торговли в пулах и оценка JIT возможностей

Использует данные о 24h объемах и количестве транзакций для оценки
среднего размера сделок и потенциала JIT стратегии.
"""

import requests
import json
from typing import Dict, List
from collections import defaultdict

GECKOTERMINAL_API = "https://api.geckoterminal.com/api/v2"
FLASH_LOAN_FEE = 0.0005
GAS_COST_USD = 2
TARGET_FEE_SHARE = 0.70


def get_pools_with_stats():
    """Получить пулы с детальной статистикой"""
    url = f"{GECKOTERMINAL_API}/networks/base/pools"
    response = requests.get(url, params={"page": 1}, timeout=10)

    if response.status_code != 200:
        return []

    data = response.json()
    pools = []

    for pool in data.get("data", []):
        attrs = pool.get("attributes", {})

        # Получаем транзакции
        transactions = attrs.get("transactions", {})
        tx_24h = transactions.get("h24", {})

        tx_count_24h = tx_24h.get("buys", 0) + tx_24h.get("sells", 0)

        # Парсим volume
        volume_data = attrs.get("volume_usd", {})
        volume_24h = 0
        if isinstance(volume_data, dict):
            volume_24h = float(volume_data.get("h24", 0))
        elif isinstance(volume_data, (int, float)):
            volume_24h = float(volume_data)

        # Парсим fee
        name = attrs.get("name", "")
        fee_percent = 0.3
        if "0.01%" in name:
            fee_percent = 0.01
        elif "0.05%" in name:
            fee_percent = 0.05
        elif "0.1%" in name:
            fee_percent = 0.1
        elif "0.3%" in name:
            fee_percent = 0.3
        elif "1%" in name:
            fee_percent = 1.0

        # Средний размер трейда
        avg_trade_size = (volume_24h / tx_count_24h) if tx_count_24h > 0 else 0

        pools.append({
            "name": name,
            "dex": attrs.get("dex", ""),
            "reserve_usd": float(attrs.get("reserve_in_usd", 0)),
            "volume_24h": volume_24h,
            "tx_count_24h": tx_count_24h,
            "avg_trade_size": avg_trade_size,
            "fee_percent": fee_percent,
            "price_change_24h": float(attrs.get("price_change_percentage", {}).get("h24", 0) or 0),
        })

    return pools


def calculate_jit_profit(trade_size, pool_reserve, fee_percent):
    """Рассчитать JIT прибыль для одного трейда"""
    if pool_reserve <= 0 or trade_size <= 0:
        return {
            "required_liquidity": 0,
            "your_fees": 0,
            "net_profit": 0,
            "roi": 0,
        }

    active_liquidity = pool_reserve * 0.5
    fee_decimal = fee_percent / 100
    total_fees = trade_size * fee_decimal
    required_liquidity = (active_liquidity * TARGET_FEE_SHARE) / (1 - TARGET_FEE_SHARE)

    total_liquidity = active_liquidity + required_liquidity
    if total_liquidity == 0:
        return {
            "required_liquidity": 0,
            "your_fees": 0,
            "net_profit": 0,
            "roi": 0,
        }

    your_share = required_liquidity / total_liquidity
    your_fees = total_fees * your_share
    flash_loan_fee = required_liquidity * FLASH_LOAN_FEE
    net_profit = your_fees - flash_loan_fee - GAS_COST_USD
    roi = (net_profit / (flash_loan_fee + GAS_COST_USD) * 100) if (flash_loan_fee + GAS_COST_USD) > 0 else 0

    return {
        "required_liquidity": required_liquidity,
        "your_fees": your_fees,
        "net_profit": net_profit,
        "roi": roi,
    }


def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                                                                  ║
    ║      АНАЛИЗ ОБЪЕМОВ И JIT ПОТЕНЦИАЛА ПУЛОВ НА BASE              ║
    ║                                                                  ║
    ║  Оценка среднего размера трейдов и потенциальной прибыли        ║
    ║  от JIT Liquidity стратегии на основе статистики                ║
    ║                                                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)

    print("📊 Загрузка статистики пулов...")
    pools = get_pools_with_stats()
    print(f"✅ Загружено {len(pools)} пулов\n")

    # Фильтруем пулы с хорошими объемами
    active_pools = [p for p in pools if p["volume_24h"] > 100000 and p["tx_count_24h"] > 10]

    print(f"📈 Активных пулов (>$100K volume, >10 tx/24h): {len(active_pools)}\n")

    # Анализируем потенциал
    jit_analysis = []

    for pool in active_pools:
        # Оцениваем JIT для среднего трейда
        avg_jit = calculate_jit_profit(
            pool["avg_trade_size"],
            pool["reserve_usd"],
            pool["fee_percent"]
        )

        # Оцениваем JIT для крупного трейда (10x средний)
        large_jit = calculate_jit_profit(
            pool["avg_trade_size"] * 10,
            pool["reserve_usd"],
            pool["fee_percent"]
        )

        # Оцениваем JIT для очень крупного трейда (50x средний)
        xlarge_jit = calculate_jit_profit(
            pool["avg_trade_size"] * 50,
            pool["reserve_usd"],
            pool["fee_percent"]
        )

        # Оцениваем сколько крупных трейдов в день (консервативно - 10% от total)
        estimated_large_trades_per_day = pool["tx_count_24h"] * 0.10

        # Дневная прибыль от JIT (если catchить все крупные трейды)
        daily_profit_potential = max(0, large_jit["net_profit"]) * estimated_large_trades_per_day

        jit_analysis.append({
            "pool": pool,
            "avg_jit": avg_jit,
            "large_jit": large_jit,
            "xlarge_jit": xlarge_jit,
            "estimated_large_trades_per_day": estimated_large_trades_per_day,
            "daily_profit_potential": daily_profit_potential,
        })

    # Сортируем по дневному потенциалу
    sorted_analysis = sorted(jit_analysis, key=lambda x: x["daily_profit_potential"], reverse=True)

    # Показываем топ-20
    print(f"{'='*140}")
    print(f"🔥 ТОП-20 ПУЛОВ ПО ПОТЕНЦИАЛУ JIT ПРИБЫЛИ")
    print(f"{'='*140}\n")

    print(f"{'Пул':<45} {'Volume 24h':>12} {'Tx/24h':>7} {'Avg Trade':>10} {'Profit/Trade':>12} {'Daily Potential':>15}")
    print(f"{'-'*140}")

    for i, analysis in enumerate(sorted_analysis[:20], 1):
        pool = analysis["pool"]
        large_profit = analysis["large_jit"]["net_profit"]

        print(f"{pool['name'][:43]:<45} ${pool['volume_24h']:>10,.0f} {pool['tx_count_24h']:>7,} ${pool['avg_trade_size']:>8,.0f} ${large_profit:>10,.0f} ${analysis['daily_profit_potential']:>13,.0f}")

    # Суммарная статистика
    total_daily_potential = sum(a["daily_profit_potential"] for a in sorted_analysis if a["daily_profit_potential"] > 0)

    print(f"\n{'='*140}")
    print(f"📊 СУММАРНАЯ СТАТИСТИКА")
    print(f"{'='*140}\n")

    print(f"💰 Потенциальная дневная прибыль (топ-20):  ${total_daily_potential:,.2f}")
    print(f"📅 Потенциальная месячная прибыль:          ${total_daily_potential * 30:,.2f}")
    print(f"📈 Потенциальная годовая прибыль:           ${total_daily_potential * 365:,.2f}")

    print(f"\n💡 ВАЖНО:")
    print(f"   Это ТЕОРЕТИЧЕСКИЙ максимум если catchить ВСЕ крупные трейды")
    print(f"   Реалистичный success rate с flashblocks: 30-50%")
    print(f"   → Реалистичная дневная прибыль:  ${total_daily_potential * 0.4:,.2f}")
    print(f"   → Реалистичная месячная прибыль: ${total_daily_potential * 0.4 * 30:,.2f}")
    print(f"   → Реалистичная годовая прибыль:  ${total_daily_potential * 0.4 * 365:,.2f}")

    # Детали топ-5
    print(f"\n{'='*140}")
    print(f"🔍 ДЕТАЛЬНЫЙ АНАЛИЗ ТОП-5 ПУЛОВ")
    print(f"{'='*140}\n")

    for i, analysis in enumerate(sorted_analysis[:5], 1):
        pool = analysis["pool"]
        avg_jit = analysis["avg_jit"]
        large_jit = analysis["large_jit"]
        xlarge_jit = analysis["xlarge_jit"]

        print(f"\n{'─'*140}")
        print(f"#{i}. {pool['name']}")
        print(f"{'─'*140}")
        print(f"DEX:                  {pool['dex']}")
        print(f"TVL:                  ${pool['reserve_usd']:,.2f}")
        print(f"24h Volume:           ${pool['volume_24h']:,.2f}")
        print(f"24h Transactions:     {pool['tx_count_24h']:,}")
        print(f"Fee Tier:             {pool['fee_percent']}%")
        print(f"Price Change 24h:     {pool['price_change_24h']:.2f}%")

        print(f"\n📊 СРЕДНИЙ ТРЕЙД (${pool['avg_trade_size']:,.0f}):")
        print(f"   Net Profit:        ${avg_jit['net_profit']:,.2f}")
        print(f"   ROI:               {avg_jit['roi']:.0f}%")

        print(f"\n💰 КРУПНЫЙ ТРЕЙД (${pool['avg_trade_size']*10:,.0f} - 10x средний):")
        print(f"   Required Liquidity: ${large_jit['required_liquidity']:,.0f}")
        print(f"   Your Fees:          ${large_jit['your_fees']:,.2f}")
        print(f"   🔥 Net Profit:      ${large_jit['net_profit']:,.2f}")
        print(f"   📈 ROI:             {large_jit['roi']:.0f}%")

        print(f"\n🚀 ОЧЕНЬ КРУПНЫЙ ТРЕЙД (${pool['avg_trade_size']*50:,.0f} - 50x средний):")
        print(f"   Required Liquidity: ${xlarge_jit['required_liquidity']:,.0f}")
        print(f"   Your Fees:          ${xlarge_jit['your_fees']:,.2f}")
        print(f"   🔥🔥 Net Profit:    ${xlarge_jit['net_profit']:,.2f}")
        print(f"   📈 ROI:             {xlarge_jit['roi']:.0f}%")

        print(f"\n💡 ДНЕВНОЙ ПОТЕНЦИАЛ:")
        print(f"   Estimated large trades/day: {analysis['estimated_large_trades_per_day']:.1f}")
        print(f"   Potential daily profit:     ${analysis['daily_profit_potential']:,.2f}")

    # Рекомендации
    print(f"\n{'='*140}")
    print(f"✅ РЕКОМЕНДАЦИИ")
    print(f"{'='*140}\n")

    # Топ пулы по разным критериям
    top_by_volume = sorted(active_pools, key=lambda x: x["volume_24h"], reverse=True)[:3]
    top_by_avg_trade = sorted(active_pools, key=lambda x: x["avg_trade_size"], reverse=True)[:3]

    print(f"🎯 ЛУЧШИЕ ПУЛЫ ДЛЯ JIT:")
    print(f"\n   По объему торговли:")
    for p in top_by_volume:
        print(f"   • {p['name'][:50]} - ${p['volume_24h']:,.0f}/день")

    print(f"\n   По среднему размеру трейда:")
    for p in top_by_avg_trade:
        print(f"   • {p['name'][:50]} - ${p['avg_trade_size']:,.0f}/трейд")

    print(f"\n   По дневному потенциалу прибыли:")
    for analysis in sorted_analysis[:3]:
        print(f"   • {analysis['pool']['name'][:50]} - ${analysis['daily_profit_potential']:,.0f}/день")

    print(f"\n💡 NEXT STEPS:")
    print(f"   1. Запустите real-time детектор на этих пулах:")
    print(f"      python3 jit_opportunity_detector.py 60")
    print(f"\n   2. Мониторьте flashblocks для крупных swaps:")
    print(f"      • Минимальный размер: $50K-100K")
    print(f"      • Фокус на пулах с 0.01-0.05% fee")
    print(f"\n   3. Разработайте JIT smart contract для автоматизации")

    print(f"\n{'='*140}\n")


if __name__ == "__main__":
    main()
