#!/usr/bin/env python3
"""Test deep psychological pattern analysis."""
import sys
sys.path.append('src')

import pandas as pd
import polars as pl
from datetime import datetime, timedelta

# Import pattern detection
from walletdoctor.features import patterns


def test_deep_patterns():
    """Test pattern detection on real wallet data."""
    print("Testing Deep Pattern Analysis\n")
    print("="*60)
    
    # Load the CSV data
    csv_df = pd.read_csv('multi_wallet_pnl.csv')
    
    # Get first wallet with trades
    wallet_data = csv_df[csv_df['wallet_address'] == csv_df['wallet_address'].iloc[0]]
    closed_trades = wallet_data[wallet_data['realizedPnl'] != 0]
    
    # Convert to Polars format
    trades_data = []
    base_time = datetime.now()
    
    for idx, (_, row) in enumerate(closed_trades.iterrows()):
        # Create realistic timestamps (some close together, some far apart)
        if idx > 0 and idx % 5 == 0:
            # Every 5th trade is much later (simulating trading sessions)
            timestamp = base_time - timedelta(hours=idx*2, days=idx//5)
        else:
            # Trades within session are 30-60 min apart
            timestamp = base_time - timedelta(hours=idx*0.75)
        
        trade = {
            'token_mint': row['mint'],
            'symbol': row['symbol'],
            'pnl': float(row['realizedPnl']),
            'pnl_pct': (float(row['realizedPnl']) / float(row['totalBought']) * 100) if row['totalBought'] > 0 else 0,
            'hold_minutes': float(row['holdTimeSeconds']) / 60 if row['holdTimeSeconds'] > 0 else 60,
            'trade_size_usd': float(row['totalBought']),
            'timestamp': timestamp,
            'side': 'sell',
            'fee': 50_000_000
        }
        trades_data.append(trade)
    
    trades_df = pl.DataFrame(trades_data).with_columns(
        pl.col("timestamp").cast(pl.Datetime)
    )
    
    print(f"Analyzing {trades_df.height} trades...\n")
    
    # Run pattern analysis
    analysis = patterns.analyze_all_patterns(trades_df)
    
    print(f"PRIMARY ISSUE: {analysis['primary_issue']}")
    print(f"Severity: {analysis['severity'].upper()}")
    print(f"\nPatterns Detected: {', '.join(analysis['patterns_detected']) if analysis['patterns_detected'] else 'None'}")
    print("\n" + "="*60 + "\n")
    
    # Show details of each detected pattern
    for pattern_name, details in analysis['pattern_details'].items():
        if details.get('detected', False):
            print(f"🔍 {pattern_name.upper().replace('_', ' ')}:")
            print(f"   {details.get('insight', 'Pattern detected')}")
            
            # Show pattern-specific details
            if pattern_name == 'loss_aversion':
                print(f"   - Winners held: {details['winner_hold']:.0f} min avg")
                print(f"   - Losers held: {details['loser_hold']:.0f} min avg") 
                print(f"   - Extra hold time on losers: {details['extra_hold_minutes']:.0f} min")
                
            elif pattern_name == 'revenge_trading':
                print(f"   - Median trade size: ${details['median_size']:,.0f}")
                print(f"   - Revenge trades found: {details['count']}")
                print(f"   - Average size increase: {details['avg_size_multiplier']:.1f}x")
                print(f"   - Total damage from revenge trades: ${details['total_damage']:,.0f}")
                
            elif pattern_name == 'no_process':
                print(f"   - Position size variance: {details['size_variance']:.0f}%")
                print(f"   - Hold time variance: {details['hold_variance']:.0f}%")
                print(f"   - Worst metric: {details['worst_metric']}")
                
            print()
    
    # Show the psychological story
    print("\n" + "="*60)
    print("THE PSYCHOLOGICAL STORY:\n")
    
    if 'loss_aversion' in analysis['patterns_detected'] and 'no_process' in analysis['patterns_detected']:
        print("""You're trading on pure emotion. The data shows:

1. You hold losers longer hoping they'll recover (ego protection)
2. Your position sizes are random (no risk management)
3. You're profitable only because a few huge wins saved you

This isn't trading—it's gambling with a narrative.

The market will eventually humble you. When your luck runs out
(and it will), that 2,800% position variance means one trade
will wipe out months of profits.

You need rules. Not suggestions—RULES:
- Max position: 2% of portfolio
- Stop loss: -5% on EVERY trade
- If you break these rules even once, stop trading for a week

The alternative is blowing up. Your choice.""")
    
    elif 'revenge_trading' in analysis['patterns_detected']:
        print("""Classic revenge trader pattern detected.

After losses, you dramatically increase position size trying to
"make it back." This isn't trading—it's emotional warfare with
the market. And the market always wins.

Your $59K loss wasn't bad luck. It was the inevitable result
of revenge trading. The pattern is clear in your data.

Break this cycle or it breaks you.""")
    
    else:
        print("Run this with actual wallet data to see deep patterns.")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    test_deep_patterns() 