# Primitive-Based Analytics Architecture Implementation Plan

## 📊 Current System Inventory

### Database Tables
1. **diary** - Main event log (trades, messages, responses)
2. **user_wallets** - User-wallet mappings
3. **user_positions** - Current token holdings
4. **user_trades** - Trade history
5. **wallet_transactions** - Raw blockchain data
6. **price_snapshots** - 1-minute price history
7. **trade_notes** - User annotations
8. **user_goals** - User trading goals (JSON)
9. **user_facts** - Key-value facts about users

### Current Data Flow
```
Blockchain → Transaction Parser → Diary → GPT Tools → Response
                                    ↓
                              (No aggregation layer)
```

### GPT Tools (Current)
- `fetch_last_n_trades` - Gets N recent trades
- `fetch_trades_by_token` - Token-specific trades
- `fetch_trades_by_time` - Hour-of-day filtering (NOT date)
- `fetch_token_balance` - Current holdings
- `fetch_wallet_stats` - Cielo API integration
- `fetch_token_pnl` - Cielo P&L data
- `fetch_market_cap_context` - Market cap analysis
- `fetch_price_context` - Price movements
- `save_user_goal` - Goal storage
- `log_fact` - Fact storage

### Critical Limitations
1. **No date-based queries** - Can't get "today's trades"
2. **No aggregations** - Can't calculate daily P&L
3. **No comparisons** - Can't compare periods
4. **GPT does math** - Inaccurate calculations
5. **No progress tracking** - Goals without measurement

## 🎯 New Architecture: Event-Driven Primitives

### Core Philosophy
- **Events are facts** - Immutable, timestamped occurrences
- **Queries are flexible** - Any time window, any grouping
- **Calculations are exact** - Python does math, not GPT
- **Intelligence emerges** - GPT interprets, doesn't calculate

### New Data Model

```sql
-- Universal event store
CREATE TABLE events (
    event_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    wallet_address TEXT,
    timestamp TIMESTAMP NOT NULL,
    event_type TEXT NOT NULL,  -- 'trade', 'goal_set', 'fact_logged', etc
    event_subtype TEXT,         -- 'buy', 'sell', etc
    data JSON NOT NULL,         -- Flexible payload
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_time (user_id, timestamp),
    INDEX idx_type_time (event_type, timestamp),
    INDEX idx_wallet_time (wallet_address, timestamp)
);

-- Materialized views for performance (optional)
CREATE TABLE event_aggregates_daily (
    user_id INTEGER,
    date DATE,
    event_type TEXT,
    metrics JSON,  -- {"count": 10, "sum_pnl": 245.50, etc}
    PRIMARY KEY (user_id, date, event_type)
);
```

### Event Types & Schema

```python
# Trade Event
{
    "event_type": "trade",
    "event_subtype": "buy" | "sell",
    "data": {
        "token_symbol": "BONK",
        "token_address": "...",
        "sol_amount": 10.5,
        "token_amount": 1000000,
        "price_per_token": 0.0000105,
        "market_cap": 1500000,
        "bankroll_before": 100.5,
        "bankroll_after": 90.0,
        "pnl_usd": null,  # For sells
        "signature": "..."
    }
}

# Goal Event
{
    "event_type": "goal_set",
    "data": {
        "metric": "sol_balance",
        "target": 100,
        "window": "month",
        "raw_text": "trying to get to 100 sol"
    }
}

# Balance Update Event
{
    "event_type": "balance_update",
    "data": {
        "sol_balance": 33.6,
        "usd_value": 5880
    }
}
```

## 🛠️ Implementation Phases

### Phase 1: Foundation (Week 1)

#### 1.1 Create Event Infrastructure
```python
# event_store.py
class EventStore:
    async def record_event(
        self,
        user_id: int,
        event_type: str,
        data: Dict,
        timestamp: datetime = None
    ) -> int:
        """Records an event and returns event_id"""
        
    async def query_events(
        self,
        user_id: int,
        start_time: datetime,
        end_time: datetime,
        event_types: List[str] = None
    ) -> List[Event]:
        """Queries events in time window"""
```

#### 1.2 Create Aggregation Engine
```python
# aggregator.py
class EventAggregator:
    def aggregate(
        self,
        events: List[Event],
        group_by: str = None,  # 'day', 'hour', 'token'
        metrics: List[str] = None  # 'sum:pnl', 'count', 'avg:size'
    ) -> Dict:
        """Pure aggregation without interpretation"""
        
    def compare_periods(
        self,
        period1_events: List[Event],
        period2_events: List[Event],
        metrics: List[str]
    ) -> Dict:
        """Compare two time periods"""
```

#### 1.3 New GPT Tools
```python
# Enhanced diary_api.py
async def query_time_range(
    user_id: int,
    start: str,  # '2024-01-20', 'today', '7_days_ago'
    end: str,    # '2024-01-20', 'now'
    event_types: List[str] = None
) -> List[Dict]:
    """Get events for any time period"""
    
async def calculate_metrics(
    events: List[Dict],
    group_by: str = None,
    metrics: List[str] = None
) -> Dict:
    """Calculate aggregates over events"""
    
async def get_goal_progress(user_id: int) -> Dict:
    """Pre-calculated goal progress"""
```

