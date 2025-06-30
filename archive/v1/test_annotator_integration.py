#!/usr/bin/env python3
"""
Test the annotator integration
"""

import asyncio
from diary_api_fixed import get_notable_trades

async def test_annotator():
    # Test wallet
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    print("Testing annotator integration...")
    print(f"Fetching notable trades for wallet: {wallet}")
    
    trades = await get_notable_trades(wallet, days=30, max_trades=7)
    
    if not trades:
        print("No trades found!")
        return
    
    print(f"\nFound {len(trades)} notable trades:")
    print("-" * 80)
    
    for trade in trades:
        print(f"\nTrade #{trade['index']}: {trade['token']}")
        print(f"  Exit Date: {trade['exit_date']}")
        print(f"  Entry: ${trade['entry_usd']:.0f} @ {trade['entry_mcap_formatted']} mcap")
        print(f"  Exit: ${trade['exit_usd']:.0f} @ {trade['exit_mcap_formatted']} mcap")
        print(f"  P&L: {trade['pnl_pct']:.0f}% (${trade['pnl_usd']:.0f})")
        print(f"  Held: {trade['held_days']} days")
        print(f"  Selection Reason: {trade['selection_reason']}")
    
    print("\n✅ Integration test passed!")

if __name__ == "__main__":
    asyncio.run(test_annotator())