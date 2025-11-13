# Flashloan Integration Guide для Cross-DEX Arbitrage на Base

## 🎯 Рекомендуемые Lending Протоколы

Основываясь на анализе всех 78 lending протоколов на Base:

### Топ-3 для Flashloan (по приоритету):

| Протокол | Комиссия | TVL на Base | Активы | Приоритет |
|----------|----------|-------------|---------|-----------|
| **Compound V3** | **0%** 🏆 | $50.8M | USDC, WETH | **#1 ЛУЧШИЙ** |
| **Morpho V1** | ~0% | $2.0B | Multiple | #2 |
| **AAVE V3** | 0.09% | $988M | Multiple | #3 |
| Euler V2 | 0.01% | $9.2M | Multiple | #4 |
| Radiant V2 | 0.09% | $2.5M | Multiple | #5 |

---

## 📍 Адреса Контрактов на Base

### 1. Compound V3 (РЕКОМЕНДУЕТСЯ - 0% комиссия!)

```solidity
// USDC Market
address constant COMET_USDC = 0xb125E6687d4313864e53df431d5425969c15Eb2F;

// WETH Market
address constant COMET_WETH = 0x46e6b214b524310239732D51387075E0e70970bf;

// Tokens
address constant USDC = 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913;
address constant WETH = 0x4200000000000000000000000000000000000006;
```

### 2. AAVE V3

```solidity
address constant AAVE_POOL = 0xA238Dd80C259a72e81d7e4664a9801593F98d1c5;
address constant AAVE_POOL_DATA_PROVIDER = 0x2d8A3C5677189723C4cB8873CfC9C8976FDF38Ac;
address constant AAVE_ORACLE = 0x2Cc0Fc26eD4563A5ce5e8bdcfe1A2878676Ae156;

// Комиссия: 0.09% (9 basis points)
uint256 constant AAVE_FLASHLOAN_PREMIUM = 9; // 0.09%
```

---

## 💻 Solidity Contract Examples

### Вариант 1: Compound V3 Flashloan (ЛУЧШИЙ - 0% комиссия)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

interface IComet {
    function flashLoan(
        address borrower,
        address receiver,
        address asset,
        uint256 amount,
        bytes calldata data
    ) external;
}

interface IUniswapV3Router {
    struct ExactInputSingleParams {
        address tokenIn;
        address tokenOut;
        uint24 fee;
        address recipient;
        uint256 deadline;
        uint256 amountIn;
        uint256 amountOutMinimum;
        uint160 sqrtPriceLimitX96;
    }

    function exactInputSingle(ExactInputSingleParams calldata params)
        external payable returns (uint256 amountOut);
}

