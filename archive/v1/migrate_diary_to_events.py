#!/usr/bin/env python3
"""
Migration script - Convert historical diary entries to events
Safe, resumable migration with validation
"""

import json
import duckdb
import sqlite3
from datetime import datetime, timedelta
from typing import Optional
from event_store import Event, EventStore, TRADE_BUY, TRADE_SELL


class DiaryToEventMigration:
    """Migrate diary entries to event store"""
    
    def __init__(self, diary_db: str = "pocket_coach.db", event_db: str = "events.db"):
        self.diary_db = diary_db
        self.event_store = EventStore(event_db)
        self.stats = {
            'total_entries': 0,
            'migrated': 0,
            'skipped': 0,
            'errors': 0
        }
    
    def get_migration_checkpoint(self) -> Optional[str]:
        """Get last migrated timestamp to resume from"""
        conn = sqlite3.connect(self.event_store.db_path)
        try:
            # Check if we have a migration checkpoint table
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='migration_checkpoint'
            """)
            
            if not cursor.fetchone():
                # Create checkpoint table
                conn.execute("""
                    CREATE TABLE migration_checkpoint (
                        id INTEGER PRIMARY KEY,
                        last_timestamp TEXT,
                        entries_migrated INTEGER,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                return None
            
            # Get last checkpoint
            cursor = conn.execute("""
                SELECT last_timestamp FROM migration_checkpoint
                ORDER BY id DESC LIMIT 1
            """)
            result = cursor.fetchone()
            return result[0] if result else None
            
        finally:
            conn.close()
    
    def save_checkpoint(self, last_timestamp: str):
        """Save migration progress"""
        conn = sqlite3.connect(self.event_store.db_path)
        try:
            conn.execute("""
                INSERT INTO migration_checkpoint (last_timestamp, entries_migrated)
                VALUES (?, ?)
            """, [last_timestamp, self.stats['migrated']])
            conn.commit()
        finally:
            conn.close()
    
    def migrate_trades(self, batch_size: int = 1000) -> int:
        """Migrate trade entries from diary to events"""
        db = duckdb.connect(self.diary_db)
        
        # Get last checkpoint
        last_timestamp = self.get_migration_checkpoint()
        
        print(f"Starting migration from checkpoint: {last_timestamp or 'beginning'}")
        
        try:
            # Count total entries to migrate
            if last_timestamp:
                count_result = db.execute("""
                    SELECT COUNT(*) FROM diary 
                    WHERE entry_type = 'trade' 
                    AND timestamp > ?
                """, [last_timestamp]).fetchone()
            else:
                count_result = db.execute("""
                    SELECT COUNT(*) FROM diary 
                    WHERE entry_type = 'trade'
                """).fetchone()
            
            total_to_migrate = count_result[0] if count_result else 0
            print(f"Found {total_to_migrate:,} trades to migrate")
            
            # Process in batches
            offset = 0
            last_processed_timestamp = last_timestamp
            
            while True:
                # Fetch batch
                if last_timestamp:
                    batch = db.execute("""
                        SELECT wallet_address, data, timestamp 
                        FROM diary 
                        WHERE entry_type = 'trade'
                        AND timestamp > ?
                        ORDER BY timestamp ASC
                        LIMIT ?
                    """, [last_timestamp, batch_size]).fetchall()
                else:
                    batch = db.execute("""
                        SELECT wallet_address, data, timestamp 
                        FROM diary 
                        WHERE entry_type = 'trade'
                        ORDER BY timestamp ASC
                        LIMIT ? OFFSET ?
                    """, [batch_size, offset]).fetchall()
                
                if not batch:
                    break
                
                # Process each entry
                for wallet_address, data_json, timestamp in batch:
                    try:
                        # Parse trade data
                        trade_data = json.loads(data_json)
                        
                        # Determine event type
                        action = trade_data.get('action', 'UNKNOWN')
                        if action == 'BUY':
                            event_type = TRADE_BUY
                        elif action == 'SELL':
                            event_type = TRADE_SELL
                        else:
                            self.stats['skipped'] += 1
                            continue
                        
                        # Create event
                        event = Event(
                            user_id=wallet_address,
                            event_type=event_type,
                            timestamp=timestamp,
                            data=trade_data
                        )
                        
                        # Record event
                        if self.event_store.record_event(event):
                            self.stats['migrated'] += 1
                        else:
                            self.stats['errors'] += 1
                        
                        last_processed_timestamp = timestamp.isoformat()
                        
                    except Exception as e:
                        print(f"Error migrating entry: {e}")
                        self.stats['errors'] += 1
                
                # Save checkpoint after each batch
                if last_processed_timestamp:
                    self.save_checkpoint(last_processed_timestamp)
                
                # Progress update
                print(f"Progress: {self.stats['migrated']:,}/{total_to_migrate:,} trades migrated")
                
                # Update offset for next batch
                offset += batch_size
                
                # For timestamp-based queries, update the timestamp
                if last_timestamp and batch:
                    last_timestamp = batch[-1][2].isoformat()
            
            print(f"\n✅ Migration completed!")
            print(f"   Migrated: {self.stats['migrated']:,}")
            print(f"   Skipped: {self.stats['skipped']:,}")
            print(f"   Errors: {self.stats['errors']:,}")
            
            return self.stats['migrated']
            
        finally:
            db.close()
    
    def validate_migration(self) -> bool:
        """Validate that migration was successful"""
        print("\n🔍 Validating migration...")
        
        # Count diary entries
        db = duckdb.connect(self.diary_db)
        diary_count = db.execute("""
            SELECT COUNT(*) FROM diary WHERE entry_type = 'trade'
        """).fetchone()[0]
        db.close()
        
        # Count event entries
        conn = sqlite3.connect(self.event_store.db_path)
        event_count = conn.execute("""
            SELECT COUNT(*) FROM events 
            WHERE event_type IN (?, ?)
        """, [TRADE_BUY, TRADE_SELL]).fetchone()[0]
        conn.close()
        
        print(f"Diary trades: {diary_count:,}")
        print(f"Event trades: {event_count:,}")
        
        # Allow for some skipped entries
        tolerance = self.stats['skipped'] + self.stats['errors']
        expected = diary_count - tolerance
        
        if abs(event_count - expected) <= 10:  # Allow small discrepancy
            print("✅ Migration validation PASSED")
            return True
        else:
            print(f"❌ Migration validation FAILED - counts don't match")
            print(f"   Expected: {expected:,} (diary - skipped - errors)")
            print(f"   Actual: {event_count:,}")
            return False
    
    def spot_check(self, num_samples: int = 5):
        """Spot check random entries for data integrity"""
        print(f"\n🔬 Spot checking {num_samples} random entries...")
        
        import random
        
        # Get some diary entries
        db = duckdb.connect(self.diary_db)
        samples = db.execute("""
            SELECT wallet_address, data, timestamp
            FROM diary 
            WHERE entry_type = 'trade'
            ORDER BY RANDOM()
            LIMIT ?
        """, [num_samples]).fetchall()
        db.close()
        
        matches = 0
        for wallet, diary_data, timestamp in samples:
            diary_trade = json.loads(diary_data)
            
            # Find corresponding event
            events = self.event_store.query_events(
                user_id=wallet,
                start_time=timestamp - timedelta(seconds=1),
                end_time=timestamp + timedelta(seconds=1)
            )
            
            if events:
                event_data = events[0].data
                # Check key fields match
                if (diary_trade.get('token_symbol') == event_data.get('token_symbol') and
                    diary_trade.get('sol_amount') == event_data.get('sol_amount')):
                    matches += 1
                    print(f"  ✅ Match: {diary_trade['token_symbol']} trade at {timestamp}")
                else:
                    print(f"  ❌ Mismatch: {diary_trade['token_symbol']} trade at {timestamp}")
            else:
                print(f"  ❌ No event found for {timestamp}")
        
        print(f"\nSpot check: {matches}/{num_samples} matches")
        return matches == num_samples


def main():
    """Run the migration"""
    print("🚀 Diary to Event Store Migration")
    print("=" * 50)
    
    migration = DiaryToEventMigration()
    
    # Run migration
    migrated = migration.migrate_trades(batch_size=1000)
    
    if migrated > 0:
        # Validate
        valid = migration.validate_migration()
        
        # Spot check
        spot_check_pass = migration.spot_check(10)
        
        if valid and spot_check_pass:
            print("\n✅ Migration completed successfully!")
            print("Event store is ready for use.")
        else:
            print("\n⚠️ Migration completed with issues")
            print("Review the discrepancies before proceeding.")
    else:
        print("\n📭 No entries to migrate")


if __name__ == "__main__":
    main() 