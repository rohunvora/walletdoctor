#!/usr/bin/env python3
"""
Market Cap API - Endpoints for retrieving market cap data
"""

import os
import asyncio
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import logging
from typing import Optional, Dict, Any, List
from decimal import Decimal

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import our modules
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.mc_calculator import calculate_market_cap, MarketCapResult
from lib.mc_cache import get_cache
from lib.mc_precache_service import get_precache_service

# Create Flask app
app = Flask(__name__)
CORS(app)

# Constants
DEFAULT_TIMEOUT = 30  # seconds


def decimal_to_float(obj):
    """Convert Decimal objects to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    return obj


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "market_cap_api",
        "timestamp": int(datetime.now().timestamp())
    })


@app.route('/v1/market-cap/<token_mint>', methods=['GET'])
async def get_market_cap(token_mint: str):
    """
    Get market cap for a specific token
    
    Query Parameters:
    - slot: Optional slot number for historical data
    - timestamp: Optional unix timestamp for cache lookup
    - use_cache: Whether to use cache (default: true)
    """
    try:
        # Parse query parameters
        slot = request.args.get('slot', type=int)
        timestamp = request.args.get('timestamp', type=int)
        use_cache = request.args.get('use_cache', 'true').lower() == 'true'
        
        # Track request in pre-cache service
        precache_service = get_precache_service()
        if precache_service:
            # Check if we have a cache hit first
            if use_cache and timestamp:
                cache = get_cache()
                if cache:
                    cached_data = cache.get(token_mint, timestamp)
                    if cached_data:
                        precache_service.track_request(token_mint, cache_hit=True)
                    else:
                        precache_service.track_request(token_mint, cache_hit=False)
                else:
                    precache_service.track_request(token_mint, cache_hit=False)
            else:
                precache_service.track_request(token_mint, cache_hit=False)
        
        # Calculate market cap
        result = await calculate_market_cap(
            token_mint=token_mint,
            slot=slot,
            timestamp=timestamp,
            use_cache=use_cache
        )
        
        # Build response
        response = {
            "token_mint": token_mint,
            "market_cap": decimal_to_float(result.value) if result.value else None,
            "confidence": result.confidence,
            "source": result.source,
            "supply": decimal_to_float(result.supply) if result.supply else None,
            "price": decimal_to_float(result.price) if result.price else None,
            "timestamp": result.timestamp,
            "slot": slot,
            "cached": result.source and result.source.startswith("cache_") if result.source else False
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting market cap for {token_mint}: {e}")
        return jsonify({
            "error": str(e),
            "token_mint": token_mint
        }), 500


@app.route('/v1/market-cap/batch', methods=['POST'])
async def get_batch_market_caps():
    """
    Get market caps for multiple tokens
    
    Request body:
    {
        "tokens": [
            {
                "mint": "token_mint_address",
                "slot": 12345,  // optional
                "timestamp": 1234567890  // optional
            }
        ],
        "use_cache": true  // optional, default true
    }
    """
    try:
        data = request.get_json()
        if not data or 'tokens' not in data:
            return jsonify({"error": "Missing 'tokens' in request body"}), 400
        
        tokens = data['tokens']
        use_cache = data.get('use_cache', True)
        
        # Limit batch size
        if len(tokens) > 50:
            return jsonify({"error": "Maximum 50 tokens per batch"}), 400
        
        # Track requests
        precache_service = get_precache_service()
        
        # Process tokens in parallel
        tasks = []
        for token_data in tokens:
            if isinstance(token_data, str):
                # Simple format: just mint address
                mint = token_data
                slot = None
                timestamp = None
            else:
                # Complex format: object with mint, slot, timestamp
                mint = token_data.get('mint')
                slot = token_data.get('slot')
                timestamp = token_data.get('timestamp')
            
            if not mint:
                continue
            
            # Track request
            if precache_service:
                precache_service.track_request(mint, cache_hit=False)
            
            # Create task
            task = calculate_market_cap(
                token_mint=mint,
                slot=slot,
                timestamp=timestamp,
                use_cache=use_cache
            )
            tasks.append((mint, slot, timestamp, task))
        
        # Wait for all calculations
        results = []
        for mint, slot, timestamp, task in tasks:
            try:
                result = await task
                results.append({
                    "token_mint": mint,
                    "market_cap": decimal_to_float(result.value) if result.value else None,
                    "confidence": result.confidence,
                    "source": result.source,
                    "supply": decimal_to_float(result.supply) if result.supply else None,
                    "price": decimal_to_float(result.price) if result.price else None,
                    "timestamp": result.timestamp,
                    "slot": slot,
                    "cached": result.source and result.source.startswith("cache_") if result.source else False
                })
            except Exception as e:
                logger.error(f"Error calculating MC for {mint}: {e}")
                results.append({
                    "token_mint": mint,
                    "error": str(e)
                })
        
        return jsonify({
            "results": results,
            "count": len(results)
        })
        
    except Exception as e:
        logger.error(f"Error in batch market cap: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/v1/market-cap/stats', methods=['GET'])
def get_stats():
    """Get market cap service statistics"""
    try:
        stats: Dict[str, Any] = {
            "cache": None,
            "precache_service": None
        }
        
        # Get cache stats
        try:
            cache = get_cache()
            if cache:
                cache_stats = cache.get_stats()
                stats["cache"] = cache_stats
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
        
        # Get pre-cache service stats
        precache_service = get_precache_service()
        if precache_service:
            stats["precache_service"] = precache_service.get_stats()
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/v1/market-cap/popular', methods=['GET'])
async def get_popular_tokens():
    """
    Get market caps for popular tokens
    
    Query parameters:
    - limit: Maximum number of tokens (default 20)
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        
        # Popular tokens list
        from lib.mc_precache_service import POPULAR_TOKENS
        
        # Get first N popular tokens
        tokens = list(POPULAR_TOKENS)[:limit]
        
        # Calculate market caps
        tasks = []
        for token in tokens:
            task = calculate_market_cap(token, use_cache=True)
            tasks.append((token, task))
        
        # Build results
        results = []
        for token, task in tasks:
            try:
                result = await task
                results.append({
                    "token_mint": token,
                    "market_cap": decimal_to_float(result.value) if result.value else None,
                    "confidence": result.confidence,
                    "source": result.source,
                    "price": decimal_to_float(result.price) if result.price else None,
                    "timestamp": result.timestamp
                })
            except Exception as e:
                logger.error(f"Error getting MC for popular token {token}: {e}")
        
        # Sort by market cap (highest first)
        results.sort(key=lambda x: x.get('market_cap') or 0, reverse=True)
        
        return jsonify({
            "tokens": results,
            "count": len(results)
        })
        
    except Exception as e:
        logger.error(f"Error getting popular tokens: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/v1/market-cap/trending', methods=['GET'])
async def get_trending_tokens():
    """
    Get market caps for trending tokens
    
    Query parameters:
    - limit: Maximum number of tokens (default 20)
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        
        # Get trending tokens from pre-cache service
        precache_service = get_precache_service()
        if not precache_service:
            return jsonify({
                "error": "Pre-cache service not available",
                "tokens": [],
                "count": 0
            })
        
        # Get tracked tokens sorted by request count
        token_stats = sorted(
            precache_service.token_stats.items(),
            key=lambda x: x[1]["request_count"],
            reverse=True
        )
        
        # Get top requested tokens
        trending_tokens = [token for token, _ in token_stats[:limit]]
        
        # Calculate market caps
        tasks = []
        for token in trending_tokens:
            task = calculate_market_cap(token, use_cache=True)
            tasks.append((token, task))
        
        # Build results
        results = []
        for token, task in tasks:
            try:
                result = await task
                stats = precache_service.token_stats[token]
                results.append({
                    "token_mint": token,
                    "market_cap": decimal_to_float(result.value) if result.value else None,
                    "confidence": result.confidence,
                    "source": result.source,
                    "price": decimal_to_float(result.price) if result.price else None,
                    "timestamp": result.timestamp,
                    "request_count": stats["request_count"],
                    "cache_hits": stats["cache_hits"]
                })
            except Exception as e:
                logger.error(f"Error getting MC for trending token {token}: {e}")
        
        return jsonify({
            "tokens": results,
            "count": len(results)
        })
        
    except Exception as e:
        logger.error(f"Error getting trending tokens: {e}")
        return jsonify({"error": str(e)}), 500


# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500


# Run with asyncio support
if __name__ == '__main__':
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    
    # Use Flask's built-in async support
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('MC_API_PORT', 5001)),
        debug=os.getenv('FLASK_ENV') == 'development'
    ) 