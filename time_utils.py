"""
Time Utilities - Natural language date parsing without rigid assumptions
Flexible time handling for human-friendly queries
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import re


def parse_time_string(time_str: str, reference_time: Optional[datetime] = None) -> Optional[datetime]:
    """
    Parse natural language time strings
    Examples: "today", "yesterday", "last week", "3 days ago", "jan 15"
    """
    if reference_time is None:
        reference_time = datetime.now()
    
    time_str = time_str.lower().strip()
    
    # Exact matches
    if time_str in ['now', 'right now']:
        return reference_time
    
    if time_str == 'today':
        return reference_time.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if time_str == 'yesterday':
        return (reference_time - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    if time_str == 'tomorrow':
        return (reference_time + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # This/last period
    if time_str == 'this week':
        days_since_monday = reference_time.weekday()
        return (reference_time - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    if time_str == 'last week':
        days_since_monday = reference_time.weekday()
        start_of_this_week = reference_time - timedelta(days=days_since_monday)
        return (start_of_this_week - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    if time_str == 'this month':
        return reference_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    if time_str == 'last month':
        first_of_month = reference_time.replace(day=1)
        last_month = first_of_month - timedelta(days=1)
        return last_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # N units ago pattern
    ago_pattern = r'(\d+)\s+(second|minute|hour|day|week|month)s?\s+ago'
    match = re.match(ago_pattern, time_str)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        
        if unit == 'second':
            return reference_time - timedelta(seconds=amount)
        elif unit == 'minute':
            return reference_time - timedelta(minutes=amount)
        elif unit == 'hour':
            return reference_time - timedelta(hours=amount)
        elif unit == 'day':
            return reference_time - timedelta(days=amount)
        elif unit == 'week':
            return reference_time - timedelta(weeks=amount)
        elif unit == 'month':
            # Approximate - 30 days
            return reference_time - timedelta(days=amount * 30)
    
    # Last N units pattern
    last_pattern = r'last\s+(\d+)\s+(second|minute|hour|day|week|month)s?'
    match = re.match(last_pattern, time_str)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        
        if unit == 'second':
            return reference_time - timedelta(seconds=amount)
        elif unit == 'minute':
            return reference_time - timedelta(minutes=amount)
        elif unit == 'hour':
            return reference_time - timedelta(hours=amount)
        elif unit == 'day':
            return reference_time - timedelta(days=amount)
        elif unit == 'week':
            return reference_time - timedelta(weeks=amount)
        elif unit == 'month':
            # Approximate - 30 days
            return reference_time - timedelta(days=amount * 30)
    
    # Try parsing as date
    date_formats = [
        '%Y-%m-%d',
        '%m/%d/%Y',
        '%m-%d-%Y',
        '%d/%m/%Y',
        '%d-%m-%Y',
        '%b %d',
        '%B %d',
        '%b %d, %Y',
        '%B %d, %Y'
    ]
    
    for fmt in date_formats:
        try:
            parsed = datetime.strptime(time_str, fmt)
            # If no year, assume current year
            if '%Y' not in fmt:
                parsed = parsed.replace(year=reference_time.year)
            return parsed
        except ValueError:
            continue
    
    return None


def get_period_bounds(period: str, reference_time: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """
    Get start and end times for common periods
    Returns (start, end) tuple
    """
    if reference_time is None:
        reference_time = datetime.now()
    
    period = period.lower().strip()
    
    if period == 'today':
        start = reference_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end = reference_time
        return (start, end)
    
    if period == 'yesterday':
        yesterday = reference_time - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1) - timedelta(microseconds=1)
        return (start, end)
    
    if period == 'this week':
        days_since_monday = reference_time.weekday()
        start = (reference_time - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = reference_time
        return (start, end)
    
    if period == 'last week':
        days_since_monday = reference_time.weekday()
        this_monday = (reference_time - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        start = this_monday - timedelta(days=7)
        end = this_monday - timedelta(microseconds=1)
        return (start, end)
    
    if period == 'this month':
        start = reference_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = reference_time
        return (start, end)
    
    if period == 'last month':
        first_of_month = reference_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = first_of_month - timedelta(microseconds=1)
        start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return (start, end)
    
    if period == 'this year':
        start = reference_time.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = reference_time
        return (start, end)
    
    if period == 'last year':
        this_year_start = reference_time.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = this_year_start - timedelta(microseconds=1)
        start = end.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return (start, end)
    
    # Last N days/hours pattern
    match = re.match(r'last\s+(\d+)\s+(hour|day|week|month)s?', period)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        
        end = reference_time
        if unit == 'hour':
            start = reference_time - timedelta(hours=amount)
        elif unit == 'day':
            start = reference_time - timedelta(days=amount)
        elif unit == 'week':
            start = reference_time - timedelta(weeks=amount)
        elif unit == 'month':
            start = reference_time - timedelta(days=amount * 30)
        else:
            start = reference_time
        
        return (start, end)
    
    # Default to today
    return get_period_bounds('today', reference_time)


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form"""
    if seconds < 60:
        return f"{int(seconds)} seconds"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''}"
    else:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''}"


def is_business_hours(dt: datetime, start_hour: int = 9, end_hour: int = 17) -> bool:
    """Check if datetime is within business hours"""
    return start_hour <= dt.hour < end_hour and dt.weekday() < 5  # Monday-Friday 