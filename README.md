# Тестирование Base Network

Этот репозиторий содержит скрипты и документацию для работы с Base Network:

1. **Тестирование Reth ноды** - проверка работоспособности собственной ноды
2. **GeckoTerminal API** - получение данных о DEX пулах и ликвидности

## 1. Тестирование Reth ноды

Результаты тестирования reth ноды, развернутой для Base Mainnet.

## Информация о ноде

- **URL**: http://80.209.241.37:8545/
- **Сеть**: Base Mainnet (Chain ID: 8453)
- **Версия клиента**: reth/v1.9.0-84785f0/x86_64-unknown-linux-gnu/base/v0.1.16

## Результаты тестов

### Основные параметры

- ✅ **Статус синхронизации**: Полностью синхронизирована
- ✅ **Chain ID**: 8453 (Base Mainnet)
- ✅ **Network Version**: 8453
- ✅ **Protocol Version**: 5
- ✅ **Подключенные пиры**: 67

### Последний блок

- **Номер блока**: 37,920,741
- **Timestamp**: 2025-11-08 19:40:29
- **Транзакций в блоке**: 538
- **Использование газа**: 78,083,893 (31.23% от лимита)
- **Лимит газа**: 250,000,000
- **Base Fee**: 0.0005 gwei

### Текущая цена газа

- **Wei**: 1,519,089
- **Gwei**: 0.001519

### Доступные RPC методы

Все основные методы доступны и работают:

- ✅ `web3_clientVersion`
- ✅ `eth_chainId`
- ✅ `eth_blockNumber`
- ✅ `eth_syncing`
- ✅ `net_version`
- ✅ `net_peerCount`
- ✅ `eth_gasPrice`
- ✅ `eth_protocolVersion`
- ✅ `eth_getBlockByNumber`
- ✅ `eth_call`
- ✅ `eth_getLogs`
- ✅ `eth_getBalance`
- ✅ `eth_getCode`
- ✅ `eth_estimateGas`

## Использование тестовых скриптов

### Bash скрипт

```bash
./test_reth_node.sh
```

Требуется: `curl`, `jq`, `bc`

### Python скрипт

```bash
python3 test_reth_node.py
```

Требуется: `python3`, `requests`

Установка зависимостей:
```bash
pip3 install requests
```

## Примеры запросов

### Получить версию клиента

```bash
curl -X POST http://80.209.241.37:8545/ \
  -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"web3_clientVersion","params":[],"id":1}'
```

### Получить последний блок

```bash
curl -X POST http://80.209.241.37:8545/ \
  -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

### Получить баланс адреса

```bash
curl -X POST http://80.209.241.37:8545/ \
  -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_getBalance","params":["0xYOUR_ADDRESS","latest"],"id":1}'
