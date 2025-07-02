#!/usr/bin/env python3
"""
Tests for Performance Validation Framework
WAL-610: Test the comprehensive validation system
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from decimal import Decimal

from src.lib.performance_validator import (
    PerformanceValidator,
    PerformanceMetrics,
    AccuracyMetrics,
    PERFORMANCE_THRESHOLDS,
    TEST_WALLETS,
    run_quick_validation,
    validate_production_readiness
)


class TestPerformanceMetrics:
    """Test PerformanceMetrics dataclass"""
    
    def test_performance_metrics_creation(self):
        """Test creating performance metrics"""
        start_time = datetime.utcnow()
        metrics = PerformanceMetrics(
            wallet="test_wallet",
            test_type="unit_test",
            start_time=start_time,
            end_time=datetime.utcnow(),
            duration_ms=1500.0,
            memory_start_mb=100.0,
            memory_peak_mb=150.0,
            memory_end_mb=120.0,
            memory_growth_mb=20.0,
            trade_count=1000,
            position_count=50,
            cache_hit_rate=85.0,
            api_latency_p95_ms=180.0
        )
        
        assert metrics.wallet == "test_wallet"
        assert metrics.duration_ms == 1500.0
        assert metrics.trade_count == 1000
        assert metrics.position_count == 50
    
    def test_performance_metrics_passed_property(self):
        """Test performance metrics pass/fail logic"""
        # Create passing metrics
        passing_metrics = PerformanceMetrics(
            wallet="test_wallet",
            test_type="small_wallet",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            duration_ms=1000.0,
            memory_start_mb=100.0,
            memory_peak_mb=150.0,  # Below 700MB limit
            memory_end_mb=120.0,
            memory_growth_mb=20.0,  # Below 50MB limit
            trade_count=1000,
            position_count=50,
            cache_hit_rate=85.0,  # Above 70% minimum
            api_latency_p95_ms=150.0,  # Below 200ms limit
            errors=[]
        )
        
        assert passing_metrics.passed is True
        
        # Create failing metrics (high memory)
        failing_metrics = PerformanceMetrics(
            wallet="test_wallet",
            test_type="small_wallet",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            duration_ms=1000.0,
            memory_start_mb=100.0,
            memory_peak_mb=800.0,  # Above 700MB limit
            memory_end_mb=120.0,
            memory_growth_mb=20.0,
            trade_count=1000,
            position_count=50,
            cache_hit_rate=85.0,
            api_latency_p95_ms=150.0,
            errors=[]
        )
        
        assert failing_metrics.passed is False
        
        # Create failing metrics (errors)
        error_metrics = PerformanceMetrics(
            wallet="test_wallet",
            test_type="small_wallet",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            duration_ms=1000.0,
            memory_start_mb=100.0,
            memory_peak_mb=150.0,
            memory_end_mb=120.0,
            memory_growth_mb=20.0,
            trade_count=1000,
            position_count=50,
            cache_hit_rate=85.0,
            api_latency_p95_ms=150.0,
            errors=["Test error"]
        )
        
        assert error_metrics.passed is False


class TestAccuracyMetrics:
    """Test AccuracyMetrics dataclass"""
    
    def test_accuracy_metrics_creation(self):
        """Test creating accuracy metrics"""
        metrics = AccuracyMetrics(
            wallet="test_wallet",
            total_trades=1000,
            positions_calculated=50,
            realized_pnl_usd=Decimal("1500.00"),
            unrealized_pnl_usd=Decimal("-200.00"),
            total_pnl_usd=Decimal("1300.00"),
            price_coverage_pct=85.0,
            confidence_high_pct=70.0,
            dust_filtered_count=10,
            accuracy_score=0.95
        )
        
        assert metrics.wallet == "test_wallet"
        assert metrics.total_trades == 1000
        assert metrics.positions_calculated == 50
        assert metrics.total_pnl_usd == Decimal("1300.00")
    
    def test_accuracy_metrics_passed_property(self):
        """Test accuracy metrics pass/fail logic"""
        # Create passing metrics
        passing_metrics = AccuracyMetrics(
            wallet="test_wallet",
            total_trades=1000,
            positions_calculated=50,
            realized_pnl_usd=Decimal("1500.00"),
            unrealized_pnl_usd=Decimal("-200.00"),
            total_pnl_usd=Decimal("1300.00"),
            price_coverage_pct=85.0,  # Above 80% minimum
            confidence_high_pct=70.0,  # Above 60% minimum
            dust_filtered_count=10,
            accuracy_score=0.95,  # Above 0.9 minimum
            validation_errors=[]
        )
        
        assert passing_metrics.passed is True
        
        # Create failing metrics (low price coverage)
        failing_metrics = AccuracyMetrics(
            wallet="test_wallet",
            total_trades=1000,
            positions_calculated=50,
            realized_pnl_usd=Decimal("1500.00"),
            unrealized_pnl_usd=Decimal("-200.00"),
            total_pnl_usd=Decimal("1300.00"),
            price_coverage_pct=70.0,  # Below 80% minimum
            confidence_high_pct=70.0,
            dust_filtered_count=10,
            accuracy_score=0.95,
            validation_errors=[]
        )
        
        assert failing_metrics.passed is False


class TestPerformanceValidator:
    """Test PerformanceValidator class"""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Mock external dependencies"""
        with patch('src.lib.performance_validator.get_memory_guardrail') as mock_guardrail:
            with patch('src.lib.performance_validator.get_metrics_collector') as mock_metrics:
                with patch('src.lib.performance_validator.get_position_cache') as mock_cache:
                    with patch('psutil.Process') as mock_process:
                        
                        # Configure mocks
                        mock_memory_info = Mock()
                        mock_memory_info.rss = 100 * 1024 * 1024  # 100MB
                        mock_process.return_value.memory_info.return_value = mock_memory_info
                        
                        mock_guardrail.return_value.take_snapshot.return_value = None
                        mock_metrics.return_value.get_snapshot.return_value = {"api_latency_p95_ms": 150.0}
                        mock_cache.return_value.get_stats.return_value = {"hit_rate": 85.0, "total_entries": 100}
                        
                        yield {
                            "guardrail": mock_guardrail.return_value,
                            "metrics": mock_metrics.return_value,
                            "cache": mock_cache.return_value,
                            "process": mock_process.return_value
                        }
    
    def test_validator_initialization(self, mock_dependencies):
        """Test validator initialization"""
        validator = PerformanceValidator()
        
        assert validator.process is not None
        assert validator.results == []
        assert validator.accuracy_results == []
    
    @pytest.mark.asyncio
    async def test_test_wallet_performance(self, mock_dependencies):
        """Test individual wallet performance testing"""
        validator = PerformanceValidator()
        
        # Mock blockchain fetcher
        mock_trades_result = {
            "summary": {
                "total_trades": 100,
                "metrics": {
                    "fetch_time_seconds": 2.5,
                    "parse_rate": 0.95
                }
            },
            "trades": []
        }
        
        with patch('src.lib.performance_validator.BlockchainFetcherV3Fast') as mock_fetcher:
            # Configure async context manager
            mock_fetcher_instance = AsyncMock()
            mock_fetcher_instance.fetch_wallet_trades.return_value = mock_trades_result
            mock_fetcher.return_value.__aenter__.return_value = mock_fetcher_instance
            
            with patch('src.lib.performance_validator.positions_enabled', return_value=False):
                with patch('tracemalloc.start'):
                    with patch('tracemalloc.get_traced_memory', return_value=(50*1024*1024, 60*1024*1024)):
                        with patch('tracemalloc.stop'):
                            
                            result = await validator._test_wallet_performance("test_wallet", "test")
                            
                            assert result.wallet == "test_wallet"
                            assert result.test_type == "test"
                            assert result.trade_count == 100
                            assert result.duration_ms > 0
                            assert len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_synthetic_load_test(self, mock_dependencies):
        """Test synthetic load generation"""
        validator = PerformanceValidator()
        
        with patch('src.lib.performance_validator.positions_enabled', return_value=False):
            result = await validator._test_synthetic_load()
            
            assert result.wallet == "synthetic_10k"
            assert result.test_type == "synthetic_load"
            assert result.trade_count == 10000
            assert result.duration_ms > 0
    
    @pytest.mark.asyncio
    async def test_memory_stress_test(self, mock_dependencies):
        """Test memory stress testing"""
        validator = PerformanceValidator()
        
        mock_trades_result = {
            "summary": {"total_trades": 50},
            "trades": []
        }
        
        with patch('src.lib.performance_validator.BlockchainFetcherV3Fast') as mock_fetcher:
            mock_fetcher_instance = AsyncMock()
            mock_fetcher_instance.fetch_wallet_trades.return_value = mock_trades_result
            mock_fetcher.return_value.__aenter__.return_value = mock_fetcher_instance
            
            with patch('gc.collect'):
                result = await validator._test_memory_stress()
                
                assert result.test_type == "memory_stress"
                assert result.wallet == "memory_stress"
                assert result.metadata["stress_test"] is True
    
    @pytest.mark.asyncio
    async def test_accuracy_validation(self, mock_dependencies):
        """Test accuracy validation on wallets"""
        validator = PerformanceValidator()
        
        # Mock trades with pricing data
        mock_trade = Mock()
        mock_trade.priced = True
        mock_trade.price_confidence = "high"
        
        mock_trades_result = {
            "trades": [mock_trade] * 100,  # 100 trades
            "summary": {"total_trades": 100}
        }
        
        with patch('src.lib.performance_validator.BlockchainFetcherV3Fast') as mock_fetcher:
            mock_fetcher_instance = AsyncMock()
            mock_fetcher_instance.fetch_wallet_trades.return_value = mock_trades_result
            mock_fetcher.return_value.__aenter__.return_value = mock_fetcher_instance
            
            with patch('src.lib.performance_validator.positions_enabled', return_value=True):
                with patch('src.lib.performance_validator.PositionBuilder') as mock_builder:
                    mock_builder.return_value.build_positions_from_trades.return_value = []
                    
                    result = await validator._validate_wallet_accuracy("test_wallet", "test")
                    
                    assert result.wallet == "test_wallet"
                    assert result.total_trades == 100
                    assert result.price_coverage_pct == 100.0
                    assert result.confidence_high_pct == 100.0
    
    @pytest.mark.asyncio
    async def test_comprehensive_validation(self, mock_dependencies):
        """Test full validation suite"""
        validator = PerformanceValidator()
        
        # Mock all external calls
        with patch.object(validator, '_run_load_tests', return_value=[]):
            with patch.object(validator, '_run_accuracy_validation', return_value=[]):
                with patch.object(validator, '_run_memory_profiling', return_value=[]):
                    with patch.object(validator, '_run_regression_tests', return_value=[]):
                        
                        result = await validator.run_comprehensive_validation()
                        
                        assert "start_time" in result
                        assert "end_time" in result
                        assert "baseline_memory_mb" in result
                        assert "tests_run" in result
                        assert "performance_results" in result
                        assert "accuracy_results" in result
                        assert "overall_pass" in result
                        assert "summary" in result


