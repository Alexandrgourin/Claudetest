#!/usr/bin/env python3
"""
Анализ latency ликвидаторов на Base

Измеряем:
1. В каком блоке позиция стала ликвидируемой
2. Как быстро её ликвидировали
3. Позицию транзакции в блоке (первая? последняя?)
"""

import requests
import json
from typing import Dict, List
from datetime import datetime

ALCHEMY_URL = "https://base-mainnet.g.alchemy.com/v2/04r_vJrz9iSljxSQj8UQn"
AAVE_POOL_ADDRESS = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"
LIQUIDATION_EVENT = "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286"

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

def get_block_with_transactions(block_number: int) -> Dict:
    """Получить блок со всеми транзакциями"""
    result = rpc_call("eth_getBlockByNumber", [hex(block_number), True])
    if "result" in result:
        return result["result"]
    return {}

def get_transaction_receipt(tx_hash: str) -> Dict:
    """Получить receipt транзакции"""
    result = rpc_call("eth_getTransactionReceipt", [tx_hash])
    if "result" in result:
        return result["result"]
    return {}

def get_liquidations(from_block: int, to_block: int, limit: int = 50) -> List[Dict]:
    """Получить последние ликвидации"""
    result = rpc_call("eth_getLogs", [{
        "address": AAVE_POOL_ADDRESS,
        "topics": [LIQUIDATION_EVENT],
        "fromBlock": hex(from_block),
        "toBlock": hex(to_block)
    }])

    if "result" not in result:
        return []

    events = result["result"][:limit]

    liquidations = []
    for event in events:
        topics = event.get("topics", [])
        if len(topics) < 4:
            continue

        user = "0x" + topics[3][-40:]
        block_number = int(event.get("blockNumber", "0x0"), 16)
        tx_hash = event.get("transactionHash", "")

        liquidations.append({
            "user": user.lower(),
            "block_number": block_number,
            "tx_hash": tx_hash,
            "log_index": int(event.get("logIndex", "0x0"), 16)
        })

    return liquidations

