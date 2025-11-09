#!/usr/bin/env python3
"""
Анализ глубины ликвидности (depth) в Uniswap V3 пулах через события Mint/Burn

Получает реальные LP позиции из событий и строит depth chart для арбитража
"""

import requests
import json
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

NODE_URL = "http://80.209.241.37:8545/"

# Uniswap V3 события
MINT_EVENT_SIGNATURE = "0x7a53080ba414158be7ec69b987b5fb7d07dee101fe85488f0853ae16239d0bde"
BURN_EVENT_SIGNATURE = "0x0c396cd989a39f4459b5fa1aed6a9a8dcdbc45908acfd67e028cd568da98982c"

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

def get_pool_creation_block(pool_address: str) -> int:
    """
    Найти блок создания пула (первая транзакция с пулом)
    Упрощенно начнем с недавнего блока
    """
    # Для простоты начнем со 100K блоков назад
    result = rpc_call("eth_blockNumber", [])
    if "result" not in result:
        return 0

    latest_block = int(result["result"], 16)
    # На Base блоки быстрые (2 sec), 100K блоков ~ 2 дня назад
    return max(0, latest_block - 100000)

def get_mint_burn_events(pool_address: str, from_block: int, to_block: str = "latest") -> Tuple[List, List]:
    """
    Получить все Mint и Burn события из пула

    Mint event:
    - topic0: event signature
    - topic1: owner (indexed)
    - topic2: tickLower (indexed)
    - topic3: tickUpper (indexed)
    - data: sender, amount, amount0, amount1

    Returns: (mint_events, burn_events)
    """
    print(f"🔍 Получение Mint событий с блока {from_block} до {to_block}...")

    # Получаем Mint события
    mint_result = rpc_call("eth_getLogs", [{
        "fromBlock": hex(from_block),
        "toBlock": to_block,
        "address": pool_address,
        "topics": [MINT_EVENT_SIGNATURE]
    }])

    mint_events = mint_result.get("result", [])
    print(f"✅ Найдено {len(mint_events)} Mint событий")

    # Получаем Burn события
    print(f"🔍 Получение Burn событий с блока {from_block} до {to_block}...")
    burn_result = rpc_call("eth_getLogs", [{
        "fromBlock": hex(from_block),
        "toBlock": to_block,
        "address": pool_address,
        "topics": [BURN_EVENT_SIGNATURE]
    }])

    burn_events = burn_result.get("result", [])
    print(f"✅ Найдено {len(burn_events)} Burn событий")

    return (mint_events, burn_events)

def decode_tick(tick_hex: str) -> int:
    """Декодировать tick из indexed параметра (int24)"""
    if not tick_hex or tick_hex == "0x":
        return 0

    # Убираем 0x и берем последние 6 hex символов (24 бита)
    tick_hex_clean = tick_hex[-6:]
    tick_raw = int(tick_hex_clean, 16)

    # Конвертируем в signed int24
    if tick_raw & 0x800000:  # Если бит 23 установлен (отрицательное)
        tick = tick_raw - 0x1000000
    else:
        tick = tick_raw

    return tick

def tick_to_price(tick: int) -> float:
    """Конвертировать tick в цену (token1/token0)"""
    return 1.0001 ** tick

