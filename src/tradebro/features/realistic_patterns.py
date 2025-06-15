"""
Realistic Pattern Detection for Tradebro

This module detects behavioral patterns using actually available data from
Cielo and Helius APIs. Focuses on actionable insights we can deliver today.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


@dataclass
class TradingPattern:
    """A detected trading pattern with evidence and recommendations"""
    pattern_name: str
    severity: str  # 'critical', 'high', 'medium', 'low'
    description: str
    evidence: List[str]
    impact: str  # Quantified cost/impact
    recommendation: str
    confidence: float  # 0-1, how confident we are in this pattern


class RealisticPatternDetector:
    """Detects trading patterns from available Cielo/Helius data"""
    
    def __init__(self, pnl_df: pd.DataFrame, tx_df: pd.DataFrame = None):
        self.pnl_df = pnl_df
        self.tx_df = tx_df if tx_df is not None else pd.DataFrame()
        self.patterns = []
        
    def detect_all_patterns(self) -> List[TradingPattern]:
        """Run all pattern detection algorithms"""
        
        # Clear previous patterns
        self.patterns = []
        
        # Run each detector
        self._detect_disposition_effect()
        self._detect_size_discipline_issues()
        self._detect_overtrading()
        self._detect_fee_burn_problem()
        self._detect_quick_flip_addiction()
        self._detect_losing_streak_behavior()
        self._detect_winner_cutting()
        self._detect_portfolio_concentration()
        
        # Sort by severity
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        self.patterns.sort(key=lambda x: severity_order.get(x.severity, 4))
        
        return self.patterns
    
    def _detect_disposition_effect(self):
        """Detect if trader holds losers longer than winners"""
        
        if self.pnl_df.empty:
            return
            
        # Separate winners and losers
        winners = self.pnl_df[self.pnl_df['realizedPnl'] > 0]
        losers = self.pnl_df[self.pnl_df['realizedPnl'] < 0]
        
        if len(winners) > 5 and len(losers) > 5:
            # Calculate average hold times
            avg_winner_hold = winners['holdTimeSeconds'].mean() / 3600  # hours
            avg_loser_hold = losers['holdTimeSeconds'].mean() / 3600
            
            if avg_loser_hold > avg_winner_hold * 1.5:
                ratio = avg_loser_hold / avg_winner_hold
                
                # Calculate the cost of this behavior
                # Losers held too long likely got worse
                extended_losses = losers['realizedPnl'].sum() * 0.2  # Estimate 20% worse
                
                pattern = TradingPattern(
                    pattern_name="Disposition Effect",
                    severity="high" if ratio > 2 else "medium",
                    description=f"You hold losing positions {ratio:.1f}x longer than winners, hoping they'll recover",
                    evidence=[
                        f"Average winner hold: {avg_winner_hold:.1f} hours",
                        f"Average loser hold: {avg_loser_hold:.1f} hours",
                        f"Losers: {len(losers)} trades, Winners: {len(winners)} trades"
                    ],
                    impact=f"Estimated additional losses from holding too long: ${abs(extended_losses):.0f}",
                    recommendation="Set strict stop losses: -5% max. Take profits incrementally: 10% at +20%, 25% at +50%",
                    confidence=0.9
                )
                self.patterns.append(pattern)
    
    def _detect_size_discipline_issues(self):
        """Detect if position sizing correlates with poor performance"""
        
        if self.pnl_df.empty or 'totalBought' not in self.pnl_df.columns:
            return
            
        # Group by position size
        df = self.pnl_df.copy()
        df['position_size'] = df['totalBought']
        
        # Find size quartiles
        if len(df) > 10:
            df['size_quartile'] = pd.qcut(df['position_size'], q=4, labels=['Small', 'Medium', 'Large', 'Huge'])
            
            # Calculate win rate by size
            size_performance = df.groupby('size_quartile').agg({
                'realizedPnl': ['mean', 'sum', 'count'],
                'position_size': 'mean'
            })
            
            # Check if larger positions perform worse
            if len(size_performance) >= 3:
                large_perf = size_performance.loc['Large', ('realizedPnl', 'mean')]
                small_perf = size_performance.loc['Small', ('realizedPnl', 'mean')]
                
                if large_perf < small_perf * 0.5:  # Large positions do 50% worse
                    large_losses = size_performance.loc['Large', ('realizedPnl', 'sum')]
                    large_count = size_performance.loc['Large', ('realizedPnl', 'count')]
                    
                    pattern = TradingPattern(
                        pattern_name="Position Size Discipline",
                        severity="critical" if large_losses < -1000 else "high",
                        description="Your largest positions consistently underperform, suggesting emotional/FOMO entries",
                        evidence=[
                            f"Large position avg P&L: ${large_perf:.0f}",
                            f"Small position avg P&L: ${small_perf:.0f}",
                            f"Total loss on large positions: ${large_losses:.0f}",
                            f"Number of large positions: {large_count}"
                        ],
                        impact=f"Large positions cost you ${abs(large_losses):.0f} vs. sizing consistently",
                        recommendation="Max position size: 5% of portfolio. If you feel FOMO, cut size by 50%",
                        confidence=0.85
                    )
                    self.patterns.append(pattern)
    
    def _detect_overtrading(self):
        """Detect if trader makes too many trades"""
        
        if self.pnl_df.empty:
            return
            
        total_trades = len(self.pnl_df)
        
        # Estimate time period from hold times
        total_hold_seconds = self.pnl_df['holdTimeSeconds'].sum()
        avg_hold_days = (self.pnl_df['holdTimeSeconds'].mean() / 86400) if total_trades > 0 else 1
        
        # Rough estimate of trading period
        est_trading_days = max(30, total_hold_seconds / 86400 / 5)  # Assume 5 concurrent positions
        trades_per_day = total_trades / est_trading_days
        
        if trades_per_day > 10:
            # Calculate if overtrading hurts performance
            # More trades = more fees, worse decisions
            total_pnl = self.pnl_df['realizedPnl'].sum()
            avg_pnl_per_trade = total_pnl / total_trades if total_trades > 0 else 0
            
            # Estimate fee impact (assuming 0.1% per trade)
            est_fees = self.pnl_df['totalBought'].sum() * 0.001
            
            pattern = TradingPattern(
                pattern_name="Overtrading",
                severity="high" if trades_per_day > 20 else "medium",
                description=f"You're averaging {trades_per_day:.0f} trades per day - this is excessive and costly",
                evidence=[
                    f"Total trades analyzed: {total_trades}",
                    f"Average per trade: ${avg_pnl_per_trade:.0f}",
                    f"Estimated fees eating profits: ${est_fees:.0f}",
                    f"Win rate: {(len(self.pnl_df[self.pnl_df['realizedPnl'] > 0]) / total_trades * 100):.0f}%"
                ],
                impact=f"Overtrading costs ~${est_fees:.0f} in fees plus poor decision quality",
                recommendation="Limit to 5 high-conviction trades per day. Quality > Quantity",
                confidence=0.7
            )
            self.patterns.append(pattern)
    
    def _detect_fee_burn_problem(self):
        """Detect if fees are eating too much of profits"""
        
        if self.pnl_df.empty or self.tx_df.empty:
            return
            
        total_pnl = self.pnl_df['realizedPnl'].sum()
        total_volume = self.pnl_df['totalBought'].sum() + self.pnl_df['totalSold'].sum()
        
        # Estimate fees from transaction count and volume
        if 'fee' in self.tx_df.columns:
            total_fees = self.tx_df['fee'].sum()
        else:
            # Estimate: 0.1% of volume
            total_fees = total_volume * 0.001
        
        if total_pnl > 0 and total_fees > total_pnl * 0.3:
            fee_percentage = (total_fees / total_pnl * 100) if total_pnl > 0 else 100
            
            pattern = TradingPattern(
                pattern_name="Fee Burn",
                severity="critical" if fee_percentage > 50 else "high",
                description=f"Transaction fees are eating {fee_percentage:.0f}% of your profits",
                evidence=[
                    f"Total profits: ${total_pnl:.0f}",
                    f"Total fees: ${total_fees:.0f}",
                    f"Trading volume: ${total_volume:.0f}",
                    f"Average trade size: ${total_volume / (len(self.pnl_df) * 2):.0f}"
                ],
                impact=f"Fees reducing profits by ${total_fees:.0f}",
                recommendation="Focus on higher conviction trades. Minimum position: $1000. Hold longer.",
                confidence=0.9
            )
            self.patterns.append(pattern)
    
    def _detect_quick_flip_addiction(self):
        """Detect if trader flips positions too quickly"""
        
        if self.pnl_df.empty:
            return
            
        # Find very short holds
        quick_flips = self.pnl_df[self.pnl_df['holdTimeSeconds'] < 3600]  # Less than 1 hour
        
        if len(quick_flips) > len(self.pnl_df) * 0.3:  # 30%+ are quick flips
            quick_flip_pnl = quick_flips['realizedPnl'].sum()
            quick_flip_pct = len(quick_flips) / len(self.pnl_df) * 100
            avg_quick_pnl = quick_flips['realizedPnl'].mean()
            
            pattern = TradingPattern(
                pattern_name="Quick Flip Addiction",
                severity="high" if quick_flip_pnl < 0 else "medium",
                description=f"{quick_flip_pct:.0f}% of your trades are quick flips under 1 hour",
                evidence=[
                    f"Quick flips: {len(quick_flips)} trades",
                    f"Quick flip P&L: ${quick_flip_pnl:.0f}",
                    f"Average quick flip result: ${avg_quick_pnl:.0f}",
                    f"Success rate: {(len(quick_flips[quick_flips['realizedPnl'] > 0]) / len(quick_flips) * 100):.0f}%"
                ],
                impact=f"Quick flipping has cost you ${abs(quick_flip_pnl):.0f}" if quick_flip_pnl < 0 else f"Quick flips made ${quick_flip_pnl:.0f} but with high risk",
                recommendation="Minimum hold time: 4 hours. If tempted to flip, reduce position by 75%",
                confidence=0.85
            )
            self.patterns.append(pattern)
    
    def _detect_losing_streak_behavior(self):
        """Detect behavior changes during losing streaks"""
        
        if self.pnl_df.empty or len(self.pnl_df) < 20:
            return
            
        # Sort by some proxy for time (we don't have exact timestamps)
        df = self.pnl_df.copy()
        
        # Look for consecutive losers
        losing_streaks = []
        current_streak = []
        
        for _, row in df.iterrows():
            if row['realizedPnl'] < 0:
                current_streak.append(row)
            else:
                if len(current_streak) >= 3:
                    losing_streaks.append(current_streak)
                current_streak = []
        
        if losing_streaks:
            # Analyze the largest losing streak
            largest_streak = max(losing_streaks, key=len)
            streak_losses = sum(row['realizedPnl'] for row in largest_streak)
            streak_avg_size = np.mean([row['totalBought'] for row in largest_streak])
            
            # Check if position sizes increased during streak (revenge trading)
            sizes = [row['totalBought'] for row in largest_streak]
            if len(sizes) > 2 and sizes[-1] > sizes[0] * 1.5:
                pattern = TradingPattern(
                    pattern_name="Revenge Trading Pattern",
                    severity="critical",
                    description="You increase position sizes during losing streaks, trying to 'make it back'",
                    evidence=[
                        f"Longest losing streak: {len(largest_streak)} trades",
                        f"Total streak losses: ${abs(streak_losses):.0f}",
                        f"Position size increased {(sizes[-1] / sizes[0]):.1f}x during streak",
                        f"Average loss per revenge trade: ${abs(streak_losses / len(largest_streak)):.0f}"
                    ],
                    impact=f"Revenge trading amplified losses by ~${abs(streak_losses * 0.5):.0f}",
                    recommendation="After 2 losses: Take 24hr break. After 3 losses: Reduce size by 50%",
                    confidence=0.8
                )
                self.patterns.append(pattern)
    
    def _detect_winner_cutting(self):
        """Detect if trader cuts winners too early"""
        
        if self.pnl_df.empty:
            return
            
        winners = self.pnl_df[self.pnl_df['realizedPnl'] > 0]
        
        if len(winners) > 10:
            # Look at hold times for winners
            avg_winner_hold = winners['holdTimeSeconds'].mean() / 3600
            
            # Check if winners are cut very quickly
            quick_winners = winners[winners['holdTimeSeconds'] < 3600]  # Less than 1 hour
            
            if len(quick_winners) > len(winners) * 0.5:
                # Estimate missed profits (could have made 2x more)
                missed_profits = winners['realizedPnl'].sum() * 0.5
                
                pattern = TradingPattern(
                    pattern_name="Cutting Winners Too Early",
                    severity="high",
                    description="You're taking profits too quickly, missing larger moves",
                    evidence=[
                        f"Average winner hold: {avg_winner_hold:.1f} hours",
                        f"{len(quick_winners)} of {len(winners)} winners sold within 1 hour",
                        f"Total winner profits: ${winners['realizedPnl'].sum():.0f}",
                        f"Average winner: ${winners['realizedPnl'].mean():.0f}"
                    ],
                    impact=f"Estimated missed profits from cutting early: ${missed_profits:.0f}",
                    recommendation="Use trailing stops. Sell 25% at +20%, 25% at +50%, let rest run",
                    confidence=0.75
                )
                self.patterns.append(pattern)
    
    def _detect_portfolio_concentration(self):
        """Detect if trader puts too much into single tokens"""
        
        if self.pnl_df.empty:
            return
            
        # Look at largest positions by total bought
        df = self.pnl_df.copy()
        total_invested = df['totalBought'].sum()
        
        if total_invested > 0 and len(df) > 5:
            # Find concentration in top tokens
            top_5_invested = df.nlargest(5, 'totalBought')['totalBought'].sum()
            concentration = top_5_invested / total_invested
            
            if concentration > 0.7:  # 70%+ in top 5 tokens
                top_token = df.nlargest(1, 'totalBought').iloc[0]
                top_concentration = top_token['totalBought'] / total_invested
                
                pattern = TradingPattern(
                    pattern_name="Portfolio Concentration Risk",
                    severity="high" if top_concentration > 0.3 else "medium",
                    description=f"You're over-concentrated: {concentration*100:.0f}% of capital in just 5 tokens",
                    evidence=[
                        f"Top token ({top_token['symbol']}): {top_concentration*100:.0f}% of total",
                        f"Top 5 tokens: {concentration*100:.0f}% of total",
                        f"Total tokens traded: {len(df)}",
                        f"Result of top token: ${top_token['realizedPnl']:.0f}"
                    ],
                    impact=f"Concentration risk could amplify losses by {concentration*100:.0f}%",
                    recommendation="Max 10% in any single token. Diversify across 15-20 positions",
                    confidence=0.8
                )
                self.patterns.append(pattern)
    
    def generate_summary_insights(self) -> Dict:
        """Generate summary statistics and insights"""
        
        if self.pnl_df.empty:
            return {"error": "No data to analyze"}
        
        total_pnl = self.pnl_df['realizedPnl'].sum()
        total_trades = len(self.pnl_df)
        winners = len(self.pnl_df[self.pnl_df['realizedPnl'] > 0])
        win_rate = (winners / total_trades * 100) if total_trades > 0 else 0
        
        avg_winner = self.pnl_df[self.pnl_df['realizedPnl'] > 0]['realizedPnl'].mean() if winners > 0 else 0
        avg_loser = self.pnl_df[self.pnl_df['realizedPnl'] < 0]['realizedPnl'].mean() if winners < total_trades else 0
        
        return {
            'total_pnl': total_pnl,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_winner': avg_winner,
            'avg_loser': avg_loser,
            'profit_factor': abs(avg_winner / avg_loser) if avg_loser != 0 else 0,
            'patterns_detected': len(self.patterns),
            'critical_issues': len([p for p in self.patterns if p.severity == 'critical'])
        } 