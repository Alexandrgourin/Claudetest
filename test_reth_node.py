#!/usr/bin/env python3
"""
Тестовый скрипт для проверки reth ноды Base
"""

import requests
import json
from datetime import datetime

NODE_URL = "http://80.209.241.37:8545/"

def rpc_call(method, params=None, id=1):
    """Выполнить JSON-RPC запрос"""
    if params is None:
        params = []

    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": id
    }

    try:
        response = requests.post(NODE_URL, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def hex_to_int(hex_str):
    """Конвертировать hex в int"""
    try:
        return int(hex_str, 16)
    except:
        return 0

def wei_to_eth(wei):
    """Конвертировать wei в ETH"""
    return wei / 10**18

def wei_to_gwei(wei):
    """Конвертировать wei в gwei"""
    return wei / 10**9

def main():
    print("=" * 50)
    print("Тестирование reth ноды Base")
    print("=" * 50)
    print()

    # 1. Версия клиента
    print("1. Версия клиента:")
    result = rpc_call("web3_clientVersion")
    if "result" in result:
        print(f"   {result['result']}")
    print()

    # 2. Chain ID
    print("2. Chain ID (должен быть 8453 для Base Mainnet):")
    result = rpc_call("eth_chainId")
    if "result" in result:
        chain_id_hex = result['result']
        chain_id_dec = hex_to_int(chain_id_hex)
        print(f"   Hex: {chain_id_hex}")
        print(f"   Dec: {chain_id_dec}")
        if chain_id_dec == 8453:
            print("   ✓ Правильная сеть (Base Mainnet)")
        else:
            print(f"   ⚠ Неожиданный Chain ID: {chain_id_dec}")
    print()

    # 3. Номер блока
    print("3. Последний блок:")
    result = rpc_call("eth_blockNumber")
    if "result" in result:
        block_hex = result['result']
        block_dec = hex_to_int(block_hex)
        print(f"   Hex: {block_hex}")
        print(f"   Dec: {block_dec:,}")
    print()

    # 4. Статус синхронизации
    print("4. Статус синхронизации:")
    result = rpc_call("eth_syncing")
    if "result" in result:
        syncing = result['result']
        if syncing is False:
            print("   ✓ Нода полностью синхронизирована")
        else:
            print(f"   ⚠ Нода синхронизируется:")
            if isinstance(syncing, dict):
                print(f"      Current Block: {hex_to_int(syncing.get('currentBlock', '0x0')):,}")
                print(f"      Highest Block: {hex_to_int(syncing.get('highestBlock', '0x0')):,}")
    print()

    # 5. Версия сети
    print("5. Версия сети:")
    result = rpc_call("net_version")
    if "result" in result:
        print(f"   {result['result']}")
    print()

    # 6. Цена газа
    print("6. Текущая цена газа:")
    result = rpc_call("eth_gasPrice")
    if "result" in result:
        gas_price_hex = result['result']
        gas_price_wei = hex_to_int(gas_price_hex)
        gas_price_gwei = wei_to_gwei(gas_price_wei)
        print(f"   Hex: {gas_price_hex}")
        print(f"   Wei: {gas_price_wei:,}")
        print(f"   Gwei: {gas_price_gwei:.6f}")
    print()

    # 7. Количество пиров
    print("7. Количество подключенных пиров:")
    result = rpc_call("net_peerCount")
    if "result" in result:
        peer_count_hex = result['result']
        peer_count_dec = hex_to_int(peer_count_hex)
        print(f"   Hex: {peer_count_hex}")
        print(f"   Dec: {peer_count_dec}")
    print()

    # 8. Версия протокола
    print("8. Версия протокола Ethereum:")
    result = rpc_call("eth_protocolVersion")
    if "result" in result:
        protocol_version = hex_to_int(result['result'])
        print(f"   {protocol_version}")
    print()

    # 9. Информация о последнем блоке
    print("9. Информация о последнем блоке:")
    result = rpc_call("eth_getBlockByNumber", ["latest", False])
    if "result" in result and result['result']:
        block = result['result']
        timestamp = hex_to_int(block.get('timestamp', '0x0'))
        dt = datetime.fromtimestamp(timestamp)

        print(f"   Hash: {block.get('hash', 'N/A')}")
        print(f"   Number: {hex_to_int(block.get('number', '0x0')):,}")
        print(f"   Timestamp: {timestamp} ({dt.strftime('%Y-%m-%d %H:%M:%S')})")
        print(f"   Transactions: {len(block.get('transactions', []))}")

        gas_used = hex_to_int(block.get('gasUsed', '0x0'))
        gas_limit = hex_to_int(block.get('gasLimit', '0x0'))
        gas_usage_percent = (gas_used / gas_limit * 100) if gas_limit > 0 else 0

        print(f"   Gas Used: {gas_used:,} ({gas_usage_percent:.2f}%)")
        print(f"   Gas Limit: {gas_limit:,}")
        print(f"   Base Fee: {wei_to_gwei(hex_to_int(block.get('baseFeePerGas', '0x0'))):.4f} gwei")
    print()

    # 10. Проверка доступности методов
    print("10. Проверка доступных RPC методов:")

    methods_to_check = [
        ("eth_call", [{"to": "0x0000000000000000000000000000000000000000", "data": "0x"}, "latest"]),
        ("eth_getLogs", [{"fromBlock": "latest", "toBlock": "latest"}]),
        ("eth_getBalance", ["0x0000000000000000000000000000000000000000", "latest"]),
        ("eth_getCode", ["0x0000000000000000000000000000000000000000", "latest"]),
        ("eth_estimateGas", [{"to": "0x0000000000000000000000000000000000000000"}]),
    ]

    for method, params in methods_to_check:
        result = rpc_call(method, params)
        status = "✓" if "result" in result else "✗"
        print(f"   {method}: {status}")
        if "error" in result:
            print(f"      Error: {result['error'].get('message', result['error'])}")

    print()
    print("=" * 50)
    print("Тестирование завершено!")
    print("=" * 50)

if __name__ == "__main__":
    main()
