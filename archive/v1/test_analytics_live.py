#!/usr/bin/env python3

import asyncio
import sys
import json
sys.path.append('.')

from diary_api import query_time_range, calculate_metrics, get_goal_progress, compare_periods

async def test_analytics():
    user_id = '34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya'
    
    print("=== Testing Analytics Tools ===")
    
    # Test 1: Query time range
    print("\n1. Testing query_time_range for today:")
    today_trades = await query_time_range(user_id, 'today')
    print(f"   Result type: {type(today_trades)}")
    print(f"   Result: {today_trades}")
    
    # Test 2: Calculate metrics
    print("\n2. Testing calculate_metrics:")
    try:
        metrics = await calculate_metrics(user_id, 'today', ['sum'], ['sol_amount'], 'action', 'SELL')
        print(f"   Metrics: {metrics}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 3: Goal progress
    print("\n3. Testing get_goal_progress:")
    try:
        goal_progress = await get_goal_progress(user_id)
        print(f"   Goal progress: {goal_progress}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 4: Compare periods
    print("\n4. Testing compare_periods:")
    try:
        comparison = await compare_periods(user_id, 'today', 'yesterday', ['sum'], ['sol_amount'])
        print(f"   Comparison: {comparison}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n=== Analytics Test Complete ===")

if __name__ == "__main__":
    asyncio.run(test_analytics())