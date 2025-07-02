#!/usr/bin/env python3
"""
Test Railway deployment performance for GPT export endpoint (WAL-613)

Tests the small wallet to ensure < 30s response time.
"""

import time
import requests
import json
import os
import sys
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
SMALL_WALLET = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
API_KEY = os.getenv("API_KEY", "wd_" + "a" * 32)
BASE_URL = os.getenv("API_BASE_URL", "https://web-production-2bb2f.up.railway.app")

# Performance targets
TARGET_COLD_CACHE = 30.0  # 30 seconds for cold cache
TARGET_WARM_CACHE = 5.0   # 5 seconds for warm cache


def test_endpoint(wallet: str, test_name: str) -> dict:
    """Test the GPT export endpoint and return timing breakdown"""
    
    url = f"{BASE_URL}/v4/positions/export-gpt/{wallet}"
    headers = {"X-Api-Key": API_KEY}
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing: {test_name}")
    logger.info(f"URL: {url}")
    logger.info(f"Wallet: {wallet}")
    
    # Start timing
    start_time = time.time()
    
    try:
        # Make request
        response = requests.get(url, headers=headers, timeout=60)
        end_time = time.time()
        
        # Calculate timings
        total_time = end_time - start_time
        
        # Extract timing from header if available
        server_time = float(response.headers.get("X-Response-Time-Ms", 0)) / 1000
        network_time = total_time - server_time if server_time > 0 else 0
        
        result = {
            "test_name": test_name,
            "status_code": response.status_code,
            "total_time": total_time,
            "server_time": server_time,
            "network_time": network_time,
            "cache_status": response.headers.get("X-Cache-Status", "UNKNOWN"),
            "timestamp": datetime.now().isoformat()
        }
        
        if response.status_code == 200:
            data = response.json()
            result["positions_count"] = len(data.get("positions", []))
            result["schema_version"] = data.get("schema_version")
            result["stale"] = data.get("stale", False)
            result["age_seconds"] = data.get("age_seconds", 0)
            
            logger.info(f"✅ Success: {response.status_code}")
            logger.info(f"Positions: {result['positions_count']}")
            logger.info(f"Cache Status: {result['cache_status']}")
        else:
            logger.error(f"❌ Failed: {response.status_code}")
            logger.error(f"Response: {response.text[:200]}")
            result["error"] = response.text
            
        # Log timing breakdown
        logger.info(f"\nTiming Breakdown:")
        logger.info(f"  Total Time: {total_time:.2f}s")
        logger.info(f"  Server Time: {server_time:.2f}s")
        logger.info(f"  Network Time: {network_time:.2f}s")
        
        # Check against targets
        if result["cache_status"] == "MISS":
            target = TARGET_COLD_CACHE
            status = "🔥 COLD CACHE"
        else:
            target = TARGET_WARM_CACHE
            status = "♨️  WARM CACHE"
            
        logger.info(f"\n{status}")
        if total_time <= target:
            logger.info(f"✅ PASS: {total_time:.2f}s <= {target}s target")
        else:
            logger.warning(f"⚠️  SLOW: {total_time:.2f}s > {target}s target")
        
        return result
        
    except requests.exceptions.Timeout:
        logger.error("❌ Request timed out after 60s")
        return {
            "test_name": test_name,
            "status_code": 0,
            "error": "Timeout after 60s",
            "total_time": 60.0,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return {
            "test_name": test_name,
            "status_code": 0,
            "error": str(e),
            "total_time": time.time() - start_time,
            "timestamp": datetime.now().isoformat()
        }


def warm_cache(wallet: str):
    """Warm the cache for a wallet"""
    url = f"{BASE_URL}/v4/positions/warm-cache/{wallet}"
    headers = {"X-Api-Key": API_KEY}
    
    logger.info(f"\nWarming cache for {wallet}...")
    
    try:
        response = requests.post(url, headers=headers, timeout=60)
        if response.status_code == 200:
            logger.info("✅ Cache warmed successfully")
        else:
            logger.warning(f"⚠️  Cache warming failed: {response.status_code}")
    except Exception as e:
        logger.warning(f"⚠️  Cache warming error: {e}")


def main():
    """Run performance tests"""
    
    logger.info(f"\n{'='*60}")
    logger.info("Railway Performance Test - WAL-613")
    logger.info(f"{'='*60}")
    logger.info(f"Base URL: {BASE_URL}")
    logger.info(f"Small Wallet: {SMALL_WALLET}")
    logger.info(f"Target (cold): {TARGET_COLD_CACHE}s")
    logger.info(f"Target (warm): {TARGET_WARM_CACHE}s")
    
    results = []
    
    # Test 1: Cold cache
    logger.info(f"\n{'='*60}")
    logger.info("TEST 1: COLD CACHE")
    result1 = test_endpoint(SMALL_WALLET, "Cold Cache")
    results.append(result1)
    
    # Give the server a moment
    time.sleep(2)
    
    # Test 2: Warm cache (should be fast)
    logger.info(f"\n{'='*60}")
    logger.info("TEST 2: WARM CACHE")
    result2 = test_endpoint(SMALL_WALLET, "Warm Cache (immediate)")
    results.append(result2)
    
    # Test 3: Explicitly warm cache
    warm_cache(SMALL_WALLET)
    time.sleep(2)
    
    logger.info(f"\n{'='*60}")
    logger.info("TEST 3: AFTER EXPLICIT WARM")
    result3 = test_endpoint(SMALL_WALLET, "After Explicit Warm")
    results.append(result3)
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("SUMMARY")
    logger.info(f"{'='*60}\n")
    
    all_passed = True
    for result in results:
        status = "✅" if result["status_code"] == 200 else "❌"
        cache = result.get("cache_status", "N/A")
        time_str = f"{result['total_time']:.2f}s"
        
        # Check against appropriate target
        if cache == "MISS":
            passed = result["total_time"] <= TARGET_COLD_CACHE
        else:
            passed = result["total_time"] <= TARGET_WARM_CACHE
            
        all_passed = all_passed and passed and result["status_code"] == 200
        
        logger.info(f"{status} {result['test_name']}: {time_str} ({cache})")
    
    # Write detailed report
    report_file = "railway_performance_report.json"
    with open(report_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "base_url": BASE_URL,
            "wallet": SMALL_WALLET,
            "targets": {
                "cold_cache": TARGET_COLD_CACHE,
                "warm_cache": TARGET_WARM_CACHE
            },
            "results": results,
            "all_passed": all_passed
        }, f, indent=2)
    
    logger.info(f"\nDetailed report saved to: {report_file}")
    
    if all_passed:
        logger.info("\n✅ All tests passed!")
        return 0
    else:
        logger.error("\n❌ Some tests failed or were too slow")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 