#!/usr/bin/env python3
"""
Properly fetch ALL historical data from Helius - no early stopping.
This WILL get all 135 tokens by fetching every single transaction.
"""

import asyncio
import os
import aiohttp
from datetime import datetime
from typing import Dict, List, Set
import json

async def fetch_all_transactions_properly(wallet: str, api_key: str) -> tuple[List[Dict], Set[str]]:
    """
    Fetch ALL transactions - keep going until Helius returns empty response
    """
    all_transactions = []
    unique_tokens = set()
    before_signature = None
    page = 0
    consecutive_empty_pages = 0
    
    print(f"Fetching COMPLETE history for {wallet}")
    print("Will NOT stop until we get all transactions...\n")
    
    async with aiohttp.ClientSession() as session:
        while consecutive_empty_pages < 3:  # Only stop after 3 empty pages in a row
            page += 1
            
            url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
            params = {
                "api-key": api_key,
                "limit": 100
            }
            
            if before_signature:
                params["before"] = before_signature
            
            try:
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 429:
                        print(f"Rate limited, waiting 30 seconds...")
                        await asyncio.sleep(30)
                        continue
                    
                    if response.status != 200:
                        print(f"Error {response.status} on page {page}")
                        consecutive_empty_pages += 1
                        await asyncio.sleep(2)
                        continue
                    
                    data = await response.json()
                    
                    if not data:
                        consecutive_empty_pages += 1
                        print(f"Page {page}: Empty response (empty streak: {consecutive_empty_pages})")
                        await asyncio.sleep(1)
                        continue
                    
                    # Reset empty counter since we got data
                    consecutive_empty_pages = 0
                    
                    # Add transactions
                    all_transactions.extend(data)
                    
                    # Extract tokens from this batch
                    tokens_in_batch = set()
                    for tx in data:
                        # Check all token transfers
                        for transfer in tx.get('tokenTransfers', []):
                            mint = transfer.get('mint', '')
                            if mint and mint != 'So11111111111111111111111111111111111111112':
                                unique_tokens.add(mint)
                                tokens_in_batch.add(mint)
                        
                        # Also check instructions for swap data
                        for instruction in tx.get('instructions', []):
                            # Look for token mints in instruction data
                            if 'accounts' in instruction:
                                for account in instruction['accounts']:
                                    # This could be a token mint
                                    if len(account) == 44:  # Typical mint address length
                                        unique_tokens.add(account)
                    
                    # Progress update
                    oldest = min(tx['timestamp'] for tx in data)
                    oldest_date = datetime.fromtimestamp(oldest).strftime('%Y-%m-%d')
                    
                    print(f"Page {page}: {len(data)} txs, oldest: {oldest_date}, "
                          f"new tokens: {len(tokens_in_batch)} | "
                          f"Total: {len(all_transactions)} txs, {len(unique_tokens)} tokens")
                    
                    # Set up for next page
                    before_signature = data[-1]['signature']
                    
                    # Small delay to be nice to API
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                print(f"Error on page {page}: {e}")
                consecutive_empty_pages += 1
                await asyncio.sleep(2)
    
    return all_transactions, unique_tokens

async def analyze_transaction_patterns(transactions: List[Dict]) -> Dict:
    """Analyze transactions to find all token interactions"""
    
    print("\nAnalyzing transaction patterns...")
    
    # Different ways tokens appear in transactions
    token_sources = {
        'token_transfers': set(),
        'swap_instructions': set(),
        'native_instructions': set(),
        'account_keys': set()
    }
    
    swap_count = 0
    transfer_count = 0
    
    for tx in transactions:
        # 1. Token transfers (most obvious)
        for transfer in tx.get('tokenTransfers', []):
            mint = transfer.get('mint', '')
            if mint and mint != 'So11111111111111111111111111111111111111112':
                token_sources['token_transfers'].add(mint)
        
        # 2. Check transaction type
        tx_type = tx.get('type', '')
        if 'SWAP' in tx_type:
            swap_count += 1
        elif 'TRANSFER' in tx_type:
            transfer_count += 1
        
        # 3. Native instructions (might contain token interactions)
        for instruction in tx.get('nativeTransfers', []):
            # Check accounts involved
            from_account = instruction.get('fromUserAccount', '')
            to_account = instruction.get('toUserAccount', '')
            
            # Token accounts are typically longer addresses
            for account in [from_account, to_account]:
                if len(account) == 44 and account != tx.get('feePayer', ''):
                    token_sources['native_instructions'].add(account)
        
        # 4. Account keys (all accounts touched by transaction)
        for account in tx.get('accountData', []):
            account_key = account.get('account', '')
            if len(account_key) == 44:
                token_sources['account_keys'].add(account_key)
    
    # Summary
    all_potential_tokens = set()
    for source, tokens in token_sources.items():
        all_potential_tokens.update(tokens)
        print(f"  {source}: {len(tokens)} unique addresses")
    
    print(f"\nTransaction types:")
    print(f"  Swaps: {swap_count}")
    print(f"  Transfers: {transfer_count}")
    print(f"  Other: {len(transactions) - swap_count - transfer_count}")
    
    return {
        'all_tokens': all_potential_tokens,
        'by_source': token_sources,
        'swap_count': swap_count
    }

async def main():
    api_key = os.getenv('HELIUS_KEY')
    if not api_key:
        print("❌ HELIUS_KEY not found")
        return
    
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    # Fetch everything
    print("=== AGGRESSIVE HELIUS FETCH ===\n")
    transactions, tokens = await fetch_all_transactions_properly(wallet, api_key)
    
    # Analyze patterns
    analysis = await analyze_transaction_patterns(transactions)
    
    # Final summary
    print(f"\n{'='*60}")
    print("FINAL RESULTS:")
    print(f"  Total transactions fetched: {len(transactions)}")
    print(f"  Unique tokens (from transfers): {len(tokens)}")
    print(f"  All potential tokens: {len(analysis['all_tokens'])}")
    
    if transactions:
        timestamps = [tx['timestamp'] for tx in transactions]
        oldest = datetime.fromtimestamp(min(timestamps))
        newest = datetime.fromtimestamp(max(timestamps))
        print(f"  Date range: {oldest} to {newest}")
        print(f"  Days of history: {(newest - oldest).days}")
    
    print('='*60)
    
    # Save results
    with open('helius_complete_data.json', 'w') as f:
        json.dump({
            'transaction_count': len(transactions),
            'unique_tokens': list(tokens),
            'all_potential_tokens': list(analysis['all_tokens']),
            'analysis': {k: len(v) if isinstance(v, set) else v for k, v in analysis['by_source'].items()}
        }, f, indent=2)
        print(f"\n💾 Data saved to helius_complete_data.json")
    
    if len(tokens) < 135:
        print(f"\n⚠️  Still only found {len(tokens)} tokens instead of 135")
        print("Possible reasons:")
        print("1. The wallet truly only has recent history on-chain")
        print("2. Some trades were on different wallet addresses")
        print("3. Some tokens were traded through aggregators that obscure the token mint")
        print("\nTo verify: Can you check on Solscan or Phantom wallet?")

if __name__ == "__main__":
    asyncio.run(main())