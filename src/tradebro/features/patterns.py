"""Complex pattern detection for deep behavioral analysis."""
import polars as pl
from typing import Dict, List, Tuple, Any


def detect_loss_aversion_asymmetry(df: pl.DataFrame) -> Dict[str, Any]:
    """
    Detect if trader holds losers significantly longer than winners.
    This reveals ego protection and inability to accept being wrong.
    """
    if df.is_empty() or "pnl" not in df.columns:
        return {"detected": False}
    
    winners = df.filter(pl.col("pnl") > 0)
    losers = df.filter(pl.col("pnl") < 0)
    
    if winners.is_empty() or losers.is_empty():
        return {"detected": False}
    
    avg_winner_hold = float(winners["hold_minutes"].mean())
    avg_loser_hold = float(losers["hold_minutes"].mean())
    
    # Losers held 20% longer indicates loss aversion
    if avg_loser_hold > avg_winner_hold * 1.2:
        return {
            "detected": True,
            "winner_hold": avg_winner_hold,
            "loser_hold": avg_loser_hold,
            "asymmetry_ratio": avg_loser_hold / avg_winner_hold,
            "extra_hold_minutes": avg_loser_hold - avg_winner_hold,
            "insight": f"You hold losers {(avg_loser_hold/avg_winner_hold - 1)*100:.0f}% longer than winners"
        }
    
    return {"detected": False}


def detect_revenge_trading_pattern(df: pl.DataFrame) -> Dict[str, Any]:
    """
    Detect massive position size increases after losses.
    Classic revenge trading: trying to "get even" with the market.
    """
    if df.is_empty() or df.height < 10:
        return {"detected": False}
    
    # Calculate median trade size
    median_size = float(df["trade_size_usd"].median())
    
    # Find trades that are unusually large
    large_trades = df.filter(pl.col("trade_size_usd") > median_size * 5)
    
    if large_trades.is_empty():
        return {"detected": False}
    
    # Check if large trades follow losses
    revenge_trades = []
    df_sorted = df.sort("timestamp")
    
    for i in range(1, df_sorted.height):
        current = df_sorted.row(i, named=True)
        previous = df_sorted.row(i-1, named=True)
        
        # Large trade after a loss?
        if (current["trade_size_usd"] > median_size * 5 and 
            previous["pnl"] < 0):
            revenge_trades.append({
                "size": current["trade_size_usd"],
                "size_multiplier": current["trade_size_usd"] / median_size,
                "previous_loss": previous["pnl"],
                "result": current["pnl"]
            })
    
    if len(revenge_trades) >= 2:  # Pattern needs repetition
        total_revenge_pnl = sum(t["result"] for t in revenge_trades)
        return {
            "detected": True,
            "count": len(revenge_trades),
            "median_size": median_size,
            "revenge_trades": revenge_trades[:3],  # Top 3 examples
            "total_damage": total_revenge_pnl,
            "avg_size_multiplier": sum(t["size_multiplier"] for t in revenge_trades) / len(revenge_trades),
            "insight": f"After losses, you increase size {sum(t['size_multiplier'] for t in revenge_trades)/len(revenge_trades):.0f}x"
        }
    
    return {"detected": False}


def detect_fomo_spiral(df: pl.DataFrame) -> Dict[str, Any]:
    """
    Detect rapid entry frequency after big wins.
    FOMO pattern: big win → overconfidence → rapid bad trades.
    """
    if df.is_empty() or df.height < 20:
        return {"detected": False}
    
    df_sorted = df.sort("timestamp")
    
    # Find big wins (top 20% of profits)
    profit_threshold = df.filter(pl.col("pnl") > 0)["pnl"].quantile(0.8) if not df.filter(pl.col("pnl") > 0).is_empty() else 0
    big_wins = df_sorted.filter(pl.col("pnl") > profit_threshold)
    
    if big_wins.is_empty():
        return {"detected": False}
    
    fomo_sequences = []
    
    for win_idx in big_wins["index"].to_list():
        if win_idx + 5 >= df_sorted.height:
            continue
            
        # Look at next 5 trades
        next_trades = df_sorted.slice(win_idx + 1, 5)
        
        # Calculate time between trades
        time_gaps = []
        for i in range(1, next_trades.height):
            gap = (next_trades["timestamp"][i] - next_trades["timestamp"][i-1]).total_seconds() / 60
            time_gaps.append(gap)
        
        avg_gap = sum(time_gaps) / len(time_gaps) if time_gaps else float('inf')
        
        # Rapid trading = gaps < 30 minutes
        if avg_gap < 30:
            results = next_trades["pnl"].to_list()
            losses = sum(1 for r in results if r < 0)
            
            fomo_sequences.append({
                "trigger_win": float(df_sorted[win_idx]["pnl"]),
                "trades_after": len(results),
                "avg_minutes_between": avg_gap,
                "losses": losses,
                "total_pnl": sum(results)
            })
    
    if len(fomo_sequences) >= 2:
        avg_losses = sum(s["losses"] for s in fomo_sequences) / sum(s["trades_after"] for s in fomo_sequences)
        return {
            "detected": True,
            "sequences": len(fomo_sequences),
            "examples": fomo_sequences[:2],
            "loss_rate_after_wins": avg_losses,
            "insight": f"After big wins, {avg_losses*100:.0f}% of your next trades lose"
        }
    
    return {"detected": False}