contract CompoundFlashloanArbitrage {
    // Compound V3 Comet
    address public constant COMET_USDC = 0xb125E6687d4313864e53df431d5425969c15Eb2F;
    address public constant COMET_WETH = 0x46e6b214b524310239732D51387075E0e70970bf;

    // Tokens
    address public constant USDC = 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913;
    address public constant WETH = 0x4200000000000000000000000000000000000006;

    // DEX Routers
    address public constant UNISWAP_V3_ROUTER = 0x2626664c2603336E57B271c5C0b26F421741e481;
    address public constant AERODROME_ROUTER = 0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43;

    address public owner;

    constructor() {
        owner = msg.sender;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }

    /**
     * @dev Execute arbitrage with Compound V3 flashloan (0% fee!)
     * @param token Token to borrow (USDC or WETH)
     * @param amount Amount to borrow
     * @param buyDex DEX to buy from (0=Uniswap, 1=Aerodrome)
     * @param sellDex DEX to sell to
     * @param minProfit Minimum profit required
     */
    function executeArbitrage(
        address token,
        uint256 amount,
        uint8 buyDex,
        uint8 sellDex,
        uint256 minProfit
    ) external onlyOwner {
        // Выбираем правильный Comet контракт
        address comet = token == USDC ? COMET_USDC : COMET_WETH;

        // Encode arbitrage parameters
        bytes memory data = abi.encode(buyDex, sellDex, minProfit);

        // Request flashloan (0% fee!)
        IComet(comet).flashLoan(
            address(this),  // borrower
            address(this),  // receiver
            token,          // asset
            amount,         // amount
            data            // callback data
        );
    }

    /**
     * @dev Callback function called by Comet after flashloan
     */
    function onFlashLoan(
        address initiator,
        address asset,
        uint256 amount,
        uint256 fee,  // Will be 0 for Compound V3!
        bytes calldata data
    ) external returns (bytes32) {
        require(
            msg.sender == COMET_USDC || msg.sender == COMET_WETH,
            "Invalid caller"
        );
        require(initiator == address(this), "Invalid initiator");

        // Decode parameters
        (uint8 buyDex, uint8 sellDex, uint256 minProfit) = abi.decode(
            data,
            (uint8, uint8, uint256)
        );

        // Execute arbitrage
        uint256 profit = _executeArbitrageLogic(asset, amount, buyDex, sellDex);

        require(profit >= minProfit, "Insufficient profit");

        // Repay flashloan (amount + fee, but fee = 0!)
        uint256 repayAmount = amount + fee;
        IERC20(asset).transfer(msg.sender, repayAmount);

        // Profit stays in contract
        emit ArbitrageExecuted(asset, amount, profit);

        return keccak256("ERC3156FlashBorrower.onFlashLoan");
    }

    /**
     * @dev Execute the actual arbitrage logic
     */
    function _executeArbitrageLogic(
        address token,
        uint256 amount,
        uint8 buyDex,
        uint8 sellDex
    ) internal returns (uint256 profit) {
        // Example: USDC -> WETH -> USDC arbitrage

        // Step 1: Swap on first DEX (buy WETH with USDC)
        IERC20(token).approve(
            buyDex == 0 ? UNISWAP_V3_ROUTER : AERODROME_ROUTER,
            amount
        );

        uint256 receivedWETH = _swapOnDex(
            buyDex,
            token,
            WETH,
            amount,
            0  // Will set proper slippage in production
        );

        // Step 2: Swap back on second DEX (sell WETH for USDC)
        IERC20(WETH).approve(
            sellDex == 0 ? UNISWAP_V3_ROUTER : AERODROME_ROUTER,
            receivedWETH
        );

        uint256 receivedUSDC = _swapOnDex(
            sellDex,
            WETH,
            token,
            receivedWETH,
            amount  // Must get at least original amount back
        );

        // Calculate profit
        profit = receivedUSDC > amount ? receivedUSDC - amount : 0;

        return profit;
    }

    /**
     * @dev Execute swap on specified DEX
     */
    function _swapOnDex(
        uint8 dex,
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 minAmountOut
    ) internal returns (uint256 amountOut) {
        if (dex == 0) {
            // Uniswap V3
            IUniswapV3Router.ExactInputSingleParams memory params =
                IUniswapV3Router.ExactInputSingleParams({
                    tokenIn: tokenIn,
                    tokenOut: tokenOut,
                    fee: 3000,  // 0.3%
                    recipient: address(this),
                    deadline: block.timestamp,
                    amountIn: amountIn,
                    amountOutMinimum: minAmountOut,
                    sqrtPriceLimitX96: 0
                });

            return IUniswapV3Router(UNISWAP_V3_ROUTER).exactInputSingle(params);
        } else {
            // Aerodrome or other DEX
            // Implementation depends on DEX interface
            revert("DEX not implemented");
        }
    }

    /**
     * @dev Withdraw profits
     */
    function withdrawProfit(address token) external onlyOwner {
        uint256 balance = IERC20(token).balanceOf(address(this));
        require(balance > 0, "No profit");
        IERC20(token).transfer(owner, balance);
    }

    event ArbitrageExecuted(
        address indexed token,
        uint256 amount,
        uint256 profit
    );
}
```

### Вариант 2: AAVE V3 Flashloan (Multi-asset support)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

interface IPoolV3 {
    function flashLoan(
        address receiverAddress,
        address[] calldata assets,
        uint256[] calldata amounts,
        uint256[] calldata modes,
        address onBehalfOf,
        bytes calldata params,
        uint16 referralCode
    ) external;
}

contract AaveFlashloanArbitrage {
    address public constant AAVE_POOL = 0xA238Dd80C259a72e81d7e4664a9801593F98d1c5;

    // Fee: 0.09% (9 basis points)
    uint256 public constant FLASHLOAN_PREMIUM_BPS = 9;

    address public owner;

    constructor() {
        owner = msg.sender;
    }

    /**
     * @dev Execute multi-asset flashloan arbitrage
     */
    function executeMultiAssetArbitrage(
        address[] calldata assets,
        uint256[] calldata amounts,
        bytes calldata params
    ) external {
        require(msg.sender == owner, "Not owner");

        // modes = 0 for flashloan (no debt)
        uint256[] memory modes = new uint256[](assets.length);

        IPoolV3(AAVE_POOL).flashLoan(
            address(this),  // receiver
            assets,         // assets to borrow
            amounts,        // amounts to borrow
            modes,          // 0 = no debt, pay back in same tx
            address(this),  // onBehalfOf
            params,         // custom params
            0               // referral code
        );
    }

    /**
     * @dev AAVE V3 flashloan callback
     */
    function executeOperation(
        address[] calldata assets,
        uint256[] calldata amounts,
        uint256[] calldata premiums,  // 0.09% fee
        address initiator,
        bytes calldata params
    ) external returns (bool) {
        require(msg.sender == AAVE_POOL, "Invalid caller");
        require(initiator == address(this), "Invalid initiator");

        // Execute arbitrage logic here
        // ...

        // Approve repayment (amount + premium)
        for (uint i = 0; i < assets.length; i++) {
            uint256 amountOwing = amounts[i] + premiums[i];
            IERC20(assets[i]).approve(AAVE_POOL, amountOwing);
        }

        return true;
    }
}
```

