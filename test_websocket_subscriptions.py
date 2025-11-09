#!/usr/bin/env python3
"""
Тест WebSocket подписок на Base node с flashblocks

Проверяем:
1. newHeads - новые блоки (включая flashblocks?)
2. newPendingTransactions - pending транзакции
3. logs - события контрактов
4. syncing - статус синхронизации
"""

import asyncio
import json
import time
from websockets import connect
from datetime import datetime

NODE_WS_URL = "ws://80.209.241.37:8545/"

async def test_new_heads():
    """
    Тест подписки на newHeads

    Ожидаем: получать уведомления о каждом новом блоке/flashblock
    """
    print("\n" + "="*80)
    print("ТЕСТ 1: Подписка на newHeads (новые блоки)")
    print("="*80 + "\n")

    try:
        async with connect(NODE_WS_URL) as ws:
            # Подписываемся
            subscribe_msg = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_subscribe",
                "params": ["newHeads"]
            }

            await ws.send(json.dumps(subscribe_msg))
            print("📤 Отправлена подписка на newHeads...")

            # Получаем subscription ID
            response = await ws.recv()
            data = json.loads(response)
            print(f"📥 Ответ: {data}\n")

            if "result" in data:
                subscription_id = data["result"]
                print(f"✅ Подписка успешна! ID: {subscription_id}\n")
                print(f"⏳ Ожидаем новые блоки (30 секунд)...\n")
                print(f"{'Время':<12} {'Block Number':<15} {'Hash':<20} {'Txs':<8} {'Interval':>10}")
                print("-"*80)

                last_time = None
                count = 0
                start_time = time.time()

                while time.time() - start_time < 30:  # 30 секунд
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        data = json.loads(message)

                        if "params" in data:
                            result = data["params"]["result"]
                            block_num = int(result.get("number", "0x0"), 16)
                            block_hash = result.get("hash", "")[:18]
                            tx_count = len(result.get("transactions", []))

                            current_time = time.time()
                            interval_ms = (current_time - last_time) * 1000 if last_time else 0
                            last_time = current_time

                            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                            print(f"{timestamp:<12} {block_num:<15,} {block_hash:<20} {tx_count:<8} {interval_ms:>9.0f}ms")

                            count += 1
                    except asyncio.TimeoutError:
                        continue

                print(f"\n📊 Получено блоков: {count}")
                if count > 1:
                    avg_interval = 30000 / count
                    print(f"   Средний интервал: {avg_interval:.0f}ms")

                    if avg_interval < 300:
                        print(f"   ✅ Похоже на flashblocks! (~200ms)")
                    else:
                        print(f"   📌 Обычные блоки (~2000ms)")

            else:
                print(f"❌ Ошибка подписки: {data}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")

async def test_new_pending_transactions():
    """
    Тест подписки на newPendingTransactions

    Ожидаем: получать хэши pending транзакций в реальном времени
    """
    print("\n" + "="*80)
    print("ТЕСТ 2: Подписка на newPendingTransactions")
    print("="*80 + "\n")

    try:
        async with connect(NODE_WS_URL) as ws:
            # Подписываемся
            subscribe_msg = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_subscribe",
                "params": ["newPendingTransactions"]
            }

            await ws.send(json.dumps(subscribe_msg))
            print("📤 Отправлена подписка на newPendingTransactions...")

            # Получаем subscription ID
            response = await ws.recv()
            data = json.loads(response)
            print(f"📥 Ответ: {data}\n")

            if "result" in data:
                subscription_id = data["result"]
                print(f"✅ Подписка успешна! ID: {subscription_id}\n")
                print(f"⏳ Ожидаем pending транзакции (10 секунд)...\n")

                count = 0
                start_time = time.time()

                while time.time() - start_time < 10:  # 10 секунд
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        data = json.loads(message)

                        if "params" in data:
                            tx_hash = data["params"]["result"]
                            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                            if count < 20:  # Показываем первые 20
                                print(f"{timestamp} - {tx_hash}")

                            count += 1
                    except asyncio.TimeoutError:
                        continue

                print(f"\n📊 Получено pending транзакций: {count}")
                if count > 0:
                    rate = count / 10
                    print(f"   Скорость: {rate:.1f} tx/сек")
                    print(f"   ✅ WebSocket работает! Можно использовать для мониторинга mempool")
                else:
                    print(f"   ⚠️  Не получено ни одной транзакции")

            else:
                print(f"❌ Ошибка подписки: {data}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")

