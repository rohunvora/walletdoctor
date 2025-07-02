#!/bin/bash
# Test locally with Railway's exact environment variables

export HELIUS_KEY="9475ccc3-58d7-417f-9760-7fe14f198fa5"
export BIRDEYE_API_KEY="4e5e878a6137491bbc280c10587a0cce"
export UNREALIZED_PNL_ENABLED="true"
export POSITION_CACHE_TTL="300"
export WEB_CONCURRENCY="2"
export POSITIONS_ENABLED="true"
export HELIUS_PARALLEL_REQUESTS="5"
export HELIUS_MAX_RETRIES="2"
export HELIUS_TIMEOUT="15"
export ENABLE_CACHE_WARMING="true"
# GUNICORN_CMD_ARGS not needed - removed UvicornWorker
export LOG_LEVEL="debug"
export FLASK_DEBUG="true"
export PORT="8080"

echo "Starting server with Railway environment..."
echo "HELIUS_KEY present: ${HELIUS_KEY:+true}"
echo "BIRDEYE_API_KEY present: ${BIRDEYE_API_KEY:+true}"

# Start with gunicorn exactly as Railway does
gunicorn src.api.wallet_analytics_api_v4_gpt:app \
    --workers $WEB_CONCURRENCY \
    --timeout 120 \
    --bind "0.0.0.0:$PORT" \
    --log-level debug \
    --access-logfile - 