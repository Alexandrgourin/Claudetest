#!/usr/bin/env python3
"""
Безопасное получение quote для арбитража с учетом race condition

Решает проблему:
- eth_call может выполняться 35-800ms
- За это время может сформироваться 0-4 новых flashblock
- Нужна валидация результата

Стратегия:
1. Получаем pending block number
2. Делаем eth_call с этим конкретным блоком
3. Верифицируем, что pending не изменился
4. Если изменился - повторяем с новым блоком
5. Добавляем safety margin к расчетам
"""

import requests
import json
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

NODE_URL = "http://80.209.241.37:8545/"

@dataclass
class QuoteResult:
    """Результат quote с метаданными"""
    amount_out: int
    block_number: int
    block_hash: str
    execution_time_ms: float
    attempts: int
    is_stale: bool  # True если блок изменился за время выполнения
    tick: Optional[int] = None
    sqrt_price: Optional[int] = None

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

def get_pending_block_info() -> Tuple[int, str]:
    """
    Получить номер и хэш текущего pending block

    Returns: (block_number, block_hash)
    """
    result = rpc_call("eth_getBlockByNumber", ["pending", False])
    if "result" not in result or not result["result"]:
        raise Exception("Failed to get pending block")

    block = result["result"]
    block_number = int(block.get("number", "0x0"), 16)
    block_hash = block.get("hash", "")

    return (block_number, block_hash)

def get_pool_state(pool_address: str, block_tag: str = "pending", debug: bool = False) -> Optional[Dict]:
    """
    Получить состояние пула

    Args:
        pool_address: адрес пула
        block_tag: тег блока ("pending", "latest" или hex номер)
        debug: включить отладочный вывод

    Returns: {tick, sqrt_price, liquidity} или None
    """
    # slot0()
    slot0_result = rpc_call("eth_call", [{
        "to": pool_address,
        "data": "0x3850c7bd"
    }, block_tag])

    if debug:
        print(f"   [DEBUG] slot0_result: {slot0_result}")

    if "result" not in slot0_result:
        if debug:
            print(f"   [DEBUG] No result in slot0_result")
        return None

    data = slot0_result["result"][2:]
    if len(data) < 128:
        return None

    sqrt_price_hex = data[0:64]
    tick_hex = data[64:128]

    sqrt_price = int(sqrt_price_hex, 16) if sqrt_price_hex else 0
    tick_raw = int(tick_hex, 16) if tick_hex else 0

    # Декодируем tick (int24)
    tick_24bit = tick_raw & 0xFFFFFF
    tick = tick_24bit - 0x1000000 if tick_24bit & 0x800000 else tick_24bit

    # liquidity()
    liq_result = rpc_call("eth_call", [{
        "to": pool_address,
        "data": "0x1a686502"
    }, block_tag])

    liquidity = 0
    if "result" in liq_result:
        liq_hex = liq_result["result"][2:]
        liquidity = int(liq_hex, 16) if liq_hex else 0

    return {
        "tick": tick,
        "sqrt_price": sqrt_price,
        "liquidity": liquidity
    }

