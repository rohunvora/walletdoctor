#!/usr/bin/env python3
"""
SSE Railway Performance Test (Python)
GPT-005: Test SSE streaming through Railway proxy with precise timing
"""

import asyncio
import aiohttp
import time
import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import argparse
from dataclasses import dataclass, asdict

@dataclass
class SSEEvent:
    """Represents a single SSE event with timing"""
    event_type: str
    data: Dict
    arrival_time: float
    elapsed_time: float
    sequence: int

@dataclass
class TestResult:
    """Results of a single SSE test"""
    test_name: str
    wallet: str
    total_events: int
    on_time_events: int
    success_rate: float
    first_event_time: float
    last_event_time: float
    connection_time: float
    events: List[SSEEvent]
    passed: bool
    error: Optional[str] = None

class SSEPerformanceTester:
    """Test SSE performance through Railway proxy"""
    
    def __init__(self, 
                 railway_url: str,
                 api_key: str,
                 timeout_threshold: float = 25.0,
                 success_threshold: float = 90.0):
        self.railway_url = railway_url.rstrip('/')
        self.api_key = api_key
        self.timeout_threshold = timeout_threshold
        self.success_threshold = success_threshold
        
    async def test_connection_speed(self) -> Tuple[bool, float]:
        """Test basic connection speed to Railway"""
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.railway_url}/health",
                    headers={"X-API-Key": self.api_key}
                ) as response:
                    connection_time = time.time() - start_time
                    success = response.status == 200
                    return success, connection_time
        except Exception as e:
            return False, time.time() - start_time
    
    async def test_sse_stream(self, wallet: str, test_name: str) -> TestResult:
        """Test SSE streaming for a specific wallet"""
        
        events = []
        start_time = time.time()
        connection_time = 0
        error = None
        sequence = 0
        
        try:
            # Set up session with proper SSE headers
            timeout = aiohttp.ClientTimeout(total=90)  # 90s max for full test
            headers = {
                "Accept": "text/event-stream",
                "X-API-Key": self.api_key,
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                url = f"{self.railway_url}/v4/wallet/{wallet}/stream"
                
                print(f"  🔗 Connecting to: {url}")
                
                async with session.get(url, headers=headers) as response:
                    connection_time = time.time() - start_time
                    print(f"  ⚡ Connected in {connection_time:.3f}s (HTTP {response.status})")
                    
                    if response.status != 200:
                        error = f"HTTP {response.status}: {await response.text()}"
                        print(f"  ❌ Connection failed: {error}")
                        return TestResult(
                            test_name=test_name,
                            wallet=wallet,
                            total_events=0,
                            on_time_events=0,
                            success_rate=0.0,
                            first_event_time=0.0,
                            last_event_time=0.0,
                            connection_time=connection_time,
                            events=[],
                            passed=False,
                            error=error
                        )
                    
                    # Read SSE stream
                    event_buffer = ""
                    max_events = 100  # Safety limit
                    
                    async for chunk in response.content.iter_any():
                        if chunk:
                            current_time = time.time()
                            elapsed = current_time - start_time
                            
                            # Decode chunk
                            data = chunk.decode('utf-8', errors='ignore')
                            event_buffer += data
                            
                            # Process complete events (separated by \n\n)
                            while '\n\n' in event_buffer:
                                event_str, event_buffer = event_buffer.split('\n\n', 1)
                                
                                if event_str.strip():
                                    # Parse SSE event
                                    lines = event_str.strip().split('\n')
                                    event_type = None
                                    event_data = None
                                    
                                    for line in lines:
                                        if line.startswith('event:'):
                                            event_type = line[6:].strip()
                                        elif line.startswith('data:'):
                                            try:
                                                event_data = json.loads(line[5:].strip())
                                            except json.JSONDecodeError:
                                                event_data = {"raw": line[5:].strip()}
                                    
                                    if event_type and event_data:
                                        sequence += 1
                                        
                                        # Create event record
                                        sse_event = SSEEvent(
                                            event_type=event_type,
                                            data=event_data,
                                            arrival_time=current_time,
                                            elapsed_time=elapsed,
                                            sequence=sequence
                                        )
                                        events.append(sse_event)
                                        
                                        print(f"    #{sequence:2d} {event_type:10s} at {elapsed:6.3f}s")
                                        
                                        # Stop conditions
                                        if event_type in ['complete', 'error']:
                                            print(f"  🏁 Stream ended with '{event_type}' event")
                                            break
                                        
                                        if len(events) >= max_events:
                                            print(f"  ⚠️ Stopping at {max_events} events for safety")
                                            break
                            
                            # Break outer loop if we hit stop conditions
                            if events and events[-1].event_type in ['complete', 'error']:
                                break
                            if len(events) >= max_events:
                                break
                                
        except asyncio.TimeoutError:
            error = "Connection timeout"
            print(f"  ❌ Timeout after {time.time() - start_time:.1f}s")
        except Exception as e:
            error = str(e)
            print(f"  ❌ Error: {error}")
        
        # Analyze results
        total_events = len(events)
        on_time_events = sum(1 for e in events if e.elapsed_time <= self.timeout_threshold)
        success_rate = (on_time_events / total_events * 100) if total_events > 0 else 0.0
        
        first_event_time = events[0].elapsed_time if events else 0.0
        last_event_time = events[-1].elapsed_time if events else 0.0
        
        passed = success_rate >= self.success_threshold and total_events > 0
        
        print(f"  📊 Results: {on_time_events}/{total_events} on-time ({success_rate:.1f}%)")
        
        return TestResult(
            test_name=test_name,
            wallet=wallet,
            total_events=total_events,
            on_time_events=on_time_events,
            success_rate=success_rate,
            first_event_time=first_event_time,
            last_event_time=last_event_time,
            connection_time=connection_time,
            events=events,
            passed=passed,
            error=error
        )
    
    async def run_concurrent_test(self, wallet: str, concurrent_count: int = 3) -> List[TestResult]:
        """Run multiple concurrent SSE tests"""
        print(f"🔄 Running {concurrent_count} concurrent streams...")
        
        tasks = []
        for i in range(concurrent_count):
            task = self.test_sse_stream(wallet, f"concurrent_{i+1}")
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        passed_count = sum(1 for r in results if r.passed)
        print(f"  ✅ {passed_count}/{concurrent_count} concurrent streams passed")
        
        return results
    
    async def run_full_test_suite(self) -> Dict:
        """Run complete test suite"""
        print("🚀 GPT-005: SSE Railway Streaming Test (Python)")
        print("=" * 50)
        print(f"Railway URL: {self.railway_url}")
        print(f"Timeout Threshold: {self.timeout_threshold}s")
        print(f"Success Threshold: {self.success_threshold}%")
        print()
        
        test_start = time.time()
        all_results = []
        
        # Phase 1: Connection speed test
        print("🔗 Phase 1: Railway Connection Test")
        print("-" * 35)
        
        conn_success, conn_time = await self.test_connection_speed()
        if not conn_success:
            print(f"❌ Railway connection failed ({conn_time:.3f}s)")
            return {
                "success": False,
                "error": "Railway connection failed",
                "recommendation": "PUNT to WebSocket (PAG-002)"
            }
        
        print(f"✅ Railway accessible in {conn_time:.3f}s")
        print()
        
        # Phase 2: Individual SSE tests
        print("📡 Phase 2: SSE Performance Tests")
        print("-" * 35)
        
        test_wallets = [
            ("8kGfFmGfFi8tBvbX6yy8Z4pvFUgbGCnBCbqKnUhcKh5h", "small_wallet"),
            ("34zYDgjy5Bd3EhwXGgN9EacjhGJMTBrKFoJg8vJx3C5n", "medium_wallet"),
        ]
        
        for wallet, test_name in test_wallets:
            print(f"🧪 Testing {test_name}...")
            result = await self.test_sse_stream(wallet, test_name)
            all_results.append(result)
            
            if result.passed:
                print(f"  ✅ PASS: {result.success_rate:.1f}% >= {self.success_threshold}%")
            else:
                print(f"  ❌ FAIL: {result.success_rate:.1f}% < {self.success_threshold}%")
                if result.error:
                    print(f"      Error: {result.error}")
            print()
        
        # Phase 3: Concurrent test
        print("⚡ Phase 3: Concurrent Streams Test")
        print("-" * 36)
        
        concurrent_results = await self.run_concurrent_test("8kGfFmGfFi8tBvbX6yy8Z4pvFUgbGCnBCbqKnUhcKh5h")
        all_results.extend(concurrent_results)
        print()
        
        # Final analysis
        print("📊 Final Analysis")
        print("-" * 18)
        
        passed_tests = sum(1 for r in all_results if r.passed)
        total_tests = len(all_results)
        overall_success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0.0
        
        print(f"Tests passed: {passed_tests}/{total_tests}")
        print(f"Overall success rate: {overall_success_rate:.1f}%")
        print(f"Test duration: {time.time() - test_start:.1f}s")
        
        # Determine recommendation
        exit_criteria_met = overall_success_rate >= 90.0
        recommendation = "PROCEED with SSE" if exit_criteria_met else "PUNT to WebSocket (PAG-002)"
        
        print()
        if exit_criteria_met:
            print("🎉 SUCCESS: SSE streaming viable through Railway")
            print("✅ RECOMMENDATION: Proceed with SSE implementation")
            print()
            print("  • >90% events arriving <25s ✅")
            print("  • Railway proxy compatible ✅")
            print("  • Concurrent connections working ✅")
        else:
            print("❌ FAILURE: SSE streaming not reliable through Railway")
            print("📋 RECOMMENDATION: Punt to WebSocket (PAG-002)")
            print()
            print("  • Performance below 90% threshold")
            print("  • Railway 30s timeout risk")
            print("  • Consider alternative: WebSocket + streaming")
        
        # Create detailed report
        report = {
            "test_timestamp": datetime.now().isoformat(),
            "railway_url": self.railway_url,
            "timeout_threshold": self.timeout_threshold,
            "success_threshold": self.success_threshold,
            "connection_time": conn_time,
            "tests_passed": passed_tests,
            "total_tests": total_tests,
            "overall_success_rate": overall_success_rate,
            "exit_criteria_met": exit_criteria_met,
            "recommendation": recommendation,
            "test_results": [asdict(r) for r in all_results],
            "summary": {
                "individual_tests": passed_tests - len(concurrent_results),
                "concurrent_tests": sum(1 for r in concurrent_results if r.passed),
                "total_events": sum(r.total_events for r in all_results),
                "avg_first_event_time": sum(r.first_event_time for r in all_results if r.first_event_time > 0) / max(1, sum(1 for r in all_results if r.first_event_time > 0))
            }
        }
        
        return report

async def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description="Test SSE streaming through Railway proxy")
    parser.add_argument("--url", default="https://walletdoctor-production.up.railway.app", 
                       help="Railway URL")
    parser.add_argument("--api-key", default="wd_test_key_1234567890123456789012345",
                       help="API key for authentication")
    parser.add_argument("--timeout", type=float, default=25.0,
                       help="Timeout threshold in seconds")
    parser.add_argument("--success-rate", type=float, default=90.0,
                       help="Required success rate percentage")
    parser.add_argument("--output", default="tmp/sse_python_test.json",
                       help="Output file for results")
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    # Run tests
    tester = SSEPerformanceTester(
        railway_url=args.url,
        api_key=args.api_key,
        timeout_threshold=args.timeout,
        success_threshold=args.success_rate
    )
    
    results = await tester.run_full_test_suite()
    
    # Save results
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: {args.output}")
    
    # Exit with appropriate code
    exit_code = 0 if results.get("exit_criteria_met", False) else 1
    sys.exit(exit_code)

if __name__ == "__main__":
    asyncio.run(main()) 