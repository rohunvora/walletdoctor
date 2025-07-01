#!/usr/bin/env python3
"""
WalletDoctor API V3
Direct blockchain analysis via Helius
"""

from flask import Flask, request, jsonify, make_response, Response
from flask_cors import CORS
import asyncio
import sys
import os
from typing import Optional
import time
import json

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from src.lib.blockchain_fetcher_v3 import BlockchainFetcherV3
from src.lib.progress_tracker import get_progress_tracker
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


async def fetch_and_analyze(wallet_address: str, progress_token: Optional[str] = None, max_pages: int = 100):
    """Fetch blockchain data and analyze"""
    logger.info(f"Starting analysis for wallet: {wallet_address}")

    # Setup progress tracking if token provided
    tracker = get_progress_tracker() if progress_token else None
    
    def progress_callback(msg: str):
        logger.info(msg)
        
        if tracker and progress_token:
            # Parse progress from message
            if "Page" in msg and "transactions" in msg:
                # Extract page number and transaction count
                try:
                    parts = msg.split()
                    page_idx = parts.index("Page")
                    if page_idx < len(parts) - 1:
                        page_str = parts[page_idx + 1].rstrip(":")
                        page_num = int(page_str)
                        
                        # Extract transaction count to estimate total pages
                        tx_count = 0
                        for i, part in enumerate(parts):
                            if part.isdigit() and i > page_idx:
                                tx_count = int(part)
                                break
                        
                        # If we're getting 100 transactions per page, estimate total
                        estimated_total = page_num + (10 if tx_count >= 100 else 0)
                        
                        tracker.update_progress(
                            progress_token,
                            status="fetching",
                            pages_fetched=page_num,
                            total_pages=estimated_total
                        )
                except:
                    pass
            elif "Extracted" in msg and "unique trades" in msg:
                # Extract trade count
                try:
                    parts = msg.split()
                    if "Extracted" in parts:
                        idx = parts.index("Extracted")
                        if idx < len(parts) - 1:
                            trades_count = int(parts[idx + 1])
                            tracker.update_progress(
                                progress_token,
                                trades_found=trades_count
                            )
                except:
                    pass
            elif "Fetched" in msg and "SWAP transactions" in msg:
                # Extract total transaction count
                try:
                    parts = msg.split()
                    if "Fetched" in parts:
                        idx = parts.index("Fetched")
                        if idx < len(parts) - 1:
                            tx_count = int(parts[idx + 1])
                            # Update with final page count
                            current = tracker.get_progress(progress_token)
                            if current:
                                tracker.update_progress(
                                    progress_token,
                                    total_pages=current.get("pages", 0)
                                )
                except:
                    pass

    # Fetch trades using V3 (which has proper pagination fix)
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

    # Return raw fetcher result
    return result


