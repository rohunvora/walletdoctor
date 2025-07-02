#!/usr/bin/env python3
"""
Load Testing Script for Memory Guardrail - WAL-609
Validates acceptance criteria: 5 req/s for 10 min keeps RSS steady (< +50 MB)

Usage:
    python scripts/test_memory_guardrail_load.py [--host localhost] [--port 5000]
"""

import argparse
import asyncio
import json
import time
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

try:
    import aiohttp
    import requests
except ImportError:
    print("Please install required packages: pip install aiohttp requests")
    sys.exit(1)

logger = logging.getLogger(__name__)


class LoadTestRunner:
    """
    Load test runner for memory guardrail validation
    
    Tests WAL-609 acceptance criteria:
    - 5 requests/second for 10 minutes
    - Memory growth must be < +50MB
    """
    
    def __init__(self, host: str = "localhost", port: int = 5000):
        self.base_url = f"http://{host}:{port}"
        self.session: aiohttp.ClientSession = None
        self.results: List[Dict[str, Any]] = []
        
        # Test configuration
        self.test_duration_min = 10
        self.requests_per_second = 5
        self.total_requests = self.test_duration_min * 60 * self.requests_per_second
        
        logger.info(f"Load test configuration:")
        logger.info(f"  Target: {self.base_url}")
        logger.info(f"  Duration: {self.test_duration_min} minutes")
        logger.info(f"  Rate: {self.requests_per_second} req/s")
        logger.info(f"  Total requests: {self.total_requests}")
    
    async def check_api_health(self) -> bool:
        """Check if API is responding"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/health") as response:
                    if response.status == 200:
                        logger.info("API health check passed")
                        return True
                    else:
                        logger.error(f"API health check failed: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"API health check error: {e}")
            return False
    
    def get_baseline(self) -> Dict[str, Any]:
        """Get initial baseline before load test"""
        try:
            response = requests.get(f"{self.base_url}/self-check/baseline", timeout=10)
            if response.status_code == 202:
                # Baseline not yet established, need warm-up
                logger.info("Baseline not established, performing warm-up...")
                self.warmup_requests()
                time.sleep(2)
                response = requests.get(f"{self.base_url}/self-check/baseline", timeout=10)
            
            if response.status_code == 200:
                baseline = response.json()
                logger.info(f"Baseline established: {baseline['baseline_rss_mb']:.1f}MB")
                return baseline
            else:
                logger.error(f"Failed to get baseline: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"Error getting baseline: {e}")
            return {}
    
    def warmup_requests(self):
        """Send warm-up requests to establish baseline"""
        logger.info("Sending warm-up requests...")
        for i in range(15):  # Send enough requests to establish baseline
            try:
                response = requests.get(f"{self.base_url}/self-check", timeout=5)
                if i % 5 == 0:
                    logger.info(f"Warm-up progress: {i+1}/15")
                time.sleep(0.2)
            except Exception as e:
                logger.warning(f"Warm-up request {i+1} failed: {e}")
    
    async def send_request(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Send single request and measure response"""
        start_time = time.time()
        
        try:
            async with session.get(f"{self.base_url}/self-check") as response:
                response_time = (time.time() - start_time) * 1000
                status = response.status
                
                if status == 200:
                    data = await response.json()
                    return {
                        "timestamp": datetime.utcnow().isoformat(),
                        "status": status,
                        "response_time_ms": response_time,
                        "rss_mb": data.get("current_memory", {}).get("rss_mb", 0),
                        "cache_entries": data.get("current_memory", {}).get("cache_entries", 0),
                        "memory_status": data.get("status", "unknown")
                    }
                else:
                    return {
                        "timestamp": datetime.utcnow().isoformat(),
                        "status": status,
                        "response_time_ms": response_time,
                        "error": f"HTTP {status}"
                    }
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "status": 0,
                "response_time_ms": response_time,
                "error": str(e)
            }
    
    async def run_load_test(self) -> Dict[str, Any]:
        """Run the main load test"""
        logger.info("Starting load test...")
        
        start_time = time.time()
        request_interval = 1.0 / self.requests_per_second  # 0.2s for 5 req/s
        
        async with aiohttp.ClientSession() as session:
            self.session = session
            
            for i in range(self.total_requests):
                # Send request
                result = await self.send_request(session)
                self.results.append(result)
                
                # Progress logging
                if (i + 1) % 50 == 0:
                    elapsed_min = (time.time() - start_time) / 60
                    progress_pct = ((i + 1) / self.total_requests) * 100
                    logger.info(f"Progress: {progress_pct:.1f}% ({i+1}/{self.total_requests}) - {elapsed_min:.1f} min")
                
                # Rate limiting
                if i < self.total_requests - 1:  # Don't sleep after last request
                    await asyncio.sleep(request_interval)
        
        total_time = time.time() - start_time
        logger.info(f"Load test completed in {total_time:.1f} seconds")
        
        return self.analyze_results()
    
    def analyze_results(self) -> Dict[str, Any]:
        """Analyze load test results"""
        if not self.results:
            return {"error": "No results to analyze"}
        
        # Filter successful requests
        successful = [r for r in self.results if r.get("status") == 200]
        
        if not successful:
            return {"error": "No successful requests"}
        
        # Memory analysis
        rss_values = [r["rss_mb"] for r in successful if "rss_mb" in r]
        cache_values = [r["cache_entries"] for r in successful if "cache_entries" in r]
        response_times = [r["response_time_ms"] for r in successful]
        
        # Calculate memory growth
        initial_rss = rss_values[0] if rss_values else 0
        final_rss = rss_values[-1] if rss_values else 0
        max_rss = max(rss_values) if rss_values else 0
        min_rss = min(rss_values) if rss_values else 0
        
        memory_growth = final_rss - initial_rss
        memory_range = max_rss - min_rss
        
        # Performance analysis
        avg_response_time = sum(response_times) / len(response_times)
        p95_response_time = sorted(response_times)[int(len(response_times) * 0.95)]
        
        # Acceptance criteria validation
        memory_growth_pass = memory_growth <= 50.0  # +50MB limit
        performance_pass = p95_response_time <= 200.0  # 200ms limit
        
        overall_pass = memory_growth_pass and performance_pass
        
        analysis = {
            "test_summary": {
                "total_requests": len(self.results),
                "successful_requests": len(successful),
                "success_rate": len(successful) / len(self.results) * 100,
                "test_duration_min": self.test_duration_min,
                "target_rps": self.requests_per_second
            },
            "memory_analysis": {
                "initial_rss_mb": initial_rss,
                "final_rss_mb": final_rss,
                "max_rss_mb": max_rss,
                "min_rss_mb": min_rss,
                "memory_growth_mb": memory_growth,
                "memory_range_mb": memory_range,
                "max_cache_entries": max(cache_values) if cache_values else 0,
                "min_cache_entries": min(cache_values) if cache_values else 0
            },
            "performance_analysis": {
                "avg_response_time_ms": avg_response_time,
                "p95_response_time_ms": p95_response_time,
                "min_response_time_ms": min(response_times),
                "max_response_time_ms": max(response_times)
            },
            "acceptance_criteria": {
                "memory_growth_limit_mb": 50,
                "memory_growth_pass": memory_growth_pass,
                "performance_limit_ms": 200,
                "performance_pass": performance_pass,
                "overall_pass": overall_pass
            },
            "verdict": "PASS" if overall_pass else "FAIL",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return analysis
    
    def generate_report(self, analysis: Dict[str, Any], baseline: Dict[str, Any]) -> str:
        """Generate human-readable test report"""
        verdict = analysis.get("verdict", "UNKNOWN")
        
        report = f"""
WAL-609 Memory Guardrail Load Test Report
========================================

Test Configuration:
  Duration: {analysis['test_summary']['test_duration_min']} minutes
  Target Rate: {analysis['test_summary']['target_rps']} req/s
  Total Requests: {analysis['test_summary']['total_requests']}
  Success Rate: {analysis['test_summary']['success_rate']:.1f}%

Memory Results:
  Baseline RSS: {baseline.get('baseline_rss_mb', 'N/A')} MB
  Initial RSS: {analysis['memory_analysis']['initial_rss_mb']:.1f} MB
  Final RSS: {analysis['memory_analysis']['final_rss_mb']:.1f} MB
  Memory Growth: {analysis['memory_analysis']['memory_growth_mb']:.1f} MB
  Memory Range: {analysis['memory_analysis']['memory_range_mb']:.1f} MB

Performance Results:
  Average Response Time: {analysis['performance_analysis']['avg_response_time_ms']:.1f} ms
  P95 Response Time: {analysis['performance_analysis']['p95_response_time_ms']:.1f} ms
  Min/Max Response Time: {analysis['performance_analysis']['min_response_time_ms']:.1f}/{analysis['performance_analysis']['max_response_time_ms']:.1f} ms

Acceptance Criteria:
  Memory Growth < 50MB: {"✓ PASS" if analysis['acceptance_criteria']['memory_growth_pass'] else "✗ FAIL"} ({analysis['memory_analysis']['memory_growth_mb']:.1f}MB)
  P95 Latency < 200ms: {"✓ PASS" if analysis['acceptance_criteria']['performance_pass'] else "✗ FAIL"} ({analysis['performance_analysis']['p95_response_time_ms']:.1f}ms)

OVERALL RESULT: {verdict}
{"=" * 40}
"""
        return report


async def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Memory Guardrail Load Test - WAL-609")
    parser.add_argument("--host", default="localhost", help="API host")
    parser.add_argument("--port", type=int, default=5000, help="API port")
    parser.add_argument("--output", help="Output file for detailed results (JSON)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Create test runner
    runner = LoadTestRunner(host=args.host, port=args.port)
    
    # Check API health
    if not await runner.check_api_health():
        logger.error("API health check failed. Please ensure the API is running.")
        sys.exit(1)
    
    # Get baseline
    baseline = runner.get_baseline()
    if not baseline:
        logger.error("Failed to establish baseline. Cannot proceed with load test.")
        sys.exit(1)
    
    # Run load test
    try:
        analysis = await runner.run_load_test()
        
        # Generate report
        report = runner.generate_report(analysis, baseline)
        print(report)
        
        # Save detailed results if requested
        if args.output:
            detailed_results = {
                "baseline": baseline,
                "analysis": analysis,
                "raw_results": runner.results
            }
            with open(args.output, 'w') as f:
                json.dump(detailed_results, f, indent=2)
            logger.info(f"Detailed results saved to {args.output}")
        
        # Exit with appropriate code
        if analysis.get("verdict") == "PASS":
            logger.info("Load test PASSED all acceptance criteria")
            sys.exit(0)
        else:
            logger.error("Load test FAILED acceptance criteria")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Load test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Load test failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 