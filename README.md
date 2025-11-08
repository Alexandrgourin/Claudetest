# Тестирование Reth ноды для Base сети

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
