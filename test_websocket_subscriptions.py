#!/usr/bin/env python3
"""
Тест WebSocket подписок на события для custom reth ноды
Проверяет: newHeads, newPendingTransactions, logs
"""

import asyncio
import json
import time
import websockets
from datetime import datetime
from typing import Dict, List, Optional

# WebSocket endpoints для тестирования
WEBSOCKET_ENDPOINTS = {
    "Custom Reth (8545)": "ws://80.209.241.37:8545",
    "Custom Reth (8546)": "ws://80.209.241.37:8546",
    "Alchemy": "wss://base-mainnet.g.alchemy.com/v2/04r_vJrz9iSljxSQj8UQn"
}

# Тестовый контракт для logs (USDC на Base)
USDC_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

class WebSocketTester:
    def __init__(self, ws_url: str, name: str):
        self.ws_url = ws_url
        self.name = name
        self.results = {
            'connection': {'success': False, 'error': None},
            'newHeads': {'supported': False, 'count': 0, 'errors': []},
            'newPendingTransactions': {'supported': False, 'count': 0, 'errors': []},
            'logs': {'supported': False, 'count': 0, 'errors': []}
        }

    async def test_connection(self) -> bool:
        """Тест базового подключения"""
        print(f"\n{'='*80}")
        print(f"🔌 Проверка подключения: {self.name}")
        print(f"{'='*80}")
        print(f"  URL: {self.ws_url}")

        try:
            async with websockets.connect(self.ws_url, ping_timeout=10, close_timeout=5) as ws:
                # Простой запрос для проверки
                request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_blockNumber",
                    "params": []
                }
                await ws.send(json.dumps(request))
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(response)
                
                if 'result' in data:
                    block_num = int(data['result'], 16)
                    print(f"  ✅ Подключение успешно! Блок: #{block_num}")
                    self.results['connection']['success'] = True
                    return True
                else:
                    print(f"  ❌ Неожиданный ответ: {data}")
                    self.results['connection']['error'] = f"Unexpected response: {data}"
                    return False

        except asyncio.TimeoutError:
            error_msg = "Timeout при подключении"
            print(f"  ❌ {error_msg}")
            self.results['connection']['error'] = error_msg
            return False
        except Exception as e:
            error_msg = str(e)
            print(f"  ❌ ОШИБКА: {error_msg}")
            self.results['connection']['error'] = error_msg
            return False

    async def test_new_heads(self, timeout: int = 25):
        """Тест подписки на новые блоки (newHeads)"""
        print(f"\n{'='*80}")
        print(f"🔍 Тест newHeads для {self.name}")
        print(f"{'='*80}")

        try:
            async with websockets.connect(self.ws_url, ping_timeout=20, close_timeout=5) as ws:
                # Подписка на новые блоки
                subscribe_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_subscribe",
                    "params": ["newHeads"]
                }
                
                await ws.send(json.dumps(subscribe_request))
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(response)
                
                if 'result' in data:
                    subscription_id = data['result']
                    print(f"  ✅ Подписка создана: {subscription_id}")
                    self.results['newHeads']['supported'] = True
                else:
                    raise Exception(f"Не удалось создать подписку: {data}")

                start_time = time.time()
                print(f"  ⏳ Ожидаю события {timeout} секунд...")

                while time.time() - start_time < timeout:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=5)
                        event = json.loads(message)
                        
                        if 'params' in event:
                            self.results['newHeads']['count'] += 1
                            result = event['params']['result']
                            block_num = int(result['number'], 16)
                            timestamp_hex = result['timestamp']
                            timestamp_int = int(timestamp_hex, 16)
                            dt = datetime.fromtimestamp(timestamp_int).strftime('%H:%M:%S')
                            
                            print(f"  📦 Блок #{block_num} | timestamp: {dt}")
                    
                    except asyncio.TimeoutError:
                        continue

                print(f"\n  ✅ Получено событий: {self.results['newHeads']['count']}")

                # Отписка
                unsubscribe_request = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "eth_unsubscribe",
                    "params": [subscription_id]
                }
                await ws.send(json.dumps(unsubscribe_request))

        except Exception as e:
            error_msg = str(e)
            print(f"  ❌ ОШИБКА: {error_msg}")
            self.results['newHeads']['errors'].append(error_msg)
            self.results['newHeads']['supported'] = False

    async def test_pending_transactions(self, timeout: int = 25):
        """Тест подписки на pending транзакции"""
        print(f"\n{'='*80}")
        print(f"🔍 Тест newPendingTransactions для {self.name}")
        print(f"{'='*80}")

        try:
            async with websockets.connect(self.ws_url, ping_timeout=20, close_timeout=5) as ws:
                # Подписка на pending транзакции
                subscribe_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_subscribe",
                    "params": ["newPendingTransactions"]
                }
                
                await ws.send(json.dumps(subscribe_request))
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(response)
                
                if 'result' in data:
                    subscription_id = data['result']
                    print(f"  ✅ Подписка создана: {subscription_id}")
                    self.results['newPendingTransactions']['supported'] = True
                else:
                    raise Exception(f"Не удалось создать подписку: {data}")

                start_time = time.time()
                print(f"  ⏳ Ожидаю события {timeout} секунд...")

                shown_count = 0
                while time.time() - start_time < timeout:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=5)
                        event = json.loads(message)
                        
                        if 'params' in event:
                            self.results['newPendingTransactions']['count'] += 1
                            tx_hash = event['params']['result']
                            
                            if shown_count < 5:
                                print(f"  🔄 Pending TX: {tx_hash}")
                                shown_count += 1
                            elif shown_count == 5:
                                print(f"  ... (показаны первые 5, всего: {self.results['newPendingTransactions']['count']})")
                                shown_count += 1
                    
                    except asyncio.TimeoutError:
                        continue

                print(f"\n  ✅ Получено событий: {self.results['newPendingTransactions']['count']}")

                # Отписка
                unsubscribe_request = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "eth_unsubscribe",
                    "params": [subscription_id]
                }
                await ws.send(json.dumps(unsubscribe_request))

        except Exception as e:
            error_msg = str(e)
            print(f"  ❌ ОШИБКА: {error_msg}")
            self.results['newPendingTransactions']['errors'].append(error_msg)
            self.results['newPendingTransactions']['supported'] = False

    async def test_logs(self, timeout: int = 25):
        """Тест подписки на события контракта (logs)"""
        print(f"\n{'='*80}")
        print(f"🔍 Тест logs (USDC Transfer события) для {self.name}")
        print(f"{'='*80}")

        try:
            async with websockets.connect(self.ws_url, ping_timeout=20, close_timeout=5) as ws:
                # Подписка на Transfer события USDC
                subscribe_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_subscribe",
                    "params": [
                        "logs",
                        {
                            "address": USDC_ADDRESS,
                            "topics": [
                                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
                            ]
                        }
                    ]
                }
                
                await ws.send(json.dumps(subscribe_request))
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(response)
                
                if 'result' in data:
                    subscription_id = data['result']
                    print(f"  ✅ Подписка создана: {subscription_id}")
                    print(f"  📝 Фильтр: USDC Transfer события")
                    self.results['logs']['supported'] = True
                else:
                    raise Exception(f"Не удалось создать подписку: {data}")

                start_time = time.time()
                print(f"  ⏳ Ожидаю события {timeout} секунд...")

                while time.time() - start_time < timeout:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=5)
                        event = json.loads(message)
                        
                        if 'params' in event:
                            self.results['logs']['count'] += 1
                            log_data = event['params']['result']
                            block_num = int(log_data['blockNumber'], 16)
                            tx_hash = log_data['transactionHash']
                            
                            print(f"  📄 Log в блоке #{block_num} | TX: {tx_hash[:10]}...")
                    
                    except asyncio.TimeoutError:
                        continue

                print(f"\n  ✅ Получено событий: {self.results['logs']['count']}")

                # Отписка
                unsubscribe_request = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "eth_unsubscribe",
                    "params": [subscription_id]
                }
                await ws.send(json.dumps(unsubscribe_request))

        except Exception as e:
            error_msg = str(e)
            print(f"  ❌ ОШИБКА: {error_msg}")
            self.results['logs']['errors'].append(error_msg)
            self.results['logs']['supported'] = False

