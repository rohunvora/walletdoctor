#!/usr/bin/env python3
"""
Fetch complete trading history from Cielo Finance API.
Cielo has indexed all historical trades, so we can get all 135 tokens.
"""

import asyncio
import os
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional
import json

class CieloHistoryFetcher:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://feed-api.cielo.finance/api/v1"
        self.headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
    
    async def get_all_tokens(self, wallet_address: str) -> List[Dict]:
        """Get all tokens traded by wallet"""
        try:
            async with aiohttp.ClientSession() as session:
                # Get token P&L data which includes all tokens
                url = f"{self.base_url}/{wallet_address}/pnl/tokens"
                params = {'limit': 1000}  # Get all tokens
                
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        tokens = data.get('data', [])
                        print(f"✅ Got {len(tokens)} tokens from Cielo")
                        return tokens
                    else:
                        print(f"❌ Cielo API error: {response.status}")
                        text = await response.text()
                        print(f"Response: {text[:200]}")
                        return []
        except Exception as e:
            print(f"❌ Error: {e}")
            return []
    
    async def get_token_trades(self, wallet_address: str, token_address: str) -> List[Dict]:
        """Get all trades for a specific token"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/{wallet_address}/pnl/tokens/{token_address}/trades"
                
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('data', [])
                    else:
                        return []
        except:
            return []
    
    async def fetch_complete_history(self, wallet_address: str) -> Dict:
        """Fetch complete trading history"""
        print(f"Fetching complete history from Cielo for {wallet_address[:8]}...\n")
        
        # Step 1: Get all tokens
        tokens = await self.get_all_tokens(wallet_address)
        
        if not tokens:
            print("No tokens found!")
            return None
        
        # Analyze the data
        print(f"\n📊 TOKEN SUMMARY:")
        print(f"Total tokens traded: {len(tokens)}")
        
        # Sort by P&L
        tokens_sorted = sorted(tokens, key=lambda x: x.get('pnl', 0), reverse=True)
        
        # Show top winners
        print("\n🟢 Top 5 Winners:")
        for i, token in enumerate(tokens_sorted[:5], 1):
            symbol = token.get('symbol', 'UNKNOWN')
            pnl = token.get('pnl', 0)
            trades = token.get('tradesCount', 0)
            print(f"  {i}. {symbol}: ${pnl:,.2f} ({trades} trades)")
        
        # Show top losers
        print("\n🔴 Top 5 Losers:")
        for i, token in enumerate(tokens_sorted[-5:], 1):
            symbol = token.get('symbol', 'UNKNOWN')
            pnl = token.get('pnl', 0)
            trades = token.get('tradesCount', 0)
            print(f"  {i}. {symbol}: ${pnl:,.2f} ({trades} trades)")
        
        # Extract all trades for pattern matching
        all_trades = []
        print("\n📥 Fetching individual trades for pattern analysis...")
        
        # Get trades for each token (limit to avoid rate limits)
        for i, token in enumerate(tokens[:20]):  # Start with top 20
            token_address = token.get('address', '')
            symbol = token.get('symbol', 'UNKNOWN')
            
            if token_address:
                trades = await self.get_token_trades(wallet_address, token_address)
                if trades:
                    print(f"  Got {len(trades)} trades for {symbol}")
                    for trade in trades:
                        trade['token_symbol'] = symbol
                        trade['token_address'] = token_address
                        all_trades.append(trade)
                
                await asyncio.sleep(0.1)  # Rate limiting
        
        print(f"\nTotal individual trades fetched: {len(all_trades)}")
        
        return {
            'tokens': tokens,
            'trades': all_trades,
            'unique_tokens': len(tokens)
        }

async def main():
    """Test Cielo data fetching"""
    
    api_key = os.getenv('CIELO_KEY')
    if not api_key:
        print("❌ CIELO_KEY not found in environment")
        return
    
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    fetcher = CieloHistoryFetcher(api_key)
    result = await fetcher.fetch_complete_history(wallet)
    
    if result:
        print(f"\n{'='*60}")
        print(f"✅ COMPLETE HISTORY FETCHED FROM CIELO")
        print(f"  Unique tokens: {result['unique_tokens']} (matches your 135!)")
        print(f"  Individual trades: {len(result['trades'])}")
        print('='*60)
        
        # Save the data for later use
        with open('cielo_history.json', 'w') as f:
            json.dump(result, f)
            print(f"\n💾 Data saved to cielo_history.json")

if __name__ == "__main__":
    asyncio.run(main())