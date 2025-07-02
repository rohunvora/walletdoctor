#!/usr/bin/env python3
"""
Tests for Metrics Collection System
WAL-608: Comprehensive monitoring tests

Tests for:
- Prometheus metrics generation
- Request latency tracking
- Memory monitoring
- Cache metrics integration
- Alert thresholds
"""

import pytest
import time
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from decimal import Decimal

from src.lib.metrics_collector import (
    MetricsCollector, 
    LatencyTracker, 
    MetricSnapshot,
    get_metrics_collector
)


class TestLatencyTracker:
    """Test latency tracking with percentile calculations"""
    
    def test_empty_tracker(self):
        """Test empty tracker returns zero percentiles"""
        tracker = LatencyTracker()
        percentiles = tracker.get_percentiles()
        
        assert percentiles["p50"] == 0.0
        assert percentiles["p95"] == 0.0
        assert percentiles["p99"] == 0.0
        assert tracker.get_count() == 0
    
    def test_single_sample(self):
        """Test tracker with single sample"""
        tracker = LatencyTracker()
        tracker.record_latency(100.0)
        
        percentiles = tracker.get_percentiles()
        assert percentiles["p50"] == 100.0
        assert percentiles["p95"] == 100.0
        assert percentiles["p99"] == 100.0
        assert tracker.get_count() == 1
    
    def test_multiple_samples(self):
        """Test tracker with multiple samples"""
        tracker = LatencyTracker()
        
        # Add samples: 10, 20, 30, 40, 50, 60, 70, 80, 90, 100
        for i in range(1, 11):
            tracker.record_latency(i * 10.0)
        
        percentiles = tracker.get_percentiles()
        
        # With 10 samples:
        # P50 = 5th element (50.0)
        # P95 = 9th element (90.0) 
        # P99 = 10th element (100.0)
        assert percentiles["p50"] == 50.0
        assert percentiles["p95"] == 90.0
        assert percentiles["p99"] == 100.0
        assert tracker.get_count() == 10
    
    def test_max_samples_eviction(self):
        """Test LRU eviction when max samples reached"""
        tracker = LatencyTracker(max_samples=5)
        
        # Add 10 samples, should keep only last 5
        for i in range(1, 11):
            tracker.record_latency(i * 10.0)
        
        assert tracker.get_count() == 5
        
        # Should contain samples 60, 70, 80, 90, 100
        percentiles = tracker.get_percentiles()
        assert percentiles["p50"] == 80.0  # Middle of last 5


