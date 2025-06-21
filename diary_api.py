"""
Diary API - Simple data access for GPT with in-memory caching
"""

import json
import logging
import duckdb
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)

# In-memory cache for last 20 trades per wallet
trade_cache = {}  # wallet_address -> deque(maxlen=20)


async def fetch_last_n_trades(wallet: str, n: int = 5) -> List[Dict]:
    """Get last N trades from diary with caching"""
    
    # Check cache first
    if wallet in trade_cache and len(trade_cache[wallet]) >= n:
        logger.info(f"Cache hit for {wallet}, returning {n} trades")
        return list(trade_cache[wallet])[:n]
    
    # Cache miss, fetch from DB
    logger.info(f"Cache miss for {wallet}, fetching from diary")
    db = duckdb.connect('pocket_coach.db')
    try:
        results = db.execute("""
            SELECT data FROM diary 
            WHERE wallet_address = ? 
            AND entry_type = 'trade'
            ORDER BY timestamp DESC 
            LIMIT 20
        """, [wallet]).fetchall()
        
        # Update cache with last 20 trades
        trades = [json.loads(r[0]) for r in results]
        if trades:
            trade_cache[wallet] = deque(trades, maxlen=20)
        
        return trades[:n]
    finally:
        db.close()


async def fetch_trades_by_token(wallet: str, token: str, n: int = 5) -> List[Dict]:
    """Get trades for specific token"""
    db = duckdb.connect('pocket_coach.db')
    try:
        results = db.execute("""
            SELECT data FROM diary 
            WHERE wallet_address = ? 
            AND entry_type = 'trade'
            AND json_extract_string(data, '$.token_symbol') = ?
            ORDER BY timestamp DESC 
            LIMIT ?
        """, [wallet, token, n]).fetchall()
        
        return [json.loads(r[0]) for r in results]
    finally:
        db.close()


async def fetch_trades_by_time(wallet: str, start_hour: int, end_hour: int, n: int = 10) -> List[Dict]:
    """Get trades within specific hour range (e.g., 2-6 for late night)"""
    db = duckdb.connect('pocket_coach.db')
    try:
        results = db.execute("""
            SELECT data FROM diary 
            WHERE wallet_address = ? 
            AND entry_type = 'trade'
            AND EXTRACT(HOUR FROM timestamp) >= ?
            AND EXTRACT(HOUR FROM timestamp) <= ?
            ORDER BY timestamp DESC 
            LIMIT ?
        """, [wallet, start_hour, end_hour, n]).fetchall()
        
        return [json.loads(r[0]) for r in results]
    finally:
        db.close()


async def fetch_token_balance(wallet: str, token: str) -> float:
    """Calculate running token balance from trades"""
    db = duckdb.connect('pocket_coach.db')
    try:
        results = db.execute("""
            SELECT 
                json_extract_string(data, '$.action') as action,
                CAST(json_extract_string(data, '$.token_amount') AS FLOAT) as amount
            FROM diary 
            WHERE wallet_address = ? 
            AND entry_type = 'trade'
            AND json_extract_string(data, '$.token_symbol') = ?
            ORDER BY timestamp ASC
        """, [wallet, token]).fetchall()
        
        balance = 0.0
        for action, amount in results:
            if amount is not None:  # Handle None values
                if action == 'BUY':
                    balance += amount
                else:  # SELL
                    balance -= amount
                
        return balance
    finally:
        db.close()


def invalidate_cache(wallet: str):
    """Invalidate cache for a wallet after new trade"""
    if wallet in trade_cache:
        del trade_cache[wallet]
        logger.info(f"Cache invalidated for {wallet}")


async def fetch_wallet_stats(wallet: str) -> Dict:
    """Get overall wallet trading statistics from Cielo"""
    try:
        # Import Cielo data fetching function
        from scripts.data import fetch_cielo_trading_stats
        
        # Fetch trading stats from Cielo
        stats_response = fetch_cielo_trading_stats(wallet)
        
        if stats_response.get('status') == 'ok':
            data = stats_response.get('data', {})
            
            # Extract and normalize the stats
            return {
                'total_swaps': data.get('swaps_count', 0),
                'win_rate': data.get('winrate', 0),
                'total_pnl_usd': data.get('pnl', 0),
                'avg_trade_size_usd': data.get('average_buy_amount_usd', 0),
                'wallet_age_days': data.get('wallet_age_days', 0),
                'total_volume_usd': data.get('total_volume_usd', 0),
                'best_token': data.get('best_performing_token', {}).get('symbol', 'N/A'),
                'worst_token': data.get('worst_performing_token', {}).get('symbol', 'N/A')
            }
        else:
            logger.warning(f"Cielo API returned non-ok status for wallet {wallet}")
            return {}
            
    except Exception as e:
        logger.error(f"Error fetching wallet stats: {e}")
        return {}


