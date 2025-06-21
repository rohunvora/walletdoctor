# Event-Driven Analytics Technical Design

## System Architecture

### Design Principles
1. **Events as Single Source of Truth** - All data derives from events
2. **Immutability** - Events are never modified, only appended
3. **Flexibility** - Schema supports any future event type
4. **Performance** - Sub-100ms query response times
5. **Accuracy** - All calculations in Python, not GPT

### Component Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Blockchain    │────▶│ Event Store  │────▶│   Aggregator    │
│   Monitors      │     │              │     │                 │
└─────────────────┘     └──────────────┘     └─────────────────┘
                               │                      │
                               ▼                      ▼
                        ┌──────────────┐     ┌─────────────────┐
                        │  GPT Tools   │────▶│  GPT Responses  │
                        │              │     │                 │
                        └──────────────┘     └─────────────────┘
```

## Detailed Component Design

### 1. Event Store

```python
# event_store.py
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import duckdb
import json

class Event:
    """Immutable event representation"""
    def __init__(self, event_id: int, user_id: int, timestamp: datetime,
                 event_type: str, event_subtype: str, data: Dict):
        self.event_id = event_id
        self.user_id = user_id
        self.timestamp = timestamp
        self.event_type = event_type
        self.event_subtype = event_subtype
        self.data = data
    
    def to_dict(self) -> Dict:
        return {
            'event_id': self.event_id,
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat(),
            'event_type': self.event_type,
            'event_subtype': self.event_subtype,
            'data': self.data
        }

class EventStore:
    def __init__(self, db_path: str = "pocket_coach.db"):
        self.db_path = db_path
        
    async def record_event(
        self,
        user_id: int,
        event_type: str,
        data: Dict,
        event_subtype: str = None,
        wallet_address: str = None,
        timestamp: datetime = None
    ) -> int:
        """Records an event and returns event_id"""
        if timestamp is None:
            timestamp = datetime.now()
            
        db = duckdb.connect(self.db_path)
        try:
            result = db.execute("""
                INSERT INTO events (
                    user_id, wallet_address, timestamp, 
                    event_type, event_subtype, data
                ) VALUES (?, ?, ?, ?, ?, ?)
                RETURNING event_id
            """, [
                user_id, wallet_address, timestamp,
                event_type, event_subtype, json.dumps(data)
            ]).fetchone()
            
            return result[0]
        finally:
            db.close()
    
    async def query_events(
        self,
        user_id: int,
        start_time: datetime,
        end_time: datetime,
        event_types: List[str] = None,
        wallet_address: str = None
    ) -> List[Event]:
        """Query events in time window"""
        db = duckdb.connect(self.db_path)
        try:
            query = """
                SELECT event_id, user_id, timestamp, 
                       event_type, event_subtype, data
                FROM events
                WHERE user_id = ?
                AND timestamp >= ?
                AND timestamp <= ?
            """
            params = [user_id, start_time, end_time]
            
            if event_types:
                placeholders = ','.join(['?' for _ in event_types])
                query += f" AND event_type IN ({placeholders})"
                params.extend(event_types)
                
            if wallet_address:
                query += " AND wallet_address = ?"
                params.append(wallet_address)
                
            query += " ORDER BY timestamp DESC"
            
            results = db.execute(query, params).fetchall()
            
            return [
                Event(
                    event_id=row[0],
                    user_id=row[1],
                    timestamp=row[2],
                    event_type=row[3],
                    event_subtype=row[4],
                    data=json.loads(row[5])
                )
                for row in results
            ]
        finally:
            db.close()
```

### 2. Event Aggregator

```python
# aggregator.py
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Any
import statistics

