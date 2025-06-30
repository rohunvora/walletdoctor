#!/usr/bin/env python3
"""Test the V2 blockchain fetcher with expert recommendations"""

import asyncio
import os
from blockchain_fetcher_v2 import BlockchainFetcherV2

WALLET = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"

async def test_v2_fetcher():
    """Test our V2 fetcher with collapsed multi-hop trades"""
    
    progress_messages = []
    def capture_progress(msg):
        print(f"Progress: {msg}")
        progress_messages.append(msg)
    
    async with BlockchainFetcherV2(progress_callback=capture_progress) as fetcher:
        try:
            # Fetch all trades
            trades = await fetcher.fetch_wallet_trades(WALLET)
            
            print(f"\n=== RESULTS ===")
            print(f"Total trades fetched: {len(trades)}")
            
            # Check metrics in progress messages
            metrics_started = False
            for msg in progress_messages:
                if "=== METRICS ===" in msg:
                    metrics_started = True
                if metrics_started:
                    print(msg)
                    
            # Expert says we should see ~800-1,100 swaps for 9,249 signatures
            print(f"\nExpert's expected range: 800-1,100 swaps")
            print(f"We got: {len(trades)} trades")
            
            # Show sample trades
            if trades:
                print(f"\nFirst 5 trades:")
                for i, trade in enumerate(trades[:5]):
                    print(f"{i+1}. {trade['timestamp']} - {trade['action']} {trade['amount']:.4f} {trade['token']}")
                    
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_v2_fetcher()) 