```

## Заключение

Нода работает стабильно и корректно:
- Полностью синхронизирована с сетью Base Mainnet
- Все RPC методы доступны и работают
- Хорошее количество подключенных пиров (67)
- Низкие комиссии (< 0.002 gwei)

Нода готова к использованию для взаимодействия с Base Mainnet.

---

## 2. GeckoTerminal API

### Описание

GeckoTerminal API предоставляет данные о DEX пулах на Base Network, включая:
- Ликвидность (TVL) пулов
- Объемы торгов
- Количество транзакций
- Изменения цен

### Использование скриптов

#### Python скрипт (детальный анализ)

```bash
python3 test_geckoterminal_api.py
```

Скрипт выводит:
- Топ-5 пулов по количеству транзакций за 24 часа
- Топ-5 самых активных пулов за последний час
- Топ-5 пулов по ликвидности
- Список доступных параметров сортировки

#### Bash скрипт (быстрый запрос)

```bash
./test_geckoterminal.sh
```

### Доступные параметры сортировки

| Параметр | Описание | Статус |
|----------|----------|--------|
| `h24_tx_count_desc` | По количеству транзакций за 24ч | ✅ Работает |
| `h24_volume_usd_desc` | По объему торгов за 24ч | ⚠️ Иногда 503 |
| `h6_volume_usd_desc` | По объему торгов за 6ч | ⚠️ Ограничено |
| `h1_volume_usd_desc` | По объему торгов за 1ч | ❌ 400 Error |
| Без параметра | По умолчанию (ликвидность) | ✅ Работает |

### Топ-5 самых ликвидных пулов на Base

1. **WETH / USDC 0.05%** (Aerodrome) - TVL: $35.59M, Vol: $141.69M/24h
2. **USDC / WETH 0.05%** (Uniswap V3) - TVL: $21.94M, Vol: $36.38M/24h
3. **WETH / USDC 0.01%** (PancakeSwap V3) - TVL: $7.94M, Vol: $98.16M/24h
4. **cbBTC / WETH 0.01%** (PancakeSwap V3) - TVL: $4.92M, Vol: $72.12M/24h
5. **ZEN / WETH 0.15%** (Aerodrome) - TVL: $4.70M, Vol: $16.64M/24h

### Примеры запросов

#### Получить топ пулы по транзакциям

```bash
curl -s "https://api.geckoterminal.com/api/v2/networks/base/pools?sort=h24_tx_count_desc" | jq .
```

#### Получить пулы по умолчанию

```bash
curl -s "https://api.geckoterminal.com/api/v2/networks/base/pools" | jq .
```

### Документация

Подробная документация по API доступна в файле [GECKOTERMINAL_API.md](GECKOTERMINAL_API.md)

---

## 3. Анализ концентрированной ликвидности пулов

### Описание

Скрипты для анализа on-chain данных пулов с концентрированной ликвидностью (Uniswap V3, Aerodrome Slipstream, PancakeSwap V3).

Получают:
- Текущий тик (current tick)
- SqrtPriceX96 (цена в формате Uniswap V3)
- Активную ликвидность в текущем диапазоне
- Реальные цены токенов

### Использование скриптов

#### Базовый анализ

```bash
python3 get_pool_liquidity.py
```

Получает топ-10 пулов и показывает их концентрированную ликвидность.

#### Детальный анализ со статистикой

```bash
python3 analyze_pool_liquidity.py
```

Выводит:
- Подробные данные о каждом пуле
- Текущие тики и цены
- Активную ликвидность
- Эффективность пулов (Volume/TVL ratio)
- Топ-3 пулов по различным метрикам

### Результаты анализа

**Топ-3 пула по активной ликвидности:**
1. VIRTUAL / WETH 0.05% - 94.91e21
2. VIRTUAL / WETH 0.05% - 89.84e21
3. ZEN / WETH 0.15% - 26.35e21

**Топ-3 пула по эффективности (Volume/TVL):**
1. WETH / USDC 0.01% - 33.07x
2. WETH / cbBTC 0.01% - 32.47x
3. VIRTUAL / WETH 0.05% - 18.00x

### Как это работает

1. **GeckoTerminal API** - получение топ пулов по объему
2. **eth_call к reth ноде** - запрос on-chain данных:
   - `slot0()` - текущий тик и sqrtPriceX96
   - `liquidity()` - активная ликвидность
3. **Декодирование** - конвертация ABI-encoded данных
4. **Расчет цен** - из тика и sqrtPriceX96

### Что такое концентрированная ликвидность?

В Uniswap V3 и подобных протоколах ликвидность концентрируется в определенных ценовых диапазонах:

- **Tick** - дискретная единица цены (~0.01% изменения)
- **Active Liquidity** - ликвидность доступная для торговли в текущем тике
- **sqrtPriceX96** - корень квадратный из цены, умноженный на 2^96

Преимущества:
- Более эффективное использование капитала
- Меньшее проскальзывание в активном диапазоне
- Возможность кастомизации стратегий LP

---

## Файлы в репозитории

### Reth Node Testing
- `test_reth_node.py` - Python скрипт для тестирования ноды
- `test_reth_node.sh` - Bash скрипт для тестирования ноды

### GeckoTerminal API
- `test_geckoterminal_api.py` - Python скрипт для работы с API
- `test_geckoterminal.sh` - Bash скрипт для быстрых запросов
- `GECKOTERMINAL_API.md` - Полная документация по API

### On-Chain Liquidity Analysis
- `get_pool_liquidity.py` - Базовый анализ ликвидности пулов
- `analyze_pool_liquidity.py` - Детальный анализ со статистикой

### Документация
- `README.md` - Этот файл

---

## Требования

### Для Reth Node скриптов
- Python 3.x
- `requests` библиотека: `pip3 install requests`
- `curl`, `jq`, `bc` (для bash скрипта)

### Для GeckoTerminal и Liquidity Analysis скриптов
- Python 3.x
- `requests` библиотека: `pip3 install requests`
- `curl`, `jq` (для bash скрипта)
- Доступ к reth ноде на Base (для on-chain запросов)

---

## Заключение

Этот репозиторий предоставляет полный набор инструментов для работы с Base Network:
- ✅ Тестирование собственной reth ноды
- ✅ Получение данных о DEX пулах через GeckoTerminal API
- ✅ On-chain анализ концентрированной ликвидности
- ✅ Скрипты на Python и Bash
- ✅ Подробная документация

### Возможности

1. **RPC Node Testing** - проверка работоспособности Ethereum-совместимой ноды
2. **DEX Analytics** - получение данных о торговых парах, объемах, ликвидности
3. **On-Chain Queries** - прямые запросы к смарт-контрактам пулов
4. **Liquidity Analysis** - анализ концентрированной ликвидности в V3 пулах
5. **Price Calculations** - расчет цен из тиков и sqrtPriceX96
