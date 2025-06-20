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
        
        prompt = f"""Looking at this trader's data, help them understand their patterns by asking thoughtful questions:

OVERVIEW:
- {journey['total_trades']} total trades
- ${journey['total_pnl']:,.0f} total P&L ({journey['win_rate']:.1f}% win rate)
- Typical position: ${journey['smallest_position']:,.0f} to ${journey['biggest_position']:,.0f}
- Typical hold: {journey['median_hold_hours']:.1f} hours

NOTABLE LOSSES:
{chr(10).join(journey['worst_trades'][:5])}

NOTABLE WINS:
{chr(10).join(journey['best_trades'][:5])}

FREQUENTLY TRADED:
{chr(10).join([f"{token}: {count} times" for token, count in list(journey['most_traded'].items())[:3]])}

Based on these patterns, generate 3-4 observations and questions that help them reflect on their trading. 
Focus on specific trades and patterns. Ask questions they can answer by adding notes to their trades."""
        
        return prompt
    
    def generate_wisdom(self, journey: Dict[str, Any]) -> Dict[str, Any]:
        """Structure the wisdom for display."""
        return {
            'journey': journey,
            'prompt': self.create_wisdom_prompt(journey),
            # The actual AI analysis will happen in the web app
        }


# System prompt for the AI
WISDOM_SYSTEM_PROMPT = """You are a trading analysis system reviewing wallet data. You can see WHAT happened but not WHY.

Your role is to:
1. Point out interesting patterns in their trades
2. Ask questions that help them reflect
3. Invite them to add context to their trades

DO NOT pretend to know:
- Why they entered trades
- What they were thinking
- Their emotional state
- Market conditions at the time

DO focus on:
- Observable patterns (hold times, position sizes, P&L)
- Specific trades worth examining
- Questions that prompt self-reflection

Example good insights:
- "Your BONK trade lost $3,200 after 47 hours. What was your plan when you entered?"
- "You have 6 trades with similar patterns - large positions held over 24h that lost money. What do these have in common?"
- "Your winning trades average 2.3 hours, losing trades average 31 hours. What makes you hold losers longer?"

Make them curious about their own behavior. Don't diagnose - invite exploration.""" 