# GeckoTerminal API - Руководство по работе с Base Network

## Описание

GeckoTerminal API предоставляет данные о DEX пулах, ликвидности, объемах торгов и ценах токенов на различных блокчейн-сетях, включая Base.

**Base URL**: `https://api.geckoterminal.com/api/v2`

## Основные endpoint'ы

### 1. Получить список сетей

```bash
GET /networks
```

**Пример:**
```bash
curl -s "https://api.geckoterminal.com/api/v2/networks" | jq .
```

**Результат:** Base имеет идентификатор `"base"`

### 2. Получить пулы на Base

```bash
GET /networks/base/pools
```

**Параметры запроса:**
- `page` - номер страницы (по умолчанию 1)
- `sort` - параметр сортировки (см. ниже)

**Пример:**
```bash
curl -s "https://api.geckoterminal.com/api/v2/networks/base/pools?page=1" | jq .
```

## Параметры сортировки

API поддерживает следующие параметры сортировки (параметр `sort`):

### ✅ Работающие параметры:

1. **`h24_tx_count_desc`** - По количеству транзакций за 24 часа (убывание)
   ```bash
   curl -s "https://api.geckoterminal.com/api/v2/networks/base/pools?sort=h24_tx_count_desc"
   ```

2. **Без параметра сортировки** - По умолчанию (предположительно по ликвидности)
   ```bash
   curl -s "https://api.geckoterminal.com/api/v2/networks/base/pools"
   ```

### ⚠️ Параметры с ограничениями:

3. **`h24_volume_usd_desc`** - По объему торгов за 24 часа
   - Иногда возвращает 503 Service Unavailable
   - Может требовать дополнительных параметров или иметь rate limiting

4. **`h6_volume_usd_desc`** - По объему торгов за 6 часов
5. **`h1_volume_usd_desc`** - По объему торгов за 1 час
   - Возвращает 400 Bad Request (возможно не поддерживается)
6. **`m5_volume_usd_desc`** - По объему торгов за 5 минут

## Структура ответа

### Основные поля пула:

```json
{
  "id": "base_0x72ab388e2e2f6facef59e3c3fa2c4e29011c2d38",
  "type": "pool",
  "attributes": {
    "name": "WETH / USDC 0.01%",
    "address": "0x72ab388e2e2f6facef59e3c3fa2c4e29011c2d38",
    "pool_created_at": "2023-10-18T05:54:25Z",

    "reserve_in_usd": "7941466.2294",

    "base_token_price_usd": "3381.88",
    "quote_token_price_usd": "0.999674943383648",

    "volume_usd": {
      "m5": "190998.649050197",
      "m15": "729405.562970849",
      "m30": "2326455.57129021",
      "h1": "3628048.92837398",
      "h6": "24854960.4817796",
      "h24": "99041305.3441086"
    },

    "transactions": {
      "h24": {
        "buys": 54173,
        "sells": 63139,
        "buyers": 6851,
        "sellers": 8500
      }
    },

    "price_change_percentage": {
      "m5": "0.132",
      "h1": "-0.351",
      "h6": "-0.752",
      "h24": "-1.812"
    },

    "fdv_usd": "584218935.724045",
    "market_cap_usd": "583745830.099296"
  },
  "relationships": {
    "base_token": { ... },
    "quote_token": { ... },
    "dex": {
      "data": {
        "id": "pancakeswap-v3-base",
        "type": "dex"
      }
    }
  }
}
```

### Описание полей:

| Поле | Описание |
|------|----------|
| `name` | Название пула (пара токенов + комиссия) |
| `address` | Адрес смарт-контракта пула |
| `reserve_in_usd` | Общая ликвидность (TVL) в USD |
| `volume_usd` | Объем торгов за разные периоды |
| `transactions` | Количество покупок/продаж и уникальных участников |
| `price_change_percentage` | Процентное изменение цены за период |
| `base_token_price_usd` | Цена базового токена в USD |
| `quote_token_price_usd` | Цена котируемого токена в USD |
| `fdv_usd` | Fully Diluted Valuation (полная оценка) |
| `market_cap_usd` | Рыночная капитализация |

