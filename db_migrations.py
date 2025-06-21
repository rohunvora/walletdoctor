#!/usr/bin/env python3
"""
Database migrations for goal-oriented adaptive coach
Run this to add user_goals and user_facts tables
"""

import duckdb
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migrations(db_path: str = "pocket_coach.db"):
    """Run database migrations for goal-oriented features"""
    db = duckdb.connect(db_path)
    
    try:
        # Create user_goals table
        logger.info("Creating user_goals table...")
        db.execute("""
            CREATE TABLE IF NOT EXISTS user_goals (
                user_id INTEGER PRIMARY KEY,
                goal_json TEXT NOT NULL, -- Store as JSON for flexibility
                raw_statement TEXT,
                confirmed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create user_facts table  
        logger.info("Creating user_facts table...")
        db.execute("""
            CREATE TABLE IF NOT EXISTS user_facts (
                user_id INTEGER NOT NULL,
                fact_key TEXT NOT NULL,
                fact_value TEXT NOT NULL,
                context TEXT, -- where/when mentioned
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                usage_count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, fact_key)
            )
        """)
        
        # Create indexes for efficient queries
        logger.info("Creating indexes...")
        db.execute("CREATE INDEX IF NOT EXISTS idx_facts_user ON user_facts(user_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_facts_timestamp ON user_facts(timestamp)")
        
        # Verify tables were created
        tables = db.execute("SHOW TABLES").fetchall()
        logger.info(f"Current tables: {[t[0] for t in tables]}")
        
        # Check user_goals schema
        goals_schema = db.execute("DESCRIBE user_goals").fetchall()
        logger.info("user_goals schema:")
        for col in goals_schema:
            logger.info(f"  {col}")
            
        # Check user_facts schema
        facts_schema = db.execute("DESCRIBE user_facts").fetchall()
        logger.info("user_facts schema:")
        for col in facts_schema:
            logger.info(f"  {col}")
        
        # Create events table for analytics
        logger.info("Creating events table...")
        db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for common query patterns
        logger.info("Creating events indexes...")
        db.execute("CREATE INDEX IF NOT EXISTS idx_events_user_timestamp ON events(user_id, timestamp)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_events_type_timestamp ON events(event_type, timestamp)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)")
        
        # Check events schema
        events_schema = db.execute("DESCRIBE events").fetchall()
        logger.info("events schema:")
        for col in events_schema:
            logger.info(f"  {col}")
        
        logger.info("✅ Database migrations completed successfully")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run_migrations() 