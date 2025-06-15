#!/usr/bin/env python3
"""
Instant stats generation for quick feedback
Works with both 'trades' and 'pnl' table schemas
"""

import duckdb
from typing import Dict, List, Any
from datetime import datetime, timedelta

class InstantStatsGenerator:
    def __init__(self, db_connection):
        self.db = db_connection
        # Check which table exists
        tables = [t[0] for t in self.db.execute("SHOW TABLES").fetchall()]
        
        if 'trades' in tables:
            self.table_name = 'trades'
            self.pnl_column = 'realizedPnl'
        elif 'pnl' in tables:
            self.table_name = 'pnl'
            self.pnl_column = 'totalPnl'  # or realizedProfit, check schema
        else:
            # Create trades table if neither exists
            self.create_trades_table()
            self.table_name = 'trades'
            self.pnl_column = 'realizedPnl'
    
    def create_trades_table(self):
        """Create trades table if it doesn't exist"""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                wallet VARCHAR,
                symbol VARCHAR,
                realizedPnl DOUBLE,
                timestamp TIMESTAMP,
                quantity DOUBLE,
                entryPrice DOUBLE,
                exitPrice DOUBLE
            )
        """)
        
    def get_baseline_stats(self) -> Dict[str, Any]:
        """Get quick baseline statistics"""
        # First, let's check what columns exist in our table
        try:
            if self.table_name == 'pnl':
                # For pnl table, check actual column names
                columns = self.db.execute(f"DESCRIBE {self.table_name}").fetchall()
                col_names = [col[0] for col in columns]
                
                # Find the right PnL column
                if 'totalPnl' in col_names:
                    self.pnl_column = 'totalPnl'
                elif 'realizedProfit' in col_names:
                    self.pnl_column = 'realizedProfit'
                elif 'realizedPnl' in col_names:
                    self.pnl_column = 'realizedPnl'
        except:
            pass
            
        # Get basic stats
        stats_query = f"""
        SELECT 
            COUNT(*) as total_trades,
            COUNT(CASE WHEN {self.pnl_column} > 0 THEN 1 END) as winning_trades,
            COUNT(CASE WHEN {self.pnl_column} < 0 THEN 1 END) as losing_trades,
            COALESCE(SUM({self.pnl_column}), 0) as total_pnl,
            COALESCE(AVG({self.pnl_column}), 0) as avg_pnl
        FROM {self.table_name}
        WHERE {self.pnl_column} IS NOT NULL
        """
        
        result = self.db.execute(stats_query).fetchone()
        
        if result and result[0] > 0:
            total_trades, winning_trades, losing_trades, total_pnl, avg_pnl = result
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        else:
            # No trades found, return zeros
            total_trades = 0
            winning_trades = 0
            losing_trades = 0
            total_pnl = 0
            avg_pnl = 0
            win_rate = 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl
        }
    
    def get_top_trades(self, limit: int = 5) -> Dict[str, List[Dict]]:
        """Get top winning and losing trades"""
        result = {'winners': [], 'losers': []}
        
        try:
            # Get symbol column name - both tables use 'symbol'
            symbol_col = 'symbol'
            
            # Top winners
            winners_query = f"""
            SELECT {symbol_col} as symbol, {self.pnl_column} as realizedPnl
            FROM {self.table_name}
            WHERE {self.pnl_column} > 0
            ORDER BY {self.pnl_column} DESC
            LIMIT {limit}
            """
            
            winners = self.db.execute(winners_query).fetchall()
            result['winners'] = [
                {'symbol': row[0], 'realizedPnl': row[1]} 
                for row in winners
            ]
            
            # Top losers
            losers_query = f"""
            SELECT {symbol_col} as symbol, {self.pnl_column} as realizedPnl
            FROM {self.table_name}
            WHERE {self.pnl_column} < 0
            ORDER BY {self.pnl_column} ASC
            LIMIT {limit}
            """
            
            losers = self.db.execute(losers_query).fetchall()
            result['losers'] = [
                {'symbol': row[0], 'realizedPnl': row[1]} 
                for row in losers
            ]
        except Exception as e:
            print(f"Error getting top trades: {e}")
            
        return result
        
    def get_recent_trades(self, days: int = 7) -> List[Dict]:
        """Get recent trades"""
        try:
            symbol_col = 'symbol'
            time_col = 'timestamp' if self.table_name == 'trades' else 'timestamp'
            
            # Check if timestamp column exists
            columns = self.db.execute(f"DESCRIBE {self.table_name}").fetchall()
            col_names = [col[0] for col in columns]
            
            if time_col not in col_names:
                # No timestamp, just get latest trades
                query = f"""
                SELECT {symbol_col} as symbol, {self.pnl_column} as realizedPnl
                FROM {self.table_name}
                WHERE {self.pnl_column} IS NOT NULL
                ORDER BY ABS({self.pnl_column}) DESC
                LIMIT 20
                """
            else:
                cutoff = datetime.now() - timedelta(days=days)
                query = f"""
                SELECT {symbol_col} as symbol, {self.pnl_column} as realizedPnl, {time_col} as timestamp
                FROM {self.table_name}
                WHERE {time_col} > '{cutoff}'
                ORDER BY {time_col} DESC
                """
            
            results = self.db.execute(query).fetchall()
            
            trades = []
            for row in results:
                trade = {
                    'symbol': row[0],
                    'realizedPnl': row[1]
                }
                if len(row) > 2:
                    trade['timestamp'] = row[2]
                trades.append(trade)
                
            return trades
            
        except Exception as e:
            print(f"Error getting recent trades: {e}")
            return []

    def get_recent_performance(self, days: int = 7) -> Dict[str, Any]:
        """Get recent performance trends without heavy analysis."""
        # For MVP, we'll use the last N trades as proxy for recency
        # In production, would filter by actual timestamps
        pnl_df = self.db.execute("SELECT * FROM pnl").df()
        
        if pnl_df.empty:
            return {'has_recent': False}
        
        # Take last 20% of trades as "recent" for MVP
        recent_count = max(1, int(len(pnl_df) * 0.2))
        recent_trades = pnl_df.tail(recent_count)
        
        recent_win_rate = (len(recent_trades[recent_trades['realizedPnl'] > 0]) / 
                          len(recent_trades) * 100)
        recent_avg_pnl = recent_trades['realizedPnl'].mean()
        
        return {
            'has_recent': True,
            'recent_trades': len(recent_trades),
            'recent_win_rate': recent_win_rate,
            'recent_avg_pnl': recent_avg_pnl,
            'trend': 'improving' if recent_win_rate > self.get_baseline_stats()['win_rate'] else 'declining'
        }
    
    def format_for_display(self, stats: Dict[str, Any], top_trades: Dict[str, List[Dict]]) -> str:
        """Format stats for clean display."""
        if not stats.get('has_data'):
            return stats.get('message', 'No data available')
        
        output = []
        output.append("📊 YOUR TRADING BASELINE")
        output.append("=" * 40)
        output.append(f"Win Rate: {stats['win_rate']:.1f}% ({stats['winning_trades']}W / {stats['losing_trades']}L)")
        output.append(f"Average P&L: ${stats['avg_pnl']:+,.2f}")
        output.append(f"Total P&L: ${stats['total_pnl']:+,.2f}")
        output.append(f"Avg Position Size: ${stats['avg_position_size']:,.2f}")
        output.append("")
        
        # Top trades
        if top_trades['winners']:
            output.append("🏆 Top Winners:")
            for t in top_trades['winners']:
                hold_time = f"{t['holdTimeSeconds']/60:.0f}min" if t['holdTimeSeconds'] < 3600 else f"{t['holdTimeSeconds']/3600:.1f}hr"
                output.append(f"  • {t['symbol']}: +${t['realizedPnl']:,.2f} ({hold_time})")
        
        if top_trades['losers']:
            output.append("\n💀 Biggest Losses:")
            for t in top_trades['losers']:
                hold_time = f"{t['holdTimeSeconds']/60:.0f}min" if t['holdTimeSeconds'] < 3600 else f"{t['holdTimeSeconds']/3600:.1f}hr"
                output.append(f"  • {t['symbol']}: -${abs(t['realizedPnl']):,.2f} ({hold_time})")
        
        return "\n".join(output)
    
    def get_rich_patterns_for_ai(self) -> Dict[str, Any]:
        """Extract rich patterns that make AI analysis actually smart."""
        pnl_df = self.db.execute("SELECT * FROM pnl").df()
        
        if pnl_df.empty:
            return {}
            
        # Calculate entry/exit prices relative to position
        pnl_df['entry_size_usd'] = pnl_df['totalBought'] * pnl_df['avgBuyPrice']
        pnl_df['exit_size_usd'] = pnl_df['totalSold'] * pnl_df['avgSellPrice']
        pnl_df['pnl_percent'] = (pnl_df['realizedPnl'] / pnl_df['entry_size_usd'] * 100)
        
        patterns = {}
        
        # 1. Revenge Trading Pattern - consecutive losses
        pnl_df['is_loss'] = pnl_df['realizedPnl'] < 0
        consecutive_losses = []
        current_streak = []
        
        for idx, row in pnl_df.iterrows():
            if row['is_loss']:
                current_streak.append(row)
            else:
                if len(current_streak) >= 3:
                    consecutive_losses.append(current_streak)
                current_streak = []
        
        if consecutive_losses:
            worst_streak = max(consecutive_losses, key=len)
            patterns['revenge_trading'] = {
                'streak_length': len(worst_streak),
                'total_loss': sum(t['realizedPnl'] for t in worst_streak),
                'tokens': [t['symbol'] for t in worst_streak],
                'avg_hold_time': sum(t['holdTimeSeconds'] for t in worst_streak) / len(worst_streak) / 3600
            }
        
        # 2. FOMO Pattern - big positions on volatile tokens
        volatile_trades = pnl_df[pnl_df['numSwaps'] > 5].copy()
        if len(volatile_trades) > 0:
            volatile_trades['position_vs_avg'] = volatile_trades['entry_size_usd'] / pnl_df['entry_size_usd'].mean()
            fomo_trades = volatile_trades[volatile_trades['position_vs_avg'] > 2]
            
            if len(fomo_trades) > 0:
                patterns['fomo_pattern'] = {
                    'count': len(fomo_trades),
                    'avg_loss': fomo_trades['realizedPnl'].mean(),
                    'biggest_fomo': {
                        'token': fomo_trades.iloc[0]['symbol'],
                        'size': fomo_trades.iloc[0]['entry_size_usd'],
                        'loss': fomo_trades.iloc[0]['realizedPnl'],
                        'swaps': fomo_trades.iloc[0]['numSwaps']
                    }
                }
        
        # 3. Shitcoin Addiction - pattern in token names
        shitcoin_keywords = ['INU', 'DOGE', 'PEPE', 'MOON', 'SAFE', 'BABY', 'ELON', 'SHIB', 'FLOKI']
        pattern = '|'.join(shitcoin_keywords)
        shitcoins = pnl_df[pnl_df['symbol'].str.contains(pattern, case=False, na=False)]
        
        if len(shitcoins) > 0:
            patterns['shitcoin_addiction'] = {
                'count': len(shitcoins),
                'total_invested': shitcoins['entry_size_usd'].sum(),
                'total_loss': shitcoins[shitcoins['realizedPnl'] < 0]['realizedPnl'].sum(),
                'win_rate': (len(shitcoins[shitcoins['realizedPnl'] > 0]) / len(shitcoins) * 100),
                'worst_shitcoins': shitcoins.nsmallest(3, 'realizedPnl')[['symbol', 'realizedPnl']].to_dict('records')
            }
        
        # 4. Bag Holder Pattern - holding losers too long
        losers = pnl_df[pnl_df['realizedPnl'] < 0]
        winners = pnl_df[pnl_df['realizedPnl'] > 0]
        
        if len(losers) > 5 and len(winners) > 5:
            patterns['bag_holding'] = {
                'avg_loser_hold_hours': losers['holdTimeSeconds'].mean() / 3600,
                'avg_winner_hold_hours': winners['holdTimeSeconds'].mean() / 3600,
                'longest_held_loser': {
                    'token': losers.nlargest(1, 'holdTimeSeconds').iloc[0]['symbol'],
                    'hold_hours': losers.nlargest(1, 'holdTimeSeconds').iloc[0]['holdTimeSeconds'] / 3600,
                    'loss': losers.nlargest(1, 'holdTimeSeconds').iloc[0]['realizedPnl']
                }
            }
        
        # 5. Size Mismanagement - biggest positions are biggest losses
        top_positions = pnl_df.nlargest(10, 'entry_size_usd')
        position_losses = top_positions[top_positions['realizedPnl'] < 0]
        
        if len(position_losses) > 3:
            patterns['size_mismanagement'] = {
                'big_position_loss_rate': len(position_losses) / len(top_positions) * 100,
                'total_big_position_losses': position_losses['realizedPnl'].sum(),
                'worst_big_bet': {
                    'token': position_losses.iloc[0]['symbol'],
                    'size': position_losses.iloc[0]['entry_size_usd'],
                    'loss': position_losses.iloc[0]['realizedPnl'],
                    'percent_loss': position_losses.iloc[0]['pnl_percent']
                }
            }
        
        return patterns 