#!/usr/bin/env python3
"""
Test the pattern-based coaching system with real data
"""

import asyncio
import sys
sys.path.append('.')

from scripts.find_similar_trades_v2 import find_similar_trades, format_similar_trades_message, analyze_pattern_performance

async def test_pattern_coaching():
    """Test pattern-based coaching with real wallet data"""
    
    print("=== PATTERN-BASED COACHING TEST ===\n")
    
    # Test wallet with real trades
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    # Test scenarios based on actual trading patterns
    scenarios = [
        {
            "name": "Small cap play (like FINNA)",
            "market_cap": 800_000,  # 800K
            "sol_amount": 2.0,
            "message": "just bought PEPE"
        },
        {
            "name": "Low mcap gamble",
            "market_cap": 400_000,  # 400K
            "sol_amount": 4.0,
            "message": "aped into this new launch"
        },
        {
            "name": "Larger position",
            "market_cap": 1_200_000,  # 1.2M
            "sol_amount": 20.0,
            "message": "bought YOURSELF"
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
            print("\nBot would say:")
            print("\"first time buying at this mcap/size combo. what's the thesis?\"")
            continue
            
        # Format the pattern message
        pattern_msg = format_similar_trades_message(similar)
        
        # Analyze performance
        analysis = analyze_pattern_performance(similar)
        
        # Build coaching response
        print(f"\nFound {len(similar)} similar trades:")
        for i, trade in enumerate(similar[:3], 1):
            status = f" ({trade['pnl_sol']:+.1f} SOL)" if trade['pnl_sol'] is not None else " (holding)"
            print(f"  {i}. {trade['token_symbol']} @ {trade['entry_mcap_formatted']}: {trade['initial_sol']:.1f} SOL{status}")
        
        print(f"\nBot would say:")
        print(f"\"last {len(similar)} times you bought ~${scenario['market_cap']/1_000_000:.1f}M coins "
              f"with ~{scenario['sol_amount']:.0f} SOL: {pattern_msg}")
        
        if analysis and analysis.get('win_rate') is not None:
            win_pct = analysis['win_rate'] * 100
            avg_pnl = analysis['avg_pnl_sol']
            
            if win_pct < 40 and analysis['closed_count'] > 0:
                print(f"\nbasically {win_pct:.0f}% win rate on these. what's the thought process?\"")
            elif avg_pnl < 0 and analysis['closed_count'] > 0:
                print(f"\naverage {avg_pnl:+.1f} SOL on these plays. what caught your eye this time?\"")
            elif analysis.get('all_holding'):
                print(f"\nstill holding all {analysis['sample_size']} similar trades. exit strategy for this one?\"")
            else:
                print(f"\nthese have worked {win_pct:.0f}% of the time for you. similar setup here?\"")
        
        # Show what happens next
        print(f"\n[User would explain reasoning]")
        print(f"[Bot would log the reasoning and offer to set alerts]")

async def test_full_conversation():
    """Simulate a full conversation flow"""
    
    print("\n\n=== SIMULATED CONVERSATION FLOW ===\n")
    
    # Find a real trade pattern
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    similar = find_similar_trades(wallet, 1_000_000, 2.0)
    pattern_msg = format_similar_trades_message(similar)
    
    conversation = [
        ("user", "just bought PEPE"),
        ("bot", f"last {len(similar)} times you bought ~1M coins with ~2 SOL: {pattern_msg}. what's the thesis here?"),
        ("user", "CT is saying it's the next BONK"),
        ("bot", "CT hype play. noted. want me to set any reminders?"),
        ("user", "yeah let me know at 2x or -50%"),
        ("bot", "got it. will ping at 2M mcap or 1 SOL value")
    ]
    
    for speaker, message in conversation:
        if speaker == "user":
            print(f"👤 User: {message}")
        else:
            print(f"🤖 Bot: {message}")
        await asyncio.sleep(0.5)
    
    print("\n[Bot stores: 'PEPE bought because CT hype', 'PEPE alert at 2x or -50%']")
    
    print("\n✅ This creates value by:")
    print("1. Showing historical performance on similar trades")
    print("2. Forcing articulation of reasoning")
    print("3. Creating accountability with alerts")
    print("4. Building a record of what works/doesn't")

if __name__ == "__main__":
    asyncio.run(test_pattern_coaching())
    asyncio.run(test_full_conversation())