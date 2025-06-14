#!/usr/bin/env python3
"""
Example usage of the Wallet Doctor trading coach.

This script demonstrates programmatic usage beyond the CLI.
"""

import os
import duckdb
from data import fetch_helius_transactions, fetch_cielo_pnl
from transforms import normalize_helius_transactions, normalize_cielo_pnl, calculate_hold_durations
from analytics import (
    calculate_win_rate,
    analyze_hold_patterns,
    identify_leak_trades,
    calculate_portfolio_metrics
)
from llm import TradingCoach, get_quick_insight

def analyze_wallet(wallet_address: str):
    """Complete analysis workflow for a single wallet."""
    
    print(f"🔍 Analyzing wallet: {wallet_address}\n")
    
    # 1. Fetch data
    print("📡 Fetching data...")
    try:
        tx_data = fetch_helius_transactions(wallet_address, limit=100)
        pnl_data = fetch_cielo_pnl(wallet_address)
        print(f"  ✓ Found {len(tx_data)} transactions")
        print(f"  ✓ Found PnL for {len(pnl_data.get('tokens', []))} tokens\n")
    except Exception as e:
        print(f"  ✗ Error fetching data: {e}")
        return
    
    # 2. Transform data
    print("🔄 Processing data...")
    tx_df = normalize_helius_transactions(tx_data)
    pnl_df = normalize_cielo_pnl(pnl_data)
    hold_durations = calculate_hold_durations(tx_df)
    
    # 3. Calculate metrics
    print("📊 Calculating metrics...\n")
    
    # Win rate
    win_metrics = calculate_win_rate(pnl_df)
    print("💰 Win Rate Analysis:")
    print(f"  - Win Rate: {win_metrics['win_rate']:.1%}")
    print(f"  - Total Trades: {win_metrics['total_trades']}")
    print(f"  - Profit Factor: {win_metrics['profit_factor']:.2f}\n")
    
    # Hold patterns
    hold_patterns = analyze_hold_patterns(hold_durations)
    print("⏱️  Hold Patterns:")
    print(f"  - Average Hold: {hold_patterns['avg_hold_hours']:.1f} hours")
    print(f"  - Quick Flips: {hold_patterns['quick_flips_ratio']:.1%}")
    print(f"  - Hold Distribution:")
    for bucket, count in hold_patterns['hold_buckets'].items():
        print(f"    {bucket}: {count} trades")
    print()
    
    # Portfolio metrics
    portfolio = calculate_portfolio_metrics(pnl_df, tx_df)
    print("📈 Portfolio Summary:")
    print(f"  - Total Realized PnL: {portfolio['total_realized_pnl']:.2f} SOL")
    print(f"  - Total Unrealized PnL: {portfolio['total_unrealized_pnl']:.2f} SOL")
    print(f"  - Active Positions: {portfolio['active_positions']}\n")
    
    # Leak trades
    leak_trades = identify_leak_trades(pnl_df, threshold_sol=-50)
    if not leak_trades.empty:
        print("🚨 Major Losses (>50 SOL):")
        for _, trade in leak_trades.head(3).iterrows():
            print(f"  - {trade.get('symbol', 'Unknown')}: {trade['realizedPnl']:.2f} SOL")
        print()
    
    # 4. Get AI insights
    print("🤖 AI Coach Analysis:\n")
    
    coach = TradingCoach()
    metrics = {
        'win_rate': win_metrics,
        'hold_patterns': hold_patterns,
        'portfolio': portfolio
    }
    
    # Get quick insight
    quick_insight = get_quick_insight(metrics)
    print(f"Quick Insight: {quick_insight}\n")
    
    # Get detailed analysis
    analysis = coach.analyze_wallet(
        "What are the top 3 things I should focus on to improve my trading?",
        metrics
    )
    print("Detailed Analysis:")
    print(analysis)
    print()
    
    # Get suggestions
    suggestions = coach.suggest_improvements(
        metrics,
        leak_trades.to_dict('records') if not leak_trades.empty else None
    )
    if suggestions:
        print("\n📝 Specific Suggestions:")
        for suggestion in suggestions:
            print(f"  {suggestion}")

def compare_wallets(wallet1: str, wallet2: str):
    """Compare performance between two wallets."""
    print(f"📊 Comparing wallets:\n  - Wallet 1: {wallet1}\n  - Wallet 2: {wallet2}\n")
    
    # This is a simplified comparison - you'd implement full logic here
    for i, wallet in enumerate([wallet1, wallet2], 1):
        print(f"\n--- Wallet {i} ---")
        try:
            pnl_data = fetch_cielo_pnl(wallet)
            pnl_df = normalize_cielo_pnl(pnl_data)
            win_metrics = calculate_win_rate(pnl_df)
            
            print(f"Win Rate: {win_metrics['win_rate']:.1%}")
            print(f"Profit Factor: {win_metrics['profit_factor']:.2f}")
            print(f"Avg Win: {win_metrics['avg_win']:.2f} SOL")
            print(f"Avg Loss: {win_metrics['avg_loss']:.2f} SOL")
        except Exception as e:
            print(f"Error: {e}")

def run_sql_analysis():
    """Example of direct SQL analysis on cached data."""
    print("🗄️  SQL Analysis Example\n")
    
    db = duckdb.connect("coach.db")
    
    # Top traded tokens
    print("Top 5 Most Traded Tokens:")
    result = db.execute("""
        SELECT 
            token_mint,
            COUNT(*) as trade_count,
            SUM(ABS(token_amount)) as total_volume
        FROM tx
        WHERE token_mint IS NOT NULL
        GROUP BY token_mint
        ORDER BY trade_count DESC
        LIMIT 5
    """).fetchall()
    
    for mint, count, volume in result:
        print(f"  - {mint[:8]}...: {count} trades, {volume:.2f} tokens")
    
    db.close()

if __name__ == "__main__":
    # Example wallet address (replace with actual)
    EXAMPLE_WALLET = "YourWalletAddressHere"
    
    # Make sure API keys are set
    if not all([os.environ.get("HELIUS_KEY"), 
                os.environ.get("CIELO_KEY"), 
                os.environ.get("OPENAI_KEY")]):
        print("⚠️  Please set HELIUS_KEY, CIELO_KEY, and OPENAI_KEY environment variables")
        exit(1)
    
    # Run analysis
    analyze_wallet(EXAMPLE_WALLET)
    
    # Uncomment to compare wallets
    # compare_wallets(WALLET1, WALLET2)
    
    # Uncomment to run SQL analysis (requires data in coach.db)
    # run_sql_analysis() 