## Топ-5 самых ликвидных пулов на Base

По результатам тестирования (2025-11-08):

1. **WETH / USDC 0.05%** (Aerodrome Slipstream)
   - TVL: $35.59M
   - Volume 24h: $141.69M
   - Transactions: 40,752

2. **USDC / WETH 0.05%** (Uniswap V3)
   - TVL: $21.94M
   - Volume 24h: $36.38M
   - Transactions: 37,445

3. **WETH / USDC 0.01%** (PancakeSwap V3)
   - TVL: $7.94M
   - Volume 24h: $98.16M
   - Transactions: 116,585

4. **cbBTC / WETH 0.01%** (PancakeSwap V3)
   - TVL: $4.92M
   - Volume 24h: $72.12M
   - Transactions: 34,166

5. **ZEN / WETH 0.15%** (Aerodrome Slipstream)
   - TVL: $4.70M
   - Volume 24h: $16.64M
   - Transactions: 21,335

## Популярные DEX на Base

- **Aerodrome Slipstream** (`aerodrome-slipstream`)
- **Uniswap V3** (`uniswap-v3-base`)
- **PancakeSwap V3** (`pancakeswap-v3-base`)
- **Uniswap V4** (`uniswap-v4-base`)
- **SushiSwap V3** (`sushiswap-v3-base`)
- **Alien Base V3** (`alien-base-v3`)

## Примеры использования

### Python

```python
import requests

def get_top_pools_by_liquidity():
    url = "https://api.geckoterminal.com/api/v2/networks/base/pools"
    response = requests.get(url)
    data = response.json()

    # Сортировка по ликвидности
    pools = sorted(
        data['data'],
        key=lambda x: float(x['attributes']['reserve_in_usd']),
        reverse=True
    )

    for pool in pools[:5]:
        attrs = pool['attributes']
        print(f"{attrs['name']}: TVL ${float(attrs['reserve_in_usd']):,.0f}")

get_top_pools_by_liquidity()
```

### Bash

```bash
#!/bin/bash

# Топ-5 пулов по количеству транзакций
curl -s "https://api.geckoterminal.com/api/v2/networks/base/pools?sort=h24_tx_count_desc" | \
  jq -r '.data[0:5] | .[] | "\(.attributes.name) - \(.attributes.transactions.h24.buys + .attributes.transactions.h24.sells) txs"'
```

## Ограничения API

- **Rate Limiting**: API может иметь ограничения на количество запросов
- **503 Errors**: Некоторые параметры сортировки могут временно возвращать 503
- **Пагинация**: Результаты разбиты по страницам
- **Без API ключа**: API работает без авторизации, но может иметь ограничения

## Рекомендации

1. **Сортировка по ликвидности**: Используйте запрос без параметров сортировки и сортируйте локально по `reserve_in_usd`
2. **Обработка ошибок**: Всегда проверяйте статус ответа (503, 400)
3. **Кэширование**: Кэшируйте результаты, чтобы избежать излишних запросов
4. **Retry логика**: Добавьте повторные попытки при ошибках 503

## Полезные ссылки

- **GeckoTerminal Web**: https://www.geckoterminal.com/base/pools
- **API Base URL**: https://api.geckoterminal.com/api/v2
- **CoinGecko**: https://www.coingecko.com/

## Заключение

GeckoTerminal API предоставляет мощный инструмент для анализа DEX пулов на Base:
- ✅ Работает без API ключа
- ✅ Предоставляет детальные данные о ликвидности и объемах
- ✅ Поддерживает различные параметры сортировки
- ⚠️ Некоторые endpoint'ы могут быть нестабильны
- ⚠️ Требуется обработка ошибок и retry логика
