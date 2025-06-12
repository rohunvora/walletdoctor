#!/usr/bin/env python3
"""Test the new insight engine with CSV data."""
import sys
sys.path.append('src')

import pandas as pd
import polars as pl
from datetime import datetime, timedelta

# Import new insight engine
from walletdoctor.features import behaviour
from walletdoctor.insights import generate_full_report
from walletdoctor.llm import make_quick_assessment


def test_with_csv():
    """Test the insight engine with CSV data."""
    print("Testing WalletDoctor Insight Engine with CSV data\n")
    
    try:
        # Load CSV data
        print("1. Loading CSV data...")
        csv_df = pd.read_csv('multi_wallet_pnl.csv')
        print(f"   ✓ Loaded {len(csv_df)} rows")
        
        # Convert to format expected by features
        print("\n2. Converting data for analysis...")
        
        # Create trades data based on CSV structure
        trades_data = []
        
        # Group by wallet
        if 'wallet_address' in csv_df.columns:
            # Get unique wallets
            unique_wallets = csv_df['wallet_address'].unique()
            print(f"   Found {len(unique_wallets)} unique wallets")
            
            # Test with first wallet that has realized PnL
            for wallet in unique_wallets:
                wallet_data = csv_df[csv_df['wallet_address'] == wallet]
                # Check if this wallet has any closed trades
                closed_trades = wallet_data[wallet_data['realizedPnl'] != 0]
                if len(closed_trades) > 0:
                    print(f"\n   Analyzing wallet: {wallet[:8]}...{wallet[-8:]}")
                    wallet_data = closed_trades
                    break
        else:
            wallet_data = csv_df[csv_df['realizedPnl'] != 0]
        
        # Convert each row to trade format
        base_time = datetime.now()
        for idx, (_, row) in enumerate(wallet_data.iterrows()):
            # Create timestamps spaced 1 hour apart
            timestamp = base_time - timedelta(hours=idx)
            
            trade = {
                'token_mint': row['mint'],
                'symbol': row['symbol'],
                'pnl': float(row['realizedPnl']),
                'pnl_pct': (float(row['realizedPnl']) / float(row['totalBought']) * 100) if row['totalBought'] > 0 else 0,
                'hold_minutes': float(row['holdTimeSeconds']) / 60 if row['holdTimeSeconds'] > 0 else 60,
                'trade_size_usd': float(row['totalBought']),
                'timestamp': timestamp,
                'side': 'sell',
                'fee': 50_000_000  # 0.05 SOL default
            }
            trades_data.append(trade)
        
        if not trades_data:
            print("\n❌ No closed trades found in data")
            return
        
        # Create Polars DataFrame with proper datetime type
        trades_df = pl.DataFrame(trades_data)
        # Ensure timestamp is datetime type
        trades_df = trades_df.with_columns(
            pl.col("timestamp").cast(pl.Datetime)
        )
        print(f"   ✓ Analyzing {trades_df.height} trades")
        
        # Compute metrics (skip overtrading score for now since it needs timestamps)
        print("\n3. Computing behavioral metrics:")
        metrics = {
            'fee_burn': behaviour.fee_burn(trades_df),
            'win_rate': behaviour.win_rate(trades_df),
            'profit_factor': behaviour.profit_factor(trades_df),
            'largest_loss': behaviour.largest_loss(trades_df),
            'avg_winner_hold_time': behaviour.avg_winner_hold_time(trades_df),
            'avg_loser_hold_time': behaviour.avg_loser_hold_time(trades_df),
            'position_sizing_variance': behaviour.position_sizing_variance(trades_df),
            'total_pnl': float(trades_df['pnl'].sum()),
            'trade_count': trades_df.height
        }
        
        # Try to add overtrading score if timestamps work
        try:
            metrics['overtrading_score'] = behaviour.overtrading_score(trades_df)
        except:
            metrics['overtrading_score'] = 0.0  # Default if timestamps don't work
        
        # Display metrics
        for name, value in metrics.items():
            if name in ['fee_burn', 'total_pnl', 'largest_loss']:
                print(f"   {name}: ${value:,.2f}")
            elif name.endswith('_pct') or name.endswith('rate'):
                print(f"   {name}: {value:.1f}%")
            else:
                print(f"   {name}: {value:.2f}")
        
        # Generate insights
        print("\n4. Generating insights:")
        report = generate_full_report(metrics, max_insights=5)
        
        print(f"\n{report['header']}")
        print("\n" + "="*60 + "\n")
        
        if report['insights']:
            print("Top insights:\n")
            for i, insight in enumerate(report['insights'], 1):
                print(f"{i}. {insight}\n")
        else:
            print("No significant behavioral patterns detected.\n")
        
        # Quick assessment
        assessment = make_quick_assessment(metrics)
        print(f"Quick assessment: {assessment}")
        
        # Show trade distribution
        print("\n5. Trade analysis:")
        winners = trades_df.filter(pl.col('pnl') > 0)
        losers = trades_df.filter(pl.col('pnl') < 0)
        print(f"   Winners: {winners.height} trades (${winners['pnl'].sum():,.2f} total)")
        print(f"   Losers: {losers.height} trades (${losers['pnl'].sum():,.2f} total)")
        
        # Show top trades
        print("\n   Top 3 wins:")
        top_wins = trades_df.sort('pnl', descending=True).head(3)
        for row in top_wins.iter_rows(named=True):
            print(f"     {row['symbol']}: +${row['pnl']:,.2f} ({row['hold_minutes']:.0f} min)")
        
        print("\n   Top 3 losses:")
        top_losses = trades_df.sort('pnl').head(3)
        for row in top_losses.iter_rows(named=True):
            print(f"     {row['symbol']}: ${row['pnl']:,.2f} ({row['hold_minutes']:.0f} min)")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_with_csv() 