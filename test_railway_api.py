#!/usr/bin/env python3
"""Test Railway API endpoint for GPT export"""

import requests
import json
import time
import sys
from datetime import datetime

# Configuration
RAILWAY_URL = "https://web-production-2bb2f.up.railway.app"
API_KEY = "wd_12345678901234567890123456789012"
TEST_WALLET = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"  # 6,424 trade wallet

def test_health():
    """Test health endpoint"""
    print("Testing health endpoint...")
    response = requests.get(f"{RAILWAY_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_gpt_export():
    """Test GPT export endpoint"""
    print(f"\nTesting GPT export endpoint for wallet: {TEST_WALLET[:8]}...")
    
    headers = {"X-Api-Key": API_KEY}
    url = f"{RAILWAY_URL}/v4/positions/export-gpt/{TEST_WALLET}"
    
    start_time = time.time()
    response = requests.get(url, headers=headers)
    duration = time.time() - start_time
    
    print(f"Status: {response.status_code}")
    print(f"Response time: {duration:.2f} seconds")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Schema version: {data.get('schema_version')}")
        print(f"Timestamp: {data.get('timestamp')}")
        print(f"Total positions: {data['summary']['total_positions']}")
        print(f"Total value USD: ${data['summary']['total_value_usd']}")
        print(f"Total unrealized P&L USD: ${data['summary']['total_unrealized_pnl_usd']}")
        print(f"Total unrealized P&L %: {data['summary']['total_unrealized_pnl_pct']}%")
        
        # Save full response
        with open('railway_api_response.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("\nFull response saved to: railway_api_response.json")
        
        # Find biggest loss
        if data['positions']:
            positions_by_loss = sorted(
                data['positions'], 
                key=lambda p: float(p['unrealized_pnl_usd'])
            )
            biggest_loss = positions_by_loss[0]
            
            print(f"\nBiggest unrealized loss:")
            print(f"  Token: {biggest_loss['token_symbol']}")
            print(f"  Loss: ${biggest_loss['unrealized_pnl_usd']} ({biggest_loss['unrealized_pnl_pct']}%)")
            print(f"  Current value: ${biggest_loss['current_value_usd']}")
            print(f"  Cost basis: ${biggest_loss['cost_basis_usd']}")
        
        return True
    else:
        print(f"Error: {response.text}")
        return False

def main():
    print("=" * 60)
    print("Railway API Test")
    print(f"URL: {RAILWAY_URL}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Test health
    health_ok = test_health()
    
    if not health_ok:
        print("\n❌ Health check failed!")
        return 1
    
    # Test GPT export
    export_ok = test_gpt_export()
    
    if export_ok:
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ GPT export test failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 