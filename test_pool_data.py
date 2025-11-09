#!/usr/bin/env python3
import requests

NODE_URL = "http://80.209.241.37:8545/"

def rpc_call(method, params):
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    response = requests.post(NODE_URL, json=payload, timeout=10)
    return response.json()

# Первый пул WETH/USDC
pool_addr = "0xdbc6998296caa1652a810dc8d3baf4a8294330f1"
weth_addr = "0x4200000000000000000000000000000000000006"
usdc_addr = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"

# Получаем balance WETH в пуле
weth_balance_data = "0x70a08231" + "0" * 24 + pool_addr[2:]
result = rpc_call("eth_call", [{"to": weth_addr, "data": weth_balance_data}, "latest"])
weth_balance_raw = int(result["result"], 16) if result.get("result") else 0
weth_balance = weth_balance_raw / 10**18

# Получаем balance USDC в пуле  
usdc_balance_data = "0x70a08231" + "0" * 24 + pool_addr[2:]
result = rpc_call("eth_call", [{"to": usdc_addr, "data": usdc_balance_data}, "latest"])
usdc_balance_raw = int(result["result"], 16) if result.get("result") else 0
usdc_balance = usdc_balance_raw / 10**6

print(f"Pool: {pool_addr}")
print(f"WETH balance: {weth_balance:,.2f} (~${weth_balance * 3429:,.2f})")
print(f"USDC balance: {usdc_balance:,.2f} (~${usdc_balance:,.2f})")
print(f"Total TVL: ~${weth_balance * 3429 + usdc_balance:,.2f}")
print(f"\nGeckoTerminal TVL: $1,322,248")
