"""
Prompt Builder - Minimal JSON for GPT
"""

import json
import logging
import duckdb
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


async def build_prompt(user_id: int, wallet_address: str, event_type: str, event_data: Dict) -> Dict:
    """Build minimal context for GPT"""
    
    # Get last 5 chat messages
    recent_chat = await fetch_recent_chat(user_id, limit=5)
    
    # Get user goal and facts
    from diary_api import fetch_user_goal, fetch_recent_facts
    user_goal = await fetch_user_goal(user_id)
    recent_facts = await fetch_recent_facts(user_id, limit=10)
    
    # Build context based on event type
    context = {
        'wallet_address': wallet_address,  # Add wallet for tool execution
        'user_id': user_id,  # Add user_id for goal/fact functions
        'current_event': {
            'type': event_type,
            'data': event_data,
            'timestamp': event_data.get('timestamp', datetime.now().isoformat())
        },
        'recent_chat': recent_chat,
        'user_goal': user_goal,  # Can be None
        'recent_facts': recent_facts  # List of recent facts
    }
    
    # For trade events, add notification hints about what's notable
    if event_type == 'trade':
        notification_hints = []
        
        # Check position size
        trade_pct = event_data.get('trade_pct_bankroll', 0)
        if trade_pct > 20:
            notification_hints.append(f"unusually large position at {trade_pct:.0f}% of bankroll")
        
        # Check if it's a partial sell
        if event_data.get('action') == 'SELL':
            position_data = event_data.get('position_state', {})
            if position_data.get('is_full_exit') == False:
                sold_pct = position_data.get('sold_percentage', 0)
                notification_hints.append(f"partial sell - took {sold_pct:.0f}% off")
        
        # Check market cap
        mcap = event_data.get('market_cap_usd', 0)
        if mcap > 10_000_000:
            notification_hints.append(f"high market cap trade at ${mcap/1_000_000:.0f}M")
        
        if notification_hints:
            context['notification_hints'] = notification_hints
    
    # CRITICAL: Add conversation continuity context
    # If this is a short message that looks like a follow-up question, 
    # include the last trade data for context
    if event_type == 'message' and len(event_data.get('text', '')) < 30:
        # Check if this might be a follow-up question
        text_lower = event_data.get('text', '').lower()
        follow_up_indicators = ['why', 'what', 'how', 'explain', '?', 'risky', 'more', 'details']
        
        if any(indicator in text_lower for indicator in follow_up_indicators):
            # Get the most recent trade to provide context
            from diary_api import fetch_last_n_trades
            recent_trades = await fetch_last_n_trades(wallet_address, 1)
            if recent_trades:
                context['likely_referencing_trade'] = recent_trades[0]
                context['is_follow_up'] = True
                
            # Also include the last assistant message to understand what we're following up on
            if recent_chat and len(recent_chat) > 0:
                for msg in reversed(recent_chat):
                    if msg.get('role') == 'assistant':
                        context['last_bot_message'] = msg.get('content')
                        break
    
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
        
        # Add trade sequence context
        last_5_trades = await get_last_n_trades_summary(wallet_address, 5)
        if last_5_trades:
            context['trade_sequence'] = {
                'last_5': last_5_trades,
                'timing_gaps': [t.get('minutes_since_previous') for t in last_5_trades if t.get('minutes_since_previous')],
                'pnl_sequence': [t.get('pnl_usd') for t in last_5_trades if t.get('pnl_usd') is not None]
            }
        
        # Add price context for the traded token
        token_address = event_data.get('token_address')
        token_symbol = event_data.get('token_symbol')
        
        if token_address and token_symbol:
            from diary_api import fetch_price_context
            price_context = await fetch_price_context(wallet_address, token_address, token_symbol)
            
            if price_context and 'error' not in price_context:
                # Add key price metrics to context - raw data, no interpretation
                context['price_context'] = {
                    'price_change_1h': price_context.get('price_change_1h'),
                    'price_change_24h': price_context.get('price_change_24h'),
                    'token_age_hours': price_context.get('token_age_hours'),
                    'current_multiplier': price_context.get('current_multiplier'),
                    'peak_multiplier': price_context.get('peak_multiplier'),
                    'down_from_peak': price_context.get('down_from_peak')
                }
                # No alerts, no thresholds - let GPT decide what's significant
    
    # NEW: System-level context primitives for better pattern recognition
    
    # 1. User behavior patterns (for comparison)
    user_patterns = await get_user_patterns(wallet_address)
    if user_patterns:
        context['user_patterns'] = user_patterns
    
    # 2. Current position state (for partial sells)
    if event_type == 'trade':
        token_symbol = event_data.get('token_symbol')
        if token_symbol:
            position_state = await get_position_state(wallet_address, token_symbol)
            if position_state:
                context['position_state'] = position_state
    
    # 3. Trade analysis primitives
    if event_type == 'trade':
        trade_analysis = await analyze_current_trade(wallet_address, event_data)
        if trade_analysis:
            context['trade_analysis'] = trade_analysis
    
    # 4. Current bankroll for context
    current_bankroll = await get_current_bankroll(wallet_address)
    if current_bankroll is not None:
        context['bankroll_sol'] = current_bankroll
    
    # 5. Add trade sequence with timing (always, not just for trades)
    trade_sequence = await get_trade_sequence_with_timing(wallet_address, limit=5)
    if trade_sequence:
        context['trade_sequence'] = trade_sequence
    
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


