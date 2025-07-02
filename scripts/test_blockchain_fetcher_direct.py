#!/usr/bin/env python3
"""Test blockchain fetcher performance directly"""

import sys
import time
import os
import asyncio
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set env vars from script args if provided
if len(sys.argv) > 1:
    os.environ["HELIUS_KEY"] = sys.argv[1]
if len(sys.argv) > 2:
    os.environ["BIRDEYE_API_KEY"] = sys.argv[2]

from src.lib.blockchain_fetcher_v3_fast import BlockchainFetcherV3Fast

async def test_blockchain_fetcher():
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    print(f"Testing blockchain fetcher for wallet: {wallet}")
    print(f"HELIUS_KEY present: {bool(os.getenv('HELIUS_KEY'))}")
    print(f"BIRDEYE_API_KEY present: {bool(os.getenv('BIRDEYE_API_KEY'))}")
    print(f"Started at: {datetime.now().isoformat()}")
    
    def progress_logger(msg):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{ts}] {msg}")
    
    start_time = time.time()
    
    try:
        async with BlockchainFetcherV3Fast(
            progress_callback=progress_logger,
            skip_pricing=False
        ) as fetcher:
            result = await fetcher.fetch_wallet_trades(wallet)
        
        elapsed = time.time() - start_time
        
        print(f"\n=== RESULTS ===")
        print(f"Total time: {elapsed:.2f}s")
        print(f"Total trades: {result['summary']['total_trades']}")
        print(f"Signature fetch time: {result['metrics'].get('signature_fetch_time', 0):.2f}s")
        print(f"Transaction fetch time: {result['metrics'].get('transaction_fetch_time', 0):.2f}s")
        print(f"Price fetch time: {result['metrics'].get('price_fetch_time', 0):.2f}s")
        
        return elapsed
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\nERROR after {elapsed:.2f}s: {e}")
        return elapsed

if __name__ == "__main__":
    duration = asyncio.run(test_blockchain_fetcher())
    print(f"\nFinal duration: {duration:.2f}s") 