#!/usr/bin/env python3
"""Debug what's wrong with the coaching data"""

import asyncio
import aiohttp
import json

async def check_cielo_data():
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    api_key = "7c855165-3874-4237-9416-450d2373ea72"
    
    async with aiohttp.ClientSession() as session:
        # Get first page of token data
        url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/tokens"
        headers = {"x-api-key": api_key}
        
        async with session.get(url, headers=headers) as response:
            data = await response.json()
            
            print("=== RAW CIELO DATA ===\n")
            print(f"Status: {response.status}")
            
            if response.status == 200:
                items = data['data']['items']
                print(f"First page has {len(items)} tokens\n")
                
                # Check for patterns around 10 SOL ($1500)
                sol_price = 150
                target_usd = 10 * sol_price  # $1500
                tolerance = 0.5
                
                matching_patterns = []
                
                for token in items[:20]:  # Check first 20
                    if token['num_swaps'] > 0:
                        avg_buy_usd = token['total_buy_usd'] / token['num_swaps']
                        avg_buy_sol = avg_buy_usd / sol_price
                        
                        print(f"{token['token_symbol']}: {token['num_swaps']} swaps, "
                              f"avg buy: ${avg_buy_usd:.0f} ({avg_buy_sol:.1f} SOL), "
                              f"ROI: {token['roi_percentage']:.1f}%")
                        
                        # Check if matches ~10 SOL
                        if target_usd * (1-tolerance) <= avg_buy_usd <= target_usd * (1+tolerance):
                            matching_patterns.append({
                                'symbol': token['token_symbol'],
                                'avg_sol': avg_buy_sol,
                                'roi': token['roi_percentage'],
                                'num_swaps': token['num_swaps']
                            })
                
                print(f"\n\nFound {len(matching_patterns)} tokens matching ~10 SOL pattern:")
                for p in matching_patterns:
                    print(f"  {p['symbol']}: {p['avg_sol']:.1f} SOL, {p['roi']:.1f}% ROI")
                    
                # Check for duplicates
                symbols = [t['token_symbol'] for t in items]
                unique_symbols = set(symbols)
                if len(symbols) != len(unique_symbols):
                    print(f"\n⚠️ DUPLICATE TOKENS FOUND!")
                    print(f"Total tokens: {len(symbols)}, Unique: {len(unique_symbols)}")

asyncio.run(check_cielo_data())