async def get_last_n_trades_summary(wallet_address: str, n: int) -> List[Dict]:
    """Get summary of last N trades for sequence context"""
    from diary_api import fetch_last_n_trades
    trades = await fetch_last_n_trades(wallet_address, n)
    
    summaries = []
    previous_timestamp = None
    
    for trade in trades:
        summary = {
            'token': trade.get('token_symbol'),
            'action': trade.get('action'),
            'size_sol': trade.get('amount_sol'),
            'pnl_usd': trade.get('realized_pnl_usd') if trade.get('action') == 'SELL' else None
        }
        
        # Calculate time gap
        if previous_timestamp and 'timestamp' in trade:
            try:
                current_time = datetime.fromisoformat(trade['timestamp'])
                prev_time = datetime.fromisoformat(previous_timestamp)
                minutes_gap = (prev_time - current_time).total_seconds() / 60
                summary['minutes_since_previous'] = int(minutes_gap)
            except:
                pass
        
        previous_timestamp = trade.get('timestamp')
        summaries.append(summary)
    
    return summaries 


async def get_user_patterns(wallet_address: str) -> Optional[Dict[str, Any]]:
    """Get user's typical trading patterns for comparison"""
    db = duckdb.connect('pocket_coach.db')
    try:
        # Get patterns from last 30 days
        patterns = db.execute("""
            WITH trade_data AS (
                SELECT 
                    json_extract_string(data, '$.trade_pct_bankroll') as pct_str,
                    json_extract_string(data, '$.market_cap_usd') as mcap_str,
                    EXTRACT(hour FROM timestamp) as trade_hour
                FROM diary 
                WHERE wallet_address = ? 
                AND entry_type = 'trade'
                AND timestamp > CURRENT_DATE - INTERVAL '30' DAY
            )
            SELECT 
                AVG(CAST(pct_str AS DOUBLE)) as avg_position_pct,
                MIN(CAST(pct_str AS DOUBLE)) as min_position_pct,
                MAX(CAST(pct_str AS DOUBLE)) as max_position_pct,
                AVG(CAST(mcap_str AS DOUBLE)) as avg_market_cap,
                MIN(CAST(mcap_str AS DOUBLE)) as min_market_cap,
                MAX(CAST(mcap_str AS DOUBLE)) as max_market_cap,
                MODE(trade_hour) as typical_trade_hour,
                COUNT(*) as total_trades_30d
            FROM trade_data
            WHERE pct_str IS NOT NULL AND mcap_str IS NOT NULL
        """, [wallet_address]).fetchone()
        
        if patterns and patterns[0] is not None:
            return {
                'position_size': {
                    'typical_pct': round(patterns[0], 1),
                    'range': (round(patterns[1], 1), round(patterns[2], 1))
                },
                'market_cap': {
                    'typical': int(patterns[3]) if patterns[3] else None,
                    'range': (int(patterns[4]) if patterns[4] else None, 
                             int(patterns[5]) if patterns[5] else None)
                },
                'typical_trade_hour': patterns[6],
                'total_trades_30d': patterns[7]
            }
        return None
    finally:
        db.close()


