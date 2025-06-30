"""
Test structured context formatting
"""

import sys
sys.path.append('..')

from datetime import datetime
from conversation_engine import ConversationContext, ConversationInput, InputType


def test_structured_context_format():
    """Test that context is formatted with clear boundaries"""
    
    # Create test input
    test_input = ConversationInput(
        type=InputType.TRADE,
        user_id=123,
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        data={
            "action": "SELL",
            "token_symbol": "BONK",
            "amount_sol": 2.5,
            "pnl_usd": 420,
            "pnl_pct": 37.5
        }
    )
    
    # Create test context
    context = ConversationContext(
        current_input=test_input,
        conversation_history=[
            {
                "role": "user",
                "content": "thinking about selling",
                "timestamp": "2024-01-15T10:25:00Z"
            },
            {
                "role": "assistant", 
                "content": "BONK up nicely! What's your target?",
                "timestamp": "2024-01-15T10:26:00Z"
            }
        ],
        user_state={
            "positions": {
                "WIF": {"size_pct": 15, "pnl_usd": -50},
                "BONK": {"size_pct": 25, "pnl_usd": 420}
            },
            "total_positions": 2,
            "total_exposure_pct": 40
        },
        trading_stats={
            "patterns": [
                "Traded BONK 5 times this week",
                "Average hold time: 2.5 hours"
            ],
            "favorite_tokens": ["BONK", "WIF"],
            "win_rate": 0.65,
            "total_trades": 20,
            "avg_position_size": 3.5
        }
    )
    
    # Get structured output
    structured = context.to_structured()
    
    # Verify sections exist
    assert "## CURRENT_EVENT" in structured
    assert "## RECENT_PATTERNS" in structured
    assert "## CONVERSATION_HISTORY" in structured
    assert "## USER_PROFILE" in structured
    
    # Verify XML tags
    assert '<trade_data timestamp="2024-01-15T10:30:00"' in structured
    assert '</trade_data>' in structured
    assert '<patterns confidence=' in structured
    assert '<messages count=' in structured
    assert '<profile trades_this_week=' in structured
    
    # Verify human-readable summary
    assert "**Summary**: Sold BONK for +$420 (+37.5%)" in structured
    
    # Verify patterns are included
    assert "Traded BONK 5 times this week" in structured
    assert "**Frequently Traded**: BONK, WIF" in structured
    
    # Verify conversation history formatting
    assert "**User**" in structured
    assert "**Coach**" in structured
    assert "thinking about selling" in structured
    
    # Verify profile formatting
    assert "**Active Positions**:" in structured
    assert "BONK: 25.0% of portfolio (+$420)" in structured
    assert "WIF: 15.0% of portfolio (-$50)" in structured
    assert "Average position: 3.5 SOL" in structured
    
    print("✅ Structured context format test passed!")
    print("\nExample output:")
    print("=" * 50)
    print(structured)
    print("=" * 50)


def test_relevance_filtering():
    """Test that relevant messages are selected based on current context"""
    
    # Create test input for BONK trade
    test_input = ConversationInput(
        type=InputType.TRADE,
        user_id=123,
        timestamp=datetime.now(),
        data={"token_symbol": "BONK", "action": "BUY"}
    )
    
    # Create conversation history with mixed tokens
    history = [
        {"role": "user", "content": "what about WIF?"},
        {"role": "assistant", "content": "WIF looking weak"},
        {"role": "user", "content": "BONK pumping hard"},
        {"role": "assistant", "content": "BONK at resistance"},
        {"role": "user", "content": "buying SOL"},
        {"role": "assistant", "content": "SOL solid choice"},
        {"role": "user", "content": "more BONK?"},
        {"role": "assistant", "content": "Careful with BONK size"},
    ]
    
    context = ConversationContext(
        current_input=test_input,
        conversation_history=history,
        user_state={},
        trading_stats={}
    )
    
    # Test relevance selection
    relevant = context._select_relevant_messages()
    
    # Should prioritize BONK-related messages
    bonk_messages = [msg for msg in relevant if "BONK" in msg.get("content", "")]
    assert len(bonk_messages) >= 2  # Should include BONK messages
    assert len(relevant) <= 7  # Should limit total messages
    
    print("✅ Relevance filtering test passed!")


def test_time_formatting():
    """Test time ago formatting"""
    context = ConversationContext(
        current_input=None,
        conversation_history=[],
        user_state={},
        trading_stats={}
    )
    
    # Test various time formats
    assert context._format_time_ago("2024-01-15T10:30:00Z") != "recently"
    assert context._format_time_ago("") == "recently"
    assert context._format_time_ago(None) == "recently"
    
    print("✅ Time formatting test passed!")


if __name__ == "__main__":
    test_structured_context_format()
    test_relevance_filtering()
    test_time_formatting()
    print("\n✅ All structured context tests passed!") 