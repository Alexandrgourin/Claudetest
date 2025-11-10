#!/usr/bin/env python3
"""
Проверка: в каком блоке возникла возможность ликвидации vs когда её выполнили

Это ключевой вопрос для понимания latency ботов:
- Если ликвидация в том же блоке = боты реагируют мгновенно
- Если в следующем блоке (+1) = latency ~2 секунды
- Если позже = медленные боты или ждут лучшей цены
"""

import requests
import json
from typing import Dict, List, Optional

ALCHEMY_URL = "https://base-mainnet.g.alchemy.com/v2/04r_vJrz9iSljxSQj8UQn"
AAVE_POOL_ADDRESS = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"
LIQUIDATION_EVENT = "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286"

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

def get_liquidations(from_block: int, to_block: int, limit: int = 30) -> List[Dict]:
    """Получить последние ликвидации"""
    result = rpc_call("eth_getLogs", [{
        "address": AAVE_POOL_ADDRESS,
        "topics": [LIQUIDATION_EVENT],
        "fromBlock": hex(from_block),
        "toBlock": hex(to_block)
    }])

    if "result" not in result:
        return []

    events = result["result"][:limit]

    liquidations = []
    for event in events:
        topics = event.get("topics", [])
        if len(topics) < 4:
            continue

        # collateralAsset = topics[1]
        # debtAsset = topics[2]
        user = "0x" + topics[3][-40:]

        block_number = int(event.get("blockNumber", "0x0"), 16)
        tx_hash = event.get("transactionHash", "")

        liquidations.append({
            "user": user.lower(),
            "block_number": block_number,
            "tx_hash": tx_hash
        })

    return liquidations

def get_user_health_factor(user_address: str, block_number: int) -> Optional[float]:
    """
    Получить Health Factor пользователя на конкретном блоке

    Вызываем getUserAccountData(address)
    Selector: 0xbf92857c

    Returns:
    - totalCollateralBase (uint256)
    - totalDebtBase (uint256)
    - availableBorrowsBase (uint256)
    - currentLiquidationThreshold (uint256)
    - ltv (uint256)
    - healthFactor (uint256)
    """

    # Формируем calldata
    selector = "0xbf92857c"
    padded_address = user_address[2:].lower().zfill(64)
    data = selector + padded_address

    result = rpc_call("eth_call", [
        {
            "to": AAVE_POOL_ADDRESS,
            "data": data
        },
        hex(block_number)
    ])

    if "result" not in result or result["result"] == "0x":
        return None

    # Парсим результат
    result_hex = result["result"]

    if len(result_hex) < 2 + 64 * 6:  # 0x + 6 uint256
        return None

    # Health Factor - это 6-е значение (индекс 5)
    health_factor_hex = result_hex[2 + 64 * 5 : 2 + 64 * 6]
    health_factor_wei = int(health_factor_hex, 16)

    # Health Factor в AAVE с 18 decimals
    # HF = 1.0 означает 1e18
    # HF < 1.0 (т.е. < 1e18) = можно ликвидировать
    health_factor = health_factor_wei / 1e18

    return health_factor

def find_liquidation_opportunity_block(user: str, liquidation_block: int, max_lookback: int = 50) -> Optional[int]:
    """
    Найти блок где Health Factor впервые упал ниже 1.0

    Ищем в обратном порядке от блока ликвидации
    """
    print(f"   🔍 Проверяем Health Factor в предыдущих {max_lookback} блоках...")

    for offset in range(1, max_lookback + 1):
        check_block = liquidation_block - offset

        hf = get_user_health_factor(user, check_block)

        if hf is None:
            continue

        # Показываем прогресс для первых нескольких блоков
        if offset <= 5:
            print(f"      Блок -{offset}: HF = {hf:.4f}")

        # Если HF >= 1.0, значит в предыдущем блоке он упал
        if hf >= 1.0:
            opportunity_block = check_block + 1
            print(f"   ✅ HF < 1.0 начиная с блока {opportunity_block} (offset -{offset - 1})")
            return opportunity_block

    # Если не нашли блок где HF >= 1.0, значит возможность была давно
    print(f"   ⚠️  HF < 1.0 уже более {max_lookback} блоков назад")
    return liquidation_block - max_lookback

