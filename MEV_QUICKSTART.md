# MEV Quick Start Guide

## Быстрый старт с MEV на Base (Flashblocks)

### 1. Проверка доступности flashblocks

```bash
# Проверка что pending блоки возвращаются
curl -X POST http://80.209.241.37:8545/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "eth_getBlockByNumber",
    "params": ["pending", true],
    "id": 1
  }' | python3 -m json.tool
```

Если вернулся блок с транзакциями - flashblocks работают! ✅

### 2. Запуск Real-time Arbitrage Monitor

```bash
# Мониторинг на 60 минут
python3 realtime_arbitrage_monitor.py 60

# Короткая сессия на 5 минут
python3 realtime_arbitrage_monitor.py 5
```

**Что делает скрипт:**
- ⚡ Мониторит pending блоки через flashblocks
- 🔍 Ищет крупные swap транзакции в мемпуле
- 💰 Сканирует cross-DEX arbitrage возможности
- 📊 Выводит real-time alerts при обнаружении возможностей
- 📈 Рассчитывает потенциальную прибыль

### 3. Запуск Detailed Arbitrage Scan (периодически)

```bash
# Детальный скан всех пулов
python3 detailed_arbitrage_scan.py
```

Используйте для поиска текущих арбитражных возможностей между DEX.

---

## Рекомендуемая стратегия

### Tier 1: Начинающий (Low Risk)

**Капитал:** $5,000 - $20,000

**Стратегии:**
1. **Cross-DEX Arbitrage** - покупка токена на одном DEX, продажа на другом
2. **Backrunning** - размещение сделки после крупного swap'а
3. **Liquidations** - ликвидация undercollateralized позиций

**Ожидаемый доход:** $100-500/день

**Инструменты:**
- `realtime_arbitrage_monitor.py` - для обнаружения возможностей
- `detailed_arbitrage_scan.py` - для периодического сканирования

### Tier 2: Продвинутый (Medium Risk)

**Капитал:** $20,000 - $100,000 (или flash loans)

**Стратегии:**
1. **Flash Loan Arbitrage** - масштабирование арбитража без капитала
2. **JIT Liquidity** - добавление ликвидности перед крупной сделкой
3. **Triangular Arbitrage** - арбитраж через 3 пары

**Ожидаемый доход:** $500-2,000/день

**Требования:**
- Опыт с DeFi протоколами
- Понимание flash loans (Aave, Balancer)
- Быстрая инфраструктура

### Tier 3: Профессиональный (High Risk)

**Капитал:** $100,000+

**Стратегии:**
1. **Frontrunning** (⚠️ этически спорно)
2. **Complex MEV strategies**
3. **MEV-as-a-Service** - продажа доступа к инфраструктуре

**Ожидаемый доход:** $2,000-10,000+/день

**⚠️ Риски:** Высокая конкуренция, юридические вопросы

---

## Ключевые преимущества flashblocks

### Скорость
- ⚡ Видите транзакции на ~0.5-1 секунду раньше публичных RPC
- ⚡ Можете отреагировать до конкурентов

### Информация
- 👀 Полный доступ к pending транзакциям
- 👀 Видите крупные swaps до исполнения
- 👀 Можете предсказать изменения цен

### Контроль
- 🎯 Собственная нода = нет rate limits
- 🎯 Нет зависимости от Infura/Alchemy
- 🎯 Полный контроль над инфраструктурой

---

## Примеры прибыльных сценариев

### Сценарий 1: Cross-DEX Arbitrage

```
Обнаружено:
- Uniswap V3: WETH/USDC = $3000
- Aerodrome:  WETH/USDC = $3015 (на 0.5% выше)

Действие:
1. Купить 10 WETH на Uniswap за $30,000
2. Продать 10 WETH на Aerodrome за $30,150
3. Gross profit: $150
4. Fees (0.05% + 0.05%): $30
5. Gas (~$1): $1
6. Net profit: $119
```

**ROI:** 0.4% за одну сделку (30 секунд)

### Сценарий 2: Backrunning Large Swap

```
Flashblocks показывает:
- Pending swap: 100 ETH → USDC на Uniswap (push price down)
- Текущая цена: $3000
- Ожидаемая цена после swap: $2985

Действие:
1. Дождаться исполнения swap
2. Купить WETH на Uniswap по $2985
3. Продать WETH на Aerodrome по $3000
4. Profit: $15 * количество ETH
```

