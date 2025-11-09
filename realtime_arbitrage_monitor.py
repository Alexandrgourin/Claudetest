#!/usr/bin/env python3
"""
Real-time арбитраж мониторинг с использованием flashblocks на Base

Этот скрипт демонстрирует как использовать преимущество собственной ноды
с flashblocks для обнаружения арбитражных возможностей раньше конкурентов.

Features:
- Мониторинг pending блоков через flashblocks
- Обнаружение крупных swaps в мемпуле
- Расчет арбитражных возможностей
- Симуляция потенциальной прибыли
- Real-time alerts в Telegram (опционально)
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from decimal import Decimal

# Configuration
NODE_URL = "http://80.209.241.37:8545/"
GECKOTERMINAL_API = "https://api.geckoterminal.com/api/v2"

# Параметры для алертов
MIN_PROFIT_PERCENT = 0.1  # Минимальный профит для alert (0.1%)
MIN_SWAP_SIZE_USD = 10000  # Минимальный размер swap для мониторинга ($10K)
CHECK_INTERVAL = 1  # Секунды между проверками

# Known DEX router addresses на Base (примеры)
DEX_ROUTERS = {
    "0x2626664c2603336E57B271c5C0b26F421741e481": "Uniswap V3 Router",
    "0xC3e2aED41ECdFB1ad41ED20D45377Da98D5489dD": "PancakeSwap V3 Router",
    "0x4fC8D635c3cB852EE25F4F3907b77cF3Cc51b0c4": "Aerodrome Router",
    "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D": "SushiSwap Router",
}

# ABI для декодирования swap методов
SWAP_METHOD_IDS = {
    "0x38ed1739": "swapExactTokensForTokens",
    "0x8803dbee": "swapTokensForExactTokens",
    "0x7ff36ab5": "swapExactETHForTokens",
    "0x18cbafe5": "swapExactTokensForETH",
    "0x414bf389": "exactInputSingle",  # Uniswap V3
    "0x5ae401dc": "multicall",  # Uniswap V3 multicall
}


class FlashblockArbitrageMonitor:
    """Мониторинг арбитража через flashblocks"""

    def __init__(self):
        self.pools_cache = {}
        self.last_prices = defaultdict(dict)
        self.arbitrage_count = 0
        self.total_potential_profit = 0.0

    def rpc_call(self, method: str, params: List = None) -> Dict:
        """Выполнить RPC вызов к ноде"""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params if params else [],
            "id": 1
        }
        try:
            response = requests.post(NODE_URL, json=payload, timeout=5)
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def get_pending_block(self) -> Optional[Dict]:
        """
        Получить pending блок через flashblocks

        Это ключевое преимущество - мы видим транзакции
        раньше чем они попадут в финализированный блок
        """
        result = self.rpc_call("eth_getBlockByNumber", ["pending", True])
        if result.get("result"):
            return result["result"]
        return None

    def get_pool_price(self, pool_address: str) -> Optional[Tuple[float, int]]:
        """Получить текущую цену из пула через slot0()"""
        # slot0() function signature
        data = "0x3850c7bd"

        result = self.rpc_call("eth_call", [{
            "to": pool_address,
            "data": data
        }, "latest"])

        if "result" in result and result["result"] != "0x":
            try:
                hex_data = result["result"][2:]
                # sqrtPriceX96 - первые 32 байта
                sqrt_price_x96 = int(hex_data[0:64], 16)
                # tick - следующие 32 байта (int24)
                tick_hex = hex_data[64:128]
                tick_raw = int(tick_hex, 16)

                # Конвертация в signed int24
                if tick_raw > 2**23:
                    tick = tick_raw - 2**24
                else:
                    tick = tick_raw

                # Расчет цены из sqrtPriceX96
                price = (sqrt_price_x96 / (2**96)) ** 2

                return (price, tick)
            except:
                return None
        return None

    def decode_swap_transaction(self, tx: Dict) -> Optional[Dict]:
        """
        Декодировать swap транзакцию из pending блока

        Returns:
            Dict с информацией о swap или None
        """
        if not tx.get("input") or len(tx["input"]) < 10:
            return None

        to_address = tx.get("to")
        if not to_address:
            return None

        to_address = to_address.lower()
        method_id = tx["input"][:10]

        # Проверяем что это DEX router
        if to_address not in [addr.lower() for addr in DEX_ROUTERS.keys()]:
            return None

        # Проверяем что это swap метод
        if method_id not in SWAP_METHOD_IDS:
            return None

        dex_name = DEX_ROUTERS.get(tx["to"], "Unknown DEX")

        # Парсим value (для ETH swaps)
        value_wei = int(tx.get("value", "0x0"), 16)
        value_eth = value_wei / 1e18

        return {
            "hash": tx.get("hash"),
            "from": tx.get("from"),
            "to": tx.get("to"),
            "dex": dex_name,
            "method": SWAP_METHOD_IDS[method_id],
            "value_eth": value_eth,
            "gas_price": int(tx.get("gasPrice", "0x0"), 16) / 1e9,  # Gwei
            "input_data": tx["input"]
        }

    def estimate_swap_size(self, swap_tx: Dict) -> float:
        """
        Оценить размер swap в USD

        Упрощенная оценка: используем value_eth * ETH_PRICE
        В реальном боте нужно декодировать parameters
        """
        ETH_PRICE_USD = 3000  # Примерная цена, в проде брать из oracle

        if swap_tx["value_eth"] > 0:
            return swap_tx["value_eth"] * ETH_PRICE_USD

        # Для ERC20 swaps нужно декодировать input data
        # Упрощенно возвращаем 0, в реальности нужен ABI decoder
        return 0

    def fetch_dex_pools(self, limit: int = 100) -> List[Dict]:
        """Получить список пулов с GeckoTerminal"""
        try:
            url = f"{GECKOTERMINAL_API}/networks/base/pools"
            params = {"page": 1}
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
        except Exception as e:
            print(f"❌ Ошибка загрузки пулов: {e}")

        return []

    def build_pools_cache(self):
        """Построить кеш пулов для быстрого поиска арбитража"""
        print("📊 Загрузка пулов с GeckoTerminal...")
        pools = self.fetch_dex_pools()

        # Группировка по токен парам
        for pool in pools:
            attrs = pool.get("attributes", {})
            address = attrs.get("address")

            if not address:
                continue

            # Получаем имена токенов
            name = attrs.get("name", "")

            # Парсим название пула (обычно формата "TOKEN1 / TOKEN2")
            if " / " in name:
                tokens = name.split(" / ")
                if len(tokens) >= 2:
                    # Убираем fee tier из имени (например "0.05%" в конце)
                    token1 = tokens[0].strip()
                    token2_parts = tokens[1].split()
                    token2 = token2_parts[0].strip() if token2_parts else tokens[1].strip()

                    base_token = token1
                    quote_token = token2
                else:
                    continue
            else:
                # Альтернативный метод - через relationships
                continue

            if not base_token or not quote_token:
                continue

            pair = tuple(sorted([base_token, quote_token]))

            if pair not in self.pools_cache:
                self.pools_cache[pair] = []

            # Парсим fee из имени
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

            self.pools_cache[pair].append({
                "address": address,
                "dex": attrs.get("dex", "Unknown"),
                "fee": fee_percent,
                "base_token": base_token,
                "quote_token": quote_token,
                "reserve_usd": float(attrs.get("reserve_in_usd", 0))
            })

        print(f"✅ Загружено {len(pools)} пулов")
        print(f"✅ Найдено {len(self.pools_cache)} уникальных пар")

    def find_arbitrage_for_pair(self, pair: Tuple[str, str]) -> Optional[Dict]:
        """
        Найти арбитраж для конкретной пары токенов

        Returns:
            Dict с информацией об арбитраже или None
        """
        pools = self.pools_cache.get(pair, [])

        if len(pools) < 2:
            return None

        # Получаем цены из всех пулов этой пары
        prices = []
        for pool in pools:
            price_data = self.get_pool_price(pool["address"])
            if price_data:
                price, tick = price_data
                prices.append({
                    "pool": pool,
                    "price": price,
                    "tick": tick
                })

        if len(prices) < 2:
            return None

        # Находим минимальную и максимальную цену
        cheapest = min(prices, key=lambda x: x["price"])
        expensive = max(prices, key=lambda x: x["price"])

        # Рассчитываем profit
        price_diff = ((expensive["price"] - cheapest["price"]) / cheapest["price"]) * 100
        total_fees = cheapest["pool"]["fee"] + expensive["pool"]["fee"]
        net_profit = price_diff - total_fees

        if net_profit > MIN_PROFIT_PERCENT:
            return {
                "pair": f"{pair[0]}/{pair[1]}",
                "buy_pool": cheapest["pool"],
                "sell_pool": expensive["pool"],
                "buy_price": cheapest["price"],
                "sell_price": expensive["price"],
                "price_diff_percent": price_diff,
                "total_fees_percent": total_fees,
                "net_profit_percent": net_profit,
                "buy_tick": cheapest["tick"],
                "sell_tick": expensive["tick"]
            }

        return None

    def scan_all_pairs(self) -> List[Dict]:
        """Сканировать все пары на арбитраж"""
        opportunities = []

        for pair in self.pools_cache.keys():
            arb = self.find_arbitrage_for_pair(pair)
            if arb:
                opportunities.append(arb)

        return sorted(opportunities, key=lambda x: x["net_profit_percent"], reverse=True)

    def monitor_pending_swaps(self):
        """
        Мониторинг pending swaps через flashblocks

        Это основная функция - отслеживает крупные swaps
        и ищет возможности для frontrun/backrun
        """
        pending_block = self.get_pending_block()

        if not pending_block or "transactions" not in pending_block:
            return []

        swaps = []
        for tx in pending_block["transactions"]:
            if not isinstance(tx, dict):
                continue

            swap_info = self.decode_swap_transaction(tx)
            if swap_info:
                swap_size = self.estimate_swap_size(swap_info)

                if swap_size >= MIN_SWAP_SIZE_USD:
                    swaps.append({
                        **swap_info,
                        "size_usd": swap_size
                    })

        return swaps

    def print_arbitrage_opportunity(self, arb: Dict):
        """Красиво вывести информацию об арбитраже"""
        print("\n" + "="*100)
        print(f"🔥 АРБИТРАЖНАЯ ВОЗМОЖНОСТЬ ОБНАРУЖЕНА!")
        print("="*100)
        print(f"\n💱 Пара: {arb['pair']}")
        print(f"\n📉 КУПИТЬ (дешевле):")
        print(f"   DEX:   {arb['buy_pool']['dex']}")
        print(f"   Цена:  {arb['buy_price']:.10f}")
        print(f"   Tick:  {arb['buy_tick']}")
        print(f"   Fee:   {arb['buy_pool']['fee']:.2f}%")
        print(f"\n📈 ПРОДАТЬ (дороже):")
        print(f"   DEX:   {arb['sell_pool']['dex']}")
        print(f"   Цена:  {arb['sell_price']:.10f}")
        print(f"   Tick:  {arb['sell_tick']}")
        print(f"   Fee:   {arb['sell_pool']['fee']:.2f}%")
        print(f"\n💰 ЭКОНОМИКА:")
        print(f"   Разница цен:    {arb['price_diff_percent']:.4f}%")
        print(f"   Комиссии DEX:   {arb['total_fees_percent']:.4f}%")
        print(f"   🔥 Чистый профит: {arb['net_profit_percent']:.4f}%")

        # Расчет потенциальной прибыли
        capital_options = [1000, 5000, 10000, 50000]
        print(f"\n💵 ПОТЕНЦИАЛЬНАЯ ПРИБЫЛЬ:")
        for capital in capital_options:
            profit = capital * (arb['net_profit_percent'] / 100)
            print(f"   С ${capital:,}: ${profit:.2f}")

        print("\n" + "="*100 + "\n")

    def print_pending_swap(self, swap: Dict):
        """Вывести информацию о крупном pending swap"""
        print("\n" + "-"*100)
        print(f"⚡ КРУПНЫЙ SWAP ОБНАРУЖЕН В FLASHBLOCK")
        print("-"*100)
        print(f"Hash:     {swap['hash']}")
        print(f"DEX:      {swap['dex']}")
        print(f"Method:   {swap['method']}")
        print(f"Size:     ${swap['size_usd']:,.2f}")
        print(f"Gas:      {swap['gas_price']:.2f} Gwei")
        print(f"\n💡 Возможные действия:")
        print(f"   - Backrun: дождаться исполнения и сделать арбитраж")
        print(f"   - Frontrun: опередить транзакцию (этически спорно)")
        print(f"   - Monitor: отследить влияние на цены пулов")
        print("-"*100 + "\n")

    def run_monitoring(self, duration_minutes: int = 60):
        """
        Запустить мониторинг

        Args:
            duration_minutes: Длительность мониторинга в минутах
        """
        print("="*100)
        print("🚀 REAL-TIME АРБИТРАЖ МОНИТОРИНГ С FLASHBLOCKS")
        print("="*100)
        print(f"\n🔍 Параметры:")
        print(f"   Нода:                {NODE_URL}")
        print(f"   Min profit:          {MIN_PROFIT_PERCENT}%")
        print(f"   Min swap size:       ${MIN_SWAP_SIZE_USD:,}")
        print(f"   Интервал проверки:   {CHECK_INTERVAL}s")
        print(f"   Длительность:        {duration_minutes} минут")
        print(f"\n⏳ Загрузка данных...\n")

        # Построить кеш пулов
        self.build_pools_cache()

        # Начальный scan на арбитраж
        print(f"\n🔍 Начальное сканирование арбитражных возможностей...")
        initial_opps = self.scan_all_pairs()

        if initial_opps:
            print(f"\n✅ Найдено {len(initial_opps)} возможностей:")
            for i, opp in enumerate(initial_opps[:5], 1):  # Показать топ-5
                print(f"{i}. {opp['pair']}: {opp['net_profit_percent']:.4f}% profit")

            # Показать детали лучшей возможности
            if initial_opps[0]['net_profit_percent'] > MIN_PROFIT_PERCENT:
                self.print_arbitrage_opportunity(initial_opps[0])
        else:
            print(f"📊 Прибыльных арбитражей пока нет")

        print(f"\n{'='*100}")
        print(f"👀 НАЧИНАЕМ МОНИТОРИНГ FLASHBLOCKS...")
        print(f"{'='*100}\n")

        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        iteration = 0

        try:
            while time.time() < end_time:
                iteration += 1
                timestamp = datetime.now().strftime("%H:%M:%S")

                # Мониторим pending swaps
                pending_swaps = self.monitor_pending_swaps()

                if pending_swaps:
                    for swap in pending_swaps:
                        self.print_pending_swap(swap)
                        # TODO: здесь можно автоматически запустить анализ арбитража

                # Периодически пересканируем все пары
                if iteration % 10 == 0:
                    print(f"[{timestamp}] 🔄 Пересканирование всех пар...")
                    new_opps = self.scan_all_pairs()

                    if new_opps and new_opps[0]['net_profit_percent'] > MIN_PROFIT_PERCENT:
                        self.print_arbitrage_opportunity(new_opps[0])
                        self.arbitrage_count += 1
                        self.total_potential_profit += new_opps[0]['net_profit_percent']
                else:
                    print(f"[{timestamp}] ✓ Итерация #{iteration} - мониторинг активен...", end='\r')

                time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print(f"\n\n⏹️  Мониторинг остановлен пользователем")

        # Статистика
        elapsed = (time.time() - start_time) / 60
        print(f"\n{'='*100}")
        print(f"📊 СТАТИСТИКА МОНИТОРИНГА")
        print(f"{'='*100}")
        print(f"Время работы:           {elapsed:.1f} минут")
        print(f"Итераций:               {iteration}")
        print(f"Найдено возможностей:   {self.arbitrage_count}")
        if self.arbitrage_count > 0:
            avg_profit = self.total_potential_profit / self.arbitrage_count
            print(f"Средний профит:         {avg_profit:.4f}%")
        print(f"{'='*100}\n")


def main():
    """Main function"""
    import sys

    # Параметры из командной строки
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 60

    monitor = FlashblockArbitrageMonitor()
    monitor.run_monitoring(duration_minutes=duration)


if __name__ == "__main__":
    main()
