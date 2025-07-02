#!/usr/bin/env python3
"""
Test script for RCA validation - runs a single GPT export and captures phase logs
"""

import requests
import time
import json
import sys
from datetime import datetime

# Configuration
BASE_URL = "https://web-production-2bb2f.up.railway.app"
SMALL_WALLET = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
API_KEY = "wd_12345678901234567890123456789012"  # Test key

def test_with_rca_logging():
    """Run single test with full logging"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"=== RCA Validation Test ===")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Wallet: {SMALL_WALLET}")
    print(f"URL: {BASE_URL}")
    print("")
    
    # Test 1: With skip_pricing=true (baseline)
    print("Test 1: skip_pricing=true (baseline)")
    url = f"{BASE_URL}/v4/positions/export-gpt/{SMALL_WALLET}?skip_pricing=true"
    headers = {"X-Api-Key": API_KEY}
    
    start = time.time()
    try:
        response = requests.get(url, headers=headers, timeout=60)
        elapsed = time.time() - start
        
        print(f"  Status: {response.status_code}")
        print(f"  Time: {elapsed:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Positions: {len(data.get('positions', []))}")
        else:
            print(f"  Error: {response.text[:200]}")
    except Exception as e:
        elapsed = time.time() - start
        print(f"  Failed after {elapsed:.2f}s: {e}")
    
    print("")
    print("Test 2: Normal flow (with pricing)")
    
    # Test 2: Normal flow
    url = f"{BASE_URL}/v4/positions/export-gpt/{SMALL_WALLET}"
    
    start = time.time()
    try:
        response = requests.get(url, headers=headers, timeout=120)
        elapsed = time.time() - start
        
        print(f"  Status: {response.status_code}")
        print(f"  Time: {elapsed:.2f}s")
        
        # Extract phase timings from headers
        if 'X-Phase-Timings' in response.headers:
            phase_timings = json.loads(response.headers['X-Phase-Timings'])
            print(f"  Phase timings:")
            for phase, duration in phase_timings.items():
                print(f"    - {phase}: {duration:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Positions: {len(data.get('positions', []))}")
            
            # Save response for analysis
            with open(f"tmp/rca_response_{timestamp}.json", "w") as f:
                json.dump(data, f, indent=2)
        else:
            print(f"  Error: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        print(f"  TIMEOUT after {time.time() - start:.2f}s")
    except Exception as e:
        elapsed = time.time() - start
        print(f"  Failed after {elapsed:.2f}s: {e}")
    
    print("")
    print(f"Results saved to tmp/rca_response_{timestamp}.json")
    print("")
    print("IMPORTANT: Now run this command to get the Railway logs:")
    print(f"railway logs --tail 500 | grep '\\[RCA\\]' > tmp/phase_log_{timestamp}.txt")
    print("")
    print("Or if railway CLI is not available, check the Railway dashboard logs")
    print("and look for lines containing '[RCA]'")

if __name__ == "__main__":
    test_with_rca_logging() 