#!/usr/bin/env python3
"""
WalletDoctor API V4 - GPT Export Enhancement
WAL-611: Export-for-GPT Endpoint

Adds GPT-friendly JSON export endpoint to the V4 API
with schema v1.1 support and API key authentication.
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
from datetime import datetime, timezone
from decimal import Decimal
from functools import wraps

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

# Core imports
from src.lib.blockchain_fetcher_v3_fast import BlockchainFetcherV3Fast
from src.lib.progress_tracker import get_progress_tracker

# P6 imports
from src.lib.position_builder import PositionBuilder
from src.lib.unrealized_pnl_calculator import UnrealizedPnLCalculator
from src.lib.position_cache_v2 import get_position_cache_v2
from src.lib.position_models import Position, PositionPnL, PositionSnapshot, CostBasisMethod
from src.config.feature_flags import positions_enabled, should_calculate_unrealized_pnl, get_cost_basis_method

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
API_KEY_HEADER = os.getenv('API_KEY_HEADER', 'X-Api-Key')
API_KEY_PREFIX = os.getenv('API_KEY_PREFIX', 'wd_')
API_KEY_LENGTH = 35  # wd_ + 32 chars


def simple_auth_required(f):
    """Simple API key authentication decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get API key from header
        api_key = request.headers.get(API_KEY_HEADER)
        
        # Check if API key is provided
        if not api_key:
            logger.warning(f"Missing API key from {request.remote_addr}")
            return jsonify({
                "error": "API key required",
                "message": f"Please provide API key via {API_KEY_HEADER} header"
            }), 401
        
        # Validate API key format
        if not api_key.startswith(API_KEY_PREFIX) or len(api_key) != API_KEY_LENGTH:
            logger.warning(f"Invalid API key format from {request.remote_addr}: {api_key[:10]}...")
            return jsonify({
                "error": "Invalid API key",
                "message": "API key must be in format wd_<32-chars>"
            }), 401
        
        # In production, validate against database
        # For now, accept any properly formatted key
        logger.info(f"Authenticated request from {request.remote_addr} with key {api_key[:10]}...")
        
        # Store API key in request context
        g.api_key = api_key
        
        return f(*args, **kwargs)
    
    return decorated_function


