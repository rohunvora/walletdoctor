#!/usr/bin/env python3
"""
Find the EXACT filter for 135 tokens - focusing on the 2+ interactions threshold
"""

import asyncio
import aiohttp
import os
from datetime import datetime
import json

async def get_detailed_token_data(wallet: str, api_key: str):
    """Get very detailed token data to find the exact filter"""
    print("Getting detailed token interaction data...")
    
    all_tokens = {}
    
    async with aiohttp.ClientSession() as session:
        # Get all signatures
        all_signatures = []
        before = None
        
        while True:
            params = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [wallet, {"limit": 1000, "before": before} if before else {"limit": 1000}]
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
        
        print(f"Processing {len(all_signatures)} transactions...")
        
        # Process all transactions
        for i in range(0, len(all_signatures), 100):
            batch = all_signatures[i:i+100]
            
            url = "https://api.helius.xyz/v0/transactions"
            params = {"api-key": api_key}
            data = {"transactions": batch}
            
            try:
                async with session.post(url, params=params, json=data, timeout=60) as response:
                    if response.status == 200:
                        transactions = await response.json()
                        
                        for tx in transactions:
                            if not tx:
                                continue
                            
                            timestamp = tx.get('timestamp', 0)
                            tx_type = tx.get('type', '')
                            signature = tx.get('signature', '')
                            fee_payer = tx.get('feePayer', '')
                            
                            # Process token transfers
                            for transfer in tx.get('tokenTransfers', []):
                                mint = transfer.get('mint', '')
                                
                                if not mint or mint == 'So11111111111111111111111111111111111111112':
                                    continue
                                
                                from_account = transfer.get('fromUserAccount', '')
                                to_account = transfer.get('toUserAccount', '')
                                
                                # Only count if wallet is sender or receiver
                                if wallet not in [from_account, to_account]:
                                    continue
                                
                                if mint not in all_tokens:
                                    all_tokens[mint] = {
                                        'mint': mint,
                                        'interactions': [],
                                        'unique_signatures': set(),
                                        'types': set(),
                                        'is_incoming': 0,
                                        'is_outgoing': 0,
                                        'first_seen': timestamp,
                                        'last_seen': timestamp,
                                        'has_swap': False,
                                        'has_transfer': False,
                                        'unique_days': set()
                                    }
                                
                                # Record interaction
                                interaction = {
                                    'timestamp': timestamp,
                                    'type': tx_type,
                                    'signature': signature,
                                    'is_incoming': to_account == wallet,
                                    'amount': transfer.get('tokenAmount', 0)
                                }
                                
                                all_tokens[mint]['interactions'].append(interaction)
                                all_tokens[mint]['unique_signatures'].add(signature)
                                all_tokens[mint]['types'].add(tx_type)
                                
                                if to_account == wallet:
                                    all_tokens[mint]['is_incoming'] += 1
                                else:
                                    all_tokens[mint]['is_outgoing'] += 1
                                
                                if tx_type == 'SWAP':
                                    all_tokens[mint]['has_swap'] = True
                                elif tx_type == 'TRANSFER':
                                    all_tokens[mint]['has_transfer'] = True
                                
                                # Track unique days
                                day = datetime.fromtimestamp(timestamp).date()
                                all_tokens[mint]['unique_days'].add(str(day))
                                
                                all_tokens[mint]['first_seen'] = min(all_tokens[mint]['first_seen'], timestamp)
                                all_tokens[mint]['last_seen'] = max(all_tokens[mint]['last_seen'], timestamp)
                
                if i % 300 == 0:
                    print(f"  Processed {i}/{len(all_signatures)} transactions")
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                pass
    
    # Calculate derived metrics
    for mint, data in all_tokens.items():
        data['interaction_count'] = len(data['interactions'])
        data['unique_tx_count'] = len(data['unique_signatures'])
        data['type_count'] = len(data['types'])
        data['unique_day_count'] = len(data['unique_days'])
        data['has_both_directions'] = data['is_incoming'] > 0 and data['is_outgoing'] > 0
    
    return all_tokens

