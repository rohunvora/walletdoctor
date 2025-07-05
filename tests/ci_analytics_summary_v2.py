#!/usr/bin/env python3
"""
CI test for v0.8.0 aggregated analytics summary endpoint
Tests performance guardrails and response format
"""

import requests
import time
import json
import sys
import os

# Test configuration
BASE_URL = os.getenv("API_BASE_URL", "https://web-production-2bb2f.up.railway.app")
API_KEY = os.getenv("API_KEY", "wd_test1234567890abcdef1234567890ab")

# Test wallets
SMALL_WALLET = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"  # ~1,100 trades
MEDIUM_WALLET = "AAXTYrQR6CHDGhJYz4uSgJ6dq7JTySTR6WyAq8QKZnF8"  # ~2,300 trades

# Performance targets
COLD_TARGET_MS = 8000   # 8s for cold path
WARM_TARGET_MS = 500    # 0.5s for warm path
SIZE_TARGET_KB = 25     # 25KB max size


def test_endpoint_disabled():
    """Test that endpoint returns 404 when AGG_SUMMARY=false"""
    print("\n=== Testing Endpoint Disabled State ===")
    
    response = requests.get(
        f"{BASE_URL}/v4/analytics/summary/{SMALL_WALLET}",
        headers={"X-Api-Key": API_KEY}
    )
    
    # When disabled, should return 404
    if response.status_code == 404:
        data = response.json()
        if "AGG_SUMMARY=true" in data.get("message", ""):
            print("✅ Endpoint correctly disabled (returns 404)")
            return True
    
    # If we get 200, the endpoint is enabled
    if response.status_code == 200:
        print("ℹ️  Endpoint is enabled (AGG_SUMMARY=true)")
        return False
    
    print(f"❌ Unexpected status code: {response.status_code}")
    return False


def test_cold_performance(wallet_address):
    """Test cold cache performance"""
    print(f"\n=== Testing Cold Performance for {wallet_address[:8]}... ===")
    
    # Force cache refresh
    start_time = time.time()
    response = requests.get(
        f"{BASE_URL}/v4/analytics/summary/{wallet_address}",
        headers={"X-Api-Key": API_KEY},
        params={"force_refresh": "true"}
    )
    duration_ms = (time.time() - start_time) * 1000
    
    if response.status_code != 200:
        print(f"❌ Request failed: {response.status_code}")
        return False
    
    # Check response time
    if duration_ms <= COLD_TARGET_MS:
        print(f"✅ Cold performance: {duration_ms:.0f}ms (target: <{COLD_TARGET_MS}ms)")
    else:
        print(f"❌ Cold performance: {duration_ms:.0f}ms (target: <{COLD_TARGET_MS}ms)")
        return False
    
    # Check response size
    response_size = len(response.content)
    size_kb = response_size / 1024
    
    if size_kb <= SIZE_TARGET_KB:
        print(f"✅ Response size: {size_kb:.1f}KB (target: <{SIZE_TARGET_KB}KB)")
    else:
        print(f"❌ Response size: {size_kb:.1f}KB (target: <{SIZE_TARGET_KB}KB)")
        return False
    
    return True


def test_warm_performance(wallet_address):
    """Test warm cache performance"""
    print(f"\n=== Testing Warm Performance for {wallet_address[:8]}... ===")
    
    # First request to warm cache
    requests.get(
        f"{BASE_URL}/v4/analytics/summary/{wallet_address}",
        headers={"X-Api-Key": API_KEY}
    )
    
    # Wait a moment for cache to settle
    time.sleep(0.1)
    
    # Test warm performance
    start_time = time.time()
    response = requests.get(
        f"{BASE_URL}/v4/analytics/summary/{wallet_address}",
        headers={"X-Api-Key": API_KEY}
    )
    duration_ms = (time.time() - start_time) * 1000
    
    if response.status_code != 200:
        print(f"❌ Request failed: {response.status_code}")
        return False
    
    if duration_ms <= WARM_TARGET_MS:
        print(f"✅ Warm performance: {duration_ms:.0f}ms (target: <{WARM_TARGET_MS}ms)")
        return True
    else:
        print(f"❌ Warm performance: {duration_ms:.0f}ms (target: <{WARM_TARGET_MS}ms)")
        return False


