#!/usr/bin/env python3
"""
Детальный анализ топового ликвидатора 0xc88eab547fde493992b2456589f2796960cc4561

Исследуем:
1. Когда был создан контракт
2. ВСЕ его ликвидации (не только за месяц)
3. Общую прибыль за все время
4. Скорость реакции
5. Паттерны работы
6. Кто им управляет
"""

import requests
import json
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict

ALCHEMY_URL = "https://base-mainnet.g.alchemy.com/v2/04r_vJrz9iSljxSQj8UQn"
AAVE_POOL_ADDRESS = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"
LIQUIDATION_EVENT = "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286"

# Топовый ликвидатор
TOP_BOT = "0xc88eab547fde493992b2456589f2796960cc4561"

def rpc_call(method: str, params: List = None) -> Dict:
    """RPC вызов"""
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
    """Получить текущий блок"""
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

def get_contract_creation_block(address: str, current_block: int) -> Optional[int]:
    """
    Найти блок создания контракта методом бинарного поиска
    """
    print(f"🔍 Ищем блок создания контракта {address}...")

    # Бинарный поиск
    # Base запущен с блока ~0, но активность началась позже
    # Начнем с блока 1,000,000 (примерно июнь 2024)
    left = 1000000
    right = current_block

    creation_block = None

    while left <= right:
        mid = (left + right) // 2

        # Проверяем есть ли код в этом блоке
        result = rpc_call("eth_getCode", [address, hex(mid)])

        if "result" in result:
            code = result["result"]
            has_code = len(code) > 2  # "0x" означает нет кода

            if has_code:
                # Контракт существует, ищем раньше
                creation_block = mid
                right = mid - 1
            else:
                # Контракта нет, ищем позже
                left = mid + 1
        else:
            break

    return creation_block

def get_bot_liquidations(bot_address: str, from_block: int, to_block: int) -> List[Dict]:
    """
    Получить все ликвидации конкретного бота
    """
    result = rpc_call("eth_getLogs", [{
        "address": AAVE_POOL_ADDRESS,
        "topics": [
            LIQUIDATION_EVENT,
            None,  # collateralAsset
            None,  # debtAsset
            None   # user
        ],
        "fromBlock": hex(from_block),
        "toBlock": hex(to_block)
    }])

    if "result" not in result:
        return []

    events = result["result"]
    bot_liquidations = []

    for event in events:
        topics = event.get("topics", [])
        data = event.get("data", "0x")

        if len(topics) < 4:
            continue

        # Парсим data чтобы найти liquidator
        data_clean = data[2:]
        if len(data_clean) >= 192:
            liquidator = "0x" + data_clean[128:192][-40:]

            if liquidator.lower() == bot_address.lower():
                # Это наш бот!
                collateral_asset = "0x" + topics[1][-40:]
                debt_asset = "0x" + topics[2][-40:]
                user = "0x" + topics[3][-40:]

                debt_to_cover = int(data_clean[0:64], 16) if data_clean[0:64] else 0
                collateral_amount = int(data_clean[64:128], 16) if data_clean[64:128] else 0

                block_number = int(event.get("blockNumber", "0x0"), 16)
                tx_hash = event.get("transactionHash", "")

                bot_liquidations.append({
                    "collateral_asset": collateral_asset.lower(),
                    "debt_asset": debt_asset.lower(),
                    "user": user.lower(),
                    "debt_to_cover": debt_to_cover,
                    "collateral_amount": collateral_amount,
                    "liquidator": liquidator.lower(),
                    "block_number": block_number,
                    "tx_hash": tx_hash
                })

    return bot_liquidations

def get_transaction_details(tx_hash: str) -> Dict:
    """Получить детали транзакции"""
    tx = rpc_call("eth_getTransactionByHash", [tx_hash])
    receipt = rpc_call("eth_getTransactionReceipt", [tx_hash])

    if "result" not in tx or "result" not in receipt:
        return {}

    tx_data = tx["result"]
    receipt_data = receipt["result"]

    return {
        "from": tx_data.get("from", ""),
        "gas_used": int(receipt_data.get("gasUsed", "0x0"), 16),
        "gas_price": int(tx_data.get("gasPrice", "0x0"), 16),
        "input_length": len(tx_data.get("input", "0x")),
        "status": int(receipt_data.get("status", "0x0"), 16)
    }

