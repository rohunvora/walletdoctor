#!/usr/bin/env python3
"""
Tests for Memory Guardrail System
WAL-609: Memory leak detection and auto-restart functionality

Tests cover:
- Memory snapshot collection
- Leak detection algorithms
- Threshold monitoring
- Auto-restart triggers
- Load testing baseline
"""

import pytest
import time
import os
import signal
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.lib.memory_guardrail import (
    MemoryGuardrail,
    MemorySnapshot,
    LeakDetectionResult,
    get_memory_guardrail,
    periodic_memory_check,
    MEMORY_RSS_THRESHOLD_MB,
    CACHE_ENTRIES_THRESHOLD,
    BASELINE_SAMPLE_COUNT
)


class TestMemorySnapshot:
    """Test MemorySnapshot dataclass"""
    
    def test_memory_snapshot_creation(self):
        """Test creating memory snapshot"""
        timestamp = datetime.utcnow()
        snapshot = MemorySnapshot(
            timestamp=timestamp,
            rss_mb=100.5,
            vms_mb=200.0,
            cache_entries=500,
            cache_hit_rate=85.0,
            api_requests_total=1000,
            process_id=12345
        )
        
        assert snapshot.timestamp == timestamp
        assert snapshot.rss_mb == 100.5
        assert snapshot.vms_mb == 200.0
        assert snapshot.cache_entries == 500
        assert snapshot.cache_hit_rate == 85.0
        assert snapshot.api_requests_total == 1000
        assert snapshot.process_id == 12345


class TestLeakDetectionResult:
    """Test LeakDetectionResult dataclass"""
    
    def test_leak_detection_result_creation(self):
        """Test creating leak detection result"""
        result = LeakDetectionResult(
            is_leak_detected=True,
            growth_rate_mb_per_min=5.5,
            time_to_threshold_min=30.0,
            current_rss_mb=150.0,
            threshold_rss_mb=700.0,
            recommendation="Monitor closely",
            severity="warning"
        )
        
        assert result.is_leak_detected is True
        assert result.growth_rate_mb_per_min == 5.5
        assert result.time_to_threshold_min == 30.0
        assert result.current_rss_mb == 150.0
        assert result.threshold_rss_mb == 700.0
        assert result.recommendation == "Monitor closely"
        assert result.severity == "warning"


