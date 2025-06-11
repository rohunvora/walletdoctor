# coach.py
import os, json, typer, duckdb
from prompt_toolkit import PromptSession
from rich import print
from rich.console import Console
from rich.table import Table
from typing import Optional

# Import our modules
from data import fetch_helius_transactions, fetch_cielo_pnl, cache_to_duckdb
from transforms import (
    normalize_helius_transactions, 
    normalize_cielo_pnl,
    calculate_hold_durations
)
from analytics import (
    calculate_win_rate,
    analyze_hold_patterns,
    calculate_slippage_estimate,
    identify_leak_trades,
    calculate_portfolio_metrics,
    generate_trading_insights
)
from llm import TradingCoach, get_quick_insight, ANALYSIS_PROMPTS

app = typer.Typer()
console = Console()
db = duckdb.connect("coach.db")

# Initialize database schema
def init_db():
    """Initialize database tables if they don't exist."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS tx (
            signature VARCHAR,
            timestamp TIMESTAMP,
            fee BIGINT,
            type VARCHAR,
            source VARCHAR,
            slot BIGINT,
            token_mint VARCHAR,
            token_amount DOUBLE,
            native_amount BIGINT,
            from_address VARCHAR,
            to_address VARCHAR,
            transfer_type VARCHAR
        )
    """)
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS pnl (
            mint VARCHAR,
            symbol VARCHAR,
            realizedPnl DOUBLE,
            unrealizedPnl DOUBLE,
            totalPnl DOUBLE,
            avgBuyPrice DOUBLE,
            avgSellPrice DOUBLE,
            quantity DOUBLE,
            totalBought DOUBLE,
            totalSold DOUBLE
        )
    """)

@app.command()
def load(addresses: str, limit: Optional[int] = 500):
    """Load & cache transactions for one or more comma-separated wallets."""
    init_db()
    
    for address in [w.strip() for w in addresses.split(",")]:
        console.print(f"[bold cyan]► Fetching data for {address}...[/]")
        
        try:
            # Fetch transaction history
            with console.status("[bold green]Fetching transactions from Helius..."):
                tx_data = fetch_helius_transactions(address, limit=limit)
                console.print(f"  ✓ Found {len(tx_data)} transactions")
            
            # Normalize and store transactions
            if tx_data:
                tx_df = normalize_helius_transactions(tx_data)
                # Clear existing data for this wallet
                try:
                    db.execute(f"DELETE FROM tx WHERE from_address = '{address}' OR to_address = '{address}'")
                except:
                    pass  # Table might not exist yet
                # Store normalized data
                cache_to_duckdb(db, "tx", tx_df.to_dict('records'))
            
            # Fetch PnL data
            with console.status("[bold green]Fetching PnL from Cielo..."):
                pnl_data = fetch_cielo_pnl(address)
                if pnl_data and 'data' in pnl_data and 'items' in pnl_data.get('data', {}):
                    tokens = pnl_data['data']['items']
                    console.print(f"  ✓ Found PnL for {len(tokens)} tokens")
                    # Pass the tokens list to normalize_cielo_pnl
                    pnl_df = normalize_cielo_pnl({'tokens': tokens})
                    # Clear existing PnL data
                    try:
                        db.execute("DELETE FROM pnl")  # Simple approach - can be improved
                    except:
                        pass
                    # Store PnL data
                    cache_to_duckdb(db, "pnl", pnl_df.to_dict('records'))
            
        except Exception as e:
            console.print(f"[red]  ✗ Error loading {address}: {str(e)}[/]")
    
    console.print("[green]✓ Data cached in coach.db[/]")

@app.command()
def stats():
    """Display wallet statistics from cached data."""
    init_db()
    
    # Load data
    tx_df = db.execute("SELECT * FROM tx").df()
    pnl_df = db.execute("SELECT * FROM pnl").df()
    
    if tx_df.empty and pnl_df.empty:
        console.print("[yellow]No data found. Run 'load' command first.[/]")
        return
    
    # Calculate metrics
    console.print("\n[bold cyan]📊 Wallet Statistics[/]\n")
    
    # Win rate
    win_metrics = calculate_win_rate(pnl_df)
    table = Table(title="Win Rate Analysis")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Win Rate", f"{win_metrics['win_rate']:.1%}")
    table.add_row("Total Trades", str(win_metrics['total_trades']))
    table.add_row("Winning Trades", str(win_metrics['winning_trades']))
    table.add_row("Losing Trades", str(win_metrics['losing_trades']))
    table.add_row("Avg Win", f"${win_metrics['avg_win']:,.2f}")
    table.add_row("Avg Loss", f"${win_metrics['avg_loss']:,.2f}")
    table.add_row("Profit Factor", f"{win_metrics['profit_factor']:.2f}")
    console.print(table)
    
    # Hold patterns
    if not tx_df.empty:
        hold_durations = calculate_hold_durations(tx_df)
        hold_patterns = analyze_hold_patterns(hold_durations)
        
        console.print("\n[bold cyan]⏱️  Hold Pattern Analysis[/]")
        console.print(f"Average hold: {hold_patterns['avg_hold_hours']:.1f} hours")
        console.print(f"Quick flips (<1h): {hold_patterns['quick_flips_ratio']:.1%}")
        
        if 'hold_buckets' in hold_patterns:
            table = Table(title="Hold Duration Distribution")
            table.add_column("Duration", style="cyan")
            table.add_column("Count", style="green")
            for bucket, count in hold_patterns['hold_buckets'].items():
                table.add_row(bucket, str(count))
            console.print(table)
    
    # Portfolio summary
    portfolio_metrics = calculate_portfolio_metrics(pnl_df, tx_df)
    console.print("\n[bold cyan]💰 Portfolio Summary[/]")
    console.print(f"Total Realized PnL: ${portfolio_metrics['total_realized_pnl']:,.2f}")
    console.print(f"Total Unrealized PnL: ${portfolio_metrics['total_unrealized_pnl']:,.2f}")
    console.print(f"Active Positions: {portfolio_metrics['active_positions']}")
    
    # Quick insight
    all_metrics = {
        'win_rate': win_metrics,
        'hold_patterns': hold_patterns if not tx_df.empty else {},
        'portfolio': portfolio_metrics
    }
    insight = get_quick_insight(all_metrics)
    console.print(f"\n[bold yellow]{insight}[/]")

@app.command()
def chat():
    """Open an interactive coaching session."""
    init_db()
    
    # Initialize coach
    coach = TradingCoach()
    session = PromptSession()
    
    console.print("[bold cyan]🎯 Solana Trading Coach[/]")
    console.print("Ask questions about your trading performance. Type 'exit' to quit.\n")
    
    # Show available prompts
    console.print("[dim]Quick prompts:[/]")
    for key, prompt in ANALYSIS_PROMPTS.items():
        console.print(f"  [dim]{key}:[/] {prompt}")
    console.print()
    
    while True:
        try:
            # Get user input
            question = session.prompt("🡢 ")
            
            if question.lower() in {"exit", "quit"}:
                break
            
            # Check for quick prompts
            if question.lower() in ANALYSIS_PROMPTS:
                question = ANALYSIS_PROMPTS[question.lower()]
            
            # Load and analyze data
            with console.status("[bold green]Analyzing..."):
                # Load data
                tx_df = db.execute("SELECT * FROM tx").df()
                pnl_df = db.execute("SELECT * FROM pnl").df()
                
                # Calculate all metrics
                metrics = {}
                
                if not pnl_df.empty:
                    metrics['win_rate'] = calculate_win_rate(pnl_df)
                    metrics['portfolio'] = calculate_portfolio_metrics(pnl_df, tx_df)
                    
                    # Identify leak trades
                    leak_trades = identify_leak_trades(pnl_df)
                    if not leak_trades.empty:
                        metrics['leak_trades'] = leak_trades.head(5).to_dict('records')
                
                if not tx_df.empty:
                    hold_durations = calculate_hold_durations(tx_df)
                    metrics['hold_patterns'] = analyze_hold_patterns(hold_durations)
                    metrics['slippage'] = calculate_slippage_estimate(tx_df)
                
                # Get coach analysis
                response = coach.analyze_wallet(question, metrics)
            
            # Display response
            console.print(f"\n[italic green]{response}[/]\n")
            
            # Show suggestions if applicable
            if "suggest" in question.lower() or "improve" in question.lower():
                suggestions = coach.suggest_improvements(
                    metrics, 
                    leak_trades.to_dict('records') if 'leak_trades' in locals() and not leak_trades.empty else None
                )
                if suggestions:
                    console.print("[bold]Specific Suggestions:[/]")
                    for suggestion in suggestions:
                        console.print(f"  {suggestion}")
                    console.print()
        
        except KeyboardInterrupt:
            console.print("\n[yellow]Chat interrupted. Type 'exit' to quit.[/]")
            continue
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/]")
            console.print("[dim]Make sure you've loaded wallet data first with the 'load' command.[/]")

@app.command()
def analyze(address: str, question: Optional[str] = None):
    """Quick analysis of a specific wallet without interactive chat."""
    # Load data for this wallet
    load(address)
    
    # If no question provided, give general analysis
    if not question:
        stats()
    else:
        # Run single analysis
        coach = TradingCoach()
        
        # Load data
        tx_df = db.execute("SELECT * FROM tx").df()
        pnl_df = db.execute("SELECT * FROM pnl").df()
        
        # Calculate metrics
        metrics = {}
        if not pnl_df.empty:
            metrics['win_rate'] = calculate_win_rate(pnl_df)
            metrics['portfolio'] = calculate_portfolio_metrics(pnl_df, tx_df)
        
        if not tx_df.empty:
            hold_durations = calculate_hold_durations(tx_df)
            metrics['hold_patterns'] = analyze_hold_patterns(hold_durations)
        
        # Get analysis
        response = coach.analyze_wallet(question, metrics)
        console.print(f"\n[italic green]{response}[/]\n")

@app.command()
def clear():
    """Clear all cached data."""
    db.execute("DROP TABLE IF EXISTS tx")
    db.execute("DROP TABLE IF EXISTS pnl")
    console.print("[green]✓ Cache cleared[/]")

if __name__ == "__main__":
    app() 