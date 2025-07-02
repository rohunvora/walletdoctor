#!/usr/bin/env python3
"""
Memory Leak Guardrail System
WAL-609: Proactive memory management with auto-restart

Provides:
- Self-check endpoint with memory and cache monitoring
- Configurable thresholds for RSS and cache size
- Auto-restart triggers when limits exceeded
- Load testing support with baseline tracking
"""

import os
import sys
import time
import psutil
import logging
import signal
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from threading import Lock

# Type hints for mock classes
class MockMetricsCollector:
    def __init__(self):
        self.counters = {}

class MockPositionCache:
    def get_stats(self):
        return {"lru_size": 0, "hit_rate": 0.0}

# Try importing with fallbacks
try:
    from src.lib.metrics_collector import get_metrics_collector
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("metrics_collector not available, using mock")
    
    def get_metrics_collector() -> Any:
        return MockMetricsCollector()

try:
    from src.lib.position_cache import get_position_cache
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("position_cache not available, using mock")
    
    def get_position_cache() -> Any:
        return MockPositionCache()

logger = logging.getLogger(__name__)

# Configuration from environment
MEMORY_RSS_THRESHOLD_MB = int(os.getenv("MEMORY_RSS_THRESHOLD_MB", "700"))  # 700MB default
CACHE_ENTRIES_THRESHOLD = int(os.getenv("CACHE_ENTRIES_THRESHOLD", "2200"))  # 2.2k entries default
AUTO_RESTART_ENABLED = os.getenv("AUTO_RESTART_ENABLED", "false").lower() == "true"
MEMORY_CHECK_INTERVAL_SEC = int(os.getenv("MEMORY_CHECK_INTERVAL_SEC", "60"))  # 1 minute default
BASELINE_SAMPLE_COUNT = int(os.getenv("BASELINE_SAMPLE_COUNT", "10"))  # Samples for baseline
LEAK_DETECTION_WINDOW_MIN = int(os.getenv("LEAK_DETECTION_WINDOW_MIN", "10"))  # 10 min detection window


@dataclass
class MemorySnapshot:
    """Memory usage snapshot for trend analysis"""
    timestamp: datetime
    rss_mb: float
    vms_mb: float
    cache_entries: int
    cache_hit_rate: float
    api_requests_total: int
    process_id: int


@dataclass
class LeakDetectionResult:
    """Result of memory leak detection analysis"""
    is_leak_detected: bool
    growth_rate_mb_per_min: float
    time_to_threshold_min: Optional[float]
    current_rss_mb: float
    threshold_rss_mb: float
    recommendation: str
    severity: str  # "normal", "warning", "critical"


