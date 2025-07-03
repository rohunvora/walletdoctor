# TODO: bump trades schema to v0.8.0 after POS-001 / PRC-001 land

# Schema Versioning Policy

## Current Versions

| Endpoint | Version | Status | Description |
|----------|---------|--------|-------------|
| `/v4/trades/export-gpt/{wallet}` | v0.7.0 | FROZEN | Trades only, no positions or current prices |
| `/v4/positions/export-gpt/{wallet}` | v1.1 | STABLE | Full positions with unrealized P&L |

## Version History

### v0.7.0 (2025-01-02)
- Initial trades export endpoint
- Basic trade data without pricing
- **Frozen until POS-001/PRC-001 complete**

### v0.8.0 (Future)
- Add `current_price_usd` to trades
- Requires POS-001 (position builder fix)
- Requires PRC-001 (Helius-only pricing)

### v1.1 (2024-12-15)
- Positions endpoint with full P&L
- Schema compatible with GPT Actions
- Price confidence levels

## Breaking Change Procedure

### Definition
A breaking change is any modification that:
- Removes or renames existing fields
- Changes field types (e.g., string → number)
- Modifies required field status
- Alters response structure

### Approval Process
1. **Proposal**: Create ticket with impact analysis
2. **Review**: Engineering lead + GPT PM approval required
3. **Notice Period**: 
   - Minor changes: 2 weeks notice
   - Major changes: 4 weeks notice
4. **Communication**:
   - Email all API key holders
   - Update docs with migration guide
   - Add deprecation warnings to old version

### Versioning Strategy
- **Patch** (x.x.1): Backward-compatible fixes
- **Minor** (x.1.x): New optional fields
- **Major** (1.x.x): Breaking changes

### Deprecation Timeline
1. **Announce**: Via email + API response header
2. **Warn**: Add `X-Deprecated: true` header
3. **Sunset**: Old version returns 410 Gone
4. **Remove**: After 90 days post-sunset

### Emergency Changes
For security fixes only:
- 24-hour notice minimum
- Direct contact to active users
- Requires CTO approval

## Non-Breaking Additions
These changes do NOT require version bump:
- Adding optional fields
- Extending enums with new values
- Adding response headers
- Performance improvements

## Testing Requirements
Before any version release:
- [ ] Schema validation passes
- [ ] Backward compatibility verified
- [ ] GPT integration tests green
- [ ] Migration guide documented 