#!/usr/bin/env python3
"""
Find similar historical trades based on market cap and SOL amount.
This enables pattern-based coaching like "last 3 times you bought at 3M mcap with 10 SOL..."
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
    """
    Find historical trades with similar market cap and SOL amount.
    
    Returns list of similar trades with their P&L outcomes.
    """
    # Calculate ranges
    mcap_min = current_market_cap * (1 - mcap_tolerance)
    mcap_max = current_market_cap * (1 + mcap_tolerance)
    sol_min = current_sol_amount * (1 - sol_tolerance)
    sol_max = current_sol_amount * (1 + sol_tolerance)
    
    conn = duckdb.connect('pocket_coach.db', read_only=True)
    
    # Query for similar BUY trades
    query = """
        WITH buy_trades AS (
            SELECT 
                timestamp,
                data->>'token_symbol' as token_symbol,
                data->>'token_address' as token_address,
                CAST(data->>'sol_amount' AS DOUBLE) as sol_amount,
                CAST(data->>'token_amount' AS DOUBLE) as token_amount,
                CAST(data->>'market_cap' AS DOUBLE) as market_cap,
                data->>'market_cap_formatted' as market_cap_formatted,
                CAST(data->>'trade_pct_bankroll' AS DOUBLE) as trade_pct_bankroll
            FROM diary
            WHERE wallet_address = ?
            AND entry_type = 'trade'
            AND data->>'action' = 'buy'
            AND CAST(data->>'market_cap' AS DOUBLE) BETWEEN ? AND ?
            AND CAST(data->>'sol_amount' AS DOUBLE) BETWEEN ? AND ?
            AND data->>'token_address' != COALESCE(?, '')  -- Exclude current token
            ORDER BY timestamp DESC
            LIMIT ?
        ),
        -- For each buy, find all related sells
        token_pnl AS (
            SELECT 
                b.token_symbol,
                b.token_address,
                b.timestamp as buy_timestamp,
                b.sol_amount as initial_sol,
                b.market_cap as entry_mcap,
                b.trade_pct_bankroll,
                SUM(CASE WHEN s.data->>'action' = 'sell' THEN CAST(s.data->>'sol_amount' AS DOUBLE) ELSE 0 END) as total_sold_sol,
                COUNT(CASE WHEN s.data->>'action' = 'sell' THEN 1 ELSE NULL END) as sell_count,
                MAX(s.timestamp) as last_sell_timestamp
            FROM buy_trades b
            LEFT JOIN diary s ON s.data->>'token_address' = b.token_address 
                AND s.wallet_address = ?
                AND s.entry_type = 'trade'
                AND s.data->>'action' = 'sell'
                AND s.timestamp > b.timestamp
            GROUP BY b.token_symbol, b.token_address, b.timestamp, 
                     b.sol_amount, b.market_cap, b.trade_pct_bankroll
        )
        SELECT 
            token_symbol,
            token_address,
            buy_timestamp,
            initial_sol,
            total_sold_sol,
            (total_sold_sol - initial_sol) as pnl_sol,
            entry_mcap,
            trade_pct_bankroll,
            sell_count,
            CASE 
                WHEN sell_count = 0 THEN 'HOLDING'
                WHEN total_sold_sol < initial_sol * 0.9 THEN 'PARTIAL'
                ELSE 'CLOSED'
            END as position_status,
            last_sell_timestamp
        FROM token_pnl
        ORDER BY buy_timestamp DESC
    """
    
    results = conn.execute(query, [
        wallet_address, mcap_min, mcap_max, sol_min, sol_max, 
        token_address, limit, wallet_address
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
            'entry_mcap_formatted': format_market_cap(row[6]),
            'trade_pct_bankroll': float(row[7]) if row[7] else None,
            'position_status': row[9],
            'last_sell_timestamp': row[10]
        }
        
        # Calculate hold duration if closed
        if trade['last_sell_timestamp'] and trade['position_status'] == 'CLOSED':
            buy_dt = datetime.fromisoformat(trade['buy_timestamp'])
            sell_dt = datetime.fromisoformat(trade['last_sell_timestamp'])
            duration = sell_dt - buy_dt
            trade['hold_duration_hours'] = duration.total_seconds() / 3600
        
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
    """
    Format similar trades into a coaching message.
    Example: "PONKE (-5.9 SOL), AURA (+4.5 SOL), CRO (-9.8 SOL)"
    """
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
    """Analyze the performance of similar trades to find patterns"""
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

# Example usage for testing
if __name__ == "__main__":
    # Test with sample values
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    # Find trades similar to buying at 3M market cap with 10 SOL
    similar = find_similar_trades(
        wallet_address=wallet,
        current_market_cap=3_000_000,  # 3M
        current_sol_amount=10.0,        # 10 SOL
    )
    
    print(f"Found {len(similar)} similar trades:")
    for trade in similar:
        print(f"\n{trade['token_symbol']} - {trade['entry_mcap_formatted']} mcap, {trade['initial_sol']:.1f} SOL")
        print(f"  Status: {trade['position_status']}")
        if trade['pnl_sol'] is not None:
            print(f"  P&L: {trade['pnl_sol']:+.1f} SOL")
    
    # Get formatted message
    message = format_similar_trades_message(similar)
    print(f"\nFormatted: {message}")
    
    # Analyze pattern
    analysis = analyze_pattern_performance(similar)
    if analysis:
        print(f"\nPattern Analysis:")
        print(f"  Win rate: {analysis['win_rate']*100:.0f}%")
        print(f"  Avg P&L: {analysis['avg_pnl_sol']:+.1f} SOL")