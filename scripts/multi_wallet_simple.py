#!/usr/bin/env python3
"""
Simplified multi-wallet loader focusing on PnL data
"""

import os
import sys
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
import duckdb
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from data import fetch_cielo_pnl
from transforms import normalize_cielo_pnl

console = Console()

def load_wallet_pnl(address: str):
    """Load a single wallet's PnL data."""
    try:
        pnl_data = fetch_cielo_pnl(address)
        if pnl_data and 'data' in pnl_data and 'items' in pnl_data.get('data', {}):
            tokens = pnl_data['data']['items']
            if tokens and len(tokens) > 0:
                pnl_df = normalize_cielo_pnl({'tokens': tokens})
                pnl_df['wallet_address'] = address
                return pnl_df
    except Exception as e:
        console.print(f"[red]Error loading {address[:8]}...: {str(e)}[/]")
    return None

def main():
    """Load multiple wallets and generate aggregate statistics."""
    
    wallets = [
        "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
        "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
        "GbVsVFh1rr9xKY2AWhHyDVV6Q36QBEaX5qPk2CQMVEXF",
        "GomBJCQXmQErreHqVcypujPFbZb9MiVeuGoEJFTZhRjR",
        "C7muvNN25ubGSnVxjav7UauSsKFZd5Qqh1d7sG1DFVsZ",
        "DSBMJFoeqJUz13HK8VntxEPqLahk4DAPpYqqie8TBLsM",
        "3VC3noVT5VAvMsFx8sbFHhD4Cm6L97j84XHzwMaJMbzW",
        "4ja8NtZL5FuMkk2P4N5gj5UvXDWiqFDrBQxhPPSPa1B1"
    ]
    
    console.print("\n[bold cyan]🩺 Tradebro Multi-Wallet Analysis[/]\n")
    console.print(f"Loading PnL data for {len(wallets)} wallets...")
    
    # Collect all PnL data
    all_pnl_data = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        for wallet in wallets:
            task_id = progress.add_task(f"Loading {wallet[:8]}...", total=1)
            pnl_df = load_wallet_pnl(wallet)
            if pnl_df is not None:
                all_pnl_data.append(pnl_df)
                progress.update(task_id, description=f"✓ {wallet[:8]}... ({len(pnl_df)} tokens)")
            else:
                progress.update(task_id, description=f"✗ {wallet[:8]}... (no data)")
    
    if not all_pnl_data:
        console.print("[red]No data loaded. Please check API keys and wallet addresses.[/]")
        return
    
    # Combine all PnL data
    combined_df = pd.concat(all_pnl_data, ignore_index=True)
    console.print(f"\n✓ Total tokens across all wallets: {len(combined_df)}")
    
    # Overall statistics
    console.print("\n[bold cyan]📊 Aggregate Portfolio Statistics[/]\n")
    
    total_realized = combined_df['realizedPnl'].sum()
    total_unrealized = combined_df['unrealizedPnl'].sum()
    total_positions = len(combined_df)
    winning_positions = len(combined_df[combined_df['realizedPnl'] > 0])
    losing_positions = len(combined_df[combined_df['realizedPnl'] <= 0])
    win_rate = (winning_positions / total_positions * 100) if total_positions > 0 else 0
    
    # Calculate median hold time safely
    hold_times = combined_df['holdTimeSeconds'].dropna()
    median_hold = hold_times.median() / 60 if len(hold_times) > 0 else 0
    
    # Display overall summary
    table = Table(title="Overall Portfolio Performance")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Active Wallets", str(len(wallets)))
    table.add_row("Total Positions", str(total_positions))
    table.add_row("Win Rate", f"{win_rate:.2f}%")
    table.add_row("Winning Positions", str(winning_positions))
    table.add_row("Losing Positions", str(losing_positions))
    table.add_row("Total Realized PnL", f"${total_realized:,.2f}")
    table.add_row("Total Unrealized PnL", f"${total_unrealized:,.2f}")
    table.add_row("Net PnL", f"${(total_realized + total_unrealized):,.2f}")
    table.add_row("Median Hold Time", f"{median_hold:.1f} minutes")
    
    console.print(table)
    
    # Per-wallet breakdown
    console.print("\n[bold cyan]💼 Per-Wallet Breakdown[/]\n")
    
    wallet_stats = combined_df.groupby('wallet_address').agg({
        'realizedPnl': ['sum', 'count'],
        'unrealizedPnl': 'sum'
    }).round(2)
    
    wallet_table = Table(title="Individual Wallet Performance")
    wallet_table.add_column("Wallet", style="cyan")
    wallet_table.add_column("Positions", style="white")
    wallet_table.add_column("Realized PnL", style="green")
    wallet_table.add_column("Unrealized PnL", style="yellow")
    wallet_table.add_column("Total PnL", style="bold")
    
    for wallet in wallet_stats.index:
        realized = wallet_stats.loc[wallet, ('realizedPnl', 'sum')]
        positions = int(wallet_stats.loc[wallet, ('realizedPnl', 'count')])
        unrealized = wallet_stats.loc[wallet, ('unrealizedPnl', 'sum')]
        total_pnl = realized + unrealized
        
        # Color code based on profitability
        pnl_color = "green" if realized > 0 else "red"
        total_color = "green" if total_pnl > 0 else "red"
        
        wallet_table.add_row(
            f"{wallet[:8]}...",
            str(positions),
            f"[{pnl_color}]${realized:,.0f}[/]",
            f"${unrealized:,.0f}",
            f"[{total_color}]${total_pnl:,.0f}[/]"
        )
    
    console.print(wallet_table)
    
    # Top performers across all wallets
    console.print("\n[bold cyan]🚀 Top 10 Performers Across All Wallets[/]\n")
    top_performers = combined_df.nlargest(10, 'realizedPnl')[['wallet_address', 'symbol', 'realizedPnl']]
    for _, row in top_performers.iterrows():
        console.print(f"  {row['symbol']} ({row['wallet_address'][:8]}...): ${row['realizedPnl']:,.2f}")
    
    # Biggest losers across all wallets
    console.print("\n[bold red]📉 Biggest 10 Losses Across All Wallets[/]\n")
    biggest_losers = combined_df[combined_df['realizedPnl'] < 0].nsmallest(10, 'realizedPnl')[['wallet_address', 'symbol', 'realizedPnl']]
    for _, row in biggest_losers.iterrows():
        console.print(f"  {row['symbol']} ({row['wallet_address'][:8]}...): ${row['realizedPnl']:,.2f}")
    
    # Save combined data
    combined_df.to_csv('multi_wallet_pnl.csv', index=False)
    console.print("\n✓ Data saved to multi_wallet_pnl.csv")

if __name__ == "__main__":
    main() 