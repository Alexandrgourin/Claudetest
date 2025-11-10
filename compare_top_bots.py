#!/usr/bin/env python3
"""
Сравнительный анализ топ-3 ликвидаторов

Сравниваем:
1. Топ-1: 0xc88eab547fde493992b2456589f2796960cc4561 (уже знаем)
2. Топ-2: 0xd12810b19b596347a3afac206d3ca65d08594b3f
3. Топ-3: 0x0a5a3e02c2aae465a016531a7aa6b4be4b21d3f9
"""

import requests
import json
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict
import time

ALCHEMY_URL = "https://base-mainnet.g.alchemy.com/v2/04r_vJrz9iSljxSQj8UQn"
AAVE_POOL_ADDRESS = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"
LIQUIDATION_EVENT = "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286"

# Топовые боты
BOTS = {
    "Bot #1 (Known)": "0xc88eab547fde493992b2456589f2796960cc4561",
    "Bot #2": "0xd12810b19b596347a3afac206d3ca65d08594b3f",
    "Bot #3": "0x0a5a3e02c2aae465a016531a7aa6b4be4b21d3f9"
}

def rpc_call(method: str, params: List = None) -> Dict:
    """RPC вызов"""
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
    """Получить текущий блок"""
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

def get_contract_creation_block(address: str, current_block: int) -> Optional[int]:
    """Найти блок создания контракта"""
    print(f"   🔍 Ищем блок создания...", end=" ")

    left = 1000000
    right = current_block
    creation_block = None

    while left <= right:
        mid = (left + right) // 2
        result = rpc_call("eth_getCode", [address, hex(mid)])

        if "result" in result:
            code = result["result"]
            has_code = len(code) > 2

            if has_code:
                creation_block = mid
                right = mid - 1
            else:
                left = mid + 1
        else:
            break

    if creation_block:
        print(f"найден блок {creation_block:,}")
    else:
        print("не найден")

    return creation_block

def get_bot_liquidations(bot_address: str, from_block: int, to_block: int) -> List[Dict]:
    """Получить все ликвидации конкретного бота"""
    result = rpc_call("eth_getLogs", [{
        "address": AAVE_POOL_ADDRESS,
        "topics": [LIQUIDATION_EVENT, None, None, None],
        "fromBlock": hex(from_block),
        "toBlock": hex(to_block)
    }])

    if "result" not in result:
        return []

    events = result["result"]
    bot_liquidations = []

    for event in events:
        topics = event.get("topics", [])
        data = event.get("data", "0x")

        if len(topics) < 4:
            continue

        data_clean = data[2:]
        if len(data_clean) >= 192:
            liquidator = "0x" + data_clean[128:192][-40:]

            if liquidator.lower() == bot_address.lower():
                collateral_asset = "0x" + topics[1][-40:]
                debt_asset = "0x" + topics[2][-40:]
                user = "0x" + topics[3][-40:]

                debt_to_cover = int(data_clean[0:64], 16) if data_clean[0:64] else 0
                collateral_amount = int(data_clean[64:128], 16) if data_clean[64:128] else 0

                block_number = int(event.get("blockNumber", "0x0"), 16)
                tx_hash = event.get("transactionHash", "")

                bot_liquidations.append({
                    "collateral_asset": collateral_asset.lower(),
                    "debt_asset": debt_asset.lower(),
                    "user": user.lower(),
                    "debt_to_cover": debt_to_cover,
                    "collateral_amount": collateral_amount,
                    "block_number": block_number,
                    "tx_hash": tx_hash
                })

    return bot_liquidations

