#!/usr/bin/env python3
"""Test GPT export without price fetching to isolate bottleneck"""

import requests
import time
import json
from datetime import datetime

BASE_URL = "https://web-production-2bb2f.up.railway.app"
SMALL_WALLET = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"

def test_no_prices():
    """Test with price fetching disabled"""
    print(f"Testing GPT export WITHOUT price fetching")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Wallet: {SMALL_WALLET}")
    print("")
    
    # First, test with skip_pricing parameter if supported
    url = f"{BASE_URL}/v4/positions/export-gpt/{SMALL_WALLET}?skip_pricing=true"
    print(f"Testing: {url}")
    
    start = time.time()
    try:
        response = requests.get(url, timeout=60)
        elapsed = time.time() - start
        
        print(f"Status: {response.status_code}")
        print(f"Time: {elapsed:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Success! Got {len(data.get('portfolio', {}).get('positions', []))} positions")
            # Check if prices are actually missing
            if data.get('portfolio', {}).get('positions'):
                pos = data['portfolio']['positions'][0]
                print(f"Sample position has price data: {'market_price' in pos}")
        else:
            print(f"Error: {response.text[:200]}")
            
    except Exception as e:
        elapsed = time.time() - start
        print(f"Failed after {elapsed:.2f}s: {e}")
    
    print("\n" + "="*60 + "\n")
    
    # Also test the diagnostics endpoint
    print("Testing diagnostics endpoint...")
    diag_url = f"{BASE_URL}/v4/diagnostics"
    
    try:
        response = requests.get(diag_url, timeout=10)
        print(f"Diagnostics status: {response.status_code}")
        if response.status_code == 200:
            print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Diagnostics failed: {e}")

if __name__ == "__main__":
    test_no_prices() 