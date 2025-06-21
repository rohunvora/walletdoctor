#!/usr/bin/env python3

import asyncio
import sys
import os
import json

sys.path.append('.')
from dotenv import load_dotenv
load_dotenv()

from gpt_client import create_gpt_client
from prompt_builder import build_prompt

async def test_single_scenario():
    """Test one scenario with the new prompt vs old"""
    
    gpt_client = create_gpt_client()
    wallet_address = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    user_id = 12345
    
    print("=== BEFORE vs AFTER COMPARISON ===")
    print("User: 'just bought POPCAT'")
    print()
    
    # Test with new prompt
    print("NEW PROMPT (v2):")
    try:
        prompt_data = await build_prompt(user_id, wallet_address, 'message', {'text': 'just bought POPCAT'})
        
        with open('coach_prompt_v2.md', 'r') as f:
            coach_prompt = f.read()
        
        from telegram_bot_coach import PocketCoachBot
        bot = PocketCoachBot("dummy_token")
        tools = bot._get_gpt_tools()
        
        response = await gpt_client.chat_with_tools(
            system_prompt=coach_prompt,
            user_message=json.dumps(prompt_data),
            tools=tools,
            wallet_address=wallet_address
        )
        
        print(f'"{response}"')
        
    except Exception as e:
        print(f"Error: {e}")
    
    print()
    print("ANALYSIS:")
    print("- Is this more engaging than 'noted. just bought POPCAT.'?")
    print("- Would you want to continue this conversation?")
    print("- Does it feel like an intelligent assistant?")

if __name__ == "__main__":
    asyncio.run(test_single_scenario())