# TICKET: Small Wallet Returns Empty Positions

**Status**: In Progress  
**Branch**: `debug/minimal-phase`  
**Created**: 2025-01-02  

## Problem Statement
Small wallet endpoint returns HTTP 200 but with empty positions array, despite having trades.

## Acceptance Criteria
✅ Response returns HTTP 200  
❓ `[CHECK] trades_found > 0`  
❓ `[CHECK] positions_built ≥ 1`  
❓ Response positions length matches `positions_built`  

## Debug Approach
1. **Minimal baseline** - Start from v0.6.0-beta2 (last known working)
2. **Two CHECK logs only** - Track trades_found and positions_built
3. **Clean environment** - PRICE_HELIUS_ONLY=true, WEB_CONCURRENCY=1, no Redis
4. **Single hypothesis per deploy** - Keep loops under 10 minutes

## Test Commands
```bash
# Cold request
curl -i -m 10 -H "X-Api-Key:$KEY" "$URL/v4/positions/export-gpt/$SMALL"

# Wait 3 seconds

# Warm request  
curl -i -m 10 -H "X-Api-Key:$KEY" "$URL/v4/positions/export-gpt/$SMALL"

# Collect logs
railway logs --since 2m | grep "\[CHECK\]" > phase.log
```

## Evidence Collection
- [ ] Cold response headers + first 200B of body
- [ ] Warm response headers + first 200B of body  
- [ ] phase.log with CHECK counts
- [ ] Commit SHA: 5280dca

## Interpretation Guide
- If `trades_found=0` → problem is trade parser
- If `trades_found>0` and `positions_built=0` → bug in position builder/filters
- If both counts look right but body shows empty → serialization/snapshot path

## Next Steps
Once green:
- [ ] Add Redis back (new PR)
- [ ] Re-enable medium wallet (new ticket)
- [ ] Reintroduce detailed phase timers (new ticket) 