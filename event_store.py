"""
Event Store - Primitive-based universal event storage system
Following the primitives-over-templates philosophy
"""
import json
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import uuid


@dataclass(frozen=True)
class Event:
    """Immutable event representing any user action"""
    user_id: str
    event_type: str
    timestamp: datetime
    data: Dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for storage"""
        return {
            'event_id': self.event_id,
            'user_id': self.user_id,
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat(),
            'data': json.dumps(self.data)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create event from dictionary"""
        return cls(
            event_id=data['event_id'],
            user_id=data['user_id'],
            event_type=data['event_type'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            data=json.loads(data['data']) if isinstance(data['data'], str) else data['data']
        )


class EventStore:
    """Store and retrieve events - no assumptions about usage"""
    
    def __init__(self, db_path: str = 'events.db'):
        # Use separate SQLite database for events (pocket_coach.db is DuckDB)
        self.db_path = db_path
        self._ensure_table()
    
    def _ensure_table(self):
        """Create events table if it doesn't exist"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Indexes for common query patterns
            conn.execute('CREATE INDEX IF NOT EXISTS idx_events_user_timestamp ON events(user_id, timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_events_type_timestamp ON events(event_type, timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)')
    
    def record_event(self, event: Event) -> bool:
        """Record an event to the store"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO events (event_id, user_id, event_type, timestamp, data)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    event.event_id,
                    event.user_id,
                    event.event_type,
                    event.timestamp.isoformat(),
                    json.dumps(event.data)
                ))
            return True
        except Exception as e:
            print(f"Error recording event: {e}")
            return False
    
    def query_events(self, 
                     user_id: Optional[str] = None,
                     event_types: Optional[List[str]] = None,
                     start_time: Optional[datetime] = None,
                     end_time: Optional[datetime] = None,
                     limit: Optional[int] = None) -> List[Event]:
        """
        Query events with flexible filtering
        No assumptions about what you're looking for
        """
        query = 'SELECT * FROM events WHERE 1=1'
        params = []
        
        if user_id:
            query += ' AND user_id = ?'
            params.append(user_id)
        
        if event_types:
            placeholders = ','.join(['?' for _ in event_types])
            query += f' AND event_type IN ({placeholders})'
            params.extend(event_types)
        
        if start_time:
            query += ' AND timestamp >= ?'
            params.append(start_time.isoformat())
        
        if end_time:
            query += ' AND timestamp <= ?'
            params.append(end_time.isoformat())
        
        query += ' ORDER BY timestamp DESC'
        
        if limit:
            query += ' LIMIT ?'
            params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            
            events = []
            for row in cursor:
                events.append(Event.from_dict(dict(row)))
            
            return events
    
    def count_events(self,
                     user_id: Optional[str] = None,
                     event_type: Optional[str] = None,
                     start_time: Optional[datetime] = None,
                     end_time: Optional[datetime] = None) -> int:
        """Count events matching criteria"""
        query = 'SELECT COUNT(*) as count FROM events WHERE 1=1'
        params = []
        
        if user_id:
            query += ' AND user_id = ?'
            params.append(user_id)
        
        if event_type:
            query += ' AND event_type = ?'
            params.append(event_type)
        
        if start_time:
            query += ' AND timestamp >= ?'
            params.append(start_time.isoformat())
        
        if end_time:
            query += ' AND timestamp <= ?'
            params.append(end_time.isoformat())
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchone()[0]


# Event type constants (not rigid categories, just common ones)
TRADE_BUY = 'trade_buy'
TRADE_SELL = 'trade_sell'
GOAL_SET = 'goal_set'
GOAL_PROGRESS = 'goal_progress'
USER_MESSAGE = 'user_message'
BOT_RESPONSE = 'bot_response'
FACT_STORED = 'fact_stored' 