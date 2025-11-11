#!/usr/bin/env python3
"""
Правильное измерение латентности RPC
1. Задержка получения latest блока (насколько свежий подтвержденный блок)
2. Задержка получения pending блока (для флешблоков)
3. Сколько транзакций в pending блоке
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Optional

# RPC endpoints
RPC_ENDPOINTS = {
    "Custom reth": "http://80.209.241.37:8545/",
    "Alchemy": "https://base-mainnet.g.alchemy.com/v2/04r_vJrz9iSljxSQj8UQn",
    "Chainstack": "https://base-mainnet.core.chainstack.com/d28ec3a626cdc7f3e4c8bb04de7c7a88"
}

def rpc_call(url: str, method: str, params: list) -> tuple[Optional[Dict], float]:
    """Make RPC call and return result + request time"""
    try:
        start_time = time.time()
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        }
        response = requests.post(url, json=payload, timeout=10)
        request_time = (time.time() - start_time) * 1000  # ms
        result = response.json()
        return result.get("result"), request_time
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return None, 0

def measure_latest_block_freshness(rpc_name: str, rpc_url: str, samples: int = 10) -> Dict:
    """
    Измерить свежесть последнего подтвержденного блока

    Freshness = (Server_time - Block_timestamp)
    Чем меньше = тем свежее блок
    """
    print(f"\n{'='*70}")
    print(f"📊 Измеряю LATEST блоки: {rpc_name}")
    print(f"{'='*70}")

    freshness_values = []
    request_times = []

    for i in range(samples):
        # Запрашиваем latest block
        server_time_start = time.time()
        block, request_time = rpc_call(rpc_url, "eth_getBlockByNumber", ["latest", False])
        server_time_end = time.time()

        server_time_avg = (server_time_start + server_time_end) / 2

        if block and "timestamp" in block:
            block_timestamp = int(block["timestamp"], 16)
            block_number = int(block["number"], 16)

            # Freshness = насколько блок "старый"
            freshness_ms = (server_time_avg - block_timestamp) * 1000

            freshness_values.append(freshness_ms)
            request_times.append(request_time)

            print(f"  Измерение {i+1}/{samples}:")
            print(f"    Block #{block_number}")
            print(f"    Request time:  {request_time:.1f} ms")
            print(f"    Block age:     {freshness_ms:.1f} ms (свежесть)")
        else:
            print(f"  ❌ Измерение {i+1}/{samples} failed")

        if i < samples - 1:
            time.sleep(0.3)

    if not freshness_values:
        return {"success": False}

    avg_freshness = sum(freshness_values) / len(freshness_values)
    avg_request_time = sum(request_times) / len(request_times)

    print(f"\n📈 Статистика LATEST:")
    print(f"  Средняя свежесть блока: {avg_freshness:.1f} ms")
    print(f"  Среднее время запроса:  {avg_request_time:.1f} ms")

    return {
        "rpc_name": rpc_name,
        "success": True,
        "avg_freshness_ms": avg_freshness,
        "avg_request_time_ms": avg_request_time,
        "min_freshness_ms": min(freshness_values),
        "max_freshness_ms": max(freshness_values)
    }

def measure_pending_block(rpc_name: str, rpc_url: str, samples: int = 10) -> Dict:
    """
    Измерить pending блок (флешблок)

    Проверяем:
    - Сколько транзакций в pending
    - Как быстро получаем pending
    - Timestamp pending блока (может быть в будущем)
    """
    print(f"\n{'='*70}")
    print(f"📊 Измеряю PENDING блоки: {rpc_name}")
    print(f"{'='*70}")

    tx_counts = []
    request_times = []
    timestamp_diffs = []

    for i in range(samples):
        server_time_start = time.time()
        block, request_time = rpc_call(rpc_url, "eth_getBlockByNumber", ["pending", True])
        server_time_end = time.time()

        server_time_avg = (server_time_start + server_time_end) / 2

        if block:
            tx_count = len(block.get("transactions", []))
            tx_counts.append(tx_count)
            request_times.append(request_time)

            # Timestamp может быть в будущем для pending блока
            if "timestamp" in block:
                block_timestamp = int(block["timestamp"], 16)
                timestamp_diff = (block_timestamp - server_time_avg) * 1000
                timestamp_diffs.append(timestamp_diff)

                status = "🔮 в будущем" if timestamp_diff > 0 else "⏪ в прошлом"

                print(f"  Измерение {i+1}/{samples}:")
                print(f"    Request time:    {request_time:.1f} ms")
                print(f"    Транзакций:      {tx_count}")
                print(f"    Timestamp diff:  {timestamp_diff:+.1f} ms ({status})")
            else:
                print(f"  Измерение {i+1}/{samples}:")
                print(f"    Request time:    {request_time:.1f} ms")
                print(f"    Транзакций:      {tx_count}")
                print(f"    Timestamp:       отсутствует")
        else:
            print(f"  ❌ Измерение {i+1}/{samples} failed")

        if i < samples - 1:
            time.sleep(0.3)

    if not tx_counts:
        return {"success": False}

    avg_tx_count = sum(tx_counts) / len(tx_counts)
    avg_request_time = sum(request_times) / len(request_times)
    avg_timestamp_diff = sum(timestamp_diffs) / len(timestamp_diffs) if timestamp_diffs else 0

    print(f"\n📈 Статистика PENDING:")
    print(f"  Среднее транзакций:     {avg_tx_count:.1f}")
    print(f"  Среднее время запроса:  {avg_request_time:.1f} ms")
    if timestamp_diffs:
        print(f"  Средний timestamp diff: {avg_timestamp_diff:+.1f} ms")

    return {
        "rpc_name": rpc_name,
        "success": True,
        "avg_tx_count": avg_tx_count,
        "avg_request_time_ms": avg_request_time,
        "avg_timestamp_diff_ms": avg_timestamp_diff,
        "has_pending_support": len(tx_counts) > 0
    }

def main():
    print("🚀 Комплексное измерение латентности RPC")
    print("=" * 70)

    all_results = {}

    # Тест 1: Latest блоки
    print("\n" + "="*70)
    print("ТЕСТ 1: СВЕЖЕСТЬ LATEST БЛОКОВ")
    print("="*70)
    print("Измеряем насколько быстро RPC отдает подтвержденные блоки\n")

    latest_results = []
    for rpc_name, rpc_url in RPC_ENDPOINTS.items():
        result = measure_latest_block_freshness(rpc_name, rpc_url, samples=10)
        if result.get("success"):
            latest_results.append(result)
            all_results[rpc_name] = result

    # Тест 2: Pending блоки
    print("\n" + "="*70)
    print("ТЕСТ 2: PENDING БЛОКИ (ФЛЕШБЛОКИ)")
    print("="*70)
    print("Измеряем скорость получения pending блоков и количество транзакций\n")

    pending_results = []
    for rpc_name, rpc_url in RPC_ENDPOINTS.items():
        result = measure_pending_block(rpc_name, rpc_url, samples=10)
        if result.get("success"):
            pending_results.append(result)
            if rpc_name in all_results:
                all_results[rpc_name].update(result)

    # Итоговое сравнение
    print(f"\n\n{'='*70}")
    print("📊 ИТОГОВОЕ СРАВНЕНИЕ")
    print(f"{'='*70}\n")

    print("LATEST блоки (подтвержденные):")
    print(f"{'RPC':<20} {'Request':<12} {'Block age':<15} {'Оценка':<20}")
    print(f"{'-'*70}")

    for result in sorted(latest_results, key=lambda x: x["avg_freshness_ms"]):
        name = result["rpc_name"]
        req_time = result["avg_request_time_ms"]
        freshness = result["avg_freshness_ms"]

        if freshness < 500:
            grade = "🏆 Отлично"
        elif freshness < 1000:
            grade = "✅ Хорошо"
        elif freshness < 2000:
            grade = "⚠️  Средне"
        else:
            grade = "❌ Плохо"

        print(f"{name:<20} {req_time:>6.1f} ms    {freshness:>8.1f} ms    {grade:<20}")

    print("\n" + "="*70)
    print("\nPENDING блоки (флешблоки):")
    print(f"{'RPC':<20} {'Request':<12} {'Avg TXs':<12} {'Оценка':<20}")
    print(f"{'-'*70}")

    for result in sorted(pending_results, key=lambda x: x["avg_request_time_ms"]):
        name = result["rpc_name"]
        req_time = result["avg_request_time_ms"]
        tx_count = result["avg_tx_count"]

        if req_time < 100 and tx_count > 50:
            grade = "🏆 Отлично"
        elif req_time < 200 and tx_count > 20:
            grade = "✅ Хорошо"
        elif req_time < 500:
            grade = "⚠️  Средне"
        else:
            grade = "❌ Плохо"

        print(f"{name:<20} {req_time:>6.1f} ms    {tx_count:>6.1f}       {grade:<20}")

    # Финальные рекомендации
    print(f"\n{'='*70}")
    print("🎯 РЕКОМЕНДАЦИИ ДЛЯ ЛИКВИДАЦИОННОГО БОТА")
    print(f"{'='*70}\n")

    if latest_results:
        best_latest = min(latest_results, key=lambda x: x["avg_freshness_ms"])
        print(f"1. Самый свежий latest блок: {best_latest['rpc_name']}")
        print(f"   Block age: {best_latest['avg_freshness_ms']:.1f} ms")
        print(f"   Request time: {best_latest['avg_request_time_ms']:.1f} ms\n")

    if pending_results:
        best_pending = min(pending_results, key=lambda x: x["avg_request_time_ms"])
        print(f"2. Самый быстрый pending: {best_pending['rpc_name']}")
        print(f"   Request time: {best_pending['avg_request_time_ms']:.1f} ms")
        print(f"   Avg transactions: {best_pending['avg_tx_count']:.1f}\n")

    print("💡 Стратегия:")
    print("  - Используйте PENDING блоки для детекции oracle updates")
    print("  - Чем меньше request time для pending = тем быстрее реакция")
    print("  - Отрицательный timestamp diff (будущее) = это нормально!")
    print("  - Целевая латентность: <100ms для pending блоков")

if __name__ == "__main__":
    main()
