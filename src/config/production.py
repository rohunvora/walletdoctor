#!/usr/bin/env python3
"""
Production configuration for WalletDoctor SSE Streaming API
"""

import os
from typing import Dict, Any

# Environment
ENV = os.getenv('ENV', 'production')
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'

# Security
SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(32).hex())
API_KEY_REQUIRED = os.getenv('API_KEY_REQUIRED', 'true').lower() == 'true'
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '*').split(',')
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max request size

# Rate Limiting
RATE_LIMIT_ENABLED = True
RATE_LIMIT_WINDOW = int(os.getenv('RATE_LIMIT_WINDOW', '60'))  # seconds
RATE_LIMIT_REQUESTS = int(os.getenv('RATE_LIMIT_REQUESTS', '50'))
RATE_LIMIT_STREAMING_CONNECTIONS = int(os.getenv('RATE_LIMIT_STREAMING_CONNECTIONS', '10'))
RATE_LIMIT_STORAGE_URL = os.getenv('REDIS_URL')  # Use Redis in production

# SSE Configuration
SSE_KEEPALIVE_INTERVAL = int(os.getenv('SSE_KEEPALIVE_INTERVAL', '30'))  # seconds
SSE_MAX_STREAM_DURATION = int(os.getenv('SSE_MAX_STREAM_DURATION', '600'))  # 10 minutes
SSE_BATCH_SIZE = int(os.getenv('SSE_BATCH_SIZE', '100'))
SSE_PROGRESS_THROTTLE = float(os.getenv('SSE_PROGRESS_THROTTLE', '0.5'))  # seconds

# Blockchain APIs
HELIUS_KEY = os.getenv('HELIUS_KEY')
BIRDEYE_API_KEY = os.getenv('BIRDEYE_API_KEY')
HELIUS_TIMEOUT = int(os.getenv('HELIUS_TIMEOUT', '30'))
BIRDEYE_TIMEOUT = int(os.getenv('BIRDEYE_TIMEOUT', '10'))

# Performance
PARALLEL_PAGES = int(os.getenv('PARALLEL_PAGES', '40'))
SIGNATURE_PAGE_LIMIT = int(os.getenv('SIGNATURE_PAGE_LIMIT', '1000'))
TX_BATCH_SIZE = int(os.getenv('TX_BATCH_SIZE', '100'))
MAX_WALLET_SIZE = int(os.getenv('MAX_WALLET_SIZE', '20000'))  # Max transactions

# Monitoring
MONITORING_ENABLED = os.getenv('MONITORING_ENABLED', 'true').lower() == 'true'
PROMETHEUS_ENABLED = os.getenv('PROMETHEUS_ENABLED', 'true').lower() == 'true'
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = 'json' if ENV == 'production' else 'text'
SENTRY_DSN = os.getenv('SENTRY_DSN')

# Caching
CACHE_ENABLED = True
CACHE_TTL = int(os.getenv('CACHE_TTL', '3600'))  # 1 hour
CACHE_BACKEND = os.getenv('CACHE_BACKEND', 'redis')  # redis or memory
CACHE_REDIS_URL = os.getenv('REDIS_URL')

# Server
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '5000'))
WORKERS = int(os.getenv('WORKERS', '4'))
WORKER_CLASS = 'aiohttp.GunicornWebWorker'
WORKER_CONNECTIONS = int(os.getenv('WORKER_CONNECTIONS', '1000'))
KEEPALIVE = int(os.getenv('KEEPALIVE', '5'))

# CORS
CORS_ENABLED = True
CORS_ORIGINS = ALLOWED_ORIGINS
CORS_METHODS = ['GET', 'POST', 'OPTIONS']
CORS_HEADERS = ['Content-Type', 'Authorization', 'X-API-Key', 'Last-Event-ID']
CORS_CREDENTIALS = True

# Security Headers
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'Content-Security-Policy': "default-src 'self'"
}

# Error Messages
ERROR_MESSAGES = {
    'RATE_LIMIT': 'Rate limit exceeded. Please try again later.',
    'AUTH_REQUIRED': 'Authentication required. Please provide a valid API key.',
    'INVALID_API_KEY': 'Invalid API key.',
    'WALLET_NOT_FOUND': 'Wallet address not found or invalid.',
    'SERVICE_UNAVAILABLE': 'Service temporarily unavailable. Please try again later.',
    'INTERNAL_ERROR': 'An unexpected error occurred. Please contact support if this persists.'
}

# Feature Flags
FEATURES = {
    'streaming_enabled': True,
    'progress_events': True,
    'batch_trades': True,
    'skip_pricing': True,
    'cache_prices': True,
    'auto_reconnect': True
}

# Validation
def validate_config():
    """Validate configuration"""
    errors = []
    
    if not HELIUS_KEY:
        errors.append("HELIUS_KEY environment variable is required")
    
    if API_KEY_REQUIRED and not SECRET_KEY:
        errors.append("SECRET_KEY is required when API_KEY_REQUIRED is true")
    
    if CACHE_BACKEND == 'redis' and not CACHE_REDIS_URL:
        errors.append("REDIS_URL is required when using Redis cache backend")
    
    if SENTRY_DSN and not SENTRY_DSN.startswith('https://'):
        errors.append("Invalid SENTRY_DSN format")
    
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")

# Production settings
if ENV == 'production':
    # Enforce security in production
    if not API_KEY_REQUIRED:
        raise ValueError("API_KEY_REQUIRED must be true in production")
    
    if DEBUG:
        raise ValueError("DEBUG must be false in production")
    
    if '*' in ALLOWED_ORIGINS:
        print("WARNING: Using wildcard CORS origin in production is not recommended")

# Export config as dict
def get_config() -> Dict[str, Any]:
    """Get configuration as dictionary"""
    return {
        'env': ENV,
        'debug': DEBUG,
        'host': HOST,
        'port': PORT,
        'workers': WORKERS,
        'rate_limit': {
            'enabled': RATE_LIMIT_ENABLED,
            'window': RATE_LIMIT_WINDOW,
            'requests': RATE_LIMIT_REQUESTS,
            'streaming_connections': RATE_LIMIT_STREAMING_CONNECTIONS
        },
        'sse': {
            'keepalive_interval': SSE_KEEPALIVE_INTERVAL,
            'max_duration': SSE_MAX_STREAM_DURATION,
            'batch_size': SSE_BATCH_SIZE,
            'progress_throttle': SSE_PROGRESS_THROTTLE
        },
        'monitoring': {
            'enabled': MONITORING_ENABLED,
            'prometheus': PROMETHEUS_ENABLED,
            'log_level': LOG_LEVEL,
            'sentry_dsn': SENTRY_DSN
        },
        'features': FEATURES
    } 