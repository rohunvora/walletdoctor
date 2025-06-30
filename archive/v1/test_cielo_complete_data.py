#!/usr/bin/env python3
"""Test if we can get complete data from Cielo"""

import asyncio
import aiohttp

async def test_all_endpoints():
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    api_key = "7c855165-3874-4237-9416-450d2373ea72"
    
    async with aiohttp.ClientSession() as session:
        headers = {"x-api-key": api_key}
        
        # Test 1: Total stats (this should be accurate)
        print("=== TOTAL STATS (Ground Truth) ===")
        url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/total-stats"
        async with session.get(url, headers=headers) as response:
            data = await response.json()
            stats = data['data']
            print(f"Total tokens traded: {stats['tokens_traded']}")
            print(f"Total P&L: ${stats['realized_pnl_usd']:,.2f}")
            print(f"Win rate: {stats['winrate']:.1f}%")
            print(f"Total buy USD: ${stats['total_buy_usd']:,.2f}")
        
        # Test 2: Try different pagination approaches
        print("\n=== TESTING PAGINATION ===")
        
        # Approach 1: Try page parameter in different ways
        for page_param in ['page', 'p', 'offset', 'skip']:
            url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/tokens?{page_param}=2"
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    first_token = data['data']['items'][0]['token_symbol'] if data['data']['items'] else "None"
                    print(f"{page_param}=2: {first_token}")
        
        # Approach 2: Try limit parameter
        url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/tokens?limit=200"
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                print(f"\nWith limit=200: {len(data['data']['items'])} tokens returned")
        
        # Approach 3: Check if there's a different endpoint
        # Try common variations
        for endpoint in ['tokens', 'all-tokens', 'tokens/all', 'tokens/list']:
            url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/{endpoint}"
            async with session.get(url, headers=headers) as response:
                print(f"\nTrying /{endpoint}: {response.status}")

asyncio.run(test_all_endpoints())