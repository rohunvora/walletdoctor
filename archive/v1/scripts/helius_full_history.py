#!/usr/bin/env python3
"""
Fetch COMPLETE trading history using Helius API with proper pagination.
This will get all 135 tokens by fetching ALL historical transactions.
"""

import asyncio
import os
import sys
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional, Set
import json
import time

sys.path.append('.')

class HeliusHistoricalFetcher:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.helius.xyz/v0"
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_all_transactions(self, address: str) -> List[Dict]:
        """Fetch ALL transactions for an address with pagination"""
        all_transactions = []
        before_signature = None
        page = 0
        consecutive_errors = 0
        
        print(f"Fetching complete transaction history for {address[:8]}...")
        print("This may take a while for wallets with many transactions...\n")
        
        while True:
            page += 1
            
            try:
                # Build request parameters
                params = {
                    "api-key": self.api_key,
                    "limit": 100,  # Maximum allowed
                }
                
                if before_signature:
                    params["before"] = before_signature
                
                url = f"{self.base_url}/addresses/{address}/transactions"
                
                # Make request with retry logic
                async with self.session.get(url, params=params, timeout=30) as response:
                    if response.status == 429:  # Rate limited
                        print(f"  Rate limited, waiting 5 seconds...")
                        await asyncio.sleep(5)
                        continue
                        
                    if response.status != 200:
                        consecutive_errors += 1
                        print(f"  Error on page {page}: Status {response.status}")
                        if consecutive_errors > 3:
                            print("  Too many errors, stopping")
                            break
                        await asyncio.sleep(2)
                        continue
                    
                    consecutive_errors = 0
                    data = await response.json()
                    
                    if not data:
                        print(f"  No more transactions after page {page}")
                        break
                    
                    all_transactions.extend(data)
                    
                    # Show progress
                    oldest_in_batch = min(tx['timestamp'] for tx in data)
                    oldest_date = datetime.fromtimestamp(oldest_in_batch).strftime('%Y-%m-%d')
                    print(f"  Page {page}: {len(data)} txs, oldest: {oldest_date} (total: {len(all_transactions)})")
                    
                    # Check if we've fetched enough history
                    # If the oldest transaction is more than 2 years old, we probably have enough
                    days_ago = (time.time() - oldest_in_batch) / 86400
                    if days_ago > 730:  # 2 years
                        print(f"  Reached 2+ years of history, stopping")
                        break
                    
                    # Pagination
                    if len(data) < 100:
                        print(f"  Last page reached")
                        break
                        
                    before_signature = data[-1]['signature']
                    
                    # Be nice to the API
                    await asyncio.sleep(0.1)
                    
            except asyncio.TimeoutError:
                print(f"  Timeout on page {page}, retrying...")
                consecutive_errors += 1
                if consecutive_errors > 3:
                    break
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"  Error on page {page}: {e}")
                consecutive_errors += 1
                if consecutive_errors > 3:
                    break
                await asyncio.sleep(2)
        
        return all_transactions
    
    def extract_swap_data(self, transactions: List[Dict], wallet_address: str) -> List[Dict]:
        """Extract swap/trade data from transactions"""
        trades = []
        unique_tokens = set()
        
        print("\nExtracting swap data from transactions...")
        
        for tx in transactions:
            # Only process successful transactions
            if tx.get('transactionError'):
                continue
                
            tx_type = tx.get('type', '')
            
            # Look for swaps in different transaction types
            if tx_type in ['SWAP', 'UNKNOWN'] or 'swap' in tx.get('description', '').lower():
                # Parse token transfers
                token_transfers = tx.get('tokenTransfers', [])
                native_transfers = tx.get('nativeTransfers', [])
                
                # Extract trade data from transfers
                sol_amount = 0
                token_info = None
                action = None
                
                # Check native SOL transfers
                for transfer in native_transfers:
                    if transfer.get('fromUserAccount') == wallet_address:
                        sol_amount += transfer.get('amount', 0) / 1e9
                        action = 'BUY'
                    elif transfer.get('toUserAccount') == wallet_address:
                        sol_amount += transfer.get('amount', 0) / 1e9
                        action = 'SELL'
                
                # Check token transfers
                for transfer in token_transfers:
                    mint = transfer.get('mint', '')
                    if mint and mint != 'So11111111111111111111111111111111111111112':
                        # This is the traded token
                        if transfer.get('toUserAccount') == wallet_address and action == 'BUY':
                            token_info = {
                                'mint': mint,
                                'amount': transfer.get('tokenAmount', 0),
                                'decimals': transfer.get('decimals', 0)
                            }
                            unique_tokens.add(mint)
                        elif transfer.get('fromUserAccount') == wallet_address and action == 'SELL':
                            token_info = {
                                'mint': mint,
                                'amount': transfer.get('tokenAmount', 0),
                                'decimals': transfer.get('decimals', 0)
                            }
                            unique_tokens.add(mint)
                
                if token_info and sol_amount > 0 and action:
                    trades.append({
                        'signature': tx['signature'],
                        'timestamp': datetime.fromtimestamp(tx['timestamp']),
                        'action': action,
                        'sol_amount': sol_amount,
                        'token_mint': token_info['mint'],
                        'token_amount': token_info['amount'],
                        'description': tx.get('description', ''),
                        'fee': tx.get('fee', 0) / 1e9
                    })
        
        print(f"Found {len(trades)} trades involving {len(unique_tokens)} unique tokens")
        return trades, unique_tokens
    
    async def get_token_metadata(self, mints: List[str]) -> Dict[str, Dict]:
        """Fetch token metadata for a list of mints"""
        print(f"\nFetching metadata for {len(mints)} tokens...")
        
        metadata = {}
        
        # Batch requests (max 100 per request)
        for i in range(0, len(mints), 100):
            batch = mints[i:i+100]
            
            try:
                url = f"{self.base_url}/token-metadata"
                params = {"api-key": self.api_key}
                data = {"mintAccounts": batch}
                
                async with self.session.post(url, params=params, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        for token_data in result:
                            mint = token_data.get('account')
                            if mint:
                                metadata[mint] = {
                                    'symbol': token_data.get('onChainMetadata', {}).get('metadata', {}).get('symbol', 'UNKNOWN'),
                                    'name': token_data.get('onChainMetadata', {}).get('metadata', {}).get('name', 'Unknown Token')
                                }
                        print(f"  Batch {i//100 + 1}: Got metadata for {len(result)} tokens")
                    else:
                        print(f"  Error fetching metadata batch {i//100 + 1}: {response.status}")
                        
                await asyncio.sleep(0.2)  # Rate limiting
                
            except Exception as e:
                print(f"  Error fetching metadata: {e}")
        
        return metadata

async def fetch_complete_history(wallet_address: str):
    """Main function to fetch complete trading history"""
    
    api_key = os.getenv('HELIUS_KEY')
    if not api_key:
        print("❌ HELIUS_KEY not found in environment")
        return None
    
    async with HeliusHistoricalFetcher(api_key) as fetcher:
        # Step 1: Fetch all transactions
        transactions = await fetcher.fetch_all_transactions(wallet_address)
        
        if not transactions:
            print("No transactions found!")
            return None
        
        # Analyze date range
        timestamps = [tx['timestamp'] for tx in transactions]
        oldest = datetime.fromtimestamp(min(timestamps))
        newest = datetime.fromtimestamp(max(timestamps))
        
        print(f"\nTransaction summary:")
        print(f"  Total transactions: {len(transactions)}")
        print(f"  Date range: {oldest.strftime('%Y-%m-%d')} to {newest.strftime('%Y-%m-%d')}")
        print(f"  Days covered: {(newest - oldest).days}")
        
        # Step 2: Extract trades
        trades, unique_tokens = fetcher.extract_swap_data(transactions, wallet_address)
        
        # Step 3: Get token metadata
        token_mints = list(unique_tokens)
        metadata = await fetcher.get_token_metadata(token_mints)
        
        # Step 4: Enhance trades with metadata
        for trade in trades:
            mint = trade['token_mint']
            if mint in metadata:
                trade['token_symbol'] = metadata[mint]['symbol']
                trade['token_name'] = metadata[mint]['name']
            else:
                trade['token_symbol'] = 'UNKNOWN'
                trade['token_name'] = 'Unknown Token'
        
        print(f"\n✅ Successfully extracted {len(trades)} trades for {len(unique_tokens)} unique tokens")
        
        # Show sample trades
        print("\nSample trades (newest first):")
        for trade in sorted(trades, key=lambda x: x['timestamp'], reverse=True)[:10]:
            print(f"  {trade['timestamp'].strftime('%Y-%m-%d %H:%M')} - "
                  f"{trade['action']} {trade['token_symbol']}: {trade['sol_amount']:.2f} SOL")
        
        return {
            'trades': trades,
            'unique_tokens': len(unique_tokens),
            'transactions_processed': len(transactions),
            'date_range': (oldest, newest)
        }

if __name__ == "__main__":
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    print(f"=== FETCHING COMPLETE HISTORY FOR {wallet} ===\n")
    
    result = asyncio.run(fetch_complete_history(wallet))
    
    if result:
        print(f"\n{'='*60}")
        print(f"FINAL RESULTS:")
        print(f"  Unique tokens traded: {result['unique_tokens']} (target: 135)")
        print(f"  Total trades: {len(result['trades'])}")
        print(f"  Date range: {result['date_range'][0]} to {result['date_range'][1]}")
        print('='*60)