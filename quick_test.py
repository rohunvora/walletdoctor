#!/usr/bin/env python3

import requests
import os
from dotenv import load_dotenv
load_dotenv()

# Get API key
CIELO_KEY = os.getenv("CIELO_KEY")
wallet = "rp8ntGS7P2k3faTvsRSWxQLa3B68DetNbwe1GHLiTUK"

print("Testing different approaches to get losses...")

# Test 1: Try offset parameter
print(f"\n{'='*50}")
print("TEST 1: Using offset=100")
print(f"{'='*50}")

url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/tokens"
headers = {"x-api-key": CIELO_KEY}
params = {"offset": 100}

response = requests.get(url, headers=headers, params=params)
if response.status_code == 200:
    data = response.json()
    if 'data' in data and 'items' in data['data']:
        items = data['data']['items']
        print(f"Total items: {len(items)}")
        if items:
            pnls = [item.get('total_pnl_usd', 0) for item in items]
            print(f"PnL range: ${min(pnls):,.0f} to ${max(pnls):,.0f}")
            negative_count = sum(1 for p in pnls if p < 0)
            print(f"Negative PnL tokens: {negative_count}/{len(pnls)}")
        else:
            print("No items returned")
else:
    print(f"Error: {response.status_code}")

# Test 2: Try different sort parameter names
print(f"\n{'='*50}")
print("TEST 2: Trying alternative sort parameters")
print(f"{'='*50}")

sort_params = ['order', 'sort_order', 'orderBy', 'order_by', 'direction']
for param_name in sort_params:
    params = {param_name: 'asc'}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        if 'data' in data and 'items' in data['data']:
            items = data['data']['items']
            first_token = items[0].get('token_symbol', 'Unknown') if items else 'None'
            first_pnl = items[0].get('total_pnl_usd', 0) if items else 0
            print(f"{param_name}=asc: First token is {first_token} (${first_pnl:,.0f})")
            
# Test 3: Check total stats endpoint
print(f"\n{'='*50}")
print("TEST 3: Total stats endpoint (for comparison)")
print(f"{'='*50}")

total_url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/total-stats"
response = requests.get(total_url, headers=headers)
if response.status_code == 200:
    data = response.json()
    if 'data' in data:
        stats = data['data']
        print(f"Total tokens traded: {stats.get('tokens_traded', 'N/A')}")
        print(f"Realized PnL: ${stats.get('realized_pnl_usd', 0):,.0f}")
        print(f"Win rate: {stats.get('winrate', 0):.1f}%")
        
        # This tells us how many tokens are missing from the 100-row view
        tokens_traded = stats.get('tokens_traded', 0)
        if tokens_traded > 100:
            print(f"\n⚠️ API shows 100/{tokens_traded} tokens - missing {tokens_traded - 100} tokens!") 