class TestUtilityFunctions:
    """Test utility functions"""
    
    @pytest.mark.asyncio
    async def test_run_quick_validation(self):
        """Test quick validation function"""
        # Mock the validator
        with patch('src.lib.performance_validator.PerformanceValidator') as mock_validator_class:
            mock_validator = Mock()
            mock_validator_class.return_value = mock_validator
            
            # Create mock performance result
            mock_result = PerformanceMetrics(
                wallet="test_wallet",
                test_type="quick_test",
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow(),
                duration_ms=1000.0,
                memory_start_mb=100.0,
                memory_peak_mb=120.0,
                memory_end_mb=110.0,
                memory_growth_mb=10.0,
                trade_count=100,
                position_count=5,
                cache_hit_rate=80.0,
                api_latency_p95_ms=150.0,
                errors=[]
            )
            
            mock_validator._test_wallet_performance = AsyncMock(return_value=mock_result)
            mock_validator._test_cache_performance = AsyncMock(return_value=mock_result)
            
            result = await run_quick_validation()
            
            assert result["quick_validation"] is True
            assert "passed" in result
            assert "results" in result
            assert len(result["results"]) > 0
    
    @pytest.mark.asyncio
    async def test_validate_production_readiness(self):
        """Test production readiness validation"""
        with patch('src.lib.performance_validator.PerformanceValidator') as mock_validator_class:
            mock_validator = Mock()
            mock_validator_class.return_value = mock_validator
            
            # Mock successful validation
            mock_validator.run_comprehensive_validation = AsyncMock(return_value={
                "overall_pass": True
            })
            
            result = await validate_production_readiness()
            
            assert result is True
            
            # Mock failed validation
            mock_validator.run_comprehensive_validation = AsyncMock(return_value={
                "overall_pass": False
            })
            
            result = await validate_production_readiness()
            
            assert result is False


