#!/usr/bin/env python3
"""
WalletDoctor API V4 - Enhanced with Comprehensive Metrics
WAL-608: Metrics & Dashboard

Adds comprehensive monitoring capabilities:
- Request latency tracking (P95 monitoring)
- Position cache hit rate and staleness metrics
- Memory usage monitoring (RSS tracking)
- Prometheus metrics endpoint
- Alert status checking
"""

from flask import Flask, request, jsonify, make_response, Response, g
from flask_cors import CORS
import asyncio
import sys
import os
from typing import Optional, Dict, Any, List
import time
import json
import logging
from datetime import datetime
from decimal import Decimal
from functools import wraps

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

# Core imports
from src.lib.blockchain_fetcher_v3_fast import BlockchainFetcherV3Fast
from src.lib.progress_tracker import get_progress_tracker
from src.lib.progress_protocol import EventBuilder, ProgressData, ErrorData

# P6 imports
from src.lib.position_builder import PositionBuilder
from src.lib.unrealized_pnl_calculator import UnrealizedPnLCalculator
from src.lib.position_cache import get_position_cache
from src.lib.position_models import Position, PositionPnL, PositionSnapshot, CostBasisMethod
from src.config.feature_flags import positions_enabled, should_calculate_unrealized_pnl, get_cost_basis_method

# Metrics imports
from src.lib.metrics_collector import get_metrics_collector, timing_decorator

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


def metrics_middleware():
    """Middleware to collect request metrics"""
    @app.before_request
    def before_request():
        g.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        # Calculate request duration
        duration_ms = (time.time() - g.start_time) * 1000
        
        # Extract endpoint name
        endpoint = request.endpoint or "unknown"
        method = request.method
        status_code = response.status_code
        
        # Record metrics
        collector = get_metrics_collector()
        collector.record_api_request(endpoint, method, status_code, duration_ms)
        
        # Update cache metrics if available
        try:
            cache = get_position_cache()
            cache_stats = cache.get_stats()
            collector.update_cache_metrics(cache_stats)
        except Exception as e:
            logger.error(f"Error updating cache metrics: {e}")
        
        # Add timing header for debugging
        response.headers['X-Response-Time-Ms'] = f"{duration_ms:.2f}"
        
        return response


# Initialize middleware
metrics_middleware()


