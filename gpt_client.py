"""
GPT Client for conversational AI responses

This module provides a clean interface to OpenAI's GPT models for generating
natural, conversational responses to trading events and user messages.
"""

import asyncio
import json
import logging
import os
from typing import Dict, Optional, List
from datetime import datetime
import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class GPTClient:
    """Client for generating conversational responses using OpenAI's GPT models"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini", 
                 timeout: float = 30.0, temperature: float = 0.7):
        """
        Initialize GPT client
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model to use (default: gpt-4o-mini for cost efficiency)
            timeout: Timeout for API calls (default: 30.0 seconds)
            temperature: Temperature for generating responses (default: 0.7)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("No OpenAI API key provided - GPT features disabled")
            
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.base_url = "https://api.openai.com/v1/chat/completions"
        
        # TODO: When OpenAI SDK supports prompt IDs, replace hardcoded prompt with:
        # self.prompt_id = os.getenv("OPENAI_PROMPT_ID", "pmpt_68510c567dec819093fc41e905284897054a655fad6e960c")
        # Then use in generate_response:
        # response = await self.client.responses.create(
        #     prompt={"id": self.prompt_id, "version": "1"},
        #     model=self.model,
        #     input=...
        # )
        
        # For now, using hardcoded system prompt
        self.system_prompt = """You are a pocket trading coach - think of yourself as a sharp, observant friend who actually trades. You:

- Notice patterns and call them out (gently roast when needed)
- Remember what tokens they trade and their habits
- Celebrate wins, commiserate losses (with real numbers)
- Ask specific questions, not generic ones
- Use their trading history when relevant
- Keep it real - no corporate BS

CRITICAL RULES:
- NEVER repeat the same stats in every message (like "54 trades and 0% win rate")
- NEVER ask generic questions like "What's your game plan?" repeatedly
- ALWAYS vary your responses and focus on different aspects each time
- When user asks about specific trades, analyze WHY they might have failed
- Look for patterns in losses (timing, token types, position sizes)
- Give actionable insights, not just observations

Style:
- Short, punchy messages (like texting)
- Casual but insightful
- Emojis when it adds flavor
- Reference specific prices/amounts when you have them
- Max 2-3 sentences usually

Examples:
User trades BONK for 5th time: "BONK again? 😅 That's like your 5th entry this week. What's different this time?"
User sells at loss: "Ouch -$230. Stop loss or just got spooked?"
User asks about worst trades: "MAG crushed you for -$413. Looking at the chart, seems like classic FOMO entry at the top?"
User with 0% win rate: "Rough week, but I notice you're averaging 0.1 SOL per trade - maybe size up on conviction plays instead of spraying?"
Multiple losses: "Your losses cluster around 3-4am. Late night degen mode hitting different?"

Never:
- Sound like a therapist
- Give financial advice
- Be overly polite
- Ask the same generic questions
- Repeat the same statistics."""
    
    async def generate_response(self, context_data: str) -> Optional[str]:
        """
        Generate a response based on context
        
        Args:
            context_data: Either JSON string (legacy) or structured markdown (enhanced)
            
        Returns:
            Generated response or None if failed/timed out
        """
        if not self.api_key:
            return None
        
        try:
            # Check if this is the new enhanced context format (markdown) or legacy JSON
            if context_data.startswith('##'):
                # New enhanced context format - use directly
                user_message = context_data
                messages = [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message}
                ]
            else:
                # Legacy JSON format - parse and format
                try:
                    context = json.loads(context_data)
                    user_message = self._format_user_message(context)
                    
                    # Build messages for API
                    messages = [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_message}
                    ]
                    
                    # Add recent conversation history if available
                    history = context.get("recent_conversation", [])
                    for msg in history[-6:]:  # Last 6 messages for context
                        if msg.get("role") == "user" and msg.get("summary"):
                            messages.append({"role": "user", "content": msg["summary"]})
                        elif msg.get("role") == "assistant" and msg.get("summary"):
                            messages.append({"role": "assistant", "content": msg["summary"]})
                except json.JSONDecodeError:
                    # If it's not valid JSON and doesn't start with ##, treat as plain text
                    messages = [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": context_data}
                    ]
            
            # Make API call with timeout
            async with httpx.AsyncClient() as client:
                response = await asyncio.wait_for(
                    client.post(
                        self.base_url,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": self.model,
                            "messages": messages,
                            "temperature": self.temperature,
                            "max_tokens": 150,  # Keep responses concise
                            "n": 1
                        }
                    ),
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.warning(f"GPT request timed out after {self.timeout}s")
            return None
        except Exception as e:
            logger.error(f"Error generating GPT response: {e}")
            return None
    
    def _format_user_message(self, context: Dict) -> str:
        """Format context into a clear message for GPT"""
        current = context.get("current_event", {})
        event_type = current.get("type", "unknown")
        event_data = current.get("data", {})
        
        # Format based on event type
        if event_type == "trade":
            action = event_data.get("action", "trade")
            token = event_data.get("token_symbol", "token")
            amount = event_data.get("amount_sol", 0)
            
            if action == "BUY":
                message = f"User just bought {amount:.3f} SOL of {token}"
            else:
                pnl = event_data.get("pnl_usd", 0)
                if pnl > 0:
                    message = f"User just sold {token} for +${pnl:.0f} profit"
                elif pnl < 0:
                    message = f"User just sold {token} for -${abs(pnl):.0f} loss"
                else:
                    message = f"User just sold {token} at breakeven"
                    
        elif event_type == "message":
            message = f"User says: {event_data.get('text', '')}"
            
        elif event_type == "command":
            command = event_data.get("command", "")
            if command == "/chat":
                message = "User wants to chat"
            else:
                message = f"User used command: {command}"
        else:
            message = f"Event: {event_type}"
        
        # Add position context if relevant
        positions = context.get("positions", {})
        if positions.get("total_positions", 0) > 0:
            message += f"\n\nCurrent positions: {positions['total_positions']} tokens"
            message += f", {positions['total_exposure_pct']:.1f}% total exposure"
            
            # Add largest position if it exists
            largest = positions.get("largest_position")
            if largest and largest in positions.get("positions", {}):
                pos_data = positions["positions"][largest]
                message += f"\nLargest: {largest} ({pos_data['size_pct']:.1f}%"
                
                pnl_usd = pos_data.get("pnl_usd", 0)
                if pnl_usd > 0:
                    message += f", +${pnl_usd:.0f})"
                elif pnl_usd < 0:
                    message += f", -${abs(pnl_usd):.0f})"
                else:
                    message += ")"
        
        # Add user stats for context
        stats = context.get("user_stats", {})
        if stats.get("total_trades_week", 0) > 0:
            message += f"\n\nUser stats: {stats['win_rate']:.0f}% win rate this week"
            message += f" ({stats['total_wins']}W/{stats['total_losses']}L)"
        
        return message
    
    def update_system_prompt(self, new_prompt: str):
        """Update the system prompt for different coaching styles"""
        self.system_prompt = new_prompt
        logger.info("Updated GPT system prompt")
    
    def is_available(self) -> bool:
        """Check if GPT client is available"""
        return bool(self.api_key)

    async def chat_with_tools(self, system_prompt: str, user_message: str, tools: list, 
                             wallet_address: str = None, max_calls: int = 3) -> Optional[str]:
        """
        Chat with GPT using function calling tools
        
        Args:
            system_prompt: System prompt for the model
            user_message: User message/context
            tools: List of tool definitions
            wallet_address: Wallet address for tool execution
            max_calls: Maximum function calls per message (rate limit)
            
        Returns:
            Final response from GPT after tool execution
        """
        if not self.api_key:
            return None
        
        # Import tool functions
        from diary_api import (
            fetch_last_n_trades, 
            fetch_trades_by_token, 
            fetch_trades_by_time,
            fetch_token_balance,
            fetch_wallet_stats,
            fetch_market_cap_context,
            fetch_price_context,
            fetch_price_snapshots,
            save_user_goal,
            log_fact,
            # New analytics functions
            query_time_range,
            calculate_metrics,
            get_goal_progress,
            compare_periods,
            # Accurate P&L calculation
            calculate_token_pnl_from_trades
        )
        
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # Track function calls for rate limiting
            function_calls_count = 0
            
            # Initial call with tools
            async with httpx.AsyncClient() as client:
                response = await asyncio.wait_for(
                    client.post(
                        self.base_url,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": self.model,
                            "messages": messages,
                            "tools": tools,
                            "temperature": self.temperature,
                            "max_tokens": 200  # Increased for analytics responses - can be brief but complete
                        }
                    ),
                    timeout=self.timeout
                )
                
                if response.status_code != 200:
                    logger.error(f"OpenAI API error: {response.status_code}")
                    return None
                
                data = response.json()
                message = data["choices"][0]["message"]
                
                # Check if GPT wants to call functions
                while "tool_calls" in message and function_calls_count < max_calls:
                    messages.append(message)  # Add assistant message with tool calls
                    
                    # Execute each function call
                    for tool_call in message["tool_calls"]:
                        function_calls_count += 1
                        if function_calls_count > max_calls:
                            logger.warning(f"Rate limit reached: {max_calls} function calls")
                            break
                        
                        function_name = tool_call["function"]["name"]
                        arguments = json.loads(tool_call["function"]["arguments"])
                        
                        logger.info(f"Executing function: {function_name} with args: {arguments}")
                        
                        # Execute the function
                        try:
                            if function_name == "fetch_last_n_trades":
                                result = await fetch_last_n_trades(wallet_address, arguments.get("n", 5))
                            elif function_name == "fetch_trades_by_token":
                                result = await fetch_trades_by_token(
                                    wallet_address, 
                                    arguments["token"], 
                                    arguments.get("n", 5)
                                )
                            elif function_name == "fetch_trades_by_time":
                                result = await fetch_trades_by_time(
                                    wallet_address,
                                    arguments["start_hour"],
                                    arguments["end_hour"],
                                    arguments.get("n", 10)
                                )
                            elif function_name == "fetch_token_balance":
                                result = await fetch_token_balance(wallet_address, arguments["token"])
                            elif function_name == "fetch_wallet_stats":
                                result = await fetch_wallet_stats(wallet_address)
                            elif function_name == "fetch_market_cap_context":
                                result = await fetch_market_cap_context(wallet_address, arguments["token"])
                            elif function_name == "fetch_price_context":
                                # Need to get token address first
                                token_symbol = arguments["token"]
                                # Get trades to find token address
                                trades = await fetch_trades_by_token(wallet_address, token_symbol, 1)
                                if trades and len(trades) > 0:
                                    token_address = trades[0].get('token_address')
                                    if token_address:
                                        result = await fetch_price_context(wallet_address, token_address, token_symbol)
                                    else:
                                        result = {"error": f"Token address not found for {token_symbol}"}
                                else:
                                    result = {"error": f"No trades found for {token_symbol}"}
                            elif function_name == "save_user_goal":
                                # Extract user_id from wallet (this is simplified - you may need better user mapping)
                                user_id = arguments.get("user_id")
                                result = await save_user_goal(
                                    user_id,
                                    arguments.get("goal_data", {}),
                                    arguments.get("raw_text", "")
                                )
                            elif function_name == "log_fact":
                                user_id = arguments.get("user_id")
                                result = await log_fact(
                                    user_id,
                                    arguments.get("key", ""),
                                    arguments.get("value", ""),
                                    arguments.get("context", "")
                                )
                            elif function_name == "query_time_range":
                                result = await query_time_range(
                                    wallet_address,
                                    arguments.get("period", "today"),
                                    arguments.get("event_types")
                                )
                            elif function_name == "calculate_metrics":
                                result = await calculate_metrics(
                                    wallet_address,
                                    arguments.get("metric_type", "sum"),
                                    arguments.get("value_field", "profit_sol"),
                                    arguments.get("period", "today"),
                                    arguments.get("group_by")
                                )
                            elif function_name == "get_goal_progress":
                                user_id = arguments.get("user_id")
                                result = await get_goal_progress(user_id, wallet_address)
                            elif function_name == "compare_periods":
                                result = await compare_periods(
                                    wallet_address,
                                    arguments.get("period1", "last week"),
                                    arguments.get("period2", "this week"),
                                    arguments.get("metric_type", "sum"),
                                    arguments.get("value_field", "profit_sol")
                                )
                            elif function_name == "calculate_token_pnl_from_trades":
                                result = await calculate_token_pnl_from_trades(
                                    wallet_address,
                                    arguments.get("token_symbol", "")
                                )
                            elif function_name == "fetch_price_snapshots":
                                result = await fetch_price_snapshots(
                                    arguments.get("token_address", ""),
                                    arguments.get("hours", 24)
                                )
                            else:
                                result = {"error": f"Unknown function: {function_name}"}
                            
                            # Add function result to messages
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "content": json.dumps(result)
                            })
                            
                        except Exception as e:
                            logger.error(f"Error executing {function_name}: {e}")
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "content": json.dumps({"error": str(e)})
                            })
                    
                    # Get next response from GPT
                    response = await asyncio.wait_for(
                        client.post(
                            self.base_url,
                            headers={
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": self.model,
                                "messages": messages,
                                "temperature": self.temperature,
                                "max_tokens": 200  # Increased for analytics responses - can be brief but complete
                            }
                        ),
                        timeout=self.timeout
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"OpenAI API error after tools: {response.status_code}")
                        return None
                    
                    data = response.json()
                    message = data["choices"][0]["message"]
                
                # Return final content
                return message.get("content", "").strip()
                
        except asyncio.TimeoutError:
            logger.warning(f"GPT request timed out after {self.timeout}s")
            return None
        except Exception as e:
            logger.error(f"Error in chat_with_tools: {e}")
            return None