def test_response_format(wallet_address):
    """Test response format and data quality"""
    print(f"\n=== Testing Response Format for {wallet_address[:8]}... ===")
    
    response = requests.get(
        f"{BASE_URL}/v4/analytics/summary/{wallet_address}",
        headers={"X-Api-Key": API_KEY}
    )
    
    if response.status_code != 200:
        print(f"❌ Request failed: {response.status_code}")
        return False
    
    data = response.json()
    
    # Check required top-level keys
    required_keys = [
        "wallet", "schema_version", "generated_at",
        "wallet_summary", "pnl_analysis", "win_rate",
        "trade_volume", "token_breakdown", "recent_windows",
        "trading_patterns", "meta"
    ]
    
    missing_keys = [key for key in required_keys if key not in data]
    if missing_keys:
        print(f"❌ Missing required keys: {missing_keys}")
        return False
    
    print("✅ All required keys present")
    
    # Validate specific fields
    checks = [
        (data["schema_version"] == "v0.8.0-aggregated", "Schema version correct"),
        (data["wallet"] == wallet_address, "Wallet address matches"),
        (isinstance(data["token_breakdown"], list), "Token breakdown is a list"),
        (len(data["token_breakdown"]) <= 10, "Token breakdown limited to 10"),
        ("payload_size_bytes" in data["meta"], "Payload size tracked"),
        (data["wallet_summary"]["total_trades"] > 0, "Has trade data")
    ]
    
    all_passed = True
    for check, description in checks:
        if check:
            print(f"✅ {description}")
        else:
            print(f"❌ {description}")
            all_passed = False
    
    # Print summary stats
    print(f"\n📊 Summary Stats:")
    print(f"  Total trades: {data['wallet_summary']['total_trades']}")
    print(f"  Realized P&L: ${data['pnl_analysis']['total_realized_pnl_usd']}")
    print(f"  Win rate: {data['win_rate']['overall_win_rate']}%")
    print(f"  Top token by P&L: {data['token_breakdown'][0]['symbol'] if data['token_breakdown'] else 'N/A'}")
    
    return all_passed


def test_window_parameter():
    """Test window parameter functionality"""
    print(f"\n=== Testing Window Parameter ===")
    
    # Test with window=false
    response = requests.get(
        f"{BASE_URL}/v4/analytics/summary/{SMALL_WALLET}",
        headers={"X-Api-Key": API_KEY},
        params={"window": "false", "force_refresh": "true"}
    )
    
    if response.status_code != 200:
        print(f"❌ Request failed: {response.status_code}")
        return False
    
    data = response.json()
    
    # Check that recent_windows is minimal
    if "recent_windows" in data:
        windows = data["recent_windows"]
        if windows.get("last_7_days", {}).get("trades", 0) == 0:
            print("✅ Window parameter working (no window calculations)")
            return True
    
    print("❌ Window parameter not working correctly")
    return False


def main():
    """Run all CI tests"""
    print("🧪 WalletDoctor Analytics Summary v2 CI Test")
    print("=" * 50)
    
    results = []
    
    # Check if endpoint is disabled
    is_disabled = test_endpoint_disabled()
    
    if is_disabled:
        print("\n⚠️  Endpoint is disabled - skipping performance tests")
        print("Set AGG_SUMMARY=true to enable endpoint")
        return 0  # Not a failure, just disabled
    
    # Run tests
    tests = [
        ("Cold Performance (Small)", lambda: test_cold_performance(SMALL_WALLET)),
        ("Warm Performance (Small)", lambda: test_warm_performance(SMALL_WALLET)),
        ("Response Format", lambda: test_response_format(SMALL_WALLET)),
        ("Window Parameter", lambda: test_window_parameter()),
        ("Cold Performance (Medium)", lambda: test_cold_performance(MEDIUM_WALLET)),
    ]
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} failed with error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} passed")
    
    if passed == total:
        print("\n✅ All tests passed!")
        return 0
    else:
        print(f"\n❌ {total - passed} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 