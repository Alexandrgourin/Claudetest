# Анализ WebSocket и альтернатив на Base Node

## Конфигурация ноды

```
URL: http://80.209.241.37:8545/
WebSocket: ws://80.209.241.37:8545/ (HTTP 403 - НЕДОСТУПЕН)
Версия: reth/v1.9.0-84785f0/x86_64-unknown-linux-gnu/base/v0.1.16
```

## Результаты тестирования

### ❌ WebSocket подключение

```
Статус: HTTP 403 Forbidden
Причина: WebSocket отключен в конфигурации reth
```

**Тестировались:**
- ❌ `eth_subscribe("newHeads")` - новые блоки
- ❌ `eth_subscribe("newPendingTransactions")` - pending транзакции
- ❌ `eth_subscribe("logs")` - события контрактов

**Вывод:** WebSocket полностью недоступен.

### ✅ HTTP Фильтры (частичная поддержка)

#### 1. Block Filter (eth_newBlockFilter)

**Статус:** ✅ РАБОТАЕТ

**Результаты (30 секунд):**
```
Блоков получено: 16
Диапазон: 37,965,468 -> 37,965,483
Средний интервал: 1875ms (~2 секунды)
```

**Выводы:**
- ✅ Фильтр работает стабильно
- ⚠️ Показывает ТОЛЬКО финализированные блоки (~2 сек)
- ❌ НЕ показывает flashblocks (200ms)
- Latency: ~200ms (polling interval)

**Пример использования:**
```python
# Создать фильтр
filter_id = rpc_call("eth_newBlockFilter")["result"]

# Polling loop
while True:
    changes = rpc_call("eth_getFilterChanges", [filter_id])
    for block_hash in changes["result"]:
        # Обработать новый блок
        process_block(block_hash)
    time.sleep(0.2)  # Polling каждые 200ms
```

#### 2. Pending Transaction Filter (eth_newPendingTransactionFilter)

**Статус:** ❌ НЕ РАБОТАЕТ

**Результаты (10 секунд):**
```
Pending транзакций: 0
```

**Вывод:** Фильтр создается, но не возвращает транзакции. Либо не поддерживается, либо отключен.

#### 3. Log Filter (eth_newFilter для событий)

**Статус:** ✅ РАБОТАЕТ ОТЛИЧНО

**Результаты (20 секунд, Swap события в WETH/USDC):**
```
Swap событий: 23
Диапазон блоков: 37,965,489 -> 37,965,498 (9 блоков)
Средняя активность: ~2.5 свопов на блок
```

**Выводы:**
- ✅ Фильтр работает идеально
- ✅ Можно мониторить Swap/Mint/Burn события
- ✅ Полезно для отслеживания активности в пулах
- Latency: ~500ms (polling interval)

**Пример использования:**
```python
SWAP_EVENT = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
POOL_ADDRESS = "0xb2cc224c1c9fee385f8ad6a55b4d94e92359dc59"

# Создать фильтр для Swap событий
filter_id = rpc_call("eth_newFilter", [{
    "address": POOL_ADDRESS,
    "topics": [SWAP_EVENT]
}])["result"]

# Polling loop
while True:
    changes = rpc_call("eth_getFilterChanges", [filter_id])
    for log in changes["result"]:
        # Обработать Swap событие
        process_swap(log)
    time.sleep(0.5)
```

## Критические ограничения

### 1. Нет доступа к flashblocks через фильтры

**Проблема:**
- HTTP фильтры показывают только финализированные блоки (~2 сек)
- Flashblocks (pending блоки каждые 200ms) НЕ доступны через фильтры
- Единственный способ мониторить flashblocks: polling `eth_getBlockByNumber('pending')`

**Сравнение:**

| Метод | Интервал | Latency | Доступ к flashblocks |
|-------|----------|---------|---------------------|
| WebSocket (недоступен) | ~10ms | <10ms | ✅ Да (теоретически) |
| HTTP Block Filter | ~1875ms | ~200ms | ❌ Нет |
| HTTP Polling 'pending' | custom | ~200ms | ✅ Да |

### 2. Нет доступа к pending транзакциям

**Проблема:**
- `eth_newPendingTransactionFilter` не возвращает транзакции
- Невозможно подписаться на новые pending транзакции
- Единственный способ: парсить `eth_getBlockByNumber('pending', true)` для списка транзакций

### 3. Polling overhead

**Проблема:**
- Все фильтры требуют polling (pull вместо push)
- Минимальный realistic polling interval: ~200ms
- Дополнительная latency: +200-500ms

## Рекомендации для арбитража

### Стратегия 1: HTTP Polling 'pending' блока (ТЕКУЩАЯ)

**Использовать:**
```python
while True:
    # Получаем pending block
    pending = eth.getBlockByNumber('pending', False)

    # Делаем quote
    quote = eth_call({...}, 'pending')

    # Принимаем решение
    if profitable(quote):
        execute_arbitrage()

    time.sleep(0.2)  # Polling каждые 200ms
```

**Плюсы:**
- ✅ Доступ к flashblocks (pending)
- ✅ Простая реализация
- ✅ Работает сейчас

