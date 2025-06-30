#!/usr/bin/env python3
"""
Clear test data from diary for fresh testing
"""

import duckdb
import sys
from typing import Optional

def clear_user_data(user_id: Optional[int] = None):
    """Clear diary entries for a specific user or all test data"""
    db = duckdb.connect('pocket_coach.db')
    
    try:
        if user_id:
            # Clear specific user
            count_result = db.execute("""
                SELECT COUNT(*) FROM diary 
                WHERE user_id = ?
            """, [user_id]).fetchone()
            count = count_result[0] if count_result else 0
            
            if count > 0:
                db.execute("""
                    DELETE FROM diary 
                    WHERE user_id = ?
                """, [user_id])
                db.commit()
                print(f"✅ Cleared {count} diary entries for user {user_id}")
            else:
                print(f"No entries found for user {user_id}")
        else:
            # Clear all recent test data (last hour)
            count_result = db.execute("""
                SELECT COUNT(*) FROM diary 
                WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL 1 HOUR
            """).fetchone()
            count = count_result[0] if count_result else 0
            
            if count > 0:
                response = input(f"Clear {count} recent entries? (y/n): ")
                if response.lower() == 'y':
                    db.execute("""
                        DELETE FROM diary 
                        WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL 1 HOUR
                    """)
                    db.commit()
                    print(f"✅ Cleared {count} recent diary entries")
                else:
                    print("Cancelled")
            else:
                print("No recent entries to clear")
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Clear specific user
        user_id = int(sys.argv[1])
        clear_user_data(user_id)
    else:
        # Clear recent test data
        clear_user_data() 