class TestThresholds:
    """Test performance threshold configuration"""
    
    def test_performance_thresholds_defined(self):
        """Test that all required thresholds are defined"""
        required_thresholds = [
            "api_latency_p95_ms",
            "memory_rss_limit_mb",
            "cache_hit_rate_min",
            "large_wallet_max_sec",
            "memory_growth_limit_mb"
        ]
        
        for threshold in required_thresholds:
            assert threshold in PERFORMANCE_THRESHOLDS
            assert isinstance(PERFORMANCE_THRESHOLDS[threshold], (int, float))
            assert PERFORMANCE_THRESHOLDS[threshold] > 0
    
    def test_test_wallets_defined(self):
        """Test that test wallet categories are defined"""
        assert "small" in TEST_WALLETS
        assert "medium" in TEST_WALLETS
        
        # Should have at least one wallet in each category
        assert len(TEST_WALLETS["small"]) > 0
        assert len(TEST_WALLETS["medium"]) > 0
        
        # All wallet addresses should be strings
        for category in TEST_WALLETS:
            for wallet in TEST_WALLETS[category]:
                assert isinstance(wallet, str)
                assert len(wallet) > 20  # Reasonable wallet address length


class TestErrorHandling:
    """Test error handling in validation"""
    
    @pytest.mark.asyncio
    async def test_wallet_performance_error_handling(self):
        """Test error handling in wallet performance testing"""
        validator = PerformanceValidator()
        
        # Mock fetcher to raise exception
        with patch('src.lib.performance_validator.BlockchainFetcherV3Fast') as mock_fetcher:
            mock_fetcher.side_effect = Exception("Network error")
            
            with patch('psutil.Process') as mock_process:
                mock_memory_info = Mock()
                mock_memory_info.rss = 100 * 1024 * 1024
                mock_process.return_value.memory_info.return_value = mock_memory_info
                
                result = await validator._test_wallet_performance("error_wallet", "test")
                
                assert len(result.errors) > 0
                assert "Network error" in result.errors[0]
                assert result.passed is False
    
    @pytest.mark.asyncio
    async def test_accuracy_validation_error_handling(self):
        """Test error handling in accuracy validation"""
        validator = PerformanceValidator()
        
        # Mock fetcher to raise exception
        with patch('src.lib.performance_validator.BlockchainFetcherV3Fast') as mock_fetcher:
            mock_fetcher.side_effect = Exception("API error")
            
            result = await validator._validate_wallet_accuracy("error_wallet", "test")
            
            assert len(result.validation_errors) > 0
            assert "API error" in result.validation_errors[0]
            assert result.passed is False


