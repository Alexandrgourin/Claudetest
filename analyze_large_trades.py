#!/usr/bin/env python3
"""
Анализ крупных трейдов на Base через GeckoTerminal API

Получает реальные крупные сделки и рассчитывает потенциальную прибыль от JIT
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List
from collections import defaultdict

GECKOTERMINAL_API = "https://api.geckoterminal.com/api/v2"
MIN_TRADE_SIZE_USD = 50000
FLASH_LOAN_FEE = 0.0005  # 0.05%
GAS_COST_USD = 2
TARGET_FEE_SHARE = 0.70


def get_top_pools(limit=50):
    """Получить топ пулы"""
    url = f"{GECKOTERMINAL_API}/networks/base/pools"
    response = requests.get(url, params={"page": 1}, timeout=10)

    if response.status_code != 200:
        return []

    data = response.json()
    pools = []

    for pool in data.get("data", [])[:limit]:
        attrs = pool.get("attributes", {})
        pools.append({
            "address": attrs.get("address"),
            "name": attrs.get("name", ""),
            "dex": attrs.get("dex", ""),
            "reserve_usd": float(attrs.get("reserve_in_usd", 0)),
            "volume_24h": float(attrs.get("volume_usd", {}).get("h24", 0)) if isinstance(attrs.get("volume_usd"), dict) else 0,
        })

    return pools


def get_pool_trades(pool_address, limit=100):
    """Получить последние трейды для пула"""
    url = f"{GECKOTERMINAL_API}/networks/base/pools/{pool_address}/trades"

    try:
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            return []

        data = response.json()
        trades = []

        for trade in data.get("data", [])[:limit]:
            attrs = trade.get("attributes", {})

            # Парсим объем
            volume_usd = 0
            volume_in_usd = attrs.get("volume_in_usd")
            if volume_in_usd:
                try:
                    volume_usd = float(volume_in_usd)
                except:
                    pass

            if volume_usd < MIN_TRADE_SIZE_USD:
                continue

            trades.append({
                "tx_hash": attrs.get("tx_hash"),
                "block_number": attrs.get("block_number"),
                "timestamp": attrs.get("block_timestamp"),
                "volume_usd": volume_usd,
                "kind": attrs.get("kind", ""),
                "from_token": attrs.get("from_token_amount", ""),
                "to_token": attrs.get("to_token_amount", ""),
            })

        return trades

    except Exception as e:
        print(f"   ⚠️  Ошибка получения трейдов для {pool_address}: {e}")
        return []


def calculate_jit_profit(trade_volume_usd, pool_reserve_usd, fee_percent):
    """Рассчитать JIT прибыль"""
    # Активная ликвидность (~50% от TVL)
    active_liquidity = pool_reserve_usd * 0.5

    # Комиссии
    fee_decimal = fee_percent / 100
    total_fees = trade_volume_usd * fee_decimal

    # Требуемая ликвидность для TARGET_FEE_SHARE
    required_liquidity = (active_liquidity * TARGET_FEE_SHARE) / (1 - TARGET_FEE_SHARE)

    # Доля комиссий
    your_share = required_liquidity / (active_liquidity + required_liquidity)

    # Прибыль
    your_fees = total_fees * your_share
    flash_loan_fee = required_liquidity * FLASH_LOAN_FEE

    net_profit = your_fees - flash_loan_fee - GAS_COST_USD

    roi = (net_profit / (flash_loan_fee + GAS_COST_USD) * 100) if (flash_loan_fee + GAS_COST_USD) > 0 else 0

    return {
        "trade_volume": trade_volume_usd,
        "required_liquidity": required_liquidity,
        "total_fees": total_fees,
        "your_fees": your_fees,
        "net_profit": net_profit,
        "roi": roi,
        "profitable": net_profit > 50
    }


def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                                                                  ║
    ║         АНАЛИЗ КРУПНЫХ ТРЕЙДОВ НА BASE (GeckoTerminal)          ║
    ║                                                                  ║
    ║  Анализирует реальные крупные сделки и рассчитывает             ║
    ║  потенциальную прибыль от JIT Liquidity стратегии                ║
    ║                                                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)

    print(f"⚙️  Параметры:")
    print(f"   Min trade size:      ${MIN_TRADE_SIZE_USD:,}")
    print(f"   Target fee share:    {TARGET_FEE_SHARE*100}%")
    print(f"   Flash loan fee:      {FLASH_LOAN_FEE*100}%")
    print(f"   Gas cost estimate:   ${GAS_COST_USD}\n")

    # Загружаем пулы
    print("📊 Загрузка топ пулов...")
    pools = get_top_pools(30)
    print(f"✅ Загружено {len(pools)} пулов\n")

    # Показываем топ-10
    sorted_pools = sorted(pools, key=lambda x: x["volume_24h"], reverse=True)
    print("📊 ТОП-10 ПУЛОВ ПО ОБЪЕМУ:\n")
    for i, pool in enumerate(sorted_pools[:10], 1):
        print(f"   {i}. {pool['name'][:50]:50} - ${pool['volume_24h']:>12,.0f}")

    # Анализируем трейды
    print(f"\n🔍 Анализ крупных трейдов...\n")

    all_opportunities = []
    pools_analyzed = 0

    for i, pool in enumerate(pools, 1):
        pool_name = pool["name"]
        pool_address = pool["address"]

        print(f"   [{i}/{len(pools)}] {pool_name[:50]:<50}", end="")

        # Парсим fee из имени
        fee_percent = 0.3
        if "0.01%" in pool_name:
            fee_percent = 0.01
        elif "0.05%" in pool_name:
            fee_percent = 0.05
        elif "0.1%" in pool_name:
            fee_percent = 0.1
        elif "0.3%" in pool_name:
            fee_percent = 0.3
        elif "1%" in pool_name:
            fee_percent = 1.0

        # Получаем трейды
        trades = get_pool_trades(pool_address, 100)

        if not trades:
            print(" - нет данных")
            continue

        large_trades = [t for t in trades if t["volume_usd"] >= MIN_TRADE_SIZE_USD]

        print(f" - {len(large_trades)} крупных")

        # Анализируем каждый трейд
        for trade in large_trades:
            jit_calc = calculate_jit_profit(
                trade["volume_usd"],
                pool["reserve_usd"],
                fee_percent
            )

            if jit_calc["profitable"]:
                opportunity = {
                    "pool": pool_name,
                    "pool_dex": pool["dex"],
                    "timestamp": trade["timestamp"],
                    "tx_hash": trade["tx_hash"],
                    **jit_calc
                }
                all_opportunities.append(opportunity)

        pools_analyzed += 1
        time.sleep(0.2)  # Rate limiting

    # Статистика
    print(f"\n{'='*100}")
    print(f"📊 РЕЗУЛЬТАТЫ АНАЛИЗА")
    print(f"{'='*100}\n")

    if not all_opportunities:
        print("❌ Прибыльных JIT возможностей не найдено")
        print("\n💡 Возможные причины:")
        print("   • Минимальный размер трейда слишком высокий ($50K)")
        print("   • Недавно не было крупных сделок")
        print("   • GeckoTerminal API возвращает ограниченную историю\n")
        return

    # Сортируем по прибыли
    sorted_opps = sorted(all_opportunities, key=lambda x: x["net_profit"], reverse=True)

    total_profit = sum(o["net_profit"] for o in sorted_opps)
    avg_profit = total_profit / len(sorted_opps)

    print(f"✅ НАЙДЕНО ВОЗМОЖНОСТЕЙ:     {len(sorted_opps):,}")
    print(f"💰 ОБЩАЯ ПРИБЫЛЬ:            ${total_profit:,.2f}")
    print(f"📊 СРЕДНЯЯ ПРИБЫЛЬ:          ${avg_profit:,.2f}")
    print(f"🔥 МАКСИМАЛЬНАЯ ПРИБЫЛЬ:     ${sorted_opps[0]['net_profit']:,.2f}")

    # Топ-30 возможностей
    print(f"\n🔥 ТОП-30 ЛУЧШИХ JIT ВОЗМОЖНОСТЕЙ:\n")
    print(f"{'№':<4} {'Пул':<40} {'Trade Size':>12} {'Profit':>10} {'ROI':>8} {'Timestamp':<20}")
    print(f"{'-'*100}")

    for i, opp in enumerate(sorted_opps[:30], 1):
        ts = datetime.fromisoformat(opp["timestamp"].replace("Z", "+00:00")) if opp["timestamp"] else datetime.now()
        ts_str = ts.strftime("%Y-%m-%d %H:%M")

        print(f"{i:<4} {opp['pool'][:38]:<40} ${opp['trade_volume']:>10,.0f} ${opp['net_profit']:>8,.0f} {opp['roi']:>6.0f}% {ts_str:<20}")

    # Статистика по пулам
    pools_stats = defaultdict(lambda: {"count": 0, "total_profit": 0})
    for opp in sorted_opps:
        pools_stats[opp["pool"]]["count"] += 1
        pools_stats[opp["pool"]]["total_profit"] += opp["net_profit"]

    sorted_pools_stats = sorted(pools_stats.items(), key=lambda x: x[1]["total_profit"], reverse=True)

    print(f"\n📊 ТОП-10 ПУЛОВ ПО ПРИБЫЛИ:\n")
    print(f"{'Пул':<50} {'Опп.':>6} {'Прибыль':>12} {'Средняя':>10}")
    print(f"{'-'*90}")

    for pool, stats in sorted_pools_stats[:10]:
        avg = stats["total_profit"] / stats["count"]
        print(f"{pool[:48]:<50} {stats['count']:>6} ${stats['total_profit']:>10,.0f} ${avg:>8,.0f}")

    # Проекция
    print(f"\n💡 ПРОЕКЦИЯ:")
    print(f"   Это данные за последние ~1-2 часа (лимит GeckoTerminal API)")
    print(f"   Если предположить {len(sorted_opps)} возможностей каждые 2 часа:")
    print(f"   → Возможностей в день:  {len(sorted_opps) * 12:,}")
    print(f"   → Прибыль в день:       ${total_profit * 12:,.2f}")
    print(f"   → Прибыль в месяц:      ${total_profit * 12 * 30:,.2f}")
    print(f"   → Прибыль в год:        ${total_profit * 12 * 365:,.2f}")

    print(f"\n{'='*100}\n")

    # Детали топ-3
    print(f"🔍 ДЕТАЛИ ТОП-3 ВОЗМОЖНОСТЕЙ:\n")

    for i, opp in enumerate(sorted_opps[:3], 1):
        print(f"\n{'─'*100}")
        print(f"#{i}. {opp['pool']}")
        print(f"{'─'*100}")
        print(f"DEX:                  {opp['pool_dex']}")
        print(f"Trade Volume:         ${opp['trade_volume']:,.2f}")
        print(f"Required Liquidity:   ${opp['required_liquidity']:,.2f}")
        print(f"Total Swap Fees:      ${opp['total_fees']:,.2f}")
        print(f"Your Fees (70%):      ${opp['your_fees']:,.2f}")
        print(f"Flash Loan Fee:       ${opp['required_liquidity'] * FLASH_LOAN_FEE:,.2f}")
        print(f"Gas Cost:             ${GAS_COST_USD:.2f}")
        print(f"───────────────────────────────────")
        print(f"🔥 NET PROFIT:        ${opp['net_profit']:,.2f}")
        print(f"📈 ROI:               {opp['roi']:.0f}%")
        print(f"TX Hash:              {opp['tx_hash']}")

    print(f"\n{'='*100}\n")


if __name__ == "__main__":
    main()
