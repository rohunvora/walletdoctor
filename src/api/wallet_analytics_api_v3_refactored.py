#!/usr/bin/env python3
"""
WalletDoctor API V3 - Unified version with production features
"""

from flask import Flask, request, jsonify, make_response, Response
from flask_cors import CORS
import asyncio
import sys
import os
from typing import Optional, AsyncGenerator
import time
import json
import uuid
import logging
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from src.lib.blockchain_fetcher_v3 import BlockchainFetcherV3
from src.lib.blockchain_fetcher_v3_stream import BlockchainFetcherV3Stream
from src.lib.progress_tracker import get_progress_tracker
from src.lib.progress_protocol import EventBuilder, ProgressData, ErrorData

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Production mode configuration
IS_PRODUCTION = os.getenv('ENV', 'development') == 'production'
STREAMING_ENABLED = os.getenv('STREAMING_ENABLED', 'true').lower() == 'true'
AUTH_REQUIRED = os.getenv('API_KEY_REQUIRED', str(IS_PRODUCTION)).lower() == 'true'

# Conditionally import production features
if IS_PRODUCTION:
    try:
        from src.lib.sse_auth import require_auth, log_api_request
        from src.lib.sse_error_handling import (
            create_error_boundary, WalletNotFoundError, DataFetchError
        )
        from src.lib.sse_monitoring import (
            stream_monitor, get_monitoring_data, format_prometheus_metrics
        )
        from src.config.production import SECURITY_HEADERS, ERROR_MESSAGES
    except ImportError:
        logger.warning("Production modules not found, running in development mode")
        IS_PRODUCTION = False
        AUTH_REQUIRED = False

# Create app
app = Flask(__name__)

# Configure CORS
cors_origins = os.getenv('ALLOWED_ORIGINS', '*').split(',') if IS_PRODUCTION else ['*']
CORS(app, 
     origins=cors_origins,
     methods=['GET', 'POST', 'OPTIONS'],
     allow_headers=['Content-Type', 'Authorization', 'X-API-Key', 'Last-Event-ID'],
     supports_credentials=True
)