class EventAggregator:
    """Pure functions for event aggregation"""
    
    def aggregate(
        self,
        events: List[Event],
        group_by: str = None,
        metrics: List[str] = None
    ) -> Dict[str, Any]:
        """
        Aggregate events with specified metrics
        
        Args:
            events: List of events to aggregate
            group_by: 'day', 'hour', 'token', 'action', etc
            metrics: ['sum:pnl_usd', 'count', 'avg:sol_amount', etc]
            
        Returns:
            Aggregated results
        """
        if not events:
            return {'total_count': 0, 'groups': {}}
            
        if not metrics:
            metrics = ['count']
            
        # Group events
        groups = self._group_events(events, group_by)
        
        # Calculate metrics for each group
        results = {
            'total_count': len(events),
            'groups': {}
        }
        
        for group_key, group_events in groups.items():
            results['groups'][group_key] = self._calculate_metrics(
                group_events, metrics
            )
            
        # Also calculate overall metrics
        results['overall'] = self._calculate_metrics(events, metrics)
        
        return results
    
    def _group_events(
        self, 
        events: List[Event], 
        group_by: str
    ) -> Dict[str, List[Event]]:
        """Group events by specified dimension"""
        if not group_by:
            return {'all': events}
            
        groups = defaultdict(list)
        
        for event in events:
            if group_by == 'day':
                key = event.timestamp.date().isoformat()
            elif group_by == 'hour':
                key = event.timestamp.hour
            elif group_by == 'token':
                key = event.data.get('token_symbol', 'unknown')
            elif group_by == 'action':
                key = event.event_subtype or event.event_type
            else:
                key = 'unknown'
                
            groups[key].append(event)
            
        return dict(groups)
    
    def _calculate_metrics(
        self,
        events: List[Event],
        metrics: List[str]
    ) -> Dict[str, Any]:
        """Calculate specified metrics for event list"""
        results = {}
        
        for metric in metrics:
            if metric == 'count':
                results['count'] = len(events)
                
            elif metric.startswith('sum:'):
                field = metric.split(':')[1]
                values = [e.data.get(field, 0) for e in events]
                results[metric] = sum(v for v in values if v is not None)
                
            elif metric.startswith('avg:'):
                field = metric.split(':')[1]
                values = [e.data.get(field, 0) for e in events]
                valid_values = [v for v in values if v is not None]
                results[metric] = statistics.mean(valid_values) if valid_values else 0
                
            elif metric.startswith('max:'):
                field = metric.split(':')[1]
                values = [e.data.get(field, 0) for e in events]
                valid_values = [v for v in values if v is not None]
                results[metric] = max(valid_values) if valid_values else 0
                
            elif metric.startswith('min:'):
                field = metric.split(':')[1]
                values = [e.data.get(field, 0) for e in events]
                valid_values = [v for v in values if v is not None]
                results[metric] = min(valid_values) if valid_values else 0
                
            elif metric == 'win_rate':
                trades = [e for e in events if e.event_type == 'trade']
                wins = [t for t in trades if t.data.get('pnl_usd', 0) > 0]
                results['win_rate'] = len(wins) / len(trades) * 100 if trades else 0
                
        return results
    
    def compare_periods(
        self,
        period1_events: List[Event],
        period2_events: List[Event],
        metrics: List[str]
    ) -> Dict[str, Any]:
        """Compare metrics between two time periods"""
        period1_metrics = self._calculate_metrics(period1_events, metrics)
        period2_metrics = self._calculate_metrics(period2_events, metrics)
        
        comparison = {
            'period1': period1_metrics,
            'period2': period2_metrics,
            'changes': {}
        }
        
        # Calculate changes
        for metric in metrics:
            if metric in period1_metrics and metric in period2_metrics:
                old_val = period2_metrics[metric]
                new_val = period1_metrics[metric]
                
                if isinstance(old_val, (int, float)) and old_val != 0:
                    change_pct = ((new_val - old_val) / old_val) * 100
                    comparison['changes'][metric] = {
                        'absolute': new_val - old_val,
                        'percentage': change_pct
                    }
                    
        return comparison
```

### 3. Time Parsing Utilities

```python
# time_utils.py
from datetime import datetime, date, timedelta
from typing import Tuple