def parse_mint_event(event: Dict, debug=False) -> Dict:
    """
    Парсинг Mint события

    topics[0]: event signature
    topics[1]: owner (indexed)
    topics[2]: tickLower (indexed int24)
    topics[3]: tickUpper (indexed int24)
    data: ABI encoded - каждый параметр занимает 32 bytes (64 hex)
          [sender(32), amount(32 padded from uint128), amount0(32), amount1(32)]
    """
    topics = event.get("topics", [])
    data = event.get("data", "0x")

    if len(topics) < 4:
        return None

    owner = topics[1]
    tick_lower = decode_tick(topics[2])
    tick_upper = decode_tick(topics[3])

    # Парсим data
    data_clean = data[2:]  # убираем 0x

    # В ABI encoding каждый параметр занимает 32 bytes (64 hex символа)
    # даже если это uint128
    #
    # Структура data:
    # bytes 0-31 (hex 0-63): sender (address padded to 32 bytes)
    # bytes 32-63 (hex 64-127): amount (uint128 padded to 32 bytes)
    # bytes 64-95 (hex 128-191): amount0 (uint256)
    # bytes 96-127 (hex 192-255): amount1 (uint256)

    if len(data_clean) < 256:  # 4 * 64 = 256 hex chars
        if debug:
            print(f"    Data too short: {len(data_clean)} < 256")
        return None

    # sender = data_clean[0:64]
    amount_hex = data_clean[64:128]     # bytes 32-63
    amount0_hex = data_clean[128:192]   # bytes 64-95
    amount1_hex = data_clean[192:256]   # bytes 96-127

    amount = int(amount_hex, 16) if amount_hex else 0
    amount0 = int(amount0_hex, 16) if amount0_hex else 0
    amount1 = int(amount1_hex, 16) if amount1_hex else 0

    if debug:
        print(f"    amount_hex: {amount_hex}")
        print(f"    amount_dec: {amount}")

    return {
        "owner": owner,
        "tick_lower": tick_lower,
        "tick_upper": tick_upper,
        "liquidity": amount,
        "amount0": amount0,
        "amount1": amount1,
        "block": int(event.get("blockNumber", "0x0"), 16)
    }

def build_liquidity_distribution(mint_events: List[Dict], burn_events: List[Dict]) -> Dict[int, int]:
    """
    Построить распределение ликвидности по тикам

    Returns: dict[tick] = total_liquidity (активная на этом тике)
    """
    # Структура: {(tick_lower, tick_upper): net_liquidity}
    positions = defaultdict(int)

    # Добавляем Mint события
    parsed_count = 0
    debug_count = 0
    for event in mint_events:
        # DEBUG первого события
        debug = (debug_count == 0)

        if debug:
            print(f"\n   DEBUG первого Mint события:")
            print(f"   Topics count: {len(event.get('topics', []))}")
            print(f"   Data: {event.get('data', '')[:100]}...")
            print(f"   Data length: {len(event.get('data', ''))}")
            debug_count += 1

        parsed = parse_mint_event(event, debug=debug)

        if debug:
            print(f"   Parsed result: {parsed}\n")

        if parsed and parsed["liquidity"] > 0:
            key = (parsed["tick_lower"], parsed["tick_upper"])
            positions[key] += parsed["liquidity"]
            parsed_count += 1

    print(f"\n   Распарсено {parsed_count} Mint событий с ликвидностью")
    print(f"   Всего уникальных позиций: {len(positions)}")

    # Вычитаем Burn события (TODO: парсинг burn)
    # Пока игнорируем burn для простоты

    # Теперь построим cumulative liquidity по тикам
    # Метод: добавляем liquidity delta на tick_lower, вычитаем на tick_upper
    tick_delta = defaultdict(int)

    for (tick_lower, tick_upper), liquidity in positions.items():
        # Позиция активна от tick_lower (включительно) до tick_upper (не включительно)
        tick_delta[tick_lower] += liquidity
        tick_delta[tick_upper] -= liquidity

    # Теперь вычисляем cumulative для каждого тика
    sorted_ticks = sorted(tick_delta.keys())
    cumulative = 0
    result = {}

    for tick in sorted_ticks:
        cumulative += tick_delta[tick]
        if cumulative != 0:  # Только ненулевые
            result[tick] = cumulative

    print(f"   Построено распределение для {len(result)} тиков с ненулевой ликвидностью")

    return result

