#!/usr/bin/env python3
"""
SSE Monitoring and Observability
"""

import time
import logging
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import asyncio
from collections import deque
import threading

logger = logging.getLogger(__name__)


@dataclass
class StreamMetrics:
    """Metrics for a single stream"""
    stream_id: str
    wallet: str
    start_time: float
    end_time: Optional[float] = None
    events_sent: int = 0
    trades_yielded: int = 0
    errors: int = 0
    bytes_sent: int = 0
    last_event_time: Optional[float] = None
    client_ip: Optional[str] = None
    api_key: Optional[str] = None
    
    @property
    def duration(self) -> float:
        """Get stream duration in seconds"""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    @property
    def events_per_second(self) -> float:
        """Calculate events per second"""
        duration = self.duration
        return self.events_sent / duration if duration > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        data = asdict(self)
        data['duration'] = self.duration
        data['events_per_second'] = self.events_per_second
        return data


class StreamMonitor:
    """Monitor active streams and collect metrics"""
    
    def __init__(self, max_history: int = 1000):
        self.active_streams: Dict[str, StreamMetrics] = {}
        self.completed_streams: deque = deque(maxlen=max_history)
        self.start_time = time.time()
        self._lock = threading.Lock()
        
        # Aggregate metrics
        self.total_streams = 0
        self.total_events = 0
        self.total_trades = 0
        self.total_errors = 0
        self.total_bytes = 0
    
    def start_stream(self, stream_id: str, wallet: str, client_ip: Optional[str] = None, api_key: Optional[str] = None) -> StreamMetrics:
        """Start monitoring a new stream"""
        with self._lock:
            metrics = StreamMetrics(
                stream_id=stream_id,
                wallet=wallet,
                start_time=time.time(),
                client_ip=client_ip,
                api_key=api_key[:10] + '...' if api_key else None
            )
            self.active_streams[stream_id] = metrics
            self.total_streams += 1
            
            logger.info(
                "stream_started",
                extra={
                    'stream_id': stream_id,
                    'wallet': wallet,
                    'client_ip': client_ip,
                    'active_streams': len(self.active_streams)
                }
            )
            
            return metrics
    
    def record_event(self, stream_id: str, event_type: str, data_size: int = 0):
        """Record an event being sent"""
        with self._lock:
            if stream_id in self.active_streams:
                metrics = self.active_streams[stream_id]
                metrics.events_sent += 1
                metrics.bytes_sent += data_size
                metrics.last_event_time = time.time()
                
                self.total_events += 1
                self.total_bytes += data_size
    
    def record_trades(self, stream_id: str, trade_count: int):
        """Record trades being sent"""
        with self._lock:
            if stream_id in self.active_streams:
                metrics = self.active_streams[stream_id]
                metrics.trades_yielded += trade_count
                self.total_trades += trade_count
    
    def record_error(self, stream_id: str):
        """Record an error in the stream"""
        with self._lock:
            if stream_id in self.active_streams:
                metrics = self.active_streams[stream_id]
                metrics.errors += 1
                self.total_errors += 1
    
    def end_stream(self, stream_id: str):
        """End monitoring for a stream"""
        with self._lock:
            if stream_id in self.active_streams:
                metrics = self.active_streams[stream_id]
                metrics.end_time = time.time()
                
                # Move to completed
                self.completed_streams.append(metrics)
                del self.active_streams[stream_id]
                
                logger.info(
                    "stream_ended",
                    extra=metrics.to_dict()
                )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        with self._lock:
            uptime = time.time() - self.start_time
            
            # Calculate rates
            streams_per_minute = (self.total_streams / uptime) * 60 if uptime > 0 else 0
            events_per_second = self.total_events / uptime if uptime > 0 else 0
            
            # Get active stream info
            active_wallets = [m.wallet for m in self.active_streams.values()]
            avg_duration = sum(m.duration for m in self.active_streams.values()) / len(self.active_streams) \
                if self.active_streams else 0
            
            return {
                'uptime_seconds': uptime,
                'active_streams': len(self.active_streams),
                'active_wallets': active_wallets[:10],  # Limit to 10
                'total_streams': self.total_streams,
                'total_events': self.total_events,
                'total_trades': self.total_trades,
                'total_errors': self.total_errors,
                'total_bytes': self.total_bytes,
                'streams_per_minute': streams_per_minute,
                'events_per_second': events_per_second,
                'avg_stream_duration': avg_duration,
                'error_rate': (self.total_errors / self.total_streams * 100) if self.total_streams > 0 else 0
            }
    
    def get_stream_metrics(self, stream_id: str) -> Optional[StreamMetrics]:
        """Get metrics for a specific stream"""
        with self._lock:
            return self.active_streams.get(stream_id)
    
    def cleanup_stale_streams(self, timeout: float = 300):
        """Clean up streams that haven't sent events in a while"""
        with self._lock:
            current_time = time.time()
            stale_streams = []
            
            for stream_id, metrics in self.active_streams.items():
                if metrics.last_event_time and current_time - metrics.last_event_time > timeout:
                    stale_streams.append(stream_id)
            
            for stream_id in stale_streams:
                logger.warning(f"Cleaning up stale stream: {stream_id}")
                self.end_stream(stream_id)


