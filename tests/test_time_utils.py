"""
Unit tests for time utilities - testing natural language parsing
"""
import unittest
from datetime import datetime, timedelta
from time_utils import parse_time_string, get_period_bounds, format_duration, is_business_hours


class TestParseTimeString(unittest.TestCase):
    """Test natural language time parsing"""
    
    def setUp(self):
        """Set up reference time for consistent testing"""
        # Use a Monday at 2pm for predictable weekday calculations
        self.reference = datetime(2024, 1, 15, 14, 0, 0)  # Monday, Jan 15, 2024, 2pm
    
    def test_exact_matches(self):
        """Test exact string matches"""
        # Now
        result = parse_time_string("now", self.reference)
        self.assertEqual(result, self.reference)
        
        # Today
        result = parse_time_string("today", self.reference)
        expected = self.reference.replace(hour=0, minute=0, second=0, microsecond=0)
        self.assertEqual(result, expected)
        
        # Yesterday
        result = parse_time_string("yesterday", self.reference)
        expected = (self.reference - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        self.assertEqual(result, expected)
        
        # Tomorrow
        result = parse_time_string("tomorrow", self.reference)
        expected = (self.reference + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        self.assertEqual(result, expected)
    
    def test_week_periods(self):
        """Test week-based periods"""
        # This week (should be Monday)
        result = parse_time_string("this week", self.reference)
        expected = self.reference.replace(hour=0, minute=0, second=0, microsecond=0)  # Monday
        self.assertEqual(result, expected)
        
        # Last week (previous Monday)
        result = parse_time_string("last week", self.reference)
        expected = (self.reference - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
        self.assertEqual(result, expected)
    
    def test_month_periods(self):
        """Test month-based periods"""
        # This month
        result = parse_time_string("this month", self.reference)
        expected = self.reference.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        self.assertEqual(result, expected)
        
        # Last month
        result = parse_time_string("last month", self.reference)
        expected = datetime(2023, 12, 1, 0, 0, 0)  # Dec 1, 2023
        self.assertEqual(result, expected)
    
    def test_ago_pattern(self):
        """Test 'N units ago' pattern"""
        # 3 days ago
        result = parse_time_string("3 days ago", self.reference)
        expected = self.reference - timedelta(days=3)
        self.assertEqual(result, expected)
        
        # 2 hours ago
        result = parse_time_string("2 hours ago", self.reference)
        expected = self.reference - timedelta(hours=2)
        self.assertEqual(result, expected)
        
        # 1 week ago
        result = parse_time_string("1 week ago", self.reference)
        expected = self.reference - timedelta(weeks=1)
        self.assertEqual(result, expected)
    
    def test_last_n_pattern(self):
        """Test 'last N units' pattern"""
        # Last 5 days
        result = parse_time_string("last 5 days", self.reference)
        expected = self.reference - timedelta(days=5)
        self.assertEqual(result, expected)
        
        # Last 24 hours
        result = parse_time_string("last 24 hours", self.reference)
        expected = self.reference - timedelta(hours=24)
        self.assertEqual(result, expected)
    
    def test_date_parsing(self):
        """Test various date formats"""
        # ISO format
        result = parse_time_string("2024-01-10", self.reference)
        expected = datetime(2024, 1, 10, 0, 0, 0)
        self.assertEqual(result, expected)
        
        # US format
        result = parse_time_string("01/10/2024", self.reference)
        expected = datetime(2024, 1, 10, 0, 0, 0)
        self.assertEqual(result, expected)
        
        # Month day (assumes current year)
        result = parse_time_string("Jan 10", self.reference)
        expected = datetime(2024, 1, 10, 0, 0, 0)
        self.assertEqual(result, expected)
    
    def test_invalid_input(self):
        """Test invalid input returns None"""
        result = parse_time_string("invalid time string", self.reference)
        self.assertIsNone(result)
        
        result = parse_time_string("", self.reference)
        self.assertIsNone(result)


class TestGetPeriodBounds(unittest.TestCase):
    """Test period boundary calculations"""
    
    def setUp(self):
        """Set up reference time"""
        # Monday, Jan 15, 2024, 2:30pm
        self.reference = datetime(2024, 1, 15, 14, 30, 0)
    
    def test_today_bounds(self):
        """Test today's bounds"""
        start, end = get_period_bounds("today", self.reference)
        
        expected_start = self.reference.replace(hour=0, minute=0, second=0, microsecond=0)
        self.assertEqual(start, expected_start)
        self.assertEqual(end, self.reference)
    
    def test_yesterday_bounds(self):
        """Test yesterday's bounds"""
        start, end = get_period_bounds("yesterday", self.reference)
        
        expected_start = (self.reference - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        expected_end = expected_start + timedelta(days=1) - timedelta(microseconds=1)
        
        self.assertEqual(start, expected_start)
        self.assertEqual(end, expected_end)
    
    def test_this_week_bounds(self):
        """Test this week's bounds"""
        start, end = get_period_bounds("this week", self.reference)
        
        # Should start on Monday
        expected_start = self.reference.replace(hour=0, minute=0, second=0, microsecond=0)
        self.assertEqual(start, expected_start)
        self.assertEqual(end, self.reference)
    
    def test_last_week_bounds(self):
        """Test last week's bounds"""
        start, end = get_period_bounds("last week", self.reference)
        
        # Previous Monday to Sunday
        this_monday = self.reference.replace(hour=0, minute=0, second=0, microsecond=0)
        expected_start = this_monday - timedelta(days=7)
        expected_end = this_monday - timedelta(microseconds=1)
        
        self.assertEqual(start, expected_start)
        self.assertEqual(end, expected_end)
    
    def test_this_month_bounds(self):
        """Test this month's bounds"""
        start, end = get_period_bounds("this month", self.reference)
        
        expected_start = self.reference.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        self.assertEqual(start, expected_start)
        self.assertEqual(end, self.reference)
    
    def test_last_n_days_pattern(self):
        """Test 'last N days' pattern"""
        start, end = get_period_bounds("last 7 days", self.reference)
        
        expected_start = self.reference - timedelta(days=7)
        self.assertEqual(start, expected_start)
        self.assertEqual(end, self.reference)
    
    def test_default_bounds(self):
        """Test default bounds for unrecognized period"""
        start, end = get_period_bounds("unrecognized period", self.reference)
        
        # Should default to today
        expected_start = self.reference.replace(hour=0, minute=0, second=0, microsecond=0)
        self.assertEqual(start, expected_start)
        self.assertEqual(end, self.reference)


class TestFormatDuration(unittest.TestCase):
    """Test duration formatting"""
    
    def test_seconds(self):
        """Test formatting seconds"""
        self.assertEqual(format_duration(45), "45 seconds")
        self.assertEqual(format_duration(1), "1 seconds")  # Note: not handling singular
    
    def test_minutes(self):
        """Test formatting minutes"""
        self.assertEqual(format_duration(120), "2 minutes")
        self.assertEqual(format_duration(60), "1 minute")
        self.assertEqual(format_duration(90), "1 minute")  # Rounds down
    
    def test_hours(self):
        """Test formatting hours"""
        self.assertEqual(format_duration(3600), "1 hour")
        self.assertEqual(format_duration(7200), "2 hours")
        self.assertEqual(format_duration(5400), "1 hour")  # 1.5 hours rounds down
    
    def test_days(self):
        """Test formatting days"""
        self.assertEqual(format_duration(86400), "1 day")
        self.assertEqual(format_duration(172800), "2 days")


class TestBusinessHours(unittest.TestCase):
    """Test business hours checking"""
    
    def test_during_business_hours(self):
        """Test times during business hours"""
        # Monday at 10am
        dt = datetime(2024, 1, 15, 10, 0, 0)
        self.assertTrue(is_business_hours(dt))
        
        # Friday at 4pm
        dt = datetime(2024, 1, 19, 16, 0, 0)
        self.assertTrue(is_business_hours(dt))
    
    def test_outside_business_hours(self):
        """Test times outside business hours"""
        # Monday at 8am (before 9am)
        dt = datetime(2024, 1, 15, 8, 0, 0)
        self.assertFalse(is_business_hours(dt))
        
        # Monday at 6pm (after 5pm)
        dt = datetime(2024, 1, 15, 18, 0, 0)
        self.assertFalse(is_business_hours(dt))
        
        # Saturday
        dt = datetime(2024, 1, 20, 10, 0, 0)
        self.assertFalse(is_business_hours(dt))
        
        # Sunday
        dt = datetime(2024, 1, 21, 10, 0, 0)
        self.assertFalse(is_business_hours(dt))
    
    def test_custom_hours(self):
        """Test custom business hours"""
        dt = datetime(2024, 1, 15, 7, 0, 0)  # Monday 7am
        
        # Custom hours 6am-2pm
        self.assertTrue(is_business_hours(dt, start_hour=6, end_hour=14))
        
        # Default hours would be false
        self.assertFalse(is_business_hours(dt))


if __name__ == '__main__':
    unittest.main() 