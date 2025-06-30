#!/usr/bin/env python3
"""
Find similar historical trades based on market cap and SOL amount.
Fixed version for JSON data structure.
"""

import duckdb
from typing import List, Dict, Optional
from datetime import datetime

def find_similar_trades(
    wallet_address: str,
    current_market_cap: float,
    current_sol_amount: float,
    token_address: str = None,
    mcap_tolerance: float = 0.5,  # ±50% market cap range
    sol_tolerance: float = 0.3,    # ±30% SOL amount range
    limit: int = 5
) -> List[Dict]:
    """Find historical trades with similar market cap and SOL amount."""
    
    # Calculate ranges
    mcap_min = current_market_cap * (1 - mcap_tolerance)
    mcap_max = current_market_cap * (1 + mcap_tolerance)
    sol_min = current_sol_amount * (1 - sol_tolerance)
    sol_max = current_sol_amount * (1 + sol_tolerance)
    
    conn = duckdb.connect('pocket_coach.db', read_only=True)
    
    # Query for similar trades with P&L calculation
    query = """
        WITH trade_data AS (
            SELECT 
                timestamp,
                json_extract_string(data, '$.token_symbol') as token_symbol,
                json_extract_string(data, '$.token_address') as token_address,
                json_extract_string(data, '$.action') as action,
                CAST(json_extract_string(data, '$.sol_amount') AS DOUBLE) as sol_amount,
                CAST(json_extract_string(data, '$.market_cap') AS DOUBLE) as market_cap,
                json_extract_string(data, '$.market_cap_formatted') as market_cap_formatted,
                CAST(json_extract_string(data, '$.trade_pct_bankroll') AS DOUBLE) as trade_pct_bankroll
            FROM diary
            WHERE wallet_address = ?
            AND entry_type = 'trade'
        ),
        buy_trades AS (
            SELECT * FROM trade_data
            WHERE action = 'BUY'
            AND market_cap BETWEEN ? AND ?
            AND sol_amount BETWEEN ? AND ?
            AND token_address != COALESCE(?, '')
            ORDER BY timestamp DESC
            LIMIT ?
        ),
        token_pnl AS (
            SELECT 
                b.token_symbol,
                b.token_address,
                b.timestamp as buy_timestamp,
                b.sol_amount as initial_sol,
                b.market_cap as entry_mcap,
                b.market_cap_formatted as entry_mcap_formatted,
                b.trade_pct_bankroll,
                SUM(CASE WHEN s.action = 'SELL' THEN s.sol_amount ELSE 0 END) as total_sold_sol,
                COUNT(CASE WHEN s.action = 'SELL' THEN 1 ELSE NULL END) as sell_count
            FROM buy_trades b
            LEFT JOIN trade_data s ON s.token_address = b.token_address 
                AND s.action = 'SELL'
                AND s.timestamp > b.timestamp
            GROUP BY b.token_symbol, b.token_address, b.timestamp, 
                     b.sol_amount, b.market_cap, b.market_cap_formatted, b.trade_pct_bankroll
        )
        SELECT 
            token_symbol,
            token_address,
            buy_timestamp,
            initial_sol,
            total_sold_sol,
            (total_sold_sol - initial_sol) as pnl_sol,
            entry_mcap,
            entry_mcap_formatted,
            trade_pct_bankroll,
            sell_count,
            CASE 
                WHEN sell_count = 0 THEN 'HOLDING'
                WHEN total_sold_sol < initial_sol * 0.9 THEN 'PARTIAL'
                ELSE 'CLOSED'
            END as position_status
        FROM token_pnl
        ORDER BY buy_timestamp DESC
    """
    
    results = conn.execute(query, [
        wallet_address, mcap_min, mcap_max, sol_min, sol_max, 
        token_address, limit
    ]).fetchall()
    
    # Format results
    similar_trades = []
    for row in results:
        trade = {
            'token_symbol': row[0],
            'token_address': row[1],
            'buy_timestamp': row[2],
            'initial_sol': float(row[3]),
            'total_sold_sol': float(row[4]) if row[4] else 0,
            'pnl_sol': float(row[5]) if row[5] else None,
            'entry_mcap': float(row[6]),
            'entry_mcap_formatted': row[7] or format_market_cap(row[6]),
            'trade_pct_bankroll': float(row[8]) if row[8] else None,
            'position_status': row[10]
        }
        similar_trades.append(trade)
    
    conn.close()
    return similar_trades

def format_market_cap(mcap: float) -> str:
    """Format market cap in human readable form"""
    if mcap >= 1_000_000_000:
        return f"${mcap/1_000_000_000:.1f}B"
    elif mcap >= 1_000_000:
        return f"${mcap/1_000_000:.1f}M"
    elif mcap >= 1_000:
        return f"${mcap/1_000:.1f}K"
    else:
        return f"${mcap:.0f}"

def format_similar_trades_message(trades: List[Dict]) -> str:
    """Format similar trades into a coaching message."""
    if not trades:
        return None
        
    # Build compact summary
    summaries = []
    for trade in trades[:3]:  # Show max 3 examples
        symbol = trade['token_symbol']
        pnl = trade['pnl_sol']
        status = trade['position_status']
        
        if status == 'HOLDING':
            summaries.append(f"{symbol} (still holding)")
        elif pnl is not None:
            sign = '+' if pnl >= 0 else ''
            summaries.append(f"{symbol} ({sign}{pnl:.1f} SOL)")
        else:
            summaries.append(f"{symbol} (partial)")
    
    return ", ".join(summaries)

def analyze_pattern_performance(trades: List[Dict]) -> Dict:
    """Analyze the performance of similar trades"""
    if not trades:
        return None
        
    closed_trades = [t for t in trades if t['position_status'] == 'CLOSED']
    
    if not closed_trades:
        return {
            'sample_size': len(trades),
            'all_holding': True
        }
    
    wins = [t for t in closed_trades if t['pnl_sol'] > 0]
    losses = [t for t in closed_trades if t['pnl_sol'] <= 0]
    
    total_pnl = sum(t['pnl_sol'] for t in closed_trades)
    avg_pnl = total_pnl / len(closed_trades) if closed_trades else 0
    
    return {
        'sample_size': len(trades),
        'closed_count': len(closed_trades),
        'win_rate': len(wins) / len(closed_trades) if closed_trades else 0,
        'total_pnl_sol': total_pnl,
        'avg_pnl_sol': avg_pnl,
        'biggest_win': max([t['pnl_sol'] for t in wins]) if wins else 0,
        'biggest_loss': min([t['pnl_sol'] for t in losses]) if losses else 0,
        'holding_count': len([t for t in trades if t['position_status'] == 'HOLDING'])
    }

# Make it importable
if __name__ == "__main__":
    # Test with sample values
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    similar = find_similar_trades(
        wallet_address=wallet,
        current_market_cap=1_000_000,  # 1M
        current_sol_amount=2.0,         # 2 SOL
    )
    
    print(f"Found {len(similar)} similar trades:")
    message = format_similar_trades_message(similar)
    print(f"Message: {message}")