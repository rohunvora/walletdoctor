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