async def fetch_token_pnl(wallet: str, token: str) -> Dict:
    """Get P&L data for a specific token from Cielo"""
    try:
        # Import Cielo data fetching function
        from scripts.data import fetch_cielo_pnl
        
        # Fetch all token P&L data
        pnl_response = fetch_cielo_pnl(wallet)
        
        if 'tokens' in pnl_response:
            tokens = pnl_response['tokens']
            
            # Find the specific token
            for token_data in tokens:
                if token_data.get('token_symbol', '').upper() == token.upper():
                    return {
                        'token_symbol': token_data.get('token_symbol', token),
                        'token_name': token_data.get('token_name', ''),
                        'realized_pnl_usd': token_data.get('total_pnl_usd', 0),
                        'unrealized_pnl_usd': token_data.get('unrealized_pnl_usd', 0),
                        'total_pnl_usd': token_data.get('total_pnl_usd', 0) + token_data.get('unrealized_pnl_usd', 0),
                        'roi_percentage': token_data.get('roi_percentage', 0),
                        'num_swaps': token_data.get('num_swaps', 0),
                        'avg_buy_price': token_data.get('average_buy_price', 0),
                        'avg_sell_price': token_data.get('average_sell_price', 0),
                        'total_buy_usd': token_data.get('total_buy_usd', 0),
                        'total_sell_usd': token_data.get('total_sell_usd', 0),
                        'holding_amount': token_data.get('holding_amount', 0),
                        'holding_time_seconds': token_data.get('holding_time_seconds', 0),
                        'has_open_position': token_data.get('holding_amount', 0) > 0
                    }
            
            # Token not found
            return {
                'token_symbol': token,
                'error': 'Token not found in trading history'
            }
        else:
            return {
                'token_symbol': token,
                'error': 'Failed to fetch P&L data'
            }
            
    except Exception as e:
        logger.error(f"Error fetching token P&L: {e}")
        return {
            'token_symbol': token,
            'error': str(e)
        }


async def fetch_market_cap_context(wallet: str, token: str) -> Dict:
    """Get market cap context for a token including entry/exit and risk analysis"""
    try:
        # Get current market cap
        from scripts.token_metadata import TokenMetadataService
        metadata_service = TokenMetadataService()
        
        # First get the token address from recent trades
        db = duckdb.connect('pocket_coach.db')
        result = db.execute("""
            SELECT json_extract_string(data, '$.token_address') as token_address
            FROM diary 
            WHERE wallet_address = ? 
            AND entry_type = 'trade'
            AND json_extract_string(data, '$.token_symbol') = ?
            ORDER BY timestamp DESC 
            LIMIT 1
        """, [wallet, token]).fetchone()
        db.close()
        
        if not result:
            return {
                'token': token,
                'error': 'Token not found in trading history'
            }
        
        token_address = result[0]
        current_mcap = await metadata_service.get_market_cap(token_address)
        
        # Get entry market cap from last BUY
        db = duckdb.connect('pocket_coach.db')
        buy_result = db.execute("""
            SELECT 
                CAST(json_extract_string(data, '$.market_cap') AS FLOAT) as entry_mcap,
                json_extract_string(data, '$.market_cap_formatted') as entry_mcap_formatted
            FROM diary 
            WHERE wallet_address = ? 
            AND entry_type = 'trade'
            AND json_extract_string(data, '$.action') = 'BUY'
            AND json_extract_string(data, '$.token_symbol') = ?
            ORDER BY timestamp DESC 
            LIMIT 1
        """, [wallet, token]).fetchone()
        db.close()
        
        context = {
            'token': token,
            'current_mcap': current_mcap,
            'current_mcap_formatted': metadata_service.format_market_cap(current_mcap)
        }
        
        if buy_result and buy_result[0]:
            entry_mcap = buy_result[0]
            context['entry_mcap'] = entry_mcap
            context['entry_mcap_formatted'] = buy_result[1]
            
            if current_mcap and entry_mcap:
                context['multiplier'] = current_mcap / entry_mcap
                
                # Risk/reward analysis
                if context['multiplier'] >= 10:
                    context['risk_reward'] = "10x+ achieved, consider taking profits"
                elif context['multiplier'] >= 5:
                    context['risk_reward'] = "5x from entry, strong gains"
                elif context['multiplier'] >= 2:
                    context['risk_reward'] = "2x from entry, decent profit"
                elif context['multiplier'] >= 1.5:
                    context['risk_reward'] = "Up 50%, could run more or dump"
                elif context['multiplier'] >= 0.7:
                    context['risk_reward'] = "Near entry, hold or cut?"
                else:
                    context['risk_reward'] = "Down significantly from entry"
        
        # Market cap category analysis
        if current_mcap:
            if current_mcap < 100_000:
                context['mcap_category'] = "micro (<$100K) - extreme risk"
            elif current_mcap < 1_000_000:
                context['mcap_category'] = "small ($100K-$1M) - high risk"
            elif current_mcap < 10_000_000:
                context['mcap_category'] = "mid ($1M-$10M) - moderate risk"
            else:
                context['mcap_category'] = "large (>$10M) - lower risk"
        
        return context
        
    except Exception as e:
        logger.error(f"Error fetching market cap context: {e}")
        return {
            'token': token,
            'error': str(e)
        }


