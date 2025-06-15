#!/usr/bin/env python3
"""Quick test to check if a wallet has trading data"""

import os
import sys
import duckdb
from datetime import datetime

# Environment variables should be set before running

# Add scripts to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

from data import fetch_cielo_pnl_smart, load_wallet
from analytics import get_wallet_stats_smart, get_top_performers_from_limited_data
from transforms import normalize_cielo_pnl

def test_wallet(address):
    print(f"Testing wallet: {address[:8]}...{address[-8:]}")
    
    # Check if API keys are available
    helius_key = os.getenv("HELIUS_KEY", "")
    cielo_key = os.getenv("CIELO_KEY", "")
    
    print(f"HELIUS_KEY: {'✓' if helius_key else '❌'}")
    print(f"CIELO_KEY: {'✓' if cielo_key else '❌'}")
    
    if not helius_key or not cielo_key:
        print("\n❌ Please set HELIUS_KEY and CIELO_KEY environment variables")
        return
    
    print()
    
    # Create a temporary database
    db = duckdb.connect(':memory:')

    # Create tables
    db.execute("""
        CREATE TABLE IF NOT EXISTS pnl (
            mint TEXT,
            symbol TEXT,
            realizedPnl DOUBLE,
            unrealizedPnl DOUBLE,
            totalPnl DOUBLE,
            avgBuyPrice DOUBLE,
            avgSellPrice DOUBLE,
            quantity DOUBLE,
            totalBought DOUBLE,
            totalSold DOUBLE,
            holdTimeSeconds BIGINT,
            numSwaps INTEGER
        )
    """)

    # Use smart fetch
    print("\nUsing smart fetch approach...")
    trading_stats, aggregated_pnl, token_pnl = fetch_cielo_pnl_smart(address, mode='instant')

    # Show trading stats if available
    if trading_stats.get('status') == 'ok' and 'data' in trading_stats:
        stats = trading_stats['data']
        print(f"\n📊 Trading Stats API Response:")
        print(f"  Raw data keys: {list(stats.keys())}")
        print(f"  Total Trades: {stats.get('totalTrades', 0):,}")
        print(f"  Win Rate: {stats.get('winRate', 0)*100:.1f}%")
        print(f"  Total PnL: ${stats.get('totalPnl', 0):,.2f}")
        print(f"  ROI: {stats.get('roi', 0)*100:.1f}%")
    else:
        print(f"\n❌ Trading Stats API failed: {trading_stats.get('status', 'unknown')}")

    # Store trading stats if available
    if trading_stats.get('status') == 'ok' and 'data' in trading_stats:
        stats = trading_stats['data']
        # Store in trading_stats table
        db.execute("""
            CREATE TABLE IF NOT EXISTS trading_stats (
                wallet_address TEXT,
                total_trades INTEGER,
                win_rate DOUBLE,
                total_pnl DOUBLE,
                realized_pnl DOUBLE,
                unrealized_pnl DOUBLE,
                roi DOUBLE,
                avg_trade_size DOUBLE,
                largest_win DOUBLE,
                largest_loss DOUBLE,
                data_timestamp TIMESTAMP
            )
        """)
        
        db.execute("""
            INSERT INTO trading_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            address,
            stats.get('totalTrades', 0),
            stats.get('winRate', 0),
            stats.get('totalPnl', 0),
            stats.get('realizedPnl', 0),
            stats.get('unrealizedPnl', 0),
            stats.get('roi', 0),
            stats.get('avgTradeSize', 0),
            stats.get('largestWin', 0),
            stats.get('largestLoss', 0),
            datetime.now()
        ])

    # Show aggregated PnL if available
    if aggregated_pnl.get('status') == 'ok' and 'data' in aggregated_pnl:
        agg_data = aggregated_pnl['data']
        print(f"\n📊 Aggregated PnL API Response:")
        print(f"  Raw data keys: {list(agg_data.keys())}")
        for key, value in agg_data.items():
            if isinstance(value, (int, float)):
                print(f"  {key}: ${value:,.2f}" if 'pnl' in key.lower() else f"  {key}: {value}")
            else:
                print(f"  {key}: {value}")
                
        # Store aggregated stats - this has the best data!
        db.execute("""
            CREATE TABLE IF NOT EXISTS aggregated_stats (
                wallet_address TEXT,
                tokens_traded INTEGER,
                win_rate DOUBLE,
                realized_pnl DOUBLE,
                unrealized_pnl DOUBLE,
                combined_pnl DOUBLE,
                realized_roi DOUBLE,
                unrealized_roi DOUBLE,
                combined_roi DOUBLE,
                total_buy_usd DOUBLE,
                total_sell_usd DOUBLE,
                avg_holding_time_seconds BIGINT,
                data_timestamp TIMESTAMP
            )
        """)
        
        db.execute("""
            INSERT INTO aggregated_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            address,
            agg_data.get('tokens_traded', 0),
            agg_data.get('winrate', 0) / 100.0,  # Convert percentage to decimal
            agg_data.get('realized_pnl_usd', 0),
            agg_data.get('unrealized_pnl_usd', 0),
            agg_data.get('combined_pnl_usd', 0),
            agg_data.get('realized_roi_percentage', 0) / 100.0,
            agg_data.get('unrealized_roi_percentage', 0) / 100.0,
            agg_data.get('combined_roi_percentage', 0) / 100.0,
            agg_data.get('total_buy_usd', 0),
            agg_data.get('total_sell_usd', 0),
            agg_data.get('average_holding_time_seconds', 0),
            datetime.now()
        ])
        print(f"\n✅ Stored aggregated stats in database")

    # Show token data
    if token_pnl.get('status') == 'ok' and 'data' in token_pnl:
        items = token_pnl['data']['items']
        is_limited = token_pnl['data'].get('is_limited', False)
        
        print(f"\n📈 Token Data:")
        print(f"  Tokens fetched: {len(items)}")
        print(f"  Limited data: {'Yes' if is_limited else 'No'}")
        
        # Calculate summary from token data
        if items:
            total_realized = sum(t.get('realizedPnl', 0) for t in items)
            total_unrealized = sum(t.get('unrealizedPnl', 0) for t in items)
            total_pnl = sum(t.get('totalPnl', 0) for t in items)
            win_count = len([t for t in items if t.get('realizedPnl', 0) > 0])
            
            print(f"\n📊 Summary from Token Data:")
            print(f"  Total Realized PnL: ${total_realized:,.2f}")
            print(f"  Total Unrealized PnL: ${total_unrealized:,.2f}")
            print(f"  Total PnL: ${total_pnl:,.2f}")
            print(f"  Win Rate: {win_count/len(items)*100:.1f}% ({win_count}/{len(items)} tokens)")
        
        if items:
            # Normalize and store
            pnl_df = normalize_cielo_pnl({'tokens': items})
            from data import cache_to_duckdb
            cache_to_duckdb(db, "pnl", pnl_df.to_dict('records'))
            
            # Get top performers
            top_performers = get_top_performers_from_limited_data(pnl_df, top_n=5)
            
            if not top_performers['top_gainers'].empty:
                print(f"\n💰 Top 5 Gainers:")
                for _, token in top_performers['top_gainers'].iterrows():
                    print(f"  {token['symbol']}: ${token['totalPnl']:,.2f}")
            
            if not top_performers['top_losers'].empty:
                print(f"\n💸 Top 5 Losers:")
                for _, token in top_performers['top_losers'].iterrows():
                    print(f"  {token['symbol']}: ${token['totalPnl']:,.2f}")

    # Get smart stats (uses trading_stats if available)
    print("\n" + "=" * 60)
    print("Getting wallet statistics...")

    # Load PnL data
    pnl_df = db.execute("SELECT * FROM pnl").df()
    stats = get_wallet_stats_smart(db, pnl_df)

    print(f"\n📊 Final Statistics:")
    print(f"  Source: {'Trading Stats API' if stats['from_trading_stats'] else 'Calculated from tokens'}")
    print(f"  Limited Data: {'Yes' if stats['is_limited_data'] else 'No'}")
    print(f"  Total Tokens: {stats['total_tokens_traded']:,}")
    print(f"  Win Rate: {stats['win_rate_pct']:.1f}%")
    print(f"  Total PnL: ${stats.get('total_pnl', stats['total_realized_pnl'] + stats['total_unrealized_pnl']):,.2f}")

    db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_wallet.py <wallet_address>")
        sys.exit(1)
    
    test_wallet(sys.argv[1]) 