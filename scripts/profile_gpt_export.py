#!/usr/bin/env python3
"""Profile GPT export endpoint to identify bottlenecks"""

import asyncio
import time
import sys
import os
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.lib.blockchain_fetcher_v3_fast import BlockchainFetcherV3Fast
from src.lib.position_builder import PositionBuilder
from src.lib.unrealized_pnl_calculator import UnrealizedPnLCalculator
from src.lib.position_cache_v2 import get_position_cache_v2
from src.lib.position_models import CostBasisMethod
from src.config.feature_flags import get_cost_basis_method

# Test wallets
WALLETS = {
    "small": "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",  # 145 trades
    "medium": "AAXTYrQR6CHDGhJYz4uSgJ6dq7JTySTR6WyAq8QKZnF8",  # 380 trades
    "large": "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",  # 6,424 trades
}


class ProfileTimer:
    """Context manager for timing operations"""
    def __init__(self, name):
        self.name = name
        self.start = None
        self.duration = 0
        
    def __enter__(self):
        self.start = time.time()
        return self
        
    def __exit__(self, *args):
        self.duration = (time.time() - self.start) * 1000  # ms
        

async def profile_wallet(wallet_address: str, wallet_label: str):
    """Profile the full GPT export pipeline for a wallet"""
    print(f"\n{'='*60}")
    print(f"Profiling {wallet_label} wallet: {wallet_address[:8]}...")
    print(f"{'='*60}")
    
    timings = {}
    total_start = time.time()
    
    # Step 1: Check cache
    with ProfileTimer("cache_check") as timer:
        cache = get_position_cache_v2()
        cached_result = await cache.get_portfolio_snapshot(wallet_address)
    timings["cache_check"] = timer.duration
    
    if cached_result:
        print(f"✓ Found in cache: {timer.duration:.1f}ms")
        snapshot, is_stale = cached_result
        print(f"  - Positions: {len(snapshot.positions)}")
        print(f"  - Is stale: {is_stale}")
        return timings
    
    print(f"✗ Not in cache, fetching fresh data...")
    
    # Step 2: Fetch trades from blockchain
    with ProfileTimer("blockchain_fetch") as timer:
        async with BlockchainFetcherV3Fast(skip_pricing=False) as fetcher:
            # Hook into progress callback
            fetch_timings = {"signatures": 0, "transactions": 0, "metadata": 0, "prices": 0}
            
            def progress_callback(msg):
                if "Fetched" in msg and "signatures" in msg:
                    fetch_timings["signatures"] = time.time()
                elif "SWAP transactions" in msg:
                    fetch_timings["transactions"] = time.time()
                elif "metadata" in msg:
                    fetch_timings["metadata"] = time.time()
                elif "Fetching prices" in msg:
                    fetch_timings["prices"] = time.time()
                print(f"  {msg}")
            
            fetcher.progress_callback = progress_callback
            result = await fetcher.fetch_wallet_trades(wallet_address)
    
    timings["blockchain_fetch"] = timer.duration
    trades = result.get("trades", [])
    print(f"✓ Fetched {len(trades)} trades: {timer.duration:.1f}ms")
    
    # Calculate sub-timings
    if fetch_timings["signatures"]:
        start = total_start
        timings["fetch_signatures"] = (fetch_timings["signatures"] - start) * 1000
        timings["fetch_transactions"] = (fetch_timings["transactions"] - fetch_timings["signatures"]) * 1000
        timings["fetch_metadata"] = (fetch_timings["metadata"] - fetch_timings["transactions"]) * 1000
        timings["fetch_prices"] = timer.duration - sum([
            timings["fetch_signatures"],
            timings["fetch_transactions"],
            timings["fetch_metadata"]
        ])
    
    # Step 3: Build positions
    with ProfileTimer("position_building") as timer:
        method = CostBasisMethod(get_cost_basis_method())
        builder = PositionBuilder(method)
        positions = builder.build_positions_from_trades(trades, wallet_address)
    timings["position_building"] = timer.duration
    print(f"✓ Built {len(positions)} positions: {timer.duration:.1f}ms")
    
    # Step 4: Calculate unrealized P&L
    with ProfileTimer("pnl_calculation") as timer:
        calculator = UnrealizedPnLCalculator()
        position_pnls = await calculator.create_position_pnl_list(positions)
    timings["pnl_calculation"] = timer.duration
    print(f"✓ Calculated P&L: {timer.duration:.1f}ms")
    
    # Step 5: Create and cache snapshot
    with ProfileTimer("snapshot_creation") as timer:
        from src.lib.position_models import PositionSnapshot
        snapshot = PositionSnapshot.from_positions(wallet_address, position_pnls)
        await cache.set_portfolio_snapshot(snapshot)
    timings["snapshot_creation"] = timer.duration
    print(f"✓ Created snapshot: {timer.duration:.1f}ms")
    
    # Total time
    total_time = (time.time() - total_start) * 1000
    timings["total"] = total_time
    
    # Print breakdown
    print(f"\n📊 Timing Breakdown:")
    print(f"{'Operation':<25} {'Time (ms)':>10} {'% of Total':>10}")
    print("-" * 47)
    
    # Sort by duration
    sorted_timings = sorted(timings.items(), key=lambda x: x[1], reverse=True)
    for operation, duration in sorted_timings:
        if operation != "total":
            percentage = (duration / total_time) * 100
            print(f"{operation:<25} {duration:>10.1f} {percentage:>10.1f}%")
    
    print("-" * 47)
    print(f"{'TOTAL':<25} {total_time:>10.1f} {100.0:>10.1f}%")
    
    return timings