def format_gpt_schema_v1_1(snapshot: PositionSnapshot, base_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Format position snapshot into GPT schema v1.1
    
    Based on docs/future-gpt-action.md specification
    """
    positions_data = []
    stale_price_count = 0
    
    for position_pnl in snapshot.positions:
        position = position_pnl.position
        
        # Determine price confidence
        if position_pnl.price_confidence.value == "high":
            price_confidence = "high"
        elif position_pnl.price_confidence.value == "est":
            price_confidence = "est"
        else:
            price_confidence = "stale"
            stale_price_count += 1
        
        position_data = {
            "position_id": position.position_id,
            "token_symbol": position.token_symbol,
            "token_mint": position.token_mint,
            "balance": str(position.balance),  # String for precision
            "decimals": position.decimals,
            "cost_basis_usd": str(position.cost_basis_usd),
            "current_price_usd": str(position_pnl.current_price_usd),
            "current_value_usd": str(position_pnl.current_value_usd),
            "unrealized_pnl_usd": str(position_pnl.unrealized_pnl_usd),
            "unrealized_pnl_pct": f"{position_pnl.unrealized_pnl_pct:.2f}",
            "price_confidence": price_confidence,
            "price_age_seconds": position_pnl.price_age_seconds,
            "opened_at": position.opened_at.isoformat() + "Z",
            "last_trade_at": position.last_trade_at.isoformat() + "Z"
        }
        
        positions_data.append(position_data)
    
    # Calculate summary
    total_positions = len(positions_data)
    total_value_usd = str(snapshot.total_value_usd)
    total_unrealized_pnl_usd = str(snapshot.total_unrealized_pnl_usd)
    total_unrealized_pnl_pct = f"{snapshot.total_unrealized_pnl_pct:.2f}"
    
    # Get base URL - use provided or try request context
    if not base_url:
        try:
            base_url = request.host_url.rstrip('/')
        except RuntimeError:
            base_url = "https://walletdoctor.app"
    
    return {
        "schema_version": "1.1",
        "wallet": snapshot.wallet,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "positions": positions_data,
        "summary": {
            "total_positions": total_positions,
            "total_value_usd": total_value_usd,
            "total_unrealized_pnl_usd": total_unrealized_pnl_usd,
            "total_unrealized_pnl_pct": total_unrealized_pnl_pct,
            "stale_price_count": stale_price_count
        },
        "price_sources": {
            "primary": f"{base_url}/v4/prices",
            "primary_hint": "POST {mints: [string], timestamps: [number]} returns {mint: price_usd} in JSON",
            "fallback": "https://api.coingecko.com/api/v3/simple/price",
            "fallback_hint": "GET ?ids={coingecko_id}&vs_currencies=usd returns {id: {usd: price}} in JSON"
        }
    }


async def get_positions_with_staleness(wallet_address: str) -> tuple[Optional[PositionSnapshot], bool, int]:
    """
    Get positions with staleness info
    
    Returns:
        (snapshot, is_stale, age_seconds)
    """
    cache = get_position_cache_v2()
    
    # Check cache
    cached_result = await cache.get_portfolio_snapshot(wallet_address)
    
    if cached_result:
        snapshot, is_stale = cached_result
        # Calculate age from snapshot timestamp
        age_seconds = int((datetime.now(timezone.utc) - snapshot.timestamp).total_seconds())
        return snapshot, is_stale, age_seconds
    
    # No cached data, need to fetch
    logger.info(f"No cached data for {wallet_address}, fetching fresh")
    
    # Fetch trades
    async with BlockchainFetcherV3Fast(skip_pricing=False) as fetcher:
        result = await fetcher.fetch_wallet_trades(wallet_address)
    
    trades = result.get("trades", [])
    
    # Calculate positions
    method = CostBasisMethod(get_cost_basis_method())
    builder = PositionBuilder(method)
    positions = builder.build_positions_from_trades(trades, wallet_address)
    
    # Calculate unrealized P&L
    if positions and should_calculate_unrealized_pnl():
        calculator = UnrealizedPnLCalculator()
        position_pnls = await calculator.create_position_pnl_list(positions)
        
        # Create snapshot
        snapshot = PositionSnapshot.from_positions(wallet_address, position_pnls)
        
        # Cache it
        await cache.set_portfolio_snapshot(snapshot)
        
        return snapshot, False, 0  # Fresh data
    
    # Return empty snapshot if no positions
    return PositionSnapshot(
        wallet=wallet_address,
        timestamp=datetime.now(timezone.utc),
        positions=[],
        total_value_usd=Decimal("0"),
        total_unrealized_pnl_usd=Decimal("0"),
        total_unrealized_pnl_pct=Decimal("0")
    ), False, 0


@app.route("/v4/positions/export-gpt/<wallet_address>", methods=["GET"])
@simple_auth_required
def export_positions_for_gpt(wallet_address: str):
    """
    Export positions in GPT-friendly format
    
    GET /v4/positions/export-gpt/{wallet}
    
    Query params:
    - schema_version: Schema version (default: 1.1)
    
    Headers:
    - X-Api-Key: API key for authentication
    
    Response:
    - 200: GPT schema v1.1 JSON with positions
    - 401: Authentication error
    - 404: Wallet not found
    - 500: Server error
    
    Performance targets:
    - <200ms for cached data
    - <1.5s for cold fetch
    """
    start_time = time.time()
    
    try:
        # Validate wallet address
        if not wallet_address or len(wallet_address) < 32:
            return jsonify({
                "error": "Invalid wallet address",
                "message": "Wallet address must be at least 32 characters"
            }), 400
        
        # Get schema version
        schema_version = request.args.get("schema_version", "1.1")
        if schema_version != "1.1":
            return jsonify({
                "error": "Unsupported schema version",
                "message": f"Schema version {schema_version} not supported. Use 1.1"
            }), 400
        
        # Check if positions are enabled
        if not positions_enabled():
            return jsonify({
                "error": "Feature disabled",
                "message": "Position tracking is not enabled"
            }), 501
        
        logger.info(f"GPT export request for wallet: {wallet_address}")
        
        # Get positions with staleness info
        snapshot, is_stale, age_seconds = asyncio.run(
            get_positions_with_staleness(wallet_address)
        )
        
        if not snapshot or (not snapshot.positions and age_seconds == 0):
            # No data found
            duration_ms = (time.time() - start_time) * 1000
            error_response = jsonify({
                "error": "Wallet not found",
                "message": f"No trading data found for wallet {wallet_address}"
            })
            error_response.headers['X-Response-Time-Ms'] = f"{duration_ms:.2f}"
            return error_response, 404
        
        # Format response
        response_data = format_gpt_schema_v1_1(snapshot)
        
        # Add staleness info if applicable
        if is_stale:
            response_data["stale"] = True
            response_data["age_seconds"] = age_seconds
        
        # Calculate response time
        duration_ms = (time.time() - start_time) * 1000
        
        # Log performance
        logger.info(
            f"GPT export completed: wallet={wallet_address[:8]}..., "
            f"positions={len(snapshot.positions)}, "
            f"stale={is_stale}, "
            f"duration_ms={duration_ms:.2f}"
        )
        
        # Create response with performance header
        response = make_response(jsonify(response_data))
        response.headers['X-Response-Time-Ms'] = f"{duration_ms:.2f}"
        response.headers['X-Cache-Status'] = 'HIT' if is_stale else 'MISS'
        
        return response
        
    except Exception as e:
        logger.error(f"Error in GPT export: {e}")
        duration_ms = (time.time() - start_time) * 1000
        
        error_response = jsonify({
            "error": "Internal server error",
            "message": "Failed to export position data"
        })
        error_response.headers['X-Response-Time-Ms'] = f"{duration_ms:.2f}"
        
        return error_response, 500


@app.route("/v4/positions/warm-cache/<wallet_address>", methods=["POST"])
@simple_auth_required  
async def warm_cache(wallet_address: str):
    """
    Pre-warm the cache for a wallet
    
    POST /v4/positions/warm-cache/{wallet}
    
    This endpoint triggers a background cache population for the wallet,
    allowing subsequent GPT export calls to return instantly.
    
    Returns immediately with a status indicating warming has started.
    """
    try:
        # Validate wallet address
        if not wallet_address or len(wallet_address) < 32:
            return jsonify({
                "error": "Invalid wallet address",
                "message": "Wallet address must be at least 32 characters"
            }), 400
        
        logger.info(f"Cache warming request for wallet: {wallet_address}")
        
        # Check if already cached
        cache = get_position_cache_v2()
        cached_result = await cache.get_portfolio_snapshot(wallet_address)
        
        if cached_result:
            snapshot, is_stale = cached_result
            age_seconds = int((datetime.now(timezone.utc) - snapshot.timestamp).total_seconds())
            
            # If data is fresh (< 5 minutes), no need to warm
            if age_seconds < 300:
                return jsonify({
                    "status": "already_cached",
                    "age_seconds": age_seconds,
                    "positions": len(snapshot.positions),
                    "message": "Cache is already warm"
                })
        
        # Start warming in background
        # For now, do it synchronously but return quickly
        # In production, this would be a background task
        
        # Create a simple progress token for tracking
        tracker = get_progress_tracker()
        progress_token = tracker.create_progress()
        
        # Initialize progress
        tracker.update_progress(
            progress_token,
            status="warming",
            trades_found=0
        )
        
        # Run the warming process
        async def warm_cache_task():
            try:
                logger.info(f"Starting cache warm for {wallet_address}")
                start_time = time.time()
                
                # Fetch trades
                async with BlockchainFetcherV3Fast(skip_pricing=False) as fetcher:
                    result = await fetcher.fetch_wallet_trades(wallet_address)
                
                trades = result.get("trades", [])
                logger.info(f"Fetched {len(trades)} trades in {time.time() - start_time:.1f}s")
                
                # Calculate positions
                method = CostBasisMethod(get_cost_basis_method())
                builder = PositionBuilder(method)
                positions = builder.build_positions_from_trades(trades, wallet_address)
                
                # Calculate unrealized P&L
                if positions and should_calculate_unrealized_pnl():
                    calculator = UnrealizedPnLCalculator()
                    position_pnls = await calculator.create_position_pnl_list(positions)
                    
                    # Create snapshot
                    snapshot = PositionSnapshot.from_positions(wallet_address, position_pnls)
                    
                    # Cache it
                    await cache.set_portfolio_snapshot(snapshot)
                    
                    duration = time.time() - start_time
                    logger.info(f"Cache warmed for {wallet_address} in {duration:.1f}s")
                    
                    # Update progress
                    tracker.update_progress(
                        progress_token,
                        status="complete",
                        trades_found=len(trades)
                    )
                else:
                    tracker.update_progress(
                        progress_token,
                        status="complete"
                    )
                    
            except Exception as e:
                logger.error(f"Error warming cache: {e}")
                tracker.update_progress(
                    progress_token,
                    status="error",
                    error=str(e)
                )
        
        # Start the task (in production, use proper background task queue)
        asyncio.create_task(warm_cache_task())
        
        return jsonify({
            "status": "warming_started",
            "progress_token": progress_token,
            "message": "Cache warming initiated",
            "check_progress_url": f"/v4/progress/{progress_token}"
        })
        
    except Exception as e:
        logger.error(f"Error in cache warming: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": "Failed to start cache warming"
        }), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "WalletDoctor GPT Export API",
        "version": "1.1",
        "features": {
            "positions_enabled": positions_enabled(),
            "unrealized_pnl_enabled": should_calculate_unrealized_pnl(),
            "cost_basis_method": get_cost_basis_method()
        }
    })


@app.route("/", methods=["GET"])
def home():
    """Home endpoint with API info"""
    return jsonify({
        "service": "WalletDoctor GPT Export API",
        "version": "1.1",
        "endpoints": {
            "/v4/positions/export-gpt/{wallet}": "GET - Export positions in GPT schema v1.1",
            "/health": "GET - Health check",
            "/": "GET - This info"
        },
        "authentication": {
            "required": True,
            "header": API_KEY_HEADER,
            "format": "wd_<32-characters>"
        },
        "schema_versions": ["1.1"],
        "documentation": "/docs/future-gpt-action.md"
    })


if __name__ == "__main__":
    # For development
    app.run(host="0.0.0.0", port=8081, debug=False) 