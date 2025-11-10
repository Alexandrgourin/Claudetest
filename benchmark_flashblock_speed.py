#!/usr/bin/env python3
"""
Бенчмарк скорости получения pending блока (flashblock) на разных RPC

Сравниваем:
1. Собственная reth нода с flashblocks
2. Alchemy RPC
3. Chainstack RPC (HTTPS + WebSocket)

Замеряем:
- Latency (скорость ответа)
- Количество pending транзакций
- Поддержку pending блоков
"""

import requests
import json
import time
import statistics
from typing import Dict, List, Optional
import asyncio
import websockets

# RPC endpoints
CUSTOM_NODE = "http://80.209.241.37:8545/"
ALCHEMY = "https://base-mainnet.g.alchemy.com/v2/04r_vJrz9iSljxSQj8UQn"
CHAINSTACK_HTTPS = "https://base-mainnet.core.chainstack.com/d28ec3a626cdc7f3e4c8bb04de7c7a88"
CHAINSTACK_WSS = "wss://base-mainnet.core.chainstack.com/d28ec3a626cdc7f3e4c8bb04de7c7a88"

def rpc_call_http(url: str, method: str, params: List = None) -> tuple[Optional[Dict], float]:
    """
    HTTP RPC вызов с замером времени

    Returns: (result, latency_ms)
    """
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params if params else [],
        "id": 1
    }

    start = time.time()

    try:
        response = requests.post(url, json=payload, timeout=5)
        latency = (time.time() - start) * 1000  # в миллисекундах

        if response.status_code == 200:
            return response.json(), latency
        else:
            return {"error": f"HTTP {response.status_code}"}, latency

    except Exception as e:
        latency = (time.time() - start) * 1000
        return {"error": str(e)}, latency

async def rpc_call_ws(url: str, method: str, params: List = None) -> tuple[Optional[Dict], float]:
    """
    WebSocket RPC вызов с замером времени

    Returns: (result, latency_ms)
    """
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params if params else [],
        "id": 1
    }

    start = time.time()

    try:
        async with websockets.connect(url) as ws:
            await ws.send(json.dumps(payload))
            response = await ws.recv()
            latency = (time.time() - start) * 1000

            return json.loads(response), latency

    except Exception as e:
        latency = (time.time() - start) * 1000
        return {"error": str(e)}, latency

