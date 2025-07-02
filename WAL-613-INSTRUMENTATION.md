# WAL-613 Instrumentation for Fault Isolation

## Added Instrumentation

### 1. Worker Identification
- `WORKER_ID` - Unique 8-char ID per worker process
- `STARTUP_TIME` - When worker started
- `env_checksum` - MD5 hash of key env vars to detect changes

### 2. Request Tracking
- `request_id` - Unique ID per request (e.g., `req-12345678`)
- All logs prefixed with `[REQUEST-{id}]` or `[PHASE-{id}]`
- Worker ID included in error responses

### 3. Phase Timing
Added detailed timing for each phase:
- `[PHASE] Request validation`
- `[PHASE] Creating BlockchainFetcherV3Fast`
- `[PHASE] Fetcher created, calling fetch_wallet_trades`
- `[PHASE] helius_fetch completed`
- `[PHASE] position_build`
- `[PHASE] price_fetch`

### 4. Enhanced Error Logging
- Full stack traces with `traceback.format_exc()`
- Exception type logging
- Phase times at point of failure
- Request context (wallet, params, env)

### 5. Startup Logging
```
[BOOT] WalletDoctor GPT API Starting - Worker 12345678
[BOOT] HELIUS_KEY present: True
[BOOT] PRICE_HELIUS_ONLY: true
[BOOT] POSITION_CACHE_TTL_SEC: 300
[BOOT] Environment checksum: a1b2c3d4
```

## Key Log Lines to Watch

1. **Worker restart detection**:
   - Different `WORKER_ID` = new worker started
   - Check `STARTUP_TIME` for recent restarts

2. **Request flow**:
   ```
   [REQUEST-abc123] Worker 12345678 handling export-gpt...
   [PHASE-abc123] Starting request validation...
   [PHASE-abc123] Starting position fetch...
   [PHASE-pos-xyz789] Creating BlockchainFetcherV3Fast...
   ```

3. **Failure point**:
   - Look for last `[PHASE]` before error
   - Check phase times to see where slowdown occurs

## Most Likely Root Causes

Based on symptoms (499s, 500s even with beta_mode):

1. **Worker crash during startup** - Check for multiple WORKER_IDs
2. **Exception in BlockchainFetcherV3Fast init** - Look for failures at "Creating BlockchainFetcherV3Fast"
3. **Async deadlock in run_async** - Check if failures happen at specific phase transitions

## Next Steps

1. Deploy this instrumentation
2. Make one request to `/v4/diagnostics`
3. Make one request to `/v4/positions/export-gpt/{wallet}`
4. Collect logs with all `[BOOT]`, `[REQUEST]`, `[PHASE]`, and error messages
5. Analyze to pinpoint exact failure location 