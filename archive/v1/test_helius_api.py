#!/usr/bin/env python3
"""
Test Helius API format
"""

import asyncio
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

async def test_helius():
    helius_key = os.getenv('HELIUS_KEY')
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    async with aiohttp.ClientSession() as session:
        # Test 1: Basic transaction fetch
        print("1. Testing basic transaction fetch...")
        url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
        params = {"api-key": helius_key}
        
        async with session.get(url, params=params) as response:
            print(f"   Status: {response.status}")
            if response.status == 200:
                data = await response.json()
                print(f"   Found {len(data)} transactions")
            else:
                text = await response.text()
                print(f"   Error: {text}")
        
        # Test 2: With type parameter
        print("\n2. Testing with type=SWAP...")
        params = {"api-key": helius_key, "type": "SWAP"}
        
        async with session.get(url, params=params) as response:
            print(f"   Status: {response.status}")
            if response.status == 200:
                data = await response.json()
                print(f"   Found {len(data)} swaps")
        
        # Test 3: Check enhanced transaction endpoint
        print("\n3. Testing enhanced endpoint...")
        url2 = f"https://api.helius.xyz/v0/transactions"
        params = {"api-key": helius_key, "account": wallet}
        
        async with session.get(url2, params=params) as response:
            print(f"   Status: {response.status}")
            if response.status != 200:
                text = await response.text()
                print(f"   Response: {text}")

asyncio.run(test_helius())