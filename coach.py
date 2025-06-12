#!/usr/bin/env python3
# coach.py
import os, json, typer, duckdb
from prompt_toolkit import PromptSession
from rich import print
from rich.console import Console
from rich.table import Table
from typing import Optional
from rich.progress import track

# Set API keys from environment variables
# DO NOT hardcode API keys in code!
# Set these in your shell or .env file:
# export HELIUS_KEY="your-helius-key"
# export CIELO_KEY="your-cielo-key"
# export OPENAI_API_KEY="your-openai-key"

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
    generate_trading_insights,
    calculate_accurate_stats,
    calculate_median_hold_time
)
from llm import TradingCoach, get_quick_insight, ANALYSIS_PROMPTS

# Import blind spots detector
from blind_spots import BlindSpotDetector

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
            totalSold DOUBLE,
            holdTimeSeconds BIGINT,
            numSwaps INTEGER
        )
    """)

@app.command()
def load(addresses: str, limit: Optional[int] = 500):
    """Load & cache transactions for one or more comma-separated wallets."""
    init_db()
    
    for address in [w.strip() for w in addresses.split(",")]:
        console.print(f"[bold cyan]► Fetching data for {address}...[/]")
        
        try:
            # Fetch transactions
            with console.status("[bold green]Fetching transactions from Helius..."):
                tx_data = fetch_helius_transactions(address, limit=100)
                if tx_data:
                    console.print(f"  ✓ Found {len(tx_data)} transactions")
                    # Pass transaction data as a list
                    tx_df = normalize_helius_transactions(tx_data)
                    # Clear existing data for this wallet
                    try:
                        db.execute(f"DELETE FROM tx WHERE from_address = '{address}' OR to_address = '{address}'")
                    except:
                        pass  # Table might not exist yet
                    # Store normalized data
                    cache_to_duckdb(db, "tx", tx_df.to_dict('records'))
            
            # Fetch PnL data
            console.print("[bold green]Fetching PnL from Cielo...[/]")
            pnl_data = fetch_cielo_pnl(address)
            if pnl_data and 'data' in pnl_data and 'items' in pnl_data.get('data', {}):
                tokens = pnl_data['data']['items']
                console.print(f"  ✓ Found PnL for {len(tokens)} tokens total")
                
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
            console.print(f"  ✗ Error loading {address}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    console.print("✓ Data cached in coach.db")

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
    
    # Calculate accurate metrics
    console.print("\n[bold cyan]📊 Wallet Statistics (Accurate)[/]\n")
    
    # Get accurate stats
    accurate_stats = calculate_accurate_stats(pnl_df)
    
    # Display summary matching Cielo's format
    table = Table(title="Performance Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Tokens Traded", str(accurate_stats['total_tokens_traded']))
    table.add_row("Token Win Rate", f"{accurate_stats['win_rate_pct']:.2f}%")
    table.add_row("Winning Tokens", str(accurate_stats['winning_tokens']))
    table.add_row("Losing Tokens", str(accurate_stats['losing_tokens']))
    table.add_row("Realized PnL", f"${accurate_stats['total_realized_pnl']:,.2f}")
    table.add_row("Unrealized PnL", f"${accurate_stats['total_unrealized_pnl']:,.2f}")
    table.add_row("Median Hold Time", f"{accurate_stats['median_hold_minutes']:.1f} minutes")
    console.print(table)
    
    # Additional detailed metrics
    if not pnl_df.empty:
        # Top gainers
        console.print("\n[bold cyan]🚀 Top 5 Gainers[/]")
        top_gainers = pnl_df.nlargest(5, 'realizedPnl')[['symbol', 'realizedPnl']]
        for _, token in top_gainers.iterrows():
            console.print(f"  {token['symbol']}: ${token['realizedPnl']:,.2f}")
        
        # Biggest losers
        biggest_losers = pnl_df[pnl_df['realizedPnl'] < 0].nsmallest(5, 'realizedPnl')[['symbol', 'realizedPnl']]
        if not biggest_losers.empty:
            console.print("\n[bold red]📉 Biggest Losses[/]")
            for _, token in biggest_losers.iterrows():
                console.print(f"  {token['symbol']}: ${token['realizedPnl']:,.2f}")

@app.command()
def blind_spots():
    """Analyze behavioral patterns and blind spots in your trading."""
    init_db()
    
    console.print("\n[bold cyan]🔍 Behavioral Pattern Analysis[/]\n")
    console.print("Analyzing your trading patterns for blind spots...\n")
    
    # Initialize detector
    detector = BlindSpotDetector()
    
    # Run analysis
    with console.status("[bold green]Detecting patterns..."):
        patterns = detector.analyze_all_patterns()
    
    # Display results
    if not patterns:
        console.print("[yellow]No patterns detected. Need more trading data.[/]")
        return
    
    for pattern in patterns:
        if 'confidence' in pattern:
            # This is a detected pattern
            console.print(f"[bold red]🎯 {pattern['pattern']}[/]")
            console.print(f"Confidence: [bold]{pattern['confidence']}[/]")
            console.print(f"Impact: [bold yellow]{pattern['impact']}[/]")
            console.print(f"Recommendation: [italic green]{pattern['recommendation']}[/]\n")
            
            # Show evidence
            if 'evidence' in pattern:
                evidence = pattern['evidence']
                
                # Create evidence table
                evidence_table = Table(title="Evidence")
                evidence_table.add_column("Metric", style="cyan")
                evidence_table.add_column("Value", style="white")
                
                # Add relevant evidence based on pattern type
                if 'FOMO' in pattern['pattern']:
                    evidence_table.add_row("Quick Trades (<10min)", str(evidence['quick_trades_count']))
                    evidence_table.add_row("Patient Trades (>1hr)", str(evidence['patient_trades_count']))
                    evidence_table.add_row("Avg Quick PnL", evidence['avg_quick_pnl'])
                    evidence_table.add_row("Avg Patient PnL", evidence['avg_patient_pnl'])
                    evidence_table.add_row("Quick Win Rate", evidence['quick_win_rate'])
                    evidence_table.add_row("Patient Win Rate", evidence['patient_win_rate'])
                    
                elif 'Loss Aversion' in pattern['pattern']:
                    evidence_table.add_row("Winners Analyzed", str(evidence['winners_count']))
                    evidence_table.add_row("Losers Analyzed", str(evidence['losers_count']))
                    evidence_table.add_row("Avg Winner Hold", evidence['avg_winner_hold'])
                    evidence_table.add_row("Avg Loser Hold", evidence['avg_loser_hold'])
                    evidence_table.add_row("Total Losses", evidence['total_losses'])
                
                console.print(evidence_table)
                console.print()
        else:
            # This is a message (no patterns found, insufficient data, etc.)
            console.print(f"[dim]{pattern['message']}[/]")
            if 'recommendation' in pattern:
                console.print(f"[dim]{pattern['recommendation']}[/]")

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
        
        # Generate deep behavioral insights
        console.print("\n[bold cyan]🧠 Deep Behavioral Analysis[/]\n")
        
        # Initialize blind spot detector
        detector = BlindSpotDetector()
        
        # Run pattern detection
        with console.status("[bold green]Analyzing behavioral patterns..."):
            patterns = detector.analyze_all_patterns()
        
        # Display detected patterns
        if patterns:
            for pattern in patterns:
                if 'confidence' in pattern:
                    console.print(f"[bold red]🎯 {pattern['pattern']}[/]")
                    console.print(f"   Confidence: {pattern['confidence']} | Severity: {pattern['impact']}")
                    console.print(f"   [italic green]✅ THE FIX: {pattern['recommendation']}[/]\n")
        
        # Generate AI insights
        console.print("[bold cyan]🤖 AI Trading Coach Insights[/]\n")
        
        # Load metrics for AI analysis
        tx_df = db.execute("SELECT * FROM tx").df()
        pnl_df = db.execute("SELECT * FROM pnl").df()
        
        if not pnl_df.empty:
            # Calculate comprehensive metrics
            metrics = {
                'stats': calculate_accurate_stats(pnl_df),
                'win_rate': calculate_win_rate(pnl_df),
                'portfolio': calculate_portfolio_metrics(pnl_df, tx_df),
                'leak_trades': identify_leak_trades(pnl_df).head(5).to_dict('records') if not identify_leak_trades(pnl_df).empty else []
            }
            
            if not tx_df.empty:
                hold_durations = calculate_hold_durations(tx_df)
                metrics['hold_patterns'] = analyze_hold_patterns(hold_durations)
            
            # Get quick insights for key patterns
            insights = []
            
            # Check for loss aversion
            if metrics['stats']['losing_tokens'] > metrics['stats']['winning_tokens'] * 2:
                insight = get_quick_insight(metrics, "loss aversion")
                insights.append(("Loss Aversion Pattern", insight))
            
            # Check for FOMO trading
            if metrics['stats']['median_hold_minutes'] < 15:
                insight = get_quick_insight(metrics, "FOMO trading")
                insights.append(("FOMO Trading Pattern", insight))
            
            # Check for poor win rate
            if metrics['stats']['win_rate_pct'] < 30:
                insight = get_quick_insight(metrics, "low win rate")
                insights.append(("Low Win Rate Pattern", insight))
            
            # Display insights
            for title, insight in insights:
                console.print(f"[bold yellow]{title}:[/]")
                console.print(f"{insight}\n")
                
    else:
        # Run single analysis with specific question
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