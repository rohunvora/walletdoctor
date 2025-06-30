"""
Unit tests for event aggregator - testing Python calculations
"""
import unittest
import tempfile
import os
from datetime import datetime, timedelta
from event_store import Event, EventStore, TRADE_BUY, TRADE_SELL
from aggregator import EventAggregator


class TestEventAggregator(unittest.TestCase):
    """Test the EventAggregator class"""
    
    def setUp(self):
        """Create temporary database and aggregator for each test"""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_file.close()
        self.store = EventStore(self.temp_file.name)
        self.aggregator = EventAggregator(self.store)
    
    def tearDown(self):
        """Clean up temporary database"""
        os.unlink(self.temp_file.name)
    
    def test_aggregate_sum(self):
        """Test sum aggregation"""
        events = [
            Event(user_id="user1", event_type=TRADE_SELL, timestamp=datetime.now(), 
                  data={"profit_sol": 1.5}),
            Event(user_id="user1", event_type=TRADE_SELL, timestamp=datetime.now(), 
                  data={"profit_sol": 2.5}),
            Event(user_id="user1", event_type=TRADE_SELL, timestamp=datetime.now(), 
                  data={"profit_sol": -1.0})
        ]
        
        result = self.aggregator.aggregate(events, metric_type='sum', value_field='profit_sol')
        self.assertEqual(result, 3.0)  # 1.5 + 2.5 - 1.0
    
    def test_aggregate_count(self):
        """Test count aggregation"""
        events = [
            Event(user_id="user1", event_type=TRADE_BUY, timestamp=datetime.now(), data={}),
            Event(user_id="user1", event_type=TRADE_BUY, timestamp=datetime.now(), data={}),
            Event(user_id="user1", event_type=TRADE_BUY, timestamp=datetime.now(), data={})
        ]
        
        result = self.aggregator.aggregate(events, metric_type='count')
        self.assertEqual(result, 3)
    
    def test_aggregate_avg(self):
        """Test average aggregation"""
        events = [
            Event(user_id="user1", event_type=TRADE_SELL, timestamp=datetime.now(), 
                  data={"profit_sol": 1.0}),
            Event(user_id="user1", event_type=TRADE_SELL, timestamp=datetime.now(), 
                  data={"profit_sol": 2.0}),
            Event(user_id="user1", event_type=TRADE_SELL, timestamp=datetime.now(), 
                  data={"profit_sol": 3.0})
        ]
        
        result = self.aggregator.aggregate(events, metric_type='avg', value_field='profit_sol')
        self.assertEqual(result, 2.0)  # (1.0 + 2.0 + 3.0) / 3
    
    def test_aggregate_min_max(self):
        """Test min/max aggregation"""
        events = [
            Event(user_id="user1", event_type=TRADE_SELL, timestamp=datetime.now(), 
                  data={"profit_sol": -5.0}),
            Event(user_id="user1", event_type=TRADE_SELL, timestamp=datetime.now(), 
                  data={"profit_sol": 10.0}),
            Event(user_id="user1", event_type=TRADE_SELL, timestamp=datetime.now(), 
                  data={"profit_sol": 2.0})
        ]
        
        min_result = self.aggregator.aggregate(events, metric_type='min', value_field='profit_sol')
        self.assertEqual(min_result, -5.0)
        
        max_result = self.aggregator.aggregate(events, metric_type='max', value_field='profit_sol')
        self.assertEqual(max_result, 10.0)
    
    def test_aggregate_group_by(self):
        """Test group by aggregation"""
        events = [
            Event(user_id="user1", event_type=TRADE_SELL, timestamp=datetime.now(), 
                  data={"token": "BONK", "profit_sol": 1.0}),
            Event(user_id="user1", event_type=TRADE_SELL, timestamp=datetime.now(), 
                  data={"token": "BONK", "profit_sol": 2.0}),
            Event(user_id="user1", event_type=TRADE_SELL, timestamp=datetime.now(), 
                  data={"token": "WIF", "profit_sol": 3.0})
        ]
        
        result = self.aggregator.aggregate(events, metric_type='sum', 
                                           value_field='profit_sol', group_by='token')
        
        self.assertEqual(result['BONK'], 3.0)  # 1.0 + 2.0
        self.assertEqual(result['WIF'], 3.0)   # 3.0
    
    def test_compare_periods(self):
        """Test comparing metrics between periods"""
        now = datetime.now()
        
        # Add trades for this week
        for i in range(3):
            self.store.record_event(Event(
                user_id="user1",
                event_type=TRADE_SELL,
                timestamp=now - timedelta(days=i),
                data={"profit_sol": 1.0}
            ))
        
        # Add trades for last week
        for i in range(2):
            self.store.record_event(Event(
                user_id="user1",
                event_type=TRADE_SELL,
                timestamp=now - timedelta(days=8+i),  # Changed from 7+i to 8+i to avoid overlap
                data={"profit_sol": 2.0}
            ))
        
        # Compare this week vs last week
        result = self.aggregator.compare_periods(
            user_id="user1",
            event_types=[TRADE_SELL],
            period1_start=now - timedelta(days=14),
            period1_end=now - timedelta(days=7, seconds=1),  # End just before 7 days ago
            period2_start=now - timedelta(days=7),
            period2_end=now,
            metric_type='sum',
            value_field='profit_sol'
        )
        
        self.assertEqual(result['period1']['value'], 4.0)  # 2 trades x 2.0
        self.assertEqual(result['period2']['value'], 3.0)  # 3 trades x 1.0
        self.assertEqual(result['change'], -1.0)
        self.assertEqual(result['change_pct'], -25.0)
    
    def test_calculate_rate(self):
        """Test rate calculation"""
        now = datetime.now()
        events = []
        
        # Add trades over 5 days
        for i in range(5):
            events.append(Event(
                user_id="user1",
                event_type=TRADE_SELL,
                timestamp=now - timedelta(days=i),
                data={"profit_sol": 2.0}
            ))
        
        # Calculate daily rate
        result = self.aggregator.calculate_rate(events, value_field='profit_sol', time_unit='day')
        
        self.assertEqual(result['total'], 10.0)  # 5 trades x 2.0
        self.assertEqual(result['duration'], 4.0)  # 4 days between first and last
        self.assertEqual(result['rate'], 2.5)  # 10.0 / 4 days
        self.assertEqual(result['unit'], 'day')
    
    def test_calculate_streaks(self):
        """Test streak calculation"""
        events = [
            Event(user_id="user1", event_type=TRADE_SELL, 
                  timestamp=datetime.now() - timedelta(days=5),
                  data={"is_win": True}),
            Event(user_id="user1", event_type=TRADE_SELL, 
                  timestamp=datetime.now() - timedelta(days=4),
                  data={"is_win": True}),
            Event(user_id="user1", event_type=TRADE_SELL, 
                  timestamp=datetime.now() - timedelta(days=3),
                  data={"is_win": False}),
            Event(user_id="user1", event_type=TRADE_SELL, 
                  timestamp=datetime.now() - timedelta(days=2),
                  data={"is_win": False}),
            Event(user_id="user1", event_type=TRADE_SELL, 
                  timestamp=datetime.now() - timedelta(days=1),
                  data={"is_win": False}),
        ]
        
        result = self.aggregator.calculate_streaks(events, success_field='is_win')
        
        self.assertEqual(result['current_streak'], 3)
        self.assertEqual(result['current_type'], 'loss')
        self.assertEqual(result['longest_win_streak'], 2)
        self.assertEqual(result['longest_loss_streak'], 3)
    
    def test_calculate_goal_progress(self):
        """Test goal progress calculation"""
        now = datetime.now()
        
        # Add today's trades
        for i in range(3):
            self.store.record_event(Event(
                user_id="user1",
                event_type=TRADE_SELL,
                timestamp=now - timedelta(hours=i),
                data={"profit_sol": 10.0}
            ))
        
        # Calculate progress toward daily goal of 50 SOL
        result = self.aggregator.calculate_goal_progress(
            user_id="user1",
            goal_amount=50.0,
            goal_period='daily',
            value_field='profit_sol'
        )
        
        self.assertEqual(result['goal'], 50.0)
        self.assertEqual(result['current'], 30.0)  # 3 trades x 10.0
        self.assertEqual(result['remaining'], 20.0)
        self.assertEqual(result['progress_pct'], 60.0)
        self.assertEqual(result['period'], 'daily')
        self.assertTrue(result['on_track'])  # > 50% for daily goal
    
    def test_empty_events(self):
        """Test aggregations with empty event lists"""
        empty_events = []
        
        # Test various aggregations
        self.assertEqual(self.aggregator.aggregate(empty_events, 'sum'), {})
        self.assertEqual(self.aggregator.aggregate(empty_events, 'count'), {})
        
        # Test rate with empty events
        rate_result = self.aggregator.calculate_rate(empty_events)
        self.assertEqual(rate_result['rate'], 0)
        self.assertEqual(rate_result['total'], 0)
        
        # Test streaks with empty events
        streak_result = self.aggregator.calculate_streaks(empty_events)
        self.assertEqual(streak_result['current_streak'], 0)
        self.assertIsNone(streak_result['current_type'])
    
    def test_mixed_data_types(self):
        """Test handling of mixed data types in aggregation"""
        events = [
            Event(user_id="user1", event_type=TRADE_SELL, timestamp=datetime.now(), 
                  data={"profit_sol": "1.5"}),  # String that can convert
            Event(user_id="user1", event_type=TRADE_SELL, timestamp=datetime.now(), 
                  data={"profit_sol": 2.5}),     # Float
            Event(user_id="user1", event_type=TRADE_SELL, timestamp=datetime.now(), 
                  data={"profit_sol": "invalid"}) # Invalid string
        ]
        
        # Should handle conversion and skip invalid
        result = self.aggregator.aggregate(events, metric_type='sum', value_field='profit_sol')
        self.assertEqual(result, 4.0)  # 1.5 + 2.5, skipping "invalid"


if __name__ == '__main__':
    unittest.main() 