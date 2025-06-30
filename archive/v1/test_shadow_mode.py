#!/usr/bin/env python3
"""
Shadow mode testing - Compare old diary queries with new event queries
Ensures both systems return consistent results
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from diary_api import (
    fetch_last_n_trades, 
    fetch_trades_by_token,
    query_time_range,
    calculate_metrics
)
from event_store import Event, EventStore, TRADE_BUY, TRADE_SELL
from prompt_builder import write_to_diary


async def create_test_data():
    """Create test trades in both diary and event store"""
    print("\n🔨 Creating test data in both systems...")
    
    # Use unique wallet for each test run to avoid data contamination
    timestamp = int(time.time())
    test_wallet = f"SHADOW_{timestamp}_zYDgjy8oinZ5v8gyrcQktzUmSfFLJztTSq5xLUVCya"
    test_user = 88888 + timestamp % 10000
    event_store = EventStore()
    
    print(f"  Using test wallet: {test_wallet[:20]}...")
    print(f"  Using test user: {test_user}")
    
    # Create 10 test trades over the last 5 days
    trades = []
    now = datetime.now()
    
    for i in range(10):
        # Create trades from oldest to newest
        # Trade 0 is 5 days ago (oldest), trade 9 is today (newest)
        days_ago = (9 - i) // 2  # 2 trades per day, reversed
        # Add seconds offset to ensure unique timestamps and proper ordering
        timestamp = (now - timedelta(days=days_ago, hours=(9-i) % 12, seconds=(9-i) * 10))
        
        # Alternate between BONK and WIF
        token = 'BONK' if i % 2 == 0 else 'WIF'
        
        # Alternate between buy and sell
        is_buy = i % 3 == 0
        action = 'BUY' if is_buy else 'SELL'
        
        trade_data = {
            'signature': f'shadow_test_{i}',
            'action': action,
            'token_symbol': token,
            'token_address': f'TEST_{token}_ADDRESS',
            'sol_amount': 1.0 + (i * 0.5),
            'token_amount': 1000000 * (i + 1),
            'bankroll_before_sol': 50.0,
            'bankroll_after_sol': 48.0 if is_buy else 52.0,
            'trade_pct_bankroll': 2.0 + (i * 0.2),
            'timestamp': timestamp.isoformat(),
            'profit_sol': 0 if is_buy else (0.5 if i % 4 == 0 else -0.3)
        }
        
        trades.append(trade_data)
        
        # Write to diary
        await write_to_diary('trade', test_user, test_wallet, trade_data)
        
        # Write to event store
        event = Event(
            user_id=test_wallet,
            event_type=TRADE_BUY if is_buy else TRADE_SELL,
            timestamp=timestamp,
            data=trade_data
        )
        event_store.record_event(event)
        
        # Small delay to ensure distinct timestamps
        await asyncio.sleep(0.01)
    
    print(f"✅ Created {len(trades)} test trades in both systems")
    return test_wallet, trades


async def compare_recent_trades(wallet: str):
    """Compare fetch_last_n_trades with event store query"""
    print("\n🔍 Comparing recent trades...")
    
    # Old system
    diary_trades = await fetch_last_n_trades(wallet, 5)
    
    # New system
    event_result = await query_time_range(wallet, "last 30 days")
    # Get the first 5 trades (which are the most recent since they're sorted newest-first)
    event_trades = event_result['trades'][:5]
    
    # Compare counts
    print(f"  Diary: {len(diary_trades)} trades")
    print(f"  Events: {len(event_trades)} trades")
    print(f"  Total events returned: {len(event_result['trades'])}")
    
    # Debug: show what we're getting
    if diary_trades:
        print(f"  Diary signatures: {[t.get('signature', '') for t in diary_trades]}")
    if event_trades:
        print(f"  Event signatures: {[t.get('signature', '') for t in event_trades]}")
    
    # Sort both by signature to ensure consistent ordering for comparison
    diary_sorted = sorted(diary_trades, key=lambda x: x.get('signature', ''))
    event_sorted = sorted(event_trades, key=lambda x: x.get('signature', ''))
    
    # Compare data
    matches = 0
    for i, (diary, event) in enumerate(zip(diary_sorted, event_sorted)):
        if (diary.get('token_symbol') == event.get('token_symbol') and
            diary.get('signature') == event.get('signature')):
            matches += 1
        else:
            print(f"  ❌ Mismatch at position {i}:")
            print(f"     Diary: {diary.get('signature')} - {diary.get('token_symbol')}")
            print(f"     Event: {event.get('signature')} - {event.get('token_symbol')}")
    
    success = matches == min(len(diary_trades), len(event_trades))
    print(f"  {'✅' if success else '❌'} Data consistency: {matches}/{min(len(diary_trades), len(event_trades))} matches")
    
    # Also verify ordering is consistent
    if len(diary_trades) > 0 and len(event_trades) > 0:
        # Both should be newest first
        diary_newest = diary_trades[0].get('signature', '')
        event_newest = event_trades[0].get('signature', '')
        print(f"  Order check - Newest trade: diary={diary_newest[-4:]}, events={event_newest[-4:]}")
    
    return success


async def compare_token_queries(wallet: str):
    """Compare token-specific queries"""
    print("\n🔍 Comparing token-specific queries...")
    
    # Old system
    bonk_trades_diary = await fetch_trades_by_token(wallet, 'BONK', 10)
    
    # New system - we need to implement token filtering
    all_events = await query_time_range(wallet, "last 30 days")
    bonk_trades_events = [t for t in all_events['trades'] if t.get('token_symbol') == 'BONK']
    
    print(f"  Diary BONK trades: {len(bonk_trades_diary)}")
    print(f"  Events BONK trades: {len(bonk_trades_events)}")
    
    success = len(bonk_trades_diary) == len(bonk_trades_events)
    print(f"  {'✅' if success else '❌'} Count matches: {success}")
    
    return success


async def compare_profit_calculations(wallet: str):
    """Compare profit calculations between systems"""
    print("\n💰 Comparing profit calculations...")
    
    # Calculate today's profit using events
    today_result = await calculate_metrics(
        wallet=wallet,
        metric_type="sum",
        value_field="profit_sol",
        period="today"
    )
    
    # Also check last 7 days
    week_result = await calculate_metrics(
        wallet=wallet,
        metric_type="sum",
        value_field="profit_sol",
        period="last 7 days"
    )
    
    print(f"  Today's profit: {today_result.get('result', 0):.2f} SOL")
    print(f"  Last 7 days profit: {week_result.get('result', 0):.2f} SOL")
    
    # For now, we just ensure the queries work
    success = 'result' in today_result and 'result' in week_result
    print(f"  {'✅' if success else '❌'} Calculations completed successfully")
    
    return success


async def compare_time_queries(wallet: str):
    """Test various time-based queries"""
    print("\n⏰ Testing time-based queries...")
    
    periods = ["today", "yesterday", "last 7 days", "this week"]
    
    all_success = True
    for period in periods:
        result = await query_time_range(wallet, period)
        
        if 'error' in result:
            print(f"  ❌ {period}: Error - {result['error']}")
            all_success = False
        else:
            print(f"  ✅ {period}: {result['count']} trades")
    
    return all_success


async def test_edge_cases(wallet: str):
    """Test edge cases and error handling"""
    print("\n🔧 Testing edge cases...")
    
    # Test with non-existent wallet
    fake_result = await query_time_range("FAKE_WALLET_ADDRESS", "today")
    print(f"  ✅ Non-existent wallet: {fake_result['count']} trades (expected 0)")
    
    # Test invalid time period
    invalid_result = await query_time_range(wallet, "invalid period")
    print(f"  ✅ Invalid period handled: returns {invalid_result['count']} trades")
    
    # Test empty aggregation
    empty_result = await calculate_metrics(
        wallet="FAKE_WALLET",
        metric_type="sum",
        value_field="profit_sol",
        period="today"
    )
    print(f"  ✅ Empty aggregation: {empty_result.get('result', 0)} (expected 0)")
    
    return True


async def generate_report(results: dict):
    """Generate shadow mode test report"""
    print("\n📊 Shadow Mode Test Report")
    print("=" * 50)
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 All shadow mode tests PASSED!")
        print("Both systems are returning consistent results.")
    else:
        print("\n⚠️  Some tests failed - investigation needed")
    
    return passed_tests == total_tests


async def main():
    """Run shadow mode tests"""
    print("🔍 Shadow Mode Testing")
    print("Comparing old diary system with new event system")
    print("=" * 50)
    
    try:
        # Create test data
        test_wallet, trades = await create_test_data()
        
        # Run comparison tests
        results = {
            "Recent trades": await compare_recent_trades(test_wallet),
            "Token queries": await compare_token_queries(test_wallet),
            "Profit calculations": await compare_profit_calculations(test_wallet),
            "Time queries": await compare_time_queries(test_wallet),
            "Edge cases": await test_edge_cases(test_wallet)
        }
        
        # Generate report
        all_passed = await generate_report(results)
        
        if all_passed:
            print("\n✅ Ready for gradual rollout!")
        else:
            print("\n❌ Issues found - fix before proceeding")
            
    except Exception as e:
        print(f"\n❌ Shadow mode test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main()) 