# Global monitor instance
stream_monitor = StreamMonitor()


# Structured logging helpers
def log_stream_event(stream_id: str, event_type: str, details: Optional[Dict[str, Any]] = None):
    """Log a stream event with structured data"""
    logger.info(
        "stream_event",
        extra={
            'stream_id': stream_id,
            'event_type': event_type,
            'details': details or {},
            'timestamp': datetime.utcnow().isoformat()
        }
    )


def log_performance_metric(metric_name: str, value: float, unit: str, tags: Optional[Dict[str, str]] = None):
    """Log a performance metric"""
    logger.info(
        "performance_metric",
        extra={
            'metric': metric_name,
            'value': value,
            'unit': unit,
            'tags': tags or {},
            'timestamp': datetime.utcnow().isoformat()
        }
    )


# Monitoring endpoints data
def get_monitoring_data() -> Dict[str, Any]:
    """Get monitoring data for /metrics endpoint"""
    metrics = stream_monitor.get_metrics()
    
    # Add system metrics
    import psutil
    process = psutil.Process()
    
    metrics.update({
        'system': {
            'cpu_percent': process.cpu_percent(),
            'memory_mb': process.memory_info().rss / 1024 / 1024,
            'threads': process.num_threads(),
            'connections': len(process.connections(kind='inet'))
        }
    })
    
    return metrics


def format_prometheus_metrics() -> str:
    """Format metrics in Prometheus format"""
    metrics = stream_monitor.get_metrics()
    lines = []
    
    # Active streams
    lines.append('# HELP walletdoctor_active_streams Number of active SSE streams')
    lines.append('# TYPE walletdoctor_active_streams gauge')
    lines.append(f'walletdoctor_active_streams {metrics["active_streams"]}')
    
    # Total streams
    lines.append('# HELP walletdoctor_total_streams Total number of streams started')
    lines.append('# TYPE walletdoctor_total_streams counter')
    lines.append(f'walletdoctor_total_streams {metrics["total_streams"]}')
    
    # Total events
    lines.append('# HELP walletdoctor_total_events Total number of SSE events sent')
    lines.append('# TYPE walletdoctor_total_events counter')
    lines.append(f'walletdoctor_total_events {metrics["total_events"]}')
    
    # Total trades
    lines.append('# HELP walletdoctor_total_trades Total number of trades yielded')
    lines.append('# TYPE walletdoctor_total_trades counter')
    lines.append(f'walletdoctor_total_trades {metrics["total_trades"]}')
    
    # Error rate
    lines.append('# HELP walletdoctor_error_rate Percentage of streams with errors')
    lines.append('# TYPE walletdoctor_error_rate gauge')
    lines.append(f'walletdoctor_error_rate {metrics["error_rate"]:.2f}')
    
    # Bytes sent
    lines.append('# HELP walletdoctor_bytes_sent Total bytes sent via SSE')
    lines.append('# TYPE walletdoctor_bytes_sent counter')
    lines.append(f'walletdoctor_bytes_sent {metrics["total_bytes"]}')
    
    return '\n'.join(lines)


# Background cleanup task
async def cleanup_task():
    """Background task to clean up stale streams"""
    while True:
        try:
            stream_monitor.cleanup_stale_streams()
            await asyncio.sleep(60)  # Check every minute
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
            await asyncio.sleep(60) 