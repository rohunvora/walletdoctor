#!/usr/bin/env python3
"""
Quick Analytics Test - Run after deployment to verify everything works
"""

import asyncio
from datetime import datetime
from diary_api import query_time_range, calculate_metrics, compare_periods, get_goal_progress
from event_store import EventStore


async def test_analytics():
    """Quick test of analytics functionality"""
    print("🧪 Quick Analytics Test")
    print("=" * 40)
    
    # Use your actual wallet address here
    test_wallet = input("Enter a wallet address to test (or press Enter for mock): ").strip()
    if not test_wallet:
        test_wallet = "MOCK_WALLET_ADDRESS"
        print("Using mock wallet address")
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: Time range query
    print("\n1️⃣ Testing time range query...")
    tests_total += 1
    try:
        result = await query_time_range(test_wallet, "today")
        print(f"✅ Today's trades: {result['count']} trades")
        print(f"   Period: {result['start_time'][:10]} to {result['end_time'][:10]}")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: Calculate metrics
    print("\n2️⃣ Testing metric calculation...")
    tests_total += 1
    try:
        result = await calculate_metrics(
            wallet=test_wallet,
            metric_type="sum",
            value_field="profit_sol",
            period="last 7 days"
        )
        print(f"✅ Last 7 days profit: {result.get('result', 0):.2f} SOL")
        print(f"   Events processed: {result.get('event_count', 0)}")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 3: Period comparison
    print("\n3️⃣ Testing period comparison...")
    tests_total += 1
    try:
        result = await compare_periods(
            wallet=test_wallet,
            period1="last week",
            period2="this week"
        )
        comparison = result.get('comparison', {})
        if 'change_pct' in comparison:
            print(f"✅ This week vs last: {comparison['change_pct']:.1f}% change")
        else:
            print(f"✅ Comparison completed (no data for percentage)")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 4: Goal progress (might not have goal)
    print("\n4️⃣ Testing goal progress...")
    tests_total += 1
    try:
        # Mock user_id for testing
        result = await get_goal_progress(12345, test_wallet)
        if result.get('has_goal'):
            print(f"✅ Goal progress: {result}")
        else:
            print(f"✅ No goal set (expected for new users)")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 5: Event store query
    print("\n5️⃣ Testing event store directly...")
    tests_total += 1
    try:
        event_store = EventStore()
        count = event_store.count_events(user_id=test_wallet)
        print(f"✅ Event store has {count} events for this wallet")
        tests_passed += 1
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 6: Natural language parsing
    print("\n6️⃣ Testing time parsing...")
    tests_total += 1
    try:
        from time_utils import parse_time_string
        
        test_phrases = ["today", "yesterday", "last 3 days", "this week"]
        all_parsed = True
        
        for phrase in test_phrases:
            parsed = parse_time_string(phrase)
            if parsed:
                print(f"   ✓ '{phrase}' → {parsed.strftime('%Y-%m-%d')}")
            else:
                print(f"   ✗ '{phrase}' failed to parse")
                all_parsed = False
        
        if all_parsed:
            print("✅ All time phrases parsed correctly")
            tests_passed += 1
        else:
            print("❌ Some time phrases failed")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Summary
    print("\n" + "=" * 40)
    print(f"📊 Results: {tests_passed}/{tests_total} tests passed")
    
    if tests_passed == tests_total:
        print("\n✅ All analytics features working!")
        print("The bot should now respond to:")
        print("  - 'how am i doing today'")
        print("  - 'profit this week?'")
        print("  - 'am i improving?'")
        print("  - 'what's my daily average'")
    else:
        print("\n⚠️ Some tests failed - check the errors above")
        print("Common issues:")
        print("  - Database not migrated (run db_migrations.py)")
        print("  - Event store not recording (check dual-write)")
        print("  - No historical data yet (wait for some trades)")
    
    return tests_passed == tests_total


if __name__ == "__main__":
    asyncio.run(test_analytics()) 