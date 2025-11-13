# Flashloan Quick Reference для Base

## 🚀 Лучший выбор: Compound V3 (0% комиссия!)

### Адреса контрактов:
```rust
// Compound V3 Comet Markets
pub const COMET_USDC: &str = "0xb125E6687d4313864e53df431d5425969c15Eb2F";
pub const COMET_WETH: &str = "0x46e6b214b524310239732D51387075E0e70970bf";

// AAVE V3 (backup, 0.09% fee)
pub const AAVE_POOL: &str = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5";

// Tokens
pub const USDC: &str = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
pub const WETH: &str = "0x4200000000000000000000000000000000000006";

// DEX Routers
pub const UNISWAP_V3: &str = "0x2626664c2603336E57B271c5C0b26F421741e481";
pub const AERODROME: &str = "0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43";
```

## 💰 Комиссии

| Протокол | Комиссия | На $100K |
|----------|----------|----------|
| **Compound V3** | **0%** | **$0** ⭐ |
| Morpho | ~0% | ~$0 |
| Euler V2 | 0.01% | $10 |
| AAVE V3 | 0.09% | $90 |

## ⚡ Минимальный код

### Solidity (Compound V3):
```solidity
IComet(COMET_USDC).flashLoan(
    address(this),  // borrower
    address(this),  // receiver
    USDC,           // asset
    amount,         // amount
    data            // callback data
);
```

### Rust (Executor):
```rust
let tx = contract
    .execute_arbitrage(
        usdc_address,
        U256::from(10_000e6),  // $10K
        0,  // Uniswap
        1,  // Aerodrome
        U256::from(50e6),  // $50 min profit
    )
    .send()
    .await?;
```

## 🎯 Калькулятор прибыльности

```
Profit = (Price_DEX_A - Price_DEX_B) * Amount - Costs

Costs:
  - Flashloan fee: 0% (Compound) ✅
  - DEX swap fees: 0.3% + 0.3% = 0.6%
  - Gas: ~$3-5

Minimum profitable amount: $5,000
Recommended amount: $10,000+
```

## 📊 Примеры расчетов

### Пример 1: $10,000 USDC арбитраж
```
Buy WETH on Uniswap:  $10,000 → 2.803 WETH (0.3% fee)
Sell WETH on Aerodrome: 2.803 WETH → $10,150 (0.3% fee)

Profit = $10,150 - $10,000 - $3 (gas) - $0 (flashloan) = $147
ROI = 1.47%
```

### Пример 2: $50,000 USDC арбитраж
```
Price difference: 0.5%

Revenue: $50,000 * 0.005 = $250
DEX fees: $50,000 * 0.006 = $300
Gas: $3
Flashloan: $0 (Compound!)

Profit = $250 - $300 - $3 = -$53 ❌ (УБЫТОК)

Нужна разница минимум 0.7% для прибыли!
```

## ⚙️ Rust Config

```rust
// config.rs
pub struct FlashloanConfig {
    pub comet_usdc: Address,
    pub comet_weth: Address,
    pub min_profit_usd: f64,
    pub max_amount_usd: f64,
    pub gas_limit: u64,
}

impl Default for FlashloanConfig {
    fn default() -> Self {
        Self {
            comet_usdc: "0xb125E6687d4313864e53df431d5425969c15Eb2F".parse().unwrap(),
            comet_weth: "0x46e6b214b524310239732D51387075E0e70970bf".parse().unwrap(),
            min_profit_usd: 50.0,
            max_amount_usd: 100_000.0,
            gas_limit: 2_000_000,
        }
    }
}
```

## 🔥 Hot Tips

1. **Всегда используйте Compound V3** для USDC/WETH (экономия $90 на каждые $100K!)
2. **Минимальная сумма $5K** для покрытия газа + DEX fees
3. **Base fee ~0.5 gwei** - очень дешевый газ
4. **Не нужны priority fees** для арбитража
5. **Ваша reth нода = 45ms latency** - огромное преимущество!

## ❌ Частые ошибки

```solidity
// ❌ НЕПРАВИЛЬНО
IERC20(asset).transfer(msg.sender, amount);  // Забыли fee!

// ✅ ПРАВИЛЬНО
IERC20(asset).transfer(msg.sender, amount + fee);

// ❌ НЕПРАВИЛЬНО (для Compound V3)
uint256 fee = (amount * 9) / 10000;  // Compound fee = 0!

// ✅ ПРАВИЛЬНО (для Compound V3)
uint256 fee = 0;  // No fee on Compound V3!
```

## 📞 Support

- Compound Docs: https://docs.compound.finance
- Base Explorer: https://basescan.org
- Your RPC: http://80.209.241.37:8545/
