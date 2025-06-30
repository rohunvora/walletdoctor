"""
Unit tests for event store - testing primitive-based storage
"""
import unittest
import tempfile
import os
from datetime import datetime, timedelta
from event_store import Event, EventStore, TRADE_BUY, TRADE_SELL


class TestEvent(unittest.TestCase):
    """Test the Event dataclass"""
    
    def test_event_creation(self):
        """Test creating an event"""
        event = Event(
            user_id="test_user",
            event_type=TRADE_BUY,
            timestamp=datetime.now(),
            data={"token": "BONK", "amount": 1.5}
        )
        
        self.assertEqual(event.user_id, "test_user")
        self.assertEqual(event.event_type, TRADE_BUY)
        self.assertEqual(event.data["token"], "BONK")
        self.assertTrue(event.event_id)  # Should have auto-generated ID
    
    def test_event_immutability(self):
        """Test that events are immutable"""
        event = Event(
            user_id="test_user",
            event_type=TRADE_BUY,
            timestamp=datetime.now(),
            data={"amount": 1.0}
        )
        
        # Should raise error when trying to modify
        with self.assertRaises(AttributeError):
            event.user_id = "modified"
    
    def test_event_serialization(self):
        """Test converting event to/from dict"""
        now = datetime.now()
        event = Event(
            user_id="test_user",
            event_type=TRADE_SELL,
            timestamp=now,
            data={"profit": 2.5, "token": "WIF"}
        )
        
        # To dict
        event_dict = event.to_dict()
        self.assertEqual(event_dict["user_id"], "test_user")
        self.assertEqual(event_dict["event_type"], TRADE_SELL)
        self.assertIn("profit", event_dict["data"])
        
        # From dict (simulate DB retrieval)
        reconstructed = Event.from_dict(event_dict)
        self.assertEqual(reconstructed.user_id, event.user_id)
        self.assertEqual(reconstructed.event_type, event.event_type)
        self.assertEqual(reconstructed.data, event.data)


class TestEventStore(unittest.TestCase):
    """Test the EventStore class"""
    
    def setUp(self):
        """Create temporary database for each test"""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_file.close()
        self.store = EventStore(self.temp_file.name)
    
    def tearDown(self):
        """Clean up temporary database"""
        os.unlink(self.temp_file.name)
    
    def test_record_single_event(self):
        """Test recording a single event"""
        event = Event(
            user_id="user123",
            event_type=TRADE_BUY,
            timestamp=datetime.now(),
            data={"token": "BONK", "amount": 10.0}
        )
        
        success = self.store.record_event(event)
        self.assertTrue(success)
        
        # Verify it was stored
        events = self.store.query_events(user_id="user123")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, TRADE_BUY)
    
    def test_query_by_user(self):
        """Test querying events by user ID"""
        # Add events for multiple users
        for i in range(3):
            self.store.record_event(Event(
                user_id="user1",
                event_type=TRADE_BUY,
                timestamp=datetime.now(),
                data={"amount": i}
            ))
        
        for i in range(2):
            self.store.record_event(Event(
                user_id="user2",
                event_type=TRADE_SELL,
                timestamp=datetime.now(),
                data={"amount": i}
            ))
        
        # Query for user1
        user1_events = self.store.query_events(user_id="user1")
        self.assertEqual(len(user1_events), 3)
        
        # Query for user2
        user2_events = self.store.query_events(user_id="user2")
        self.assertEqual(len(user2_events), 2)
    
    def test_query_by_event_type(self):
        """Test querying by event type"""
        # Mix of buy and sell events
        self.store.record_event(Event(
            user_id="user1",
            event_type=TRADE_BUY,
            timestamp=datetime.now(),
            data={"token": "BONK"}
        ))
        
        self.store.record_event(Event(
            user_id="user1",
            event_type=TRADE_SELL,
            timestamp=datetime.now(),
            data={"token": "BONK"}
        ))
        
        self.store.record_event(Event(
            user_id="user1",
            event_type=TRADE_BUY,
            timestamp=datetime.now(),
            data={"token": "WIF"}
        ))
        
        # Query only buys
        buys = self.store.query_events(event_types=[TRADE_BUY])
        self.assertEqual(len(buys), 2)
        
        # Query only sells
        sells = self.store.query_events(event_types=[TRADE_SELL])
        self.assertEqual(len(sells), 1)
    
    def test_query_by_time_range(self):
        """Test querying by time range"""
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        last_week = now - timedelta(days=7)
        
        # Add events at different times
        self.store.record_event(Event(
            user_id="user1",
            event_type=TRADE_BUY,
            timestamp=last_week,
            data={"when": "last_week"}
        ))
        
        self.store.record_event(Event(
            user_id="user1",
            event_type=TRADE_BUY,
            timestamp=yesterday,
            data={"when": "yesterday"}
        ))
        
        self.store.record_event(Event(
            user_id="user1",
            event_type=TRADE_BUY,
            timestamp=now,
            data={"when": "now"}
        ))
        
        # Query last 2 days
        recent = self.store.query_events(
            start_time=now - timedelta(days=2),
            end_time=now
        )
        self.assertEqual(len(recent), 2)
        
        # Query only yesterday
        yesterday_only = self.store.query_events(
            start_time=yesterday - timedelta(hours=1),
            end_time=yesterday + timedelta(hours=1)
        )
        self.assertEqual(len(yesterday_only), 1)
        self.assertEqual(yesterday_only[0].data["when"], "yesterday")
    
    def test_query_with_limit(self):
        """Test limiting query results"""
        # Add 10 events
        for i in range(10):
            self.store.record_event(Event(
                user_id="user1",
                event_type=TRADE_BUY,
                timestamp=datetime.now(),
                data={"index": i}
            ))
        
        # Query with limit
        limited = self.store.query_events(limit=5)
        self.assertEqual(len(limited), 5)
    
    def test_count_events(self):
        """Test counting events"""
        # Add some events
        for i in range(3):
            self.store.record_event(Event(
                user_id="user1",
                event_type=TRADE_BUY,
                timestamp=datetime.now(),
                data={"index": i}
            ))
        
        for i in range(2):
            self.store.record_event(Event(
                user_id="user1",
                event_type=TRADE_SELL,
                timestamp=datetime.now(),
                data={"index": i}
            ))
        
        # Count all for user1
        total = self.store.count_events(user_id="user1")
        self.assertEqual(total, 5)
        
        # Count only buys
        buys = self.store.count_events(user_id="user1", event_type=TRADE_BUY)
        self.assertEqual(buys, 3)
        
        # Count non-existent user
        none = self.store.count_events(user_id="nobody")
        self.assertEqual(none, 0)
    
    def test_complex_query(self):
        """Test complex query with multiple filters"""
        now = datetime.now()
        
        # Add various events
        self.store.record_event(Event(
            user_id="user1",
            event_type=TRADE_BUY,
            timestamp=now - timedelta(days=2),
            data={"token": "OLD"}
        ))
        
        self.store.record_event(Event(
            user_id="user1",
            event_type=TRADE_BUY,
            timestamp=now,
            data={"token": "NEW"}
        ))
        
        self.store.record_event(Event(
            user_id="user2",
            event_type=TRADE_BUY,
            timestamp=now,
            data={"token": "OTHER"}
        ))
        
        # Complex query: user1's buys in last day
        results = self.store.query_events(
            user_id="user1",
            event_types=[TRADE_BUY],
            start_time=now - timedelta(days=1),
            limit=10
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].data["token"], "NEW")


if __name__ == '__main__':
    unittest.main() 