class TestMemoryGuardrail:
    """Test MemoryGuardrail functionality"""
    
    def test_singleton_pattern(self):
        """Test singleton pattern works"""
        guardrail1 = get_memory_guardrail()
        guardrail2 = get_memory_guardrail()
        assert guardrail1 is guardrail2
    
    def test_memory_snapshot_creation(self):
        """Test creating memory snapshot"""
        timestamp = datetime.utcnow()
        snapshot = MemorySnapshot(
            timestamp=timestamp,
            rss_mb=100.5,
            vms_mb=200.0,
            cache_entries=500,
            cache_hit_rate=85.0,
            api_requests_total=1000,
            process_id=12345
        )
        
        assert snapshot.timestamp == timestamp
        assert snapshot.rss_mb == 100.5
        assert snapshot.cache_entries == 500
    
    def test_growth_rate_calculation(self):
        """Test linear regression for growth rate"""
        guardrail = MemoryGuardrail()
        
        # Create snapshots with steady growth
        start_time = datetime.utcnow() - timedelta(minutes=10)
        snapshots = []
        
        for i in range(5):
            timestamp = start_time + timedelta(minutes=i * 2)
            rss_mb = 100.0 + (i * 10.0)  # 10MB every 2 min = 5MB/min
            snapshot = MemorySnapshot(
                timestamp=timestamp, rss_mb=rss_mb, vms_mb=200.0,
                cache_entries=500, cache_hit_rate=85.0,
                api_requests_total=1000, process_id=12345
            )
            snapshots.append(snapshot)
        
        growth_rate = guardrail._calculate_growth_rate(snapshots)
        
        # Should detect ~5MB/min growth rate
        assert abs(growth_rate - 5.0) < 0.1
    
    def test_load_test_acceptance_criteria(self):
        """Test load test baseline meets WAL-609 acceptance criteria"""
        guardrail = MemoryGuardrail()
        
        mock_cache = Mock()
        mock_cache.get_stats.return_value = {"lru_size": 500, "hit_rate": 85.0}
        
        mock_metrics = Mock()
        mock_metrics.counters = {"api_requests_total": 1000}
        
        with patch('src.lib.memory_guardrail.get_position_cache', return_value=mock_cache):
            with patch('src.lib.memory_guardrail.get_metrics_collector', return_value=mock_metrics):
                # Establish baseline
                for _ in range(BASELINE_SAMPLE_COUNT):
                    guardrail.take_snapshot()
                guardrail.establish_baseline()
                
                # Simulate acceptable growth (+40MB < +50MB limit)
                mock_process = Mock()
                mock_memory_info = Mock()
                mock_memory_info.rss = 140 * 1024 * 1024  # 140MB (+40MB)
                mock_memory_info.vms = 200 * 1024 * 1024
                mock_process.memory_info.return_value = mock_memory_info
                guardrail.process = mock_process
                
                baseline_data = guardrail.get_load_test_baseline()
        
        # Should pass acceptance criteria (+40MB < +50MB limit)
        assert baseline_data["rss_growth_mb"] <= 50
        assert baseline_data["growth_percentage"] <= 50
    
    @pytest.fixture
    def mock_process(self):
        """Mock psutil.Process"""
        mock_process = Mock()
        mock_memory_info = Mock()
        mock_memory_info.rss = 100 * 1024 * 1024  # 100MB in bytes
        mock_memory_info.vms = 200 * 1024 * 1024  # 200MB in bytes
        mock_process.memory_info.return_value = mock_memory_info
        return mock_process
    
    @pytest.fixture
    def mock_cache(self):
        """Mock position cache"""
        mock_cache = Mock()
        mock_cache.get_stats.return_value = {
            "lru_size": 500,
            "hit_rate": 85.0
        }
        return mock_cache
    
    @pytest.fixture
    def mock_metrics(self):
        """Mock metrics collector"""
        mock_metrics = Mock()
        mock_metrics.counters = {"api_requests_total": 1000}
        return mock_metrics
    
    @pytest.fixture
    def guardrail(self, mock_process):
        """Create MemoryGuardrail with mocked dependencies"""
        with patch('src.lib.memory_guardrail.psutil.Process', return_value=mock_process):
            with patch('src.lib.memory_guardrail.os.getpid', return_value=12345):
                return MemoryGuardrail()
    
    def test_guardrail_initialization(self, guardrail):
        """Test guardrail initialization"""
        assert guardrail.snapshots == []
        assert guardrail.baseline_rss_mb is None
        assert guardrail.baseline_established is False
        assert guardrail.restart_count == 0
        assert guardrail.last_restart_time is None
    
    def test_take_snapshot(self, guardrail, mock_cache, mock_metrics):
        """Test taking memory snapshot"""
        with patch('src.lib.memory_guardrail.get_position_cache', return_value=mock_cache):
            with patch('src.lib.memory_guardrail.get_metrics_collector', return_value=mock_metrics):
                snapshot = guardrail.take_snapshot()
        
        assert snapshot.rss_mb == 100.0  # 100MB
        assert snapshot.vms_mb == 200.0  # 200MB
        assert snapshot.cache_entries == 500
        assert snapshot.cache_hit_rate == 85.0
        assert snapshot.api_requests_total == 1000
        assert snapshot.process_id == 12345
        assert len(guardrail.snapshots) == 1
    
    def test_snapshot_cleanup(self, guardrail, mock_cache, mock_metrics):
        """Test snapshot cleanup keeps only recent snapshots"""
        with patch('src.lib.memory_guardrail.get_position_cache', return_value=mock_cache):
            with patch('src.lib.memory_guardrail.get_metrics_collector', return_value=mock_metrics):
                # Add old snapshot
                old_snapshot = MemorySnapshot(
                    timestamp=datetime.utcnow() - timedelta(hours=2),
                    rss_mb=50.0, vms_mb=100.0, cache_entries=100,
                    cache_hit_rate=70.0, api_requests_total=500, process_id=12345
                )
                guardrail.snapshots.append(old_snapshot)
                
                # Take new snapshot (should trigger cleanup)
                new_snapshot = guardrail.take_snapshot()
        
        # Old snapshot should be removed
        assert len(guardrail.snapshots) == 1
        assert guardrail.snapshots[0] == new_snapshot
    
    def test_establish_baseline(self, guardrail, mock_cache, mock_metrics):
        """Test baseline establishment"""
        with patch('src.lib.memory_guardrail.get_position_cache', return_value=mock_cache):
            with patch('src.lib.memory_guardrail.get_metrics_collector', return_value=mock_metrics):
                # Take enough snapshots to establish baseline
                for i in range(BASELINE_SAMPLE_COUNT):
                    guardrail.take_snapshot()
                
                baseline_ready = guardrail.establish_baseline()
        
        assert baseline_ready is True
        assert guardrail.baseline_established is True
        assert guardrail.baseline_rss_mb == 100.0  # All snapshots have 100MB
    
    def test_establish_baseline_insufficient_data(self, guardrail):
        """Test baseline establishment with insufficient data"""
        baseline_ready = guardrail.establish_baseline()
        
        assert baseline_ready is False
        assert guardrail.baseline_established is False
        assert guardrail.baseline_rss_mb is None
    
    def test_growth_rate_no_growth(self, guardrail):
        """Test growth rate calculation with stable memory"""
        # Create snapshots with no growth
        start_time = datetime.utcnow() - timedelta(minutes=10)
        snapshots = []
        
        for i in range(5):
            timestamp = start_time + timedelta(minutes=i * 2)
            snapshot = MemorySnapshot(
                timestamp=timestamp, rss_mb=100.0, vms_mb=200.0,
                cache_entries=500, cache_hit_rate=85.0,
                api_requests_total=1000, process_id=12345
            )
            snapshots.append(snapshot)
        
        growth_rate = guardrail._calculate_growth_rate(snapshots)
        
        # Should detect no growth
        assert abs(growth_rate) < 0.1
    
    def test_detect_memory_leak_insufficient_data(self, guardrail):
        """Test leak detection with insufficient data"""
        result = guardrail.detect_memory_leak()
        
        assert result.is_leak_detected is False
        assert result.growth_rate_mb_per_min == 0.0
        assert result.time_to_threshold_min is None
        assert result.recommendation == "Insufficient data for leak detection"
        assert result.severity == "normal"
    
    def test_detect_memory_leak_stable(self, guardrail, mock_cache, mock_metrics):
        """Test leak detection with stable memory"""
        with patch('src.lib.memory_guardrail.get_position_cache', return_value=mock_cache):
            with patch('src.lib.memory_guardrail.get_metrics_collector', return_value=mock_metrics):
                # Take several snapshots with stable memory
                for _ in range(5):
                    guardrail.take_snapshot()
                    time.sleep(0.01)  # Small delay to ensure different timestamps
        
        result = guardrail.detect_memory_leak()
        
        assert result.is_leak_detected is False
        assert result.growth_rate_mb_per_min < 2.0  # Below leak threshold
        assert result.severity == "normal"
        assert "stable" in result.recommendation.lower()
    
    def test_detect_memory_leak_critical_threshold(self, guardrail):
        """Test leak detection when already above threshold"""
        # Create snapshot above threshold
        critical_snapshot = MemorySnapshot(
            timestamp=datetime.utcnow(),
            rss_mb=800.0,  # Above 700MB threshold
            vms_mb=1000.0,
            cache_entries=500,
            cache_hit_rate=85.0,
            api_requests_total=1000,
            process_id=12345
        )
        guardrail.snapshots.append(critical_snapshot)
        
        result = guardrail.detect_memory_leak()
        
        assert result.severity == "critical"
        assert "IMMEDIATE RESTART" in result.recommendation
        assert result.current_rss_mb == 800.0
    
    def test_check_thresholds_healthy(self, guardrail, mock_cache, mock_metrics):
        """Test threshold checking with healthy state"""
        with patch('src.lib.memory_guardrail.get_position_cache', return_value=mock_cache):
            with patch('src.lib.memory_guardrail.get_metrics_collector', return_value=mock_metrics):
                status = guardrail.check_thresholds()
        
        assert status["status"] == "healthy"
        assert status["current_memory"]["rss_mb"] == 100.0
        assert status["current_memory"]["cache_entries"] == 500
        assert status["thresholds"]["rss_mb"] == MEMORY_RSS_THRESHOLD_MB
        assert status["thresholds"]["cache_entries"] == CACHE_ENTRIES_THRESHOLD
    
    def test_check_thresholds_rss_exceeded(self, guardrail, mock_cache, mock_metrics):
        """Test threshold checking with RSS exceeded"""
        # Mock high memory usage
        mock_process = Mock()
        mock_memory_info = Mock()
        mock_memory_info.rss = 800 * 1024 * 1024  # 800MB in bytes
        mock_memory_info.vms = 1000 * 1024 * 1024
        mock_process.memory_info.return_value = mock_memory_info
        guardrail.process = mock_process
        
        with patch('src.lib.memory_guardrail.get_position_cache', return_value=mock_cache):
            with patch('src.lib.memory_guardrail.get_metrics_collector', return_value=mock_metrics):
                status = guardrail.check_thresholds()
        
        assert status["status"] == "critical"
        assert status["current_memory"]["rss_mb"] == 800.0
        assert any("RSS memory" in rec for rec in status["recommendations"])
    
    def test_check_thresholds_cache_exceeded(self, guardrail, mock_metrics):
        """Test threshold checking with cache exceeded"""
        # Mock high cache usage
        mock_cache = Mock()
        mock_cache.get_stats.return_value = {
            "lru_size": 3000,  # Above 2200 threshold
            "hit_rate": 85.0
        }
        
        with patch('src.lib.memory_guardrail.get_position_cache', return_value=mock_cache):
            with patch('src.lib.memory_guardrail.get_metrics_collector', return_value=mock_metrics):
                status = guardrail.check_thresholds()
        
        assert status["status"] == "critical"
        assert status["current_memory"]["cache_entries"] == 3000
        assert any("Cache entries" in rec for rec in status["recommendations"])
    
    def test_should_restart_disabled(self, guardrail):
        """Test restart check when auto-restart is disabled"""
        with patch.dict(os.environ, {"AUTO_RESTART_ENABLED": "false"}):
            should_restart, reason = guardrail.should_restart()
        
        assert should_restart is False
        assert "Auto-restart disabled" in reason
    
    def test_should_restart_rss_threshold(self, guardrail, mock_cache, mock_metrics):
        """Test restart trigger for RSS threshold"""
        with patch.dict(os.environ, {"AUTO_RESTART_ENABLED": "true"}):
            # Mock high memory usage
            mock_process = Mock()
            mock_memory_info = Mock()
            mock_memory_info.rss = 800 * 1024 * 1024  # 800MB
            mock_memory_info.vms = 1000 * 1024 * 1024
            mock_process.memory_info.return_value = mock_memory_info
            guardrail.process = mock_process
            
            with patch('src.lib.memory_guardrail.get_position_cache', return_value=mock_cache):
                with patch('src.lib.memory_guardrail.get_metrics_collector', return_value=mock_metrics):
                    should_restart, reason = guardrail.should_restart()
        
        assert should_restart is True
        assert "RSS memory" in reason
        assert "800.0MB" in reason
    
    def test_should_restart_cache_threshold(self, guardrail, mock_metrics):
        """Test restart trigger for cache threshold"""
        with patch.dict(os.environ, {"AUTO_RESTART_ENABLED": "true"}):
            # Mock high cache usage
            mock_cache = Mock()
            mock_cache.get_stats.return_value = {
                "lru_size": 3000,  # Above threshold
                "hit_rate": 85.0
            }
            
            with patch('src.lib.memory_guardrail.get_position_cache', return_value=mock_cache):
                with patch('src.lib.memory_guardrail.get_metrics_collector', return_value=mock_metrics):
                    should_restart, reason = guardrail.should_restart()
        
        assert should_restart is True
        assert "Cache entries" in reason
        assert "3000" in reason
    
    def test_should_restart_rate_limiting(self, guardrail):
        """Test restart rate limiting"""
        with patch.dict(os.environ, {"AUTO_RESTART_ENABLED": "true"}):
            # Set recent restart time
            guardrail.last_restart_time = datetime.utcnow() - timedelta(minutes=2)
            
            should_restart, reason = guardrail.should_restart()
        
        assert should_restart is False
        assert "Too soon since last restart" in reason
    
    def test_trigger_restart(self, guardrail):
        """Test restart triggering"""
        with patch('src.lib.memory_guardrail.os.kill') as mock_kill:
            with patch('src.lib.memory_guardrail.time.sleep'):
                guardrail.trigger_restart("Test restart")
        
        assert guardrail.restart_count == 1
        assert guardrail.last_restart_time is not None
        mock_kill.assert_called_once_with(os.getpid(), signal.SIGTERM)
    
    def test_get_load_test_baseline_not_established(self, guardrail):
        """Test load test baseline when not established"""
        result = guardrail.get_load_test_baseline()
        
        assert "error" in result
        assert "Baseline not established" in result["error"]
    
    def test_get_load_test_baseline_established(self, guardrail, mock_cache, mock_metrics):
        """Test load test baseline when established"""
        with patch('src.lib.memory_guardrail.get_position_cache', return_value=mock_cache):
            with patch('src.lib.memory_guardrail.get_metrics_collector', return_value=mock_metrics):
                # Establish baseline
                for _ in range(BASELINE_SAMPLE_COUNT):
                    guardrail.take_snapshot()
                guardrail.establish_baseline()
                
                # Take another snapshot (simulating growth)
                mock_process = Mock()
                mock_memory_info = Mock()
                mock_memory_info.rss = 120 * 1024 * 1024  # 120MB (20MB growth)
                mock_memory_info.vms = 200 * 1024 * 1024
                mock_process.memory_info.return_value = mock_memory_info
                guardrail.process = mock_process
                
                result = guardrail.get_load_test_baseline()
        
        assert result["baseline_rss_mb"] == 100.0
        assert result["current_rss_mb"] == 120.0
        assert result["rss_growth_mb"] == 20.0
        assert result["growth_percentage"] == 20.0
        assert result["baseline_established"] is True
    
    def test_get_detailed_stats(self, guardrail, mock_cache, mock_metrics):
        """Test getting detailed statistics"""
        with patch('src.lib.memory_guardrail.get_position_cache', return_value=mock_cache):
            with patch('src.lib.memory_guardrail.get_metrics_collector', return_value=mock_metrics):
                # Take some snapshots
                for _ in range(3):
                    guardrail.take_snapshot()
                    time.sleep(0.01)
                
                stats = guardrail.get_detailed_stats()
        
        assert "process_info" in stats
        assert "memory_trend" in stats
        assert "leak_detection" in stats
        assert "thresholds" in stats
        assert "baseline" in stats
        assert len(stats["memory_trend"]) == 3


