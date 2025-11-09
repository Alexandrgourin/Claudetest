#!/usr/bin/env python3
"""
Тест HTTP фильтров как альтернатива WebSocket

Если WebSocket недоступен, можно использовать:
- eth_newBlockFilter - фильтр для новых блоков
- eth_newPendingTransactionFilter - фильтр для pending транзакций
- eth_getFilterChanges - получить изменения с последнего запроса
"""

import requests
import json
import time

NODE_URL = "http://80.209.241.37:8545/"

def rpc_call(method: str, params=None):
    """RPC вызов"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params if params else [],
        "id": 1
    }
    response = requests.post(NODE_URL, json=payload, timeout=10)
    return response.json()

def test_block_filter():
    """
    Тест eth_newBlockFilter + eth_getFilterChanges

    Аналог WebSocket newHeads подписки
    """
    print("\n" + "="*80)
    print("ТЕСТ 1: HTTP Block Filter (альтернатива WebSocket newHeads)")
    print("="*80 + "\n")

    # Создаем фильтр
    result = rpc_call("eth_newBlockFilter")

    if "result" in result:
        filter_id = result["result"]
        print(f"✅ Создан block filter: {filter_id}\n")
        print(f"⏳ Мониторим новые блоки (30 секунд)...\n")
        print(f"{'Время':<12} {'Блок':<10} {'Hash':<20} {'Interval':>10}")
        print("-"*80)

        last_time = None
        blocks_seen = []
        start_time = time.time()

        while time.time() - start_time < 30:
            # Получаем изменения
            changes = rpc_call("eth_getFilterChanges", [filter_id])

            if "result" in changes and len(changes["result"]) > 0:
                current_time = time.time()

                for block_hash in changes["result"]:
                    # Получаем информацию о блоке
                    block_info = rpc_call("eth_getBlockByHash", [block_hash, False])

                    if "result" in block_info and block_info["result"]:
                        block_num = int(block_info["result"]["number"], 16)
                        interval_ms = (current_time - last_time) * 1000 if last_time else 0
                        last_time = current_time

                        timestamp = time.strftime("%H:%M:%S")
                        print(f"{timestamp:<12} {block_num:<10,} {block_hash[:18]:<20} {interval_ms:>9.0f}ms")

                        blocks_seen.append(block_num)

            time.sleep(0.2)  # Polling каждые 200ms (частота flashblocks)

        print(f"\n📊 Результаты:")
        print(f"   Блоков получено: {len(blocks_seen)}")

        if len(blocks_seen) > 1:
            total_blocks = blocks_seen[-1] - blocks_seen[0]
            print(f"   Диапазон блоков: {blocks_seen[0]:,} -> {blocks_seen[-1]:,} (всего {total_blocks})")
            print(f"   Пропущено блоков: {total_blocks - len(blocks_seen)}")

            avg_interval = 30000 / len(blocks_seen) if len(blocks_seen) > 0 else 0
            print(f"   Средний интервал: {avg_interval:.0f}ms")

            if avg_interval < 500:
                print(f"   ⚠️  ПРОБЛЕМА: Polling с interval 200ms видит только {len(blocks_seen)}/{total_blocks} блоков")
                print(f"   💡 WebSocket был бы лучше, но он недоступен")

        # Удаляем фильтр
        rpc_call("eth_uninstallFilter", [filter_id])
        print(f"\n✅ Фильтр удален")

    elif "error" in result:
        print(f"❌ Ошибка: {result['error']['message']}")
        print(f"   Фильтры не поддерживаются на этой ноде")

def test_pending_tx_filter():
    """
    Тест eth_newPendingTransactionFilter + eth_getFilterChanges

    Аналог WebSocket newPendingTransactions подписки
    """
    print("\n" + "="*80)
    print("ТЕСТ 2: HTTP Pending TX Filter (альтернатива WebSocket)")
    print("="*80 + "\n")

    # Создаем фильтр
    result = rpc_call("eth_newPendingTransactionFilter")

    if "result" in result:
        filter_id = result["result"]
        print(f"✅ Создан pending tx filter: {filter_id}\n")
        print(f"⏳ Мониторим pending транзакции (10 секунд)...\n")

        total_txs = 0
        start_time = time.time()

        while time.time() - start_time < 10:
            # Получаем изменения
            changes = rpc_call("eth_getFilterChanges", [filter_id])

            if "result" in changes and len(changes["result"]) > 0:
                batch_size = len(changes["result"])
                total_txs += batch_size
                timestamp = time.strftime("%H:%M:%S")

                if total_txs <= 20:  # Показываем первые 20
                    for tx_hash in changes["result"][:5]:  # Первые 5 из батча
                        print(f"{timestamp} - {tx_hash}")

            time.sleep(0.2)  # Polling каждые 200ms

        print(f"\n📊 Результаты:")
        print(f"   Pending транзакций получено: {total_txs}")
        print(f"   Скорость: {total_txs / 10:.1f} tx/сек")

        # Удаляем фильтр
        rpc_call("eth_uninstallFilter", [filter_id])
        print(f"\n✅ Фильтр удален")

    elif "error" in result:
        print(f"❌ Ошибка: {result['error']['message']}")
        print(f"   Фильтры не поддерживаются на этой ноде")

def test_log_filter():
    """
    Тест eth_newFilter для логов (события контрактов)
    """
    print("\n" + "="*80)
    print("ТЕСТ 3: HTTP Log Filter (мониторинг Swap событий)")
    print("="*80 + "\n")

    SWAP_EVENT = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
    POOL_ADDRESS = "0xb2cc224c1c9fee385f8ad6a55b4d94e92359dc59"

    # Создаем фильтр для Swap событий
    result = rpc_call("eth_newFilter", [{
        "address": POOL_ADDRESS,
        "topics": [SWAP_EVENT]
    }])

    if "result" in result:
        filter_id = result["result"]
        print(f"✅ Создан log filter: {filter_id}")
        print(f"   Пул: WETH/USDC {POOL_ADDRESS}\n")
        print(f"⏳ Мониторим Swap события (20 секунд)...\n")

        swaps_seen = 0
        start_time = time.time()

        while time.time() - start_time < 20:
            # Получаем изменения
            changes = rpc_call("eth_getFilterChanges", [filter_id])

            if "result" in changes and len(changes["result"]) > 0:
                for log in changes["result"]:
                    block_num = int(log["blockNumber"], 16)
                    tx_hash = log["transactionHash"][:18]
                    timestamp = time.strftime("%H:%M:%S")

                    print(f"{timestamp} - Block {block_num:,} - Tx {tx_hash}...")
                    swaps_seen += 1

            time.sleep(0.5)  # Polling каждые 500ms

        print(f"\n📊 Результаты:")
        print(f"   Swap событий получено: {swaps_seen}")

        # Удаляем фильтр
        rpc_call("eth_uninstallFilter", [filter_id])
        print(f"\n✅ Фильтр удален")

    elif "error" in result:
        print(f"❌ Ошибка: {result['error']['message']}")

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                                                                      ║
    ║         ТЕСТИРОВАНИЕ HTTP ФИЛЬТРОВ (АЛЬТЕРНАТИВА WEBSOCKET)         ║
    ║                                                                      ║
    ║  WebSocket недоступен (403), проверяем HTTP polling с фильтрами     ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)

    # Тест 1: Block filter
    test_block_filter()

    # Тест 2: Pending TX filter
    test_pending_tx_filter()

    # Тест 3: Log filter
    test_log_filter()

    print("\n" + "="*80)
    print("💡 ВЫВОДЫ")
    print("="*80 + "\n")

    print("❌ WebSocket НЕДОСТУПЕН:")
    print("   - Получили HTTP 403 при попытке подключения")
    print("   - Возможно WebSocket отключен в конфигурации reth")
    print("   - Или требуется аутентификация")
    print()

    print("⚠️  HTTP ФИЛЬТРЫ (если поддерживаются):")
    print("   - eth_newBlockFilter - для мониторинга блоков")
    print("   - eth_newPendingTransactionFilter - для pending транзакций")
    print("   - eth_newFilter - для логов (Swap/Mint/Burn события)")
    print("   - Требуют polling (запросы каждые 200ms)")
    print()

    print("📊 СРАВНЕНИЕ:")
    print("   WebSocket (push):    <10ms latency, 0% потерь")
    print("   HTTP filters (pull): ~200ms latency, возможны потери блоков")
    print()

    print("💡 РЕКОМЕНДАЦИИ:")
    print()
    print("1. ЕСЛИ HTTP ФИЛЬТРЫ РАБОТАЮТ:")
    print("   - Использовать их с polling interval 100-200ms")
    print("   - Учитывать дополнительную задержку ~200ms")
    print("   - Добавить к safety margin еще +0.5%")
    print()

    print("2. ЕСЛИ HTTP ФИЛЬТРЫ НЕ РАБОТАЮТ:")
    print("   - Спросить владельца ноды включить WebSocket")
    print("   - Или добавить доступ к WebSocket endpoint")
    print("   - Конфиг reth: --ws --ws-addr 0.0.0.0 --ws-port 8546")
    print()

    print("3. ТЕКУЩАЯ СТРАТЕГИЯ:")
    print("   - Продолжать использовать HTTP с eth_call")
    print("   - Polling pending block каждые 200-300ms")
    print("   - Safety margin 3-5% для покрытия latency")
    print()

if __name__ == "__main__":
    main()
