#!/usr/bin/env python3
"""
instant_stats.py - Immediate feedback without statistical gates

Show users their baseline metrics instantly.
No waiting for 30 trades or bootstrap confidence.
"""

import pandas as pd
import duckdb
from typing import Dict, List, Tuple, Any, Optional


class InstantStatsGenerator:
    """Generate immediate, ungated statistics for instant gratification."""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def get_baseline_stats(self) -> Dict[str, Any]:
        """Get core stats that always display, regardless of trade count."""
        pnl_df = self.db.execute("SELECT * FROM pnl").df()
        
        if pnl_df.empty:
            return {
                'has_data': False,
                'message': 'No trading data found. Connect your wallet to get started.'
            }
        
        # Core metrics - always show these
        total_trades = len(pnl_df)
        winners = len(pnl_df[pnl_df['realizedPnl'] > 0])
        win_rate = (winners / total_trades * 100) if total_trades > 0 else 0
        
        total_pnl = pnl_df['realizedPnl'].sum()
        avg_pnl = pnl_df['realizedPnl'].mean()
        
        # Calculate average trade size
        pnl_df['entry_size_usd'] = pnl_df['totalBought'] * pnl_df['avgBuyPrice']
        avg_position_size = pnl_df['entry_size_usd'].mean()
        
        return {
            'has_data': True,
            'win_rate': win_rate,
            'total_trades': total_trades,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'avg_position_size': avg_position_size,
            'winning_trades': winners,
            'losing_trades': total_trades - winners,
            'best_trade': pnl_df.loc[pnl_df['realizedPnl'].idxmax()] if total_trades > 0 else None,
            'worst_trade': pnl_df.loc[pnl_df['realizedPnl'].idxmin()] if total_trades > 0 else None
        }
    
    def get_top_trades(self, limit: int = 3) -> Dict[str, List[Dict]]:
        """Get top winners and losers for immediate engagement."""
        pnl_df = self.db.execute("SELECT * FROM pnl").df()
        
        if pnl_df.empty:
            return {'winners': [], 'losers': []}
        
        # Calculate entry size for context
        pnl_df['entry_size_usd'] = pnl_df['totalBought'] * pnl_df['avgBuyPrice']
        
        # Get top winners
        winners = pnl_df.nlargest(limit, 'realizedPnl')[
            ['symbol', 'realizedPnl', 'entry_size_usd', 'holdTimeSeconds']
        ].to_dict('records')
        
        # Get top losers (but not all losers if < limit)
        losers_df = pnl_df[pnl_df['realizedPnl'] < 0]
        if len(losers_df) >= limit:
            losers = losers_df.nsmallest(limit, 'realizedPnl')[
                ['symbol', 'realizedPnl', 'entry_size_usd', 'holdTimeSeconds']
            ].to_dict('records')
        else:
            losers = losers_df[
                ['symbol', 'realizedPnl', 'entry_size_usd', 'holdTimeSeconds']
            ].to_dict('records')
        
        return {
            'winners': winners,
            'losers': losers
        }
    
    def get_recent_performance(self, days: int = 7) -> Dict[str, Any]:
        """Get recent performance trends without heavy analysis."""
        # For MVP, we'll use the last N trades as proxy for recency
        # In production, would filter by actual timestamps
        pnl_df = self.db.execute("SELECT * FROM pnl").df()
        
        if pnl_df.empty:
            return {'has_recent': False}
        
        # Take last 20% of trades as "recent" for MVP
        recent_count = max(1, int(len(pnl_df) * 0.2))
        recent_trades = pnl_df.tail(recent_count)
        
        recent_win_rate = (len(recent_trades[recent_trades['realizedPnl'] > 0]) / 
                          len(recent_trades) * 100)
        recent_avg_pnl = recent_trades['realizedPnl'].mean()
        
        return {
            'has_recent': True,
            'recent_trades': len(recent_trades),
            'recent_win_rate': recent_win_rate,
            'recent_avg_pnl': recent_avg_pnl,
            'trend': 'improving' if recent_win_rate > self.get_baseline_stats()['win_rate'] else 'declining'
        }
    
    def format_for_display(self, stats: Dict[str, Any], top_trades: Dict[str, List[Dict]]) -> str:
        """Format stats for clean display."""
        if not stats.get('has_data'):
            return stats.get('message', 'No data available')
        
        output = []
        output.append("📊 YOUR TRADING BASELINE")
        output.append("=" * 40)
        output.append(f"Win Rate: {stats['win_rate']:.1f}% ({stats['winning_trades']}W / {stats['losing_trades']}L)")
        output.append(f"Average P&L: ${stats['avg_pnl']:+,.2f}")
        output.append(f"Total P&L: ${stats['total_pnl']:+,.2f}")
        output.append(f"Avg Position Size: ${stats['avg_position_size']:,.2f}")
        output.append("")
        
        # Top trades
        if top_trades['winners']:
            output.append("🏆 Top Winners:")
            for t in top_trades['winners']:
                hold_time = f"{t['holdTimeSeconds']/60:.0f}min" if t['holdTimeSeconds'] < 3600 else f"{t['holdTimeSeconds']/3600:.1f}hr"
                output.append(f"  • {t['symbol']}: +${t['realizedPnl']:,.2f} ({hold_time})")
        
        if top_trades['losers']:
            output.append("\n💀 Biggest Losses:")
            for t in top_trades['losers']:
                hold_time = f"{t['holdTimeSeconds']/60:.0f}min" if t['holdTimeSeconds'] < 3600 else f"{t['holdTimeSeconds']/3600:.1f}hr"
                output.append(f"  • {t['symbol']}: -${abs(t['realizedPnl']):,.2f} ({hold_time})")
        
        return "\n".join(output) 