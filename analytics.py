# analytics.py
import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime, timedelta

def calculate_win_rate(pnl_df: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate win rate metrics from PnL data.
    
    Returns:
    - Overall win rate
    - Win rate by token
    - Average win/loss amounts
    """
    default_metrics = {
        'win_rate': 0.0,
        'total_trades': 0,
        'winning_trades': 0,
        'losing_trades': 0,
        'avg_win': 0.0,
        'avg_loss': 0.0,
        'profit_factor': 0.0
    }
    
    if pnl_df.empty or 'realizedPnl' not in pnl_df.columns:
        return default_metrics
    
    # Filter for closed positions
    closed_positions = pnl_df[pnl_df['realizedPnl'].notna()]
    
    if closed_positions.empty:
        return default_metrics
    
    wins = closed_positions[closed_positions['realizedPnl'] > 0]
    losses = closed_positions[closed_positions['realizedPnl'] <= 0]
    
    win_rate = len(wins) / len(closed_positions) if len(closed_positions) > 0 else 0
    avg_win = wins['realizedPnl'].mean() if not wins.empty else 0
    avg_loss = losses['realizedPnl'].mean() if not losses.empty else 0
    
    return {
        'win_rate': win_rate,
        'total_trades': len(closed_positions),
        'winning_trades': len(wins),
        'losing_trades': len(losses),
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
    }

def analyze_hold_patterns(hold_durations_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyze holding patterns to identify trader behavior.
    
    Returns:
    - Average hold duration
    - Hold duration distribution
    - Quick flip vs longer hold ratio
    """
    if hold_durations_df.empty:
        return {
            'avg_hold_hours': 0,
            'median_hold_hours': 0,
            'min_hold_hours': 0,
            'max_hold_hours': 0,
            'quick_flips_ratio': 0,
            'hold_buckets': {
                '<1h': 0,
                '1-6h': 0,
                '6-24h': 0,
                '1-7d': 0,
                '>7d': 0
            }
        }
    
    hold_hours = hold_durations_df['hold_duration_hours']
    
    # Define quick flip as < 1 hour
    quick_flips = len(hold_hours[hold_hours < 1])
    total_trades = len(hold_hours)
    
    return {
        'avg_hold_hours': hold_hours.mean(),
        'median_hold_hours': hold_hours.median(),
        'min_hold_hours': hold_hours.min(),
        'max_hold_hours': hold_hours.max(),
        'quick_flips_ratio': quick_flips / total_trades if total_trades > 0 else 0,
        'hold_buckets': {
            '<1h': len(hold_hours[hold_hours < 1]),
            '1-6h': len(hold_hours[(hold_hours >= 1) & (hold_hours < 6)]),
            '6-24h': len(hold_hours[(hold_hours >= 6) & (hold_hours < 24)]),
            '1-7d': len(hold_hours[(hold_hours >= 24) & (hold_hours < 168)]),
            '>7d': len(hold_hours[hold_hours >= 168])
        }
    }

def calculate_slippage_estimate(
    transactions_df: pd.DataFrame,
    reference_price: Optional[float] = None
) -> Dict[str, float]:
    """
    Estimate slippage from swap transactions.
    
    This is a simplified version - in production you'd want to
    compare against real-time price feeds.
    """
    swap_txs = transactions_df[
        transactions_df['type'].str.contains('swap', case=False, na=False)
    ]
    
    if swap_txs.empty:
        return {'avg_slippage_pct': 0.0, 'total_swaps': 0}
    
    # Placeholder for slippage calculation
    # In reality, you'd compare execution price vs market price
    return {
        'avg_slippage_pct': 0.5,  # Placeholder
        'total_swaps': len(swap_txs),
        'high_slippage_trades': 0  # Trades with >2% slippage
    }

def identify_leak_trades(
    pnl_df: pd.DataFrame,
    threshold_usd: float = -5000
) -> pd.DataFrame:
    """
    Identify significant losing trades that warrant analysis.
    
    Returns DataFrame of trades that lost more than threshold.
    """
    if pnl_df.empty or 'realizedPnl' not in pnl_df.columns:
        return pd.DataFrame()
    
    # Filter trades with losses exceeding the threshold
    leak_trades = pnl_df[
        (pnl_df['realizedPnl'] < threshold_usd) & 
        (pnl_df['realizedPnl'].notna())
    ].copy()
    
    # Add additional context
    if not leak_trades.empty:
        leak_trades['loss_severity'] = abs(leak_trades['realizedPnl'] / threshold_usd)
        leak_trades = leak_trades.sort_values('realizedPnl')
    
    return leak_trades

def calculate_portfolio_metrics(
    pnl_df: pd.DataFrame,
    transactions_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Calculate overall portfolio performance metrics.
    
    Returns:
    - Total PnL
    - ROI
    - Sharpe ratio approximation
    - Max drawdown
    """
    if pnl_df.empty:
        return {
            'total_realized_pnl': 0,
            'total_unrealized_pnl': 0,
            'total_pnl': 0,
            'roi_pct': 0,
            'sharpe_ratio': 0,
            'max_drawdown_pct': 0,
            'active_positions': 0
        }
    
    total_realized = pnl_df['realizedPnl'].sum() if 'realizedPnl' in pnl_df.columns else 0
    total_unrealized = pnl_df['unrealizedPnl'].sum() if 'unrealizedPnl' in pnl_df.columns else 0
    
    # Calculate daily returns for Sharpe approximation
    if not transactions_df.empty and 'timestamp' in transactions_df.columns:
        daily_pnl = calculate_daily_pnl(transactions_df, pnl_df)
        sharpe = calculate_sharpe_ratio(daily_pnl)
        max_dd = calculate_max_drawdown(daily_pnl)
    else:
        sharpe = 0
        max_dd = 0
    
    return {
        'total_realized_pnl': total_realized,
        'total_unrealized_pnl': total_unrealized,
        'total_pnl': total_realized + total_unrealized,
        'sharpe_ratio': sharpe,
        'max_drawdown_pct': max_dd,
        'active_positions': len(pnl_df[pnl_df['quantity'] > 0]) if 'quantity' in pnl_df.columns else 0
    }

def calculate_daily_pnl(
    transactions_df: pd.DataFrame,
    pnl_df: pd.DataFrame
) -> pd.Series:
    """Helper to calculate daily PnL series."""
    # Simplified implementation
    if transactions_df.empty or 'timestamp' not in transactions_df.columns:
        return pd.Series()
    
    # Group by date and sum PnL
    # This is a placeholder - real implementation would be more complex
    return pd.Series()

def calculate_sharpe_ratio(daily_returns: pd.Series, risk_free_rate: float = 0.02) -> float:
    """Calculate Sharpe ratio from daily returns."""
    if daily_returns.empty:
        return 0
    
    excess_returns = daily_returns - risk_free_rate / 365
    return np.sqrt(365) * excess_returns.mean() / excess_returns.std() if excess_returns.std() > 0 else 0

def calculate_max_drawdown(daily_pnl: pd.Series) -> float:
    """Calculate maximum drawdown percentage."""
    if daily_pnl.empty:
        return 0
    
    cumulative = daily_pnl.cumsum()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    return drawdown.min() * 100 if not drawdown.empty else 0

def generate_trading_insights(
    win_rate_metrics: Dict[str, float],
    hold_patterns: Dict[str, Any],
    portfolio_metrics: Dict[str, Any],
    leak_trades_df: pd.DataFrame
) -> List[str]:
    """
    Generate actionable insights from analytics.
    
    Returns list of insight strings.
    """
    insights = []
    
    # Win rate insights
    if win_rate_metrics['win_rate'] < 0.4:
        insights.append(f"Low win rate ({win_rate_metrics['win_rate']:.1%}) - consider reviewing entry criteria")
    
    # Hold pattern insights
    if hold_patterns.get('quick_flips_ratio', 0) > 0.7:
        insights.append("Over 70% of trades are quick flips (<1h) - may be overtrading")
    
    # Loss insights
    if not leak_trades_df.empty:
        worst_loss = leak_trades_df.iloc[0]['realizedPnl']
        insights.append(f"Largest loss: ${worst_loss:,.2f} USD - review risk management")
    
    # Portfolio insights
    if portfolio_metrics['total_realized_pnl'] < 0:
        insights.append("Net negative realized PnL - focus on improving trade selection")
    
    return insights 