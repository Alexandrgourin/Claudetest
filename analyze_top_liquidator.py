#!/usr/bin/env python3
"""
Анализ стратегии топ-ликвидатора AAVE на Base

Изучаем: 0xc88eab547fde493992b2456589f2796960cc4561
- Самая прибыльная ликвидация: $21,707
- Как он работает?
- Какая стратегия?
"""

import requests
import json
from collections import defaultdict
from typing import Dict, List
from datetime import datetime

ALCHEMY_URL = "https://base-mainnet.g.alchemy.com/v2/04r_vJrz9iSljxSQj8UQn"
AAVE_POOL_ADDRESS = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"
LIQUIDATION_EVENT = "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286"

# Топ ликвидатор
TOP_LIQUIDATOR = "0xc88eab547fde493992b2456589f2796960cc4561"

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

def get_code(address: str) -> str:
    """Получить bytecode контракта"""
    result = rpc_call("eth_getCode", [address, "latest"])
    if "result" in result:
        return result["result"]
    return "0x"

def get_transaction(tx_hash: str) -> Dict:
    """Получить детали транзакции"""
    result = rpc_call("eth_getTransactionByHash", [tx_hash])
    if "result" in result:
        return result["result"]
    return {}

def get_transaction_receipt(tx_hash: str) -> Dict:
    """Получить receipt транзакции"""
    result = rpc_call("eth_getTransactionReceipt", [tx_hash])
    if "result" in result:
        return result["result"]
    return {}

def get_liquidations_by_liquidator(liquidator: str, from_block: int, to_block: int) -> List[Dict]:
    """Получить все ликвидации конкретного ликвидатора"""
    print(f"🔍 Поиск ликвидаций бота {liquidator[:10]}...")

    # Получаем все ликвидации
    result = rpc_call("eth_getLogs", [{
        "address": AAVE_POOL_ADDRESS,
        "topics": [LIQUIDATION_EVENT],
        "fromBlock": hex(from_block),
        "toBlock": hex(to_block)
    }])

    if "result" not in result:
        return []

    events = result["result"]

    # Фильтруем по ликвидатору
    liquidator_events = []
    for event in events:
        data = event.get("data", "0x")
        data_clean = data[2:]

        if len(data_clean) >= 192:
            event_liquidator = "0x" + data_clean[128:192][-40:]

            if event_liquidator.lower() == liquidator.lower():
                liquidator_events.append(event)

    print(f"   Найдено: {len(liquidator_events)} ликвидаций этого бота")
    return liquidator_events

def parse_liquidation_event(event: Dict) -> Dict:
    """Парсить событие ликвидации"""
    topics = event.get("topics", [])
    data = event.get("data", "0x")

    if len(topics) < 4:
        return None

    collateral_asset = "0x" + topics[1][-40:]
    debt_asset = "0x" + topics[2][-40:]
    user = "0x" + topics[3][-40:]

    data_clean = data[2:]
    if len(data_clean) >= 256:
        debt_to_cover = int(data_clean[0:64], 16)
        collateral_amount = int(data_clean[64:128], 16)
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

def analyze_transaction_pattern(tx_hash: str) -> Dict:
    """Анализировать паттерн транзакции"""
    tx = get_transaction(tx_hash)
    receipt = get_transaction_receipt(tx_hash)

    if not tx or not receipt:
        return {}

    # Анализируем input data
    input_data = tx.get("input", "0x")

    # Газ
    gas_used = int(receipt.get("gasUsed", "0x0"), 16)
    gas_price = int(tx.get("gasPrice", "0x0"), 16)
    gas_cost_wei = gas_used * gas_price
    gas_cost_eth = gas_cost_wei / 10**18

    # Блок
    block_number = int(tx.get("blockNumber", "0x0"), 16)

    # From address
    from_addr = tx.get("from", "").lower()

    # To address (контракт?)
    to_addr = tx.get("to", "").lower()

    # Logs count (сколько событий)
    logs_count = len(receipt.get("logs", []))

    return {
        "from": from_addr,
        "to": to_addr,
        "input_data": input_data,
        "input_length": len(input_data),
        "gas_used": gas_used,
        "gas_price_gwei": gas_price / 10**9,
        "gas_cost_eth": gas_cost_eth,
        "block_number": block_number,
        "logs_count": logs_count,
        "is_contract_call": to_addr != AAVE_POOL_ADDRESS.lower()
    }

