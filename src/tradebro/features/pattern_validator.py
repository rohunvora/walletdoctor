"""Pattern validation to ensure insights are accurate and prevent false conclusions."""
import polars as pl
from typing import Dict, Any, List, Tuple
import numpy as np
from scipy import stats


class PatternValidator:
    """Validates detected patterns to prevent false psychological conclusions."""
    
    def __init__(self, min_confidence: float = 0.75):
        self.min_confidence = min_confidence
    
    def validate_pattern(self, pattern_data: Dict[str, Any], df: pl.DataFrame) -> Dict[str, Any]:
        """
        Validate a detected pattern with statistical checks.
        
        Returns:
            Dict with 'valid', 'confidence', 'concerns', and 'evidence'
        """
        pattern_type = pattern_data.get('type', 'unknown')
        
        validators = {
            'loss_aversion': self._validate_loss_aversion,
            'revenge_trading': self._validate_revenge_trading,
            'fomo_spiral': self._validate_fomo_spiral,
            'no_process': self._validate_no_process
        }
        
        validator = validators.get(pattern_type, self._validate_generic)
        return validator(pattern_data, df)
    
    def _validate_loss_aversion(self, pattern: Dict[str, Any], df: pl.DataFrame) -> Dict[str, Any]:
        """Validate loss aversion pattern with statistical tests."""
        if not pattern.get('detected'):
            return {'valid': False, 'confidence': 0}
        
        winners = df.filter(pl.col('pnl') > 0)
        losers = df.filter(pl.col('pnl') < 0)
        
        # Need sufficient sample size
        if winners.height < 10 or losers.height < 10:
            return {
                'valid': False,
                'confidence': 0.3,
                'concerns': ['Insufficient sample size (need 10+ winners and losers)'],
                'evidence': f'Only {winners.height} winners and {losers.height} losers'
            }
        
        # Statistical test: Are hold times significantly different?
        winner_holds = winners['hold_minutes'].to_numpy()
        loser_holds = losers['hold_minutes'].to_numpy()
        
        # T-test for difference in means
        t_stat, p_value = stats.ttest_ind(loser_holds, winner_holds)
        
        # Effect size (Cohen's d)
        cohens_d = (loser_holds.mean() - winner_holds.mean()) / np.sqrt(
            ((loser_holds.std()**2 + winner_holds.std()**2) / 2)
        )
        
        # Consistency check: Is this pattern consistent across time periods?
        consistency = self._check_temporal_consistency(df, 'loss_aversion')
        
        # Calculate confidence
        confidence = 0.0
        if p_value < 0.05:  # Statistically significant
            confidence += 0.4
        if abs(cohens_d) > 0.5:  # Medium effect size
            confidence += 0.3
        if consistency > 0.7:  # Pattern is consistent
            confidence += 0.3
        
        concerns = []
        if p_value >= 0.05:
            concerns.append(f'Not statistically significant (p={p_value:.3f})')
        if abs(cohens_d) < 0.3:
            concerns.append(f'Small effect size (d={cohens_d:.2f})')
        if consistency < 0.7:
            concerns.append(f'Inconsistent pattern (consistency={consistency:.1%})')
        
        return {
            'valid': confidence >= self.min_confidence,
            'confidence': confidence,
            'concerns': concerns,
            'evidence': {
                'p_value': p_value,
                'effect_size': cohens_d,
                'consistency': consistency,
                'avg_winner_hold': winner_holds.mean(),
                'avg_loser_hold': loser_holds.mean(),
                'sample_size': {'winners': winners.height, 'losers': losers.height}
            }
        }
    
    def _validate_revenge_trading(self, pattern: Dict[str, Any], df: pl.DataFrame) -> Dict[str, Any]:
        """Validate revenge trading pattern."""
        if not pattern.get('detected'):
            return {'valid': False, 'confidence': 0}
        
        revenge_trades = pattern.get('revenge_trades', [])
        
        # Need multiple instances
        if len(revenge_trades) < 3:
            return {
                'valid': False,
                'confidence': 0.4,
                'concerns': ['Too few instances (need 3+) to confirm pattern'],
                'evidence': f'Only {len(revenge_trades)} potential revenge trades found'
            }
        
        # Check if size increases are statistically significant
        normal_sizes = df['trade_size_usd'].to_numpy()
        revenge_sizes = [t['size'] for t in revenge_trades]
        
        # Are revenge trade sizes significantly larger?
        percentile_rank = np.mean([
            stats.percentileofscore(normal_sizes, size) 
            for size in revenge_sizes
        ])
        
        # Check if revenge trades consistently follow losses
        follows_loss_rate = sum(1 for t in revenge_trades if t['previous_loss'] < 0) / len(revenge_trades)
        
        # Check outcome: Do revenge trades tend to lose?
        revenge_loss_rate = sum(1 for t in revenge_trades if t['result'] < 0) / len(revenge_trades)
        
        confidence = 0.0
        if percentile_rank > 90:  # Sizes in top 10%
            confidence += 0.4
        if follows_loss_rate > 0.8:  # Usually after losses
            confidence += 0.3
        if revenge_loss_rate > 0.6:  # Often fail
            confidence += 0.3
        
        concerns = []
        if percentile_rank < 90:
            concerns.append(f'Size increases not extreme (percentile={percentile_rank:.0f})')
        if follows_loss_rate < 0.8:
            concerns.append('Not consistently following losses')
        
        return {
            'valid': confidence >= self.min_confidence,
            'confidence': confidence,
            'concerns': concerns,
            'evidence': {
                'instances': len(revenge_trades),
                'size_percentile': percentile_rank,
                'follows_loss_rate': follows_loss_rate,
                'failure_rate': revenge_loss_rate,
                'avg_size_increase': np.mean([t['size_multiplier'] for t in revenge_trades])
            }
        }
    
    def _validate_no_process(self, pattern: Dict[str, Any], df: pl.DataFrame) -> Dict[str, Any]:
        """Validate lack of process/consistency."""
        if not pattern.get('detected'):
            return {'valid': False, 'confidence': 0}
        
        # Compare variance to random trading
        size_cv = pattern.get('size_variance', 0)
        hold_cv = pattern.get('hold_variance', 0)
        
        # Benchmark: What would random look like?
        # Professional traders typically have CV < 50% for position sizing
        
        confidence = 0.0
        if size_cv > 200:  # Extreme variance
            confidence += 0.5
        elif size_cv > 150:
            confidence += 0.3
        
        if hold_cv > 200:
            confidence += 0.3
        elif hold_cv > 150:
            confidence += 0.2
        
        # Check if variance is due to evolution (learning) vs chaos
        is_evolving = self._check_if_evolving(df)
        
        if is_evolving:
            confidence *= 0.5  # Reduce confidence if trader is improving
            
        concerns = []
        if size_cv < 150:
            concerns.append('Position variance not extreme enough')
        if is_evolving:
            concerns.append('Variance might indicate learning/adaptation, not chaos')
        
        return {
            'valid': confidence >= self.min_confidence,
            'confidence': confidence,
            'concerns': concerns,
            'evidence': {
                'size_cv': size_cv,
                'hold_cv': hold_cv,
                'is_evolving': is_evolving
            }
        }
    
    def _validate_fomo_spiral(self, pattern: Dict[str, Any], df: pl.DataFrame) -> Dict[str, Any]:
        """Validate FOMO trading pattern."""
        if not pattern.get('detected'):
            return {'valid': False, 'confidence': 0}
        
        sequences = pattern.get('sequences', 0)
        examples = pattern.get('examples', [])
        
        if sequences < 3:
            return {
                'valid': False,
                'confidence': 0.3,
                'concerns': ['Too few FOMO sequences to confirm pattern'],
                'evidence': f'Only {sequences} sequences found'
            }
        
        # Check if rapid trading after wins is actually worse than normal
        baseline_loss_rate = df.filter(pl.col('pnl') < 0).height / df.height
        fomo_loss_rate = pattern.get('loss_rate_after_wins', 0)
        
        # Is FOMO trading significantly worse?
        loss_rate_increase = (fomo_loss_rate - baseline_loss_rate) / baseline_loss_rate
        
        confidence = 0.0
        if sequences >= 5:
            confidence += 0.4
        elif sequences >= 3:
            confidence += 0.2
            
        if loss_rate_increase > 0.3:  # 30% worse than baseline
            confidence += 0.4
        elif loss_rate_increase > 0.1:
            confidence += 0.2
            
        # Check if time gaps are really unusual
        avg_gap = np.mean([ex['avg_minutes_between'] for ex in examples])
        if avg_gap < 15:  # Very rapid
            confidence += 0.2
        
        concerns = []
        if loss_rate_increase < 0.1:
            concerns.append('FOMO trading not significantly worse than baseline')
        if avg_gap > 30:
            concerns.append('Trading frequency not unusually high')
        
        return {
            'valid': confidence >= self.min_confidence,
            'confidence': confidence,
            'concerns': concerns,
            'evidence': {
                'sequences': sequences,
                'loss_rate_increase': loss_rate_increase,
                'avg_time_between': avg_gap,
                'baseline_loss_rate': baseline_loss_rate,
                'fomo_loss_rate': fomo_loss_rate
            }
        }
    
    def _check_temporal_consistency(self, df: pl.DataFrame, pattern_type: str) -> float:
        """Check if pattern is consistent across different time periods."""
        if df.height < 50:
            return 0.5  # Not enough data
        
        # Split data into quarters
        quarter_size = df.height // 4
        quarters = [
            df.slice(i * quarter_size, quarter_size) 
            for i in range(4)
        ]
        
        # Check if pattern exists in each quarter
        pattern_scores = []
        
        for quarter in quarters:
            if pattern_type == 'loss_aversion':
                winners = quarter.filter(pl.col('pnl') > 0)
                losers = quarter.filter(pl.col('pnl') < 0)
                if winners.height > 0 and losers.height > 0:
                    ratio = losers['hold_minutes'].mean() / winners['hold_minutes'].mean()
                    pattern_scores.append(1 if ratio > 1.2 else 0)
        
        return np.mean(pattern_scores) if pattern_scores else 0.5
    
    def _check_if_evolving(self, df: pl.DataFrame) -> bool:
        """Check if high variance is due to learning/evolution."""
        if df.height < 50:
            return False
        
        # Split into first half and second half
        mid = df.height // 2
        first_half = df.head(mid)
        second_half = df.tail(df.height - mid)
        
        # Compare variance in both halves
        first_cv = first_half['trade_size_usd'].std() / first_half['trade_size_usd'].mean()
        second_cv = second_half['trade_size_usd'].std() / second_half['trade_size_usd'].mean()
        
        # If variance is decreasing, trader might be learning
        return second_cv < first_cv * 0.7
    
    def _validate_generic(self, pattern: Dict[str, Any], df: pl.DataFrame) -> Dict[str, Any]:
        """Generic validation for unknown patterns."""
        return {
            'valid': False,
            'confidence': 0,
            'concerns': ['Unknown pattern type'],
            'evidence': {}
        }
    
    def generate_confidence_statement(self, validation_result: Dict[str, Any]) -> str:
        """Generate a statement about confidence in the pattern."""
        confidence = validation_result.get('confidence', 0)
        concerns = validation_result.get('concerns', [])
        
        if confidence >= 0.9:
            return "Very high confidence - pattern is clear and consistent"
        elif confidence >= 0.75:
            return "High confidence - pattern is statistically significant"
        elif confidence >= 0.6:
            return f"Moderate confidence - {concerns[0] if concerns else 'some uncertainty'}"
        elif confidence >= 0.4:
            return f"Low confidence - {', '.join(concerns[:2])}"
        else:
            return f"Pattern not validated - {', '.join(concerns)}" 