@app.route("/analyze", methods=["POST"])
def analyze_wallet():
    """
    Analyze a wallet by fetching data from blockchain

    Request body:
    {
        "wallet": "wallet_address"
    }
    """
    try:
        data = request.get_json()
        if not data or "wallet" not in data:
            return jsonify({"error": "Missing wallet address"}), 400

        wallet_address = data["wallet"]

        # Validate wallet address format
        if not wallet_address or len(wallet_address) < 32:
            return jsonify({"error": "Invalid wallet address"}), 400

        logger.info(f"Analyzing wallet: {wallet_address}")

        # Run async function (no progress tracking for v3 endpoint)
        result = asyncio.run(fetch_and_analyze(wallet_address))

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error analyzing wallet: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/v4/analyze", methods=["POST"])
def analyze_wallet_v4():
    """
    V4 API endpoint - Analyze a wallet by fetching data from blockchain

    Request body:
    {
        "wallet": "wallet_address"
    }
    
    Response includes X-Progress-Token header for tracking long-running operations
    """
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
            total_pages=0,  # Will be updated as we go
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
        # Update progress with error if we have a token
        if 'progress_token' in locals() and 'tracker' in locals():
            tracker.update_progress(progress_token, status="error", error=str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/v4/prices", methods=["POST"])
def fetch_prices():
    """
    Fetch prices for a batch of tokens at specific timestamps
    
    Request body:
    {
        "mints": ["mint1", "mint2", ...],
        "timestamps": [unix_timestamp1, unix_timestamp2, ...]
    }
    
    Returns:
    {
        "mint1": price_usd,
        "mint2": price_usd,
        ...
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing request body"}), 400
            
        mints = data.get("mints", [])
        timestamps = data.get("timestamps", [])
        
        if not mints:
            return jsonify({"error": "Missing mints array"}), 400
        if not timestamps:
            return jsonify({"error": "Missing timestamps array"}), 400
            
        if not isinstance(mints, list) or not isinstance(timestamps, list):
            return jsonify({"error": "mints and timestamps must be arrays"}), 400
            
        logger.info(f"Fetching prices for {len(mints)} mints at {len(timestamps)} timestamps")
        
        # Fetch prices using BlockchainFetcherV3
        async def fetch_prices_async():
            async with BlockchainFetcherV3() as fetcher:
                return await fetcher._fetch_batch_prices(mints, timestamps)
        
        prices = asyncio.run(fetch_prices_async())
        
        return jsonify(prices)
        
    except Exception as e:
        logger.error(f"Error fetching prices: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/v4/progress/<token>", methods=["GET"])
def get_progress(token):
    """
    Get progress status for a long-running operation
    
    Returns:
    {
        "token": "uuid",
        "status": "fetching",  # pending, fetching, complete, error
        "pages": 45,
        "total": 72,
        "trades": 3500,
        "error": null,
        "age_seconds": 15
    }
    """
    try:
        tracker = get_progress_tracker()
        progress = tracker.get_progress(token)
        
        if progress is None:
            return jsonify({"error": "Progress token not found or expired"}), 404
        
        return jsonify(progress)
        
    except Exception as e:
        logger.error(f"Error getting progress: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/v4/analyze/stream", methods=["POST"])
def analyze_wallet_stream():
    """
    SSE endpoint for streaming wallet analysis results
    
    Request body:
    {
        "wallet": "wallet_address"
    }
    
    Returns: Server-Sent Events stream
    """
    try:
        data = request.get_json()
        if not data or "wallet" not in data:
            return jsonify({"error": "Missing wallet address"}), 400

        wallet_address = data["wallet"]

        # Validate wallet address format
        if not wallet_address or len(wallet_address) < 32:
            return jsonify({"error": "Invalid wallet address"}), 400

        logger.info(f"Starting SSE stream for wallet: {wallet_address}")
        
        def generate():
            """Generator function for SSE events"""
            # Send initial connected event
            yield f"event: connected\ndata: {json.dumps({'status': 'connected', 'wallet': wallet_address})}\n\n"
            
            # For now, just implement heartbeat
            # In future tickets, this will integrate with the streaming fetcher
            start_time = time.time()
            last_heartbeat = start_time
            
            # Simulate some work with heartbeats
            while time.time() - start_time < 60:  # Max 60 seconds for now
                current_time = time.time()
                
                # Send heartbeat every 30 seconds
                if current_time - last_heartbeat >= 30:
                    yield f"event: heartbeat\ndata: {json.dumps({'timestamp': int(current_time)})}\n\n"
                    last_heartbeat = current_time
                
                # Small sleep to prevent busy loop
                time.sleep(0.1)
                
                # TODO: In WAL-402/404, integrate actual fetcher here
                # For now, just send a complete event after 2 seconds to test
                if current_time - start_time > 2:
                    yield f"event: complete\ndata: {json.dumps({'status': 'complete', 'message': 'Stream scaffolding test complete'})}\n\n"
                    break
        
        # Create SSE response with proper headers
        response = Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
                "Connection": "keep-alive",
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error in SSE stream: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "version": "3.0"})


@app.route("/", methods=["GET"])
def home():
    """Home endpoint with API info"""
    return jsonify(
        {
            "service": "WalletDoctor API V3",
            "version": "3.0",
            "endpoints": {
                "/analyze": 'POST - Analyze wallet (body: {"wallet": "address"})',
                "/v4/analyze": 'POST - V4 Analyze wallet (body: {"wallet": "address"}) - Returns X-Progress-Token header',
                "/v4/prices": 'POST - Batch fetch prices (body: {"mints": [...], "timestamps": [...]})',
                "/v4/progress/{token}": "GET - Get progress status for long-running operations",
                "/v4/analyze/stream": "POST - SSE stream for wallet analysis results",
                "/health": "GET - Health check",
                "/": "GET - This info",
            },
            "features": [
                "Direct blockchain fetching via Helius",
                "Fallback parser for all DEX types",
                "Real-time price data from Birdeye",
                "Parse rate: ~100% with fallback parser",
            ],
            "limits": {"max_pages": 10, "reason": "API response time optimization"},
        }
    )


if __name__ == "__main__":
    # For development
    app.run(host="0.0.0.0", port=8080, debug=False)  # Debug mode can cause issues

    # For production, use gunicorn:
    # gunicorn -w 4 -b 0.0.0.0:8080 wallet_analytics_api_v3:app