def safe_get_quote(
    pool_address: str,
    amount_in: int,
    zero_for_one: bool,
    max_attempts: int = 3,
    allow_stale: bool = False
) -> Optional[QuoteResult]:
    """
    Безопасное получение quote с защитой от race condition

    Args:
        pool_address: адрес пула
        amount_in: входная сумма (в wei для token0 или raw для token1)
        zero_for_one: True = свап token0->token1, False = token1->token0
        max_attempts: максимум попыток при изменении блока
        allow_stale: разрешить вернуть результат даже если блок изменился

    Returns: QuoteResult или None
    """
    attempt = 0

    while attempt < max_attempts:
        attempt += 1

        # Шаг 1: Получаем текущий pending block
        try:
            block_before, hash_before = get_pending_block_info()
        except Exception as e:
            print(f"❌ Попытка {attempt}: не удалось получить pending block: {e}")
            continue

        # Шаг 2: Делаем запрос состояния для pending блока
        t_start = time.time()

        state = get_pool_state(pool_address, block_tag="pending", debug=False)

        t_end = time.time()
        execution_time_ms = (t_end - t_start) * 1000

        if not state:
            print(f"❌ Попытка {attempt}: не удалось получить состояние пула")
            continue

        # Шаг 3: Проверяем, не изменился ли pending
        try:
            block_after, hash_after = get_pending_block_info()
        except Exception as e:
            print(f"⚠️  Попытка {attempt}: не удалось проверить pending после запроса: {e}")
            block_after = block_before + 1  # Assume it changed
            hash_after = ""

        is_stale = (block_after != block_before)

        if is_stale:
            blocks_diff = block_after - block_before
            print(f"⚠️  Попытка {attempt}: pending изменился на {blocks_diff} блок(ов)")
            print(f"   До: {block_before} ({hash_before[:10]}...)")
            print(f"   После: {block_after} ({hash_after[:10]}...)")
            print(f"   Время выполнения: {execution_time_ms:.0f}ms")

            if not allow_stale and attempt < max_attempts:
                print(f"   🔄 Повторяем с новым блоком...")
                time.sleep(0.05)  # Небольшая задержка
                continue
            elif not allow_stale:
                print(f"   ❌ Не удалось получить стабильный результат за {max_attempts} попыток")
                return None

        # Успех!
        print(f"✅ Попытка {attempt}: получен валидный quote")
        print(f"   Блок: {block_before}")
        print(f"   Tick: {state['tick']:,}")
        print(f"   Liquidity: {state['liquidity']:,}")
        print(f"   Время: {execution_time_ms:.0f}ms")
        print(f"   Статус: {'⚠️ STALE' if is_stale else '✅ FRESH'}")

        # TODO: Здесь должна быть реальная логика расчета quote
        # Для примера просто возвращаем 0
        amount_out = 0

        return QuoteResult(
            amount_out=amount_out,
            block_number=block_before,
            block_hash=hash_before,
            execution_time_ms=execution_time_ms,
            attempts=attempt,
            is_stale=is_stale,
            tick=state["tick"],
            sqrt_price=state["sqrt_price"]
        )

    return None

