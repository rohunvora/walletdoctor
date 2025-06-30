#!/usr/bin/env python3

import asyncio
from prompt_builder import build_prompt
import json

async def test_prompt_data():
    """See what data is being sent to GPT for 'how am i doing today?'"""
    
    user_id = 2105556647  # Your user ID from logs
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    # Build the prompt data
    prompt_data = await build_prompt(user_id, wallet, 'message', {'text': 'how am i doing today?'})
    
    print("PROMPT DATA SENT TO GPT:")
    print("=" * 60)
    print(json.dumps(prompt_data, indent=2))
    
    # Check if it contains the wrong $717
    prompt_str = json.dumps(prompt_data)
    if "717" in prompt_str:
        print("\n⚠️  FOUND $717 IN PROMPT DATA!")
        print("This is why GPT keeps saying $717 - it's in the context")

if __name__ == "__main__":
    asyncio.run(test_prompt_data()) 