#!/usr/bin/env python3
"""
Performance CI test for WalletDoctor V3
Ensures the API can process a 5k+ trade wallet in under 20 seconds
"""

import os
import pytest
import asyncio
import time
from src.lib.blockchain_fetcher_v3 import BlockchainFetcherV3

# Test wallet with 5k+ trades
TEST_WALLET = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
PERFORMANCE_TARGET_SECONDS = 20
MIN_EXPECTED_TRADES = 5000


def test_performance_under_20_seconds():
    """Test that a 5k+ trade wallet completes in under 20 seconds"""
    # Ensure required environment variables are set
    if not os.getenv("HELIUS_KEY"):
        pytest.skip("HELIUS_KEY not set, skipping performance test")
    
    if not os.getenv("BIRDEYE_API_KEY"):
        pytest.skip("BIRDEYE_API_KEY not set, skipping performance test")
    
    async def run_test():
        start_time = time.time()
        
        async with BlockchainFetcherV3(skip_pricing=True) as fetcher:
            result = await fetcher.fetch_wallet_trades(TEST_WALLET)
        
        elapsed = time.time() - start_time
        
        # Assertions - check the actual response structure
        assert "wallet" in result, "Response missing wallet field"
        assert result["wallet"] == TEST_WALLET
        
        total_trades = result["summary"]["total_trades"]
        assert total_trades >= MIN_EXPECTED_TRADES, (
            f"Expected at least {MIN_EXPECTED_TRADES} trades, got {total_trades}"
        )
        
        assert elapsed < PERFORMANCE_TARGET_SECONDS, (
            f"Performance target failed: took {elapsed:.1f}s (target: <{PERFORMANCE_TARGET_SECONDS}s)"
        )
        
        print(f"\n✅ Performance test passed:")
        print(f"  - Wallet: {TEST_WALLET}")
        print(f"  - Trades: {total_trades}")
        print(f"  - Time: {elapsed:.1f}s")
        print(f"  - Target: <{PERFORMANCE_TARGET_SECONDS}s")
        
        return result, elapsed
    
    # Run the async test
    result, elapsed = asyncio.run(run_test())
    
    # Additional validation
    assert "trades" in result
    assert len(result["trades"]) == result["summary"]["total_trades"]
    assert "summary" in result
    assert "metrics" in result["summary"]
    assert result["summary"]["metrics"]["signatures_fetched"] > 0


def test_rpc_endpoint_configured():
    """Verify RPC endpoint is properly configured"""
    from src.lib.blockchain_fetcher_v3 import HELIUS_RPC_BASE, SIGNATURE_PAGE_LIMIT
    
    assert HELIUS_RPC_BASE == "https://mainnet.helius-rpc.com"
    assert SIGNATURE_PAGE_LIMIT == 1000


def test_no_limit_100_references():
    """Ensure no hardcoded limit=100 references remain in active code"""
    import subprocess
    
    # Search for limit=100 patterns in src directory
    result = subprocess.run(
        ["grep", "-r", "limit.*=.*100", "src/"],
        capture_output=True,
        text=True
    )
    
    # Filter out acceptable uses (like Birdeye batch limits)
    problematic_lines = []
    for line in result.stdout.strip().split('\n'):
        if line and "birdeye" not in line.lower() and "batch" not in line.lower() and "TX_BATCH" not in line:
            problematic_lines.append(line)
    
    assert len(problematic_lines) == 0, (
        f"Found hardcoded limit=100 references:\n" + "\n".join(problematic_lines)
    )


if __name__ == "__main__":
    # Run the test directly
    print("Running WalletDoctor V3 Performance Test...")
    test_performance_under_20_seconds()
    test_rpc_endpoint_configured()
    test_no_limit_100_references()
    print("\n✅ All tests passed!") 