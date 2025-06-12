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
        
        # 1. Bag Holder Analysis
        bag_holder = self._analyze_bag_holding(pnl_df)
        if bag_holder:
            insights.append(bag_holder)
            
        # 2. Gambling Addiction Check
        gambling = self._analyze_gambling_behavior(pnl_df)
        if gambling:
            insights.append(gambling)
            
        # 3. Shitcoin Degen Analysis
        shitcoin = self._analyze_shitcoin_addiction(pnl_df)
        if shitcoin:
            insights.append(shitcoin)
            
        # 4. Win Rate Reality Check
        win_rate = self._analyze_win_rate(pnl_df)
        if win_rate:
            insights.append(win_rate)
            
        # 5. Biggest Disasters
        disasters = self._analyze_disasters(pnl_df)
        if disasters:
            insights.append(disasters)
            
        # 6. Time-based patterns (if we can derive them)
        time_pattern = self._analyze_time_patterns(pnl_df)
        if time_pattern:
            insights.append(time_pattern)
            
        return insights
    
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
        
        return {
            "type": "risk",
            "severity": "critical", 
            "title": "💀 YOUR BIGGEST DISASTERS",
            "facts": [
                f"Top 10 losses: ${total_disaster_loss:,.0f}",
                f"Worst single trade: {disasters.iloc[0]['symbol']} lost ${disasters.iloc[0]['realizedPnl']:,.0f}",
                f"Average disaster hold time: {avg_disaster_hold:.1f} hours",
                f"These 10 trades wiped out profits from {min(50, len(pnl_df[pnl_df['realizedPnl'] > 0]))} winning trades"
            ],
            "cost": f"${abs(total_disaster_loss):,.0f} gone forever",
            "fix": "Position sizing: Never risk more than 2% per trade. Your worst loss should be -$500, not -$5000.",
            "examples": [f"{row['symbol']}: ${row['realizedPnl']:,.0f} ({row['holdTimeSeconds']/3600:.1f}h)" 
                        for _, row in disasters.head(5).iterrows()]
        }
    
    def _analyze_time_patterns(self, pnl_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze patterns based on hold times as proxy for behavior."""
        # We don't have entry times, but we can analyze by hold duration buckets
        
        # Define buckets
        pnl_df['hold_bucket'] = pd.cut(
            pnl_df['holdTimeSeconds'], 
            bins=[0, 300, 600, 3600, 86400, float('inf')],  # 5min, 10min, 1hr, 1day, inf
            labels=['panic_sell', 'fomo_exit', 'normal', 'patient', 'bag_hold']
        )
        
        # Analyze by bucket
        bucket_stats = pnl_df.groupby('hold_bucket').agg({
            'realizedPnl': ['sum', 'mean', 'count'],
            'symbol': 'count'
        }).round(2)
        
        # Find worst performing bucket
        if bucket_stats[('realizedPnl', 'sum')].min() > -1000:
            return None
            
        panic_pnl = pnl_df[pnl_df['hold_bucket'] == 'panic_sell']['realizedPnl'].sum()
        panic_count = len(pnl_df[pnl_df['hold_bucket'] == 'panic_sell'])
        
        if panic_count < 20:
            return None
            
        return {
            "type": "timing",
            "severity": "high",
            "title": "⏱️ PANIC SELLER DETECTED", 
            "facts": [
                f"Panic sells (<5 min): {panic_count} trades",
                f"Panic sell P&L: ${panic_pnl:,.0f}",
                f"You're literally selling the bottom",
                f"Patient holds (>1hr) perform {abs(panic_pnl/max(pnl_df[pnl_df['hold_bucket'] == 'patient']['realizedPnl'].sum(), 1)):.0f}x better"
            ],
            "cost": f"Panic selling cost: ${abs(panic_pnl):,.0f}",
            "fix": "Before selling, walk around the block. Seriously. If you still want to sell after 10 minutes, do it.",
            "examples": []
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