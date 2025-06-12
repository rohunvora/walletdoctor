#!/usr/bin/env python3
"""
blind_spots.py - Behavioral Pattern Detection with Statistical Validation

Core principle: Only report patterns we can prove with statistical confidence.
No guessing, no hallucination, just facts backed by data.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import duckdb

# Pattern detection requirements - strict thresholds for accuracy
PATTERN_REQUIREMENTS = {
    "min_sample_size": 30,      # Need at least 30 instances
    "confidence_level": 0.95,   # 95% confidence required
    "min_dollar_impact": 500,   # Must matter financially
    "min_relative_diff": 0.2    # 20% relative difference required
}


class BlindSpotDetector:
    """Detect behavioral patterns in trading data with statistical confidence."""
    
    def __init__(self, db_path: str = "coach.db"):
        """Initialize with database connection."""
        self.db = duckdb.connect(db_path, read_only=True)
        self.patterns_found = []
        
    def analyze_all_patterns(self, wallet_address: Optional[str] = None) -> List[Dict]:
        """Run all pattern detections and return confirmed patterns only."""
        # Load data
        pnl_df, tx_df = self._load_data(wallet_address)
        
        if pnl_df.empty or tx_df.empty:
            return [{
                "pattern": "Insufficient Data",
                "message": "Need at least 30 trades to detect behavioral patterns.",
                "recommendation": "Keep trading and check back later."
            }]
        
        # Run each pattern detector
        patterns = []
        
        # 1. FOMO vs Patience Pattern - simplest to implement accurately
        fomo_pattern = self._detect_fomo_pattern(pnl_df, tx_df)
        if fomo_pattern:
            patterns.append(fomo_pattern)
            
        # 2. Hold Bias Pattern
        hold_bias = self._detect_hold_bias(pnl_df)
        if hold_bias:
            patterns.append(hold_bias)
        
        return patterns if patterns else [{
            "pattern": "No Clear Patterns",
            "message": "Your trading shows no statistically significant behavioral patterns.",
            "recommendation": "Keep doing what you're doing!"
        }]
    
    def _load_data(self, wallet_address: Optional[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Load PnL and transaction data from database."""
        # Load PnL data
        pnl_query = "SELECT * FROM pnl"
        if wallet_address:
            pnl_query += f" WHERE wallet_address = '{wallet_address}'"
        pnl_df = self.db.execute(pnl_query).df()
        
        # Load transaction data
        tx_query = "SELECT * FROM tx"
        if wallet_address:
            tx_query += f" WHERE from_address = '{wallet_address}' OR to_address = '{wallet_address}'"
        tx_df = self.db.execute(tx_query).df()
        
        # Convert timestamps
        if 'timestamp' in tx_df.columns:
            tx_df['timestamp'] = pd.to_datetime(tx_df['timestamp'], unit='s')
            
        return pnl_df, tx_df
    
    def _detect_fomo_pattern(self, pnl_df: pd.DataFrame, tx_df: pd.DataFrame) -> Optional[Dict]:
        """Detect if quick trades perform worse than patient holds."""
        # Filter for closed positions with hold time data
        closed_trades = pnl_df[
            (pnl_df['realizedPnl'].notna()) & 
            (pnl_df['holdTimeSeconds'] > 0)
        ].copy()
        
        if len(closed_trades) < PATTERN_REQUIREMENTS['min_sample_size'] * 2:
            return None
            
        # Define quick trades (< 10 minutes) vs patient trades (> 1 hour)
        quick_trades = closed_trades[closed_trades['holdTimeSeconds'] < 600]  # 10 min
        patient_trades = closed_trades[closed_trades['holdTimeSeconds'] > 3600]  # 1 hour
        
        if len(quick_trades) < PATTERN_REQUIREMENTS['min_sample_size'] or \
           len(patient_trades) < PATTERN_REQUIREMENTS['min_sample_size']:
            return None
            
        # Calculate basic statistics
        avg_quick = quick_trades['realizedPnl'].mean()
        avg_patient = patient_trades['realizedPnl'].mean()
        std_quick = quick_trades['realizedPnl'].std()
        std_patient = patient_trades['realizedPnl'].std()
        
        # Simple difference test - is the difference meaningful?
        relative_diff = abs(avg_patient - avg_quick) / (abs(avg_quick) + 1)  # +1 to avoid division by zero
        
        # Calculate potential improvement
        potential_improvement = (avg_patient - avg_quick) * len(quick_trades)
        
        # Calculate confidence using bootstrap-like approach
        # Sample both groups many times and see how often patient > quick
        better_count = 0
        for _ in range(1000):
            sample_quick = np.random.choice(quick_trades['realizedPnl'].values, size=30, replace=True)
            sample_patient = np.random.choice(patient_trades['realizedPnl'].values, size=30, replace=True)
            if sample_patient.mean() > sample_quick.mean():
                better_count += 1
        
        confidence = better_count / 1000
        
        if (confidence > PATTERN_REQUIREMENTS['confidence_level'] and 
            relative_diff > PATTERN_REQUIREMENTS['min_relative_diff'] and
            potential_improvement > PATTERN_REQUIREMENTS['min_dollar_impact']):
            
            # Get example trades
            worst_quick_trades = quick_trades.nsmallest(5, 'realizedPnl')[['symbol', 'realizedPnl', 'holdTimeSeconds']]
            best_patient_trades = patient_trades.nlargest(5, 'realizedPnl')[['symbol', 'realizedPnl', 'holdTimeSeconds']]
            
            return {
                "pattern": "FOMO Trading Detected",
                "confidence": f"{confidence*100:.0f}%",
                "impact": f"${potential_improvement:,.0f} potential gain",
                "evidence": {
                    "quick_trades_count": len(quick_trades),
                    "patient_trades_count": len(patient_trades),
                    "avg_quick_pnl": f"${avg_quick:,.0f}",
                    "avg_patient_pnl": f"${avg_patient:,.0f}",
                    "quick_win_rate": f"{(quick_trades['realizedPnl'] > 0).mean()*100:.0f}%",
                    "patient_win_rate": f"{(patient_trades['realizedPnl'] > 0).mean()*100:.0f}%",
                    "worst_quick_trades": worst_quick_trades.to_dict('records'),
                    "best_patient_trades": best_patient_trades.to_dict('records')
                },
                "recommendation": f"Try holding positions for at least 1 hour. Your patient trades make ${avg_patient-avg_quick:,.0f} more on average."
            }
            
        return None
    
    def _detect_hold_bias(self, pnl_df: pd.DataFrame) -> Optional[Dict]:
        """Detect if trader holds losers longer than winners."""
        # Filter for closed positions
        closed_trades = pnl_df[
            (pnl_df['realizedPnl'].notna()) & 
            (pnl_df['holdTimeSeconds'] > 0)
        ].copy()
        
        winners = closed_trades[closed_trades['realizedPnl'] > 0]
        losers = closed_trades[closed_trades['realizedPnl'] < 0]
        
        if len(winners) < 15 or len(losers) < 15:  # Need reasonable sample
            return None
            
        # Compare hold times
        winner_hold_times = winners['holdTimeSeconds'].values
        loser_hold_times = losers['holdTimeSeconds'].values
        
        # Calculate the bias
        avg_winner_hold = winner_hold_times.mean() / 3600  # Convert to hours
        avg_loser_hold = loser_hold_times.mean() / 3600
        
        # Bootstrap confidence test
        hold_longer_count = 0
        for _ in range(1000):
            sample_winners = np.random.choice(winner_hold_times, size=15, replace=True)
            sample_losers = np.random.choice(loser_hold_times, size=15, replace=True)
            if sample_losers.mean() > sample_winners.mean() * 1.3:  # 30% longer
                hold_longer_count += 1
        
        confidence = hold_longer_count / 1000
        
        if (confidence > PATTERN_REQUIREMENTS['confidence_level'] and 
            avg_loser_hold > avg_winner_hold * 1.5):  # Losers held 50% longer
            
            # Calculate opportunity cost
            total_loser_pnl = losers['realizedPnl'].sum()
            
            return {
                "pattern": "Loss Aversion Detected",
                "confidence": f"{confidence*100:.0f}%",
                "impact": f"Holding losers {avg_loser_hold/avg_winner_hold:.1f}x longer than winners",
                "evidence": {
                    "winners_count": len(winners),
                    "losers_count": len(losers),
                    "avg_winner_hold": f"{avg_winner_hold:.1f} hours",
                    "avg_loser_hold": f"{avg_loser_hold:.1f} hours",
                    "total_losses": f"${total_loser_pnl:,.0f}",
                    "longest_held_losers": losers.nlargest(5, 'holdTimeSeconds')[['symbol', 'realizedPnl', 'holdTimeSeconds']].to_dict('records')
                },
                "recommendation": "Set stop losses. You hold losers hoping they'll recover, but data shows cutting losses early improves performance."
            }
            
        return None


def main():
    """Example usage."""
    detector = BlindSpotDetector()
    patterns = detector.analyze_all_patterns()
    
    for pattern in patterns:
        print(f"\n🎯 {pattern['pattern']}")
        if 'confidence' in pattern:
            print(f"   Confidence: {pattern['confidence']}")
            print(f"   Impact: {pattern['impact']}")
            print(f"   Recommendation: {pattern['recommendation']}")
        else:
            print(f"   {pattern['message']}")


if __name__ == "__main__":
    main() 