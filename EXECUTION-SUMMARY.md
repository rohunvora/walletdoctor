# Execution Summary - Debug Reset Plan

## ✅ Completed Steps

### Step 0: Hard Baseline
- Checked out tag `v0.6.0-beta2` (commit 0659533)
- Created branch `debug/minimal-phase`

### Step 1: Added Two CHECK Logs
```python
# After trades fetched (line ~297)
logger.info(f"[CHECK] trades_found={len(trades)}")

# Before response built (line ~467)  
logger.info(f"[CHECK] positions_built={len(snapshot.positions)}")
```

### Step 2: Ready for Clean Deploy
- Branch pushed to trigger Railway deployment
- Environment checklist created in `DEPLOYMENT-CHECKLIST.md`

### Step 3-5: Documentation Created
- Test commands documented in `TICKET-SMALL-WALLET-EMPTY.md`
- Interpretation guide included
- GitHub tracking ticket created with acceptance criteria

## 🔄 Next Actions Required

1. **Configure Railway Environment**
   - Set `PRICE_HELIUS_ONLY=true`
   - Set `WEB_CONCURRENCY=1`
   - Unset all Redis/cache variables

2. **Wait for Deployment**
   - Monitor Railway for successful deployment
   - Look for "[BOOT]" log lines

3. **Execute Test Sequence**
   ```bash
   # After deployment completes:
   curl -i -m 10 -H "X-Api-Key:$KEY" "$URL/v4/positions/export-gpt/$SMALL"
   sleep 3
   curl -i -m 10 -H "X-Api-Key:$KEY" "$URL/v4/positions/export-gpt/$SMALL"
   railway logs --since 2m | grep "\[CHECK\]" > phase.log
   ```

4. **Collect Evidence**
   - Cold/warm response headers + body samples
   - phase.log with CHECK counts
   - Update ticket with findings

## Key Files
- **Code Change**: `src/api/wallet_analytics_api_v4_gpt.py` (commit 5280dca)
- **Ticket**: `TICKET-SMALL-WALLET-EMPTY.md`
- **Checklist**: `DEPLOYMENT-CHECKLIST.md`

## Success Metrics
The deployment is successful when:
- `[CHECK] trades_found > 0`
- `[CHECK] positions_built ≥ 1`  
- Response positions array length matches positions_built count

---
*One hypothesis per deploy, keep loops under 10 minutes* 