#!/usr/bin/env python3
"""Debug script to understand pagination issues"""

import os
import asyncio
import aiohttp
from datetime import datetime
import json

HELIUS_KEY = os.getenv("HELIUS_KEY", "09cd02b2-f35d-4d54-ac9b-a9033919d6ee")
WALLET = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"

async def debug_pagination():
    """Test different approaches to understand the issue"""
    
    async with aiohttp.ClientSession() as session:
        
        # Test 1: Basic query without type filter
        print("\n=== TEST 1: No type filter ===")
        url = f"https://api.helius.xyz/v0/addresses/{WALLET}/transactions"
        params = {
            "api-key": HELIUS_KEY,
            "limit": 100,
            "maxSupportedTransactionVersion": "0"
        }
        
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            print(f"Status: {resp.status}")
            print(f"Results: {len(data) if isinstance(data, list) else 'Error'}")
            if isinstance(data, list) and len(data) > 0:
                print(f"First tx: {data[0].get('signature')[:20]}...")
                print(f"Last tx: {data[-1].get('signature')[:20]}...")
                print(f"Types found: {set(tx.get('type', 'NONE') for tx in data[:10])}")
        
        # Test 2: With SWAP filter
        print("\n=== TEST 2: With type=SWAP ===")
        params["type"] = "SWAP"
        
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            print(f"Status: {resp.status}")
            print(f"Results: {len(data) if isinstance(data, list) else 'Error'}")
            if isinstance(data, list) and len(data) > 0:
                print(f"Sources: {set(tx.get('source', 'NONE') for tx in data)}")
        
        # Test 3: Check pagination with small limit
        print("\n=== TEST 3: Pagination test (limit=10) ===")
        params = {
            "api-key": HELIUS_KEY,
            "limit": 10,
            "type": "SWAP",
            "maxSupportedTransactionVersion": "0"
        }
        
        total_pages = 0
        total_txs = 0
        before_sig = None
        
        for page in range(5):  # Test first 5 pages
            if before_sig:
                params["before"] = before_sig
                
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                if isinstance(data, list) and len(data) > 0:
                    total_pages += 1
                    total_txs += len(data)
                    print(f"Page {page + 1}: {len(data)} txs, last sig: {data[-1]['signature'][:20]}...")
                    before_sig = data[-1]['signature']
                    
                    # Check if we got less than requested
                    if len(data) < 10:
                        print(f"  -> Got less than limit ({len(data)} < 10), pagination would stop!")
                        break
                else:
                    print(f"Page {page + 1}: No data or error")
                    break
                    
        print(f"Total from 5 pages: {total_txs} transactions")
        
        # Test 4: Check total count endpoint if available
        print("\n=== TEST 4: Check if there's a count endpoint ===")
        # Try different potential endpoints
        count_url = f"https://api.helius.xyz/v0/addresses/{WALLET}/transactions/count"
        try:
            async with session.get(count_url, params={"api-key": HELIUS_KEY}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"Total count: {data}")
                else:
                    print(f"Count endpoint not available (status: {resp.status})")
        except:
            print("Count endpoint doesn't exist")
            
        # Test 5: Get all transaction signatures using RPC
        print("\n=== TEST 5: Get signatures via RPC ===")
        rpc_url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}"
        
        # Get total signatures count
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [WALLET, {"limit": 1000}]
        }
        
        async with session.post(rpc_url, json=payload) as resp:
            result = await resp.json()
            if "result" in result:
                print(f"RPC signatures found: {len(result['result'])}")
                if len(result['result']) == 1000:
                    print("  -> Hit 1000 limit, there are likely more!")
            else:
                print(f"RPC error: {result.get('error', 'Unknown')}")
                
        # Test 6: Check UNKNOWN transactions
        print("\n=== TEST 6: Check type=UNKNOWN ===")
        params = {
            "api-key": HELIUS_KEY,
            "limit": 100,
            "type": "UNKNOWN",
            "maxSupportedTransactionVersion": "0"
        }
        
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            print(f"Status: {resp.status}")
            print(f"UNKNOWN type results: {len(data) if isinstance(data, list) else 'Error'}")
            
            if isinstance(data, list) and len(data) > 0:
                # Check if any look like swaps
                swap_like = []
                for tx in data[:20]:
                    if tx.get('tokenTransfers') and len(tx.get('tokenTransfers', [])) > 1:
                        swap_like.append(tx['signature'])
                        
                print(f"Found {len(swap_like)} UNKNOWN txs that look like swaps in first 20")
                
        # Test 7: Try without maxSupportedTransactionVersion
        print("\n=== TEST 7: Without maxSupportedTransactionVersion ===")
        params = {
            "api-key": HELIUS_KEY,
            "limit": 100,
            "type": "SWAP"
        }
        
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            print(f"Status: {resp.status}")
            print(f"Results without version param: {len(data) if isinstance(data, list) else 'Error'}")

if __name__ == "__main__":
    asyncio.run(debug_pagination()) 