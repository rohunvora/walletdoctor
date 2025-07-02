#!/usr/bin/env python3
"""
Performance Validation Framework
WAL-610: Comprehensive testing for production readiness

Validates:
- Load testing with large wallets (10k+ trades)
- Accuracy validation on real wallets
- Memory profiling under load
- Performance regression testing
"""

import asyncio
import time
import psutil
import logging
import gc
import tracemalloc
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import json
import os

# Import core components for testing
from src.lib.blockchain_fetcher_v3_fast import BlockchainFetcherV3Fast
from src.lib.position_builder import PositionBuilder
from src.lib.unrealized_pnl_calculator import UnrealizedPnLCalculator
from src.lib.position_cache import get_position_cache
from src.lib.memory_guardrail import get_memory_guardrail
from src.lib.metrics_collector import get_metrics_collector
from src.config.feature_flags import positions_enabled

logger = logging.getLogger(__name__)

# Performance thresholds
PERFORMANCE_THRESHOLDS = {
    "api_latency_p95_ms": 200,      # 200ms P95 latency target
    "memory_rss_limit_mb": 700,     # 700MB RSS memory limit
    "cache_hit_rate_min": 70,       # 70% minimum cache hit rate
    "position_calc_p95_ms": 120,    # 120ms position calculation
    "large_wallet_max_sec": 20,     # 20s for large wallets
    "memory_growth_limit_mb": 50,   # 50MB growth during load test
}

# Test wallet categories
TEST_WALLETS = {
    "small": [
        "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",  # ~145 trades
    ],
    # Medium and large wallets disabled for beta while Railway tuning is in progress
    # TODO: Enable once 30s barrier is solved
    # "medium": [
    #     "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",  # ~6.4k trades
    # ],
    # "large": [
    #     # Add wallets with 10k+ trades when identified
    # ]
}


@dataclass
class PerformanceMetrics:
    """Performance metrics for a single test"""
    wallet: str
    test_type: str
    start_time: datetime
    end_time: datetime
    duration_ms: float
    memory_start_mb: float
    memory_peak_mb: float
    memory_end_mb: float
    memory_growth_mb: float
    trade_count: int
    position_count: int
    cache_hit_rate: float
    api_latency_p95_ms: float
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Check if test passed all thresholds"""
        if self.errors:
            return False
        
        # Check against thresholds
        checks = [
            self.api_latency_p95_ms <= PERFORMANCE_THRESHOLDS["api_latency_p95_ms"],
            self.memory_peak_mb <= PERFORMANCE_THRESHOLDS["memory_rss_limit_mb"],
            self.cache_hit_rate >= PERFORMANCE_THRESHOLDS["cache_hit_rate_min"],
            self.memory_growth_mb <= PERFORMANCE_THRESHOLDS["memory_growth_limit_mb"]
        ]
        
        if self.test_type == "large_wallet":
            checks.append(self.duration_ms / 1000 <= PERFORMANCE_THRESHOLDS["large_wallet_max_sec"])
        
        return all(checks)


@dataclass
class AccuracyMetrics:
    """Accuracy metrics for P&L validation"""
    wallet: str
    total_trades: int
    positions_calculated: int
    realized_pnl_usd: Decimal
    unrealized_pnl_usd: Decimal
    total_pnl_usd: Decimal
    price_coverage_pct: float
    confidence_high_pct: float
    dust_filtered_count: int
    accuracy_score: float
    validation_errors: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Check if accuracy validation passed"""
        return (
            len(self.validation_errors) == 0 and
            self.price_coverage_pct >= 80.0 and  # 80% price coverage
            self.confidence_high_pct >= 60.0 and  # 60% high confidence
            self.accuracy_score >= 0.9  # 90% accuracy score
        )


