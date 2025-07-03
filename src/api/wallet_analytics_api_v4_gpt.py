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
import concurrent.futures
import hashlib
import traceback
import uuid
import subprocess

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
logging.basicConfig(
    level=logging.DEBUG if os.getenv('FLASK_DEBUG', '').lower() == 'true' or os.getenv('LOG_LEVEL', '').lower() == 'debug' else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Generate a unique worker ID at startup
WORKER_ID = str(uuid.uuid4())[:8]
STARTUP_TIME = datetime.now(timezone.utc).isoformat()

# Log startup info immediately with worker ID
logger.info("="*60)
logger.info(f"[BOOT] WalletDoctor GPT API Starting - Worker {WORKER_ID}")
logger.info(f"[BOOT] Startup time: {STARTUP_TIME}")
logger.info(f"[BOOT] HELIUS_KEY present: {bool(os.getenv('HELIUS_KEY'))}")
logger.info(f"[BOOT] BIRDEYE_API_KEY present: {bool(os.getenv('BIRDEYE_API_KEY'))}")
logger.info(f"[BOOT] POSITIONS_ENABLED: {os.getenv('POSITIONS_ENABLED', 'false')}")
logger.info(f"[BOOT] PRICE_HELIUS_ONLY: {os.getenv('PRICE_HELIUS_ONLY', 'false')}")
logger.info(f"[BOOT] POSITION_CACHE_TTL_SEC: {os.getenv('POSITION_CACHE_TTL_SEC', 'NOT SET')}")
logger.info(f"[BOOT] Python version: {sys.version}")

# Create env checksum for verification
env_string = f"{os.getenv('PRICE_HELIUS_ONLY', '')}:{os.getenv('POSITION_CACHE_TTL_SEC', '')}:{os.getenv('POSITIONS_ENABLED', '')}"
env_checksum = hashlib.md5(env_string.encode()).hexdigest()[:8]
logger.info(f"[BOOT] Environment checksum: {env_checksum}")

# Add commit SHA for deployment verification
try:
    BOOT_SHA = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
    logger.info(f"[BOOT] commit_sha={BOOT_SHA}")
except:
    logger.info(f"[BOOT] commit_sha=unknown")
sys.stdout.flush()

logger.info("="*60)

app = Flask(__name__)
CORS(app)

# Global error handler for debugging
@app.errorhandler(Exception)
def handle_exception(e):
    """Log exceptions before returning 500"""
    import traceback
    logger.error(f"Unhandled exception: {e}")
    logger.error(traceback.format_exc())
    return jsonify({
        "error": "Internal server error",
        "message": str(e),
        "traceback": traceback.format_exc() if os.getenv('FLASK_DEBUG', '').lower() == 'true' else None
    }), 500

# Configuration
API_KEY_HEADER = os.getenv('API_KEY_HEADER', 'X-Api-Key')
API_KEY_PREFIX = os.getenv('API_KEY_PREFIX', 'wd_')
API_KEY_LENGTH = 35  # wd_ + 32 chars


def run_async(coro):
    """
    Safely run async code in Flask/gunicorn environment
    
    This handles event loop issues that can occur with asyncio.run()
    in production environments.
    """
    try:
        # Try to get the running loop
        loop = asyncio.get_running_loop()
        # If we're in a running loop, create a new event loop in a thread
        logger.debug("Running async code in thread due to existing event loop")
        
        # Create a new event loop in a thread
        import threading
        result = None
        exception = None
        
        def run_in_thread():
            nonlocal result, exception
            try:
                # Create a new event loop for this thread
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result = new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()
            except Exception as e:
                exception = e
        
        thread = threading.Thread(target=run_in_thread)
        thread.start()
        thread.join()
        
        if exception:
            raise exception
        return result
        
    except RuntimeError:
        # No loop running, safe to use asyncio.run
        logger.debug("No event loop running, using asyncio.run directly")
        return asyncio.run(coro)


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
        if position_pnl.current_price_usd is None:
            price_confidence = "unpriced"
        elif position_pnl.price_confidence.value == "high":
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
            "current_price_usd": str(position_pnl.current_price_usd) if position_pnl.current_price_usd is not None else None,
            "current_value_usd": str(position_pnl.current_value_usd) if position_pnl.current_value_usd is not None else None,
            "unrealized_pnl_usd": str(position_pnl.unrealized_pnl_usd) if position_pnl.unrealized_pnl_usd is not None else None,
            "unrealized_pnl_pct": f"{position_pnl.unrealized_pnl_pct:.2f}" if position_pnl.unrealized_pnl_pct is not None else None,
            "price_confidence": price_confidence,
            "price_age_seconds": position_pnl.price_age_seconds if position_pnl.current_price_usd is not None else None,
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


async def get_positions_with_staleness(wallet_address: str, skip_pricing: bool = False) -> tuple[Optional[PositionSnapshot], bool, int]:
    """
    Get positions with staleness info - MINIMAL PHASE STAMPS
    
    Returns:
        (snapshot, is_stale, age_seconds)
    """
    # Minimal phase timing setup
    PHASE = time.perf_counter
    start = PHASE()
    log = lambda label: logger.info(f"[PHASE] {label} ms={int((PHASE()-start)*1000)}")
    
    log("start_request")
    
    cache = get_position_cache_v2()
    
    # Check cache (unless we're skipping pricing, then always fetch fresh)
    if not skip_pricing:
        cached_result = await cache.get_portfolio_snapshot(wallet_address)
        
        if cached_result:
            snapshot, is_stale = cached_result
            # Calculate age from snapshot timestamp
            age_seconds = int((datetime.now(timezone.utc) - snapshot.timestamp).total_seconds())
            log("response_sent")
            return snapshot, is_stale, age_seconds
    
    # No cached data, need to fetch
    try:
        async with BlockchainFetcherV3Fast(skip_pricing=skip_pricing) as fetcher:
            result = await fetcher.fetch_wallet_trades(wallet_address)
        
        logger.info(f"[CHECK] sigs_received_in_api={len(result.get('signatures', []))} id={id(result.get('signatures', []))}")
        
        log("helius_signatures_fetched")
        log("transactions_fetched")
        log("trades_extracted")
        
    except Exception as e:
        logger.error(f"[PHASE] helius_fetch failed: {str(e)}")
        raise
    
    # Extract data and log counts
    signatures = result.get("signatures", [])
    import sys
    app.logger.info("[CHECK] helius_signatures_post_call=%d", len(signatures))
    sys.stdout.flush()
    app.logger.info("[CHECK] helius_signatures=%d", len(signatures))
    
    trades = result.get("trades", [])
    app.logger.info("[CHECK] trades_raw=%d", len(trades))
    
    # Calculate positions
    method = CostBasisMethod(get_cost_basis_method())
    builder = PositionBuilder(method)
    positions = builder.build_positions_from_trades(trades, wallet_address)
    app.logger.info("[CHECK] positions_raw=%d", len(positions))
    
    # hard-flush so the lines always hit the log
    for h in app.logger.handlers:
        try:
            h.flush()
        except Exception:
            pass
    
    log("positions_built")
    
    # Calculate unrealized P&L
    if positions and should_calculate_unrealized_pnl():
        log("price_lookup_started")
        calculator = UnrealizedPnLCalculator()
        
        # Pass transactions and trades for Helius price extraction
        if os.getenv('PRICE_HELIUS_ONLY', '').lower() == 'true':
            calculator.trades = trades
            calculator.transactions = result.get("transactions", [])
        
        position_pnls = await calculator.create_position_pnl_list(positions, skip_pricing=skip_pricing)
        log("price_lookup_finished")
        
        # Create snapshot
        snapshot = PositionSnapshot.from_positions(wallet_address, position_pnls)
        app.logger.info("[CHECK] positions_after_filter=%d", len(snapshot.positions))
        
        # Cache it
        await cache.set_portfolio_snapshot(snapshot)
        
        log("response_sent")
        return snapshot, False, 0  # Fresh data
    
    # Return empty snapshot if no positions
    log("response_sent")
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
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    phase_times = {}
    
    # Initialize these before try block for exception handler access
    skip_pricing = False
    beta_mode = False
    
    # Log request details immediately
    logger.info(f"[REQUEST-{request_id}] Worker {WORKER_ID} handling export-gpt for {wallet_address[:8]}...")
    logger.info(f"[REQUEST-{request_id}] Query params: {dict(request.args)}")
    logger.info(f"[REQUEST-{request_id}] Env check: PRICE_HELIUS_ONLY={os.getenv('PRICE_HELIUS_ONLY')}, checksum={env_checksum}")
    
    try:
        # Phase 0: Request validation
        phase_start = time.time()
        logger.info(f"[PHASE-{request_id}] Starting request validation...")
        # Validate wallet address
        if not wallet_address or len(wallet_address) < 32:
            phase_times["validation"] = time.time() - phase_start
            logger.warning(f"[REQUEST-{request_id}] Invalid wallet address")
            return jsonify({
                "error": "Invalid wallet address",
                "message": "Wallet address must be at least 32 characters"
            }), 400
        
        # Get schema version
        schema_version = request.args.get("schema_version", "1.1")
        if schema_version != "1.1":
            phase_times["validation"] = time.time() - phase_start
            return jsonify({
                "error": "Unsupported schema version",
                "message": f"Schema version {schema_version} not supported. Use 1.1"
            }), 400
        
        # Check if positions are enabled
        if not positions_enabled():
            phase_times["validation"] = time.time() - phase_start
            logger.warning(f"[REQUEST-{request_id}] Positions not enabled")
            return jsonify({
                "error": "Feature disabled",
                "message": "Position tracking is not enabled"
            }), 501
        
        phase_times["validation"] = time.time() - phase_start
        logger.info(f"[PHASE-{request_id}] Validation complete in {phase_times['validation']:.3f}s")
        
        # Phase timing
        phase_timings = {}
        
        # Check if we should skip pricing (for debugging or beta mode)
        skip_pricing = request.args.get('skip_pricing', '').lower() == 'true'
        beta_mode = request.args.get('beta_mode', '').lower() == 'true'
        skip_birdeye = request.args.get('skip_birdeye', '').lower() == 'true'
        
        # [CHECK] Log for troubleshooting
        logger.info(f"[CHECK-{request_id}] env PRICE_HELIUS_ONLY={os.getenv('PRICE_HELIUS_ONLY')} skip_pricing={skip_pricing} beta_mode={beta_mode} skip_birdeye={skip_birdeye}")
        
        if skip_pricing or beta_mode or skip_birdeye:
            skip_pricing = True
            logger.info(f"Price fetching disabled - skip_pricing={request.args.get('skip_pricing')}, beta_mode={beta_mode}, skip_birdeye={skip_birdeye}")
        
        # Get positions with staleness info
        phase_start = time.time()
        logger.info(f"[PHASE-{request_id}] Starting position fetch...")
        try:
            snapshot, is_stale, age_seconds = run_async(
                get_positions_with_staleness(wallet_address, skip_pricing=skip_pricing)
            )
            phase_times["position_fetch"] = time.time() - phase_start
            logger.info(f"[PHASE-{request_id}] Position fetch complete in {phase_times['position_fetch']:.3f}s")
        except Exception as e:
            phase_times["position_fetch"] = time.time() - phase_start
            logger.error(f"[PHASE-{request_id}] Position fetch failed after {phase_times['position_fetch']:.3f}s: {str(e)}")
            logger.error(f"[PHASE-{request_id}] Traceback: {traceback.format_exc()}")
            raise
        
        if not snapshot:
            # Truly no data found (no trades at all)
            duration_ms = (time.time() - start_time) * 1000
            error_response = jsonify({
                "error": "Wallet not found",
                "message": f"No trading data found for wallet {wallet_address}"
            })
            error_response.headers['X-Response-Time-Ms'] = f"{duration_ms:.2f}"
            error_response.headers['X-Phase-Timings'] = json.dumps(phase_timings)
            return error_response, 404
        
        # Format response
        phase_start = time.time()
        response_data = format_gpt_schema_v1_1(snapshot)
        phase_timings["format_response"] = time.time() - phase_start
        logger.info(f"phase=format_response took={phase_timings['format_response']:.2f}s")
        
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
        
        # Create response with required headers
        response = make_response(jsonify(response_data))
        response.headers['X-Worker-ID'] = WORKER_ID
        response.headers['X-Phase-Total-MS'] = f"{duration_ms:.0f}"
        response.headers['X-Price-Mode'] = "helius-only"
        
        return response
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"[FATAL-{request_id}] Request failed wallet={wallet_address} after {duration_ms:.0f}ms: {str(e)}")
        logger.error(f"[FATAL-{request_id}] Exception type: {type(e).__name__}")
        logger.error(f"[FATAL-{request_id}] Phase times: {phase_times}")
        logger.error(f"[FATAL-{request_id}] skip_pricing={skip_pricing} beta_mode={beta_mode} PRICE_HELIUS_ONLY={os.getenv('PRICE_HELIUS_ONLY')}")
        logger.exception(f"[FATAL-{request_id}] Full traceback:")
        
        error_response = jsonify({
            "error": "Internal server error",
            "message": "Failed to export position data",
            "request_id": request_id,
            "worker_id": WORKER_ID
        })
        error_response.headers['X-Response-Time-Ms'] = f"{duration_ms:.2f}"
        error_response.headers['X-Request-Id'] = request_id
        error_response.headers['X-Worker-Id'] = WORKER_ID
        
        return error_response, 500