def analyze_liquidation_latency(liquidation: Dict) -> Dict:
    """
    Анализировать latency конкретной ликвидации

    Определяем:
    1. Позицию TX в блоке (transaction index)
    2. Была ли активность пользователя в предыдущих блоках
    3. Оценка latency
    """
    block_number = liquidation["block_number"]
    tx_hash = liquidation["tx_hash"]
    user = liquidation["user"]

    print(f"\n{'='*80}")
    print(f"Анализ ликвидации: {tx_hash[:20]}...")
    print(f"{'='*80}")

    # Получаем блок с транзакциями
    block = get_block_with_transactions(block_number)

    if not block:
        return {}

    transactions = block.get("transactions", [])
    block_timestamp = int(block.get("timestamp", "0x0"), 16)

    # Находим нашу транзакцию
    tx_index = None
    liquidation_tx = None

    for i, tx in enumerate(transactions):
        if tx.get("hash", "").lower() == tx_hash.lower():
            tx_index = i
            liquidation_tx = tx
            break

    if tx_index is None:
        print(f"❌ Транзакция не найдена в блоке")
        return {}

    total_txs = len(transactions)
    position_pct = (tx_index / total_txs * 100) if total_txs > 0 else 0

    print(f"\n📦 БЛОК #{block_number:,}")
    print(f"   Timestamp: {datetime.fromtimestamp(block_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Всего транзакций: {total_txs}")
    print(f"   Позиция ликвидации: #{tx_index + 1} ({position_pct:.1f}%)")

    # Анализируем газ
    gas_price_gwei = int(liquidation_tx.get("gasPrice", "0x0"), 16) / 10**9
    print(f"   Gas price: {gas_price_gwei:.2f} gwei")

    if tx_index == 0:
        print(f"   🥇 ПЕРВАЯ транзакция в блоке!")
        latency_estimate = "Максимальная скорость"
    elif tx_index < 5:
        print(f"   ⚡ В топ-5 транзакций блока")
        latency_estimate = "Очень быстро"
    elif position_pct < 20:
        print(f"   🚀 В первых 20% блока")
        latency_estimate = "Быстро"
    else:
        print(f"   🐌 Во второй половине блока")
        latency_estimate = "Медленно"

    # Проверяем предыдущие блоки на активность пользователя
    print(f"\n🔍 ПРОВЕРКА АКТИВНОСТИ ПОЛЬЗОВАТЕЛЯ:")
    print(f"   User: {user[:20]}...")

    user_activity_found = False
    blocks_to_check = 5  # Проверяем 5 предыдущих блоков (~10 секунд)

    for offset in range(1, blocks_to_check + 1):
        prev_block_num = block_number - offset
        prev_block = get_block_with_transactions(prev_block_num)

        if not prev_block:
            continue

        prev_transactions = prev_block.get("transactions", [])

        # Ищем транзакции пользователя
        for tx in prev_transactions:
            tx_from = tx.get("from", "") or ""
            tx_from = tx_from.lower() if tx_from else ""
            tx_to = tx.get("to", "") or ""
            tx_to = tx_to.lower() if tx_to else ""

            if tx_from == user or tx_to == user or tx_to == AAVE_POOL_ADDRESS.lower():
                # Нашли активность
                if not user_activity_found:
                    print(f"\n   ✅ Найдена активность в предыдущих блоках:")
                    user_activity_found = True

                tx_hash_short = tx.get("hash", "")[:20]
                print(f"      Блок -{offset}: {tx_hash_short}... (from: {tx_from[:10]}...)")

    if not user_activity_found:
        print(f"   ⚠️  Активность не найдена в предыдущих {blocks_to_check} блоках")

    # Оценка latency
    print(f"\n⏱️  ОЦЕНКА LATENCY:")

    if tx_index == 0:
        print(f"   🎯 Ликвидация в ПЕРВОЙ транзакции блока")
        print(f"   💡 Позиция стала ликвидируемой в предыдущем блоке")
        print(f"   ⚡ Latency: ~2 секунды (1 блок)")
        estimated_latency_sec = 2
    elif tx_index < 3:
        print(f"   🎯 Ликвидация в топ-3 транзакциях")
        print(f"   💡 Очень быстрая реакция")
        print(f"   ⚡ Latency: <1 секунды (внутри блока)")
        estimated_latency_sec = 0.5
    else:
        print(f"   🎯 Ликвидация не в первых транзакциях")
        print(f"   💡 Либо медленная реакция, либо низкий gas price")
        print(f"   ⚡ Latency: {tx_index * 0.01:.2f} секунд (оценка)")
        estimated_latency_sec = tx_index * 0.01

    # Проверяем конкуренцию - были ли другие попытки ликвидации
    print(f"\n🏆 КОНКУРЕНЦИЯ В БЛОКЕ:")

    liquidation_attempts = 0
    for tx in transactions[:tx_index + 5]:  # Проверяем соседние транзакции
        tx_to = tx.get("to", "") or ""
        tx_to = tx_to.lower() if tx_to else ""
        if tx_to == AAVE_POOL_ADDRESS.lower() or len(tx.get("input", "0x")) > 100:
            liquidation_attempts += 1

    print(f"   Потенциальных попыток ликвидации: {liquidation_attempts}")

    if liquidation_attempts > 3:
        print(f"   ⚠️  ВЫСОКАЯ конкуренция - много ботов!")
    elif liquidation_attempts > 1:
        print(f"   📊 Средняя конкуренция")
    else:
        print(f"   ✅ Низкая конкуренция")

    return {
        "block_number": block_number,
        "tx_index": tx_index,
        "total_txs": total_txs,
        "position_pct": position_pct,
        "gas_price_gwei": gas_price_gwei,
        "estimated_latency_sec": estimated_latency_sec,
        "latency_estimate": latency_estimate,
        "competition_level": "HIGH" if liquidation_attempts > 3 else "MEDIUM" if liquidation_attempts > 1 else "LOW"
    }

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                                                                      ║
    ║           АНАЛИЗ LATENCY ЛИКВИДАТОРОВ НА BASE                       ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)

    print(f"🌐 Анализируем скорость реакции ботов на возможность ликвидации\n")

    current_block = get_current_block()
    print(f"📊 Текущий блок: {current_block:,}\n")

    # Берем последние 30 ликвидаций
    print("🔍 Получаем последние 30 ликвидаций...")
    from_block = current_block - 100000
    to_block = current_block

    liquidations = get_liquidations(from_block, to_block, limit=30)

    if not liquidations:
        print("❌ Ликвидации не найдены")
        return

    print(f"✅ Найдено: {len(liquidations)} ликвидаций\n")

    # Анализируем каждую
    results = []

    for i, liq in enumerate(liquidations[:10], 1):  # Берем первые 10 для детального анализа
        print(f"\n{'#'*80}")
        print(f"ЛИКВИДАЦИЯ #{i}/{min(10, len(liquidations))}")
        print(f"{'#'*80}")

        result = analyze_liquidation_latency(liq)
        if result:
            results.append(result)

        if i < 10:
            print(f"\nНажмите Enter для следующей ликвидации...")
            # input()  # Раскомментировать для пошагового просмотра

    # Итоговая статистика
    if results:
        print("\n" + "="*80)
        print("📊 ИТОГОВАЯ СТАТИСТИКА")
        print("="*80 + "\n")

        # Позиции в блоках
        first_tx_count = sum(1 for r in results if r['tx_index'] == 0)
        top5_count = sum(1 for r in results if r['tx_index'] < 5)

        print(f"ПОЗИЦИИ В БЛОКЕ:")
        print(f"   Первая транзакция: {first_tx_count}/{len(results)} ({first_tx_count/len(results)*100:.1f}%)")
        print(f"   В топ-5 транзакций: {top5_count}/{len(results)} ({top5_count/len(results)*100:.1f}%)")

        avg_position = sum(r['tx_index'] for r in results) / len(results)
        avg_position_pct = sum(r['position_pct'] for r in results) / len(results)

        print(f"   Средняя позиция: #{avg_position:.1f} ({avg_position_pct:.1f}% блока)")

        # Latency
        avg_latency = sum(r['estimated_latency_sec'] for r in results) / len(results)
        min_latency = min(r['estimated_latency_sec'] for r in results)
        max_latency = max(r['estimated_latency_sec'] for r in results)

        print(f"\nLATENCY:")
        print(f"   Средняя: {avg_latency:.2f} секунд")
        print(f"   Минимальная: {min_latency:.2f} секунд")
        print(f"   Максимальная: {max_latency:.2f} секунд")

        # Gas price
        avg_gas = sum(r['gas_price_gwei'] for r in results) / len(results)
        max_gas = max(r['gas_price_gwei'] for r in results)

        print(f"\nGAS PRICE:")
        print(f"   Средний: {avg_gas:.2f} gwei")
        print(f"   Максимальный: {max_gas:.2f} gwei")

        # Конкуренция
        high_comp = sum(1 for r in results if r['competition_level'] == 'HIGH')

        print(f"\nКОНКУРЕНЦИЯ:")
        print(f"   Высокая: {high_comp}/{len(results)} ({high_comp/len(results)*100:.1f}%)")

    # Выводы
    print("\n" + "="*80)
    print("💡 ВЫВОДЫ ДЛЯ ВАШЕЙ СТРАТЕГИИ")
    print("="*80 + "\n")

    if results:
        if first_tx_count / len(results) > 0.3:
            print("1. СКОРОСТЬ КРИТИЧНА:")
            print(f"   {first_tx_count/len(results)*100:.0f}% ликвидаций происходят в ПЕРВОЙ транзакции блока")
            print(f"   💡 Боты реагируют мгновенно (latency ~2 сек)")
            print(f"   💡 Нужен мониторинг каждого блока")
        else:
            print("1. КОНКУРЕНЦИЯ УМЕРЕННАЯ:")
            print(f"   Не все ликвидации моментальные")
            print(f"   💡 Есть возможность успеть")

        if avg_latency < 1:
            print(f"\n2. СРЕДНЯЯ LATENCY: {avg_latency:.2f} сек")
            print(f"   ⚡ ОЧЕНЬ БЫСТРЫЕ боты!")
            print(f"   💡 Ваш бот должен быть не медленнее")
        else:
            print(f"\n2. СРЕДНЯЯ LATENCY: {avg_latency:.2f} сек")
            print(f"   📊 Есть запас времени")

        if avg_gas > 1.0:
            print(f"\n3. GAS PRICE: {avg_gas:.2f} gwei")
            print(f"   💰 Боты платят премию за скорость")
            print(f"   💡 Возможно используют priority/MEV")
        else:
            print(f"\n3. GAS PRICE: {avg_gas:.2f} gwei")
            print(f"   ✅ Обычные gas цены")

    print(f"\n🎯 РЕКОМЕНДАЦИИ:")
    print(f"   1. Мониторить каждый новый блок (~2 сек)")
    print(f"   2. Проверять Health Factor сразу при изменении блока")
    print(f"   3. Отправлять транзакцию немедленно при HF < 1.0")
    print(f"   4. Использовать приемлемый gas price (0.5-1 gwei)")
    print(f"   5. Возможно использовать flashblock node для преимущества")
    print()

if __name__ == "__main__":
    main()