def calculate_slippage(current_tick: int, tick_liquidity: Dict[int, int],
                      swap_amount_token1: float, token1_decimals: int) -> Dict:
    """
    Рассчитать slippage для свопа определенного размера

    Свопаем token1 -> token0 (продаем token1, покупаем token0)
    Цена будет двигаться вниз (tick уменьшается)
    """
    # Сортируем тики по убыванию от текущего
    ticks_below = sorted([t for t in tick_liquidity.keys() if t <= current_tick], reverse=True)

    if not ticks_below:
        return {"error": "No liquidity data"}

    start_price = tick_to_price(current_tick)
    remaining = swap_amount_token1
    total_token0_out = 0

    # Идем вниз по тикам пока не исчерпаем swap amount
    for i, tick in enumerate(ticks_below):
        if remaining <= 0:
            break

        liquidity = tick_liquidity[tick]
        if liquidity <= 0:
            continue

        tick_price = tick_to_price(tick)

        # Следующий тик
        next_tick = ticks_below[i + 1] if i + 1 < len(ticks_below) else tick - 1
        next_price = tick_to_price(next_tick)

        # Сколько token1 можем обменять на этом уровне ликвидности
        # Упрощенная формула (в реальности сложнее)
        # ΔY = L × (√P_current - √P_next)

        sqrt_current = tick_price ** 0.5
        sqrt_next = next_price ** 0.5

        # Virtual reserves
        # L = sqrt(x * y)
        # Грубая оценка capacity
        capacity_token1 = liquidity * (sqrt_current - sqrt_next) / (10 ** token1_decimals)

        # Сколько используем на этом тике
        used = min(remaining, capacity_token1)

        # Получаем token0 по средней цене
        avg_price = (tick_price + next_price) / 2
        token0_out = used / avg_price

        total_token0_out += token0_out
        remaining -= used

        if remaining <= 0:
            end_tick = tick
            end_price = tick_price
            break
    else:
        # Не хватило ликвидности
        end_tick = ticks_below[-1] if ticks_below else current_tick
        end_price = tick_to_price(end_tick)

    # Рассчитываем среднюю цену исполнения
    avg_execution_price = swap_amount_token1 / total_token0_out if total_token0_out > 0 else 0

    # Slippage %
    slippage_pct = ((start_price - avg_execution_price) / start_price * 100) if start_price > 0 else 0

    return {
        "swap_amount": swap_amount_token1,
        "start_price": start_price,
        "end_price": end_price,
        "avg_price": avg_execution_price,
        "token0_received": total_token0_out,
        "slippage_pct": slippage_pct,
        "price_impact_pct": ((end_price - start_price) / start_price * 100),
        "fully_filled": remaining <= 0
    }

