"""
Test conversation storage - Task 1.4 verification
"""

import asyncio
import sys
import os
from datetime import datetime
import tempfile
import duckdb
from unittest.mock import Mock, AsyncMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conversation_engine import (
    ConversationEngine, 
    InputType,
    create_conversation_engine
)
from conversation_manager import create_conversation_manager
from state_manager import StateManager


async def test_conversation_storage():
    """Test conversation storage and persistence"""
    print("Testing Conversation Storage - Task 1.4 Success Criteria")
    print("=" * 60)
    
    # Create temporary database
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_conversations.db')
    
    try:
        # Test 1: Store conversation turns
        print("\n1. Testing conversation storage...")
        
        # Create real conversation manager with database
        conv_mgr = create_conversation_manager(db_path=db_path)
        
        # Mock get_recent_trades to avoid user_trades table dependency
        conv_mgr.get_recent_trades = AsyncMock(return_value=[])
        
        # Create mock state manager
        state_mgr = Mock()
        state_mgr.get_all_notebooks = AsyncMock(return_value={})
        
        # Create engine
        engine = create_conversation_engine(state_mgr, conv_mgr)
        
        user_id = 12345
        
        # Simulate a conversation
        # Trade 1
        response1 = await engine.process_input(
            InputType.TRADE,
            {"action": "BUY", "token_symbol": "BONK", "amount_sol": 0.5},
            user_id
        )
        assert response1 is not None
        print(f"   Trade stored: BUY BONK")
        print(f"   Bot response: {response1}")
        
        # User message
        await asyncio.sleep(0.1)
        engine.last_response_time[user_id] = datetime(2020, 1, 1)  # Reset rate limit
        
        response2 = await engine.process_input(
            InputType.MESSAGE,
            {"text": "I think BONK has good momentum"},
            user_id
        )
        assert response2 is not None
        print(f"   Message stored: 'I think BONK has good momentum'")
        print(f"   Bot response: {response2}")
        
        # Check thread ID was assigned
        assert user_id in engine.active_threads
        thread_id = engine.active_threads[user_id]
        print(f"   Thread ID: {thread_id}")
        print("   ✅ Conversations are being stored with thread IDs")
        
        # Test 2: Retrieve conversation history
        print("\n2. Testing conversation retrieval...")
        
        history = await conv_mgr.get_conversation_history(user_id, limit=10)
        assert len(history) >= 4  # 2 user inputs + 2 bot responses
        
        # Verify order (oldest to newest)
        assert history[0]['type'] == 'trade'
        assert history[1]['type'] == 'bot_response'
        assert history[2]['type'] == 'message'
        assert history[3]['type'] == 'bot_response'
        
        print(f"   Retrieved {len(history)} messages")
        for i, msg in enumerate(history):
            print(f"   {i+1}. {msg['type']}: {msg.get('content', {}).get('text', msg.get('content', {}))}")
        print("   ✅ Conversation history retrieved correctly")
        
        # Test 3: Persistence across sessions
        print("\n3. Testing persistence across sessions...")
        
        # Create new engine instance (simulating bot restart)
        conv_mgr2 = create_conversation_manager(db_path=db_path)
        conv_mgr2.get_recent_trades = AsyncMock(return_value=[])
        engine2 = create_conversation_engine(state_mgr, conv_mgr2)
        
        # Answer the previous question first (bot asked "what's the play?")
        engine2.last_response_time[user_id] = datetime(2020, 1, 1)
        answer_response = await engine2.process_input(
            InputType.MESSAGE,
            {"text": "Just riding the momentum"},
            user_id
        )
        print(f"   Answer response: {answer_response}")
        
        # Wait a bit to ensure messages are processed
        await asyncio.sleep(0.1)
        
        # Continue conversation with a trade
        engine2.last_response_time[user_id] = datetime(2020, 1, 1)
        response3 = await engine2.process_input(
            InputType.TRADE,
            {"action": "SELL", "token_symbol": "BONK", "pnl_usd": 15},
            user_id
        )
        
        # Get history from new instance
        history2 = await conv_mgr2.get_conversation_history(user_id, limit=20)
        
        # Should include previous conversation + new interactions
        assert len(history2) >= 6, f"Expected >= 6 messages, got {len(history2)}"
        print(f"   Retrieved {len(history2)} messages after restart")
        print("   ✅ Conversations persist across sessions")
        
        # Test 4: Unanswered question detection
        print("\n4. Testing unanswered question detection...")
        
        # Clear and start fresh conversation
        await engine2.clear_conversation(user_id)
        engine2.last_response_time[user_id] = datetime(2020, 1, 1)
        
        # Create a question scenario
        class MockGPT:
            async def generate_response(self, context):
                return "What made you interested in PEPE?"
        
        engine2.gpt_client = MockGPT()
        
        # Generate a question
        await engine2.process_input(
            InputType.TRADE,
            {"action": "BUY", "token_symbol": "PEPE"},
            user_id
        )
        
        # Try another trade - should skip because question is unanswered
        engine2.last_response_time[user_id] = datetime(2020, 1, 1)
        response_skip = await engine2.process_input(
            InputType.TRADE,
            {"action": "BUY", "token_symbol": "WIF"},
            user_id
        )
        
        assert response_skip is None  # Should skip due to unanswered question
        print("   ✅ Unanswered question detection working")
        
        # Answer the question
        response_answer = await engine2.process_input(
            InputType.MESSAGE,
            {"text": "Saw it trending on Twitter"},
            user_id
        )
        assert response_answer is not None
        print("   ✅ Conversation continues after answering")
        
        # Test 5: Conversation summary
        print("\n5. Testing conversation summary...")
        
        summary = await engine2.get_conversation_summary(user_id)
        print(f"   Summary: {summary}")
        assert "trades" in summary
        assert "messages" in summary
        assert "BONK" in summary or "PEPE" in summary
        print("   ✅ Conversation summary generation working")
        
        # Test 6: Clear conversation
        print("\n6. Testing conversation clearing...")
        
        await engine2.clear_conversation(user_id)
        assert user_id not in engine2.active_threads
        assert user_id not in engine2.last_response_time
        print("   ✅ Conversation clearing working")
        
        # Test 7: Performance with real database
        print("\n7. Testing storage performance...")
        
        import time
        start_time = time.time()
        
        # Store 10 messages rapidly
        for i in range(10):
            await conv_mgr2.store_message(
                user_id=99999,
                message_type="message",
                content={"text": f"Test message {i}"},
                timestamp=datetime.now()
            )
        
        # Retrieve them
        history = await conv_mgr2.get_conversation_history(99999)
        
        elapsed = time.time() - start_time
        print(f"   Stored and retrieved 10 messages in {elapsed:.2f}s")
        assert elapsed < 1.0  # Should be fast even with real DB
        print("   ✅ Storage performance acceptable")
        
        print("\n" + "=" * 60)
        print("🎉 SUCCESS: Task 1.4 Complete!")
        print("✅ Conversations stored in database")
        print("✅ Conversations retrieved across sessions")
        print("✅ Thread IDs maintain conversation context")
        print("✅ Unanswered question detection implemented")
        print("✅ Conversation clearing implemented")
        print("✅ Summary generation implemented")
        print("✅ Performance with real database verified")
        
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    asyncio.run(test_conversation_storage()) 