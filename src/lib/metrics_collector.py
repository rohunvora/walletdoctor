#!/usr/bin/env python3
"""
Metrics Collector for WalletDoctor API
WAL-608: Comprehensive monitoring for position cache and API performance

Collects Prometheus-ready metrics for:
- API request latency (P95 tracking)
- Position cache hit rates and staleness
- Memory usage (RSS tracking)
- Position calculation times
"""

import time
import psutil
import os
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque, defaultdict
from threading import Lock
import json

logger = logging.getLogger(__name__)


@dataclass
class MetricSnapshot:
    """Snapshot of metrics at a point in time"""
    timestamp: datetime
    api_request_count: int
    api_p95_latency_ms: float
    cache_hit_rate_pct: float
    cache_stale_serve_rate_pct: float
    memory_rss_mb: float
    cache_entries: int
    position_calc_p95_ms: float


class LatencyTracker:
    """Tracks request latency with percentile calculations"""
    
    def __init__(self, max_samples: int = 1000):
        self.samples: deque = deque(maxlen=max_samples)
        self.lock = Lock()
    
    def record_latency(self, latency_ms: float):
        """Record a latency sample"""
        with self.lock:
            self.samples.append(latency_ms)
    
    def get_percentiles(self) -> Dict[str, float]:
        """Get latency percentiles"""
        with self.lock:
            if not self.samples:
                return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
            
            sorted_samples = sorted(self.samples)
            n = len(sorted_samples)
            
            return {
                "p50": sorted_samples[int(n * 0.5)] if n > 0 else 0.0,
                "p95": sorted_samples[int(n * 0.95)] if n > 1 else sorted_samples[0] if n > 0 else 0.0,
                "p99": sorted_samples[int(n * 0.99)] if n > 2 else sorted_samples[-1] if n > 0 else 0.0
            }
    
    def get_count(self) -> int:
        """Get total number of samples"""
        with self.lock:
            return len(self.samples)