class PerformanceValidator:
    """
    Comprehensive performance validation framework
    
    Tests production readiness across multiple dimensions:
    - Load testing with large wallets
    - Accuracy validation with real data
    - Memory profiling under stress
    - Performance regression detection
    """
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.results: List[PerformanceMetrics] = []
        self.accuracy_results: List[AccuracyMetrics] = []
        
        # Initialize monitoring components
        self.memory_guardrail = get_memory_guardrail()
        self.metrics_collector = get_metrics_collector()
        self.position_cache = get_position_cache()
        
        logger.info("Performance validator initialized")
    
    async def run_comprehensive_validation(self) -> Dict[str, Any]:
        """
        Run complete validation suite
        
        Returns comprehensive test results and pass/fail status
        """
        logger.info("Starting comprehensive performance validation...")
        
        # Take baseline memory snapshot
        baseline_memory = self.process.memory_info().rss / 1024 / 1024
        self.memory_guardrail.take_snapshot()
        
        validation_results = {
            "start_time": datetime.utcnow().isoformat(),
            "baseline_memory_mb": baseline_memory,
            "tests_run": [],
            "performance_results": [],
            "accuracy_results": [],
            "overall_pass": False,
            "summary": {}
        }
        
        try:
            # 1. Load Testing
            logger.info("Running load tests...")
            load_results = await self._run_load_tests()
            validation_results["performance_results"].extend(load_results)
            validation_results["tests_run"].append("load_testing")
            
            # 2. Accuracy Validation
            logger.info("Running accuracy validation...")
            accuracy_results = await self._run_accuracy_validation()
            validation_results["accuracy_results"].extend(accuracy_results)
            validation_results["tests_run"].append("accuracy_validation")
            
            # 3. Memory Profiling
            logger.info("Running memory profiling...")
            memory_results = await self._run_memory_profiling()
            validation_results["performance_results"].extend(memory_results)
            validation_results["tests_run"].append("memory_profiling")
            
            # 4. Performance Regression Tests
            logger.info("Running regression tests...")
            regression_results = await self._run_regression_tests()
            validation_results["performance_results"].extend(regression_results)
            validation_results["tests_run"].append("regression_testing")
            
            # Generate summary
            validation_results["summary"] = self._generate_summary(
                validation_results["performance_results"],
                validation_results["accuracy_results"]
            )
            
            # Overall pass/fail
            validation_results["overall_pass"] = (
                validation_results["summary"]["performance_pass"] and
                validation_results["summary"]["accuracy_pass"]
            )
            
        except Exception as e:
            logger.error(f"Validation failed with error: {e}")
            validation_results["error"] = str(e)
            validation_results["overall_pass"] = False
        
        finally:
            validation_results["end_time"] = datetime.utcnow().isoformat()
        
        return validation_results
    
    async def _run_load_tests(self) -> List[PerformanceMetrics]:
        """Run load tests with various wallet sizes"""
        results = []
        
        # Test small wallets (baseline performance)
        for wallet in TEST_WALLETS["small"][:1]:  # Test one small wallet
            result = await self._test_wallet_performance(wallet, "small_wallet")
            results.append(result)
        
        # Test medium wallets (production load simulation)
        for wallet in TEST_WALLETS["medium"][:1]:  # Test one medium wallet
            result = await self._test_wallet_performance(wallet, "medium_wallet")
            results.append(result)
        
        # Test large wallets if available (stress testing)
        if TEST_WALLETS["large"]:
            for wallet in TEST_WALLETS["large"][:1]:
                result = await self._test_wallet_performance(wallet, "large_wallet")
                results.append(result)
        
        # Synthetic load test (10k trades)
        synthetic_result = await self._test_synthetic_load()
        results.append(synthetic_result)
        
        return results
    
    async def _run_accuracy_validation(self) -> List[AccuracyMetrics]:
        """Run accuracy validation on real wallets"""
        results = []
        
        # Test accuracy on different wallet types
        test_wallets = [
            ("small", TEST_WALLETS["small"][:1]),
            ("medium", TEST_WALLETS["medium"][:1])
        ]
        
        for category, wallets in test_wallets:
            for wallet in wallets:
                try:
                    result = await self._validate_wallet_accuracy(wallet, category)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Accuracy validation failed for {wallet}: {e}")
                    # Create failed result
                    failed_result = AccuracyMetrics(
                        wallet=wallet,
                        total_trades=0,
                        positions_calculated=0,
                        realized_pnl_usd=Decimal("0"),
                        unrealized_pnl_usd=Decimal("0"),
                        total_pnl_usd=Decimal("0"),
                        price_coverage_pct=0.0,
                        confidence_high_pct=0.0,
                        dust_filtered_count=0,
                        accuracy_score=0.0,
                        validation_errors=[str(e)]
                    )
                    results.append(failed_result)
        
        return results
    
    async def _run_memory_profiling(self) -> List[PerformanceMetrics]:
        """Run memory profiling under various load conditions"""
        results = []
        
        # Memory stress test - process multiple wallets sequentially
        result = await self._test_memory_stress()
        results.append(result)
        
        # Memory leak test - repeated operations
        leak_result = await self._test_memory_leaks()
        results.append(leak_result)
        
        return results
    
    async def _run_regression_tests(self) -> List[PerformanceMetrics]:
        """Run performance regression tests"""
        results = []
        
        # Cache performance regression
        cache_result = await self._test_cache_performance()
        results.append(cache_result)
        
        # API latency regression
        latency_result = await self._test_api_latency()
        results.append(latency_result)
        
        return results
    
    async def _test_wallet_performance(self, wallet: str, test_type: str) -> PerformanceMetrics:
        """Test performance for a single wallet"""
        start_time = datetime.utcnow()
        start_memory = self.process.memory_info().rss / 1024 / 1024
        
        # Start memory tracking
        tracemalloc.start()
        
        errors = []
        metadata = {}
        
        try:
            # Clear caches for clean test
            await self._clear_caches()
            
            # Start timing
            perf_start = time.time()
            
            # Fetch and analyze wallet
            async with BlockchainFetcherV3Fast(skip_pricing=False) as fetcher:
                trades_result = await fetcher.fetch_wallet_trades(wallet)
            
            # Build positions if enabled
            trade_count = trades_result["summary"]["total_trades"]
            position_count = 0
            
            if positions_enabled():
                builder = PositionBuilder()
                positions = builder.build_positions_from_trades(
                    wallet, trades_result.get("trades", [])
                )
                position_count = len(positions)
                
                # Calculate unrealized P&L
                if positions:
                    calculator = UnrealizedPnLCalculator()
                    await calculator.calculate_batch_unrealized_pnl(positions)
            
            duration_ms = (time.time() - perf_start) * 1000
            
            # Get memory metrics
            current_memory = self.process.memory_info().rss / 1024 / 1024
            traced_current, traced_peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            
            peak_memory = max(current_memory, traced_peak / 1024 / 1024)
            
            # Get cache stats
            cache_stats = self.position_cache.get_stats()
            cache_hit_rate = cache_stats.get("hit_rate", 0.0)
            
            # Get API latency from metrics
            metrics_snapshot = self.metrics_collector.get_snapshot()
            api_latency_p95 = metrics_snapshot.get("api_latency_p95_ms", 0.0)
            
            metadata.update({
                "fetch_time_ms": trades_result["summary"]["metrics"].get("fetch_time_seconds", 0) * 1000,
                "parse_rate": trades_result["summary"]["metrics"].get("parse_rate", 0),
                "cache_entries": cache_stats.get("total_entries", 0),
                "traced_peak_mb": traced_peak / 1024 / 1024
            })
            
        except Exception as e:
            logger.error(f"Performance test failed for {wallet}: {e}")
            errors.append(str(e))
            duration_ms = 0
            trade_count = 0
            position_count = 0
            current_memory = start_memory
            peak_memory = start_memory
            cache_hit_rate = 0.0
            api_latency_p95 = 0.0
            
            if tracemalloc.is_tracing():
                tracemalloc.stop()
        
        return PerformanceMetrics(
            wallet=wallet,
            test_type=test_type,
            start_time=start_time,
            end_time=datetime.utcnow(),
            duration_ms=duration_ms,
            memory_start_mb=start_memory,
            memory_peak_mb=peak_memory,
            memory_end_mb=current_memory,
            memory_growth_mb=current_memory - start_memory,
            trade_count=trade_count,
            position_count=position_count,
            cache_hit_rate=cache_hit_rate,
            api_latency_p95_ms=api_latency_p95,
            errors=errors,
            metadata=metadata
        )
    
    async def _test_synthetic_load(self) -> PerformanceMetrics:
        """Test synthetic load with 10k trades"""
        start_time = datetime.utcnow()
        start_memory = self.process.memory_info().rss / 1024 / 1024
        
        errors = []
        trade_count = 10000
        
        try:
            # Generate synthetic trades for performance testing
            perf_start = time.time()
            
            # Simulate processing 10k trades
            from src.lib.blockchain_fetcher_v3_fast import Trade
            
            trades = []
            for i in range(trade_count):
                trade = Trade(
                    signature=f"synthetic_sig_{i}",
                    timestamp=int(time.time()) - i,
                    slot=300000000 + i,
                    token_in_mint="So11111111111111111111111111111111111111112",
                    token_in_symbol="SOL",
                    token_in_amount=Decimal("1.0"),
                    token_out_mint=f"Token{i % 100}",  # 100 different tokens
                    token_out_symbol=f"TKN{i % 100}",
                    token_out_amount=Decimal("1000.0"),
                    value_usd=Decimal("150.0"),
                    priced=True
                )
                trades.append(trade)
                
                # Yield control every 100 trades
                if i % 100 == 0:
                    await asyncio.sleep(0.001)
            
            # Process positions if enabled
            position_count = 0
            if positions_enabled():
                builder = PositionBuilder()
                positions = builder.build_positions_from_trades("synthetic_wallet", trades)
                position_count = len(positions)
            
            duration_ms = (time.time() - perf_start) * 1000
            
        except Exception as e:
            logger.error(f"Synthetic load test failed: {e}")
            errors.append(str(e))
            duration_ms = 0
            position_count = 0
        
        current_memory = self.process.memory_info().rss / 1024 / 1024
        
        return PerformanceMetrics(
            wallet="synthetic_10k",
            test_type="synthetic_load",
            start_time=start_time,
            end_time=datetime.utcnow(),
            duration_ms=duration_ms,
            memory_start_mb=start_memory,
            memory_peak_mb=current_memory,
            memory_end_mb=current_memory,
            memory_growth_mb=current_memory - start_memory,
            trade_count=trade_count,
            position_count=position_count,
            cache_hit_rate=0.0,
            api_latency_p95_ms=0.0,
            errors=errors,
            metadata={"synthetic": True}
        )
    
    async def _validate_wallet_accuracy(self, wallet: str, category: str) -> AccuracyMetrics:
        """Validate accuracy for a specific wallet"""
        validation_errors = []
        
        try:
            # Fetch trades
            async with BlockchainFetcherV3Fast(skip_pricing=False) as fetcher:
                result = await fetcher.fetch_wallet_trades(wallet)
            
            trades = result.get("trades", [])
            total_trades = len(trades)
            
            if not positions_enabled():
                return AccuracyMetrics(
                    wallet=wallet,
                    total_trades=total_trades,
                    positions_calculated=0,
                    realized_pnl_usd=Decimal("0"),
                    unrealized_pnl_usd=Decimal("0"),
                    total_pnl_usd=Decimal("0"),
                    price_coverage_pct=0.0,
                    confidence_high_pct=0.0,
                    dust_filtered_count=0,
                    accuracy_score=0.0,
                    validation_errors=["Positions not enabled"]
                )
            
            # Build positions
            builder = PositionBuilder()
            positions = builder.build_positions_from_trades(wallet, trades)
            
            # Calculate unrealized P&L
            calculator = UnrealizedPnLCalculator()
            pnl_results = await calculator.calculate_batch_unrealized_pnl(positions)
            
            # Calculate metrics
            priced_trades = [t for t in trades if getattr(t, 'priced', False)]
            price_coverage_pct = (len(priced_trades) / total_trades * 100) if total_trades > 0 else 0
            
            high_confidence_trades = [
                t for t in priced_trades 
                if getattr(t, 'price_confidence', '') == 'high'
            ]
            confidence_high_pct = (len(high_confidence_trades) / len(priced_trades) * 100) if priced_trades else 0
            
            # Calculate P&L totals
            realized_pnl = sum(
                getattr(t, 'pnl_usd', 0) for t in trades 
                if hasattr(t, 'pnl_usd')
            )
            
            unrealized_pnl = sum(
                result.unrealized_pnl_usd for result in pnl_results 
                if result.unrealized_pnl_usd
            )
            
            total_pnl = realized_pnl + unrealized_pnl
            
            # Calculate accuracy score (based on data quality)
            accuracy_score = min(1.0, (
                price_coverage_pct / 100 * 0.4 +
                confidence_high_pct / 100 * 0.3 +
                (1.0 if len(positions) > 0 else 0.0) * 0.3
            ))
            
            # Validation checks
            if total_trades == 0:
                validation_errors.append("No trades found")
            
            if len(positions) == 0 and total_trades > 0:
                validation_errors.append("No positions generated from trades")
            
            if price_coverage_pct < 50:
                validation_errors.append(f"Low price coverage: {price_coverage_pct:.1f}%")
            
            return AccuracyMetrics(
                wallet=wallet,
                total_trades=total_trades,
                positions_calculated=len(positions),
                realized_pnl_usd=Decimal(str(realized_pnl)),
                unrealized_pnl_usd=Decimal(str(unrealized_pnl)),
                total_pnl_usd=Decimal(str(total_pnl)),
                price_coverage_pct=price_coverage_pct,
                confidence_high_pct=confidence_high_pct,
                dust_filtered_count=0,  # Would need to implement dust counting
                accuracy_score=accuracy_score,
                validation_errors=validation_errors
            )
            
        except Exception as e:
            logger.error(f"Accuracy validation failed for {wallet}: {e}")
            return AccuracyMetrics(
                wallet=wallet,
                total_trades=0,
                positions_calculated=0,
                realized_pnl_usd=Decimal("0"),
                unrealized_pnl_usd=Decimal("0"),
                total_pnl_usd=Decimal("0"),
                price_coverage_pct=0.0,
                confidence_high_pct=0.0,
                dust_filtered_count=0,
                accuracy_score=0.0,
                validation_errors=[str(e)]
            )
    
    async def _test_memory_stress(self) -> PerformanceMetrics:
        """Test memory usage under stress"""
        start_time = datetime.utcnow()
        start_memory = self.process.memory_info().rss / 1024 / 1024
        peak_memory = start_memory
        
        errors = []
        
        try:
            perf_start = time.time()
            
            # Process multiple wallets sequentially to stress memory
            for i, wallet in enumerate(TEST_WALLETS["small"] + TEST_WALLETS["medium"]):
                async with BlockchainFetcherV3Fast(skip_pricing=True) as fetcher:
                    await fetcher.fetch_wallet_trades(wallet)
                
                # Check memory
                current_memory = self.process.memory_info().rss / 1024 / 1024
                peak_memory = max(peak_memory, current_memory)
                
                # Force garbage collection
                gc.collect()
                
                # Check memory guardrail
                status = self.memory_guardrail.check_thresholds()
                if status["status"] == "critical":
                    errors.append(f"Memory guardrail triggered: {status['recommendations'][0]}")
                    break
                
                await asyncio.sleep(0.1)  # Brief pause
            
            duration_ms = (time.time() - perf_start) * 1000
            
        except Exception as e:
            logger.error(f"Memory stress test failed: {e}")
            errors.append(str(e))
            duration_ms = 0
        
        current_memory = self.process.memory_info().rss / 1024 / 1024
        
        return PerformanceMetrics(
            wallet="memory_stress",
            test_type="memory_stress",
            start_time=start_time,
            end_time=datetime.utcnow(),
            duration_ms=duration_ms,
            memory_start_mb=start_memory,
            memory_peak_mb=peak_memory,
            memory_end_mb=current_memory,
            memory_growth_mb=current_memory - start_memory,
            trade_count=0,
            position_count=0,
            cache_hit_rate=0.0,
            api_latency_p95_ms=0.0,
            errors=errors,
            metadata={"stress_test": True}
        )
    
    async def _test_memory_leaks(self) -> PerformanceMetrics:
        """Test for memory leaks with repeated operations"""
        start_time = datetime.utcnow()
        start_memory = self.process.memory_info().rss / 1024 / 1024
        
        errors = []
        
        try:
            perf_start = time.time()
            
            # Repeated operations to detect leaks
            for i in range(10):
                # Clear caches
                await self._clear_caches()
                
                # Process small wallet repeatedly
                if TEST_WALLETS["small"]:
                    wallet = TEST_WALLETS["small"][0]
                    async with BlockchainFetcherV3Fast(skip_pricing=True) as fetcher:
                        await fetcher.fetch_wallet_trades(wallet)
                
                # Check for memory growth
                current_memory = self.process.memory_info().rss / 1024 / 1024
                growth = current_memory - start_memory
                
                if growth > PERFORMANCE_THRESHOLDS["memory_growth_limit_mb"]:
                    errors.append(f"Memory leak detected: {growth:.1f}MB growth after {i+1} iterations")
                    break
                
                await asyncio.sleep(0.1)
            
            duration_ms = (time.time() - perf_start) * 1000
            
        except Exception as e:
            logger.error(f"Memory leak test failed: {e}")
            errors.append(str(e))
            duration_ms = 0
        
        current_memory = self.process.memory_info().rss / 1024 / 1024
        
        return PerformanceMetrics(
            wallet="memory_leak_test",
            test_type="memory_leak",
            start_time=start_time,
            end_time=datetime.utcnow(),
            duration_ms=duration_ms,
            memory_start_mb=start_memory,
            memory_peak_mb=current_memory,
            memory_end_mb=current_memory,
            memory_growth_mb=current_memory - start_memory,
            trade_count=0,
            position_count=0,
            cache_hit_rate=0.0,
            api_latency_p95_ms=0.0,
            errors=errors,
            metadata={"leak_test": True}
        )
    
    async def _test_cache_performance(self) -> PerformanceMetrics:
        """Test cache performance regression"""
        start_time = datetime.utcnow()
        start_memory = self.process.memory_info().rss / 1024 / 1024
        
        errors = []
        
        try:
            perf_start = time.time()
            
            # Test cache hit rates with repeated requests
            if TEST_WALLETS["small"]:
                wallet = TEST_WALLETS["small"][0]
                
                # First request (cold cache)
                async with BlockchainFetcherV3Fast(skip_pricing=False) as fetcher:
                    await fetcher.fetch_wallet_trades(wallet)
                
                # Second request (should hit cache)
                async with BlockchainFetcherV3Fast(skip_pricing=False) as fetcher:
                    await fetcher.fetch_wallet_trades(wallet)
                
                # Check cache stats
                cache_stats = self.position_cache.get_stats()
                hit_rate = cache_stats.get("hit_rate", 0.0)
                
                if hit_rate < PERFORMANCE_THRESHOLDS["cache_hit_rate_min"]:
                    errors.append(f"Cache hit rate too low: {hit_rate:.1f}%")
            
            duration_ms = (time.time() - perf_start) * 1000
            
        except Exception as e:
            logger.error(f"Cache performance test failed: {e}")
            errors.append(str(e))
            duration_ms = 0
        
        current_memory = self.process.memory_info().rss / 1024 / 1024
        cache_stats = self.position_cache.get_stats()
        
        return PerformanceMetrics(
            wallet="cache_test",
            test_type="cache_performance",
            start_time=start_time,
            end_time=datetime.utcnow(),
            duration_ms=duration_ms,
            memory_start_mb=start_memory,
            memory_peak_mb=current_memory,
            memory_end_mb=current_memory,
            memory_growth_mb=current_memory - start_memory,
            trade_count=0,
            position_count=0,
            cache_hit_rate=cache_stats.get("hit_rate", 0.0),
            api_latency_p95_ms=0.0,
            errors=errors,
            metadata=cache_stats
        )
    
    async def _test_api_latency(self) -> PerformanceMetrics:
        """Test API latency regression"""
        start_time = datetime.utcnow()
        start_memory = self.process.memory_info().rss / 1024 / 1024
        
        errors = []
        latencies = []
        
        try:
            # Multiple API calls to measure latency
            for i in range(5):
                if TEST_WALLETS["small"]:
                    wallet = TEST_WALLETS["small"][0]
                    
                    call_start = time.time()
                    async with BlockchainFetcherV3Fast(skip_pricing=True) as fetcher:
                        await fetcher.fetch_wallet_trades(wallet)
                    
                    latency_ms = (time.time() - call_start) * 1000
                    latencies.append(latency_ms)
                    
                    await asyncio.sleep(0.1)
            
            # Calculate P95 latency
            if latencies:
                latencies.sort()
                p95_index = int(len(latencies) * 0.95)
                api_latency_p95 = latencies[p95_index]
                
                if api_latency_p95 > PERFORMANCE_THRESHOLDS["api_latency_p95_ms"]:
                    errors.append(f"API latency too high: {api_latency_p95:.1f}ms")
            else:
                api_latency_p95 = 0.0
            
            duration_ms = sum(latencies)
            
        except Exception as e:
            logger.error(f"API latency test failed: {e}")
            errors.append(str(e))
            duration_ms = 0
            api_latency_p95 = 0.0
        
        current_memory = self.process.memory_info().rss / 1024 / 1024
        
        return PerformanceMetrics(
            wallet="latency_test",
            test_type="api_latency",
            start_time=start_time,
            end_time=datetime.utcnow(),
            duration_ms=duration_ms,
            memory_start_mb=start_memory,
            memory_peak_mb=current_memory,
            memory_end_mb=current_memory,
            memory_growth_mb=current_memory - start_memory,
            trade_count=0,
            position_count=0,
            cache_hit_rate=0.0,
            api_latency_p95_ms=api_latency_p95,
            errors=errors,
            metadata={"latencies": latencies}
        )
    
    async def _clear_caches(self):
        """Clear all caches for clean testing"""
        try:
            # Clear position cache
            if hasattr(self.position_cache, 'clear'):
                self.position_cache.clear()
            
            # Reset metrics
            if hasattr(self.metrics_collector, 'reset'):
                self.metrics_collector.reset()
            
            # Force garbage collection
            gc.collect()
            
        except Exception as e:
            logger.warning(f"Error clearing caches: {e}")
    
    def _generate_summary(self, performance_results: List[PerformanceMetrics], 
                         accuracy_results: List[AccuracyMetrics]) -> Dict[str, Any]:
        """Generate validation summary"""
        
        # Performance summary
        perf_passed = sum(1 for r in performance_results if r.passed)
        perf_total = len(performance_results)
        perf_pass_rate = (perf_passed / perf_total * 100) if perf_total > 0 else 0
        
        # Accuracy summary
        acc_passed = sum(1 for r in accuracy_results if r.passed)
        acc_total = len(accuracy_results)
        acc_pass_rate = (acc_passed / acc_total * 100) if acc_total > 0 else 0
        
        # Overall metrics
        total_errors = sum(len(r.errors) for r in performance_results)
        total_validation_errors = sum(len(r.validation_errors) for r in accuracy_results)
        
        # Performance statistics
        perf_stats = {}
        if performance_results:
            durations = [r.duration_ms for r in performance_results if r.duration_ms > 0]
            memory_growths = [r.memory_growth_mb for r in performance_results]
            
            if durations:
                perf_stats.update({
                    "avg_duration_ms": sum(durations) / len(durations),
                    "max_duration_ms": max(durations),
                    "min_duration_ms": min(durations)
                })
            
            if memory_growths:
                perf_stats.update({
                    "avg_memory_growth_mb": sum(memory_growths) / len(memory_growths),
                    "max_memory_growth_mb": max(memory_growths)
                })
        
        return {
            "performance_pass": perf_passed == perf_total and total_errors == 0,
            "accuracy_pass": acc_passed == acc_total and total_validation_errors == 0,
            "performance_pass_rate": perf_pass_rate,
            "accuracy_pass_rate": acc_pass_rate,
            "total_tests": perf_total + acc_total,
            "total_passed": perf_passed + acc_passed,
            "total_errors": total_errors + total_validation_errors,
            "performance_stats": perf_stats,
            "thresholds": PERFORMANCE_THRESHOLDS
        }


# Utility functions for standalone usage
async def run_quick_validation() -> Dict[str, Any]:
    """Run quick validation for CI/CD"""
    validator = PerformanceValidator()
    
    # Run subset of tests for quick feedback
    results = []
    
    # Test one small wallet
    if TEST_WALLETS["small"]:
        result = await validator._test_wallet_performance(
            TEST_WALLETS["small"][0], "quick_test"
        )
        results.append(result)
    
    # Test cache performance
    cache_result = await validator._test_cache_performance()
    results.append(cache_result)
    
    passed = all(r.passed for r in results)
    
    return {
        "quick_validation": True,
        "passed": passed,
        "results": [
            {
                "test": r.test_type,
                "wallet": r.wallet,
                "passed": r.passed,
                "duration_ms": r.duration_ms,
                "errors": r.errors
            }
            for r in results
        ]
    }


async def validate_production_readiness() -> bool:
    """
    Validate production readiness with full test suite
    
    Returns True if all validations pass
    """
    validator = PerformanceValidator()
    results = await validator.run_comprehensive_validation()
    
    return results["overall_pass"] 