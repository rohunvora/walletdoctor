#!/usr/bin/env python3
"""
Phase A Timing Test - Validate beta_mode performance
Expected: < 10s cold, < 0.3s warm
"""

import requests
import time
import json
from datetime import datetime

BASE_URL = "https://web-production-2bb2f.up.railway.app"
SMALL_WALLET = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
API_KEY = "wd_12345678901234567890123456789012"

def test_phase_a():
    """Test Phase A implementation"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = []
    
    print("=== Phase A Timing Test ===")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Wallet: {SMALL_WALLET}")
    print("")
    
    # Test 1: Cold cache with beta_mode
    print("Test 1: Cold cache with beta_mode=true")
    url = f"{BASE_URL}/v4/positions/export-gpt/{SMALL_WALLET}?beta_mode=true"
    headers = {"X-Api-Key": API_KEY}
    
    start = time.time()
    try:
        response = requests.get(url, headers=headers, timeout=30)
        elapsed = time.time() - start
        
        result = {
            "test": "cold_cache_beta",
            "status": response.status_code,
            "time": elapsed,
            "success": response.status_code == 200 and elapsed < 10
        }
        
        print(f"  Status: {response.status_code}")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Success: {'✅' if result['success'] else '❌'}")
        
        if response.status_code == 200:
            data = response.json()
            positions = data.get('positions', [])
            print(f"  Positions: {len(positions)}")
            
            # Check if prices are null as expected
            if positions:
                first_pos = positions[0]
                has_price = first_pos.get('current_price_usd') is not None
                print(f"  Has prices: {'Yes' if has_price else 'No (as expected)'}")
                
        results.append(result)
        
    except Exception as e:
        elapsed = time.time() - start
        print(f"  Failed after {elapsed:.2f}s: {e}")
        results.append({"test": "cold_cache_beta", "error": str(e), "time": elapsed})
    
    # Wait 2 seconds
    print("\nWaiting 2 seconds before warm test...")
    time.sleep(2)
    
    # Test 2: Warm cache with beta_mode
    print("\nTest 2: Warm cache with beta_mode=true")
    
    start = time.time()
    try:
        response = requests.get(url, headers=headers, timeout=5)
        elapsed = time.time() - start
        
        result = {
            "test": "warm_cache_beta",
            "status": response.status_code,
            "time": elapsed,
            "success": response.status_code == 200 and elapsed < 0.3
        }
        
        print(f"  Status: {response.status_code}")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Success: {'✅' if result['success'] else '❌'}")
        
        results.append(result)
        
    except Exception as e:
        elapsed = time.time() - start
        print(f"  Failed after {elapsed:.2f}s: {e}")
        results.append({"test": "warm_cache_beta", "error": str(e), "time": elapsed})
    
    # Test 3: Check environment variables
    print("\nTest 3: Check environment variables")
    diag_url = f"{BASE_URL}/v4/diagnostics"
    
    try:
        response = requests.get(diag_url, timeout=5)
        if response.status_code == 200:
            env = response.json().get('env', {})
            
            expected = {
                "POSITION_CACHE_TTL_SEC": "300",  # Fixed name
                "WEB_CONCURRENCY": "1",
                "HELIUS_PARALLEL_REQUESTS": "15",
                "HELIUS_TIMEOUT": "20"
            }
            
            print("  Environment variables:")
            all_correct = True
            for key, expected_val in expected.items():
                actual = env.get(key.replace("_SEC", ""), "NOT SET")  # Handle old name
                if key == "POSITION_CACHE_TTL_SEC":
                    # Check both possible names
                    actual = env.get("POSITION_CACHE_TTL_SEC") or env.get("POSITION_CACHE_TTL", "NOT SET")
                
                is_correct = str(actual) == expected_val
                all_correct &= is_correct
                print(f"    {key}: {actual} {'✅' if is_correct else f'❌ (expected {expected_val})'}")
                
            results.append({"test": "env_check", "success": all_correct})
    except Exception as e:
        print(f"  Failed: {e}")
        results.append({"test": "env_check", "error": str(e)})
    
    # Save results
    with open(f"tmp/phase_a_timing_{timestamp}.json", "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "overall_success": all(r.get("success", False) for r in results)
        }, f, indent=2)
    
    print(f"\nResults saved to tmp/phase_a_timing_{timestamp}.json")
    
    # Summary
    print("\n=== SUMMARY ===")
    cold_time = next((r['time'] for r in results if r.get('test') == 'cold_cache_beta'), None)
    warm_time = next((r['time'] for r in results if r.get('test') == 'warm_cache_beta'), None)
    
    if cold_time:
        print(f"Cold cache: {cold_time:.2f}s (target < 10s) {'✅' if cold_time < 10 else '❌'}")
    if warm_time:
        print(f"Warm cache: {warm_time:.2f}s (target < 0.3s) {'✅' if warm_time < 0.3 else '❌'}")
    
    overall = all(r.get("success", False) for r in results)
    print(f"\nOverall: {'✅ PASS' if overall else '❌ FAIL'}")
    
    return overall

if __name__ == "__main__":
    success = test_phase_a()
    exit(0 if success else 1) 