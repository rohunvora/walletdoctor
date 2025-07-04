# TODO: bump trades schema to v0.8.0 after POS-001 / PRC-001 land

# Schema Versioning Policy

## Current Versions

| Endpoint | Version | Status | Description |
|----------|---------|--------|-------------|
| `/v4/trades/export-gpt/{wallet}` | v0.7.0 | STABLE | Trades only, no positions or current prices |
| `/v4/positions/export-gpt/{wallet}` | v0.8.0-prices | **ACTIVE** | Full positions with SOL spot pricing |

## Version History

### v0.8.0-prices (2025-01-15) ⭐ **CURRENT**
- **PRC-001**: SOL spot pricing for all positions using single SOL/USD rate
- **New Fields**: `price_source` field showing "sol_spot_price" when active
- **Enhanced Pricing**: `current_price_usd` now populated via CoinGecko SOL price
- **Consistent Values**: All positions use same SOL exchange rate for trading-friendly analysis
- **Graceful Degradation**: Null pricing values when SOL price unavailable
- **Performance**: <200ms price fetch with 30s caching, >95% success rate
- **Schema Version**: Response includes `"schema_version": "v0.8.0-prices"`

**Backward Compatibility**: ✅ **NON-BREAKING**
- All existing fields preserved in same format
- New `price_source` field is optional (can be null)
- v0.7.0 clients can safely ignore new fields
- No field removals or type changes

**Production Validation**: 
- Demo wallets: 18 + 356 positions priced correctly
- Response format: `{"current_price_usd": "152.64", "price_source": "sol_spot_price"}`
- ChatGPT ready for meaningful dollar value discussions

### v0.7.0 (2025-01-02) 📌 **LEGACY STABLE**
- Initial trades export endpoint
- Basic trade data without pricing
- **Status**: Remains valid indefinitely (no breaking changes in v0.8.0-prices)
- **Use Case**: Simple trade analysis without position pricing

### v1.1 (2024-12-15) 🔄 **DEPRECATED** → **Migrated to v0.8.0-prices**
- Legacy positions endpoint schema
- No longer recommended for new integrations
- Use v0.8.0-prices for improved SOL pricing

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
- **Minor** (x.1.x): New optional fields (like v0.8.0-prices)
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
- Adding optional fields (like `price_source`)
- Improving existing field accuracy (like `current_price_usd`)
- Performance optimizations
- New nullable field values

## Migration Guide: v1.1 → v0.8.0-prices

If you're using the legacy v1.1 schema, migrate to v0.8.0-prices:

**Before (v1.1)**:
```json
{
  "schema_version": "1.1",
  "positions": [{
    "current_price_usd": null,
    "price_confidence": "unavailable"
  }]
}
```

**After (v0.8.0-prices)**:
```json
{
  "schema_version": "v0.8.0-prices", 
  "positions": [{
    "current_price_usd": "152.64",
    "current_value_usd": "152640000.00",
    "price_confidence": "est",
    "price_source": "sol_spot_price"
  }]
}
```

**Changes**:
- ✅ All existing fields preserved
- ➕ New `price_source` field indicates pricing method
- 🔄 `current_price_usd` now populated with SOL spot price
- 📈 Reliable pricing enables meaningful ChatGPT financial discussions

## Testing Requirements
Before any version release:
- [ ] Schema validation passes
- [ ] Backward compatibility verified
- [ ] GPT integration tests green
- [ ] Migration guide documented 