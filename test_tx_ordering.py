#!/usr/bin/env python3
"""
Анализ корреляции между ordering в flashblocks и canonical blocks

Проверяет насколько порядок транзакций меняется между pending и canonical блоками
"""

import requests
import time
from typing import Dict, List, Optional

ALCHEMY_RPC = "https://base-mainnet.g.alchemy.com/v2/04r_vJrz9iSljxSQj8UQn"
RETH_NODE = "http://80.209.241.37:8545/"

def rpc_call(url: str, method: str, params: List = None) -> Dict:
    """RPC вызов"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params if params else [],
        "id": 1
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def compare_block_ordering():
    """Сравнить ordering между pending и canonical блоками"""

    print("""
    ╔════════════════════════════════════════════════════════════════════════╗
    ║                                                                        ║
    ║     АНАЛИЗ TX ORDERING: Flashblocks vs Canonical Blocks                ║
    ║                                                                        ║
    ║  Проверяем насколько меняется порядок транзакций                       ║
    ║                                                                        ║
    ╚════════════════════════════════════════════════════════════════════════╝
    """)

    print("🔍 Получаем pending блок через flashblocks...\n")

    # Получаем pending блок
    pending = rpc_call(RETH_NODE, "eth_getBlockByNumber", ["pending", True])

    if "result" not in pending or not pending["result"]:
        print("❌ Pending блок недоступен")
        return

    pending_block = pending["result"]
    pending_txs = pending_block.get("transactions", [])

    if not pending_txs or not isinstance(pending_txs[0], dict):
        print("❌ Нет транзакций в pending блоке")
        return

    print(f"✅ Pending блок содержит {len(pending_txs)} транзакций")

    # Собираем первые 20 TX с их gas prices
    pending_tx_data = []
    for i, tx in enumerate(pending_txs[:20]):
        if isinstance(tx, dict):
            gas_price = int(tx.get("gasPrice", "0x0"), 16) / 1e9  # Gwei
            pending_tx_data.append({
                "hash": tx.get("hash"),
                "from": tx.get("from"),
                "gas_price": gas_price,
                "pending_position": i
            })

    print(f"\n📊 Топ-20 транзакций в PENDING блоке:\n")
    print(f"{'Pos':<5} {'Gas Price':>12} {'From Address':<45} {'TX Hash':<70}")
    print("-" * 140)

    for tx in pending_tx_data[:10]:
        print(f"{tx['pending_position']:<5} {tx['gas_price']:>10.2f} Gwei {tx['from']:<45} {tx['hash']:<70}")

    # Ждем несколько секунд чтобы блок финализировался
    print(f"\n⏳ Ждем 5 секунд пока блок финализируется...")
    time.sleep(5)

    # Получаем последний canonical блок
    print(f"\n🔍 Получаем canonical блок...\n")

    latest = rpc_call(RETH_NODE, "eth_getBlockByNumber", ["latest", True])

    if "result" not in latest or not latest["result"]:
        print("❌ Не удалось получить latest блок")
        return

    canonical_block = latest["result"]
    canonical_txs = canonical_block.get("transactions", [])

    print(f"✅ Canonical блок #{int(canonical_block['number'], 16)} содержит {len(canonical_txs)} транзакций")

    # Ищем наши TX в canonical блоке
    canonical_positions = {}
    for i, tx in enumerate(canonical_txs):
        if isinstance(tx, dict):
            tx_hash = tx.get("hash")
            if tx_hash:
                canonical_positions[tx_hash] = {
                    "position": i,
                    "gas_price": int(tx.get("gasPrice", "0x0"), 16) / 1e9
                }

    # Сравниваем
    print(f"\n📊 СРАВНЕНИЕ ORDERING:\n")
    print(f"{'TX Hash':<70} {'Pending Pos':<15} {'Canonical Pos':<15} {'Diff':<10} {'Gas Price':>12}")
    print("-" * 140)

    found_count = 0
    position_changes = []

    for tx in pending_tx_data:
        tx_hash = tx["hash"]
        if tx_hash in canonical_positions:
            found_count += 1
            canon_pos = canonical_positions[tx_hash]["position"]
            diff = canon_pos - tx["pending_position"]
            position_changes.append(abs(diff))

            status = "✅ Same" if diff == 0 else f"⚠️ Moved {diff:+d}"

            print(f"{tx_hash:<70} {tx['pending_position']:<15} {canon_pos:<15} {status:<10} {tx['gas_price']:>10.2f} Gwei")

    # Статистика
    print(f"\n{'='*140}")
    print(f"📊 СТАТИСТИКА ORDERING")
    print(f"{'='*140}\n")

    print(f"Транзакций из pending найдено в canonical: {found_count}/{len(pending_tx_data)}")

    if position_changes:
        avg_change = sum(position_changes) / len(position_changes)
        max_change = max(position_changes)
        unchanged = sum(1 for c in position_changes if c == 0)

        print(f"Позиция не изменилась:                     {unchanged}/{found_count} ({unchanged/found_count*100:.1f}%)")
        print(f"Средное изменение позиции:                 {avg_change:.1f} позиций")
        print(f"Максимальное изменение:                    {max_change} позиций")

        print(f"\n💡 ВЫВОДЫ:")

        if avg_change < 2:
            print(f"   ✅ Ordering относительно стабильный")
            print(f"   ✅ Flashblocks показывают примерный порядок")
        elif avg_change < 5:
            print(f"   ⚠️ Ordering умеренно меняется")
            print(f"   ⚠️ Нельзя полностью доверять порядку в flashblocks")
        else:
            print(f"   ❌ Ordering сильно меняется!")
            print(f"   ❌ Flashblocks НЕ показывают реальный порядок")

        print(f"\n   🎯 Для JIT стратегии:")
        if avg_change < 3:
            print(f"      • Можно пытаться frontrun с умеренным gas")
            print(f"      • Шанс успеха: 50-70%")
        else:
            print(f"      • Frontrun очень рискован")
            print(f"      • Рекомендуется backrun strategy")
            print(f"      • Или ОЧЕНЬ высокий gas price")

    # Анализ газа
    print(f"\n📊 АНАЛИЗ GAS PRICES:")

    # Сортируем pending TX по gas
    sorted_by_gas = sorted(pending_tx_data, key=lambda x: x["gas_price"], reverse=True)

    print(f"\n   Топ-5 по gas в pending:")
    for i, tx in enumerate(sorted_by_gas[:5], 1):
        if tx["hash"] in canonical_positions:
            canon_pos = canonical_positions[tx["hash"]]["position"]
            print(f"   {i}. {tx['gas_price']:>10.2f} Gwei → canonical position: {canon_pos}")
        else:
            print(f"   {i}. {tx['gas_price']:>10.2f} Gwei → NOT in canonical block!")

    print(f"\n{'='*140}\n")

if __name__ == "__main__":
    compare_block_ordering()
