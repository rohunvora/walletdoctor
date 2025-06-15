"""Pure behavioral feature extraction functions.

Each function is deterministic and returns a single numeric value.
These are the building blocks for insights.
"""
import polars as pl
from typing import Optional


def fee_burn(df: pl.DataFrame) -> float:
    """Total SOL spent on fees/slippage."""
    if df.is_empty() or "fee" not in df.columns:
        return 0.0
    return float(df.select((pl.col("fee") / 1e9).sum())[0, 0])


def premature_exits(df: pl.DataFrame) -> float:
    """% of winning trades closed in first 15 minutes."""
    if df.is_empty() or "pnl" not in df.columns:
        return 0.0
    
    winners = df.filter(pl.col("pnl") > 0)
    if winners.is_empty():
        return 0.0
    
    early = winners.filter(pl.col("hold_minutes") <= 15)
    return 100 * early.height / winners.height


def revenge_trading_risk(df: pl.DataFrame) -> float:
    """% of losses that happen within 30min of previous loss."""
    if df.is_empty() or "pnl" not in df.columns:
        return 0.0
    
    losses = df.filter(pl.col("pnl") < 0).sort("timestamp")
    if losses.height < 2:
        return 0.0
    
    # Check time between consecutive losses
    revenge_count = 0
    timestamps = losses["timestamp"].to_list()
    
    for i in range(1, len(timestamps)):
        time_diff = (timestamps[i] - timestamps[i-1]).total_seconds() / 60
        if time_diff <= 30:
            revenge_count += 1
    
    return 100 * revenge_count / (losses.height - 1)


def market_impact_trades(df: pl.DataFrame, threshold_pct: float = 10.0) -> int:
    """Count of trades that moved the market > threshold%."""
    if df.is_empty() or "price_impact_pct" not in df.columns:
        return 0
    
    return df.filter(pl.col("price_impact_pct").abs() > threshold_pct).height


def win_rate(df: pl.DataFrame) -> float:
    """Simple win rate percentage."""
    if df.is_empty() or "pnl" not in df.columns:
        return 0.0
    
    wins = df.filter(pl.col("pnl") > 0).height
    total = df.height
    return 100 * wins / total if total > 0 else 0.0


def avg_winner_hold_time(df: pl.DataFrame) -> float:
    """Average hold time for winning trades in minutes."""
    if df.is_empty() or "pnl" not in df.columns:
        return 0.0
    
    winners = df.filter(pl.col("pnl") > 0)
    if winners.is_empty() or "hold_minutes" not in winners.columns:
        return 0.0
    
    return float(winners["hold_minutes"].mean())


def avg_loser_hold_time(df: pl.DataFrame) -> float:
    """Average hold time for losing trades in minutes."""
    if df.is_empty() or "pnl" not in df.columns:
        return 0.0
    
    losers = df.filter(pl.col("pnl") <= 0)
    if losers.is_empty() or "hold_minutes" not in losers.columns:
        return 0.0
    
    return float(losers["hold_minutes"].mean())


def profit_factor(df: pl.DataFrame) -> float:
    """Total wins / Total losses (absolute value)."""
    if df.is_empty() or "pnl" not in df.columns:
        return 0.0
    
    total_wins = float(df.filter(pl.col("pnl") > 0)["pnl"].sum())
    total_losses = abs(float(df.filter(pl.col("pnl") < 0)["pnl"].sum()))
    
    return total_wins / total_losses if total_losses > 0 else float('inf')


def largest_loss(df: pl.DataFrame) -> float:
    """Largest single loss (positive number)."""
    if df.is_empty() or "pnl" not in df.columns:
        return 0.0
    
    losses = df.filter(pl.col("pnl") < 0)
    if losses.is_empty():
        return 0.0
    
    return abs(float(losses["pnl"].min()))


def median_trade_size(df: pl.DataFrame) -> float:
    """Median trade size in USD."""
    if df.is_empty() or "trade_size_usd" not in df.columns:
        return 0.0
    
    return float(df["trade_size_usd"].median())


def overtrading_score(df: pl.DataFrame) -> float:
    """% of trades that happen within 5 min of previous trade."""
    if df.is_empty() or df.height < 2:
        return 0.0
    
    df_sorted = df.sort("timestamp")
    timestamps = df_sorted["timestamp"].to_list()
    
    rapid_trades = 0
    for i in range(1, len(timestamps)):
        time_diff = (timestamps[i] - timestamps[i-1]).total_seconds() / 60
        if time_diff <= 5:
            rapid_trades += 1
    
    return 100 * rapid_trades / (df.height - 1)


def position_sizing_variance(df: pl.DataFrame) -> float:
    """Coefficient of variation for position sizes (consistency metric)."""
    if df.is_empty() or "trade_size_usd" not in df.columns:
        return 0.0
    
    sizes = df["trade_size_usd"]
    mean_size = float(sizes.mean())
    std_size = float(sizes.std())
    
    return (std_size / mean_size * 100) if mean_size > 0 else 0.0 