@app.route("/v4/positions/warm-cache/<wallet_address>", methods=["POST"])
@simple_auth_required  
def warm_cache(wallet_address: str):
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
        cached_result = run_async(cache.get_portfolio_snapshot(wallet_address))
        
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
                    
                    # Pass transactions and trades for Helius price extraction
                    if os.getenv('PRICE_HELIUS_ONLY', '').lower() == 'true':
                        calculator.trades = trades
                        calculator.transactions = result.get("transactions", [])
                        logger.info(f"[PRICE] Helius-only mode (warm cache): {len(calculator.transactions)} transactions")
                    
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
        
        # Run the warming synchronously for now
        # In production, this should use a proper task queue like Celery
        run_async(warm_cache_task())
        
        return jsonify({
            "status": "cache_warmed",
            "progress_token": progress_token,
            "message": "Cache warming completed"
        })
        
    except Exception as e:
        logger.error(f"Error in cache warming: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": "Failed to start cache warming"
        }), 500


@app.route("/v4/diagnostics", methods=["GET"])
def diagnostics():
    """Diagnostics endpoint for debugging deployment issues"""
    diag_start = time.time()
    request_id = f"diag-{str(uuid.uuid4())[:8]}"
    
    try:
        logger.info(f"[DIAG-{request_id}] Diagnostics called, worker={WORKER_ID}")
        
        import redis
        
        # Check environment variables
        env_vars = {
            "HELIUS_KEY": bool(os.getenv("HELIUS_KEY")),
            "BIRDEYE_API_KEY": bool(os.getenv("BIRDEYE_API_KEY")),
            "POSITIONS_ENABLED": os.getenv("POSITIONS_ENABLED", "false"),
            "UNREALIZED_PNL_ENABLED": os.getenv("UNREALIZED_PNL_ENABLED", "false"),
            "WEB_CONCURRENCY": os.getenv("WEB_CONCURRENCY", "1"),
            "HELIUS_PARALLEL_REQUESTS": os.getenv("HELIUS_PARALLEL_REQUESTS", "1"),
            "HELIUS_TIMEOUT": os.getenv("HELIUS_TIMEOUT", "30"),
            "POSITION_CACHE_TTL": os.getenv("POSITION_CACHE_TTL", "300"),
            "POSITION_CACHE_TTL_SEC": os.getenv("POSITION_CACHE_TTL_SEC", "NOT SET"),
            "PRICE_HELIUS_ONLY": os.getenv("PRICE_HELIUS_ONLY", "false"),
            "ENABLE_CACHE_WARMING": os.getenv("ENABLE_CACHE_WARMING", "false"),
            "FLASK_DEBUG": os.getenv("FLASK_DEBUG", "false"),
            "GUNICORN_CMD_ARGS": os.getenv("GUNICORN_CMD_ARGS", "")
        }
        
        # Test Redis connection
        redis_status = "unknown"
        cache_entries = 0
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            r = redis.from_url(redis_url, decode_responses=True)
            redis_status = r.ping()
            if redis_status:
                redis_status = "PONG"
                cache_entries = r.dbsize()
        except Exception as e:
            redis_status = f"error: {str(e)}"
        
        # Check feature flags
        features = {
            "positions_enabled": positions_enabled(),
            "unrealized_pnl_enabled": should_calculate_unrealized_pnl(),
            "cost_basis_method": get_cost_basis_method()
        }
        
        duration_ms = (time.time() - diag_start) * 1000
        logger.info(f"[DIAG-{request_id}] Diagnostics complete in {duration_ms:.0f}ms")
        
        return jsonify({
            "status": "ok",
            "worker_id": WORKER_ID,
            "startup_time": STARTUP_TIME,
            "env_checksum": env_checksum,
            "helius_key_present": env_vars["HELIUS_KEY"],
            "birdeye_key_present": env_vars["BIRDEYE_API_KEY"],
            "env": env_vars,
            "features": features,
            "redis_ping": redis_status,
            "cache_entries": cache_entries,
            "python_version": sys.version,
            "process_id": os.getpid(),
            "response_time_ms": duration_ms
        })
        
    except Exception as e:
        duration_ms = (time.time() - diag_start) * 1000
        logger.error(f"[DIAG-{request_id}] Failed after {duration_ms:.0f}ms: {str(e)}")
        logger.error(f"[DIAG-{request_id}] Traceback:\n{traceback.format_exc()}")
        
        return jsonify({
            "status": "error",
            "error": str(e),
            "worker_id": WORKER_ID,
            "request_id": request_id,
            "response_time_ms": duration_ms
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


@app.route("/v4/positions/export-gpt-stream/<wallet_address>", methods=["GET"])
@simple_auth_required
def export_positions_stream(wallet_address: str):
    """
    Stream positions export in GPT-friendly format using Server-Sent Events
    
    GET /v4/positions/export-gpt-stream/{wallet}
    
    This endpoint streams the response as data becomes available,
    allowing ChatGPT to start processing before the full response is ready.
    
    Headers:
    - X-Api-Key: API key for authentication
    
    Returns: SSE stream with events:
    - progress: Updates on fetching progress
    - data: Partial position data as available
    - complete: Final summary when done
    """
    from flask import Response
    import json
    
    def generate():
        """Generate SSE events"""
        try:
            # Send initial connection event
            yield f"event: connected\ndata: {json.dumps({'wallet': wallet_address})}\n\n"
            
            # Check cache first
            cache = get_position_cache_v2()
            cached_result = run_async(cache.get_portfolio_snapshot(wallet_address))
            
            if cached_result:
                snapshot, is_stale = cached_result
                age_seconds = int((datetime.now(timezone.utc) - snapshot.timestamp).total_seconds())
                
                # If data is fresh, send it immediately
                if age_seconds < 300:  # 5 minutes
                    yield f"event: cache_hit\ndata: {json.dumps({'age_seconds': age_seconds})}\n\n"
                    
                    # Send the full response
                    response_data = format_gpt_schema_v1_1(snapshot)
                    yield f"event: complete\ndata: {json.dumps(response_data)}\n\n"
                    return
            
            # Need to fetch fresh data - stream progress
            yield f"event: cache_miss\ndata: {json.dumps({'message': 'Fetching fresh data'})}\n\n"
            
            # Fetch trades (without streaming progress for now)
            start_time = time.time()
            yield f"event: fetching\ndata: {json.dumps({'message': 'Fetching blockchain data...'})}\n\n"
            
            async def fetch_data():
                async with BlockchainFetcherV3Fast(skip_pricing=False) as fetcher:
                    return await fetcher.fetch_wallet_trades(wallet_address)
            
            result = run_async(fetch_data())
            trades = result.get("trades", [])
            
            fetch_duration = time.time() - start_time
            yield f"event: trades_fetched\ndata: {json.dumps({'count': len(trades), 'duration': fetch_duration})}\n\n"
            
            # Build positions
            method = CostBasisMethod(get_cost_basis_method())
            builder = PositionBuilder(method)
            positions = builder.build_positions_from_trades(trades, wallet_address)
            
            yield f"event: positions_built\ndata: {json.dumps({'count': len(positions)})}\n\n"
            
            # Calculate P&L
            if positions and should_calculate_unrealized_pnl():
                calculator = UnrealizedPnLCalculator()
                
                # Stream positions as they're calculated
                position_pnls = []
                batch_size = 10
                
                for i in range(0, len(positions), batch_size):
                    batch = positions[i:i+batch_size]
                    batch_pnls = run_async(calculator.create_position_pnl_list(batch))
                    position_pnls.extend(batch_pnls)
                    
                    # Send batch update
                    yield f"event: pnl_batch\ndata: {json.dumps({'processed': len(position_pnls), 'total': len(positions)})}\n\n"
                
                # Create and cache snapshot
                snapshot = PositionSnapshot.from_positions(wallet_address, position_pnls)
                run_async(cache.set_portfolio_snapshot(snapshot))
                
                # Send complete response
                response_data = format_gpt_schema_v1_1(snapshot)
                total_duration = time.time() - start_time
                response_data['_performance'] = {
                    'duration_seconds': total_duration,
                    'trades_count': len(trades),
                    'positions_count': len(positions)
                }
                
                yield f"event: complete\ndata: {json.dumps(response_data)}\n\n"
            else:
                # No positions
                yield f"event: complete\ndata: {json.dumps({'error': 'No positions found'})}\n\n"
                
        except Exception as e:
            logger.error(f"Error in SSE stream: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
    
    # Return SSE response
    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


if __name__ == "__main__":
    # For development
    app.run(host="0.0.0.0", port=8081, debug=False) 