#!/usr/bin/env python3
"""
Deep analysis of Cielo's data format and methodology
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from collections import defaultdict

async def analyze_cielo_deeply():
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    api_key = "7c855165-3874-4237-9416-450d2373ea72"
    
    async with aiohttp.ClientSession() as session:
        headers = {"x-api-key": api_key}
        
        print("=== CIELO DATA FORMAT & METHODOLOGY ANALYSIS ===\n")
        
        # 1. Analyze the rasmr P&L discrepancy
        print("1. P&L CALCULATION MYSTERY - rasmr token")
        print("-" * 50)
        
        url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/tokens"
        async with session.get(url, headers=headers) as response:
            data = await response.json()
            tokens = data['data']['items']
            
            # Find rasmr
            rasmr = next(t for t in tokens if t['token_symbol'] == 'rasmr')
            
            print(f"Total bought: {rasmr['total_buy_amount']} tokens for ${rasmr['total_buy_usd']}")
            print(f"Total sold: {rasmr['total_sell_amount']} tokens for ${rasmr['total_sell_usd']}")
            print(f"Holding: {rasmr['holding_amount']} tokens worth ${rasmr['holding_amount_usd']}")
            
            # Calculate expected P&L
            simple_pnl = rasmr['total_sell_usd'] - rasmr['total_buy_usd']
            print(f"\nSimple P&L (sell - buy): ${simple_pnl:.2f}")
            print(f"Reported P&L: ${rasmr['total_pnl_usd']:.2f}")
            print(f"Difference: ${rasmr['total_pnl_usd'] - simple_pnl:.2f}")
            
            # Check if holding explains it
            if rasmr['holding_amount'] > 0:
                print(f"\nStill holding {rasmr['holding_amount']:.2f} tokens")
                print("This might explain the P&L difference")
                
                # Try to calculate implied value
                remaining_tokens = rasmr['total_buy_amount'] - rasmr['total_sell_amount']
                print(f"Tokens unaccounted: {remaining_tokens:.2f}")
                
                if remaining_tokens > 0:
                    implied_value = rasmr['total_pnl_usd'] - simple_pnl
                    implied_price = implied_value / remaining_tokens
                    print(f"Implied current value: ${implied_value:.2f}")
                    print(f"Implied price per token: ${implied_price:.8f}")
        
        # 2. Analyze the 50 token limit
        print("\n\n2. TOKEN LIMIT ANALYSIS")
        print("-" * 50)
        
        # Check if tokens are sorted
        roi_values = [t['roi_percentage'] for t in tokens]
        pnl_values = [t['total_pnl_usd'] for t in tokens]
        time_values = [t['last_trade'] for t in tokens]
        
        print(f"First 5 ROIs: {roi_values[:5]}")
        print(f"Last 5 ROIs: {roi_values[-5:]}")
        
        # Check for any patterns in selection
        print(f"\nToken selection criteria:")
        print(f"- All have swaps: {all(t['num_swaps'] > 0 for t in tokens)}")
        print(f"- Volume range: ${min(t['total_buy_usd'] + t['total_sell_usd'] for t in tokens):.2f} - ${max(t['total_buy_usd'] + t['total_sell_usd'] for t in tokens):,.2f}")
        print(f"- Time range: {datetime.fromtimestamp(min(t['first_trade'] for t in tokens if t['first_trade']))} to {datetime.fromtimestamp(max(t['last_trade'] for t in tokens if t['last_trade']))}")
        
        # 3. Analyze data structure patterns
        print("\n\n3. DATA STRUCTURE PATTERNS")
        print("-" * 50)
        
        # Check for calculated vs stored fields
        for i, token in enumerate(tokens[:3]):
            print(f"\nToken: {token['token_symbol']}")
            
            # Check average price calculations
            if token['num_swaps'] > 0 and token['total_buy_amount'] > 0:
                calc_avg_buy = token['total_buy_usd'] / token['total_buy_amount']
                print(f"  Calculated avg buy: ${calc_avg_buy:.8f}")
                print(f"  Stored avg buy: ${token['average_buy_price']:.8f}")
                print(f"  Match: {abs(calc_avg_buy - token['average_buy_price']) < 0.0001}")
            
            # Check holding time calculation
            if token['first_trade'] and token['last_trade']:
                calc_hold_time = token['last_trade'] - token['first_trade']
                print(f"  Calculated hold time: {calc_hold_time}s")
                print(f"  Stored hold time: {token['holding_time_seconds']}s")
        
        # 4. Try to find hidden endpoints
        print("\n\n4. ENDPOINT DISCOVERY")
        print("-" * 50)
        
        # Test various endpoint patterns
        endpoints = [
            "/pnl/tokens/full",
            "/pnl/all",
            "/pnl/complete",
            "/tokens/all",
            "/full-history",
            "/export",
            "/csv",
            "/download"
        ]
        
        for endpoint in endpoints:
            url = f"https://feed-api.cielo.finance/api/v1/{wallet}{endpoint}"
            async with session.get(url, headers=headers) as response:
                print(f"  {endpoint}: {response.status}")
        
        # 5. Check if there's a way to get specific tokens
        print("\n\n5. SPECIFIC TOKEN ACCESS")
        print("-" * 50)
        
        # Try to access a token we know exists but isn't in the 50
        # From total stats, we have 136 tokens but only see 50
        print("Attempting to access tokens beyond the first 50...")
        
        # Try offset-based access
        for offset in [50, 100, 130]:
            url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/tokens?offset={offset}&limit=10"
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    count = len(data['data']['items'])
                    first = data['data']['items'][0]['token_symbol'] if count > 0 else "None"
                    print(f"  Offset {offset}: {count} tokens, first: {first}")
        
        # 6. Analyze the missing data impact
        print("\n\n6. MISSING DATA IMPACT ANALYSIS")
        print("-" * 50)
        
        # Get totals again
        url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/total-stats"
        async with session.get(url, headers=headers) as response:
            total_data = await response.json()
            total_stats = total_data['data']
        
        # Calculate what we're missing
        visible_buy = sum(t['total_buy_usd'] for t in tokens)
        visible_sell = sum(t['total_sell_usd'] for t in tokens)
        visible_pnl = sum(t['total_pnl_usd'] for t in tokens)
        
        missing_buy = total_stats['total_buy_usd'] - visible_buy
        missing_sell = total_stats['total_sell_usd'] - visible_sell
        missing_pnl = total_stats['realized_pnl_usd'] - visible_pnl
        
        print(f"Visible (50 tokens):")
        print(f"  Buy: ${visible_buy:,.2f}")
        print(f"  Sell: ${visible_sell:,.2f}")
        print(f"  P&L: ${visible_pnl:,.2f}")
        
        print(f"\nMissing (86 tokens):")
        print(f"  Buy: ${missing_buy:,.2f}")
        print(f"  Sell: ${missing_sell:,.2f}")
        print(f"  P&L: ${missing_pnl:,.2f}")
        
        print(f"\nAverage per token:")
        print(f"  Visible: ${visible_pnl/50:.2f}")
        print(f"  Missing: ${missing_pnl/86:.2f}")
        
        # This suggests the API is showing the best performers
        print(f"\nConclusion: The API appears to show the top 50 tokens by some metric")
        print(f"The missing 86 tokens have an average P&L of ${missing_pnl/86:.2f}")
        print(f"This explains why the total P&L is negative while visible tokens show profit")

asyncio.run(analyze_cielo_deeply())