# Add security headers in production
if IS_PRODUCTION:
    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses"""
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response

# Conditional decorator for auth
def maybe_require_auth(f):
    """Apply auth decorator only if AUTH_REQUIRED is True"""
    if AUTH_REQUIRED and IS_PRODUCTION:
        return require_auth(f)
    return f


async def fetch_and_analyze(wallet_address: str, progress_token: Optional[str] = None, max_pages: int = 100):
    """Fetch blockchain data and analyze"""
    logger.info(f"Starting analysis for wallet: {wallet_address}")

    # Setup progress tracking if token provided
    tracker = get_progress_tracker() if progress_token else None
    
    def progress_callback(msg: str):
        logger.info(msg)
        
        if tracker and progress_token:
            # Parse progress from message (same as before)
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

    # Fetch trades using V3
    async with BlockchainFetcherV3(
        progress_callback=progress_callback,
        skip_pricing=True
    ) as fetcher:
        result = await fetcher.fetch_wallet_trades(wallet_address)

    # Mark as complete
    if tracker and progress_token:
        trades_count = len(result.get("trades", []))
        tracker.update_progress(
            progress_token,
            status="complete",
            trades_found=trades_count
        )

    return result


@app.route("/analyze", methods=["POST"])
def analyze_wallet():
    """V3 API endpoint - kept for backwards compatibility"""
    try:
        data = request.get_json()
        if not data or "wallet" not in data:
            return jsonify({"error": "Missing wallet address"}), 400

        wallet_address = data["wallet"]

        # Validate wallet address format
        if not wallet_address or len(wallet_address) < 32:
            return jsonify({"error": "Invalid wallet address"}), 400

        logger.info(f"Analyzing wallet: {wallet_address}")

        # Run async function
        result = asyncio.run(fetch_and_analyze(wallet_address))

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error analyzing wallet: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/v4/analyze", methods=["POST"])
@maybe_require_auth
def analyze_wallet_v4():
    """V4 API endpoint with progress tracking"""
    try:
        data = request.get_json()
        if not data or "wallet" not in data:
            return jsonify({"error": "Missing wallet address"}), 400

        wallet_address = data["wallet"]

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

        # Run async function with progress tracking
        result = asyncio.run(fetch_and_analyze(wallet_address, progress_token))
        
        # Create response with progress header
        response = make_response(jsonify(result))
        response.headers['X-Progress-Token'] = progress_token

        return response

    except Exception as e:
        logger.error(f"Error analyzing wallet (v4): {e}")
        if 'progress_token' in locals() and 'tracker' in locals():
            tracker.update_progress(progress_token, status="error", error=str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/v4/wallet/<wallet_address>/stream", methods=["GET", "OPTIONS"])
@maybe_require_auth
def stream_wallet_endpoint(wallet_address: str):
    """SSE endpoint for streaming wallet analysis results"""
    
    # Handle preflight
    if request.method == "OPTIONS":
        return "", 204
    
    # Check if streaming is enabled
    if not STREAMING_ENABLED:
        return jsonify({"error": "Streaming not enabled"}), 501
    
    start_time = time.time()
    stream_id = str(uuid.uuid4())
    
    try:
        # Validate wallet address
        if not wallet_address or len(wallet_address) < 32:
            if IS_PRODUCTION:
                raise WalletNotFoundError(wallet_address)
            else:
                return jsonify({"error": "Invalid wallet address"}), 400
        
        logger.info(f"Starting SSE stream {stream_id} for wallet: {wallet_address}")
        
        # Create streaming generator
        async def stream_wallet_analysis():
            # Track stream in production
            if IS_PRODUCTION:
                stream_monitor.start_stream(
                    stream_id=stream_id,
                    wallet=wallet_address,
                    client_ip=request.remote_addr,
                    api_key=getattr(request, 'api_key', None)
                )
            
            try:
                # Send initial connected event
                connected_event = EventBuilder.connected({
                    'stream_id': stream_id,
                    'wallet': wallet_address,
                    'timestamp': int(time.time())
                })
                yield connected_event.to_sse_format()
                
                # Use streaming fetcher
                async with BlockchainFetcherV3Stream(skip_pricing=True) as fetcher:
                    trades_yielded = 0
                    
                    async for event in fetcher.fetch_wallet_trades_stream(wallet_address):
                        event_type = event["type"]
                        data = event["data"]
                        
                        if event_type == "progress":
                            progress_data = ProgressData(
                                message=data["message"],
                                percentage=data["percentage"],
                                step=data.get("step", "processing"),
                                trades_found=data.get("trades_count", trades_yielded)
                            )
                            yield EventBuilder.progress(progress_data).to_sse_format()
                            
                        elif event_type == "trades":
                            # Yield individual trade events
                            for trade in data["trades"]:
                                yield f"event: trade\ndata: {json.dumps(trade)}\n\n"
                                trades_yielded += 1
                                
                            # Record batch in monitoring
                            if IS_PRODUCTION:
                                stream_monitor.record_trades(stream_id, len(data["trades"]))
                        
                        elif event_type == "complete":
                            complete_event = EventBuilder.complete({
                                'trades_found': data["summary"]["total_trades"],
                                'duration': data["total_time"],
                                'summary': data["summary"]
                            })
                            yield complete_event.to_sse_format()
                            break
                            
                        elif event_type == "error":
                            error_data = ErrorData(
                                error=data["error"],
                                code="STREAM_ERROR"
                            )
                            yield EventBuilder.error(error_data).to_sse_format()
                            break
                        
                        # Send heartbeat periodically
                        if time.time() - start_time > 30:
                            yield EventBuilder.heartbeat().to_sse_format()
                            
            except Exception as e:
                logger.error(f"Stream {stream_id} error: {e}", exc_info=True)
                if IS_PRODUCTION:
                    stream_monitor.record_error(stream_id)
                
                error_data = ErrorData(
                    error=str(e),
                    code=getattr(e, 'code', 'STREAM_ERROR')
                )
                yield EventBuilder.error(error_data).to_sse_format()
                
            finally:
                if IS_PRODUCTION:
                    stream_monitor.end_stream(stream_id)
        
        # Wrap with error boundary in production
        if IS_PRODUCTION:
            stream_generator = create_error_boundary(stream_wallet_analysis)
        else:
            stream_generator = stream_wallet_analysis
        
        # Run async generator
        def generate():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                gen = stream_generator()
                while True:
                    try:
                        event = loop.run_until_complete(gen.__anext__())
                        yield event
                    except StopAsyncIteration:
                        break
            finally:
                loop.close()
        
        # Create SSE response
        response = Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
                "X-Stream-ID": stream_id
            }
        )
        
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        if IS_PRODUCTION:
            log_api_request(
                getattr(request, 'api_key', 'unknown'),
                'stream_wallet',
                duration,
                500
            )
        
        logger.error(f"Failed to start stream: {e}")
        error_msg = ERROR_MESSAGES.get(getattr(e, 'code', 'INTERNAL_ERROR'), str(e)) if IS_PRODUCTION else str(e)
        return jsonify({
            "error": error_msg,
            "code": getattr(e, 'code', 'INTERNAL_ERROR')
        }), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    health_data = {
        "status": "healthy",
        "version": "3.0",
        "timestamp": int(time.time()),
        "mode": "production" if IS_PRODUCTION else "development",
        "features": {
            "streaming": STREAMING_ENABLED,
            "auth_required": AUTH_REQUIRED
        }
    }
    
    # Add production metrics if available
    if IS_PRODUCTION and 'stream_monitor' in globals():
        metrics = stream_monitor.get_metrics()
        health_data["streaming"] = {
            "active_streams": metrics["active_streams"],
            "total_streams": metrics["total_streams"],
            "error_rate": metrics["error_rate"]
        }
    
    return jsonify(health_data)


@app.route("/metrics", methods=["GET"])
def metrics_endpoint():
    """Prometheus metrics endpoint"""
    if not IS_PRODUCTION:
        return "Metrics only available in production mode", 404
    
    try:
        metrics_text = format_prometheus_metrics()
        return Response(
            metrics_text,
            mimetype="text/plain; version=0.0.4",
            headers={"Content-Type": "text/plain; version=0.0.4"}
        )
    except Exception as e:
        logger.error(f"Metrics endpoint error: {e}")
        return "# Error generating metrics\n", 500


@app.route("/", methods=["GET"])
def home():
    """Home endpoint with API info"""
    endpoints = {
        "/analyze": 'POST - Analyze wallet (body: {"wallet": "address"})',
        "/v4/analyze": 'POST - V4 Analyze wallet (body: {"wallet": "address"}) - Returns X-Progress-Token header',
        "/health": "GET - Health check",
        "/": "GET - This info",
    }
    
    if STREAMING_ENABLED:
        endpoints["/v4/wallet/{address}/stream"] = "GET - Stream wallet trades via SSE"
    
    if IS_PRODUCTION:
        endpoints["/metrics"] = "GET - Prometheus metrics"
    
    return jsonify({
        "service": "WalletDoctor API V3",
        "version": "3.0",
        "mode": "production" if IS_PRODUCTION else "development",
        "endpoints": endpoints,
        "features": {
            "streaming_enabled": STREAMING_ENABLED,
            "auth_required": AUTH_REQUIRED
        },
        "authentication": "Required" if AUTH_REQUIRED else "Not required"
    })


if __name__ == "__main__":
    # Validate configuration on startup in production
    if IS_PRODUCTION:
        from src.config.production import validate_config
        try:
            validate_config()
            logger.info("Configuration validated successfully")
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            sys.exit(1)
    
    # Development mode warning
    if not IS_PRODUCTION:
        logger.warning("Running in development mode - some features may be disabled")
    
    # For development only
    app.run(host="0.0.0.0", port=5000, debug=False)
    
    # For production, use gunicorn:
    # gunicorn -c gunicorn.conf.py src.api.wallet_analytics_api_v3_refactored:app 