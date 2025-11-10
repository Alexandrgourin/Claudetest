#!/usr/bin/env python3
"""
Поиск адресов с займами в AAVE на Base network

Стратегия:
1. Находим Pool контракт AAVE v3 на Base
2. Используем eth_getLogs для поиска Borrow событий
3. Извлекаем адреса заемщиков
4. Проверяем текущий долг через getUserAccountData()
"""

import requests
import json
from collections import defaultdict
from typing import Dict, List, Set

NODE_URL = "http://80.209.241.37:8545/"

# AAVE v3 на Base
AAVE_POOL_ADDRESS = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"  # AAVE v3 Pool на Base

# Event signatures
# Borrow(address indexed reserve, address user, address indexed onBehalfOf, uint256 amount, uint8 interestRateMode, uint256 borrowRate, uint16 indexed referralCode)
BORROW_EVENT = "0xb3d084820fb1a9decffb176436bd02558d15fac9b0ddfed8c465bc7359d7dce0"

# Repay(address indexed reserve, address indexed user, address indexed repayer, uint256 amount, bool useATokens)
REPAY_EVENT = "0xa534c8dbe71f871f9f3530e97a74601fea17b426cae02e1c5aee42c96c784051"

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

def get_borrow_events(from_block: int, to_block: int) -> List[Dict]:
    """
    Получить Borrow события из AAVE Pool

    Args:
        from_block: начальный блок
        to_block: конечный блок

    Returns: список событий
    """
    print(f"🔍 Поиск Borrow событий в блоках {from_block:,} -> {to_block:,}...")

    result = rpc_call("eth_getLogs", [{
        "address": AAVE_POOL_ADDRESS,
        "topics": [BORROW_EVENT],
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

def parse_borrow_event(event: Dict) -> Dict:
    """
    Парсить Borrow событие

    Event Borrow:
    - topics[0]: event signature
    - topics[1]: reserve (indexed) - адрес актива
    - topics[2]: onBehalfOf (indexed) - адрес заемщика
    - topics[3]: referralCode (indexed)
    - data: user, amount, interestRateMode, borrowRate
    """
    topics = event.get("topics", [])
    data = event.get("data", "0x")

    if len(topics) < 3:
        return None

    # reserve (токен который заняли)
    reserve = "0x" + topics[1][-40:]

    # onBehalfOf (заемщик)
    borrower = "0x" + topics[2][-40:]

    # Парсим data
    data_clean = data[2:]
    if len(data_clean) >= 256:
        # user (address, 32 bytes)
        user_hex = data_clean[0:64]
        user = "0x" + user_hex[-40:]

        # amount (uint256, 32 bytes)
        amount_hex = data_clean[64:128]
        amount = int(amount_hex, 16) if amount_hex else 0

        # interestRateMode (uint8, 32 bytes padded)
        rate_mode_hex = data_clean[128:192]
        rate_mode = int(rate_mode_hex, 16) if rate_mode_hex else 0

        # borrowRate (uint256, 32 bytes)
        borrow_rate_hex = data_clean[192:256]
        borrow_rate = int(borrow_rate_hex, 16) if borrow_rate_hex else 0

        block_number = int(event.get("blockNumber", "0x0"), 16)
        tx_hash = event.get("transactionHash", "")

        return {
            "borrower": borrower.lower(),
            "user": user.lower(),
            "reserve": reserve.lower(),
            "amount": amount,
            "rate_mode": rate_mode,  # 1 = stable, 2 = variable
            "borrow_rate": borrow_rate,
            "block_number": block_number,
            "tx_hash": tx_hash
        }

    return None

def get_user_account_data(user_address: str) -> Dict:
    """
    Получить данные аккаунта пользователя в AAVE

    function getUserAccountData(address user) returns (
        uint256 totalCollateralBase,
        uint256 totalDebtBase,
        uint256 availableBorrowsBase,
        uint256 currentLiquidationThreshold,
        uint256 ltv,
        uint256 healthFactor
    )
    """
    # Selector: getUserAccountData(address) = 0xbf92857c
    data = "0xbf92857c" + user_address[2:].zfill(64)

    result = rpc_call("eth_call", [{
        "to": AAVE_POOL_ADDRESS,
        "data": data
    }, "latest"])

    if "result" in result:
        data_hex = result["result"][2:]
        if len(data_hex) >= 384:  # 6 * 64 hex chars
            total_collateral = int(data_hex[0:64], 16)
            total_debt = int(data_hex[64:128], 16)
            available_borrows = int(data_hex[128:192], 16)
            liquidation_threshold = int(data_hex[192:256], 16)
            ltv = int(data_hex[256:320], 16)
            health_factor = int(data_hex[320:384], 16)

            return {
                "total_collateral": total_collateral,  # В базовой валюте (USD * 10^8)
                "total_debt": total_debt,              # В базовой валюте (USD * 10^8)
                "available_borrows": available_borrows,
                "liquidation_threshold": liquidation_threshold,  # В basis points
                "ltv": ltv,                             # В basis points
                "health_factor": health_factor          # * 10^18
            }

    return None

def format_usd(amount: int) -> str:
    """Форматировать USD amount (base 10^8)"""
    return f"${amount / 10**8:,.2f}"

def format_health_factor(hf: int) -> str:
    """Форматировать health factor"""
    if hf == 0:
        return "∞ (no debt)"
    hf_float = hf / 10**18
    return f"{hf_float:.3f}"

def get_token_symbol(token_address: str) -> str:
    """Получить symbol токена"""
    # symbol() selector = 0x95d89b41
    result = rpc_call("eth_call", [{
        "to": token_address,
        "data": "0x95d89b41"
    }, "latest"])

    if "result" in result:
        data = result["result"]
        try:
            # Декодируем string из ABI
            hex_str = data[2:]
            if len(hex_str) >= 128:
                offset = int(hex_str[0:64], 16)
                length = int(hex_str[64:128], 16)
                string_data = hex_str[128:128+length*2]
                return bytes.fromhex(string_data).decode('utf-8', errors='ignore')
        except:
            pass

    return token_address[:8] + "..."

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                                                                      ║
    ║              ПОИСК АДРЕСОВ С ЗАЙМАМИ В AAVE НА BASE                 ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)

    print(f"📍 AAVE v3 Pool: {AAVE_POOL_ADDRESS}\n")

    # Получаем текущий блок
    current_block = get_current_block()
    print(f"📊 Текущий блок: {current_block:,}\n")

    # Поиск за последние 10,000 блоков (~5 часов на Base при 2 сек/блок)
    from_block = current_block - 10000
    to_block = current_block

    print(f"🔍 Анализируем последние 10,000 блоков...\n")
    print("="*80)

    # Получаем Borrow события
    borrow_events = get_borrow_events(from_block, to_block)

    if not borrow_events:
        print("\n⚠️  Не найдено Borrow событий за указанный период")
        return

    # Парсим события
    print(f"\n📝 Парсинг событий...")
    borrowers = {}  # borrower -> list of borrows
    reserves_seen = set()

    for event in borrow_events:
        parsed = parse_borrow_event(event)
        if parsed:
            borrower = parsed["borrower"]
            reserves_seen.add(parsed["reserve"])

            if borrower not in borrowers:
                borrowers[borrower] = []
            borrowers[borrower].append(parsed)

    print(f"   Уникальных заемщиков: {len(borrowers)}")
    print(f"   Уникальных активов: {len(reserves_seen)}")

    # Получаем символы токенов
    print(f"\n🔤 Получаем символы токенов...")
    token_symbols = {}
    for reserve in reserves_seen:
        symbol = get_token_symbol(reserve)
        token_symbols[reserve] = symbol
        print(f"   {reserve}: {symbol}")

    # Выводим заемщиков
    print("\n" + "="*80)
    print("👥 ЗАЕМЩИКИ С АКТИВНЫМИ ЗАЙМАМИ")
    print("="*80 + "\n")

    borrowers_with_debt = []

    for i, (borrower, borrows) in enumerate(borrowers.items(), 1):
        print(f"\n{i}. Адрес: {borrower}")
        print(f"   Займов за период: {len(borrows)}")

        # Показываем детали займов
        total_borrowed = defaultdict(int)
        for borrow in borrows:
            reserve = borrow["reserve"]
            symbol = token_symbols.get(reserve, reserve[:8])
            amount = borrow["amount"]
            total_borrowed[symbol] += amount

            print(f"   - Блок {borrow['block_number']:,}: {amount / 10**18:,.4f} {symbol} "
                  f"(rate mode: {'stable' if borrow['rate_mode'] == 1 else 'variable'})")

        # Получаем текущие данные аккаунта
        account_data = get_user_account_data(borrower)

        if account_data:
            collateral = account_data["total_collateral"]
            debt = account_data["total_debt"]
            health_factor = account_data["health_factor"]

            print(f"\n   💰 Текущее состояние:")
            print(f"      Collateral: {format_usd(collateral)}")
            print(f"      Debt: {format_usd(debt)}")
            print(f"      Health Factor: {format_health_factor(health_factor)}")

            if debt > 0:
                borrowers_with_debt.append({
                    "address": borrower,
                    "collateral": collateral,
                    "debt": debt,
                    "health_factor": health_factor,
                    "borrows": borrows
                })

                # Предупреждение о риске ликвидации
                hf_float = health_factor / 10**18 if health_factor > 0 else float('inf')
                if hf_float < 1.1 and hf_float > 0:
                    print(f"      ⚠️  РИСК ЛИКВИДАЦИИ! Health factor < 1.1")
                elif hf_float < 1.3 and hf_float > 0:
                    print(f"      ⚡ Health factor < 1.3 - мониторить")
            else:
                print(f"      ✅ Долг погашен")

        if i >= 20:  # Показываем первых 20
            print(f"\n... и еще {len(borrowers) - 20} заемщиков")
            break

    # Итоговая статистика
    print("\n" + "="*80)
    print("📊 СТАТИСТИКА")
    print("="*80 + "\n")

    print(f"Всего Borrow событий: {len(borrow_events)}")
    print(f"Уникальных заемщиков: {len(borrowers)}")
    print(f"С активным долгом: {len(borrowers_with_debt)}")
    print(f"Уникальных активов: {len(reserves_seen)}")

    if borrowers_with_debt:
        total_debt = sum(b["debt"] for b in borrowers_with_debt)
        total_collateral = sum(b["collateral"] for b in borrowers_with_debt)

        print(f"\nОбщий долг: {format_usd(total_debt)}")
        print(f"Общий collateral: {format_usd(total_collateral)}")

        # Сортируем по health factor (от низкого к высокому)
        at_risk = [b for b in borrowers_with_debt
                   if b["health_factor"] > 0 and b["health_factor"] / 10**18 < 1.5]

        if at_risk:
            at_risk.sort(key=lambda x: x["health_factor"])

            print(f"\n⚠️  АДРЕСА В ЗОНЕ РИСКА (Health Factor < 1.5):")
            print("-"*80)
            for b in at_risk[:10]:  # Топ-10 рискованных
                hf = b["health_factor"] / 10**18
                print(f"   {b['address']}")
                print(f"   Debt: {format_usd(b['debt'])}, HF: {hf:.3f}")

    # Рекомендации
    print("\n" + "="*80)
    print("💡 ПРИМЕНЕНИЕ ДЛЯ MEV")
    print("="*80 + "\n")

    print("1. ЛИКВИДАЦИИ:")
    print("   - Мониторить адреса с Health Factor < 1.1")
    print("   - При HF < 1.0 можно ликвидировать и получить бонус")
    print("   - Типичный бонус: 5-10% от суммы ликвидации")
    print()

    print("2. МОНИТОРИНГ:")
    print("   - Подписаться на Borrow события через eth_newFilter")
    print("   - Отслеживать изменения цен активов")
    print("   - Рассчитывать когда HF упадет < 1.0")
    print()

    print("3. РАСШИРЕННЫЙ АНАЛИЗ:")
    print("   - Анализировать за больший период (100k+ блоков)")
    print("   - Находить крупных заемщиков (>$100k debt)")
    print("   - Учитывать волатильность collateral активов")
    print()

if __name__ == "__main__":
    main()
