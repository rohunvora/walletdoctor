# Railway Debug Steps

Since HELIUS_KEY is confirmed present, the issue is likely one of:

## 1. Test with Fixed Response
Add to Railway environment:
```
DEBUG_FIXED_RESPONSE=true
LOG_LEVEL=debug
```

Then test:
```bash
curl -H "X-Api-Key: wd_12345678901234567890123456789012" \
  https://web-production-2bb2f.up.railway.app/v4/positions/export-gpt/test
```

If this returns `{"ok": true, ...}`, the issue is in our async code. If it still 502s, it's a startup issue.

## 2. Check Railway Logs
After deploying with LOG_LEVEL=debug, watch for:
- "WalletDoctor GPT API Starting..." message
- Any import errors
- Stack traces from our global error handler

## 3. Try Sync Workers
Railway might have issues with UvicornWorker. Try using Procfile.sync:
```
web: gunicorn src.api.wallet_analytics_api_v4_gpt:app --workers $WEB_CONCURRENCY --timeout 120 --bind "0.0.0.0:$PORT" --log-level debug --access-logfile -
```

## 4. Test Minimal App
Deploy the minimal test app to isolate framework issues:
```python
# In Procfile, temporarily change to:
web: gunicorn src.api.minimal_test_app:app --workers 1 --timeout 120 --bind "0.0.0.0:$PORT" --log-level debug
```

## 5. Possible Causes

### A. Asyncio Event Loop Conflict
UvicornWorker creates its own event loop which conflicts with our `asyncio.run()` calls. We've updated the code to handle this.

### B. Memory/Resource Limits
The app might be hitting Railway's memory limit during startup. Check Railway metrics.

### C. Network Egress
Railway might block outbound connections to Helius/Birdeye. Test with:
```python
import requests
response = requests.get("https://api.helius.xyz/v0/addresses/test", 
                       params={"api-key": HELIUS_KEY})
print(response.status_code)
```

### D. Import-time Exceptions
Even though HELIUS_KEY is set, there might be other import failures. Our new logging should catch these.

## 6. Local Testing
Run locally with exact Railway config:
```bash
chmod +x test_local_railway_env.sh
./test_local_railway_env.sh
```

Then test:
```bash
curl -H "X-Api-Key: wd_12345678901234567890123456789012" \
  http://localhost:8080/v4/positions/export-gpt/34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya
```

## 7. Emergency Workaround
If nothing else works, try:
1. Remove `--worker-class uvicorn.workers.UvicornWorker` from GUNICORN_CMD_ARGS
2. Set `WEB_CONCURRENCY=1`
3. Add `PYTHONUNBUFFERED=1` to see logs immediately 