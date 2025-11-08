#!/bin/bash

# Тестовый скрипт для работы с GeckoTerminal API
# API для получения данных о DEX пулах на Base

API_BASE="https://api.geckoterminal.com/api/v2"
NETWORK="base"

echo "========================================================================"
echo "GeckoTerminal API - Тестирование для Base Network"
echo "========================================================================"
echo ""

# 1. Топ 5 пулов по количеству транзакций за 24 часа
echo "1. ТОП-5 ПУЛОВ ПО КОЛИЧЕСТВУ ТРАНЗАКЦИЙ ЗА 24 ЧАСА:"
echo "------------------------------------------------------------------------"
curl -s "${API_BASE}/networks/${NETWORK}/pools?sort=h24_tx_count_desc&page=1" | \
  jq -r '.data[0:5] | .[] | "• \(.attributes.name)\n  Reserve: $\(.attributes.reserve_in_usd | tonumber | floor)\n  Vol 24h: $\(.attributes.volume_usd.h24 | tonumber | floor)\n  Transactions: \(.attributes.transactions.h24.buys + .attributes.transactions.h24.sells)\n  Address: \(.attributes.address)\n"'
echo ""

# 2. Доступные параметры сортировки
echo "2. ДОСТУПНЫЕ ПАРАМЕТРЫ СОРТИРОВКИ:"
echo "------------------------------------------------------------------------"
echo "✓ h24_tx_count_desc    - По количеству транзакций за 24 часа"
echo "✗ h24_volume_usd_desc  - По объему торгов за 24 часа (иногда 503)"
echo "✗ h6_volume_usd_desc   - По объему торгов за 6 часов"
echo "✗ h1_volume_usd_desc   - По объему торгов за 1 час (400 Bad Request)"
echo "✗ m5_volume_usd_desc   - По объему торгов за 5 минут"
echo ""
echo "Примечание: Некоторые параметры могут быть временно недоступны"
echo "или требуют дополнительных параметров."
echo ""

# 3. Информация о доступных полях
echo "3. ДОСТУПНЫЕ ПОЛЯ В ОТВЕТЕ:"
echo "------------------------------------------------------------------------"
echo "• reserve_in_usd       - Общая ликвидность (TVL) в USD"
echo "• volume_usd           - Объем торгов (m5, m15, m30, h1, h6, h24)"
echo "• transactions         - Количество покупок/продаж за период"
echo "• price_change_percentage - Изменение цены за период"
echo "• base_token_price_usd - Цена базового токена в USD"
echo "• quote_token_price_usd - Цена котируемого токена в USD"
echo ""

# 4. Пример запроса напрямую
echo "4. ПРИМЕР ПРЯМОГО ЗАПРОСА:"
echo "------------------------------------------------------------------------"
echo "curl -s '${API_BASE}/networks/${NETWORK}/pools?page=1' | jq ."
echo ""

echo "========================================================================"
echo "Тестирование завершено!"
echo "========================================================================"