def parse_time_string(time_str: str) -> datetime:
    """
    Parse flexible time strings into datetime objects
    
    Examples:
        'today' -> start of today
        'now' -> current time
        '7_days_ago' -> 7 days before now
        'yesterday' -> start of yesterday
        '2024-01-20' -> start of that date
    """
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if time_str == 'now':
        return now
    elif time_str == 'today':
        return today
    elif time_str == 'yesterday':
        return today - timedelta(days=1)
    elif time_str.endswith('_days_ago'):
        days = int(time_str.split('_')[0])
        return now - timedelta(days=days)
    elif time_str.endswith('_hours_ago'):
        hours = int(time_str.split('_')[0])
        return now - timedelta(hours=hours)
    else:
        # Try to parse as date
        try:
            return datetime.strptime(time_str, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Cannot parse time string: {time_str}")

def get_period_bounds(period: str) -> Tuple[datetime, datetime]:
    """Get start and end times for common periods"""
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if period == 'today':
        return today, now
    elif period == 'yesterday':
        yesterday = today - timedelta(days=1)
        return yesterday, today
    elif period == 'this_week':
        start = today - timedelta(days=today.weekday())
        return start, now
    elif period == 'last_week':
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=7)
        return start, end
    elif period == 'this_month':
        start = today.replace(day=1)
        return start, now
    else:
        raise ValueError(f"Unknown period: {period}")
```

### 4. Enhanced GPT Tools

```python
# diary_api.py additions
async def query_time_range(
    user_id: int,
    start: str,
    end: str,
    event_types: List[str] = None
) -> List[Dict]:
    """
    Get events for any time period
    
    Args:
        user_id: User ID
        start: Start time string ('today', '7_days_ago', '2024-01-20')
        end: End time string ('now', 'today', '2024-01-20')
        event_types: Optional filter for event types
        
    Returns:
        List of event dictionaries
    """
    event_store = EventStore()
    
    # Parse time strings
    start_time = parse_time_string(start)
    end_time = parse_time_string(end)
    
    # Query events
    events = await event_store.query_events(
        user_id=user_id,
        start_time=start_time,
        end_time=end_time,
        event_types=event_types
    )
    
    # Convert to dictionaries for GPT
    return [event.to_dict() for event in events]

async def calculate_metrics(
    events: List[Dict],
    group_by: str = None,
    metrics: List[str] = None
) -> Dict:
    """
    Calculate aggregates over events
    
    Args:
        events: Event dictionaries from query_time_range
        group_by: How to group ('day', 'hour', 'token', 'action')
        metrics: Metrics to calculate (['sum:pnl_usd', 'count', 'avg:size'])
        
    Returns:
        Aggregated metrics
    """
    aggregator = EventAggregator()
    
    # Convert dicts back to Event objects
    event_objects = [
        Event(
            event_id=e['event_id'],
            user_id=e['user_id'],
            timestamp=datetime.fromisoformat(e['timestamp']),
            event_type=e['event_type'],
            event_subtype=e.get('event_subtype'),
            data=e['data']
        )
        for e in events
    ]
    
    # Calculate aggregates
    return aggregator.aggregate(
        events=event_objects,
        group_by=group_by,
        metrics=metrics or ['count']
    )

async def get_goal_progress(user_id: int) -> Dict:
    """Get pre-calculated goal progress"""
    # Fetch user's goal
    goal_data = await fetch_user_goal(user_id)
    if not goal_data:
        return {'has_goal': False}
    
    goal = goal_data['goal']
    metric = goal.get('metric')
    target = goal.get('target')
    
    # Calculate current value based on metric type
    if metric == 'sol_balance':
        # Get latest balance
        wallet = await get_user_wallet(user_id)
        current = await get_sol_balance(wallet)
        remaining = target - current
        progress_pct = (current / target * 100) if target > 0 else 0
        
        return {
            'has_goal': True,
            'metric': metric,
            'current': current,
            'target': target,
            'remaining': remaining,
            'progress_pct': progress_pct,
            'on_track': current >= target * 0.8  # Simple heuristic
        }
        
    elif metric == 'profit_daily':
        # Calculate average daily profit
        events = await query_time_range(
            user_id, '7_days_ago', 'now', ['trade']
        )
        
        # Group by day and calculate
        aggregates = await calculate_metrics(
            events, 
            group_by='day',
            metrics=['sum:pnl_usd']
        )
        
        daily_profits = [
            day_data.get('sum:pnl_usd', 0) 
            for day_data in aggregates['groups'].values()
        ]
        avg_daily = sum(daily_profits) / len(daily_profits) if daily_profits else 0
        
        return {
            'has_goal': True,
            'metric': metric,
            'current': avg_daily,
            'target': target,
            'remaining': target - avg_daily,
            'on_track': avg_daily >= target * 0.8
        }
        
    # Add more goal types as needed
    
    return {'has_goal': True, 'metric': metric, 'supported': False}
