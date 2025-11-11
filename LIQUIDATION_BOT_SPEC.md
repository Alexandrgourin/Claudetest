# Техническое задание: AAVE Liquidation Bot на Base

**Версия:** 1.0
**Дата:** 10 ноября 2025
**Язык:** Rust
**Целевая сеть:** Base (L2)

---

## 📋 Содержание

1. [Executive Summary](#executive-summary)
2. [Результаты исследования рынка](#результаты-исследования-рынка)
3. [Архитектура системы](#архитектура-системы)
4. [Технические требования](#технические-требования)
5. [Детальные спецификации компонентов](#детальные-спецификации-компонентов)
6. [Стратегия мониторинга](#стратегия-мониторинга)
7. [Алгоритмы и логика](#алгоритмы-и-логика)
8. [Метрики производительности](#метрики-производительности)
9. [Безопасность и управление рисками](#безопасность-и-управление-рисками)
10. [Этапы разработки](#этапы-разработки)
11. [Appendix: Данные конкурентов](#appendix-данные-конкурентов)

---

## Executive Summary

### Цель проекта
Разработать высокопроизводительный бот для ликвидации позиций в AAVE v3 на Base network, способный конкурировать с топовыми ботами и захватывать 20-30% рынка.

### Ключевые метрики рынка
- **Размер рынка:** $244K/месяц (топ-3 бота вместе)
- **Частота возможностей:** ~58 крупных ликвидаций/неделю (>$1K долг)
- **Средняя прибыль:** $525 на ликвидацию (крупные позиции)
- **Максимальная прибыль:** $511K (рекорд Bot #2)

### Целевые показатели
- **Месячный доход:** $40-80K (20-30% рынка)
- **Latency:** 150-200ms (от детекции до отправки tx)
- **Позиция в блоке:** топ 10-15% (#180-300 из ~1700)
- **Success rate:** >80% успешных ликвидаций при детекции

### Конкурентное преимущество
- ✅ **Reth node с flashblocks:** 78ms latency (vs 333ms Alchemy)
- ✅ **Pending block monitoring:** детекция в mempool, не в блоке
- ✅ **Rust производительность:** sub-millisecond обработка
- ✅ **Прямое преимущество:** +250ms перед ботами на Alchemy

---

## Результаты исследования рынка

### Анализ конкурентов

#### Bot #1: 0xc88eab547fde493992b2456589f2796960cc4561
**Профиль:**
- Создан: 10.11.2024 (365 дней работы)
- Контракт: 291 bytes (очень компактный)
- Тип: Селективный (только крупные позиции)

**Производительность:**
- Ликвидаций: 76 за год (0.21/день, ~6/месяц)
- Прибыль: $618,391 за год ($50,828/месяц)
- Средняя прибыль: $8,137 на ликвидацию
- Лучшая ликвидация: $123,586
- Средний долг: $29,154 (только крупные позиции)

**Скорость:**
- 100% ликвидаций в том же блоке (0 задержка)
- Средняя позиция: #620 (~35% блока)
- Gas: 0.28 gwei avg, 0.34 gwei max (базовый fee)
- Управление: 41 уникальный caller (distributed keeper network)

**Стратегия:**
- Фокус на крупные позиции (>$20K долг)
- Селективный подход (10% рынка)
- Не использует priority fees
- Полагается на скорость детекции

---

#### Bot #2: 0xd12810b19b596347a3afac206d3ca65d08594b3f ⭐ КОРОЛЬ РЫНКА
**Профиль:**
- Создан: 30.05.2024 (529 дней работы)
- Контракт: 170 bytes (экстремально компактный!)
- Тип: Агрессивный (берет все подряд)

**Производительность:**
- Ликвидаций: 567 за 18 месяцев (1.07/день, ~32/месяц)
- Прибыль: $2,981,097 за 18 месяцев ($169,060/месяц) 🔥
- Средняя прибыль: $5,258 на ликвидацию
- Лучшая ликвидация: $511,766 (абсолютный рекорд!)
- Средний долг: $11,734 (средние позиции)

**Скорость:**
- 100% ликвидаций в том же блоке (0 задержка)
- Средняя позиция: #1308 (~59% блока) - медленнее других!
- Gas: 0.30 gwei avg, 0.44 gwei max (базовый fee)

**Стратегия:**
- Берет ВСЕ подряд (агрессивная стратегия)
- Доминирует на рынке (~40% доли)
- Частые ликвидации каждый день
- Простая логика, высокая эффективность

---

#### Bot #3: 0x0a5a3e02c2aae465a016531a7aa6b4be4b21d3f9
**Профиль:**
- Создан: 14.10.2025 (27 дней работы)
- Контракт: 21,338 bytes (сложная логика!)
- Тип: Ультра-селективный (только гиганты)

**Производительность:**
- Ликвидаций: 2 за месяц (0.07/день)
- Прибыль: $21,824 за месяц ($24,249/месяц projected)
- Средняя прибыль: $10,912 на ликвидацию (самая высокая!)
- Лучшая ликвидация: $13,128
- Средний долг: $80,260 (только огромные позиции!)

**Скорость:**
- 100% ликвидаций в том же блоке (0 задержка)
- Средняя позиция: #314 (~18% блока) - САМЫЙ БЫСТРЫЙ! ⚡
- Gas: 0.40 gwei avg, 0.60 gwei max (базовый fee)

**Стратегия:**
- Только массивные позиции (>$50K долг)
- Высочайшая эффективность
- Новый бот, но уже эффективный
- Сложная логика в контракте (21KB)

---

### Ключевые выводы из анализа конкурентов

**1. Скорость - критична:**
- Все 3 бота делают 100% ликвидаций в том же блоке
- Bot #3 самый быстрый (позиция #314)
- Никто не использует priority fees
- Скорость детекции = единственный фактор успеха

**2. Стратегии различаются:**
- Селективная (Bot #1): 10% рынка, $50K/месяц
- Агрессивная (Bot #2): 40% рынка, $169K/месяц ⭐
- Ультра-селективная (Bot #3): 5% рынка, $24K/месяц

**3. Технология:**
- Используют flashblocks/mempool monitoring
- Реагируют на pending oracle updates
- Симулируют или извлекают цены из pending tx
- Отправляют tx немедленно (0-400ms latency)

**4. Наша возможность:**
- Bot #2 доминирует но МЕДЛЕННЫЙ (позиция #1308)
- Bot #3 быстрый но селективный (только 2 лик/месяц)
- Bot #1 умеренный (позиция #620)
- **С нашим reth node мы можем быть позиция #180-300!**

---

## Архитектура системы

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     LIQUIDATION BOT                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐        ┌──────────────┐                 │
│  │   RPC Node   │◄──────►│  Monitoring  │                 │
│  │   Manager    │        │   Service    │                 │
│  │              │        │              │                 │
│  │  - Reth      │        │ - Pending    │                 │
│  │  - Alchemy   │        │   Blocks     │                 │
│  │  - Failover  │        │ - Oracle     │                 │
│  └──────┬───────┘        │   Updates    │                 │
│         │                └──────┬───────┘                 │
│         │                       │                          │
│         │                       ▼                          │
│         │              ┌─────────────────┐                │
│         │              │  Position       │                │
│         └─────────────►│  Tracker        │                │
│                        │                 │                │
│                        │ - Health        │                │
│                        │   Factors       │                │
│                        │ - Borrowers     │                │
│                        │ - Risk Levels   │                │
│                        └────────┬────────┘                │
│                                 │                          │
│                                 ▼                          │
│                        ┌─────────────────┐                │
│                        │  Liquidation    │                │
│                        │  Engine         │                │
│                        │                 │                │
│                        │ - Profitability │                │
│                        │ - Simulation    │                │
│                        │ - Decision      │                │
│                        └────────┬────────┘                │
│                                 │                          │
│                                 ▼                          │
│                        ┌─────────────────┐                │
│                        │  Transaction    │                │
│                        │  Manager        │                │
│                        │                 │                │
│                        │ - Building      │                │
│                        │ - Signing       │                │
│                        │ - Sending       │                │
│                        └────────┬────────┘                │
│                                 │                          │
│                                 ▼                          │
│                        ┌─────────────────┐                │
│                        │  Metrics &      │                │
│                        │  Monitoring     │                │
│                        │                 │                │
│                        │ - Performance   │                │
│                        │ - Profitability │                │
│                        │ - Alerts        │                │
│                        └─────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

### Модульная структура

```
liquidation-bot/
├── src/
│   ├── main.rs                    # Entry point
│   ├── config/
│   │   ├── mod.rs
│   │   ├── chain.rs               # Chain configs
│   │   └── bot.rs                 # Bot settings
│   ├── rpc/
│   │   ├── mod.rs
│   │   ├── manager.rs             # RPC connection pool
│   │   ├── flashblocks.rs         # Pending block monitoring
│   │   └── fallback.rs            # Failover logic
│   ├── monitoring/
│   │   ├── mod.rs
│   │   ├── pending_scanner.rs     # Parse pending transactions
│   │   ├── oracle_detector.rs     # Detect oracle updates
│   │   └── price_simulator.rs     # Simulate price changes
│   ├── positions/
│   │   ├── mod.rs
│   │   ├── tracker.rs             # Track borrower positions
│   │   ├── health_factor.rs       # HF calculation
│   │   └── database.rs            # Position cache
│   ├── liquidation/
│   │   ├── mod.rs
│   │   ├── engine.rs              # Main liquidation logic
│   │   ├── profitability.rs       # Profit calculation
│   │   └── simulator.rs           # Liquidation simulation
│   ├── transaction/
│   │   ├── mod.rs
│   │   ├── builder.rs             # Build liquidation tx
│   │   ├── signer.rs              # Sign transactions
│   │   └── sender.rs              # Send to network
│   ├── contracts/
│   │   ├── mod.rs
│   │   ├── aave.rs                # AAVE Pool interface
│   │   ├── oracle.rs              # Chainlink interface
│   │   └── flashloan.rs           # Flashloan contract
│   ├── metrics/
│   │   ├── mod.rs
│   │   ├── prometheus.rs          # Metrics export
│   │   └── logger.rs              # Structured logging
│   └── utils/
│       ├── mod.rs
│       ├── math.rs                # Fixed-point math
│       └── time.rs                # Timing utilities
├── contracts/                      # Solidity contracts
│   ├── Liquidator.sol             # Main liquidator
│   ├── FlashloanReceiver.sol      # Flashloan logic
│   └── interfaces/
│       ├── IPool.sol
│       └── IFlashLoanReceiver.sol
├── Cargo.toml
├── .env.example
└── README.md
```

---

## Технические требования

### Язык и инструменты
- **Язык:** Rust 1.75+ (stable)
- **Build system:** Cargo
- **Async runtime:** Tokio 1.35+
- **HTTP client:** Reqwest 0.11+ (для RPC)
- **WebSocket:** tokio-tungstenite (для RPC subscriptions)
- **Crypto:** ethers-rs 2.0+ (Ethereum library)
- **Database:** SQLite или Redis (для кеша позиций)
- **Metrics:** Prometheus + Grafana
- **Logging:** tracing + tracing-subscriber

### Зависимости (Cargo.toml)

```toml
[dependencies]
# Ethereum
ethers = { version = "2.0", features = ["full"] }
alloy-primitives = "0.6"
alloy-sol-types = "0.6"

# Async
tokio = { version = "1.35", features = ["full"] }
tokio-tungstenite = "0.21"
futures = "0.3"

# HTTP
reqwest = { version = "0.11", features = ["json"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"

# Database
sqlx = { version = "0.7", features = ["sqlite", "runtime-tokio"] }
redis = { version = "0.24", features = ["tokio-comp"] }

# Logging & Metrics
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }
prometheus = "0.13"

# Utils
anyhow = "1.0"
thiserror = "1.0"
chrono = "0.4"
dotenv = "0.15"

# Math
uint = "0.9"
fixed = "1.24"  # Fixed-point arithmetic

[dev-dependencies]
criterion = "0.5"  # Benchmarking
mockito = "1.2"    # HTTP mocking
```

### Инфраструктура

**Минимальные требования:**
- CPU: 4 cores (для параллельной обработки)
- RAM: 8GB (для кеша позиций)
- Disk: 50GB SSD (для логов и базы)
- Network: 100Mbps+ (низкая latency к RPC)

**Рекомендуемые требования:**
- CPU: 8+ cores
- RAM: 16GB
- Disk: 100GB NVMe SSD
- Network: 1Gbps, proximity к Base RPC

**RPC Nodes:**
- Primary: Собственный Reth node (http://80.209.241.37:8545/)
- Backup: Alchemy (https://base-mainnet.g.alchemy.com/v2/...)
- Fallback: Chainstack или другой провайдер

---

## Детальные спецификации компонентов

### 1. RPC Manager

**Назначение:** Управление подключениями к RPC nodes с failover и load balancing.

**Функционал:**
```rust
pub struct RpcManager {
    primary: Arc<Provider<Http>>,
    backup: Vec<Arc<Provider<Http>>>,
    current_provider: AtomicUsize,
    health_check_interval: Duration,
}

impl RpcManager {
    /// Создать RPC manager с primary и backup nodes
    pub async fn new(config: RpcConfig) -> Result<Self>;

    /// Получить текущий активный provider
    pub fn get_provider(&self) -> Arc<Provider<Http>>;

    /// Проверить здоровье всех providers
    pub async fn health_check(&self) -> Vec<ProviderHealth>;

    /// Автоматический failover при проблемах
    pub async fn auto_failover(&self);

    /// Получить pending блок через flashblocks
    pub async fn get_pending_block(&self) -> Result<Block<Transaction>>;

    /// Получить метрики latency
    pub fn get_latency_stats(&self) -> LatencyStats;
}
```

**Требования к производительности:**
- Latency к primary node: <100ms
- Health check frequency: каждые 5 секунд
- Failover time: <1 секунда
- Connection pool: 10 connections per provider

---

### 2. Monitoring Service

**Назначение:** Мониторинг pending блоков и детекция изменений цен.

#### 2.1 Pending Scanner

**Функционал:**
```rust
pub struct PendingScanner {
    rpc: Arc<RpcManager>,
    scan_interval: Duration,  // 200ms
    filters: Vec<TransactionFilter>,
}

impl PendingScanner {
    /// Запустить continuous scanning pending блоков
    pub async fn start(&self, tx: mpsc::Sender<PendingTransaction>);

    /// Фильтровать релевантные транзакции
    pub fn filter_transactions(&self, txs: Vec<Transaction>) -> Vec<PendingTransaction>;

    /// Определить тип транзакции
    pub fn classify_transaction(&self, tx: &Transaction) -> TransactionType;
}

pub enum TransactionType {
    OracleUpdate { feed: Address, new_price: U256 },
    DexSwap { pool: Address, amount_in: U256, amount_out: U256 },
    AaveOperation { operation: AaveOp, user: Address },
    LiquidationAttempt { liquidator: Address, user: Address },
    Irrelevant,
}
```

**Критические транзакции для отслеживания:**

1. **Chainlink Oracle Updates:**
   - Contract: Chainlink Price Feeds
   - Methods: `updateAnswer`, `transmit`
   - Assets: ETH, wstETH, cbBTC, USDC

2. **DEX Swaps (большие объемы):**
   - Uniswap V3: `swap` на ETH/USDC пуле
   - Aerodrome: major swaps
   - Threshold: >$100K USD volume

3. **AAVE Operations:**
   - `borrow`: увеличение долга
   - `withdraw`: уменьшение collateral
   - `liquidationCall`: конкуренты

---

#### 2.2 Oracle Detector

**Функционал:**
```rust
pub struct OracleDetector {
    oracle_feeds: HashMap<Address, AssetInfo>,
}

impl OracleDetector {
    /// Детектировать oracle update в pending tx
    pub fn detect_oracle_update(&self, tx: &Transaction) -> Option<PriceUpdate>;

    /// Извлечь новую цену из calldata
    pub fn extract_price_from_calldata(&self, data: &Bytes) -> Result<U256>;

    /// Определить какой актив обновляется
    pub fn identify_asset(&self, oracle: Address) -> Option<Asset>;
}

pub struct PriceUpdate {
    pub asset: Asset,
    pub old_price: U256,
    pub new_price: U256,
    pub timestamp: u64,
    pub deviation_pct: f64,
}
```

**Oracle Addresses на Base:**
```rust
// Chainlink Price Feeds (Base Mainnet)
const ORACLE_ETH_USD: Address = address!("0x71041dddad3595F9CEd3DcCFBe3D1F4b0a16Bb70");
const ORACLE_WSTETH_ETH: Address = address!("0x...");  // TBD
const ORACLE_CBBTC_USD: Address = address!("0x...");   // TBD
const ORACLE_USDC_USD: Address = address!("0x...");    // TBD

// AAVE Oracle Wrapper
const AAVE_ORACLE: Address = address!("0x2Cc0Fc26eD4563A5ce5e8bdcfe1A2878676Ae156");
```

---

#### 2.3 Price Simulator (опционально для v2)

**Функционал:**
```rust
pub struct PriceSimulator {
    dex_pools: HashMap<Address, PoolState>,
}

impl PriceSimulator {
    /// Симулировать swap и получить новую цену
    pub fn simulate_swap(&self, pool: Address, amount_in: U256, token_in: Address) -> U256;

    /// Оценить impact крупного swap на цену
    pub fn estimate_price_impact(&self, swap: &DexSwap) -> f64;

    /// Предсказать oracle update на основе DEX цен
    pub fn predict_oracle_update(&self, asset: Asset) -> Option<U256>;
}
```

---

### 3. Position Tracker

**Назначение:** Отслеживание позиций borrowers и расчет Health Factors.

**Функционал:**
```rust
pub struct PositionTracker {
    db: Arc<Database>,
    aave_pool: Address,
    positions: Arc<RwLock<HashMap<Address, Position>>>,
    update_interval: Duration,  // 10 секунд
}

pub struct Position {
    pub user: Address,
    pub total_collateral_base: U256,
    pub total_debt_base: U256,
    pub available_borrows_base: U256,
    pub current_liquidation_threshold: U256,
    pub ltv: U256,
    pub health_factor: U256,  // 18 decimals (1e18 = 1.0)
    pub last_updated: u64,
}

impl PositionTracker {
    /// Инициализация: загрузить все активные позиции
    pub async fn initialize(&mut self) -> Result<usize>;

    /// Загрузить borrowers из AAVE events
    pub async fn load_borrowers(&self, from_block: u64) -> Result<Vec<Address>>;

    /// Получить Health Factor пользователя on-chain
    pub async fn fetch_health_factor(&self, user: Address) -> Result<U256>;

    /// Обновить все позиции
    pub async fn update_all_positions(&mut self);

    /// Получить позицию из кеша
    pub fn get_position(&self, user: Address) -> Option<Position>;

    /// Пересчитать HF с новой ценой (без on-chain call)
    pub fn recalculate_hf(&self, user: Address, new_prices: &PriceMap) -> U256;

    /// Получить liquidatable позиции
    pub fn get_liquidatable(&self, threshold: U256) -> Vec<Address>;
}
```

**Стратегия обновления:**
1. **Full sync:** Каждые 10 секунд обновлять все позиции
2. **Incremental update:** При детекции oracle update пересчитать HF локально
3. **Verification:** Перед отправкой tx проверить HF on-chain

**Cache structure (SQLite):**
```sql
CREATE TABLE positions (
    user_address TEXT PRIMARY KEY,
    total_collateral_base TEXT NOT NULL,
    total_debt_base TEXT NOT NULL,
    health_factor TEXT NOT NULL,
    last_updated INTEGER NOT NULL,
    liquidation_threshold INTEGER NOT NULL
);

CREATE INDEX idx_health_factor ON positions(health_factor);
CREATE INDEX idx_last_updated ON positions(last_updated);
```

---

### 4. Liquidation Engine

**Назначение:** Принятие решений о ликвидации и расчет прибыльности.

**Функционал:**
```rust
pub struct LiquidationEngine {
    tracker: Arc<PositionTracker>,
    profitability_calculator: ProfitabilityCalculator,
    min_profit_usd: f64,  // Минимальная прибыль для ликвидации
}

impl LiquidationEngine {
    /// Обработать price update и найти возможности
    pub async fn process_price_update(&self, update: PriceUpdate) -> Vec<LiquidationOpportunity>;

    /// Оценить прибыльность ликвидации
    pub async fn calculate_profitability(&self, opportunity: &LiquidationOpportunity) -> f64;

    /// Симулировать ликвидацию
    pub async fn simulate_liquidation(&self, user: Address) -> Result<SimulationResult>;

    /// Принять решение о ликвидации
    pub fn should_liquidate(&self, opportunity: &LiquidationOpportunity) -> bool;
}

pub struct LiquidationOpportunity {
    pub user: Address,
    pub collateral_asset: Address,
    pub debt_asset: Address,
    pub debt_to_cover: U256,
    pub expected_collateral: U256,
    pub estimated_profit_usd: f64,
    pub health_factor: U256,
    pub gas_cost_estimate: U256,
    pub confidence: f64,  // 0.0-1.0
}

pub struct ProfitabilityCalculator {
    gas_price: U256,
    token_prices: Arc<RwLock<HashMap<Address, U256>>>,
}

impl ProfitabilityCalculator {
    /// Рассчитать ожидаемую прибыль
    pub fn calculate_profit(&self, opportunity: &LiquidationOpportunity) -> f64;

    /// Оценить gas cost
    pub fn estimate_gas_cost(&self) -> U256;

    /// Рассчитать collateral bonus (5-10%)
    pub fn calculate_liquidation_bonus(&self, collateral: Address) -> f64;
}
```

**Decision criteria:**
```rust
// Ликвидировать если:
// 1. HF < 1.0 (можно ликвидировать)
// 2. Прибыль > $50 (минимальный порог)
// 3. Gas cost < 30% прибыли
// 4. Confidence > 0.8 (высокая уверенность)
fn should_liquidate(opp: &LiquidationOpportunity) -> bool {
    opp.health_factor < U256::from(1_000_000_000_000_000_000u128) && // HF < 1.0
    opp.estimated_profit_usd > 50.0 &&
    opp.gas_cost_estimate.as_u64() as f64 < opp.estimated_profit_usd * 0.3 &&
    opp.confidence > 0.8
}
```

---

### 5. Transaction Manager

**Назначение:** Построение, подписание и отправка транзакций.

**Функционал:**
```rust
pub struct TransactionManager {
    signer: Arc<LocalWallet>,
    liquidator_contract: Address,
    nonce_manager: NonceManager,
    gas_strategy: GasStrategy,
}

impl TransactionManager {
    /// Построить liquidation transaction
    pub fn build_liquidation_tx(&self, opp: &LiquidationOpportunity) -> Transaction;

    /// Подписать транзакцию
    pub fn sign_transaction(&self, tx: Transaction) -> Result<Bytes>;

    /// Отправить транзакцию
    pub async fn send_transaction(&self, signed_tx: Bytes) -> Result<H256>;

    /// Ждать подтверждения
    pub async fn wait_for_receipt(&self, tx_hash: H256) -> Result<TransactionReceipt>;
}

pub struct NonceManager {
    current_nonce: AtomicU64,
}

impl NonceManager {
    /// Получить следующий nonce (atomic)
    pub fn next_nonce(&self) -> u64;

    /// Синхронизировать с on-chain nonce
    pub async fn sync_nonce(&mut self, provider: &Provider<Http>);
}

pub struct GasStrategy {
    base_fee_multiplier: f64,  // 1.0 = базовый fee
    priority_fee: U256,         // 0 для Base (не нужен)
}

impl GasStrategy {
    /// Рассчитать optimal gas price
    pub async fn calculate_gas_price(&self, provider: &Provider<Http>) -> U256;

    /// Получить базовый fee из pending блока
    pub fn get_base_fee_from_pending(&self, block: &Block<Transaction>) -> U256;
}
```

**Transaction structure:**
```rust
// Вызов liquidation на вашем контракте
let tx = TransactionRequest::new()
    .to(liquidator_contract)
    .data(
        // liquidate(address user, address collateralAsset, address debtAsset, uint256 debtToCover)
        encode_function_data("liquidate", (user, collateral, debt, amount))
    )
    .gas(1_200_000)  // ~1.2M газ для flashloan liquidation
    .gas_price(calculate_gas_price())  // 0.3-0.6 gwei
    .nonce(get_next_nonce());
```

---

### 6. Metrics & Monitoring

**Назначение:** Сбор метрик производительности и алертинг.

**Prometheus metrics:**
```rust
lazy_static! {
    // Latency metrics
    static ref PENDING_BLOCK_LATENCY: Histogram = register_histogram!(
        "pending_block_latency_ms",
        "Latency to receive pending block"
    ).unwrap();

    static ref LIQUIDATION_DECISION_TIME: Histogram = register_histogram!(
        "liquidation_decision_time_ms",
        "Time to make liquidation decision"
    ).unwrap();

    static ref TX_SEND_TIME: Histogram = register_histogram!(
        "tx_send_time_ms",
        "Time to send transaction"
    ).unwrap();

    // Success metrics
    static ref LIQUIDATIONS_ATTEMPTED: Counter = register_counter!(
        "liquidations_attempted_total",
        "Total liquidations attempted"
    ).unwrap();

    static ref LIQUIDATIONS_SUCCESSFUL: Counter = register_counter!(
        "liquidations_successful_total",
        "Total successful liquidations"
    ).unwrap();

    static ref PROFIT_USD: Counter = register_counter!(
        "profit_usd_total",
        "Total profit in USD"
    ).unwrap();

    // Position metrics
    static ref POSITIONS_TRACKED: Gauge = register_gauge!(
        "positions_tracked",
        "Number of positions being tracked"
    ).unwrap();

    static ref LIQUIDATABLE_POSITIONS: Gauge = register_gauge!(
        "liquidatable_positions",
        "Number of liquidatable positions"
    ).unwrap();
}
```

**Grafana dashboards:**
- Latency dashboard (pending scan, decision, tx send)
- Profitability dashboard (успешные лик, profit, ROI)
- Position dashboard (tracked, liquidatable, at-risk)
- Competition dashboard (проигранные лик, причины)

**Алертинг:**
- RPC node недоступен >30 секунд
- Latency >500ms
- No liquidations за последние 24 часа (возможно проблема)
- Failed transactions >20%
- Низкий баланс ETH для газа (<0.1 ETH)

---

## Стратегия мониторинга

### Подход: Hybrid Pending + Oracle

**Этап 1 (MVP):** Мониторинг oracle updates в pending

```rust
async fn monitor_pending_oracle_updates() {
    loop {
        // 1. Получить pending блок
        let pending = rpc.get_pending_block().await?;

        // 2. Найти oracle update транзакции
        for tx in pending.transactions {
            if let Some(price_update) = oracle_detector.detect_oracle_update(&tx) {
                // 3. Пересчитать HF всех позиций с новой ценой
                let liquidatable = tracker.recalculate_all_with_price(price_update);

                // 4. Для каждой liquidatable позиции
                for user in liquidatable {
                    let opp = engine.create_opportunity(user, price_update).await?;

                    // 5. Если прибыльно -> отправить tx
                    if engine.should_liquidate(&opp) {
                        let tx = tx_manager.build_liquidation_tx(&opp);
                        let tx_hash = tx_manager.send_transaction(tx).await?;

                        log::info!("Sent liquidation tx: {}", tx_hash);
                    }
                }
            }
        }

        // 6. Wait 200ms before next scan
        tokio::time::sleep(Duration::from_millis(200)).await;
    }
}
```

**Ожидаемая производительность:**
- Latency: 78ms (reth) + 50ms (processing) + 50ms (tx send) = **~180ms**
- Позиция в блоке: **#180-250** (топ 10-15%)

---

**Этап 2 (Advanced):** Симуляция DEX swaps

```rust
async fn monitor_dex_swaps() {
    // Дополнительно мониторить крупные DEX swaps
    // Симулировать их влияние на цены
    // Предсказывать oracle updates
    // Отправлять tx упреждающе
}
```

**Ожидаемая производительность:**
- Latency: 78ms + 80ms (simulation) + 50ms = **~210ms**
- Позиция в блоке: **#200-300**
- Преимущество: возможность ликвидировать ДО oracle update

---

### Параллельная обработка

```rust
#[tokio::main]
async fn main() {
    // Запустить несколько параллельных tasks

    // Task 1: Pending block scanner
    tokio::spawn(async move {
        scanner.start(tx_sender).await;
    });

    // Task 2: Position updater
    tokio::spawn(async move {
        loop {
            tracker.update_all_positions().await;
            tokio::time::sleep(Duration::from_secs(10)).await;
        }
    });

    // Task 3: Liquidation processor
    tokio::spawn(async move {
        while let Some(opportunity) = rx_receiver.recv().await {
            process_liquidation(opportunity).await;
        }
    });

    // Task 4: Metrics exporter
    tokio::spawn(async move {
        metrics_server.run().await;
    });
}
```

---

## Алгоритмы и логика

### Health Factor Calculation

```rust
/// AAVE v3 Health Factor formula:
/// HF = (totalCollateralBase * liquidationThreshold) / totalDebtBase
///
/// Where:
/// - totalCollateralBase: total collateral in base currency (USD)
/// - liquidationThreshold: weighted average of collateral LTs (scaled to 10000)
/// - totalDebtBase: total debt in base currency (USD)
///
/// HF is scaled to 18 decimals (1e18 = 1.0)
/// HF < 1.0 = liquidatable
pub fn calculate_health_factor(position: &Position) -> U256 {
    if position.total_debt_base.is_zero() {
        return U256::MAX; // No debt = infinite HF
    }

    let numerator = position.total_collateral_base
        .checked_mul(position.current_liquidation_threshold)
        .expect("overflow");

    let denominator = position.total_debt_base
        .checked_mul(U256::from(10000))
        .expect("overflow");

    numerator.checked_div(denominator).unwrap_or(U256::ZERO)
}

/// Пересчитать HF с новой ценой актива
pub fn recalculate_hf_with_new_price(
    position: &Position,
    asset: Asset,
    old_price: U256,
    new_price: U256,
) -> U256 {
    // Определить какой актив изменился (collateral или debt)
    let (new_collateral, new_debt) = if asset.is_collateral() {
        let ratio = new_price.checked_mul(U256::from(1e18)).unwrap().checked_div(old_price).unwrap();
        let new_coll = position.total_collateral_base.checked_mul(ratio).unwrap().checked_div(U256::from(1e18)).unwrap();
        (new_coll, position.total_debt_base)
    } else {
        let ratio = new_price.checked_mul(U256::from(1e18)).unwrap().checked_div(old_price).unwrap();
        let new_debt = position.total_debt_base.checked_mul(ratio).unwrap().checked_div(U256::from(1e18)).unwrap();
        (position.total_collateral_base, new_debt)
    };

    // Пересчитать HF
    if new_debt.is_zero() {
        return U256::MAX;
    }

    let numerator = new_collateral
        .checked_mul(position.current_liquidation_threshold)
        .expect("overflow");

    let denominator = new_debt
        .checked_mul(U256::from(10000))
        .expect("overflow");

    numerator.checked_div(denominator).unwrap_or(U256::ZERO)
}
```

### Liquidation Bonus Calculation

```rust
/// AAVE v3 Liquidation Bonus (5-10% в зависимости от актива)
///
/// Для Base:
/// - WETH: 5% (10500 = 105%)
/// - wstETH: 7% (10700 = 107%)
/// - cbBTC: 10% (11000 = 110%)
/// - USDC: 5% (10500 = 105%)
pub fn get_liquidation_bonus(collateral_asset: Address) -> u16 {
    match collateral_asset {
        WETH => 10500,      // 5%
        WSTETH => 10700,    // 7%
        CBBTC => 11000,     // 10%
        USDC => 10500,      // 5%
        _ => 10500,         // Default 5%
    }
}

/// Рассчитать ожидаемый collateral
pub fn calculate_expected_collateral(
    debt_to_cover: U256,
    collateral_asset: Address,
    debt_price: U256,
    collateral_price: U256,
) -> U256 {
    let bonus = get_liquidation_bonus(collateral_asset);

    // debt_to_cover * debt_price = USD value
    let debt_usd = debt_to_cover.checked_mul(debt_price).unwrap();

    // debt_usd * bonus / 10000 = collateral USD with bonus
    let collateral_usd = debt_usd.checked_mul(U256::from(bonus)).unwrap()
        .checked_div(U256::from(10000)).unwrap();

    // collateral_usd / collateral_price = collateral amount
    collateral_usd.checked_div(collateral_price).unwrap()
}

/// Рассчитать прибыль
pub fn calculate_profit_usd(
    debt_to_cover_usd: f64,
    collateral_received_usd: f64,
    gas_cost_usd: f64,
) -> f64 {
    collateral_received_usd - debt_to_cover_usd - gas_cost_usd
}
```

### Gas Optimization

```rust
/// Оптимальная gas price стратегия для Base
pub async fn calculate_optimal_gas_price(provider: &Provider<Http>) -> U256 {
    // Base использует базовый fee без priority fees
    // Достаточно базового fee + небольшой запас

    let pending_block = provider.get_block(BlockNumber::Pending).await?;
    let base_fee = pending_block.base_fee_per_gas.unwrap_or(U256::from(100_000_000)); // 0.1 gwei

    // Добавляем 10% запас для уверенности
    base_fee.checked_mul(U256::from(110)).unwrap()
        .checked_div(U256::from(100)).unwrap()
}

/// Из анализа: боты используют 0.3-0.6 gwei
/// Мы можем использовать базовый fee + 10% = достаточно
```

---

## Метрики производительности

### Target Metrics

| Метрика | Target | Обоснование |
|---------|--------|-------------|
| **Pending Block Latency** | <100ms | Reth node: 78ms avg |
| **Oracle Detection Time** | <20ms | Парсинг calldata |
| **HF Recalculation Time** | <30ms | 100 позиций |
| **Decision Time** | <20ms | Profitability calc |
| **TX Building Time** | <30ms | Encode + sign |
| **TX Send Time** | <50ms | Network latency |
| **Total Latency (E2E)** | **150-200ms** | Цель: позиция #180-300 |

### Success Metrics

| Метрика | Target | Измерение |
|---------|--------|-----------|
| **Liquidation Success Rate** | >80% | Успешные tx / отправленные |
| **Market Share** | 20-30% | Наши лик / все лик |
| **Avg Block Position** | #180-300 | Топ 10-15% |
| **Monthly Profit** | $40-80K | Прибыль в USD |
| **Profit per Liquidation** | >$400 | После gas costs |
| **Uptime** | >99.9% | 24/7 operation |

### Benchmark Tests

```rust
#[cfg(test)]
mod benchmarks {
    use criterion::{black_box, criterion_group, criterion_main, Criterion};

    fn bench_hf_calculation(c: &mut Criterion) {
        c.bench_function("hf_calc", |b| {
            b.iter(|| {
                calculate_health_factor(black_box(&position))
            });
        });
    }

    fn bench_oracle_detection(c: &mut Criterion) {
        c.bench_function("oracle_detect", |b| {
            b.iter(|| {
                oracle_detector.detect_oracle_update(black_box(&tx))
            });
        });
    }

    // Target: <1ms per operation
    criterion_group!(benches, bench_hf_calculation, bench_oracle_detection);
    criterion_main!(benches);
}
```

---

## Безопасность и управление рисками

### Private Key Management

```rust
// НЕ ХАРДКОДИТЬ В КОДЕ!
// Использовать environment variables или AWS Secrets Manager

pub fn load_wallet() -> Result<LocalWallet> {
    let private_key = std::env::var("LIQUIDATOR_PRIVATE_KEY")
        .expect("LIQUIDATOR_PRIVATE_KEY must be set");

    let wallet = private_key.parse::<LocalWallet>()?;
    Ok(wallet)
}

// Или использовать hardware wallet (Ledger, Trezor)
```

### Smart Contract Security

**Liquidator Contract требования:**
- ✅ Reentrancy guard на всех internal functions
- ✅ Access control: only owner can withdraw profits
- ✅ Slippage protection на swaps
- ✅ Emergency pause mechanism
- ✅ Flashloan callback validation
- ✅ Audited by reputable firm (Trail of Bits, OpenZeppelin)

**Example contract structure:**
```solidity
// contracts/Liquidator.sol
contract Liquidator is Ownable, ReentrancyGuard {
    IAavePool public immutable AAVE_POOL;
    ISwapRouter public immutable SWAP_ROUTER;

    bool public paused;

    modifier whenNotPaused() {
        require(!paused, "Contract paused");
        _;
    }

    /// @notice Liquidate position using flashloan
    /// @dev Only callable by bot's EOA
    function liquidate(
        address user,
        address collateralAsset,
        address debtAsset,
        uint256 debtToCover
    ) external onlyOwner whenNotPaused nonReentrant {
        // 1. Take flashloan
        // 2. Liquidate on AAVE
        // 3. Swap collateral for debt asset
        // 4. Repay flashloan
        // 5. Profit stays in contract
    }

    /// @notice Withdraw profits (only owner)
    function withdrawProfits(address token) external onlyOwner {
        // Transfer profits to owner
    }

    /// @notice Emergency pause
    function pause() external onlyOwner {
        paused = true;
    }
}
```

### Risk Management

**1. Position Size Limits:**
```rust
const MAX_LIQUIDATION_SIZE_USD: f64 = 100_000.0;  // Max $100K per liquidation
const MAX_DAILY_VOLUME_USD: f64 = 1_000_000.0;    // Max $1M per day
```

**2. Profit Thresholds:**
```rust
const MIN_PROFIT_USD: f64 = 50.0;          // Минимум $50 прибыли
const MIN_PROFIT_MARGIN: f64 = 0.02;       // Минимум 2% margin
const MAX_GAS_COST_RATIO: f64 = 0.3;       // Газ не больше 30% прибыли
```

**3. Monitoring & Alerts:**
- Real-time Telegram/Discord alerts на успешные ликвидации
- Alerts на failed transactions (investigate why)
- Daily profit reports
- Weekly competition analysis

**4. Failsafe Mechanisms:**
```rust
// Автоматическая остановка при проблемах
pub async fn health_check() -> HealthStatus {
    // Check RPC connectivity
    // Check wallet balance
    // Check contract state
    // Check recent success rate

    if success_rate < 0.5 {
        return HealthStatus::Critical; // Stop operations
    }

    HealthStatus::Healthy
}
```

**5. Fund Management:**
- Держать минимальный баланс для газа (0.5 ETH)
- Автоматический withdraw profits при >5 ETH
- Multi-sig для withdrawal крупных сумм

---

## Этапы разработки

### Phase 1: MVP (2-3 недели)

**Цель:** Базовый working bot с мониторингом oracle updates.

**Задачи:**
- [x] Setup Rust project structure
- [ ] Implement RPC Manager
  - [ ] Connection to Reth node
  - [ ] Failover to Alchemy
  - [ ] Health checks
- [ ] Implement Pending Scanner
  - [ ] eth_getBlockByNumber("pending")
  - [ ] Parse transactions
  - [ ] Filter oracle updates
- [ ] Implement Oracle Detector
  - [ ] Detect Chainlink updates
  - [ ] Extract new prices from calldata
- [ ] Implement Position Tracker
  - [ ] Load borrowers from events
  - [ ] Fetch Health Factors
  - [ ] Cache in SQLite
- [ ] Implement Liquidation Engine
  - [ ] Detect HF < 1.0
  - [ ] Calculate profitability
  - [ ] Basic decision logic
- [ ] Implement Transaction Manager
  - [ ] Build liquidation tx
  - [ ] Sign with private key
  - [ ] Send to network
- [ ] Deploy simple Liquidator contract
  - [ ] Flashloan logic
  - [ ] AAVE liquidation call
  - [ ] Swap on Uniswap
- [ ] Testing on Base testnet
- [ ] **Deploy to mainnet with small capital**

**Success Criteria:**
- ✅ Bot detects liquidation opportunities
- ✅ Successfully executes at least 1 liquidation on mainnet
- ✅ No critical bugs or exploits
- ✅ Latency <500ms (acceptable for MVP)

---

### Phase 2: Optimization (2-3 недели)

**Цель:** Оптимизировать производительность до target metrics.

**Задачи:**
- [ ] Optimize latency
  - [ ] Parallel processing
  - [ ] Reduce HF calc time
  - [ ] Optimize TX building
- [ ] Improve decision logic
  - [ ] Better profitability calculation
  - [ ] Gas cost estimation
  - [ ] Risk scoring
- [ ] Add metrics & monitoring
  - [ ] Prometheus integration
  - [ ] Grafana dashboards
  - [ ] Telegram alerts
- [ ] Optimize gas usage
  - [ ] Dynamic gas pricing
  - [ ] Contract gas optimization
- [ ] Database optimization
  - [ ] Efficient indexing
  - [ ] Redis cache layer
- [ ] Competition analysis
  - [ ] Track competitor liquidations
  - [ ] Analyze why we lost
  - [ ] Adjust strategy

**Success Criteria:**
- ✅ Latency <200ms consistently
- ✅ Position in block: топ 20%
- ✅ Success rate >70%
- ✅ Making profit consistently ($1-5K/week)

---

### Phase 3: Advanced Features (3-4 недели)

**Цель:** Добавить advanced функционал для максимальной конкурентоспособности.

**Задачи:**
- [ ] DEX swap simulation
  - [ ] Monitor large DEX swaps
  - [ ] Predict price changes
  - [ ] Preemptive liquidations
- [ ] Multi-asset support
  - [ ] Support all AAVE assets
  - [ ] Cross-collateral liquidations
- [ ] Advanced gas strategies
  - [ ] MEV bundle inclusion (опционально)
  - [ ] Flashbots integration (если доступен на Base)
- [ ] Machine learning (опционально)
  - [ ] Predict liquidation windows
  - [ ] Optimize decision thresholds
- [ ] Multi-protocol support
  - [ ] Compound v3
  - [ ] Sonne Finance
  - [ ] Другие lending protocols на Base

**Success Criteria:**
- ✅ Latency <150ms
- ✅ Position in block: топ 10%
- ✅ Success rate >80%
- ✅ Market share >20%
- ✅ Monthly profit $40K+

---

### Phase 4: Scale & Maintain (Ongoing)

**Цель:** Масштабировать операции и поддерживать конкурентоспособность.

**Задачи:**
- [ ] Multi-chain expansion
  - [ ] Ethereum mainnet
  - [ ] Arbitrum, Optimism
  - [ ] Polygon
- [ ] Keeper network
  - [ ] Distributed monitoring
  - [ ] Geographic redundancy
  - [ ] Multiple operators
- [ ] Advanced analytics
  - [ ] Historical data analysis
  - [ ] Competitor tracking
  - [ ] Market trend analysis
- [ ] Continuous optimization
  - [ ] A/B testing strategies
  - [ ] Parameter tuning
  - [ ] Code profiling

---

## Appendix: Данные конкурентов

### Детальные данные Bot #1

```
Address: 0xc88eab547fde493992b2456589f2796960cc4561
Contract Size: 291 bytes
Created: 10.11.2024 (блок 22,224,199)
Active: 365 days

Performance (365 days):
- Liquidations: 76
- Total Profit: $618,391
- Monthly Avg: $50,828
- Daily Avg: $1,695
- Per Liquidation Avg: $8,137
- Best: $123,586
- Worst: -$8,637

Speed:
- Same block: 100%
- Avg position: #620 (35.3%)
- Avg latency: 0 blocks

Gas:
- Avg: 0.28 gwei
- Max: 0.34 gwei
- Priority fees: No

Strategy:
- Selective (10% market share)
- Large positions (avg $29K debt)
- 41 unique callers (distributed)
```

### Детальные данные Bot #2

```
Address: 0xd12810b19b596347a3afac206d3ca65d08594b3f
Contract Size: 170 bytes ⭐
Created: 30.05.2024 (блок 15,149,037)
Active: 529 days

Performance (529 days):
- Liquidations: 567
- Total Profit: $2,981,097 🔥
- Monthly Avg: $169,060
- Daily Avg: $5,635
- Per Liquidation Avg: $5,258
- Best: $511,766 (RECORD!)
- Worst: -$42,017

Speed:
- Same block: 100%
- Avg position: #1308 (59.3%)
- Avg latency: 0 blocks

Gas:
- Avg: 0.30 gwei
- Max: 0.44 gwei
- Priority fees: No

Strategy:
- Aggressive (40% market share)
- All sizes (avg $11K debt)
- High frequency (1.07/day)
- Dominant market player
```

### Детальные данные Bot #3

```
Address: 0x0a5a3e02c2aae465a016531a7aa6b4be4b21d3f9
Contract Size: 21,338 bytes (complex!)
Created: 14.10.2025 (блок 36,818,641)
Active: 27 days

Performance (27 days):
- Liquidations: 2
- Total Profit: $21,824
- Monthly Avg: $24,249 (projected)
- Per Liquidation Avg: $10,912 (HIGHEST!)
- Best: $13,128
- Worst: $8,696

Speed:
- Same block: 100%
- Avg position: #314 (18.2%) ⚡ FASTEST
- Avg latency: 0 blocks

Gas:
- Avg: 0.40 gwei
- Max: 0.60 gwei
- Priority fees: No

Strategy:
- Ultra-selective (5% market share)
- Massive positions only (avg $80K debt!)
- Very rare but highly profitable
- New player, proving effectiveness
```

---

## Configuration Example

**.env file:**
```bash
# RPC Endpoints
PRIMARY_RPC_URL=http://80.209.241.37:8545/
BACKUP_RPC_URL=https://base-mainnet.g.alchemy.com/v2/04r_vJrz9iSljxSQj8UQn
FALLBACK_RPC_URL=https://base-mainnet.core.chainstack.com/d28ec3a626cdc7f3e4c8bb04de7c7a88

# Private Key (use environment variable or secrets manager)
LIQUIDATOR_PRIVATE_KEY=0x...

# Contracts
AAVE_POOL_ADDRESS=0xA238Dd80C259a72e81d7e4664a9801593F98d1c5
LIQUIDATOR_CONTRACT_ADDRESS=0x...  # Your deployed contract
AAVE_ORACLE_ADDRESS=0x2Cc0Fc26eD4563A5ce5e8bdcfe1A2878676Ae156

# Strategy Parameters
MIN_PROFIT_USD=50.0
MIN_HEALTH_FACTOR=1000000000000000000  # 1.0 in 18 decimals
MAX_GAS_COST_RATIO=0.3
SCAN_INTERVAL_MS=200

# Database
DATABASE_URL=sqlite://liquidation_bot.db

# Monitoring
PROMETHEUS_PORT=9090
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# Logging
RUST_LOG=info,liquidation_bot=debug
LOG_FILE=liquidation_bot.log
```

---

## Заключение

Это comprehensive техническое задание для разработки production-ready AAVE liquidation bot на Rust для Base network.

**Ключевые преимущества вашего бота:**
1. ⚡ **Reth node с flashblocks:** 78ms latency (в 4.2x быстрее Alchemy)
2. 🚀 **Rust производительность:** Sub-millisecond обработка
3. 📊 **Pending block monitoring:** Детекция до включения в блок
4. 🎯 **Target latency 150-200ms:** Позиция #180-300 (топ 10-15%)

**Ожидаемые результаты:**
- Market share: 20-30%
- Monthly profit: $40-80K
- Success rate: >80%
- Можете обогнать Bot #2 (король рынка!)

**Следующий шаг:** Начать разработку с Phase 1 (MVP).

Успехов в разработке! 🚀
