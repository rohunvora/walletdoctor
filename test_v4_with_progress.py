#!/usr/bin/env python3
"""Test v4 endpoint with progress indicators"""

import requests
import json
import time
import sys
from datetime import datetime
import threading

# Configuration
BASE_URL = "http://localhost:8080"
TEST_WALLET = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"

def spinning_cursor():
    """Show a spinning cursor while waiting"""
    while True:
        for cursor in '|/-\\':
            yield cursor

def show_progress(stop_event):
    """Show progress indicator in a separate thread"""
    spinner = spinning_cursor()
    start_time = time.time()
    while not stop_event.is_set():
        elapsed = time.time() - start_time
        sys.stdout.write(f'\r[{next(spinner)}] Waiting for response... {elapsed:.1f}s')
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write('\r' + ' ' * 50 + '\r')  # Clear the line
    sys.stdout.flush()

print("=" * 60)
print("V4 ENDPOINT TEST WITH PROGRESS INDICATORS")
print("=" * 60)

# Step 1: Check server health
print("1. Checking server health...")
try:
    health_response = requests.get(f"{BASE_URL}/health", timeout=2)
    if health_response.status_code == 200:
        print(f"   ✅ Server is healthy: {health_response.json()}")
    else:
        print(f"   ❌ Server health check failed: {health_response.status_code}")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ Cannot connect to server: {e}")
    print("   Make sure the server is running on port 8080")
    sys.exit(1)

# Step 2: Test with a small request first
print("\n2. Testing with simple request...")
try:
    test_response = requests.get(f"{BASE_URL}/", timeout=2)
    print(f"   ✅ API info retrieved successfully")
except Exception as e:
    print(f"   ❌ Simple request failed: {e}")

# Step 3: Main wallet test
print(f"\n3. Testing wallet analysis...")
print(f"   Wallet: {TEST_WALLET}")
print(f"   Endpoint: {BASE_URL}/v4/analyze")
print(f"   Time: {datetime.now().strftime('%H:%M:%S')}")
print("\n   Sending request...")

# Start progress indicator in separate thread
stop_event = threading.Event()
progress_thread = threading.Thread(target=show_progress, args=(stop_event,))
progress_thread.start()

start_time = time.time()

try:
    # Make the actual request
    response = requests.post(
        f"{BASE_URL}/v4/analyze", 
        json={"wallet": TEST_WALLET},
        timeout=120,  # 2 minute timeout
        stream=True   # Stream response for better progress tracking
    )
    
    # Stop progress indicator
    stop_event.set()
    progress_thread.join()
    
    elapsed = time.time() - start_time
    print(f"\n   ✅ Response received in {elapsed:.2f} seconds")
    print(f"   HTTP Status: {response.status_code}")
    
    if response.status_code == 200:
        # Read response content
        print("   Reading response data...")
        content = response.content
        data = json.loads(content)
        
        # Response stats
        response_size = len(content)
        print(f"   Response size: {response_size:,} bytes ({response_size/1024/1024:.2f} MB)")
        
        # Summary
        print("\n4. RESPONSE SUMMARY")
        print("   " + "-" * 40)
        trades = data.get('trades', [])
        print(f"   Total trades: {len(trades)}")
        
        if 'summary' in data:
            summary = data['summary']
            print(f"   Total P&L: ${summary.get('total_pnl_usd', 0):,.2f}")
            print(f"   Win rate: {summary.get('win_rate', 0):.1f}%")
            
            if 'metrics' in summary:
                metrics = summary['metrics']
                print(f"\n   Fetch metrics:")
                print(f"   - Transactions fetched: {metrics.get('signatures_fetched', 0)}")
                print(f"   - Trades parsed: {metrics.get('signatures_parsed', 0)}")
                print(f"   - Parse rate: {metrics.get('signatures_parsed', 0)/max(metrics.get('signatures_fetched', 1), 1)*100:.1f}%")
        
        print(f"\n   API processing time: {data.get('elapsed_seconds', 'N/A')}s")
        
        # Check if we hit limits
        if len(trades) == 0:
            print("\n   ⚠️  No trades returned - wallet may be empty or API key issues")
        elif len(trades) >= 1000:
            print("\n   ⚠️  Hit 1000 trade limit - wallet has more trades")
        
        # Save response
        with open('v4_test_response.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("\n   ✅ Full response saved to v4_test_response.json")
        
    else:
        print(f"\n   ❌ Error response: {response.status_code}")
        print(f"   {response.text[:200]}...")

except requests.Timeout:
    stop_event.set()
    progress_thread.join()
    print(f"\n   ❌ Request timed out after {time.time() - start_time:.2f} seconds")
    print("   The wallet may have too many trades or API is slow")
    
except Exception as e:
    stop_event.set()
    progress_thread.join()
    print(f"\n   ❌ Error: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60) 