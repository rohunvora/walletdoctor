"""
Personal Trading History Manager
Stores and analyzes individual user trading patterns
"""

import duckdb
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import statistics

logger = logging.getLogger(__name__)

class PersonalHistoryManager:
    """Manages personal trading history and pattern analysis"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    def load_historical_trades(self, wallet_address: str, days: int = 30) -> bool:
        """Load historical trades for a wallet to build baseline patterns"""
        from .data import load_wallet
        
        # Create temporary DB for loading
        temp_db_path = f"/tmp/history_{wallet_address[:8]}_{int(datetime.now().timestamp())}.db"
        temp_db = duckdb.connect(temp_db_path)
        
        try:
            # Initialize schema
            self._init_temp_schema(temp_db)
            
            # Load wallet data
            success = load_wallet(temp_db, wallet_address, mode='instant')
            if not success:
                return False
            
            # Transfer relevant data to main DB
            self._transfer_historical_data(temp_db, wallet_address)
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading historical trades: {e}")
            return False
        finally:
            temp_db.close()
            # Clean up temp file
            import os
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
    
    def _init_temp_schema(self, db):
        """Initialize temporary database schema"""
        db.execute("""
            CREATE TABLE IF NOT EXISTS tx (
                signature VARCHAR,
                timestamp BIGINT,
                fee BIGINT,
                type VARCHAR,
                source VARCHAR,
                slot BIGINT,
                token_mint VARCHAR,
                token_amount DOUBLE,
                native_amount BIGINT,
                from_address VARCHAR,
                to_address VARCHAR,
                transfer_type VARCHAR
            )
        """)
        
        db.execute("""
            CREATE TABLE IF NOT EXISTS pnl (
                mint VARCHAR,
                symbol VARCHAR,
                realizedPnl DOUBLE,
                unrealizedPnl DOUBLE,
                totalPnl DOUBLE,
                avgBuyPrice DOUBLE,
                avgSellPrice DOUBLE,
                quantity DOUBLE,
                totalBought DOUBLE,
                totalSold DOUBLE,
                holdTimeSeconds BIGINT,
                numSwaps INTEGER
            )
        """)
    
    def _transfer_historical_data(self, temp_db, wallet_address: str):
        """Transfer historical data to main database"""
        main_db = duckdb.connect(self.db_path)
        
        try:
            # Get PnL data
            pnl_data = temp_db.execute("""
                SELECT 
                    mint,
                    symbol,
                    totalPnl,
                    totalBought,
                    totalSold,
                    holdTimeSeconds,
                    numSwaps
                FROM pnl
                WHERE totalPnl IS NOT NULL
            """).fetchall()
            
            # Store as historical patterns
            for mint, symbol, pnl, bought, sold, hold_time, swaps in pnl_data:
                # Calculate average trade size
                avg_size = (bought + sold) / (swaps * 2) if swaps > 0 else bought
                
                # Store in user_trades for pattern detection
                main_db.execute("""
                    INSERT INTO user_trades
                    (user_id, wallet_address, tx_signature, timestamp, action,
                     token_address, token_symbol, sol_amount, pnl_usd, 
                     hold_time_minutes, token_amount, entry_price, current_price, pnl_percent)
                    VALUES 
                    (0, ?, ?, CURRENT_TIMESTAMP, 'historical',
                     ?, ?, ?, ?, ?, 0, 0, 0, 0)
                """, [
                    wallet_address,
                    f"historical_{mint[:8]}",  # Fake signature
                    mint,
                    symbol or 'Unknown',
                    avg_size,
                    pnl,
                    (hold_time / 60) if hold_time else 0
                ])
            
            main_db.commit()
            logger.info(f"Transferred {len(pnl_data)} historical trades for {wallet_address}")
            
        except Exception as e:
            logger.error(f"Error transferring historical data: {e}")
        finally:
            main_db.close()
    
    def get_token_history(self, wallet_address: str, token_address: str) -> Dict:
        """Get historical performance for a specific token"""
        db = duckdb.connect(self.db_path)
        
        try:
            result = db.execute("""
                SELECT 
                    COUNT(*) as times_traded,
                    SUM(pnl_usd) as total_pnl,
                    AVG(pnl_usd) as avg_pnl,
                    SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                    AVG(sol_amount) as avg_size,
                    AVG(hold_time_minutes) as avg_hold_time
                FROM user_trades
                WHERE wallet_address = ?
                AND token_address = ?
            """, [wallet_address, token_address]).fetchone()
            
            if result and result[0] > 0:
                times_traded, total_pnl, avg_pnl, wins, avg_size, avg_hold = result
                return {
                    'times_traded': times_traded,
                    'total_pnl': total_pnl or 0,
                    'avg_pnl': avg_pnl or 0,
                    'win_rate': (wins / times_traded) if times_traded > 0 else 0,
                    'avg_size': avg_size or 0,
                    'avg_hold_time': avg_hold or 0
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting token history: {e}")
            return None
        finally:
            db.close()
    
    def get_size_performance(self, wallet_address: str) -> Dict:
        """Analyze performance by position size"""
        db = duckdb.connect(self.db_path)
        
        try:
            # Get average position size
            avg_result = db.execute("""
                SELECT AVG(sol_amount) as avg_size
                FROM user_trades
                WHERE wallet_address = ?
                AND action IN ('buy', 'sell', 'historical')
            """, [wallet_address]).fetchone()
            
            avg_size = avg_result[0] if avg_result and avg_result[0] else 1.0
            
            # Get performance by size buckets
            bucket_results = db.execute("""
                SELECT 
                    CASE 
                        WHEN sol_amount < ? * 0.5 THEN 'small'
                        WHEN sol_amount < ? * 2 THEN 'normal'
                        ELSE 'large'
                    END as size_bucket,
                    COUNT(*) as trades,
                    SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                    AVG(pnl_usd) as avg_pnl
                FROM user_trades
                WHERE wallet_address = ?
                AND action IN ('buy', 'sell', 'historical')
                GROUP BY size_bucket
            """, [avg_size, avg_size, wallet_address]).fetchall()
            
            performance = {
                'avg_size': avg_size,
                'buckets': {}
            }
            
            for bucket, trades, wins, avg_pnl in bucket_results:
                performance['buckets'][bucket] = {
                    'trades': trades,
                    'win_rate': (wins / trades) if trades > 0 else 0,
                    'avg_pnl': avg_pnl or 0
                }
            
            return performance
            
        except Exception as e:
            logger.error(f"Error analyzing size performance: {e}")
            return {'avg_size': 1.0, 'buckets': {}}
        finally:
            db.close()
    
    def get_hold_time_patterns(self, wallet_address: str) -> Dict:
        """Analyze optimal hold times"""
        db = duckdb.connect(self.db_path)
        
        try:
            # Get hold time stats for winners vs losers
            results = db.execute("""
                SELECT 
                    CASE WHEN pnl_usd > 0 THEN 'winner' ELSE 'loser' END as outcome,
                    AVG(hold_time_minutes) as avg_hold,
                    MIN(hold_time_minutes) as min_hold,
                    MAX(hold_time_minutes) as max_hold,
                    COUNT(*) as count
                FROM user_trades
                WHERE wallet_address = ?
                AND hold_time_minutes > 0
                AND action IN ('buy', 'sell', 'historical')
                GROUP BY outcome
            """, [wallet_address]).fetchall()
            
            patterns = {}
            for outcome, avg_hold, min_hold, max_hold, count in results:
                patterns[outcome] = {
                    'avg_hold': avg_hold or 0,
                    'min_hold': min_hold or 0,
                    'max_hold': max_hold or 0,
                    'count': count
                }
            
            # Get performance by hold time buckets
            bucket_results = db.execute("""
                SELECT 
                    CASE 
                        WHEN hold_time_minutes < 10 THEN 'quick'
                        WHEN hold_time_minutes < 60 THEN 'medium'
                        ELSE 'long'
                    END as hold_bucket,
                    COUNT(*) as trades,
                    AVG(pnl_usd) as avg_pnl,
                    SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins
                FROM user_trades
                WHERE wallet_address = ?
                AND hold_time_minutes > 0
                AND action IN ('buy', 'sell', 'historical')
                GROUP BY hold_bucket
            """, [wallet_address]).fetchall()
            
            patterns['buckets'] = {}
            for bucket, trades, avg_pnl, wins in bucket_results:
                patterns['buckets'][bucket] = {
                    'trades': trades,
                    'avg_pnl': avg_pnl or 0,
                    'win_rate': (wins / trades) if trades > 0 else 0
                }
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error analyzing hold time patterns: {e}")
            return {}
        finally:
            db.close()
    
    def store_trade(self, user_id: int, wallet_address: str, trade_data: Dict):
        """Store a new trade in the history"""
        db = duckdb.connect(self.db_path)
        
        try:
            db.execute("""
                INSERT INTO user_trades
                (user_id, wallet_address, tx_signature, timestamp, action,
                 token_address, token_symbol, sol_amount, token_amount,
                 entry_price, current_price, pnl_usd, pnl_percent, 
                 hold_time_minutes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                user_id,
                wallet_address,
                trade_data.get('tx_signature'),
                trade_data.get('timestamp', datetime.now()),
                trade_data.get('action'),
                trade_data.get('token_address'),
                trade_data.get('token_symbol', 'Unknown'),
                trade_data.get('sol_amount', 0),
                trade_data.get('token_amount', 0),
                trade_data.get('entry_price', 0),
                trade_data.get('current_price', 0),
                trade_data.get('pnl_usd', 0),
                trade_data.get('pnl_percent', 0),
                trade_data.get('hold_time_minutes', 0)
            ])
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error storing trade: {e}")
        finally:
            db.close()
    
    def get_recent_patterns(self, wallet_address: str, hours: int = 24) -> List[Dict]:
        """Get recent trading patterns for real-time analysis"""
        db = duckdb.connect(self.db_path)
        
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            patterns = []
            
            # Check for repeat tokens in recent trades
            repeat_tokens = db.execute("""
                SELECT 
                    token_address,
                    token_symbol,
                    COUNT(*) as count,
                    SUM(pnl_usd) as total_pnl
                FROM user_trades
                WHERE wallet_address = ?
                AND timestamp > ?
                GROUP BY token_address, token_symbol
                HAVING count > 1
                ORDER BY count DESC
            """, [wallet_address, cutoff_time]).fetchall()
            
            for token, symbol, count, pnl in repeat_tokens:
                patterns.append({
                    'type': 'repeat_trading',
                    'token': token,
                    'symbol': symbol,
                    'count': count,
                    'pnl': pnl or 0
                })
            
            # Check for increasing position sizes
            size_trend = db.execute("""
                SELECT 
                    sol_amount,
                    timestamp,
                    ROW_NUMBER() OVER (ORDER BY timestamp) as trade_num
                FROM user_trades
                WHERE wallet_address = ?
                AND timestamp > ?
                AND action = 'buy'
                ORDER BY timestamp DESC
                LIMIT 5
            """, [wallet_address, cutoff_time]).fetchall()
            
            if len(size_trend) >= 3:
                sizes = [s[0] for s in size_trend]
                if sizes[0] > sizes[-1] * 2:  # Recent size 2x older
                    patterns.append({
                        'type': 'size_increase',
                        'recent_size': sizes[0],
                        'older_size': sizes[-1],
                        'multiplier': sizes[0] / sizes[-1] if sizes[-1] > 0 else 0
                    })
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error getting recent patterns: {e}")
            return []
        finally:
            db.close() 