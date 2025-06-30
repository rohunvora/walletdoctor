#!/usr/bin/env python3
"""
Quick test to demonstrate system-level improvements
"""

import asyncio
from test_gpt_integration import test_gpt
from test_bot_scenarios import TradeEvent
from datetime import datetime, timedelta

async def test_improvements():
    """Test the system improvements with a concrete example"""
    
    # Create a test context with FINNA trades
    base_time = datetime.now() - timedelta(minutes=30)
    
    trades = [
        TradeEvent(
            action="BUY",
            token="FINNA",
            amount_sol=10.0,
            signature="buy_sig",
            timestamp=base_time,
            market_cap=771_000,
            bankroll_before=40.0,
            bankroll_after=30.0
        ),
        TradeEvent(
            action="SELL", 
            token="FINNA",
            amount_sol=3.0,  # Partial sell - 30%
            signature="sell_sig",
            timestamp=base_time + timedelta(minutes=5),
            market_cap=800_000,
            bankroll_before=30.0,
            bankroll_after=33.0
        )
    ]
    
    context = {
        'trades': trades,
        'current_bankroll': 33.0,
        'user_profile': type('Profile', (), {
            'typical_position_size_pct': (5.0, 10.0),
            'typical_mcap_range': (500_000, 2_000_000),
            'goal': '100 sol'
        })()
    }
    
    print("=== Testing System Improvements ===\n")
    
    # Test 1: P&L Calculation
    print("1. Testing P&L calculation:")
    print("   User: 'finna pnl?'")
    response1, tools1 = await test_gpt.get_response(context, "finna pnl?")
    print(f"   Bot: {response1}")
    print(f"   Tools called: {tools1}")
    print()
    
    # Test 2: Follow-up context
    print("2. Testing follow-up context:")
    print("   User: 'why risky?'")
    response2, tools2 = await test_gpt.get_response(context, "why risky?")
    print(f"   Bot: {response2}")
    print(f"   Expected: Should mention FINNA and/or 771k mcap")
    print()
    
    # Test 3: Position state
    print("3. Testing position state:")
    print("   User: 'finna position?'")
    response3, tools3 = await test_gpt.get_response(context, "finna position?")
    print(f"   Bot: {response3}")
    print(f"   Tools called: {tools3}")
    print(f"   Expected: Should mention 7 sol remaining (70%)")
    print()
    
    # Test 4: Trade notification with large position
    large_trade = TradeEvent(
        action="BUY",
        token="POPCAT",
        amount_sol=8.25,  # 25% of bankroll!
        signature="large_buy",
        timestamp=datetime.now(),
        market_cap=1_200_000,
        bankroll_before=33.0,
        bankroll_after=24.75
    )
    
    context['trades'].append(large_trade)
    context['current_bankroll'] = 24.75
    
    print("4. Testing unusual position size recognition:")
    print("   [Trade notification: Bought 8.25 SOL of POPCAT (25% of bankroll)]")
    # Simulate a trade notification by passing empty message with recent trade
    response4, tools4 = await test_gpt.get_response(context, "just bought popcat")
    print(f"   Bot: {response4}")
    print(f"   Expected: Should mention the large position size")
    print()

if __name__ == "__main__":
    asyncio.run(test_improvements()) 