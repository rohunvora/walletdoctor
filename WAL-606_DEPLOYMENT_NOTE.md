# WAL-606 Deployment Note

## Current State
- The existing production deployment uses `src.api.wallet_analytics_api_v3:app`
- The V3 API has basic V4 endpoints without position tracking
- The new enhanced V4 API is in `src.api.wallet_analytics_api_v4:app`

## Integration Options

### Option 1: Update V3 to Import V4 Routes (Recommended for Testing)
```python
# In wallet_analytics_api_v3.py, replace the basic V4 routes with:
from src.api.wallet_analytics_api_v4 import (
    analyze_wallet_v4, 
    get_wallet_positions,
    get_progress as get_progress_v4
)

# Then update the route decorators to use the imported functions
```

### Option 2: Switch Deployment to V4 (Recommended for Production)
```bash
# Update Procfile:
web: gunicorn src.api.wallet_analytics_api_v4:app
```

The V4 API is a superset of V3 functionality and maintains full backward compatibility.

### Option 3: Run Both Side-by-Side (For A/B Testing)
- Keep V3 on main domain
- Deploy V4 to a subdomain or different port
- Gradually migrate traffic

## Feature Flag Configuration
Before enabling in production, set environment variables:
```bash
POSITIONS_ENABLED=false          # Start with disabled
UNREALIZED_PNL_ENABLED=false    # Enable after positions work
COST_BASIS_METHOD=weighted_avg  # or "fifo"
```

## Testing Checklist
1. Deploy with features disabled
2. Verify existing endpoints work unchanged
3. Enable positions for select test wallets
4. Monitor cache performance and API latency
5. Gradually increase feature flag enablement

## Rollback Plan
If issues arise:
1. Set `POSITIONS_ENABLED=false` - immediate effect
2. Optionally revert Procfile to use V3 API
3. Position data remains in cache until TTL expires

The implementation is designed for zero-downtime deployment and rollback. 