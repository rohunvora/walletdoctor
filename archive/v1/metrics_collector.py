"""
Metrics Collector - Track conversational interactions for optimization
Feeds data to AI for learning what works
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)

class MetricsCollector:
    """Collects and stores conversation metrics for optimization"""
    
    def __init__(self, db_connection):
        self.db = db_connection
        self._ensure_schema()
    
    def _ensure_schema(self):
        """Ensure metrics tables exist"""
        try:
            # Interaction tracking table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS interaction_metrics (
                    id INTEGER PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    event_type TEXT NOT NULL,
                    pattern_type TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    response_time_seconds REAL,
                    metadata JSON,
                    success BOOLEAN DEFAULT TRUE
                )
            """)
            
            # Performance tracking table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY,
                    date DATE DEFAULT CURRENT_DATE,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    metadata JSON,
                    UNIQUE(date, metric_name)
                )
            """)
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error ensuring metrics schema: {e}")
    
    async def track_interaction(self, event_type: str, metadata: Dict[str, Any]):
        """Track user interaction events"""
        try:
            self.db.execute("""
                INSERT INTO interaction_metrics 
                (user_id, event_type, pattern_type, response_time_seconds, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, [
                metadata.get('user_id'),
                event_type,
                metadata.get('pattern_type'),
                metadata.get('response_time_seconds'),
                json.dumps(metadata)
            ])
            
            self.db.commit()
            logger.debug(f"Tracked {event_type} interaction")
            
        except Exception as e:
            logger.error(f"Error tracking interaction: {e}")
    
    async def calculate_daily_metrics(self, date: datetime = None) -> Dict[str, float]:
        """Calculate daily performance metrics"""
        if date is None:
            date = datetime.now().date()
        
        try:
            # Response rate
            total_questions = self.db.execute("""
                SELECT COUNT(*) FROM interaction_metrics
                WHERE DATE(timestamp) = ? AND event_type = 'question_sent'
            """, [date]).fetchone()[0]
            
            total_responses = self.db.execute("""
                SELECT COUNT(*) FROM interaction_metrics
                WHERE DATE(timestamp) = ? AND event_type = 'response_received'
            """, [date]).fetchone()[0]
            
            response_rate = (total_responses / total_questions) if total_questions > 0 else 0
            
            # Average response time
            avg_response_time = self.db.execute("""
                SELECT AVG(response_time_seconds) FROM interaction_metrics
                WHERE DATE(timestamp) = ? AND event_type = 'response_received'
                AND response_time_seconds IS NOT NULL
            """, [date]).fetchone()[0] or 0
            
            # Button vs free text usage
            button_responses = self.db.execute("""
                SELECT COUNT(*) FROM interaction_metrics
                WHERE DATE(timestamp) = ? AND event_type = 'response_received'
                AND JSON_EXTRACT(metadata, '$.response_type') = 'button'
            """, [date]).fetchone()[0]
            
            freetext_responses = self.db.execute("""
                SELECT COUNT(*) FROM interaction_metrics
                WHERE DATE(timestamp) = ? AND event_type = 'response_received'
                AND JSON_EXTRACT(metadata, '$.response_type') = 'freetext'
            """, [date]).fetchone()[0]
            
            button_usage_rate = (button_responses / total_responses) if total_responses > 0 else 0
            
            # Pattern-specific response rates
            pattern_performance = {}
            patterns = self.db.execute("""
                SELECT 
                    pattern_type,
                    COUNT(CASE WHEN event_type = 'question_sent' THEN 1 END) as questions,
                    COUNT(CASE WHEN event_type = 'response_received' THEN 1 END) as responses
                FROM interaction_metrics
                WHERE DATE(timestamp) = ? AND pattern_type IS NOT NULL
                GROUP BY pattern_type
            """, [date]).fetchall()
            
            for pattern, questions, responses in patterns:
                pattern_performance[f"{pattern}_response_rate"] = (responses / questions) if questions > 0 else 0
            
            metrics = {
                'response_rate': response_rate,
                'avg_response_time_seconds': avg_response_time,
                'button_usage_rate': button_usage_rate,
                'total_questions': total_questions,
                'total_responses': total_responses,
                **pattern_performance
            }
            
            # Store aggregated metrics
            for metric_name, value in metrics.items():
                await self.store_performance_metric(metric_name, value, date)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating daily metrics: {e}")
            return {}
    
    async def store_performance_metric(self, metric_name: str, value: float, 
                                     date: datetime = None, metadata: Dict = None):
        """Store a performance metric"""
        if date is None:
            date = datetime.now().date()
        
        try:
            self.db.execute("""
                INSERT INTO performance_metrics (date, metric_name, metric_value, metadata)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (date, metric_name) 
                DO UPDATE SET metric_value = ?, metadata = ?
            """, [
                date, metric_name, value, json.dumps(metadata or {}),
                value, json.dumps(metadata or {})
            ])
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error storing performance metric: {e}")
    
    async def get_metrics_trend(self, metric_name: str, days: int = 7) -> List[Dict]:
        """Get trend data for a specific metric"""
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            result = self.db.execute("""
                SELECT date, metric_value, metadata
                FROM performance_metrics
                WHERE metric_name = ? AND date BETWEEN ? AND ?
                ORDER BY date DESC
            """, [metric_name, start_date, end_date]).fetchall()
            
            trend_data = []
            for date, value, metadata_json in result:
                trend_data.append({
                    'date': date,
                    'value': value,
                    'metadata': json.loads(metadata_json) if metadata_json else {}
                })
            
            return trend_data
            
        except Exception as e:
            logger.error(f"Error getting metrics trend: {e}")
            return []
    
    async def get_conversation_insights(self, user_id: int = None, days: int = 7) -> Dict:
        """Get insights about conversation patterns"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            query = """
                SELECT 
                    pattern_type,
                    COUNT(CASE WHEN event_type = 'question_sent' THEN 1 END) as questions_sent,
                    COUNT(CASE WHEN event_type = 'response_received' THEN 1 END) as responses_received,
                    AVG(CASE WHEN event_type = 'response_received' THEN response_time_seconds END) as avg_response_time
                FROM interaction_metrics
                WHERE timestamp > ?
            """
            params = [cutoff_date]
            
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            
            query += " GROUP BY pattern_type"
            
            result = self.db.execute(query, params).fetchall()
            
            insights = {
                'patterns': {},
                'overall': {
                    'total_questions': 0,
                    'total_responses': 0,
                    'overall_response_rate': 0
                }
            }
            
            total_questions = total_responses = 0
            
            for pattern, questions, responses, avg_time in result:
                if pattern:  # Skip None patterns
                    insights['patterns'][pattern] = {
                        'questions_sent': questions,
                        'responses_received': responses,
                        'response_rate': (responses / questions) if questions > 0 else 0,
                        'avg_response_time': avg_time or 0
                    }
                    
                    total_questions += questions
                    total_responses += responses
            
            insights['overall']['total_questions'] = total_questions
            insights['overall']['total_responses'] = total_responses
            insights['overall']['overall_response_rate'] = (total_responses / total_questions) if total_questions > 0 else 0
            
            return insights
            
        except Exception as e:
            logger.error(f"Error getting conversation insights: {e}")
            return {}


# Factory function
def create_metrics_collector(db_connection) -> MetricsCollector:
    """Create metrics collector instance"""
    return MetricsCollector(db_connection) 