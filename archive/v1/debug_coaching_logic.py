#!/usr/bin/env python3
"""Debug the coaching logic to find the duplication issue"""

import asyncio
from src.services.trading_coach import TradingCoach

async def debug_pattern_matching():
    coach = TradingCoach("7c855165-3874-4237-9416-450d2373ea72")
    
    # Get patterns for 10 SOL
    patterns = await coach._get_similar_patterns(
        "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
        10.0,
        tolerance=0.5
    )
    
    print(f"Total patterns found: {len(patterns)}\n")
    
    # Check for duplicates
    seen = {}
    for i, p in enumerate(patterns[:20]):
        key = f"{p.symbol}_{p.avg_buy_sol:.1f}_{p.roi_percentage:.1f}"
        if key in seen:
            print(f"⚠️ DUPLICATE at index {i}: {p.symbol}")
        else:
            seen[key] = i
            
        print(f"{i}: {p.symbol} - {p.avg_buy_sol:.1f} SOL, {p.roi_percentage:.1f}% ROI")
    
    # Check unique symbols
    all_symbols = [p.symbol for p in patterns]
    unique_symbols = set(all_symbols)
    
    print(f"\n\nTotal patterns: {len(patterns)}")
    print(f"Unique symbols: {len(unique_symbols)}")
    
    # Count occurrences
    from collections import Counter
    symbol_counts = Counter(all_symbols)
    
    print("\nMost repeated symbols:")
    for symbol, count in symbol_counts.most_common(10):
        if count > 1:
            print(f"  {symbol}: appears {count} times")

asyncio.run(debug_pattern_matching())