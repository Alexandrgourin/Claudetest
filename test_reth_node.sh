#!/bin/bash

# Тестовый скрипт для проверки reth ноды Base
# URL ноды
NODE_URL="http://80.209.241.37:8545/"

echo "=========================================="
echo "Тестирование reth ноды Base"
echo "=========================================="
echo ""

# Функция для выполнения JSON-RPC запроса
rpc_call() {
    local method=$1
    local params=$2
    local id=$3

    curl -s -X POST "$NODE_URL" \
        -H "Content-Type: application/json" \
        --data "{\"jsonrpc\":\"2.0\",\"method\":\"$method\",\"params\":$params,\"id\":$id}"
}

# 1. Версия клиента
echo "1. Версия клиента:"
rpc_call "web3_clientVersion" "[]" 1 | jq -r '.result'
echo ""

# 2. Chain ID
echo "2. Chain ID (должен быть 8453 для Base Mainnet):"
CHAIN_ID=$(rpc_call "eth_chainId" "[]" 2 | jq -r '.result')
echo "Hex: $CHAIN_ID"
echo "Dec: $((CHAIN_ID))"
echo ""

# 3. Номер блока
echo "3. Последний блок:"
BLOCK_NUM=$(rpc_call "eth_blockNumber" "[]" 3 | jq -r '.result')
echo "Hex: $BLOCK_NUM"
echo "Dec: $((BLOCK_NUM))"
echo ""

# 4. Статус синхронизации
echo "4. Статус синхронизации:"
SYNCING=$(rpc_call "eth_syncing" "[]" 4 | jq -r '.result')
if [ "$SYNCING" = "false" ]; then
    echo "✓ Нода полностью синхронизирована"
else
    echo "⚠ Нода синхронизируется: $SYNCING"
fi
echo ""

# 5. Версия сети
echo "5. Версия сети:"
rpc_call "net_version" "[]" 5 | jq -r '.result'
echo ""

# 6. Цена газа
echo "6. Текущая цена газа:"
GAS_PRICE=$(rpc_call "eth_gasPrice" "[]" 6 | jq -r '.result')
echo "Hex: $GAS_PRICE"
GAS_WEI=$((GAS_PRICE))
GAS_GWEI=$(echo "scale=4; $GAS_WEI / 1000000000" | bc)
echo "Wei: $GAS_WEI"
echo "Gwei: $GAS_GWEI"
echo ""

# 7. Количество пиров
echo "7. Количество подключенных пиров:"
PEER_COUNT=$(rpc_call "net_peerCount" "[]" 7 | jq -r '.result')
echo "Hex: $PEER_COUNT"
echo "Dec: $((PEER_COUNT))"
echo ""

# 8. Версия протокола
echo "8. Версия протокола Ethereum:"
rpc_call "eth_protocolVersion" "[]" 8 | jq -r '.result'
echo ""

# 9. Информация о последнем блоке
echo "9. Информация о последнем блоке:"
BLOCK_INFO=$(rpc_call "eth_getBlockByNumber" "[\"latest\",false]" 9)
echo "Hash: $(echo $BLOCK_INFO | jq -r '.result.hash')"
echo "Timestamp: $(echo $BLOCK_INFO | jq -r '.result.timestamp') ($(($(echo $BLOCK_INFO | jq -r '.result.timestamp'))))"
echo "Transactions: $(echo $BLOCK_INFO | jq -r '.result.transactions | length')"
echo "Gas Used: $(echo $BLOCK_INFO | jq -r '.result.gasUsed') ($(($(echo $BLOCK_INFO | jq -r '.result.gasUsed'))))"
echo "Gas Limit: $(echo $BLOCK_INFO | jq -r '.result.gasLimit') ($(($(echo $BLOCK_INFO | jq -r '.result.gasLimit'))))"
echo ""

# 10. Проверка доступности методов
echo "10. Проверка доступных RPC методов:"
echo -n "   eth_call: "
rpc_call "eth_call" "[{\"to\":\"0x0000000000000000000000000000000000000000\",\"data\":\"0x\"},\"latest\"]" 10 > /dev/null && echo "✓" || echo "✗"

echo -n "   eth_getLogs: "
rpc_call "eth_getLogs" "[{\"fromBlock\":\"latest\",\"toBlock\":\"latest\"}]" 11 > /dev/null && echo "✓" || echo "✗"

echo -n "   eth_getTransactionReceipt: "
rpc_call "eth_getTransactionReceipt" "[\"0x0000000000000000000000000000000000000000000000000000000000000000\"]" 12 > /dev/null && echo "✓" || echo "✗"

echo ""
echo "=========================================="
echo "Тестирование завершено!"
echo "=========================================="
