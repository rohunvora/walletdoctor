#!/usr/bin/env python3
# coach.py
import os, json, typer, duckdb
from prompt_toolkit import PromptSession
from rich import print
from rich.console import Console
from rich.table import Table
from typing import Optional
from rich.progress import track
from datetime import datetime

# Set API keys from environment variables
# DO NOT hardcode API keys in code!
# Set these in your shell or .env file:
# export HELIUS_KEY="your-helius-key"
# export CIELO_KEY="your-cielo-key"
# export OPENAI_API_KEY="your-openai-key"

# Import our modules
from data import fetch_helius_transactions, fetch_cielo_pnl, cache_to_duckdb, load_wallet
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

# Import dialogue generator
from dialogue_generator import DialogueGenerator

# Import new modules for the pivot
from instant_stats import InstantStatsGenerator
from db_migrations import run_migrations, add_annotation, get_similar_annotations, save_snapshot
from trade_comparison import TradeComparator

app = typer.Typer()
console = Console()
db = duckdb.connect("coach.db")

# Initialize database schema
def init_db():
    """Initialize database tables if they don't exist."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS tx (
            signature VARCHAR,
            timestamp BIGINT,
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
    
    # Run new migrations for annotation support
    run_migrations(db)

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
                else:
                    console.print("[yellow]  ⚠ No transactions found from Helius[/]")
            
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
            else:
                console.print("[yellow]  ⚠ No PnL data found from Cielo[/]")
            
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
    detector = BlindSpotDetector(db_connection=db)
    
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
        detector = BlindSpotDetector(db_connection=db)
        
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
            
            # Initialize coach for AI insights
            coach = TradingCoach()
            
            # Check for loss aversion
            if metrics['stats']['losing_tokens'] > metrics['stats']['winning_tokens'] * 2:
                response = coach.analyze_wallet(
                    f"The trader has {metrics['stats']['losing_tokens']} losing tokens vs {metrics['stats']['winning_tokens']} winning tokens. Analyze this loss aversion pattern.",
                    metrics
                )
                insights.append(("Loss Aversion Pattern", response))
            
            # Check for FOMO trading
            if metrics['stats']['median_hold_minutes'] < 15:
                response = coach.analyze_wallet(
                    f"The trader has a median hold time of {metrics['stats']['median_hold_minutes']:.1f} minutes. Analyze this FOMO trading pattern.",
                    metrics
                )
                insights.append(("FOMO Trading Pattern", response))
            
            # Check for poor win rate
            if metrics['stats']['win_rate_pct'] < 30:
                response = coach.analyze_wallet(
                    f"The trader has a win rate of {metrics['stats']['win_rate_pct']:.1f}%. Analyze this low win rate pattern.",
                    metrics
                )
                insights.append(("Low Win Rate Pattern", response))
            
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

@app.command()
def quick_analyze(address: str):
    """Quick analysis for web interface - wisdom and patterns only, no AI"""
    # Load data for this wallet
    load(address)
    
    # Show stats
    stats()
    
    # Generate wisdom insights
    console.print("\n[bold cyan]🧠 WISDOM FROM YOUR TRADING JOURNEY[/]\n")
    
    # Initialize wisdom generator
    wisdom_gen = DialogueGenerator(db)
    journey = wisdom_gen.extract_trading_journey()
    
    if journey.get('has_data'):
        # Display journey highlights
        console.print(f"[yellow]Total journey: {journey['total_trades']} trades, ${journey['total_pnl']:,.0f} P&L[/]")
        console.print(f"[yellow]Win rate: {journey['win_rate']:.1f}%[/]\n")
        
        if journey['worst_trades']:
            console.print("[bold red]Your disasters:[/]")
            for trade in journey['worst_trades'][:3]:
                console.print(f"  • {trade}")
        
        if journey['best_trades']:
            console.print("\n[bold green]Your triumphs:[/]")
            for trade in journey['best_trades'][:3]:
                console.print(f"  • {trade}")
        
        if journey['most_traded']:
            console.print("\n[bold yellow]Tokens you can't quit:[/]")
            for token, count in list(journey['most_traded'].items())[:3]:
                console.print(f"  • {token}: {count} times")
        
        console.print(f"\n[dim]Quick flips (<10min): {len(journey['quick_trades'])} trades[/]")
        console.print(f"[dim]Diamond hands (>24h): {len(journey['long_holds'])} trades[/]")
    else:
        console.print("[yellow]No trading journey found. Load some wallet data first![/]")
    
    console.print("\n[dim]💡 For AI-powered wisdom, use the web interface with OpenAI configured![/]")

@app.command()
def instant(address: str):
    """New instant gratification experience - no gates, immediate value."""
    init_db()
    
    # Load data
    console.print(f"[bold cyan]⚡ Loading {address} instantly...[/]")
    
    # Use load_wallet from data.py with instant mode for limited data
    success = load_wallet(db, address, mode='instant')
    
    if not success:
        console.print("[red]Failed to load wallet data. Please check the wallet address.[/]")
        return
    
    # Initialize instant stats generator
    instant_gen = InstantStatsGenerator(db)
    
    # Get baseline stats
    console.print("\n[bold cyan]📊 YOUR INSTANT BASELINE[/]\n")
    stats = instant_gen.get_baseline_stats()
    top_trades = instant_gen.get_top_trades()
    
    # Display formatted stats
    output = instant_gen.format_for_display(stats, top_trades)
    console.print(output)
    
    # Show annotation prompt
    console.print("\n[bold yellow]💭 Add notes to your trades to unlock personalized coaching![/]")
    console.print("[dim]Use 'coach annotate' to add notes to any trade[/]\n")
    
    # Save a snapshot - temporarily disabled due to auto-increment issue
    # save_snapshot(db)
    
    # Show recent performance if available
    recent = instant_gen.get_recent_performance()
    if recent.get('has_recent'):
        console.print(f"\n📈 Recent Trend: {recent['trend'].upper()}")
        console.print(f"   Last {recent['recent_trades']} trades: {recent['recent_win_rate']:.1f}% win rate")
        console.print(f"   Recent avg P&L: ${recent['recent_avg_pnl']:+,.2f}")
        
    # Show data limit warning if needed
    pnl_count = db.execute("SELECT COUNT(*) FROM pnl").fetchone()[0]
    if pnl_count >= 1000:
        console.print("\n[yellow]⚠️  Showing first 1,000 trades only. Large wallets may have partial data.[/]")

@app.command()
def annotate(symbol: str, note: str):
    """Add a note to a recent trade for personalized insights."""
    init_db()
    
    # Find the trade
    pnl_df = db.execute(f"""
        SELECT * FROM pnl 
        WHERE UPPER(symbol) = UPPER('{symbol}')
        ORDER BY mint DESC
        LIMIT 1
    """).df()
    
    if pnl_df.empty:
        console.print(f"[red]Trade not found for {symbol}[/]")
        return
    
    trade = pnl_df.iloc[0]
    
    # Add annotation
    annotation_id = add_annotation(
        db,
        token_symbol=trade['symbol'],
        token_mint=trade['mint'],
        trade_pnl=trade['realizedPnl'],
        user_note=note,
        entry_size_usd=trade['totalBought'] * trade['avgBuyPrice'],
        hold_time_seconds=trade['holdTimeSeconds']
    )
    
    console.print(f"[green]✅ Note added to {symbol} trade[/]")
    
    # Find similar past trades with annotations
    similar = get_similar_annotations(db, entry_size_usd=trade['totalBought'] * trade['avgBuyPrice'])
    
    if similar:
        console.print("\n[bold cyan]📝 Similar trades you've annotated:[/]")
        for s in similar[:3]:
            console.print(f"  • {s[0]}: \"{s[2]}\" (P&L: ${s[1]:+,.2f})")
    
    # Use trade comparator for insights
    comparator = TradeComparator(db)
    comparison = comparator.compare_to_personal_average(trade.to_dict())
    similar_trades = comparator.find_similar_past_trades(trade.to_dict())
    
    insight = comparator.generate_comparison_insight(trade.to_dict(), comparison, similar_trades)
    console.print(f"\n{insight}")

@app.command()
def refresh():
    """Check for new trades and compare to your patterns."""
    init_db()
    
    console.print("[bold cyan]🔄 Checking for new trades...[/]\n")
    
    # Initialize comparator
    comparator = TradeComparator(db)
    
    # Detect new trades (force check for demo)
    new_trades = comparator.detect_new_trades(force_check=True)
    
    if not new_trades:
        console.print("[yellow]No new trades detected. Make a trade and refresh![/]")
        return
    
    console.print(f"[green]Found {len(new_trades)} new trades![/]\n")
    
    # Analyze each new trade
    for trade in new_trades[:3]:  # Limit to 3 for readability
        # Compare to personal average
        comparison = comparator.compare_to_personal_average(trade)
        
        # Find similar past trades
        similar_trades = comparator.find_similar_past_trades(trade)
        
        # Generate insight
        insight = comparator.generate_comparison_insight(trade, comparison, similar_trades)
        console.print(insight)
        console.print("")
        
        # Prompt for annotation
        console.print(f"[dim]💭 Add a note: coach annotate {trade['symbol']} \"your thoughts\"[/]")
        console.print("-" * 40)
        console.print("")

@app.command()
def evolution():
    """See how your trading has evolved with annotations."""
    init_db()
    
    console.print("[bold cyan]📈 YOUR TRADING EVOLUTION[/]\n")
    
    # Get snapshots
    snapshots = db.execute("""
        SELECT * FROM trade_snapshots 
        ORDER BY created_at DESC 
        LIMIT 10
    """).df()
    
    if snapshots.empty:
        console.print("[yellow]No evolution data yet. Keep trading and annotating![/]")
        return
    
    # Show evolution
    latest = snapshots.iloc[0]
    oldest = snapshots.iloc[-1]
    
    console.print(f"📊 From {oldest['snapshot_date']} → {latest['snapshot_date']}")
    console.print(f"   Win Rate: {oldest['win_rate']:.1f}% → {latest['win_rate']:.1f}%")
    console.print(f"   Avg P&L: ${oldest['avg_pnl']:+,.2f} → ${latest['avg_pnl']:+,.2f}")
    console.print(f"   Annotations: {oldest['annotations_count']} → {latest['annotations_count']}")
    
    # Show annotation insights
    annotations = db.execute("""
        SELECT sentiment, COUNT(*) as count 
        FROM trade_annotations 
        GROUP BY sentiment
    """).df()
    
    if not annotations.empty:
        console.print("\n💭 Your trading sentiments:")
        for _, row in annotations.iterrows():
            console.print(f"   {row['sentiment']}: {row['count']} trades")
    
    # Show most valuable annotations
    valuable = db.execute("""
        SELECT token_symbol, user_note, trade_pnl
        FROM trade_annotations
        WHERE LENGTH(user_note) > 20
        ORDER BY ABS(trade_pnl) DESC
        LIMIT 3
    """).df()
    
    if not valuable.empty:
        console.print("\n📝 Your most insightful notes:")
        for _, row in valuable.iterrows():
            console.print(f"   {row['token_symbol']} (${row['trade_pnl']:+,.2f}): \"{row['user_note'][:50]}...\"")

if __name__ == "__main__":
    app() 