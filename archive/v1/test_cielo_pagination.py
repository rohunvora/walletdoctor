#!/usr/bin/env python3
"""Test if Cielo API is returning duplicates across pages"""

import asyncio
import aiohttp

async def test_pagination():
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    api_key = "7c855165-3874-4237-9416-450d2373ea72"
    
    all_tokens = []
    seen_addresses = set()
    duplicates = []
    
    async with aiohttp.ClientSession() as session:
        for page in range(1, 5):  # Test first 4 pages
            url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/tokens"
            headers = {"x-api-key": api_key}
            params = {"page": page}
            
            async with session.get(url, headers=headers, params=params) as response:
                if response.status != 200:
                    print(f"Error on page {page}: {response.status}")
                    break
                    
                data = await response.json()
                items = data['data']['items']
                paging = data['data'].get('paging', {})
                
                print(f"\nPage {page}:")
                print(f"  Items: {len(items)}")
                print(f"  Has next: {paging.get('has_next_page', False)}")
                
                if not items:
                    print("  No items, stopping")
                    break
                
                # Check for duplicates
                for token in items:
                    addr = token['token_address']
                    if addr in seen_addresses:
                        duplicates.append(f"Page {page}: {token['token_symbol']} ({addr})")
                    else:
                        seen_addresses.add(addr)
                        all_tokens.append(token)
                
                # Show first few tokens
                for i, token in enumerate(items[:3]):
                    print(f"  [{i}] {token['token_symbol']}: {token['num_swaps']} swaps")
                
                if not paging.get('has_next_page', False):
                    print("  No more pages")
                    break
    
    print(f"\n\nSummary:")
    print(f"Total unique tokens: {len(all_tokens)}")
    print(f"Duplicates found: {len(duplicates)}")
    
    if duplicates:
        print("\nDuplicate tokens:")
        for dup in duplicates[:5]:
            print(f"  {dup}")

asyncio.run(test_pagination())