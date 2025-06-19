#!/usr/bin/env python3
"""
Live testing script for Pocket Trading Coach conversational AI
"""

import os
import asyncio
import sys
from datetime import datetime
from unittest.mock import Mock, AsyncMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_bot_coach import PocketCoachBot
from conversation_engine import InputType


async def test_bot_locally():
    """Test the bot without Telegram"""
    print("🧪 Testing Pocket Trading Coach Conversational AI")
    print("=" * 60)
    
    # Set up test environment
    os.environ['USE_NEW_AI'] = 'true'  # Enable new AI for all users
    
    # Create bot instance
    bot = PocketCoachBot(
        token="test-token",  # Not used for local testing
        db_path="test_pocket_coach.db"
    )
    
    # Mock the GPT client to avoid API errors
    if hasattr(bot, 'conversation_engine') and bot.conversation_engine.gpt_client:
        mock_gpt = Mock()
        mock_gpt.is_available = Mock(return_value=False)  # Force fallback responses
        bot.conversation_engine.gpt_client = mock_gpt
    
    # Test user ID
    test_user_id = 12345
    
    print("\n1. Testing Natural Language Understanding")
    print("-" * 40)
    
    # Test pause intent
    response = await bot.conversation_engine.process_input(
        InputType.MESSAGE,
        {"text": "hey this is too much, pause for now"},
        test_user_id
    )
    print(f"User: 'hey this is too much, pause for now'")
    print(f"Bot: {response}")
    assert "break" in response.lower() or "got it" in response.lower()
    
    # Test message while paused
    response = await bot.conversation_engine.process_input(
        InputType.MESSAGE,
        {"text": "actually I'm ready to continue"},
        test_user_id
    )
    print(f"\nUser: 'actually I'm ready to continue'")
    print(f"Bot: {response}")
    assert "action" in response.lower() or "market" in response.lower()
    
    print("\n2. Testing Trade Processing")
    print("-" * 40)
    
    # Simulate a trade
    trade_data = {
        "action": "BUY",
        "token_symbol": "BONK",
        "token_address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "amount_sol": 2.5,
        "pnl_usd": None
    }
    
    response = await bot.conversation_engine.process_input(
        InputType.TRADE,
        trade_data,
        test_user_id
    )
    print(f"Trade: BUY 2.5 SOL of BONK")
    print(f"Bot: {response}")
    assert "BONK" in response  # Should mention the token
    
    # Simulate user response
    await asyncio.sleep(1)
    response = await bot.conversation_engine.process_input(
        InputType.MESSAGE,
        {"text": "I saw it trending on Twitter and the chart looked good"},
        test_user_id
    )
    print(f"\nUser: 'I saw it trending on Twitter and the chart looked good'")
    print(f"Bot: {response}")
    assert "twitter" in response.lower() or "strategy" in response.lower()
    
    print("\n3. Testing Conversation Memory")
    print("-" * 40)
    
    # Check conversation history
    history = await bot.conversation_manager.get_conversation_history(test_user_id, limit=10)
    print(f"Conversation history: {len(history)} messages stored")
    
    # Test clear intent
    response = await bot.conversation_engine.process_input(
        InputType.MESSAGE,
        {"text": "let's start fresh, clear our chat"},
        test_user_id
    )
    print(f"\nUser: 'let's start fresh, clear our chat'")
    print(f"Bot: {response}")
    assert "clean" in response.lower() or "slate" in response.lower() or "fresh" in response.lower()
    
    print("\n4. Testing Help Intent")
    print("-" * 40)
    
    response = await bot.conversation_engine.process_input(
        InputType.MESSAGE,
        {"text": "what can you do?"},
        test_user_id
    )
    print(f"User: 'what can you do?'")
    print(f"Bot: {response}")
    assert "watch" in response.lower() or "pattern" in response.lower()
    
    print("\n5. Testing Personality")
    print("-" * 40)
    
    # Test greeting
    response = await bot.conversation_engine.process_input(
        InputType.MESSAGE,
        {"text": "yo"},
        test_user_id
    )
    print(f"User: 'yo'")
    print(f"Bot: {response}")
    
    # Test loss scenario
    trade_data = {
        "action": "SELL",
        "token_symbol": "WIF",
        "amount_sol": 3.0,
        "pnl_usd": -150
    }
    response = await bot.conversation_engine.process_input(
        InputType.TRADE,
        trade_data,
        test_user_id
    )
    print(f"\nTrade: SELL WIF at -$150 loss")
    print(f"Bot: {response}")
    assert "$" in response  # Should mention the loss amount
    
    print("\n" + "=" * 60)
    print("✅ All tests passed! The conversational AI is working.")
    print("\nNext steps:")
    print("1. Set TELEGRAM_BOT_TOKEN environment variable")
    print("2. Set USE_NEW_AI=true to enable for all users")
    print("3. Or set NEW_AI_USER_IDS=123,456 for specific beta testers")
    print("4. Run: python3 telegram_bot_coach.py")
    
    # Cleanup
    if os.path.exists("test_pocket_coach.db"):
        os.remove("test_pocket_coach.db")


async def test_with_telegram():
    """Instructions for testing with real Telegram"""
    print("\n📱 Testing with Real Telegram Bot")
    print("=" * 60)
    print("""
1. Set environment variables:
   export TELEGRAM_BOT_TOKEN="your-bot-token"
   export USE_NEW_AI=false  # Start with it off
   export NEW_AI_USER_IDS="your-telegram-id"  # Just you for testing
   
2. Run the bot:
   python3 telegram_bot_coach.py
   
3. In Telegram:
   - Send /start
   - Send your wallet address (natural flow)
   - Make a trade or say "hey"
   - Try "pause", "resume", "clear chat"
   - Notice the inline buttons
   
4. Monitor logs for:
   - "Using new conversation engine for user X"
   - "Sent AI response to user X"
   - Response times
   
5. Test rollback:
   export USE_NEW_AI=false
   # Bot instantly returns to template system
""")


if __name__ == "__main__":
    print("Choose test mode:")
    print("1. Test locally (no Telegram needed)")
    print("2. See Telegram testing instructions")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        asyncio.run(test_bot_locally())
    else:
        asyncio.run(test_with_telegram()) 