def get_token_price_usd(token_address: str) -> float:
    """Получить цену токена"""
    prices = {
        "0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452": 4000,
        "0x4200000000000000000000000000000000000006": 3400,
        "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf": 97000,
        "0x2ae3f1ec7f1f5012cfeab0185bfc7aa3cf0dec22": 3500,
        "0x60a3e35cc302bfa44cb288bc5a4f316fdb1adb42": 1.05,
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": 1.0,
    }
    return prices.get(token_address.lower(), 0)

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                                                                      ║
    ║            АНАЛИЗ СТРАТЕГИИ ТОП-ЛИКВИДАТОРА AAVE НА BASE           ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)

    print(f"🤖 Анализируем бота: {TOP_LIQUIDATOR}\n")

    # Проверяем - это контракт или EOA?
    code = get_code(TOP_LIQUIDATOR)
    is_contract = len(code) > 2

    print("="*80)
    print("📋 ИНФОРМАЦИЯ О БОТЕ")
    print("="*80 + "\n")

    if is_contract:
        print(f"✅ Это СМАРТ-КОНТРАКТ")
        print(f"   Bytecode size: {len(code)} bytes")
        print(f"   Контракт использует автоматизацию\n")
    else:
        print(f"⚠️  Это EOA (Externally Owned Account)")
        print(f"   Управляется вручную или через external bot\n")

    # Получаем текущий блок
    current_block = get_current_block()

    # Анализируем за последний месяц
    from_block = current_block - 302400 * 4  # 4 недели
    to_block = current_block

    # Получаем все ликвидации этого бота
    events = get_liquidations_by_liquidator(TOP_LIQUIDATOR, from_block, to_block)

    if not events:
        print("❌ Ликвидаций не найдено за последний месяц")
        return

    print("\n" + "="*80)
    print("💰 АНАЛИЗ ЛИКВИДАЦИЙ")
    print("="*80 + "\n")

    # Парсим все ликвидации
    liquidations = []
    for event in events:
        parsed = parse_liquidation_event(event)
        if parsed:
            liquidations.append(parsed)

    # Сортируем по размеру долга
    liquidations_with_usd = []
    for liq in liquidations:
        debt_token_decimals = 18 if "weth" in liq['debt_asset'] else 6
        collateral_token_decimals = 18 if "weth" in liq['collateral_asset'] else 6

        debt_usd = (liq['debt_to_cover'] / 10**debt_token_decimals) * get_token_price_usd(liq['debt_asset'])
        collateral_usd = (liq['collateral_amount'] / 10**collateral_token_decimals) * get_token_price_usd(liq['collateral_asset'])
        bonus_usd = collateral_usd - debt_usd

        liquidations_with_usd.append({
            **liq,
            "debt_usd": debt_usd,
            "collateral_usd": collateral_usd,
            "bonus_usd": bonus_usd
        })

    liquidations_with_usd.sort(key=lambda x: x['bonus_usd'], reverse=True)

    # Статистика
    total_bonus = sum(l['bonus_usd'] for l in liquidations_with_usd)
    avg_bonus = total_bonus / len(liquidations_with_usd) if liquidations_with_usd else 0

    print(f"Всего ликвидаций: {len(liquidations_with_usd)}")
    print(f"Общая прибыль: ${total_bonus:,.2f}")
    print(f"Средняя прибыль: ${avg_bonus:,.2f}")
    print(f"Максимальная прибыль: ${liquidations_with_usd[0]['bonus_usd']:,.2f}")

    # ТОП-5 самых прибыльных
    print("\n🏆 ТОП-5 САМЫХ ПРИБЫЛЬНЫХ ЛИКВИДАЦИЙ:\n")

    for i, liq in enumerate(liquidations_with_usd[:5], 1):
        print(f"{i}. Блок {liq['block_number']:,}")
        print(f"   TX: {liq['tx_hash']}")
        print(f"   💰 Прибыль: ${liq['bonus_usd']:,.2f}")
        print(f"   💸 Долг: ${liq['debt_usd']:,.2f}")
        print(f"   🏦 Collateral: ${liq['collateral_usd']:,.2f}\n")

    # Анализируем транзакции
    print("="*80)
    print("🔍 АНАЛИЗ ПАТТЕРНОВ ТРАНЗАКЦИЙ")
    print("="*80 + "\n")

    print("Анализируем ТОП-3 транзакции...\n")

    patterns = []
    for i, liq in enumerate(liquidations_with_usd[:3], 1):
        print(f"Транзакция #{i}: {liq['tx_hash'][:20]}...")
        pattern = analyze_transaction_pattern(liq['tx_hash'])

        if pattern:
            patterns.append(pattern)

            print(f"   From: {pattern['from'][:20]}...")
            print(f"   To: {pattern['to'][:20]}...")
            print(f"   Gas used: {pattern['gas_used']:,}")
            print(f"   Gas price: {pattern['gas_price_gwei']:.2f} gwei")
            print(f"   Gas cost: {pattern['gas_cost_eth']:.6f} ETH (${pattern['gas_cost_eth'] * 3400:.2f})")
            print(f"   Input length: {pattern['input_length']} bytes")
            print(f"   Logs count: {pattern['logs_count']}")

            if pattern['is_contract_call']:
                print(f"   ✅ Вызывает внешний контракт (не напрямую AAVE)")
            else:
                print(f"   📍 Прямой вызов AAVE Pool")

            print()

    # Анализ паттернов
    if patterns:
        print("="*80)
        print("📊 ВЫВОДЫ О СТРАТЕГИИ")
        print("="*80 + "\n")

        # Средний газ
        avg_gas = sum(p['gas_used'] for p in patterns) / len(patterns)
        avg_gas_price = sum(p['gas_price_gwei'] for p in patterns) / len(patterns)
        avg_gas_cost = sum(p['gas_cost_eth'] for p in patterns) / len(patterns)

        print(f"1. ГАЗОВЫЕ ЗАТРАТЫ:")
        print(f"   Средний gas: {avg_gas:,.0f}")
        print(f"   Средний gas price: {avg_gas_price:.2f} gwei")
        print(f"   Средняя стоимость: {avg_gas_cost:.6f} ETH (${avg_gas_cost * 3400:.2f})")

        if avg_gas > 500000:
            print(f"   💡 Высокий газ = сложная логика (flashloans?)")
        else:
            print(f"   💡 Низкий газ = простая ликвидация")

        # Проверяем все ли через контракт
        all_via_contract = all(p['is_contract_call'] for p in patterns)

        print(f"\n2. МЕТОД ЛИКВИДАЦИИ:")
        if all_via_contract:
            print(f"   ✅ Все ликвидации через смарт-контракт")
            print(f"   💡 Скорее всего использует flashloans")
            print(f"   💡 Автоматизированная стратегия")
        else:
            print(f"   📍 Прямые вызовы AAVE Pool")
            print(f"   💡 Возможно имеет капитал на балансе")

        # Анализ размеров
        large_liquidations = [l for l in liquidations_with_usd if l['debt_usd'] > 10000]
        small_liquidations = [l for l in liquidations_with_usd if l['debt_usd'] <= 1000]

        print(f"\n3. ПРЕДПОЧТЕНИЯ ПО РАЗМЕРУ:")
        print(f"   Крупные (>$10K): {len(large_liquidations)} ({len(large_liquidations)/len(liquidations_with_usd)*100:.1f}%)")
        print(f"   Мелкие (<$1K): {len(small_liquidations)} ({len(small_liquidations)/len(liquidations_with_usd)*100:.1f}%)")

        if len(large_liquidations) > len(small_liquidations):
            print(f"   💡 ФОКУС НА КРУПНЫХ позициях")
        else:
            print(f"   💡 Собирает и мелкие позиции")

        # Временной анализ
        blocks = [l['block_number'] for l in liquidations_with_usd]
        if len(blocks) > 1:
            block_intervals = [blocks[i] - blocks[i+1] for i in range(len(blocks)-1)]
            avg_interval = sum(block_intervals) / len(block_intervals) if block_intervals else 0

            print(f"\n4. АКТИВНОСТЬ:")
            print(f"   Средний интервал между ликвидациями: {avg_interval:,.0f} блоков")
            print(f"   Время: ~{avg_interval * 2 / 3600:.1f} часов")

            if avg_interval < 1000:
                print(f"   💡 ОЧЕНЬ АКТИВНЫЙ - мониторит постоянно")
            else:
                print(f"   💡 Умеренная активность")

        # Анализ активов
        collateral_assets = defaultdict(int)
        debt_assets = defaultdict(int)

        for liq in liquidations_with_usd:
            collateral_assets[liq['collateral_asset']] += 1
            debt_assets[liq['debt_asset']] += 1

        print(f"\n5. ПРЕДПОЧИТАЕМЫЕ АКТИВЫ:")
        print(f"   Collateral:")
        for asset, count in sorted(collateral_assets.items(), key=lambda x: x[1], reverse=True)[:3]:
            print(f"      {asset[:10]}...: {count} ликвидаций")

        print(f"   Debt:")
        for asset, count in sorted(debt_assets.items(), key=lambda x: x[1], reverse=True)[:3]:
            print(f"      {asset[:10]}...: {count} ликвидаций")

    # Финальные рекомендации
    print("\n" + "="*80)
    print("💡 РЕКОМЕНДАЦИИ ДЛЯ ВАШЕГО БОТА")
    print("="*80 + "\n")

    if is_contract:
        print("1. АВТОМАТИЗАЦИЯ:")
        print("   ✅ Топ-бот использует смарт-контракт")
        print("   ✅ Вам нужен свой контракт для ликвидаций")
        print("   ✅ Лучше с flashloan для безрискового капитала")

    print(f"\n2. СТРАТЕГИЯ:")
    print(f"   - Средняя прибыль: ${avg_bonus:,.0f}")
    print(f"   - Для прибыльности нужно делать {int(100/avg_bonus)} ликвидаций в месяц")
    print(f"   - Или фокусироваться только на крупных (>$10K)")

    print(f"\n3. КОНКУРЕНЦИЯ:")
    print(f"   - Этот бот сделал {len(liquidations_with_usd)} ликвидаций за месяц")
    print(f"   - Скорость реакции критична")
    print(f"   - Нужен мониторинг 24/7")

    if patterns and all_via_contract:
        print(f"\n4. ТЕХНОЛОГИЯ:")
        print(f"   - Flashloans для ликвидации без капитала")
        print(f"   - Автоматический мониторинг Health Factor")
        print(f"   - Возможно использует Flashbots/MEV для приоритета")

if __name__ == "__main__":
    main()