**Минусы:**
- ❌ High latency (~1500-1700ms для eth_call)
- ❌ Race condition (блок меняется за время eth_call)
- ❌ Требует safety margin 3-5%

### Стратегия 2: Комбо - Block Filter + Polling

**Использовать:**
```python
# Создаем block filter для финализированных блоков
block_filter = eth_newBlockFilter()

while True:
    # Проверяем финализированные блоки
    new_blocks = eth_getFilterChanges(block_filter)

    if new_blocks:
        # Новый финализированный блок - агрессивно чекаем pending
        for i in range(5):  # 5 попыток за 1 секунду
            pending = eth.getBlockByNumber('pending', False)
            # ... проверка арбитража
            time.sleep(0.2)
    else:
        # Спокойный режим
        time.sleep(1.0)
```

**Плюсы:**
- ✅ Меньше запросов в спокойное время
- ✅ Агрессивный мониторинг после новых блоков
- ✅ Баланс между latency и нагрузкой

**Минусы:**
- ❌ Все еще high latency для eth_call
- ❌ Race condition сохраняется

### Стратегия 3: Log Filter для триггеров + Quote on-demand

**Использовать:**
```python
# Создаем фильтры для Swap событий в интересных пулах
swap_filter = eth_newFilter({
    "address": [pool1, pool2, pool3],
    "topics": [SWAP_EVENT]
})

while True:
    # Проверяем новые Swap события
    swaps = eth_getFilterChanges(swap_filter)

    for swap in swaps:
        # Swap произошел -> проверяем возможность обратного арбитража
        pool = swap["address"]
        quote = get_quote_for_reverse_swap(pool)

        if profitable(quote):
            execute_arbitrage()

    time.sleep(0.5)
```

**Плюсы:**
- ✅ Реактивная стратегия (реагируем на события)
- ✅ Меньше "холостых" запросов
- ✅ Log filter работает отлично

**Минусы:**
- ❌ Упускаем возможности которые не triggered свопами
- ❌ Latency ~500ms + eth_call latency

## Как включить WebSocket на ноде

Если у вас есть доступ к конфигурации reth ноды, добавьте флаги:

```bash
reth node \
  --http \
  --http.addr 0.0.0.0 \
  --http.port 8545 \
  --ws \                        # Включить WebSocket
  --ws.addr 0.0.0.0 \           # Слушать на всех интерфейсах
  --ws.port 8546 \              # WebSocket порт (можно использовать 8545)
  --ws.origins '*' \            # CORS origins (осторожно в production!)
  --ws.api eth,net,web3 \       # Доступные API
  ...
```

После включения WebSocket:
- URL: `ws://80.209.241.37:8546/` (или 8545 если на том же порту)
- Доступные подписки:
  - `eth_subscribe("newHeads")` - новые блоки (включая flashblocks!)
  - `eth_subscribe("newPendingTransactions")` - pending транзакции
  - `eth_subscribe("logs", {...})` - события контрактов

## Сравнительная таблица

| Фича | WebSocket | HTTP Filter | HTTP Polling |
|------|-----------|-------------|--------------|
| **Доступность** | ❌ 403 | ✅ Работает | ✅ Работает |
| **Flashblocks** | ✅ Да* | ❌ Нет | ✅ Да |
| **Latency** | <10ms | ~200ms | ~200ms |
| **Pending TX** | ✅ Да* | ❌ Нет | ✅ Да |
| **Events (logs)** | ✅ Да* | ✅ Да | ✅ Да |
| **Overhead** | Низкий | Средний | Высокий |
| **Надежность** | Высокая* | Средняя | Высокая |
| **Сложность** | Средняя | Низкая | Низкая |

*если был бы доступен

## Итоговые выводы

### Для текущей ситуации (WebSocket недоступен):

1. ✅ **Использовать HTTP polling** для мониторинга pending блоков
   - Polling interval: 200-300ms
   - Safety margin: 3-5%
   - Минимальная прибыль: 5-7%

2. ✅ **Использовать Log Filter** для мониторинга активности пулов
   - Отслеживать Swap события
   - Реагировать на изменения ликвидности
   - Polling interval: 500ms

3. ⚠️ **Принять ограничения:**
   - eth_call latency: 1500-1700ms
   - Race condition: неизбежна
   - Подходит только для MFT арбитража (не HFT)

### Для будущего (если включат WebSocket):

1. 🚀 **Перейти на WebSocket** для всех подписок
   - Latency: <100ms (вместо 1500ms)
   - Real-time flashblocks
   - Push вместо pull

2. 🚀 **Снизить safety margin:**
   - С 3-5% до 1-2%
   - Возможен HFT арбитраж
   - Более конкурентная стратегия

## Файлы в проекте

- `test_websocket_subscriptions.py` - тесты WebSocket (получили 403)
- `test_http_filters.py` - тесты HTTP фильтров (частично работают)
- `arbitrage_safe_quote.py` - production решение для текущей ситуации
- `WEBSOCKET_ANALYSIS.md` - этот документ
