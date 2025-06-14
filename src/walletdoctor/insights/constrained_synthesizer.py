"""
Constrained Insight Synthesizer

Only makes claims that can be verified from the available data.
No speculation about what happened after trades or market movements we didn't observe.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
import pandas as pd


@dataclass
class VerifiableClaim:
    """A claim that can be verified from available data"""
    claim: str
    evidence: List[str]
    data_source: str  # Which data supports this


class ConstrainedSynthesizer:
    """Generates insights only from verifiable data"""
    
    def __init__(self):
        self.available_data = self._define_available_data()
        
    def _define_available_data(self) -> Dict[str, List[str]]:
        """Define what we can actually know from Cielo/Helius data"""
        
        return {
            "cielo_pnl": [
                "realized_pnl_per_token",
                "average_buy_price",
                "average_sell_price", 
                "total_bought_amount",
                "total_sold_amount",
                "hold_time_seconds",
                "number_of_swaps"
            ],
            "helius_tx": [
                "transaction_timestamps",
                "transaction_fees",
                "token_transfers",
                "wallet_interactions"
            ],
            "derived_metrics": [
                "win_rate",
                "average_hold_time",
                "position_sizes",
                "pnl_by_position_size",
                "hold_time_by_outcome",
                "trade_frequency"
            ]
        }
    
    def generate_verifiable_insights(self, data: Dict[str, Any]) -> List[VerifiableClaim]:
        """Generate only insights we can verify"""
        
        insights = []
        
        # Win rate - we can verify this
        if 'win_rate' in data:
            insights.append(VerifiableClaim(
                claim=f"You win on {data['win_rate']:.1f}% of your trades",
                evidence=[f"{data['winners']} winners out of {data['total_trades']} total trades"],
                data_source="realized_pnl"
            ))
        
        # Hold times - we can verify this
        if 'avg_hold_times' in data:
            winner_hold = data['avg_hold_times']['winners']
            loser_hold = data['avg_hold_times']['losers']
            
            if loser_hold > winner_hold:
                insights.append(VerifiableClaim(
                    claim=f"You hold losing positions {loser_hold/winner_hold:.1f}x longer than winning positions",
                    evidence=[
                        f"Winners held: {winner_hold:.1f} hours average",
                        f"Losers held: {loser_hold:.1f} hours average"
                    ],
                    data_source="hold_time_seconds"
                ))
        
        # Position sizing - we can verify this
        if 'position_size_performance' in data:
            size_data = data['position_size_performance']
            if size_data['large']['avg_pnl'] < size_data['small']['avg_pnl']:
                insights.append(VerifiableClaim(
                    claim="Your largest positions perform worse than smaller ones",
                    evidence=[
                        f"Large positions avg: ${size_data['large']['avg_pnl']:.2f}",
                        f"Small positions avg: ${size_data['small']['avg_pnl']:.2f}"
                    ],
                    data_source="position_size_analysis"
                ))
        
        # Quick trading - we can verify this
        if 'quick_flip_stats' in data:
            qf = data['quick_flip_stats']
            insights.append(VerifiableClaim(
                claim=f"{qf['percentage']:.0f}% of your trades are held less than 1 hour",
                evidence=[
                    f"{qf['count']} trades under 1 hour",
                    f"Quick flip P&L: ${qf['total_pnl']:.2f}"
                ],
                data_source="hold_time_seconds"
            ))
        
        return insights
    
    def generate_constrained_prompt(self, verifiable_claims: List[VerifiableClaim], 
                                  raw_stats: Dict[str, Any]) -> str:
        """Generate a prompt that constrains the AI to only use verifiable data"""
        
        prompt = f"""Write a sharp, psychologically insightful analysis of this trader's behavior.

IMPORTANT CONSTRAINTS:
- Only make claims supported by the data below
- Do NOT speculate about:
  * What happened to tokens after they sold
  * Whether they "cut winners early" (we don't know future prices)
  * Market conditions at time of trade
  * Their emotional state (unless clearly indicated by behavior)
  * Why they entered trades (we only know outcomes)

VERIFIABLE FACTS:
{json.dumps([{
    'fact': claim.claim,
    'evidence': claim.evidence
} for claim in verifiable_claims], indent=2)}

RAW STATS:
- Total P&L: ${raw_stats.get('total_pnl', 0):,.2f}
- Total Trades: {raw_stats.get('total_trades', 0)}
- Time Period: {raw_stats.get('period_days', 30)} days

WHAT YOU CAN DISCUSS:
1. Their actual win rate and what it means
2. The fact they hold losers longer (not why)
3. Position sizing patterns and outcomes
4. Trading frequency and its correlation with results
5. Specific examples from their trades

Write an insight that:
- Starts with a specific behavior they'll recognize
- Explains what the data shows (not what might have happened)
- Identifies patterns without assuming causation
- Suggests one concrete change based on the data
- Asks questions they can answer (not rhetorical ones)

Remember: If the data doesn't show it, don't say it."""
        
        return prompt
    
    def extract_verifiable_stats(self, pnl_df, patterns) -> Dict[str, Any]:
        """Extract only stats we can verify"""
        
        winners = pnl_df[pnl_df['realizedPnl'] > 0]
        losers = pnl_df[pnl_df['realizedPnl'] < 0]
        
        # Position size analysis
        pnl_df['size_quartile'] = pd.qcut(pnl_df['totalBought'], q=4, labels=['Small', 'Medium', 'Large', 'Huge'])
        size_perf = pnl_df.groupby('size_quartile')['realizedPnl'].agg(['mean', 'count'])
        
        # Quick flips
        quick_flips = pnl_df[pnl_df['holdTimeSeconds'] < 3600]
        
        return {
            'total_pnl': pnl_df['realizedPnl'].sum(),
            'total_trades': len(pnl_df),
            'winners': len(winners),
            'win_rate': len(winners) / len(pnl_df) * 100 if len(pnl_df) > 0 else 0,
            'avg_hold_times': {
                'winners': winners['holdTimeSeconds'].mean() / 3600 if len(winners) > 0 else 0,
                'losers': losers['holdTimeSeconds'].mean() / 3600 if len(losers) > 0 else 0
            },
            'position_size_performance': {
                'small': {
                    'avg_pnl': size_perf.loc['Small', 'mean'],
                    'count': size_perf.loc['Small', 'count']
                },
                'large': {
                    'avg_pnl': size_perf.loc['Huge', 'mean'], 
                    'count': size_perf.loc['Huge', 'count']
                }
            },
            'quick_flip_stats': {
                'count': len(quick_flips),
                'percentage': len(quick_flips) / len(pnl_df) * 100,
                'total_pnl': quick_flips['realizedPnl'].sum()
            }
        }


# Example of constrained output
def example_constrained_insight():
    """Show what a properly constrained insight looks like"""
    
    return """
You made 847 trades in 30 days. That's 28 trades per day.

Here's what actually happened:
- 73% of those trades lost money
- You held losers 4.2x longer than winners (9.7 hours vs 2.3 hours)
- Your biggest positions lost 3x more than your smallest ones

I can't tell you if you "cut winners too early" - I don't know what happened 
to those tokens after you sold. But I can tell you that holding losers 4x longer 
than winners is a pattern that's costing you money.

The data shows position size matters: your large positions average -$1,235 per trade 
while small positions average -$287. That's not speculation - that's your actual results.

One change: Cap position size at $5,000 until your win rate improves.

Questions only you can answer:
• Why do you hold losers so much longer?
• What makes you size up on certain trades?
• Would you take the same trades with smaller size?
""" 