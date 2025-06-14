#!/usr/bin/env python3
"""
db_migrations.py - Database schema evolution for annotation support

Adds tables for storing user annotations and coaching feedback.
"""

import duckdb
from datetime import datetime
from typing import Optional


def run_migrations(db_connection: duckdb.DuckDBPyConnection):
    """Run all database migrations."""
    
    # Create trade_annotations table
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS trade_annotations (
            annotation_id INTEGER PRIMARY KEY DEFAULT nextval('annotation_seq'),
            token_symbol VARCHAR,
            token_mint VARCHAR,
            trade_pnl DOUBLE,
            user_note TEXT,
            sentiment VARCHAR, -- 'positive', 'negative', 'neutral', 'learning'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            entry_size_usd DOUBLE,
            hold_time_seconds INTEGER
        )
    """)
    
    # Create trade_snapshots table for tracking baseline evolution
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS trade_snapshots (
            snapshot_id INTEGER PRIMARY KEY DEFAULT nextval('snapshot_seq'),
            snapshot_date DATE DEFAULT CURRENT_DATE,
            total_trades INTEGER,
            win_rate DOUBLE,
            avg_pnl DOUBLE,
            total_pnl DOUBLE,
            annotations_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create coaching_history table for tracking insights
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS coaching_history (
            insight_id INTEGER PRIMARY KEY DEFAULT nextval('insight_seq'),
            insight_type VARCHAR, -- 'similar_trade', 'pattern', 'suggestion'
            trade_context TEXT,
            suggestion TEXT,
            user_feedback VARCHAR, -- 'helpful', 'not_helpful', null
            related_trades TEXT, -- JSON array of similar trade IDs
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create new_trades_tracking table for incremental updates
    db_connection.execute("""
        CREATE TABLE IF NOT EXISTS new_trades_tracking (
            tracking_id INTEGER PRIMARY KEY DEFAULT nextval('tracking_seq'),
            last_signature VARCHAR,
            last_check_timestamp TIMESTAMP,
            trades_since_last_check INTEGER DEFAULT 0
        )
    """)
    
    # Create sequences if they don't exist
    try:
        db_connection.execute("CREATE SEQUENCE IF NOT EXISTS annotation_seq")
        db_connection.execute("CREATE SEQUENCE IF NOT EXISTS snapshot_seq")
        db_connection.execute("CREATE SEQUENCE IF NOT EXISTS insight_seq")
        db_connection.execute("CREATE SEQUENCE IF NOT EXISTS tracking_seq")
    except:
        pass  # Sequences might already exist
    
    print("✅ Database migrations completed successfully")


def add_annotation(
    db_connection: duckdb.DuckDBPyConnection,
    token_symbol: str,
    token_mint: str,
    trade_pnl: float,
    user_note: str,
    sentiment: Optional[str] = None,
    entry_size_usd: Optional[float] = None,
    hold_time_seconds: Optional[int] = None
) -> int:
    """Add a new trade annotation."""
    
    # Auto-detect sentiment if not provided
    if not sentiment:
        if trade_pnl > 0:
            sentiment = 'positive' if 'good' in user_note.lower() or 'great' in user_note.lower() else 'learning'
        else:
            sentiment = 'negative' if 'bad' in user_note.lower() or 'mistake' in user_note.lower() else 'learning'
    
    result = db_connection.execute("""
        INSERT INTO trade_annotations 
        (token_symbol, token_mint, trade_pnl, user_note, sentiment, entry_size_usd, hold_time_seconds)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        RETURNING annotation_id
    """, [token_symbol, token_mint, trade_pnl, user_note, sentiment, entry_size_usd, hold_time_seconds])
    
    return result.fetchone()[0]


def get_similar_annotations(
    db_connection: duckdb.DuckDBPyConnection,
    token_symbol: str = None,
    entry_size_usd: float = None,
    size_tolerance: float = 0.5
) -> list:
    """Find similar trade annotations based on token or size."""
    
    conditions = []
    params = []
    
    if token_symbol:
        conditions.append("token_symbol = ?")
        params.append(token_symbol)
    
    if entry_size_usd:
        # Find trades within size tolerance (e.g., 50% range)
        min_size = entry_size_usd * (1 - size_tolerance)
        max_size = entry_size_usd * (1 + size_tolerance)
        conditions.append("entry_size_usd BETWEEN ? AND ?")
        params.extend([min_size, max_size])
    
    if not conditions:
        return []
    
    query = f"""
        SELECT 
            token_symbol,
            trade_pnl,
            user_note,
            sentiment,
            entry_size_usd,
            hold_time_seconds,
            created_at
        FROM trade_annotations
        WHERE {' AND '.join(conditions)}
        ORDER BY created_at DESC
        LIMIT 10
    """
    
    result = db_connection.execute(query, params)
    return result.fetchall()


def save_snapshot(db_connection: duckdb.DuckDBPyConnection):
    """Save current performance snapshot."""
    
    # Get current stats
    pnl_df = db_connection.execute("SELECT * FROM pnl").df()
    if pnl_df.empty:
        return
    
    total_trades = len(pnl_df)
    winners = len(pnl_df[pnl_df['realizedPnl'] > 0])
    win_rate = (winners / total_trades * 100) if total_trades > 0 else 0
    avg_pnl = pnl_df['realizedPnl'].mean()
    total_pnl = pnl_df['realizedPnl'].sum()
    
    # Count annotations
    annotations_count = db_connection.execute(
        "SELECT COUNT(*) FROM trade_annotations"
    ).fetchone()[0]
    
    # Insert snapshot
    db_connection.execute("""
        INSERT INTO trade_snapshots 
        (total_trades, win_rate, avg_pnl, total_pnl, annotations_count)
        VALUES (?, ?, ?, ?, ?)
    """, [total_trades, win_rate, avg_pnl, total_pnl, annotations_count])


if __name__ == "__main__":
    # Test migrations
    db = duckdb.connect("coach.db")
    run_migrations(db)
    
    # Test annotation
    annotation_id = add_annotation(
        db,
        token_symbol="BONK",
        token_mint="DezXAZ...",
        trade_pnl=-150.50,
        user_note="FOMO'd into the pump, should have waited for pullback",
        entry_size_usd=500
    )
    print(f"Created annotation {annotation_id}")
    
    # Test finding similar
    similar = get_similar_annotations(db, entry_size_usd=500)
    print(f"Found {len(similar)} similar trades") 