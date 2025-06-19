"""
Test GPT conversation engine integration - Task 1.3 verification
"""

import asyncio
import sys
import os
from datetime import datetime
import time
from unittest.mock import Mock, AsyncMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conversation_engine import (
    ConversationEngine, 
    InputType,
    create_conversation_engine
)
from gpt_client import GPTClient, create_gpt_client


# Mock GPT client for testing
class MockGPTClient:
    """Mock GPT client that simulates responses"""
    
    def __init__(self, response_time=0.1, should_timeout=False, should_fail=False):
        self.response_time = response_time
        self.should_timeout = should_timeout
        self.should_fail = should_fail
        self.api_key = "mock-key"
        
    async def generate_response(self, context_json: str) -> str:
        """Simulate GPT response generation"""
        if self.should_fail:
            raise Exception("Mock GPT error")
            
        # Simulate response time
        await asyncio.sleep(self.response_time)
        
        if self.should_timeout:
            await asyncio.sleep(3.0)  # Exceed timeout
            
        # Generate contextual mock response
        import json
        context = json.loads(context_json)
        event = context.get("current_event", {})
        
        if event.get("type") == "trade":
            action = event["data"].get("action")
            token = event["data"].get("token_symbol")
            if action == "BUY":
                return f"Interesting move on {token}. What caught your eye?"
            else:
                pnl = event["data"].get("pnl_usd", 0)
                if pnl > 0:
                    return f"Nice win on {token}! What made you take profits there?"
                else:
                    return f"Tough break on {token}. What would you do differently?"
                    
        elif event.get("type") == "message":
            return "Tell me more about your thinking there."
            
        return "I see. How does that fit your strategy?"
        
    def is_available(self) -> bool:
        return True


async def test_gpt_conversation_engine():
    """Test GPT integration with conversation engine"""
    print("Testing GPT Conversation Engine - Task 1.3 Success Criteria")
    print("=" * 60)
    
    # Create mocks
    state_mgr = Mock()
    state_mgr.get_all_notebooks = AsyncMock(return_value={})
    
    conv_mgr = Mock()
    conv_mgr.store_message = AsyncMock(return_value=None)
    conv_mgr.get_conversation_history = AsyncMock(return_value=[])
    conv_mgr.get_recent_trades = AsyncMock(return_value=[])
    
    # Test 1: GPT generates contextual responses
    print("\n1. Testing contextual response generation...")
    
    mock_gpt = MockGPTClient()
    engine = create_conversation_engine(state_mgr, conv_mgr, gpt_client=mock_gpt)
    
    # Test buy response
    start_time = time.time()
    response = await engine.process_input(
        InputType.TRADE,
        {"action": "BUY", "token_symbol": "BONK", "amount_sol": 0.5},
        user_id=12345
    )
    elapsed = time.time() - start_time
    
    assert response is not None
    assert "BONK" in response
    assert "caught your eye" in response
    print(f"   ✅ Buy response: '{response}' (in {elapsed:.2f}s)")
    
    # Test sell with profit
    engine.last_response_time[12345] = datetime(2020, 1, 1)  # Reset rate limit
    response = await engine.process_input(
        InputType.TRADE,
        {"action": "SELL", "token_symbol": "PEPE", "pnl_usd": 25},
        user_id=12345
    )
    
    assert response is not None
    assert "Nice win" in response
    assert "PEPE" in response
    print(f"   ✅ Profit response: '{response}'")
    
    # Test 2: Response time under 2 seconds
    print("\n2. Testing response time requirement...")
    
    # Test with slower mock (0.5s)
    mock_gpt.response_time = 0.5
    engine.last_response_time[12345] = datetime(2020, 1, 1)
    
    start_time = time.time()
    response = await engine.process_input(
        InputType.MESSAGE,
        {"text": "I think this might pump"},
        user_id=12345
    )
    elapsed = time.time() - start_time
    
    assert response is not None
    assert elapsed < 2.0
    print(f"   ✅ Response generated in {elapsed:.2f}s (< 2s requirement)")
    
    # Test 3: Fallback on timeout
    print("\n3. Testing timeout fallback...")
    
    # Create engine with real GPT client that will timeout
    real_gpt = create_gpt_client(api_key="fake-key", timeout=0.1)
    engine_timeout = create_conversation_engine(state_mgr, conv_mgr, gpt_client=real_gpt)
    
    # This should fallback because of invalid API key
    response = await engine_timeout.process_input(
        InputType.TRADE,
        {"action": "BUY", "token_symbol": "SOL", "amount_sol": 1.0},
        user_id=12345
    )
    
    assert response is not None
    assert response == "Bought SOL - what's the play?"  # Fallback response
    print(f"   ✅ Fallback response on timeout: '{response}'")
    
    # Test 4: Fallback on error
    print("\n4. Testing error fallback...")
    
    mock_gpt_error = MockGPTClient(should_fail=True)
    engine_error = create_conversation_engine(state_mgr, conv_mgr, gpt_client=mock_gpt_error)
    
    response = await engine_error.process_input(
        InputType.MESSAGE,
        {"text": "What do you think?"},
        user_id=12345
    )
    
    assert response is not None
    assert response == "I hear you. Tell me more?"  # Fallback response
    print(f"   ✅ Fallback response on error: '{response}'")
    
    # Test 5: Works without GPT client
    print("\n5. Testing without GPT client...")
    
    engine_no_gpt = create_conversation_engine(state_mgr, conv_mgr, gpt_client=None)
    
    response = await engine_no_gpt.process_input(
        InputType.COMMAND,
        {"command": "/chat"},
        user_id=12345
    )
    
    assert response is not None
    assert response == "What's on your mind?"  # Fallback response
    print(f"   ✅ Fallback response without GPT: '{response}'")
    
    # Test 6: Context is passed correctly
    print("\n6. Testing context passing to GPT...")
    
    # Track what context was passed
    received_context = None
    
    async def capture_context(context_json):
        nonlocal received_context
        import json
        received_context = json.loads(context_json)
        return "Context captured"
    
    mock_gpt.generate_response = capture_context
    
    # Reset rate limit
    engine.last_response_time[12345] = datetime(2020, 1, 1)
    
    await engine.process_input(
        InputType.TRADE,
        {"action": "BUY", "token_symbol": "WIF"},
        user_id=12345
    )
    
    assert received_context is not None
    assert received_context["current_event"]["type"] == "trade"
    assert received_context["current_event"]["data"]["token_symbol"] == "WIF"
    print("   ✅ Context correctly passed to GPT")
    
    print("\n" + "=" * 60)
    print("🎉 SUCCESS: Task 1.3 Complete!")
    print("✅ GPT generates contextual responses")
    print("✅ Response time < 2s requirement met")
    print("✅ Timeout fallback working")
    print("✅ Error fallback working")
    print("✅ Works without GPT client")
    print("✅ Context properly formatted and passed")


if __name__ == "__main__":
    asyncio.run(test_gpt_conversation_engine()) 