def detect_no_process_chaos(df: pl.DataFrame) -> Dict[str, Any]:
    """
    Detect if trading lacks any consistency.
    High variance in everything = no systematic approach.
    """
    if df.is_empty() or df.height < 20:
        return {"detected": False}
    
    # Calculate coefficient of variation for key metrics
    size_cv = (df["trade_size_usd"].std() / df["trade_size_usd"].mean() * 100) if df["trade_size_usd"].mean() > 0 else 0
    hold_cv = (df["hold_minutes"].std() / df["hold_minutes"].mean() * 100) if df["hold_minutes"].mean() > 0 else 0
    
    # Time between trades
    df_sorted = df.sort("timestamp")
    time_gaps = []
    for i in range(1, df_sorted.height):
        gap = (df_sorted["timestamp"][i] - df_sorted["timestamp"][i-1]).total_seconds() / 3600  # hours
        if gap < 24 * 7:  # Exclude gaps > 1 week
            time_gaps.append(gap)
    
    time_cv = (pl.Series(time_gaps).std() / pl.Series(time_gaps).mean() * 100) if time_gaps else 0
    
    # High CV = no consistency
    if size_cv > 150 and hold_cv > 150:
        return {
            "detected": True,
            "size_variance": float(size_cv),
            "hold_variance": float(hold_cv),
            "timing_variance": float(time_cv),
            "insight": "Your trading is pure chaos - no consistency in size, timing, or holds",
            "worst_metric": "position_sizing" if size_cv > hold_cv else "hold_duration"
        }
    
    return {"detected": False}


def detect_winner_cutter_pattern(df: pl.DataFrame) -> Dict[str, Any]:
    """
    Detect if trader systematically cuts winners too early.
    Compares potential vs actual gains.
    """
    if df.is_empty():
        return {"detected": False}
    
    winners = df.filter(pl.col("pnl") > 0)
    if winners.is_empty() or winners.height < 5:
        return {"detected": False}
    
    # Winners closed very quickly (< 30 min)
    quick_winners = winners.filter(pl.col("hold_minutes") < 30)
    
    if quick_winners.height > winners.height * 0.5:
        avg_quick_pnl = float(quick_winners["pnl_pct"].mean())
        avg_patient_pnl = float(winners.filter(pl.col("hold_minutes") >= 60)["pnl_pct"].mean()) if winners.filter(pl.col("hold_minutes") >= 60).height > 0 else avg_quick_pnl * 2
        
        return {
            "detected": True,
            "quick_exit_rate": quick_winners.height / winners.height,
            "avg_quick_pnl_pct": avg_quick_pnl,
            "avg_patient_pnl_pct": avg_patient_pnl,
            "missed_gains_multiplier": avg_patient_pnl / avg_quick_pnl if avg_quick_pnl > 0 else 2,
            "insight": f"{quick_winners.height/winners.height*100:.0f}% of winners cut within 30min"
        }
    
    return {"detected": False}


def analyze_all_patterns(df: pl.DataFrame) -> Dict[str, Any]:
    """Run all pattern detections and return summary."""
    patterns = {
        "loss_aversion": detect_loss_aversion_asymmetry(df),
        "revenge_trading": detect_revenge_trading_pattern(df),
        "fomo_spiral": detect_fomo_spiral(df),
        "no_process": detect_no_process_chaos(df),
        "winner_cutting": detect_winner_cutter_pattern(df)
    }
    
    detected = [k for k, v in patterns.items() if v.get("detected", False)]
    
    # Determine primary behavioral issue
    if "revenge_trading" in detected and "no_process" in detected:
        primary_issue = "Emotional gambling disguised as trading"
    elif "loss_aversion" in detected and "winner_cutting" in detected:
        primary_issue = "Fear-based trading destroying your edge"
    elif "fomo_spiral" in detected:
        primary_issue = "Dopamine-driven decision making"
    elif detected:
        primary_issue = f"Primary issue: {detected[0].replace('_', ' ').title()}"
    else:
        primary_issue = "No major behavioral patterns detected"
    
    return {
        "patterns_detected": detected,
        "pattern_details": patterns,
        "primary_issue": primary_issue,
        "severity": "critical" if len(detected) >= 3 else "high" if len(detected) >= 2 else "moderate"
    } 