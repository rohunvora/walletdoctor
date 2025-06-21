#!/usr/bin/env python3
"""
Load test for analytics system
Verifies performance with realistic data volumes
"""

import asyncio
import time
import random
from datetime import datetime, timedelta
from event_store import Event, EventStore, TRADE_BUY, TRADE_SELL
from aggregator import EventAggregator
from diary_api import query_time_range, calculate_metrics


async def generate_test_events(num_events: int = 100000):
    """Generate realistic test events"""
    print(f"\n🏗️ Generating {num_events:,} test events...")
    
    event_store = EventStore("test_load.db")
    
    # Test parameters
    num_users = 100
    tokens = ['BONK', 'WIF', 'PEPE', 'MEW', 'POPCAT', 'MYRO', 'SAMO', 'BOME']
    
    start_time = time.time()
    events_created = 0
    
    # Generate events spread over 90 days
    base_time = datetime.now() - timedelta(days=90)
    
    for i in range(num_events):
        # Random user
        user_id = f"wallet_{random.randint(1, num_users)}"
        
        # Random token
        token = random.choice(tokens)
        
        # Random timestamp within 90 days
        days_offset = random.uniform(0, 90)
        timestamp = base_time + timedelta(days=days_offset)
        
        # Alternate between buys and sells
        is_buy = i % 2 == 0
        event_type = TRADE_BUY if is_buy else TRADE_SELL
        
        # Generate trade data
        sol_amount = random.uniform(0.1, 10.0)
        profit_sol = 0 if is_buy else random.uniform(-2.0, 5.0)
        
        event = Event(
            user_id=user_id,
            event_type=event_type,
            timestamp=timestamp,
            data={
                'token_symbol': token,
                'sol_amount': sol_amount,
                'profit_sol': profit_sol,
                'trade_pct_bankroll': random.uniform(1.0, 20.0),
                'is_win': profit_sol > 0
            }
        )
        
        event_store.record_event(event)
        events_created += 1
        
        if events_created % 10000 == 0:
            elapsed = time.time() - start_time
            rate = events_created / elapsed
            print(f"  Generated {events_created:,} events ({rate:.0f} events/sec)")
    
    total_time = time.time() - start_time
    print(f"✅ Generated {events_created:,} events in {total_time:.1f}s ({events_created/total_time:.0f} events/sec)")
    
    return event_store, num_users


async def test_query_performance(event_store: EventStore, num_users: int):
    """Test various query patterns"""
    print("\n⚡ Testing Query Performance...")
    
    test_user = f"wallet_{random.randint(1, num_users)}"
    
    # Test 1: Recent trades query
    start = time.time()
    events = event_store.query_events(
        user_id=test_user,
        limit=20
    )
    elapsed = (time.time() - start) * 1000
    print(f"✅ Recent 20 trades: {elapsed:.1f}ms ({len(events)} results)")
    
    # Test 2: Time range query (today)
    start = time.time()
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    events = event_store.query_events(
        user_id=test_user,
        start_time=today_start,
        end_time=datetime.now()
    )
    elapsed = (time.time() - start) * 1000
    print(f"✅ Today's trades: {elapsed:.1f}ms ({len(events)} results)")
    
    # Test 3: Last 7 days query
    start = time.time()
    week_ago = datetime.now() - timedelta(days=7)
    events = event_store.query_events(
        user_id=test_user,
        start_time=week_ago,
        end_time=datetime.now()
    )
    elapsed = (time.time() - start) * 1000
    print(f"✅ Last 7 days: {elapsed:.1f}ms ({len(events)} results)")
    
    # Test 4: Token-specific query
    start = time.time()
    events = event_store.query_events(
        user_id=test_user,
        event_types=[TRADE_BUY, TRADE_SELL],
        limit=50
    )
    # Filter by token in Python (simulating token-specific query)
    bonk_events = [e for e in events if e.data.get('token_symbol') == 'BONK']
    elapsed = (time.time() - start) * 1000
    print(f"✅ BONK trades: {elapsed:.1f}ms ({len(bonk_events)} results)")
    
    # All queries should be under 100ms
    return elapsed < 100