def get_token_price_usd(token_address: str) -> float:
    """Получить цену токена в USD"""
    prices = {
        "0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452": 4000,
        "0x4200000000000000000000000000000000000006": 3400,
        "0x236aa50979d5f3de3bd1eeb40e81137f22ab794b": 97000,
        "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf": 97000,
        "0x2ae3f1ec7f1f5012cfeab0185bfc7aa3cf0dec22": 3500,
        "0x04c0599ae5a44757c0af6f9ec3b93da8976c150a": 3800,
        "0x6bb7a212910682dcfdbd5bcbb3e28fb4e8da10ee": 1.0,
        "0x60a3e35cc302bfa44cb288bc5a4f316fdb1adb42": 1.05,
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": 1.0,
        "0xd9aaec86b65d86f6a7b5b1b0c42ffa531710b6ca": 1.0,
        "0x63706e401c06ac8513145b7687a14804d17f814b": 200,
    }
    return prices.get(token_address.lower(), 0)

def get_token_decimals(token_address: str) -> int:
    """Получить decimals токена"""
    result = rpc_call("eth_call", [{
        "to": token_address,
        "data": "0x313ce567"
    }, "latest"])

    if "result" in result:
        try:
            return int(result["result"], 16)
        except:
            pass
    return 18

def analyze_bot(bot_name: str, bot_address: str, current_block: int) -> Dict:
    """Полный анализ одного бота"""
    print(f"\n{'='*80}")
    print(f"🤖 {bot_name}: {bot_address}")
    print("="*80)

    # 1. Проверяем тип адреса
    code_result = rpc_call("eth_getCode", [bot_address, "latest"])
    is_contract = False
    code_size = 0

    if "result" in code_result:
        code = code_result["result"]
        code_size = (len(code) - 2) // 2
        is_contract = code_size > 0

    print(f"\n📝 Тип: {'Смарт-контракт' if is_contract else 'EOA (обычный адрес)'}")
    if is_contract:
        print(f"   Размер кода: {code_size} bytes")

    # 2. Находим когда был создан
    creation_block = get_contract_creation_block(bot_address, current_block)

    if not creation_block:
        creation_block = current_block - 3888000  # 3 месяца назад

    creation_ts = get_block_timestamp(creation_block)
    creation_date = datetime.fromtimestamp(creation_ts)
    days_active = (datetime.now() - creation_date).days

    print(f"\n📅 Создан: {creation_date.strftime('%d.%m.%Y')} (блок {creation_block:,})")
    print(f"⏱️  Активен: {days_active} дней")

    # 3. Сканируем все ликвидации
    print(f"\n🔍 Сканируем ликвидации с блока {creation_block:,}...")

    all_liquidations = []
    chunk_size = 100000
    from_block = creation_block

    while from_block < current_block:
        to_block = min(from_block + chunk_size, current_block)
        liquidations = get_bot_liquidations(bot_address, from_block, to_block)
        all_liquidations.extend(liquidations)
        from_block = to_block + 1

    print(f"✅ Найдено: {len(all_liquidations)} ликвидаций")

    if not all_liquidations:
        return {
            "name": bot_name,
            "address": bot_address,
            "is_contract": is_contract,
            "code_size": code_size,
            "creation_date": creation_date,
            "days_active": days_active,
            "liquidations_count": 0,
            "total_profit": 0,
            "avg_profit": 0,
            "best_profit": 0,
            "total_debt": 0,
            "avg_debt": 0,
            "liquidations_per_day": 0,
            "monthly_earnings": 0
        }

    # 4. Рассчитываем прибыль для каждой
    print(f"💰 Рассчитываем прибыль...")

    total_profit = 0
    total_debt = 0
    profits = []

    for liq in all_liquidations:
        debt_decimals = get_token_decimals(liq['debt_asset'])
        collateral_decimals = get_token_decimals(liq['collateral_asset'])

        debt_usd = (liq['debt_to_cover'] / 10**debt_decimals) * get_token_price_usd(liq['debt_asset'])
        collateral_usd = (liq['collateral_amount'] / 10**collateral_decimals) * get_token_price_usd(liq['collateral_asset'])
        profit_usd = collateral_usd - debt_usd

        total_profit += profit_usd
        total_debt += debt_usd
        profits.append(profit_usd)

    # 5. Статистика
    avg_profit = total_profit / len(all_liquidations) if all_liquidations else 0
    avg_debt = total_debt / len(all_liquidations) if all_liquidations else 0
    best_profit = max(profits) if profits else 0
    worst_profit = min(profits) if profits else 0

    liquidations_per_day = len(all_liquidations) / days_active if days_active > 0 else 0
    monthly_earnings = total_profit / days_active * 30 if days_active > 0 else 0

    print(f"\n📊 СТАТИСТИКА:")
    print(f"   Всего ликвидаций: {len(all_liquidations)}")
    print(f"   Общая прибыль: ${total_profit:,.2f}")
    print(f"   Средняя прибыль: ${avg_profit:,.2f}")
    print(f"   Лучшая прибыль: ${best_profit:,.2f}")
    print(f"   Худшая прибыль: ${worst_profit:,.2f}")
    print(f"   Средний долг: ${avg_debt:,.2f}")
    print(f"   Частота: {liquidations_per_day:.2f} лик/день")
    print(f"   Месячный доход: ${monthly_earnings:,.2f}")

    return {
        "name": bot_name,
        "address": bot_address,
        "is_contract": is_contract,
        "code_size": code_size,
        "creation_date": creation_date,
        "days_active": days_active,
        "liquidations_count": len(all_liquidations),
        "total_profit": total_profit,
        "avg_profit": avg_profit,
        "best_profit": best_profit,
        "worst_profit": worst_profit,
        "total_debt": total_debt,
        "avg_debt": avg_debt,
        "liquidations_per_day": liquidations_per_day,
        "monthly_earnings": monthly_earnings
    }

