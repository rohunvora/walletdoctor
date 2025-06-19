"""
Prompt Builder - Minimal JSON for GPT
"""

import json
import logging
import duckdb
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


async def build_prompt(user_id: int, wallet_address: str, event_type: str, event_data: Dict) -> Dict:
    """Build minimal context for GPT"""
    
    # Get last 5 chat messages
    recent_chat = await fetch_recent_chat(user_id, limit=5)
    
    # Build context based on event type
    context = {
        'current_event': {
            'type': event_type,
            'data': event_data,
            'timestamp': event_data.get('timestamp', datetime.now().isoformat())
        },
        'recent_chat': recent_chat
    }
    
    # Add bankroll context for trades
    if event_type == 'trade':
        context['bankroll_before_sol'] = event_data.get('bankroll_before_sol')
        context['bankroll_after_sol'] = event_data.get('bankroll_after_sol')
        context['trade_pct_bankroll'] = event_data.get('trade_pct_bankroll')
    
    return context


async def fetch_recent_chat(user_id: int, limit: int = 5) -> List[Dict]:
    """Get recent messages and responses from diary"""
    db = duckdb.connect('pocket_coach.db')
    try:
        results = db.execute("""
            SELECT 
                entry_type,
                data,
                timestamp
            FROM diary 
            WHERE user_id = ? 
            AND entry_type IN ('message', 'response')
            ORDER BY timestamp DESC 
            LIMIT ?
        """, [user_id, limit]).fetchall()
        
        chat = []
        for entry_type, data_json, timestamp in reversed(results):
            data = json.loads(data_json)
            chat.append({
                'role': 'user' if entry_type == 'message' else 'assistant',
                'content': data.get('text', ''),
                'timestamp': timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)
            })
        
        return chat
    finally:
        db.close()


async def write_to_diary(entry_type: str, user_id: int, wallet_address: str, data: Dict):
    """Write an entry to the diary"""
    db = duckdb.connect('pocket_coach.db')
    try:
        # Ensure we have a timestamp
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now().isoformat()
            
        db.execute("""
            INSERT INTO diary (entry_type, user_id, wallet_address, data)
            VALUES (?, ?, ?, ?)
        """, [entry_type, user_id, wallet_address, json.dumps(data)])
        
        db.commit()
        logger.info(f"Wrote {entry_type} to diary for user {user_id}")
        
        # Invalidate trade cache if this was a trade
        if entry_type == 'trade' and wallet_address:
            from diary_api import invalidate_cache
            invalidate_cache(wallet_address)
            
    finally:
        db.close() 