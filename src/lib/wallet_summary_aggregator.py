"""
Wallet Summary Aggregator
Computes aggregated statistics from all wallet trades for ChatGPT compatibility.
Ensures payload stays under 25KB while providing complete wallet insights.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class WalletSummaryAggregator:
    """Aggregates wallet trade data into a compact summary for ChatGPT."""
    
    MAX_PAYLOAD_SIZE = 25 * 1024  # 25KB limit
    SAFETY_BUFFER = 5 * 1024      # 5KB safety margin
    
    def __init__(self):
        self.logger = logger
    
    def aggregate_wallet_summary(
        self, 
        trades: List[Dict[str, Any]], 
        include_windows: bool = True,
        max_tokens: int = 10
    ) -> Dict[str, Any]:
        """
        Aggregate all trades into a compact summary.
        
        Args:
            trades: List of enriched trade dictionaries
            include_windows: Whether to include 7d/30d windows
            max_tokens: Maximum tokens to include in breakdown
            
        Returns:
            Aggregated summary dict under 25KB
        """
        if not trades:
            return self._empty_summary()
        
        # Sort trades by timestamp
        sorted_trades = sorted(trades, key=lambda x: x.get('timestamp', 0))
        
        # Core aggregations
        summary = {
            "wallet_summary": {
                "total_trades": len(trades),
                "first_trade": sorted_trades[0]['timestamp'],
                "last_trade": sorted_trades[-1]['timestamp'],
                "unique_tokens": len(set(t.get('token_symbol', t.get('token_mint', '')) for t in trades)),
                "unique_dexes": len(set(t.get('dex', 'unknown') for t in trades))
            }
        }
        
        # P&L Analysis
        pnl_stats = self._calculate_pnl_stats(trades)
        summary["pnl_analysis"] = pnl_stats
        
        # Win Rate
        win_rate_stats = self._calculate_win_rate(trades)
        summary["win_rate"] = win_rate_stats
        
        # Trade Volume
        volume_stats = self._calculate_volume_stats(trades)
        summary["trade_volume"] = volume_stats
        
        # Token Breakdown (Top 10 by absolute P&L)
        token_breakdown = self._calculate_token_breakdown(trades, max_tokens)
        summary["token_breakdown"] = token_breakdown
        
        # Recent Windows (7d/30d)
        if include_windows:
            window_stats = self._calculate_window_stats(sorted_trades)
            summary["recent_windows"] = window_stats
        
        # Trading Patterns
        pattern_stats = self._calculate_trading_patterns(sorted_trades)
        summary["trading_patterns"] = pattern_stats
        
        # Ensure we're under size limit
        summary = self._trim_if_needed(summary)
        
        return summary
    
    def _calculate_pnl_stats(self, trades: List[Dict]) -> Dict[str, Any]:
        """Calculate P&L statistics from all trades."""
        sell_trades = [t for t in trades if t.get('action') == 'sell']
        
        total_pnl = sum(float(t.get('pnl_usd', 0)) for t in sell_trades)
        positive_pnl = sum(float(t.get('pnl_usd', 0)) for t in sell_trades if float(t.get('pnl_usd', 0)) > 0)
        negative_pnl = sum(float(t.get('pnl_usd', 0)) for t in sell_trades if float(t.get('pnl_usd', 0)) < 0)
        
        # Calculate profit factor
        profit_factor = abs(positive_pnl / negative_pnl) if negative_pnl != 0 else float('inf')
        if profit_factor == float('inf'):
            profit_factor_str = "inf"
        else:
            profit_factor_str = f"{profit_factor:.2f}"
        
        return {
            "total_realized_pnl_usd": f"{total_pnl:.2f}",
            "total_gains_usd": f"{positive_pnl:.2f}",
            "total_losses_usd": f"{negative_pnl:.2f}",
            "profit_factor": profit_factor_str,
            "largest_win_usd": f"{max((float(t.get('pnl_usd', 0)) for t in sell_trades if float(t.get('pnl_usd', 0)) > 0), default=0):.2f}",
            "largest_loss_usd": f"{min((float(t.get('pnl_usd', 0)) for t in sell_trades if float(t.get('pnl_usd', 0)) < 0), default=0):.2f}",
            "sell_trades_count": len(sell_trades)
        }
    
    def _calculate_win_rate(self, trades: List[Dict]) -> Dict[str, Any]:
        """Calculate win rate statistics."""
        sell_trades = [t for t in trades if t.get('action') == 'sell']
        
        if not sell_trades:
            return {
                "overall_win_rate": "0.00",
                "winning_trades": 0,
                "losing_trades": 0,
                "breakeven_trades": 0
            }
        
        winning = sum(1 for t in sell_trades if float(t.get('pnl_usd', 0)) > 0)
        losing = sum(1 for t in sell_trades if float(t.get('pnl_usd', 0)) < 0)
        breakeven = len(sell_trades) - winning - losing
        
        win_rate = (winning / len(sell_trades) * 100) if sell_trades else 0
        
        return {
            "overall_win_rate": f"{win_rate:.2f}",
            "winning_trades": winning,
            "losing_trades": losing,
            "breakeven_trades": breakeven
        }
    
    def _calculate_volume_stats(self, trades: List[Dict]) -> Dict[str, Any]:
        """Calculate trading volume statistics."""
        total_volume_usd = sum(float(t.get('value_usd', 0)) for t in trades)
        buy_volume_usd = sum(float(t.get('value_usd', 0)) for t in trades if t.get('action') == 'buy')
        sell_volume_usd = sum(float(t.get('value_usd', 0)) for t in trades if t.get('action') == 'sell')
        
        buy_count = sum(1 for t in trades if t.get('action') == 'buy')
        sell_count = sum(1 for t in trades if t.get('action') == 'sell')
        
        return {
            "total_volume_usd": f"{total_volume_usd:.2f}",
            "buy_volume_usd": f"{buy_volume_usd:.2f}",
            "sell_volume_usd": f"{sell_volume_usd:.2f}",
            "buy_count": buy_count,
            "sell_count": sell_count,
            "buy_sell_ratio": f"{buy_count/sell_count:.2f}" if sell_count > 0 else "inf"
        }
    
    def _calculate_token_breakdown(self, trades: List[Dict], max_tokens: int = 10) -> List[Dict[str, Any]]:
        """Calculate per-token statistics, sorted by absolute P&L."""
        token_stats = {}
        
        for trade in trades:
            token = trade.get('token_symbol', trade.get('token_mint', 'unknown'))
            
            if token not in token_stats:
                token_stats[token] = {
                    'symbol': token,
                    'trades': 0,
                    'buy_count': 0,
                    'sell_count': 0,
                    'realized_pnl_usd': 0,
                    'volume_usd': 0,
                    'wins': 0,
                    'losses': 0,
                    'total_bought': 0,
                    'total_sold': 0,
                    'avg_buy_price': 0,
                    'avg_sell_price': 0
                }
            
            stats = token_stats[token]
            stats['trades'] += 1
            stats['volume_usd'] += float(trade.get('value_usd', 0))
            
            if trade.get('action') == 'buy':
                stats['buy_count'] += 1
                stats['total_bought'] += float(trade.get('value_usd', 0))
                # Track for average buy price
                if stats['buy_count'] == 1:
                    stats['avg_buy_price'] = float(trade.get('price_usd', 0))
                else:
                    # Weighted average
                    stats['avg_buy_price'] = (
                        stats['avg_buy_price'] * (stats['buy_count'] - 1) + 
                        float(trade.get('price_usd', 0))
                    ) / stats['buy_count']
            
            elif trade.get('action') == 'sell':
                stats['sell_count'] += 1
                stats['total_sold'] += float(trade.get('value_usd', 0))
                pnl = float(trade.get('pnl_usd', 0))
                stats['realized_pnl_usd'] += pnl
                
                if pnl > 0:
                    stats['wins'] += 1
                elif pnl < 0:
                    stats['losses'] += 1
                
                # Track for average sell price
                if stats['sell_count'] == 1:
                    stats['avg_sell_price'] = float(trade.get('price_usd', 0))
                else:
                    # Weighted average
                    stats['avg_sell_price'] = (
                        stats['avg_sell_price'] * (stats['sell_count'] - 1) + 
                        float(trade.get('price_usd', 0))
                    ) / stats['sell_count']
        
        # Convert to list and sort by absolute P&L
        token_list = []
        for token, stats in token_stats.items():
            win_rate = (stats['wins'] / stats['sell_count'] * 100) if stats['sell_count'] > 0 else 0
            
            token_list.append({
                "symbol": stats['symbol'],
                "trades": stats['trades'],
                "realized_pnl_usd": f"{stats['realized_pnl_usd']:.2f}",
                "win_rate": f"{win_rate:.1f}",
                "volume_usd": f"{stats['volume_usd']:.2f}",
                "buy_count": stats['buy_count'],
                "sell_count": stats['sell_count'],
                "avg_buy_price_usd": f"{stats['avg_buy_price']:.6f}" if stats['avg_buy_price'] > 0 else "0",
                "avg_sell_price_usd": f"{stats['avg_sell_price']:.6f}" if stats['avg_sell_price'] > 0 else "0"
            })
        
        # Sort by absolute P&L (largest magnitude first)
        token_list.sort(key=lambda x: abs(float(x['realized_pnl_usd'])), reverse=True)
        
        # Return top N tokens
        return token_list[:max_tokens]
    
    def _calculate_window_stats(self, sorted_trades: List[Dict]) -> Dict[str, Any]:
        """Calculate statistics for recent time windows."""
        now = datetime.now()
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)
        
        # Convert to timestamps
        seven_days_ts = int(seven_days_ago.timestamp())
        thirty_days_ts = int(thirty_days_ago.timestamp())
        
        # Filter trades by window
        trades_7d = [t for t in sorted_trades if t.get('timestamp', 0) >= seven_days_ts]
        trades_30d = [t for t in sorted_trades if t.get('timestamp', 0) >= thirty_days_ts]
        
        return {
            "last_7_days": {
                "trades": len(trades_7d),
                "pnl_usd": f"{sum(float(t.get('pnl_usd', 0)) for t in trades_7d if t.get('action') == 'sell'):.2f}",
                "volume_usd": f"{sum(float(t.get('value_usd', 0)) for t in trades_7d):.2f}"
            },
            "last_30_days": {
                "trades": len(trades_30d),
                "pnl_usd": f"{sum(float(t.get('pnl_usd', 0)) for t in trades_30d if t.get('action') == 'sell'):.2f}",
                "volume_usd": f"{sum(float(t.get('value_usd', 0)) for t in trades_30d):.2f}"
            }
        }
    
    def _calculate_trading_patterns(self, sorted_trades: List[Dict]) -> Dict[str, Any]:
        """Calculate trading pattern statistics."""
        if not sorted_trades:
            return {
                "most_active_hour_utc": "N/A",
                "avg_trades_per_day": "0",
                "favorite_dex": "N/A"
            }
        
        # Hour analysis
        hour_counts = {}
        for trade in sorted_trades:
            hour = datetime.fromtimestamp(trade.get('timestamp', 0)).hour
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        
        most_active_hour = max(hour_counts.items(), key=lambda x: x[1])[0] if hour_counts else 0
        
        # Trades per day
        first_ts = sorted_trades[0].get('timestamp', 0)
        last_ts = sorted_trades[-1].get('timestamp', 0)
        days_active = max((last_ts - first_ts) / 86400, 1)
        avg_trades_per_day = len(sorted_trades) / days_active
        
        # Favorite DEX
        dex_counts = {}
        for trade in sorted_trades:
            dex = trade.get('dex', 'unknown')
            dex_counts[dex] = dex_counts.get(dex, 0) + 1
        
        favorite_dex = max(dex_counts.items(), key=lambda x: x[1])[0] if dex_counts else "unknown"
        
        return {
            "most_active_hour_utc": most_active_hour,
            "avg_trades_per_day": f"{avg_trades_per_day:.1f}",
            "favorite_dex": favorite_dex
        }
    
    def _trim_if_needed(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """Trim summary if it exceeds size limit."""
        serialized = json.dumps(summary, separators=(',', ':'))
        current_size = len(serialized.encode('utf-8'))
        
        if current_size <= (self.MAX_PAYLOAD_SIZE - self.SAFETY_BUFFER):
            summary['meta'] = {
                'payload_size_bytes': current_size,
                'trimmed': False
            }
            return summary
        
        # Trim token breakdown progressively
        original_token_count = len(summary.get('token_breakdown', []))
        while current_size > (self.MAX_PAYLOAD_SIZE - self.SAFETY_BUFFER) and len(summary.get('token_breakdown', [])) > 3:
            summary['token_breakdown'] = summary['token_breakdown'][:-1]
            serialized = json.dumps(summary, separators=(',', ':'))
            current_size = len(serialized.encode('utf-8'))
        
        summary['meta'] = {
            'payload_size_bytes': current_size,
            'trimmed': True,
            'original_token_count': original_token_count,
            'trimmed_token_count': len(summary.get('token_breakdown', []))
        }
        
        return summary
    
    def _empty_summary(self) -> Dict[str, Any]:
        """Return empty summary structure."""
        return {
            "wallet_summary": {
                "total_trades": 0,
                "first_trade": None,
                "last_trade": None,
                "unique_tokens": 0,
                "unique_dexes": 0
            },
            "pnl_analysis": {
                "total_realized_pnl_usd": "0.00",
                "total_gains_usd": "0.00",
                "total_losses_usd": "0.00",
                "profit_factor": "0.00",
                "largest_win_usd": "0.00",
                "largest_loss_usd": "0.00",
                "sell_trades_count": 0
            },
            "win_rate": {
                "overall_win_rate": "0.00",
                "winning_trades": 0,
                "losing_trades": 0,
                "breakeven_trades": 0
            },
            "trade_volume": {
                "total_volume_usd": "0.00",
                "buy_volume_usd": "0.00",
                "sell_volume_usd": "0.00",
                "buy_count": 0,
                "sell_count": 0,
                "buy_sell_ratio": "0.00"
            },
            "token_breakdown": [],
            "recent_windows": {
                "last_7_days": {
                    "trades": 0,
                    "pnl_usd": "0.00",
                    "volume_usd": "0.00"
                },
                "last_30_days": {
                    "trades": 0,
                    "pnl_usd": "0.00",
                    "volume_usd": "0.00"
                }
            },
            "trading_patterns": {
                "most_active_hour_utc": "N/A",
                "avg_trades_per_day": "0",
                "favorite_dex": "N/A"
            },
            "meta": {
                "payload_size_bytes": 0,
                "trimmed": False
            }
        } 