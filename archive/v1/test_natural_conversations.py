#!/usr/bin/env python3

import asyncio
import sys
import os
import json
from datetime import datetime

# Set up environment and imports
sys.path.append('.')
from dotenv import load_dotenv
load_dotenv()

from gpt_client import create_gpt_client
from prompt_builder import build_prompt

async def test_natural_conversation():
    """Test natural conversation flows with real trading data"""
    
    print("=== NATURAL CONVERSATION TEST ===")
    print("Testing conversational flows that feel like talking to a trading buddy")
    
    # Create GPT client
    gpt_client = create_gpt_client()
    if not gpt_client.is_available():
        print("❌ No OpenAI API key available")
        return
    
    # Your actual wallet
    wallet_address = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    # Test realistic conversation scenarios
    conversation_tests = [
        {
            "name": "User expresses frustration",
            "user_message": "ugh, rough day",
            "context": "User just had a losing trade or bad day",
            "expected_behavior": "Coach should probe what happened and look at recent performance"
        },
        {
            "name": "User celebrates a win", 
            "user_message": "just hit 3x on a play!",
            "context": "User excited about a good trade",
            "expected_behavior": "Coach should put win in context of overall performance and patterns"
        },
        {
            "name": "User asks for advice",
            "user_message": "should I keep playing small caps?",
            "context": "User uncertain about strategy",
            "expected_behavior": "Coach should analyze their small cap performance vs other strategies"
        },
        {
            "name": "User shows uncertainty",
            "user_message": "not sure if I'm getting better at this",
            "context": "User questions their progress",
            "expected_behavior": "Coach should compare recent periods and highlight specific improvements"
        },
        {
            "name": "User asks vague question",
            "user_message": "how am I doing?",
            "context": "Open-ended question",
            "expected_behavior": "Coach should provide relevant context based on recent activity"
        }
    ]
    
    for i, test in enumerate(conversation_tests, 1):
        print(f"\n{'='*60}")
        print(f"Test {i}: {test['name']}")
        print(f"User: \"{test['user_message']}\"")
        print(f"Expected: {test['expected_behavior']}")
        print("-" * 60)
        
        try:
            # Use dummy user_id for testing
            user_id = 12345
            
            # Build prompt context like the bot does
            prompt_data = await build_prompt(user_id, wallet_address, 'message', {'text': test['user_message']})
            
            # Get coach system prompt
            with open('coach_prompt_v1.md', 'r') as f:
                coach_prompt = f.read()
            
            # Get GPT tools from bot
            from telegram_bot_coach import PocketCoachBot
            bot = PocketCoachBot("dummy_token")  # Just to access the tools method
            tools = bot._get_gpt_tools()
            
            # Ask GPT (same pattern as telegram bot)
            response = await gpt_client.chat_with_tools(
                system_prompt=coach_prompt,
                user_message=json.dumps(prompt_data),
                tools=tools,
                wallet_address=wallet_address
            )
            
            print(f"Coach Response:")
            print(f"\"{response}\"")
            
            # Basic evaluation
            if response and len(response) > 50:
                print("✅ Got substantial response")
            else:
                print("⚠️  Response too short or missing")
                
            if any(keyword in response.lower() for keyword in ['sol', 'trade', 'profit', 'loss']):
                print("✅ Uses trading context")
            else:
                print("⚠️  Missing trading context")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print(f"\n{'='*60}")
    print("CONVERSATION TEST COMPLETE")
    print("\nEvaluation Questions:")
    print("1. Do responses feel natural vs robotic?")
    print("2. Does coach proactively use data vs wait for specific requests?") 
    print("3. Would you naturally continue these conversations?")
    print("4. Do responses help with actual trading decisions?")

if __name__ == "__main__":
    asyncio.run(test_natural_conversation())