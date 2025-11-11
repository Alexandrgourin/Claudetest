#!/usr/bin/env python3
"""
Точное измерение латентности флешблоков
Сравнение timestamp блока с текущим временем сервера
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Optional

# RPC endpoints
RPC_ENDPOINTS = {
    "Custom reth node": "http://80.209.241.37:8545/",
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
        print(f"❌ Error: {e}")
        return None

def measure_flashblock_latency(rpc_name: str, rpc_url: str, samples: int = 10) -> Dict:
    """
    Измерить латентность флешблока

    Латентность = Server_timestamp - Block_timestamp
    Показывает насколько "старый" флешблок мы получаем
    """
    print(f"\n{'='*70}")
    print(f"📊 Измеряю латентность: {rpc_name}")
    print(f"{'='*70}")

    latencies = []
    block_timestamps = []
    server_timestamps = []

    for i in range(samples):
        # Получаем текущее время сервера ДО запроса
        server_time_before = time.time()

        # Запрашиваем pending block
        block = rpc_call(rpc_url, "eth_getBlockByNumber", ["pending", False])

        # Получаем текущее время сервера ПОСЛЕ запроса
        server_time_after = time.time()

        # Среднее время - момент когда мы "получили" блок
        server_time_avg = (server_time_before + server_time_after) / 2

        if block and "timestamp" in block:
            # Конвертируем hex timestamp в decimal
            block_timestamp = int(block["timestamp"], 16)

            # Латентность = разница между временем сервера и временем блока
            latency_ms = (server_time_avg - block_timestamp) * 1000

            latencies.append(latency_ms)
            block_timestamps.append(block_timestamp)
            server_timestamps.append(server_time_avg)

            print(f"  Измерение {i+1}/{samples}:")
            print(f"    Block timestamp:  {block_timestamp} ({datetime.fromtimestamp(block_timestamp).strftime('%H:%M:%S.%f')[:-3]})")
            print(f"    Server timestamp: {server_time_avg:.3f} ({datetime.fromtimestamp(server_time_avg).strftime('%H:%M:%S.%f')[:-3]})")
            print(f"    Латентность:      {latency_ms:.1f} ms")
        else:
            print(f"  ❌ Измерение {i+1}/{samples} failed")

        # Пауза между измерениями
        if i < samples - 1:
            time.sleep(0.5)

    if not latencies:
        return {
            "rpc_name": rpc_name,
            "success": False,
            "error": "No successful measurements"
        }

    # Статистика
    avg_latency = sum(latencies) / len(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)

    print(f"\n📈 Статистика:")
    print(f"  Среднее:  {avg_latency:.1f} ms")
    print(f"  Минимум:  {min_latency:.1f} ms")
    print(f"  Максимум: {max_latency:.1f} ms")
    print(f"  Успешных измерений: {len(latencies)}/{samples}")

    return {
        "rpc_name": rpc_name,
        "success": True,
        "avg_latency_ms": avg_latency,
        "min_latency_ms": min_latency,
        "max_latency_ms": max_latency,
        "samples": len(latencies),
        "raw_latencies": latencies
    }

def main():
    print("🚀 Точное измерение латентности флешблоков")
    print("=" * 70)
    print("\nМетодология:")
    print("  1. Получаем pending block от RPC")
    print("  2. Извлекаем timestamp блока")
    print("  3. Сравниваем с текущим временем сервера")
    print("  4. Латентность = Server_time - Block_timestamp")
    print("\nЧем меньше латентность = тем свежее данные!")

    results = []

    # Измеряем каждый RPC
    for rpc_name, rpc_url in RPC_ENDPOINTS.items():
        result = measure_flashblock_latency(rpc_name, rpc_url, samples=10)
        results.append(result)

    # Итоговое сравнение
    print(f"\n\n{'='*70}")
    print("📊 ИТОГОВОЕ СРАВНЕНИЕ")
    print(f"{'='*70}\n")

    print(f"{'RPC Provider':<25} {'Средняя латентность':<25} {'Min/Max':<20}")
    print(f"{'-'*70}")

    successful_results = [r for r in results if r["success"]]

    for result in successful_results:
        name = result["rpc_name"]
        avg = result["avg_latency_ms"]
        min_lat = result["min_latency_ms"]
        max_lat = result["max_latency_ms"]

        print(f"{name:<25} {avg:>8.1f} ms {'':<14} {min_lat:>6.1f} / {max_lat:<6.1f} ms")

    # Находим самый быстрый
    if successful_results:
        fastest = min(successful_results, key=lambda x: x["avg_latency_ms"])

        print(f"\n{'='*70}")
        print(f"🏆 ПОБЕДИТЕЛЬ: {fastest['rpc_name']}")
        print(f"{'='*70}")
        print(f"Средняя латентность: {fastest['avg_latency_ms']:.1f} ms")

        # Сравнение с другими
        print(f"\n📊 Преимущество перед конкурентами:")
        for result in successful_results:
            if result["rpc_name"] != fastest["rpc_name"]:
                diff = result["avg_latency_ms"] - fastest["avg_latency_ms"]
                speedup = result["avg_latency_ms"] / fastest["avg_latency_ms"]
                print(f"  vs {result['rpc_name']:<20} +{diff:>6.1f} ms быстрее ({speedup:.2f}x)")

        print(f"\n💡 Интерпретация:")
        if fastest["avg_latency_ms"] < 200:
            print(f"  ✅ Отличная латентность! Флешблоки очень свежие (<200ms)")
        elif fastest["avg_latency_ms"] < 500:
            print(f"  ✅ Хорошая латентность! Флешблоки свежие (<500ms)")
        elif fastest["avg_latency_ms"] < 1000:
            print(f"  ⚠️  Средняя латентность. Флешблоки с задержкой (<1s)")
        else:
            print(f"  ❌ Высокая латентность! Флешблоки устаревшие (>1s)")

        print(f"\n🎯 Для ликвидаций:")
        if fastest["avg_latency_ms"] < 300:
            print(f"  ✅ Excellent! Можно успевать в топ 10-15% блока")
            print(f"  ✅ Конкурентное преимущество над Bot #2 (1500ms)")
        else:
            print(f"  ⚠️  Нужна оптимизация для конкуренции с топ ботами")

if __name__ == "__main__":
    main()
