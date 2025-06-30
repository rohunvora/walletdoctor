#!/usr/bin/env python3
"""
Bot Testing Framework - Test real conversation scenarios to catch regressions
"""

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import argparse
import time
from collections import defaultdict

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

@dataclass
class TradeEvent:
    """Represents a trade event in a scenario"""
    action: str  # BUY or SELL
    token: str
    amount_sol: float
    signature: str
    timestamp: datetime
    market_cap: int
    bankroll_before: float
    bankroll_after: float
    duplicates: int = 1  # For testing duplicate trade bug
    
@dataclass
class Message:
    """Represents a user message and expected bot behavior"""
    text: str
    timestamp: datetime
    must_contain: List[str] = field(default_factory=list)
    must_not_contain: List[str] = field(default_factory=list)
    expected_tools: List[str] = field(default_factory=list)
    context_note: str = ""  # For documentation

@dataclass
class UserProfile:
    """Typical trading patterns for a test user"""
    typical_position_size_pct: Tuple[float, float] = (5.0, 10.0)  # 5-10% typical
    typical_mcap_range: Tuple[int, int] = (500_000, 2_000_000)  # $500K-$2M
    typical_hold_time: timedelta = timedelta(hours=2)
    goal: Optional[str] = "100 sol"
    
@dataclass
class TestScenario:
    """Complete test scenario with setup, actions, and expectations"""
    name: str
    description: str
    user_profile: UserProfile
    trades: List[TradeEvent] = field(default_factory=list)
    messages: List[Message] = field(default_factory=list)
    initial_bankroll: float = 33.0
    expected_final_state: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TestResult:
    """Result of running a test scenario"""
    scenario_name: str
    passed: bool
    assertions_passed: int
    assertions_total: int
    failures: List[Dict[str, Any]] = field(default_factory=list)
    execution_time: float = 0.0
    gpt_response: Optional[str] = None
    tools_called: List[str] = field(default_factory=list)

