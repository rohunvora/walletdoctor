#!/usr/bin/env python3
"""
Fetch trading history using Birdeye API as an alternative.
Birdeye has comprehensive historical data for Solana tokens.
"""

import asyncio
import os
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional
import json

class BirdeyeHistoricalFetcher:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://public-api.birdeye.so"
        self.headers = {
            "X-API-KEY": api_key,
            "Accept": "application/json"
        }
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_wallet_portfolio(self, wallet: str) -> Dict:
        """Get wallet's current and historical portfolio"""
        url = f"{self.base_url}/wallet/portfolio"
        params = {"wallet": wallet}
        
        try:
            async with self.session.get(url, headers=self.headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"Error fetching portfolio: {response.status}")
                    return None
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    async def get_wallet_trades(self, wallet: str, offset: int = 0, limit: int = 50) -> Dict:
        """Get wallet's trading history"""
        url = f"{self.base_url}/wallet/trades"
        params = {
            "wallet": wallet,
            "offset": offset,
            "limit": limit
        }
        
        try:
            async with self.session.get(url, headers=self.headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"Error fetching trades: {response.status}")
                    text = await response.text()
                    print(f"Response: {text[:200]}")
                    return None
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    async def get_token_info(self, token_address: str) -> Dict:
        """Get token metadata including historical market cap"""
        url = f"{self.base_url}/defi/token_overview"
        params = {"address": token_address}
        
        try:
            async with self.session.get(url, headers=self.headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return None
        except:
            return None
    
    async def fetch_all_trades(self, wallet: str) -> List[Dict]:
        """Fetch all trades for a wallet with pagination"""
        all_trades = []
        offset = 0
        limit = 50
        
        print(f"Fetching trades from Birdeye for {wallet[:8]}...")
        
        while True:
            result = await self.get_wallet_trades(wallet, offset, limit)
            
            if not result or 'data' not in result:
                break
                
            trades = result['data'].get('trades', [])
            if not trades:
                break
                
            all_trades.extend(trades)
            print(f"  Fetched {len(trades)} trades (total: {len(all_trades)})")
            
            if len(trades) < limit:
                break
                
            offset += limit
            await asyncio.sleep(0.5)  # Rate limiting
        
        return all_trades

async def test_birdeye_api(wallet_address: str):
    """Test Birdeye API for historical data"""
    
    # Note: Birdeye requires a different API key than Helius
    api_key = os.getenv('BIRDEYE_API_KEY')
    if not api_key:
        print("❌ BIRDEYE_API_KEY not found in environment")
        print("ℹ️  Birdeye API requires registration at https://birdeye.so")
        return None
    
    async with BirdeyeHistoricalFetcher(api_key) as fetcher:
        # Get portfolio
        print("Fetching portfolio data...")
        portfolio = await fetcher.get_wallet_portfolio(wallet_address)
        
        if portfolio:
            tokens = portfolio.get('data', {}).get('tokens', [])
            print(f"Found {len(tokens)} tokens in portfolio")
        
        # Get trades
        trades = await fetcher.fetch_all_trades(wallet_address)
        
        if trades:
            print(f"\nTotal trades found: {len(trades)}")
            
            # Analyze unique tokens
            unique_tokens = set()
            for trade in trades:
                token = trade.get('token_address')
                if token:
                    unique_tokens.add(token)
            
            print(f"Unique tokens traded: {len(unique_tokens)}")
            
            # Show sample trades
            print("\nSample trades:")
            for trade in trades[:5]:
                timestamp = trade.get('block_time', 0)
                date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
                action = trade.get('side', 'UNKNOWN')
                symbol = trade.get('token_symbol', 'UNKNOWN')
                amount = trade.get('amount_usd', 0)
                
                print(f"  {date} - {action} {symbol}: ${amount:.2f}")
        
        return {
            'trades': trades,
            'unique_tokens': len(unique_tokens) if trades else 0
        }

# Also create a Solscan fetcher as another alternative
class SolscanHistoricalFetcher:
    def __init__(self):
        self.base_url = "https://public-api.solscan.io"
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0"  # Solscan public API
        }
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_wallet_transactions(self, wallet: str, before_hash: str = None) -> List[Dict]:
        """Get wallet transactions from Solscan"""
        url = f"{self.base_url}/account/transactions"
        params = {
            "account": wallet,
            "limit": 50
        }
        
        if before_hash:
            params["beforeHash"] = before_hash
        
        try:
            async with self.session.get(url, headers=self.headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"Solscan error: {response.status}")
                    return []
        except Exception as e:
            print(f"Error: {e}")
            return []

async def test_solscan_api(wallet_address: str):
    """Test Solscan public API"""
    print("\n=== Testing Solscan API ===")
    
    async with SolscanHistoricalFetcher() as fetcher:
        transactions = await fetcher.get_wallet_transactions(wallet_address)
        
        if transactions:
            print(f"Got {len(transactions)} transactions from Solscan")
            
            # Note: Solscan public API has limitations
            print("\nℹ️  Solscan public API limitations:")
            print("  - Rate limited")
            print("  - May require API key for full history")
            print("  - Best used for recent transactions")

if __name__ == "__main__":
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    print("=== TESTING ALTERNATIVE DATA SOURCES ===\n")
    
    # Test Birdeye
    result = asyncio.run(test_birdeye_api(wallet))
    
    # Test Solscan
    asyncio.run(test_solscan_api(wallet))