class MemoryGuardrail:
    """
    Memory leak detection and auto-restart system
    
    Features:
    - Continuous memory monitoring
    - Leak detection with trend analysis
    - Configurable auto-restart triggers
    - Load testing baseline establishment
    """
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.snapshots: List[MemorySnapshot] = []
        self.baseline_rss_mb: Optional[float] = None
        self.baseline_established = False
        self.lock = Lock()
        
        # Restart tracking
        self.restart_count = 0
        self.last_restart_time: Optional[datetime] = None
        
        logger.info(f"Memory guardrail initialized (PID: {os.getpid()})")
        logger.info(f"Thresholds: RSS {MEMORY_RSS_THRESHOLD_MB}MB, Cache {CACHE_ENTRIES_THRESHOLD} entries")
        logger.info(f"Auto-restart: {'enabled' if AUTO_RESTART_ENABLED else 'disabled'}")
    
    def take_snapshot(self) -> MemorySnapshot:
        """Take a memory usage snapshot"""
        try:
            # Get memory info
            memory_info = self.process.memory_info()
            
            # Get cache stats
            cache = get_position_cache()
            cache_stats = cache.get_stats()
            
            # Get metrics
            collector = get_metrics_collector()
            
            snapshot = MemorySnapshot(
                timestamp=datetime.utcnow(),
                rss_mb=memory_info.rss / (1024 * 1024),
                vms_mb=memory_info.vms / (1024 * 1024),
                cache_entries=cache_stats.get("lru_size", 0),
                cache_hit_rate=cache_stats.get("hit_rate", 0.0),
                api_requests_total=collector.counters.get("api_requests_total", 0),
                process_id=os.getpid()
            )
            
            with self.lock:
                self.snapshots.append(snapshot)
                
                # Keep only recent snapshots (last hour)
                cutoff_time = datetime.utcnow() - timedelta(hours=1)
                self.snapshots = [s for s in self.snapshots if s.timestamp > cutoff_time]
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error taking memory snapshot: {e}")
            raise
    
    def establish_baseline(self) -> bool:
        """
        Establish memory baseline for leak detection
        
        Returns True when baseline is established
        """
        if self.baseline_established:
            return True
        
        with self.lock:
            if len(self.snapshots) >= BASELINE_SAMPLE_COUNT:
                # Calculate baseline from first N samples
                baseline_samples = self.snapshots[:BASELINE_SAMPLE_COUNT]
                self.baseline_rss_mb = sum(s.rss_mb for s in baseline_samples) / len(baseline_samples)
                self.baseline_established = True
                
                logger.info(f"Memory baseline established: {self.baseline_rss_mb:.1f}MB from {len(baseline_samples)} samples")
                return True
        
        return False
    
    def detect_memory_leak(self) -> LeakDetectionResult:
        """
        Analyze memory usage trends to detect potential leaks
        
        Uses linear regression on recent samples to detect growth rate
        """
        with self.lock:
            if len(self.snapshots) < 3:
                return LeakDetectionResult(
                    is_leak_detected=False,
                    growth_rate_mb_per_min=0.0,
                    time_to_threshold_min=None,
                    current_rss_mb=self.snapshots[-1].rss_mb if self.snapshots else 0.0,
                    threshold_rss_mb=MEMORY_RSS_THRESHOLD_MB,
                    recommendation="Insufficient data for leak detection",
                    severity="normal"
                )
            
            # Use samples from detection window
            cutoff_time = datetime.utcnow() - timedelta(minutes=LEAK_DETECTION_WINDOW_MIN)
            recent_samples = [s for s in self.snapshots if s.timestamp > cutoff_time]
            
            if len(recent_samples) < 3:
                return LeakDetectionResult(
                    is_leak_detected=False,
                    growth_rate_mb_per_min=0.0,
                    time_to_threshold_min=None,
                    current_rss_mb=self.snapshots[-1].rss_mb,
                    threshold_rss_mb=MEMORY_RSS_THRESHOLD_MB,
                    recommendation="Insufficient recent data",
                    severity="normal"
                )
            
            # Calculate growth rate using linear regression
            current_rss = recent_samples[-1].rss_mb
            growth_rate = self._calculate_growth_rate(recent_samples)
            
            # Determine if leak is detected
            is_leak = growth_rate > 5.0  # > 5MB/min growth considered a leak
            
            # Calculate time to threshold
            time_to_threshold = None
            if growth_rate > 0:
                remaining_mb = MEMORY_RSS_THRESHOLD_MB - current_rss
                if remaining_mb > 0:
                    time_to_threshold = remaining_mb / growth_rate
            
            # Determine severity and recommendation
            severity = "normal"
            recommendation = "Memory usage is stable"
            
            if current_rss > MEMORY_RSS_THRESHOLD_MB:
                severity = "critical"
                recommendation = "IMMEDIATE RESTART REQUIRED - Memory threshold exceeded"
            elif is_leak and time_to_threshold and time_to_threshold < 10:
                severity = "critical"
                recommendation = f"RESTART RECOMMENDED - Will exceed threshold in {time_to_threshold:.1f} minutes"
            elif is_leak and time_to_threshold and time_to_threshold < 30:
                severity = "warning"
                recommendation = f"Monitor closely - Will exceed threshold in {time_to_threshold:.1f} minutes"
            elif growth_rate > 2.0:
                severity = "warning"
                recommendation = "Memory growth detected - monitor for leaks"
            
            return LeakDetectionResult(
                is_leak_detected=is_leak,
                growth_rate_mb_per_min=growth_rate,
                time_to_threshold_min=time_to_threshold,
                current_rss_mb=current_rss,
                threshold_rss_mb=MEMORY_RSS_THRESHOLD_MB,
                recommendation=recommendation,
                severity=severity
            )
    
    def _calculate_growth_rate(self, samples: List[MemorySnapshot]) -> float:
        """Calculate memory growth rate in MB/min using linear regression"""
        if len(samples) < 2:
            return 0.0
        
        # Convert timestamps to minutes from first sample
        start_time = samples[0].timestamp
        x_values = [(s.timestamp - start_time).total_seconds() / 60.0 for s in samples]
        y_values = [s.rss_mb for s in samples]
        
        # Simple linear regression
        n = len(samples)
        sum_x = sum(x_values)
        sum_y = sum(y_values)
        sum_xy = sum(x * y for x, y in zip(x_values, y_values))
        sum_x2 = sum(x * x for x in x_values)
        
        # Calculate slope (growth rate)
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return 0.0
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        return slope
    
    def check_thresholds(self) -> Dict[str, Any]:
        """
        Check current memory and cache against thresholds
        
        Returns status and recommendations
        """
        snapshot = self.take_snapshot()
        leak_result = self.detect_memory_leak()
        
        # Check individual thresholds
        rss_exceeded = snapshot.rss_mb > MEMORY_RSS_THRESHOLD_MB
        cache_exceeded = snapshot.cache_entries > CACHE_ENTRIES_THRESHOLD
        
        # Determine overall status
        if rss_exceeded or cache_exceeded:
            status = "critical"
        elif leak_result.severity == "warning":
            status = "warning"
        else:
            status = "healthy"
        
        # Build recommendations
        recommendations = []
        if rss_exceeded:
            recommendations.append(f"RSS memory ({snapshot.rss_mb:.1f}MB) exceeds threshold ({MEMORY_RSS_THRESHOLD_MB}MB)")
        if cache_exceeded:
            recommendations.append(f"Cache entries ({snapshot.cache_entries}) exceeds threshold ({CACHE_ENTRIES_THRESHOLD})")
        
        recommendations.append(leak_result.recommendation)
        
        return {
            "status": status,
            "timestamp": snapshot.timestamp.isoformat(),
            "current_memory": {
                "rss_mb": snapshot.rss_mb,
                "vms_mb": snapshot.vms_mb,
                "cache_entries": snapshot.cache_entries,
                "cache_hit_rate": snapshot.cache_hit_rate
            },
            "thresholds": {
                "rss_mb": MEMORY_RSS_THRESHOLD_MB,
                "cache_entries": CACHE_ENTRIES_THRESHOLD
            },
            "leak_detection": {
                "is_leak_detected": leak_result.is_leak_detected,
                "growth_rate_mb_per_min": leak_result.growth_rate_mb_per_min,
                "time_to_threshold_min": leak_result.time_to_threshold_min,
                "severity": leak_result.severity
            },
            "baseline": {
                "established": self.baseline_established,
                "baseline_rss_mb": self.baseline_rss_mb
            },
            "recommendations": recommendations,
            "auto_restart_enabled": AUTO_RESTART_ENABLED,
            "process_id": os.getpid()
        }
    
    def should_restart(self) -> tuple[bool, str]:
        """
        Determine if process should restart based on current conditions
        
        Returns (should_restart, reason)
        """
        if not AUTO_RESTART_ENABLED:
            return False, "Auto-restart disabled"
        
        # Rate limiting - don't restart too frequently
        if self.last_restart_time:
            time_since_restart = datetime.utcnow() - self.last_restart_time
            if time_since_restart < timedelta(minutes=5):
                return False, f"Too soon since last restart ({time_since_restart.total_seconds():.0f}s ago)"
        
        snapshot = self.take_snapshot()
        leak_result = self.detect_memory_leak()
        
        # Check hard thresholds
        if snapshot.rss_mb > MEMORY_RSS_THRESHOLD_MB:
            return True, f"RSS memory ({snapshot.rss_mb:.1f}MB) exceeds threshold ({MEMORY_RSS_THRESHOLD_MB}MB)"
        
        if snapshot.cache_entries > CACHE_ENTRIES_THRESHOLD:
            return True, f"Cache entries ({snapshot.cache_entries}) exceeds threshold ({CACHE_ENTRIES_THRESHOLD})"
        
        # Check leak detection
        if leak_result.severity == "critical" and leak_result.time_to_threshold_min and leak_result.time_to_threshold_min < 5:
            return True, f"Memory leak detected - will exceed threshold in {leak_result.time_to_threshold_min:.1f} minutes"
        
        return False, "All thresholds within limits"
    
    def trigger_restart(self, reason: str) -> None:
        """
        Trigger graceful process restart
        
        Logs the reason and sends SIGTERM to self
        """
        self.restart_count += 1
        self.last_restart_time = datetime.utcnow()
        
        logger.critical(f"TRIGGERING RESTART #{self.restart_count}: {reason}")
        logger.critical(f"Process PID: {os.getpid()}")
        
        # Log final memory state
        try:
            snapshot = self.take_snapshot()
            logger.critical(f"Final memory state: RSS={snapshot.rss_mb:.1f}MB, Cache={snapshot.cache_entries} entries")
        except Exception as e:
            logger.error(f"Error logging final state: {e}")
        
        # Give some time for logs to flush
        time.sleep(1)
        
        # Send SIGTERM to self for graceful shutdown
        os.kill(os.getpid(), signal.SIGTERM)
    
    def get_load_test_baseline(self) -> Dict[str, Any]:
        """Get baseline metrics for load testing validation"""
        if not self.baseline_established or self.baseline_rss_mb is None:
            return {"error": "Baseline not established"}
        
        current_snapshot = self.take_snapshot()
        
        rss_growth_mb = current_snapshot.rss_mb - self.baseline_rss_mb
        growth_percentage = (rss_growth_mb / self.baseline_rss_mb) * 100
        
        return {
            "baseline_rss_mb": self.baseline_rss_mb,
            "current_rss_mb": current_snapshot.rss_mb,
            "rss_growth_mb": rss_growth_mb,
            "growth_percentage": growth_percentage,
            "cache_entries": current_snapshot.cache_entries,
            "api_requests_total": current_snapshot.api_requests_total,
            "snapshots_count": len(self.snapshots),
            "baseline_established": self.baseline_established
        }
    
    def get_detailed_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics for debugging"""
        with self.lock:
            recent_snapshots = self.snapshots[-10:]  # Last 10 snapshots
        
        if not recent_snapshots:
            return {"error": "No snapshots available"}
        
        return {
            "process_info": {
                "pid": os.getpid(),
                "uptime_seconds": time.time() - psutil.Process().create_time(),
                "restart_count": self.restart_count,
                "last_restart": self.last_restart_time.isoformat() if self.last_restart_time else None
            },
            "memory_trend": [
                {
                    "timestamp": s.timestamp.isoformat(),
                    "rss_mb": s.rss_mb,
                    "cache_entries": s.cache_entries,
                    "api_requests": s.api_requests_total
                }
                for s in recent_snapshots
            ],
            "leak_detection": self.detect_memory_leak().__dict__,
            "thresholds": {
                "rss_mb": MEMORY_RSS_THRESHOLD_MB,
                "cache_entries": CACHE_ENTRIES_THRESHOLD,
                "auto_restart_enabled": AUTO_RESTART_ENABLED
            },
            "baseline": {
                "established": self.baseline_established,
                "rss_mb": self.baseline_rss_mb
            }
        }


# Global guardrail instance
_guardrail_instance: Optional[MemoryGuardrail] = None


def get_memory_guardrail() -> MemoryGuardrail:
    """Get or create global memory guardrail instance"""
    global _guardrail_instance
    if _guardrail_instance is None:
        _guardrail_instance = MemoryGuardrail()
    return _guardrail_instance


def periodic_memory_check():
    """
    Periodic memory check function for background monitoring
    
    Can be called by a scheduler or monitoring thread
    """
    try:
        guardrail = get_memory_guardrail()
        
        # Take snapshot and establish baseline if needed
        guardrail.take_snapshot()
        guardrail.establish_baseline()
        
        # Check if restart is needed
        should_restart, reason = guardrail.should_restart()
        
        if should_restart:
            logger.warning(f"Memory guardrail triggering restart: {reason}")
            guardrail.trigger_restart(reason)
        else:
            # Log periodic status
            status = guardrail.check_thresholds()
            if status["status"] != "healthy":
                logger.warning(f"Memory guardrail status: {status['status']} - {status['recommendations'][0]}")
            
    except Exception as e:
        logger.error(f"Error in periodic memory check: {e}")


# Graceful shutdown handler
def setup_shutdown_handler():
    """Setup graceful shutdown handler for SIGTERM"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        
        # Log final memory state
        try:
            guardrail = get_memory_guardrail()
            snapshot = guardrail.take_snapshot()
            logger.info(f"Shutdown memory state: RSS={snapshot.rss_mb:.1f}MB, Cache={snapshot.cache_entries} entries")
        except Exception as e:
            logger.error(f"Error logging shutdown state: {e}")
        
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler) 