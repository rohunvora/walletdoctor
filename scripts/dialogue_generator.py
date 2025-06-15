#!/usr/bin/env python3
"""
dialogue_generator.py - Create realistic dialogue between frustrated trader and coach

Forces specific insights without hallucination.
"""

import pandas as pd
from typing import Dict, Any, List, Tuple
import json

class DialogueGenerator:
    """Generate dialogue that extracts real insights."""
    
    def __init__(self, db_connection):
        self.db = db_connection
        
    def prepare_trade_data(self) -> Dict[str, Any]:
        """Prepare comprehensive trade data for the coach to reference."""
        pnl_df = self.db.execute("SELECT * FROM pnl").df()
        
        if pnl_df.empty:
            return {'has_data': False}
        
        # Calculate key fields
        pnl_df['entry_size_usd'] = pnl_df['totalBought'] * pnl_df['avgBuyPrice']
        pnl_df['hold_time_hours'] = pnl_df['holdTimeSeconds'] / 3600
        pnl_df['pnl_percent'] = (pnl_df['realizedPnl'] / pnl_df['entry_size_usd'] * 100).round(1)
        
        # Sort by time if possible (using mint as proxy)
        pnl_df = pnl_df.sort_values('mint')
        
        # Find patterns in consecutive trades
        pnl_df['prev_pnl'] = pnl_df['realizedPnl'].shift(1)
        pnl_df['prev_size'] = pnl_df['entry_size_usd'].shift(1)
        pnl_df['size_change'] = (pnl_df['entry_size_usd'] / pnl_df['prev_size']).round(2)
        
        # Extract clear patterns with specific examples
        patterns = {
            'revenge_trading': self._find_revenge_patterns(pnl_df),
            'size_patterns': self._find_size_patterns(pnl_df),
            'hold_patterns': self._find_hold_patterns(pnl_df),
            'streak_patterns': self._find_streak_patterns(pnl_df),
            'time_patterns': self._find_time_patterns(pnl_df)
        }
        
        # Format all trades for reference
        all_trades = []
        for _, trade in pnl_df.iterrows():
            all_trades.append({
                'symbol': trade['symbol'],
                'entry_size': f"${trade['entry_size_usd']:,.0f}",
                'pnl': f"${trade['realizedPnl']:+,.0f}",
                'pnl_percent': f"{trade['pnl_percent']:+.1f}%",
                'hold_hours': f"{trade['hold_time_hours']:.1f}h",
                'swaps': trade['numSwaps']
            })
        
        return {
            'has_data': True,
            'total_trades': len(pnl_df),
            'total_pnl': pnl_df['realizedPnl'].sum(),
            'patterns': patterns,
            'all_trades': all_trades,
            'summary_stats': {
                'avg_win': pnl_df[pnl_df['realizedPnl'] > 0]['realizedPnl'].mean(),
                'avg_loss': pnl_df[pnl_df['realizedPnl'] < 0]['realizedPnl'].mean(),
                'avg_position': pnl_df['entry_size_usd'].mean(),
                'win_rate': (len(pnl_df[pnl_df['realizedPnl'] > 0]) / len(pnl_df) * 100)
            }
        }
    
    def _find_revenge_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """Find specific instances of revenge trading."""
        patterns = []
        
        # Look for size increases after losses
        loss_followed_by_bigger = df[(df['prev_pnl'] < -100) & (df['size_change'] > 1.5)]
        
        for _, trade in loss_followed_by_bigger.iterrows():
            prev_idx = df.index[df.index.get_loc(trade.name) - 1]
            prev_trade = df.loc[prev_idx]
            
            patterns.append({
                'type': 'size_increase_after_loss',
                'sequence': [
                    f"{prev_trade['symbol']}: ${prev_trade['entry_size_usd']:,.0f} position → ${prev_trade['realizedPnl']:+,.0f} loss",
                    f"Next: {trade['symbol']}: ${trade['entry_size_usd']:,.0f} position ({trade['size_change']:.1f}x bigger) → ${trade['realizedPnl']:+,.0f}"
                ]
            })
        
        return patterns[:3]  # Top 3 examples
    
    def _find_size_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """Find patterns in position sizing."""
        patterns = []
        
        # Compare average sizes for wins vs losses
        wins = df[df['realizedPnl'] > 0]
        losses = df[df['realizedPnl'] < 0]
        
        if len(wins) > 5 and len(losses) > 5:
            avg_win_size = wins['entry_size_usd'].mean()
            avg_loss_size = losses['entry_size_usd'].mean()
            
            if avg_loss_size > avg_win_size * 1.3:
                # Find specific examples
                big_losses = losses.nlargest(3, 'entry_size_usd')
                examples = [f"{t['symbol']}: ${t['entry_size_usd']:,.0f} → ${t['realizedPnl']:,.0f}" 
                           for _, t in big_losses.iterrows()]
                
                patterns.append({
                    'type': 'bigger_positions_lose',
                    'avg_winning_size': f"${avg_win_size:,.0f}",
                    'avg_losing_size': f"${avg_loss_size:,.0f}",
                    'examples': examples
                })
        
        return patterns
    
    def _find_hold_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """Find patterns in hold times."""
        patterns = []
        
        # Compare hold times for wins vs losses
        wins = df[df['realizedPnl'] > 0]
        losses = df[df['realizedPnl'] < 0]
        
        if len(wins) > 5 and len(losses) > 5:
            avg_win_hold = wins['hold_time_hours'].mean()
            avg_loss_hold = losses['hold_time_hours'].mean()
            
            if avg_loss_hold > avg_win_hold * 2:
                # Find specific long-held losses
                long_losses = losses.nlargest(3, 'hold_time_hours')
                examples = [f"{t['symbol']}: held {t['hold_time_hours']:.1f}h → ${t['realizedPnl']:,.0f}" 
                           for _, t in long_losses.iterrows()]
                
                patterns.append({
                    'type': 'holding_losers_too_long',
                    'avg_win_hold': f"{avg_win_hold:.1f}h",
                    'avg_loss_hold': f"{avg_loss_hold:.1f}h",
                    'examples': examples
                })
        
        return patterns
    
    def _find_streak_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """Find winning/losing streaks."""
        patterns = []
        
        # Find consecutive losses
        df['is_loss'] = df['realizedPnl'] < 0
        df['loss_streak'] = (df['is_loss'] != df['is_loss'].shift()).cumsum()
        
        loss_streaks = df[df['is_loss']].groupby('loss_streak').agg({
            'symbol': 'count',
            'realizedPnl': 'sum',
            'entry_size_usd': 'mean'
        })
        
        # Find worst streak
        if len(loss_streaks) > 0:
            worst_streak = loss_streaks.nlargest(1, 'symbol').iloc[0]
            if worst_streak['symbol'] >= 3:  # At least 3 in a row
                streak_trades = df[df['loss_streak'] == loss_streaks.index[0]]
                
                patterns.append({
                    'type': 'loss_streak',
                    'count': int(worst_streak['symbol']),
                    'total_loss': f"${worst_streak['realizedPnl']:,.0f}",
                    'trades': [f"{t['symbol']}: ${t['realizedPnl']:,.0f}" 
                              for _, t in streak_trades.iterrows()]
                })
        
        return patterns
    
    def _find_time_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """Find patterns in timing."""
        patterns = []
        
        # Quick trades that lost money
        quick_losses = df[(df['holdTimeSeconds'] < 600) & (df['realizedPnl'] < -100)]
        
        if len(quick_losses) >= 3:
            examples = [f"{t['symbol']}: {t['holdTimeSeconds']/60:.0f}min → ${t['realizedPnl']:,.0f}" 
                       for _, t in quick_losses.head(3).iterrows()]
            
            patterns.append({
                'type': 'quick_flip_losses',
                'count': len(quick_losses),
                'total_loss': f"${quick_losses['realizedPnl'].sum():,.0f}",
                'examples': examples
            })
        
        return patterns