---

## 🦀 Rust Executor Code

### executor.rs - Compound V3 Integration

```rust
use ethers::prelude::*;
use ethers::contract::abigen;
use std::sync::Arc;

// Generate contract bindings
abigen!(
    CompoundFlashloanArbitrage,
    r#"[
        function executeArbitrage(address token, uint256 amount, uint8 buyDex, uint8 sellDex, uint256 minProfit) external
        function withdrawProfit(address token) external
        event ArbitrageExecuted(address indexed token, uint256 amount, uint256 profit)
    ]"#
);

abigen!(
    IComet,
    r#"[
        function balanceOf(address account) external view returns (uint256)
        function borrowBalanceOf(address account) external view returns (uint256)
    ]"#
);

abigen!(
    IERC20,
    r#"[
        function balanceOf(address account) external view returns (uint256)
        function approve(address spender, uint256 amount) external returns (bool)
    ]"#
);

// Contract addresses on Base
pub const COMET_USDC: &str = "0xb125E6687d4313864e53df431d5425969c15Eb2F";
pub const COMET_WETH: &str = "0x46e6b214b524310239732D51387075E0e70970bf";
pub const USDC: &str = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913";
pub const WETH: &str = "0x4200000000000000000000000000000000000006";

pub struct FlashloanExecutor {
    contract: CompoundFlashloanArbitrage<SignerMiddleware<Provider<Http>, Wallet<SigningKey>>>,
    usdc: IERC20<SignerMiddleware<Provider<Http>, Wallet<SigningKey>>>,
    weth: IERC20<SignerMiddleware<Provider<Http>, Wallet<SigningKey>>>,
}

impl FlashloanExecutor {
    pub async fn new(
        rpc_url: &str,
        contract_address: Address,
        private_key: &str,
    ) -> Result<Self, Box<dyn std::error::Error>> {
        // Setup provider
        let provider = Provider::<Http>::try_from(rpc_url)?;

        // Setup wallet
        let wallet: Wallet<SigningKey> = private_key.parse()?;
        let chain_id = provider.get_chainid().await?;
        let wallet = wallet.with_chain_id(chain_id.as_u64());

        // Create middleware
        let client = Arc::new(SignerMiddleware::new(provider, wallet));

        // Create contract instances
        let contract = CompoundFlashloanArbitrage::new(contract_address, client.clone());
        let usdc = IERC20::new(USDC.parse()?, client.clone());
        let weth = IERC20::new(WETH.parse()?, client.clone());

        Ok(Self {
            contract,
            usdc,
            weth,
        })
    }

    /// Execute arbitrage with Compound V3 flashloan (0% fee!)
    pub async fn execute_arbitrage(
        &self,
        token: Address,
        amount: U256,
        buy_dex: u8,  // 0 = Uniswap, 1 = Aerodrome
        sell_dex: u8,
        min_profit: U256,
    ) -> Result<TransactionReceipt, Box<dyn std::error::Error>> {
        println!("🚀 Executing arbitrage:");
        println!("  Token: {:?}", token);
        println!("  Amount: {}", amount);
        println!("  Buy DEX: {}", buy_dex);
        println!("  Sell DEX: {}", sell_dex);
        println!("  Min Profit: {}", min_profit);

        // Build transaction
        let tx = self.contract
            .execute_arbitrage(token, amount, buy_dex, sell_dex, min_profit)
            .gas(2_000_000)  // Set appropriate gas limit
            .gas_price(1_000_000_000);  // 1 gwei base fee on Base

        // Send transaction
        let pending_tx = tx.send().await?;
        println!("  📝 Transaction sent: {:?}", pending_tx.tx_hash());

        // Wait for confirmation
        let receipt = pending_tx
            .await?
            .ok_or("Transaction failed")?;

        println!("  ✅ Transaction confirmed in block: {}", receipt.block_number.unwrap());

        // Parse events
        for log in &receipt.logs {
            if let Ok(event) = self.contract.decode_event::<ArbitrageExecutedFilter>(
                "ArbitrageExecuted",
                log.topics.clone(),
                log.data.clone(),
            ) {
                println!("  💰 Profit: {} ({})",
                    event.profit,
                    self.format_token_amount(event.profit, 6)  // USDC has 6 decimals
                );
            }
        }

        Ok(receipt)
    }

    /// Calculate expected profit before execution
    pub async fn simulate_arbitrage(
        &self,
        token: Address,
        amount: U256,
        buy_dex: u8,
        sell_dex: u8,
    ) -> Result<U256, Box<dyn std::error::Error>> {
        // Call contract as read-only to simulate
        let tx = self.contract
            .execute_arbitrage(token, amount, buy_dex, sell_dex, U256::zero())
            .call()
            .await;

        match tx {
            Ok(_) => {
                // In production, would parse logs from call
                println!("  ✅ Simulation successful");
                Ok(U256::from(1000))  // Placeholder
            }
            Err(e) => {
                println!("  ❌ Simulation failed: {}", e);
                Err(Box::new(e))
            }
        }
    }

    /// Withdraw accumulated profits
    pub async fn withdraw_profit(
        &self,
        token: Address,
    ) -> Result<TransactionReceipt, Box<dyn std::error::Error>> {
        println!("💰 Withdrawing profit for token: {:?}", token);

        let tx = self.contract
            .withdraw_profit(token)
            .gas(100_000);

        let pending_tx = tx.send().await?;
        let receipt = pending_tx.await?.ok_or("Transaction failed")?;

        println!("  ✅ Profit withdrawn!");

        Ok(receipt)
    }

    /// Check contract balance
    pub async fn check_balance(&self) -> Result<(U256, U256), Box<dyn std::error::Error>> {
        let usdc_balance = self.usdc.balance_of(self.contract.address()).call().await?;
        let weth_balance = self.weth.balance_of(self.contract.address()).call().await?;

        println!("📊 Contract balances:");
        println!("  USDC: {}", self.format_token_amount(usdc_balance, 6));
        println!("  WETH: {}", self.format_token_amount(weth_balance, 18));

        Ok((usdc_balance, weth_balance))
    }

    /// Helper: Format token amount with decimals
    fn format_token_amount(&self, amount: U256, decimals: u32) -> String {
        let divisor = U256::from(10).pow(U256::from(decimals));
        let whole = amount / divisor;
        let fraction = amount % divisor;

        format!("{}.{:06}", whole, fraction)
    }
}

/// Example usage in main.rs
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Configuration
    let rpc_url = "http://80.209.241.37:8545/";  // Your custom reth node
    let contract_address: Address = "0x...".parse()?;  // Your deployed contract
    let private_key = std::env::var("PRIVATE_KEY")?;

    // Initialize executor
    let executor = FlashloanExecutor::new(rpc_url, contract_address, &private_key).await?;

    // Check balances
    executor.check_balance().await?;

    // Execute arbitrage
    let token = USDC.parse()?;
    let amount = U256::from(10_000) * U256::from(10).pow(U256::from(6));  // 10,000 USDC
    let min_profit = U256::from(50) * U256::from(10).pow(U256::from(6));  // $50 minimum

    // Simulate first
    let simulated_profit = executor.simulate_arbitrage(
        token,
        amount,
        0,  // Buy on Uniswap
        1,  // Sell on Aerodrome
    ).await?;

    if simulated_profit >= min_profit {
        // Execute real transaction
        let receipt = executor.execute_arbitrage(
            token,
            amount,
            0,  // Buy on Uniswap
            1,  // Sell on Aerodrome
            min_profit,
        ).await?;

        println!("✅ Arbitrage executed: {:?}", receipt.transaction_hash);
    } else {
        println!("⚠️  Profit too low, skipping");
    }

    Ok(())
}
```

