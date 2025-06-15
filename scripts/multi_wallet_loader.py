#!/usr/bin/env python3
"""
Multi-wallet loader and analyzer for comprehensive portfolio view
"""

import os
import sys
from typing import List
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
import duckdb
import pandas as pd

# Import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from data import fetch_helius_transactions, fetch_cielo_pnl, cache_to_duckdb
from transforms import normalize_helius_transactions, normalize_cielo_pnl
from analytics import calculate_accurate_stats

console = Console()

def load_wallet(address: str, db, progress, task_id):
    """Load a single wallet's data."""
    progress.update(task_id, description=f"Loading {address[:8]}...")
    
    try:
        # Fetch transactions
        tx_data = fetch_helius_transactions(address, limit=100)
        tx_count = len(tx_data) if tx_data else 0
        
        # Fetch PnL data
        pnl_data = fetch_cielo_pnl(address)
        token_count = 0
        if pnl_data and 'data' in pnl_data and 'items' in pnl_data.get('data', {}):
            tokens = pnl_data['data']['items']
            token_count = len(tokens)
            
            # Add wallet address to each record
            if tx_data and len(tx_data) > 0:
                tx_df = normalize_helius_transactions(tx_data)
                tx_df['wallet_address'] = address
                cache_to_duckdb(db, "tx_multi", tx_df)
            
            if tokens and len(tokens) > 0:
                pnl_df = normalize_cielo_pnl({'tokens': tokens})
                pnl_df['wallet_address'] = address
                cache_to_duckdb(db, "pnl_multi", pnl_df)
        
        progress.update(task_id, description=f"✓ {address[:8]}... ({tx_count} tx, {token_count} tokens)")
        return True, tx_count, token_count
        
    except Exception as e:
        progress.update(task_id, description=f"✗ {address[:8]}... Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, 0, 0

def main():
    """Load multiple wallets and generate aggregate statistics."""
    
    wallets = [
        "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",  # Already analyzed
        "rp8ntGS7P2k3faTvsRSWxQLa3B68DetNbwe1GHLiTUK",  # Already analyzed
        "GbVsVFh1rr9xKY2AWhHyDVV6Q36QBEaX5qPk2CQMVEXF",
        "GomBJCQXmQErreHqVcypujPFbZb9MiVeuGoEJFTZhRjR",
        "C7muvNN25ubGSnVxjav7UauSsKFZd5Qqh1d7sG1DFVsZ",
        "DSBMJFoeqJUz13HK8VntxEPqLahk4DAPpYqqie8TBLsM",
        "3VC3noVT5VAvMsFx8sbFHhD4Cm6L97j84XHzwMaJMbzW",
        "4ja8NtZL5FuMkk2P4N5gj5UvXDWiqFDrBQxhPPSPa1B1"
    ]
    
    console.print("\n[bold cyan]🩺 Tradebro Multi-Wallet Analysis[/]\n")
    console.print(f"Loading data for {len(wallets)} wallets...")
    
    # Initialize database
    db = duckdb.connect('multi_wallet.db')
    
    # Create tables with wallet_address column
    db.execute("""
        CREATE TABLE IF NOT EXISTS tx_multi (
            wallet_address VARCHAR,
            signature VARCHAR,
            timestamp BIGINT,
            fee BIGINT,
            type VARCHAR,
            source VARCHAR,
            slot BIGINT,
            token_mint VARCHAR,
            token_amount DOUBLE,
            native_amount DOUBLE,
            from_address VARCHAR,
            to_address VARCHAR,
            transfer_type VARCHAR
        )
    """)
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS pnl_multi (
            wallet_address VARCHAR,
            mint VARCHAR,
            symbol VARCHAR,
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
    
    # Clear existing data
    db.execute("DELETE FROM tx_multi")
    db.execute("DELETE FROM pnl_multi")
    
    # Load each wallet with progress
    total_tx = 0
    total_tokens = 0
    successful = 0
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        for wallet in wallets:
            task_id = progress.add_task(f"Loading {wallet[:8]}...", total=1)
            success, tx_count, token_count = load_wallet(wallet, db, progress, task_id)
            if success:
                successful += 1
                total_tx += tx_count
                total_tokens += token_count
    
    console.print(f"\n✓ Loaded {successful}/{len(wallets)} wallets successfully")
    console.print(f"  Total transactions: {total_tx}")
    console.print(f"  Total tokens traded: {total_tokens}")
    
    # Generate aggregate statistics
    console.print("\n[bold cyan]📊 Aggregate Portfolio Statistics[/]\n")
    
    # Overall PnL
    overall_stats = db.execute("""
        SELECT 
            COUNT(DISTINCT wallet_address) as num_wallets,
            COUNT(*) as total_positions,
            SUM(realizedPnl) as total_realized_pnl,
            SUM(unrealizedPnl) as total_unrealized_pnl,
            COUNT(CASE WHEN realizedPnl > 0 THEN 1 END) as winning_positions,
            COUNT(CASE WHEN realizedPnl <= 0 THEN 1 END) as losing_positions,
            AVG(holdTimeSeconds / 60.0) as avg_hold_minutes,
            MEDIAN(holdTimeSeconds / 60.0) as median_hold_minutes
        FROM pnl_multi
    """).fetchone()
    
    if not overall_stats or overall_stats[1] == 0:
        console.print("[yellow]No data available for analysis. Check if wallets loaded successfully.[/]")
        db.close()
        return
    
    # Display overall summary
    table = Table(title="Overall Portfolio Performance")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Active Wallets", str(overall_stats[0]))
    table.add_row("Total Positions", str(overall_stats[1]))
    table.add_row("Win Rate", f"{(overall_stats[4] / overall_stats[1] * 100):.2f}%" if overall_stats[1] > 0 else "0%")
    table.add_row("Total Realized PnL", f"${overall_stats[2]:,.2f}" if overall_stats[2] is not None else "$0.00")
    table.add_row("Total Unrealized PnL", f"${overall_stats[3]:,.2f}" if overall_stats[3] is not None else "$0.00")
    table.add_row("Net PnL", f"${(overall_stats[2] + overall_stats[3]):,.2f}" if overall_stats[2] is not None and overall_stats[3] is not None else "$0.00")
    table.add_row("Median Hold Time", f"{overall_stats[7]:.1f} minutes" if overall_stats[7] is not None else "N/A")
    
    console.print(table)
    
    # Per-wallet breakdown
    console.print("\n[bold cyan]💼 Per-Wallet Breakdown[/]\n")
    
    wallet_stats = db.execute("""
        SELECT 
            wallet_address,
            COUNT(*) as positions,
            SUM(realizedPnl) as realized_pnl,
            SUM(unrealizedPnl) as unrealized_pnl,
            COUNT(CASE WHEN realizedPnl > 0 THEN 1 END) as wins,
            MEDIAN(holdTimeSeconds / 60.0) as median_hold_min
        FROM pnl_multi
        GROUP BY wallet_address
        ORDER BY realized_pnl DESC
    """).fetchall()
    
    wallet_table = Table(title="Individual Wallet Performance")
    wallet_table.add_column("Wallet", style="cyan")
    wallet_table.add_column("Positions", style="white")
    wallet_table.add_column("Win Rate", style="white")
    wallet_table.add_column("Realized PnL", style="green")
    wallet_table.add_column("Unrealized PnL", style="yellow")
    wallet_table.add_column("Total PnL", style="bold")
    
    for wallet, positions, realized, unrealized, wins, hold_time in wallet_stats:
        win_rate = (wins / positions * 100) if positions > 0 else 0
        total_pnl = realized + unrealized
        
        # Color code based on profitability
        pnl_color = "green" if realized > 0 else "red"
        total_color = "green" if total_pnl > 0 else "red"
        
        wallet_table.add_row(
            f"{wallet[:8]}...",
            str(positions),
            f"{win_rate:.1f}%",
            f"[{pnl_color}]${realized:,.0f}[/]",
            f"${unrealized:,.0f}",
            f"[{total_color}]${total_pnl:,.0f}[/]"
        )
    
    console.print(wallet_table)
    
    # Save results
    db.close()
    console.print("\n✓ Data saved to multi_wallet.db")

if __name__ == "__main__":
    main() 