# Результаты тестирования WebSocket подписок на reth ноде

**Адрес ноды:** 80.209.241.37
**Дата проверки:** 2025-11-14
**Версия reth:** v1.9.2-74351d9/x86_64-unknown-linux-gnu/base/v0.2.0

---

## ✅ Что работает

### HTTP RPC (порт 8545)
- **Статус:** ✅ Работает отлично
- **Текущий блок:** 38,174,187 (0x24681eb)
- **Доступные методы:**
  - `web3_clientVersion` - ✅
  - `eth_blockNumber` - ✅
  - `eth_subscribe` - ⚠️ Распознается, но требует WebSocket

**Пример работающего запроса:**
```bash
curl http://80.209.241.37:8545 \
  -X POST \
  -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

**Ответ:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": "0x24681eb"
}
```

---

## ❌ Что НЕ работает

### WebSocket подключения
- **Порт 8545:** ❌ WebSocket handshake timeout
- **Порт 8546:** ❌ HTTP 403 Forbidden
- **Причина:** WebSocket не доступен извне или блокируется

**Попытка подключения к WebSocket:**
```bash
# Возвращает timeout
wscat -c ws://80.209.241.37:8545
wscat -c ws://80.209.241.37:8546
```

**Попытка eth_subscribe через HTTP:**
```bash
curl http://80.209.241.37:8545 \
  -X POST \
  -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_subscribe","params":["newHeads"],"id":1}'
```

**Ответ:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32603,
    "message": "Internal error"
  }
}
```

---

## 🔧 Решение проблемы

### Вариант 1: Включить WebSocket на существующем порту

Проверьте, как запущена ваша reth нода. Для включения WebSocket используйте следующие флаги:

```bash
reth node \
  --http \
  --http.addr 0.0.0.0 \
  --http.port 8545 \
  --http.api "eth,web3,net,debug,trace" \
  --ws \
  --ws.addr 0.0.0.0 \
  --ws.port 8546 \
  --ws.api "eth,web3,net,debug,trace" \
  --ws.origins "*"
```

**Важные параметры:**
- `--ws` - включает WebSocket сервер
- `--ws.addr 0.0.0.0` - слушает на всех интерфейсах (не только localhost)
- `--ws.port 8546` - порт для WebSocket (стандартный)
- `--ws.origins "*"` - разрешает подключения с любых origin (для продакшна используйте конкретные домены)
- `--ws.api` - доступные API методы

### Вариант 2: Открыть порт в файерволле

Если WebSocket уже включен, но недоступен извне:

```bash
# Для UFW
sudo ufw allow 8546/tcp
sudo ufw reload

# Для iptables
sudo iptables -A INPUT -p tcp --dport 8546 -j ACCEPT
sudo iptables-save > /etc/iptables/rules.v4

# Проверка открытых портов
sudo netstat -tlnp | grep 8546
```

### Вариант 3: Проверить конфигурацию NGINX/Apache (если используется reverse proxy)

Если перед reth стоит reverse proxy, нужно настроить WebSocket проксирование:

**Пример для NGINX:**
```nginx
server {
    listen 8546;
    server_name 80.209.241.37;

    location / {
        proxy_pass http://localhost:8546;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

---

## 🧪 Проверка после настройки

После настройки WebSocket используйте тестовые скрипты:

### 1. Проверка портов
```bash
node test_reth_ports.js
```

### 2. Тест WebSocket подписки (newHeads)
```bash
node test_reth_ws_8545.js
```

### 3. Быстрый тест с curl
```bash
# Upgrade запрос должен вернуть 101 Switching Protocols
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Host: 80.209.241.37:8546" \
  -H "Origin: http://80.209.241.37:8546" \
  http://80.209.241.37:8546/
```

### 4. Тест с websocat (если установлен)
```bash
# Установка websocat
wget https://github.com/vi/websocat/releases/download/v1.12.0/websocat.x86_64-unknown-linux-musl -O websocat
chmod +x websocat

# Тест подписки
echo '{"jsonrpc":"2.0","method":"eth_subscribe","params":["newHeads"],"id":1}' | \
  ./websocat ws://80.209.241.37:8546
```

---

## 📊 Ожидаемый результат после настройки

После успешной настройки вы должны увидеть:

```javascript
// Подключение
✅ WebSocket соединение установлено!

// Ответ на подписку
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": "0x1234..." // subscription ID
}

// События новых блоков
{
  "jsonrpc": "2.0",
  "method": "eth_subscription",
  "params": {
    "subscription": "0x1234...",
    "result": {
      "number": "0x24681ec",
      "hash": "0xabc...",
      "timestamp": "0x...",
      "miner": "0x...",
      ...
    }
  }
}
```

---

## 📝 Дополнительная информация

### Проверка конфигурации reth

1. **Найдите процесс reth:**
   ```bash
   ps aux | grep reth
   ```

2. **Проверьте логи:**
   ```bash
   journalctl -u reth -f
   # или
   tail -f /path/to/reth/logs
   ```

3. **Проверьте прослушиваемые порты:**
   ```bash
   sudo netstat -tlnp | grep reth
   ```

### Поддерживаемые типы подписок eth_subscribe

- `newHeads` - новые блоки
- `logs` - события смарт-контрактов
- `newPendingTransactions` - новые транзакции в mempool
- `syncing` - статус синхронизации

---

## ⚠️ Важные замечания для продакшна

1. **Безопасность:**
   - НЕ используйте `--ws.origins "*"` в продакшне
   - Ограничьте доступ через файерволл
   - Используйте WSS (WebSocket Secure) вместо WS

2. **Производительность:**
   - Ограничьте количество одновременных WebSocket подключений
   - Настройте rate limiting
   - Мониторьте нагрузку на ноду

3. **Мониторинг:**
   - Настройте алерты на разрыв WebSocket соединений
   - Отслеживайте количество активных подписок

---

## 🔗 Полезные ссылки

- [Reth documentation](https://reth.rs/)
- [Ethereum JSON-RPC specification](https://ethereum.github.io/execution-apis/api-documentation/)
- [WebSocket API](https://docs.infura.io/networks/ethereum/json-rpc-methods/subscription-methods)

---

## 📞 Следующие шаги

1. Проверьте команду запуска reth и добавьте флаги `--ws`
2. Откройте порт 8546 в файерволле
3. Перезапустите reth ноду
4. Запустите `node test_reth_ws_8545.js` для проверки
5. Если проблема сохраняется - проверьте логи reth

Если нужна помощь с конфигурацией, пришлите:
- Команду запуска reth (из `ps aux | grep reth`)
- Вывод `sudo netstat -tlnp | grep reth`
- Логи reth
