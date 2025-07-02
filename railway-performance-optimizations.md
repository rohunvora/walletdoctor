# Railway Performance Optimizations for WAL-613

## Current Issue

Small wallet (34zYDgjy9Uyj9NZnDVKBB45urkbBV4h5LzxWjXJg9VCya) GPT export endpoint exceeds 30s target for cold cache requests.

## Recommended Optimizations

### 1. Update Gunicorn Configuration

**Current**: Single worker
**Recommended**: 2 workers with Uvicorn worker class

Update `Procfile`:
```
web: gunicorn -w 2 -k uvicorn.workers.UvicornWorker --timeout 120 --bind "0.0.0.0:$PORT" src.api.wallet_analytics_api_v4_gpt:app
```

**Rationale**: 
- 2 workers allow parallel request handling
- UvicornWorker maintains async compatibility
- 120s timeout prevents premature termination

### 2. Environment Variables

Add these to Railway environment:
```bash
# Helius optimization
HELIUS_PARALLEL_REQUESTS=5
HELIUS_MAX_RETRIES=2
HELIUS_TIMEOUT=15

# Cache settings
POSITION_CACHE_TTL=300
ENABLE_CACHE_WARMING=true

# Python optimizations
PYTHONUNBUFFERED=1
```

**Important**: Ensure NO quotes around values in Railway UI

### 3. Memory and Resource Allocation

If on Railway Hobby plan ($5):
- Consider upgrading to Pro plan for better network performance
- Pro plan includes:
  - Priority routing
  - Better network connectivity
  - Higher resource limits

### 4. Code Optimizations

Add connection pooling for Helius requests:

```python
# In blockchain_fetcher_v3_fast.py
class BlockchainFetcherV3Fast:
    def __init__(self):
        # Use connection pooling
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                ttl_dns_cache=300
            ),
            timeout=aiohttp.ClientTimeout(total=30)
        )
```

### 5. Monitoring

Add these logs to identify bottlenecks:

```python
# In wallet_analytics_api_v4_gpt.py
logger.info(f"Helius fetch started")
helius_start = time.time()
# ... fetch code ...
logger.info(f"Helius fetch completed in {time.time() - helius_start:.2f}s")

logger.info(f"Position calculation started")
calc_start = time.time()
# ... calculation code ...
logger.info(f"Position calculation completed in {time.time() - calc_start:.2f}s")
```

## Testing Procedure

1. Deploy with optimizations
2. Run performance test:
   ```bash
   python3 scripts/test_railway_performance.py
   ```

3. Expected results:
   - Cold cache: < 30s ✅
   - Warm cache: < 5s ✅

## Alternative: Background Processing

If optimizations don't achieve < 30s:

1. **Immediate Response with Progress Token**
   ```python
   @app.route("/v4/positions/export-gpt/<wallet>", methods=["POST"])
   def start_export(wallet):
       token = start_background_task(wallet)
       return {"progress_token": token}, 202
   ```

2. **Polling Endpoint**
   ```python
   @app.route("/v4/positions/export-gpt/<wallet>/status/<token>")
   def check_status(wallet, token):
       status = get_task_status(token)
       if status.complete:
           return status.result
       return {"status": "processing", "progress": status.progress}, 202
   ```

3. **WebSocket Alternative**
   Use Server-Sent Events for real-time updates

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Cold Cache | < 30s | TBD |
| Warm Cache | < 5s | TBD |
| Network Latency | < 100ms | TBD |
| Helius Fetch | < 15s | TBD |
| Position Calc | < 5s | TBD |

## Next Steps

1. Apply optimizations to Railway
2. Run performance tests
3. Capture timing breakdown
4. If still > 30s, implement background processing 