---

## 💰 Cost Comparison

### На сумму $100,000 flashloan:

| Протокол | Комиссия | Стоимость | Экономия vs AAVE |
|----------|----------|-----------|------------------|
| **Compound V3** | **0%** | **$0** | **+$90** ✅ |
| Morpho | ~0% | ~$0 | +$90 |
| Euler V2 | 0.01% | $10 | +$80 |
| AAVE V3 | 0.09% | $90 | baseline |

### Минимальная прибыльная сумма:

```
Для USDC/WETH арбитража:
- Газ: ~$2-5
- DEX fees: 0.3% + 0.3% = 0.6%
- Flashloan fee (Compound): 0%

Минимум для прибыли:
Amount * 0.006 > Gas + Flashloan_fee
$10,000 * 0.006 = $60 > $5 ✅

Рекомендуемый минимум: $5,000-10,000
```

---

## 🎯 Рекомендации

### 1. **Используйте Compound V3 как основной источник flashloan**
   - ✅ 0% комиссия
   - ✅ Доступны USDC и WETH (самые ликвидные активы)
   - ✅ Простой интерфейс
   - ✅ Проверенный протокол ($50M TVL на Base)

### 2. **AAVE V3 как backup**
   - Используйте если нужны другие активы
   - Или для multi-asset arbitrage
   - Комиссия 0.09% все еще приемлема

### 3. **Оптимизация газа**
   - Используйте `estimateGas()` перед отправкой
   - Base fee обычно 0.3-0.6 gwei
   - Не нужны priority fees для арбитража

### 4. **Безопасность**
   - Всегда проверяйте `msg.sender` в callback
   - Используйте `nonReentrant` modifier
   - Проверяйте минимальную прибыль перед execution
   - Храните private keys в `.env` файле

---

## 📦 Deployment Checklist

- [ ] Deploy контракт на Base
- [ ] Verify на BaseScan
- [ ] Approve токенов для DEX routers
- [ ] Протестировать с малыми суммами
- [ ] Настроить мониторинг прибыльности
- [ ] Подготовить Rust executor
- [ ] Настроить автоматическое выполнение
- [ ] Подключить к вашей reth ноде (45ms latency!)

---

## 🔗 Полезные ссылки

- Compound V3 Docs: https://docs.compound.finance
- AAVE V3 Docs: https://docs.aave.com/developers
- Base Explorer: https://basescan.org
- Uniswap V3 Router: https://docs.uniswap.org
