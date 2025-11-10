#!/usr/bin/env python3
"""
Анализ ликвидаций в AAVE v3 на Base через Alchemy RPC

Alchemy обычно имеет лучшие лимиты:
- Может запрашивать больший диапазон блоков
- Быстрее обработка
- Надежнее соединение
"""

import requests
import json
from collections import defaultdict
from typing import Dict, List
from datetime import datetime

# Alchemy RPC
ALCHEMY_URL = "https://base-mainnet.g.alchemy.com/v2/04r_vJrz9iSljxSQj8UQn"

# AAVE v3 на Base
AAVE_POOL_ADDRESS = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"

# LiquidationCall event signature
LIQUIDATION_EVENT = "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286"

def rpc_call(method: str, params: List = None) -> Dict:
    """RPC вызов к Alchemy"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params if params else [],
        "id": 1
    }
    try:
        response = requests.post(ALCHEMY_URL, json=payload, timeout=30)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def get_current_block() -> int:
    """Получить номер текущего блока"""
    result = rpc_call("eth_blockNumber")
    if "result" in result:
        return int(result["result"], 16)
    return 0

def get_block_timestamp(block_number: int) -> int:
    """Получить timestamp блока"""
    result = rpc_call("eth_getBlockByNumber", [hex(block_number), False])
    if "result" in result and result["result"]:
        return int(result["result"]["timestamp"], 16)
    return 0

def get_liquidation_events(from_block: int, to_block: int) -> List[Dict]:
    """Получить события LiquidationCall"""
    print(f"🔍 Поиск Liquidation событий в блоках {from_block:,} -> {to_block:,}...")

    result = rpc_call("eth_getLogs", [{
        "address": AAVE_POOL_ADDRESS,
        "topics": [LIQUIDATION_EVENT],
        "fromBlock": hex(from_block),
        "toBlock": hex(to_block)
    }])

    if "result" in result:
        events = result["result"]
        print(f"   ✅ Найдено событий: {len(events)}")
        return events
    elif "error" in result:
        error_msg = result["error"].get("message", str(result["error"]))
        print(f"   ❌ Ошибка: {error_msg}")
        return []
    else:
        print(f"   ❌ Неизвестная ошибка")
        return []

def parse_liquidation_event(event: Dict) -> Dict:
    """Парсить LiquidationCall событие"""
    topics = event.get("topics", [])
    data = event.get("data", "0x")

    if len(topics) < 4:
        return None

    collateral_asset = "0x" + topics[1][-40:]
    debt_asset = "0x" + topics[2][-40:]
    user = "0x" + topics[3][-40:]

    data_clean = data[2:]
    if len(data_clean) >= 256:
        debt_to_cover = int(data_clean[0:64], 16) if data_clean[0:64] else 0
        collateral_amount = int(data_clean[64:128], 16) if data_clean[64:128] else 0
        liquidator = "0x" + data_clean[128:192][-40:]
        receive_atoken = int(data_clean[192:256], 16) == 1 if data_clean[192:256] else False

        block_number = int(event.get("blockNumber", "0x0"), 16)
        tx_hash = event.get("transactionHash", "")

        return {
            "collateral_asset": collateral_asset.lower(),
            "debt_asset": debt_asset.lower(),
            "user": user.lower(),
            "debt_to_cover": debt_to_cover,
            "collateral_amount": collateral_amount,
            "liquidator": liquidator.lower(),
            "receive_atoken": receive_atoken,
            "block_number": block_number,
            "tx_hash": tx_hash
        }

    return None

def get_token_info(token_address: str) -> Dict:
    """Получить информацию о токене"""
    # symbol()
    symbol_result = rpc_call("eth_call", [{
        "to": token_address,
        "data": "0x95d89b41"
    }, "latest"])

    symbol = token_address[:8] + "..."
    if "result" in symbol_result:
        try:
            data = symbol_result["result"][2:]
            if len(data) >= 128:
                offset = int(data[0:64], 16)
                length = int(data[64:128], 16)
                string_data = data[128:128+length*2]
                symbol = bytes.fromhex(string_data).decode('utf-8', errors='ignore')
        except:
            pass

    # decimals()
    decimals_result = rpc_call("eth_call", [{
        "to": token_address,
        "data": "0x313ce567"
    }, "latest"])

    decimals = 18
    if "result" in decimals_result:
        try:
            decimals = int(decimals_result["result"], 16)
        except:
            pass

    return {"symbol": symbol, "decimals": decimals}

def get_token_price_usd(token_address: str) -> float:
    """Получить примерную цену токена в USD"""
    prices = {
        "0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452": 4000,   # wstETH
        "0x4200000000000000000000000000000000000006": 3400,   # WETH
        "0x236aa50979d5f3de3bd1eeb40e81137f22ab794b": 97000,  # tBTC
        "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf": 97000,  # cbBTC
        "0x2ae3f1ec7f1f5012cfeab0185bfc7aa3cf0dec22": 3500,   # cbETH
        "0x6bb7a212910682dcfdbd5bcbb3e28fb4e8da10ee": 1.0,    # GHO
        "0x60a3e35cc302bfa44cb288bc5a4f316fdb1adb42": 1.05,   # EURC
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": 1.0,    # USDC
        "0xd9aaec86b65d86f6a7b5b1b0c42ffa531710b6ca": 1.0,    # USDbC
    }
    return prices.get(token_address.lower(), 0)

def format_token_amount(amount: int, decimals: int, symbol: str) -> str:
    """Форматировать количество токенов"""
    value = amount / (10 ** decimals)
    if value < 0.0001:
        return f"{value:.8f} {symbol}"
    elif value < 1:
        return f"{value:.4f} {symbol}"
    else:
        return f"{value:,.2f} {symbol}"

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                                                                      ║
    ║       АНАЛИЗ ЛИКВИДАЦИЙ В AAVE V3 НА BASE (ЧЕРЕЗ ALCHEMY RPC)      ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)

    print(f"📍 AAVE v3 Pool: {AAVE_POOL_ADDRESS}")
    print(f"🌐 RPC: Alchemy\n")

    # Получаем текущий блок
    current_block = get_current_block()
    print(f"📊 Текущий блок: {current_block:,}\n")

    # Пробуем запросить за разные периоды
    test_ranges = [
        ("7 дней", 302400),      # 7 дней
        ("3 дня", 129600),       # 3 дня
        ("1 день", 43200),       # 1 день
    ]

    liquidations_found = []
    period_used = None

    for period_name, blocks in test_ranges:
        print(f"🔍 Попытка запроса за {period_name} ({blocks:,} блоков)...")

        from_block = current_block - blocks
        to_block = current_block

        events = get_liquidation_events(from_block, to_block)

        if events is not None and len(events) >= 0:  # Успешный запрос
            liquidations_found = events
            period_used = (period_name, from_block, to_block, blocks)
            print(f"   ✅ Успешно! Используем этот период.\n")
            break
        else:
            print(f"   ❌ Не удалось, пробуем меньший период...\n")

    if period_used is None:
        print("❌ Не удалось получить данные ни за один период")
        return

    period_name, from_block, to_block, blocks = period_used

    # Получаем timestamps
    from_timestamp = get_block_timestamp(from_block)
    to_timestamp = get_block_timestamp(to_block)
    from_time = datetime.fromtimestamp(from_timestamp)
    to_time = datetime.fromtimestamp(to_timestamp)
    duration_hours = (to_timestamp - from_timestamp) / 3600

    print("="*80)
    print(f"📅 ПЕРИОД АНАЛИЗА: {period_name}")
    print("="*80)
    print(f"От: {from_time.strftime('%Y-%m-%d %H:%M:%S')} (блок {from_block:,})")
    print(f"До: {to_time.strftime('%Y-%m-%d %H:%M:%S')} (блок {to_block:,})")
    print(f"Длительность: {duration_hours:.1f} часов ({blocks:,} блоков)\n")

    if not liquidations_found:
        print("="*80)
        print("✅ ЛИКВИДАЦИЙ НЕ БЫЛО!")
        print("="*80 + "\n")
        print("💡 Это означает:")
        print("   - Все позиции здоровые (HF > 1.0)")
        print("   - Рынок стабилен без резких движений цен")
        print("   - Заемщики активно управляют позициями")
        return

    # Парсим события
    print(f"📝 Парсинг {len(liquidations_found)} событий...\n")
    liquidations = []
    tokens_seen = set()

    for event in liquidations_found:
        parsed = parse_liquidation_event(event)
        if parsed:
            liquidations.append(parsed)
            tokens_seen.add(parsed["collateral_asset"])
            tokens_seen.add(parsed["debt_asset"])

    # Получаем информацию о токенах
    print(f"🔤 Получаем информацию о {len(tokens_seen)} токенах...")
    token_info = {}
    for token in tokens_seen:
        info = get_token_info(token)
        token_info[token] = info
        print(f"   {token}: {info['symbol']}")

    # Выводим детали
    print("\n" + "="*80)
    print(f"💥 НАЙДЕНО {len(liquidations)} ЛИКВИДАЦИЙ")
    print("="*80 + "\n")

    total_debt_usd = 0
    total_collateral_usd = 0
    total_bonus_usd = 0

    liquidators = defaultdict(lambda: {"count": 0, "profit": 0})
    victims = defaultdict(int)
    collateral_tokens = defaultdict(float)
    debt_tokens = defaultdict(float)

    for i, liq in enumerate(liquidations[:20], 1):  # Показываем первые 20
        debt_token = token_info.get(liq['debt_asset'], {"symbol": "???", "decimals": 18})
        collateral_token = token_info.get(liq['collateral_asset'], {"symbol": "???", "decimals": 18})

        debt_amount = liq['debt_to_cover']
        collateral_amount = liq['collateral_amount']

        debt_formatted = format_token_amount(debt_amount, debt_token['decimals'], debt_token['symbol'])
        collateral_formatted = format_token_amount(collateral_amount, collateral_token['decimals'], collateral_token['symbol'])

        debt_usd = (debt_amount / 10**debt_token['decimals']) * get_token_price_usd(liq['debt_asset'])
        collateral_usd = (collateral_amount / 10**collateral_token['decimals']) * get_token_price_usd(liq['collateral_asset'])
        bonus_usd = collateral_usd - debt_usd
        bonus_pct = (bonus_usd / debt_usd * 100) if debt_usd > 0 else 0

        print(f"{i}. Блок {liq['block_number']:,}")
        print(f"   TX: {liq['tx_hash']}")
        print(f"   💸 Погашено: {debt_formatted} (${debt_usd:,.2f})")
        print(f"   🏦 Конфисковано: {collateral_formatted} (${collateral_usd:,.2f})")
        print(f"   💰 Бонус: ${bonus_usd:,.2f} ({bonus_pct:.1f}%)")
        print(f"   👤 Victim: {liq['user']}")
        print(f"   🤖 Liquidator: {liq['liquidator']}\n")

        # Статистика
        total_debt_usd += debt_usd
        total_collateral_usd += collateral_usd
        total_bonus_usd += bonus_usd

        liquidators[liq['liquidator']]["count"] += 1
        liquidators[liq['liquidator']]["profit"] += bonus_usd
        victims[liq['user']] += 1

        collateral_tokens[collateral_token['symbol']] += collateral_amount / 10**collateral_token['decimals']
        debt_tokens[debt_token['symbol']] += debt_amount / 10**debt_token['decimals']

    if len(liquidations) > 20:
        print(f"... и еще {len(liquidations) - 20} ликвидаций\n")

    # Итоговая статистика
    print("="*80)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("="*80 + "\n")

    print(f"🔢 Всего ликвидаций: {len(liquidations)}")
    print(f"💸 Общий долг: ${total_debt_usd:,.2f}")
    print(f"🏦 Общий collateral: ${total_collateral_usd:,.2f}")
    print(f"💰 Общий бонус: ${total_bonus_usd:,.2f}")

    if total_debt_usd > 0:
        avg_bonus_pct = (total_bonus_usd / total_debt_usd) * 100
        avg_per_liquidation = total_bonus_usd / len(liquidations)
        print(f"📈 Средний бонус: {avg_bonus_pct:.2f}%")
        print(f"💵 Средняя прибыль на ликвидацию: ${avg_per_liquidation:,.2f}")

    # Топ ликвидаторов
    if liquidators:
        print(f"\n🏆 ТОП ЛИКВИДАТОРЫ:")
        sorted_liquidators = sorted(liquidators.items(), key=lambda x: x[1]['profit'], reverse=True)
        for addr, stats in sorted_liquidators[:5]:
            print(f"   {addr}")
            print(f"   Ликвидаций: {stats['count']}, Прибыль: ${stats['profit']:,.2f}\n")

    # Активы
    if collateral_tokens:
        print(f"💎 КОНФИСКОВАННЫЕ АКТИВЫ:")
        for symbol, amount in sorted(collateral_tokens.items(), key=lambda x: x[1], reverse=True):
            print(f"   {symbol}: {amount:,.4f}")

    if debt_tokens:
        print(f"\n💸 ПОГАШЕННЫЕ ДОЛГИ:")
        for symbol, amount in sorted(debt_tokens.items(), key=lambda x: x[1], reverse=True):
            print(f"   {symbol}: {amount:,.4f}")

    # Выводы
    print("\n" + "="*80)
    print("💡 ВЫВОДЫ ДЛЯ MEV")
    print("="*80 + "\n")

    liquidations_per_day = len(liquidations) / (duration_hours / 24)
    profit_per_day = total_bonus_usd / (duration_hours / 24)

    print(f"📊 Активность:")
    print(f"   Ликвидаций в день: {liquidations_per_day:.1f}")
    print(f"   Потенциальная прибыль в день: ${profit_per_day:,.2f}")

    if len(liquidations) == 0:
        print("\n✅ Рынок стабилен")
    elif avg_per_liquidation > 1000:
        print(f"\n🔥 ВЫСОКАЯ ДОХОДНОСТЬ! Средняя прибыль ${avg_per_liquidation:,.0f}")
    elif avg_per_liquidation > 100:
        print(f"\n📈 Хорошая возможность, средняя прибыль ${avg_per_liquidation:,.0f}")
    else:
        print(f"\n📉 Низкая прибыль, высокая конкуренция")

    print(f"\n🎯 РЕКОМЕНДАЦИИ:")
    if len(liquidations) > 0:
        print(f"   - Мониторить адреса с HF < 1.2")
        print(f"   - Средний бонус {avg_bonus_pct:.1f}% - типичная ставка AAVE")
        print(f"   - Конкуренция: {len(liquidators)} уникальных ликвидаторов")
    else:
        print(f"   - Рынок стабилен, но стоит мониторить")
        print(f"   - Проверить адреса из find_aave_borrowers.py")

if __name__ == "__main__":
    main()