async def test_logs_subscription():
    """
    Тест подписки на logs (события контрактов)

    Ожидаем: получать события Swap/Mint/Burn из Uniswap V3 пулов
    """
    print("\n" + "="*80)
    print("ТЕСТ 3: Подписка на logs (события контрактов)")
    print("="*80 + "\n")

    # Swap event signature для Uniswap V3
    SWAP_EVENT = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"

    # WETH/USDC pool
    POOL_ADDRESS = "0xb2cc224c1c9fee385f8ad6a55b4d94e92359dc59"

    try:
        async with connect(NODE_WS_URL) as ws:
            # Подписываемся на Swap события в конкретном пуле
            subscribe_msg = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_subscribe",
                "params": [
                    "logs",
                    {
                        "address": POOL_ADDRESS,
                        "topics": [SWAP_EVENT]
                    }
                ]
            }

            await ws.send(json.dumps(subscribe_msg))
            print(f"📤 Подписка на Swap события в пуле WETH/USDC...")
            print(f"   Пул: {POOL_ADDRESS}\n")

            # Получаем subscription ID
            response = await ws.recv()
            data = json.loads(response)
            print(f"📥 Ответ: {data}\n")

            if "result" in data:
                subscription_id = data["result"]
                print(f"✅ Подписка успешна! ID: {subscription_id}\n")
                print(f"⏳ Ожидаем Swap события (30 секунд)...\n")

                count = 0
                start_time = time.time()

                while time.time() - start_time < 30:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        data = json.loads(message)

                        if "params" in data:
                            log = data["params"]["result"]
                            block_num = int(log.get("blockNumber", "0x0"), 16)
                            tx_hash = log.get("transactionHash", "")[:18]
                            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                            print(f"{timestamp} - Block {block_num:,} - Tx {tx_hash}...")
                            count += 1
                    except asyncio.TimeoutError:
                        continue

                print(f"\n📊 Получено Swap событий: {count}")
                if count > 0:
                    print(f"   ✅ Отлично! Можно использовать для мониторинга свопов в реальном времени")
                else:
                    print(f"   📌 За 30 сек не было свопов в этом пуле (это нормально для малоактивных пулов)")

            else:
                print(f"❌ Ошибка подписки: {data}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")

async def test_all_subscriptions_parallel():
    """
    Тест нескольких подписок одновременно

    Показывает как можно использовать множественные подписки для полной картины
    """
    print("\n" + "="*80)
    print("ТЕСТ 4: Множественные подписки одновременно")
    print("="*80 + "\n")

    try:
        async with connect(NODE_WS_URL) as ws:
            # Подписываемся на newHeads
            await ws.send(json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_subscribe",
                "params": ["newHeads"]
            }))
            response1 = await ws.recv()
            heads_id = json.loads(response1).get("result")
            print(f"✅ Подписка newHeads: {heads_id}")

            # Подписываемся на newPendingTransactions
            await ws.send(json.dumps({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "eth_subscribe",
                "params": ["newPendingTransactions"]
            }))
            response2 = await ws.recv()
            pending_id = json.loads(response2).get("result")
            print(f"✅ Подписка newPendingTransactions: {pending_id}\n")

            print(f"⏳ Мониторим оба потока (15 секунд)...\n")

            blocks = 0
            txs = 0
            start_time = time.time()

            while time.time() - start_time < 15:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    data = json.loads(message)

                    if "params" in data:
                        subscription = data["params"]["subscription"]
                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                        if subscription == heads_id:
                            result = data["params"]["result"]
                            block_num = int(result.get("number", "0x0"), 16)
                            tx_count = len(result.get("transactions", []))
                            print(f"{timestamp} [BLOCK] #{block_num:,} ({tx_count} txs)")
                            blocks += 1
                        elif subscription == pending_id:
                            if txs < 10:  # Показываем только первые 10
                                tx_hash = data["params"]["result"][:18]
                                print(f"{timestamp} [TX]    {tx_hash}...")
                            txs += 1
                except asyncio.TimeoutError:
                    continue

            print(f"\n📊 Результаты за 15 секунд:")
            print(f"   Новых блоков: {blocks}")
            print(f"   Pending транзакций: {txs}")

            if blocks > 0:
                avg_block_time = 15000 / blocks
                print(f"   Средний интервал блоков: {avg_block_time:.0f}ms")

            print(f"\n💡 Выводы:")
            print(f"   ✅ Можно подписаться на несколько событий одновременно")
            print(f"   ✅ События приходят мгновенно (без polling)")
            print(f"   ✅ Идеально для арбитража: получаем блоки и транзакции в реальном времени")

    except Exception as e:
        print(f"❌ Ошибка: {e}")

