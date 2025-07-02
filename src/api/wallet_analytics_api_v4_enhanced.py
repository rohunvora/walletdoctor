#!/usr/bin/env python3
"""
WalletDoctor API V4 Enhanced - With Cache Staleness Support
WAL-607: Adds staleness marking and lazy refresh

Enhanced version of V4 API that supports cache eviction, staleness marking,
and lazy refresh for position data.
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
from src.lib.blockchain_fetcher_v3_fast import BlockchainFetcherV3Fast
from src.lib.progress_tracker import get_progress_tracker
from src.lib.progress_protocol import EventBuilder, ProgressData, ErrorData

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


@app.route("/v4/positions/<wallet_address>", methods=["GET"])
def get_wallet_positions_enhanced(wallet_address: str):
    """
    Enhanced position endpoint with staleness support
    
    Returns open positions with current values, unrealized P&L,
    and staleness indicators for cache management.
    
    Query params:
    - refresh: Force refresh from blockchain (default: false)
    
    Response includes:
    - stale: true if data is older than TTL
    - age_seconds: Age of cached data
    
    Response:
    {
        "wallet": "wallet_address",
        "positions": [
            {
                ...position data...,
                "stale": false
            }
        ],
        "summary": {
            "total_positions": 5,
            "total_value_usd": "1234.56",
            "total_unrealized_pnl_usd": "234.56",
            "total_unrealized_pnl_pct": "23.45"
        },
        "timestamp": "2024-01-01T00:00:00Z",
        "cached": true,
        "stale": false,
        "age_seconds": 120
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
        
        # Get enhanced cache
        cache = get_position_cache_v2()
        
        # Check cache first unless refresh requested
        if not force_refresh:
            # Try to get cached snapshot with staleness info
            cache_result = asyncio.run(cache.get_portfolio_snapshot(
                wallet_address,
                trigger_refresh=True  # Trigger background refresh if stale
            ))
            
            if cache_result:
                snapshot, is_stale = cache_result
                logger.info(f"Returning {'stale' if is_stale else 'fresh'} cached positions for {wallet_address}")
                
                result = snapshot.to_dict()
                result["wallet"] = wallet_address
                result["cached"] = True
                result["stale"] = is_stale
                
                # Calculate age
                age_seconds = int((datetime.utcnow() - snapshot.timestamp).total_seconds())
                result["age_seconds"] = age_seconds
                
                # Mark individual positions as stale if needed
                if is_stale and "positions" in result:
                    for pos in result["positions"]:
                        pos["stale"] = True
                
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
            positions = await calculate_positions(wallet_address, trades)
            
            # Calculate unrealized P&L if enabled
            if positions and should_calculate_unrealized_pnl():
                position_pnls = await calculate_unrealized_pnl(positions)
                
                # Create and cache snapshot
                snapshot = PositionSnapshot.from_positions(wallet_address, position_pnls)
                await cache.set_portfolio_snapshot(snapshot)
                
                # Invalidate old data
                await cache.invalidate_wallet(wallet_address)
                
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
                    "cached": False,
                    "stale": False,
                    "age_seconds": 0
                }
        
        result = asyncio.run(fetch_positions())
        
        # Convert to response format
        if isinstance(result, PositionSnapshot):
            response = result.to_dict()
            response["wallet"] = wallet_address
            response["cached"] = False
            response["stale"] = False
            response["age_seconds"] = 0
        else:
            response = result
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return jsonify({"error": str(e)}), 500


async def calculate_positions(wallet_address: str, trades: List[Dict[str, Any]]) -> List[Position]:
    """Calculate positions from trade history"""
    method = CostBasisMethod(get_cost_basis_method())
    builder = PositionBuilder(method)
    positions = builder.build_positions_from_trades(trades, wallet_address)
    return positions


async def calculate_unrealized_pnl(positions: List[Position]) -> List[PositionPnL]:
    """Calculate unrealized P&L for positions"""
    calculator = UnrealizedPnLCalculator()
    return await calculator.create_position_pnl_list(positions)


@app.route("/metrics", methods=["GET"])
def metrics():
    """
    Prometheus metrics endpoint
    
    Includes position cache metrics from WAL-607
    """
    cache = get_position_cache_v2()
    metrics = cache.get_metrics()
    
    # Format as Prometheus text format
    lines = []
    lines.append("# HELP position_cache_hits Total cache hits")
    lines.append("# TYPE position_cache_hits counter")
    lines.append(f"position_cache_hits {metrics['position_cache_hits']}")
    
    lines.append("# HELP position_cache_misses Total cache misses")
    lines.append("# TYPE position_cache_misses counter")
    lines.append(f"position_cache_misses {metrics['position_cache_misses']}")
    
    lines.append("# HELP position_cache_evictions Total cache evictions")
    lines.append("# TYPE position_cache_evictions counter")
    lines.append(f"position_cache_evictions {metrics['position_cache_evictions']}")
    
    lines.append("# HELP position_cache_refresh_errors Total refresh errors")
    lines.append("# TYPE position_cache_refresh_errors counter")
    lines.append(f"position_cache_refresh_errors {metrics['position_cache_refresh_errors']}")
    
    lines.append("# HELP position_cache_stale_serves Total stale data serves")
    lines.append("# TYPE position_cache_stale_serves counter")
    lines.append(f"position_cache_stale_serves {metrics['position_cache_stale_serves']}")
    
    lines.append("# HELP position_cache_refresh_triggers Total refresh triggers")
    lines.append("# TYPE position_cache_refresh_triggers counter")
    lines.append(f"position_cache_refresh_triggers {metrics['position_cache_refresh_triggers']}")
    
    return Response("\n".join(lines), mimetype="text/plain")


@app.route("/health", methods=["GET"])
def health_check():
    """Enhanced health check with cache stats"""
    cache = get_position_cache_v2()
    
    return jsonify({
        "status": "healthy",
        "version": "4.1",
        "features": {
            "positions_enabled": positions_enabled(),
            "unrealized_pnl_enabled": should_calculate_unrealized_pnl(),
            "cost_basis_method": get_cost_basis_method()
        },
        "cache_stats": cache.get_stats()
    })


if __name__ == "__main__":
    # For development
    app.run(host="0.0.0.0", port=8080, debug=False) 