class TestGlobalFunctions:
    """Test global functions and utilities"""
    
    def test_periodic_memory_check(self, mock_cache, mock_metrics):
        """Test periodic memory check function"""
        with patch('src.lib.memory_guardrail.get_position_cache', return_value=mock_cache):
            with patch('src.lib.memory_guardrail.get_metrics_collector', return_value=mock_metrics):
                # Should not raise exception
                periodic_memory_check()


class TestLoadTestingSupport:
    """Test load testing specific functionality"""
    
    def test_load_test_baseline_validation(self, mock_cache, mock_metrics):
        """Test load test baseline meets acceptance criteria"""
        guardrail = MemoryGuardrail()
        
        with patch('src.lib.memory_guardrail.get_position_cache', return_value=mock_cache):
            with patch('src.lib.memory_guardrail.get_metrics_collector', return_value=mock_metrics):
                # Establish baseline
                for _ in range(BASELINE_SAMPLE_COUNT):
                    guardrail.take_snapshot()
                guardrail.establish_baseline()
                
                # Simulate 10 minutes of load test with minimal growth
                for i in range(10):
                    # Gradual memory increase (total +40MB over 10 minutes)
                    mock_process = Mock()
                    mock_memory_info = Mock()
                    rss_bytes = (100 + (i * 4)) * 1024 * 1024  # +4MB per minute
                    mock_memory_info.rss = rss_bytes
                    mock_memory_info.vms = 200 * 1024 * 1024
                    mock_process.memory_info.return_value = mock_memory_info
                    guardrail.process = mock_process
                    
                    guardrail.take_snapshot()
                
                baseline_data = guardrail.get_load_test_baseline()
        
        # Should pass acceptance criteria (+40MB < +50MB limit)
        assert baseline_data["rss_growth_mb"] <= 50
        assert baseline_data["growth_percentage"] <= 50  # 50% growth limit
    
    def test_load_test_baseline_failure(self, mock_cache, mock_metrics):
        """Test load test baseline failure scenario"""
        guardrail = MemoryGuardrail()
        
        with patch('src.lib.memory_guardrail.get_position_cache', return_value=mock_cache):
            with patch('src.lib.memory_guardrail.get_metrics_collector', return_value=mock_metrics):
                # Establish baseline
                for _ in range(BASELINE_SAMPLE_COUNT):
                    guardrail.take_snapshot()
                guardrail.establish_baseline()
                
                # Simulate excessive memory growth (+60MB)
                mock_process = Mock()
                mock_memory_info = Mock()
                mock_memory_info.rss = 160 * 1024 * 1024  # 160MB (+60MB)
                mock_memory_info.vms = 200 * 1024 * 1024
                mock_process.memory_info.return_value = mock_memory_info
                guardrail.process = mock_process
                
                baseline_data = guardrail.get_load_test_baseline()
        
        # Should fail acceptance criteria (+60MB > +50MB limit)
        assert baseline_data["rss_growth_mb"] > 50


