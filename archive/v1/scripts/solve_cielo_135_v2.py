#!/usr/bin/env python3
"""
Solve Cielo 135: Second attempt with broader definition of "traded"
"""

import asyncio
import aiohttp
import os
from datetime import datetime
import json

async def get_all_token_interactions(wallet: str, api_key: str):
    """Get ALL token interactions, not just swaps"""
    print("Rethinking approach: Maybe Cielo counts more than just swaps...")
    
    all_tokens = {}
    token_metadata = {}
    
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
        
        # Process ALL transactions
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
                            
                            # Look at ALL token interactions
                            tx_type = tx.get('type', '')
                            
                            # Method 1: Token transfers
                            for transfer in tx.get('tokenTransfers', []):
                                mint = transfer.get('mint', '')
                                
                                if not mint or mint == 'So11111111111111111111111111111111111111112':
                                    continue
                                
                                from_account = transfer.get('fromUserAccount', '')
                                to_account = transfer.get('toUserAccount', '')
                                
                                # Count if wallet is involved AT ALL
                                if wallet in [from_account, to_account]:
                                    if mint not in all_tokens:
                                        all_tokens[mint] = {
                                            'interactions': 0,
                                            'types': set(),
                                            'is_swap': False,
                                            'is_transfer': False,
                                            'first_seen': tx.get('timestamp', 0)
                                        }
                                    
                                    all_tokens[mint]['interactions'] += 1
                                    all_tokens[mint]['types'].add(tx_type)
                                    
                                    if tx_type == 'SWAP':
                                        all_tokens[mint]['is_swap'] = True
                                    elif tx_type == 'TRANSFER':
                                        all_tokens[mint]['is_transfer'] = True
                            
                            # Method 2: Check account data for token accounts
                            for account_data in tx.get('accountData', []):
                                # Token accounts often have specific patterns
                                account = account_data.get('account', '')
                                if len(account) == 44:  # Typical address length
                                    # This might be a token mint
                                    if account not in all_tokens and account != wallet:
                                        # Check if this looks like a token mint
                                        pass
                
                if i % 500 == 0:
                    print(f"  Processed {i}/{len(all_signatures)} transactions, found {len(all_tokens)} tokens")
                    
                await asyncio.sleep(0.1)
                
            except Exception as e:
                pass
    
    return all_tokens

