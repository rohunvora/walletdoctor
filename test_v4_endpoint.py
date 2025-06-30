#!/usr/bin/env python3
"""Test v4 endpoint with comprehensive logging"""

import requests
import json
import time
from datetime import datetime

# Configuration
API_URL = "http://localhost:8080/v4/analyze"
TEST_WALLET = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"

print("=" * 60)
print("V4 ENDPOINT TEST - LARGE WALLET")
print("=" * 60)
print(f"Wallet: {TEST_WALLET}")
print(f"Endpoint: {API_URL}")
print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# Make request with timing
print("\nSending request...")
start_time = time.time()

try:
    response = requests.post(
        API_URL, 
        json={"wallet": TEST_WALLET},
        timeout=120  # 2 minute timeout
    )
    
    elapsed = time.time() - start_time
    print(f"Response received in {elapsed:.2f} seconds")
    print(f"HTTP Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        # Response size
        response_size = len(response.text)
        print(f"Response size: {response_size:,} bytes ({response_size/1024/1024:.2f} MB)")
        
        # Summary stats
        print("\n--- RESPONSE SUMMARY ---")
        print(f"Wallet: {data.get('wallet', 'N/A')}")
        print(f"Total trades: {len(data.get('trades', []))}")
        
        if 'summary' in data:
            summary = data['summary']
            print(f"Total P&L: ${summary.get('total_pnl_usd', 0):,.2f}")
            print(f"Win rate: {summary.get('win_rate', 0):.1f}%")
            print(f"Priced trades: {summary.get('priced_trades', 0)}")
            
            if 'metrics' in summary:
                metrics = summary['metrics']
                print(f"\n--- FETCH METRICS ---")
                print(f"Signatures fetched: {metrics.get('signatures_fetched', 0)}")
                print(f"Signatures parsed: {metrics.get('signatures_parsed', 0)}")
                print(f"Parse rate: {metrics['signatures_parsed']/metrics['signatures_fetched']*100:.1f}%")
                print(f"Events.swap: {metrics.get('events_swap_rows', 0)}")
                print(f"Fallback: {metrics.get('fallback_rows', 0)}")
        
        print(f"\nFrom slot: {data.get('from_slot', 'N/A')}")
        print(f"To slot: {data.get('to_slot', 'N/A')}")
        print(f"API elapsed time: {data.get('elapsed_seconds', 'N/A')}s")
        
        # Sample trades
        trades = data.get('trades', [])
        if trades:
            print(f"\n--- SAMPLE TRADES (first 3) ---")
            for i, trade in enumerate(trades[:3]):
                print(f"\nTrade {i+1}:")
                print(f"  Action: {trade.get('action')} {trade.get('token')}")
                print(f"  Amount: {trade.get('amount', 0):.6f}")
                print(f"  Value: ${trade.get('value_usd', 0):.2f}")
                print(f"  P&L: ${trade.get('pnl_usd', 0):.2f}")
                print(f"  tx_type: {trade.get('tx_type', 'N/A')}")
        
        # Pagination check
        if len(trades) >= 1000:
            print(f"\n⚠️  Hit pagination limit (1000 trades)")
            print("Note: Actual wallet may have more trades")
        
        # Save full response
        with open('v4_test_response.json', 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\n✅ Full response saved to v4_test_response.json")
        
    else:
        print(f"\n❌ Error: {response.status_code}")
        print(response.text[:500])

except requests.Timeout:
    print(f"\n❌ Request timed out after {time.time() - start_time:.2f} seconds")
    print("The wallet may have too many trades for current limits")
    
except Exception as e:
    print(f"\n❌ Error: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60) 