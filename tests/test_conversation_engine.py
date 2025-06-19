"""
Test conversation engine - unified message handling
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from conversation_engine import (
    ConversationEngine, 
    InputType,
    create_conversation_engine
)


@pytest.fixture
def mock_state_manager():
    """Create mock state manager"""
    manager = Mock()
    manager.get_all_notebooks = AsyncMock(return_value={
        "TOKEN1": {
            "last_side": "buy",
            "exposure_pct": 5.0,
            "live_pnl_sol": 0.1,
            "last_trade_time": datetime.now().isoformat()
        }
    })
    return manager


@pytest.fixture
def mock_conversation_manager():
    """Create mock conversation manager"""
    manager = Mock()
    manager.store_message = AsyncMock(return_value=None)
    return manager


@pytest.fixture
def engine(mock_state_manager, mock_conversation_manager):
    """Create conversation engine with mocks"""
    return create_conversation_engine(
        state_manager=mock_state_manager,
        conversation_manager=mock_conversation_manager
    )


@pytest.mark.asyncio
async def test_process_trade_input(engine):
    """Test processing a trade through the unified pipeline"""
    # Process a buy trade
    response = await engine.process_input(
        input_type=InputType.TRADE,
        data={
            "action": "BUY",
            "token_symbol": "PEPE",
            "amount_sol": 0.5,
            "price": 0.0001
        },
        user_id=12345
    )
    
    # Should get a response
    assert response is not None
    assert "PEPE" in response
    assert "what's the play?" in response
    
    # Process a sell trade with profit
    response = await engine.process_input(
        input_type=InputType.TRADE,
        data={
            "action": "SELL",
            "token_symbol": "PEPE",
            "pnl_usd": 50
        },
        user_id=12345
    )
    
    # Should be rate limited (< 30 seconds)
    assert response is None
    
    # Wait and try again
    await asyncio.sleep(0.1)  # Simulate time passing
    engine.last_response_time[12345] = datetime(2020, 1, 1)  # Old timestamp
    
    response = await engine.process_input(
        input_type=InputType.TRADE,
        data={
            "action": "SELL",
            "token_symbol": "PEPE",
            "pnl_usd": 50
        },
        user_id=12345
    )
    
    assert response is not None
    assert "+$50" in response


@pytest.mark.asyncio
async def test_process_message_input(engine):
    """Test processing a message through the unified pipeline"""
    response = await engine.process_input(
        input_type=InputType.MESSAGE,
        data={
            "text": "I think this token might pump",
            "message_id": 123
        },
        user_id=12345
    )
    
    # Should always respond to messages
    assert response is not None
    assert "Tell me more" in response


@pytest.mark.asyncio
async def test_process_command_input(engine):
    """Test processing commands through the unified pipeline"""
    # Test /chat command
    response = await engine.process_input(
        input_type=InputType.COMMAND,
        data={
            "command": "/chat"
        },
        user_id=12345
    )
    
    assert response is not None
    assert "What's on your mind?" in response
    
    # Test /pause command
    response = await engine.process_input(
        input_type=InputType.COMMAND,
        data={
            "command": "/pause"
        },
        user_id=12345
    )
    
    assert response is not None
    assert "paused" in response


@pytest.mark.asyncio
async def test_process_time_event(engine):
    """Test processing time events through the unified pipeline"""
    response = await engine.process_input(
        input_type=InputType.TIME_EVENT,
        data={
            "event_type": "position_check",
            "token": "BONK"
        },
        user_id=12345
    )
    
    # Should not respond to time events by default
    assert response is None


@pytest.mark.asyncio
async def test_pause_resume_functionality(engine):
    """Test pause/resume functionality"""
    user_id = 12345
    
    # Normal message should get response
    response = await engine.process_input(
        input_type=InputType.MESSAGE,
        data={"text": "Hello"},
        user_id=user_id
    )
    assert response is not None
    
    # Pause user
    engine.pause_user(user_id)
    assert engine.is_paused(user_id)
    
    # Should not respond when paused
    response = await engine.process_input(
        input_type=InputType.MESSAGE,
        data={"text": "Hello again"},
        user_id=user_id
    )
    assert response is None
    
    # Resume user
    engine.resume_user(user_id)
    assert not engine.is_paused(user_id)
    
    # Should respond again
    response = await engine.process_input(
        input_type=InputType.MESSAGE,
        data={"text": "Hello once more"},
        user_id=user_id
    )
    assert response is not None


@pytest.mark.asyncio
async def test_context_building(engine, mock_state_manager):
    """Test that context is properly aggregated"""
    # Process input
    await engine.process_input(
        input_type=InputType.TRADE,
        data={"action": "BUY", "token_symbol": "SOL"},
        user_id=12345
    )
    
    # Verify state manager was called to get positions
    mock_state_manager.get_all_notebooks.assert_called_with(12345)


@pytest.mark.asyncio
async def test_conversation_storage(engine, mock_conversation_manager):
    """Test that conversations are stored"""
    # Process input
    await engine.process_input(
        input_type=InputType.MESSAGE,
        data={"text": "Test message"},
        user_id=12345
    )
    
    # Verify conversation manager stored both input and response
    assert mock_conversation_manager.store_message.call_count >= 2  # Input + response


def test_input_types_enum():
    """Test that all required input types are defined"""
    assert InputType.TRADE.value == "trade"
    assert InputType.MESSAGE.value == "message"
    assert InputType.TIME_EVENT.value == "time_event"
    assert InputType.COMMAND.value == "command"


if __name__ == "__main__":
    # Run basic smoke test
    print("Running conversation engine smoke test...")
    
    # Create mock dependencies
    state_mgr = Mock()
    state_mgr.get_all_notebooks = AsyncMock(return_value={})
    
    conv_mgr = Mock()
    conv_mgr.store_message = AsyncMock(return_value=None)
    
    # Create engine
    engine = create_conversation_engine(state_mgr, conv_mgr)
    
    # Test processing different input types
    async def run_test():
        # Test trade
        result = await engine.process_input(
            InputType.TRADE,
            {"action": "BUY", "token_symbol": "TEST"},
            12345
        )
        print(f"Trade response: {result}")
        
        # Test message
        result = await engine.process_input(
            InputType.MESSAGE,
            {"text": "Hello bot"},
            12345
        )
        print(f"Message response: {result}")
        
        # Test command
        result = await engine.process_input(
            InputType.COMMAND,
            {"command": "/chat"},
            12345
        )
        print(f"Command response: {result}")
        
        print("✅ All input types processed successfully!")
    
    asyncio.run(run_test()) 