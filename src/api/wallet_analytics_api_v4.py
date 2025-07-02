#!/usr/bin/env python3
"""
WalletDoctor API V4 - Enhanced with Position Tracking
WAL-606: API Endpoint Enhancement

Adds unrealized P&L and open position tracking to the existing V3 API
while maintaining backward compatibility through feature flags.
"""

from flask import Flask, request, jsonify, make_response, Response
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

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

# Core imports
from src.lib.blockchain_fetcher_v3 import BlockchainFetcherV3
from src.lib.blockchain_fetcher_v3_fast import BlockchainFetcherV3Fast
from src.lib.progress_tracker import get_progress_tracker
from src.lib.progress_protocol import EventBuilder, ProgressData, ErrorData

# P6 imports
from src.lib.position_builder import PositionBuilder
from src.lib.unrealized_pnl_calculator import UnrealizedPnLCalculator
from src.lib.position_cache import get_position_cache
from src.lib.position_models import Position, PositionPnL, PositionSnapshot, CostBasisMethod
from src.config.feature_flags import positions_enabled, should_calculate_unrealized_pnl, get_cost_basis_method

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


async def fetch_and_analyze_v4(
    wallet_address: str, 
    progress_token: Optional[str] = None,
    include_positions: bool = True
) -> Dict[str, Any]:
    """
    Enhanced V4 fetch that includes position tracking
    
    Args:
        wallet_address: Wallet to analyze
        progress_token: Optional progress tracking token
        include_positions: Whether to calculate positions
        
    Returns:
        Analysis result with optional position data
    """
    logger.info(f"Starting V4 analysis for wallet: {wallet_address}")

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
            
            # Get position cache
            cache = get_position_cache()
            
            # Check cache first
            cached_snapshot = await cache.get_portfolio_snapshot(wallet_address)
            
            if cached_snapshot and _is_cache_fresh(cached_snapshot.timestamp):
                # Use cached data
                logger.info(f"Using cached position data for {wallet_address}")
                result["positions"] = [p.to_dict() for p in cached_snapshot.positions]
                result["position_summary"] = cached_snapshot.to_dict()["summary"]
            else:
                # Calculate positions
                positions = await calculate_positions(
                    wallet_address,
                    result.get("trades", [])
                )
                
                # Calculate unrealized P&L if enabled
                if positions and should_calculate_unrealized_pnl():
                    position_pnls = await calculate_unrealized_pnl(positions)
                    
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
                else:
                    # Just add positions without P&L
                    result["positions"] = [p.to_dict() for p in positions]
                    result["position_summary"] = {
                        "total_positions": len(positions),
                        "message": "Unrealized P&L calculation disabled"
                    }
                
                # Invalidate cache on new data
                await cache.invalidate_wallet_positions(wallet_address)
                
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

    return result


async def calculate_positions(wallet_address: str, trades: List[Dict[str, Any]]) -> List[Position]:
    """
    Calculate positions from trade history
    
    Args:
        wallet_address: Wallet address
        trades: List of trade dictionaries
        
    Returns:
        List of Position objects
    """
    # Initialize position builder
    method = CostBasisMethod(get_cost_basis_method())
    builder = PositionBuilder(method)
    
    # Build positions
    positions = builder.build_positions_from_trades(trades, wallet_address)
    
    # Return the open positions
    return positions


async def calculate_unrealized_pnl(positions: List[Position]) -> List[PositionPnL]:
    """
    Calculate unrealized P&L for positions
    
    Args:
        positions: List of Position objects
        
    Returns:
        List of PositionPnL objects
    """
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
    """
    V4 API endpoint - Enhanced with position tracking
    
    Request body:
    {
        "wallet": "wallet_address",
        "include_positions": true  // Optional, defaults to true
    }
    
    Response includes:
    - All V3 data (trades, summary)
    - positions: Array of open positions with unrealized P&L
    - position_summary: Portfolio-level statistics
    - totals: Combined realized + unrealized P&L
    - X-Progress-Token header for tracking
    """
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

        # Run async function with progress tracking
        result = asyncio.run(fetch_and_analyze_v4(
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
    """
    Get current positions for a wallet
    
    Returns open positions with current values and unrealized P&L.
    Uses cache when available for performance.
    
    Query params:
    - refresh: Force refresh from blockchain (default: false)
    
    Response:
    {
        "wallet": "wallet_address",
        "positions": [...],
        "summary": {
            "total_positions": 5,
            "total_value_usd": "1234.56",
            "total_unrealized_pnl_usd": "234.56",
            "total_unrealized_pnl_pct": "23.45"
        },
        "timestamp": "2024-01-01T00:00:00Z",
        "cached": false
    }
    """
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
                return jsonify(result)
        
        # Fetch fresh data
        logger.info(f"Fetching fresh positions for {wallet_address}")
        
        # Fetch trades
        async def fetch_positions():
            # Get trades
            async with BlockchainFetcherV3(skip_pricing=False) as fetcher:
                trade_data = await fetcher.fetch_wallet_trades(wallet_address)
            
            trades = trade_data.get("trades", [])
            
            # Calculate positions
            positions = await calculate_positions(wallet_address, trades)
            
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


@app.route("/v4/progress/<token>", methods=["GET"])
def get_progress(token):
    """
    Get progress status for a long-running operation
    
    Enhanced to include position calculation progress.
    
    Returns:
    {
        "token": "uuid",
        "status": "calculating_positions",  // New status
        "pages": 45,
        "total": 72,
        "trades": 3500,
        "positions_calculated": 12,  // New field
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


@app.route("/health", methods=["GET"])
def health_check():
    """Enhanced health check with feature flags"""
    return jsonify({
        "status": "healthy",
        "version": "4.0",
        "features": {
            "positions_enabled": positions_enabled(),
            "unrealized_pnl_enabled": should_calculate_unrealized_pnl(),
            "cost_basis_method": get_cost_basis_method()
        },
        "cache_stats": get_position_cache().get_stats()
    })


@app.route("/", methods=["GET"])
def home():
    """Home endpoint with V4 API info"""
    return jsonify({
        "service": "WalletDoctor API V4",
        "version": "4.0",
        "endpoints": {
            "/v4/analyze": 'POST - Analyze wallet with positions (body: {"wallet": "address", "include_positions": true})',
            "/v4/positions/{wallet}": "GET - Get current positions for a wallet",
            "/v4/progress/{token}": "GET - Get progress status for long-running operations",
            "/health": "GET - Health check with feature flags",
            "/": "GET - This info",
        },
        "features": [
            "Direct blockchain fetching via Helius",
            "Open position tracking with cost basis",
            "Unrealized P&L calculation",
            "Combined realized + unrealized P&L totals",
            "Redis-backed position caching",
            "Feature flag controlled rollout"
        ],
        "position_features": {
            "enabled": positions_enabled(),
            "unrealized_pnl": should_calculate_unrealized_pnl(),
            "cost_basis_method": get_cost_basis_method()
        }
    })


if __name__ == "__main__":
    # For development
    app.run(host="0.0.0.0", port=8080, debug=False)
    
    # For production, use gunicorn:
    # gunicorn -w 4 -b 0.0.0.0:8080 src.api.wallet_analytics_api_v4:app 