#!/usr/bin/env python3
"""Test the new insight engine with a real wallet."""
import os
import sys
sys.path.append('src')

import pandas as pd
import polars as pl
import duckdb
from typing import Dict, Any

# Import existing modules
from data import fetch_helius_transactions, fetch_cielo_pnl
from transforms import normalize_helius_transactions, normalize_cielo_pnl

# Import new insight engine
from walletdoctor.features import behaviour
from walletdoctor.insights import generate_full_report, calculate_extras
from walletdoctor.llm import make_messages, make_quick_assessment, format_for_cli

# Set demo API keys (you'll need to replace these with real ones)
os.environ['HELIUS_KEY'] = os.environ.get('HELIUS_KEY', 'demo-key')
os.environ['CIELO_KEY'] = os.environ.get('CIELO_KEY', 'demo-key')


def convert_real_data_to_polars(pnl_df: pd.DataFrame, tx_df: pd.DataFrame) -> pl.DataFrame:
    """Convert real wallet data to format expected by new features."""
    trades_data = []
    
    # Convert PnL data
    for _, row in pnl_df.iterrows():
        if row.get('realizedPnl', 0) != 0:  # Only closed trades
            trade = {
                'token_mint': row.get('mint', ''),
                'symbol': row.get('symbol', ''),
                'pnl': row.get('realizedPnl', 0),
                'pnl_pct': (row.get('realizedPnl', 0) / row.get('totalBought', 1) * 100) if row.get('totalBought', 0) > 0 else 0,
                'hold_minutes': row.get('holdTimeSeconds', 0) / 60 if row.get('holdTimeSeconds') else 0,
                'trade_size_usd': row.get('totalBought', 0),
                'timestamp': pd.Timestamp.now(),  # Would need actual timestamps from tx data
                'side': 'sell',
                'fee': 0  # Will be updated from tx data
            }
            trades_data.append(trade)
    
    if not trades_data:
        print("No closed trades found in PnL data")
        return pl.DataFrame()
    
    # Create initial DataFrame
    trades_df = pl.DataFrame(trades_data)
    
    # Add fee data from transactions if available
    if not tx_df.empty and 'fee' in tx_df.columns:
        total_fees = tx_df['fee'].sum()
        # Distribute fees proportionally across trades (simplified approach)
        if len(trades_data) > 0:
            fee_per_trade = total_fees / len(trades_data)
            trades_df = trades_df.with_columns(
                pl.lit(fee_per_trade).alias('fee')
            )
    
    return trades_df


def test_wallet(wallet_address: str):
    """Test the new insight engine with a real wallet."""
    print(f"Testing WalletDoctor Insight Engine on wallet: {wallet_address[:8]}...{wallet_address[-8:]}\n")
    
    try:
        # Fetch data
        print("1. Fetching wallet data...")
        
        # Fetch transactions
        tx_data = fetch_helius_transactions(wallet_address, limit=100)
        if tx_data:
            print(f"   ✓ Found {len(tx_data)} transactions")
            tx_df = normalize_helius_transactions(tx_data)
        else:
            print("   ⚠ No transaction data available")
            tx_df = pd.DataFrame()
        
        # Fetch PnL
        pnl_data = fetch_cielo_pnl(wallet_address)
        if pnl_data and 'data' in pnl_data and 'items' in pnl_data.get('data', {}):
            tokens = pnl_data['data']['items']
            print(f"   ✓ Found PnL data for {len(tokens)} tokens")
            pnl_df = normalize_cielo_pnl({'tokens': tokens})
        else:
            print("   ⚠ No PnL data available")
            pnl_df = pd.DataFrame()
        
        if pnl_df.empty:
            print("\n❌ No trading data found for this wallet")
            return
        
        # Convert to Polars format
        print("\n2. Converting data for analysis...")
        trades_df = convert_real_data_to_polars(pnl_df, tx_df)
        
        if trades_df.is_empty():
            print("   ⚠ No closed trades to analyze")
            return
        
        print(f"   ✓ Analyzing {trades_df.height} trades")
        
        # Compute metrics
        print("\n3. Computing behavioral metrics:")
        metrics = {}
        
        # Safe metric computation with error handling
        try:
            metrics['fee_burn'] = behaviour.fee_burn(trades_df)
            metrics['win_rate'] = behaviour.win_rate(trades_df)
            metrics['profit_factor'] = behaviour.profit_factor(trades_df)
            metrics['largest_loss'] = behaviour.largest_loss(trades_df)
            metrics['avg_winner_hold_time'] = behaviour.avg_winner_hold_time(trades_df)
            metrics['avg_loser_hold_time'] = behaviour.avg_loser_hold_time(trades_df)
            metrics['overtrading_score'] = behaviour.overtrading_score(trades_df)
            metrics['position_sizing_variance'] = behaviour.position_sizing_variance(trades_df)
            
            # Add summary metrics
            metrics['total_pnl'] = float(trades_df['pnl'].sum())
            metrics['trade_count'] = trades_df.height
            
            # Display metrics
            for name, value in metrics.items():
                if name in ['fee_burn', 'total_pnl', 'largest_loss']:
                    print(f"   {name}: ${value:.2f}")
                elif name.endswith('_pct') or name.endswith('rate'):
                    print(f"   {name}: {value:.1f}%")
                else:
                    print(f"   {name}: {value:.2f}")
        
        except Exception as e:
            print(f"   ⚠ Error computing metrics: {e}")
            return
        
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
        print(f"\nQuick assessment: {assessment}")
        
        # Show some raw data for context
        print("\n5. Sample trades analyzed:")
        sample_df = trades_df.head(5)
        for row in sample_df.iter_rows(named=True):
            pnl_str = f"+${row['pnl']:.2f}" if row['pnl'] > 0 else f"-${abs(row['pnl']):.2f}"
            print(f"   {row['symbol']}: {pnl_str} ({row['hold_minutes']:.1f} min hold)")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Test with the provided wallet
    wallet = "CRVidEDtEUTYZisCxBZkpELzhQc9eauMLR3FWg74tReL"
    
    print("Note: This test requires valid API keys.")
    print("Set HELIUS_KEY and CIELO_KEY environment variables.\n")
    
    test_wallet(wallet) 