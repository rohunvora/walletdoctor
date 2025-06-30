#!/usr/bin/env python3
"""
Trading Report Card Grading Engine
Calculates letter grades based on performance percentiles
"""

import statistics
from typing import Dict, List, Any, Tuple

class TradingGrader:
    def __init__(self):
        # Grade thresholds (percentile ranges)
        self.grade_thresholds = {
            'A+': 95,
            'A':  90,
            'A-': 85,
            'B+': 80,
            'B':  70,
            'B-': 60,
            'C+': 50,
            'C':  40,
            'C-': 30,
            'D+': 20,
            'D':  10,
            'F':  0
        }
    
    def calculate_composite_score(self, stats: Dict[str, Any]) -> float:
        """Calculate a composite trading score from various metrics."""
        
        # Extract key metrics with defaults
        win_rate = stats.get('win_rate_pct', stats.get('win_rate', 0)) / 100
        total_pnl = stats.get('total_realized_pnl', stats.get('total_pnl', 0))
        total_trades = stats.get('total_tokens_traded', stats.get('total_trades', 1))
        
        # Normalize win rate (0-1, where 0.5 is average)
        win_rate_score = min(win_rate * 2, 1.0)  # Cap at 1.0
        
        # Normalize average PnL per trade
        avg_pnl = total_pnl / max(total_trades, 1)
        # Use sigmoid-like function to handle extreme values
        pnl_score = max(0, min(1, (avg_pnl + 1000) / 2000))
        
        # Volume score (more trades = more experience, but diminishing returns)
        volume_score = min(1.0, total_trades / 100)
        
        # Weighted composite score
        composite = (
            win_rate_score * 0.4 +      # 40% weight on win rate
            pnl_score * 0.4 +           # 40% weight on profitability  
            volume_score * 0.2          # 20% weight on experience
        )
        
        return composite
    
    def get_percentile_rank(self, user_score: float, reference_scores: List[float]) -> int:
        """Calculate what percentile the user's score falls into."""
        
        if not reference_scores:
            return 50  # Default to middle if no reference data
        
        # Count how many scores are below the user's score
        below_count = sum(1 for score in reference_scores if score < user_score)
        percentile = (below_count / len(reference_scores)) * 100
        
        return int(percentile)
    
    def score_to_grade(self, percentile: int) -> str:
        """Convert percentile to letter grade."""
        
        for grade, threshold in self.grade_thresholds.items():
            if percentile >= threshold:
                return grade
        
        return 'F'
    
    def generate_grade_report(self, stats: Dict[str, Any], reference_data: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate a complete grade report with percentile and insights."""
        
        # Calculate user's composite score
        user_score = self.calculate_composite_score(stats)
        
        # Get reference scores for comparison
        if reference_data:
            reference_scores = [self.calculate_composite_score(ref) for ref in reference_data]
        else:
            # Use sample distribution if no reference data
            reference_scores = self._get_sample_distribution()
        
        # Calculate percentile
        percentile = self.get_percentile_rank(user_score, reference_scores)
        
        # Get letter grade
        grade = self.score_to_grade(percentile)
        
        # Generate insights
        insights = self._generate_grade_insights(stats, percentile, grade)
        
        return {
            'grade': grade,
            'percentile': percentile,
            'score': user_score,
            'insights': insights,
            'stats_used': {
                'win_rate': stats.get('win_rate_pct', stats.get('win_rate', 0)),
                'total_pnl': stats.get('total_realized_pnl', stats.get('total_pnl', 0)),
                'total_trades': stats.get('total_tokens_traded', stats.get('total_trades', 0))
            }
        }
    
    def _get_sample_distribution(self) -> List[float]:
        """Generate a realistic sample distribution of trading scores."""
        
        # Based on typical trading performance distribution
        # Most traders lose money, few are highly profitable
        sample_scores = []
        
        # 70% of traders are below average (scores 0.2-0.45)
        for _ in range(70):
            sample_scores.append(0.2 + (0.25 * (hash(str(_)) % 100) / 100))
        
        # 20% are average (scores 0.45-0.65)
        for _ in range(20):
            sample_scores.append(0.45 + (0.2 * (hash(str(_ + 100)) % 100) / 100))
        
        # 10% are above average (scores 0.65-1.0)
        for _ in range(10):
            sample_scores.append(0.65 + (0.35 * (hash(str(_ + 200)) % 100) / 100))
        
        return sample_scores
    
    def _generate_grade_insights(self, stats: Dict[str, Any], percentile: int, grade: str) -> Dict[str, str]:
        """Generate insights based on grade and performance."""
        
        win_rate = stats.get('win_rate_pct', stats.get('win_rate', 0))
        total_pnl = stats.get('total_realized_pnl', stats.get('total_pnl', 0))
        
        insights = {}
        
        # Grade-specific messages
        if grade in ['A+', 'A', 'A-']:
            insights['grade_message'] = f"Top tier trader! Better than {percentile}% of traders."
            insights['superpower'] = "Consistent profitability"
            if win_rate > 60:
                insights['kryptonite'] = "Don't get overconfident"
            else:
                insights['kryptonite'] = "Low win rate but big winners"
                
        elif grade in ['B+', 'B', 'B-']:
            insights['grade_message'] = f"Solid performance. Better than {percentile}% of traders."
            insights['superpower'] = "Above average execution"
            insights['kryptonite'] = "Room for consistency improvement"
            
        elif grade in ['C+', 'C', 'C-']:
            insights['grade_message'] = f"Average trader. Better than {percentile}% of traders."
            if total_pnl > 0:
                insights['superpower'] = "At least you're profitable"
                insights['kryptonite'] = "Barely beating the market"
            else:
                insights['superpower'] = "You keep trying"
                insights['kryptonite'] = "Losing money consistently"
                
        else:  # D+, D, F
            insights['grade_message'] = f"Needs improvement. Better than {percentile}% of traders."
            insights['superpower'] = "Learning through pain"
            insights['kryptonite'] = "Everything (for now)"
        
        return insights

# Quick test function
def quick_grade_test():
    """Test the grading system with sample data."""
    
    grader = TradingGrader()
    
    # Test cases
    test_cases = [
        {'win_rate': 75, 'total_pnl': 50000, 'total_trades': 100},  # Should be A
        {'win_rate': 45, 'total_pnl': 10000, 'total_trades': 50},   # Should be B-C
        {'win_rate': 25, 'total_pnl': -5000, 'total_trades': 200},  # Should be D-F
    ]
    
    for i, test_case in enumerate(test_cases):
        result = grader.generate_grade_report(test_case)
        print(f"Test {i+1}: Grade {result['grade']} (Percentile: {result['percentile']}%)")
        print(f"  Message: {result['insights']['grade_message']}")
        print()

if __name__ == "__main__":
    quick_grade_test() 