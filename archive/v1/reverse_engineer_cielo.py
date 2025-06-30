#!/usr/bin/env python3
"""
Reverse engineer Cielo's data format and methodology
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from collections import defaultdict

async def analyze_cielo_methodology():
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    api_key = "7c855165-3874-4237-9416-450d2373ea72"
    
    async with aiohttp.ClientSession() as session:
        headers = {"x-api-key": api_key}
        
        print("=== REVERSE ENGINEERING CIELO ===\n")
        
        # 1. Analyze token data structure
        print("1. TOKEN DATA STRUCTURE")
        print("-" * 50)
        
        url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/tokens"
        async with session.get(url, headers=headers) as response:
            data = await response.json()
            
            # Get first token as example
            if data['data']['items']:
                token = data['data']['items'][0]
                print("Token fields:")
                for key, value in token.items():
                    print(f"  {key}: {type(value).__name__} = {value}")
                
                # Analyze calculations
                print("\n2. P&L CALCULATION METHODOLOGY")
                print("-" * 50)
                
                # Check first few tokens
                for i, token in enumerate(data['data']['items'][:5]):
                    print(f"\nToken: {token['token_symbol']}")
                    print(f"  Buys: {token['num_swaps']} swaps")
                    print(f"  Total bought: {token['total_buy_amount']} tokens for ${token['total_buy_usd']}")
                    print(f"  Total sold: {token['total_sell_amount']} tokens for ${token['total_sell_usd']}")
                    
                    # Reverse engineer calculations
                    if token['num_swaps'] > 0:
                        avg_buy = token['total_buy_usd'] / token['num_swaps']
                        print(f"  Avg buy per swap: ${avg_buy:.2f}")
                    
                    # Check P&L calculation
                    calculated_pnl = token['total_sell_usd'] - token['total_buy_usd']
                    print(f"  Calculated P&L: ${calculated_pnl:.2f}")
                    print(f"  Reported P&L: ${token['total_pnl_usd']:.2f}")
                    print(f"  Match: {abs(calculated_pnl - token['total_pnl_usd']) < 0.01}")
                    
                    # Check ROI calculation  
                    if token['total_buy_usd'] > 0:
                        calculated_roi = (calculated_pnl / token['total_buy_usd']) * 100
                        print(f"  Calculated ROI: {calculated_roi:.2f}%")
                        print(f"  Reported ROI: {token['roi_percentage']:.2f}%")
                
                # Analyze data patterns
                print("\n3. DATA PATTERNS & METHODOLOGY")
                print("-" * 50)
                
                tokens = data['data']['items']
                
                # Check if tokens are sorted
                roi_sorted = all(tokens[i]['roi_percentage'] >= tokens[i+1]['roi_percentage'] 
                               for i in range(len(tokens)-1))
                pnl_sorted = all(tokens[i]['total_pnl_usd'] >= tokens[i+1]['total_pnl_usd'] 
                               for i in range(len(tokens)-1))
                time_sorted = all(tokens[i]['last_trade'] >= tokens[i+1]['last_trade'] 
                                for i in range(len(tokens)-1))
                
                print(f"Sorted by ROI (desc): {roi_sorted}")
                print(f"Sorted by P&L (desc): {pnl_sorted}")
                print(f"Sorted by time (desc): {time_sorted}")
                
                # Check for filters
                print(f"\n4. INCLUSION CRITERIA")
                print("-" * 50)
                
                # Check if all have trades
                all_have_swaps = all(t['num_swaps'] > 0 for t in tokens)
                print(f"All tokens have swaps: {all_have_swaps}")
                
                # Check minimum thresholds
                min_swaps = min(t['num_swaps'] for t in tokens)
                min_volume = min(t['total_buy_usd'] + t['total_sell_usd'] for t in tokens)
                print(f"Minimum swaps: {min_swaps}")
                print(f"Minimum volume: ${min_volume:.2f}")
                
                # Check for specific token types
                chains = set(t.get('chain', 'unknown') for t in tokens)
                print(f"Chains included: {chains}")
                
                # Analyze holding patterns
                print(f"\n5. HOLDING ANALYSIS")
                print("-" * 50)
                
                holding_tokens = [t for t in tokens if t.get('holding_amount', 0) > 0]
                sold_all = [t for t in tokens if t.get('holding_amount', 0) == 0]
                
                print(f"Tokens still held: {len(holding_tokens)}")
                print(f"Tokens fully sold: {len(sold_all)}")
                
                # Time analysis
                print(f"\n6. TIME RANGE ANALYSIS")
                print("-" * 50)
                
                timestamps = []
                for t in tokens:
                    if t.get('first_trade'):
                        timestamps.append(t['first_trade'])
                    if t.get('last_trade'):
                        timestamps.append(t['last_trade'])
                
                if timestamps:
                    min_time = min(timestamps)
                    max_time = max(timestamps)
                    
                    print(f"Earliest trade: {datetime.fromtimestamp(min_time)}")
                    print(f"Latest trade: {datetime.fromtimestamp(max_time)}")
                    print(f"Time span: {(max_time - min_time) / 86400:.1f} days")
        
        # Test total stats calculation
        print(f"\n7. TOTAL STATS RECONCILIATION")
        print("-" * 50)
        
        url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/total-stats"
        async with session.get(url, headers=headers) as response:
            total_data = await response.json()
            total_stats = total_data['data']
            
            # Try to reconcile with token data
            token_url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/tokens"
            async with session.get(token_url, headers=headers) as response:
                token_data = await response.json()
                tokens = token_data['data']['items']
                
                # Calculate from tokens
                calc_total_buy = sum(t['total_buy_usd'] for t in tokens)
                calc_total_sell = sum(t['total_sell_usd'] for t in tokens)
                calc_total_pnl = sum(t['total_pnl_usd'] for t in tokens)
                
                print(f"From 50 tokens:")
                print(f"  Total buy: ${calc_total_buy:,.2f}")
                print(f"  Total sell: ${calc_total_sell:,.2f}")
                print(f"  Total P&L: ${calc_total_pnl:,.2f}")
                
                print(f"\nFrom total stats (136 tokens):")
                print(f"  Total buy: ${total_stats['total_buy_usd']:,.2f}")
                print(f"  Total sell: ${total_stats['total_sell_usd']:,.2f}")
                print(f"  Total P&L: ${total_stats['realized_pnl_usd']:,.2f}")
                
                print(f"\nCoverage: {calc_total_buy / total_stats['total_buy_usd'] * 100:.1f}% of volume")

asyncio.run(analyze_cielo_methodology())