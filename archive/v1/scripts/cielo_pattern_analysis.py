#!/usr/bin/env python3
"""
Analyze Cielo data to understand what we can use for pattern-based coaching
"""

import json
import os
from datetime import datetime
from collections import defaultdict

def analyze_cielo_results():
    """Analyze the Cielo API test results"""
    
    with open('cielo_api_test_results.json', 'r') as f:
        data = json.load(f)
    
    # Extract token PNL data
    token_pnl_data = None
    for result in data['results']:
        if result['endpoint'] == 'Token PNL' and result['status'] == 'success':
            token_pnl_data = result['data']['data']['items']
            break
    
    if not token_pnl_data:
        print("No token PNL data found")
        return
    
    print(f"=== CIELO DATA ANALYSIS ===\n")
    print(f"Total tokens from Cielo: {len(token_pnl_data)}")
    
    # Analyze what data we have
    print("\n1. DATA AVAILABLE PER TOKEN:")
    first_token = token_pnl_data[0]
    for key in first_token.keys():
        print(f"   - {key}: {type(first_token[key]).__name__}")
    
    # Group tokens by patterns we can detect
    print("\n2. PATTERNS WE CAN DETECT WITH CIELO DATA:")
    
    # Pattern 1: Group by buy amount ranges
    buy_ranges = defaultdict(list)
    ranges = [(0, 500), (500, 1000), (1000, 5000), (5000, 10000), (10000, float('inf'))]
    
    for token in token_pnl_data:
        avg_buy = token['total_buy_usd'] / token['num_swaps'] if token['num_swaps'] > 0 else 0
        for low, high in ranges:
            if low <= avg_buy < high:
                buy_ranges[f"${low}-${high if high != float('inf') else '∞'}"].append(token)
                break
    
    print("\n   Buy Amount Distribution:")
    for range_name, tokens in sorted(buy_ranges.items()):
        avg_roi = sum(t['roi_percentage'] for t in tokens) / len(tokens) if tokens else 0
        win_rate = sum(1 for t in tokens if t['roi_percentage'] > 0) / len(tokens) * 100 if tokens else 0
        print(f"   - {range_name}: {len(tokens)} tokens, avg ROI: {avg_roi:.1f}%, win rate: {win_rate:.1f}%")
    
    # Pattern 2: Group by holding time
    print("\n   Holding Time Patterns:")
    time_ranges = [
        (0, 300, "< 5 min"),
        (300, 1800, "5-30 min"),
        (1800, 7200, "30 min - 2 hrs"),
        (7200, 86400, "2-24 hrs"),
        (86400, float('inf'), "> 24 hrs")
    ]
    
    time_groups = defaultdict(list)
    for token in token_pnl_data:
        holding_time = token.get('holding_time_seconds', 0)
        for low, high, label in time_ranges:
            if low <= holding_time < high:
                time_groups[label].append(token)
                break
    
    for label, tokens in time_groups.items():
        avg_roi = sum(t['roi_percentage'] for t in tokens) / len(tokens) if tokens else 0
        print(f"   - {label}: {len(tokens)} tokens, avg ROI: {avg_roi:.1f}%")
    
    # Pattern 3: Find similar trades for coaching
    print("\n3. EXAMPLE PATTERN MATCHING:")
    
    # Take a sample token and find similar ones
    sample_token = next((t for t in token_pnl_data if t['roi_percentage'] < -10), token_pnl_data[0])
    sample_avg_buy = sample_token['total_buy_usd'] / sample_token['num_swaps']
    
    print(f"\n   Sample trade: {sample_token['token_symbol']}")
    print(f"   - Avg buy: ${sample_avg_buy:.0f}")
    print(f"   - ROI: {sample_token['roi_percentage']:.1f}%")
    print(f"   - Swaps: {sample_token['num_swaps']}")
    
    # Find similar trades (±30% buy amount)
    similar = []
    for token in token_pnl_data:
        if token['token_address'] == sample_token['token_address']:
            continue
        token_avg_buy = token['total_buy_usd'] / token['num_swaps'] if token['num_swaps'] > 0 else 0
        if sample_avg_buy * 0.7 <= token_avg_buy <= sample_avg_buy * 1.3:
            similar.append(token)
    
    similar = sorted(similar, key=lambda x: x['roi_percentage'], reverse=True)[:3]
    
    print(f"\n   Similar trades by buy amount:")
    for t in similar:
        avg_buy = t['total_buy_usd'] / t['num_swaps']
        print(f"   - {t['token_symbol']}: ${avg_buy:.0f} avg buy → {t['roi_percentage']:.1f}% ROI")
    
    # What we're missing
    print("\n4. LIMITATIONS FOR PATTERN COACHING:")
    print("   ❌ No market cap at time of trade")
    print("   ❌ No SOL amounts (only USD)")
    print("   ❌ No individual trade details")
    print("   ❌ Can't match by 'bought at ~3M mcap'")
    print("   ✅ Can match by USD amount ranges")
    print("   ✅ Can analyze by holding time")
    print("   ✅ Can show P&L outcomes")

    # Recommendation
    print("\n5. HYBRID APPROACH NEEDED:")
    print("   1. Use Helius to get market cap at trade time")
    print("   2. Use Cielo for P&L calculations")
    print("   3. Combine for pattern matching:")
    print("      - Helius: mcap, SOL amounts, trade timing")
    print("      - Cielo: P&L, ROI, win rates")

if __name__ == "__main__":
    analyze_cielo_results()