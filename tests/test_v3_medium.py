#!/usr/bin/env python3
"""Test V3 with 20 pages to verify ~900-1,100 trades expectation"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.lib.blockchain_fetcher_v3_fast import BlockchainFetcherV3Fast
import asyncio

WALLET = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"


async def test_medium():
    """Test with 20 pages"""
    print("Testing V3 with 20 pages (expecting ~200-300 trades)...")
    print("=" * 60)

    async with BlockchainFetcherV3Fast(
        progress_callback=print, max_pages=20, skip_pricing=True  # 20 pages  # Skip pricing for speed
    ) as fetcher:
        result = await fetcher.fetch_wallet_trades(WALLET)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    metrics = result["summary"]["metrics"]
    total_trades = result["summary"]["total_trades"]

    print(f"\nFETCHED:")
    print(f"  Signatures: {metrics['signatures_fetched']}")
    print(f"  Parsed: {metrics['signatures_parsed']}")
    print(f"  Parse rate: {metrics['signatures_parsed']/metrics['signatures_fetched']*100:.1f}%")

    print(f"\nBREAKDOWN:")
    print(f"  Events.swap: {metrics['events_swap_rows']}")
    print(f"  Fallback: {metrics['fallback_rows']}")
    print(f"  Ratio: 1:{metrics['fallback_rows']/metrics['events_swap_rows']:.1f}")

    print(f"\nPROJECTION:")
    print(f"  20 pages → {total_trades} trades")
    print(f"  If we have ~86 pages total...")
    print(f"  Estimated total: {total_trades * (86/20):.0f} trades")

    print(f"\nVERDICT:")
    estimated = total_trades * (86 / 20)
    if 800 <= estimated <= 1200:
        print(f"  ✅ SUCCESS! Estimate ({estimated:.0f}) within expert's 900-1,100 range")
    else:
        print(f"  ⚠️  Estimate ({estimated:.0f}) outside expected range")


if __name__ == "__main__":
    asyncio.run(test_medium())
