#!/usr/bin/env python3
"""Debug script to analyze all transaction types and find swaps"""

import os
import asyncio
import aiohttp
from collections import defaultdict
import json

HELIUS_KEY = os.getenv("HELIUS_KEY", "09cd02b2-f35d-4d54-ac9b-a9033919d6ee")
WALLET = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"

async def analyze_all_transactions():
    """Fetch all transactions and analyze them"""
    
    async with aiohttp.ClientSession() as session:
        url = f"https://api.helius.xyz/v0/addresses/{WALLET}/transactions"
        
        # Fetch multiple pages of ALL transactions
        all_txs = []
        before_sig = None
        
        print("Fetching all transactions (no type filter)...")
        for page in range(10):  # Get first 1000 transactions
            params = {
                "api-key": HELIUS_KEY,
                "limit": 100,
                "maxSupportedTransactionVersion": "0"
            }
            
            if before_sig:
                params["before"] = before_sig
                
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                if isinstance(data, list) and len(data) > 0:
                    all_txs.extend(data)
                    print(f"Page {page + 1}: Got {len(data)} transactions")
                    before_sig = data[-1]['signature']
                    
                    if len(data) < 100:
                        print(f"Last page reached")
                        break
                else:
                    break
                    
        print(f"\nTotal transactions fetched: {len(all_txs)}")
        
        # Analyze transaction types
        type_counts = defaultdict(int)
        source_counts = defaultdict(int)
        potential_swaps = []
        
        for tx in all_txs:
            tx_type = tx.get('type', 'NONE')
            source = tx.get('source', 'NONE')
            type_counts[tx_type] += 1
            source_counts[source] += 1
            
            # Look for swap-like patterns in non-SWAP transactions
            token_transfers = tx.get('tokenTransfers', [])
            
            # Pattern 1: Multiple token transfers involving user
            if len(token_transfers) >= 2 and tx_type != 'SWAP':
                user_sent = False
                user_received = False
                
                for tt in token_transfers:
                    if tt.get('fromUserAccount') == WALLET:
                        user_sent = True
                    if tt.get('toUserAccount') == WALLET:
                        user_received = True
                        
                if user_sent and user_received:
                    potential_swaps.append({
                        'signature': tx['signature'],
                        'type': tx_type,
                        'source': source,
                        'transfers': len(token_transfers),
                        'description': tx.get('description', 'No description')
                    })
                    
        print("\n=== Transaction Type Distribution ===")
        for tx_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"{tx_type}: {count}")
            
        print("\n=== Source Distribution ===")
        for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"{source}: {count}")
            
        print(f"\n=== Potential Swaps in Non-SWAP Transactions ===")
        print(f"Found {len(potential_swaps)} transactions that look like swaps but aren't marked as SWAP")
        
        # Show examples
        for i, ps in enumerate(potential_swaps[:5]):
            print(f"\nExample {i+1}:")
            print(f"  Type: {ps['type']}")
            print(f"  Source: {ps['source']}")
            print(f"  Transfers: {ps['transfers']}")
            print(f"  Description: {ps['description'][:100]}...")
            print(f"  Signature: {ps['signature'][:40]}...")
            
        # Check specific transaction patterns
        print("\n=== Checking Specific Patterns ===")
        
        # Pattern: TRANSFER transactions from known DEXs
        dex_transfers = []
        for tx in all_txs:
            if tx.get('type') == 'TRANSFER':
                desc = tx.get('description', '').lower()
                if any(dex in desc for dex in ['jupiter', 'raydium', 'orca', 'pump', 'meteora']):
                    dex_transfers.append(tx)
                    
        print(f"TRANSFER transactions mentioning DEXs: {len(dex_transfers)}")
        
        # Save sample for analysis
        sample_data = {
            'total_transactions': len(all_txs),
            'type_distribution': dict(type_counts),
            'source_distribution': dict(source_counts),
            'potential_swaps_count': len(potential_swaps),
            'potential_swaps_examples': potential_swaps[:10],
            'dex_transfers_count': len(dex_transfers),
            'dex_transfers_examples': [
                {
                    'signature': tx['signature'],
                    'description': tx.get('description', ''),
                    'type': tx.get('type'),
                    'source': tx.get('source')
                } for tx in dex_transfers[:5]
            ]
        }
        
        with open('transaction_analysis.json', 'w') as f:
            json.dump(sample_data, f, indent=2)
            
        print("\nDetailed analysis saved to transaction_analysis.json")

if __name__ == "__main__":
    asyncio.run(analyze_all_transactions()) 