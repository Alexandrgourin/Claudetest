#!/usr/bin/env python3
"""
Сравнение timestamp флешблоков между разными RPC
Проверяем насколько "свежие" или "старые" pending блоки
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, Optional

# RPC endpoints
RPC_ENDPOINTS = {
    "Custom reth": "http://80.209.241.37:8545/",
    "Alchemy": "https://base-mainnet.g.alchemy.com/v2/04r_vJrz9iSljxSQj8UQn",
    "Chainstack": "https://base-mainnet.core.chainstack.com/d28ec3a626cdc7f3e4c8bb04de7c7a88"
}

def rpc_call(url: str, method: str, params: list) -> Optional[Dict]:
    """Make RPC call"""
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        }
        response = requests.post(url, json=payload, timeout=10)
        result = response.json()
        return result.get("result")
    except Exception as e:
        print(f"      ❌ Error: {e}")
        return None

def check_flashblock_timestamp(rpc_name: str, rpc_url: str, samples: int = 20) -> Dict:
    """
    Проверить timestamp флешблока vs реальное время сервера

    Если разница:
    - Отрицательная (блок в будущем) = хороший pending блок ✅
    - Положительная (блок в прошлом) = устаревший блок ❌
    - Около 0 = идеальный синхрон
    """
    print(f"\n{'='*80}")
    print(f"📊 {rpc_name}")
    print(f"{'='*80}")

    differences = []
    block_timestamps = []
    server_timestamps = []

    for i in range(samples):
        # Получаем текущее время сервера В МИЛЛИСЕКУНДАХ (как в вашем Rust коде)
        server_time_ms = int(time.time() * 1000)

        # Запрашиваем pending block
        block = rpc_call(rpc_url, "eth_getBlockByNumber", ["pending", False])

        if block and "timestamp" in block:
            # Timestamp блока в hex, конвертируем в decimal
            block_timestamp_hex = block["timestamp"]
            block_timestamp_sec = int(block_timestamp_hex, 16)
            block_timestamp_ms = block_timestamp_sec * 1000

            # Разница: сервер - блок (положительная = блок старый)
            difference_ms = server_time_ms - block_timestamp_ms

            differences.append(difference_ms)
            block_timestamps.append(block_timestamp_ms)
            server_timestamps.append(server_time_ms)

            # Форматируем даты
            block_time_str = datetime.fromtimestamp(block_timestamp_sec).strftime('%Y-%m-%d %H:%M:%S')
            server_time_str = datetime.fromtimestamp(server_time_ms / 1000).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

            # Определяем статус
            if difference_ms < -1000:
                status = "🔮 в будущем (отличный pending!)"
            elif difference_ms < 0:
                status = "🔮 в будущем (хороший pending)"
            elif difference_ms < 500:
                status = "✅ синхронизирован"
            elif difference_ms < 2000:
                status = "⚠️  небольшая задержка"
            else:
                status = "❌ устаревший блок"

            print(f"  Измерение {i+1}/{samples}:")
            print(f"    Блок:    {block_timestamp_ms}ms ({block_time_str})")
            print(f"    Сервер:  {server_time_ms}ms ({server_time_str})")
            print(f"    Разница: {difference_ms:+d}ms {status}")
        else:
            print(f"  ❌ Измерение {i+1}/{samples} failed")

        # Небольшая пауза
        if i < samples - 1:
            time.sleep(0.2)

    if not differences:
        return {
            "rpc_name": rpc_name,
            "success": False
        }

    # Статистика
    avg_diff = sum(differences) / len(differences)
    min_diff = min(differences)
    max_diff = max(differences)

    print(f"\n📈 Статистика:")
    print(f"  Средняя разница:  {avg_diff:+.1f}ms")
    print(f"  Минимум:          {min_diff:+d}ms")
    print(f"  Максимум:         {max_diff:+d}ms")
    print(f"  Успешных:         {len(differences)}/{samples}")

    # Оценка
    if avg_diff < -500:
        grade = "🏆 ОТЛИЧНО - блоки в будущем!"
    elif avg_diff < 0:
        grade = "✅ ХОРОШО - блоки свежие"
    elif avg_diff < 1000:
        grade = "⚠️  СРЕДНЕ - небольшая задержка"
    elif avg_diff < 3000:
        grade = "❌ ПЛОХО - блоки устаревшие"
    else:
        grade = "💀 КРИТИЧНО - огромная задержка!"

    print(f"  Оценка:           {grade}")

    return {
        "rpc_name": rpc_name,
        "success": True,
        "avg_difference_ms": avg_diff,
        "min_difference_ms": min_diff,
        "max_difference_ms": max_diff,
        "samples": len(differences),
        "grade": grade
    }

def main():
    print("🚀 Сравнение TIMESTAMP флешблоков между RPC")
    print("=" * 80)
    print("\nПроверяем:")
    print("  - Насколько свежие pending блоки от каждого RPC")
    print("  - Разница между timestamp блока и реальным временем сервера")
    print("\nИнтерпретация:")
    print("  🔮 Отрицательная разница (блок в будущем) = ХОРОШО!")
    print("  ✅ Около нуля = отлично синхронизировано")
    print("  ❌ Положительная разница >2000ms = ПЛОХО (устаревший блок)")
    print()

    results = []

    # Проверяем каждый RPC
    for rpc_name, rpc_url in RPC_ENDPOINTS.items():
        result = check_flashblock_timestamp(rpc_name, rpc_url, samples=20)
        if result["success"]:
            results.append(result)

    # Итоговое сравнение
    print(f"\n\n{'='*80}")
    print("📊 ИТОГОВОЕ СРАВНЕНИЕ TIMESTAMP")
    print(f"{'='*80}\n")

    print(f"{'RPC Provider':<20} {'Средняя разница':<25} {'Min/Max':<30} {'Оценка':<20}")
    print(f"{'-'*95}")

    for result in sorted(results, key=lambda x: x["avg_difference_ms"]):
        name = result["rpc_name"]
        avg = result["avg_difference_ms"]
        min_d = result["min_difference_ms"]
        max_d = result["max_difference_ms"]
        grade = result["grade"]

        print(f"{name:<20} {avg:>+8.1f}ms {'':<14} {min_d:>+6d} / {max_d:<+6d}ms {grade:<20}")

    # Анализ вашей проблемы
    print(f"\n{'='*80}")
    print("🔍 АНАЛИЗ ВАШЕЙ ПРОБЛЕМЫ")
    print(f"{'='*80}\n")

    custom_result = next((r for r in results if "Custom" in r["rpc_name"]), None)

    if custom_result:
        avg_diff = custom_result["avg_difference_ms"]

        print(f"Ваша нода показывает среднюю разницу: {avg_diff:+.0f}ms")
        print()

        if avg_diff > 2000:
            print("❌ ПРОБЛЕМА ПОДТВЕРЖДЕНА!")
            print()
            print("Ваш pending блок на 2-3 секунды старее реального времени.")
            print("Это означает:")
            print("  1. Вы получаете СТАРЫЕ pending блоки")
            print("  2. Oracle updates уже произошли, но вы видите их с задержкой")
            print("  3. Конкуренты на Alchemy/Chainstack видят обновления РАНЬШЕ вас!")
            print()
            print("🔧 Возможные причины:")
            print("  - Проблема синхронизации времени на сервере (проверьте NTP)")
            print("  - Проблема конфигурации reth ноды")
            print("  - Нода отстает от сети")
            print()
            print("⚡ Срочно нужно:")
            print("  1. Проверить синхронизацию времени: timedatectl status")
            print("  2. Проверить статус ноды: curl http://80.209.241.37:8545 -X POST -H 'Content-Type: application/json' -d '{\"jsonrpc\":\"2.0\",\"method\":\"eth_syncing\",\"params\":[],\"id\":1}'")
            print("  3. Сравнить block number вашей ноды с публичными RPC")

        elif avg_diff > 0:
            print("⚠️  Небольшая задержка")
            print(f"Ваш pending блок старее на {avg_diff:.0f}ms")
            print("Это не критично, но можно улучшить.")

        else:
            print("✅ Все отлично!")
            print("Ваш pending блок в будущем - это правильное поведение!")

        # Сравнение с конкурентами
        print(f"\n{'='*80}")
        print("⚔️  СРАВНЕНИЕ С КОНКУРЕНТАМИ")
        print(f"{'='*80}\n")

        for result in results:
            if "Custom" not in result["rpc_name"]:
                competitor_diff = result["avg_difference_ms"]
                advantage = competitor_diff - avg_diff

                print(f"{result['rpc_name']}:")
                print(f"  Их разница:    {competitor_diff:+.0f}ms")
                print(f"  Ваше преимущество: {advantage:+.0f}ms")

                if advantage > 0:
                    print(f"  ✅ Вы на {advantage:.0f}ms БЫСТРЕЕ!")
                elif advantage < 0:
                    print(f"  ❌ Вы на {abs(advantage):.0f}ms МЕДЛЕННЕЕ!")
                else:
                    print(f"  ⚖️  Одинаково")
                print()

if __name__ == "__main__":
    main()