def test_pending_block_http(name: str, url: str, iterations: int = 10) -> Dict:
    """
    Тест получения pending блока через HTTP
    """
    print(f"\n{'='*80}")
    print(f"🧪 Тестируем: {name}")
    print(f"   URL: {url}")
    print(f"{'='*80}")

    latencies = []
    tx_counts = []
    errors = 0
    no_pending = 0

    for i in range(iterations):
        result, latency = rpc_call_http(url, "eth_getBlockByNumber", ["pending", True])

        latencies.append(latency)

        if "error" in result:
            errors += 1
            print(f"   #{i+1:2d}: ❌ ERROR - {result['error'][:50]} ({latency:.0f}ms)")
        elif "result" not in result or result["result"] is None:
            no_pending += 1
            print(f"   #{i+1:2d}: ⚠️  NO PENDING BLOCK ({latency:.0f}ms)")
        else:
            block = result["result"]
            txs = block.get("transactions", [])
            tx_count = len(txs)
            tx_counts.append(tx_count)

            if tx_count > 0:
                print(f"   #{i+1:2d}: ✅ {tx_count:4d} pending txs ({latency:.0f}ms)")
            else:
                print(f"   #{i+1:2d}: 📭 0 pending txs ({latency:.0f}ms)")

        time.sleep(0.5)  # Небольшая пауза между запросами

    # Статистика
    print(f"\n📊 РЕЗУЛЬТАТЫ:")

    if latencies:
        avg_latency = statistics.mean(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        median_latency = statistics.median(latencies)

        print(f"\n   LATENCY:")
        print(f"      Средний: {avg_latency:.2f}ms")
        print(f"      Медиана: {median_latency:.2f}ms")
        print(f"      Мин: {min_latency:.2f}ms")
        print(f"      Макс: {max_latency:.2f}ms")

    if tx_counts:
        avg_txs = statistics.mean(tx_counts)
        min_txs = min(tx_counts)
        max_txs = max(tx_counts)

        print(f"\n   PENDING ТРАНЗАКЦИИ:")
        print(f"      Среднее: {avg_txs:.1f}")
        print(f"      Мин: {min_txs}")
        print(f"      Макс: {max_txs}")
    else:
        print(f"\n   ⚠️  Pending транзакции НЕ НАЙДЕНЫ")

    print(f"\n   НАДЕЖНОСТЬ:")
    print(f"      Ошибки: {errors}/{iterations} ({errors/iterations*100:.1f}%)")
    print(f"      Нет pending: {no_pending}/{iterations} ({no_pending/iterations*100:.1f}%)")
    print(f"      Успешно: {iterations-errors-no_pending}/{iterations} ({(iterations-errors-no_pending)/iterations*100:.1f}%)")

    success_rate = (iterations - errors - no_pending) / iterations
    has_pending_txs = len(tx_counts) > 0 and statistics.mean(tx_counts) > 0

    return {
        "name": name,
        "url": url,
        "protocol": "HTTP",
        "avg_latency": statistics.mean(latencies) if latencies else 0,
        "median_latency": statistics.median(latencies) if latencies else 0,
        "min_latency": min(latencies) if latencies else 0,
        "max_latency": max(latencies) if latencies else 0,
        "avg_tx_count": statistics.mean(tx_counts) if tx_counts else 0,
        "max_tx_count": max(tx_counts) if tx_counts else 0,
        "success_rate": success_rate,
        "errors": errors,
        "no_pending": no_pending,
        "has_pending_txs": has_pending_txs
    }

async def test_pending_block_ws(name: str, url: str, iterations: int = 10) -> Dict:
    """
    Тест получения pending блока через WebSocket
    """
    print(f"\n{'='*80}")
    print(f"🧪 Тестируем: {name} (WebSocket)")
    print(f"   URL: {url}")
    print(f"{'='*80}")

    latencies = []
    tx_counts = []
    errors = 0
    no_pending = 0

    for i in range(iterations):
        result, latency = await rpc_call_ws(url, "eth_getBlockByNumber", ["pending", True])

        latencies.append(latency)

        if "error" in result:
            errors += 1
            print(f"   #{i+1:2d}: ❌ ERROR - {result['error'][:50]} ({latency:.0f}ms)")
        elif "result" not in result or result["result"] is None:
            no_pending += 1
            print(f"   #{i+1:2d}: ⚠️  NO PENDING BLOCK ({latency:.0f}ms)")
        else:
            block = result["result"]
            txs = block.get("transactions", [])
            tx_count = len(txs)
            tx_counts.append(tx_count)

            if tx_count > 0:
                print(f"   #{i+1:2d}: ✅ {tx_count:4d} pending txs ({latency:.0f}ms)")
            else:
                print(f"   #{i+1:2d}: 📭 0 pending txs ({latency:.0f}ms)")

        await asyncio.sleep(0.5)

    # Статистика
    print(f"\n📊 РЕЗУЛЬТАТЫ:")

    if latencies:
        avg_latency = statistics.mean(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        median_latency = statistics.median(latencies)

        print(f"\n   LATENCY:")
        print(f"      Средний: {avg_latency:.2f}ms")
        print(f"      Медиана: {median_latency:.2f}ms")
        print(f"      Мин: {min_latency:.2f}ms")
        print(f"      Макс: {max_latency:.2f}ms")

    if tx_counts:
        avg_txs = statistics.mean(tx_counts)
        min_txs = min(tx_counts)
        max_txs = max(tx_counts)

        print(f"\n   PENDING ТРАНЗАКЦИИ:")
        print(f"      Среднее: {avg_txs:.1f}")
        print(f"      Мин: {min_txs}")
        print(f"      Макс: {max_txs}")
    else:
        print(f"\n   ⚠️  Pending транзакции НЕ НАЙДЕНЫ")

    print(f"\n   НАДЕЖНОСТЬ:")
    print(f"      Ошибки: {errors}/{iterations} ({errors/iterations*100:.1f}%)")
    print(f"      Нет pending: {no_pending}/{iterations} ({no_pending/iterations*100:.1f}%)")
    print(f"      Успешно: {iterations-errors-no_pending}/{iterations} ({(iterations-errors-no_pending)/iterations*100:.1f}%)")

    success_rate = (iterations - errors - no_pending) / iterations
    has_pending_txs = len(tx_counts) > 0 and statistics.mean(tx_counts) > 0

    return {
        "name": name,
        "url": url,
        "protocol": "WebSocket",
        "avg_latency": statistics.mean(latencies) if latencies else 0,
        "median_latency": statistics.median(latencies) if latencies else 0,
        "min_latency": min(latencies) if latencies else 0,
        "max_latency": max(latencies) if latencies else 0,
        "avg_tx_count": statistics.mean(tx_counts) if tx_counts else 0,
        "max_tx_count": max(tx_counts) if tx_counts else 0,
        "success_rate": success_rate,
        "errors": errors,
        "no_pending": no_pending,
        "has_pending_txs": has_pending_txs
    }

def print_comparison(results: List[Dict]):
    """
    Сравнительная таблица результатов
    """
    print(f"\n\n{'='*80}")
    print(f"🏆 СРАВНЕНИЕ ВСЕХ RPC")
    print(f"{'='*80}\n")

    # Сортируем по latency
    results_sorted = sorted(results, key=lambda x: x['avg_latency'])

    print(f"{'RPC':<25} {'Protocol':<10} {'Latency':<15} {'Pending TXs':<15} {'Success':<10}")
    print(f"{'-'*25} {'-'*10} {'-'*15} {'-'*15} {'-'*10}")

    for r in results_sorted:
        name = r['name'][:24]
        protocol = r['protocol']
        latency = f"{r['avg_latency']:.1f}ms"
        txs = f"{r['avg_tx_count']:.1f}" if r['has_pending_txs'] else "NOT SUPPORTED"
        success = f"{r['success_rate']*100:.0f}%"

        print(f"{name:<25} {protocol:<10} {latency:<15} {txs:<15} {success:<10}")

    # Определяем победителя
    print(f"\n{'='*80}")
    print(f"💡 ВЫВОДЫ")
    print(f"{'='*80}\n")

    # Лучший по latency
    fastest = results_sorted[0]
    print(f"🚀 САМЫЙ БЫСТРЫЙ:")
    print(f"   {fastest['name']} ({fastest['protocol']})")
    print(f"   Latency: {fastest['avg_latency']:.1f}ms (медиана: {fastest['median_latency']:.1f}ms)")

    # У кого больше всего pending транзакций
    most_txs = max(results, key=lambda x: x['avg_tx_count'])
    if most_txs['has_pending_txs']:
        print(f"\n📊 БОЛЬШЕ ВСЕГО PENDING ТРАНЗАКЦИЙ:")
        print(f"   {most_txs['name']} ({most_txs['protocol']})")
        print(f"   Среднее: {most_txs['avg_tx_count']:.1f} txs")
        print(f"   Максимум: {most_txs['max_tx_count']} txs")

    # Самый надежный
    most_reliable = max(results, key=lambda x: x['success_rate'])
    print(f"\n✅ САМЫЙ НАДЕЖНЫЙ:")
    print(f"   {most_reliable['name']} ({most_reliable['protocol']})")
    print(f"   Success rate: {most_reliable['success_rate']*100:.0f}%")

    # Рекомендация
    print(f"\n🎯 РЕКОМЕНДАЦИЯ ДЛЯ MEV:")

    # Находим RPC с pending транзакциями
    with_pending = [r for r in results if r['has_pending_txs']]

    if with_pending:
        best = min(with_pending, key=lambda x: x['avg_latency'])
        print(f"   Используйте: {best['name']} ({best['protocol']})")
        print(f"   ✅ Поддерживает pending блоки")
        print(f"   ✅ Latency: {best['avg_latency']:.1f}ms")
        print(f"   ✅ Среднее {best['avg_tx_count']:.0f} pending транзакций")

        if best['name'] == "Custom reth node":
            print(f"\n   🏆 ВАШ СОБСТВЕННЫЙ RETH NODE - ЛУЧШИЙ ВЫБОР!")
            print(f"   💡 У вас есть преимущество перед другими ботами")
    else:
        print(f"   ⚠️  НИ ОДИН RPC НЕ ПОДДЕРЖИВАЕТ PENDING БЛОКИ")
        print(f"   💡 Нужно использовать другой метод мониторинга mempool")

async def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                                                                      ║
    ║          БЕНЧМАРК FLASHBLOCK / PENDING BLOCK SPEED                  ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)

    print("🎯 Замеряем скорость получения pending блока на разных RPC\n")
    print("📝 Метод: eth_getBlockByNumber('pending', true)")
    print("🔄 Итераций на каждый RPC: 10\n")

    results = []

    # 1. Custom reth node
    print("\n" + "🔵"*40)
    print("ТЕСТ #1: Собственная reth нода с flashblocks")
    print("🔵"*40)
    r1 = test_pending_block_http("Custom reth node", CUSTOM_NODE, iterations=10)
    results.append(r1)

    # 2. Alchemy
    print("\n" + "🟣"*40)
    print("ТЕСТ #2: Alchemy RPC")
    print("🟣"*40)
    r2 = test_pending_block_http("Alchemy", ALCHEMY, iterations=10)
    results.append(r2)

    # 3. Chainstack HTTPS
    print("\n" + "🟢"*40)
    print("ТЕСТ #3: Chainstack HTTPS")
    print("🟢"*40)
    r3 = test_pending_block_http("Chainstack HTTPS", CHAINSTACK_HTTPS, iterations=10)
    results.append(r3)

    # 4. Chainstack WebSocket
    print("\n" + "🟡"*40)
    print("ТЕСТ #4: Chainstack WebSocket")
    print("🟡"*40)
    r4 = await test_pending_block_ws("Chainstack WSS", CHAINSTACK_WSS, iterations=10)
    results.append(r4)

    # Сравнение
    print_comparison(results)

if __name__ == "__main__":
    asyncio.run(main())
