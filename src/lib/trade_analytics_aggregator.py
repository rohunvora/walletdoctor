"""
Trade Analytics Aggregator - v0.8.0-summary implementation
Aggregates enriched trade data into compact analytics summaries
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


class TradeAnalyticsAggregator:
    """Aggregates trade data into analytics summaries for v0.8.0-summary"""
    
    def __init__(self):
        self.reset_stats()
    
    def reset_stats(self):
        """Reset internal statistics"""
        self.stats = {
            "trades_processed": 0,
            "trades_with_pnl": 0,
            "computation_time_ms": 0
        }
    
    async def aggregate_analytics(self, trades: List[Dict], wallet: str) -> Dict[str, Any]:
        """
        Aggregate trade data into analytics summary
        
        Args:
            trades: List of enriched trades (must have price/P&L data)
            wallet: Wallet address
            
        Returns:
            Analytics summary following v0.8.0-summary schema
        """
        import time
        start_time = time.time()
        
        # Initialize counters
        pnl_metrics = self._calculate_pnl_metrics(trades)
        volume_metrics = self._calculate_volume_metrics(trades)
        token_metrics = self._calculate_token_metrics(trades)
        time_window = self._calculate_time_window(trades)
        recent_windows = self._calculate_recent_windows(trades)
        
        # Build response
        summary = {
            "wallet": wallet,
            "schema_version": "v0.8.0-summary",
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "time_window": time_window,
            "pnl": pnl_metrics,
            "volume": volume_metrics,
            "top_tokens": token_metrics[:10],  # Top 10 tokens
            "recent_windows": recent_windows
        }
        
        # Track stats
        self.stats["trades_processed"] = len(trades)
        self.stats["computation_time_ms"] = int((time.time() - start_time) * 1000)
        
        # Log summary size
        summary_json = json.dumps(summary)
        summary_size = len(summary_json)
        logger.info(
            f"Analytics summary generated: "
            f"wallet={wallet[:8]}..., "
            f"trades={len(trades)}, "
            f"size={summary_size:,} bytes ({summary_size/1024:.1f} KB), "
            f"time={self.stats['computation_time_ms']}ms"
        )
        
        return summary
    
    def _calculate_pnl_metrics(self, trades: List[Dict]) -> Dict[str, Any]:
        """Calculate P&L metrics from trades"""
        total_pnl = Decimal("0")
        wins = 0
        losses = 0
        max_win = Decimal("0")
        max_loss = Decimal("0")
        
        # Only analyze sell trades (where P&L is realized)
        sell_trades = [t for t in trades if t.get("action") == "sell"]
        
        for trade in sell_trades:
            pnl_str = trade.get("pnl_usd")
            if not pnl_str or pnl_str == "":
                continue
            
            try:
                pnl = Decimal(pnl_str)
                total_pnl += pnl
                
                if pnl > 0:
                    wins += 1
                    max_win = max(max_win, pnl)
                elif pnl < 0:
                    losses += 1
                    max_loss = min(max_loss, pnl)
            except:
                continue
        
        # Calculate win rate
        total_with_pnl = wins + losses
        win_rate = float(wins) / total_with_pnl if total_with_pnl > 0 else 0.0
        
        # Calculate percentage return (would need initial investment for accuracy)
        # For now, use a simple heuristic based on average trade size
        avg_trade_value = self._get_avg_trade_value(trades)
        if avg_trade_value > 0:
            # Assume ~100 trades worth of capital
            estimated_capital = avg_trade_value * 100
            realized_pct = (total_pnl / estimated_capital * 100) if estimated_capital > 0 else Decimal("0")
        else:
            realized_pct = Decimal("0")
        
        return {
            "realized_usd": self._format_decimal(total_pnl),
            "realized_pct": self._format_decimal(realized_pct),
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 3),
            "max_single_win_usd": self._format_decimal(max_win) if max_win > 0 else "0",
            "max_single_loss_usd": self._format_decimal(max_loss) if max_loss < 0 else "0"
        }
    
    def _calculate_volume_metrics(self, trades: List[Dict]) -> Dict[str, Any]:
        """Calculate volume metrics from trades"""
        total_sol_volume = Decimal("0")
        total_usd_volume = Decimal("0")
        trade_count = len(trades)
        
        for trade in trades:
            # Calculate SOL volume from token_in/token_out
            token_in = trade.get("token_in", {})
            token_out = trade.get("token_out", {})
            
            if token_in.get("symbol") == "So111111":  # SOL
                sol_amount = Decimal(str(token_in.get("amount", 0)))
                total_sol_volume += sol_amount
            elif token_out.get("symbol") == "So111111":  # SOL
                sol_amount = Decimal(str(token_out.get("amount", 0)))
                total_sol_volume += sol_amount
            
            # Add USD volume if available
            value_usd = trade.get("value_usd")
            if value_usd and value_usd != "":
                try:
                    total_usd_volume += Decimal(value_usd)
                except:
                    pass
        
        # Calculate average trade value
        avg_trade_value = total_usd_volume / trade_count if trade_count > 0 else Decimal("0")
        
        # Calculate trades per day
        time_window = self._calculate_time_window(trades)
        days = time_window.get("days", 1)
        trades_per_day = trade_count / days if days > 0 else 0
        
        return {
            "total_trades": trade_count,
            "total_sol_volume": self._format_decimal(total_sol_volume),
            "avg_trade_value_usd": self._format_decimal(avg_trade_value),
            "trades_per_day": round(trades_per_day, 2)
        }
    
    def _calculate_token_metrics(self, trades: List[Dict]) -> List[Dict[str, Any]]:
        """Calculate per-token metrics"""
        token_stats = defaultdict(lambda: {"trades": 0, "pnl": Decimal("0")})
        
        for trade in trades:
            token = trade.get("token", "")
            if not token:
                continue
            
            token_stats[token]["trades"] += 1
            
            # Add P&L if this is a sell trade
            if trade.get("action") == "sell":
                pnl_str = trade.get("pnl_usd")
                if pnl_str and pnl_str != "":
                    try:
                        token_stats[token]["pnl"] += Decimal(pnl_str)
                    except:
                        pass
        
        # Convert to sorted list
        token_list = []
        for symbol, stats in token_stats.items():
            token_list.append({
                "symbol": symbol[:10],  # Truncate long symbols
                "trades": stats["trades"],
                "realized_pnl_usd": self._format_decimal(stats["pnl"])
            })
        
        # Sort by trade count (most traded first)
        token_list.sort(key=lambda x: x["trades"], reverse=True)
        
        return token_list
    
    def _calculate_time_window(self, trades: List[Dict]) -> Dict[str, Any]:
        """Calculate time window from first to last trade"""
        if not trades:
            return {
                "start": None,
                "end": None,
                "days": 0
            }
        
        # Parse timestamps
        timestamps = []
        for trade in trades:
            ts_str = trade.get("timestamp", "")
            if ts_str:
                try:
                    # Handle ISO format
                    if ts_str.endswith("Z"):
                        ts_str = ts_str[:-1] + "+00:00"
                    dt = datetime.fromisoformat(ts_str)
                    timestamps.append(dt)
                except:
                    continue
        
        if not timestamps:
            return {"start": None, "end": None, "days": 0}
        
        # Sort to find first and last
        timestamps.sort()
        start_dt = timestamps[0]
        end_dt = timestamps[-1]
        
        # Calculate days
        delta = end_dt - start_dt
        days = delta.days + 1  # Include both start and end days
        
        return {
            "start": start_dt.isoformat().replace("+00:00", "Z"),
            "end": end_dt.isoformat().replace("+00:00", "Z"),
            "days": days
        }
    
    def _calculate_recent_windows(self, trades: List[Dict]) -> Dict[str, Any]:
        """Calculate metrics for recent time windows (30d, 7d)"""
        now = datetime.now(timezone.utc)
        
        # Filter trades by time windows
        trades_30d = []
        trades_7d = []
        
        for trade in trades:
            ts_str = trade.get("timestamp", "")
            if not ts_str:
                continue
            
            try:
                # Parse timestamp
                if ts_str.endswith("Z"):
                    ts_str = ts_str[:-1] + "+00:00"
                dt = datetime.fromisoformat(ts_str)
                
                # Check time windows
                days_ago = (now - dt).days
                
                if days_ago <= 30:
                    trades_30d.append(trade)
                    if days_ago <= 7:
                        trades_7d.append(trade)
            except:
                continue
        
        # Calculate metrics for each window
        def calculate_window_metrics(window_trades):
            if not window_trades:
                return {"pnl_usd": "0", "trades": 0, "win_rate": 0}
            
            pnl = Decimal("0")
            wins = 0
            losses = 0
            
            for trade in window_trades:
                if trade.get("action") == "sell":
                    pnl_str = trade.get("pnl_usd")
                    if pnl_str and pnl_str != "":
                        try:
                            pnl_val = Decimal(pnl_str)
                            pnl += pnl_val
                            if pnl_val > 0:
                                wins += 1
                            elif pnl_val < 0:
                                losses += 1
                        except:
                            pass
            
            total_with_pnl = wins + losses
            win_rate = float(wins) / total_with_pnl if total_with_pnl > 0 else 0.0
            
            return {
                "pnl_usd": self._format_decimal(pnl),
                "trades": len(window_trades),
                "win_rate": round(win_rate, 2)
            }
        
        return {
            "last_30d": calculate_window_metrics(trades_30d),
            "last_7d": calculate_window_metrics(trades_7d)
        }
    
    def _get_avg_trade_value(self, trades: List[Dict]) -> Decimal:
        """Get average trade value in USD"""
        total_value = Decimal("0")
        count = 0
        
        for trade in trades:
            value_str = trade.get("value_usd")
            if value_str and value_str != "":
                try:
                    total_value += Decimal(value_str)
                    count += 1
                except:
                    pass
        
        return total_value / count if count > 0 else Decimal("0")
    
    def _format_decimal(self, value: Any) -> str:
        """Format decimal values as strings with appropriate precision"""
        # Convert to Decimal for consistent handling
        if isinstance(value, (int, float)):
            value = Decimal(str(value))
        elif not isinstance(value, Decimal):
            value = Decimal(value)
        
        # Remove trailing zeros and format nicely
        formatted = f"{value:.2f}"
        
        # For whole numbers, remove .00
        if formatted.endswith(".00"):
            formatted = formatted[:-3]
        
        return formatted 