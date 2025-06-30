#!/usr/bin/env python3
"""
Demo of pattern-based coaching using real Cielo data
Shows what the end user will actually see
"""

import json
import random
from datetime import datetime

def load_cielo_data():
    """Load the actual Cielo data we retrieved"""
    with open('cielo_api_test_results.json', 'r') as f:
        data = json.load(f)
    
    # Extract token PNL data
    for result in data['results']:
        if result['endpoint'] == 'Token PNL' and result['status'] == 'success':
            return result['data']['data']['items']
    return []

def format_sol_amount(usd_amount):
    """Convert USD to SOL (rough estimate at $150/SOL)"""
    return usd_amount / 150

def find_similar_patterns(tokens, target_usd, tolerance=0.3):
    """Find tokens with similar buy amounts"""
    similar = []
    
    for token in tokens:
        if token['num_swaps'] == 0:
            continue
            
        avg_buy_usd = token['total_buy_usd'] / token['num_swaps']
        
        # Check if within tolerance range
        if target_usd * (1-tolerance) <= avg_buy_usd <= target_usd * (1+tolerance):
            similar.append({
                'symbol': token['token_symbol'],
                'name': token['token_name'],
                'avg_buy_usd': avg_buy_usd,
                'avg_buy_sol': format_sol_amount(avg_buy_usd),
                'roi': token['roi_percentage'],
                'pnl_usd': token['total_pnl_usd'],
                'pnl_sol': format_sol_amount(token['total_pnl_usd']),
                'holding_time': token['holding_time_seconds'] / 3600,  # hours
                'num_trades': token['num_swaps']
            })
    
    # Sort by ROI for better presentation
    similar.sort(key=lambda x: x['roi'], reverse=True)
    return similar

def generate_coaching_message(patterns, current_sol):
    """Generate the actual coaching message users will see"""
    
    if not patterns:
        return {
            'message': f"No historical data found for ~{current_sol:.1f} SOL trades. This would be a new position size for you.",
            'coaching': "Starting with a new position size? Consider your risk management.",
            'emoji': '🆕'
        }
    
    # Take top 3-5 patterns
    show_patterns = patterns[:5]
    
    # Calculate statistics
    total_trades = len(patterns)
    winners = [p for p in patterns if p['roi'] > 0]
    win_rate = len(winners) / total_trades * 100 if total_trades > 0 else 0
    avg_roi = sum(p['roi'] for p in patterns) / len(patterns)
    
    # Format pattern lines
    pattern_lines = []
    for p in show_patterns:
        emoji = '🟢' if p['roi'] > 0 else '🔴'
        roi_sign = '+' if p['roi'] > 0 else ''
        pnl_sign = '+' if p['pnl_sol'] > 0 else ''
        
        line = f"{emoji} {p['symbol']}: {p['avg_buy_sol']:.1f} SOL → {roi_sign}{p['roi']:.1f}% ({pnl_sign}{p['pnl_sol']:.1f} SOL)"
        pattern_lines.append(line)
    
    # Build message
    message_parts = [
        f"**Last {min(5, total_trades)} times you bought with ~{current_sol:.1f} SOL:**",
        "",
        *pattern_lines,
        "",
        f"📊 **Pattern Stats**: {win_rate:.0f}% win rate, {avg_roi:+.1f}% avg return"
    ]
    
    message = "\n".join(message_parts)
    
    # Generate contextual coaching
    if win_rate < 30:
        coaching = "This position size hasn't worked well. Consider smaller size or different strategy?"
        emoji = '⚠️'
    elif win_rate > 70:
        coaching = "Strong track record with this size! Stick to what works."
        emoji = '✅'
    elif avg_roi < -20:
        coaching = "Heavy losses at this size. What will you do differently?"
        emoji = '🤔'
    else:
        coaching = "Mixed results. What's your edge this time?"
        emoji = '🎯'
    
    return {
        'message': message,
        'coaching': coaching,
        'emoji': emoji,
        'stats': {
            'total_patterns': total_trades,
            'win_rate': win_rate,
            'avg_roi': avg_roi
        }
    }

def demo_user_scenarios():
    """Demo what users will actually see"""
    
    print("=== PATTERN-BASED COACHING DEMO ===\n")
    print("Showing actual output users will see in Telegram:\n")
    
    tokens = load_cielo_data()
    
    # Scenario 1: Small position
    print("="*60)
    print("SCENARIO 1: User considering a 5 SOL trade")
    print("-"*60)
    
    patterns = find_similar_patterns(tokens, 5 * 150, tolerance=0.5)  # 5 SOL = $750
    result = generate_coaching_message(patterns, 5)
    
    print(result['message'])
    print(f"\n{result['emoji']} {result['coaching']}")
    
    # Scenario 2: Medium position
    print("\n" + "="*60)
    print("SCENARIO 2: User considering a 20 SOL trade")
    print("-"*60)
    
    patterns = find_similar_patterns(tokens, 20 * 150, tolerance=0.5)  # 20 SOL = $3000
    result = generate_coaching_message(patterns, 20)
    
    print(result['message'])
    print(f"\n{result['emoji']} {result['coaching']}")
    
    # Scenario 3: Large position
    print("\n" + "="*60)
    print("SCENARIO 3: User considering a 50 SOL trade")
    print("-"*60)
    
    patterns = find_similar_patterns(tokens, 50 * 150, tolerance=0.5)  # 50 SOL = $7500
    result = generate_coaching_message(patterns, 50)
    
    print(result['message'])
    print(f"\n{result['emoji']} {result['coaching']}")
    
    # Show how it integrates with trading flow
    print("\n" + "="*60)
    print("INTEGRATION EXAMPLE: Full Trading Flow")
    print("="*60)
    
    print("\n🤖 **Trading Assistant**")
    print("\nUser: /buy NEWTOKEN 15")
    print("\nBot response:")
    print("-"*40)
    
    # Find patterns for 15 SOL
    patterns = find_similar_patterns(tokens, 15 * 150, tolerance=0.5)
    result = generate_coaching_message(patterns, 15)
    
    print(result['message'])
    print(f"\n{result['emoji']} {result['coaching']}")
    print("\n💭 _What's your thesis?_")
    print("\n[Execute Trade] [Cancel]")

def show_value_propositions():
    """Show why this is valuable for users"""
    
    print("\n" + "="*60)
    print("VALUE FOR USERS")
    print("="*60)
    
    print("\n✅ **What users get:**")
    print("1. Instant pattern recognition before trades")
    print("2. Historical performance at similar position sizes")
    print("3. Contextual coaching based on their track record")
    print("4. Encouragement to think before acting")
    
    print("\n📈 **Example outcomes:**")
    print("- User sees they lose 80% of the time with 50 SOL trades → reduces position size")
    print("- User sees strong 70% win rate with 10 SOL trades → maintains discipline")
    print("- User notices patterns in their losses → adjusts strategy")
    
    print("\n🎯 **End result:**")
    print("Better trading decisions through self-awareness")

if __name__ == "__main__":
    demo_user_scenarios()
    show_value_propositions()