#!/usr/bin/env python3

import asyncio
import sys
import os
import json
from datetime import datetime

# Set up environment and imports
sys.path.append('.')

# Load environment
from dotenv import load_dotenv
load_dotenv()

from gpt_client import create_gpt_client

async def test_analytics_cutover():
    """Test the analytics cutover by simulating real user queries"""
    
    print("=== ANALYTICS CUTOVER TEST ===")
    
    # Create GPT client with test settings
    try:
        gpt_client = create_gpt_client()
        # Note: max_tokens is hardcoded in gpt_client.py at 40 tokens  
        print("✅ GPT client created successfully")
    except Exception as e:
        print(f"❌ Failed to create GPT client: {e}")
        return
    
    # Test user data
    user_id = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    test_queries = [
        "how am i doing today?",
        "what's my profit this week?",
        "am i doing better than last week?",
        "hit my goal?"
    ]
    
    print(f"\nTesting with user: {user_id}")
    print(f"Running {len(test_queries)} test queries...\n")
    
    for i, query in enumerate(test_queries, 1):
        print(f"{i}. Testing: '{query}'")
        
        try:
            # Build a minimal context for the query
            context = {
                "wallet_address": user_id,
                "user_goal": "reach 50 SOL bankroll",
                "current_bankroll": 33.47,
                "recent_facts": [],
                "trade_sequence": []
            }
            
            # Build system prompt and user message
            system_prompt = """You are a trading coach. Help the user track their trading progress.
Use analytics tools to provide accurate data."""
            
            # Create tool definitions for analytics (correct OpenAI format)
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "query_time_range",
                        "description": "Query trades for flexible time periods",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "period": {"type": "string", "description": "Time period like 'today', 'this week'"}
                            },
                            "required": ["period"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "calculate_metrics", 
                        "description": "Calculate accurate metrics",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "metric_type": {"type": "string", "enum": ["sum", "count", "avg"]},
                                "value_field": {"type": "string", "description": "Field to calculate"},
                                "period": {"type": "string", "description": "Time period"}
                            },
                            "required": ["metric_type", "value_field", "period"]
                        }
                    }
                }
            ]
            
            # Ask GPT with tools available
            response = await gpt_client.chat_with_tools(
                system_prompt,
                f"User question: {query}. Current bankroll: {context['current_bankroll']} SOL. Goal: {context['user_goal']}",
                tools,
                wallet_address=user_id
            )
            
            print(f"   Response: {response}")
            
            # Check response type and tools used
            if isinstance(response, dict):
                if 'content' in response:
                    print(f"   Content: {response['content']}")
                if 'tool_calls' in response and response['tool_calls']:
                    tools_used = [call['function']['name'] for call in response['tool_calls']]
                    print(f"   🔧 Tools used: {', '.join(tools_used)}")
                else:
                    print(f"   ⚠️  No tools used")
            else:
                print(f"   Response type: {type(response)}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print()
    
    print("=== TEST COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(test_analytics_cutover())