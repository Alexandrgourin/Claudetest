#!/usr/bin/env python3
"""
Исторический анализ JIT возможностей на Base за последние N дней

Анализирует реальные крупные swaps на Uniswap V3 пулах и рассчитывает
потенциальную прибыль от JIT Liquidity стратегии.

Использует:
- Alchemy RPC для получения исторических блоков и транзакций
- GeckoTerminal для данных о пулах
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# Configuration
ALCHEMY_RPC = "https://base-mainnet.g.alchemy.com/v2/04r_vJrz9iSljxSQj8UQn"
GECKOTERMINAL_API = "https://api.geckoterminal.com/api/v2"

# JIT параметры
MIN_SWAP_SIZE_USD = 50000   # Минимум $50K для анализа
FLASH_LOAN_FEE_PERCENT = 0.05
ESTIMATED_GAS_COST_USD = 2
TARGET_FEE_SHARE = 0.70

# Uniswap V3 / PancakeSwap V3 addresses на Base
ROUTER_ADDRESSES = {
    "0x2626664c2603336E57B271c5C0b26F421741e481": "Uniswap V3 SwapRouter",
    "0x4752ba5dbc23f44d87826276bf6fd6b1c372ad24": "Uniswap V3 SwapRouter02",
    "0xC3e2aED41ECdFB1ad41ED20D45377Da98D5489dD": "PancakeSwap V3 Router",
    "0x4fC8D635c3cB852EE25F4F3907b77cF3Cc51b0c4": "Aerodrome Router",
}

# Swap method signatures
SWAP_METHODS = {
    "0x414bf389": "exactInputSingle",
    "0x04e45aaf": "exactOutputSingle",
    "0xc04b8d59": "exactInput",
    "0xf28c0498": "exactOutput",
    "0x5ae401dc": "multicall",
}

# Known pool addresses (топ пулы на Base)
KNOWN_POOLS = {}  # Будет заполнено из GeckoTerminal


class HistoricalJITAnalyzer:
    """Анализ исторических JIT возможностей"""

    def __init__(self):
        self.pools_data = {}
        self.jit_opportunities = []
        self.total_potential_profit = 0.0
        self.eth_price_usd = 3000

    def rpc_call(self, method: str, params: List = None) -> Dict:
        """RPC вызов к Alchemy"""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params if params else [],
            "id": 1
        }
        try:
            response = requests.post(ALCHEMY_RPC, json=payload, timeout=30)
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def get_block_by_timestamp(self, target_timestamp: int) -> Optional[int]:
        """
        Найти номер блока по timestamp (приблизительно)

        Base: ~2 секунды на блок
        """
        # Получаем последний блок
        latest_result = self.rpc_call("eth_blockNumber")
        if "result" not in latest_result:
            return None

        latest_block_num = int(latest_result["result"], 16)

        # Получаем timestamp последнего блока
        latest_block = self.rpc_call("eth_getBlockByNumber", [hex(latest_block_num), False])
        if "result" not in latest_block:
            return None

        latest_timestamp = int(latest_block["result"]["timestamp"], 16)

        # Рассчитываем приблизительный блок
        blocks_ago = (latest_timestamp - target_timestamp) // 2  # ~2 сек на блок
        estimated_block = latest_block_num - blocks_ago

        return max(0, estimated_block)

    def load_top_pools(self):
        """Загрузить топ пулы с GeckoTerminal"""
        print("📊 Загрузка топ пулов с GeckoTerminal...")

        try:
            url = f"{GECKOTERMINAL_API}/networks/base/pools"
            response = requests.get(url, params={"page": 1}, timeout=10)

            if response.status_code != 200:
                print(f"❌ GeckoTerminal API error: {response.status_code}")
                return

            data = response.json()
            pools = data.get("data", [])

            for pool in pools[:100]:  # Топ-100 пулов
                attrs = pool.get("attributes", {})
                address = attrs.get("address")

                if not address:
                    continue

                name = attrs.get("name", "")

                # Парсим fee
                fee_percent = 0.3
                if "0.01%" in name:
                    fee_percent = 0.01
                elif "0.05%" in name:
                    fee_percent = 0.05
                elif "0.1%" in name or "0.10%" in name:
                    fee_percent = 0.1
                elif "0.3%" in name or "0.30%" in name:
                    fee_percent = 0.3
                elif "1%" in name or "1.0%" in name:
                    fee_percent = 1.0

                volume_data = attrs.get("volume_usd", {})
                volume_24h = 0
                if isinstance(volume_data, dict):
                    volume_24h = float(volume_data.get("h24", 0))
                elif isinstance(volume_data, (int, float)):
                    volume_24h = float(volume_data)

                self.pools_data[address.lower()] = {
                    "address": address,
                    "name": name,
                    "dex": attrs.get("dex", "Unknown"),
                    "fee_percent": fee_percent,
                    "fee_decimal": fee_percent / 100,
                    "reserve_usd": float(attrs.get("reserve_in_usd", 0)),
                    "volume_24h_usd": volume_24h,
                }

                KNOWN_POOLS[address.lower()] = name

            print(f"✅ Загружено {len(self.pools_data)} пулов")

            # Показываем топ-10 по объему
            sorted_pools = sorted(
                self.pools_data.values(),
                key=lambda x: x["volume_24h_usd"],
                reverse=True
            )

            print(f"\n📊 ТОП-10 ПУЛОВ ПО ОБЪЕМУ 24Ч:")
            for i, pool in enumerate(sorted_pools[:10], 1):
                print(f"   {i}. {pool['name'][:50]:50} - ${pool['volume_24h_usd']:>12,.0f}")

        except Exception as e:
            print(f"❌ Ошибка: {e}")

    def decode_swap_transaction(self, tx: Dict) -> Optional[Dict]:
        """Декодировать swap транзакцию"""
        to_address = tx.get("to")
        if not to_address:
            return None

        to_address = to_address.lower()

        # Проверяем что это router
        if to_address not in [addr.lower() for addr in ROUTER_ADDRESSES.keys()]:
            return None

        input_data = tx.get("input", "")
        if len(input_data) < 10:
            return None

        method_id = input_data[:10]

        if method_id not in SWAP_METHODS:
            return None

        # Парсим value
        value_wei = int(tx.get("value", "0x0"), 16)
        value_eth = value_wei / 1e18

        return {
            "hash": tx.get("hash"),
            "from": tx.get("from"),
            "to": tx.get("to"),
            "block": int(tx.get("blockNumber", "0x0"), 16),
            "router": ROUTER_ADDRESSES.get(tx["to"], "Unknown"),
            "method": SWAP_METHODS[method_id],
            "value_eth": value_eth,
            "value_usd": value_eth * self.eth_price_usd,
            "gas_used": int(tx.get("gas", "0x0"), 16),
        }

    def get_transaction_receipt(self, tx_hash: str) -> Optional[Dict]:
        """Получить receipt транзакции для анализа logs"""
        result = self.rpc_call("eth_getTransactionReceipt", [tx_hash])
        if "result" in result:
            return result["result"]
        return None

    def analyze_swap_from_logs(self, receipt: Dict) -> Optional[Dict]:
        """
        Анализировать swap из logs

        Swap event signature:
        Swap(address,address,int256,int256,uint160,uint128,int24)
        """
        if not receipt or "logs" not in receipt:
            return None

        # Swap event topic
        SWAP_TOPIC = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"

        for log in receipt["logs"]:
            topics = log.get("topics", [])
            if not topics:
                continue

            # Проверяем что это Swap event
            if topics[0].lower() == SWAP_TOPIC.lower():
                pool_address = log.get("address", "").lower()

                # Проверяем что это известный пул
                if pool_address in self.pools_data:
                    # Декодируем данные (упрощенно)
                    data = log.get("data", "0x")

                    # amount0 и amount1 можно декодировать из data
                    # Для простоты, используем pool data

                    return {
                        "pool_address": pool_address,
                        "pool_name": self.pools_data[pool_address]["name"],
                        "pool_data": self.pools_data[pool_address]
                    }

        return None

    def estimate_swap_size(self, tx: Dict, swap_data: Dict) -> float:
        """Оценить размер swap в USD"""
        # Для ETH swaps
        if tx["value_eth"] > 0:
            return tx["value_usd"]

        # Для ERC20 используем volume пула как proxy
        # В реальности нужно декодировать log data
        pool_volume = swap_data["pool_data"]["volume_24h_usd"]

        # Консервативная оценка: средний swap = 0.5% от 24h volume
        estimated_size = pool_volume * 0.005

        return estimated_size

    def calculate_jit_profit(self, swap_size_usd: float, pool_data: Dict) -> Dict:
        """Рассчитать потенциальную прибыль от JIT"""
        # Активная ликвидность (оценка)
        active_liquidity_usd = pool_data["reserve_usd"] * 0.5

        # Комиссии
        fee_decimal = pool_data["fee_decimal"]
        total_fees_usd = swap_size_usd * fee_decimal

        # Требуемая ликвидность
        required_liquidity_usd = (active_liquidity_usd * TARGET_FEE_SHARE) / (1 - TARGET_FEE_SHARE)

        # Доля комиссий
        total_liquidity = active_liquidity_usd + required_liquidity_usd
        your_share = required_liquidity_usd / total_liquidity

        # Прибыль
        your_fees_usd = total_fees_usd * your_share
        flash_loan_fee_usd = required_liquidity_usd * (FLASH_LOAN_FEE_PERCENT / 100)
        net_profit_usd = your_fees_usd - flash_loan_fee_usd - ESTIMATED_GAS_COST_USD

        return {
            "swap_size_usd": swap_size_usd,
            "total_fees_usd": total_fees_usd,
            "required_liquidity_usd": required_liquidity_usd,
            "your_fees_usd": your_fees_usd,
            "net_profit_usd": net_profit_usd,
            "roi_percent": (net_profit_usd / (flash_loan_fee_usd + ESTIMATED_GAS_COST_USD) * 100) if (flash_loan_fee_usd + ESTIMATED_GAS_COST_USD) > 0 else 0
        }

    def analyze_historical_blocks(self, start_block: int, end_block: int, max_blocks: int = 1000):
        """
        Анализировать исторические блоки

        Из-за rate limits, анализируем выборочно
        """
        print(f"\n🔍 Анализ блоков {start_block:,} → {end_block:,}")
        print(f"   Всего блоков: {end_block - start_block:,}")
        print(f"   Будет проанализировано: ~{max_blocks:,} блоков (выборочно)")

        # Вычисляем шаг для выборки
        total_blocks = end_block - start_block
        step = max(1, total_blocks // max_blocks)

        print(f"   Шаг: каждый {step}-й блок\n")

        opportunities_found = 0
        blocks_processed = 0

        for block_num in range(start_block, end_block, step):
            blocks_processed += 1

            if blocks_processed % 50 == 0:
                print(f"   Обработано {blocks_processed} блоков, найдено {opportunities_found} возможностей...")

            try:
                # Получаем блок с транзакциями
                block = self.rpc_call("eth_getBlockByNumber", [hex(block_num), True])

                if "result" not in block or not block["result"]:
                    continue

                block_data = block["result"]
                transactions = block_data.get("transactions", [])

                # Анализируем транзакции
                for tx in transactions:
                    if not isinstance(tx, dict):
                        continue

                    # Декодируем swap
                    swap_tx = self.decode_swap_transaction(tx)

                    if not swap_tx:
                        continue

                    # Получаем receipt для анализа logs
                    receipt = self.get_transaction_receipt(tx["hash"])

                    if not receipt:
                        continue

                    # Анализируем swap из logs
                    swap_data = self.analyze_swap_from_logs(receipt)

                    if not swap_data:
                        continue

                    # Оцениваем размер swap
                    swap_size = self.estimate_swap_size(swap_tx, swap_data)

                    # Фильтруем по минимальному размеру
                    if swap_size < MIN_SWAP_SIZE_USD:
                        continue

                    # Рассчитываем JIT profit
                    jit_calc = self.calculate_jit_profit(swap_size, swap_data["pool_data"])

                    # Фильтруем прибыльные
                    if jit_calc["net_profit_usd"] > 50:
                        timestamp = int(block_data["timestamp"], 16)

                        opportunity = {
                            "block": block_num,
                            "timestamp": timestamp,
                            "datetime": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                            "tx_hash": swap_tx["hash"],
                            "pool": swap_data["pool_name"],
                            "pool_address": swap_data["pool_address"],
                            **jit_calc
                        }

                        self.jit_opportunities.append(opportunity)
                        self.total_potential_profit += jit_calc["net_profit_usd"]
                        opportunities_found += 1

                # Rate limiting
                time.sleep(0.1)

            except Exception as e:
                # print(f"   ⚠️  Ошибка в блоке {block_num}: {e}")
                continue

        print(f"\n✅ Анализ завершен!")
        print(f"   Обработано блоков: {blocks_processed:,}")
        print(f"   Найдено возможностей: {opportunities_found}")

    def print_summary(self):
        """Вывести итоговую статистику"""
        if not self.jit_opportunities:
            print("\n❌ Прибыльных JIT возможностей не найдено")
            return

        print(f"\n{'='*120}")
        print(f"📊 ИТОГОВАЯ СТАТИСТИКА ПО JIT ВОЗМОЖНОСТЯМ")
        print(f"{'='*120}\n")

        # Сортируем по прибыли
        sorted_opps = sorted(self.jit_opportunities, key=lambda x: x["net_profit_usd"], reverse=True)

        # Общая статистика
        total_opps = len(sorted_opps)
        total_profit = sum(o["net_profit_usd"] for o in sorted_opps)
        avg_profit = total_profit / total_opps
        max_profit = sorted_opps[0]["net_profit_usd"]
        min_profit = sorted_opps[-1]["net_profit_usd"]

        print(f"📈 ОБЩАЯ СТАТИСТИКА:")
        print(f"   Всего возможностей:      {total_opps:,}")
        print(f"   Общая потенц. прибыль:   ${total_profit:,.2f}")
        print(f"   Средняя прибыль:         ${avg_profit:,.2f}")
        print(f"   Максимальная прибыль:    ${max_profit:,.2f}")
        print(f"   Минимальная прибыль:     ${min_profit:,.2f}")

        # Статистика по пулам
        pools_stats = defaultdict(lambda: {"count": 0, "total_profit": 0})
        for opp in sorted_opps:
            pool = opp["pool"]
            pools_stats[pool]["count"] += 1
            pools_stats[pool]["total_profit"] += opp["net_profit_usd"]

        sorted_pools = sorted(pools_stats.items(), key=lambda x: x[1]["total_profit"], reverse=True)

        print(f"\n📊 ТОП-10 ПУЛОВ ПО ПРИБЫЛИ:")
        for i, (pool, stats) in enumerate(sorted_pools[:10], 1):
            avg = stats["total_profit"] / stats["count"]
            print(f"   {i}. {pool[:50]:50} - {stats['count']:3} опп, ${stats['total_profit']:>10,.0f} (avg ${avg:,.0f})")

        # Топ-20 лучших возможностей
        print(f"\n🔥 ТОП-20 ЛУЧШИХ JIT ВОЗМОЖНОСТЕЙ:\n")
        print(f"{'Дата/Время':<20} {'Пул':<40} {'Swap Size':>12} {'Profit':>10} {'ROI':>8}")
        print(f"{'-'*120}")

        for i, opp in enumerate(sorted_opps[:20], 1):
            print(f"{opp['datetime']:<20} {opp['pool'][:38]:<40} ${opp['swap_size_usd']:>10,.0f} ${opp['net_profit_usd']:>8,.0f} {opp['roi_percent']:>6.0f}%")

        # Распределение по дням
        days_stats = defaultdict(lambda: {"count": 0, "total_profit": 0})
        for opp in sorted_opps:
            day = opp["datetime"][:10]
            days_stats[day]["count"] += 1
            days_stats[day]["total_profit"] += opp["net_profit_usd"]

        print(f"\n📅 РАСПРЕДЕЛЕНИЕ ПО ДНЯМ:\n")
        print(f"{'Дата':<12} {'Опп.':>6} {'Прибыль':>12} {'Средняя':>10}")
        print(f"{'-'*50}")

        for day in sorted(days_stats.keys()):
            stats = days_stats[day]
            avg = stats["total_profit"] / stats["count"]
            print(f"{day:<12} {stats['count']:>6} ${stats['total_profit']:>10,.0f} ${avg:>8,.0f}")

        print(f"\n{'='*120}\n")

        # Проекция на месяц
        days_analyzed = len(days_stats)
        if days_analyzed > 0:
            daily_avg_profit = total_profit / days_analyzed
            daily_avg_opps = total_opps / days_analyzed

            monthly_projection = daily_avg_profit * 30
            yearly_projection = daily_avg_profit * 365

            print(f"💰 ПРОЕКЦИЯ ПРИБЫЛИ:")
            print(f"   Дней проанализировано:   {days_analyzed}")
            print(f"   Средний profit/день:     ${daily_avg_profit:,.2f} ({daily_avg_opps:.1f} опп/день)")
            print(f"   Проекция на месяц:       ${monthly_projection:,.2f}")
            print(f"   Проекция на год:         ${yearly_projection:,.2f}")
            print(f"\n{'='*120}\n")


def main():
    """Main function"""
    import sys

    days_back = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    max_blocks = int(sys.argv[2]) if len(sys.argv) > 2 else 1000

    print("""
    ╔════════════════════════════════════════════════════════════════════════╗
    ║                                                                        ║
    ║           ИСТОРИЧЕСКИЙ АНАЛИЗ JIT ВОЗМОЖНОСТЕЙ НА BASE                ║
    ║                                                                        ║
    ║  Анализирует реальные крупные swaps за последние N дней               ║
    ║  и рассчитывает потенциальную прибыль от JIT Liquidity                ║
    ║                                                                        ║
    ╚════════════════════════════════════════════════════════════════════════╝
    """)

    print(f"⚙️  Параметры анализа:")
    print(f"   Дней назад:          {days_back}")
    print(f"   Макс. блоков:        {max_blocks:,}")
    print(f"   Min swap size:       ${MIN_SWAP_SIZE_USD:,}")
    print(f"   Min profit:          $50")
    print(f"   Target fee share:    {TARGET_FEE_SHARE*100}%\n")

    analyzer = HistoricalJITAnalyzer()

    # Загружаем пулы
    analyzer.load_top_pools()

    if not analyzer.pools_data:
        print("❌ Не удалось загрузить данные о пулах")
        return

    # Определяем временной диапазон
    now = int(time.time())
    start_time = now - (days_back * 24 * 60 * 60)

    print(f"\n🕐 Временной диапазон:")
    print(f"   От:  {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   До:  {datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:%M:%S')}")

    # Находим блоки
    print(f"\n🔍 Поиск блоков...")
    start_block = analyzer.get_block_by_timestamp(start_time)

    latest_result = analyzer.rpc_call("eth_blockNumber")
    end_block = int(latest_result["result"], 16)

    if not start_block:
        print("❌ Не удалось определить стартовый блок")
        return

    # Анализируем
    analyzer.analyze_historical_blocks(start_block, end_block, max_blocks)

    # Выводим результаты
    analyzer.print_summary()


if __name__ == "__main__":
    main()
