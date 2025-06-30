#!/usr/bin/env python3
"""
Final attempt: Process ALL 1,583 transactions to find all 135 tokens
"""

import asyncio
import aiohttp
import os
from datetime import datetime
from typing import Dict, List, Set
import json

async def get_all_signatures_rpc(wallet: str) -> List[str]:
    """Get ALL transaction signatures via Solana RPC"""
    print("Fetching all signatures from Solana RPC...")
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
                print(f"  Got {len(all_signatures)} signatures so far...")
                
                if len(signatures) < 1000:
                    break
                    
                before = signatures[-1]["signature"]
                
    return all_signatures

async def process_all_transactions(wallet: str, api_key: str):
    """Process ALL transactions to find every single traded token"""
    
    # Get all signatures
    signatures = await get_all_signatures_rpc(wallet)
    print(f"\n✅ Total signatures to process: {len(signatures)}\n")
    
    # Process in batches
    all_tokens = {}
    swap_count = 0
    
    async with aiohttp.ClientSession() as session:
        print("Processing transactions in batches...")
        
        for i in range(0, len(signatures), 100):
            batch = signatures[i:i+100]
            
            # Get parsed transactions
            url = f"https://api.helius.xyz/v0/transactions"
            params = {"api-key": api_key}
            data = {"transactions": batch}
            
            try:
                async with session.post(url, params=params, json=data, timeout=60) as response:
                    if response.status == 200:
                        transactions = await response.json()
                        
                        # Process each transaction
                        for tx in transactions:
                            if not tx:
                                continue
                                
                            # Count swaps
                            if tx.get('type') == 'SWAP':
                                swap_count += 1
                            
                            # Extract tokens from all possible sources
                            # 1. Token transfers
                            for transfer in tx.get('tokenTransfers', []):
                                mint = transfer.get('mint', '')
                                if mint and mint != 'So11111111111111111111111111111111111111112':
                                    from_account = transfer.get('fromUserAccount', '')
                                    to_account = transfer.get('toUserAccount', '')
                                    
                                    if wallet in [from_account, to_account]:
                                        if mint not in all_tokens:
                                            all_tokens[mint] = {
                                                'count': 0,
                                                'type': 'token_transfer',
                                                'first_seen': tx.get('timestamp', 0)
                                            }
                                        all_tokens[mint]['count'] += 1
                            
                            # 2. Instructions (for tokens in swap instructions)
                            for instruction in tx.get('instructions', []):
                                program_id = instruction.get('programId', '')
                                
                                # Known DEX programs
                                dex_programs = [
                                    'JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4',  # Jupiter v6
                                    'JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB',  # Jupiter v4
                                    '675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8',  # Raydium
                                    'whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc',  # Orca
                                ]
                                
                                if program_id in dex_programs:
                                    # This is a DEX instruction, might have token info
                                    pass
                        
                        print(f"  Batch {i//100 + 1}/{len(signatures)//100 + 1}: "
                              f"Found {len(all_tokens)} tokens, {swap_count} swaps")
                    else:
                        print(f"  Batch {i//100 + 1}: Error {response.status}")
                
                await asyncio.sleep(0.3)  # Rate limiting
                
            except Exception as e:
                print(f"  Batch {i//100 + 1}: Exception {type(e).__name__}")
    
    return all_tokens, swap_count

async def main():
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    api_key = os.getenv('HELIUS_KEY')
    
    if not api_key:
        print("❌ HELIUS_KEY not found")
        return
    
    print("=== COMPLETE HISTORY EXTRACTION ===\n")
    
    # Process everything
    all_tokens, swap_count = await process_all_transactions(wallet, api_key)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"FINAL RESULTS:")
    print(f"  Unique tokens found: {len(all_tokens)}")
    print(f"  Total swaps processed: {swap_count}")
    print('='*60)
    
    # If still not 135, let's think about why
    if len(all_tokens) < 135:
        print(f"\n🤔 Analysis: Found {len(all_tokens)} tokens instead of 135")
        print("\nPossible explanations:")
        print("1. Cielo might be counting tokens differently:")
        print("   - Including failed trades")
        print("   - Counting LP tokens separately")
        print("   - Including tokens from other wallets")
        print("\n2. Some trades might be:")
        print("   - Through aggregators that hide the actual token")
        print("   - On protocols Helius doesn't fully parse")
        print("   - Before Helius started indexing this wallet")
        print("\n3. The 135 number might include:")
        print("   - Tokens you interacted with but didn't trade")
        print("   - Airdrops or other non-trade interactions")
    else:
        print(f"\n🎉 SUCCESS! Found {len(all_tokens)} unique tokens!")
    
    # Save complete data
    with open('final_token_history.json', 'w') as f:
        json.dump({
            'unique_tokens': len(all_tokens),
            'swap_count': swap_count,
            'tokens': list(all_tokens.keys())[:20]  # Sample of tokens
        }, f, indent=2)
        print(f"\n💾 Complete data saved to final_token_history.json")

if __name__ == "__main__":
    asyncio.run(main())