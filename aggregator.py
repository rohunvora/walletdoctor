"""
Event Aggregator - Pure Python calculations for accurate metrics
No LLM math approximations, just reliable computation
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Tuple
from collections import defaultdict
from event_store import Event, EventStore


class EventAggregator:
    """Aggregate events into metrics - let intelligence interpret results"""
    
    def __init__(self, event_store: EventStore):
        self.event_store = event_store
    
    def aggregate(self,
                  events: List[Event],
                  metric_type: str = 'sum',
                  value_field: str = 'amount',
                  group_by: Optional[str] = None) -> Dict[str, Any]:
        """
        Aggregate events with flexible options
        
        metric_type: 'sum', 'count', 'avg', 'min', 'max', 'list'
        value_field: which field in event.data to aggregate
        group_by: field to group results by
        """
        if not events:
            return {}
        
        # Group events if requested
        if group_by:
            groups = defaultdict(list)
            for event in events:
                group_key = event.data.get(group_by, 'unknown')
                groups[group_key].append(event)
            
            # Aggregate each group
            results = {}
            for group_key, group_events in groups.items():
                results[group_key] = self._calculate_metric(
                    group_events, metric_type, value_field
                )
            return results
        else:
            # Single aggregation
            return self._calculate_metric(events, metric_type, value_field)
    
    def _calculate_metric(self,
                          events: List[Event],
                          metric_type: str,
                          value_field: str) -> Any:
        """Calculate a specific metric from events"""
        if metric_type == 'count':
            return len(events)
        
        # Extract values
        values = []
        for event in events:
            value = event.data.get(value_field)
            if value is not None:
                try:
                    values.append(float(value))
                except (ValueError, TypeError):
                    continue
        
        if not values:
            return 0
        
        if metric_type == 'sum':
            return sum(values)
        elif metric_type == 'avg':
            return sum(values) / len(values)
        elif metric_type == 'min':
            return min(values)
        elif metric_type == 'max':
            return max(values)
        elif metric_type == 'list':
            return values
        else:
            return values
    
    def compare_periods(self,
                        user_id: str,
                        event_types: List[str],
                        period1_start: datetime,
                        period1_end: datetime,
                        period2_start: datetime,
                        period2_end: datetime,
                        metric_type: str = 'sum',
                        value_field: str = 'amount') -> Dict[str, Any]:
        """Compare metrics between two time periods"""
        # Get events for both periods
        period1_events = self.event_store.query_events(
            user_id=user_id,
            event_types=event_types,
            start_time=period1_start,
            end_time=period1_end
        )
        
        period2_events = self.event_store.query_events(
            user_id=user_id,
            event_types=event_types,
            start_time=period2_start,
            end_time=period2_end
        )
        
        # Calculate metrics
        period1_value = self._calculate_metric(period1_events, metric_type, value_field)
        period2_value = self._calculate_metric(period2_events, metric_type, value_field)
        
        # Calculate change
        if isinstance(period1_value, (int, float)) and isinstance(period2_value, (int, float)):
            if period1_value != 0:
                change_pct = ((period2_value - period1_value) / abs(period1_value)) * 100
            else:
                change_pct = 100 if period2_value > 0 else -100 if period2_value < 0 else 0
            
            return {
                'period1': {
                    'start': period1_start.isoformat(),
                    'end': period1_end.isoformat(),
                    'value': period1_value
                },
                'period2': {
                    'start': period2_start.isoformat(),
                    'end': period2_end.isoformat(),
                    'value': period2_value
                },
                'change': period2_value - period1_value,
                'change_pct': change_pct
            }
        else:
            return {
                'period1': {
                    'start': period1_start.isoformat(),
                    'end': period1_end.isoformat(),
                    'value': period1_value
                },
                'period2': {
                    'start': period2_start.isoformat(),
                    'end': period2_end.isoformat(),
                    'value': period2_value
                }
            }
    
    def calculate_rate(self,
                       events: List[Event],
                       value_field: str = 'amount',
                       time_unit: str = 'day') -> Dict[str, Any]:
        """Calculate rate of change (e.g., profit per day)"""
        if not events:
            return {'rate': 0, 'total': 0, 'duration': 0, 'unit': time_unit}
        
        # Get time span
        timestamps = [e.timestamp for e in events]
        min_time = min(timestamps)
        max_time = max(timestamps)
        
        # Calculate duration in requested units
        duration_seconds = (max_time - min_time).total_seconds()
        if time_unit == 'hour':
            duration = duration_seconds / 3600
        elif time_unit == 'day':
            duration = duration_seconds / 86400
        elif time_unit == 'week':
            duration = duration_seconds / 604800
        else:
            duration = duration_seconds
        
        # Avoid division by zero
        if duration == 0:
            duration = 1
        
        # Calculate total
        total = self._calculate_metric(events, 'sum', value_field)
        
        return {
            'rate': total / duration if duration > 0 else 0,
            'total': total,
            'duration': duration,
            'unit': time_unit,
            'start': min_time.isoformat(),
            'end': max_time.isoformat()
        }
    
    def calculate_streaks(self,
                          events: List[Event],
                          success_field: str = 'is_win',
                          date_field: str = 'timestamp') -> Dict[str, Any]:
        """Calculate winning/losing streaks"""
        if not events:
            return {
                'current_streak': 0,
                'current_type': None,
                'longest_win_streak': 0,
                'longest_loss_streak': 0
            }
        
        # Sort by timestamp
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        
        current_streak = 0
        current_type = None
        longest_win = 0
        longest_loss = 0
        
        for event in sorted_events:
            is_win = event.data.get(success_field, False)
            
            if current_type is None:
                current_type = 'win' if is_win else 'loss'
                current_streak = 1
            elif (is_win and current_type == 'win') or (not is_win and current_type == 'loss'):
                current_streak += 1
            else:
                # Streak broken
                if current_type == 'win':
                    longest_win = max(longest_win, current_streak)
                else:
                    longest_loss = max(longest_loss, current_streak)
                
                current_type = 'win' if is_win else 'loss'
                current_streak = 1
        
        # Final streak
        if current_type == 'win':
            longest_win = max(longest_win, current_streak)
        else:
            longest_loss = max(longest_loss, current_streak)
        
        return {
            'current_streak': current_streak,
            'current_type': current_type,
            'longest_win_streak': longest_win,
            'longest_loss_streak': longest_loss
        }
    
    def calculate_goal_progress(self,
                                user_id: str,
                                goal_amount: float,
                                goal_period: str = 'daily',
                                value_field: str = 'profit_sol') -> Dict[str, Any]:
        """Calculate progress toward a goal"""
        # Determine time range based on goal period
        now = datetime.now()
        if goal_period == 'daily':
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif goal_period == 'weekly':
            start_time = now - timedelta(days=now.weekday())
            start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        elif goal_period == 'monthly':
            start_time = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            # Custom period, use as-is
            start_time = now - timedelta(days=30)
        
        # Get relevant events
        events = self.event_store.query_events(
            user_id=user_id,
            event_types=['trade_sell'],  # Only completed trades count
            start_time=start_time,
            end_time=now
        )
        
        # Calculate current value
        current_value = self._calculate_metric(events, 'sum', value_field)
        
        # Calculate progress
        progress_pct = (current_value / goal_amount * 100) if goal_amount > 0 else 0
        
        # Calculate rate to see if on track
        rate_info = self.calculate_rate(events, value_field, 'day')
        
        # Estimate completion
        if rate_info['rate'] > 0:
            days_to_complete = (goal_amount - current_value) / rate_info['rate']
        else:
            days_to_complete = float('inf')
        
        return {
            'goal': goal_amount,
            'current': current_value,
            'remaining': goal_amount - current_value,
            'progress_pct': progress_pct,
            'period': goal_period,
            'daily_rate': rate_info['rate'],
            'on_track': progress_pct >= (100 / 7) if goal_period == 'weekly' else progress_pct >= 50,
            'days_to_complete': days_to_complete if days_to_complete != float('inf') else None
        } 