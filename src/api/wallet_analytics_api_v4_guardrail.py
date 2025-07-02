#!/usr/bin/env python3
"""
Wallet Analytics API V4 with Memory Guardrail
WAL-609: Self-check endpoints and auto-restart capabilities

Extends V4 API with:
- Memory and cache monitoring endpoints
- Self-check functionality
- Load testing baseline support
- Auto-restart triggers
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from flask import Flask, request, jsonify, Response
except ImportError:
    print("Flask not available for API endpoints")
    Flask = None

# Import existing V4 functionality
try:
    from src.api.wallet_analytics_api_v4_metrics import (
        create_app_with_metrics,
        get_wallet_positions_with_timing
    )
except ImportError:
    print("V4 metrics API not available")
    create_app_with_metrics = None

# Memory guardrail system
from src.lib.memory_guardrail import (
    get_memory_guardrail,
    periodic_memory_check,
    setup_shutdown_handler,
    MEMORY_RSS_THRESHOLD_MB,
    CACHE_ENTRIES_THRESHOLD,
    BASELINE_SAMPLE_COUNT
)

logger = logging.getLogger(__name__)


def create_app_with_guardrail():
    """
    Create Flask app with memory guardrail endpoints
    
    Extends the metrics-enabled V4 API with memory management
    """
    # Start with metrics-enabled app
    if create_app_with_metrics:
        app = create_app_with_metrics()
    else:
        app = Flask(__name__)
    
    # Setup graceful shutdown handling
    setup_shutdown_handler()
    
    # Initialize memory guardrail
    guardrail = get_memory_guardrail()
    
    @app.route('/self-check', methods=['GET'])
    def self_check():
        """
        Self-check endpoint - primary guardrail monitoring
        
        Returns current memory usage, cache stats, and threshold status
        Required for WAL-609 acceptance criteria
        """
        try:
            start_time = time.time()
            
            # Get comprehensive status
            status = guardrail.check_thresholds()
            
            # Check if restart is recommended
            should_restart, restart_reason = guardrail.should_restart()
            
            # Add self-check specific metadata
            response_data = {
                **status,
                "self_check": {
                    "should_restart": should_restart,
                    "restart_reason": restart_reason,
                    "response_time_ms": round((time.time() - start_time) * 1000, 2),
                    "endpoint": "/self-check",
                    "check_timestamp": datetime.utcnow().isoformat()
                }
            }
            
            # Set appropriate HTTP status based on health
            http_status = 200
            if status["status"] == "critical":
                http_status = 503  # Service Unavailable
            elif status["status"] == "warning":
                http_status = 206  # Partial Content
            
            return jsonify(response_data), http_status
            
        except Exception as e:
            logger.error(f"Error in self-check endpoint: {e}")
            return jsonify({
                "error": str(e),
                "status": "error",
                "timestamp": datetime.utcnow().isoformat()
            }), 500
    
    @app.route('/self-check/memory', methods=['GET'])
    def self_check_memory():
        """
        Memory-focused self-check endpoint
        
        Returns detailed memory statistics and leak detection
        """
        try:
            guardrail = get_memory_guardrail()
            
            # Force a snapshot
            current_snapshot = guardrail.take_snapshot()
            
            # Get leak detection analysis
            leak_result = guardrail.detect_memory_leak()
            
            return jsonify({
                "memory": {
                    "rss_mb": current_snapshot.rss_mb,
                    "vms_mb": current_snapshot.vms_mb,
                    "process_id": current_snapshot.process_id
                },
                "cache": {
                    "entries": current_snapshot.cache_entries,
                    "hit_rate": current_snapshot.cache_hit_rate
                },
                "thresholds": {
                    "rss_threshold_mb": MEMORY_RSS_THRESHOLD_MB,
                    "cache_threshold": CACHE_ENTRIES_THRESHOLD
                },
                "leak_detection": {
                    "is_leak_detected": leak_result.is_leak_detected,
                    "growth_rate_mb_per_min": leak_result.growth_rate_mb_per_min,
                    "time_to_threshold_min": leak_result.time_to_threshold_min,
                    "severity": leak_result.severity,
                    "recommendation": leak_result.recommendation
                },
                "baseline": {
                    "established": guardrail.baseline_established,
                    "baseline_rss_mb": guardrail.baseline_rss_mb
                },
                "timestamp": current_snapshot.timestamp.isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error in memory self-check: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/self-check/cache', methods=['GET'])
    def self_check_cache():
        """
        Cache-focused self-check endpoint
        
        Returns cache statistics and health status
        """
        try:
            guardrail = get_memory_guardrail()
            current_snapshot = guardrail.take_snapshot()
            
            # Get position cache directly for detailed stats
            from src.lib.position_cache import get_position_cache
            cache = get_position_cache()
            detailed_stats = cache.get_stats()
            
            return jsonify({
                "cache_summary": {
                    "entries": current_snapshot.cache_entries,
                    "hit_rate": current_snapshot.cache_hit_rate,
                    "threshold": CACHE_ENTRIES_THRESHOLD,
                    "usage_percentage": (current_snapshot.cache_entries / CACHE_ENTRIES_THRESHOLD) * 100
                },
                "detailed_stats": detailed_stats,
                "health": {
                    "status": "critical" if current_snapshot.cache_entries > CACHE_ENTRIES_THRESHOLD else "healthy",
                    "recommendation": "Clear cache" if current_snapshot.cache_entries > CACHE_ENTRIES_THRESHOLD else "Cache operating normally"
                },
                "timestamp": current_snapshot.timestamp.isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error in cache self-check: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/self-check/baseline', methods=['GET'])
    def self_check_baseline():
        """
        Load testing baseline endpoint
        
        Returns baseline metrics for load test validation
        Required for WAL-609 load testing acceptance gate
        """
        try:
            guardrail = get_memory_guardrail()
            
            # Force baseline establishment if needed
            guardrail.take_snapshot()
            baseline_ready = guardrail.establish_baseline()
            
            if not baseline_ready:
                return jsonify({
                    "baseline_status": "establishing",
                    "snapshots_taken": len(guardrail.snapshots),
                    "snapshots_needed": BASELINE_SAMPLE_COUNT,
                    "message": "Take more requests to establish baseline"
                }), 202  # Accepted but not ready
            
            baseline_data = guardrail.get_load_test_baseline()
            
            # Add load test specific metadata
            baseline_data.update({
                "load_test_validation": {
                    "growth_limit_mb": 50,  # +50MB limit from acceptance criteria
                    "growth_status": "PASS" if baseline_data.get("rss_growth_mb", 0) <= 50 else "FAIL",
                    "rss_stable": baseline_data.get("rss_growth_mb", 0) <= 50
                },
                "acceptance_criteria": {
                    "max_growth_mb": 50,
                    "test_duration": "10 minutes",
                    "test_rate": "5 req/s"
                }
            })
            
            return jsonify(baseline_data)
            
        except Exception as e:
            logger.error(f"Error in baseline self-check: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/self-check/detailed', methods=['GET'])
    def self_check_detailed():
        """
        Comprehensive self-check with all statistics
        
        Returns detailed debugging information
        """
        try:
            guardrail = get_memory_guardrail()
            detailed_stats = guardrail.get_detailed_stats()
            
            return jsonify(detailed_stats)
            
        except Exception as e:
            logger.error(f"Error in detailed self-check: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/self-check/restart', methods=['POST'])
    def self_check_restart():
        """
        Manual restart trigger endpoint
        
        Allows manual restart for testing purposes
        Requires confirmation parameter for safety
        """
        try:
            data = request.get_json() or {}
            confirm = data.get('confirm', False)
            reason = data.get('reason', 'Manual restart via API')
            
            if not confirm:
                return jsonify({
                    "error": "Manual restart requires confirmation",
                    "required_payload": {
                        "confirm": True,
                        "reason": "Optional reason for restart"
                    }
                }), 400
            
            guardrail = get_memory_guardrail()
            
            # Log the manual restart request
            logger.warning(f"Manual restart requested via API: {reason}")
            
            # Trigger restart (this will terminate the process)
            guardrail.trigger_restart(f"Manual restart: {reason}")
            
            # This line should not be reached
            return jsonify({"message": "Restart triggered"}), 202
            
        except Exception as e:
            logger.error(f"Error in restart endpoint: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/self-check/force-memory-check', methods=['POST'])
    def force_memory_check():
        """
        Force periodic memory check
        
        Triggers the background memory check logic manually
        """
        try:
            # Run periodic check
            periodic_memory_check()
            
            # Get current status after check
            guardrail = get_memory_guardrail()
            status = guardrail.check_thresholds()
            
            return jsonify({
                "message": "Memory check completed",
                "status": status,
                "timestamp": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error in force memory check: {e}")
            return jsonify({"error": str(e)}), 500
    
    # Enhanced health endpoint with guardrail status
    @app.route('/health', methods=['GET'])
    def health_with_guardrail():
        """
        Enhanced health endpoint with memory guardrail status
        
        Combines standard health check with memory monitoring
        """
        try:
            # Get basic health from metrics app
            basic_health = {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "version": "v4-guardrail"
            }
            
            # Add guardrail status
            guardrail = get_memory_guardrail()
            guardrail_status = guardrail.check_thresholds()
            
            # Combine status
            overall_status = "healthy"
            if guardrail_status["status"] == "critical":
                overall_status = "critical"
            elif guardrail_status["status"] == "warning":
                overall_status = "warning"
            
            return jsonify({
                **basic_health,
                "overall_status": overall_status,
                "guardrail": {
                    "memory_status": guardrail_status["status"],
                    "rss_mb": guardrail_status["current_memory"]["rss_mb"],
                    "cache_entries": guardrail_status["current_memory"]["cache_entries"],
                    "auto_restart_enabled": guardrail_status["auto_restart_enabled"]
                }
            })
            
        except Exception as e:
            logger.error(f"Error in health endpoint: {e}")
            return jsonify({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }), 500
    
    # Background memory monitoring
    @app.before_first_request
    def start_background_monitoring():
        """Start background memory monitoring"""
        logger.info("Starting background memory monitoring...")
        
        # Take initial snapshot
        guardrail = get_memory_guardrail()
        guardrail.take_snapshot()
        
        # Schedule periodic checks (in production, this would be handled by a proper scheduler)
        # For now, we'll rely on manual triggering and request-based monitoring
        logger.info("Memory guardrail initialized and ready")
    
    return app


# For development and testing
if __name__ == '__main__':
    app = create_app_with_guardrail()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Starting WalletDoctor V4 API with Memory Guardrail")
    
    # Run with auto-reload for development
    app.run(host='0.0.0.0', port=5000, debug=True) 