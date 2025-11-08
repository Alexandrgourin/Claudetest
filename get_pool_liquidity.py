#!/usr/bin/env python3
"""
Получение концентрированной ликвидности для топ-10 пулов на Base
Использует GeckoTerminal API для получения пулов и reth ноду для запроса данных
"""

import requests
import json
from typing import Dict, List, Optional

# Конфигурация
GECKOTERMINAL_API = "https://api.geckoterminal.com/api/v2"
RETH_NODE_URL = "http://80.209.241.37:8545/"
NETWORK = "base"

# ABI для основных методов Uniswap V3 / Aerodrome Slipstream пулов
# slot0() -> (sqrtPriceX96, tick, observationIndex, observationCardinality, observationCardinalityNext, feeProtocol, unlocked)
SLOT0_ABI = "0x3850c7bd"  # slot0()
LIQUIDITY_ABI = "0x1a686502"  # liquidity()


def rpc_call(method: str, params: list, request_id: int = 1) -> Optional[Dict]:
    """Выполнить JSON-RPC запрос к reth ноде"""
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": request_id
    }

    try:
        response = requests.post(RETH_NODE_URL, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()

        if "error" in result:
            print(f"  ⚠ RPC Error: {result['error'].get('message', result['error'])}")
            return None

        return result.get("result")
    except Exception as e:
        print(f"  ⚠ Request Error: {e}")
        return None


def get_top_pools_by_volume(limit: int = 10) -> Optional[List[Dict]]:
    """Получить топ пулы по объему торгов за 24 часа"""
    try:
        # Пробуем с сортировкой
        url = f"{GECKOTERMINAL_API}/networks/{NETWORK}/pools?sort=h24_tx_count_desc&page=1"
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            # Если не работает, пробуем без сортировки
            url = f"{GECKOTERMINAL_API}/networks/{NETWORK}/pools?page=1"
            response = requests.get(url, timeout=10)

        response.raise_for_status()
        data = response.json()

        if 'data' not in data:
            return None

        # Сортируем по объему торгов за 24 часа
        pools = data['data']
        pools_sorted = sorted(
            pools,
            key=lambda x: float(x['attributes'].get('volume_usd', {}).get('h24', 0)),
            reverse=True
        )

        return pools_sorted[:limit]

    except Exception as e:
        print(f"Error fetching pools: {e}")
        return None


def get_pool_slot0(pool_address: str) -> Optional[Dict]:
    """Получить slot0 пула (текущий тик, цена, и т.д.)"""
    # eth_call для вызова slot0()
    call_data = {
        "to": pool_address,
        "data": SLOT0_ABI
    }

    result = rpc_call("eth_call", [call_data, "latest"])

    if not result or result == "0x":
        return None

    try:
        # Декодируем результат
        # slot0 возвращает: (uint160 sqrtPriceX96, int24 tick, uint16 observationIndex, ...)
        # Каждое значение кодируется как 32 байта (64 hex символа)
        data = result[2:]  # Убираем '0x'

        if len(data) < 128:
            return None

        # sqrtPriceX96 - uint160, но закодирован в 32 байтах (первые 32 байта)
        sqrt_price_hex = data[0:64]
        sqrt_price_x96 = int(sqrt_price_hex, 16)

        # tick - int24, закодирован в следующих 32 байтах
        tick_hex = data[64:128]
        tick_raw = int(tick_hex, 16)

        # Конвертируем в signed int24 (диапазон: -8388608 до 8388607)
        # int24 max = 2^23 - 1 = 8388607
        # Если значение > max, то это отрицательное число в two's complement
        MAX_INT24 = 8388607
        MIN_INT24 = -8388608

        if tick_raw > MAX_INT24:
            # Это отрицательное число в two's complement
            # Для 32-байтового представления с sign extension
            if tick_raw > 2**255:  # Старший бит установлен
                tick = tick_raw - 2**256
            else:
                tick = tick_raw
        else:
            tick = tick_raw

        # Дополнительная проверка диапазона
        if tick < -887272 or tick > 887272:  # Максимальный диапазон тиков в Uniswap V3
            # Попробуем альтернативный способ декодирования
            # Берем только младшие 3 байта (24 бита)
            tick_24bit = tick_raw & 0xFFFFFF
            if tick_24bit > MAX_INT24:
                tick = tick_24bit - 2**24
            else:
                tick = tick_24bit

        return {
            "sqrtPriceX96": sqrt_price_x96,
            "tick": tick,
            "tick_raw": tick_raw
        }

    except Exception as e:
        print(f"  ⚠ Error decoding slot0: {e}")
        return None


def get_pool_liquidity(pool_address: str) -> Optional[int]:
    """Получить текущую активную ликвидность пула"""
    call_data = {
        "to": pool_address,
        "data": LIQUIDITY_ABI
    }

    result = rpc_call("eth_call", [call_data, "latest"])

    if not result or result == "0x":
        return None

    try:
        # liquidity() возвращает uint128
        liquidity = int(result, 16)
        return liquidity

    except Exception as e:
        print(f"  ⚠ Error decoding liquidity: {e}")
        return None


def format_number(num: float) -> str:
    """Форматировать число с разделителями"""
    if num >= 1_000_000_000:
        return f"${num/1_000_000_000:.2f}B"
    elif num >= 1_000_000:
        return f"${num/1_000_000:.2f}M"
    elif num >= 1_000:
        return f"${num/1_000:.2f}K"
    else:
        return f"${num:.2f}"


def calculate_price_from_tick(tick: int, decimals0: int = 18, decimals1: int = 6) -> float:
    """Вычислить цену из тика (упрощенная формула)"""
    # price = 1.0001^tick * (10^decimals1 / 10^decimals0)
    price = (1.0001 ** tick) * (10 ** (decimals1 - decimals0))
    return price


def main():
    print("=" * 80)
    print("АНАЛИЗ КОНЦЕНТРИРОВАННОЙ ЛИКВИДНОСТИ В ТОП-10 ПУЛАХ BASE")
    print("=" * 80)
    print()

    # 1. Получаем топ-10 пулов
    print("📊 Получение топ-10 пулов по объему торгов за 24 часа...")
    pools = get_top_pools_by_volume(10)

    if not pools:
        print("❌ Не удалось получить данные о пулах")
        return

    print(f"✅ Получено {len(pools)} пулов")
    print()

    # 2. Для каждого пула получаем данные из ноды
    print("🔍 Запрос данных о ликвидности через reth ноду...")
    print("=" * 80)
    print()

    successful_queries = 0
    failed_queries = 0

    for i, pool in enumerate(pools, 1):
        attrs = pool['attributes']
        pool_address = attrs['address']
        pool_name = attrs['name']
        dex = pool['relationships']['dex']['data']['id']

        volume_24h = float(attrs.get('volume_usd', {}).get('h24', 0))
        reserve = float(attrs.get('reserve_in_usd', 0))

        print(f"{i}. {pool_name}")
        print(f"   DEX: {dex}")
        print(f"   Address: {pool_address}")
        print(f"   Reserve: {format_number(reserve)}")
        print(f"   Volume 24h: {format_number(volume_24h)}")

        # Проверяем, что это V3-подобный пул (с концентрированной ликвидностью)
        if any(x in dex.lower() for x in ['v3', 'v4', 'slipstream', 'pancakeswap-v3', 'uniswap-v3', 'aerodrome-slipstream']):
            print("   Type: Concentrated Liquidity Pool ✓")

            # Получаем slot0
            slot0 = get_pool_slot0(pool_address)

            if slot0:
                tick = slot0['tick']
                sqrt_price_x96 = slot0['sqrtPriceX96']

                print(f"   Current Tick: {tick}")
                print(f"   SqrtPriceX96: {sqrt_price_x96}")

                # Вычисляем цену из sqrtPriceX96
                # price = (sqrtPriceX96 / 2^96)^2
                if sqrt_price_x96 > 0:
                    sqrt_price = sqrt_price_x96 / (2 ** 96)
                    price = sqrt_price ** 2
                    print(f"   Price (from sqrtPrice): {price:.8f}")

                    # Вычисляем цену из тика для сравнения
                    if abs(tick) < 1000000:  # Разумный диапазон
                        tick_price = 1.0001 ** tick
                        print(f"   Price (from tick): {tick_price:.8f}")
                else:
                    print(f"   Price: Unable to calculate")

                # Получаем ликвидность
                liquidity = get_pool_liquidity(pool_address)

                if liquidity:
                    print(f"   💧 Active Liquidity: {liquidity:,}")

                    # Вычисляем ликвидность в USD (приблизительно)
                    # L = sqrt(x * y), где x и y - количества токенов
                    # Для упрощения используем reserve
                    liquidity_ratio = (liquidity / 10**18) if liquidity > 0 else 0
                    print(f"   💧 Liquidity Ratio: {liquidity_ratio:.2f}")

                    successful_queries += 1
                else:
                    print("   ⚠ Не удалось получить liquidity")
                    failed_queries += 1
            else:
                print("   ⚠ Не удалось получить slot0")
                failed_queries += 1
        else:
            print("   Type: V2 Pool (не поддерживает концентрированную ликвидность)")
            failed_queries += 1

        print()

    # Статистика
    print("=" * 80)
    print("СТАТИСТИКА ЗАПРОСОВ:")
    print("=" * 80)
    print(f"✅ Успешных запросов: {successful_queries}")
    print(f"❌ Неудачных запросов: {failed_queries}")
    print(f"📊 Всего пулов проанализировано: {len(pools)}")
    print()

    print("=" * 80)
    print("ПРИМЕЧАНИЕ:")
    print("=" * 80)
    print("""
Активная ликвидность (Active Liquidity) - это количество ликвидности,
которая доступна для торговли в текущем ценовом диапазоне (тике).

Значение liquidity представлено в единицах L = sqrt(x * y), где:
- x - количество первого токена
- y - количество второго токена

В концентрированных пулах (V3) ликвидность сконцентрирована в определенных
ценовых диапазонах, что делает их более эффективными по капиталу.

Текущий тик (Current Tick) определяет текущую цену в пуле:
- Каждый тик соответствует изменению цены на ~0.01%
- Price = 1.0001^tick
    """)

    print("=" * 80)


if __name__ == "__main__":
    main()