class TestMetricsCollector:
    """Test comprehensive metrics collection"""
    
    def test_initialization(self):
        """Test metrics collector initialization"""
        collector = MetricsCollector()
        
        assert collector.start_time > 0
        assert collector.api_latency is not None
        assert collector.position_calc_latency is not None
        assert isinstance(collector.counters, dict)
        assert isinstance(collector.gauges, dict)
        assert len(collector.snapshots) == 0
    
    def test_api_request_recording(self):
        """Test API request metrics recording"""
        collector = MetricsCollector()
        
        # Record multiple requests
        collector.record_api_request("analyze", "POST", 200, 150.5)
        collector.record_api_request("positions", "GET", 200, 75.2)
        collector.record_api_request("health", "GET", 200, 5.1)
        
        # Check counters
        assert collector.counters["api_requests_total"] == 3
        assert collector.counters["api_requests_analyze_POST"] == 1
        assert collector.counters["api_requests_positions_GET"] == 1
        assert collector.counters["api_responses_200"] == 3
        
        # Check latency tracking
        percentiles = collector.api_latency.get_percentiles()
        assert percentiles["p50"] == 75.2  # Middle value
        assert collector.gauges["api_last_request_latency_ms"] == 5.1  # Last recorded
    
    def test_position_calculation_recording(self):
        """Test position calculation metrics"""
        collector = MetricsCollector()
        
        collector.record_position_calculation("wallet1", 5, 250.0)
        collector.record_position_calculation("wallet2", 12, 180.0)
        
        assert collector.counters["position_calculations_total"] == 2
        assert collector.counters["positions_calculated_total"] == 17
        assert collector.gauges["position_last_calc_time_ms"] == 180.0
        
        percentiles = collector.position_calc_latency.get_percentiles()
        assert 180.0 in [percentiles["p50"], percentiles["p95"]]
    
    def test_cache_refresh_recording(self):
        """Test cache refresh metrics"""
        collector = MetricsCollector()
        
        collector.record_cache_refresh("position", 50.0, True)
        collector.record_cache_refresh("snapshot", 25.0, False)
        
        assert collector.counters["cache_refresh_total"] == 2
        assert collector.counters["cache_refresh_position"] == 1
        assert collector.counters["cache_refresh_snapshot"] == 1
        assert collector.counters["cache_refresh_success"] == 1
        assert collector.counters["cache_refresh_errors"] == 1
    
    @patch('psutil.Process')
    def test_memory_usage(self, mock_process):
        """Test memory usage monitoring"""
        # Mock memory info
        mock_memory = Mock()
        mock_memory.rss = 512 * 1024 * 1024  # 512 MB
        mock_memory.vms = 1024 * 1024 * 1024  # 1 GB
        
        mock_process_instance = Mock()
        mock_process_instance.memory_info.return_value = mock_memory
        mock_process_instance.memory_percent.return_value = 15.5
        mock_process.return_value = mock_process_instance
        
        collector = MetricsCollector()
        memory = collector.get_memory_usage()
        
        assert memory["rss_mb"] == 512.0
        assert memory["vms_mb"] == 1024.0
        assert memory["percent"] == 15.5
    
    def test_cache_metrics_update(self):
        """Test cache metrics integration"""
        collector = MetricsCollector()
        
        cache_stats = {
            "cache_hits": 150,
            "cache_misses": 50,
            "lru_size": 1200,
            "backend": "redis"
        }
        
        collector.update_cache_metrics(cache_stats)
        
        assert collector.cache_metrics == cache_stats
        assert collector.gauges["cache_hit_rate_pct"] == 75.0  # 150/(150+50) * 100
    
    def test_prometheus_metrics_generation(self):
        """Test Prometheus metrics text generation"""
        collector = MetricsCollector()
        
        # Add some sample data
        collector.record_api_request("test", "GET", 200, 100.0)
        collector.record_position_calculation("wallet1", 3, 50.0)
        collector.update_cache_metrics({"cache_hits": 10, "cache_misses": 2, "lru_size": 100})
        
        metrics_text = collector.get_prometheus_metrics()
        
        # Check required metrics are present
        assert "walletdoctor_uptime_seconds" in metrics_text
        assert "walletdoctor_api_requests_total 1" in metrics_text
        assert "walletdoctor_api_latency_p95_ms 100.00" in metrics_text
        assert "walletdoctor_cache_hits_total 10" in metrics_text
        assert "walletdoctor_cache_hit_rate_pct 83.33" in metrics_text
        assert "walletdoctor_position_calculations_total 1" in metrics_text
        
        # Check format compliance
        lines = metrics_text.split('\n')
        help_lines = [l for l in lines if l.startswith("# HELP")]
        type_lines = [l for l in lines if l.startswith("# TYPE")]
        
        assert len(help_lines) > 5  # Should have multiple help lines
        assert len(type_lines) > 5  # Should have multiple type lines
    
    @patch('psutil.Process')
    def test_alert_thresholds(self, mock_process):
        """Test alert threshold checking"""
        # Mock memory
        mock_memory = Mock()
        mock_memory.rss = 700 * 1024 * 1024  # 700 MB (over threshold)
        mock_memory.vms = 1024 * 1024 * 1024
        
        mock_process_instance = Mock()
        mock_process_instance.memory_info.return_value = mock_memory
        mock_process_instance.memory_percent.return_value = 25.0
        mock_process.return_value = mock_process_instance
        
        collector = MetricsCollector()
        
        # Add high latency samples
        for _ in range(10):
            collector.api_latency.record_latency(250.0)  # Over 200ms threshold
        
        alerts = collector.get_alert_status()
        
        # Should have critical alerts
        assert len(alerts["critical"]) == 2  # Latency + Memory
        assert any("API P95 latency" in alert["message"] for alert in alerts["critical"])
        assert any("Memory RSS" in alert["message"] for alert in alerts["critical"])
    
    @patch('psutil.Process')
    def test_health_summary(self, mock_process):
        """Test comprehensive health summary"""
        # Mock memory
        mock_memory = Mock()
        mock_memory.rss = 300 * 1024 * 1024  # 300 MB (healthy)
        mock_memory.vms = 800 * 1024 * 1024
        
        mock_process_instance = Mock()
        mock_process_instance.memory_info.return_value = mock_memory
        mock_process_instance.memory_percent.return_value = 10.0
        mock_process.return_value = mock_process_instance
        
        collector = MetricsCollector()
        
        # Add healthy metrics
        collector.record_api_request("test", "GET", 200, 50.0)
        collector.update_cache_metrics({"cache_hits": 90, "cache_misses": 10, "lru_size": 500})
        
        health = collector.get_health_summary()
        
        assert health["status"] == "healthy"
        assert "timestamp" in health
        assert health["metrics"]["api_p95_latency_ms"] == 50.0
        assert health["metrics"]["memory_rss_mb"] == 300.0
        assert health["metrics"]["cache_hit_rate_pct"] == 90.0
        assert len(health["alerts"]["critical"]) == 0
    
    def test_snapshot_creation(self):
        """Test metric snapshot creation and storage"""
        collector = MetricsCollector()
        
        # Add sample data
        collector.record_api_request("test", "GET", 200, 100.0)
        collector.record_position_calculation("wallet1", 5, 200.0)
        collector.update_cache_metrics({
            "cache_hits": 80, 
            "cache_misses": 20, 
            "lru_size": 1500,
            "stale_serves": 5
        })
        
        snapshot = collector.create_snapshot()
        
        assert isinstance(snapshot, MetricSnapshot)
        assert snapshot.api_request_count == 1
        assert snapshot.api_p95_latency_ms == 100.0
        assert snapshot.cache_hit_rate_pct == 80.0
        assert snapshot.cache_stale_serve_rate_pct == 6.25  # 5/80 * 100
        assert snapshot.cache_entries == 1500
        assert snapshot.position_calc_p95_ms == 200.0
        
        # Check snapshot was stored
        assert len(collector.snapshots) == 1
        assert collector.snapshots[0] == snapshot


