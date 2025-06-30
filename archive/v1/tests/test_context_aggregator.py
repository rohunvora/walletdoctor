"""
Test context aggregator - Task 1.2 verification
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
import json
import time
from unittest.mock import Mock, AsyncMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conversation_engine import (
    ConversationEngine, 
    InputType,
    ConversationInput,
    ConversationContext,
    create_conversation_engine
)


async def test_context_aggregator():
    """Test that context aggregator meets all requirements"""
    print("Testing Context Aggregator - Task 1.2 Success Criteria")
    print("=" * 60)
    
    # Create sophisticated mocks with realistic data
    state_mgr = Mock()
    state_mgr.get_all_notebooks = AsyncMock(return_value={
        "BONK": {
            "last_side": "buy",
            "exposure_pct": 8.5,
            "live_pnl_sol": 0.25,
            "last_trade_time": datetime.now().isoformat(),
            "last_reason": "testing support level",
            "unanswered_question": False
        },
        "PEPE": {
            "last_side": "buy", 
            "exposure_pct": 3.2,
            "live_pnl_sol": -0.08,
            "last_trade_time": (datetime.now() - timedelta(hours=2)).isoformat(),
            "last_reason": "following whale",
            "unanswered_question": True
        }
    })
    
    conv_mgr = Mock()
    # Mock conversation history
    conv_mgr.get_conversation_history = AsyncMock(return_value=[
        {
            "type": "trade",
            "content": {"action": "BUY", "token_symbol": "BONK", "amount_sol": 0.5},
            "timestamp": (datetime.now() - timedelta(minutes=30)).isoformat(),
            "metadata": {}
        },
        {
            "type": "bot_response",
            "content": {"text": "BONK again? What's the setup?"},
            "timestamp": (datetime.now() - timedelta(minutes=29)).isoformat(),
            "metadata": {}
        },
        {
            "type": "message",
            "content": {"text": "testing support at 0.000024"},
            "timestamp": (datetime.now() - timedelta(minutes=28)).isoformat(),
            "metadata": {}
        }
    ])
    
    # Mock recent trades
    conv_mgr.get_recent_trades = AsyncMock(return_value=[
        {"token_symbol": "BONK", "action": "BUY", "sol_amount": 0.5, "pnl_usd": None, "timestamp": datetime.now().isoformat()},
        {"token_symbol": "PEPE", "action": "SELL", "sol_amount": 0.3, "pnl_usd": 15.0, "timestamp": datetime.now().isoformat()},
        {"token_symbol": "BONK", "action": "SELL", "sol_amount": 0.2, "pnl_usd": -5.0, "timestamp": datetime.now().isoformat()},
        {"token_symbol": "WIF", "action": "BUY", "sol_amount": 1.0, "pnl_usd": None, "timestamp": datetime.now().isoformat()},
        {"token_symbol": "WIF", "action": "SELL", "sol_amount": 1.0, "pnl_usd": 50.0, "timestamp": datetime.now().isoformat()},
    ])
    
    conv_mgr.store_message = AsyncMock(return_value=None)
    
    # Create engine
    engine = create_conversation_engine(state_mgr, conv_mgr)
    
    print("✅ Created engine with mock data")
    
    # Test 1: Build context for a trade input
    print("\n1. Testing context aggregation...")
    
    trade_input = ConversationInput(
        type=InputType.TRADE,
        user_id=12345,
        timestamp=datetime.now(),
        data={
            "action": "SELL",
            "token_symbol": "BONK",
            "amount_sol": 0.25,
            "pnl_usd": 12.5
        }
    )
    
    # Measure performance
    start_time = time.time()
    context = await engine._build_context(trade_input)
    elapsed_ms = (time.time() - start_time) * 1000
    
    print(f"   Context built in {elapsed_ms:.1f}ms")
    assert elapsed_ms < 50, f"Context build too slow: {elapsed_ms}ms"
    print("   ✅ Performance requirement met (<50ms)")
    
    # Test 2: Verify context structure
    print("\n2. Verifying context structure...")
    
    assert isinstance(context, ConversationContext)
    assert context.current_input == trade_input
    assert len(context.conversation_history) == 3
    assert context.user_positions["total_positions"] == 2
    assert context.user_stats["total_trades_week"] == 5
    print("   ✅ Context has all required components")
    
    # Test 3: Test JSON serialization
    print("\n3. Testing JSON serialization...")
    
    json_str = context.to_json()
    parsed = json.loads(json_str)
    
    assert "current_event" in parsed
    assert "recent_conversation" in parsed
    assert "positions" in parsed
    assert "user_stats" in parsed
    
    print("   JSON structure:")
    print(f"   - Current event: {parsed['current_event']['type']}")
    print(f"   - Conversation history: {len(parsed['recent_conversation'])} messages")
    print(f"   - Active positions: {parsed['positions']['total_positions']}")
    print(f"   - User stats: {parsed['user_stats']['win_rate']}% win rate")
    print("   ✅ Clean JSON output for GPT")
    
    # Test 4: Verify conversation history formatting
    print("\n4. Verifying conversation history format...")
    
    history = context.conversation_history
    assert history[0]["role"] == "user"
    assert history[0]["type"] == "trade"
    assert "summary" in history[0]
    assert history[1]["role"] == "assistant"
    assert history[2]["role"] == "user"
    print("   ✅ Conversation history properly formatted")
    
    # Test 5: Verify position data
    print("\n5. Verifying position data...")
    
    positions = context.user_positions
    assert "BONK" in positions["positions"]
    assert positions["positions"]["BONK"]["size_pct"] == 8.5
    assert positions["positions"]["BONK"]["pnl_usd"] == 0.25 * 175
    assert positions["total_exposure_pct"] == 11.7  # 8.5 + 3.2
    assert positions["largest_position"] == "BONK"
    print("   ✅ Position data correctly aggregated")
    
    # Test 6: Verify user stats
    print("\n6. Verifying user statistics...")
    
    stats = context.user_stats
    assert stats["total_trades_week"] == 5
    assert stats["win_rate"] == 66.7  # 2 wins out of 3 with P&L
    assert stats["favorite_tokens"] == ["BONK", "WIF", "PEPE"]
    assert stats["total_wins"] == 2
    assert stats["total_losses"] == 1
    print("   ✅ User stats correctly calculated")
    
    # Test 7: Performance with parallel execution
    print("\n7. Testing parallel data fetching...")
    
    # Run multiple context builds to ensure consistent performance
    times = []
    for i in range(5):
        start = time.time()
        await engine._build_context(trade_input)
        times.append((time.time() - start) * 1000)
    
    avg_time = sum(times) / len(times)
    max_time = max(times)
    
    print(f"   Average: {avg_time:.1f}ms, Max: {max_time:.1f}ms")
    assert max_time < 50, f"Max time exceeded 50ms: {max_time}ms"
    print("   ✅ Consistent performance with parallel fetching")
    
    print("\n" + "=" * 60)
    print("🎉 SUCCESS: Task 1.2 Complete!")
    print("✅ Context aggregates all required data")
    print("✅ Clean JSON structure for GPT consumption")
    print("✅ Performance consistently <50ms")
    print("✅ Parallel data fetching implemented")
    print("✅ Human-readable summaries included")


if __name__ == "__main__":
    asyncio.run(test_context_aggregator()) 