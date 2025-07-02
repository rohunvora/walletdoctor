#!/usr/bin/env python3
"""
Test script for RCA - runs without Birdeye to isolate price fetching bottleneck
"""

import os
import sys
import time
import asyncio
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Temporarily disable Birdeye
os.environ["BIRDEYE_API_KEY"] = ""

# Set other required env vars
os.environ["HELIUS_KEY"] = "9475ccc3-58d7-417f-9760-7fe14f198fa5"

from src.lib.blockchain_fetcher_v3_fast import BlockchainFetcherV3Fast

async def test_without_birdeye():
    """Test blockchain fetcher without Birdeye price lookups"""
    
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"=== No-Birdeye Control Test ===")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Wallet: {wallet}")
    print(f"HELIUS_KEY present: True")
    print(f"BIRDEYE_API_KEY present: False (disabled)")
    print("")
    
    def progress_logger(msg):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{ts}] {msg}")
    
    start_time = time.time()
    
    try:
        # Run with skip_pricing=True to avoid Birdeye calls
        async with BlockchainFetcherV3Fast(
            progress_callback=progress_logger,
            skip_pricing=True  # This should skip all price fetching
        ) as fetcher:
            result = await fetcher.fetch_wallet_trades(wallet)
        
        elapsed = time.time() - start_time
        
        print(f"\n=== RESULTS ===")
        print(f"Total time: {elapsed:.2f}s")
        print(f"Total trades: {result['summary']['total_trades']}")
        print(f"Signature fetch time: {result.get('metrics', {}).get('signature_fetch_time', 0):.2f}s")
        print(f"Transaction fetch time: {result.get('metrics', {}).get('transaction_fetch_time', 0):.2f}s")
        
        # Save results
        with open(f"tmp/phase_log_no_birdeye_{timestamp}.txt", "w") as f:
            f.write(f"=== No-Birdeye Control Test ===\n")
            f.write(f"Time: {datetime.now().isoformat()}\n")
            f.write(f"Wallet: {wallet}\n")
            f.write(f"Total time: {elapsed:.2f}s\n")
            f.write(f"Total trades: {result['summary']['total_trades']}\n")
            f.write(f"\nMetrics:\n")
            for key, value in result.get('metrics', {}).items():
                f.write(f"  {key}: {value}\n")
        
        print(f"\nResults saved to tmp/phase_log_no_birdeye_{timestamp}.txt")
        
        return elapsed
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\nERROR after {elapsed:.2f}s: {e}")
        import traceback
        traceback.print_exc()
        return elapsed

if __name__ == "__main__":
    duration = asyncio.run(test_without_birdeye())
    print(f"\nFinal duration: {duration:.2f}s") 