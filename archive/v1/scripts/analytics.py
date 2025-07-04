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

def calculate_median_hold_time(pnl_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate median hold time from PnL data.
    
    Returns median hold time in minutes and other hold time stats.
    """
    if pnl_df.empty or 'holdTimeSeconds' not in pnl_df.columns:
        return {
            'median_hold_minutes': 0,
            'avg_hold_minutes': 0,
            'min_hold_minutes': 0,
            'max_hold_minutes': 0
        }
    
    # Filter out tokens that haven't been sold (holdTimeSeconds = 0)
    sold_tokens = pnl_df[pnl_df['holdTimeSeconds'] > 0]
    
    if sold_tokens.empty:
        return {
            'median_hold_minutes': 0,
            'avg_hold_minutes': 0,
            'min_hold_minutes': 0,
            'max_hold_minutes': 0
        }
    
    hold_minutes = sold_tokens['holdTimeSeconds'] / 60
    
    return {
        'median_hold_minutes': hold_minutes.median(),
        'avg_hold_minutes': hold_minutes.mean(),
        'min_hold_minutes': hold_minutes.min(),
        'max_hold_minutes': hold_minutes.max(),
        'total_tokens_traded': len(pnl_df),
        'tokens_with_hold_data': len(sold_tokens)
    }

def calculate_accurate_stats(pnl_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate accurate wallet statistics matching Cielo's display.
    
    Win rate is based on all tokens traded, not just closed positions.
    """
    if pnl_df.empty:
        return {
            'total_tokens_traded': 0,
            'win_rate_pct': 0,
            'total_realized_pnl': 0,
            'total_unrealized_pnl': 0,
            'median_hold_minutes': 0
        }
    
    # Count all tokens traded
    total_tokens = len(pnl_df)
    
    # Count winning tokens (positive realized PnL)
    winning_tokens = len(pnl_df[pnl_df['realizedPnl'] > 0])
    
    # Calculate win rate as percentage of all tokens
    win_rate = (winning_tokens / total_tokens * 100) if total_tokens > 0 else 0
    
    # Sum realized and unrealized PnL
    total_realized = pnl_df['realizedPnl'].sum()
    total_unrealized = pnl_df['unrealizedPnl'].sum()
    
    # Get median hold time
    hold_stats = calculate_median_hold_time(pnl_df)
    
    return {
        'total_tokens_traded': total_tokens,
        'win_rate_pct': win_rate,
        'total_realized_pnl': total_realized,
        'total_unrealized_pnl': total_unrealized,
        'median_hold_minutes': hold_stats['median_hold_minutes'],
        'winning_tokens': winning_tokens,
        'losing_tokens': total_tokens - winning_tokens
    }

def get_wallet_stats_smart(db_connection, pnl_df: pd.DataFrame = None) -> Dict[str, Any]:
    """
    Get wallet statistics using aggregated_stats table if available (best data),
    otherwise trading_stats table, otherwise calculate from PnL data.
    
    This allows us to show accurate stats even when we only fetch limited token data.
    """
    try:
        # Check if aggregated_stats table exists and has data (BEST SOURCE)
        tables = [t[0] for t in db_connection.execute("SHOW TABLES").fetchall()]
        
        if 'aggregated_stats' in tables:
            # Try to get stats from aggregated_stats table
            stats_result = db_connection.execute("""
                SELECT * FROM aggregated_stats 
                ORDER BY data_timestamp DESC 
                LIMIT 1
            """).fetchone()
            
            if stats_result:
                # Convert to dict using column names
                columns = [desc[0] for desc in db_connection.execute("SELECT * FROM aggregated_stats LIMIT 0").description]
                stats_dict = dict(zip(columns, stats_result))
                
                # Format for consistency
                return {
                    'total_tokens_traded': stats_dict.get('tokens_traded', 0),
                    'win_rate_pct': stats_dict.get('win_rate', 0) * 100,  # Convert to percentage
                    'total_realized_pnl': stats_dict.get('realized_pnl', 0),
                    'total_unrealized_pnl': stats_dict.get('unrealized_pnl', 0),
                    'total_pnl': stats_dict.get('combined_pnl', 0),
                    'roi_pct': stats_dict.get('combined_roi', 0) * 100,  # Convert to percentage
                    'total_buy_usd': stats_dict.get('total_buy_usd', 0),
                    'total_sell_usd': stats_dict.get('total_sell_usd', 0),
                    'avg_holding_seconds': stats_dict.get('avg_holding_time_seconds', 0),
                    'from_trading_stats': True,  # Flag to indicate source
                    'data_source': 'aggregated_stats',  # Specific source
                    'is_limited_data': False  # We have full stats
                }
        
        if 'trading_stats' in tables:
            # Try to get stats from trading_stats table
            stats_result = db_connection.execute("""
                SELECT * FROM trading_stats 
                ORDER BY data_timestamp DESC 
                LIMIT 1
            """).fetchone()
            
            if stats_result:
                # Convert to dict using column names
                columns = [desc[0] for desc in db_connection.execute("SELECT * FROM trading_stats LIMIT 0").description]
                stats_dict = dict(zip(columns, stats_result))
                
                # Format for consistency with calculate_accurate_stats
                return {
                    'total_tokens_traded': stats_dict.get('total_trades', 0),
                    'win_rate_pct': stats_dict.get('win_rate', 0) * 100,  # Convert to percentage
                    'total_realized_pnl': stats_dict.get('realized_pnl', 0),
                    'total_unrealized_pnl': stats_dict.get('unrealized_pnl', 0),
                    'total_pnl': stats_dict.get('total_pnl', 0),
                    'roi_pct': stats_dict.get('roi', 0) * 100,  # Convert to percentage
                    'avg_trade_size': stats_dict.get('avg_trade_size', 0),
                    'largest_win': stats_dict.get('largest_win', 0),
                    'largest_loss': stats_dict.get('largest_loss', 0),
                    'from_trading_stats': True,  # Flag to indicate source
                    'data_source': 'trading_stats',  # Specific source
                    'is_limited_data': False  # We have full stats
                }
    except Exception as e:
        print(f"Error reading stats tables: {e}")
    
    # Fall back to calculating from PnL data
    if pnl_df is not None and not pnl_df.empty:
        stats = calculate_accurate_stats(pnl_df)
        stats['from_trading_stats'] = False
        stats['data_source'] = 'calculated'
        
        # Check if this is limited data
        try:
            # Check if pnl table has is_limited flag
            result = db_connection.execute("""
                SELECT COUNT(*) as count FROM pnl
            """).fetchone()
            token_count = result[0] if result else len(pnl_df)
            
            # If we have exactly 100, 200, or 1000 tokens, it's likely limited
            stats['is_limited_data'] = token_count in [100, 200, 1000]
        except:
            stats['is_limited_data'] = False
            
        return stats
    
    # No data available
    return {
        'total_tokens_traded': 0,
        'win_rate_pct': 0,
        'total_realized_pnl': 0,
        'total_unrealized_pnl': 0,
        'total_pnl': 0,
        'from_trading_stats': False,
        'data_source': 'none',
        'is_limited_data': False
    }

def get_top_performers_from_limited_data(pnl_df: pd.DataFrame, top_n: int = 5) -> Dict[str, pd.DataFrame]:
    """
    Get top gainers and losers from limited PnL data.
    Useful when we only fetch a subset of tokens for large wallets.
    """
    if pnl_df.empty:
        return {
            'top_gainers': pd.DataFrame(),
            'top_losers': pd.DataFrame()
        }
    
    # Sort by total PnL
    sorted_df = pnl_df.sort_values('totalPnl', ascending=False)
    
    # Get top gainers
    top_gainers = sorted_df.head(top_n)
    
    # Get top losers (exclude tokens with 0 PnL)
    losers = sorted_df[sorted_df['totalPnl'] < 0]
    top_losers = losers.tail(top_n) if not losers.empty else pd.DataFrame()
    
    return {
        'top_gainers': top_gainers,
        'top_losers': top_losers
    } 