"""
Fixed diary API function for the annotator
"""

import json
import logging
import duckdb
from typing import List, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def format_market_cap_short(mcap):
    """Format market cap for display"""
    if not mcap or mcap == 0:
        return "Unknown"
    
    if mcap >= 1_000_000_000:
        return f"${mcap/1_000_000_000:.1f}B"
    elif mcap >= 1_000_000:
        return f"${mcap/1_000_000:.1f}M"
    elif mcap >= 1_000:
        return f"${mcap/1_000:.0f}K"
    else:
        return f"${mcap:.0f}"


async def get_notable_trades(wallet: str, days: int = 30, max_trades: int = 7) -> List[Dict]:
    """Get notable individual trades for annotation - each SELL is a complete trade story"""
    
    # Validate wallet
    if not wallet:
        logger.warning("No wallet address provided to get_notable_trades")
        return []
    
    try:
        # First check if wallet exists in our system
        db = duckdb.connect('pocket_coach.db')
        wallet_check = db.execute("""
            SELECT COUNT(*) FROM diary 
            WHERE wallet_address = ? 
            LIMIT 1
        """, [wallet]).fetchone()
        
        if not wallet_check or wallet_check[0] == 0:
            db.close()
            return []
        
        # Get date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Fetch all SELL trades in date range
        results = db.execute("""
            SELECT 
                data,
                timestamp
            FROM diary 
            WHERE wallet_address = ? 
            AND entry_type = 'trade'
            AND json_extract_string(data, '$.action') = 'SELL'
            AND timestamp >= ?
            ORDER BY timestamp DESC
        """, [wallet, start_date]).fetchall()
        
        all_trades = []
        for row in results:
            trade_data = json.loads(row[0])
            trade_data['actual_timestamp'] = row[1]
            trade_data['exit_date'] = row[1].strftime('%Y-%m-%d')
            
            # Extract key data points
            trade_info = {
                'token': trade_data.get('token_symbol', 'Unknown'),
                'exit_date': trade_data['exit_date'],
                'exit_timestamp': row[1],
                'sol_received': trade_data.get('sol_amount', 0),
                'exit_usd': trade_data.get('trade_size_usd', trade_data.get('sol_amount', 0) * 140),
                'exit_mcap': trade_data.get('market_cap'),
                'exit_mcap_formatted': format_market_cap_short(trade_data.get('market_cap'))
            }
            
            # Add entry data if available from Cielo
            if 'avg_buy_price' in trade_data and trade_data.get('avg_buy_price', 0) > 0:
                # Calculate entry value in USD
                avg_sell_price = trade_data.get('avg_sell_price', 1)
                avg_buy_price = trade_data.get('avg_buy_price', 1)
                if avg_buy_price > 0:
                    price_ratio = avg_sell_price / avg_buy_price
                    if price_ratio > 0:
                        sol_invested = trade_data.get('sol_amount', 0) / price_ratio
                        trade_info['entry_usd'] = sol_invested * trade_data.get('sol_price_usd', 140)
                        trade_info['avg_buy_price'] = trade_data['avg_buy_price']
            
            # Add entry market cap if available
            if 'entry_market_cap' in trade_data:
                trade_info['entry_mcap'] = trade_data['entry_market_cap']
                trade_info['entry_mcap_formatted'] = trade_data.get('entry_market_cap_formatted', format_market_cap_short(trade_data['entry_market_cap']))
            elif 'market_cap_multiplier' in trade_data and trade_data.get('market_cap') and trade_data.get('market_cap_multiplier', 0) > 0:
                # Calculate entry mcap from multiplier
                entry_mcap = trade_data['market_cap'] / trade_data['market_cap_multiplier']
                trade_info['entry_mcap'] = entry_mcap
                trade_info['entry_mcap_formatted'] = format_market_cap_short(entry_mcap)
            
            # Add P&L data (prioritize validated data)
            if 'pnl_validated' in trade_data:
                pnl_data = trade_data['pnl_validated']
                trade_info['pnl_usd'] = pnl_data.get('calculated_pnl', 0)
                trade_info['pnl_pct'] = pnl_data.get('roi_percentage', 0)
            elif 'realized_pnl_usd' in trade_data:
                trade_info['pnl_usd'] = trade_data['realized_pnl_usd']
                trade_info['pnl_pct'] = trade_data.get('roi_percentage', 0)
            
            # Add hold time
            if 'hold_time_seconds' in trade_data:
                trade_info['held_days'] = max(1, int(trade_data['hold_time_seconds'] / 86400))
            else:
                trade_info['held_days'] = 1  # Default
            
            all_trades.append(trade_info)
        
        db.close()
        
        if not all_trades:
            return []
        
        # Select notable trades
        notable = []
        
        # 1. Biggest winner
        winners = [t for t in all_trades if t.get('pnl_pct', 0) > 0]
        if winners:
            biggest_winner = max(winners, key=lambda x: x.get('pnl_pct', 0))
            biggest_winner['selection_reason'] = 'biggest_winner'
            notable.append(biggest_winner)
        
        # 2. Biggest loser  
        losers = [t for t in all_trades if t.get('pnl_pct', 0) < 0]
        if losers:
            biggest_loser = min(losers, key=lambda x: x.get('pnl_pct', 0))
            biggest_loser['selection_reason'] = 'biggest_loser'
            notable.append(biggest_loser)
        
        # 3. Largest trade by USD
        if all_trades:
            largest = max(all_trades, key=lambda x: x.get('exit_usd', 0))
            if largest not in notable:
                largest['selection_reason'] = 'largest_trade'
                notable.append(largest)
        
        # 4. Most recent trade
        if all_trades:
            recent = all_trades[0]  # Already sorted by timestamp DESC
            if recent not in notable:
                recent['selection_reason'] = 'most_recent'
                notable.append(recent)
        
        # 5. Quick flip (held < 2 days with good P&L)
        quick_trades = [t for t in all_trades if t.get('held_days', 0) <= 2 and abs(t.get('pnl_pct', 0)) > 20]
        if quick_trades:
            quick_flip = max(quick_trades, key=lambda x: abs(x.get('pnl_pct', 0)))
            if quick_flip not in notable:
                quick_flip['selection_reason'] = 'quick_flip'
                notable.append(quick_flip)
        
        # 6. Diamond hands (held > 7 days)
        long_holds = [t for t in all_trades if t.get('held_days', 0) > 7]
        if long_holds:
            diamond = max(long_holds, key=lambda x: x.get('held_days', 0))
            if diamond not in notable:
                diamond['selection_reason'] = 'diamond_hands'
                notable.append(diamond)
        
        # 7. Biggest mcap multiplier
        mcap_trades = [t for t in all_trades if 'entry_mcap' in t and 'exit_mcap' in t and t['entry_mcap'] > 0]
        if mcap_trades:
            for t in mcap_trades:
                t['mcap_multiplier'] = t['exit_mcap'] / t['entry_mcap']
            best_mcap = max(mcap_trades, key=lambda x: x['mcap_multiplier'])
            if best_mcap not in notable and best_mcap['mcap_multiplier'] > 2:
                best_mcap['selection_reason'] = 'mcap_multiplier'
                notable.append(best_mcap)
        
        # Format for display
        formatted_trades = []
        for i, trade in enumerate(notable[:max_trades]):
            formatted = {
                'index': i + 1,
                'token': trade['token'],
                'exit_date': trade['exit_date'],
                'entry_usd': trade.get('entry_usd', trade.get('exit_usd', 0) / max(0.01, 1 + trade.get('pnl_pct', 0) / 100)),
                'exit_usd': trade['exit_usd'],
                'entry_mcap_formatted': trade.get('entry_mcap_formatted', 'Unknown'),
                'exit_mcap_formatted': trade['exit_mcap_formatted'],
                'pnl_pct': trade.get('pnl_pct', 0),
                'pnl_usd': trade.get('pnl_usd', 0),
                'held_days': trade['held_days'],
                'selection_reason': trade['selection_reason']
            }
            
            formatted_trades.append(formatted)
        
        return formatted_trades
        
    except Exception as e:
        logger.error(f"Error getting notable trades: {e}")
        return []