class TestMetricsIntegration:
    """Test metrics integration with real components"""
    
    @patch('src.lib.position_cache.get_position_cache')
    def test_cache_metrics_integration(self, mock_get_cache):
        """Test integration with position cache"""
        # Mock cache with stats
        mock_cache = Mock()
        mock_cache.get_stats.return_value = {
            "cache_hits": 100,
            "cache_misses": 25,
            "lru_size": 800,
            "backend": "redis",
            "hit_rate": 80.0
        }
        mock_get_cache.return_value = mock_cache
        
        collector = get_metrics_collector()
        cache_stats = mock_cache.get_stats()
        collector.update_cache_metrics(cache_stats)
        
        # Verify metrics are updated
        assert collector.cache_metrics["cache_hits"] == 100
        assert collector.gauges["cache_hit_rate_pct"] == 80.0
    
    def test_global_collector_singleton(self):
        """Test global collector is singleton"""
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()
        
        assert collector1 is collector2
        
        # Verify state is shared
        collector1.record_api_request("test", "GET", 200, 50.0)
        assert collector2.counters["api_requests_total"] == 1


class TestMetricsAPI:
    """Test metrics API endpoints"""
    
    def test_prometheus_endpoint_format(self):
        """Test Prometheus endpoint returns valid format"""
        collector = MetricsCollector()
        collector.record_api_request("test", "GET", 200, 100.0)
        
        metrics_text = collector.get_prometheus_metrics()
        
        # Check Prometheus format compliance
        lines = metrics_text.split('\n')
        
        # Should have HELP and TYPE comments
        help_lines = [l for l in lines if l.startswith("# HELP")]
        type_lines = [l for l in lines if l.startswith("# TYPE")]
        
        assert len(help_lines) > 0
        assert len(type_lines) > 0
        
        # Should have actual metric values
        metric_lines = [l for l in lines if l and not l.startswith("#")]
        assert len(metric_lines) > 0
        
        # Check specific metric format
        uptime_metrics = [l for l in metric_lines if l.startswith("walletdoctor_uptime_seconds")]
        assert len(uptime_metrics) == 1
        assert " " in uptime_metrics[0]  # Should have space between name and value
    
    def test_alert_status_format(self):
        """Test alert status endpoint format"""
        collector = MetricsCollector()
        
        # Add data that should trigger warnings
        collector.api_latency.record_latency(160.0)  # Warning threshold
        collector.update_cache_metrics({"cache_hits": 60, "cache_misses": 40, "lru_size": 100})  # 60% hit rate
        
        alerts = collector.get_alert_status()
        
        # Check structure
        assert "critical" in alerts
        assert "warning" in alerts  
        assert "healthy" in alerts
        
        # Should have warning for cache hit rate
        assert len(alerts["warning"]) >= 1
        
        # Check alert object structure
        if alerts["warning"]:
            alert = alerts["warning"][0]
            assert "metric" in alert
            assert "value" in alert
            assert "threshold" in alert
            assert "message" in alert


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 