async def fetch_price_context(wallet: str, token_address: str, token_symbol: str) -> Dict:
    """Get price context including changes, peaks, and age for a token"""
    try:
        db = duckdb.connect('pocket_coach.db')
        
        # Get current and historical price data
        current_time = datetime.now()
        one_hour_ago = current_time - timedelta(hours=1)
        one_day_ago = current_time - timedelta(days=1)
        
        # Get current price
        current_result = db.execute("""
            SELECT price_usd, price_sol, market_cap, timestamp
            FROM price_snapshots
            WHERE token_address = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, [token_address]).fetchone()
        
        if not current_result:
            db.close()
            return {'error': 'No price data available'}
        
        current_price_usd, current_price_sol, current_mcap, latest_timestamp = current_result
        
        # Get 1 hour ago price
        hour_ago_result = db.execute("""
            SELECT price_usd, market_cap
            FROM price_snapshots
            WHERE token_address = ?
            AND timestamp <= ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, [token_address, one_hour_ago]).fetchone()
        
        # Get 24 hours ago price
        day_ago_result = db.execute("""
            SELECT price_usd, market_cap
            FROM price_snapshots
            WHERE token_address = ?
            AND timestamp <= ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, [token_address, one_day_ago]).fetchone()
        
        # Get first price record (token age)
        first_result = db.execute("""
            SELECT timestamp, price_usd
            FROM price_snapshots
            WHERE token_address = ?
            ORDER BY timestamp ASC
            LIMIT 1
        """, [token_address]).fetchone()
        
        # Get user's position info if available
        position_result = None
        if wallet:
            # Get user ID from wallet
            user_result = db.execute("""
                SELECT user_id FROM user_wallets
                WHERE wallet_address = ?
            """, [wallet]).fetchone()
            
            if user_result:
                user_id = user_result[0]
                position_result = db.execute("""
                    SELECT 
                        avg_entry_price_usd,
                        peak_price_usd,
                        peak_multiplier_from_entry,
                        peak_timestamp
                    FROM user_positions
                    WHERE user_id = ? AND token_address = ?
                """, [user_id, token_address]).fetchone()
        
        db.close()
        
        # Build context
        context = {
            'token_symbol': token_symbol,
            'current_price_usd': current_price_usd,
            'current_price_sol': current_price_sol,
            'current_market_cap': current_mcap,
            'latest_update': latest_timestamp.isoformat()
        }
        
        # Calculate 1h price change
        if hour_ago_result:
            hour_price = hour_ago_result[0]
            context['price_change_1h'] = ((current_price_usd - hour_price) / hour_price) * 100 if hour_price > 0 else 0
            context['price_1h_ago'] = hour_price
        
        # Calculate 24h price change
        if day_ago_result:
            day_price = day_ago_result[0]
            context['price_change_24h'] = ((current_price_usd - day_price) / day_price) * 100 if day_price > 0 else 0
            context['price_24h_ago'] = day_price
            context['mcap_change_24h'] = ((current_mcap - day_ago_result[1]) / day_ago_result[1]) * 100 if day_ago_result[1] > 0 else 0
        
        # Calculate token age
        if first_result:
            first_timestamp, first_price = first_result
            token_age = current_time - first_timestamp
            context['token_age_hours'] = int(token_age.total_seconds() / 3600)
            context['token_age_days'] = token_age.days
            context['first_seen_price'] = first_price
            context['all_time_change'] = ((current_price_usd - first_price) / first_price) * 100 if first_price > 0 else 0
        
        # Add position-specific context
        if position_result:
            entry_price, peak_price, peak_multiplier, peak_time = position_result
            if entry_price:
                context['entry_price_usd'] = entry_price
                context['current_multiplier'] = current_price_usd / entry_price if entry_price > 0 else 0
                
            if peak_price:
                context['peak_price_usd'] = peak_price
                context['peak_multiplier'] = peak_multiplier
                context['peak_timestamp'] = peak_time.isoformat() if peak_time else None
                context['down_from_peak'] = ((peak_price - current_price_usd) / peak_price) * 100 if peak_price > 0 else 0
        
        return context
        
    except Exception as e:
        logger.error(f"Error fetching price context: {e}")
        return {'error': str(e)}


async def fetch_price_snapshots(token_address: str, hours: int = 24) -> List[Dict]:
    """Get price snapshots for charting or analysis"""
    try:
        db = duckdb.connect('pocket_coach.db')
        
        since_time = datetime.now() - timedelta(hours=hours)
        
        results = db.execute("""
            SELECT timestamp, price_usd, price_sol, market_cap, volume_24h, liquidity_usd
            FROM price_snapshots
            WHERE token_address = ?
            AND timestamp >= ?
            ORDER BY timestamp DESC
        """, [token_address, since_time]).fetchall()
        
        db.close()
        
        snapshots = []
        for row in results:
            snapshots.append({
                'timestamp': row[0].isoformat(),
                'price_usd': row[1],
                'price_sol': row[2],
                'market_cap': row[3],
                'volume_24h': row[4],
                'liquidity_usd': row[5]
            })
        
        return snapshots
        
    except Exception as e:
        logger.error(f"Error fetching price snapshots: {e}")
        return []


async def save_user_goal(user_id: int, goal_data: dict, raw_text: str) -> Dict:
    """GPT calls this when goal is clear enough"""
    try:
        db = duckdb.connect('pocket_coach.db')
        
        # Insert or replace user goal
        db.execute("""
            INSERT OR REPLACE INTO user_goals (user_id, goal_json, raw_statement, confirmed)
            VALUES (?, ?, ?, FALSE)
        """, [user_id, json.dumps(goal_data), raw_text])
        
        db.close()
        
        logger.info(f"Saved goal for user {user_id}: {goal_data}")
        return {
            'success': True,
            'goal': goal_data,
            'message': 'Goal saved successfully'
        }
        
    except Exception as e:
        logger.error(f"Error saving user goal: {e}")
        return {
            'success': False,
            'error': str(e)
        }


async def log_fact(user_id: int, key: str, value: str, context: str) -> Dict:
    """Store any fact worth remembering"""
    try:
        db = duckdb.connect('pocket_coach.db')
        
        # Insert or replace fact (upsert)
        db.execute("""
            INSERT OR REPLACE INTO user_facts (user_id, fact_key, fact_value, context, timestamp)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, [user_id, key, value, context])
        
        # Increment usage count on update
        db.execute("""
            UPDATE user_facts 
            SET usage_count = usage_count + 1
            WHERE user_id = ? AND fact_key = ?
        """, [user_id, key])
        
        db.close()
        
        logger.info(f"Logged fact for user {user_id}: {key}={value}")
        return {
            'success': True,
            'fact_key': key,
            'fact_value': value
        }
        
    except Exception as e:
        logger.error(f"Error logging fact: {e}")
        return {
            'success': False,
            'error': str(e)
        }


