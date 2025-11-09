#!/usr/bin/env python3
"""
Мониторинг мемпула (пендинг транзакций) на Base через reth ноду
"""

import requests
import json
import time
from datetime import datetime

NODE_URL = "http://80.209.241.37:8545/"

def rpc_call(method, params=None):
    """Выполнить RPC вызов"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params if params else [],
        "id": 1
    }
    try:
        response = requests.post(NODE_URL, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def get_txpool_status():
    """Получить статус мемпула"""
    return rpc_call("txpool_status")

def get_txpool_content():
    """Получить содержимое мемпула"""
    return rpc_call("txpool_content")

def get_pending_block():
    """Попытка получить пендинг блок"""
    return rpc_call("eth_getBlockByNumber", ["pending", True])

def format_tx_short(tx):
    """Форматировать транзакцию для короткого вывода"""
    return {
        "from": tx.get("from", "N/A"),
        "to": tx.get("to", "N/A"),
        "value": int(tx.get("value", "0x0"), 16) / 1e18,
        "gas": int(tx.get("gas", "0x0"), 16),
        "gasPrice": int(tx.get("gasPrice", "0x0"), 16) / 1e9,  # в Gwei
    }

def monitor_mempool(interval=5, max_iterations=10):
    """
    Мониторить мемпул

    Args:
        interval: интервал проверки в секундах
        max_iterations: максимальное количество итераций (0 = бесконечно)
    """
    print("=" * 100)
    print("МОНИТОРИНГ МЕМПУЛА RETH НОДЫ (BASE NETWORK)")
    print("=" * 100)
    print(f"\n🔍 Интервал проверки: {interval} сек")
    print(f"🔍 Нода: {NODE_URL}\n")

    iteration = 0
    try:
        while max_iterations == 0 or iteration < max_iterations:
            iteration += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            print(f"\n[{timestamp}] Проверка #{iteration}")
            print("-" * 100)

            # Проверяем статус мемпула
            status = get_txpool_status()
            if "result" in status:
                pending_count = int(status["result"]["pending"], 16)
                queued_count = int(status["result"]["queued"], 16)

                print(f"📊 Статус мемпула:")
                print(f"   Pending: {pending_count} транзакций")
                print(f"   Queued:  {queued_count} транзакций")

                # Если есть пендинг транзакции, показываем детали
                if pending_count > 0 or queued_count > 0:
                    content = get_txpool_content()
                    if "result" in content:
                        print(f"\n📋 Детали транзакций:")

                        # Pending транзакции
                        if content["result"]["pending"]:
                            print(f"\n   🔥 PENDING ({pending_count}):")
                            for address, txs in content["result"]["pending"].items():
                                print(f"\n   From: {address}")
                                for nonce, tx in txs.items():
                                    tx_short = format_tx_short(tx)
                                    print(f"      Nonce {nonce}:")
                                    print(f"         To:       {tx_short['to'][:20]}...")
                                    print(f"         Value:    {tx_short['value']:.4f} ETH")
                                    print(f"         Gas:      {tx_short['gas']:,}")
                                    print(f"         GasPrice: {tx_short['gasPrice']:.2f} Gwei")

                        # Queued транзакции
                        if content["result"]["queued"]:
                            print(f"\n   ⏳ QUEUED ({queued_count}):")
                            for address, txs in content["result"]["queued"].items():
                                print(f"\n   From: {address}")
                                for nonce, tx in txs.items():
                                    tx_short = format_tx_short(tx)
                                    print(f"      Nonce {nonce}:")
                                    print(f"         To:       {tx_short['to'][:20]}...")
                                    print(f"         Value:    {tx_short['value']:.4f} ETH")
                else:
                    print(f"   ✅ Мемпул пуст")
            else:
                print(f"   ❌ Ошибка: {status.get('error', 'Unknown error')}")

            # Проверяем пендинг блок
            pending_block = get_pending_block()
            if "result" in pending_block and pending_block["result"]:
                print(f"\n📦 Пендинг блок:")
                block = pending_block["result"]
                tx_count = len(block.get("transactions", []))
                print(f"   Транзакций: {tx_count}")
                print(f"   Gas used:   {int(block.get('gasUsed', '0x0'), 16):,}")

            if max_iterations == 0 or iteration < max_iterations:
                time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n\n⏹️  Мониторинг остановлен пользователем")

    print(f"\n{'=' * 100}")
    print(f"✅ Всего выполнено проверок: {iteration}")
    print(f"{'=' * 100}\n")

def test_all_methods():
    """Протестировать все доступные методы для работы с мемпулом"""
    print("=" * 100)
    print("ТЕСТИРОВАНИЕ МЕТОДОВ ДЛЯ РАБОТЫ С МЕМПУЛОМ")
    print("=" * 100)

    methods = [
        ("txpool_status", []),
        ("txpool_content", []),
        ("eth_getBlockByNumber", ["pending", True]),
        ("eth_pendingTransactions", []),
        ("txpool_inspect", []),
    ]

    for method, params in methods:
        print(f"\n{'─' * 100}")
        print(f"🔍 Тестирование: {method}")
        print(f"{'─' * 100}")

        result = rpc_call(method, params)

        if "error" in result:
            print(f"❌ Ошибка: {result['error']}")
        else:
            print(f"✅ Успешно")
            # Красивый вывод результата
            if method == "txpool_status":
                pending = int(result["result"]["pending"], 16)
                queued = int(result["result"]["queued"], 16)
                print(f"   Pending: {pending}")
                print(f"   Queued:  {queued}")
            elif method == "eth_getBlockByNumber":
                if result["result"]:
                    print(f"   Пендинг блок доступен")
                else:
                    print(f"   Пендинг блок недоступен (null)")
            else:
                print(f"   {json.dumps(result['result'], indent=2)[:200]}...")

    print(f"\n{'=' * 100}\n")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Режим тестирования всех методов
        test_all_methods()
    else:
        # Режим мониторинга
        # Можно указать: python3 monitor_mempool.py [interval] [max_iterations]
        interval = int(sys.argv[1]) if len(sys.argv) > 1 else 5
        max_iterations = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        monitor_mempool(interval=interval, max_iterations=max_iterations)
