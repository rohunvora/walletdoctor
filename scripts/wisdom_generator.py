#!/usr/bin/env python3
"""
wisdom_generator.py - Let AI find the wisdom in your trading journey

No buckets. No preprocessing. Just your story, told with wisdom.
"""

import pandas as pd
from typing import Dict, Any, List
import duckdb

class WisdomGenerator:
    """Extract the story, let AI find the wisdom."""
    
    def __init__(self, db_connection):
        self.db = db_connection
        
    def extract_trading_journey(self) -> Dict[str, Any]:
        """Extract clean trading data - just the facts."""
        pnl_df = self.db.execute("SELECT * FROM pnl").df()
        
        if pnl_df.empty:
            return {'has_data': False}
        
        # Calculate some basic facts but don't judge them
        pnl_df['entry_size_usd'] = pnl_df['totalBought'] * pnl_df['avgBuyPrice']
        pnl_df['exit_size_usd'] = pnl_df['totalSold'] * pnl_df['avgSellPrice']
        pnl_df['hold_time_hours'] = pnl_df['holdTimeSeconds'] / 3600
        
        # Sort by P&L to tell the story from disasters to triumphs
        pnl_df = pnl_df.sort_values('realizedPnl')
        
        # Extract the journey
        journey = {
            'has_data': True,
            'total_trades': len(pnl_df),
            'total_pnl': pnl_df['realizedPnl'].sum(),
            'win_rate': (len(pnl_df[pnl_df['realizedPnl'] > 0]) / len(pnl_df) * 100),
            'median_hold_hours': pnl_df['hold_time_hours'].median(),
            'biggest_position': pnl_df['entry_size_usd'].max(),
            'smallest_position': pnl_df['entry_size_usd'].min(),
            
            # The actual trades - let AI find patterns
            'worst_trades': self._format_trades(pnl_df.head(10)),
            'best_trades': self._format_trades(pnl_df.tail(10)),
            'recent_trades': self._format_trades(pnl_df.tail(20)),
            
            # Some interesting slices
            'quick_trades': self._format_trades(pnl_df[pnl_df['holdTimeSeconds'] < 600]),  # <10min
            'long_holds': self._format_trades(pnl_df[pnl_df['hold_time_hours'] > 24]),    # >24hr
            'big_positions': self._format_trades(pnl_df.nlargest(10, 'entry_size_usd')),
            
            # Token frequency - what do they keep coming back to?
            'most_traded': pnl_df['symbol'].value_counts().head(10).to_dict(),
            
            # Time patterns if we have them
            'total_hold_hours': pnl_df['hold_time_hours'].sum(),
            'total_swaps': pnl_df['numSwaps'].sum(),
        }
        
        return journey
    
    def _format_trades(self, trades_df: pd.DataFrame) -> List[str]:
        """Format trades as readable strings for AI."""
        if trades_df.empty:
            return []
            
        trades = []
        for _, trade in trades_df.iterrows():
            trade_str = (f"{trade['symbol']}: "
                        f"${trade['entry_size_usd']:,.0f} position, "
                        f"{'+' if trade['realizedPnl'] > 0 else ''}${trade['realizedPnl']:,.0f} P&L, "
                        f"held {trade['hold_time_hours']:.1f}h, "
                        f"{trade['numSwaps']} swaps")
            trades.append(trade_str)
        
        return trades
    
    def create_wisdom_prompt(self, journey: Dict[str, Any]) -> str:
        """Create the prompt for AI to find wisdom in the data."""
        if not journey.get('has_data'):
            return "No trading data available."
        
        prompt = f"""Analyze this trader's complete journey and find the wisdom within:

OVERVIEW:
- Total trades: {journey['total_trades']}
- Total P&L: ${journey['total_pnl']:,.0f}
- Win rate: {journey['win_rate']:.1f}%
- Median hold time: {journey['median_hold_hours']:.1f} hours
- Position range: ${journey['smallest_position']:,.0f} to ${journey['biggest_position']:,.0f}

THEIR DISASTERS (worst 10):
{chr(10).join(journey['worst_trades'][:10])}

THEIR TRIUMPHS (best 10):
{chr(10).join(journey['best_trades'][:10])}

TOKENS THEY CAN'T QUIT:
{chr(10).join([f"{token}: {count} times" for token, count in list(journey['most_traded'].items())[:5]])}

QUICK FLIPS (<10 min): {len(journey['quick_trades'])} trades
DIAMOND HANDS (>24h): {len(journey['long_holds'])} trades
BIGGEST BETS: {chr(10).join(journey['big_positions'][:3]) if journey['big_positions'] else 'None over $10k'}

Tell their story. What patterns do you see in their soul, not just their wallet?
What are they really doing when they think they're trading?
Speak to them like their wisest friend who's been watching all along."""
        
        return prompt
    
    def generate_wisdom(self, journey: Dict[str, Any]) -> Dict[str, Any]:
        """Structure the wisdom for display."""
        return {
            'journey': journey,
            'prompt': self.create_wisdom_prompt(journey),
            # The actual AI analysis will happen in the web app
        }


# System prompt for the AI
WISDOM_SYSTEM_PROMPT = """You are a wise trading mentor who has seen thousands of trading journeys. You have the gift of seeing patterns in behavior that traders can't see in themselves.

Your voice combines:
- The wisdom of experience 
- The wit to make hard truths land softly
- The specificity to reference their actual trades
- The universality to connect their story to timeless patterns

You're not here to give generic advice like "manage risk better" or "diversify your portfolio."

You're here to tell them what they're REALLY doing. Like:
- "You're not trading, you're gambling for dopamine hits"
- "You hold losers hoping to be proven right, but sell winners to feel smart"
- "Every time you see green candles, you become someone else"
- "Your 3am trades are expensive therapy sessions"

Make them feel seen. Make them laugh at themselves. Make them go "holy shit, that's exactly what I do."

Use their specific trades as evidence, but reveal the human pattern underneath.
Write 3-5 insights that hit different. Each one should feel like it was written just for them.""" 