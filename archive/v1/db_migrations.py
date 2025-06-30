"""
Database migrations and annotation functions for the web app
"""
import duckdb
from typing import List, Dict, Any

def run_migrations(db: duckdb.DuckDBPyConnection):
    """Run database migrations to ensure required tables exist"""
    try:
        # Create annotations table if it doesn't exist
        db.execute("""
            CREATE TABLE IF NOT EXISTS annotations (
                id INTEGER PRIMARY KEY,
                wallet_address TEXT,
                symbol TEXT,
                pnl DECIMAL,
                annotation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create any other required tables
        db.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id TEXT PRIMARY KEY,
                wallet_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
    except Exception as e:
        print(f"Migration error: {e}")

def add_annotation(db: duckdb.DuckDBPyConnection, wallet_address: str, symbol: str, pnl: float, annotation: str) -> int:
    """Add an annotation to the database"""
    try:
        result = db.execute("""
            INSERT INTO annotations (wallet_address, symbol, pnl, annotation)
            VALUES (?, ?, ?, ?)
            RETURNING id
        """, [wallet_address, symbol, pnl, annotation]).fetchone()
        
        return result[0] if result else 0
    except Exception as e:
        print(f"Error adding annotation: {e}")
        return 0

def get_similar_annotations(db: duckdb.DuckDBPyConnection, symbol: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Get similar annotations for a symbol"""
    try:
        results = db.execute("""
            SELECT annotation, pnl, created_at
            FROM annotations
            WHERE symbol = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, [symbol, limit]).fetchall()
        
        return [
            {
                'annotation': row[0],
                'pnl': row[1],
                'created_at': row[2]
            }
            for row in results
        ]
    except Exception as e:
        print(f"Error getting similar annotations: {e}")
        return [] 