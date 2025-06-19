"""
Test Enhanced Context Builder - Task 3.5.2.1 verification

Tests the unified context system that combines ContextPack and ConversationContext
"""

import asyncio
import sys
import os
import time
import json
from datetime import datetime
from unittest.mock import Mock, AsyncMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enhanced_context_builder import (
    EnhancedContextBuilder,
    EnhancedContext,
    ContextScope
)


async def test_enhanced_context_builder():
    """Test enhanced context builder meets all requirements"""
    print("Testing Enhanced Context Builder - Task 3.5.2.1 Success Criteria")
    print("=" * 60)
    
    # Create sophisticated mocks
    state_mgr = Mock()
    state_mgr.get_all_notebooks = AsyncMock(return_value={
        "BONK": {
            "exposure_pct": 8.5,
            "live_pnl_sol": 0.25,
            "last_trade_time": datetime.now().isoformat()
        },
        "PEPE": {
            "exposure_pct": 3.2,
            "live_pnl_sol": -0.08,
            "last_trade_time": datetime.now().isoformat()
        }
    })
    
    conv_mgr = Mock()
    conv_mgr.get_conversation_history = AsyncMock(return_value=[
        {
            "role": "user",
            "content": "just bought BONK",
            "timestamp": "2024-01-15T10:25:00Z",
            "tag": "entry"
        },
        {
            "role": "assistant",
            "content": "BONK again? What caught your eye?",
            "timestamp": "2024-01-15T10:26:00Z"
        },
        {
            "role": "user",
            "content": "whale activity",
            "timestamp": "2024-01-15T10:27:00Z",
            "tag": "whale_follow"
        }
    ])
    
    pattern_service = Mock()
    pattern_service.get_user_baselines = Mock(return_value={
        'avg_position_size': 2.5,
        'total_trades': 20,
        'overall_pnl': 150.0
    })
    
    pnl_service = Mock()
    pnl_service.get_token_pnl_data = AsyncMock(return_value={
        'realized_pnl_usd': 250.0,
        'unrealized_pnl_usd': -50.0,
        'total_trades': 3,
        'win_rate': 0.67
    })
    
    # Create enhanced context builder
    builder = EnhancedContextBuilder(
        state_manager=state_mgr,
        conversation_manager=conv_mgr,
        pattern_service=pattern_service,
        pnl_service=pnl_service
    )
    
    # Test 1: Performance requirement
    print("\n1. Testing context build performance...")
    
    trade_input = {
        'action': 'SELL',
        'token_symbol': 'BONK',
        'amount_sol': 0.5,
        'pnl_usd': 42.0,
        'pnl_pct': 15.0
    }
    
    start_time = time.time()
    context = await builder.build_context(
        input_type='trade',
        input_data=trade_input,
        user_id=12345,
        scope=ContextScope.FULL
    )
    elapsed_ms = (time.time() - start_time) * 1000
    
    assert isinstance(context, EnhancedContext)
    assert elapsed_ms < 50, f"Context build too slow: {elapsed_ms:.1f}ms"
    print(f"   ✅ Built context in {elapsed_ms:.1f}ms (<50ms requirement)")
    
    # Test 2: Unified structure
    print("\n2. Testing unified context structure...")
    
    assert context.user_id == 12345
    assert context.scope == ContextScope.FULL
    assert context.event_significance in ['low', 'medium', 'high', 'critical']
    assert 'SELL' in str(context.current_event)
    assert len(context.data_sources) > 0
    print(f"   ✅ Context has unified structure with {len(context.data_sources)} data sources")
    
    # Test 3: Anonymized GPT format
    print("\n3. Testing anonymized GPT format...")
    
    gpt_format = context.to_gpt_format(anonymize=True)
    
    # Should contain required sections
    assert "## CURRENT_EVENT" in gpt_format
    assert "## TRADING_CONTEXT" in gpt_format
    assert "## USER_PROFILE" in gpt_format
    
    # Should not contain sensitive data
    assert str(context.user_id) not in gpt_format
    assert "12345" not in gpt_format
    
    # Should contain trading context
    assert "BONK" in gpt_format
    assert "SELL" in gpt_format
    
    print(f"   ✅ GPT format anonymized and structured ({len(gpt_format)} chars)")
    
    # Test 4: Scope-based context
    print("\n4. Testing scope-based context building...")
    
    # Test minimal scope
    minimal_context = await builder.build_context(
        input_type='trade',
        input_data=trade_input,
        user_id=12345,
        scope=ContextScope.MINIMAL
    )
    
    minimal_format = minimal_context.to_gpt_format()
    full_format = context.to_gpt_format()
    
    assert len(minimal_format) < len(full_format)
    assert minimal_context.build_time_ms <= context.build_time_ms
    print(f"   ✅ Minimal scope: {len(minimal_format)} chars vs Full: {len(full_format)} chars")
    
    # Test 5: Rich trading data
    print("\n5. Testing rich trading data integration...")
    
    # Should include P&L data from pnl_service
    assert context.trade_context.get('current_pnl_usd') == 250.0
    assert context.trade_context.get('unrealized_pnl_usd') == -50.0
    assert context.trade_context.get('win_rate_token') == 0.67
    
    # Should include position data from state_manager
    assert context.position_context.get('total_positions') == 2
    assert 'BONK' in context.position_context.get('positions', {})
    
    print("   ✅ Rich trading data integrated from all services")
    
    # Test 6: Conversation context
    print("\n6. Testing conversation context...")
    
    assert len(context.conversation_context.get('relevant_messages', [])) > 0
    
    # Should prioritize relevant messages
    messages = context.conversation_context['relevant_messages']
    bonk_messages = [msg for msg in messages if 'BONK' in str(msg)]
    assert len(bonk_messages) > 0, "Should include BONK-related messages"
    
    print(f"   ✅ Conversation context with {len(messages)} relevant messages")
    
    # Test 7: Performance metrics
    print("\n7. Testing performance metrics...")
    
    metrics = context.get_performance_metrics()
    assert 'build_time_ms' in metrics
    assert 'data_sources' in metrics
    assert 'context_size_bytes' in metrics
    assert metrics['scope'] == 'full'
    
    print(f"   ✅ Performance metrics: {metrics['build_time_ms']:.1f}ms, {metrics['context_size_bytes']} bytes")
    
    # Test 8: Pattern analysis
    print("\n8. Testing pattern analysis...")
    
    # Should have placeholder pattern data
    assert context.pattern_context.get('primary_pattern') is not None
    assert 'recent_patterns' in context.pattern_context
    assert 'velocity_indicators' in context.pattern_context
    
    gpt_format = context.to_gpt_format()
    assert "## PATTERN_ANALYSIS" in gpt_format
    
    print("   ✅ Pattern analysis included in context")
    
    # Test 9: Timing context
    print("\n9. Testing timing context...")
    
    assert 'trade_hour' in context.timing_context
    assert context.timing_context['trade_hour'] in range(0, 24)
    assert 'is_weekend' in context.timing_context
    
    gpt_format = context.to_gpt_format()
    if 22 <= context.timing_context['trade_hour'] or context.timing_context['trade_hour'] <= 6:
        assert "Late night trade" in gpt_format
    
    print("   ✅ Timing context with trade hour and patterns")
    
    # Test 10: Error handling
    print("\n10. Testing error handling...")
    
    # Mock service failures
    failing_state_mgr = Mock()
    failing_state_mgr.get_all_notebooks = AsyncMock(side_effect=Exception("Service down"))
    
    failing_builder = EnhancedContextBuilder(
        state_manager=failing_state_mgr,
        conversation_manager=conv_mgr
    )
    
    # Should still work with service failures
    try:
        failing_context = await failing_builder.build_context(
            input_type='message',
            input_data={'text': 'hello'},
            user_id=12345,
            scope=ContextScope.MINIMAL
        )
        assert failing_context is not None
        print("   ✅ Graceful error handling when services fail")
    except Exception as e:
        print(f"   ❌ Error handling failed: {e}")
        raise
    
    print("\n" + "=" * 60)
    print("🎉 SUCCESS: Task 3.5.2.1 Enhanced Context Builder Complete!")
    print("✅ Single unified context system")
    print("✅ Context generation <50ms")
    print("✅ Rich trading data integration")
    print("✅ Privacy through anonymization") 
    print("✅ Scope-based optimization")
    print("✅ Performance monitoring")
    print("✅ Graceful error handling")