def analyze_liquidation_timing(liquidation: Dict) -> Dict:
    """
    Анализ timing конкретной ликвидации
    """
    user = liquidation["user"]
    liq_block = liquidation["block_number"]
    tx_hash = liquidation["tx_hash"]

    print(f"\n{'='*80}")
    print(f"Ликвидация: {tx_hash}")
    print(f"User: {user}")
    print(f"Блок ликвидации: {liq_block:,}")
    print(f"{'='*80}")

    # Проверяем HF в блоке ликвидации (должен быть < 1.0)
    hf_at_liquidation = get_user_health_factor(user, liq_block - 1)  # Блок ДО ликвидации

    if hf_at_liquidation:
        print(f"\n📊 Health Factor перед ликвидацией (блок {liq_block - 1}): {hf_at_liquidation:.4f}")
        if hf_at_liquidation >= 1.0:
            print(f"   ⚠️  СТРАННО: HF >= 1.0, но ликвидация произошла!")
    else:
        print(f"\n   ⚠️  Не удалось получить HF")

    # Ищем блок где возникла возможность ликвидации
    opportunity_block = find_liquidation_opportunity_block(user, liq_block, max_lookback=50)

    if opportunity_block:
        block_delay = liq_block - opportunity_block
        time_delay = block_delay * 2  # ~2 секунды на блок на Base

        print(f"\n⏱️  TIMING АНАЛИЗ:")
        print(f"   Возможность ликвидации: блок {opportunity_block:,}")
        print(f"   Ликвидация выполнена: блок {liq_block:,}")
        print(f"   📊 Задержка: {block_delay} блоков (~{time_delay} секунд)")

        if block_delay == 0:
            print(f"   🚀 МОМЕНТАЛЬНО - в том же блоке!")
            speed = "INSTANT"
        elif block_delay == 1:
            print(f"   ⚡ ОЧЕНЬ БЫСТРО - следующий блок (~2 сек)")
            speed = "VERY_FAST"
        elif block_delay <= 3:
            print(f"   🏃 БЫСТРО - в течение 3 блоков (~6 сек)")
            speed = "FAST"
        elif block_delay <= 10:
            print(f"   🚶 СРЕДНЕ - в течение 10 блоков (~20 сек)")
            speed = "MEDIUM"
        else:
            print(f"   🐌 МЕДЛЕННО - больше 10 блоков (>{block_delay*2} сек)")
            speed = "SLOW"

        return {
            "user": user,
            "liquidation_block": liq_block,
            "opportunity_block": opportunity_block,
            "block_delay": block_delay,
            "time_delay_sec": time_delay,
            "speed": speed,
            "hf_before": hf_at_liquidation
        }

    return {}

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                                                                      ║
    ║        АНАЛИЗ: В КАКОМ БЛОКЕ ПРОИСХОДИТ ЛИКВИДАЦИЯ?                ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)

    print("🎯 Ключевой вопрос: ликвидация в том же блоке что и возможность?\n")

    current_block = get_current_block()
    print(f"📊 Текущий блок: {current_block:,}\n")

    # Берем последние ликвидации
    print("🔍 Получаем последние 20 ликвидаций...")
    from_block = current_block - 100000  # ~55 часов
    to_block = current_block

    liquidations = get_liquidations(from_block, to_block, limit=20)

    if not liquidations:
        print("❌ Ликвидации не найдены")
        return

    print(f"✅ Найдено: {len(liquidations)} ликвидаций\n")

    # Анализируем первые 10
    results = []

    for i, liq in enumerate(liquidations[:10], 1):
        print(f"\n{'#'*80}")
        print(f"ЛИКВИДАЦИЯ #{i}/10")
        print(f"{'#'*80}")

        result = analyze_liquidation_timing(liq)
        if result:
            results.append(result)

        print(f"\nНажмите Enter для следующей...")
        # input()  # Раскомментировать для пошагового просмотра

    # Итоговая статистика
    if results:
        print("\n" + "="*80)
        print("📊 ИТОГОВАЯ СТАТИСТИКА")
        print("="*80 + "\n")

        # Распределение по скорости
        instant = sum(1 for r in results if r['block_delay'] == 0)
        very_fast = sum(1 for r in results if r['block_delay'] == 1)
        fast = sum(1 for r in results if 2 <= r['block_delay'] <= 3)
        medium = sum(1 for r in results if 4 <= r['block_delay'] <= 10)
        slow = sum(1 for r in results if r['block_delay'] > 10)

        total = len(results)

        print(f"СКОРОСТЬ РЕАКЦИИ:")
        print(f"   🚀 Тот же блок (0): {instant}/{total} ({instant/total*100:.1f}%)")
        print(f"   ⚡ Следующий блок (+1): {very_fast}/{total} ({very_fast/total*100:.1f}%)")
        print(f"   🏃 2-3 блока: {fast}/{total} ({fast/total*100:.1f}%)")
        print(f"   🚶 4-10 блоков: {medium}/{total} ({medium/total*100:.1f}%)")
        print(f"   🐌 >10 блоков: {slow}/{total} ({slow/total*100:.1f}%)")

        avg_delay = sum(r['block_delay'] for r in results) / len(results)
        avg_time = sum(r['time_delay_sec'] for r in results) / len(results)

        print(f"\nСРЕДНЯЯ ЗАДЕРЖКА:")
        print(f"   Блоков: {avg_delay:.1f}")
        print(f"   Времени: {avg_time:.1f} секунд")

        min_delay = min(r['block_delay'] for r in results)
        max_delay = max(r['block_delay'] for r in results)

        print(f"\nДИАПАЗОН:")
        print(f"   Минимум: {min_delay} блоков")
        print(f"   Максимум: {max_delay} блоков (~{max_delay*2} сек)")

    # Выводы
    print("\n" + "="*80)
    print("💡 КРИТИЧЕСКИЕ ВЫВОДЫ")
    print("="*80 + "\n")

    if results:
        same_block_pct = (instant / total * 100) if total > 0 else 0
        next_block_pct = (very_fast / total * 100) if total > 0 else 0

        if same_block_pct > 50:
            print("🚨 КРИТИЧНО: Большинство ликвидаций в ТОМ ЖЕ БЛОКЕ!")
            print("   💡 Боты мониторят каждую транзакцию в реальном времени")
            print("   💡 Используют mempool monitoring или flashblocks")
            print("   💡 Ликвидируют ВНУТРИ блока, не ждут следующего")
            print("   ⚡ Ваш бот должен работать так же быстро!")
        elif same_block_pct + next_block_pct > 70:
            print("⚡ БЫСТРО: Большинство ликвидаций в течение 1 блока")
            print("   💡 Боты реагируют на новый блок за ~2 секунды")
            print("   💡 Нужен мониторинг каждого блока")
            print("   📊 У вас есть ~2 секунды на реакцию")
        else:
            print("📊 УМЕРЕННО: Ликвидации происходят с задержкой")
            print("   💡 Не все боты моментальные")
            print(f"   📊 Средняя задержка: {avg_delay:.1f} блоков (~{avg_time:.1f} сек)")
            print("   ✅ Есть возможность конкурировать")

        print(f"\n🎯 ВАШ ПЛАН ДЕЙСТВИЙ:")
        if same_block_pct > 30:
            print("   1. НУЖЕН mempool monitoring (flashblocks)")
            print("   2. Реагировать на изменение HF ВНУТРИ блока")
            print("   3. Использовать priority gas для быстрого включения")
            print("   4. Возможно bundle transactions (MEV)")
        else:
            print("   1. Мониторинг каждого нового блока")
            print("   2. Проверка HF всех позиций при новом блоке")
            print("   3. Моментальная отправка транзакции при HF < 1.0")
            print("   4. Базовый gas fee + небольшая премия")

    print()

if __name__ == "__main__":
    main()