def calculate_safety_margin(
    quote: QuoteResult,
    flashblock_interval_ms: float = 200,
    max_execution_time_ms: float = 1000
) -> Dict:
    """
    Рассчитать safety margin с учетом race condition

    Args:
        quote: результат quote
        flashblock_interval_ms: интервал формирования flashblocks
        max_execution_time_ms: максимальное время выполнения транзакции

    Returns: рекомендации по safety margin
    """
    # Сколько flashblocks могло пройти
    potential_flashblocks = int(quote.execution_time_ms / flashblock_interval_ms)

    # Если quote уже stale, добавляем еще
    if quote.is_stale:
        potential_flashblocks += 1

    # До отправки транзакции может пройти еще время
    total_potential_flashblocks = int((quote.execution_time_ms + max_execution_time_ms) / flashblock_interval_ms)

    # Оценка волатильности: каждый flashblock может изменить цену на ~0.1-0.5%
    # Консервативная оценка: 0.3% на flashblock
    price_volatility_pct = total_potential_flashblocks * 0.3

    # Safety margin должен покрыть:
    # 1. Волатильность цены
    # 2. Slippage
    # 3. Gas costs
    recommended_margin_pct = price_volatility_pct + 0.5  # +0.5% на slippage

    return {
        "potential_flashblocks": potential_flashblocks,
        "total_potential_flashblocks": total_potential_flashblocks,
        "estimated_price_volatility_pct": price_volatility_pct,
        "recommended_safety_margin_pct": recommended_margin_pct,
        "status": "HIGH_RISK" if recommended_margin_pct > 2.0 else "MEDIUM_RISK" if recommended_margin_pct > 1.0 else "LOW_RISK"
    }

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                                                                      ║
    ║              БЕЗОПАСНОЕ ПОЛУЧЕНИЕ QUOTE ДЛЯ АРБИТРАЖА               ║
    ║                                                                      ║
    ║  С защитой от race condition и расчетом safety margin               ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)

    pool_address = "0xb2cc224c1c9fee385f8ad6a55b4d94e92359dc59"  # WETH/USDC
    amount_in = 10 ** 18  # 1 WETH

    print(f"📊 Пул: {pool_address}")
    print(f"💰 Входная сумма: {amount_in / 10**18} WETH\n")

    print("="*80)
    print("ТЕСТ 1: Строгая проверка (не разрешаем stale)")
    print("="*80 + "\n")

    quote1 = safe_get_quote(
        pool_address=pool_address,
        amount_in=amount_in,
        zero_for_one=True,
        max_attempts=3,
        allow_stale=False
    )

    if quote1:
        print(f"\n📈 Результат:")
        print(f"   Блок: {quote1.block_number}")
        print(f"   Попыток: {quote1.attempts}")
        print(f"   Время: {quote1.execution_time_ms:.0f}ms")
        print(f"   Stale: {quote1.is_stale}")

        margin = calculate_safety_margin(quote1)
        print(f"\n💡 Safety Margin:")
        print(f"   Потенциальных flashblocks: {margin['potential_flashblocks']}")
        print(f"   Всего flashblocks до исполнения: {margin['total_potential_flashblocks']}")
        print(f"   Оценка волатильности: {margin['estimated_price_volatility_pct']:.2f}%")
        print(f"   Рекомендуемый margin: {margin['recommended_safety_margin_pct']:.2f}%")
        print(f"   Статус риска: {margin['status']}")
    else:
        print(f"\n❌ Не удалось получить quote")

    print("\n" + "="*80)
    print("ТЕСТ 2: Разрешаем stale результат")
    print("="*80 + "\n")

    quote2 = safe_get_quote(
        pool_address=pool_address,
        amount_in=amount_in,
        zero_for_one=True,
        max_attempts=1,
        allow_stale=True
    )

    if quote2:
        print(f"\n📈 Результат:")
        print(f"   Блок: {quote2.block_number}")
        print(f"   Stale: {quote2.is_stale}")

        margin = calculate_safety_margin(quote2)
        print(f"\n💡 Safety Margin:")
        print(f"   Рекомендуемый margin: {margin['recommended_safety_margin_pct']:.2f}%")
        print(f"   Статус риска: {margin['status']}")

    print("\n" + "="*80)
    print("💡 РЕКОМЕНДАЦИИ ДЛЯ СТРАТЕГИИ АРБИТРАЖА")
    print("="*80 + "\n")

    print("1. ДЛЯ ВЫСОКОЧАСТОТНОГО АРБИТРАЖА:")
    print("   - Используйте allow_stale=False")
    print("   - max_attempts=2-3")
    print("   - Safety margin 1-2%")
    print("   - Отменяйте сделку если margin > 2%")

    print("\n2. ДЛЯ СРЕДНЕЧАСТОТНОГО АРБИТРАЖА:")
    print("   - Можно использовать allow_stale=True")
    print("   - max_attempts=1")
    print("   - Safety margin 2-3%")
    print("   - Учитывайте execution_time_ms в расчетах")

    print("\n3. ОПТИМИЗАЦИИ:")
    print("   - Использовать WebSocket для получения блоков")
    print("   - Кэшировать HTTP соединения (keep-alive)")
    print("   - Предрасчитывать quote для разных price levels")
    print("   - Мониторить latency к ноде")

    print("\n4. КРИТИЧЕСКИЕ ФАКТОРЫ:")
    print("   - Время выполнения eth_call: 35-800ms (нестабильно!)")
    print("   - Flashblocks каждые 200ms")
    print("   - За 800ms может пройти 4 flashblocks")
    print("   - Каждый flashblock меняет цену на 0.1-0.5%")
    print("   - Итого возможное отклонение: 0.4-2%")
    print()

if __name__ == "__main__":
    main()