def get_token_price_usd(token_address: str) -> float:
    """Получить цену токена в USD"""
    prices = {
        "0xc1cba3fcea344f92d9239c08c0568f6f2f0ee452": 4000,   # wstETH
        "0x4200000000000000000000000000000000000006": 3400,   # WETH
        "0x236aa50979d5f3de3bd1eeb40e81137f22ab794b": 97000,  # tBTC
        "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf": 97000,  # cbBTC
        "0x2ae3f1ec7f1f5012cfeab0185bfc7aa3cf0dec22": 3500,   # cbETH
        "0x04c0599ae5a44757c0af6f9ec3b93da8976c150a": 3800,   # weETH
        "0x6bb7a212910682dcfdbd5bcbb3e28fb4e8da10ee": 1.0,    # GHO
        "0x60a3e35cc302bfa44cb288bc5a4f316fdb1adb42": 1.05,   # EURC
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": 1.0,    # USDC
        "0xd9aaec86b65d86f6a7b5b1b0c42ffa531710b6ca": 1.0,    # USDbC
        "0x63706e401c06ac8513145b7687a14804d17f814b": 200,    # AAVE
    }
    return prices.get(token_address.lower(), 0)

def get_token_decimals(token_address: str) -> int:
    """Получить decimals токена"""
    result = rpc_call("eth_call", [{
        "to": token_address,
        "data": "0x313ce567"  # decimals()
    }, "latest"])

    if "result" in result:
        try:
            return int(result["result"], 16)
        except:
            pass
    return 18

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                                                                      ║
    ║           ДЕТАЛЬНЫЙ АНАЛИЗ ТОПОВОГО ЛИКВИДАТОРА                     ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)

    print(f"🤖 Бот: {TOP_BOT}\n")

    current_block = get_current_block()
    print(f"📊 Текущий блок: {current_block:,}\n")

    # 1. Проверяем что это контракт
    print("="*80)
    print("1️⃣  ИНФОРМАЦИЯ О КОНТРАКТЕ")
    print("="*80 + "\n")

    code_result = rpc_call("eth_getCode", [TOP_BOT, "latest"])
    if "result" in code_result:
        code = code_result["result"]
        code_size = (len(code) - 2) // 2  # Убираем 0x и делим на 2 (hex)

        print(f"📝 Размер кода: {code_size} bytes")

        if code_size > 0:
            print(f"✅ Это смарт-контракт")
        else:
            print(f"❌ Это EOA (обычный адрес)")

    # 2. Находим когда был создан
    creation_block = get_contract_creation_block(TOP_BOT, current_block)

    if creation_block:
        creation_ts = get_block_timestamp(creation_block)
        creation_date = datetime.fromtimestamp(creation_ts)
        days_active = (datetime.now() - creation_date).days

        print(f"\n🎂 Создан в блоке: {creation_block:,}")
        print(f"📅 Дата создания: {creation_date.strftime('%d.%m.%Y %H:%M')}")
        print(f"⏱️  Работает: {days_active} дней")
    else:
        print(f"\n⚠️  Не удалось найти блок создания")
        # Будем сканировать последние 3 месяца
        creation_block = current_block - 3888000  # ~3 месяца

    # 3. Ищем ВСЕ ликвидации этого бота
    print(f"\n{'='*80}")
    print("2️⃣  ВСЕ ЛИКВИДАЦИИ БОТА")
    print("="*80 + "\n")

    print(f"🔍 Сканируем с блока {creation_block:,} до {current_block:,}")
    print(f"   Это {current_block - creation_block:,} блоков...")

    # Разбиваем на чанки по 100k блоков
    all_liquidations = []
    chunk_size = 100000

    from_block = creation_block
    chunk_num = 0

    while from_block < current_block:
        to_block = min(from_block + chunk_size, current_block)
        chunk_num += 1

        print(f"   Чанк {chunk_num}: блоки {from_block:,} - {to_block:,}...", end=" ")

        liquidations = get_bot_liquidations(TOP_BOT, from_block, to_block)
        all_liquidations.extend(liquidations)

        print(f"найдено {len(liquidations)} ликвидаций")

        from_block = to_block + 1

    print(f"\n✅ ВСЕГО найдено: {len(all_liquidations)} ликвидаций\n")

    if not all_liquidations:
        print("❌ Ликвидации не найдены")
        return

    # 4. Анализируем каждую ликвидацию
    print("="*80)
    print("3️⃣  ДЕТАЛЬНЫЙ АНАЛИЗ КАЖДОЙ ЛИКВИДАЦИИ")
    print("="*80 + "\n")

    liquidations_detailed = []

    for i, liq in enumerate(all_liquidations, 1):
        print(f"Анализирую ликвидацию {i}/{len(all_liquidations)}...", end="\r")

        # Получаем детали транзакции
        tx_details = get_transaction_details(liq['tx_hash'])

        # Рассчитываем USD
        debt_decimals = get_token_decimals(liq['debt_asset'])
        collateral_decimals = get_token_decimals(liq['collateral_asset'])

        debt_usd = (liq['debt_to_cover'] / 10**debt_decimals) * get_token_price_usd(liq['debt_asset'])
        collateral_usd = (liq['collateral_amount'] / 10**collateral_decimals) * get_token_price_usd(liq['collateral_asset'])
        profit_usd = collateral_usd - debt_usd

        # Рассчитываем gas cost
        gas_cost_eth = (tx_details.get('gas_used', 0) * tx_details.get('gas_price', 0)) / 10**18
        gas_cost_usd = gas_cost_eth * 3400  # ETH цена

        net_profit = profit_usd - gas_cost_usd

        block_ts = get_block_timestamp(liq['block_number'])

        liquidations_detailed.append({
            **liq,
            'debt_usd': debt_usd,
            'collateral_usd': collateral_usd,
            'profit_usd': profit_usd,
            'gas_cost_usd': gas_cost_usd,
            'net_profit': net_profit,
            'gas_used': tx_details.get('gas_used', 0),
            'gas_price_gwei': tx_details.get('gas_price', 0) / 10**9,
            'caller': tx_details.get('from', ''),
            'timestamp': block_ts
        })

    print("\n")

    # Сортируем по прибыли
    liquidations_detailed.sort(key=lambda x: x['profit_usd'], reverse=True)

    # 5. Показываем все ликвидации
    print("📋 ВСЕ ЛИКВИДАЦИИ:\n")

    for i, liq in enumerate(liquidations_detailed, 1):
        date_str = datetime.fromtimestamp(liq['timestamp']).strftime('%d.%m.%Y %H:%M')

        print(f"{i}. 📅 {date_str} | Блок {liq['block_number']:,}")
        print(f"   TX: {liq['tx_hash']}")
        print(f"   💰 Прибыль: ${liq['profit_usd']:,.2f} (газ: ${liq['gas_cost_usd']:.2f}, чистая: ${liq['net_profit']:,.2f})")
        print(f"   💸 Долг: ${liq['debt_usd']:,.2f}")
        print(f"   ⛽ Gas: {liq['gas_used']:,} ({liq['gas_price_gwei']:.2f} gwei)")
        print(f"   👤 Caller: {liq['caller']}")
        print()

    # 6. Итоговая статистика
    print("="*80)
    print("4️⃣  ИТОГОВАЯ СТАТИСТИКА")
    print("="*80 + "\n")

    total_profit = sum(l['profit_usd'] for l in liquidations_detailed)
    total_gas = sum(l['gas_cost_usd'] for l in liquidations_detailed)
    total_net = sum(l['net_profit'] for l in liquidations_detailed)

    total_debt = sum(l['debt_usd'] for l in liquidations_detailed)

    print(f"📊 ОБЩАЯ СТАТИСТИКА:")
    print(f"   Всего ликвидаций: {len(liquidations_detailed)}")
    print(f"   Общий погашенный долг: ${total_debt:,.2f}")
    print()
    print(f"💰 ПРИБЫЛЬ:")
    print(f"   Валовая прибыль: ${total_profit:,.2f}")
    print(f"   Расходы на газ: ${total_gas:,.2f}")
    print(f"   Чистая прибыль: ${total_net:,.2f}")
    print()
    print(f"📈 СРЕДНИЕ ЗНАЧЕНИЯ:")
    print(f"   Средняя прибыль: ${total_profit/len(liquidations_detailed):,.2f}")
    print(f"   Средний газ: ${total_gas/len(liquidations_detailed):,.2f}")
    print(f"   Средняя чистая: ${total_net/len(liquidations_detailed):,.2f}")
    print(f"   Средний долг: ${total_debt/len(liquidations_detailed):,.2f}")
    print()
    print(f"🏆 ЛУЧШИЕ РЕЗУЛЬТАТЫ:")
    print(f"   Лучшая прибыль: ${max(l['profit_usd'] for l in liquidations_detailed):,.2f}")
    print(f"   Худшая прибыль: ${min(l['profit_usd'] for l in liquidations_detailed):,.2f}")
    print(f"   Максимальный газ: ${max(l['gas_cost_usd'] for l in liquidations_detailed):,.2f}")
    print(f"   Минимальный газ: ${min(l['gas_cost_usd'] for l in liquidations_detailed):,.2f}")

    # 7. Анализируем кто вызывает бота
    print(f"\n{'='*80}")
    print("5️⃣  КТО УПРАВЛЯЕТ БОТОМ?")
    print("="*80 + "\n")

    callers = defaultdict(int)
    for liq in liquidations_detailed:
        callers[liq['caller']] += 1

    print(f"👥 Уникальных caller'ов: {len(callers)}")
    print(f"\n📊 Распределение вызовов:\n")

    sorted_callers = sorted(callers.items(), key=lambda x: x[1], reverse=True)
    for addr, count in sorted_callers:
        pct = count / len(liquidations_detailed) * 100
        print(f"   {addr}: {count} вызовов ({pct:.1f}%)")

    # 8. Временной анализ
    print(f"\n{'='*80}")
    print("6️⃣  ВРЕМЕННОЙ АНАЛИЗ")
    print("="*80 + "\n")

    if creation_block and len(liquidations_detailed) > 1:
        first_liq_ts = min(l['timestamp'] for l in liquidations_detailed)
        last_liq_ts = max(l['timestamp'] for l in liquidations_detailed)

        active_days = (last_liq_ts - first_liq_ts) / 86400

        print(f"📅 Период активности:")
        print(f"   Первая ликвидация: {datetime.fromtimestamp(first_liq_ts).strftime('%d.%m.%Y %H:%M')}")
        print(f"   Последняя ликвидация: {datetime.fromtimestamp(last_liq_ts).strftime('%d.%m.%Y %H:%M')}")
        print(f"   Активных дней: {active_days:.1f}")
        print()
        print(f"📊 Частота:")
        print(f"   Ликвидаций в день: {len(liquidations_detailed)/active_days:.2f}")
        print(f"   Заработок в день: ${total_net/active_days:,.2f}")
        print(f"   Заработок в месяц: ${total_net/active_days*30:,.2f}")

    # 9. Выводы
    print(f"\n{'='*80}")
    print("💡 КЛЮЧЕВЫЕ ВЫВОДЫ О БОТЕ")
    print("="*80 + "\n")

    avg_profit = total_profit / len(liquidations_detailed)

    print(f"1️⃣  СТРАТЕГИЯ:")
    if avg_profit > 5000:
        print(f"   ✅ Фокусируется на КРУПНЫХ позициях (>${avg_profit:,.0f} средняя)")
    else:
        print(f"   📊 Берет средние и крупные позиции")

    print(f"\n2️⃣  ЭФФЕКТИВНОСТЬ:")
    avg_gas = total_gas / len(liquidations_detailed)
    print(f"   💰 ROI: {total_net/total_gas*100:.1f}% (прибыль / расходы на газ)")
    print(f"   ⛽ Средний газ: ${avg_gas:.2f}")

    if len(callers) == 1:
        print(f"\n3️⃣  УПРАВЛЕНИЕ:")
        print(f"   🎯 Один operator - высокая централизация")
    else:
        print(f"\n3️⃣  УПРАВЛЕНИЕ:")
        print(f"   🌐 {len(callers)} operators - распределенная система")

    print(f"\n4️⃣  КОНКУРЕНТОСПОСОБНОСТЬ:")
    if active_days > 0:
        freq = len(liquidations_detailed) / active_days
        if freq > 1:
            print(f"   ⚡ ОЧЕНЬ АКТИВНЫЙ - {freq:.1f} ликвидаций/день")
        else:
            print(f"   📊 Умеренная активность - {freq:.2f} ликвидаций/день")

    print()

if __name__ == "__main__":
    main()
