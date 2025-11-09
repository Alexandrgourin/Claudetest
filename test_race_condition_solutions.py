#!/usr/bin/env python3
"""
Тест race condition с flashblocks и поиск решений

Проблема:
- eth_call('pending') берет snapshot на момент НАЧАЛА выполнения
- За время выполнения (~785ms) успевает сформироваться 3-4 новых flashblock
- Результат устаревает к моменту возврата

Решения для тестирования:
1. Использовать конкретный номер блока вместо 'pending'
2. Делать повторный запрос состояния после eth_call
3. Минимизировать время между чтением pending и eth_call
"""

import requests
import json
import time
from typing import Dict, List

NODE_URL = "http://80.209.241.37:8545/"

def rpc_call(method: str, params: List = None) -> Dict:
    """RPC вызов к ноде"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params if params else [],
        "id": 1
    }
    try:
        response = requests.post(NODE_URL, json=payload, timeout=30)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def test_solution_1_use_block_number():
    """
    Решение 1: Использовать конкретный номер блока вместо 'pending'

    Гипотеза: если мы зафиксируем номер блока, eth_call будет работать
    с этим конкретным состоянием, даже если блок уже изменился
    """
    print("\n" + "="*80)
    print("ТЕСТ 1: Использование конкретного номера блока")
    print("="*80 + "\n")

    pool_address = "0xb2cc224c1c9fee385f8ad6a55b4d94e92359dc59"
    slot0_data = "0x3850c7bd"

    # Шаг 1: Получаем pending block
    t1 = time.time()
    pending_result = rpc_call("eth_getBlockByNumber", ["pending", False])
    pending_block_hex = pending_result.get("result", {}).get("number", "0x0")
    pending_block_num = int(pending_block_hex, 16)
    pending_tx_count = len(pending_result.get("result", {}).get("transactions", []))
    t2 = time.time()

    print(f"📦 Pending block: {pending_block_hex} ({pending_block_num})")
    print(f"   Транзакций: {pending_tx_count}")
    print(f"   Время получения: {(t2-t1)*1000:.0f}ms\n")

    # Шаг 2: Сразу же делаем eth_call с этим номером блока
    t3 = time.time()
    call_result = rpc_call("eth_call", [{
        "to": pool_address,
        "data": slot0_data
    }, pending_block_hex])  # Используем конкретный номер!
    t4 = time.time()

    call_time_ms = (t4 - t3) * 1000
    print(f"⏱️  eth_call выполнился за: {call_time_ms:.0f}ms")

    if "result" in call_result:
        data = call_result["result"][2:]
        tick_hex = data[64:128]
        tick_raw = int(tick_hex, 16)
        tick_24bit = tick_raw & 0xFFFFFF
        tick = tick_24bit - 0x1000000 if tick_24bit & 0x800000 else tick_24bit
        print(f"✅ Получен tick: {tick:,}\n")

    # Шаг 3: Проверяем текущий pending block
    t5 = time.time()
    new_pending = rpc_call("eth_getBlockByNumber", ["pending", False])
    new_pending_hex = new_pending.get("result", {}).get("number", "0x0")
    new_pending_num = int(new_pending_hex, 16)
    new_tx_count = len(new_pending.get("result", {}).get("transactions", []))
    t6 = time.time()

    print(f"📦 Pending block ПОСЛЕ eth_call: {new_pending_hex} ({new_pending_num})")
    print(f"   Транзакций: {new_tx_count}")

    # Анализ
    blocks_passed = new_pending_num - pending_block_num
    total_time_ms = (t6 - t1) * 1000

    print(f"\n{'='*80}")
    print(f"📊 АНАЛИЗ:")
    print(f"{'='*80}")
    print(f"   Блоков прошло: {blocks_passed}")
    print(f"   Общее время: {total_time_ms:.0f}ms")
    print(f"   Время на eth_call: {call_time_ms:.0f}ms ({call_time_ms/total_time_ms*100:.1f}%)")

    if blocks_passed > 0:
        print(f"\n   ⚠️  ПРОБЛЕМА: За время теста pending изменился на {blocks_passed} блок(ов)")
        print(f"   💡 НО: eth_call использовал конкретный блок {pending_block_hex}")
        print(f"   ✅ Результат ВАЛИДЕН для блока {pending_block_hex}, но блок уже устарел")
    else:
        print(f"\n   ✅ Pending не изменился, результат актуален")

    return {
        "blocks_passed": blocks_passed,
        "call_time_ms": call_time_ms,
        "total_time_ms": total_time_ms,
        "solution": "use_block_number"
    }

def test_solution_2_rapid_sequence():
    """
    Решение 2: Быстрая последовательность запросов

    Минимизируем задержку между получением pending и eth_call
    """
    print("\n" + "="*80)
    print("ТЕСТ 2: Быстрая последовательность без задержек")
    print("="*80 + "\n")

    pool_address = "0xb2cc224c1c9fee385f8ad6a55b4d94e92359dc59"
    slot0_data = "0x3850c7bd"

    t_start = time.time()

    # Без задержек сразу запускаем оба запроса
    pending_result = rpc_call("eth_getBlockByNumber", ["pending", False])
    pending_block_hex = pending_result.get("result", {}).get("number", "0x0")
    pending_block_num = int(pending_block_hex, 16)

    t_before_call = time.time()

    # Сразу eth_call
    call_result = rpc_call("eth_call", [{
        "to": pool_address,
        "data": slot0_data
    }, "pending"])

    t_after_call = time.time()

    # Проверка
    new_pending = rpc_call("eth_getBlockByNumber", ["pending", False])
    new_pending_hex = new_pending.get("result", {}).get("number", "0x0")
    new_pending_num = int(new_pending_hex, 16)

    t_end = time.time()

    time_to_call = (t_before_call - t_start) * 1000
    call_duration = (t_after_call - t_before_call) * 1000
    total_time = (t_end - t_start) * 1000
    blocks_passed = new_pending_num - pending_block_num

    print(f"📦 Начальный pending: {pending_block_hex}")
    print(f"📦 Конечный pending: {new_pending_hex}")
    print(f"\n⏱️  Время до eth_call: {time_to_call:.0f}ms")
    print(f"⏱️  Длительность eth_call: {call_duration:.0f}ms")
    print(f"⏱️  Общее время: {total_time:.0f}ms")
    print(f"\n📊 Блоков прошло: {blocks_passed}")

    if blocks_passed == 0:
        print(f"   ✅ ОТЛИЧНО! Успели в рамках одного flashblock")
    else:
        print(f"   ⚠️  Даже при быстрой последовательности прошло {blocks_passed} блок(ов)")

    return {
        "blocks_passed": blocks_passed,
        "call_time_ms": call_duration,
        "total_time_ms": total_time,
        "solution": "rapid_sequence"
    }

def test_solution_3_verify_after():
    """
    Решение 3: Верификация после eth_call

    После получения результата eth_call проверяем, не изменился ли pending.
    Если изменился - повторяем запрос.
    """
    print("\n" + "="*80)
    print("ТЕСТ 3: Верификация с повтором при изменении")
    print("="*80 + "\n")

    pool_address = "0xb2cc224c1c9fee385f8ad6a55b4d94e92359dc59"
    slot0_data = "0x3850c7bd"

    max_attempts = 5
    attempt = 0

    while attempt < max_attempts:
        attempt += 1
        print(f"\n🔄 Попытка {attempt}/{max_attempts}")

        t_start = time.time()

        # Получаем pending
        pending_before = rpc_call("eth_getBlockByNumber", ["pending", False])
        block_before = pending_before.get("result", {}).get("number", "0x0")
        block_before_num = int(block_before, 16)

        # eth_call
        t_call_start = time.time()
        call_result = rpc_call("eth_call", [{
            "to": pool_address,
            "data": slot0_data
        }, block_before])  # Используем конкретный блок
        t_call_end = time.time()

        # Проверяем pending снова
        pending_after = rpc_call("eth_getBlockByNumber", ["pending", False])
        block_after = pending_after.get("result", {}).get("number", "0x0")
        block_after_num = int(block_after, 16)

        t_end = time.time()

        call_time = (t_call_end - t_call_start) * 1000
        total_time = (t_end - t_start) * 1000

        print(f"   Блок до: {block_before}")
        print(f"   Блок после: {block_after}")
        print(f"   Время eth_call: {call_time:.0f}ms")
        print(f"   Общее время: {total_time:.0f}ms")

        if block_before_num == block_after_num:
            print(f"\n   ✅ УСПЕХ! Блок не изменился, результат валиден")

            if "result" in call_result:
                data = call_result["result"][2:]
                tick_hex = data[64:128]
                tick_raw = int(tick_hex, 16)
                tick_24bit = tick_raw & 0xFFFFFF
                tick = tick_24bit - 0x1000000 if tick_24bit & 0x800000 else tick_24bit
                print(f"   Tick: {tick:,}")

            return {
                "success": True,
                "attempts": attempt,
                "call_time_ms": call_time,
                "total_time_ms": total_time,
                "solution": "verify_after"
            }
        else:
            blocks_diff = block_after_num - block_before_num
            print(f"   ⚠️  Блок изменился на {blocks_diff}, повторяем...")

    print(f"\n   ❌ Не удалось получить стабильный результат за {max_attempts} попыток")
    return {
        "success": False,
        "attempts": attempt,
        "solution": "verify_after"
    }

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                                                                      ║
    ║          ТЕСТИРОВАНИЕ РЕШЕНИЙ ДЛЯ RACE CONDITION                    ║
    ║                                                                      ║
    ║  Проблема: eth_call('pending') устаревает за время выполнения       ║
    ║  Flashblocks обновляются каждые ~200ms                              ║
    ║  eth_call выполняется ~785ms = 3-4 flashblocks                      ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)

    results = []

    # Тест 1: Использование конкретного номера блока
    try:
        result1 = test_solution_1_use_block_number()
        results.append(result1)
    except Exception as e:
        print(f"❌ Ошибка в тесте 1: {e}")

    time.sleep(1)  # Пауза между тестами

    # Тест 2: Быстрая последовательность
    try:
        result2 = test_solution_2_rapid_sequence()
        results.append(result2)
    except Exception as e:
        print(f"❌ Ошибка в тесте 2: {e}")

    time.sleep(1)

    # Тест 3: Верификация с повтором
    try:
        result3 = test_solution_3_verify_after()
        results.append(result3)
    except Exception as e:
        print(f"❌ Ошибка в тесте 3: {e}")

    # Итоговый анализ
    print("\n" + "="*80)
    print("📊 ИТОГОВЫЙ АНАЛИЗ РЕШЕНИЙ")
    print("="*80 + "\n")

    for i, result in enumerate(results, 1):
        print(f"{i}. {result['solution'].upper().replace('_', ' ')}")
        print(f"   Блоков прошло: {result.get('blocks_passed', 'N/A')}")
        print(f"   Время eth_call: {result.get('call_time_ms', 0):.0f}ms")
        print(f"   Общее время: {result.get('total_time_ms', 0):.0f}ms")

        if 'attempts' in result:
            print(f"   Попыток: {result['attempts']}")
            print(f"   Успех: {'✅' if result.get('success') else '❌'}")

        print()

    print("\n💡 РЕКОМЕНДАЦИИ ДЛЯ АРБИТРАЖА:")
    print("\n1. ЛУЧШЕЕ РЕШЕНИЕ: Использовать конкретный номер блока")
    print("   - Получить pending block number")
    print("   - Использовать его для eth_call вместо 'pending'")
    print("   - Результат будет валиден для этого конкретного блока")
    print("   - НО блок может уже устареть к моменту отправки транзакции")

    print("\n2. ДЛЯ КРИТИЧНЫХ СЛУЧАЕВ: Верификация с повтором")
    print("   - Проверять, не изменился ли pending после eth_call")
    print("   - Повторять, если изменился")
    print("   - Гарантирует актуальность, но медленнее")

    print("\n3. ОПТИМИЗАЦИЯ: Минимизировать задержки")
    print("   - Использовать HTTP keep-alive")
    print("   - Возможно, websocket вместо HTTP")
    print("   - Пайплайнинг запросов где возможно")

    print("\n4. ПРИНЯТЬ РЕАЛЬНОСТЬ:")
    print("   - За ~785ms формируется 3-4 flashblocks")
    print("   - Невозможно полностью избежать race condition")
    print("   - Нужно учитывать это в стратегии арбитража")
    print("   - Использовать safety margin в расчетах")
    print()

if __name__ == "__main__":
    main()
