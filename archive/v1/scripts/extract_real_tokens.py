#!/usr/bin/env python3
"""
Extract REAL traded tokens from Helius data by analyzing SWAP transactions
"""

import asyncio
import os
import aiohttp
from datetime import datetime
from typing import Dict, List, Set
import json

async def get_real_traded_tokens(wallet: str, api_key: str) -> Dict:
    """
    Get actual traded tokens by analyzing SWAP transactions specifically
    """
    traded_tokens = {}  # token_address -> {symbol, trades, first_trade, last_trade}
    before_signature = None
    page = 0
    total_swaps = 0
    
    print(f"Extracting real traded tokens for {wallet}...\n")
    
    async with aiohttp.ClientSession() as session:
        while True:
            page += 1
            
            url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
            params = {
                "api-key": api_key,
                "limit": 100,
                "type": "SWAP"  # Only get SWAP transactions
            }
            
            if before_signature:
                params["before"] = before_signature
            
            try:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 429:
                        print("Rate limited, waiting...")
                        await asyncio.sleep(30)
                        continue
                    
                    if response.status != 200:
                        break
                    
                    data = await response.json()
                    if not data:
                        break
                    
                    total_swaps += len(data)
                    
                    # Analyze each swap
                    for tx in data:
                        timestamp = datetime.fromtimestamp(tx['timestamp'])
                        
                        # Extract token from description
                        description = tx.get('description', '')
                        token_symbol = 'UNKNOWN'
                        
                        # Parse descriptions like "User swapped 1.5 SOL for 1000 BONK"
                        if 'swapped' in description.lower():
                            parts = description.split()
                            # Find token symbol (usually after "for")
                            if 'for' in parts:
                                for_index = parts.index('for')
                                if for_index + 2 < len(parts):
                                    token_symbol = parts[for_index + 2]
                        
                        # Get token mint from transfers
                        token_mint = None
                        for transfer in tx.get('tokenTransfers', []):
                            mint = transfer.get('mint', '')
                            # Skip SOL
                            if mint and mint != 'So11111111111111111111111111111111111111112':
                                from_account = transfer.get('fromUserAccount', '')
                                to_account = transfer.get('toUserAccount', '')
                                
                                # If user received tokens (buy) or sent tokens (sell)
                                if wallet in [from_account, to_account]:
                                    token_mint = mint
                                    break
                        
                        if token_mint:
                            if token_mint not in traded_tokens:
                                traded_tokens[token_mint] = {
                                    'symbol': token_symbol,
                                    'trades': 0,
                                    'first_trade': timestamp,
                                    'last_trade': timestamp,
                                    'signatures': []
                                }
                            
                            traded_tokens[token_mint]['trades'] += 1
                            traded_tokens[token_mint]['last_trade'] = max(
                                traded_tokens[token_mint]['last_trade'], 
                                timestamp
                            )
                            traded_tokens[token_mint]['first_trade'] = min(
                                traded_tokens[token_mint]['first_trade'], 
                                timestamp
                            )
                            traded_tokens[token_mint]['signatures'].append(tx['signature'])
                    
                    # Progress
                    print(f"Page {page}: {len(data)} swaps | Total: {total_swaps} swaps, "
                          f"{len(traded_tokens)} unique tokens")
                    
                    before_signature = data[-1]['signature']
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                print(f"Error: {e}")
                break
    
    return traded_tokens

async def get_token_metadata(tokens: List[str], api_key: str) -> Dict[str, Dict]:
    """Get proper token symbols from Helius metadata API"""
    
    print(f"\nFetching metadata for {len(tokens)} tokens...")
    metadata = {}
    
    async with aiohttp.ClientSession() as session:
        # Batch by 100
        for i in range(0, len(tokens), 100):
            batch = tokens[i:i+100]
            
            url = "https://api.helius.xyz/v0/token-metadata"
            params = {"api-key": api_key}
            data = {"mintAccounts": batch}
            
            try:
                async with session.post(url, params=params, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        for item in result:
                            mint = item.get('account')
                            if mint and 'onChainMetadata' in item:
                                meta = item['onChainMetadata'].get('metadata', {})
                                metadata[mint] = {
                                    'symbol': meta.get('symbol', 'UNKNOWN'),
                                    'name': meta.get('name', 'Unknown Token')
                                }
                        print(f"  Batch {i//100 + 1}: Got {len(result)} metadata entries")
                    
                await asyncio.sleep(0.2)
                
            except Exception as e:
                print(f"  Error in batch {i//100 + 1}: {e}")
    
    return metadata

async def main():
    api_key = os.getenv('HELIUS_KEY')
    if not api_key:
        print("❌ HELIUS_KEY not found")
        return
    
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    # Get real traded tokens
    print("=== EXTRACTING REAL TRADED TOKENS ===\n")
    traded_tokens = await get_real_traded_tokens(wallet, api_key)
    
    # Get metadata
    token_addresses = list(traded_tokens.keys())
    metadata = await get_token_metadata(token_addresses, api_key)
    
    # Update symbols
    for mint, meta in metadata.items():
        if mint in traded_tokens:
            traded_tokens[mint]['symbol'] = meta['symbol']
            traded_tokens[mint]['name'] = meta['name']
    
    # Summary
    print(f"\n{'='*60}")
    print("REAL TRADED TOKENS:")
    print(f"  Total unique tokens: {len(traded_tokens)}")
    
    # Sort by trade count
    sorted_tokens = sorted(
        traded_tokens.items(), 
        key=lambda x: x[1]['trades'], 
        reverse=True
    )
    
    print("\nTop 20 most traded tokens:")
    for i, (mint, data) in enumerate(sorted_tokens[:20], 1):
        symbol = data['symbol']
        trades = data['trades']
        first = data['first_trade'].strftime('%Y-%m-%d')
        last = data['last_trade'].strftime('%Y-%m-%d')
        print(f"  {i:2}. {symbol:10} - {trades:3} trades ({first} to {last})")
    
    print('='*60)
    
    # Check if we're getting closer to 135
    print(f"\n{'🎯' if len(traded_tokens) >= 135 else '⚠️'}  Found {len(traded_tokens)} unique tokens")
    
    if len(traded_tokens) < 135:
        print("\nNote: This wallet's on-chain history shows fewer tokens than expected.")
        print("The 135 tokens on Cielo might include:")
        print("- Tokens from other wallets you own")
        print("- Tokens traded before this wallet was created")
        print("- Off-chain or aggregated trades")

if __name__ == "__main__":
    asyncio.run(main())