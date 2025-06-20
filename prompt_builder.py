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
        'wallet_address': wallet_address,  # Add wallet for tool execution
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
        
        # Add USD context if available
        if 'sol_price_usd' in event_data:
            context['sol_price_usd'] = event_data.get('sol_price_usd')
            context['trade_size_usd'] = event_data.get('trade_size_usd')
        
        # Add timing context
        if 'minutes_since_last_trade' in event_data:
            context['minutes_since_last_trade'] = event_data.get('minutes_since_last_trade')
            
        # Add session stats
        if 'trades_last_24h' in event_data:
            context['trades_last_24h'] = event_data.get('trades_last_24h')
            context['session_pnl_usd'] = event_data.get('session_pnl_usd')
        
        # Add price context for the traded token
        token_address = event_data.get('token_address')
        token_symbol = event_data.get('token_symbol')
        
        if token_address and token_symbol:
            from diary_api import fetch_price_context
            price_context = await fetch_price_context(wallet_address, token_address, token_symbol)
            
            if price_context and 'error' not in price_context:
                # Add key price metrics to context
                context['price_context'] = {
                    'price_change_1h': price_context.get('price_change_1h'),
                    'price_change_24h': price_context.get('price_change_24h'),
                    'token_age_hours': price_context.get('token_age_hours'),
                    'current_multiplier': price_context.get('current_multiplier'),
                    'peak_multiplier': price_context.get('peak_multiplier'),
                    'down_from_peak': price_context.get('down_from_peak')
                }
                
                # Add special alerts for significant events
                if price_context.get('down_from_peak', 0) > 50:
                    context['price_alert'] = 'down_50_percent_from_peak'
                elif price_context.get('current_multiplier', 0) >= 10:
                    context['price_alert'] = '10x_from_entry'
                elif price_context.get('price_change_1h', 0) > 50:
                    context['price_alert'] = 'pumping_hard_1h'
                elif price_context.get('price_change_1h', 0) < -30:
                    context['price_alert'] = 'dumping_hard_1h'
    
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