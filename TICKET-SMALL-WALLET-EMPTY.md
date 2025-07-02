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

## Micro-Experiment #1: Helius Response Check
**Commit**: 04025d7 - Added CHECK logs in `_fetch_signature_page` to capture:
- `[CHECK] helius_url=` - The exact URL being called
- `[CHECK] helius_resp_first_200B=` - First 200 bytes of raw response

### Expected Outcomes:
| Observation | Next Move |
|------------|-----------|
| `{"message":"Missing or invalid API key"}` | HELIUS_KEY not loaded in runtime |
| Empty JSON list `[]` | Wrong cluster or endpoint path |
| Non-empty array but still 0 trades | Parser bug in signature collection |

## Test Commands
```bash
# Single cold request only (no need for warm)
curl -i -m 10 -H "X-Api-Key:$KEY" "$URL/v4/positions/export-gpt/$SMALL"

# Immediately collect logs
railway logs --since 2m | grep "\[CHECK\] helius" > helius_check.log
```

## Evidence Collection
- [ ] Cold response headers + first 200B of body
- [ ] Warm response headers + first 200B of body  
- [ ] phase.log with CHECK counts
- [x] Commit SHA: 5280dca (original)
- [x] Commit SHA: 04025d7 (Helius checks)

## Interpretation Guide
- If `trades_found=0` → problem is trade parser
- If `trades_found>0` and `positions_built=0` → bug in position builder/filters
- If both counts look right but body shows empty → serialization/snapshot path

## Next Steps
Once green:
- [ ] Add Redis back (new PR)
- [ ] Re-enable medium wallet (new ticket)
- [ ] Reintroduce detailed phase timers (new ticket) 