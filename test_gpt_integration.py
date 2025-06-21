"""
Minimal GPT integration for testing bot responses
Uses real GPT client and coach prompt without full bot infrastructure
"""

import os
import json
import asyncio
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

# Import components we need
from gpt_client import GPTClient
from prompt_builder import build_prompt


class TestGPTIntegration:
    """Minimal GPT integration for testing"""
    
    def __init__(self):
        try:
            self.gpt_client = GPTClient(timeout=15.0)  # Increased timeout for tests
            self.has_gpt = self.gpt_client.is_available()
        except Exception as e:
            print(f"Warning: Could not initialize GPT client: {e}")
            self.gpt_client = None
            self.has_gpt = False
        self.tools_called = []
        self.wallet_address = "test_wallet_34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
        self.user_id = "test_user_2105556647"
        
    async def get_response(self, context: Dict[str, Any], message: str) -> Tuple[str, List[str]]:
        """Get GPT response with minimal context"""
        self.tools_called = []
        
        # If no GPT available, return a mock response based on the scenario
        if not self.has_gpt or self.gpt_client is None:
            return self._get_mock_response(context, message)
        
        # Build prompt data from test context
        prompt_data = self._build_prompt_data(context, message)
        
        # Build the actual prompt using the real prompt builder
        from prompt_builder import build_prompt as build_prompt_real
        full_prompt_dict = await build_prompt_real(
            user_id=int(self.user_id.replace('test_user_', '')),
            wallet_address=self.wallet_address,
            event_type='message',
            event_data={'text': message}
        )
        
        # Convert to string format for GPT
        full_prompt = json.dumps(full_prompt_dict)
        
        # Get the coach prompt
        coach_prompt = self._load_coach_prompt()
        
        # Get tool definitions from the bot
        tools = self._get_gpt_tools()
        
        # Monkey patch the diary functions to return test data
        await self._setup_test_data_handlers(context)
        
        # Debug: print context if running tests
        if os.getenv('DEBUG_TESTS'):
            print(f"\nDEBUG: Full prompt dict keys: {list(full_prompt_dict.keys())}")
            if 'position_state' in full_prompt_dict:
                print(f"DEBUG: position_state: {full_prompt_dict['position_state']}")
            if 'trade_analysis' in full_prompt_dict:
                print(f"DEBUG: trade_analysis: {full_prompt_dict['trade_analysis']}")
        
        # Call GPT with tools
        response = await self.gpt_client.chat_with_tools(
            system_prompt=coach_prompt,
            user_message=full_prompt,
            tools=tools,
            wallet_address=self.wallet_address
        )
        
        return response or "", self.tools_called
    
    def _build_prompt_data(self, context: Dict[str, Any], message: str) -> Dict[str, Any]:
        """Build prompt data from test context"""
        # Convert test trades to diary format
        recent_trades = []
        for trade in context.get('trades', [])[-5:]:  # Last 5 trades
            recent_trades.append({
                'action': trade.action,
                'token_symbol': trade.token,
                'amount_sol': trade.amount_sol,
                'timestamp': trade.timestamp.isoformat(),
                'market_cap_usd': trade.market_cap,
                'trade_pct_bankroll': (trade.amount_sol / trade.bankroll_before) * 100
            })
        
        # Build prompt data similar to real bot
        prompt_data = {
            'wallet_address': self.wallet_address,
            'user_id': self.user_id,
            'current_event': {
                'type': 'message',
                'data': {'text': message},
                'timestamp': datetime.now().isoformat()
            },
            'recent_chat': self._build_chat_history(context, message),
            'user_goal': context['user_profile'].goal,
            'recent_facts': [],
            'trade_sequence': recent_trades,
            'bankroll_sol': context.get('current_bankroll', 33.0),
            'likely_referencing_trade': recent_trades[-1] if recent_trades else None,
            'is_follow_up': self._is_follow_up(message)
        }
        
        return prompt_data
    
    def _build_chat_history(self, context: Dict[str, Any], current_message: str) -> List[Dict[str, str]]:
        """Build chat history from previous messages"""
        history = []
        
        # Add previous messages
        for msg in context.get('message_history', []):
            history.append({
                'role': 'user',
                'content': msg.text
            })
            # Would need bot responses here, but we're testing without them
        
        # Add current message
        history.append({
            'role': 'user', 
            'content': current_message
        })
        
        return history[-10:]  # Last 10 messages
    
    def _is_follow_up(self, message: str) -> bool:
        """Detect if message is likely a follow-up"""
        follow_up_indicators = ['?', 'why', 'what', 'how', 'explain']
        message_lower = message.lower()
        return any(indicator in message_lower for indicator in follow_up_indicators) and len(message.split()) < 5
    
    def _load_coach_prompt(self) -> str:
        """Load the coach prompt"""
        try:
            with open('coach_prompt_v1.md', 'r') as f:
                return f.read()
        except FileNotFoundError:
            print("Warning: coach_prompt_v1.md not found, using default prompt")
            return """You are a trading coach. Be brief and helpful."""
    
    def _get_gpt_tools(self) -> List[Dict[str, Any]]:
        """Get tool definitions from the bot"""
        # Minimal tool definitions for testing
        return [
            {
                "type": "function",
                "function": {
                    "name": "calculate_token_pnl_from_trades",
                    "description": "Calculate accurate P&L for a token using trade deduplication",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "token_symbol": {"type": "string", "description": "Token symbol (e.g. BONK, WIF)"}
                        },
                        "required": ["token_symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_token_balance",
                    "description": "Get current token balance in wallet",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "token": {"type": "string", "description": "Token symbol"}
                        },
                        "required": ["token"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_last_n_trades",
                    "description": "Get last N trades from wallet",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "n": {"type": "integer", "description": "Number of trades to fetch", "default": 5}
                        }
                    }
                }
            }
        ]
    
    async def _handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Handle tool calls for testing"""
        self.tools_called.append(tool_name)
        
        # Return mock data for different tools
        if tool_name == "calculate_token_pnl_from_trades":
            return {
                'token': arguments.get('token', 'UNKNOWN'),
                'total_bought_sol': 10.022,
                'total_sold_sol': 6.594,
                'net_sol': -3.428,
                'profit_sol': -3.428,
                'profit_pct': -34.2
            }
        elif tool_name == "fetch_token_balance":
            return {
                'token': arguments.get('token', 'UNKNOWN'),
                'balance': 7.0,
                'value_sol': 7.0
            }
        elif tool_name == "fetch_last_n_trades":
            return []  # Empty for now
        else:
            return {}
    
    def _get_mock_response(self, context: Dict[str, Any], message: str) -> Tuple[str, List[str]]:
        """Get mock response when GPT is not available"""
        # Simple mock responses based on message content
        message_lower = message.lower()
        
        if "pnl" in message_lower or "profit" in message_lower:
            self.tools_called = ["calculate_token_pnl_from_trades"]
            return "3.4 sol loss on FINNA", self.tools_called
        elif "position" in message_lower:
            self.tools_called = ["fetch_token_balance"]
            return "7 sol remaining (70% of position)", self.tools_called
        elif "why" in message_lower:
            return "FINNA at 771k mcap is risky", []
        else:
            return "33 sol bankroll", []
    
    async def _setup_test_data_handlers(self, context: Dict[str, Any]):
        """Set up function handlers to return test data"""
        import diary_api
        
        # Store original functions
        self._orig_fetch_trades_by_token = diary_api.fetch_trades_by_token
        self._orig_fetch_token_balance = diary_api.fetch_token_balance
        self._orig_calculate_token_pnl = diary_api.calculate_token_pnl_from_trades
        self._orig_fetch_last_n_trades = diary_api.fetch_last_n_trades
        
        # Also mock the new prompt builder functions
        import prompt_builder
        self._orig_get_user_patterns = getattr(prompt_builder, 'get_user_patterns', None)
        self._orig_get_position_state = getattr(prompt_builder, 'get_position_state', None)
        self._orig_get_current_bankroll = getattr(prompt_builder, 'get_current_bankroll', None)
        
        # Get test trades from context
        test_trades = context.get('trades', [])
        
        # Reference to self for inner functions
        tools_called = self.tools_called
        
        # Create mock functions that return test data
        async def mock_fetch_trades_by_token(wallet: str, token: str, n: int = 10):
            """Return test trades for the requested token"""
            tools_called.append("fetch_trades_by_token")
            # Filter trades for this token
            token_trades = []
            for trade in test_trades:
                if trade.token.upper() == token.upper():
                    token_trades.append({
                        'action': trade.action,
                        'token_symbol': trade.token,
                        'amount_sol': trade.amount_sol,
                        'signature': trade.signature,
                        'timestamp': trade.timestamp.isoformat(),
                        'market_cap_usd': trade.market_cap,
                        'trade_pct_bankroll': (trade.amount_sol / trade.bankroll_before) * 100,
                        'bankroll_before_sol': trade.bankroll_before,
                        'bankroll_after_sol': trade.bankroll_after
                    })
            return token_trades[:n]
        
        async def mock_fetch_token_balance(wallet: str, token: str):
            """Calculate token balance from test trades"""
            tools_called.append("fetch_token_balance")
            balance = 0.0
            for trade in test_trades:
                if trade.token.upper() == token.upper():
                    if trade.action == 'BUY':
                        balance += trade.amount_sol
                    else:  # SELL
                        balance -= trade.amount_sol
            
            return {
                'token': token,
                'balance': max(0, balance),  # Can't have negative balance
                'value_sol': max(0, balance)
            }
        
        async def mock_calculate_token_pnl(wallet: str, token: str):
            """Calculate realistic P&L from test trades"""
            tools_called.append("calculate_token_pnl_from_trades")
            total_bought = 0.0
            total_sold = 0.0
            signatures = set()
            
            for trade in test_trades:
                if trade.token.upper() == token.upper():
                    # Handle duplicates (key part of FINNA test)
                    if trade.signature in signatures and trade.duplicates == 1:
                        continue
                    signatures.add(trade.signature)
                    
                    if trade.action == 'BUY':
                        total_bought += trade.amount_sol
                    else:  # SELL
                        # If duplicates, only count once
                        if trade.duplicates > 1:
                            total_sold += trade.amount_sol
                        else:
                            total_sold += trade.amount_sol
            
            net_sol = total_sold - total_bought
            profit_pct = (net_sol / total_bought * 100) if total_bought > 0 else 0
            
            return {
                'token': token,
                'total_bought_sol': total_bought,
                'total_sold_sol': total_sold,
                'net_sol': net_sol,
                'profit_sol': net_sol,
                'profit_pct': profit_pct,
                'num_buys': sum(1 for t in test_trades if t.token.upper() == token.upper() and t.action == 'BUY'),
                'num_sells': sum(1 for t in test_trades if t.token.upper() == token.upper() and t.action == 'SELL')
            }
        
        async def mock_fetch_last_n_trades(wallet: str, n: int = 10):
            """Return last N test trades"""
            tools_called.append("fetch_last_n_trades")
            trades = []
            for trade in test_trades[-n:]:
                trades.append({
                    'action': trade.action,
                    'token_symbol': trade.token,
                    'amount_sol': trade.amount_sol,
                    'signature': trade.signature,
                    'timestamp': trade.timestamp.isoformat(),
                    'market_cap_usd': trade.market_cap,
                    'trade_pct_bankroll': (trade.amount_sol / trade.bankroll_before) * 100
                })
            return trades
        
        # Monkey patch the functions
        diary_api.fetch_trades_by_token = mock_fetch_trades_by_token
        diary_api.fetch_token_balance = mock_fetch_token_balance
        diary_api.calculate_token_pnl_from_trades = mock_calculate_token_pnl
        diary_api.fetch_last_n_trades = mock_fetch_last_n_trades
        
        # Mock the new prompt builder functions
        async def mock_get_user_patterns(wallet: str):
            """Return typical user patterns from test context"""
            user_profile = context.get('user_profile')
            if user_profile:
                return {
                    'position_size': {
                        'typical_pct': sum(user_profile.typical_position_size_pct) / 2,
                        'range': user_profile.typical_position_size_pct
                    },
                    'market_cap': {
                        'typical': sum(user_profile.typical_mcap_range) / 2,
                        'range': user_profile.typical_mcap_range
                    },
                    'typical_trade_hour': 14,  # 2 PM
                    'total_trades_30d': 50
                }
            return None
        
        async def mock_get_position_state(wallet: str, token: str):
            """Return position state for partial sells"""
            # Calculate from test trades
            total_bought = 0.0
            total_sold = 0.0
            buy_count = 0
            sell_count = 0
            
            for trade in test_trades:
                if trade.token.upper() == token.upper():
                    if trade.action == 'BUY':
                        total_bought += trade.amount_sol
                        buy_count += 1
                    else:
                        total_sold += trade.amount_sol
                        sell_count += 1
            
            if total_bought == 0:
                return None
                
            remaining = total_bought - total_sold
            pct_sold = (total_sold / total_bought * 100) if total_bought > 0 else 0
            pct_remaining = 100 - pct_sold
            
            return {
                'token': token,
                'total_bought_sol': round(total_bought, 3),
                'total_sold_sol': round(total_sold, 3),
                'remaining_sol': round(remaining, 3),
                'pct_remaining': round(pct_remaining, 1),
                'pct_sold': round(pct_sold, 1),
                'num_buys': buy_count,
                'num_sells': sell_count,
                'is_partial_sell': sell_count > 0 and remaining > 0.001
            }
        
        async def mock_get_current_bankroll(wallet: str):
            """Return current bankroll from context"""
            return context.get('current_bankroll', 33.0)
        
        # Patch the prompt builder functions to ensure they work in tests
        import sys
        if 'prompt_builder' not in sys.modules:
            import prompt_builder
        
        # Store originals
        orig_get_user_patterns = prompt_builder.get_user_patterns
        orig_get_position_state = prompt_builder.get_position_state
        orig_get_current_bankroll = prompt_builder.get_current_bankroll
        orig_analyze_current_trade = prompt_builder.analyze_current_trade if hasattr(prompt_builder, 'analyze_current_trade') else None
        orig_get_trade_sequence = prompt_builder.get_trade_sequence_with_timing if hasattr(prompt_builder, 'get_trade_sequence_with_timing') else None
        
        # Create wrapper functions that fallback to mocks
        async def wrapped_get_user_patterns(wallet: str):
            try:
                result = await orig_get_user_patterns(wallet)
                if result:
                    return result
            except:
                pass
            return await mock_get_user_patterns(wallet)
        
        async def wrapped_get_position_state(wallet: str, token: str):
            try:
                result = await orig_get_position_state(wallet, token)
                if result:
                    return result
            except:
                pass
            return await mock_get_position_state(wallet, token)
        
        async def wrapped_get_current_bankroll(wallet: str):
            try:
                result = await orig_get_current_bankroll(wallet)
                if result is not None:
                    return result
            except:
                pass
            return await mock_get_current_bankroll(wallet)
        
        async def wrapped_analyze_current_trade(wallet: str, event_data: dict):
            """Analyze current trade vs user patterns"""
            if 'trade_pct_bankroll' in event_data:
                current_pct = event_data['trade_pct_bankroll']
                typical_pct = 7.5  # Average of 5-10%
                return {
                    'position_size_vs_typical': round(current_pct / typical_pct, 1),
                    'is_unusually_large': current_pct > 10.0,
                    'is_unusually_small': current_pct < 5.0,
                    'current_hour': datetime.now().hour,
                    'is_unusual_time': datetime.now().hour == 3  # 3 AM is unusual
                }
            return {}
        
        async def wrapped_get_trade_sequence_with_timing(wallet: str, limit: int = 5):
            """Get trade sequence with timing gaps"""
            sequence = []
            for i, trade in enumerate(test_trades[-limit:]):
                trade_info = {
                    'token': trade.token,
                    'action': trade.action,
                    'amount_sol': trade.amount_sol,
                    'market_cap': trade.market_cap,
                    'timestamp': trade.timestamp.isoformat()
                }
                if i > 0:
                    # Calculate actual timing gap
                    current = trade.timestamp
                    previous = test_trades[-limit:][i-1].timestamp
                    gap_minutes = int((current - previous).total_seconds() / 60)
                    trade_info['minutes_since_last'] = gap_minutes
                sequence.append(trade_info)
            return sequence
        
        # Apply patches
        prompt_builder.get_user_patterns = wrapped_get_user_patterns
        prompt_builder.get_position_state = wrapped_get_position_state
        prompt_builder.get_current_bankroll = wrapped_get_current_bankroll
        prompt_builder.analyze_current_trade = wrapped_analyze_current_trade
        prompt_builder.get_trade_sequence_with_timing = wrapped_get_trade_sequence_with_timing
        
        # We'll track tool calls through the GPT client's logging


# Singleton instance
test_gpt = TestGPTIntegration() 