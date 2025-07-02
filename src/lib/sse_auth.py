#!/usr/bin/env python3
"""
SSE Authentication and Rate Limiting Middleware
"""

import os
import time
import hashlib
import hmac
from functools import wraps
from flask import request, Response
from typing import Dict, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

# Rate limiting configuration
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_REQUESTS = 50  # requests per window
RATE_LIMIT_STREAMING_CONNECTIONS = 10  # concurrent SSE connections per key

# In-memory rate limiting (use Redis in production)
rate_limit_cache: Dict[str, Dict[str, Any]] = {}
active_connections: Dict[str, int] = {}


def validate_api_key(api_key: str) -> bool:
    """
    Validate API key format and existence
    
    In production, this should:
    - Check against database
    - Validate key permissions
    - Check if key is active/not revoked
    """
    if not api_key:
        return False
    
    # Basic format validation
    if not api_key.startswith("wd_") or len(api_key) != 35:
        return False
    
    # In production, check against database
    # For now, accept any properly formatted key
    return True


def get_api_key_from_request() -> Optional[str]:
    """Extract API key from request headers or query params"""
    # Check Authorization header
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]
    
    # Check X-API-Key header
    api_key = request.headers.get('X-API-Key')
    if api_key:
        return api_key
    
    # Check query parameter (for SSE compatibility)
    return request.args.get('api_key')


def check_rate_limit(api_key: str, is_streaming: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Check if request is within rate limits
    
    Returns:
        (allowed, error_message)
    """
    current_time = time.time()
    
    # Initialize cache for this key if needed
    if api_key not in rate_limit_cache:
        rate_limit_cache[api_key] = {
            'requests': [],
            'window_start': current_time
        }
    
    key_data = rate_limit_cache[api_key]
    
    # Clean old requests outside window
    window_start = current_time - RATE_LIMIT_WINDOW
    key_data['requests'] = [
        req_time for req_time in key_data['requests'] 
        if req_time > window_start
    ]
    
    # Check streaming connection limit
    if is_streaming:
        active_count = active_connections.get(api_key, 0)
        if active_count >= RATE_LIMIT_STREAMING_CONNECTIONS:
            return False, f"Maximum concurrent streaming connections ({RATE_LIMIT_STREAMING_CONNECTIONS}) reached"
    
    # Check request limit
    if len(key_data['requests']) >= RATE_LIMIT_REQUESTS:
        retry_after = int(window_start + RATE_LIMIT_WINDOW - current_time)
        return False, f"Rate limit exceeded. Retry after {retry_after} seconds"
    
    # Add current request
    key_data['requests'].append(current_time)
    
    return True, None


def require_auth(f):
    """Decorator to require authentication for endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = get_api_key_from_request()
        
        # Check if API key is provided
        if not api_key:
            logger.warning(f"Missing API key from {request.remote_addr}")
            return Response(
                '{"error": "API key required. Pass via Authorization header or api_key parameter"}',
                status=401,
                mimetype='application/json'
            )
        
        # Validate API key
        if not validate_api_key(api_key):
            logger.warning(f"Invalid API key from {request.remote_addr}: {api_key[:10]}...")
            return Response(
                '{"error": "Invalid API key"}',
                status=401,
                mimetype='application/json'
            )
        
        # Check rate limit
        is_streaming = request.path.endswith('/stream')
        allowed, error_msg = check_rate_limit(api_key, is_streaming)
        if not allowed:
            logger.warning(f"Rate limit exceeded for {api_key[:10]}...")
            return Response(
                f'{{"error": "{error_msg}"}}',
                status=429,
                headers={'Retry-After': '60'},
                mimetype='application/json'
            )
        
        # Track streaming connections
        if is_streaming:
            active_connections[api_key] = active_connections.get(api_key, 0) + 1
        
        # Store API key in request context
        request.api_key = api_key
        
        try:
            return f(*args, **kwargs)
        finally:
            # Clean up streaming connection
            if is_streaming and api_key in active_connections:
                active_connections[api_key] -= 1
                if active_connections[api_key] <= 0:
                    del active_connections[api_key]
    
    return decorated_function


def generate_api_key() -> str:
    """Generate a new API key"""
    # Generate random bytes
    random_bytes = os.urandom(24)
    
    # Create hash
    key_hash = hashlib.sha256(random_bytes).hexdigest()[:32]
    
    # Format as wd_<key>
    return f"wd_{key_hash}"


def sign_request(api_key: str, data: str) -> str:
    """Sign request data with API key for webhook validation"""
    return hmac.new(
        api_key.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


# Error response helpers
def auth_error_response(message: str = "Authentication required") -> Response:
    """Create standardized auth error response"""
    return Response(
        f'{{"error": "{message}", "code": "AUTH_REQUIRED"}}',
        status=401,
        mimetype='application/json',
        headers={'WWW-Authenticate': 'Bearer'}
    )


def rate_limit_error_response(retry_after: int = 60) -> Response:
    """Create standardized rate limit error response"""
    return Response(
        f'{{"error": "Rate limit exceeded", "code": "RATE_LIMIT", "retry_after": {retry_after}}}',
        status=429,
        mimetype='application/json',
        headers={'Retry-After': str(retry_after)}
    )


# Monitoring helpers
def log_api_request(api_key: str, endpoint: str, duration: float, status: int):
    """Log API request for monitoring"""
    logger.info(
        "api_request",
        extra={
            'api_key': api_key[:10] + '...' if api_key else None,
            'endpoint': endpoint,
            'duration_ms': round(duration * 1000, 2),
            'status': status,
            'ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', '')
        }
    )


# Usage example:
"""
from sse_auth import require_auth, log_api_request

@app.route('/v4/wallet/<wallet_address>/stream')
@require_auth
def stream_wallet(wallet_address):
    start_time = time.time()
    try:
        # Your streaming logic here
        return Response(stream_generator(), mimetype='text/event-stream')
    finally:
        duration = time.time() - start_time
        log_api_request(request.api_key, 'stream_wallet', duration, 200)
""" 