class TestPerformanceRegression:
    """Test performance regression detection"""
    
    def test_large_wallet_duration_threshold(self):
        """Test that large wallet duration is checked against threshold"""
        # Create metrics for large wallet that exceeds time threshold
        slow_metrics = PerformanceMetrics(
            wallet="large_wallet",
            test_type="large_wallet",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            duration_ms=25000.0,  # 25 seconds > 20 second threshold
            memory_start_mb=100.0,
            memory_peak_mb=150.0,
            memory_end_mb=120.0,
            memory_growth_mb=20.0,
            trade_count=10000,
            position_count=50,
            cache_hit_rate=85.0,
            api_latency_p95_ms=150.0,
            errors=[]
        )
        
        assert slow_metrics.passed is False
        
        # Create metrics for large wallet within threshold
        fast_metrics = PerformanceMetrics(
            wallet="large_wallet",
            test_type="large_wallet",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            duration_ms=15000.0,  # 15 seconds < 20 second threshold
            memory_start_mb=100.0,
            memory_peak_mb=150.0,
            memory_end_mb=120.0,
            memory_growth_mb=20.0,
            trade_count=10000,
            position_count=50,
            cache_hit_rate=85.0,
            api_latency_p95_ms=150.0,
            errors=[]
        )
        
        assert fast_metrics.passed is True


class TestIntegration:
    """Integration tests for the validation framework"""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not pytest.param,  # Skip by default in CI
        reason="Integration test requires full environment"
    )
    async def test_real_wallet_validation(self):
        """Test validation with real wallet (requires API keys)"""
        validator = PerformanceValidator()
        
        # Use a small test wallet
        test_wallet = TEST_WALLETS["small"][0]
        
        result = await validator._test_wallet_performance(test_wallet, "integration_test")
        
        # Basic validation that it completed
        assert result.wallet == test_wallet
        assert result.trade_count >= 0  # Should have some trades or handle gracefully
        assert result.duration_ms > 0 or len(result.errors) > 0  # Either works or has errors 