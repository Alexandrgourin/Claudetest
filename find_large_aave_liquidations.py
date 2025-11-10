#!/usr/bin/env python3
"""
Поиск крупных ликвидаций в AAVE v3 на Base за последний месяц

Стратегия:
- Разбиваем месяц на недели (4 запроса)
- Ищем только крупные ликвидации (>$1000)
- Показываем топ по размеру прибыли
"""

import requests
import json
from collections import defaultdict
from typing import Dict, List
from datetime import datetime
import time

ALCHEMY_URL = "https://base-mainnet.g.alchemy.com/v2/04r_vJrz9iSljxSQj8UQn"
AAVE_POOL_ADDRESS = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"
LIQUIDATION_EVENT = "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286"

def rpc_call(method: str, params: List = None) -> Dict:
    """RPC вызов к Alchemy"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params if params else [],
        "id": 1
    }
    try:
        response = requests.post(ALCHEMY_URL, json=payload, timeout=30)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def get_current_block() -> int:
    """Получить номер текущего блока"""
    result = rpc_call("eth_blockNumber")
    if "result" in result:
        return int(result["result"], 16)
    return 0

def get_block_timestamp(block_number: int) -> int:
    """Получить timestamp блока"""
    result = rpc_call("eth_getBlockByNumber", [hex(block_number), False])
    if "result" in result and result["result"]:
        return int(result["result"]["timestamp"], 16)
    return 0

def get_liquidation_events(from_block: int, to_block: int) -> List[Dict]:
    """Получить события LiquidationCall"""
    result = rpc_call("eth_getLogs", [{
        "address": AAVE_POOL_ADDRESS,
        "topics": [LIQUIDATION_EVENT],
        "fromBlock": hex(from_block),
        "toBlock": hex(to_block)
    }])

    if "result" in result:
        return result["result"]
    return []

def parse_liquidation_event(event: Dict) -> Dict:
    """Парсить LiquidationCall событие"""
    topics = event.get("topics", [])
    data = event.get("data", "0x")

    if len(topics) < 4:
        return None

    collateral_asset = "0x" + topics[1][-40:]
    debt_asset = "0x" + topics[2][-40:]
    user = "0x" + topics[3][-40:]

    data_clean = data[2:]
    if len(data_clean) >= 256:
        debt_to_cover = int(data_clean[0:64], 16) if data_clean[0:64] else 0
        collateral_amount = int(data_clean[64:128], 16) if data_clean[64:128] else 0
        liquidator = "0x" + data_clean[128:192][-40:]

        block_number = int(event.get("blockNumber", "0x0"), 16)
        tx_hash = event.get("transactionHash", "")

        return {
            "collateral_asset": collateral_asset.lower(),
            "debt_asset": debt_asset.lower(),
            "user": user.lower(),
            "debt_to_cover": debt_to_cover,
            "collateral_amount": collateral_amount,
            "liquidator": liquidator.lower(),
            "block_number": block_number,
            "tx_hash": tx_hash
        }

    return None

def get_token_info(token_address: str, cache: Dict) -> Dict:
    """Получить информацию о токене с кешированием"""
    if token_address in cache:
        return cache[token_address]

    # symbol()
    symbol_result = rpc_call("eth_call", [{
        "to": token_address,
        "data": "0x95d89b41"
    }, "latest"])

    symbol = token_address[:8] + "..."
    if "result" in symbol_result:
        try:
            data = symbol_result["result"][2:]
            if len(data) >= 128:
                length = int(data[64:128], 16)
                string_data = data[128:128+length*2]
                symbol = bytes.fromhex(string_data).decode('utf-8', errors='ignore')
        except:
            pass

    # decimals()
    decimals_result = rpc_call("eth_call", [{
        "to": token_address,
        "data": "0x313ce567"
    }, "latest"])

    decimals = 18
    if "result" in decimals_result:
        try:
            decimals = int(decimals_result["result"], 16)
        except:
            pass

    info = {"symbol": symbol, "decimals": decimals}
    cache[token_address] = info
    return info

def get_token_price_usd(token_address: str) -> float:
    """Получить цену токена в USD"""
    prices = {
        "0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452": 4000,   # wstETH
        "0x4200000000000000000000000000000000000006": 3400,   # WETH
        "0x236aa50979d5f3de3bd1eeb40e81137f22ab794b": 97000,  # tBTC
        "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf": 97000,  # cbBTC
        "0x2ae3f1ec7f1f5012cfeab0185bfc7aa3cf0dec22": 3500,   # cbETH
        "0x04c0599ae5a44757c0af6f9ec3b93da8976c150a": 3800,   # weETH
        "0x6bb7a212910682dcfdbd5bcbb3e28fb4e8da10ee": 1.0,    # GHO
        "0x60a3e35cc302bfa44cb288bc5a4f316fdb1adb42": 1.05,   # EURC
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": 1.0,    # USDC
        "0xd9aaec86b65d86f6a7b5b1b0c42ffa531710b6ca": 1.0,    # USDbC
        "0x63706e401c06ac8513145b7687a14804d17f814b": 200,    # AAVE
    }
    return prices.get(token_address.lower(), 0)

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                                                                      ║
    ║        ПОИСК КРУПНЫХ ЛИКВИДАЦИЙ В AAVE V3 ЗА ПОСЛЕДНИЙ МЕСЯЦ       ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)

    print(f"📍 AAVE v3 Pool: {AAVE_POOL_ADDRESS}")
    print(f"🌐 RPC: Alchemy\n")

    current_block = get_current_block()
    print(f"📊 Текущий блок: {current_block:,}\n")

    # Месяц = ~30 дней * 43200 блоков/день = 1,296,000 блоков
    # Разобьем на 4 недели по ~302,400 блоков
    blocks_per_week = 302400

    print("="*80)
    print("🔍 СКАНИРОВАНИЕ ЗА 4 НЕДЕЛИ")
    print("="*80 + "\n")

    all_liquidations = []
    token_cache = {}

    for week in range(4):
        week_num = 4 - week  # Неделя 4, 3, 2, 1 (от новой к старой)
        to_block = current_block - (week * blocks_per_week)
        from_block = to_block - blocks_per_week

        from_ts = get_block_timestamp(from_block)
        to_ts = get_block_timestamp(to_block)
        from_time = datetime.fromtimestamp(from_ts)
        to_time = datetime.fromtimestamp(to_ts)

        print(f"📅 Неделя {week_num}: {from_time.strftime('%d.%m')} - {to_time.strftime('%d.%m')}")
        print(f"   Блоки: {from_block:,} -> {to_block:,}")

        events = get_liquidation_events(from_block, to_block)
        print(f"   Найдено событий: {len(events)}")

        # Парсим события
        for event in events:
            parsed = parse_liquidation_event(event)
            if parsed:
                all_liquidations.append(parsed)

        print()
        time.sleep(0.5)  # Небольшая задержка между запросами

    print(f"✅ Всего найдено ликвидаций: {len(all_liquidations)}\n")

    if not all_liquidations:
        print("❌ Ликвидаций не найдено за последний месяц")
        return

    # Получаем информацию о токенах
    print("🔤 Получаем информацию о токенах...")
    tokens_seen = set()
    for liq in all_liquidations:
        tokens_seen.add(liq["collateral_asset"])
        tokens_seen.add(liq["debt_asset"])

    for token in tokens_seen:
        get_token_info(token, token_cache)

    # Рассчитываем суммы в USD для каждой ликвидации
    print("💰 Рассчитываем суммы...\n")

    liquidations_with_usd = []
    for liq in all_liquidations:
        debt_token = token_cache.get(liq['debt_asset'], {"symbol": "???", "decimals": 18})
        collateral_token = token_cache.get(liq['collateral_asset'], {"symbol": "???", "decimals": 18})

        debt_usd = (liq['debt_to_cover'] / 10**debt_token['decimals']) * get_token_price_usd(liq['debt_asset'])
        collateral_usd = (liq['collateral_amount'] / 10**collateral_token['decimals']) * get_token_price_usd(liq['collateral_asset'])
        bonus_usd = collateral_usd - debt_usd
        bonus_pct = (bonus_usd / debt_usd * 100) if debt_usd > 0 else 0

        liquidations_with_usd.append({
            **liq,
            "debt_usd": debt_usd,
            "collateral_usd": collateral_usd,
            "bonus_usd": bonus_usd,
            "bonus_pct": bonus_pct,
            "debt_token": debt_token,
            "collateral_token": collateral_token
        })

    # Сортируем по размеру долга (от большего к меньшему)
    liquidations_with_usd.sort(key=lambda x: x['debt_usd'], reverse=True)

    # Фильтруем крупные (> $1000)
    large_liquidations = [l for l in liquidations_with_usd if l['debt_usd'] > 1000]

    print("="*80)
    print(f"💎 КРУПНЫЕ ЛИКВИДАЦИИ (ДОЛГ > $1000)")
    print("="*80 + "\n")

    if not large_liquidations:
        print("❌ Крупных ликвидаций (>$1000) не найдено за месяц\n")

        # Показываем самые крупные из того что есть
        print("📊 ТОП-10 САМЫХ КРУПНЫХ:")
        for i, liq in enumerate(liquidations_with_usd[:10], 1):
            debt_amount = liq['debt_to_cover'] / 10**liq['debt_token']['decimals']
            collateral_amount = liq['collateral_amount'] / 10**liq['collateral_token']['decimals']

            print(f"\n{i}. Блок {liq['block_number']:,} ({datetime.fromtimestamp(get_block_timestamp(liq['block_number'])).strftime('%d.%m %H:%M')})")
            print(f"   TX: {liq['tx_hash']}")
            print(f"   💸 Долг: {debt_amount:,.4f} {liq['debt_token']['symbol']} (${liq['debt_usd']:,.2f})")
            print(f"   🏦 Collateral: {collateral_amount:,.4f} {liq['collateral_token']['symbol']} (${liq['collateral_usd']:,.2f})")
            print(f"   💰 Бонус: ${liq['bonus_usd']:,.2f} ({liq['bonus_pct']:.1f}%)")
            print(f"   👤 Victim: {liq['user']}")
            print(f"   🤖 Liquidator: {liq['liquidator']}")
    else:
        print(f"✅ Найдено {len(large_liquidations)} крупных ликвидаций!\n")

        for i, liq in enumerate(large_liquidations, 1):
            block_ts = get_block_timestamp(liq['block_number'])
            date_str = datetime.fromtimestamp(block_ts).strftime('%d.%m.%Y %H:%M')

            debt_amount = liq['debt_to_cover'] / 10**liq['debt_token']['decimals']
            collateral_amount = liq['collateral_amount'] / 10**liq['collateral_token']['decimals']

            print(f"{i}. 📅 {date_str} | Блок {liq['block_number']:,}")
            print(f"   TX: https://basescan.org/tx/{liq['tx_hash']}")
            print(f"   💸 Погашено: {debt_amount:,.4f} {liq['debt_token']['symbol']} (${liq['debt_usd']:,.2f})")
            print(f"   🏦 Конфисковано: {collateral_amount:,.4f} {liq['collateral_token']['symbol']} (${liq['collateral_usd']:,.2f})")
            print(f"   💰 БОНУС: ${liq['bonus_usd']:,.2f} ({liq['bonus_pct']:.1f}%)")
            print(f"   👤 Victim: {liq['user']}")
            print(f"   🤖 Liquidator: {liq['liquidator']}\n")

    # Итоговая статистика
    print("="*80)
    print("📊 СТАТИСТИКА ЗА МЕСЯЦ")
    print("="*80 + "\n")

    total_debt = sum(l['debt_usd'] for l in liquidations_with_usd)
    total_collateral = sum(l['collateral_usd'] for l in liquidations_with_usd)
    total_bonus = sum(l['bonus_usd'] for l in liquidations_with_usd)

    print(f"🔢 Всего ликвидаций: {len(liquidations_with_usd)}")
    print(f"💎 Крупных (>$1000): {len(large_liquidations)}")
    print(f"🐜 Мелких (<$1000): {len(liquidations_with_usd) - len(large_liquidations)}")
    print()
    print(f"💸 Общий погашенный долг: ${total_debt:,.2f}")
    print(f"🏦 Общий конфискованный collateral: ${total_collateral:,.2f}")
    print(f"💰 Общий бонус ликвидаторов: ${total_bonus:,.2f}")

    if len(liquidations_with_usd) > 0:
        avg_debt = total_debt / len(liquidations_with_usd)
        avg_bonus = total_bonus / len(liquidations_with_usd)
        print(f"\n📊 Средние значения:")
        print(f"   Средний долг: ${avg_debt:,.2f}")
        print(f"   Средний бонус: ${avg_bonus:,.2f}")

    if large_liquidations:
        large_debt = sum(l['debt_usd'] for l in large_liquidations)
        large_bonus = sum(l['bonus_usd'] for l in large_liquidations)

        print(f"\n💎 Крупные ликвидации:")
        print(f"   Доля от общего числа: {len(large_liquidations)/len(liquidations_with_usd)*100:.1f}%")
        print(f"   Доля от общего долга: {large_debt/total_debt*100:.1f}%")
        print(f"   Доля от общего бонуса: {large_bonus/total_bonus*100:.1f}%")
        print(f"   Средний бонус: ${large_bonus/len(large_liquidations):,.2f}")

    # Топ ликвидаторы
    liquidators = defaultdict(lambda: {"count": 0, "profit": 0})
    for liq in liquidations_with_usd:
        liquidators[liq['liquidator']]["count"] += 1
        liquidators[liq['liquidator']]["profit"] += liq['bonus_usd']

    print(f"\n🏆 ТОП-5 ЛИКВИДАТОРОВ:")
    sorted_liquidators = sorted(liquidators.items(), key=lambda x: x[1]['profit'], reverse=True)
    for i, (addr, stats) in enumerate(sorted_liquidators[:5], 1):
        print(f"   {i}. {addr}")
        print(f"      Ликвидаций: {stats['count']}, Прибыль: ${stats['profit']:,.2f}")

    # Выводы
    print("\n" + "="*80)
    print("💡 ВЫВОДЫ ДЛЯ MEV")
    print("="*80 + "\n")

    if large_liquidations:
        max_bonus = max(l['bonus_usd'] for l in large_liquidations)
        print(f"🔥 БЫЛИ КРУПНЫЕ ВОЗМОЖНОСТИ!")
        print(f"   Максимальный бонус: ${max_bonus:,.2f}")
        print(f"   Крупных ликвидаций: {len(large_liquidations)} за месяц")
        print(f"   Средняя прибыль: ${large_bonus/len(large_liquidations):,.2f}")
    else:
        print(f"⚠️  ЗА МЕСЯЦ НЕ БЫЛО КРУПНЫХ ЛИКВИДАЦИЙ")
        print(f"   Все {len(liquidations_with_usd)} ликвидаций - микро-позиции")
        print(f"   Максимальный долг: ${liquidations_with_usd[0]['debt_usd']:,.2f}")

    print(f"\n🎯 СТРАТЕГИЯ:")
    print(f"   1. Крупные ликвидации РЕДКИ - в среднем {len(large_liquidations)/4:.1f} в неделю")
    print(f"   2. Основная масса - микро-позиции (боты чистят автоматически)")
    print(f"   3. ФОКУС на мониторинг крупных позиций из find_aave_borrowers.py")
    print(f"   4. При HF < 1.05 - готовиться к ликвидации")
    print(f"   5. Конкуренция: {len(liquidators)} активных ликвидаторов")

if __name__ == "__main__":
    main()
