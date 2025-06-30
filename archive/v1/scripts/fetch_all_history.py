#!/usr/bin/env python3
"""
Aggressively fetch ALL historical transactions to find all 135 tokens.
This will keep paginating until we find no more transactions.
"""

import asyncio
import os
import aiohttp
from datetime import datetime
import json
import sys

async def fetch_complete_history(wallet_address: str):
    """Fetch ALL transactions, no matter how far back"""
    
    api_key = os.getenv('HELIUS_KEY')
    if not api_key:
        print("❌ HELIUS_KEY not found")
        return None
    
    all_transactions = []
    unique_tokens = set()
    before_signature = None
    page = 0
    
    print(f"Fetching COMPLETE history for {wallet_address}")
    print("Will continue until no more transactions are found...\n")
    
    async with aiohttp.ClientSession() as session:
        while True:
            page += 1
            
            # Build URL and params
            url = f"https://api.helius.xyz/v0/addresses/{wallet_address}/transactions"
            params = {
                "api-key": api_key,
                "limit": 1000  # Try maximum limit
            }
            
            if before_signature:
                params["before"] = before_signature
            
            try:
                async with session.get(url, params=params, timeout=60) as response:
                    if response.status == 429:
                        print(f"Rate limited, waiting 10 seconds...")
                        await asyncio.sleep(10)
                        continue
                    
                    if response.status != 200:
                        print(f"Error {response.status}")
                        # Try with smaller limit
                        params["limit"] = 100
                        async with session.get(url, params=params, timeout=60) as retry_response:
                            if retry_response.status != 200:
                                print(f"Retry also failed: {retry_response.status}")
                                break
                            response = retry_response
                    
                    data = await response.json()
                    
                    if not data:
                        print(f"No more data after page {page}")
                        break
                    
                    # Process transactions
                    swaps_in_batch = 0
                    for tx in data:
                        all_transactions.append(tx)
                        
                        # Count swaps and extract tokens
                        if tx.get('type') == 'SWAP' or 'swap' in tx.get('description', '').lower():
                            swaps_in_batch += 1
                            
                            # Extract token addresses
                            for transfer in tx.get('tokenTransfers', []):
                                mint = transfer.get('mint', '')
                                if mint and mint != 'So11111111111111111111111111111111111111112':
                                    unique_tokens.add(mint)
                    
                    # Show progress
                    if data:
                        oldest = min(tx['timestamp'] for tx in data)
                        oldest_date = datetime.fromtimestamp(oldest).strftime('%Y-%m-%d')
                        print(f"Page {page}: {len(data)} txs, {swaps_in_batch} swaps, "
                              f"oldest: {oldest_date} | Total: {len(all_transactions)} txs, "
                              f"{len(unique_tokens)} tokens")
                    
                    # Continue pagination
                    if len(data) < 100:  # Reached the end
                        print("Reached end of transaction history")
                        break
                    
                    before_signature = data[-1]['signature']
                    
                    # Small delay to avoid rate limits
                    await asyncio.sleep(0.2)
                    
            except asyncio.TimeoutError:
                print(f"Timeout on page {page}, continuing...")
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"Error on page {page}: {e}")
                await asyncio.sleep(2)
    
    # Analyze results
    if all_transactions:
        timestamps = [tx['timestamp'] for tx in all_transactions]
        oldest = datetime.fromtimestamp(min(timestamps))
        newest = datetime.fromtimestamp(max(timestamps))
        
        print(f"\n{'='*60}")
        print(f"COMPLETE HISTORY SUMMARY:")
        print(f"  Total transactions: {len(all_transactions)}")
        print(f"  Date range: {oldest.strftime('%Y-%m-%d')} to {newest.strftime('%Y-%m-%d')}")
        print(f"  Days covered: {(newest - oldest).days}")
        print(f"  Unique tokens found: {len(unique_tokens)} (target: 135)")
        print('='*60)
        
        # If still not 135 tokens, check what might be missing
        if len(unique_tokens) < 135:
            print(f"\n⚠️  Only found {len(unique_tokens)} tokens instead of 135")
            print("Possible reasons:")
            print("1. Some trades might be on other DEXes not captured")
            print("2. Some tokens might be in different transaction types")
            print("3. The wallet might have used other addresses")
            print("4. Need to check LP operations, not just swaps")
    
    return {
        'transactions': len(all_transactions),
        'unique_tokens': len(unique_tokens),
        'tokens': list(unique_tokens)
    }

# Also check other transaction types
async def analyze_all_transaction_types(wallet_address: str):
    """Analyze all transaction types to find where tokens might be"""
    
    api_key = os.getenv('HELIUS_KEY')
    if not api_key:
        return
    
    print(f"\nAnalyzing transaction types for {wallet_address[:8]}...")
    
    async with aiohttp.ClientSession() as session:
        url = f"https://api.helius.xyz/v0/addresses/{wallet_address}/transactions"
        params = {
            "api-key": api_key,
            "limit": 1000
        }
        
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                
                # Count transaction types
                tx_types = {}
                tokens_by_type = {}
                
                for tx in data:
                    tx_type = tx.get('type', 'UNKNOWN')
                    tx_types[tx_type] = tx_types.get(tx_type, 0) + 1
                    
                    # Count unique tokens per type
                    if tx_type not in tokens_by_type:
                        tokens_by_type[tx_type] = set()
                    
                    for transfer in tx.get('tokenTransfers', []):
                        mint = transfer.get('mint', '')
                        if mint and mint != 'So11111111111111111111111111111111111111112':
                            tokens_by_type[tx_type].add(mint)
                
                print("\nTransaction types breakdown:")
                for tx_type, count in sorted(tx_types.items(), key=lambda x: x[1], reverse=True):
                    token_count = len(tokens_by_type.get(tx_type, set()))
                    print(f"  {tx_type}: {count} transactions, {token_count} unique tokens")

if __name__ == "__main__":
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    # First, fetch complete history
    result = asyncio.run(fetch_complete_history(wallet))
    
    # Then analyze transaction types
    asyncio.run(analyze_all_transaction_types(wallet))