#!/usr/bin/env python3
"""Profile GPT export endpoint on deployed API to identify bottlenecks"""

import requests
import time
import json
from datetime import datetime

# Deployed API endpoint
API_BASE_URL = "https://web-production-2bb2f.up.railway.app"
API_KEY = "wd_12345678901234567890123456789012"  # Test key

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


def test_gpt_export(wallet_label: str, wallet_info: dict, timeout: int = 60):
    """Test GPT export endpoint with timing"""
    print(f"\n{'='*60}")
    print(f"Testing {wallet_label} wallet: {wallet_info['address'][:8]}... ({wallet_info['trades']} trades)")
    print(f"{'='*60}")
    
    headers = {
        "X-API-Key": API_KEY,
        "Accept": "application/json"
    }
    
    url = f"{API_BASE_URL}/v4/positions/export-gpt/{wallet_info['address']}"
    
    # Test 1: Cold cache (first request)
    print("\n🧊 Cold Cache Test:")
    start_time = time.time()
    
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        cold_duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Success: {cold_duration:.1f}s")
            print(f"  - Positions: {len(data.get('positions', []))}")
            print(f"  - Total Value: ${data.get('totalValueUsd', 0):,.2f}")
        else:
            print(f"✗ Failed: {response.status_code}")
            print(f"  Response: {response.text}")
            cold_duration = None
            
    except requests.exceptions.Timeout:
        cold_duration = time.time() - start_time
        print(f"✗ Timeout after {cold_duration:.1f}s")
        cold_duration = None
    except Exception as e:
        cold_duration = time.time() - start_time
        print(f"✗ Error: {e}")
        cold_duration = None
    
    # Test 2: Warm cache (immediate second request)
    print("\n🔥 Warm Cache Test:")
    time.sleep(1)  # Brief pause
    
    start_time = time.time()
    try:
        response = requests.get(url, headers=headers, timeout=30)
        warm_duration = time.time() - start_time
        
        if response.status_code == 200:
            print(f"✓ Success: {warm_duration:.3f}s ({warm_duration*1000:.1f}ms)")
        else:
            print(f"✗ Failed: {response.status_code}")
            warm_duration = None
            
    except Exception as e:
        warm_duration = time.time() - start_time
        print(f"✗ Error: {e}")
        warm_duration = None
    
    return {
        "cold_cache": cold_duration,
        "warm_cache": warm_duration
    }


def main():
    """Run performance tests"""
    print("🔍 GPT Export Remote API Performance Testing")
    print(f"📍 API: {API_BASE_URL}")
    print(f"🔑 Key: {API_KEY}")
    
    # First check health
    print("\n📡 Checking API health...")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        health = response.json()
        print(f"✓ API is healthy")
        print(f"  - Version: {health.get('version', 'unknown')}")
        print(f"  - Features: {health.get('features', {})}")
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return
    
    results = {}
    
    # Test each wallet
    for label, info in WALLETS.items():
        results[label] = test_gpt_export(label.upper(), info)
    
    # Summary
    print("\n" + "="*60)
    print("📊 PERFORMANCE SUMMARY")
    print("="*60)
    print(f"{'Wallet':<10} {'Trades':<8} {'Cold Cache':>12} {'Warm Cache':>12} {'Status':<10}")
    print("-"*60)
    
    for label, info in WALLETS.items():
        result = results[label]
        cold = f"{result['cold_cache']:.1f}s" if result['cold_cache'] else "TIMEOUT"
        warm = f"{result['warm_cache']*1000:.0f}ms" if result['warm_cache'] else "FAILED"
        status = "✓ OK" if result['cold_cache'] and result['cold_cache'] < 30 else "✗ SLOW"
        
        print(f"{label.upper():<10} {info['trades']:<8} {cold:>12} {warm:>12} {status:<10}")
    
    # Analysis
    print("\n🎯 BOTTLENECK ANALYSIS")
    print("-"*40)
    
    large_result = results.get('large', {})
    if not large_result.get('cold_cache'):
        print("❌ Large wallet times out on cold cache")
        print("   - Current timeout: >30s")
        print("   - Railway limit: 30s")
        print("   - ChatGPT limit: 30s")
        print("\n💡 IMMEDIATE ACTION REQUIRED:")
        print("   1. Implement cache pre-warming")
        print("   2. Or switch to SSE streaming")
        print("   3. Or optimize fetching/calculation")
    else:
        print("✅ Large wallet completes within timeout")
    
    print("\n📝 RECOMMENDATIONS:")
    print("1. Cache Warming: Add /api/v4/warm-cache/:wallet endpoint")
    print("2. SSE Streaming: Convert GPT export to stream progress")
    print("3. Batch Optimization: Profile Helius API calls for concurrency gains")


if __name__ == "__main__":
    main() 