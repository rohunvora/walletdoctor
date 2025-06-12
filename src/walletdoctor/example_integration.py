"""Example integration of the new insight engine with existing WalletDoctor code."""
import pandas as pd
import polars as pl
from typing import Dict, Any
import sys
sys.path.append('..')  # Add parent to path

# Import existing modules
from llm import TradingCoach  # Your existing OpenAI wrapper

# Import new insight engine
from walletdoctor.features import behaviour
from walletdoctor.insights import generate_full_report, calculate_extras
from walletdoctor.llm import make_messages, format_for_cli


def convert_to_polars_format(pnl_df: pd.DataFrame, tx_df: pd.DataFrame) -> pl.DataFrame:
    """
    Convert existing pandas DataFrames to format expected by new features.
    
    This is where you'd map your existing columns to the expected schema.
    """
    # Example conversion - adapt based on your actual schema
    trades_data = []
    
    # Convert PnL data
    for _, row in pnl_df.iterrows():
        trade = {
            'token_mint': row.get('mint', ''),
            'symbol': row.get('symbol', ''),
            'pnl': row.get('realizedPnl', 0),
            'pnl_pct': (row.get('realizedPnl', 0) / row.get('totalBought', 1) * 100) if row.get('totalBought', 0) > 0 else 0,
            'hold_minutes': row.get('holdTimeSeconds', 0) / 60 if row.get('holdTimeSeconds') else 0,
            'trade_size_usd': row.get('totalBought', 0),
            'timestamp': pd.Timestamp.now(),  # Would need actual timestamps
            'side': 'sell' if row.get('realizedPnl') is not None else 'hold'
        }
        trades_data.append(trade)
    
    # Add fee data from transactions
    if not tx_df.empty and 'fee' in tx_df.columns:
        # This would be summed elsewhere, just showing structure
        fee_total = tx_df['fee'].sum()
    
    return pl.DataFrame(trades_data)


def compute_behavioral_metrics(df: pl.DataFrame) -> Dict[str, float]:
    """Compute all behavioral metrics using the new feature functions."""
    metrics = {}
    
    # Core metrics
    metrics['fee_burn'] = behaviour.fee_burn(df)
    metrics['win_rate'] = behaviour.win_rate(df)
    metrics['profit_factor'] = behaviour.profit_factor(df)
    metrics['largest_loss'] = behaviour.largest_loss(df)
    
    # Behavioral patterns
    metrics['premature_exits'] = behaviour.premature_exits(df)
    metrics['revenge_trading_risk'] = behaviour.revenge_trading_risk(df)
    metrics['overtrading_score'] = behaviour.overtrading_score(df)
    metrics['avg_winner_hold_time'] = behaviour.avg_winner_hold_time(df)
    metrics['avg_loser_hold_time'] = behaviour.avg_loser_hold_time(df)
    
    # Risk metrics
    metrics['position_sizing_variance'] = behaviour.position_sizing_variance(df)
    
    # Additional context for header
    metrics['total_pnl'] = float(df['pnl'].sum()) if 'pnl' in df.columns else 0
    metrics['trade_count'] = df.height
    
    return metrics


def generate_coaching_insights(pnl_df: pd.DataFrame, tx_df: pd.DataFrame, coach: TradingCoach) -> str:
    """
    Main integration function - generates insights using the new architecture.
    
    Args:
        pnl_df: Your existing PnL DataFrame
        tx_df: Your existing transactions DataFrame  
        coach: Your existing TradingCoach instance
    
    Returns:
        Formatted coaching insights
    """
    # Step 1: Convert data to Polars format
    trades_df = convert_to_polars_format(pnl_df, tx_df)
    
    # Step 2: Compute behavioral metrics
    metrics = compute_behavioral_metrics(trades_df)
    
    # Step 3: Calculate any extras needed for insights
    extras = calculate_extras(trades_df)
    
    # Step 4: Generate insight report
    report = generate_full_report(metrics, extras, max_insights=5)
    
    # Step 5: If we have insights, get LLM to weave narrative
    if report['insights']:
        messages = make_messages(
            header=report['header'],
            bullets=report['insights']
        )
        
        # Use existing coach to get response
        response = coach.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=300
        )
        
        narrative = response.choices[0].message.content
        return format_for_cli(narrative)
    else:
        # No significant insights triggered
        return "Your trading metrics look balanced. Keep monitoring for changes."


# Example usage in existing coach.py chat command
def enhanced_chat_response(question: str, metrics: Dict[str, Any], coach: TradingCoach) -> str:
    """
    Drop-in replacement for existing chat logic.
    
    This would replace the current coach.analyze_wallet() call.
    """
    # Load your data as usual
    tx_df = pd.DataFrame()  # Your transaction data
    pnl_df = pd.DataFrame()  # Your PnL data
    
    # Generate insights using new engine
    insights = generate_coaching_insights(pnl_df, tx_df, coach)
    
    return insights


if __name__ == "__main__":
    # Quick test with mock data
    mock_pnl = pd.DataFrame([
        {'mint': 'token1', 'symbol': 'TOK1', 'realizedPnl': -6000, 'holdTimeSeconds': 300, 'totalBought': 10000},
        {'mint': 'token2', 'symbol': 'TOK2', 'realizedPnl': 2000, 'holdTimeSeconds': 600, 'totalBought': 5000},
        {'mint': 'token3', 'symbol': 'TOK3', 'realizedPnl': 1000, 'holdTimeSeconds': 900, 'totalBought': 3000},
    ])
    
    mock_tx = pd.DataFrame([
        {'fee': 50000000},  # 0.05 SOL in lamports
        {'fee': 50000000},
        {'fee': 50000000},
    ])
    
    # Note: This won't run without OpenAI key
    print("Example integration created. See enhanced_chat_response() for usage.") 