#!/usr/bin/env python3
"""
harsh_insights.py - Brutal honesty about your trading

No fluff. No "consider" or "perhaps". Just facts that hurt and fixes that work.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any
import duckdb

class HarshTruthGenerator:
    """Generate insights that actually change behavior."""
    
    def __init__(self, db_connection):
        self.db = db_connection
        
    def generate_all_insights(self) -> List[Dict[str, Any]]:
        """Generate all harsh insights from the data."""
        insights = []
        
        # Load the data
        pnl_df = self.db.execute("SELECT * FROM pnl").df()
        tx_df = self.db.execute("SELECT * FROM tx").df()
        
        if pnl_df.empty:
            return [{
                "type": "error",
                "title": "No Data",
                "message": "Load some wallet data first.",
                "severity": "info"
            }]
        
        # Calculate position sizes in USD
        pnl_df['entry_size_usd'] = pnl_df['totalBought'] * pnl_df['avgBuyPrice']
        pnl_df['exit_size_usd'] = pnl_df['totalSold'] * pnl_df['avgSellPrice']
        
        # 1. Position Size Analysis - NEW!
        position_size = self._analyze_position_sizes(pnl_df)
        if position_size:
            insights.append(position_size)
        
        # 2. Bag Holder Analysis
        bag_holder = self._analyze_bag_holding(pnl_df)
        if bag_holder:
            insights.append(bag_holder)
            
        # 3. Hold Time Sweet Spot
        hold_time = self._analyze_hold_time_buckets(pnl_df)
        if hold_time:
            insights.append(hold_time)
            
        # 4. Gambling Addiction Check
        gambling = self._analyze_gambling_behavior(pnl_df)
        if gambling:
            insights.append(gambling)
            
        # 5. Shitcoin Degen Analysis
        shitcoin = self._analyze_shitcoin_addiction(pnl_df)
        if shitcoin:
            insights.append(shitcoin)
            
        # 6. Swap Frequency Impact
        swap_impact = self._analyze_swap_frequency(pnl_df)
        if swap_impact:
            insights.append(swap_impact)
            
        # 7. Win Rate Reality Check
        win_rate = self._analyze_win_rate(pnl_df)
        if win_rate:
            insights.append(win_rate)
            
        # 8. Biggest Disasters
        disasters = self._analyze_disasters(pnl_df)
        if disasters:
            insights.append(disasters)
            
        return insights
    
    def _analyze_position_sizes(self, pnl_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze profitability by position size."""
        # Filter out invalid entries
        valid_df = pnl_df[pnl_df['entry_size_usd'] > 0].copy()
        
        if len(valid_df) < 20:
            return None
            
        # Create position size buckets
        valid_df['size_bucket'] = pd.cut(
            valid_df['entry_size_usd'],
            bins=[0, 100, 500, 1000, 5000, 10000, 50000, float('inf')],
            labels=['<$100', '$100-500', '$500-1K', '$1K-5K', '$5K-10K', '$10K-50K', '>$50K']
        )
        
        # Analyze by bucket
        bucket_stats = valid_df.groupby('size_bucket').agg({
            'realizedPnl': ['sum', 'mean', 'count'],
            'symbol': 'count'
        })
        
        # Calculate win rates by bucket
        bucket_win_rates = valid_df.groupby('size_bucket').apply(
            lambda x: (x['realizedPnl'] > 0).sum() / len(x) * 100
        )
        
        # Find best and worst buckets
        total_by_bucket = bucket_stats[('realizedPnl', 'sum')]
        best_bucket = total_by_bucket.idxmax() if total_by_bucket.max() > 0 else None
        worst_bucket = total_by_bucket.idxmin() if total_by_bucket.min() < 0 else None
        
        if not best_bucket or not worst_bucket:
            return None
            
        # Get specific examples
        best_trades = valid_df[valid_df['size_bucket'] == best_bucket].nlargest(3, 'realizedPnl')
        worst_trades = valid_df[valid_df['size_bucket'] == worst_bucket].nsmallest(3, 'realizedPnl')
        
        return {
            "type": "position_sizing",
            "severity": "critical",
            "title": "💰 YOUR POSITION SIZE SWEET SPOT",
            "facts": [
                f"Best size range: {best_bucket} (Total P&L: ${total_by_bucket[best_bucket]:,.0f})",
                f"Worst size range: {worst_bucket} (Total P&L: ${total_by_bucket[worst_bucket]:,.0f})",
                f"{best_bucket} win rate: {bucket_win_rates[best_bucket]:.0f}%",
                f"{worst_bucket} win rate: {bucket_win_rates[worst_bucket]:.0f}%",
                f"You lose money on {sum(1 for x in total_by_bucket if x < 0)} out of {len(total_by_bucket)} size ranges"
            ],
            "cost": f"Wrong position sizing cost: ${abs(total_by_bucket[total_by_bucket < 0].sum()):,.0f}",
            "fix": f"Stick to {best_bucket} positions. Your {worst_bucket} trades are ego, not edge.",
            "examples": [f"{row['symbol']}: ${row['entry_size_usd']:,.0f} entry → ${row['realizedPnl']:+,.0f}" 
                        for _, row in best_trades.iterrows()]
        }
    
    def _analyze_hold_time_buckets(self, pnl_df: pd.DataFrame) -> Dict[str, Any]:
        """Find the optimal hold time window."""
        # Create hold time buckets
        pnl_df['hold_bucket'] = pd.cut(
            pnl_df['holdTimeSeconds'] / 60,  # Convert to minutes
            bins=[0, 10, 30, 120, 360, 1440, float('inf')],
            labels=['<10min', '10-30min', '30min-2hr', '2-6hr', '6-24hr', '>24hr']
        )
        
        # Analyze by bucket
        bucket_stats = pnl_df.groupby('hold_bucket').agg({
            'realizedPnl': ['sum', 'mean', 'count']
        })
        
        # Calculate win rates
        bucket_win_rates = pnl_df.groupby('hold_bucket').apply(
            lambda x: (x['realizedPnl'] > 0).sum() / len(x) * 100
        )
        
        # Find best performing bucket
        total_by_bucket = bucket_stats[('realizedPnl', 'sum')]
        best_bucket = total_by_bucket.idxmax()
        
        # Get stats for display
        stats = []
        for bucket in bucket_stats.index:
            count = bucket_stats.loc[bucket, ('realizedPnl', 'count')]
            total = total_by_bucket[bucket]
            win_rate = bucket_win_rates[bucket]
            stats.append(f"{bucket}: {win_rate:.0f}% win rate, ${total:,.0f} total ({count} trades)")
        
        return {
            "type": "timing",
            "severity": "high",
            "title": "⏰ YOUR PROFITABLE TIME WINDOW",
            "facts": stats,
            "cost": f"Trading outside {best_bucket}: ${abs(total_by_bucket[total_by_bucket < 0].sum()):,.0f} lost",
            "fix": f"Set alerts at the edges of {best_bucket}. That's your zone.",
            "examples": []
        }
    
    def _analyze_swap_frequency(self, pnl_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze impact of swap frequency on profitability."""
        # Create swap buckets
        pnl_df['swap_bucket'] = pd.cut(
            pnl_df['numSwaps'],
            bins=[0, 2, 5, 10, 20, float('inf')],
            labels=['1-2 swaps', '3-5 swaps', '6-10 swaps', '11-20 swaps', '20+ swaps']
        )
        
        # Analyze by bucket
        bucket_stats = pnl_df.groupby('swap_bucket').agg({
            'realizedPnl': ['sum', 'mean', 'count']
        })
        
        if len(bucket_stats) < 2:
            return None
            
        # Calculate win rates
        bucket_win_rates = pnl_df.groupby('swap_bucket').apply(
            lambda x: (x['realizedPnl'] > 0).sum() / len(x) * 100
        )
        
        # Find if overtrading hurts
        low_swap_pnl = pnl_df[pnl_df['numSwaps'] <= 5]['realizedPnl'].sum()
        high_swap_pnl = pnl_df[pnl_df['numSwaps'] > 5]['realizedPnl'].sum()
        
        if high_swap_pnl >= low_swap_pnl:
            return None  # More swaps aren't hurting
            
        # Get worst overtraded examples
        overtraded = pnl_df[pnl_df['numSwaps'] > 10].nsmallest(5, 'realizedPnl')
        
        return {
            "type": "behavioral",
            "severity": "high",
            "title": "🔄 OVERTRADING EACH POSITION",
            "facts": [
                f"Low swap (≤5) P&L: ${low_swap_pnl:,.0f}",
                f"High swap (>5) P&L: ${high_swap_pnl:,.0f}",
                f"Tokens with 10+ swaps: {len(pnl_df[pnl_df['numSwaps'] > 10])}",
                f"Average loss on 10+ swaps: ${pnl_df[pnl_df['numSwaps'] > 10]['realizedPnl'].mean():,.0f}",
                "The more you touch it, the more you lose"
            ],
            "cost": f"Overtrading cost: ${abs(high_swap_pnl):,.0f}",
            "fix": "Plan your trade, trade your plan. Max 3 adjustments.",
            "examples": [f"{row['symbol']}: {row['numSwaps']} swaps, lost ${abs(row['realizedPnl']):,.0f}" 
                        for _, row in overtraded.head(3).iterrows()]
        }
    
    def _analyze_bag_holding(self, pnl_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze if trader holds losers too long."""
        # Split winners and losers
        winners = pnl_df[pnl_df['realizedPnl'] > 0]
        losers = pnl_df[pnl_df['realizedPnl'] < 0]
        
        if len(winners) < 10 or len(losers) < 10:
            return None
            
        # Calculate average hold times
        avg_winner_hold = winners['holdTimeSeconds'].mean() / 3600  # hours
        avg_loser_hold = losers['holdTimeSeconds'].mean() / 3600
        
        if avg_loser_hold <= avg_winner_hold * 1.5:
            return None  # Not a significant pattern
            
        # Find the worst bag held
        worst_bags = losers.nlargest(5, 'holdTimeSeconds')
        worst_bag = worst_bags.iloc[0]
        
        # Calculate the cost
        extended_losses = losers[losers['holdTimeSeconds'] > winners['holdTimeSeconds'].mean()]
        bag_holding_cost = extended_losses['realizedPnl'].sum()
        
        return {
            "type": "behavioral",
            "severity": "critical",
            "title": "❌ YOUR WORST HABIT: Bag Holding",
            "facts": [
                f"You hold losers {avg_loser_hold/avg_winner_hold:.1f}x longer than winners",
                f"Average winner hold: {avg_winner_hold:.1f} hours",
                f"Average loser hold: {avg_loser_hold:.1f} hours",
                f"Worst bag: {worst_bag['symbol']} held for {worst_bag['holdTimeSeconds']/3600:.1f} hours, lost ${abs(worst_bag['realizedPnl']):,.0f}"
            ],
            "cost": f"This habit cost you ${abs(bag_holding_cost):,.0f}",
            "fix": "Set stop losses at -10%. When it hits, sell. No exceptions. No 'but maybe it'll recover'.",
            "examples": [f"{row['symbol']}: held {row['holdTimeSeconds']/3600:.1f}h, lost ${abs(row['realizedPnl']):,.0f}" 
                        for _, row in worst_bags.head(3).iterrows()]
        }
    
    def _analyze_gambling_behavior(self, pnl_df: pd.DataFrame) -> Dict[str, Any]:
        """Check if this is trading or gambling."""
        total_tokens = len(pnl_df)
        median_hold = pnl_df['holdTimeSeconds'].median() / 60  # minutes
        quick_trades = len(pnl_df[pnl_df['holdTimeSeconds'] < 600])  # < 10 min
        
        # Calculate daily rate (assuming data spans some period)
        # This is approximate without exact date ranges
        tokens_per_day = total_tokens / 30  # rough estimate
        
        if total_tokens < 100 or median_hold > 60:
            return None  # Not gambling pattern
            
        # Calculate quick trade performance
        quick_pnl = pnl_df[pnl_df['holdTimeSeconds'] < 600]['realizedPnl'].sum()
        quick_win_rate = len(pnl_df[(pnl_df['holdTimeSeconds'] < 600) & (pnl_df['realizedPnl'] > 0)]) / max(quick_trades, 1) * 100
        
        return {
            "type": "behavioral", 
            "severity": "critical",
            "title": "🎰 REALITY CHECK: You're Not Trading, You're Gambling",
            "facts": [
                f"{total_tokens} tokens traded (≈{tokens_per_day:.0f} per day)",
                f"Median hold time: {median_hold:.1f} minutes",
                f"{quick_trades} trades under 10 minutes ({quick_trades/total_tokens*100:.0f}%)",
                f"Quick trade P&L: ${quick_pnl:,.0f}",
                f"Quick trade win rate: {quick_win_rate:.0f}%"
            ],
            "cost": "Your broker loves you. Your wallet doesn't.",
            "fix": "Maximum 5 trades per day. Minimum 1 hour hold. If you can't explain why you're buying in one sentence, don't buy.",
            "examples": []
        }
    
    def _analyze_shitcoin_addiction(self, pnl_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze performance on low-cap shitcoins."""
        # Identify potential shitcoins by name patterns or losing heavily
        shitcoin_patterns = ['INU', 'DOGE', 'PEPE', 'MEME', 'MOON', 'ELON', 'SAFE', 'BABY', 'SHIB']
        
        # Find tokens matching patterns
        shitcoins = pnl_df[pnl_df['symbol'].str.upper().str.contains('|'.join(shitcoin_patterns), na=False)]
        
        # Also add heavy losers (lost > 50%)
        heavy_losers = pnl_df[pnl_df['realizedPnl'] < -1000]  # Arbitrary threshold
        
        # Combine
        degen_trades = pd.concat([shitcoins, heavy_losers]).drop_duplicates()
        
        if len(degen_trades) < 10:
            return None
            
        degen_pnl = degen_trades['realizedPnl'].sum()
        degen_win_rate = len(degen_trades[degen_trades['realizedPnl'] > 0]) / len(degen_trades) * 100
        
        # Find the worst ones
        worst_shitcoins = degen_trades.nsmallest(5, 'realizedPnl')
        
        return {
            "type": "selection",
            "severity": "high",
            "title": "💩 SHITCOIN ADDICTION DETECTED",
            "facts": [
                f"Degen trades: {len(degen_trades)} tokens",
                f"Total P&L on memecoins: ${degen_pnl:,.0f}",
                f"Memecoin win rate: {degen_win_rate:.0f}%",
                f"Money lit on fire: ${abs(degen_trades[degen_trades['realizedPnl'] < 0]['realizedPnl'].sum()):,.0f}"
            ],
            "cost": f"Shitcoins cost you ${abs(degen_pnl):,.0f}" if degen_pnl < 0 else f"Even a broken clock... +${degen_pnl:,.0f}",
            "fix": "If it has a dog, rocket, or 'safe' in the name, it's not safe. Stick to top 100 by market cap.",
            "examples": [f"{row['symbol']}: ${row['realizedPnl']:,.0f}" for _, row in worst_shitcoins.iterrows()]
        }
    
    def _analyze_win_rate(self, pnl_df: pd.DataFrame) -> Dict[str, Any]:
        """Brutal truth about win rate."""
        total = len(pnl_df)
        winners = len(pnl_df[pnl_df['realizedPnl'] > 0])
        win_rate = winners / total * 100
        
        if win_rate > 40:  # Decent win rate
            return None
            
        # Calculate what win rate means in money
        total_wins = pnl_df[pnl_df['realizedPnl'] > 0]['realizedPnl'].sum()
        total_losses = abs(pnl_df[pnl_df['realizedPnl'] < 0]['realizedPnl'].sum())
        avg_win = total_wins / max(winners, 1)
        avg_loss = total_losses / max(total - winners, 1)
        
        # Find patterns in losers
        losers = pnl_df[pnl_df['realizedPnl'] < 0]
        quick_losers = losers[losers['holdTimeSeconds'] < 600]
        
        return {
            "type": "performance",
            "severity": "critical",
            "title": f"📊 WIN RATE: {win_rate:.0f}% (Translation: You Lose 3 Out of 4 Times)",
            "facts": [
                f"Wins: {winners} / {total} trades",
                f"Average win: ${avg_win:,.0f}",
                f"Average loss: ${avg_loss:,.0f}",
                f"Win/Loss ratio: {avg_win/avg_loss:.2f}x" if avg_loss > 0 else "N/A",
                f"Quick losses (<10min): {len(quick_losers)} trades"
            ],
            "cost": f"Net result: ${total_wins - total_losses:,.0f}",
            "fix": "Stop trading everything that moves. Quality > Quantity. Better to miss 100 trades than lose 75.",
            "examples": []
        }
    
    def _analyze_disasters(self, pnl_df: pd.DataFrame) -> Dict[str, Any]:
        """Your biggest fuckups."""
        disasters = pnl_df.nsmallest(10, 'realizedPnl')
        
        if disasters['realizedPnl'].sum() > -5000:  # Not that bad
            return None
            
        total_disaster_loss = disasters['realizedPnl'].sum()
        
        # Find common patterns
        disaster_holds = disasters['holdTimeSeconds'].values
        avg_disaster_hold = np.mean(disaster_holds) / 3600
        
        # Add entry size analysis
        avg_disaster_entry = disasters['entry_size_usd'].mean()
        
        return {
            "type": "risk",
            "severity": "critical", 
            "title": "💀 YOUR BIGGEST DISASTERS",
            "facts": [
                f"Top 10 losses: ${total_disaster_loss:,.0f}",
                f"Worst single trade: {disasters.iloc[0]['symbol']} lost ${disasters.iloc[0]['realizedPnl']:,.0f}",
                f"Average disaster hold time: {avg_disaster_hold:.1f} hours",
                f"Average disaster entry size: ${avg_disaster_entry:,.0f}",
                f"These 10 trades wiped out profits from {min(50, len(pnl_df[pnl_df['realizedPnl'] > 0]))} winning trades"
            ],
            "cost": f"${abs(total_disaster_loss):,.0f} gone forever",
            "fix": "Position sizing: Never risk more than 2% per trade. Your worst loss should be -$500, not -$5000.",
            "examples": [f"{row['symbol']}: ${row['entry_size_usd']:,.0f} entry → ${row['realizedPnl']:,.0f} loss" 
                        for _, row in disasters.head(5).iterrows()]
        }


def format_insights_for_web(insights: List[Dict[str, Any]]) -> str:
    """Format insights for web display with color and emphasis."""
    output = []
    
    for insight in insights:
        severity_emoji = {"critical": "🚨", "high": "⚠️", "medium": "📊"}
        
        output.append(f"\n{severity_emoji.get(insight['severity'], '📌')} {insight['title']}")
        output.append("=" * 60)
        
        # Facts
        for fact in insight['facts']:
            output.append(f"   • {fact}")
        
        # Cost
        output.append(f"\n   💸 COST: {insight['cost']}")
        
        # Fix
        output.append(f"   ✅ THE FIX: {insight['fix']}")
        
        # Examples
        if insight['examples']:
            output.append("\n   📝 Examples:")
            for example in insight['examples']:
                output.append(f"      - {example}")
        
        output.append("")
    
    return "\n".join(output) 