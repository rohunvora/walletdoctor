#!/usr/bin/env python3
"""
Use Solana RPC directly to get complete transaction history
This should get ALL transactions, not just recent ones
"""

import asyncio
import aiohttp
from datetime import datetime
from typing import List, Dict, Set
import json
import os

class SolanaRPCFetcher:
    def __init__(self, rpc_url: str = "https://api.mainnet-beta.solana.com"):
        self.rpc_url = rpc_url
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_signatures_for_address(self, address: str, before: str = None, limit: int = 1000) -> List[Dict]:
        """Get transaction signatures for an address"""
        params = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [
                address,
                {
                    "limit": limit,
                    "before": before
                } if before else {"limit": limit}
            ]
        }
        
        async with self.session.post(self.rpc_url, json=params) as response:
            result = await response.json()
            if "result" in result:
                return result["result"]
            return []
    
    async def fetch_all_signatures(self, address: str) -> List[str]:
        """Fetch ALL transaction signatures for an address"""
        all_signatures = []
        before = None
        page = 0
        
        print(f"Fetching all transaction signatures for {address[:8]}...")
        
        while True:
            page += 1
            signatures = await self.get_signatures_for_address(address, before)
            
            if not signatures:
                break
                
            all_signatures.extend(signatures)
            
            # Get oldest signature info
            oldest = signatures[-1]
            oldest_time = datetime.fromtimestamp(oldest['blockTime']) if oldest.get('blockTime') else None
            
            print(f"  Page {page}: {len(signatures)} signatures, "
                  f"oldest: {oldest_time.strftime('%Y-%m-%d') if oldest_time else 'unknown'} "
                  f"(total: {len(all_signatures)})")
            
            # Check if we've hit the end
            if len(signatures) < 1000:
                break
                
            # Set up for next page
            before = signatures[-1]['signature']
            
            # Small delay to avoid rate limits
            await asyncio.sleep(0.1)
        
        return all_signatures

async def use_helius_enhanced(wallet: str, api_key: str):
    """Try Helius enhanced API which might have better historical coverage"""
    print("\nTrying Helius Enhanced API for complete history...")
    
    async with aiohttp.ClientSession() as session:
        # Try the enhanced transactions endpoint
        url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions/enhanced"
        
        all_transactions = []
        before = None
        page = 0
        
        while True:
            page += 1
            params = {
                "api-key": api_key,
                "limit": 100,
                "showRaw": True,  # Get raw transaction data
                "commitment": "finalized"
            }
            
            if before:
                params["before"] = before
            
            try:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status != 200:
                        print(f"Enhanced API error: {response.status}")
                        break
                        
                    data = await response.json()
                    if not data:
                        break
                        
                    all_transactions.extend(data)
                    
                    # Show progress
                    if data:
                        oldest = min(tx.get('timestamp', float('inf')) for tx in data)
                        if oldest != float('inf'):
                            oldest_date = datetime.fromtimestamp(oldest).strftime('%Y-%m-%d')
                            print(f"  Page {page}: {len(data)} txs, oldest: {oldest_date} (total: {len(all_transactions)})")
                    
                    if len(data) < 100:
                        break
                        
                    before = data[-1].get('signature')
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                print(f"Error: {e}")
                break
        
        return all_transactions

async def main():
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    print("=== FETCHING COMPLETE HISTORY VIA SOLANA RPC ===\n")
    
    # Method 1: Direct Solana RPC
    async with SolanaRPCFetcher() as fetcher:
        signatures = await fetcher.fetch_all_signatures(wallet)
        
        print(f"\n✅ Found {len(signatures)} total transactions via Solana RPC")
        
        if signatures:
            # Get date range
            valid_sigs = [sig for sig in signatures if sig.get('blockTime')]
            if valid_sigs:
                oldest = min(valid_sigs, key=lambda x: x['blockTime'])
                newest = max(valid_sigs, key=lambda x: x['blockTime'])
                
                oldest_date = datetime.fromtimestamp(oldest['blockTime'])
                newest_date = datetime.fromtimestamp(newest['blockTime'])
                
                print(f"📅 Date range: {oldest_date} to {newest_date}")
                print(f"⏱️  Days of history: {(newest_date - oldest_date).days}")
                
                # Check specific date - 17 days ago would be around June 9
                june_9_start = datetime(2025, 6, 9).timestamp()
                older_txs = [sig for sig in signatures if sig.get('blockTime', float('inf')) < june_9_start]
                print(f"📊 Transactions before June 9: {len(older_txs)}")
                
                # Show some of the oldest transactions
                print("\n📜 Some of the oldest transactions:")
                for sig in sorted(valid_sigs, key=lambda x: x['blockTime'])[:5]:
                    date = datetime.fromtimestamp(sig['blockTime']).strftime('%Y-%m-%d %H:%M')
                    print(f"  {date}: {sig['signature'][:20]}...")
    
    # Method 2: Try Helius Enhanced API
    api_key = os.getenv('HELIUS_KEY')
    if api_key:
        enhanced_txs = await use_helius_enhanced(wallet, api_key)
        if enhanced_txs:
            print(f"\n✅ Helius Enhanced API found {len(enhanced_txs)} transactions")

if __name__ == "__main__":
    asyncio.run(main())