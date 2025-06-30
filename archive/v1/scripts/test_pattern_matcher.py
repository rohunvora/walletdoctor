#!/usr/bin/env python3
"""
Test the pattern matcher with real scenarios
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.pattern_matcher import get_trade_patterns
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_pattern_scenarios():
    """Test various trading scenarios"""
    
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    print("=== PATTERN-BASED COACHING SYSTEM TEST ===\n")
    
    # Test scenarios that match user's typical trading patterns
    scenarios = [
        {
            "name": "Small cap gamble",
            "market_cap": 3_000_000,  # $3M
            "sol_amount": 10,         # 10 SOL
            "description": "Typical pump.fun launch play"
        },
        {
            "name": "Mid cap momentum",
            "market_cap": 50_000_000,  # $50M
            "sol_amount": 50,          # 50 SOL
            "description": "Established token with momentum"
        },
        {
            "name": "Micro cap degen",
            "market_cap": 500_000,     # $500k
            "sol_amount": 5,           # 5 SOL
            "description": "Ultra high risk micro cap"
        },
        {
            "name": "Blue chip position",
            "market_cap": 500_000_000,  # $500M
            "sol_amount": 100,          # 100 SOL
            "description": "Larger established project"
        }
    ]
    
    for scenario in scenarios:
        print(f"\n{'='*60}")
        print(f"SCENARIO: {scenario['name']}")
        print(f"Description: {scenario['description']}")
        print(f"Parameters: ${scenario['market_cap']/1e6:.1f}M mcap, {scenario['sol_amount']} SOL")
        print("-" * 60)
        
        # Get coaching data
        result = await get_trade_patterns(
            wallet=wallet,
            current_market_cap=scenario['market_cap'],
            current_sol_amount=scenario['sol_amount']
        )
        
        if result['success']:
            print(f"\n{result['message']}")
            print(f"\n💭 {result['coaching_prompt']}")
            
            if result.get('statistics'):
                stats = result['statistics']
                print(f"\n📊 Pattern Stats:")
                print(f"   - Occurrences: {stats['pattern_count']}")
                print(f"   - Win Rate: {stats['win_rate']:.0f}%")
                print(f"   - Avg ROI: {stats['avg_roi']:.1f}%")
                print(f"   - Total P&L: ${stats['total_pnl']:.0f}")
        else:
            print(f"\n❌ {result['message']}")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")


async def test_specific_trade():
    """Test a specific trade the user is considering"""
    
    print("\n=== SPECIFIC TRADE ANALYSIS ===\n")
    
    # Example: User is looking at a new token
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    # Let's say they're looking at a $2M mcap token with 15 SOL
    result = await get_trade_patterns(
        wallet=wallet,
        current_market_cap=2_000_000,
        current_sol_amount=15
    )
    
    if result['success']:
        print("📈 HISTORICAL PATTERN ANALYSIS")
        print("-" * 40)
        print(result['message'])
        print(f"\n🤖 COACH: {result['coaching_prompt']}")
        
        # Show how this would appear in the Telegram bot
        print("\n\n📱 TELEGRAM BOT OUTPUT:")
        print("-" * 40)
        telegram_msg = (
            f"🔍 **Pattern Analysis**\n\n"
            f"{result['message']}\n"
            f"_{result['coaching_prompt']}_"
        )
        print(telegram_msg)


# Add this to demonstrate caching efficiency
async def test_performance():
    """Test caching and performance"""
    
    print("\n=== PERFORMANCE TEST ===\n")
    
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    import time
    
    # First call - will hit APIs
    start = time.time()
    result1 = await get_trade_patterns(wallet, 5_000_000, 20)
    time1 = time.time() - start
    
    # Second call - should use cache
    start = time.time()
    result2 = await get_trade_patterns(wallet, 5_000_000, 20)
    time2 = time.time() - start
    
    print(f"First call (cold): {time1:.2f}s")
    print(f"Second call (cached): {time2:.2f}s")
    print(f"Speed improvement: {time1/time2:.1f}x faster")


if __name__ == "__main__":
    # Run all tests
    asyncio.run(test_pattern_scenarios())
    asyncio.run(test_specific_trade())
    asyncio.run(test_performance())