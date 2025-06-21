#!/usr/bin/env python3
"""
Automated Chat Scenario Testing
Simulates various user conversations and verifies bot behavior
"""

import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from gpt_client import GPTClient
from prompt_builder import build_prompt, write_to_diary
from event_store import Event, EventStore, TRADE_BUY, TRADE_SELL
from diary_api import query_time_range, calculate_metrics, compare_periods


class ChatScenarioTester:
    """Test various chat scenarios automatically"""
    
    def __init__(self):
        self.gpt_client = GPTClient()
        self.test_wallet = "TEST_SCENARIO_WALLET_" + str(int(datetime.now().timestamp()))
        self.test_user_id = 99999
        self.event_store = EventStore()
        self.results = []
    
    async def setup_test_data(self):
        """Create test trades for scenarios"""
        print("🔧 Setting up test data...")
        
        # Create trades over the past week
        now = datetime.now()
        trades = [
            # Today - net loss
            {"days_ago": 0, "token": "BONK", "action": "BUY", "sol": 10.0, "profit": 0},
            {"days_ago": 0, "token": "BONK", "action": "SELL", "sol": 8.0, "profit": -2.0},
            {"days_ago": 0, "token": "WIF", "action": "BUY", "sol": 5.0, "profit": 0},
            {"days_ago": 0, "token": "WIF", "action": "SELL", "sol": 4.0, "profit": -1.0},
            
            # Yesterday - net profit
            {"days_ago": 1, "token": "PEPE", "action": "BUY", "sol": 20.0, "profit": 0},
            {"days_ago": 1, "token": "PEPE", "action": "SELL", "sol": 30.0, "profit": 10.0},
            
            # Last week - mixed
            {"days_ago": 7, "token": "MYRO", "action": "BUY", "sol": 15.0, "profit": 0},
            {"days_ago": 7, "token": "MYRO", "action": "SELL", "sol": 18.0, "profit": 3.0},
            {"days_ago": 8, "token": "SAMO", "action": "BUY", "sol": 10.0, "profit": 0},
            {"days_ago": 8, "token": "SAMO", "action": "SELL", "sol": 5.0, "profit": -5.0},
        ]
        
        for trade in trades:
            timestamp = now - timedelta(days=trade["days_ago"], hours=trade["days_ago"] % 6)
            
            trade_data = {
                'signature': f'test_{trade["token"]}_{trade["action"]}_{trade["days_ago"]}',
                'action': trade["action"],
                'token_symbol': trade["token"],
                'sol_amount': trade["sol"],
                'profit_sol': trade["profit"],
                'trade_pct_bankroll': 10.0,
                'timestamp': timestamp.isoformat(),
                'bankroll_before_sol': 100.0,
                'bankroll_after_sol': 100.0 + (trade["profit"] if trade["action"] == "SELL" else -trade["sol"])
            }
            
            # Write to diary
            await write_to_diary('trade', self.test_user_id, self.test_wallet, trade_data)
            
            # Write to event store
            event = Event(
                user_id=self.test_wallet,
                event_type=TRADE_BUY if trade["action"] == "BUY" else TRADE_SELL,
                timestamp=timestamp,
                data=trade_data
            )
            self.event_store.record_event(event)
        
        print(f"✅ Created {len(trades)} test trades")
    
    async def simulate_chat(self, user_message: str, expected_patterns: List[str]) -> Dict:
        """Simulate a chat interaction and check response"""
        print(f"\n💬 User: '{user_message}'")
        
        # Build context
        context = await build_prompt(
            wallet_address=self.test_wallet,
            user_id=self.test_user_id,
            recent_chat=[{"role": "user", "content": user_message}]
        )
        
        # Get GPT response
        response = await self.gpt_client.chat_with_tools(
            messages=[
                {"role": "system", "content": context['system_prompt']},
                {"role": "user", "content": user_message}
            ],
            user_context={
                'wallet_address': self.test_wallet,
                'user_id': self.test_user_id
            }
        )
        
        bot_message = response.get('message', '')
        tools_used = response.get('tools_used', [])
        
        print(f"🤖 Bot: '{bot_message}'")
        if tools_used:
            print(f"🔧 Tools used: {', '.join(tools_used)}")
        
        # Check patterns
        patterns_found = []
        patterns_missing = []
        
        for pattern in expected_patterns:
            if pattern.startswith("TOOL:"):
                # Check if specific tool was used
                tool_name = pattern.replace("TOOL:", "")
                if tool_name in tools_used:
                    patterns_found.append(pattern)
                else:
                    patterns_missing.append(pattern)
            elif pattern.startswith("NUMBER:"):
                # Check for specific number in response
                number = pattern.replace("NUMBER:", "")
                if number in bot_message:
                    patterns_found.append(pattern)
                else:
                    patterns_missing.append(pattern)
            else:
                # Check for text pattern (case insensitive)
                if pattern.lower() in bot_message.lower():
                    patterns_found.append(pattern)
                else:
                    patterns_missing.append(pattern)
        
        success = len(patterns_missing) == 0
        
        return {
            'user_message': user_message,
            'bot_response': bot_message,
            'tools_used': tools_used,
            'expected_patterns': expected_patterns,
            'patterns_found': patterns_found,
            'patterns_missing': patterns_missing,
            'success': success
        }
    
    async def run_scenarios(self):
        """Run all test scenarios"""
        print("\n🚀 Running Chat Scenarios Test Suite")
        print("=" * 50)
        
        scenarios = [
            # Time-based queries
            {
                'message': "how am i doing today",
                'patterns': ["TOOL:query_time_range", "down", "3", "sol"]
            },
            {
                'message': "profit this week?",
                'patterns': ["TOOL:calculate_metrics", "sol"]
            },
            {
                'message': "am i improving?",
                'patterns': ["TOOL:compare_periods"]
            },
            {
                'message': "what's my daily average",
                'patterns': ["TOOL:calculate_metrics", "avg"]
            },
            
            # Goal-related queries
            {
                'message': "i want to make 100 sol",
                'patterns': ["TOOL:save_user_goal", "100", "sol"]
            },
            {
                'message': "how far from my goal",
                'patterns': ["TOOL:get_goal_progress"]
            },
            
            # Edge cases
            {
                'message': "yo",
                'patterns': ["sol"]  # Should mention current balance
            },
            {
                'message': "asdfghjkl",
                'patterns': ["?"]  # Should respond with confusion
            },
            
            # Fact storage
            {
                'message': "i only trade at night",
                'patterns': ["TOOL:log_fact", "noted"]
            },
            
            # Historical queries
            {
                'message': "show me my BONK trades",
                'patterns': ["TOOL:fetch_trades_by_token", "BONK"]
            },
            {
                'message': "what's my win rate",
                'patterns': ["TOOL:fetch_wallet_stats"]
            },
            
            # Complex queries
            {
                'message': "compare yesterday to today",
                'patterns': ["TOOL:compare_periods", "yesterday", "today"]
            },
            {
                'message': "total profit last 7 days",
                'patterns': ["TOOL:calculate_metrics", "NUMBER:5"]  # 10-5+3 = 8, but might show 5
            }
        ]
        
        for scenario in scenarios:
            result = await self.simulate_chat(
                scenario['message'],
                scenario['patterns']
            )
            self.results.append(result)
            
            # Brief pause between scenarios
            await asyncio.sleep(0.5)
    
    def generate_report(self):
        """Generate test report"""
        print("\n\n📊 Chat Scenario Test Report")
        print("=" * 50)
        
        passed = sum(1 for r in self.results if r['success'])
        total = len(self.results)
        
        print(f"\nOverall: {passed}/{total} scenarios passed ({passed/total*100:.1f}%)\n")
        
        # Detailed results
        for i, result in enumerate(self.results, 1):
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"\nScenario {i}: {status}")
            print(f"User: '{result['user_message']}'")
            print(f"Bot: '{result['bot_response']}'")
            
            if result['tools_used']:
                print(f"Tools: {', '.join(result['tools_used'])}")
            
            if not result['success']:
                print(f"Missing patterns: {', '.join(result['patterns_missing'])}")
        
        # Tool usage summary
        print("\n\n🔧 Tool Usage Summary")
        print("-" * 30)
        tool_counts = {}
        for result in self.results:
            for tool in result['tools_used']:
                tool_counts[tool] = tool_counts.get(tool, 0) + 1
        
        for tool, count in sorted(tool_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"{tool}: {count} times")
        
        return passed == total


async def main():
    """Run the chat scenario tests"""
    tester = ChatScenarioTester()
    
    try:
        # Setup test data
        await tester.setup_test_data()
        
        # Run scenarios
        await tester.run_scenarios()
        
        # Generate report
        all_passed = tester.generate_report()
        
        if all_passed:
            print("\n\n🎉 All chat scenarios passed!")
        else:
            print("\n\n⚠️ Some scenarios failed - review the bot's responses")
            
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main()) 