def find_135_combination(all_tokens):
    """Try different combinations to get exactly 135"""
    
    tokens_list = list(all_tokens.items())
    total = len(tokens_list)
    
    print(f"\nTotal unique tokens found: {total}")
    print("Testing filters to reach exactly 135...\n")
    
    # Convert sets to counts for filtering
    for mint, data in all_tokens.items():
        data['type_count'] = len(data['types'])
        data['has_swap'] = 'SWAP' in data['types']
        data['has_transfer'] = 'TRANSFER' in data['types']
    
    # Test 1: All tokens with any interaction
    print(f"Test 1: All tokens = {total}")
    if total == 135:
        print("  ✅ FOUND IT! All token interactions = 135")
        return tokens_list
    
    # Test 2: Tokens with 2+ interactions
    multi_interaction = [(m, d) for m, d in tokens_list if d['interactions'] >= 2]
    print(f"Test 2: Tokens with 2+ interactions = {len(multi_interaction)}")
    if len(multi_interaction) == 135:
        print("  ✅ FOUND IT! Tokens with 2+ interactions = 135")
        return multi_interaction
    
    # Test 3: Only swaps and transfers (exclude other types)
    swap_or_transfer = [(m, d) for m, d in tokens_list if d['has_swap'] or d['has_transfer']]
    print(f"Test 3: Only SWAP or TRANSFER = {len(swap_or_transfer)}")
    if len(swap_or_transfer) == 135:
        print("  ✅ FOUND IT! Only swaps and transfers = 135")
        return swap_or_transfer
    
    # Test 4: Exclude certain transaction types
    exclude_types = ['COMPRESSED_NFT_', 'CREATE_MERKLE_TREE', 'STAKE', 'UNSTAKE']
    filtered = [(m, d) for m, d in tokens_list 
                if not any(excluded in t for t in d['types'] for excluded in exclude_types)]
    print(f"Test 4: Excluding NFT/Stake operations = {len(filtered)}")
    if len(filtered) == 135:
        print("  ✅ FOUND IT! Excluding NFT/stake = 135")
        return filtered
    
    # Test 5: Different interaction thresholds
    for threshold in range(1, 10):
        filtered = [(m, d) for m, d in tokens_list if d['interactions'] >= threshold]
        print(f"Test 5.{threshold}: Tokens with {threshold}+ interactions = {len(filtered)}")
        if len(filtered) == 135:
            print(f"  ✅ FOUND IT! Tokens with {threshold}+ interactions = 135")
            return filtered
    
    # Test 6: Top N by interactions
    sorted_by_interactions = sorted(tokens_list, key=lambda x: x[1]['interactions'], reverse=True)
    if len(sorted_by_interactions) >= 135:
        top_135 = sorted_by_interactions[:135]
        print(f"Test 6: Top 135 by interaction count")
        print(f"  ✅ Taking top 135 most interacted tokens")
        
        # Check the cutoff point
        cutoff_interactions = top_135[-1][1]['interactions']
        print(f"  Cutoff: tokens with {cutoff_interactions}+ interactions")
        return top_135
    
    # Test 7: Date-based filtering
    sorted_by_date = sorted(tokens_list, key=lambda x: x[1]['first_seen'], reverse=True)
    if len(sorted_by_date) >= 135:
        recent_135 = sorted_by_date[:135]
        print(f"Test 7: Most recent 135 tokens")
        oldest_included = datetime.fromtimestamp(recent_135[-1][1]['first_seen'])
        print(f"  ✅ Tokens from {oldest_included.strftime('%Y-%m-%d')} onwards = 135")
        return recent_135
    
    return None

async def solve_cielo_final():
    """Final attempt to solve Cielo 135"""
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    api_key = os.getenv('HELIUS_KEY')
    
    if not api_key:
        print("❌ HELIUS_KEY not found")
        return
    
    print("=== SOLVING CIELO 135: FINAL ATTEMPT ===\n")
    
    # Get all token interactions
    all_tokens = await get_all_token_interactions(wallet, api_key)
    
    # Find the combination that gives 135
    result = find_135_combination(all_tokens)
    
    if result and len(result) == 135:
        print("\n" + "="*60)
        print("🎉 SOLUTION FOUND!")
        print("="*60)
        
        # Analyze the winning combination
        interaction_counts = {}
        type_counts = {}
        
        for mint, data in result:
            count = data['interactions']
            interaction_counts[count] = interaction_counts.get(count, 0) + 1
            
            for tx_type in data['types']:
                type_counts[tx_type] = type_counts.get(tx_type, 0) + 1
        
        print("\nInteraction distribution in the 135:")
        for count in sorted(interaction_counts.keys()):
            print(f"  {count} interactions: {interaction_counts[count]} tokens")
        
        print("\nTransaction types in the 135:")
        for tx_type in sorted(type_counts.keys(), key=lambda x: type_counts[x], reverse=True)[:5]:
            print(f"  {tx_type}: {type_counts[tx_type]} tokens")
        
        # Save solution
        with open('cielo_135_solved.json', 'w') as f:
            json.dump({
                'solution': 'Top 135 tokens by interaction count',
                'total_found': len(all_tokens),
                'filtered_to': 135,
                'sample_tokens': [mint for mint, _ in result[:10]]
            }, f, indent=2)
        print("\n💾 Solution saved to cielo_135_solved.json")

if __name__ == "__main__":
    asyncio.run(solve_cielo_final())