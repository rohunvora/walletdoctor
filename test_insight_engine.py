#!/usr/bin/env python3
"""Test the new insight engine with mock data."""
import sys
sys.path.append('src')

import polars as pl
from walletdoctor.features import behaviour
from walletdoctor.insights import generate_full_report
from walletdoctor.llm import make_quick_assessment


def test_insight_engine():
    """Test with mock trading data."""
    print("Testing WalletDoctor Insight Engine 2.0\n")
    
    # Create mock trade data
    trades = pl.DataFrame({
        'token_mint': ['TOK1', 'TOK2', 'TOK3', 'TOK4', 'TOK5', 'TOK6', 'TOK7', 'TOK8'],
        'symbol': ['TOK1', 'TOK2', 'TOK3', 'TOK4', 'TOK5', 'TOK6', 'TOK7', 'TOK8'],
        'pnl': [-6000, 2000, -1000, 500, -3000, 1500, -500, 800],
        'pnl_pct': [-60, 40, -20, 10, -30, 30, -10, 16],
        'hold_minutes': [5, 180, 8, 240, 12, 300, 6, 120],  # Mix of quick and patient
        'trade_size_usd': [10000, 5000, 5000, 5000, 10000, 5000, 5000, 5000],
        'timestamp': pl.datetime_range(
            start=pl.datetime(2024, 1, 1),
            end=pl.datetime(2024, 1, 8),
            interval='1d',
            eager=True
        ),
        'side': ['sell'] * 8,
        'fee': [50_000_000] * 8  # 0.05 SOL per trade in lamports
    })
    
    # Compute metrics
    print("1. Computing behavioral metrics:")
    metrics = {
        'fee_burn': behaviour.fee_burn(trades),
        'win_rate': behaviour.win_rate(trades),
        'profit_factor': behaviour.profit_factor(trades),
        'largest_loss': behaviour.largest_loss(trades),
        'premature_exits': behaviour.premature_exits(trades),
        'avg_winner_hold_time': behaviour.avg_winner_hold_time(trades),
        'avg_loser_hold_time': behaviour.avg_loser_hold_time(trades),
        'overtrading_score': behaviour.overtrading_score(trades),
        'position_sizing_variance': behaviour.position_sizing_variance(trades),
        'total_pnl': float(trades['pnl'].sum()),
        'trade_count': trades.height
    }
    
    for name, value in metrics.items():
        print(f"  {name}: {value:.2f}")
    
    # Generate insights
    print("\n2. Generating insights:")
    report = generate_full_report(metrics, max_insights=5)
    
    print(f"\nHeader: {report['header']}")
    print("\nTop insights:")
    if report['insights']:
        for i, insight in enumerate(report['insights'], 1):
            print(f"  {i}. {insight}")
    else:
        print("  No significant insights triggered (all metrics within normal ranges)")
    
    # Show metadata
    print(f"\nMetadata: {report['metadata']}")
    
    # Quick assessment (no LLM needed)
    print(f"\n3. Quick assessment:")
    assessment = make_quick_assessment(metrics)
    print(f"  {assessment}")
    
    print("\n✓ Insight engine test complete!")
    print("\nNote: To test full narrative generation, you'll need an OpenAI API key.")


if __name__ == "__main__":
    test_insight_engine() 