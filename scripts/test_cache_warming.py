#!/usr/bin/env python3
"""Test cache warming to solve GPT export timeout issues"""

import requests
import time
import json

# Configuration
API_BASE_URL = "https://web-production-2bb2f.up.railway.app"
API_KEY = "wd_12345678901234567890123456789012"

# Test wallets
WALLETS = {
    "small": {
        "address": "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
        "trades": 145
    },
    "medium": {
        "address": "AAXTYrQR6CHDGhJYz4uSgJ6dq7JTySTR6WyAq8QKZnF8", 
        "trades": 380
    },
    "large": {
        "address": "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
        "trades": 6424
    }
}


def warm_cache(wallet_address: str):
    """Warm the cache for a wallet"""
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    url = f"{API_BASE_URL}/v4/positions/warm-cache/{wallet_address}"
    
    print(f"\n🔥 Warming cache for {wallet_address[:8]}...")
    start_time = time.time()
    
    try:
        response = requests.post(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ {data['status']}: {data.get('message', '')}")
            
            # If warming started, wait and check progress
            if 'progress_token' in data:
                progress_token = data['progress_token']
                print(f"  Progress token: {progress_token[:8]}...")
                
                # Poll progress
                for i in range(120):  # Max 2 minutes
                    time.sleep(1)
                    progress_url = f"{API_BASE_URL}/v4/progress/{progress_token}"
                    prog_resp = requests.get(progress_url)
                    
                    if prog_resp.status_code == 200:
                        progress = prog_resp.json()
                        status = progress.get('status', 'unknown')
                        trades = progress.get('trades', 0)
                        
                        if status == 'complete':
                            duration = time.time() - start_time
                            print(f"✓ Cache warmed in {duration:.1f}s ({trades} trades)")
                            return True
                        elif status == 'error':
                            print(f"✗ Error: {progress.get('error', 'Unknown error')}")
                            return False
                        elif i % 10 == 0:
                            print(f"  Still warming... ({i}s)")
                
                print("✗ Timeout waiting for cache warm")
                return False
            else:
                # Already cached
                return True
        else:
            print(f"✗ Failed: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_gpt_export(wallet_address: str, label: str):
    """Test GPT export performance"""
    headers = {
        "X-API-Key": API_KEY,
        "Accept": "application/json"
    }
    
    url = f"{API_BASE_URL}/v4/positions/export-gpt/{wallet_address}"
    
    print(f"\n📊 Testing GPT export for {label} wallet...")
    start_time = time.time()
    
    try:
        response = requests.get(url, headers=headers, timeout=35)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            cache_status = response.headers.get('X-Cache-Status', 'UNKNOWN')
            response_time = response.headers.get('X-Response-Time-Ms', 'N/A')
            
            print(f"✓ Success in {duration:.1f}s")
            print(f"  - Cache: {cache_status}")
            print(f"  - Response time: {response_time}ms")
            print(f"  - Positions: {len(data.get('positions', []))}")
            print(f"  - Total value: ${data['summary']['total_value_usd']}")
            
            return duration
        else:
            print(f"✗ Failed: {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        duration = time.time() - start_time
        print(f"✗ Timeout after {duration:.1f}s")
        return None
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def main():
    """Run cache warming tests"""
    print("🚀 Cache Warming Performance Test")
    print("=" * 60)
    
    # First check if the new endpoint exists
    print("\n🔍 Checking for cache warming endpoint...")
    test_url = f"{API_BASE_URL}/v4/positions/warm-cache/test"
    try:
        resp = requests.post(test_url, headers={"X-API-Key": API_KEY}, timeout=5)
        if resp.status_code == 404:
            print("✗ Cache warming endpoint not found - need to deploy updated code")
            print("\nTesting with current deployment...")
        elif resp.status_code == 400:
            print("✓ Cache warming endpoint exists")
        else:
            print(f"? Unexpected response: {resp.status_code}")
    except:
        pass
    
    results = {}
    
    # Test each wallet
    for label, info in WALLETS.items():
        wallet = info['address']
        
        print(f"\n{'='*60}")
        print(f"Testing {label.upper()} wallet ({info['trades']} trades)")
        print(f"{'='*60}")
        
        # First try without cache warming (baseline)
        print("\n1️⃣ BASELINE (no cache warming):")
        baseline_time = test_gpt_export(wallet, label)
        
        # Then warm the cache
        print("\n2️⃣ WARMING CACHE:")
        warmed = warm_cache(wallet)
        
        # Test again with warm cache
        if warmed:
            print("\n3️⃣ WITH WARM CACHE:")
            warm_time = test_gpt_export(wallet, label)
        else:
            warm_time = None
        
        results[label] = {
            'baseline': baseline_time,
            'warm': warm_time
        }
    
    # Summary
    print("\n" + "="*60)
    print("📈 PERFORMANCE SUMMARY")
    print("="*60)
    print(f"{'Wallet':<10} {'Trades':<8} {'Baseline':>12} {'Warm Cache':>12} {'Improvement':>12}")
    print("-"*60)
    
    for label, info in WALLETS.items():
        result = results[label]
        baseline = f"{result['baseline']:.1f}s" if result['baseline'] else "TIMEOUT"
        warm = f"{result['warm']:.1f}s" if result['warm'] else "N/A"
        
        if result['baseline'] and result['warm']:
            improvement = f"{(result['baseline'] - result['warm']) / result['baseline'] * 100:.0f}%"
        else:
            improvement = "N/A"
        
        print(f"{label.upper():<10} {info['trades']:<8} {baseline:>12} {warm:>12} {improvement:>12}")
    
    print("\n💡 CONCLUSION:")
    if any(r['warm'] and r['warm'] < 30 for r in results.values()):
        print("✅ Cache warming successfully reduces response time below 30s!")
    else:
        print("❌ Cache warming alone may not be sufficient for large wallets")
        print("   Need to implement SSE streaming or further optimizations")


if __name__ == "__main__":
    main() 