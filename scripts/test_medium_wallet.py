#!/usr/bin/env python3
"""
Medium Wallet Test - Validate performance with ~380 trades
Expected: < 12s cold, < 0.5s warm
"""

import requests
import time
import json
import os
from datetime import datetime

# Allow override via environment
BASE_URL = os.getenv("API_BASE_URL", "https://web-production-2bb2f.up.railway.app")
MEDIUM_WALLET = "AAXTYrQR6CHDGhJYz4uSgJ6dq7JTySTR6WyAq8QKZnF8"  # 380 trades
API_KEY = os.getenv("API_KEY", "wd_12345678901234567890123456789012")

def test_medium_wallet():
    """Test medium wallet implementation"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = []
    
    print("=== Medium Wallet Test ===")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Wallet: {MEDIUM_WALLET}")
    print("")
    
    # Test 1: Cold cache
    print("Test 1: Cold cache (medium wallet)")
    url = f"{BASE_URL}/v4/positions/export-gpt/{MEDIUM_WALLET}"
    headers = {"X-Api-Key": API_KEY}
    
    start = time.time()
    try:
        response = requests.get(url, headers=headers, timeout=60)
        elapsed = time.time() - start
        
        result = {
            "test": "cold_cache_medium",
            "status": response.status_code,
            "time": elapsed,
            "success": response.status_code == 200 and elapsed < 12
        }
        
        print(f"  Status: {response.status_code}")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Success: {'✅' if result['success'] else '❌'}")
        
        if response.status_code == 200:
            data = response.json()
            positions = data.get('positions', [])
            print(f"  Positions: {len(positions)}")
            print(f"  Total value: ${data.get('summary', {}).get('total_value_usd', '0')}")
                
        results.append(result)
        
    except Exception as e:
        elapsed = time.time() - start
        print(f"  Failed after {elapsed:.2f}s: {e}")
        results.append({"test": "cold_cache_medium", "error": str(e), "time": elapsed})
    
    # Wait 2 seconds
    print("\nWaiting 2 seconds before warm test...")
    time.sleep(2)
    
    # Test 2: Warm cache
    print("\nTest 2: Warm cache (medium wallet)")
    
    start = time.time()
    try:
        response = requests.get(url, headers=headers, timeout=10)
        elapsed = time.time() - start
        
        result = {
            "test": "warm_cache_medium",
            "status": response.status_code,
            "time": elapsed,
            "success": response.status_code == 200 and elapsed < 0.5
        }
        
        print(f"  Status: {response.status_code}")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Success: {'✅' if result['success'] else '❌'}")
        
        results.append(result)
        
    except Exception as e:
        elapsed = time.time() - start
        print(f"  Failed after {elapsed:.2f}s: {e}")
        results.append({"test": "warm_cache_medium", "error": str(e), "time": elapsed})
    
    # Save results
    with open(f"tmp/medium_wallet_{timestamp}.json", "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "wallet": MEDIUM_WALLET,
            "results": results,
            "overall_success": all(r.get("success", False) for r in results)
        }, f, indent=2)
    
    print(f"\nResults saved to tmp/medium_wallet_{timestamp}.json")
    
    # Summary
    print("\n=== SUMMARY ===")
    cold_time = next((r['time'] for r in results if r.get('test') == 'cold_cache_medium'), None)
    warm_time = next((r['time'] for r in results if r.get('test') == 'warm_cache_medium'), None)
    
    if cold_time:
        print(f"Cold cache: {cold_time:.2f}s (target < 12s) {'✅' if cold_time < 12 else '❌'}")
    if warm_time:
        print(f"Warm cache: {warm_time:.2f}s (target < 0.5s) {'✅' if warm_time < 0.5 else '❌'}")
    
    overall = all(r.get("success", False) for r in results)
    print(f"\nOverall: {'✅ PASS' if overall else '❌ FAIL'}")
    
    return overall

if __name__ == "__main__":
    success = test_medium_wallet()
    exit(0 if success else 1) 