async def fetch_user_goal(user_id: int) -> Optional[Dict]:
    """Fetch user's current goal if exists"""
    try:
        db = duckdb.connect('pocket_coach.db')
        
        result = db.execute("""
            SELECT goal_json, raw_statement, confirmed, created_at
            FROM user_goals
            WHERE user_id = ?
        """, [user_id]).fetchone()
        
        db.close()
        
        if result:
            goal_json, raw_statement, confirmed, created_at = result
            goal_data = json.loads(goal_json) if goal_json else {}
            return {
                'goal': goal_data,
                'raw_statement': raw_statement,
                'confirmed': confirmed,
                'created_at': created_at.isoformat() if created_at else None
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Error fetching user goal: {e}")
        return None


async def fetch_recent_facts(user_id: int, limit: int = 10) -> List[Dict]:
    """Fetch recent facts for a user"""
    try:
        db = duckdb.connect('pocket_coach.db')
        
        results = db.execute("""
            SELECT fact_key, fact_value, context, timestamp, usage_count
            FROM user_facts
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, [user_id, limit]).fetchall()
        
        db.close()
        
        facts = []
        for row in results:
            facts.append({
                'key': row[0],
                'value': row[1],
                'context': row[2],
                'timestamp': row[3].isoformat() if row[3] else None,
                'usage_count': row[4]
            })
        
        return facts
        
    except Exception as e:
        logger.error(f"Error fetching recent facts: {e}")
        return [] 