```

## Migration Strategy

### Phase 1: Schema Creation
```sql
-- Run in db_migrations.py
CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id INTEGER NOT NULL,
    wallet_address TEXT,
    timestamp TIMESTAMP NOT NULL,
    event_type TEXT NOT NULL,
    event_subtype TEXT,
    data JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_user_time ON events(user_id, timestamp);
CREATE INDEX idx_events_type_time ON events(event_type, timestamp);
CREATE INDEX idx_events_wallet_time ON events(wallet_address, timestamp);
```

### Phase 2: Data Migration
```python
# migration/migrate_diary_to_events.py
async def migrate_diary_to_events():
    """Migrate existing diary entries to events"""
    db = duckdb.connect('pocket_coach.db')
    event_store = EventStore()
    
    # Get all diary entries
    diary_entries = db.execute("""
        SELECT user_id, wallet_address, entry_type, 
               data, timestamp
        FROM diary
        ORDER BY timestamp
    """).fetchall()
    
    migrated = 0
    for user_id, wallet, entry_type, data_json, timestamp in diary_entries:
        data = json.loads(data_json)
        
        # Map diary entry types to event types
        if entry_type == 'trade':
            event_type = 'trade'
            event_subtype = data.get('action', '').lower()
        elif entry_type == 'message':
            event_type = 'user_message'
            event_subtype = None
        elif entry_type == 'response':
            event_type = 'bot_response'
            event_subtype = None
        else:
            event_type = entry_type
            event_subtype = None
            
        # Record event
        await event_store.record_event(
            user_id=user_id,
            event_type=event_type,
            event_subtype=event_subtype,
            data=data,
            wallet_address=wallet,
            timestamp=timestamp
        )
        
        migrated += 1
        if migrated % 1000 == 0:
            print(f"Migrated {migrated} entries...")
            
    print(f"Migration complete: {migrated} entries")
```

## Performance Considerations

### Query Optimization
1. **Indexed queries** - All common query patterns have indexes
2. **Time-based partitioning** - Consider for >1M events
3. **Materialized views** - For frequently accessed aggregates
4. **Connection pooling** - Reuse database connections

### Caching Strategy
```python
# Simple in-memory cache for recent queries
from functools import lru_cache
from datetime import datetime, timedelta

@lru_cache(maxsize=100)
def get_cached_daily_stats(user_id: int, date_str: str):
    """Cache daily stats for completed days"""
    # Only cache if date is not today
    if date_str != datetime.now().date().isoformat():
        return calculate_daily_stats(user_id, date_str)
    return None
```

## Testing Strategy

### Unit Tests
```python
# tests/test_event_store.py
async def test_record_and_query_events():
    """Test basic event operations"""
    store = EventStore(":memory:")
    
    # Record event
    event_id = await store.record_event(
        user_id=123,
        event_type='trade',
        event_subtype='buy',
        data={'token': 'BONK', 'amount': 10.5}
    )
    
    # Query it back
    events = await store.query_events(
        user_id=123,
        start_time=datetime.now() - timedelta(hours=1),
        end_time=datetime.now()
    )
    
    assert len(events) == 1
    assert events[0].data['token'] == 'BONK'
```

### Integration Tests
```python
# tests/test_gpt_tools.py
async def test_daily_pnl_calculation():
    """Test that daily P&L matches expected values"""
    # Setup test data
    await create_test_trades(user_id=123)
    
    # Query today's trades
    events = await query_time_range(123, 'today', 'now', ['trade'])
    
    # Calculate metrics
    metrics = await calculate_metrics(
        events,
        metrics=['sum:pnl_usd', 'count', 'win_rate']
    )
    
    assert metrics['overall']['sum:pnl_usd'] == 245.50
    assert metrics['overall']['count'] == 5
    assert metrics['overall']['win_rate'] == 60.0
```

## Monitoring & Observability

### Key Metrics
1. **Query latency** - P50, P95, P99
2. **Event ingestion rate** - Events/second
3. **Storage growth** - MB/day
4. **Cache hit rate** - For completed days

### Logging
```python
import logging
logger = logging.getLogger(__name__)

# Log slow queries
if query_time > 100:  # ms
    logger.warning(f"Slow query: {query_time}ms for {user_id}")
```

This design provides a flexible, performant foundation for any analytics need without making assumptions about specific use cases. 