### Phase 2: Migration (Week 1-2)

#### 2.1 Diary → Events Migration
```python
# migration/diary_to_events.py
async def migrate_diary_to_events():
    """
    1. Read all diary entries
    2. Transform to event format
    3. Insert into events table
    4. Maintain diary for backward compatibility
    """
```

#### 2.2 Dual-Write Period
```python
# During transition, write to both:
await write_to_diary(...)  # Existing
await event_store.record_event(...)  # New
```

#### 2.3 Update Trade Processing
```python
# telegram_bot_coach.py
async def _process_swap(...):
    # Existing diary write
    await write_to_diary('trade', user_id, wallet_address, trade_data)
    
    # New event write
    await event_store.record_event(
        user_id=user_id,
        event_type='trade',
        data={
            'subtype': swap.action.lower(),
            'token_symbol': token_symbol,
            'sol_amount': sol_amount,
            # ... all trade data
        }
    )
```

### Phase 3: GPT Integration (Week 2)

#### 3.1 Update Tool Definitions
```python
def _get_gpt_tools(self):
    return existing_tools + [
        {
            "type": "function",
            "function": {
                "name": "query_time_range",
                "description": "Get events for any time period. Use for 'how am I doing today?' type questions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start": {
                            "type": "string",
                            "description": "Start time: 'today', 'yesterday', '7_days_ago', or '2024-01-20'"
                        },
                        "end": {
                            "type": "string", 
                            "description": "End time: 'now', 'today', or '2024-01-20'"
                        },
                        "event_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter by event types: ['trade', 'balance_update']"
                        }
                    },
                    "required": ["start", "end"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "calculate_metrics",
                "description": "Calculate sums, averages, counts over events",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "events": {
                            "type": "array",
                            "description": "Events from query_time_range"
                        },
                        "group_by": {
                            "type": "string",
                            "enum": ["day", "hour", "token", "action"],
                            "description": "How to group events"
                        },
                        "metrics": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Metrics to calculate: ['sum:sol_amount', 'count', 'sum:pnl_usd']"
                        }
                    },
                    "required": ["events", "metrics"]
                }
            }
        }
    ]
```

#### 3.2 Update System Prompt
```markdown
## data access

you now have flexible event querying:

tools for time-based analysis:
- query_time_range: get events for any period
- calculate_metrics: aggregate events accurately
- get_goal_progress: pre-calculated progress

when users ask about performance:
1. identify the time period they care about
2. query relevant events
3. calculate appropriate metrics
4. interpret results

examples:
- "how am i doing today?"
  → query_time_range(start='today', end='now', event_types=['trade'])
  → calculate_metrics(events, metrics=['sum:pnl_usd', 'count'])
  → "up $145 on 7 trades today"

- "am i improving?"
  → query this week vs last week
  → compare metrics
  → "this week: 65% wins vs last week: 45%"

never calculate math yourself. always use calculate_metrics.
```

### Phase 4: Testing & Validation (Week 2-3)

#### 4.1 Test Scenarios
```python
# tests/test_analytics.py
async def test_daily_pnl():
    """Verify daily P&L calculations match manual math"""
    
async def test_period_comparison():
    """Test week-over-week comparisons"""
    
async def test_goal_progress():
    """Test various goal type calculations"""
    
async def test_edge_cases():
    """Empty periods, single trades, timezone issues"""
```

#### 4.2 Performance Testing
- Query response times with 10k+ events
- Aggregation performance
- Concurrent user load

### Phase 5: Cutover (Week 3)

1. **Verify data integrity** - Event counts match diary
2. **Shadow mode** - Run both systems, compare outputs
3. **Gradual rollout** - Enable for test users first
4. **Full cutover** - Switch all users to event-based
5. **Deprecate diary queries** - Remove old tools

## 📈 Success Metrics

1. **Query Performance**: <100ms for daily queries
2. **Accuracy**: 100% match with manual calculations
3. **Flexibility**: Support any time window query
4. **User Satisfaction**: Can answer common questions

## 🚨 Risk Mitigation

1. **Data Loss**: Keep diary table as backup
2. **Performance**: Add indexes, consider materialized views
3. **Compatibility**: Dual-write during transition
4. **Testing**: Extensive test coverage before cutover

## 📝 Documentation TODOs

1. API documentation for new tools
2. Migration guide for developers
3. Updated system prompt guide
4. Performance tuning guide

## 🎯 Definition of Done

- [ ] Events table created and indexed
- [ ] EventStore class implemented
- [ ] Aggregator class implemented  
- [ ] Historical data migrated
- [ ] New GPT tools working
- [ ] System prompt updated
- [ ] All tests passing
- [ ] Performance benchmarks met
- [ ] Documentation complete

---

This plan provides clean primitives that enable any future analytics need without assumptions or band-aids. 