async def get_position_state(wallet_address: str, token_symbol: str) -> Dict[str, Any]:
    """Get current position state including entry and partial sell info"""
    if not token_symbol:
        return None
        
    from diary_api import fetch_trades_by_token
    trades = await fetch_trades_by_token(wallet_address, token_symbol, n=50)
    
    if not trades:
        return None
    
    # Calculate position from trades
    total_bought = 0.0
    total_sold = 0.0
    buy_count = 0
    sell_count = 0
    
    for trade in trades:
        if trade['action'] == 'BUY':
            total_bought += trade['amount_sol']
            buy_count += 1
        else:
            total_sold += trade['amount_sol']
            sell_count += 1
    
    remaining = total_bought - total_sold
    
    # Calculate percentage sold/remaining
    pct_sold = (total_sold / total_bought * 100) if total_bought > 0 else 0
    pct_remaining = 100 - pct_sold
    
    return {
        'token': token_symbol,
        'total_bought_sol': round(total_bought, 3),
        'total_sold_sol': round(total_sold, 3),
        'remaining_sol': round(remaining, 3),
        'pct_remaining': round(pct_remaining, 1),
        'pct_sold': round(pct_sold, 1),
        'num_buys': buy_count,
        'num_sells': sell_count,
        'is_partial_sell': sell_count > 0 and remaining > 0.001
    }


async def analyze_current_trade(wallet_address: str, event_data: Dict) -> Dict[str, Any]:
    """Analyze current trade in context of user patterns and position"""
    analysis = {}
    
    # Get user patterns
    patterns = await get_user_patterns(wallet_address)
    if patterns and 'trade_pct_bankroll' in event_data:
        current_pct = event_data['trade_pct_bankroll']
        typical_pct = patterns['position_size']['typical_pct']
        
        # Position size comparison
        analysis['position_size_vs_typical'] = round(current_pct / typical_pct, 1) if typical_pct > 0 else None
        analysis['is_unusually_large'] = current_pct > patterns['position_size']['range'][1]
        analysis['is_unusually_small'] = current_pct < patterns['position_size']['range'][0]
    
    # Market cap comparison
    if patterns and 'market_cap_usd' in event_data and patterns['market_cap']['typical']:
        current_mcap = event_data['market_cap_usd']
        typical_mcap = patterns['market_cap']['typical']
        
        analysis['mcap_vs_typical'] = round(current_mcap / typical_mcap, 1) if typical_mcap > 0 else None
        analysis['is_higher_mcap_than_usual'] = current_mcap > patterns['market_cap']['range'][1]
    
    # Time analysis
    current_hour = datetime.now().hour
    if patterns and patterns.get('typical_trade_hour') is not None:
        analysis['current_hour'] = current_hour
        analysis['is_unusual_time'] = abs(current_hour - patterns['typical_trade_hour']) > 6
    
    return analysis


async def get_current_bankroll(wallet_address: str) -> float:
    """Get current bankroll from most recent trade"""
    from diary_api import fetch_last_n_trades
    trades = await fetch_last_n_trades(wallet_address, 1)
    
    if trades and trades[0].get('bankroll_after_sol') is not None:
        return trades[0]['bankroll_after_sol']
    return None


async def get_trade_sequence_with_timing(wallet_address: str, limit: int = 5) -> List[Dict]:
    """Get recent trades with timing gaps and context"""
    from diary_api import fetch_last_n_trades
    trades = await fetch_last_n_trades(wallet_address, limit)
    
    if not trades:
        return []
    
    sequence = []
    for i, trade in enumerate(trades):
        trade_info = {
            'token': trade.get('token_symbol'),
            'action': trade.get('action'),
            'amount_sol': trade.get('amount_sol'),
            'market_cap': trade.get('market_cap_usd'),
            'timestamp': trade.get('timestamp')
        }
        
        # Add timing gap from previous trade
        if i > 0 and 'timestamp' in trade and 'timestamp' in trades[i-1]:
            try:
                current = datetime.fromisoformat(trade['timestamp'])
                previous = datetime.fromisoformat(trades[i-1]['timestamp'])
                gap_minutes = int((previous - current).total_seconds() / 60)
                trade_info['minutes_since_last'] = gap_minutes
            except:
                pass
        
        sequence.append(trade_info)
    
    return sequence 