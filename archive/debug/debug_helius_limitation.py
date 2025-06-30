#!/usr/bin/env python3
"""Debug Helius API limitations"""

import os
import asyncio
import aiohttp
from datetime import datetime

HELIUS_KEY = os.getenv("HELIUS_KEY", "09cd02b2-f35d-4d54-ac9b-a9033919d6ee")
WALLET = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"

async def test_helius_limits():
    """Test various Helius API approaches"""
    
    async with aiohttp.ClientSession() as session:
        
        # Test 1: Check date range of returned transactions
        print("=== Test 1: Date range of Helius transactions ===")
        url = f"https://api.helius.xyz/v0/addresses/{WALLET}/transactions"
        params = {
            "api-key": HELIUS_KEY,
            "limit": 100,
            "maxSupportedTransactionVersion": "0"
        }
        
        all_dates = []
        before_sig = None
        
        for page in range(10):
            if before_sig:
                params["before"] = before_sig
                
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                
                if isinstance(data, list) and len(data) > 0:
                    for tx in data:
                        if 'timestamp' in tx:
                            all_dates.append(datetime.fromtimestamp(tx['timestamp']))
                    
                    before_sig = data[-1].get('signature')
                    
                    if len(data) < 100:
                        break
                else:
                    break
                    
        if all_dates:
            all_dates.sort()
            print(f"Earliest transaction: {all_dates[0]}")
            print(f"Latest transaction: {all_dates[-1]}")
            print(f"Date range: {(all_dates[-1] - all_dates[0]).days} days")
            print(f"Total transactions returned: {len(all_dates)}")
        
        # Test 2: Try with different parameters
        print("\n=== Test 2: Testing different parameter combinations ===")
        
        test_cases = [
            {"name": "No params", "params": {}},
            {"name": "Large limit", "params": {"limit": 1000}},
            {"name": "With commitment", "params": {"commitment": "finalized"}},
            {"name": "Without version", "params": {"limit": 100}},
        ]
        
        for test in test_cases:
            params = {"api-key": HELIUS_KEY}
            params.update(test["params"])
            
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        print(f"{test['name']}: {len(data)} transactions")
                    else:
                        print(f"{test['name']}: Error - {data}")
                else:
                    print(f"{test['name']}: HTTP {resp.status}")
                    
        # Test 3: Check if there's documentation about limits
        print("\n=== Test 3: Checking for limit information ===")
        
        # Try to get the oldest transaction from RPC and check if Helius has it
        rpc_url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}"
        
        # Get signatures from the end
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [
                WALLET,
                {
                    "limit": 1000,
                    "commitment": "finalized"
                }
            ]
        }
        
        # Get signatures from multiple pages to find old ones
        oldest_sig = None
        before_sig = None
        
        for i in range(9):  # Get to page 9 to find old transactions
            if before_sig:
                payload["params"][1]["before"] = before_sig
                
            async with session.post(rpc_url, json=payload) as resp:
                result = await resp.json()
                sigs = result.get("result", [])
                if sigs:
                    before_sig = sigs[-1]["signature"]
                    if i == 8:  # Use a signature from page 9
                        oldest_sig = sigs[0]["signature"]
                        
        if oldest_sig:
            print(f"\nTesting old transaction: {oldest_sig[:20]}...")
            
            # Try to get this specific transaction from Helius
            tx_url = f"https://api.helius.xyz/v0/transactions/{oldest_sig}"
            params = {"api-key": HELIUS_KEY}
            
            async with session.get(tx_url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    timestamp = data.get('timestamp')
                    if timestamp:
                        date = datetime.fromtimestamp(timestamp)
                        print(f"Old transaction found! Date: {date}")
                    else:
                        print("Old transaction found but no timestamp")
                else:
                    print(f"Old transaction not found in Helius (HTTP {resp.status})")
                    
        # Test 4: Check if pagination continues beyond what we see
        print("\n=== Test 4: Force pagination beyond visible limit ===")
        
        # Get the last signature from our 196 transactions
        params = {
            "api-key": HELIUS_KEY,
            "limit": 100,
            "maxSupportedTransactionVersion": "0"
        }
        
        last_sig = None
        for page in range(2):
            if last_sig:
                params["before"] = last_sig
                
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                if isinstance(data, list) and data:
                    last_sig = data[-1]["signature"]
                    
        if last_sig:
            print(f"Last signature from enhanced API: {last_sig[:20]}...")
            
            # Try to continue pagination
            params["before"] = last_sig
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                if isinstance(data, list):
                    print(f"Continuing pagination: {len(data)} more transactions")
                else:
                    print(f"Pagination stopped: {data}")

if __name__ == "__main__":
    asyncio.run(test_helius_limits()) 