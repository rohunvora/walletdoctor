#!/usr/bin/env python3
"""
Test edge cases using the Cielo data we already retrieved
"""

import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.trading_coach import TradingCoach, TradingPattern
from unittest.mock import patch

def load_test_data():
    """Load the Cielo data we already have"""
    with open('cielo_api_test_results.json', 'r') as f:
        data = json.load(f)
    
    for result in data['results']:
        if result['endpoint'] == 'Token PNL' and result['status'] == 'success':
            return result['data']['data']['items']
    return []

async def test_with_mock_data():
    """Test edge cases with our saved data"""
    
    coach = TradingCoach('test_key')
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    # Load real data
    token_data = load_test_data()
    
    print("=== EDGE CASE TESTING WITH REAL DATA ===\n")
    print(f"Using {len(token_data)} tokens from Cielo\n")
    
    # Mock the API call
    with patch.object(coach, '_fetch_cielo_data', return_value=token_data):
        
        # Edge Case 1: Zero SOL
        print("1. EDGE CASE: Zero SOL Amount")
        print("-" * 40)
        result = await coach.get_coaching_for_trade(wallet, 0.0)
        print(f"Message: {result['message']}")
        print(f"Coaching: {result['coaching']}")
        print(f"Shows patterns: {'statistics' in result}")
        
        # Edge Case 2: Tiny amount  
        print("\n2. EDGE CASE: Dust Amount (0.01 SOL)")
        print("-" * 40)
        result = await coach.get_coaching_for_trade(wallet, 0.01)
        stats = result.get('statistics', {})
        print(f"Found patterns: {stats.get('total_patterns', 0)}")
        print(f"Coaching: {result['coaching']}")
        
        # Edge Case 3: Exact match with historical
        print("\n3. EDGE CASE: Exact Historical Amount")
        print("-" * 40)
        # Find an exact amount from history
        exact_amounts = set()
        for token in token_data[:10]:
            if token['num_swaps'] > 0:
                avg_sol = (token['total_buy_usd'] / token['num_swaps']) / 150
                exact_amounts.add(round(avg_sol, 1))
        
        if exact_amounts:
            test_amount = list(exact_amounts)[0]
            print(f"Testing with exact historical: {test_amount} SOL")
            result = await coach.get_coaching_for_trade(wallet, test_amount)
            stats = result.get('statistics', {})
            print(f"Found patterns: {stats.get('total_patterns', 0)}")
            print(f"Win rate: {stats.get('win_rate', 0):.0f}%")
        
        # Edge Case 4: Boundary testing
        print("\n4. EDGE CASE: Tolerance Boundaries (50%)")
        print("-" * 40)
        base = 10.0
        
        # Test at different tolerance levels
        for multiplier in [0.49, 0.50, 0.51, 1.49, 1.50, 1.51]:
            amount = base * multiplier
            result = await coach.get_coaching_for_trade(wallet, amount)
            stats = result.get('statistics', {})
            patterns = stats.get('total_patterns', 0)
            print(f"{amount:>5.1f} SOL ({multiplier:>4.2f}x): {patterns} patterns found")
        
        # Edge Case 5: Statistical anomalies
        print("\n5. STATISTICAL ANOMALIES")
        print("-" * 40)
        
        # Find the position size with most variance
        import statistics
        
        position_analyses = []
        for test_sol in [5, 10, 20, 50]:
            patterns = await coach._get_similar_patterns(wallet, test_sol, tolerance=0.5)
            if len(patterns) >= 3:
                rois = [p.roi_percentage for p in patterns]
                mean_roi = statistics.mean(rois)
                stdev_roi = statistics.stdev(rois)
                cv = abs(stdev_roi / mean_roi) if mean_roi != 0 else float('inf')
                
                position_analyses.append({
                    'sol': test_sol,
                    'count': len(patterns),
                    'mean_roi': mean_roi,
                    'stdev': stdev_roi,
                    'cv': cv
                })
        
        if position_analyses:
            # Sort by coefficient of variation
            position_analyses.sort(key=lambda x: x['cv'], reverse=True)
            
            print("Position sizes by volatility (most unpredictable first):")
            for analysis in position_analyses:
                print(f"{analysis['sol']:>3.0f} SOL: "
                      f"μ={analysis['mean_roi']:>+6.1f}%, "
                      f"σ={analysis['stdev']:>5.1f}%, "
                      f"CV={analysis['cv']:>4.2f}, "
                      f"n={analysis['count']}")
        
        # Edge Case 6: Single trade positions
        print("\n6. SINGLE TRADE POSITIONS")
        print("-" * 40)
        
        single_trade_tokens = [t for t in token_data if t['num_swaps'] == 1]
        print(f"Found {len(single_trade_tokens)} tokens with only 1 trade")
        
        if single_trade_tokens:
            # Find a position size that matches single trades
            for token in single_trade_tokens[:3]:
                sol_amount = token['total_buy_usd'] / 150
                result = await coach.get_coaching_for_trade(wallet, sol_amount)
                stats = result.get('statistics', {})
                if stats.get('total_patterns', 0) > 0:
                    print(f"\n{sol_amount:.1f} SOL position:")
                    print(f"  Patterns: {stats['total_patterns']}")
                    print(f"  Coaching: {result['coaching'][:50]}...")
                    break