class TestEnvironmentConfiguration:
    """Test environment variable configuration"""
    
    def test_custom_thresholds(self):
        """Test custom threshold configuration"""
        with patch.dict(os.environ, {
            "MEMORY_RSS_THRESHOLD_MB": "500",
            "CACHE_ENTRIES_THRESHOLD": "1000",
            "BASELINE_SAMPLE_COUNT": "5"
        }):
            # Import after environment change
            import importlib
            import src.lib.memory_guardrail
            importlib.reload(src.lib.memory_guardrail)
            
            # Verify constants updated
            assert src.lib.memory_guardrail.MEMORY_RSS_THRESHOLD_MB == 500
            assert src.lib.memory_guardrail.CACHE_ENTRIES_THRESHOLD == 1000
            assert src.lib.memory_guardrail.BASELINE_SAMPLE_COUNT == 5
    
    def test_auto_restart_enabled(self):
        """Test auto-restart enabled configuration"""
        with patch.dict(os.environ, {"AUTO_RESTART_ENABLED": "true"}):
            import importlib
            import src.lib.memory_guardrail
            importlib.reload(src.lib.memory_guardrail)
            
            assert src.lib.memory_guardrail.AUTO_RESTART_ENABLED is True


# Performance and stress tests
class TestPerformanceStress:
    """Test performance characteristics"""
    
    def test_snapshot_performance(self, mock_cache, mock_metrics):
        """Test snapshot collection performance"""
        guardrail = MemoryGuardrail()
        
        with patch('src.lib.memory_guardrail.get_position_cache', return_value=mock_cache):
            with patch('src.lib.memory_guardrail.get_metrics_collector', return_value=mock_metrics):
                start_time = time.time()
                
                # Take 100 snapshots
                for _ in range(100):
                    guardrail.take_snapshot()
                
                end_time = time.time()
                avg_time_per_snapshot = (end_time - start_time) / 100
        
        # Should be very fast (< 10ms per snapshot)
        assert avg_time_per_snapshot < 0.01
    
    def test_memory_efficiency(self, mock_cache, mock_metrics):
        """Test memory efficiency of guardrail itself"""
        guardrail = MemoryGuardrail()
        
        with patch('src.lib.memory_guardrail.get_position_cache', return_value=mock_cache):
            with patch('src.lib.memory_guardrail.get_metrics_collector', return_value=mock_metrics):
                # Take many snapshots to test cleanup
                for _ in range(1000):
                    guardrail.take_snapshot()
        
        # Should not accumulate too many snapshots (cleanup should work)
        assert len(guardrail.snapshots) < 100  # Should be much less due to 1-hour window 