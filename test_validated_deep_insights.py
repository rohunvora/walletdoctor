#!/usr/bin/env python3
"""Test the validated deep insight system."""
import sys
sys.path.append('src')

import pandas as pd
import polars as pl
from datetime import datetime, timedelta
import numpy as np

# Conditionally import scipy
try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Note: scipy not installed. Installing with: pip install scipy")

from walletdoctor.insights.deep_generator import DeepInsightGenerator


def create_test_data_with_patterns():
    """Create test data with clear behavioral patterns."""
    trades = []
    base_time = datetime.now()
    
    # Create pattern 1: Loss aversion (hold losers longer)
    for i in range(30):
        if i % 3 == 0:  # Winners
            trades.append({
                'token_mint': f'TOKEN{i}',
                'symbol': f'TOK{i}',
                'pnl': np.random.uniform(1000, 5000),
                'hold_minutes': np.random.uniform(180, 300),  # 3-5 hours
                'trade_size_usd': np.random.uniform(5000, 7000),
                'timestamp': base_time - timedelta(days=30-i),
            })
        else:  # Losers
            trades.append({
                'token_mint': f'TOKEN{i}',
                'symbol': f'TOK{i}',
                'pnl': np.random.uniform(-5000, -1000),
                'hold_minutes': np.random.uniform(300, 500),  # 5-8 hours (longer!)
                'trade_size_usd': np.random.uniform(5000, 7000),
                'timestamp': base_time - timedelta(days=30-i),
            })
    
    # Create pattern 2: Revenge trading (big sizes after losses)
    for i in range(30, 40):
        if i % 4 == 0:  # Revenge trade after loss
            trades.append({
                'token_mint': f'TOKEN{i}',
                'symbol': f'TOK{i}',
                'pnl': -20000,  # Big loss from revenge trade
                'hold_minutes': 120,
                'trade_size_usd': 50000,  # 10x normal size
                'timestamp': base_time - timedelta(days=40-i, hours=1),
            })
        else:  # Normal trade
            trades.append({
                'token_mint': f'TOKEN{i}',
                'symbol': f'TOK{i}',
                'pnl': np.random.uniform(-2000, 3000),
                'hold_minutes': np.random.uniform(60, 240),
                'trade_size_usd': 5000,  # Normal size
                'timestamp': base_time - timedelta(days=40-i),
            })
    
    # Add the massive loss
    trades.append({
        'token_mint': 'XBT',
        'symbol': 'XBT',
        'pnl': -59224,
        'hold_minutes': 139,
        'trade_size_usd': 100000,  # 20x normal
        'timestamp': base_time - timedelta(days=5),
    })
    
    return pl.DataFrame(trades).with_columns([
        pl.col("timestamp").cast(pl.Datetime),
        pl.lit(50_000_000).alias("fee"),
        pl.lit("sell").alias("side"),
        (pl.col("pnl") / pl.col("trade_size_usd") * 100).alias("pnl_pct")
    ])


def format_insight_output(insight: Dict) -> str:
    """Format a single insight for display."""
    output = []
    
    # Headline with confidence
    confidence_pct = insight['confidence'] * 100
    output.append(f"\n{'='*60}")
    output.append(f"🎯 {insight['headline']}")
    output.append(f"   Confidence: {confidence_pct:.0f}% | Severity: {insight['severity'].upper()}")
    
    # Psychological analysis
    output.append(f"\n📊 ROOT CAUSE: {insight['psychological_root']}")
    output.append(f"💭 YOUR INNER VOICE: {insight['subconscious_narrative']}")
    output.append(f"🔄 THE LOOP: {insight['behavioral_loop']}")
    
    # Evidence
    output.append(f"\n📈 EVIDENCE:")
    for evidence in insight['specific_evidence']:
        output.append(f"   • {evidence}")
    
    # Harsh truth
    output.append(f"\n⚡ HARSH TRUTH:")
    output.append(f"   {insight['harsh_truth']}")
    
    # Fix
    output.append(f"\n✅ THE FIX:")
    output.append(f"   {insight['fix']}")
    
    # Caveats if any
    if 'caveats' in insight:
        output.append(f"\n⚠️  CAVEATS:")
        for caveat in insight['caveats']:
            output.append(f"   • {caveat}")
    
    return '\n'.join(output)


def test_deep_insights():
    """Test the deep insight system with validation."""
    print("VALIDATED DEEP INSIGHT SYSTEM TEST")
    print("="*60)
    
    if not SCIPY_AVAILABLE:
        print("\n❌ scipy is required for statistical validation")
        print("Install with: pip install scipy")
        return
    
    # Create test data
    print("\n1. Creating test data with behavioral patterns...")
    df = create_test_data_with_patterns()
    print(f"   ✓ Created {df.height} trades with embedded patterns")
    
    # Run deep insight analysis
    print("\n2. Running deep psychological analysis with validation...")
    generator = DeepInsightGenerator(min_confidence=0.7)
    
    try:
        analysis = generator.generate_insights(df, max_insights=3)
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        print("\nThis might be due to missing dependencies or data issues.")
        return
    
    # Display overall diagnosis
    print("\n3. OVERALL DIAGNOSIS")
    print("="*60)
    diagnosis = analysis['diagnosis']
    print(f"🔍 Primary Issue: {diagnosis['primary_issue']}")
    print(f"🧠 Root Problem: {diagnosis['root_problem']}")
    print(f"⚠️  Severity: {diagnosis['severity'].upper()}")
    print(f"📊 Patterns Active: {diagnosis['patterns_active']}")
    print(f"\n🔮 PROGNOSIS: {diagnosis['prognosis']}")
    
    print(f"\n💊 PRESCRIPTION:")
    for i, action in enumerate(diagnosis['prescription'], 1):
        print(f"   {i}. {action}")
    
    # Display confidence summary
    print(f"\n📈 Analysis Confidence: {analysis['confidence_summary']}")
    
    # Display individual insights
    print("\n\n4. VALIDATED BEHAVIORAL PATTERNS")
    
    if not analysis['insights']:
        print("\n   No patterns detected with sufficient statistical confidence.")
        print("   This could mean:")
        print("   • Not enough data")
        print("   • Patterns not statistically significant")
        print("   • Trader is actually disciplined")
    else:
        for insight in analysis['insights']:
            print(format_insight_output(insight))
    
    # Summary
    print("\n" + "="*60)
    print("WHAT MAKES THIS DIFFERENT:")
    print("• Statistical validation prevents false conclusions")
    print("• Psychological mapping reveals WHY, not just WHAT")
    print("• Harsh truths that force self-reflection")
    print("• Specific, actionable fixes for each pattern")
    print("• Confidence levels show when we're certain vs guessing")
    
    if analysis['requires_action']:
        print("\n🚨 CRITICAL: Immediate action required to prevent account blow-up!")


if __name__ == "__main__":
    test_deep_insights() 