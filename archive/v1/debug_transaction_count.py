#!/usr/bin/env python3
"""
Debug transaction fetching to see why we get fewer tokens
"""

import asyncio
import aiohttp
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

async def debug_wallet(wallet: str):
    """Debug transaction fetching for a wallet"""
    
    helius_key = os.getenv('HELIUS_KEY')
    
    print(f"\n=== DEBUGGING WALLET: {wallet} ===")
    
    async with aiohttp.ClientSession() as session:
        # Test 1: Get all transaction types
        url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
        
        # First, get ALL transactions (not just swaps)
        print("\n1. Fetching ALL transaction types...")
        params = {
            "api-key": helius_key,
            "limit": 100
        }
        
        async with session.get(url, params=params) as response:
            if response.status == 200:
                all_txs = await response.json()
                
                # Count by type
                type_counts = {}
                for tx in all_txs:
                    tx_type = tx.get('type', 'UNKNOWN')
                    type_counts[tx_type] = type_counts.get(tx_type, 0) + 1
                
                print(f"Found {len(all_txs)} recent transactions")
                print("Transaction types:")
                for tx_type, count in sorted(type_counts.items()):
                    print(f"  {tx_type}: {count}")
        
        # Test 2: Get SWAP transactions
        print("\n2. Fetching SWAP transactions...")
        params = {
            "api-key": helius_key,
            "limit": 100,
            "type": "SWAP"
        }
        
        total_swaps = 0
        unique_tokens = set()
        before_sig = None
        
        for page in range(5):  # Check first 5 pages
            if before_sig:
                params["before"] = before_sig
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    swaps = await response.json()
                    
                    if not swaps:
                        break
                    
                    total_swaps += len(swaps)
                    
                    # Extract unique tokens
                    for swap in swaps:
                        for transfer in swap.get('tokenTransfers', []):
                            mint = transfer.get('mint')
                            if mint and mint != 'So11111111111111111111111111111111111111112':
                                unique_tokens.add(mint)
                    
                    before_sig = swaps[-1].get('signature') if swaps else None
                    
                    await asyncio.sleep(0.5)  # Rate limit
                else:
                    print(f"Error: {response.status}")
                    break
        
        print(f"Found {total_swaps} swap transactions")
        print(f"Found {len(unique_tokens)} unique tokens traded")
        
        # Test 3: Check Cielo for comparison
        print("\n3. Checking Cielo API for comparison...")
        cielo_key = "7c855165-3874-4237-9416-450d2373ea72"
        
        headers = {"x-api-key": cielo_key}
        cielo_url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/total-stats"
        
        async with session.get(cielo_url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                stats = data['data']
                print(f"Cielo reports: {stats['tokens_traded']} tokens traded")
            else:
                print(f"Cielo error: {response.status}")

async def main():
    wallets = [
        "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
        "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2", 
        "215nhcAHjQQGgwpQSJQ7zR26etbjjtVdW74NLzwEgQjP"
    ]
    
    for wallet in wallets:
        await debug_wallet(wallet)
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())