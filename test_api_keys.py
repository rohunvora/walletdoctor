#!/usr/bin/env python3
"""Test script to verify API keys are working"""

import os
import sys
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

print("=== API Key Test ===\n")

# Check if keys exist
helius_key = os.getenv("HELIUS_KEY")
cielo_key = os.getenv("CIELO_KEY")

print(f"HELIUS_KEY: {'✅ Found' if helius_key else '❌ Missing'}")
print(f"CIELO_KEY: {'✅ Found' if cielo_key else '❌ Missing'}")

if not helius_key or not cielo_key:
    print("\n❌ API keys missing! Check your .env file")
    sys.exit(1)

# Test wallet
test_wallet = "A4DCAjDwkq5jYhNoZ5Xn2NbkTLimARkerVv81w2dhXgL"
headers = {"x-api-key": cielo_key}

print("\n=== Testing Cielo Trading Stats API ===")
url = f"https://feed-api.cielo.finance/api/v1/{test_wallet}/trading-stats"
try:
    print(f"Testing: {url}")
    response = requests.get(url, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        if 'data' in data:
            stats = data['data']
            print(f"✅ Trading Stats API:")
            print(f"  - Swaps: {stats.get('swaps_count', 'N/A')}")
            print(f"  - PnL: ${stats.get('pnl', 0):,.2f}")
            print(f"  - Win rate: {stats.get('winrate', 0):.1f}%")
        else:
            print(f"❌ Unexpected response format: {list(data.keys())}")
    else:
        print(f"❌ API error: {response.text[:200]}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n=== Testing Cielo Aggregated PnL API ===")
url = f"https://feed-api.cielo.finance/api/v1/{test_wallet}/pnl/total-stats"
try:
    print(f"Testing: {url}")
    response = requests.get(url, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        if 'data' in data:
            agg = data['data']
            print(f"✅ Aggregated PnL API:")
            print(f"  - Tokens traded: {agg.get('tokens_traded', 'N/A')}")
            print(f"  - Realized PnL: ${agg.get('realized_pnl_usd', 0):,.2f}")
            print(f"  - Unrealized PnL: ${agg.get('unrealized_pnl_usd', 0):,.2f}")
            print(f"  - Combined PnL: ${agg.get('combined_pnl_usd', 0):,.2f}")
            print(f"  - Win rate: {agg.get('winrate', 0):.1f}%")
        else:
            print(f"❌ Unexpected response format: {list(data.keys())}")
    else:
        print(f"❌ API error: {response.text[:200]}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n=== Testing Cielo PnL Tokens ===")
url = f"https://feed-api.cielo.finance/api/v1/{test_wallet}/pnl/tokens"

try:
    print(f"Testing: {url}")
    response = requests.get(url, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        if 'data' in data and 'items' in data.get('data', {}):
            items = data['data']['items']
            print(f"✅ PnL Tokens API: Found {len(items)} tokens")
            if items:
                # Calculate totals from token list
                total_pnl = sum(item.get('totalPnl', 0) for item in items)
                realized_pnl = sum(item.get('realizedPnl', 0) for item in items)
                print(f"  - Total PnL (sum): ${total_pnl:,.2f}")
                print(f"  - Realized PnL (sum): ${realized_pnl:,.2f}")
                print(f"  - First token: {items[0].get('symbol', 'N/A')}")
        else:
            print(f"❌ No items found. Response keys: {list(data.keys())}")
            if 'data' in data:
                print(f"  Data keys: {list(data['data'].keys())}")
    else:
        print(f"❌ API error: {response.text[:200]}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\nDone!") 