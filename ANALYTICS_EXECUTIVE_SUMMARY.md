# Executive Summary: Analytics Architecture Implementation

## The Ask
Enable the bot to answer time-based questions like "How am I doing today?" and track progress toward goals like "$100/day profit".

## The Problem
Current system can only query "last N trades" or "trades between 2-6am". Cannot:
- Query by date ("today", "this week")
- Calculate aggregates (daily P&L, win rate by period)
- Track rate-based goals ($X/day)
- Compare periods ("this week vs last week")

## The Solution
Build a primitive event store that records all user actions as timestamped events, with a pure Python aggregator for accurate calculations.

```
Current: diary → GPT does math → often wrong
New: events → Python aggregates → GPT interprets → always accurate
```

## Implementation Overview

### What We're Building
1. **Event Store** (~150 LOC)
   - Universal table for all user actions
   - Flexible JSON schema
   - Proper time-based indexes

2. **Aggregator** (~200 LOC)
   - Pure Python calculations
   - Standard metrics (sum, avg, count, group by)
   - Period comparisons

3. **New GPT Tools** (~100 LOC)
   - `query_time_range("today", "now")`
   - `calculate_metrics(events, ["sum:pnl_usd", "count"])`
   - `get_goal_progress()` - pre-calculated

### Migration Strategy
1. **Dual-write period** - Write to both diary and events
2. **Shadow mode** - Compare outputs, build confidence
3. **Gradual cutover** - Switch tools one at a time
4. **Keep diary** - As backup, no breaking changes

## Timeline & Effort
- **Development**: 2-3 weeks
- **Testing**: 1 week
- **Migration**: 3-5 days
- **Total**: 3-4 weeks

## Risk Assessment
- **Risk Level**: MEDIUM-LOW
- **Main Risks**: Performance at scale, migration accuracy
- **Mitigation**: Extensive testing, gradual rollout, full rollback capability

## Why This Approach

### Alternatives Rejected
- **Quick fix aggregation table**: Doesn't solve root problem
- **Full event sourcing**: Over-engineered for our needs
- **External time-series DB**: Adds operational complexity

### This Approach Wins Because
- **Minimal complexity** - 550 LOC total addition
- **Maximum flexibility** - Any future query possible
- **No assumptions** - Store facts, let intelligence emerge
- **Gradual migration** - No big bang, low risk

## Business Impact
- Users can track daily/weekly progress
- Bot can answer natural time-based questions
- Goals become measurable, not just aspirational
- Foundation for future analytics (streaks, patterns, comparisons)

## Decision Required
Proceed with implementation? The plan is thorough, risks are mitigated, and the approach aligns with our primitives-first philosophy.

## Next Steps If Approved
1. Create feature branch
2. Implement event store (Week 1)
3. Build aggregator (Week 1-2)
4. Add GPT tools (Week 2)
5. Test extensively (Week 3)
6. Migrate with dual-write (Week 4) 