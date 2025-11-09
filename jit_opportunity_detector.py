#!/usr/bin/env python3
"""
JIT (Just-In-Time) Liquidity Opportunity Detector

Мониторит pending блоки через flashblocks и детектирует прибыльные
возможности для JIT liquidity стратегии на Uniswap V3 пулах.

Использование:
    python3 jit_opportunity_detector.py [duration_minutes]
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

# Configuration
NODE_URL = "http://80.209.241.37:8545/"
GECKOTERMINAL_API = "https://api.geckoterminal.com/api/v2"

# JIT параметры
MIN_SWAP_SIZE_USD = 100000  # Минимум $100K swap для JIT
MIN_NET_PROFIT_USD = 50     # Минимум $50 чистой прибыли
FLASH_LOAN_FEE_PERCENT = 0.05  # Aave 0.05%
ESTIMATED_GAS_COST_USD = 2  # Консервативная оценка gas на Base
TARGET_FEE_SHARE = 0.70     # Целевая доля комиссий (70%)

# Uniswap V3 Router addresses на Base
UNISWAP_ROUTERS = {
    "0x2626664c2603336E57B271c5C0b26F421741e481": "Uniswap V3 SwapRouter",
    "0x4752ba5dbc23f44d87826276bf6fd6b1c372ad24": "Uniswap V3 SwapRouter02",
    "0xC3e2aED41ECdFB1ad41ED20D45377Da98D5489dD": "PancakeSwap V3 Router",
    "0x4fC8D635c3cB852EE25F4F3907b77cF3Cc51b0c4": "Aerodrome Router",
}

# Method signatures для swap функций
SWAP_METHODS = {
    "0x414bf389": "exactInputSingle",     # Uniswap V3
    "0x04e45aaf": "exactOutputSingle",    # Uniswap V3
    "0xc04b8d59": "exactInput",           # Uniswap V3 multi-hop
    "0xf28c0498": "exactOutput",          # Uniswap V3 multi-hop
    "0x5ae401dc": "multicall",            # Uniswap V3 multicall
}


class JITOpportunityDetector:
    """Детектор JIT возможностей через flashblocks"""

    def __init__(self):
        self.pools_data = {}
        self.opportunities_found = 0
        self.total_potential_profit = 0.0
        self.eth_price_usd = 3000  # Обновляется динамически

    def rpc_call(self, method: str, params: List = None) -> Dict:
        """RPC вызов к ноде"""
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
        """Получить pending блок через flashblocks"""
        result = self.rpc_call("eth_getBlockByNumber", ["pending", True])
        if result.get("result"):
            return result["result"]
        return None

    def load_pools_data(self):
        """Загрузить данные о пулах"""
        print("📊 Загрузка данных о пулах...")

        try:
            # Получаем пулы с GeckoTerminal
            url = f"{GECKOTERMINAL_API}/networks/base/pools"
            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                print(f"❌ GeckoTerminal API error: {response.status_code}")
                return

            data = response.json()
            pools = data.get("data", [])
            print(f"   Получено {len(pools)} пулов от GeckoTerminal")

            loaded_count = 0
            for i, pool in enumerate(pools[:50], 1):  # Ограничим первыми 50 для скорости
                attrs = pool.get("attributes", {})
                address = attrs.get("address")

                if not address:
                    continue

                # Получаем on-chain данные
                pool_state = self.get_pool_state(address)

                if pool_state:
                    name = attrs.get("name", "")

                    # Парсим fee из имени
                    fee_percent = 0.3  # default
                    try:
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
                    except:
                        pass

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
                        **pool_state
                    }
                    loaded_count += 1

                if i % 10 == 0:
                    print(f"   Обработано {i}/{len(pools[:50])} пулов... ({loaded_count} с on-chain данными)")

            print(f"✅ Загружено {len(self.pools_data)} пулов с on-chain данными")

        except Exception as e:
            print(f"❌ Ошибка загрузки пулов: {e}")
            import traceback
            traceback.print_exc()

    def get_pool_state(self, pool_address: str) -> Optional[Dict]:
        """
        Получить текущее состояние пула через slot0() и liquidity()
        """
        # slot0()
        slot0_result = self.rpc_call("eth_call", [{
            "to": pool_address,
            "data": "0x3850c7bd"  # slot0()
        }, "latest"])

        # liquidity()
        liquidity_result = self.rpc_call("eth_call", [{
            "to": pool_address,
            "data": "0x1a686502"  # liquidity()
        }, "latest"])

        if "result" in slot0_result and "result" in liquidity_result:
            try:
                # Парсим slot0
                slot0_data = slot0_result["result"][2:]
                sqrt_price_x96 = int(slot0_data[0:64], 16)
                tick_hex = slot0_data[64:128]
                tick_raw = int(tick_hex, 16)

                # Конвертация в signed int24
                if tick_raw > 2**23:
                    tick = tick_raw - 2**24
                else:
                    tick = tick_raw

                # Парсим liquidity
                liquidity_hex = liquidity_result["result"][2:]
                liquidity = int(liquidity_hex, 16) if liquidity_hex else 0

                # Расчет цены
                price = (sqrt_price_x96 / (2**96)) ** 2

                return {
                    "sqrt_price_x96": sqrt_price_x96,
                    "tick": tick,
                    "liquidity": liquidity,
                    "price": price
                }
            except:
                pass

        return None

    def decode_swap_transaction(self, tx: Dict) -> Optional[Dict]:
        """Декодировать swap транзакцию"""
        if not tx.get("input") or len(tx["input"]) < 10:
            return None

        to_address = tx.get("to")
        if not to_address:
            return None

        to_address = to_address.lower()
        method_id = tx["input"][:10]

        # Проверяем что это Uniswap router
        if to_address not in [addr.lower() for addr in UNISWAP_ROUTERS.keys()]:
            return None

        # Проверяем что это swap метод
        if method_id not in SWAP_METHODS:
            return None

        # Парсим value (для ETH swaps)
        value_wei = int(tx.get("value", "0x0"), 16)
        value_eth = value_wei / 1e18

        return {
            "hash": tx.get("hash"),
            "from": tx.get("from"),
            "to": tx.get("to"),
            "router": UNISWAP_ROUTERS.get(tx["to"], "Unknown"),
            "method": SWAP_METHODS[method_id],
            "value_eth": value_eth,
            "value_usd": value_eth * self.eth_price_usd,
            "gas_price_gwei": int(tx.get("gasPrice", "0x0"), 16) / 1e9,
            "input_data": tx["input"]
        }

    def estimate_swap_size_and_pool(self, swap_tx: Dict) -> Optional[Tuple[float, str]]:
        """
        Оценить размер swap и определить пул

        Returns:
            (swap_size_usd, pool_address) или None
        """
        # Для ETH swaps
        if swap_tx["value_eth"] > 0:
            return (swap_tx["value_usd"], None)

        # TODO: Декодировать input data для определения точного размера
        # Для простоты, пока возвращаем None для ERC20 swaps
        # В production нужен полный ABI decoder

        return None

    def calculate_jit_opportunity(self, swap_size_usd: float, pool_data: Dict) -> Dict:
        """
        Рассчитать JIT возможность для swap

        Returns:
            Dict с деталями возможности
        """
        # Текущая активная ликвидность (в USD эквиваленте)
        # Упрощенная оценка: используем reserve_usd как proxy
        # В реальности нужно конвертировать liquidity через sqrtPrice
        active_liquidity_usd = pool_data["reserve_usd"] * 0.5  # ~50% активной

        # Ожидаемые комиссии от swap
        fee_decimal = pool_data["fee_decimal"]
        total_fees_usd = swap_size_usd * fee_decimal

        # Рассчитываем сколько ликвидности нужно добавить для TARGET_FEE_SHARE
        required_liquidity_usd = (active_liquidity_usd * TARGET_FEE_SHARE) / (1 - TARGET_FEE_SHARE)

        # Ваша доля комиссий
        total_liquidity = active_liquidity_usd + required_liquidity_usd
        your_share = required_liquidity_usd / total_liquidity

        # Ваши комиссии
        your_fees_usd = total_fees_usd * your_share

        # Costs
        flash_loan_fee_usd = required_liquidity_usd * (FLASH_LOAN_FEE_PERCENT / 100)
        gas_cost_usd = ESTIMATED_GAS_COST_USD

        # Net profit
        net_profit_usd = your_fees_usd - flash_loan_fee_usd - gas_cost_usd

        # ROI
        total_costs = flash_loan_fee_usd + gas_cost_usd
        roi_percent = (net_profit_usd / total_costs * 100) if total_costs > 0 else 0

        return {
            "profitable": net_profit_usd > MIN_NET_PROFIT_USD,
            "swap_size_usd": swap_size_usd,
            "active_liquidity_usd": active_liquidity_usd,
            "required_liquidity_usd": required_liquidity_usd,
            "total_fees_usd": total_fees_usd,
            "your_share_percent": your_share * 100,
            "your_fees_usd": your_fees_usd,
            "flash_loan_fee_usd": flash_loan_fee_usd,
            "gas_cost_usd": gas_cost_usd,
            "net_profit_usd": net_profit_usd,
            "roi_percent": roi_percent,
            "pool": pool_data
        }

    def find_best_pool_for_swap(self, swap_size_usd: float, token_pair: str = None) -> Optional[Dict]:
        """
        Найти лучший пул для данного swap размера

        Возвращает пул с наилучшим JIT potential
        """
        best_opportunity = None
        max_profit = 0

        for pool_address, pool_data in self.pools_data.items():
            # Если пул слишком маленький, пропускаем
            if pool_data["reserve_usd"] < swap_size_usd * 0.1:
                continue

            # Рассчитываем JIT opportunity
            jit_calc = self.calculate_jit_opportunity(swap_size_usd, pool_data)

            if jit_calc["profitable"] and jit_calc["net_profit_usd"] > max_profit:
                max_profit = jit_calc["net_profit_usd"]
                best_opportunity = jit_calc

        return best_opportunity

    def calculate_optimal_tick_range(self, current_tick: int, fee_percent: float) -> Tuple[int, int]:
        """
        Рассчитать оптимальный tick range для JIT позиции

        Returns:
            (lower_tick, upper_tick)
        """
        # Tick spacing зависит от fee tier
        if fee_percent <= 0.01:
            tick_spacing = 1
        elif fee_percent <= 0.05:
            tick_spacing = 10
        elif fee_percent <= 0.3:
            tick_spacing = 60
        else:
            tick_spacing = 200

        # Округляем current_tick до ближайшего tick spacing
        current_tick_rounded = round(current_tick / tick_spacing) * tick_spacing

        # Агрессивный range: ±1 tick spacing
        # Консервативный range: ±3 tick spacing
        range_multiplier = 2  # Средний вариант

        lower_tick = current_tick_rounded - (tick_spacing * range_multiplier)
        upper_tick = current_tick_rounded + (tick_spacing * range_multiplier)

        return (lower_tick, upper_tick)

    def print_jit_opportunity(self, opportunity: Dict, swap_tx: Dict):
        """Красиво вывести JIT возможность"""
        print("\n" + "="*120)
        print("🔥🔥🔥 JIT LIQUIDITY OPPORTUNITY DETECTED! 🔥🔥🔥")
        print("="*120)

        pool = opportunity["pool"]

        print(f"\n📊 SWAP DETAILS:")
        print(f"   Transaction: {swap_tx['hash']}")
        print(f"   Router:      {swap_tx['router']}")
        print(f"   Method:      {swap_tx['method']}")
        print(f"   Size:        ${opportunity['swap_size_usd']:,.2f}")
        print(f"   Gas Price:   {swap_tx['gas_price_gwei']:.2f} Gwei")

        print(f"\n🏊 POOL DETAILS:")
        print(f"   Pool:        {pool['name']}")
        print(f"   Address:     {pool['address']}")
        print(f"   DEX:         {pool['dex']}")
        print(f"   Fee Tier:    {pool['fee_percent']:.2f}%")
        print(f"   TVL:         ${pool['reserve_usd']:,.2f}")
        print(f"   24h Volume:  ${pool['volume_24h_usd']:,.2f}")
        print(f"   Current Tick: {pool['tick']}")

        # Рассчитываем optimal tick range
        lower_tick, upper_tick = self.calculate_optimal_tick_range(
            pool['tick'],
            pool['fee_percent']
        )

        print(f"\n📐 OPTIMAL POSITION:")
        print(f"   Current Tick:  {pool['tick']}")
        print(f"   Lower Tick:    {lower_tick}")
        print(f"   Upper Tick:    {upper_tick}")
        print(f"   Range Width:   {upper_tick - lower_tick} ticks")

        print(f"\n💰 LIQUIDITY CALCULATION:")
        print(f"   Active Liquidity:   ${opportunity['active_liquidity_usd']:,.2f}")
        print(f"   Required Add:       ${opportunity['required_liquidity_usd']:,.2f}")
        print(f"   Your Fee Share:     {opportunity['your_share_percent']:.1f}%")

        print(f"\n💵 PROFIT BREAKDOWN:")
        print(f"   Total Swap Fees:    ${opportunity['total_fees_usd']:,.2f}")
        print(f"   Your Fees:          ${opportunity['your_fees_usd']:,.2f}")
        print(f"   Flash Loan Fee:     ${opportunity['flash_loan_fee_usd']:,.2f}")
        print(f"   Gas Cost (est):     ${opportunity['gas_cost_usd']:.2f}")
        print(f"   ─────────────────────────────────")
        print(f"   🔥 NET PROFIT:      ${opportunity['net_profit_usd']:,.2f}")
        print(f"   📈 ROI:             {opportunity['roi_percent']:.1f}%")

        print(f"\n⚡ EXECUTION PLAN:")
        print(f"   Block N (Current):   Detect pending swap via flashblocks")
        print(f"   Block N+1:           1. Flash loan ${opportunity['required_liquidity_usd']:,.0f}")
        print(f"   Block N+1:           2. mint() position at ticks [{lower_tick}, {upper_tick}]")
        print(f"   Block N+2:           3. Victim's swap executes → collect fees")
        print(f"   Block N+3:           4. burn() position + repay flash loan")
        print(f"   Block N+3:           5. Profit ${opportunity['net_profit_usd']:,.2f}! 🚀")

        print(f"\n⏱️  TIMING:")
        print(f"   Total Duration:     ~6-8 seconds (3-4 blocks)")
        print(f"   Critical Window:    Must execute in next block!")

        print(f"\n⚠️  RISKS:")
        print(f"   • Victim tx может fail или измениться")
        print(f"   • Конкуренция с другими JIT ботами")
        print(f"   • Impermanent loss если не уберете вовремя")
        print(f"   • Gas price wars для priority")

        print(f"\n✅ RECOMMENDED ACTION:")
        print(f"   1. Verify pool liquidity via eth_call")
        print(f"   2. Prepare flash loan transaction")
        print(f"   3. Set gas price 1.5x higher than victim")
        print(f"   4. Execute atomically: loan → mint → wait → burn → repay")

        print("\n" + "="*120 + "\n")

    def monitor_jit_opportunities(self, duration_minutes: int = 60):
        """Мониторить JIT возможности через flashblocks"""
        print("="*120)
        print("🎯 JIT LIQUIDITY OPPORTUNITY DETECTOR")
        print("="*120)
        print(f"\n⚙️  Configuration:")
        print(f"   Node URL:              {NODE_URL}")
        print(f"   Min Swap Size:         ${MIN_SWAP_SIZE_USD:,}")
        print(f"   Min Net Profit:        ${MIN_NET_PROFIT_USD}")
        print(f"   Target Fee Share:      {TARGET_FEE_SHARE*100}%")
        print(f"   Flash Loan Fee:        {FLASH_LOAN_FEE_PERCENT}%")
        print(f"   Estimated Gas Cost:    ${ESTIMATED_GAS_COST_USD}")
        print(f"   Duration:              {duration_minutes} minutes")

        print(f"\n📊 Loading pools data...")
        self.load_pools_data()

        if not self.pools_data:
            print("❌ No pools loaded. Exiting.")
            return

        print(f"\n{'='*120}")
        print(f"👀 MONITORING FLASHBLOCKS FOR JIT OPPORTUNITIES...")
        print(f"{'='*120}\n")

        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        iteration = 0

        try:
            while time.time() < end_time:
                iteration += 1
                timestamp = datetime.now().strftime("%H:%M:%S")

                # Получаем pending блок
                pending_block = self.get_pending_block()

                if pending_block and "transactions" in pending_block:
                    tx_count = len(pending_block["transactions"])

                    # Анализируем каждую транзакцию
                    for tx in pending_block["transactions"]:
                        if not isinstance(tx, dict):
                            continue

                        # Декодируем swap
                        swap_tx = self.decode_swap_transaction(tx)

                        if swap_tx:
                            # Оцениваем размер swap
                            if swap_tx["value_usd"] >= MIN_SWAP_SIZE_USD:
                                # Ищем лучший пул для JIT
                                opportunity = self.find_best_pool_for_swap(swap_tx["value_usd"])

                                if opportunity and opportunity["profitable"]:
                                    self.print_jit_opportunity(opportunity, swap_tx)
                                    self.opportunities_found += 1
                                    self.total_potential_profit += opportunity["net_profit_usd"]

                    print(f"[{timestamp}] Block checked: {tx_count} txs | Opportunities: {self.opportunities_found}", end='\r')
                else:
                    print(f"[{timestamp}] Monitoring... | Opportunities found: {self.opportunities_found}", end='\r')

                time.sleep(1)  # Проверяем каждую секунду

        except KeyboardInterrupt:
            print(f"\n\n⏹️  Monitoring stopped by user")

        # Статистика
        elapsed_minutes = (time.time() - start_time) / 60
        print(f"\n\n{'='*120}")
        print(f"📊 MONITORING STATISTICS")
        print(f"{'='*120}")
        print(f"Duration:                {elapsed_minutes:.1f} minutes")
        print(f"Iterations:              {iteration}")
        print(f"JIT Opportunities Found: {self.opportunities_found}")
        if self.opportunities_found > 0:
            print(f"Total Potential Profit:  ${self.total_potential_profit:,.2f}")
            print(f"Average Profit/Opp:      ${self.total_potential_profit/self.opportunities_found:,.2f}")
            print(f"Opportunities/Hour:      {self.opportunities_found / (elapsed_minutes/60):.1f}")
            print(f"\n💡 Estimated Daily Profit: ${(self.total_potential_profit / elapsed_minutes) * 60 * 24:,.2f}")
        print(f"{'='*120}\n")


def main():
    """Main function"""
    import sys

    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 60

    print("""
    ╔════════════════════════════════════════════════════════════════════════╗
    ║                                                                        ║
    ║              JIT LIQUIDITY OPPORTUNITY DETECTOR v1.0                   ║
    ║                                                                        ║
    ║  Monitors flashblocks for profitable Just-In-Time liquidity            ║
    ║  opportunities on Uniswap V3 pools.                                    ║
    ║                                                                        ║
    ║  Strategy: Add liquidity 1 block before large swap,                   ║
    ║           capture majority of fees, remove immediately after.          ║
    ║                                                                        ║
    ╚════════════════════════════════════════════════════════════════════════╝
    """)

    detector = JITOpportunityDetector()
    detector.monitor_jit_opportunities(duration_minutes=duration)


if __name__ == "__main__":
    main()