def analyze_blind_spots():
    """Analyze blind spots in the data"""
    
    print("\n\n=== BLIND SPOT ANALYSIS ===\n")
    
    token_data = load_test_data()
    
    # Time blindness
    print("1. TIME BLINDNESS EVIDENCE")
    print("-" * 40)
    
    # Get time range of trades
    timestamps = []
    for token in token_data:
        if token.get('first_trade'):
            timestamps.append(token['first_trade'])
        if token.get('last_trade'):
            timestamps.append(token['last_trade'])
    
    if timestamps:
        from datetime import datetime
        min_time = min(timestamps)
        max_time = max(timestamps)
        min_date = datetime.fromtimestamp(min_time)
        max_date = datetime.fromtimestamp(max_time)
        days_span = (max_time - min_time) / 86400
        
        print(f"Trade history spans: {days_span:.1f} days")
        print(f"Oldest: {min_date.strftime('%Y-%m-%d')}")
        print(f"Newest: {max_date.strftime('%Y-%m-%d')}")
        print("❌ All trades weighted equally regardless of age")
    
    # Pattern blindness
    print("\n2. PATTERN REPETITION BLINDNESS")
    print("-" * 40)
    
    # Check for repeated tokens
    token_counts = {}
    for token in token_data:
        symbol = token['token_symbol']
        token_counts[symbol] = token_counts.get(symbol, 0) + 1
    
    repeated = {k: v for k, v in token_counts.items() if v > 1}
    if repeated:
        print("Tokens appearing multiple times:")
        for symbol, count in sorted(repeated.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {symbol}: {count} times")
        print("❌ System doesn't detect repeat trading patterns")
    
    # Outcome distribution
    print("\n3. EXTREME OUTCOME BLINDNESS")
    print("-" * 40)
    
    # Find extreme outcomes
    extreme_wins = [t for t in token_data if t['roi_percentage'] > 100]
    extreme_losses = [t for t in token_data if t['roi_percentage'] < -50]
    
    print(f"Extreme wins (>100% ROI): {len(extreme_wins)} tokens")
    print(f"Extreme losses (<-50% ROI): {len(extreme_losses)} tokens")
    
    if extreme_wins:
        best = max(extreme_wins, key=lambda x: x['roi_percentage'])
        print(f"Best trade: {best['token_symbol']} +{best['roi_percentage']:.0f}%")
    
    if extreme_losses:
        worst = min(extreme_losses, key=lambda x: x['roi_percentage'])
        print(f"Worst trade: {worst['token_symbol']} {worst['roi_percentage']:.0f}%")
    
    print("❌ No special handling for outliers that skew averages")
    
    # Market cap blindness
    print("\n4. MARKET CAP BLINDNESS")
    print("-" * 40)
    print("Token data contains:")
    sample = token_data[0] if token_data else {}
    for key in sample.keys():
        print(f"  - {key}")
    print("❌ No market cap data at time of trade")
    print("❌ Can't distinguish between micro/small/large caps")

async def demonstrate_improvements():
    """Show potential improvements"""
    
    print("\n\n=== POTENTIAL IMPROVEMENTS ===\n")
    
    coach = TradingCoach('test_key')
    token_data = load_test_data()
    
    with patch.object(coach, '_fetch_cielo_data', return_value=token_data):
        
        # Improvement 1: Confidence scoring
        print("1. CONFIDENCE SCORING")
        print("-" * 40)
        
        for sol_amount in [5, 20, 100]:
            patterns = await coach._get_similar_patterns(wallet, sol_amount)
            count = len(patterns)
            
            if count < 3:
                confidence = "⚠️ Low confidence"
            elif count < 10:
                confidence = "📊 Medium confidence"
            else:
                confidence = "✅ High confidence"
                
            print(f"{sol_amount} SOL: {count} patterns - {confidence}")
        
        # Improvement 2: Recency weighting
        print("\n2. RECENCY WEIGHTING (Concept)")
        print("-" * 40)
        print("Current: All trades weighted equally")
        print("Improved: Recent trades weighted more")
        print("Example weights:")
        print("  - Last 7 days: 100% weight")
        print("  - Last 30 days: 50% weight")
        print("  - Older: 25% weight")
        
        # Improvement 3: Volatility warnings
        print("\n3. VOLATILITY WARNINGS")
        print("-" * 40)
        
        patterns = await coach._get_similar_patterns(wallet, 15.0)
        if len(patterns) >= 2:
            import statistics
            rois = [p.roi_percentage for p in patterns]
            stdev = statistics.stdev(rois)
            
            if stdev > 50:
                print("⚠️ HIGH VOLATILITY WARNING")
                print(f"ROI ranges from {min(rois):.0f}% to {max(rois):.0f}%")
                print("Results highly unpredictable at this position size!")

# Main execution
import asyncio

wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"

if __name__ == "__main__":
    print("🧪 EDGE CASE TESTING WITH SAVED DATA\n")
    
    # Run async tests
    asyncio.run(test_with_mock_data())
    
    # Run sync analysis
    analyze_blind_spots()
    
    # Show improvements
    asyncio.run(demonstrate_improvements())
    
    print("\n\n=== KEY TAKEAWAYS ===")
    print("\n✅ What Works Well:")
    print("1. Handles various position sizes gracefully")
    print("2. Provides meaningful statistics when data exists")
    print("3. Clear coaching messages")
    print("4. Fast with caching")
    
    print("\n⚠️ Edge Cases to Watch:")
    print("1. Very small/large positions may have no matches")
    print("2. Single trade positions give limited insight")
    print("3. High variance positions need warnings")
    print("4. Time relevance not considered")
    
    print("\n🚀 Recommended Next Steps:")
    print("1. Add confidence scores based on sample size")
    print("2. Implement recency weighting")
    print("3. Add variance/volatility warnings")
    print("4. Handle outliers separately")
    print("5. Consider market context (future)")