async def test_warm_cache(wallet_address: str, wallet_label: str):
    """Test warm cache performance"""
    print(f"\n🔥 Testing warm cache for {wallet_label}...")
    
    # Ensure cache is warm
    cache = get_position_cache_v2()
    cached = await cache.get_portfolio_snapshot(wallet_address)
    
    if not cached:
        print("Cache miss - warming cache first...")
        await profile_wallet(wallet_address, wallet_label)
    
    # Now test warm cache
    start = time.time()
    snapshot, is_stale = await cache.get_portfolio_snapshot(wallet_address)
    duration = (time.time() - start) * 1000
    
    print(f"✓ Warm cache response: {duration:.1f}ms")
    print(f"  - Positions: {len(snapshot.positions)}")
    print(f"  - Total value: ${snapshot.total_value_usd}")
    
    return duration


async def main():
    """Run profiling tests"""
    print("🔍 GPT Export Performance Profiling")
    print("=" * 60)
    
    results = {}
    
    # Test each wallet size
    for size, wallet in WALLETS.items():
        results[size] = await profile_wallet(wallet, size.upper())
        
        # Also test warm cache
        warm_time = await test_warm_cache(wallet, size.upper())
        results[size]["warm_cache"] = warm_time
    
    # Summary
    print("\n📈 Performance Summary")
    print("=" * 60)
    print(f"{'Wallet Size':<12} {'Trades':<8} {'Cold (s)':>10} {'Warm (ms)':>10}")
    print("-" * 42)
    
    print(f"{'Small':<12} {'145':<8} {results['small']['total']/1000:>10.1f} {results['small']['warm_cache']:>10.1f}")
    print(f"{'Medium':<12} {'380':<8} {results['medium']['total']/1000:>10.1f} {results['medium']['warm_cache']:>10.1f}")
    print(f"{'Large':<12} {'6,424':<8} {results['large']['total']/1000:>10.1f} {results['large']['warm_cache']:>10.1f}")
    
    # Identify bottleneck for large wallet
    print("\n🎯 Large Wallet Bottleneck Analysis")
    print("-" * 40)
    large_timings = results['large']
    
    # Find top 3 slowest operations
    sorted_ops = sorted(
        [(k, v) for k, v in large_timings.items() if k not in ['total', 'warm_cache']],
        key=lambda x: x[1],
        reverse=True
    )[:3]
    
    for op, duration in sorted_ops:
        percentage = (duration / large_timings['total']) * 100
        print(f"{op}: {duration/1000:.1f}s ({percentage:.0f}%)")
    
    # Recommendations
    print("\n💡 Optimization Recommendations:")
    if large_timings.get('fetch_prices', 0) > 10000:
        print("- Price fetching is the bottleneck")
        print("- Consider: Batch price fetching, cache prices more aggressively")
    
    if large_timings.get('fetch_transactions', 0) > 10000:
        print("- Transaction fetching is the bottleneck")
        print("- Consider: Increase parallel fetching, optimize batch sizes")
    
    if large_timings.get('blockchain_fetch', 0) > 30000:
        print("- Overall blockchain fetch exceeds 30s")
        print("- MUST implement cache warming or streaming response")


if __name__ == "__main__":
    asyncio.run(main()) 