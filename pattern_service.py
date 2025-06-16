"""
Pattern Service - REST-ready pattern detection service
Can be called by rules today, AI tomorrow
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import statistics
import logging
import duckdb

logger = logging.getLogger(__name__)

class PatternService:
    """REST-ready pattern detection service"""
    
    def __init__(self, db_connection=None, pnl_service=None, db_path=None):
        if db_connection:
            self.db = db_connection
            self.db_path = None
        elif db_path:
            self.db_path = db_path
            self.db = None
        else:
            # Default for when called from bot
            self.db = None
            self.db_path = "pocket_coach.db"
        self.pnl_service = pnl_service
    
    def _get_db(self):
        """Get database connection, creating new one if using db_path"""
        if self.db:
            return self.db
        elif self.db_path:
            return duckdb.connect(self.db_path)
        else:
            raise ValueError("No database connection or path available")
    
    async def detect(self, trade_context: Dict) -> List[Dict]:
        """
        Main pattern detection endpoint
        
        Args:
            trade_context: {
                "user_id": int,
                "wallet_address": str,
                "token_address": str,
                "token_symbol": str,
                "sol_amount": float,
                "action": str,  # "BUY" or "SELL"
                "timestamp": datetime
            }
        
        Returns:
            List of detected patterns with their data
        """
        patterns = []
        
        try:
            # Check immediate patterns (no history needed)
            immediate_pattern = self.check_immediate_patterns(trade_context)
            if immediate_pattern:
                patterns.append(immediate_pattern)
            
            # Check position size pattern
            size_pattern = await self.check_position_size(trade_context)
            if size_pattern:
                patterns.append(size_pattern)
            
            # Check repeat token pattern
            repeat_pattern = await self.check_repeat_token(trade_context)
            if repeat_pattern:
                patterns.append(repeat_pattern)
            
            # Check hold time pattern (for existing positions)
            hold_pattern = await self.check_hold_time(trade_context)
            if hold_pattern:
                patterns.append(hold_pattern)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error in pattern detection: {e}")
            return []
    
    def check_immediate_patterns(self, context: Dict) -> Optional[Dict]:
        """Check patterns that don't require trading history"""
        sol_amount = context["sol_amount"]
        token_symbol = context["token_symbol"]
        action = context["action"]
        
        # Dust trade pattern
        if sol_amount < 0.1:
            return {
                "type": "dust_trade",
                "confidence": 0.9,
                "data": {
                    "sol_amount": sol_amount,
                    "action": action,
                    "token_symbol": token_symbol
                }
            }
        
        # Round number pattern (often emotional)
        if sol_amount > 5 and sol_amount % 5 == 0:
            return {
                "type": "round_number", 
                "confidence": 0.7,
                "data": {
                    "sol_amount": sol_amount,
                    "action": action,
                    "token_symbol": token_symbol
                }
            }
        
        # Late night trading pattern
        hour = datetime.now().hour
        if hour >= 2 and hour <= 6:
            return {
                "type": "late_night",
                "confidence": 0.8,
                "data": {
                    "hour": hour,
                    "action": action,
                    "token_symbol": token_symbol
                }
            }
        
        return None
    
    async def check_position_size(self, context: Dict) -> Optional[Dict]:
        """Check if position size is unusual compared to user's average"""
        try:
            db = self._get_db()
            wallet_address = context["wallet_address"]
            sol_amount = context["sol_amount"]
            
            # Get user's average position size
            result = db.execute("""
                SELECT AVG(sol_amount) as avg_sol
                FROM user_trades
                WHERE wallet_address = ?
                AND action IN ('BUY', 'SELL')
            """, [wallet_address]).fetchone()
            
            avg_size = result[0] if result and result[0] else 2.0  # Default market average
            
            # Check if significantly larger than average
            if sol_amount > avg_size * 2.5:
                # Get historical performance with large positions
                performance_data = db.execute("""
                    SELECT 
                        COUNT(*) as total_large,
                        SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins_large
                    FROM user_trades
                    WHERE wallet_address = ?
                    AND sol_amount > ?
                """, [wallet_address, avg_size * 2]).fetchone()
                
                pattern_data = {
                    "ratio": sol_amount / avg_size,
                    "avg_size": avg_size,
                    "current_size": sol_amount,
                    "token_symbol": context["token_symbol"],
                    "action": context["action"]
                }
                
                if performance_data and performance_data[0] > 0:
                    win_rate = performance_data[1] / performance_data[0]
                    pattern_data.update({
                        "large_position_win_rate": win_rate,
                        "historical_large_trades": performance_data[0]
                    })
                
                return {
                    "type": "position_size",
                    "confidence": 0.85,
                    "data": pattern_data
                }
            
            # Close if we created a new connection
            if not self.db:
                db.close()
        
        except Exception as e:
            logger.error(f"Error checking position size: {e}")
        
        return None
    
    async def check_repeat_token(self, context: Dict) -> Optional[Dict]:
        """Check if user has traded this token before"""
        try:
            wallet_address = context["wallet_address"]
            token_address = context["token_address"]
            token_symbol = context["token_symbol"]
            action = context["action"]
            
            # Try P&L service first if available
            if self.pnl_service:
                try:
                    pnl_data = await self.pnl_service.get_token_pnl_data(wallet_address, token_address)
                    
                    if pnl_data and pnl_data.get('total_trades', 0) > 0:
                        return {
                            "type": "repeat_token",
                            "confidence": 0.9,
                            "data": {
                                "times_traded": pnl_data['total_trades'],
                                "total_pnl": pnl_data['realized_pnl_usd'],
                                "win_rate": pnl_data['win_rate'],
                                "token_symbol": pnl_data['token_symbol'],
                                "has_open_position": pnl_data.get('has_open_position', False),
                                "unrealized_pnl_usd": pnl_data.get('unrealized_pnl_usd', 0),
                                "action": action
                            }
                        }
                except Exception as e:
                    logger.warning(f"P&L service failed, using local database fallback: {e}")
            
            # Always try local database fallback
            db = self._get_db()
            result = db.execute("""
                SELECT 
                    COUNT(*) as times_traded,
                    COALESCE(SUM(pnl_usd), 0) as total_pnl,
                    SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                    MIN(token_symbol) as symbol
                FROM user_trades
                WHERE wallet_address = ?
                AND token_address = ?
                AND timestamp < CURRENT_TIMESTAMP
            """, [wallet_address, token_address]).fetchone()
            
            # Close if we created a new connection
            if not self.db:
                db.close()
            
            if result and result[0] >= 1:
                times_traded, total_pnl, wins, symbol = result
                win_rate = wins / times_traded if times_traded > 0 else 0
                
                return {
                    "type": "repeat_token",
                    "confidence": 0.8,
                    "data": {
                        "times_traded": times_traded,
                        "total_pnl": total_pnl or 0,
                        "win_rate": win_rate,
                        "token_symbol": symbol or token_symbol,
                        "action": action
                    }
                }
        
        except Exception as e:
            logger.error(f"Error checking repeat token: {e}")
        
        return None
    
    async def check_hold_time(self, context: Dict) -> Optional[Dict]:
        """Check if holding past typical exit window"""
        try:
            wallet_address = context["wallet_address"]
            token_address = context["token_address"]
            
            # Only check hold time for existing positions
            if context["action"] != "SELL":
                return None
            
            # Get user's typical hold times for winners
            db = self._get_db()
            winner_holds = db.execute("""
                SELECT hold_time_minutes
                FROM user_trades
                WHERE wallet_address = ?
                AND pnl_usd > 0
                AND hold_time_minutes > 0
            """, [wallet_address]).fetchall()
            
            # Close if we created a new connection
            if not self.db:
                db.close()
            
            if not winner_holds:
                return None
            
            hold_times = [h[0] for h in winner_holds]
            avg_winner_hold = statistics.mean(hold_times)
            
            # Check current position entry time (simplified - would need actual tracking)
            # For now, return pattern if we have enough data
            if len(hold_times) >= 3:
                return {
                    "type": "hold_time",
                    "confidence": 0.6,
                    "data": {
                        "typical_winner_exit": avg_winner_hold,
                        "token_symbol": context["token_symbol"]
                    }
                }
        
        except Exception as e:
            logger.error(f"Error checking hold time: {e}")
        
        return None
    
    def get_user_baselines(self, wallet_address: str) -> Dict:
        """Get user's trading baselines for pattern detection"""
        try:
            db = self._get_db()
            
            # Average position size
            avg_result = db.execute("""
                SELECT AVG(sol_amount) as avg_sol
                FROM user_trades
                WHERE wallet_address = ?
            """, [wallet_address]).fetchone()
            
            avg_position_size = avg_result[0] if avg_result and avg_result[0] else 1.0
            
            # Winner hold times
            winner_holds = db.execute("""
                SELECT hold_time_minutes
                FROM user_trades
                WHERE wallet_address = ?
                AND pnl_usd > 0
                AND hold_time_minutes > 0
            """, [wallet_address]).fetchall()
            
            # Close if we created a new connection
            if not self.db:
                db.close()
            
            hold_times = [h[0] for h in winner_holds if h[0]]
            avg_winner_hold = statistics.mean(hold_times) if hold_times else 0
            
            return {
                "avg_position_size": avg_position_size,
                "avg_winner_hold_minutes": avg_winner_hold,
                "total_trades": len(winner_holds)
            }
            
        except Exception as e:
            logger.error(f"Error getting user baselines: {e}")
            return {
                "avg_position_size": 1.0,
                "avg_winner_hold_minutes": 0,
                "total_trades": 0
            }


# Factory function for REST endpoint usage
def create_pattern_service(db_connection=None, pnl_service=None, db_path=None) -> PatternService:
    """Create pattern service instance"""
    return PatternService(db_connection, pnl_service, db_path) 