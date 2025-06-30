#!/usr/bin/env python3
"""
Fetch all traded tokens using Solana RPC + Helius for transaction details
This combines RPC for complete history with Helius for parsing
"""

import asyncio
import aiohttp
import os
from datetime import datetime
from typing import Dict, List, Set
import json

async def get_all_signatures_rpc(wallet: str) -> List[str]:
    """Get ALL transaction signatures via Solana RPC"""
    all_signatures = []
    before = None
    
    async with aiohttp.ClientSession() as session:
        while True:
            params = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [
                    wallet,
                    {"limit": 1000, "before": before} if before else {"limit": 1000}
                ]
            }
            
            async with session.post("https://api.mainnet-beta.solana.com", json=params) as response:
                result = await response.json()
                if "result" not in result or not result["result"]:
                    break
                    
                signatures = result["result"]
                all_signatures.extend([sig["signature"] for sig in signatures])
                
                if len(signatures) < 1000:
                    break
                    
                before = signatures[-1]["signature"]
                
    return all_signatures

async def get_transaction_details_batch(signatures: List[str], api_key: str) -> List[Dict]:
    """Get transaction details from Helius in batches"""
    transactions = []
    
    async with aiohttp.ClientSession() as session:
        # Process in batches of 100
        for i in range(0, len(signatures), 100):
            batch = signatures[i:i+100]
            
            url = "https://api.helius.xyz/v0/transactions"
            params = {"api-key": api_key}
            data = {"transactions": batch}
            
            try:
                async with session.post(url, params=params, json=data, timeout=30) as response:
                    if response.status == 200:
                        result = await response.json()
                        transactions.extend(result)
                        print(f"  Batch {i//100 + 1}: Got {len(result)} transaction details")
                    else:
                        print(f"  Batch {i//100 + 1}: Error {response.status}")
                        
                await asyncio.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                print(f"  Batch {i//100 + 1}: Exception {e}")
    
    return transactions

async def extract_traded_tokens(transactions: List[Dict], wallet: str) -> Dict[str, Dict]:
    """Extract unique traded tokens from transactions"""
    traded_tokens = {}
    
    for tx in transactions:
        if not tx or tx.get('type') != 'SWAP':
            continue
            
        timestamp = datetime.fromtimestamp(tx.get('timestamp', 0))
        
        # Extract tokens from transfers
        for transfer in tx.get('tokenTransfers', []):
            mint = transfer.get('mint', '')
            if mint and mint != 'So11111111111111111111111111111111111111112':
                from_account = transfer.get('fromUserAccount', '')
                to_account = transfer.get('toUserAccount', '')
                
                # If wallet is involved in the transfer
                if wallet in [from_account, to_account]:
                    if mint not in traded_tokens:
                        traded_tokens[mint] = {
                            'first_trade': timestamp,
                            'last_trade': timestamp,
                            'trade_count': 0,
                            'signatures': []
                        }
                    
                    traded_tokens[mint]['trade_count'] += 1
                    traded_tokens[mint]['last_trade'] = max(traded_tokens[mint]['last_trade'], timestamp)
                    traded_tokens[mint]['first_trade'] = min(traded_tokens[mint]['first_trade'], timestamp)
                    traded_tokens[mint]['signatures'].append(tx.get('signature', ''))
    
    return traded_tokens

async def main():
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    api_key = os.getenv('HELIUS_KEY')
    
    if not api_key:
        print("❌ HELIUS_KEY not found")
        return
    
    print("=== FETCHING COMPLETE TOKEN HISTORY ===\n")
    
    # Step 1: Get ALL signatures from Solana RPC
    print("1. Getting all transaction signatures from Solana RPC...")
    signatures = await get_all_signatures_rpc(wallet)
    print(f"   ✅ Found {len(signatures)} total transactions\n")
    
    # Step 2: Get transaction details from Helius
    print("2. Fetching transaction details from Helius...")
    transactions = await get_transaction_details_batch(signatures[:500], api_key)  # Start with first 500
    print(f"   ✅ Got details for {len(transactions)} transactions\n")
    
    # Step 3: Extract traded tokens
    print("3. Extracting traded tokens...")
    traded_tokens = await extract_traded_tokens(transactions, wallet)
    print(f"   ✅ Found {len(traded_tokens)} unique traded tokens\n")
    
    # Step 4: Get more transactions if needed
    if len(traded_tokens) < 135 and len(signatures) > 500:
        print("4. Fetching more transaction details to find all 135 tokens...")
        more_transactions = await get_transaction_details_batch(signatures[500:1000], api_key)
        more_tokens = await extract_traded_tokens(more_transactions, wallet)
        
        # Merge tokens
        for mint, data in more_tokens.items():
            if mint in traded_tokens:
                traded_tokens[mint]['trade_count'] += data['trade_count']
                traded_tokens[mint]['last_trade'] = max(traded_tokens[mint]['last_trade'], data['last_trade'])
                traded_tokens[mint]['first_trade'] = min(traded_tokens[mint]['first_trade'], data['first_trade'])
                traded_tokens[mint]['signatures'].extend(data['signatures'])
            else:
                traded_tokens[mint] = data
        
        print(f"   ✅ Now have {len(traded_tokens)} unique traded tokens\n")
    
    # Summary
    print(f"{'='*60}")
    print(f"FINAL RESULTS:")
    print(f"  Total unique tokens found: {len(traded_tokens)}")
    
    if traded_tokens:
        # Date range
        all_first_trades = [data['first_trade'] for data in traded_tokens.values()]
        all_last_trades = [data['last_trade'] for data in traded_tokens.values()]
        
        oldest = min(all_first_trades)
        newest = max(all_last_trades)
        
        print(f"  Trading history: {oldest.strftime('%Y-%m-%d')} to {newest.strftime('%Y-%m-%d')}")
        print(f"  Days of trading: {(newest - oldest).days}")
    
    print('='*60)
    
    # Save results
    with open('complete_token_history.json', 'w') as f:
        json.dump({
            'unique_tokens': len(traded_tokens),
            'tokens': {mint: {
                'first_trade': data['first_trade'].isoformat(),
                'last_trade': data['last_trade'].isoformat(),
                'trade_count': data['trade_count']
            } for mint, data in traded_tokens.items()}
        }, f, indent=2)
        print(f"\n💾 Data saved to complete_token_history.json")
    
    if len(traded_tokens) >= 135:
        print(f"\n🎉 SUCCESS! Found all {len(traded_tokens)} tokens!")
    else:
        print(f"\n📝 Found {len(traded_tokens)} tokens so far. To get all 135:")
        print("   - Process more of the 1,583 transactions")
        print("   - Or check if some trades were on other DEXes")

if __name__ == "__main__":
    asyncio.run(main())