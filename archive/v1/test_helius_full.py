#!/usr/bin/env python3
"""Test getting ALL transactions from Helius"""

import asyncio
import os
import aiohttp
from datetime import datetime

async def test_full_history():
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    helius_key = os.getenv('HELIUS_KEY')
    
    if not helius_key:
        print("❌ HELIUS_KEY not found")
        return
    
    print(f"Testing Helius API for wallet: {wallet}\n")
    
    # Test 1: Get transaction history (all types)
    print("1. Fetching ALL transaction types...")
    url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
    
    async with aiohttp.ClientSession() as session:
        # First, get total count
        params = {
            "api-key": helius_key,
            "limit": 1000  # Get more in one request
        }
        
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                print(f"   Got {len(data)} transactions")
                
                # Analyze transaction types
                tx_types = {}
                oldest = None
                newest = None
                
                for tx in data:
                    tx_type = tx.get('type', 'UNKNOWN')
                    tx_types[tx_type] = tx_types.get(tx_type, 0) + 1
                    
                    timestamp = tx.get('timestamp', 0)
                    if timestamp:
                        if not oldest or timestamp < oldest:
                            oldest = timestamp
                        if not newest or timestamp > newest:
                            newest = timestamp
                
                print("\n   Transaction types:")
                for tx_type, count in sorted(tx_types.items(), key=lambda x: x[1], reverse=True):
                    print(f"     {tx_type}: {count}")
                
                if oldest and newest:
                    oldest_date = datetime.fromtimestamp(oldest).strftime('%Y-%m-%d')
                    newest_date = datetime.fromtimestamp(newest).strftime('%Y-%m-%d')
                    print(f"\n   Date range: {oldest_date} to {newest_date}")
                    
                    # Calculate how far back this goes
                    days_of_history = (newest - oldest) / 86400
                    print(f"   Days of history: {days_of_history:.1f}")
            else:
                print(f"   Error: {response.status}")
    
    # Test 2: Check if we need to use different endpoint for complete history
    print("\n\n2. Checking parsed transaction history...")
    parsed_url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions/parsed"
    
    async with aiohttp.ClientSession() as session:
        params = {
            "api-key": helius_key,
            "commitment": "confirmed"
        }
        
        async with session.get(parsed_url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                print(f"   Parsed endpoint returned: {len(data)} transactions")
            else:
                print(f"   Parsed endpoint error: {response.status}")
    
    print("\n\n💡 To get all 135 tokens:")
    print("1. The basic transaction endpoint may have limits on history")
    print("2. You might need to use Solana RPC directly for complete history")
    print("3. Or use a service like Solscan API that indexes all historical data")
    print("4. The current data only goes back a few days")

if __name__ == "__main__":
    asyncio.run(test_full_history())