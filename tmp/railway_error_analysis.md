# Railway 502 Error Analysis

## Root Cause
The app fails to start because `blockchain_fetcher_v3_fast.py` raises a `ValueError` at import time if HELIUS_KEY is not set:

```python
HELIUS_KEY = os.getenv("HELIUS_KEY")
if not HELIUS_KEY:
    raise ValueError("HELIUS_KEY environment variable is required")
```

This prevents the entire app from starting, causing Railway's proxy to timeout and return 502.

## Evidence
1. Local test shows import failure without HELIUS_KEY
2. All endpoints (even /health) return 502
3. Consistent ~5s timeout suggests app startup failure

## Solutions

### 1. Immediate Fix (for Railway admin)
Ensure HELIUS_KEY is set in Railway environment:
```
HELIUS_KEY=<actual_key_value>
```

### 2. Code Fix (make startup more resilient)
Move the validation from import time to runtime:

```python
# At module level
HELIUS_KEY = os.getenv("HELIUS_KEY")

# In class __init__ or method
if not HELIUS_KEY:
    raise ValueError("HELIUS_KEY environment variable is required")
```

This allows the app to start and serve diagnostics/health endpoints even if trading endpoints fail.

### 3. Better Error Visibility
Add startup logging to show which env vars are missing:

```python
# In app startup
missing_vars = []
for var in ['HELIUS_KEY', 'BIRDEYE_API_KEY']:
    if not os.getenv(var):
        missing_vars.append(var)
if missing_vars:
    logger.error(f"Missing required env vars: {missing_vars}")
```

## Testing Steps
1. Set HELIUS_KEY in Railway
2. Redeploy
3. Test /v4/diagnostics first
4. Then test /v4/positions/export-gpt/...

## Timing Expectations
Once the app starts properly:
- Cold cache: 5-30s depending on wallet size
- Warm cache: <0.2s

The current 502 errors are NOT due to processing time but due to startup failure. 