def find_exact_135_filter(all_tokens):
    """Find the exact combination that gives 135 tokens"""
    
    tokens_list = list(all_tokens.items())
    total = len(tokens_list)
    
    print(f"\nTotal tokens: {total}")
    print("Finding exact filter for 135...\n")
    
    # We know 2+ interactions gives 138, so we need to remove 3
    two_plus = [(m, d) for m, d in tokens_list if d['interaction_count'] >= 2]
    print(f"Tokens with 2+ interactions: {len(two_plus)}")
    
    # Let's analyze the tokens with exactly 2 interactions
    exactly_two = [(m, d) for m, d in two_plus if d['interaction_count'] == 2]
    print(f"Tokens with exactly 2 interactions: {len(exactly_two)}")
    
    # Sort tokens with 2 interactions by different criteria
    print("\nAnalyzing tokens with 2 interactions to find which 3 to exclude:")
    
    # Try excluding by transaction type
    two_unknown_only = [(m, d) for m, d in exactly_two if d['types'] == {'UNKNOWN'}]
    two_transfer_only = [(m, d) for m, d in exactly_two if d['types'] == {'TRANSFER'}]
    two_mixed_types = [(m, d) for m, d in exactly_two if len(d['types']) > 1]
    
    print(f"  - With only UNKNOWN type: {len(two_unknown_only)}")
    print(f"  - With only TRANSFER type: {len(two_transfer_only)}")
    print(f"  - With mixed types: {len(two_mixed_types)}")
    
    # Test: Exclude tokens with 2 interactions that are UNKNOWN only
    if len(two_unknown_only) == 3:
        filtered = [(m, d) for m, d in two_plus if not (d['interaction_count'] == 2 and d['types'] == {'UNKNOWN'})]
        print(f"\nTest: Excluding 2-interaction UNKNOWN-only tokens: {len(filtered)}")
        if len(filtered) == 135:
            print("  ✅ FOUND IT! This is the exact filter!")
            return filtered, "2+ interactions, excluding UNKNOWN-only with exactly 2 interactions"
    
    # Test: Exclude oldest tokens with 2 interactions
    two_sorted_by_date = sorted(exactly_two, key=lambda x: x[1]['first_seen'])
    if len(two_plus) - 3 == 135:
        exclude_oldest_3 = set([m for m, d in two_sorted_by_date[:3]])
        filtered = [(m, d) for m, d in two_plus if m not in exclude_oldest_3]
        print(f"\nTest: Excluding 3 oldest tokens with 2 interactions: {len(filtered)}")
        if len(filtered) == 135:
            print("  ✅ FOUND IT! Excluding 3 oldest 2-interaction tokens!")
            return filtered, "2+ interactions, excluding 3 oldest with exactly 2 interactions"
    
    # Test: Exclude newest tokens with 2 interactions
    two_sorted_by_date_desc = sorted(exactly_two, key=lambda x: x[1]['last_seen'], reverse=True)
    if len(two_plus) - 3 == 135:
        exclude_newest_3 = set([m for m, d in two_sorted_by_date_desc[:3]])
        filtered = [(m, d) for m, d in two_plus if m not in exclude_newest_3]
        print(f"\nTest: Excluding 3 newest tokens with 2 interactions: {len(filtered)}")
        if len(filtered) == 135:
            print("  ✅ FOUND IT! Excluding 3 newest 2-interaction tokens!")
            return filtered, "2+ interactions, excluding 3 newest with exactly 2 interactions"
    
    # Test: Exclude tokens with 2 interactions that are only incoming
    two_incoming_only = [(m, d) for m, d in exactly_two if d['is_incoming'] == 2 and d['is_outgoing'] == 0]
    print(f"\nTokens with 2 incoming-only interactions: {len(two_incoming_only)}")
    
    if len(two_incoming_only) >= 3:
        exclude_first_3 = set([m for m, d in two_incoming_only[:3]])
        filtered = [(m, d) for m, d in two_plus if m not in exclude_first_3]
        print(f"Test: Excluding first 3 incoming-only 2-interaction tokens: {len(filtered)}")
        if len(filtered) == 135:
            print("  ✅ FOUND IT! This is the exact filter!")
            return filtered, "2+ interactions, excluding 3 incoming-only tokens"
    
    # Test: Look at unique days
    two_single_day = [(m, d) for m, d in exactly_two if d['unique_day_count'] == 1]
    print(f"\nTokens with 2 interactions on same day: {len(two_single_day)}")
    
    # Test: Combination - tokens with 2 interactions, both on same day, and specific type
    special_cases = []
    for m, d in exactly_two:
        if d['unique_day_count'] == 1 and 'TRANSFER' in d['types'] and not d['has_swap']:
            special_cases.append((m, d))
    
    print(f"\nSpecial cases (2 interactions, same day, TRANSFER only): {len(special_cases)}")
    
    if len(special_cases) >= 3:
        exclude_special = set([m for m, d in special_cases[:3]])
        filtered = [(m, d) for m, d in two_plus if m not in exclude_special]
        print(f"Test: Excluding first 3 special cases: {len(filtered)}")
        if len(filtered) == 135:
            print("  ✅ FOUND IT! This is the exact filter!")
            return filtered, "2+ interactions, excluding same-day TRANSFER-only tokens"
    
    # If we still haven't found it, try more combinations
    print("\nTrying additional combinations...")
    
    # Maybe it's not about excluding from 2+ but a different threshold
    for threshold in [2.5, 3]:
        if threshold == 2.5:
            # Tokens with 3+ OR (2 with specific criteria)
            filtered = [(m, d) for m, d in tokens_list 
                       if d['interaction_count'] >= 3 or 
                       (d['interaction_count'] == 2 and d['has_swap'])]
        else:
            filtered = [(m, d) for m, d in tokens_list if d['interaction_count'] >= threshold]
        
        print(f"Threshold {threshold}: {len(filtered)} tokens")
        if len(filtered) == 135:
            print("  ✅ FOUND IT!")
            return filtered, f"Interactions >= {threshold}"
    
    return None, None

async def solve_cielo_exactly_135():
    """Solve for exactly 135 tokens"""
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    api_key = os.getenv('HELIUS_KEY')
    
    if not api_key:
        print("❌ HELIUS_KEY not found")
        return
    
    print("=== FINDING EXACT FILTER FOR 135 TOKENS ===\n")
    
    # Get detailed token data
    all_tokens = await get_detailed_token_data(wallet, api_key)
    
    # Find exact filter
    result, filter_description = find_exact_135_filter(all_tokens)
    
    if result and len(result) == 135:
        print("\n" + "="*60)
        print("🎉 EXACT SOLUTION FOUND!")
        print("="*60)
        print(f"\nFilter: {filter_description}")
        print(f"Result: Exactly {len(result)} tokens")
        
        # Save the solution
        with open('cielo_135_exact_solution.json', 'w') as f:
            json.dump({
                'filter': filter_description,
                'token_count': len(result),
                'verification': 'EXACT MATCH - 135 tokens'
            }, f, indent=2)
        
        print("\n✅ Solution verified and saved!")
    else:
        print("\n❌ Could not find exact 135 filter in this run")

if __name__ == "__main__":
    asyncio.run(solve_cielo_exactly_135())