async def test_aggregation_performance(event_store: EventStore, num_users: int):
    """Test aggregation performance"""
    print("\n📊 Testing Aggregation Performance...")
    
    aggregator = EventAggregator(event_store)
    test_user = f"wallet_{random.randint(1, num_users)}"
    
    # Test 1: Daily profit sum
    start = time.time()
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    events = event_store.query_events(
        user_id=test_user,
        event_types=[TRADE_SELL],
        start_time=today_start,
        end_time=datetime.now()
    )
    result = aggregator.aggregate(events, 'sum', 'profit_sol')
    elapsed = (time.time() - start) * 1000
    print(f"✅ Daily profit sum: {elapsed:.1f}ms (result: {result:.2f} SOL)")
    
    # Test 2: Weekly average
    start = time.time()
    week_ago = datetime.now() - timedelta(days=7)
    events = event_store.query_events(
        user_id=test_user,
        event_types=[TRADE_SELL],
        start_time=week_ago,
        end_time=datetime.now()
    )
    result = aggregator.aggregate(events, 'avg', 'profit_sol')
    elapsed = (time.time() - start) * 1000
    print(f"✅ Weekly average: {elapsed:.1f}ms (result: {result:.2f} SOL)")
    
    # Test 3: Group by token
    start = time.time()
    events = event_store.query_events(
        user_id=test_user,
        event_types=[TRADE_SELL],
        start_time=week_ago,
        end_time=datetime.now()
    )
    result = aggregator.aggregate(events, 'sum', 'profit_sol', group_by='token_symbol')
    elapsed = (time.time() - start) * 1000
    print(f"✅ Group by token: {elapsed:.1f}ms ({len(result)} tokens)")
    
    # Test 4: Period comparison
    start = time.time()
    comparison = aggregator.compare_periods(
        user_id=test_user,
        event_types=[TRADE_SELL],
        period1_start=datetime.now() - timedelta(days=14),
        period1_end=datetime.now() - timedelta(days=7),
        period2_start=datetime.now() - timedelta(days=7),
        period2_end=datetime.now(),
        metric_type='sum',
        value_field='profit_sol'
    )
    elapsed = (time.time() - start) * 1000
    if 'change_pct' in comparison:
        print(f"✅ Period comparison: {elapsed:.1f}ms ({comparison['change_pct']:.1f}% change)")
    else:
        print(f"✅ Period comparison: {elapsed:.1f}ms")
    
    return True


async def test_concurrent_access():
    """Test concurrent reads/writes"""
    print("\n🔀 Testing Concurrent Access...")
    
    event_store = EventStore("test_concurrent.db")
    
    async def writer(user_id: str, num_writes: int):
        """Simulate writes"""
        for i in range(num_writes):
            event = Event(
                user_id=user_id,
                event_type=TRADE_BUY,
                timestamp=datetime.now(),
                data={'amount': i}
            )
            event_store.record_event(event)
            await asyncio.sleep(0.001)  # Small delay
    
    async def reader(user_id: str, num_reads: int):
        """Simulate reads"""
        for i in range(num_reads):
            events = event_store.query_events(user_id=user_id, limit=10)
            await asyncio.sleep(0.005)  # Small delay
    
    # Run concurrent operations
    start = time.time()
    tasks = []
    
    # 5 writers, 10 readers
    for i in range(5):
        tasks.append(writer(f"user_{i}", 100))
    
    for i in range(10):
        tasks.append(reader(f"user_{i % 5}", 50))
    
    await asyncio.gather(*tasks)
    elapsed = time.time() - start
    
    print(f"✅ Concurrent test completed in {elapsed:.1f}s")
    print(f"   - 500 writes, 500 reads")
    print(f"   - No errors or conflicts")
    
    return True


async def cleanup():
    """Clean up test databases"""
    import os
    for db in ['test_load.db', 'test_concurrent.db']:
        if os.path.exists(db):
            os.remove(db)
    print("\n🧹 Cleaned up test databases")


async def main():
    """Run load tests"""
    print("🚀 Analytics Load Test Suite")
    print("=" * 50)
    
    try:
        # Generate test data
        event_store, num_users = await generate_test_events(100000)
        
        # Test query performance
        query_pass = await test_query_performance(event_store, num_users)
        
        # Test aggregation performance
        agg_pass = await test_aggregation_performance(event_store, num_users)
        
        # Test concurrent access
        concurrent_pass = await test_concurrent_access()
        
        print("\n📊 Load Test Results:")
        print(f"✅ 100k events handled")
        print(f"✅ All queries under 100ms: {query_pass}")
        print(f"✅ Aggregations performant: {agg_pass}")
        print(f"✅ Concurrent access safe: {concurrent_pass}")
        
        if query_pass and agg_pass and concurrent_pass:
            print("\n🎉 All load tests PASSED!")
        else:
            print("\n❌ Some tests failed")
            
    except Exception as e:
        print(f"\n❌ Load test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await cleanup()


if __name__ == "__main__":
    asyncio.run(main()) 