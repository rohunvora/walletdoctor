#!/usr/bin/env python3
"""
Startup script for Railway deployment
Runs database migrations and initialization before starting the web server
"""

import os
import sys
import duckdb

# Add scripts directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

from db_migrations import run_migrations

def initialize_app():
    """Initialize the application on startup."""
    print("🚀 Starting WalletDoctor MVP initialization...")
    
    # Ensure required environment variables are set
    required_vars = ['HELIUS_KEY', 'CIELO_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"⚠️  Warning: Missing environment variables: {', '.join(missing_vars)}")
        print("   The app will start but API calls will fail without these keys.")
    
    # Initialize database and run migrations
    print("📊 Initializing database...")
    try:
        db = duckdb.connect("coach.db")
        
        # Drop existing tables to fix schema issues
        print("🔄 Dropping old tables to fix schema...")
        try:
            db.execute("DROP TABLE IF EXISTS tx")
            db.execute("DROP TABLE IF EXISTS pnl")
            db.execute("DROP TABLE IF EXISTS trade_annotations")
            db.execute("DROP TABLE IF EXISTS trade_snapshots")
            db.execute("DROP TABLE IF EXISTS coaching_history")
            db.execute("DROP TABLE IF EXISTS new_trades_tracking")
            db.execute("DROP SEQUENCE IF EXISTS annotation_seq")
            db.execute("DROP SEQUENCE IF EXISTS snapshot_seq")
            db.execute("DROP SEQUENCE IF EXISTS insight_seq")
            db.execute("DROP SEQUENCE IF EXISTS tracking_seq")
        except:
            pass  # Tables might not exist
        
        # Close and reopen to ensure clean state
        db.close()
        db = duckdb.connect("coach.db")
        
        # Run migrations
        print("🔄 Running database migrations...")
        run_migrations(db)
        
        print("✅ Database initialized successfully!")
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        # Don't exit - let the app start anyway
    
    # Create templates directory if it doesn't exist
    os.makedirs('templates_v2', exist_ok=True)
    
    print("✨ Initialization complete! Starting web server...")

if __name__ == "__main__":
    initialize_app() 