class MetricsCollector:
    """
    Central metrics collection for WalletDoctor API
    
    Tracks:
    - API request latency and counts
    - Position cache performance
    - Memory usage
    - Position calculation performance
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.process = psutil.Process(os.getpid())
        
        # Latency tracking
        self.api_latency = LatencyTracker()
        self.position_calc_latency = LatencyTracker()
        
        # Counters
        self.counters = defaultdict(int)
        self.gauges = defaultdict(float)
        
        # Cache metrics (refreshed from cache)
        self.cache_metrics = {}
        
        # Historical snapshots for trends
        self.snapshots: deque = deque(maxlen=100)  # Keep last 100 snapshots
        
        # Lock for thread safety
        self.lock = Lock()
        
        logger.info("Metrics collector initialized")
    
    def record_api_request(self, endpoint: str, method: str, status_code: int, latency_ms: float):
        """Record API request metrics"""
        with self.lock:
            # Increment counters
            self.counters[f"api_requests_total"] += 1
            self.counters[f"api_requests_{endpoint}_{method}"] += 1
            self.counters[f"api_responses_{status_code}"] += 1
            
            # Record latency
            self.api_latency.record_latency(latency_ms)
            
            # Update gauges
            self.gauges[f"api_last_request_latency_ms"] = latency_ms
    
    def record_position_calculation(self, wallet: str, positions_count: int, calc_time_ms: float):
        """Record position calculation metrics"""
        with self.lock:
            self.counters["position_calculations_total"] += 1
            self.counters["positions_calculated_total"] += positions_count
            self.position_calc_latency.record_latency(calc_time_ms)
            self.gauges["position_last_calc_time_ms"] = calc_time_ms
    
    def record_cache_refresh(self, cache_type: str, refresh_time_ms: float, success: bool):
        """Record cache refresh metrics"""
        with self.lock:
            self.counters[f"cache_refresh_total"] += 1
            self.counters[f"cache_refresh_{cache_type}"] += 1
            if success:
                self.counters[f"cache_refresh_success"] += 1
            else:
                self.counters[f"cache_refresh_errors"] += 1
            self.gauges[f"cache_last_refresh_time_ms"] = refresh_time_ms
    
    def update_cache_metrics(self, cache_stats: Dict[str, Any]):
        """Update cache metrics from position cache"""
        with self.lock:
            self.cache_metrics = cache_stats.copy()
            
            # Update derived metrics
            if "cache_hits" in cache_stats and "cache_misses" in cache_stats:
                total_requests = cache_stats["cache_hits"] + cache_stats["cache_misses"]
                if total_requests > 0:
                    hit_rate = (cache_stats["cache_hits"] / total_requests) * 100
                    self.gauges["cache_hit_rate_pct"] = hit_rate
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage"""
        try:
            memory_info = self.process.memory_info()
            return {
                "rss_mb": memory_info.rss / (1024 * 1024),
                "vms_mb": memory_info.vms / (1024 * 1024),
                "percent": self.process.memory_percent()
            }
        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return {"rss_mb": 0.0, "vms_mb": 0.0, "percent": 0.0}
    
    def get_prometheus_metrics(self) -> str:
        """
        Generate Prometheus metrics in text format
        
        Returns formatted metrics for scraping
        """
        lines = []
        
        # Uptime
        uptime_seconds = time.time() - self.start_time
        lines.append("# HELP walletdoctor_uptime_seconds Total uptime")
        lines.append("# TYPE walletdoctor_uptime_seconds counter")
        lines.append(f"walletdoctor_uptime_seconds {uptime_seconds:.2f}")
        lines.append("")
        
        # API request metrics
        lines.append("# HELP walletdoctor_api_requests_total Total API requests")
        lines.append("# TYPE walletdoctor_api_requests_total counter")
        lines.append(f"walletdoctor_api_requests_total {self.counters.get('api_requests_total', 0)}")
        lines.append("")
        
        # API latency percentiles
        latency_percentiles = self.api_latency.get_percentiles()
        for percentile, value in latency_percentiles.items():
            lines.append(f"# HELP walletdoctor_api_latency_{percentile}_ms API latency {percentile}")
            lines.append(f"# TYPE walletdoctor_api_latency_{percentile}_ms gauge")
            lines.append(f"walletdoctor_api_latency_{percentile}_ms {value:.2f}")
            lines.append("")
        
        # Position cache metrics
        lines.append("# HELP walletdoctor_cache_hits_total Cache hits")
        lines.append("# TYPE walletdoctor_cache_hits_total counter")
        lines.append(f"walletdoctor_cache_hits_total {self.cache_metrics.get('cache_hits', 0)}")
        lines.append("")
        
        lines.append("# HELP walletdoctor_cache_misses_total Cache misses")
        lines.append("# TYPE walletdoctor_cache_misses_total counter")
        lines.append(f"walletdoctor_cache_misses_total {self.cache_metrics.get('cache_misses', 0)}")
        lines.append("")
        
        lines.append("# HELP walletdoctor_cache_hit_rate_pct Cache hit rate percentage")
        lines.append("# TYPE walletdoctor_cache_hit_rate_pct gauge")
        lines.append(f"walletdoctor_cache_hit_rate_pct {self.gauges.get('cache_hit_rate_pct', 0.0):.2f}")
        lines.append("")
        
        lines.append("# HELP walletdoctor_cache_entries Current cache entries")
        lines.append("# TYPE walletdoctor_cache_entries gauge")
        lines.append(f"walletdoctor_cache_entries {self.cache_metrics.get('lru_size', 0)}")
        lines.append("")
        
        # Memory metrics
        memory = self.get_memory_usage()
        lines.append("# HELP walletdoctor_memory_rss_mb Resident Set Size in MB")
        lines.append("# TYPE walletdoctor_memory_rss_mb gauge")
        lines.append(f"walletdoctor_memory_rss_mb {memory['rss_mb']:.2f}")
        lines.append("")
        
        lines.append("# HELP walletdoctor_memory_percent Memory usage percentage")
        lines.append("# TYPE walletdoctor_memory_percent gauge")
        lines.append(f"walletdoctor_memory_percent {memory['percent']:.2f}")
        lines.append("")
        
        # Position calculation metrics
        lines.append("# HELP walletdoctor_position_calculations_total Total position calculations")
        lines.append("# TYPE walletdoctor_position_calculations_total counter")
        lines.append(f"walletdoctor_position_calculations_total {self.counters.get('position_calculations_total', 0)}")
        lines.append("")
        
        position_percentiles = self.position_calc_latency.get_percentiles()
        for percentile, value in position_percentiles.items():
            lines.append(f"# HELP walletdoctor_position_calc_{percentile}_ms Position calculation {percentile}")
            lines.append(f"# TYPE walletdoctor_position_calc_{percentile}_ms gauge")
            lines.append(f"walletdoctor_position_calc_{percentile}_ms {value:.2f}")
            lines.append("")
        
        # HTTP status codes
        for key, value in self.counters.items():
            if key.startswith("api_responses_"):
                status_code = key.split("_")[-1]
                lines.append(f"# HELP walletdoctor_api_responses_{status_code} HTTP {status_code} responses")
                lines.append(f"# TYPE walletdoctor_api_responses_{status_code} counter")
                lines.append(f"walletdoctor_api_responses_{status_code} {value}")
                lines.append("")
        
        return "\n".join(lines)
    
    def create_snapshot(self) -> MetricSnapshot:
        """Create a metrics snapshot for trending"""
        memory = self.get_memory_usage()
        latency_percentiles = self.api_latency.get_percentiles()
        position_percentiles = self.position_calc_latency.get_percentiles()
        
        # Calculate stale serve rate
        stale_serves = self.cache_metrics.get("stale_serves", 0)
        total_serves = self.cache_metrics.get("cache_hits", 0)
        stale_rate = (stale_serves / total_serves * 100) if total_serves > 0 else 0.0
        
        snapshot = MetricSnapshot(
            timestamp=datetime.utcnow(),
            api_request_count=self.counters.get('api_requests_total', 0),
            api_p95_latency_ms=latency_percentiles["p95"],
            cache_hit_rate_pct=self.gauges.get('cache_hit_rate_pct', 0.0),
            cache_stale_serve_rate_pct=stale_rate,
            memory_rss_mb=memory["rss_mb"],
            cache_entries=self.cache_metrics.get('lru_size', 0),
            position_calc_p95_ms=position_percentiles["p95"]
        )
        
        with self.lock:
            self.snapshots.append(snapshot)
        
        return snapshot
    
    def get_alert_status(self) -> Dict[str, Any]:
        """
        Check current metrics against alert thresholds
        
        Returns alert status for monitoring systems
        """
        memory = self.get_memory_usage()
        latency_percentiles = self.api_latency.get_percentiles()
        
        alerts = {
            "critical": [],
            "warning": [],
            "healthy": []
        }
        
        # P95 latency > 200ms (critical)
        if latency_percentiles["p95"] > 200:
            alerts["critical"].append({
                "metric": "api_p95_latency",
                "value": latency_percentiles["p95"],
                "threshold": 200,
                "message": f"API P95 latency {latency_percentiles['p95']:.1f}ms exceeds 200ms threshold"
            })
        elif latency_percentiles["p95"] > 150:
            alerts["warning"].append({
                "metric": "api_p95_latency",
                "value": latency_percentiles["p95"],
                "threshold": 150,
                "message": f"API P95 latency {latency_percentiles['p95']:.1f}ms approaching threshold"
            })
        else:
            alerts["healthy"].append("api_p95_latency")
        
        # RSS > 600MB (critical)
        if memory["rss_mb"] > 600:
            alerts["critical"].append({
                "metric": "memory_rss",
                "value": memory["rss_mb"],
                "threshold": 600,
                "message": f"Memory RSS {memory['rss_mb']:.1f}MB exceeds 600MB threshold"
            })
        elif memory["rss_mb"] > 450:
            alerts["warning"].append({
                "metric": "memory_rss",
                "value": memory["rss_mb"],
                "threshold": 450,
                "message": f"Memory RSS {memory['rss_mb']:.1f}MB approaching threshold"
            })
        else:
            alerts["healthy"].append("memory_rss")
        
        # Cache entries > 2000 (warning)
        cache_entries = self.cache_metrics.get('lru_size', 0)
        if cache_entries > 2000:
            alerts["warning"].append({
                "metric": "cache_entries",
                "value": cache_entries,
                "threshold": 2000,
                "message": f"Cache entries {cache_entries} exceeds expected maximum"
            })
        else:
            alerts["healthy"].append("cache_entries")
        
        # Cache hit rate < 70% (warning)
        hit_rate = self.gauges.get('cache_hit_rate_pct', 0.0)
        if hit_rate < 70 and self.api_latency.get_count() > 10:  # Only alert if we have enough samples
            alerts["warning"].append({
                "metric": "cache_hit_rate",
                "value": hit_rate,
                "threshold": 70,
                "message": f"Cache hit rate {hit_rate:.1f}% below 70% threshold"
            })
        else:
            alerts["healthy"].append("cache_hit_rate")
        
        return alerts
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary for dashboards"""
        snapshot = self.create_snapshot()
        alerts = self.get_alert_status()
        
        return {
            "timestamp": snapshot.timestamp.isoformat(),
            "status": "critical" if alerts["critical"] else "warning" if alerts["warning"] else "healthy",
            "metrics": {
                "api_requests_total": snapshot.api_request_count,
                "api_p95_latency_ms": snapshot.api_p95_latency_ms,
                "cache_hit_rate_pct": snapshot.cache_hit_rate_pct,
                "memory_rss_mb": snapshot.memory_rss_mb,
                "cache_entries": snapshot.cache_entries,
                "position_calc_p95_ms": snapshot.position_calc_p95_ms
            },
            "alerts": alerts,
            "cache_backend": self.cache_metrics.get("backend", "unknown"),
            "uptime_seconds": time.time() - self.start_time
        }


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create global metrics collector"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def timing_decorator(metric_name: str):
    """Decorator to time function execution and record metrics"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                execution_time = (time.time() - start_time) * 1000  # Convert to ms
                collector = get_metrics_collector()
                if metric_name == "position_calculation":
                    # Extract position count if available
                    positions_count = len(result) if hasattr(result, '__len__') else 1
                    collector.record_position_calculation("", positions_count, execution_time)
                else:
                    collector.gauges[f"{metric_name}_last_execution_ms"] = execution_time
        return wrapper
    return decorator 