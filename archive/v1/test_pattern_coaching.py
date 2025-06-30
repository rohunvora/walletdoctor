#!/usr/bin/env python3
"""
Test the pattern-based coaching system end-to-end
"""

import asyncio
import sys
sys.path.append('.')

from scripts.similar_trades import find_similar_trades, format_similar_trades_message, analyze_pattern_performance

async def test_pattern_coaching():
    """Test pattern-based coaching with real scenarios"""
    
    print("=== PATTERN-BASED COACHING TEST ===\n")
    
    # Test wallet
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    # Test scenarios
    scenarios = [
        {
            "name": "Small cap degen play",
            "market_cap": 2_500_000,  # 2.5M
            "sol_amount": 10.0,
            "message": "just bought PEPE"
        },
        {
            "name": "Mid cap momentum",
            "market_cap": 25_000_000,  # 25M
            "sol_amount": 5.0,
            "message": "aped into POPCAT"
        },
        {
            "name": "Micro cap gamble",
            "market_cap": 500_000,  # 500K
            "sol_amount": 3.0,
            "message": "bought this new launch"
        }
    ]
    
    for scenario in scenarios:
        print(f"\n{'='*60}")
        print(f"Scenario: {scenario['name']}")
        print(f"User: \"{scenario['message']}\"")
        print(f"Token market cap: ${scenario['market_cap']:,.0f}")
        print(f"SOL spent: {scenario['sol_amount']}")
        print('-'*60)
        
        # Find similar trades
        similar = find_similar_trades(
            wallet_address=wallet,
            current_market_cap=scenario['market_cap'],
            current_sol_amount=scenario['sol_amount']
        )
        
        if not similar:
            print("No similar historical trades found")
            continue
            
        # Format the pattern message
        pattern_msg = format_similar_trades_message(similar)
        
        # Analyze performance
        analysis = analyze_pattern_performance(similar)
        
        # Build coaching response
        print(f"\nBot would say:")
        print(f"\"last {len(similar)} times you bought ~{scenario['market_cap']/1_000_000:.1f}M coins "
              f"with ~{scenario['sol_amount']:.0f} SOL: {pattern_msg}")
        
        if analysis and analysis.get('win_rate') is not None:
            win_pct = analysis['win_rate'] * 100
            avg_pnl = analysis['avg_pnl_sol']
            
            if win_pct < 40:
                print(f"\nbasically {win_pct:.0f}% win rate on these. what's the thought process?\"")
            elif avg_pnl < 0:
                print(f"\naverage {avg_pnl:+.1f} SOL on these plays. what caught your eye this time?\"")
            else:
                print(f"\nthese have worked {win_pct:.0f}% of the time for you. similar setup here?\"")
        
        # Show what would be logged
        print(f"\n[Bot would then log the user's reasoning and any price targets]")
        
        # Show detailed breakdown
        print(f"\nDetailed pattern breakdown:")
        for i, trade in enumerate(similar[:3], 1):
            print(f"{i}. {trade['token_symbol']} @ {trade['entry_mcap_formatted']}")
            print(f"   Bought with: {trade['initial_sol']:.1f} SOL")
            print(f"   Status: {trade['position_status']}")
            if trade['pnl_sol'] is not None:
                print(f"   P&L: {trade['pnl_sol']:+.1f} SOL")

async def test_integration_flow():
    """Test the full conversation flow"""
    
    print("\n\n=== FULL CONVERSATION FLOW TEST ===\n")
    
    conversation = [
        ("user", "just bought PEPE"),
        ("bot", "last 3 times you bought ~3M coins with ~10 SOL: BONK (-6.2), WIF (+15.3), SILLY (-8.1). what's the thesis here?"),
        ("user", "it4i said it's going to moon"),
        ("bot", "it4i alpha. noted. want me to set any reminders?"),
        ("user", "yeah let me know at 2x or -50%"),
        ("bot", "got it. will ping at 6M mcap or 5 SOL value")
    ]
    
    for speaker, message in conversation:
        if speaker == "user":
            print(f"👤 User: {message}")
        else:
            print(f"🤖 Bot: {message}")
        await asyncio.sleep(0.5)  # Simulate conversation pace
    
    print("\n[Bot stores: 'PEPE bought because it4i alpha', 'PEPE alert at 2x or -50%']")

if __name__ == "__main__":
    asyncio.run(test_pattern_coaching())
    asyncio.run(test_integration_flow())