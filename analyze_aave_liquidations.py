#!/usr/bin/env python3
"""
Анализ ликвидаций в AAVE v3 на Base за последние 24 часа

Событие LiquidationCall:
- collateralAsset (indexed) - какой актив забрали
- debtAsset (indexed) - какой долг погасили
- user (indexed) - адрес ликвидированного
- debtToCover - сумма погашенного долга
- liquidatedCollateralAmount - сумма конфискованного collateral
- liquidator - адрес ликвидатора
- receiveAToken - получил aToken или underlying
"""

import requests
import json
from collections import defaultdict
from typing import Dict, List
from datetime import datetime, timedelta

NODE_URL = "http://80.209.241.37:8545/"

# AAVE v3 на Base
AAVE_POOL_ADDRESS = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"

# LiquidationCall event signature
LIQUIDATION_EVENT = "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286"

def rpc_call(method: str, params: List = None) -> Dict:
    """RPC вызов к ноде"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params if params else [],
        "id": 1
    }
    try:
        response = requests.post(NODE_URL, json=payload, timeout=30)
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
    """
    Получить события LiquidationCall из AAVE Pool

    Args:
        from_block: начальный блок
        to_block: конечный блок

    Returns: список событий
    """
    print(f"🔍 Поиск Liquidation событий в блоках {from_block:,} -> {to_block:,}...")

    result = rpc_call("eth_getLogs", [{
        "address": AAVE_POOL_ADDRESS,
        "topics": [LIQUIDATION_EVENT],
        "fromBlock": hex(from_block),
        "toBlock": hex(to_block)
    }])

    if "result" in result:
        events = result["result"]
        print(f"   Найдено событий: {len(events)}")
        return events
    else:
        print(f"   ❌ Ошибка: {result.get('error', 'Unknown')}")
        return []

def parse_liquidation_event(event: Dict) -> Dict:
    """
    Парсить LiquidationCall событие

    Event LiquidationCall:
    - topics[0]: event signature
    - topics[1]: collateralAsset (indexed)
    - topics[2]: debtAsset (indexed)
    - topics[3]: user (indexed) - ликвидированный
    - data: debtToCover, liquidatedCollateralAmount, liquidator, receiveAToken
    """
    topics = event.get("topics", [])
    data = event.get("data", "0x")

    if len(topics) < 4:
        return None

    # Извлекаем indexed параметры
    collateral_asset = "0x" + topics[1][-40:]
    debt_asset = "0x" + topics[2][-40:]
    user = "0x" + topics[3][-40:]

    # Парсим data
    data_clean = data[2:]
    if len(data_clean) >= 256:
        # debtToCover (uint256, 32 bytes)
        debt_to_cover_hex = data_clean[0:64]
        debt_to_cover = int(debt_to_cover_hex, 16) if debt_to_cover_hex else 0

        # liquidatedCollateralAmount (uint256, 32 bytes)
        collateral_amount_hex = data_clean[64:128]
        collateral_amount = int(collateral_amount_hex, 16) if collateral_amount_hex else 0

        # liquidator (address, 32 bytes padded)
        liquidator_hex = data_clean[128:192]
        liquidator = "0x" + liquidator_hex[-40:]

        # receiveAToken (bool, 32 bytes padded)
        receive_atoken_hex = data_clean[192:256]
        receive_atoken = int(receive_atoken_hex, 16) == 1 if receive_atoken_hex else False

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
    """Получить информацию о токене (symbol, decimals)"""
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

    decimals = 18  # default
    if "result" in decimals_result:
        try:
            decimals = int(decimals_result["result"], 16)
        except:
            pass

    return {"symbol": symbol, "decimals": decimals}

def get_token_price_usd(token_address: str) -> float:
    """
    Получить примерную цену токена в USD
    (упрощенная версия - можно улучшить через oracle)
    """
    # Известные цены (примерные)
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

def calculate_liquidation_bonus(debt_usd: float, collateral_usd: float) -> float:
    """Рассчитать бонус ликвидатора в USD"""
    return collateral_usd - debt_usd

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                                                                      ║
    ║          АНАЛИЗ ЛИКВИДАЦИЙ В AAVE V3 НА BASE (МАКС. ПЕРИОД)        ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)

    print(f"📍 AAVE v3 Pool: {AAVE_POOL_ADDRESS}\n")

    # Получаем текущий блок
    current_block = get_current_block()
    print(f"📊 Текущий блок: {current_block:,}")

    # Рассчитываем блоки за максимальный период (100k блоков ~ 55 часов)
    # Base: ~2 секунды на блок => 43,200 блоков за 24 часа
    # Нода ограничивает max 100,000 блоков
    max_blocks = 100000
    from_block = current_block - max_blocks
    to_block = current_block

    # Проверяем timestamp первого блока
    from_timestamp = get_block_timestamp(from_block)
    to_timestamp = get_block_timestamp(to_block)

    from_time = datetime.fromtimestamp(from_timestamp)
    to_time = datetime.fromtimestamp(to_timestamp)
    duration_hours = (to_timestamp - from_timestamp) / 3600

    print(f"🕐 Период анализа:")
    print(f"   От: {from_time.strftime('%Y-%m-%d %H:%M:%S')} (блок {from_block:,})")
    print(f"   До: {to_time.strftime('%Y-%m-%d %H:%M:%S')} (блок {to_block:,})")
    print(f"   Длительность: {duration_hours:.1f} часов\n")

    print("="*80)

    # Получаем события ликвидации
    liquidation_events = get_liquidation_events(from_block, to_block)

    if not liquidation_events:
        print("\n✅ ЗА ПОСЛЕДНИЕ 24 ЧАСА ЛИКВИДАЦИЙ НЕ БЫЛО!")
        print("\n💡 Это означает:")
        print("   - Все позиции здоровые (HF > 1.0)")
        print("   - Или рынок стабилен без резких движений цен")
        print("   - Или заемщики вовремя добавляют collateral / погашают долги")
        return

    # Парсим события
    print(f"\n📝 Парсинг событий...")
    liquidations = []
    tokens_seen = set()

    for event in liquidation_events:
        parsed = parse_liquidation_event(event)
        if parsed:
            liquidations.append(parsed)
            tokens_seen.add(parsed["collateral_asset"])
            tokens_seen.add(parsed["debt_asset"])

    print(f"   Ликвидаций: {len(liquidations)}")
    print(f"   Уникальных токенов: {len(tokens_seen)}")

    # Получаем информацию о токенах
    print(f"\n🔤 Получаем информацию о токенах...")
    token_info = {}
    for token in tokens_seen:
        info = get_token_info(token)
        token_info[token] = info
        print(f"   {token}: {info['symbol']} (decimals: {info['decimals']})")

    # Выводим детали ликвидаций
    print("\n" + "="*80)
    print("💥 ДЕТАЛИ ЛИКВИДАЦИЙ")
    print("="*80 + "\n")

    total_debt_usd = 0
    total_collateral_usd = 0
    total_bonus_usd = 0

    liquidators = defaultdict(lambda: {"count": 0, "profit": 0})
    victims = defaultdict(int)
    collateral_tokens = defaultdict(float)
    debt_tokens = defaultdict(float)

    for i, liq in enumerate(liquidations, 1):
        print(f"{i}. Блок {liq['block_number']:,}")
        print(f"   Транзакция: {liq['tx_hash']}")

        # Debt (что погасили)
        debt_token = token_info[liq['debt_asset']]
        debt_amount = liq['debt_to_cover']
        debt_formatted = format_token_amount(debt_amount, debt_token['decimals'], debt_token['symbol'])
        debt_usd = (debt_amount / 10**debt_token['decimals']) * get_token_price_usd(liq['debt_asset'])

        print(f"   💸 Погашено долга: {debt_formatted} (≈${debt_usd:,.2f})")

        # Collateral (что забрали)
        collateral_token = token_info[liq['collateral_asset']]
        collateral_amount = liq['collateral_amount']
        collateral_formatted = format_token_amount(collateral_amount, collateral_token['decimals'], collateral_token['symbol'])
        collateral_usd = (collateral_amount / 10**collateral_token['decimals']) * get_token_price_usd(liq['collateral_asset'])

        print(f"   🏦 Конфисковано: {collateral_formatted} (≈${collateral_usd:,.2f})")

        # Бонус ликвидатора
        bonus_usd = calculate_liquidation_bonus(debt_usd, collateral_usd)
        bonus_pct = (bonus_usd / debt_usd * 100) if debt_usd > 0 else 0

        print(f"   💰 Бонус ликвидатора: ${bonus_usd:,.2f} ({bonus_pct:.2f}%)")

        print(f"   👤 Ликвидированный: {liq['user']}")
        print(f"   🤖 Ликвидатор: {liq['liquidator']}\n")

        # Обновляем статистику
        total_debt_usd += debt_usd
        total_collateral_usd += collateral_usd
        total_bonus_usd += bonus_usd

        liquidators[liq['liquidator']]["count"] += 1
        liquidators[liq['liquidator']]["profit"] += bonus_usd

        victims[liq['user']] += 1

        collateral_tokens[collateral_token['symbol']] += collateral_amount / 10**collateral_token['decimals']
        debt_tokens[debt_token['symbol']] += debt_amount / 10**debt_token['decimals']

    # Итоговая статистика
    print("="*80)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("="*80 + "\n")

    print(f"🔢 Всего ликвидаций: {len(liquidations)}")
    print(f"💸 Общая сумма долга: ${total_debt_usd:,.2f}")
    print(f"🏦 Общая сумма collateral: ${total_collateral_usd:,.2f}")
    print(f"💰 Общий бонус ликвидаторов: ${total_bonus_usd:,.2f}")

    if total_debt_usd > 0:
        avg_bonus_pct = (total_bonus_usd / total_debt_usd) * 100
        print(f"📈 Средний бонус: {avg_bonus_pct:.2f}%")

    # Топ ликвидаторов
    if liquidators:
        print(f"\n🏆 ТОП ЛИКВИДАТОРЫ:")
        sorted_liquidators = sorted(liquidators.items(), key=lambda x: x[1]['profit'], reverse=True)
        for addr, stats in sorted_liquidators[:5]:
            print(f"   {addr}")
            print(f"   Ликвидаций: {stats['count']}, Прибыль: ${stats['profit']:,.2f}\n")

    # Ликвидированные активы
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
    print("💡 ВЫВОДЫ")
    print("="*80 + "\n")

    if len(liquidations) == 0:
        print("✅ Рынок стабилен, ликвидаций не было")
    elif len(liquidations) < 5:
        print(f"⚠️  Немного ликвидаций ({len(liquidations)}) - рынок относительно стабилен")
    elif len(liquidations) < 20:
        print(f"⚡ Умеренная активность ({len(liquidations)} ликвидаций)")
    else:
        print(f"🔥 ВЫСОКАЯ АКТИВНОСТЬ! {len(liquidations)} ликвидаций за 24 часа")

    if total_bonus_usd > 0:
        print(f"\n💰 Средняя прибыль на ликвидацию: ${total_bonus_usd / len(liquidations):,.2f}")

        if avg_bonus_pct > 8:
            print(f"   📈 Высокий бонус ({avg_bonus_pct:.1f}%) - выгодная возможность!")
        elif avg_bonus_pct > 5:
            print(f"   📊 Средний бонус ({avg_bonus_pct:.1f}%) - стандартная ставка")
        else:
            print(f"   📉 Низкий бонус ({avg_bonus_pct:.1f}%) - конкуренция высока")

    print("\n🎯 ДЛЯ MEV СТРАТЕГИИ:")
    if len(liquidations) > 0:
        print("   - Есть активность в ликвидациях")
        print("   - Стоит мониторить адреса из find_aave_borrowers.py")
        print("   - Особенно с Health Factor < 1.2")
    else:
        print("   - Рынок стабилен, но могут быть возможности при движении цен")
        print("   - Мониторить адреса с HF < 1.3 из find_aave_borrowers.py")

if __name__ == "__main__":
    main()
