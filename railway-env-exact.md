# Railway Environment Variables - EXACT List

Copy/paste these EXACTLY into Railway dashboard (Settings → Variables):

```
HELIUS_KEY=<real key>
BIRDEYE_API_KEY=<real key>
POSITIONS_ENABLED=true
UNREALIZED_PNL_ENABLED=true
WEB_CONCURRENCY=1
# GUNICORN_CMD_ARGS removed - not needed after fixing Procfile
HELIUS_PARALLEL_REQUESTS=15
HELIUS_MAX_RETRIES=2
HELIUS_TIMEOUT=20
POSITION_CACHE_TTL=300
ENABLE_CACHE_WARMING=true
FLASK_DEBUG=true
RAILWAY_PROXY_TIMEOUT=60
GUNICORN_TIMEOUT=60
LOG_LEVEL=info
# DEBUG_FIXED_RESPONSE=true  # Remove this - was for debugging only
```

**Important**: 
- NO quotes around any values
- Remove any duplicate or unused variables
- Keep your actual API keys (don't use placeholders) 