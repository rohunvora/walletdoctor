#!/usr/bin/env python3
"""
Backfill complete trading history from Helius.
This will fetch ALL historical trades to get the full 135 tokens.
"""

import asyncio
import os
import sys
import aiohttp
import duckdb
from datetime import datetime
from typing import Dict, List, Optional
import json

sys.path.append('.')

class HistoricalBackfiller:
    def __init__(self, helius_key: str):
        self.helius_key = helius_key
        self.helius_url = "https://api.helius.xyz/v0"
        
    async def fetch_all_swaps(self, wallet: str) -> List[Dict]:
        """Fetch ALL swap transactions for a wallet"""
        print(f"Fetching complete swap history for {wallet[:8]}...")
        
        all_swaps = []
        before_signature = None
        page = 0
        
        async with aiohttp.ClientSession() as session:
            while True:
                page += 1
                url = f"{self.helius_url}/addresses/{wallet}/transactions"
                params = {
                    "api-key": self.helius_key,
                    "limit": 100,  # Max allowed
                    "type": "SWAP"  # Only get swaps
                }
                
                if before_signature:
                    params["before"] = before_signature
                
                try:
                    async with session.get(url, params=params) as response:
                        if response.status != 200:
                            print(f"Error fetching page {page}: {response.status}")
                            break
                            
                        data = await response.json()
                        
                        if not data:
                            print(f"No more transactions after page {page}")
                            break
                            
                        all_swaps.extend(data)
                        print(f"  Page {page}: Got {len(data)} swaps (total: {len(all_swaps)})")
                        
                        # If we got less than limit, we're done
                        if len(data) < 100:
                            break
                        
                        # Get the last signature for pagination
                        before_signature = data[-1]['signature']
                        
                        # Be nice to the API
                        await asyncio.sleep(0.1)
                        
                except Exception as e:
                    print(f"Error on page {page}: {e}")
                    break
        
        print(f"\nTotal swaps fetched: {len(all_swaps)}")
        return all_swaps
    
    def parse_swap_data(self, swap: Dict, wallet: str) -> Optional[Dict]:
        """Parse a swap transaction into trade data"""
        try:
            # Skip if no token transfers
            if 'tokenTransfers' not in swap:
                return None
                
            # Find SOL and token transfers
            sol_amount = 0
            token_amount = 0
            token_mint = None
            action = None
            
            for transfer in swap['tokenTransfers']:
                mint = transfer.get('mint', '')
                amount = transfer.get('tokenAmount', 0)
                from_addr = transfer.get('fromUserAccount', '')
                to_addr = transfer.get('toUserAccount', '')
                
                # SOL (wrapped SOL)
                if mint == 'So11111111111111111111111111111111111111112':
                    if from_addr == wallet:
                        sol_amount += amount
                        action = 'BUY'  # Sending SOL = buying token
                    elif to_addr == wallet:
                        sol_amount += amount
                        action = 'SELL'  # Receiving SOL = selling token
                else:
                    # Other token
                    if to_addr == wallet and action == 'BUY':
                        token_amount = amount
                        token_mint = mint
                    elif from_addr == wallet and action == 'SELL':
                        token_amount = amount
                        token_mint = mint
            
            if not token_mint or sol_amount == 0:
                return None
                
            # Get token metadata from description if available
            description = swap.get('description', '')
            token_symbol = 'UNKNOWN'
            
            # Try to extract token symbol from description
            # e.g., "34zY... swapped 1.5 SOL for 1000 BONK"
            if 'swapped' in description and 'for' in description:
                parts = description.split('for')
                if len(parts) > 1:
                    token_part = parts[1].strip().split()
                    if len(token_part) > 1:
                        token_symbol = token_part[1]
            
            return {
                'signature': swap['signature'],
                'timestamp': datetime.fromtimestamp(swap['timestamp']),
                'action': action,
                'token_address': token_mint,
                'token_symbol': token_symbol,
                'sol_amount': sol_amount / 1e9,  # Convert lamports to SOL
                'token_amount': token_amount,
                'fee': swap.get('fee', 0) / 1e9
            }
            
        except Exception as e:
            print(f"Error parsing swap {swap.get('signature', 'unknown')}: {e}")
            return None
    
    async def backfill_wallet(self, wallet: str):
        """Backfill complete history for a wallet"""
        print(f"\n{'='*60}")
        print(f"BACKFILLING COMPLETE HISTORY FOR: {wallet}")
        print('='*60)
        
        # Step 1: Fetch all swaps
        swaps = await self.fetch_all_swaps(wallet)
        
        if not swaps:
            print("No swaps found!")
            return
            
        # Step 2: Parse swaps into trades
        print("\nParsing swap data...")
        trades = []
        unique_tokens = set()
        
        for swap in swaps:
            trade_data = self.parse_swap_data(swap, wallet)
            if trade_data:
                trades.append(trade_data)
                unique_tokens.add(trade_data['token_address'])
        
        print(f"Parsed {len(trades)} trades")
        print(f"Unique tokens: {len(unique_tokens)}")
        
        # Step 3: Show sample of what we found
        print("\nSample trades:")
        for trade in trades[:5]:
            print(f"  {trade['timestamp']} - {trade['action']} {trade['token_symbol']}: "
                  f"{trade['sol_amount']:.2f} SOL")
        
        # Step 4: Get token metadata for unknowns
        print("\nWould need to fetch metadata for UNKNOWN tokens using:")
        print("- Jupiter API for token list")
        print("- Helius token metadata API")
        print("- DexScreener API")
        
        # Step 5: Calculate market caps at trade time
        print("\nWould need to fetch historical market caps using:")
        print("- Birdeye historical data API")
        print("- DexScreener historical API")
        
        return {
            'trades': trades,
            'unique_tokens': len(unique_tokens),
            'date_range': (
                min(t['timestamp'] for t in trades) if trades else None,
                max(t['timestamp'] for t in trades) if trades else None
            )
        }

async def main():
    """Test the complete historical backfill"""
    
    helius_key = os.getenv('HELIUS_KEY')
    if not helius_key:
        print("❌ HELIUS_KEY not found in environment")
        return
        
    backfiller = HistoricalBackfiller(helius_key)
    
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    result = await backfiller.backfill_wallet(wallet)
    
    if result:
        print(f"\n\n=== BACKFILL SUMMARY ===")
        print(f"Unique tokens traded: {result['unique_tokens']} (target: 135)")
        if result['date_range'][0]:
            print(f"Date range: {result['date_range'][0]} to {result['date_range'][1]}")
        
        print("\n⚠️  To complete the backfill, we need:")
        print("1. Token metadata (symbols, names) for all tokens")
        print("2. Historical market cap data at trade time")
        print("3. Historical SOL balance for position sizing")
        print("4. Store all this in the diary table")

if __name__ == "__main__":
    asyncio.run(main())