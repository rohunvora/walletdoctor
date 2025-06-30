#!/usr/bin/env python3
"""
Validation test scenarios for the intelligent assistant behavior
Based on architect's checklist
"""

import asyncio
import json
from datetime import datetime
from gpt_client import create_gpt_client
from prompt_builder import build_prompt

async def test_scenario(scenario_name: str, user_message: str, trade_data: dict = None):
    """Test a specific scenario"""
    print(f"\n{'='*60}")
    print(f"SCENARIO: {scenario_name}")
    print(f"USER: {user_message}")
    print(f"{'='*60}")
    
    # Mock data
    user_id = 123456
    wallet_address = "7xKXtg2CW87d97TXJSDpbD5jBkheTXqA6Q3vmh9tDKzU"
    
    # Create GPT client
    gpt_client = create_gpt_client()
    
    # Load v2 prompt
    with open('coach_prompt_v2.md', 'r') as f:
        coach_prompt = f.read()
    
    # Build context
    if trade_data:
        prompt_data = await build_prompt(user_id, wallet_address, 'trade', trade_data)
    else:
        prompt_data = await build_prompt(user_id, wallet_address, 'message', {'text': user_message})
    
    # Mock pattern analysis if it's a trade
    if trade_data:
        prompt_data['current_event']['data']['pattern_analysis'] = {
            'patterns': [
                {'symbol': 'BONK', 'avg_buy_sol': 0.5, 'roi_percentage': 25.3},
                {'symbol': 'WIF', 'avg_buy_sol': 0.8, 'roi_percentage': -15.2}
            ],
            'summary': 'Mixed results with memecoins',
            'recommendation': 'Consider smaller positions'
        }
    
    # Get response
    response = await gpt_client.chat_with_tools(
        system_prompt=coach_prompt,
        user_message=json.dumps(prompt_data),
        tools=[],  # Empty tools for testing
        wallet_address=wallet_address
    )
    
    print(f"\nBOT RESPONSE: {response}")
    print(f"Response length: {len(response.split()) if response else 0} words")
    
    # Validate response characteristics
    if response:
        word_count = len(response.split())
        print(f"\n✓ Response generated")
        print(f"{'✓' if 10 <= word_count <= 30 else '✗'} Word count in range (10-30): {word_count}")
        print(f"{'✓' if '%' in response else '✗'} Contains percentage (position sizing)")
        print(f"{'✓' if any(t in response.lower() for t in ['pattern', 'similar', 'like your']) else '✗'} References patterns")
    else:
        print("\n✗ No response generated")

async def main():
    """Run all validation scenarios"""
    print("INTELLIGENT ASSISTANT VALIDATION TEST")
    print("Testing v2 behavior based on architect's checklist")
    
    # Scenario 1: User says "just bought POPCAT"
    await test_scenario(
        "User announces a buy",
        "just bought POPCAT",
        {
            'action': 'BUY',
            'token_symbol': 'POPCAT',
            'sol_amount': 0.5,
            'trade_pct_bankroll': 15.2,
            'bankroll_before_sol': 3.29,
            'market_cap': 1_200_000
        }
    )
    
    # Scenario 2: User says "this is pumping hard"
    await test_scenario(
        "User mentions price action",
        "this is pumping hard"
    )
    
    # Scenario 3: User asks "how am i doing today?"
    await test_scenario(
        "User asks for performance",
        "how am i doing today?"
    )
    
    # Scenario 4: User makes multiple rapid trades
    print("\n" + "="*60)
    print("SCENARIO: Multiple rapid trades")
    print("(Would test batching and non-spammy behavior)")
    print("="*60)
    
    # Scenario 5: User asks for specific help
    await test_scenario(
        "User asks for help",
        "should I take profits on WIF?"
    )
    
    print("\n" + "="*60)
    print("VALIDATION TEST COMPLETE")
    print("Compare responses against expected intelligent behavior")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())