def print_comparison(results: List[Dict]):
    """Сравнительная таблица"""
    print(f"\n\n{'='*80}")
    print(f"🏆 СРАВНЕНИЕ ТОПОВЫХ БОТОВ")
    print("="*80 + "\n")

    print(f"{'Метрика':<30} {'Bot #1':<20} {'Bot #2':<20} {'Bot #3':<20}")
    print(f"{'-'*30} {'-'*20} {'-'*20} {'-'*20}")

    # Тип
    print(f"{'Тип':<30} {('Contract' if results[0]['is_contract'] else 'EOA'):<20} {('Contract' if results[1]['is_contract'] else 'EOA'):<20} {('Contract' if results[2]['is_contract'] else 'EOA'):<20}")

    # Возраст
    print(f"{'Дней активен':<30} {results[0]['days_active']:<20} {results[1]['days_active']:<20} {results[2]['days_active']:<20}")

    # Ликвидации
    print(f"{'Всего ликвидаций':<30} {results[0]['liquidations_count']:<20} {results[1]['liquidations_count']:<20} {results[2]['liquidations_count']:<20}")

    # Прибыль
    profit1 = f"${results[0]['total_profit']:,.0f}"
    profit2 = f"${results[1]['total_profit']:,.0f}"
    profit3 = f"${results[2]['total_profit']:,.0f}"
    print(f"{'Общая прибыль':<30} {profit1:<20} {profit2:<20} {profit3:<20}")

    # Средняя прибыль
    avg1 = f"${results[0]['avg_profit']:,.0f}"
    avg2 = f"${results[1]['avg_profit']:,.0f}"
    avg3 = f"${results[2]['avg_profit']:,.0f}"
    print(f"{'Средняя прибыль':<30} {avg1:<20} {avg2:<20} {avg3:<20}")

    # Лучшая прибыль
    best1 = f"${results[0]['best_profit']:,.0f}"
    best2 = f"${results[1]['best_profit']:,.0f}"
    best3 = f"${results[2]['best_profit']:,.0f}"
    print(f"{'Лучшая прибыль':<30} {best1:<20} {best2:<20} {best3:<20}")

    # Средний долг
    debt1 = f"${results[0]['avg_debt']:,.0f}"
    debt2 = f"${results[1]['avg_debt']:,.0f}"
    debt3 = f"${results[2]['avg_debt']:,.0f}"
    print(f"{'Средний долг':<30} {debt1:<20} {debt2:<20} {debt3:<20}")

    # Частота
    freq1 = f"{results[0]['liquidations_per_day']:.2f}"
    freq2 = f"{results[1]['liquidations_per_day']:.2f}"
    freq3 = f"{results[2]['liquidations_per_day']:.2f}"
    print(f"{'Ликвидаций/день':<30} {freq1:<20} {freq2:<20} {freq3:<20}")

    # Месячный доход
    monthly1 = f"${results[0]['monthly_earnings']:,.0f}"
    monthly2 = f"${results[1]['monthly_earnings']:,.0f}"
    monthly3 = f"${results[2]['monthly_earnings']:,.0f}"
    print(f"{'Месячный доход':<30} {monthly1:<20} {monthly2:<20} {monthly3:<20}")

    # Выводы
    print(f"\n{'='*80}")
    print(f"💡 КЛЮЧЕВЫЕ РАЗЛИЧИЯ")
    print("="*80 + "\n")

    # Самый прибыльный
    most_profitable_idx = max(range(3), key=lambda i: results[i]['total_profit'])
    print(f"🏆 САМЫЙ ПРИБЫЛЬНЫЙ: {results[most_profitable_idx]['name']}")
    print(f"   Общая прибыль: ${results[most_profitable_idx]['total_profit']:,.0f}")
    print(f"   Месячно: ${results[most_profitable_idx]['monthly_earnings']:,.0f}")

    # Самый активный
    most_active_idx = max(range(3), key=lambda i: results[i]['liquidations_per_day'])
    print(f"\n⚡ САМЫЙ АКТИВНЫЙ: {results[most_active_idx]['name']}")
    print(f"   Частота: {results[most_active_idx]['liquidations_per_day']:.2f} лик/день")
    print(f"   Всего ликвидаций: {results[most_active_idx]['liquidations_count']}")

    # Самый эффективный (прибыль на ликвидацию)
    most_efficient_idx = max(range(3), key=lambda i: results[i]['avg_profit'])
    print(f"\n💎 САМЫЙ ЭФФЕКТИВНЫЙ: {results[most_efficient_idx]['name']}")
    print(f"   Средняя прибыль: ${results[most_efficient_idx]['avg_profit']:,.0f}")
    print(f"   Средний долг: ${results[most_efficient_idx]['avg_debt']:,.0f}")

    # Стратегии
    print(f"\n📊 СТРАТЕГИИ:")

    for i, result in enumerate(results):
        strategy = ""
        if result['liquidations_per_day'] < 0.5:
            strategy = "Селективная (редкие, но крупные)"
        elif result['liquidations_per_day'] > 2:
            strategy = "Агрессивная (частые ликвидации)"
        else:
            strategy = "Сбалансированная"

        size_focus = ""
        if result['avg_debt'] > 20000:
            size_focus = "Фокус на крупные (>$20K)"
        elif result['avg_debt'] > 5000:
            size_focus = "Средние позиции ($5-20K)"
        else:
            size_focus = "Малые позиции (<$5K)"

        print(f"\n   {result['name']}:")
        print(f"      {strategy}")
        print(f"      {size_focus}")

    # Общий вывод
    total_market = sum(r['total_profit'] for r in results)
    print(f"\n🌐 РЫНОК:")
    print(f"   Топ-3 бота заработали: ${total_market:,.0f}")
    print(f"   Средний месячный доход топ-3: ${sum(r['monthly_earnings'] for r in results):,.0f}")
    print(f"   Это показывает размер рынка AAVE Base liquidations")

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                                                                      ║
    ║              СРАВНЕНИЕ ТОПОВЫХ ЛИКВИДАТОРОВ                         ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)

    current_block = get_current_block()
    print(f"📊 Текущий блок: {current_block:,}\n")

    results = []

    # Анализируем каждого бота
    for bot_name, bot_address in BOTS.items():
        result = analyze_bot(bot_name, bot_address, current_block)
        results.append(result)
        time.sleep(1)  # Небольшая пауза между ботами

    # Сравнение
    print_comparison(results)

if __name__ == "__main__":
    main()