async def fetch_and_analyze_v4_with_metrics(
    wallet_address: str, 
    progress_token: Optional[str] = None,
    include_positions: bool = True
) -> Dict[str, Any]:
    """
    Enhanced V4 fetch with metrics tracking
    
    Times position calculations and updates metrics
    """
    logger.info(f"Starting V4 analysis for wallet: {wallet_address}")
    start_time = time.time()
    
    # Setup progress tracking if token provided
    tracker = get_progress_tracker() if progress_token else None
    
    def progress_callback(msg: str):
        logger.info(msg)
        
        if tracker and progress_token:
            # Parse progress from message
            if "Page" in msg and "transactions" in msg:
                try:
                    parts = msg.split()
                    page_idx = parts.index("Page")
                    if page_idx < len(parts) - 1:
                        page_str = parts[page_idx + 1].rstrip(":")
                        page_num = int(page_str)
                        
                        tx_count = 0
                        for i, part in enumerate(parts):
                            if part.isdigit() and i > page_idx:
                                tx_count = int(part)
                                break
                        
                        estimated_total = page_num + (10 if tx_count >= 100 else 0)
                        
                        tracker.update_progress(
                            progress_token,
                            status="fetching",
                            pages_fetched=page_num,
                            total_pages=estimated_total
                        )
                except:
                    pass

    # Fetch trades using V3 Fast for better pagination handling
    async with BlockchainFetcherV3Fast(
        progress_callback=progress_callback,
        skip_pricing=False  # We need prices for position calculations
    ) as fetcher:
        result = await fetcher.fetch_wallet_trades(wallet_address)

    # Add position tracking if enabled
    if include_positions and positions_enabled():
        try:
            # Update progress
            if tracker and progress_token:
                tracker.update_progress(
                    progress_token,
                    status="calculating_positions"
                )
            
            # Time position calculation
            position_start = time.time()
            
            # Get position cache
            cache = get_position_cache()
            
            # Check cache first
            cached_snapshot = await cache.get_portfolio_snapshot(wallet_address)
            
            if cached_snapshot and _is_cache_fresh(cached_snapshot.timestamp):
                # Use cached data
                logger.info(f"Using cached position data for {wallet_address}")
                result["positions"] = [p.to_dict() for p in cached_snapshot.positions]
                result["position_summary"] = cached_snapshot.to_dict()["summary"]
                result["cached"] = True
            else:
                # Calculate positions
                positions = await calculate_positions_with_metrics(
                    wallet_address,
                    result.get("trades", [])
                )
                
                # Calculate unrealized P&L if enabled
                if positions and should_calculate_unrealized_pnl():
                    pnl_start = time.time()
                    position_pnls = await calculate_unrealized_pnl(positions)
                    pnl_time = (time.time() - pnl_start) * 1000
                    
                    # Record P&L calculation time
                    collector = get_metrics_collector()
                    collector.gauges["pnl_calculation_last_ms"] = pnl_time
                    
                    # Create snapshot
                    snapshot = PositionSnapshot.from_positions(
                        wallet_address,
                        position_pnls
                    )
                    
                    # Cache snapshot
                    await cache.set_portfolio_snapshot(snapshot)
                    
                    # Add to result
                    result["positions"] = [p.to_dict() for p in position_pnls]
                    result["position_summary"] = snapshot.to_dict()["summary"]
                    result["cached"] = False
                else:
                    # Just add positions without P&L
                    result["positions"] = [p.to_dict() for p in positions]
                    result["position_summary"] = {
                        "total_positions": len(positions),
                        "message": "Unrealized P&L calculation disabled"
                    }
                    result["cached"] = False
                
                # Invalidate cache on new data
                await cache.invalidate_wallet_positions(wallet_address)
            
            # Record total position processing time
            position_time = (time.time() - position_start) * 1000
            collector = get_metrics_collector()
            positions_count = len(result.get("positions", []))
            collector.record_position_calculation(wallet_address, positions_count, position_time)
                
        except Exception as e:
            logger.error(f"Error calculating positions: {e}")
            result["position_error"] = str(e)
    
    # Calculate totals
    if "trades" in result:
        realized_pnl = sum(
            Decimal(str(t.get("pnl_usd", 0))) 
            for t in result["trades"]
        )
        result["totals"] = {
            "total_trades": len(result["trades"]),
            "realized_pnl_usd": float(realized_pnl)
        }
        
        # Add unrealized P&L to totals if available
        if "position_summary" in result and "total_unrealized_pnl_usd" in result["position_summary"]:
            unrealized_pnl = Decimal(result["position_summary"]["total_unrealized_pnl_usd"])
            result["totals"]["unrealized_pnl_usd"] = float(unrealized_pnl)
            result["totals"]["total_pnl_usd"] = float(realized_pnl + unrealized_pnl)

    # Mark as complete
    if tracker and progress_token:
        trades_count = len(result.get("trades", []))
        positions_count = len(result.get("positions", []))
        tracker.update_progress(
            progress_token,
            status="complete",
            trades_found=trades_count
        )

    # Record total processing time
    total_time = (time.time() - start_time) * 1000
    logger.info(f"Analysis completed in {total_time:.1f}ms for {wallet_address}")

    return result


async def calculate_positions_with_metrics(wallet_address: str, trades: List[Dict[str, Any]]) -> List[Position]:
    """Calculate positions with timing metrics"""
    start_time = time.time()
    
    # Initialize position builder
    method = CostBasisMethod(get_cost_basis_method())
    builder = PositionBuilder(method)
    
    # Build positions
    positions = builder.build_positions_from_trades(trades, wallet_address)
    
    # Record timing
    calc_time = (time.time() - start_time) * 1000
    collector = get_metrics_collector()
    collector.gauges["position_builder_last_ms"] = calc_time
    
    logger.debug(f"Position calculation took {calc_time:.1f}ms for {len(positions)} positions")
    
    return positions


async def calculate_unrealized_pnl(positions: List[Position]) -> List[PositionPnL]:
    """Calculate unrealized P&L for positions"""
    calculator = UnrealizedPnLCalculator()
    return await calculator.create_position_pnl_list(positions)


def _is_cache_fresh(timestamp: datetime, max_age_seconds: int = 60) -> bool:
    """Check if cached data is fresh enough"""
    from datetime import timezone
    now = datetime.now(timezone.utc)
    age = (now - timestamp).total_seconds()
    return age < max_age_seconds