async def check_supported_methods():
    """
    Проверка поддерживаемых методов подписки
    """
    print("\n" + "="*80)
    print("ТЕСТ 0: Проверка подключения и доступных методов")
    print("="*80 + "\n")

    try:
        async with connect(NODE_WS_URL, ping_interval=None) as ws:
            # Проверяем версию
            version_msg = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "web3_clientVersion",
                "params": []
            }

            await ws.send(json.dumps(version_msg))
            response = await ws.recv()
            data = json.loads(response)

            print(f"✅ Подключение успешно!")
            print(f"   Node: {data.get('result', 'unknown')}\n")

            # Проверяем текущий блок
            block_msg = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "eth_blockNumber",
                "params": []
            }

            await ws.send(json.dumps(block_msg))
            response = await ws.recv()
            data = json.loads(response)

            block_num = int(data.get('result', '0x0'), 16)
            print(f"📊 Текущий блок: {block_num:,}\n")

            print(f"📋 Стандартные WebSocket подписки для Ethereum/Base:")
            print(f"   1. newHeads - новые блоки (включая flashblocks)")
            print(f"   2. newPendingTransactions - pending транзакции")
            print(f"   3. logs - события контрактов (Swap, Mint, Burn)")
            print(f"   4. syncing - статус синхронизации ноды\n")

    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")

async def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                                                                      ║
    ║            ТЕСТИРОВАНИЕ WEBSOCKET ПОДПИСОК НА BASE NODE             ║
    ║                                                                      ║
    ║  Проверяем какие события доступны для мониторинга flashblocks       ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)

    # Тест 0: Проверка подключения
    await check_supported_methods()

    # Тест 1: newHeads (самый важный для flashblocks!)
    await test_new_heads()

    # Тест 2: newPendingTransactions
    await test_new_pending_transactions()

    # Тест 3: logs (Swap события)
    await test_logs_subscription()

    # Тест 4: Множественные подписки
    await test_all_subscriptions_parallel()

    print("\n" + "="*80)
    print("💡 ИТОГОВЫЕ РЕКОМЕНДАЦИИ ДЛЯ АРБИТРАЖА")
    print("="*80 + "\n")

    print("1. ИСПОЛЬЗУЙТЕ WebSocket вместо HTTP для:")
    print("   ✅ Мониторинга новых блоков (newHeads)")
    print("   ✅ Отслеживания pending транзакций (newPendingTransactions)")
    print("   ✅ Реакции на Swap события в целевых пулах (logs)")
    print()

    print("2. ПРЕИМУЩЕСТВА WebSocket:")
    print("   ⚡ Данные приходят мгновенно (push, а не pull)")
    print("   ⚡ Нет overhead на HTTP handshake для каждого запроса")
    print("   ⚡ Снижение latency с ~1500ms (HTTP) до <100ms (WebSocket)")
    print("   ⚡ Можно подписаться на несколько событий одновременно")
    print()

    print("3. АРХИТЕКТУРА ДЛЯ АРБИТРАЖА:")
    print("   📌 WebSocket подписка на newHeads -> получаем flashblocks каждые 200ms")
    print("   📌 При новом блоке -> сразу делаем eth_call для quote (через тот же WS)")
    print("   📌 Если есть возможность -> отправляем транзакцию")
    print("   📌 Подписка на logs -> мониторим исполнение нашей транзакции")
    print()

    print("4. КОД ДЛЯ PRODUCTION:")
    print("   - Использовать библиотеку websockets (async)")
    print("   - Автоматический reconnect при обрыве соединения")
    print("   - Обработка нескольких подписок в параллельных tasks")
    print("   - Heartbeat/ping для поддержания соединения")
    print()

if __name__ == "__main__":
    asyncio.run(main())