# Factory function
def create_gpt_client(api_key: str = None, model: str = "gpt-4o-mini",
                     timeout: float = 30.0) -> GPTClient:
    """Create GPT client instance"""
    return GPTClient(api_key=api_key, model=model, timeout=timeout)


# Testing
async def test_gpt_client():
    """Test GPT client functionality"""
    print("Testing GPT Client...")
    
    # Create client (will use env var if available)
    client = create_gpt_client()
    
    if not client.is_available():
        print("❌ No OpenAI API key - set OPENAI_API_KEY env var")
        return
    
    # Test context
    test_context = {
        "current_event": {
            "type": "trade",
            "data": {
                "action": "BUY",
                "token_symbol": "BONK",
                "amount_sol": 0.5
            }
        },
        "positions": {
            "total_positions": 2,
            "total_exposure_pct": 15.5,
            "largest_position": "PEPE",
            "positions": {
                "PEPE": {
                    "size_pct": 10.0,
                    "pnl_usd": 25.0
                }
            }
        },
        "user_stats": {
            "win_rate": 65.0,
            "total_wins": 13,
            "total_losses": 7,
            "total_trades_week": 20
        },
        "recent_conversation": []
    }
    
    # Test response generation
    print("\nGenerating response for BONK buy...")
    response = await client.generate_response(json.dumps(test_context))
    
    if response:
        print(f"✅ Response: {response}")
    else:
        print("❌ Failed to generate response")
    
    # Test with loss scenario
    test_context["current_event"] = {
        "type": "trade",
        "data": {
            "action": "SELL",
            "token_symbol": "WIF",
            "pnl_usd": -15.0
        }
    }
    
    print("\nGenerating response for WIF loss...")
    response = await client.generate_response(json.dumps(test_context))
    
    if response:
        print(f"✅ Response: {response}")
    else:
        print("❌ Failed to generate response")


if __name__ == "__main__":
    asyncio.run(test_gpt_client()) 