async def test_context_format_examples():
    """Test context format with real examples"""
    print("\n" + "=" * 60)
    print("Enhanced Context Format Examples")
    print("=" * 60)
    
    # Create minimal builder for format testing
    builder = EnhancedContextBuilder(
        state_manager=Mock(),
        conversation_manager=Mock()
    )
    
    # Mock some data
    builder.state_manager.get_all_notebooks = AsyncMock(return_value={})
    builder.conversation_manager.get_conversation_history = AsyncMock(return_value=[])
    
    # Test profit scenario
    profit_trade = {
        'action': 'SELL',
        'token_symbol': 'WIF',
        'amount_sol': 2.5,
        'pnl_usd': 420.0,
        'pnl_pct': 35.0
    }
    
    context = await builder.build_context(
        input_type='trade',
        input_data=profit_trade,
        user_id=67890,
        scope=ContextScope.TRADE_FOCUSED
    )
    
    print("\nProfit Trade Context Format:")
    print("-" * 40)
    gpt_format = context.to_gpt_format()
    print(gpt_format[:500] + "..." if len(gpt_format) > 500 else gpt_format)
    
    # Test loss scenario
    loss_trade = {
        'action': 'SELL',
        'token_symbol': 'PEPE',
        'amount_sol': 1.0,
        'pnl_usd': -150.0,
        'pnl_pct': -25.0
    }
    
    context = await builder.build_context(
        input_type='trade',
        input_data=loss_trade,
        user_id=67890,
        scope=ContextScope.TRADE_FOCUSED
    )
    
    print("\nLoss Trade Context Format:")
    print("-" * 40)
    gpt_format = context.to_gpt_format()
    print(gpt_format[:500] + "..." if len(gpt_format) > 500 else gpt_format)


if __name__ == "__main__":
    asyncio.run(test_enhanced_context_builder())
    asyncio.run(test_context_format_examples()) 