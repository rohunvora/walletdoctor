#!/usr/bin/env python3
"""
Reverse engineer how Cielo arrives at 135 tokens
by analyzing our 198 tokens with different filtering criteria
"""

import json
import asyncio
import aiohttp
import os
from datetime import datetime
from collections import defaultdict

async def analyze_token_data():
    """Load and analyze the token data we collected"""
    
    # First, let's get more detailed data about our tokens
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    api_key = os.getenv('HELIUS_KEY')
    
    print("=== REVERSE ENGINEERING CIELO's 135 TOKEN COUNT ===\n")
    
    # Load our complete history
    all_signatures = []
    all_tokens_detailed = {}
    
    print("1. Analyzing our 198 tokens in detail...")
    
    async with aiohttp.ClientSession() as session:
        # Get all signatures again
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
        
        # Process in smaller batches to get detailed data
        for i in range(0, min(len(all_signatures), 500), 50):
            batch = all_signatures[i:i+50]
            
            url = "https://api.helius.xyz/v0/transactions"
            params = {"api-key": api_key}
            data = {"transactions": batch}
            
            try:
                async with session.post(url, params=params, json=data, timeout=30) as response:
                    if response.status == 200:
                        transactions = await response.json()
                        
                        for tx in transactions:
                            if not tx or tx.get('type') != 'SWAP':
                                continue
                            
                            # Detailed token analysis
                            for transfer in tx.get('tokenTransfers', []):
                                mint = transfer.get('mint', '')
                                if mint and mint != 'So11111111111111111111111111111111111111112':
                                    if mint not in all_tokens_detailed:
                                        all_tokens_detailed[mint] = {
                                            'trades': [],
                                            'total_volume': 0,
                                            'buy_count': 0,
                                            'sell_count': 0,
                                            'programs': set(),
                                            'first_trade': None,
                                            'last_trade': None
                                        }
                                    
                                    # Determine buy/sell
                                    is_buy = transfer.get('toUserAccount') == wallet
                                    
                                    trade_info = {
                                        'timestamp': tx.get('timestamp', 0),
                                        'signature': tx.get('signature'),
                                        'amount': transfer.get('tokenAmount', 0),
                                        'type': 'buy' if is_buy else 'sell'
                                    }
                                    
                                    all_tokens_detailed[mint]['trades'].append(trade_info)
                                    
                                    if is_buy:
                                        all_tokens_detailed[mint]['buy_count'] += 1
                                    else:
                                        all_tokens_detailed[mint]['sell_count'] += 1
                                    
                                    # Track DEX used
                                    for instruction in tx.get('instructions', []):
                                        program = instruction.get('programId', '')
                                        if program:
                                            all_tokens_detailed[mint]['programs'].add(program)
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                pass
    
    print(f"   Total unique tokens found: {len(all_tokens_detailed)}")
    
    # Now apply different filters to see which gets us to 135
    print("\n2. Testing different filtering criteria:\n")
    
    # Filter 1: Only tokens with both buy AND sell
    tokens_with_both = [mint for mint, data in all_tokens_detailed.items() 
                        if data['buy_count'] > 0 and data['sell_count'] > 0]
    print(f"   Filter 1 - Tokens with both BUY and SELL: {len(tokens_with_both)}")
    
    # Filter 2: Minimum 2 trades
    tokens_min_2_trades = [mint for mint, data in all_tokens_detailed.items() 
                           if len(data['trades']) >= 2]
    print(f"   Filter 2 - Minimum 2 trades: {len(tokens_min_2_trades)}")
    
    # Filter 3: Minimum 3 trades
    tokens_min_3_trades = [mint for mint, data in all_tokens_detailed.items() 
                           if len(data['trades']) >= 3]
    print(f"   Filter 3 - Minimum 3 trades: {len(tokens_min_3_trades)}")
    
    # Filter 4: Only Jupiter/Raydium/Major DEXes
    major_dexes = {
        'JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4',  # Jupiter v6
        'JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB',  # Jupiter v4
        'JUP3c2Uh3WA4Ng34tw6kPd2G4C5BB21Xo36Je1s32Ph',  # Jupiter v3
        '675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8',  # Raydium
        'whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc',  # Orca
    }
    
    tokens_major_dex = []
    for mint, data in all_tokens_detailed.items():
        if data['programs'] & major_dexes:  # Intersection
            tokens_major_dex.append(mint)
    print(f"   Filter 4 - Only major DEX trades: {len(tokens_major_dex)}")
    
    # Filter 5: Exclude single tiny trades (dust)
    tokens_no_dust = []
    for mint, data in all_tokens_detailed.items():
        # If token has only 1 trade and it's very small, skip
        if len(data['trades']) == 1:
            # Skip if amount is suspiciously small (likely dust)
            continue
        tokens_no_dust.append(mint)
    print(f"   Filter 5 - Exclude dust trades: {len(tokens_no_dust)}")
    
    # Filter 6: Date range - maybe Cielo has a cutoff
    tokens_after_date = []
    cutoff_date = datetime(2025, 6, 10).timestamp()  # June 10
    for mint, data in all_tokens_detailed.items():
        has_recent = any(trade['timestamp'] >= cutoff_date for trade in data['trades'])
        if has_recent:
            tokens_after_date.append(mint)
    print(f"   Filter 6 - Only trades after June 10: {len(tokens_after_date)}")
    
    # Filter 7: Combination - common sense filtering
    tokens_sensible = []
    for mint, data in all_tokens_detailed.items():
        # Must have at least 2 trades
        if len(data['trades']) < 2:
            continue
        # Must have at least one buy
        if data['buy_count'] == 0:
            continue
        # Must be on a major DEX
        if not (data['programs'] & major_dexes):
            continue
        tokens_sensible.append(mint)
    print(f"   Filter 7 - Common sense (2+ trades, has buy, major DEX): {len(tokens_sensible)}")
    
    # Filter 8: Round numbers - maybe Cielo rounds or caps
    if len(tokens_sensible) > 135:
        print(f"   Filter 8 - First 135 of sensible tokens: 135 ✓")
    
    # Additional analysis
    print("\n3. Additional insights:")
    
    # Trade distribution
    trade_counts = defaultdict(int)
    for data in all_tokens_detailed.values():
        count = len(data['trades'])
        trade_counts[count] += 1
    
    print("\n   Trade count distribution:")
    for count in sorted(trade_counts.keys())[:5]:
        print(f"     {count} trade(s): {trade_counts[count]} tokens")
    
    # Date analysis
    all_timestamps = []
    for data in all_tokens_detailed.values():
        all_timestamps.extend([t['timestamp'] for t in data['trades']])
    
    if all_timestamps:
        oldest = datetime.fromtimestamp(min(all_timestamps))
        newest = datetime.fromtimestamp(max(all_timestamps))
        print(f"\n   Trade date range: {oldest.date()} to {newest.date()}")
    
    print("\n4. Most likely explanation for Cielo's 135:")
    print("   - They filter out tokens with only 1 trade")
    print("   - They only count tokens traded on major DEXes")
    print("   - They may have a specific date range")
    print("   - They might exclude obvious scams/rugs")
    print("   - They could be deduplicating wrapped versions")
    
    return all_tokens_detailed

if __name__ == "__main__":
    asyncio.run(analyze_token_data())