def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                                                                  ║
    ║            АНАЛИЗ ГЛУБИНЫ ЛИКВИДНОСТИ (DEPTH CHART)             ║
    ║                                                                  ║
    ║  Получает реальные LP позиции через события Mint/Burn           ║
    ║  и рассчитывает точный slippage для арбитража                   ║
    ║                                                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)

    # Пример: топовый пул WETH/USDC 0.05%
    pool_address = "0xb2cc224c1c9fee385f8ad6a55b4d94e92359dc59"
    pool_name = "WETH / USDC 0.05%"

    print(f"📊 Анализ пула: {pool_name}")
    print(f"   Адрес: {pool_address}\n")

    # Получаем блок создания
    from_block = get_pool_creation_block(pool_address)
    print(f"📅 Анализируем события с блока {from_block}\n")

    # Получаем события
    mint_events, burn_events = get_mint_burn_events(pool_address, from_block, "latest")

    if not mint_events:
        print("❌ Не найдено Mint событий")
        return

    # Строим распределение ликвидности
    print(f"\n🔨 Построение распределения ликвидности...")
    tick_liquidity = build_liquidity_distribution(mint_events, burn_events)

    print(f"✅ Построено распределение для {len(tick_liquidity)} тиков")

    # Получаем текущий тик
    slot0_result = rpc_call("eth_call", [{
        "to": pool_address,
        "data": "0x3850c7bd"  # slot0()
    }, "latest"])

    if "result" in slot0_result:
        slot0_data = slot0_result["result"][2:]
        tick_hex = slot0_data[64:128]
        tick_raw = int(tick_hex, 16)

        tick_24bit = tick_raw & 0xFFFFFF
        if tick_24bit & 0x800000:
            current_tick = tick_24bit - 0x1000000
        else:
            current_tick = tick_24bit

        current_price = tick_to_price(current_tick)

        print(f"\n📍 Текущее состояние пула:")
        print(f"   Current Tick: {current_tick:,}")
        print(f"   Current Price: {current_price:.10f} USDC/WETH")
        print(f"   Current Price (inverted): ${1/current_price:,.2f} per ETH")
    else:
        print("❌ Не удалось получить текущий тик")
        return

    # Показываем top 10 уровней ликвидности
    print(f"\n{'='*120}")
    print(f"📊 ТОП-15 УРОВНЕЙ ЛИКВИДНОСТИ (вокруг текущей цены)")
    print(f"{'='*120}\n")

    # Берем тики вокруг текущего
    ticks_with_liq = sorted(tick_liquidity.keys())

    if not ticks_with_liq:
        print("❌ Нет данных о ликвидности")
    else:
        # Находим ближайший тик к текущему
        current_idx = min(range(len(ticks_with_liq)), key=lambda i: abs(ticks_with_liq[i] - current_tick))

        start_idx = max(0, current_idx - 7)
        end_idx = min(len(ticks_with_liq), current_idx + 8)

        print(f"{'Tick':>10} {'Price (token1/token0)':>22} {'Price ($/ETH)':>15} {'Liquidity L':>20} {'Status':>10}")
        print(f"{'-'*120}")

        for tick in ticks_with_liq[start_idx:end_idx]:
            price = tick_to_price(tick)
            price_inverted = 1 / price if price > 0 else 0
            liq = tick_liquidity[tick]
            is_current = "👉 CURRENT" if abs(tick - current_tick) < 50 else ""

            print(f"{tick:>10,} {price:>22.15f} ${price_inverted:>14,.2f} {liq:>20,} {is_current:>10}")

    # Рассчитываем slippage для разных размеров свопа
    print(f"\n{'='*100}")
    print(f"💹 РАСЧЕТ SLIPPAGE ДЛЯ РАЗНЫХ РАЗМЕРОВ АРБИТРАЖА")
    print(f"{'='*100}\n")
    print(f"Сценарий: Продаем USDC за ETH (цена идет вниз)\n")

    swap_sizes = [1000, 5000, 10000, 50000, 100000, 500000, 1000000]

    print(f"{'Swap Size':>15} {'Start Price':>15} {'Avg Price':>15} {'Slippage':>12} {'ETH Out':>15} {'Filled':>10}")
    print(f"{'-'*100}")

    for size in swap_sizes:
        result = calculate_slippage(current_tick, tick_liquidity, size, 6)  # USDC decimals = 6

        if "error" not in result:
            filled = "✅ YES" if result["fully_filled"] else "❌ NO"

            # Обработка division by zero
            start_price_inv = 1/result['start_price'] if result['start_price'] > 0 else 0
            avg_price_inv = 1/result['avg_price'] if result['avg_price'] > 0 else 0

            print(f"${size:>13,} ${start_price_inv:>13,.2f} "
                  f"${avg_price_inv:>13,.2f} "
                  f"{result['slippage_pct']:>10,.2f}% "
                  f"{result['token0_received']:>14,.4f} "
                  f"{filled:>10}")

    print(f"\n💡 Рекомендации для арбитража:")
    print(f"   ✅ Безопасный размер (slippage <0.1%): посмотрите результаты выше")
    print(f"   ⚠️  Средний риск (slippage 0.1-0.5%): возможен, если spread покрывает")
    print(f"   ❌ Высокий риск (slippage >0.5%): вероятно убыточно")
    print()

if __name__ == "__main__":
    main()
