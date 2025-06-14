#!/usr/bin/env python3
"""
trade_comparison.py - "You vs You" trade comparison engine

Detects new trades and compares them to your personal trading history.
No external benchmarks, just your own patterns.
"""

import pandas as pd
import duckdb
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, timedelta


class TradeComparator:
    """Compare new trades against personal trading history."""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def detect_new_trades(self, force_check: bool = False) -> List[Dict[str, Any]]:
        """Detect trades added since last check."""
        # Get last tracking info
        tracking = self.db.execute("""
            SELECT last_signature, last_check_timestamp 
            FROM new_trades_tracking 
            ORDER BY tracking_id DESC 
            LIMIT 1
        """).fetchone()
        
        if not tracking or force_check:
            # First time or forced - consider all trades "new" for demo
            # In production, would track properly
            all_trades = self.db.execute("""
                SELECT * FROM pnl 
                ORDER BY mint DESC 
                LIMIT 5
            """).df()
            
            if all_trades.empty:
                return []
            
            # Convert to list of dicts
            new_trades = all_trades.to_dict('records')
            
            # Update tracking
            if not all_trades.empty:
                self.db.execute("""
                    INSERT INTO new_trades_tracking (last_signature, last_check_timestamp, trades_since_last_check)
                    VALUES (?, CURRENT_TIMESTAMP, ?)
                """, [all_trades.iloc[0]['mint'], len(new_trades)])
            
            return new_trades
        
        # In production, would check for actual new trades
        # For MVP, simulate by returning recent trades
        return []
    
    def compare_to_personal_average(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        """Compare a trade to personal averages."""
        pnl_df = self.db.execute("SELECT * FROM pnl").df()
        
        if pnl_df.empty:
            return {
                'has_comparison': False,
                'message': 'First trade - no history to compare'
            }
        
        # Calculate personal averages
        avg_pnl = pnl_df['realizedPnl'].mean()
        avg_win = pnl_df[pnl_df['realizedPnl'] > 0]['realizedPnl'].mean() if len(pnl_df[pnl_df['realizedPnl'] > 0]) > 0 else 0
        avg_loss = pnl_df[pnl_df['realizedPnl'] < 0]['realizedPnl'].mean() if len(pnl_df[pnl_df['realizedPnl'] < 0]) > 0 else 0
        
        # Calculate position size average
        pnl_df['entry_size_usd'] = pnl_df['totalBought'] * pnl_df['avgBuyPrice']
        avg_position_size = pnl_df['entry_size_usd'].mean()
        
        # Compare this trade
        trade_pnl = trade.get('realizedPnl', 0)
        trade_size = trade.get('totalBought', 0) * trade.get('avgBuyPrice', 0)
        
        comparison = {
            'has_comparison': True,
            'trade_pnl': trade_pnl,
            'avg_pnl': avg_pnl,
            'pnl_vs_avg': ((trade_pnl - avg_pnl) / abs(avg_pnl) * 100) if avg_pnl != 0 else 0,
            'size_vs_avg': ((trade_size - avg_position_size) / avg_position_size * 100) if avg_position_size != 0 else 0,
            'verdict': self._get_verdict(trade_pnl, avg_pnl, avg_win, avg_loss)
        }
        
        return comparison
    
    def find_similar_past_trades(
        self, 
        trade: Dict[str, Any], 
        similarity_criteria: List[str] = ['size', 'token']
    ) -> List[Dict[str, Any]]:
        """Find similar trades from history."""
        pnl_df = self.db.execute("SELECT * FROM pnl").df()
        
        if pnl_df.empty:
            return []
        
        # Calculate entry sizes
        pnl_df['entry_size_usd'] = pnl_df['totalBought'] * pnl_df['avgBuyPrice']
        trade_size = trade.get('totalBought', 0) * trade.get('avgBuyPrice', 0)
        
        similar_trades = pnl_df.copy()
        
        # Apply similarity filters
        if 'size' in similarity_criteria and trade_size > 0:
            # Find trades within 50% size range
            size_min = trade_size * 0.5
            size_max = trade_size * 1.5
            similar_trades = similar_trades[
                (similar_trades['entry_size_usd'] >= size_min) & 
                (similar_trades['entry_size_usd'] <= size_max)
            ]
        
        if 'token' in similarity_criteria:
            # Same token or similar patterns (e.g., all memecoins)
            token_symbol = trade.get('symbol', '').upper()
            if token_symbol:
                # Exact match
                exact_matches = similar_trades[similar_trades['symbol'] == token_symbol]
                if len(exact_matches) > 0:
                    similar_trades = exact_matches
                else:
                    # Pattern match (memecoin detection)
                    if any(pattern in token_symbol for pattern in ['INU', 'DOGE', 'PEPE', 'MOON']):
                        pattern_matches = similar_trades[
                            similar_trades['symbol'].str.contains('INU|DOGE|PEPE|MOON', case=False, na=False)
                        ]
                        if len(pattern_matches) > 0:
                            similar_trades = pattern_matches
        
        # Sort by relevance (could be more sophisticated)
        similar_trades = similar_trades.sort_values('realizedPnl', ascending=False)
        
        # Return top 5 most similar
        return similar_trades.head(5).to_dict('records')
    
    def generate_comparison_insight(
        self, 
        trade: Dict[str, Any],
        comparison: Dict[str, Any],
        similar_trades: List[Dict[str, Any]]
    ) -> str:
        """Generate actionable insight from comparisons."""
        insights = []
        
        # Header
        symbol = trade.get('symbol', 'Unknown')
        pnl = trade.get('realizedPnl', 0)
        insights.append(f"📊 {symbol}: ${pnl:+,.2f}")
        
        # Comparison to average
        if comparison.get('has_comparison'):
            verdict = comparison.get('verdict', '')
            pnl_diff = comparison.get('pnl_vs_avg', 0)
            
            if pnl > 0:
                if pnl_diff > 50:
                    insights.append(f"✨ {abs(pnl_diff):.0f}% better than your average win!")
                elif pnl_diff > 0:
                    insights.append(f"✅ Solid win, {abs(pnl_diff):.0f}% above average")
                else:
                    insights.append(f"📉 Below your typical win by {abs(pnl_diff):.0f}%")
            else:
                if pnl_diff < -50:
                    insights.append(f"🚨 {abs(pnl_diff):.0f}% worse than your average loss")
                elif pnl_diff < 0:
                    insights.append(f"⚠️ Bigger loss than usual by {abs(pnl_diff):.0f}%")
                else:
                    insights.append(f"🔄 Smaller loss than typical")
        
        # Similar trades pattern
        if similar_trades:
            wins = [t for t in similar_trades if t['realizedPnl'] > 0]
            losses = [t for t in similar_trades if t['realizedPnl'] < 0]
            
            if len(similar_trades) >= 3:
                win_rate = len(wins) / len(similar_trades) * 100
                avg_similar_pnl = sum(t['realizedPnl'] for t in similar_trades) / len(similar_trades)
                
                insights.append(f"\n📂 Similar trades: {win_rate:.0f}% win rate")
                insights.append(f"   Average outcome: ${avg_similar_pnl:+,.2f}")
                
                # Pattern detection
                if win_rate < 30:
                    insights.append("   ⚠️ Pattern: You usually lose on these")
                elif win_rate > 70:
                    insights.append("   ✅ Pattern: This is your sweet spot")
        
        return "\n".join(insights)
    
    def _get_verdict(self, trade_pnl: float, avg_pnl: float, avg_win: float, avg_loss: float) -> str:
        """Quick verdict on the trade."""
        if trade_pnl > 0:
            if trade_pnl > avg_win * 1.5:
                return "exceptional_win"
            elif trade_pnl > avg_win:
                return "good_win"
            else:
                return "below_average_win"
        else:
            if trade_pnl < avg_loss * 1.5:
                return "disaster"
            elif trade_pnl < avg_loss:
                return "bad_loss"
            else:
                return "manageable_loss"
    
    def create_similarity_buckets(self) -> Dict[str, pd.DataFrame]:
        """Pre-compute similarity buckets for faster lookup."""
        pnl_df = self.db.execute("SELECT * FROM pnl").df()
        
        if pnl_df.empty:
            return {}
        
        # Calculate entry sizes
        pnl_df['entry_size_usd'] = pnl_df['totalBought'] * pnl_df['avgBuyPrice']
        
        # Create size buckets
        buckets = {
            'micro': pnl_df[pnl_df['entry_size_usd'] < 100],
            'small': pnl_df[(pnl_df['entry_size_usd'] >= 100) & (pnl_df['entry_size_usd'] < 500)],
            'medium': pnl_df[(pnl_df['entry_size_usd'] >= 500) & (pnl_df['entry_size_usd'] < 2000)],
            'large': pnl_df[(pnl_df['entry_size_usd'] >= 2000) & (pnl_df['entry_size_usd'] < 10000)],
            'whale': pnl_df[pnl_df['entry_size_usd'] >= 10000]
        }
        
        return buckets 