class ScenarioTester:
    """Main test runner for bot scenarios"""
    
    def __init__(self, use_cache: bool = True, quick_mode: bool = False):
        self.use_cache = use_cache
        self.quick_mode = quick_mode
        self.cache_dir = ".test_cache"
        self.results: List[TestResult] = []
        self.gpt_client = None  # Will be initialized when needed
        
        # Create cache directory if needed
        if self.use_cache and not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
    
    def _get_cache_key(self, scenario: TestScenario, message_idx: int) -> str:
        """Generate cache key for a scenario + message combination"""
        # Include relevant parts that would affect the response
        key_parts = [
            scenario.name,
            str(message_idx),
            # Include trade history up to this point
            str(len([t for t in scenario.trades if t.timestamp <= scenario.messages[message_idx].timestamp])),
        ]
        return "_".join(key_parts).replace(" ", "_")
    
    def _load_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Load cached GPT response if available"""
        if not self.use_cache:
            return None
            
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                return json.load(f)
        return None
    
    def _save_cached_response(self, cache_key: str, response: Dict[str, Any]):
        """Save GPT response to cache"""
        if not self.use_cache:
            return
            
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        with open(cache_file, 'w') as f:
            json.dump(response, f, indent=2)
    
    async def run_scenario(self, scenario: TestScenario) -> TestResult:
        """Run a single test scenario"""
        print(f"\n{BLUE}Running scenario: {scenario.name}{RESET}")
        print(f"  {scenario.description}")
        
        start_time = time.time()
        result = TestResult(
            scenario_name=scenario.name,
            passed=True,
            assertions_passed=0,
            assertions_total=0
        )
        
        # TODO: Set up test environment with scenario data
        # For now, we'll create the structure and add implementation next
        
        # Process each message in the scenario
        for idx, message in enumerate(scenario.messages):
            print(f"\n  Message {idx+1}: \"{message.text}\"")
            if message.context_note:
                print(f"    Context: {message.context_note}")
            
            # Check cache first
            cache_key = self._get_cache_key(scenario, idx)
            cached_response = self._load_cached_response(cache_key)
            
            if cached_response:
                print(f"    {YELLOW}Using cached response{RESET}")
                response = cached_response['response']
                tools_called = cached_response['tools_called']
            else:
                # Call GPT with minimal context
                response, tools_called = await self._get_gpt_response(scenario, idx, message)
                
                # Save to cache
                self._save_cached_response(cache_key, {
                    'response': response,
                    'tools_called': tools_called,
                    'timestamp': datetime.now().isoformat()
                })
            
            # Run assertions
            assertion_results = self._run_assertions(message, response, tools_called)
            result.assertions_total += len(assertion_results)
            
            for assertion in assertion_results:
                if assertion['passed']:
                    result.assertions_passed += 1
                    print(f"    {GREEN}✓ {assertion['description']}{RESET}")
                else:
                    result.passed = False
                    result.failures.append({
                        'message': message.text,
                        'assertion': assertion['description'],
                        'expected': assertion['expected'],
                        'actual': assertion['actual']
                    })
                    print(f"    {RED}✗ {assertion['description']}{RESET}")
                    print(f"      Expected: {assertion['expected']}")
                    print(f"      Actual: {assertion['actual']}")
        
        result.execution_time = time.time() - start_time
        return result
    
    def _run_assertions(self, message: Message, response: str, tools_called: List[str]) -> List[Dict[str, Any]]:
        """Run all assertions for a message"""
        assertions = []
        
        # Check must_contain
        for expected in message.must_contain:
            assertions.append({
                'description': f'Response contains "{expected}"',
                'passed': expected.lower() in response.lower(),
                'expected': expected,
                'actual': response[:100] + "..." if len(response) > 100 else response
            })
        
        # Check must_not_contain
        for forbidden in message.must_not_contain:
            assertions.append({
                'description': f'Response does not contain "{forbidden}"',
                'passed': forbidden.lower() not in response.lower(),
                'expected': f'not containing "{forbidden}"',
                'actual': response[:100] + "..." if len(response) > 100 else response
            })
        
        # Check expected tools
        for tool in message.expected_tools:
            assertions.append({
                'description': f'Called tool "{tool}"',
                'passed': tool in tools_called,
                'expected': tool,
                'actual': str(tools_called)
            })
        
        return assertions
    
    async def _get_gpt_response(self, scenario: TestScenario, message_idx: int, message: Message) -> Tuple[str, List[str]]:
        """Get GPT response for a message in a scenario"""
        # Initialize GPT client if needed
        if self.gpt_client is None:
            self.gpt_client = await self._initialize_gpt_client()
        
        # Build context from scenario
        context = self._build_context(scenario, message_idx)
        
        # Call GPT
        response, tools_called = await self._call_gpt_with_context(context, message.text)
        
        return response, tools_called
    
    async def _initialize_gpt_client(self):
        """Initialize minimal GPT client for testing"""
        # For now, return a mock - will implement real GPT next
        return {"initialized": True}
    
    def _build_context(self, scenario: TestScenario, message_idx: int) -> Dict[str, Any]:
        """Build context for GPT from scenario state"""
        # Get trades up to this point
        current_time = scenario.messages[message_idx].timestamp
        relevant_trades = [t for t in scenario.trades if t.timestamp <= current_time]
        
        # Build context similar to what the bot would have
        context = {
            'user_profile': scenario.user_profile,
            'trades': relevant_trades,
            'initial_bankroll': scenario.initial_bankroll,
            'current_bankroll': self._calculate_current_bankroll(scenario, current_time),
            'message_history': scenario.messages[:message_idx]
        }
        
        return context
    
    def _calculate_current_bankroll(self, scenario: TestScenario, up_to_time: datetime) -> float:
        """Calculate bankroll at a point in time"""
        bankroll = scenario.initial_bankroll
        for trade in scenario.trades:
            if trade.timestamp <= up_to_time:
                bankroll = trade.bankroll_after
        return bankroll
    
    async def _call_gpt_with_context(self, context: Dict[str, Any], message: str) -> Tuple[str, List[str]]:
        """Call GPT with context - minimal implementation for now"""
        try:
            from test_gpt_integration import test_gpt
            return await test_gpt.get_response(context, message)
        except Exception as e:
            print(f"{RED}Error calling GPT: {e}{RESET}")
            return "error calling GPT", []
    
    async def run_all_scenarios(self, scenarios: List[TestScenario]) -> None:
        """Run all test scenarios and display results"""
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}Bot Testing Framework - Running {len(scenarios)} scenarios{RESET}")
        print(f"{BLUE}{'='*60}{RESET}")
        
        if self.quick_mode:
            print(f"{YELLOW}Quick mode: Running only core scenarios{RESET}")
            scenarios = scenarios[:5]  # Run only first 5 in quick mode
        
        # Run each scenario
        for scenario in scenarios:
            result = await self.run_scenario(scenario)
            self.results.append(result)
        
        # Display summary
        self._display_summary()
        
        # Display detailed failures
        self._display_failures()
    
    def _display_summary(self):
        """Display test summary with emoji indicators"""
        print(f"\n{BLUE}{'='*60}{RESET}")
        print(f"{BLUE}SUMMARY:{RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")
        
        total_time = sum(r.execution_time for r in self.results)
        
        for result in self.results:
            status = f"{GREEN}✅{RESET}" if result.passed else f"{RED}❌{RESET}"
            assertion_summary = f"({result.assertions_passed}/{result.assertions_total} assertions)"
            print(f"{status} {result.scenario_name} {assertion_summary}")
        
        # Overall stats
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        print(f"\n{BLUE}Overall: {passed}/{total} scenarios passed{RESET}")
        print(f"{BLUE}Total execution time: {total_time:.1f} seconds{RESET}")
        
        if self.use_cache:
            print(f"{YELLOW}Note: Using cached responses. Run with --no-cache to test fresh{RESET}")
    
    def _display_failures(self):
        """Display detailed failure information"""
        failed_results = [r for r in self.results if not r.passed]
        
        if not failed_results:
            return
        
        print(f"\n{RED}{'='*60}{RESET}")
        print(f"{RED}FAILURES:{RESET}")
        print(f"{RED}{'='*60}{RESET}\n")
        
        for result in failed_results:
            print(f"{RED}FAILED: {result.scenario_name}{RESET}")
            
            for failure in result.failures:
                print(f"\n  When user said: \"{failure['message']}\"")
                print(f"  > {failure['assertion']}")
                print(f"  > Expected: {failure['expected']}")
                print(f"  > Actual: {failure['actual']}")
                print(f"  > Full conversation: [run with --verbose to see]")


def load_test_scenarios() -> List[TestScenario]:
    """Load all test scenarios"""
    try:
        from test_scenarios.all_scenarios import all_scenarios
        return all_scenarios
    except ImportError:
        # Fallback to simple test if scenarios not found
        print(f"{YELLOW}Warning: Could not load test scenarios, using simple test{RESET}")
        default_profile = UserProfile()
        
        hello_world = TestScenario(
            name="Hello World Test",
            description="Basic test to verify framework is working",
            user_profile=default_profile,
            messages=[
                Message(
                    text="yo",
                    timestamp=datetime.now(),
                    must_contain=["sol"],
                    must_not_contain=["error", "undefined"],
                    context_note="User greeting should get bankroll response"
                )
            ]
        )
        
        return [hello_world]


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Run bot test scenarios')
    parser.add_argument('--no-cache', action='store_true', 
                       help='Disable response caching (slower but tests current prompt)')
    parser.add_argument('--quick', action='store_true',
                       help='Run only core scenarios (first 5)')
    parser.add_argument('--verbose', action='store_true',
                       help='Show full conversation details')
    
    args = parser.parse_args()
    
    # Create tester
    tester = ScenarioTester(
        use_cache=not args.no_cache,
        quick_mode=args.quick
    )
    
    # Load scenarios
    scenarios = load_test_scenarios()
    
    # Run tests
    await tester.run_all_scenarios(scenarios)
    
    # Exit with error code if any tests failed
    if any(not r.passed for r in tester.results):
        exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 