# Prompts for the dialogue system
WALLET_OWNER_PROMPT = """You are a frustrated trader who just received vague trading analysis.
You're tired of generic advice like "manage risk better" or "control emotions."

Your job is to push for SPECIFIC, ACTIONABLE insights by asking pointed questions.

DO NOT:
- Mention any specific trades, tokens, or amounts (you don't have the data)
- Accept vague patterns without examples
- Be satisfied with generic advice

DO:
- Demand specific examples: "Show me exactly when this happened"
- Ask for comparisons: "How is this different from my winning trades?"
- Push for actionable steps: "What specifically should I do differently?"
- Express frustration with vagueness: "That tells me nothing useful"

Example responses:
- "That's too vague. Give me actual examples from my trades where this pattern hurt me."
- "Everyone says 'control emotions' - show me specifically when emotions cost me money."
- "What does 'revenge trading' even look like in my actual history?"

Be genuinely frustrated but constructive. You want to improve but need real insights."""

COACH_FINAL_RESPONSE_PROMPT = """The trader is frustrated with vague insights and wants specifics.
You have access to their complete trading data with patterns already identified.

CRITICAL RULES:
1. ONLY use examples that exist in the provided data
2. Reference specific token names, amounts, and sequences
3. Show clear patterns with multiple examples
4. Compare winning vs losing behaviors with real trades
5. Never approximate or invent details

Structure your response:
1. Acknowledge their frustration
2. Provide 2-3 SPECIFIC patterns with real examples
3. Show the cost of each pattern in dollars
4. Give actionable rules based on their actual data

Example format:
"You're right to be frustrated. Here's exactly what's happening:

1. After losses, you double down: [specific examples with tokens and amounts]
2. Your winners vs losers: [specific comparison with real trades]
3. The pattern that's killing you: [specific sequence of actual trades]

This cost you $X. Here's the rule: [specific actionable step based on their data]"

Make it impossible for them to say it's vague by using their actual trade data."""

def create_dialogue_flow(trade_data: Dict[str, Any], initial_insight: str) -> List[Tuple[str, str]]:
    """Create the dialogue flow without hallucination."""
    dialogue = []
    
    # The wallet owner pushes back on the initial insight
    wallet_owner_response = "That's exactly the kind of generic advice I'm tired of. " \
                          "Show me SPECIFICALLY when and how this happened in my trades. " \
                          "Give me real examples, not philosophy."
    
    dialogue.append(("Wallet Owner", wallet_owner_response))
    
    # The coach must now provide specific examples
    coach_data_summary = json.dumps(trade_data, indent=2)
    
    # This is where the coach gives the final, specific response
    # The AI will be forced to use only the provided data
    
    return dialogue, coach_data_summary 