async def main():
    print("🚀 Тест WebSocket подписок на события")
    print("="*80)
    print(f"Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # Сначала проверяем подключение ко всем endpoint'ам
    print("\n" + "="*80)
    print("ШАГ 1: ПРОВЕРКА ПОДКЛЮЧЕНИЯ")
    print("="*80)

    testers = {}
    for name, url in WEBSOCKET_ENDPOINTS.items():
        tester = WebSocketTester(url, name)
        if await tester.test_connection():
            testers[name] = tester
        else:
            print(f"  ⚠️  Пропускаем {name} - не удалось подключиться")

    if not testers:
        print("\n❌ Не удалось подключиться ни к одному endpoint!")
        return

    # Тестируем подписки только для успешно подключенных endpoint'ов
    test_duration = 20

    print("\n" + "="*80)
    print("ШАГ 2: ТЕСТ ПОДПИСОК")
    print("="*80)

    for name, tester in testers.items():
        print(f"\n{'='*80}")
        print(f"Тестируем: {name}")
        print(f"{'='*80}")

        await tester.test_new_heads(test_duration)
        await tester.test_pending_transactions(test_duration)
        await tester.test_logs(test_duration)

    # Итоговая таблица сравнения
    print("\n" + "="*80)
    print("📊 ИТОГОВОЕ СРАВНЕНИЕ")
    print("="*80)

    print(f"\n{'Endpoint':<25} {'newHeads':<20} {'Pending TXs':<20} {'Logs':<20}")
    print("-" * 85)

    for name, tester in testers.items():
        newheads_status = f"✅ ({tester.results['newHeads']['count']})" if tester.results['newHeads']['supported'] else "❌"
        pending_status = f"✅ ({tester.results['newPendingTransactions']['count']})" if tester.results['newPendingTransactions']['supported'] else "❌"
        logs_status = f"✅ ({tester.results['logs']['count']})" if tester.results['logs']['supported'] else "❌"

        print(f"{name:<25} {newheads_status:<20} {pending_status:<20} {logs_status:<20}")

    # Детали ошибок
    print("\n" + "="*80)
    print("🔴 ОШИБКИ И ПРОБЛЕМЫ")
    print("="*80)

    any_errors = False
    for name, tester in testers.items():
        errors_found = False
        
        for sub_type in ['newHeads', 'newPendingTransactions', 'logs']:
            errors = tester.results[sub_type]['errors']
            if errors:
                if not errors_found:
                    print(f"\n{name}:")
                    errors_found = True
                    any_errors = True
                print(f"  {sub_type}:")
                for err in errors:
                    print(f"    ❌ {err}")

    if not any_errors:
        print("\n  ✅ Нет ошибок!")

    # Сохраняем результаты
    results = {
        'timestamp': datetime.now().isoformat(),
        'endpoints': {name: tester.results for name, tester in testers.items()}
    }

    with open('websocket_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print("\n" + "="*80)
    print("✅ Результаты сохранены в websocket_test_results.json")
    print("="*80)

    # Анализ custom reth
    print("\n" + "="*80)
    print("🔍 АНАЛИЗ ВАШЕЙ CUSTOM RETH НОДЫ")
    print("="*80)

    custom_testers = {k: v for k, v in testers.items() if "Custom" in k}
    
    if custom_testers:
        for name, tester in custom_testers.items():
            print(f"\n{name}:")
            
            if tester.results['newHeads']['supported']:
                print(f"  ✅ newHeads: РАБОТАЕТ ({tester.results['newHeads']['count']} событий)")
            else:
                print(f"  ❌ newHeads: НЕ РАБОТАЕТ")
            
            if tester.results['newPendingTransactions']['supported']:
                print(f"  ✅ newPendingTransactions: РАБОТАЕТ ({tester.results['newPendingTransactions']['count']} событий)")
            else:
                print(f"  ❌ newPendingTransactions: НЕ РАБОТАЕТ")
            
            if tester.results['logs']['supported']:
                print(f"  ✅ logs: РАБОТАЕТ ({tester.results['logs']['count']} событий)")
            else:
                print(f"  ❌ logs: НЕ РАБОТАЕТ")
    else:
        print("\n  ❌ Custom reth нода недоступна по WebSocket!")
        print("\n  💡 Рекомендации:")
        print("    1. Проверьте, что WebSocket включен в конфигурации reth")
        print("    2. Проверьте firewall правила для портов 8545/8546")
        print("    3. Попробуйте подключиться локально: ws://localhost:8546")

if __name__ == "__main__":
    asyncio.run(main())
