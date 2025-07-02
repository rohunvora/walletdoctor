# Debug Deployment Checklist

## Environment Variables to Set
- [x] `PRICE_HELIUS_ONLY=true`
- [x] `WEB_CONCURRENCY=1`
- [ ] All Redis vars → unset/blank
- [ ] All cache vars → unset/blank

## Deployment Info
- **Branch**: `debug/minimal-phase`
- **Commit**: `5280dca` - debug: add minimal CHECK logs for trades and positions counts
- **Base**: `v0.6.0-beta2` (tag 0659533)

## Changes Made
1. Added `[CHECK] trades_found={count}` log after trades fetched
2. Added `[CHECK] positions_built={count}` log before response built
3. No other code changes - keeping it surgical

## Test Sequence
1. Wait for "app boot" line in Railway logs
2. Run cold request with 10s timeout
3. Wait 3 seconds
4. Run warm request with 10s timeout  
5. Collect logs from 2-minute window

## Success Criteria
- Both CHECK logs appear
- trades_found > 0
- positions_built ≥ 1
- Response body positions array length matches positions_built 