"""
Advanced Trading Pattern Detection

This module identifies complex, interconnected trading behaviors that reveal
deeper psychological and strategic issues in trading patterns.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import pandas as pd
import numpy as np


@dataclass
class PositionContext:
    """Complete context around a trading position"""
    # Basic position data
    token: str
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    position_size_usd: float
    
    # Bankroll context
    bankroll_at_entry: float
    position_pct_of_bankroll: float
    free_capital_after_entry: float
    concurrent_positions: int
    
    # Market context
    token_24h_volume: float
    token_market_cap: float
    market_sentiment_score: float  # -1 to 1
    btc_price_at_entry: float
    eth_price_at_entry: float
    
    # Exit context
    exit_reason: Optional[str]  # 'profit_target', 'stop_loss', 'need_capital', 'panic', 'rug'
    time_to_exit: Optional[float]  # in minutes
    subsequent_position: Optional[str]  # what they bought after selling
    time_to_next_position: Optional[float]  # how quickly they entered next trade
    
    # Performance context
    unrealized_high: float  # highest profit they saw
    unrealized_low: float  # biggest drawdown
    max_profit_given_up: float  # unrealized_high - exit_price
    panic_score: float  # 0-1, based on exit patterns


@dataclass
class LiquidityConstraint:
    """Identifies when trader was liquidity constrained"""
    timestamp: datetime
    free_capital: float
    total_bankroll: float
    utilization_rate: float
    positions_held: List[str]
    missed_opportunity: Optional[str]  # token that pumped while fully allocated
    forced_sale: Optional[Tuple[str, float]]  # (token_sold, loss_taken)


@dataclass
class BehavioralPattern:
    """Deep behavioral pattern with cascading effects"""
    pattern_type: str
    severity: float  # 0-1
    frequency: float  # occurrences per day
    cost_basis: float  # estimated USD impact
    
    # Pattern-specific data
    data: Dict
    
    # Cascading effects
    leads_to: List[str]  # other patterns this triggers
    triggered_by: List[str]  # patterns that cause this
    
    # Psychological indicators
    emotional_state: str  # 'fomo', 'panic', 'greed', 'fear', 'tilt'
    cognitive_bias: str  # 'confirmation', 'recency', 'anchoring', etc.


class AdvancedPatternDetector:
    """Detects complex, interconnected trading patterns"""
    
    def __init__(self, transactions_df: pd.DataFrame, prices_df: pd.DataFrame):
        self.tx_df = transactions_df
        self.prices_df = prices_df
        self.positions = self._build_position_contexts()
        
    def _build_position_contexts(self) -> List[PositionContext]:
        """Build complete context for each position"""
        positions = []
        
        # Group by token and match buys/sells
        for token in self.tx_df['token_symbol'].unique():
            token_txs = self.tx_df[self.tx_df['token_symbol'] == token].sort_values('timestamp')
            
            # Match entries and exits
            entries = token_txs[token_txs['type'] == 'buy']
            exits = token_txs[token_txs['type'] == 'sell']
            
            for _, entry in entries.iterrows():
                # Find corresponding exit
                exit_candidates = exits[exits['timestamp'] > entry['timestamp']]
                exit_tx = exit_candidates.iloc[0] if not exit_candidates.empty else None
                
                # Calculate bankroll context
                bankroll = self._estimate_bankroll_at_time(entry['timestamp'])
                concurrent = self._count_concurrent_positions(entry['timestamp'])
                
                # Determine exit reason
                exit_reason = None
                if exit_tx is not None:
                    exit_reason = self._classify_exit_reason(entry, exit_tx, concurrent)
                
                position = PositionContext(
                    token=token,
                    entry_time=entry['timestamp'],
                    exit_time=exit_tx['timestamp'] if exit_tx is not None else None,
                    entry_price=entry['price'],
                    exit_price=exit_tx['price'] if exit_tx is not None else None,
                    position_size_usd=entry['amount_usd'],
                    bankroll_at_entry=bankroll,
                    position_pct_of_bankroll=entry['amount_usd'] / bankroll if bankroll > 0 else 0,
                    free_capital_after_entry=bankroll - entry['amount_usd'],
                    concurrent_positions=concurrent,
                    token_24h_volume=entry.get('volume_24h', 0),
                    token_market_cap=entry.get('market_cap', 0),
                    market_sentiment_score=self._calculate_sentiment(entry['timestamp']),
                    btc_price_at_entry=self._get_btc_price(entry['timestamp']),
                    eth_price_at_entry=self._get_eth_price(entry['timestamp']),
                    exit_reason=exit_reason,
                    time_to_exit=(exit_tx['timestamp'] - entry['timestamp']).total_seconds() / 60 if exit_tx is not None else None,
                    subsequent_position=self._find_next_position(exit_tx['timestamp']) if exit_tx is not None else None,
                    time_to_next_position=self._time_to_next_trade(exit_tx['timestamp']) if exit_tx is not None else None,
                    unrealized_high=self._calculate_unrealized_high(entry, exit_tx),
                    unrealized_low=self._calculate_unrealized_low(entry, exit_tx),
                    max_profit_given_up=self._calculate_profit_given_up(entry, exit_tx),
                    panic_score=self._calculate_panic_score(entry, exit_tx, exit_reason)
                )
                
                positions.append(position)
                
        return positions
    
    def detect_oversizing_cascade(self) -> List[BehavioralPattern]:
        """Detect the oversizing → forced selling → poor decisions cascade"""
        patterns = []
        
        # Find positions that were oversized
        oversized_positions = [p for p in self.positions if p.position_pct_of_bankroll > 0.25]
        
        for position in oversized_positions:
            # Check if this led to forced selling
            if position.exit_reason == 'need_capital' and position.exit_price < position.entry_price:
                # Check if they immediately aped into something else
                if position.time_to_next_position and position.time_to_next_position < 5:  # within 5 minutes
                    
                    cascade_data = {
                        'initial_oversize_pct': position.position_pct_of_bankroll * 100,
                        'forced_loss_pct': ((position.exit_price - position.entry_price) / position.entry_price) * 100,
                        'panic_ape_token': position.subsequent_position,
                        'time_between_trades': position.time_to_next_position,
                        'free_capital_at_exit': position.free_capital_after_entry + (position.exit_price * position.position_size_usd / position.entry_price)
                    }
                    
                    pattern = BehavioralPattern(
                        pattern_type='oversizing_cascade',
                        severity=min(position.position_pct_of_bankroll * 2, 1.0),  # More severe as position size increases
                        frequency=self._calculate_pattern_frequency('oversizing_cascade'),
                        cost_basis=abs(position.exit_price - position.entry_price) * position.position_size_usd / position.entry_price,
                        data=cascade_data,
                        leads_to=['panic_selling', 'fomo_entry', 'revenge_trading'],
                        triggered_by=['greed', 'overconfidence', 'fomo'],
                        emotional_state='tilt',
                        cognitive_bias='overconfidence'
                    )
                    
                    patterns.append(pattern)
        
        return patterns
    
    def detect_liquidity_traps(self) -> List[LiquidityConstraint]:
        """Identify times when trader was fully allocated and missed opportunities"""
        constraints = []
        
        # Calculate capital utilization over time
        timestamps = sorted(self.tx_df['timestamp'].unique())
        
        for ts in timestamps:
            bankroll = self._estimate_bankroll_at_time(ts)
            allocated = self._calculate_allocated_capital(ts)
            utilization = allocated / bankroll if bankroll > 0 else 0
            
            if utilization > 0.9:  # Over 90% allocated
                # Check what pumped while they were fully allocated
                missed_pumps = self._find_missed_opportunities(ts, ts + pd.Timedelta(hours=1))
                
                # Check if they panic sold to free up capital
                forced_sale = self._detect_forced_sale(ts, ts + pd.Timedelta(minutes=30))
                
                constraint = LiquidityConstraint(
                    timestamp=ts,
                    free_capital=bankroll - allocated,
                    total_bankroll=bankroll,
                    utilization_rate=utilization,
                    positions_held=self._get_positions_at_time(ts),
                    missed_opportunity=missed_pumps[0] if missed_pumps else None,
                    forced_sale=forced_sale
                )
                
                constraints.append(constraint)
        
        return constraints
    
    def detect_psychological_spirals(self) -> List[BehavioralPattern]:
        """Detect psychological spirals like tilt, revenge trading, etc."""
        patterns = []
        
        # Look for rapid-fire trades after losses
        for i, position in enumerate(self.positions[:-5]):  # Need at least 5 trades ahead
            if position.exit_price and position.exit_price < position.entry_price:  # Lost money
                # Check next 5 trades
                next_positions = self.positions[i+1:i+6]
                
                # Calculate metrics for spiral detection
                time_between_trades = [p.entry_time - self.positions[i+j].exit_time 
                                      for j, p in enumerate(next_positions) 
                                      if self.positions[i+j].exit_time]
                
                avg_time_between = np.mean([t.total_seconds() / 60 for t in time_between_trades if t])
                
                if avg_time_between < 10:  # Less than 10 minutes between trades
                    # This indicates tilt/revenge trading
                    subsequent_performance = sum([
                        (p.exit_price - p.entry_price) / p.entry_price 
                        for p in next_positions 
                        if p.exit_price
                    ])
                    
                    pattern = BehavioralPattern(
                        pattern_type='tilt_spiral',
                        severity=min(1.0, 5 / avg_time_between),  # More severe with faster trades
                        frequency=self._calculate_pattern_frequency('tilt_spiral'),
                        cost_basis=abs(subsequent_performance) * np.mean([p.position_size_usd for p in next_positions]),
                        data={
                            'trigger_loss': (position.exit_price - position.entry_price) / position.entry_price,
                            'trades_in_spiral': len(next_positions),
                            'avg_time_between': avg_time_between,
                            'spiral_performance': subsequent_performance
                        },
                        leads_to=['overtrading', 'poor_risk_management', 'account_blowup'],
                        triggered_by=['loss_aversion', 'emotional_trading', 'revenge_mindset'],
                        emotional_state='tilt',
                        cognitive_bias='loss_aversion'
                    )
                    
                    patterns.append(pattern)
        
        return patterns
    
    def generate_deep_insights(self) -> Dict:
        """Generate comprehensive insights about trading behavior"""
        
        # Detect all pattern types
        oversizing_cascades = self.detect_oversizing_cascade()
        liquidity_traps = self.detect_liquidity_traps()
        psychological_spirals = self.detect_psychological_spirals()
        
        # Calculate aggregate metrics
        avg_position_size = np.mean([p.position_pct_of_bankroll for p in self.positions])
        oversize_frequency = len([p for p in self.positions if p.position_pct_of_bankroll > 0.25]) / len(self.positions)
        
        # Build insight structure
        insights = {
            'position_sizing': {
                'avg_position_pct': avg_position_size * 100,
                'oversize_frequency': oversize_frequency * 100,
                'largest_position_pct': max([p.position_pct_of_bankroll for p in self.positions]) * 100,
                'optimal_position_size': self._calculate_kelly_criterion(),
                'sizing_discipline_score': self._calculate_sizing_discipline()
            },
            'liquidity_management': {
                'avg_utilization': np.mean([c.utilization_rate for c in liquidity_traps]) * 100,
                'liquidity_trap_count': len(liquidity_traps),
                'forced_sales_count': len([c for c in liquidity_traps if c.forced_sale]),
                'missed_opportunities': [c.missed_opportunity for c in liquidity_traps if c.missed_opportunity],
                'capital_efficiency_score': self._calculate_capital_efficiency()
            },
            'behavioral_patterns': {
                'oversizing_cascades': len(oversizing_cascades),
                'cascade_total_cost': sum([p.cost_basis for p in oversizing_cascades]),
                'tilt_episodes': len(psychological_spirals),
                'emotional_control_score': self._calculate_emotional_control(),
                'most_costly_pattern': max(oversizing_cascades + psychological_spirals, 
                                          key=lambda p: p.cost_basis).pattern_type if oversizing_cascades + psychological_spirals else None
            },
            'recommendations': self._generate_recommendations(oversizing_cascades, liquidity_traps, psychological_spirals)
        }
        
        return insights
    
    def _generate_recommendations(self, cascades, traps, spirals) -> List[Dict]:
        """Generate specific, actionable recommendations"""
        recommendations = []
        
        if cascades:
            avg_oversize = np.mean([p.data['initial_oversize_pct'] for p in cascades])
            recommendations.append({
                'issue': 'Position Oversizing',
                'severity': 'critical',
                'specific_problem': f'You average {avg_oversize:.1f}% of bankroll per position, leading to forced selling',
                'recommendation': 'Implement hard rule: Max 10% per position, 5% for low-cap tokens',
                'expected_improvement': 'Reduce forced sales by 80%, improve win rate by 15%'
            })
        
        if len(traps) > 5:
            recommendations.append({
                'issue': 'Capital Allocation',
                'severity': 'high',
                'specific_problem': f'Fully allocated {len(traps)} times, missing major opportunities',
                'recommendation': 'Always keep 30% cash reserve for opportunities',
                'expected_improvement': 'Capture 2-3 more winning trades per week'
            })
        
        if spirals:
            avg_spiral_cost = np.mean([p.cost_basis for p in spirals])
            recommendations.append({
                'issue': 'Emotional Trading',
                'severity': 'critical',
                'specific_problem': f'Tilt trading costs average ${avg_spiral_cost:.0f} per episode',
                'recommendation': 'Mandatory 30-min cooldown after any loss > 5%',
                'expected_improvement': 'Save ${avg_spiral_cost * len(spirals):.0f} per month'
            })
        
        return recommendations
    
    # Placeholder methods for calculations
    def _estimate_bankroll_at_time(self, timestamp): 
        # This would calculate total portfolio value at given time
        return 10000  # Placeholder
    
    def _count_concurrent_positions(self, timestamp):
        # Count open positions at timestamp
        return 5  # Placeholder
    
    def _classify_exit_reason(self, entry, exit, concurrent_positions):
        # Classify why the exit happened
        if concurrent_positions > 10 and exit['price'] < entry['price']:
            return 'need_capital'
        return 'profit_target'  # Placeholder
    
    def _calculate_sentiment(self, timestamp):
        # Market sentiment score
        return 0.5  # Placeholder
    
    def _get_btc_price(self, timestamp):
        return 50000  # Placeholder
    
    def _get_eth_price(self, timestamp):
        return 3000  # Placeholder
    
    def _find_next_position(self, timestamp):
        # Find what they bought next
        return "PEPE"  # Placeholder
    
    def _time_to_next_trade(self, timestamp):
        return 3.5  # Placeholder minutes
    
    def _calculate_unrealized_high(self, entry, exit):
        return entry['price'] * 1.5  # Placeholder
    
    def _calculate_unrealized_low(self, entry, exit):
        return entry['price'] * 0.8  # Placeholder
    
    def _calculate_profit_given_up(self, entry, exit):
        return 0.2  # Placeholder
    
    def _calculate_panic_score(self, entry, exit, exit_reason):
        if exit_reason == 'need_capital':
            return 0.8
        return 0.2  # Placeholder
    
    def _calculate_pattern_frequency(self, pattern_type):
        return 0.3  # Placeholder - times per day
    
    def _calculate_allocated_capital(self, timestamp):
        return 8000  # Placeholder
    
    def _get_positions_at_time(self, timestamp):
        return ["PEPE", "WOJAK", "TURBO"]  # Placeholder
    
    def _find_missed_opportunities(self, start, end):
        return ["BONK"]  # Placeholder
    
    def _detect_forced_sale(self, start, end):
        return ("PEPE", -500)  # Placeholder
    
    def _calculate_kelly_criterion(self):
        return 7.5  # Placeholder - optimal position size %
    
    def _calculate_sizing_discipline(self):
        return 0.3  # Placeholder - 0 to 1 score
    
    def _calculate_capital_efficiency(self):
        return 0.6  # Placeholder - 0 to 1 score
    
    def _calculate_emotional_control(self):
        return 0.4  # Placeholder - 0 to 1 score 