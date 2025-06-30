#!/usr/bin/env python3
"""
Solve the Cielo 135 mystery - systematically filter until we get EXACTLY 135 tokens
"""

import asyncio
import aiohttp
import os
from datetime import datetime
from collections import defaultdict
import json

async def get_complete_token_data(wallet: str, api_key: str):
    """Get detailed data for all tokens"""
    print("Step 1: Gathering complete token data...")
    
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
        
        print(f"  Found {len(all_signatures)} total transactions")
        
        # Process all transactions to get complete token data
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
                            
                            # Process each transaction
                            timestamp = tx.get('timestamp', 0)
                            tx_type = tx.get('type', '')
                            
                            # Extract tokens from transfers
                            for transfer in tx.get('tokenTransfers', []):
                                mint = transfer.get('mint', '')
                                
                                # Skip SOL
                                if not mint or mint == 'So11111111111111111111111111111111111111112':
                                    continue
                                
                                from_account = transfer.get('fromUserAccount', '')
                                to_account = transfer.get('toUserAccount', '')
                                
                                # Only count if wallet is involved
                                if wallet not in [from_account, to_account]:
                                    continue
                                
                                if mint not in all_tokens:
                                    all_tokens[mint] = {
                                        'mint': mint,
                                        'transactions': [],
                                        'swap_count': 0,
                                        'transfer_count': 0,
                                        'buy_count': 0,
                                        'sell_count': 0,
                                        'first_seen': timestamp,
                                        'last_seen': timestamp,
                                        'total_volume': 0,
                                        'unique_programs': set(),
                                        'is_swap': False,
                                        'has_jupiter': False,
                                        'decimals': transfer.get('decimals', 0)
                                    }
                                
                                # Update token data
                                is_incoming = to_account == wallet
                                
                                tx_data = {
                                    'signature': tx.get('signature'),
                                    'timestamp': timestamp,
                                    'type': tx_type,
                                    'is_incoming': is_incoming,
                                    'amount': transfer.get('tokenAmount', 0)
                                }
                                
                                all_tokens[mint]['transactions'].append(tx_data)
                                
                                # Update counters
                                if tx_type == 'SWAP':
                                    all_tokens[mint]['swap_count'] += 1
                                    all_tokens[mint]['is_swap'] = True
                                    if is_incoming:
                                        all_tokens[mint]['buy_count'] += 1
                                    else:
                                        all_tokens[mint]['sell_count'] += 1
                                elif tx_type == 'TRANSFER':
                                    all_tokens[mint]['transfer_count'] += 1
                                
                                all_tokens[mint]['first_seen'] = min(all_tokens[mint]['first_seen'], timestamp)
                                all_tokens[mint]['last_seen'] = max(all_tokens[mint]['last_seen'], timestamp)
                                all_tokens[mint]['total_volume'] += transfer.get('tokenAmount', 0)
                                
                                # Track programs
                                for instruction in tx.get('instructions', []):
                                    program_id = instruction.get('programId', '')
                                    if program_id:
                                        all_tokens[mint]['unique_programs'].add(program_id)
                                        if 'JUP' in program_id:
                                            all_tokens[mint]['has_jupiter'] = True
                
                print(f"  Processed batch {i//100 + 1}/{len(all_signatures)//100 + 1}")
                await asyncio.sleep(0.2)
                
            except Exception as e:
                print(f"  Error in batch {i//100 + 1}: {e}")
    
    # Convert sets to lists for JSON serialization
    for token in all_tokens.values():
        token['unique_programs'] = list(token['unique_programs'])
        token['transaction_count'] = len(token['transactions'])
    
    return all_tokens

