#!/usr/bin/env python3
"""
Example: Deep Behavioral Analysis

Shows how Tradebro can detect complex behavioral patterns like:
- Oversizing leading to forced selling
- Liquidity traps causing missed opportunities  
- Emotional spirals after losses
- Cascading bad decisions
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tradebro.features.advanced_patterns import AdvancedPatternDetector
from src.tradebro.insights.behavioral_insights import BehavioralInsightGenerator
import pandas as pd
from datetime import datetime, timedelta
import numpy as np


def create_sample_data_with_behavioral_patterns():
    """Create sample data that exhibits the behavioral patterns we want to detect"""
    
    # Simulate a trader with problematic patterns
    trades = []
    
    # Starting conditions
    current_time = datetime.now() - timedelta(days=30)
    bankroll = 50000
    
    # Pattern 1: Oversizing leading to forced selling
    # Big position in PEPE
    trades.append({
        'timestamp': current_time,
        'token_symbol': 'PEPE',
        'type': 'buy',
        'amount_usd': 20000,  # 40% of bankroll!
        'price': 0.000001,
        'volume_24h': 1000000,
        'market_cap': 500000000
    })
    
    current_time += timedelta(hours=2)
    
    # BONK starts pumping but we're out of capital
    # Forced to sell PEPE at a loss to chase BONK
    trades.append({
        'timestamp': current_time,
        'token_symbol': 'PEPE',
        'type': 'sell',
        'amount_usd': 18000,  # Lost $2000
        'price': 0.0000009,  # -10%
    })
    
    # Immediately ape into BONK (FOMO)
    current_time += timedelta(minutes=3)
    trades.append({
        'timestamp': current_time,
        'token_symbol': 'BONK',
        'type': 'buy',
        'amount_usd': 18000,
        'price': 0.00001,
        'volume_24h': 2000000,
        'market_cap': 600000000
    })
    
    # Pattern 2: Tilt spiral after loss
    current_time += timedelta(hours=1)
    
    # BONK dumps, we panic sell
    trades.append({
        'timestamp': current_time,
        'token_symbol': 'BONK',
        'type': 'sell',
        'amount_usd': 15000,  # Lost another $3000
        'price': 0.0000083,
    })
    
    # Now we're tilted - rapid fire trades trying to make it back
    tilt_tokens = ['WOJAK', 'TURBO', 'FLOKI', 'SHIB', 'DOGE']
    for i, token in enumerate(tilt_tokens):
        # Quick buy
        current_time += timedelta(minutes=5)
        trades.append({
            'timestamp': current_time,
            'token_symbol': token,
            'type': 'buy',
            'amount_usd': 3000 + i * 1000,  # Increasing size (desperation)
            'price': 0.001 * (i + 1),
            'volume_24h': 500000,
            'market_cap': 100000000
        })
        
        # Quick sell (usually at loss)
        current_time += timedelta(minutes=15)
        loss_pct = np.random.uniform(0.05, 0.15)  # 5-15% losses
        trades.append({
            'timestamp': current_time,
            'token_symbol': token,
            'type': 'sell',
            'amount_usd': (3000 + i * 1000) * (1 - loss_pct),
            'price': 0.001 * (i + 1) * (1 - loss_pct),
        })
    
    # Pattern 3: Chronic oversizing continues
    current_time += timedelta(days=2)
    
    # Another big position
    trades.append({
        'timestamp': current_time,
        'token_symbol': 'MEME',
        'type': 'buy',
        'amount_usd': 15000,  # Still oversizing despite losses
        'price': 0.01,
        'volume_24h': 3000000,
        'market_cap': 1000000000
    })
    
    # Add more normal-sized trades to show the contrast
    normal_tokens = ['LINK', 'UNI', 'AAVE', 'SUSHI']
    for token in normal_tokens:
        current_time += timedelta(days=1)
        trades.append({
            'timestamp': current_time,
            'token_symbol': token,
            'type': 'buy',
            'amount_usd': 2000,  # Reasonable 4% position
            'price': 10,
            'volume_24h': 50000000,
            'market_cap': 5000000000
        })
        
        current_time += timedelta(days=2)
        # Some winners
        profit = np.random.uniform(1.1, 1.3)
        trades.append({
            'timestamp': current_time,
            'token_symbol': token,
            'type': 'sell',
            'amount_usd': 2000 * profit,
            'price': 10 * profit,
        })
    
    return pd.DataFrame(trades)


def demonstrate_deep_analysis():
    """Demonstrate the deep behavioral analysis"""
    
    print("=== Tradebro Deep Behavioral Analysis Demo ===\n")
    
    # Create sample data
    tx_df = create_sample_data_with_behavioral_patterns()
    prices_df = pd.DataFrame()  # Empty for this demo
    
    print("Loading trading data...")
    print(f"Analyzing {len(tx_df)} transactions over {(tx_df['timestamp'].max() - tx_df['timestamp'].min()).days} days\n")
    
    # Run advanced pattern detection
    print("Detecting behavioral patterns...")
    detector = AdvancedPatternDetector(tx_df, prices_df)
    insights_data = detector.generate_deep_insights()
    
    # Generate human-readable insights
    print("Generating insights...\n")
    generator = BehavioralInsightGenerator(insights_data)
    insights = generator.generate_all_insights()
    
    # Display the insights
    print("=" * 80)
    print("DEEP BEHAVIORAL INSIGHTS")
    print("=" * 80)
    
    # Show top 3 critical insights
    for i, insight in enumerate(insights[:3], 1):
        print(f"\n{i}. {insight.title}")
        print(f"   Severity: {insight.severity.upper()}")
        print(f"\n   {insight.description}")
        
        print(f"\n   Evidence:")
        for evidence in insight.evidence:
            print(f"   • {evidence}")
        
        print(f"\n   Root Cause: {insight.root_cause}")
        
        print(f"\n   This leads to:")
        for effect in insight.cascade_effects[:3]:
            print(f"   → {effect}")
        
        print(f"\n   THE FIX: {insight.specific_fix}")
        print(f"\n   Expected Result: {insight.expected_outcome}")
        print("\n" + "-" * 80)
    
    # Show the narrative summary
    print("\n" + "=" * 80)
    print("YOUR TRADING PSYCHOLOGY PROFILE")
    print("=" * 80)
    summary = generator.generate_narrative_summary()
    print(summary)
    
    # Show the action plan
    print("\n" + "=" * 80)
    print("YOUR PERSONALIZED ACTION PLAN")
    print("=" * 80)
    
    action_plan = generator.generate_action_plan()
    for i, action in enumerate(action_plan, 1):
        print(f"\n{i}. {action['action'].split(':')[0]}")
        print(f"   Priority: {action['priority']}/10")
        print(f"   Timeframe: {action['timeframe']}")
        print(f"   Expected: {action['expected_result']}")
        print(f"   Track: {action['how_to_track']}")
    
    # Show specific examples from their data
    print("\n" + "=" * 80)
    print("SPECIFIC EXAMPLES FROM YOUR TRADING")
    print("=" * 80)
    
    # Find the PEPE → BONK forced sale cascade
    pepe_trade = tx_df[(tx_df['token_symbol'] == 'PEPE') & (tx_df['type'] == 'buy')].iloc[0]
    bonk_trade = tx_df[(tx_df['token_symbol'] == 'BONK') & (tx_df['type'] == 'buy')].iloc[0]
    
    print(f"\nExample of Oversizing Cascade:")
    print(f"1. You bought ${pepe_trade['amount_usd']:,.0f} of PEPE (40% of bankroll)")
    print(f"2. BONK started pumping but you had no capital")
    print(f"3. You panic sold PEPE at a -10% loss")
    print(f"4. You immediately aped into BONK within 3 minutes")
    print(f"5. This emotional decision led to another -17% loss")
    print(f"Total cascade cost: $5,000 in 3 hours")
    
    # Show the tilt spiral
    tilt_trades = tx_df[tx_df['token_symbol'].isin(['WOJAK', 'TURBO', 'FLOKI', 'SHIB', 'DOGE'])]
    tilt_losses = tilt_trades[tilt_trades['type'] == 'sell']['amount_usd'].sum() - \
                  tilt_trades[tilt_trades['type'] == 'buy']['amount_usd'].sum()
    
    print(f"\nExample of Tilt Spiral:")
    print(f"After the BONK loss, you made 5 trades in 90 minutes:")
    for _, trade in tilt_trades[tilt_trades['type'] == 'buy'].iterrows():
        print(f"  • {trade['token_symbol']}: ${trade['amount_usd']:,.0f}")
    print(f"Total tilt spiral loss: ${abs(tilt_losses):,.0f}")
    print(f"Average time between trades: 18 minutes")
    print(f"Clear sign of emotional/revenge trading")
    
    print("\n" + "=" * 80)
    print("REMEMBER: These patterns are costing you thousands of dollars.")
    print("Fix the behavior, transform your results.")
    print("=" * 80)


if __name__ == "__main__":
    demonstrate_deep_analysis() 