@app.route("/v4/analyze", methods=["POST"])
def analyze_wallet_v4():
    """V4 API endpoint with metrics tracking"""
    try:
        data = request.get_json()
        if not data or "wallet" not in data:
            return jsonify({"error": "Missing wallet address"}), 400

        wallet_address = data["wallet"]
        include_positions = data.get("include_positions", True)

        # Validate wallet address format
        if not wallet_address or len(wallet_address) < 32:
            return jsonify({"error": "Invalid wallet address"}), 400

        logger.info(f"Analyzing wallet (v4): {wallet_address}")
        
        # Create progress token
        tracker = get_progress_tracker()
        progress_token = tracker.create_progress()
        
        # Initialize progress
        tracker.update_progress(
            progress_token,
            status="fetching",
            total_pages=0,
            pages_fetched=0,
            trades_found=0
        )

        # Run async function with metrics tracking
        result = asyncio.run(fetch_and_analyze_v4_with_metrics(
            wallet_address, 
            progress_token,
            include_positions
        ))
        
        # Create response with progress header
        response = make_response(jsonify(result))
        response.headers['X-Progress-Token'] = progress_token

        return response

    except Exception as e:
        logger.error(f"Error analyzing wallet (v4): {e}")
        if 'progress_token' in locals() and 'tracker' in locals():
            tracker.update_progress(progress_token, status="error", error=str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/v4/positions/<wallet_address>", methods=["GET"])
def get_wallet_positions(wallet_address: str):
    """Get current positions with metrics tracking"""
    try:
        # Check if positions are enabled
        if not positions_enabled():
            return jsonify({
                "error": "Position tracking is not enabled",
                "feature_flag": "positions_enabled"
            }), 501
        
        # Validate wallet address
        if not wallet_address or len(wallet_address) < 32:
            return jsonify({"error": "Invalid wallet address"}), 400
        
        force_refresh = request.args.get("refresh", "false").lower() == "true"
        
        logger.info(f"Getting positions for wallet: {wallet_address} (refresh: {force_refresh})")
        
        start_time = time.time()
        
        # Get cache
        cache = get_position_cache()
        
        # Check cache first unless refresh requested
        if not force_refresh:
            cached_snapshot = asyncio.run(cache.get_portfolio_snapshot(wallet_address))
            if cached_snapshot and _is_cache_fresh(cached_snapshot.timestamp, max_age_seconds=300):
                logger.info(f"Returning cached positions for {wallet_address}")
                result = cached_snapshot.to_dict()
                result["wallet"] = wallet_address
                result["cached"] = True
                
                # Record cache hit timing
                cache_time = (time.time() - start_time) * 1000
                collector = get_metrics_collector()
                collector.gauges["position_cache_hit_time_ms"] = cache_time
                
                return jsonify(result)
        
        # Fetch fresh data
        logger.info(f"Fetching fresh positions for {wallet_address}")
        
        # Fetch trades
        async def fetch_positions():
            # Get trades
            async with BlockchainFetcherV3Fast(skip_pricing=False) as fetcher:
                trade_data = await fetcher.fetch_wallet_trades(wallet_address)
            
            trades = trade_data.get("trades", [])
            
            # Calculate positions
            positions = await calculate_positions_with_metrics(wallet_address, trades)
            
            # Calculate unrealized P&L if enabled
            if positions and should_calculate_unrealized_pnl():
                position_pnls = await calculate_unrealized_pnl(positions)
                
                # Create and cache snapshot
                snapshot = PositionSnapshot.from_positions(wallet_address, position_pnls)
                await cache.set_portfolio_snapshot(snapshot)
                
                # Invalidate individual position caches
                await cache.invalidate_wallet_positions(wallet_address)
                
                return snapshot
            else:
                # Return positions without P&L
                return {
                    "wallet": wallet_address,
                    "positions": [p.to_dict() for p in positions],
                    "summary": {
                        "total_positions": len(positions),
                        "message": "Unrealized P&L calculation disabled"
                    },
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "cached": False
                }
        
        result = asyncio.run(fetch_positions())
        
        # Convert to response format
        if isinstance(result, PositionSnapshot):
            response = result.to_dict()
            response["wallet"] = wallet_address
            response["cached"] = False
        else:
            response = result
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/metrics", methods=["GET"])
def prometheus_metrics():
    """
    Prometheus metrics endpoint
    
    Returns metrics in Prometheus text format for scraping
    """
    try:
        collector = get_metrics_collector()
        metrics_text = collector.get_prometheus_metrics()
        
        response = Response(metrics_text, mimetype='text/plain')
        response.headers['Cache-Control'] = 'no-cache'
        return response
        
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        return Response(f"# Error generating metrics: {e}", mimetype='text/plain'), 500


@app.route("/metrics/health", methods=["GET"])
def metrics_health():
    """
    Detailed health check with alerts and metrics summary
    
    Returns:
    {
        "status": "healthy|warning|critical",
        "timestamp": "2024-01-01T00:00:00Z",
        "metrics": {...},
        "alerts": {...},
        "uptime_seconds": 3600
    }
    """
    try:
        collector = get_metrics_collector()
        health_summary = collector.get_health_summary()
        
        return jsonify(health_summary)
        
    except Exception as e:
        logger.error(f"Error getting health summary: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@app.route("/metrics/alerts", methods=["GET"])
def metrics_alerts():
    """
    Alert status endpoint for monitoring systems
    
    Returns alert levels and current thresholds
    """
    try:
        collector = get_metrics_collector()
        alerts = collector.get_alert_status()
        
        return jsonify({
            "timestamp": datetime.utcnow().isoformat(),
            "alerts": alerts,
            "thresholds": {
                "api_p95_latency_ms": {"warning": 150, "critical": 200},
                "memory_rss_mb": {"warning": 450, "critical": 600},
                "cache_entries": {"warning": 2000},
                "cache_hit_rate_pct": {"warning": 70}
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/v4/progress/<token>", methods=["GET"])
def get_progress(token):
    """Get progress status with enhanced metrics"""
    try:
        tracker = get_progress_tracker()
        progress = tracker.get_progress(token)
        
        if progress is None:
            return jsonify({"error": "Progress token not found or expired"}), 404
        
        return jsonify(progress)
        
    except Exception as e:
        logger.error(f"Error getting progress: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Basic health check with feature flags and metrics summary"""
    try:
        collector = get_metrics_collector()
        cache = get_position_cache()
        
        return jsonify({
            "status": "healthy",
            "version": "4.0-metrics",
            "features": {
                "positions_enabled": positions_enabled(),
                "unrealized_pnl_enabled": should_calculate_unrealized_pnl(),
                "cost_basis_method": get_cost_basis_method()
            },
            "cache_stats": cache.get_stats(),
            "metrics_summary": {
                "api_requests": collector.counters.get('api_requests_total', 0),
                "memory_rss_mb": collector.get_memory_usage()["rss_mb"],
                "uptime_seconds": time.time() - collector.start_time
            }
        })
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/", methods=["GET"])
def home():
    """Home endpoint with metrics info"""
    return jsonify({
        "service": "WalletDoctor API V4 - Metrics Enhanced",
        "version": "4.0-metrics",
        "endpoints": {
            "/v4/analyze": 'POST - Analyze wallet with positions and metrics',
            "/v4/positions/{wallet}": "GET - Get current positions for a wallet",
            "/v4/progress/{token}": "GET - Get progress status",
            "/metrics": "GET - Prometheus metrics",
            "/metrics/health": "GET - Detailed health check with alerts",
            "/metrics/alerts": "GET - Alert status",
            "/health": "GET - Basic health check",
            "/": "GET - This info",
        },
        "features": [
            "Comprehensive Prometheus metrics",
            "Request latency tracking (P95 monitoring)",
            "Position cache hit rate monitoring",
            "Memory usage tracking (RSS)",
            "Alert thresholds for critical metrics",
            "Real-time health status"
        ],
        "monitoring": {
            "prometheus_endpoint": "/metrics",
            "alert_thresholds": {
                "api_p95_latency_ms": 200,
                "memory_rss_mb": 600
            }
        }
    })


if __name__ == "__main__":
    # For development
    app.run(host="0.0.0.0", port=8080, debug=False)
    
    # For production, use gunicorn:
    # gunicorn -w 4 -b 0.0.0.0:8080 src.api.wallet_analytics_api_v4_metrics:app 