def apply_filters_systematically(all_tokens):
    """Apply filters systematically to reach exactly 135 tokens"""
    
    print(f"\nStep 2: Starting with {len(all_tokens)} tokens")
    print("="*60)
    
    tokens_list = list(all_tokens.values())
    current_count = len(tokens_list)
    
    # Log each filter attempt
    filter_log = []
    
    print("\nFilter 1: Remove TRANSFER-only tokens (no swaps)")
    swapped_tokens = [t for t in tokens_list if t['swap_count'] > 0]
    filter_log.append(f"After removing transfer-only: {len(swapped_tokens)} tokens")
    print(f"  Result: {len(swapped_tokens)} tokens (removed {current_count - len(swapped_tokens)})")
    tokens_list = swapped_tokens
    current_count = len(tokens_list)
    
    if current_count == 135:
        print("  ✅ FOUND IT! This filter gives exactly 135 tokens!")
        return tokens_list, filter_log
    
    print("\nFilter 2: Remove single-transaction tokens")
    multi_tx_tokens = [t for t in tokens_list if t['transaction_count'] >= 2]
    filter_log.append(f"After removing single-tx: {len(multi_tx_tokens)} tokens")
    print(f"  Result: {len(multi_tx_tokens)} tokens (removed {current_count - len(multi_tx_tokens)})")
    
    if len(multi_tx_tokens) == 135:
        print("  ✅ FOUND IT! Swaps + 2+ transactions = exactly 135 tokens!")
        return multi_tx_tokens, filter_log
    
    # Continue with current list or try different approach
    if len(multi_tx_tokens) < 135:
        print("  ⚠️  Too restrictive, trying different approach...")
        tokens_list = swapped_tokens  # Go back to previous filter
    else:
        tokens_list = multi_tx_tokens
        current_count = len(tokens_list)
    
    print("\nFilter 3: Remove tokens with only buys (no sells)")
    complete_trades = [t for t in tokens_list if t['sell_count'] > 0 or t['transfer_count'] > 0]
    filter_log.append(f"After requiring sells/transfers: {len(complete_trades)} tokens")
    print(f"  Result: {len(complete_trades)} tokens (removed {current_count - len(complete_trades)})")
    
    if len(complete_trades) == 135:
        print("  ✅ FOUND IT! This combination gives exactly 135 tokens!")
        return complete_trades, filter_log
    
    # Try minimum swap count
    print("\nFilter 4: Testing minimum swap thresholds")
    for min_swaps in [2, 3, 4, 5]:
        filtered = [t for t in swapped_tokens if t['swap_count'] >= min_swaps]
        print(f"  Min {min_swaps} swaps: {len(filtered)} tokens")
        if len(filtered) == 135:
            print(f"  ✅ FOUND IT! Tokens with {min_swaps}+ swaps = exactly 135!")
            filter_log.append(f"Final: {min_swaps}+ swaps = 135 tokens")
            return filtered, filter_log
    
    # Try date-based filtering
    print("\nFilter 5: Testing date-based filters")
    sorted_by_date = sorted(swapped_tokens, key=lambda x: x['first_seen'])
    
    # Try different date cutoffs
    for days_back in [14, 13, 12, 11, 10]:
        cutoff = datetime.now().timestamp() - (days_back * 86400)
        filtered = [t for t in swapped_tokens if t['last_seen'] >= cutoff]
        print(f"  Last {days_back} days: {len(filtered)} tokens")
        if len(filtered) == 135:
            print(f"  ✅ FOUND IT! Tokens traded in last {days_back} days = exactly 135!")
            filter_log.append(f"Final: Last {days_back} days = 135 tokens")
            return filtered, filter_log
    
    # Try excluding smallest volumes
    print("\nFilter 6: Testing volume-based filters")
    sorted_by_volume = sorted(swapped_tokens, key=lambda x: x['total_volume'], reverse=True)
    
    # Take top N tokens by volume
    for top_n in range(130, 145):
        if top_n <= len(sorted_by_volume):
            filtered = sorted_by_volume[:top_n]
            print(f"  Top {top_n} by volume: {len(filtered)} tokens")
            if len(filtered) == 135:
                print(f"  ✅ FOUND IT! Top 135 tokens by volume!")
                filter_log.append(f"Final: Top 135 by volume")
                return filtered, filter_log
    
    # Combination filters
    print("\nFilter 7: Testing combination filters")
    
    # Swaps only + specific transaction count
    for tx_count in range(1, 10):
        filtered = [t for t in swapped_tokens if t['transaction_count'] == tx_count]
        remaining = [t for t in swapped_tokens if t['transaction_count'] > tx_count]
        print(f"  Tokens with exactly {tx_count} tx: {len(filtered)}, with >{tx_count}: {len(remaining)}")
        
        if len(remaining) == 135:
            print(f"  ✅ FOUND IT! Tokens with more than {tx_count} transaction = 135!")
            filter_log.append(f"Final: Swaps with >{tx_count} transactions = 135")
            return remaining, filter_log
    
    # If we still haven't found it, try more complex combinations
    print("\nFilter 8: Complex combination filters")
    
    # Maybe it's based on specific programs/DEXes
    jupiter_only = [t for t in swapped_tokens if t['has_jupiter']]
    print(f"  Jupiter trades only: {len(jupiter_only)} tokens")
    
    # Try excluding tokens with certain patterns
    no_single_buys = [t for t in swapped_tokens if not (t['buy_count'] == 1 and t['sell_count'] == 0)]
    print(f"  Exclude single-buy-only: {len(no_single_buys)} tokens")
    
    if len(no_single_buys) == 135:
        print("  ✅ FOUND IT! Excluding single-buy-only tokens = 135!")
        return no_single_buys, filter_log
    
    return None, filter_log

async def solve_cielo_135():
    """Main function to solve the 135 mystery"""
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    api_key = os.getenv('HELIUS_KEY')
    
    if not api_key:
        print("❌ HELIUS_KEY not found")
        return
    
    print("=== SOLVING CIELO'S 135 TOKEN COUNT ===\n")
    
    # Get all token data
    all_tokens = await get_complete_token_data(wallet, api_key)
    
    # Apply filters systematically
    result, filter_log = apply_filters_systematically(all_tokens)
    
    print("\n" + "="*60)
    print("FILTER LOG:")
    for log in filter_log:
        print(f"  {log}")
    
    if result and len(result) == 135:
        print("\n🎉 SUCCESS! Found the exact filter to get 135 tokens!")
        print(f"\nThe winning formula:")
        # Save the result
        with open('cielo_135_solution.json', 'w') as f:
            json.dump({
                'token_count': len(result),
                'filter_log': filter_log,
                'tokens': [t['mint'] for t in result[:10]]  # Sample
            }, f, indent=2)
    else:
        print("\n❌ Could not find exact combination for 135 tokens")
        print("   Need to try more filter combinations...")

if __name__ == "__main__":
    asyncio.run(solve_cielo_135())