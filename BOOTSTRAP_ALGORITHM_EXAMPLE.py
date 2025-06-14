"""
Bootstrap Confidence Testing Implementation
==========================================

This file demonstrates the statistical validation method used in WalletDoctor
to ensure patterns are real, not random noise.

The bootstrap method is used because:
1. It doesn't assume normal distribution (crypto P&L is often skewed)
2. It provides confidence intervals without complex math
3. It's intuitive: "If I randomly sample my trades 1000 times, how often does pattern X appear?"
"""

import numpy as np
import pandas as pd
from typing import Tuple, List


def bootstrap_confidence_test(
    sample1: np.ndarray, 
    sample2: np.ndarray, 
    test_type: str = 'greater',
    n_iterations: int = 1000,
    sample_size: int = 30
) -> Tuple[float, dict]:
    """
    Perform bootstrap confidence test to validate trading patterns.
    
    Args:
        sample1: First group (e.g., quick trades P&L)
        sample2: Second group (e.g., patient trades P&L)
        test_type: 'greater' if testing sample2 > sample1
        n_iterations: Number of bootstrap samples
        sample_size: Size of each bootstrap sample
        
    Returns:
        confidence: Probability that the pattern exists (0-1)
        statistics: Additional statistics about the comparison
    """
    
    # Ensure we have enough data
    if len(sample1) < sample_size or len(sample2) < sample_size:
        return 0.0, {"error": "Insufficient data"}
    
    # Track results
    pattern_count = 0
    differences = []
    
    # Run bootstrap iterations
    for i in range(n_iterations):
        # Randomly sample with replacement
        bootstrap_sample1 = np.random.choice(sample1, size=sample_size, replace=True)
        bootstrap_sample2 = np.random.choice(sample2, size=sample_size, replace=True)
        
        # Calculate means
        mean1 = bootstrap_sample1.mean()
        mean2 = bootstrap_sample2.mean()
        
        # Record difference
        differences.append(mean2 - mean1)
        
        # Test the hypothesis
        if test_type == 'greater' and mean2 > mean1:
            pattern_count += 1
        elif test_type == 'less' and mean2 < mean1:
            pattern_count += 1
        elif test_type == 'different' and mean2 != mean1:
            pattern_count += 1
    
    # Calculate confidence
    confidence = pattern_count / n_iterations
    
    # Calculate confidence interval
    differences = np.array(differences)
    ci_lower = np.percentile(differences, 2.5)
    ci_upper = np.percentile(differences, 97.5)
    
    statistics = {
        "confidence": confidence,
        "mean_difference": differences.mean(),
        "ci_95_lower": ci_lower,
        "ci_95_upper": ci_upper,
        "sample1_mean": sample1.mean(),
        "sample2_mean": sample2.mean(),
        "sample1_size": len(sample1),
        "sample2_size": len(sample2)
    }
    
    return confidence, statistics


def detect_fomo_pattern_with_validation(trades_df: pd.DataFrame) -> dict:
    """
    Real-world example: Detecting FOMO trading pattern with statistical validation.
    
    Args:
        trades_df: DataFrame with columns ['holdTimeSeconds', 'realizedPnl']
        
    Returns:
        Pattern detection result with confidence score
    """
    
    # Define behavioral groups
    quick_trades = trades_df[trades_df['holdTimeSeconds'] < 600]['realizedPnl'].values
    patient_trades = trades_df[trades_df['holdTimeSeconds'] > 3600]['realizedPnl'].values
    
    # Run bootstrap test
    confidence, stats = bootstrap_confidence_test(
        quick_trades,
        patient_trades,
        test_type='greater',
        n_iterations=1000
    )
    
    # Calculate potential improvement
    avg_quick = stats['sample1_mean']
    avg_patient = stats['sample2_mean']
    potential_gain = (avg_patient - avg_quick) * len(quick_trades)
    
    # Decision logic
    CONFIDENCE_THRESHOLD = 0.95
    DOLLAR_IMPACT_THRESHOLD = 500
    
    if confidence >= CONFIDENCE_THRESHOLD and potential_gain >= DOLLAR_IMPACT_THRESHOLD:
        return {
            "pattern_detected": True,
            "pattern_name": "FOMO Trading",
            "confidence": f"{confidence*100:.1f}%",
            "evidence": {
                "quick_trades_count": len(quick_trades),
                "patient_trades_count": len(patient_trades),
                "avg_quick_pnl": f"${avg_quick:.2f}",
                "avg_patient_pnl": f"${avg_patient:.2f}",
                "confidence_interval": f"[${stats['ci_95_lower']:.2f}, ${stats['ci_95_upper']:.2f}]"
            },
            "impact": f"${potential_gain:,.0f} potential gain",
            "recommendation": f"Hold positions for at least 1 hour. Patient trades make ${avg_patient - avg_quick:.0f} more on average."
        }
    else:
        return {
            "pattern_detected": False,
            "reason": f"Confidence ({confidence:.1%}) below threshold or impact (${potential_gain:.0f}) too small"
        }


# Example usage
if __name__ == "__main__":
    # Generate sample data
    np.random.seed(42)
    
    # Simulate trading data where quick trades perform worse
    n_quick = 500
    n_patient = 100
    
    # Quick trades: mostly losses with high variance
    quick_pnl = np.random.normal(-35, 150, n_quick)  # Mean -$35, high variance
    
    # Patient trades: mostly profits with lower variance  
    patient_pnl = np.random.normal(120, 80, n_patient)  # Mean +$120, lower variance
    
    # Create DataFrame
    trades = pd.DataFrame({
        'holdTimeSeconds': 
            [np.random.randint(60, 600) for _ in range(n_quick)] +  # Quick trades
            [np.random.randint(3600, 7200) for _ in range(n_patient)],  # Patient trades
        'realizedPnl': 
            list(quick_pnl) + list(patient_pnl)
    })
    
    # Run pattern detection
    result = detect_fomo_pattern_with_validation(trades)
    
    # Display results
    print("FOMO Pattern Detection Results")
    print("=" * 50)
    if result['pattern_detected']:
        print(f"✓ Pattern: {result['pattern_name']}")
        print(f"✓ Confidence: {result['confidence']}")
        print(f"✓ Impact: {result['impact']}")
        print(f"\nEvidence:")
        for key, value in result['evidence'].items():
            print(f"  - {key}: {value}")
        print(f"\nRecommendation: {result['recommendation']}")
    else:
        print(f"✗ No pattern detected: {result['reason']}")
    
    # Show how confidence changes with sample size
    print("\n\nConfidence vs Sample Size Analysis")
    print("=" * 50)
    sample_sizes = [10, 20, 30, 50, 100, 200]
    for size in sample_sizes:
        if size <= min(len(quick_pnl), len(patient_pnl)):
            conf, _ = bootstrap_confidence_test(
                quick_pnl[:size],
                patient_pnl[:size],
                test_type='greater',
                sample_size=min(size, 30)
            )
            print(f"Sample size {size}: {conf*100:.1f}% confidence") 