**ROI:** 0.5% за сделку

### Сценарий 3: Flash Loan Arbitrage

```
Обнаружен арбитраж 0.3% между DEX

Действие:
1. Flash loan 500,000 USDC (Aave)
2. Купить WETH на дешевом DEX
3. Продать WETH на дорогом DEX
4. Вернуть loan + 0.05% fee
5. Чистый profit: 0.25% * $500K = $1,250
```

**ROI:** $1,250 за одну транзакцию БЕЗ собственного капитала!

---

## Важные метрики для отслеживания

### Прибыльность
- **Win Rate** - % прибыльных сделок (цель: >70%)
- **Average Profit** - средняя прибыль на сделку
- **Daily P&L** - дневная прибыль/убыток

### Эффективность
- **Gas Spent** - потраченный gas
- **Failed Transactions** - неудачные транзакции
- **Latency** - задержка от обнаружения до исполнения

### Риски
- **Max Drawdown** - максимальная просадка
- **Exposure** - текущая экспозиция в рынок
- **Slippage** - среднее проскальзывание

---

## Мониторинг и алерты

### Настройка Telegram бота (опционально)

```python
# В realtime_arbitrage_monitor.py можно добавить:
import telegram

bot = telegram.Bot(token='YOUR_BOT_TOKEN')

def send_alert(message):
    bot.send_message(chat_id='YOUR_CHAT_ID', text=message)

# Использование:
if arbitrage_found:
    send_alert(f"🔥 Arbitrage found: {net_profit}% profit!")
```

### Grafana Dashboard

1. Экспортировать метрики в Prometheus
2. Настроить Grafana для визуализации
3. Создать алерты на критические события

---

## Безопасность

### Критически важно:

1. **Используйте hardware wallet** для хранения прибыли
2. **Multi-sig для управления** капиталом
3. **Circuit breakers** - автоматическая остановка при убытках
4. **Rate limiting** на RPC endpoint
5. **Мониторинг аномалий** в транзакциях

### Never:
- ❌ Не храните все средства на hot wallet
- ❌ Не давайте unlimited approvals
- ❌ Не запускайте непроверенный код на mainnet
- ❌ Не игнорируйте security audits

---

## Следующие шаги

1. ✅ Убедиться что flashblocks работают на вашей ноде
2. ✅ Запустить `realtime_arbitrage_monitor.py` на пару часов
3. ✅ Изучить найденные возможности
4. ✅ Протестировать на testnet (если доступен)
5. ✅ Начать с малых сумм на mainnet ($500-1000)
6. ✅ Постепенно масштабировать при успехе

---

## Полезные ссылки

### Документация:
- [MEV_OPPORTUNITIES.md](MEV_OPPORTUNITIES.md) - подробный анализ всех возможностей
- [README.md](README.md) - общая документация проекта

### Flash Loan Providers на Base:
- Aave V3: https://app.aave.com/
- Balancer: https://app.balancer.fi/

### MEV Research:
- Flashbots: https://docs.flashbots.net/
- MEV-Boost: https://boost.flashbots.net/

---

## Часто задаваемые вопросы

### Q: Сколько можно заработать?

**A:** Зависит от капитала и стратегии:
- С $5K: $100-500/день (консервативно)
- С $50K: $500-2,000/день (умеренно)
- С flash loans: $1,000+/день (агрессивно)

### Q: Какие риски?

**A:** Основные риски:
- Конкуренция с другими MEV ботами
- Убытки на gas при неудачных транзакциях
- Изменение цен между обнаружением и исполнением
- Smart contract exploits
- Регуляторные риски

### Q: Нужен ли большой капитал?

**A:** Нет! С flash loans можно начать БЕЗ капитала.
Но для обучения рекомендуется $1-5K.

### Q: Это законно?

**A:** Большинство стратегий легальны:
- ✅ Arbitrage
- ✅ Liquidations
- ✅ Backrunning
- ⚠️ Frontrunning (серая зона)
- ❌ Sandwich attacks (вредит пользователям)

Консультируйтесь с юристом!

---

## Контакты и поддержка

Для вопросов и предложений:
- GitHub Issues
- MEV research communities
- DeFi developer forums

**Успехов в MEV! 🚀💰**
