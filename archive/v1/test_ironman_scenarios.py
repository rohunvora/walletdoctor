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

async def test_ironman_scenarios():
    """Test specific 'ironman suit' scenarios with real wallet data"""
    
    print("=== IRONMAN SUIT TRADING ASSISTANT TEST ===")
    print("Testing real use cases you described")
    
    # Create GPT client
    gpt_client = create_gpt_client()
    if not gpt_client.is_available():
        print("❌ No OpenAI API key available")
        return
    
    # Test wallets
    wallets = [
        "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",  # Your wallet
        "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
        "9xdv9Jt2ef3UmLPn8VLsSZ41Gr79Nj55nqjsekt5ASM",
        "215nhcAHjQQGgwpQSJQ7zR26etbjjtVdW74NLzwEgQjP"
    ]
    
    # Real scenarios from your brain dump
    scenarios = [
        {
            "name": "Position sizing awareness",
            "user_message": "just bought POPCAT",
            "goal": "Bot should tell me % of bankroll + find similar trades at that mcap/sizing",
            "look_for": ["% of bankroll", "similar", "mcap", "sizing"]
        },
        {
            "name": "Moonboy check",
            "user_message": "this is pumping hard, looks like it could 10x",
            "goal": "Bot should push me to come up with sell plan",
            "look_for": ["exit", "plan", "sell", "target", "profit"]
        },
        {
            "name": "Random buy discipline",
            "user_message": "aped into this new token",
            "goal": "Bot should ask for reasoning to sharpen thinking",
            "look_for": ["why", "reason", "thinking", "thesis"]
        },
        {
            "name": "Pattern recognition",
            "user_message": "bought some more",
            "goal": "Bot should spot patterns and give context",
            "look_for": ["pattern", "similar", "last time", "usual"]
        },
        {
            "name": "Price target reminder",
            "user_message": "should I sell this pump?",
            "goal": "Bot should remember any previous sell plans/targets",
            "look_for": ["target", "plan", "said", "remember"]
        }
    ]
    
    for wallet_idx, wallet in enumerate(wallets):
        print(f"\n{'='*80}")
        print(f"TESTING WALLET {wallet_idx + 1}: {wallet[:8]}...")
        print('='*80)
        
        for scenario_idx, scenario in enumerate(scenarios, 1):
            print(f"\n--- Scenario {scenario_idx}: {scenario['name']} ---")
            print(f"User: \"{scenario['user_message']}\"")
            print(f"Goal: {scenario['goal']}")
            print("-" * 60)
            
            try:
                # Use dummy user_id
                user_id = 12345 + wallet_idx
                
                # Build prompt context
                prompt_data = await build_prompt(user_id, wallet, 'message', {'text': scenario['user_message']})
                
                # Get new intelligent coach system prompt
                with open('coach_prompt_v2.md', 'r') as f:
                    coach_prompt = f.read()
                
                # Get GPT tools
                from telegram_bot_coach import PocketCoachBot
                bot = PocketCoachBot("dummy_token")
                tools = bot._get_gpt_tools()
                
                # Ask GPT
                response = await gpt_client.chat_with_tools(
                    system_prompt=coach_prompt,
                    user_message=json.dumps(prompt_data),
                    tools=tools,
                    wallet_address=wallet
                )
                
                print(f"Bot Response:")
                print(f"\"{response}\"")
                
                # Evaluate against goals
                print(f"\nEvaluation:")
                if response:
                    found_keywords = [kw for kw in scenario['look_for'] if kw.lower() in response.lower()]
                    if found_keywords:
                        print(f"✅ Found relevant concepts: {', '.join(found_keywords)}")
                    else:
                        print(f"⚠️  Missing expected concepts: {', '.join(scenario['look_for'])}")
                    
                    if len(response) > 100:
                        print("✅ Substantial response")
                    else:
                        print("⚠️  Response too brief")
                else:
                    print("❌ No response")
                
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
    
    print(f"\n{'='*80}")
    print("IRONMAN SUIT TEST COMPLETE")
    print("\nKey Questions:")
    print("1. Does it feel like a smart assistant that knows your patterns?")
    print("2. Would these responses actually change your trading behavior?") 
    print("3. Does it proactively surface useful info vs just acknowledging?")
    print("4. Would you want to keep talking to get more details?")

if __name__ == "__main__":
    asyncio.run(test_ironman_scenarios())