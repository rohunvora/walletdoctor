#!/usr/bin/env python3
"""
WAL-610 Production Readiness Validation Script

Comprehensive performance and accuracy testing for P6 post-beta hardening.
This script validates production readiness across multiple dimensions:
- Load testing with large wallets
- Accuracy validation on real wallets  
- Memory profiling under stress
- Performance regression testing
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.lib.performance_validator import (
    PerformanceValidator,
    run_quick_validation,
    validate_production_readiness,
    PERFORMANCE_THRESHOLDS,
    TEST_WALLETS
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('wal610_validation.log')
    ]
)

logger = logging.getLogger(__name__)


def print_banner():
    """Print validation banner"""
    print("=" * 80)
    print("🚀 WAL-610: Production Readiness Validation")
    print("=" * 80)
    print("📊 Testing P6 post-beta hardening components:")
    print("   - Position Cache Eviction & Refresh (WAL-607)")
    print("   - Metrics & Dashboard (WAL-608)")
    print("   - Memory-Leak Guardrail (WAL-609)")
    print("=" * 80)
    print()


def print_thresholds():
    """Print performance thresholds"""
    print("🎯 Performance Thresholds:")
    print("-" * 40)
    for key, value in PERFORMANCE_THRESHOLDS.items():
        unit = ""
        if "ms" in key:
            unit = "ms"
        elif "mb" in key:
            unit = "MB"
        elif "sec" in key:
            unit = "s"
        elif "pct" in key or "rate" in key:
            unit = "%"
        
        print(f"   {key:<25}: {value:>8} {unit}")
    print()


def print_test_wallets():
    """Print test wallet configuration"""
    print("💼 Test Wallet Configuration:")
    print("-" * 40)
    for category, wallets in TEST_WALLETS.items():
        print(f"   {category.capitalize()}:")
        for wallet in wallets:
            print(f"     - {wallet}")
    print()


def format_duration(ms: float) -> str:
    """Format duration in human readable format"""
    if ms < 1000:
        return f"{ms:.1f}ms"
    elif ms < 60000:
        return f"{ms/1000:.2f}s"
    else:
        return f"{ms/60000:.1f}m"


def format_memory(mb: float) -> str:
    """Format memory in human readable format"""
    if mb < 1024:
        return f"{mb:.1f}MB"
    else:
        return f"{mb/1024:.2f}GB"


def print_performance_results(results: list):
    """Print performance test results in a formatted table"""
    if not results:
        print("   No performance results to display")
        return
    
    print("📈 Performance Test Results:")
    print("-" * 100)
    print(f"{'Test Type':<20} {'Wallet':<20} {'Duration':<12} {'Memory':<12} {'Trades':<8} {'Status':<8}")
    print("-" * 100)
    
    for result in results:
        wallet_short = result['wallet'][:18] + "..." if len(result['wallet']) > 20 else result['wallet']
        duration = format_duration(result['duration_ms'])
        memory = format_memory(result['memory_peak_mb'])
        status = "✅ PASS" if result['passed'] else "❌ FAIL"
        
        print(f"{result['test_type']:<20} {wallet_short:<20} {duration:<12} {memory:<12} {result['trade_count']:<8} {status:<8}")
        
        if result['errors']:
            for error in result['errors']:
                print(f"     🔴 {error}")
    
    print()


def print_accuracy_results(results: list):
    """Print accuracy validation results"""
    if not results:
        print("   No accuracy results to display")
        return
    
    print("🎯 Accuracy Validation Results:")
    print("-" * 100)
    print(f"{'Wallet':<20} {'Trades':<8} {'Price Cov':<10} {'Confidence':<12} {'Score':<8} {'Status':<8}")
    print("-" * 100)
    
    for result in results:
        wallet_short = result['wallet'][:18] + "..." if len(result['wallet']) > 20 else result['wallet']
        price_cov = f"{result['price_coverage_pct']:.1f}%"
        confidence = f"{result['confidence_high_pct']:.1f}%"
        score = f"{result['accuracy_score']:.2f}"
        status = "✅ PASS" if result['passed'] else "❌ FAIL"
        
        print(f"{wallet_short:<20} {result['total_trades']:<8} {price_cov:<10} {confidence:<12} {score:<8} {status:<8}")
        
        if result['validation_errors']:
            for error in result['validation_errors']:
                print(f"     🔴 {error}")
    
    print()


def print_summary(summary: dict):
    """Print validation summary"""
    print("📋 Validation Summary:")
    print("-" * 50)
    print(f"   Performance Tests: {summary['performance_pass_rate']:.1f}% pass rate")
    print(f"   Accuracy Tests:    {summary['accuracy_pass_rate']:.1f}% pass rate")
    print(f"   Total Tests:       {summary['total_passed']}/{summary['total_tests']} passed")
    print(f"   Total Errors:      {summary['total_errors']}")
    
    if 'performance_stats' in summary and summary['performance_stats']:
        stats = summary['performance_stats']
        print(f"\n   Performance Statistics:")
        if 'avg_duration_ms' in stats:
            print(f"     Average Duration: {format_duration(stats['avg_duration_ms'])}")
        if 'max_memory_growth_mb' in stats:
            print(f"     Max Memory Growth: {format_memory(stats['max_memory_growth_mb'])}")
    
    overall_status = "✅ PASSED" if summary['performance_pass'] and summary['accuracy_pass'] else "❌ FAILED"
    print(f"\n   Overall Status: {overall_status}")
    print()


def save_results(results: dict, filename: Optional[str] = None):
    """Save validation results to JSON file"""
    if filename is None:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"wal610_validation_results_{timestamp}.json"
    
    # Convert any non-serializable types
    def convert_for_json(obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return str(obj)
    
    # Process results for JSON serialization
    json_results = json.loads(json.dumps(results, default=convert_for_json))
    
    with open(filename, 'w') as f:
        json.dump(json_results, f, indent=2)
    
    print(f"💾 Results saved to: {filename}")
    return filename


async def run_quick_test():
    """Run quick validation test"""
    print("🏃 Running Quick Validation...")
    print("This is a subset of tests for fast feedback\n")
    
    try:
        results = await run_quick_validation()
        
        print_performance_results(results['results'])
        
        status = "✅ PASSED" if results['passed'] else "❌ FAILED"
        print(f"Quick Validation Status: {status}")
        
        return results
        
    except Exception as e:
        logger.error(f"Quick validation failed: {e}")
        print(f"❌ Quick validation failed: {e}")
        return {"passed": False, "error": str(e)}


async def run_comprehensive_test():
    """Run comprehensive validation test"""
    print("🔍 Running Comprehensive Validation...")
    print("This includes all test categories: load, accuracy, memory, regression\n")
    
    try:
        validator = PerformanceValidator()
        results = await validator.run_comprehensive_validation()
        
        # Print detailed results
        print_performance_results([
            {
                "test_type": r.test_type,
                "wallet": r.wallet,
                "duration_ms": r.duration_ms,
                "memory_peak_mb": r.memory_peak_mb,
                "trade_count": r.trade_count,
                "passed": r.passed,
                "errors": r.errors
            }
            for r in validator.results
        ])
        
        print_accuracy_results([
            {
                "wallet": r.wallet,
                "total_trades": r.total_trades,
                "price_coverage_pct": r.price_coverage_pct,
                "confidence_high_pct": r.confidence_high_pct,
                "accuracy_score": r.accuracy_score,
                "passed": r.passed,
                "validation_errors": r.validation_errors
            }
            for r in validator.accuracy_results
        ])
        
        print_summary(results['summary'])
        
        # Save results
        save_results(results)
        
        return results
        
    except Exception as e:
        logger.error(f"Comprehensive validation failed: {e}")
        print(f"❌ Comprehensive validation failed: {e}")
        return {"overall_pass": False, "error": str(e)}


async def check_production_readiness():
    """Check if system is ready for production"""
    print("🚦 Checking Production Readiness...")
    print("Running complete validation to determine if system is ready for production deployment\n")
    
    try:
        is_ready = await validate_production_readiness()
        
        if is_ready:
            print("🟢 PRODUCTION READY")
            print("   All validation tests passed. System is ready for production deployment.")
        else:
            print("🔴 NOT PRODUCTION READY")
            print("   Some validation tests failed. Review results before deployment.")
        
        return is_ready
        
    except Exception as e:
        logger.error(f"Production readiness check failed: {e}")
        print(f"❌ Production readiness check failed: {e}")
        return False


def check_environment():
    """Check if required environment variables are set"""
    print("🔧 Environment Check:")
    print("-" * 30)
    
    required_vars = ["HELIUS_KEY", "BIRDEYE_API_KEY"]
    optional_vars = ["REDIS_URL", "SECRET_KEY"]
    
    all_required_set = True
    
    for var in required_vars:
        if os.getenv(var):
            print(f"   ✅ {var}: Set")
        else:
            print(f"   ❌ {var}: Missing (required)")
            all_required_set = False
    
    for var in optional_vars:
        if os.getenv(var):
            print(f"   ✅ {var}: Set")
        else:
            print(f"   ⚠️  {var}: Missing (optional)")
    
    print()
    
    if not all_required_set:
        print("❌ Missing required environment variables. Some tests may fail.")
        return False
    
    print("✅ Environment check passed.")
    return True


async def main():
    """Main validation script"""
    print_banner()
    
    # Check environment
    env_ok = check_environment()
    
    # Print configuration
    print_thresholds()
    print_test_wallets()
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="WAL-610 Production Readiness Validation")
    parser.add_argument("--quick", action="store_true", help="Run quick validation only")
    parser.add_argument("--comprehensive", action="store_true", help="Run comprehensive validation")
    parser.add_argument("--production-check", action="store_true", help="Check production readiness")
    parser.add_argument("--all", action="store_true", help="Run all validation types")
    
    args = parser.parse_args()
    
    # Default to all tests if no specific test is requested
    if not any([args.quick, args.comprehensive, args.production_check]):
        args.all = True
    
    results = {}
    
    try:
        if args.quick or args.all:
            results['quick'] = await run_quick_test()
            print()
        
        if args.comprehensive or args.all:
            results['comprehensive'] = await run_comprehensive_test()
            print()
        
        if args.production_check or args.all:
            results['production_ready'] = await check_production_readiness()
            print()
        
        # Final summary
        print("🏁 Final Summary:")
        print("-" * 40)
        
        if 'quick' in results:
            status = "✅ PASS" if results['quick'].get('passed', False) else "❌ FAIL"
            print(f"   Quick Validation:        {status}")
        
        if 'comprehensive' in results:
            status = "✅ PASS" if results['comprehensive'].get('overall_pass', False) else "❌ FAIL"
            print(f"   Comprehensive Validation: {status}")
        
        if 'production_ready' in results:
            status = "✅ READY" if results['production_ready'] else "❌ NOT READY"
            print(f"   Production Readiness:     {status}")
        
        print()
        
        # Overall exit code
        if all(results.values()):
            print("🎉 All validations passed! WAL-610 is complete.")
            return 0
        else:
            print("⚠️  Some validations failed. Review results above.")
            return 1
            
    except KeyboardInterrupt:
        print("\n❌ Validation interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Validation script failed: {e}")
        print(f"\n❌ Validation script failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main()) 