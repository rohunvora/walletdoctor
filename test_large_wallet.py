#!/usr/bin/env python3
"""Test with a wallet known to have many SWAP transactions"""

import requests
import json
import time
from datetime import datetime

# Popular DEX trader wallets with many swaps
TEST_WALLETS = [
    # Original wallet
    {
        "address": "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
        "description": "Original test wallet"
    },
    # Add more active trader wallets here if needed
]

BASE_URL = "http://localhost:8080"

print("=" * 60)
print("TESTING LARGE WALLET SUPPORT")
print("=" * 60)

# Wait for server
print("Waiting for server to start...")
time.sleep(3)

# Check server health
try:
    health = requests.get(f"{BASE_URL}/health", timeout=2)
    if health.status_code != 200:
        print("❌ Server not healthy")
        exit(1)
    print("✅ Server is healthy")
except:
    print("❌ Cannot connect to server")
    exit(1)

# Test each wallet
for wallet_info in TEST_WALLETS:
    wallet = wallet_info["address"]
    desc = wallet_info["description"]
    
    print(f"\nTesting: {desc}")
    print(f"Wallet: {wallet}")
    print("-" * 60)
    
    start_time = time.time()
    
    try:
        # First, let's check how many total transactions this wallet has
        # by looking at the response
        print("Fetching SWAP transactions...")
        
        response = requests.post(
            f"{BASE_URL}/v4/analyze",
            json={"wallet": wallet},
            timeout=120
        )
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            trades = data.get('trades', [])
            summary = data.get('summary', {})
            metrics = summary.get('metrics', {})
            
            print(f"\nResults:")
            print(f"  Response time: {elapsed:.2f}s")
            print(f"  SWAP transactions found: {metrics.get('signatures_fetched', 0)}")
            print(f"  Trades parsed: {len(trades)}")
            print(f"  Parse rate: {metrics.get('signatures_parsed', 0)/max(metrics.get('signatures_fetched', 1), 1)*100:.1f}%")
            
            # Check if we hit page limit
            if len(trades) % 100 == 0 and len(trades) > 0:
                print(f"\n⚠️  Possible pagination - got exactly {len(trades)} trades")
            
            # Show date range
            if trades:
                first_date = trades[-1].get('timestamp', 'N/A')
                last_date = trades[0].get('timestamp', 'N/A') 
                print(f"\n  Date range:")
                print(f"    First: {first_date}")
                print(f"    Last: {last_date}")
            
            # Note about transaction types
            print(f"\n📝 Note: This only shows SWAP transactions.")
            print(f"   The wallet may have many more non-SWAP transactions.")
            
        else:
            print(f"\n❌ Error: {response.status_code}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
print("\nTo see ALL transaction types (not just SWAPs), the API would need")
print("to remove the 'type: SWAP' filter in the Helius query.") 