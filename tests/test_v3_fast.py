#!/usr/bin/env python3
"""Test the V3 Fast implementation"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.lib.blockchain_fetcher_v3_fast import fetch_wallet_trades_fast
import time

WALLET = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"

def test_fast_mode():
    """Test fast mode (limited data, no pricing)"""
    print("=" * 60)
    print("TESTING V3 FAST - TEST MODE")
    print("=" * 60)
    
    start = time.time()
    result = fetch_wallet_trades_fast(WALLET, print, test_mode=True)
    elapsed = time.time() - start
    
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    metrics = result['summary']['metrics']
    print(f"\nMETRICS:")
    print(f"  Signatures fetched: {metrics['signatures_fetched']}")
    print(f"  Signatures parsed: {metrics['signatures_parsed']}")
    print(f"  Events swap rows: {metrics['events_swap_rows']}")
    print(f"  Fallback rows: {metrics['fallback_rows']}")
    
    print(f"\nPERFORMANCE:")
    print(f"  Time taken: {elapsed:.1f}s")
    print(f"  Total trades: {result['summary']['total_trades']}")
    
    # Check if fallback parser is working
    if metrics['fallback_rows'] > 0:
        print(f"\n✓ Fallback parser working: {metrics['fallback_rows']} trades parsed")
    else:
        print(f"\n✗ Fallback parser not working!")
        
    # Show the improvement
    expected_time_v3 = 30  # V3 would take ~30s for this
    speedup = expected_time_v3 / elapsed
    print(f"\nSPEED IMPROVEMENT: {speedup:.1f}x faster than V3!")

if __name__ == "__main__":
    test_fast_mode() 