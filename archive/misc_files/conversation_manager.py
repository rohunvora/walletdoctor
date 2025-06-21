"""
Conversation Manager - Handles responses, memory, and learning
Stores raw user responses for future AI training
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json
import logging
import duckdb

logger = logging.getLogger(__name__)

class ConversationManager:
    """Manages conversation state, responses, and memory"""
    
    def __init__(self, db_connection=None, db_path=None):
        if db_connection:
            self.db = db_connection
            self.db_path = None
        elif db_path:
            self.db_path = db_path
            self.db = None
        else:
            raise ValueError("Must provide either db_connection or db_path")
        
        self.pending_responses = {}  # user_id -> trade_context
        self._ensure_schema()
    
    def _get_db(self):
        """Get database connection, creating new one if using db_path"""
        if self.db:
            return self.db
        elif self.db_path:
            return duckdb.connect(self.db_path)
        else:
            raise ValueError("No database connection or path available")
    
    def _ensure_schema(self):
        """Ensure conversation tables exist"""
        try:
            db = self._get_db()
            
            # Trade notes table with raw storage and thread support
            db.execute("""
                CREATE TABLE IF NOT EXISTS trade_notes (
                    id INTEGER PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    trade_id TEXT NOT NULL,
                    thread_id TEXT,
                    token_address TEXT,
                    token_symbol TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    pattern_type TEXT,
                    user_response TEXT,  -- Raw text, no enums!
                    response_type TEXT CHECK(response_type IN ('button', 'freetext')),
                    metadata JSON,       -- Flexible context for AI
                    confidence REAL DEFAULT 1.0
                )
            """)
            
            # Add index for thread queries
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_trade_notes_thread_id 
                ON trade_notes(thread_id)
            """)
            
            # User vocabulary tracking
            db.execute("""
                CREATE TABLE IF NOT EXISTS user_vocabulary (
                    id INTEGER PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    phrase TEXT NOT NULL,
                    pattern_type TEXT,
                    frequency INTEGER DEFAULT 1,
                    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, phrase, pattern_type)
                )
            """)
            
            db.commit()
            
            # Close if we created a new connection
            if not self.db:
                db.close()
            
        except Exception as e:
            logger.error(f"Error ensuring conversation schema: {e}")
    
    async def store_response(self, user_id: int, trade_id: str, response: str, 
                           metadata: Dict, thread_id: str = None) -> bool:
        """Store user response with flexible metadata and thread support"""
        try:
            db = self._get_db()
            
            # Use trade_id as default thread_id for backward compatibility
            if thread_id is None:
                thread_id = trade_id
            
            # Store raw response
            db.execute("""
                INSERT INTO trade_notes 
                (user_id, trade_id, thread_id, token_address, token_symbol, pattern_type, 
                 user_response, response_type, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                user_id,
                trade_id,
                thread_id,
                metadata.get('token_address'),
                metadata.get('token_symbol'),
                metadata.get('pattern_type'),
                response,
                metadata.get('response_type', 'button'),
                json.dumps(metadata)
            ])
            
            # Update vocabulary tracking
            await self._update_vocabulary(user_id, response, metadata.get('pattern_type'))
            
            db.commit()
            
            # Close if we created a new connection
            if not self.db:
                db.close()
            
            logger.info(f"Stored response for user {user_id}: {response}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing response: {e}")
            return False
    
    async def _update_vocabulary(self, user_id: int, response: str, pattern_type: str = None):
        """Track user vocabulary for adaptive buttons"""
        try:
            db = self._get_db()
            
            # Clean and extract key phrases
            phrases = self._extract_phrases(response)
            
            for phrase in phrases:
                # Update or insert vocabulary entry
                db.execute("""
                    INSERT INTO user_vocabulary (user_id, phrase, pattern_type, frequency)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT (user_id, phrase, pattern_type) 
                    DO UPDATE SET 
                        frequency = frequency + 1,
                        last_used = CURRENT_TIMESTAMP
                """, [user_id, phrase, pattern_type])
            
            # Close if we created a new connection
            if not self.db:
                db.close()
            
        except Exception as e:
            logger.error(f"Error updating vocabulary: {e}")
    
    def _extract_phrases(self, response: str) -> List[str]:
        """Extract meaningful phrases from user response"""
        # Simple phrase extraction - can be enhanced with NLP
        phrases = []
        
        # Clean response
        cleaned = response.lower().strip()
        
        # Common trading phrases to track
        trading_terms = [
            'fomo', 'alpha', 'aping', 'degen', 'moon', 'bag', 'scalp', 'hold',
            'revenge', 'whale', 'pump', 'dump', 'rekt', 'diamond hands',
            'paper hands', 'yolo', 'hodl', 'dca', 'flip', 'long', 'short'
        ]
        
        for term in trading_terms:
            if term in cleaned:
                phrases.append(term)
        
        # Add the full response if it's short and meaningful
        if len(cleaned) <= 20 and cleaned not in ['other', 'idk', 'yes', 'no']:
            phrases.append(cleaned)
        
        return phrases
    
    async def get_last_response(self, user_id: int, token_address: str = None,
                              pattern_type: str = None) -> Optional[Dict]:
        """Get last relevant response with confidence score"""
        try:
            db = self._get_db()
            
            query = """
                SELECT user_response, pattern_type, created_at, metadata
                FROM trade_notes
                WHERE user_id = ?
            """
            params = [user_id]
            
            if token_address:
                query += " AND token_address = ?"
                params.append(token_address)
            
            if pattern_type:
                query += " AND pattern_type = ?"
                params.append(pattern_type)
            
            query += " ORDER BY created_at DESC LIMIT 1"
            
            result = db.execute(query, params).fetchone()
            
            # Close if we created a new connection
            if not self.db:
                db.close()
            
            if result:
                response, p_type, created_at, metadata_json = result
                
                # Calculate confidence based on recency and relevance
                confidence = self._calculate_confidence(created_at, token_address is not None)
                
                return {
                    'text': response,
                    'pattern_type': p_type,
                    'timestamp': created_at,
                    'confidence': confidence,
                    'metadata': json.loads(metadata_json) if metadata_json else {}
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting last response: {e}")
            return None
    
    async def get_last_trade(self, user_id: int, token_address: str, 
                            exclude_tx: str = None) -> Optional[Dict]:
        """Get last actual trade (BUY/SELL) for a token"""
        try:
            db = self._get_db()
            
            query = """
                SELECT 
                    tx_signature,
                    action,
                    sol_amount,
                    token_amount,
                    timestamp,
                    pnl_usd
                FROM user_trades
                WHERE user_id = ?
                AND token_address = ?
            """
            params = [user_id, token_address]
            
            if exclude_tx:
                query += " AND tx_signature != ?"
                params.append(exclude_tx)
            
            query += " ORDER BY timestamp DESC LIMIT 1"
            
            result = db.execute(query, params).fetchone()
            
            # Close if we created a new connection
            if not self.db:
                db.close()
            
            if result:
                tx_sig, action, sol_amount, token_amount, timestamp, pnl = result
                return {
                    'tx_signature': tx_sig,
                    'action': action,
                    'sol_amount': sol_amount,
                    'token_amount': token_amount,
                    'timestamp': timestamp,
                    'pnl_usd': pnl
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting last trade: {e}")
            return None
    
    async def get_token_position_history(self, user_id: int, token_address: str) -> Dict:
        """Get complete position history for a token including current holdings"""
        try:
            db = self._get_db()
            
            # Get all trades for this token
            trades = db.execute("""
                SELECT 
                    action,
                    sol_amount,
                    token_amount,
                    timestamp,
                    pnl_usd
                FROM user_trades
                WHERE user_id = ?
                AND token_address = ?
                ORDER BY timestamp ASC
            """, [user_id, token_address]).fetchall()
            
            # Close if we created a new connection
            if not self.db:
                db.close()
            
            # Calculate position
            total_bought = 0
            total_sold = 0
            buy_count = 0
            sell_count = 0
            total_spent_sol = 0
            total_received_sol = 0
            
            for action, sol_amount, token_amount, timestamp, pnl in trades:
                if action == 'BUY':
                    total_bought += token_amount
                    total_spent_sol += sol_amount
                    buy_count += 1
                else:  # SELL
                    total_sold += token_amount
                    total_received_sol += sol_amount
                    sell_count += 1
            
            remaining_tokens = total_bought - total_sold
            net_sol = total_received_sol - total_spent_sol
            
            return {
                'total_bought': total_bought,
                'total_sold': total_sold,
                'remaining_tokens': remaining_tokens,
                'buy_count': buy_count,
                'sell_count': sell_count,
                'total_spent_sol': total_spent_sol,
                'total_received_sol': total_received_sol,
                'net_sol': net_sol,
                'trade_count': len(trades),
                'is_closed': remaining_tokens <= 0
            }
            
        except Exception as e:
            logger.error(f"Error getting token position history: {e}")
            return {
                'total_bought': 0,
                'total_sold': 0,
                'remaining_tokens': 0,
                'buy_count': 0,
                'sell_count': 0,
                'total_spent_sol': 0,
                'total_received_sol': 0,
                'net_sol': 0,
                'trade_count': 0,
                'is_closed': True
            }
    
    def _calculate_confidence(self, timestamp: datetime, is_token_specific: bool) -> float:
        """Calculate confidence score for memory callback"""
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        # Time decay factor
        hours_ago = (datetime.now() - timestamp).total_seconds() / 3600
        time_confidence = max(0.1, 1.0 - (hours_ago / 168))  # Decay over 1 week
        
        # Relevance boost for token-specific memories
        relevance_boost = 0.3 if is_token_specific else 0.0
        
        return min(1.0, time_confidence + relevance_boost)
    
    async def get_user_vocabulary(self, user_id: int, pattern_type: str = None,
                                limit: int = 5) -> List[str]:
        """Get user's most common phrases for adaptive buttons"""
        try:
            query = """
                SELECT phrase, frequency
                FROM user_vocabulary
                WHERE user_id = ?
            """
            params = [user_id]
            
            if pattern_type:
                query += " AND pattern_type = ?"
                params.append(pattern_type)
            
            query += """
                ORDER BY frequency DESC, last_used DESC
                LIMIT ?
            """
            params.append(limit)
            
            result = self.db.execute(query, params).fetchall()
            return [phrase[0] for phrase in result]
            
        except Exception as e:
            logger.error(f"Error getting user vocabulary: {e}")
            return []
    
    async def get_user_notes(self, user_id: int, days: int = 7) -> List[Dict]:
        """Get recent user notes for analysis"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            result = self.db.execute("""
                SELECT user_response, pattern_type, token_symbol, created_at, metadata
                FROM trade_notes
                WHERE user_id = ?
                AND created_at > ?
                ORDER BY created_at DESC
            """, [user_id, cutoff_date]).fetchall()
            
            notes = []
            for response, p_type, symbol, created_at, metadata_json in result:
                notes.append({
                    'response': response,
                    'pattern_type': p_type,
                    'token_symbol': symbol,
                    'timestamp': created_at,  # Keep as timestamp for compatibility
                    'metadata': json.loads(metadata_json) if metadata_json else {}
                })
            
            return notes
            
        except Exception as e:
            logger.error(f"Error getting user notes: {e}")
            return []
    
    async def export_training_data(self, user_id: int = None) -> List[Dict]:
        """Export conversation data for AI training"""
        try:
            query = """
                SELECT 
                    n.user_id,
                    n.user_response,
                    n.pattern_type,
                    n.metadata,
                    n.created_at,
                    t.pnl_usd,
                    t.token_symbol,
                    t.sol_amount
                FROM trade_notes n
                LEFT JOIN user_trades t ON n.trade_id = t.tx_signature
            """
            params = []
            
            if user_id:
                query += " WHERE n.user_id = ?"
                params.append(user_id)
            
            query += " ORDER BY n.created_at DESC"
            
            result = self.db.execute(query, params).fetchall()
            
            training_data = []
            for row in result:
                uid, response, p_type, metadata_json, created_at, pnl, symbol, sol_amount = row
                
                training_data.append({
                    'context': {
                        'user_id': uid,
                        'pattern_type': p_type,
                        'token_symbol': symbol,
                        'sol_amount': sol_amount,
                        'metadata': json.loads(metadata_json) if metadata_json else {}
                    },
                    'user_response': response,
                    'outcome': {
                        'pnl_usd': pnl,
                        'timestamp': created_at  # Keep as timestamp for compatibility
                    }
                })
            
            return training_data
            
        except Exception as e:
            logger.error(f"Error exporting training data: {e}")
            return []
    
    def set_pending_response(self, user_id: int, context: Dict):
        """Set pending response context for 'Other...' handling"""
        self.pending_responses[user_id] = context
    
    def get_pending_response(self, user_id: int) -> Optional[Dict]:
        """Get and clear pending response context"""
        return self.pending_responses.pop(user_id, None)
    
    def clear_pending_response(self, user_id: int):
        """Clear pending response context without returning it"""
        self.pending_responses.pop(user_id, None)
    
    async def generate_weekly_digest(self, user_id: int) -> str:
        """Generate weekly digest using user's own words"""
        try:
            notes = await self.get_user_notes(user_id, days=7)
            
            if not notes:
                return "No trades or notes this week. Taking a break?"
            
            # Count patterns in responses
            pattern_counts = {}
            for note in notes:
                response = note['response'].lower()
                pattern_counts[response] = pattern_counts.get(response, 0) + 1
            
            # Get most common responses
            top_responses = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            
            # Build digest
            digest = f"📊 Your Week in Review\n\n"
            digest += f"Trades: {len(notes)}\n"
            digest += f"Notes added: {len([n for n in notes if n['response'] != 'Other'])}\n\n"
            
            if top_responses:
                digest += "Your words:\n"
                for response, count in top_responses:
                    digest += f"- Said '{response}' {count} times\n"
            
            digest += f"\nKeep the honest self-reflection coming!"
            
            return digest
            
        except Exception as e:
            logger.error(f"Error generating weekly digest: {e}")
            return "Error generating digest. Try again later."
    
    async def get_thread_messages(self, thread_id: str) -> List[Dict]:
        """Get all messages in a conversation thread"""
        try:
            db = self._get_db()
            
            result = db.execute("""
                SELECT 
                    user_response, 
                    pattern_type, 
                    timestamp, 
                    metadata,
                    response_type
                FROM trade_notes
                WHERE thread_id = ?
                ORDER BY timestamp ASC
            """, [thread_id]).fetchall()
            
            # Close if we created a new connection
            if not self.db:
                db.close()
            
            messages = []
            for response, p_type, ts, metadata_json, resp_type in result:
                messages.append({
                    'response': response,
                    'pattern_type': p_type,
                    'timestamp': ts,
                    'metadata': json.loads(metadata_json) if metadata_json else {},
                    'response_type': resp_type
                })
            
            return messages
            
        except Exception as e:
            logger.error(f"Error getting thread messages: {e}")
            return []
    
    async def get_conversation_context(self, trade_id: str, user_id: int) -> Dict:
        """Get full conversation context for a trade"""
        try:
            db = self._get_db()
            
            # Get all messages for this thread
            messages = await self.get_thread_messages(trade_id)
            
            # Get trade info
            trade_result = db.execute("""
                SELECT 
                    token_symbol,
                    sol_amount,
                    pnl_usd,
                    action,
                    timestamp
                FROM user_trades
                WHERE tx_signature = ?
                AND user_id = ?
                LIMIT 1
            """, [trade_id, user_id]).fetchone()
            
            # Close if we created a new connection
            if not self.db:
                db.close()
            
            context = {
                'thread_id': trade_id,
                'messages': messages,
                'message_count': len(messages)
            }
            
            if trade_result:
                token_symbol, sol_amount, pnl_usd, action, timestamp = trade_result
                context.update({
                    'token_symbol': token_symbol,
                    'sol_amount': sol_amount,
                    'pnl_usd': pnl_usd,
                    'action': action,
                    'trade_timestamp': timestamp
                })
            
            return context
            
        except Exception as e:
            logger.error(f"Error getting conversation context: {e}")
            return {}
    
    async def get_pattern_history(self, user_id: int, pattern_type: str, limit: int = 5) -> List[Dict]:
        """Get user's history with a specific pattern type"""
        try:
            db = self._get_db()
            
            result = db.execute("""
                SELECT DISTINCT
                    n.user_response,
                    n.token_symbol,
                    n.timestamp,
                    n.metadata,
                    t.pnl_usd
                FROM trade_notes n
                LEFT JOIN user_trades t ON n.trade_id = t.tx_signature
                WHERE n.user_id = ?
                AND n.pattern_type = ?
                ORDER BY n.timestamp DESC
                LIMIT ?
            """, [user_id, pattern_type, limit]).fetchall()
            
            # Close if we created a new connection
            if not self.db:
                db.close()
            
            history = []
            for response, token, ts, metadata_json, pnl in result:
                history.append({
                    'response': response,
                    'token_symbol': token,
                    'timestamp': ts,
                    'pnl_usd': pnl,
                    'metadata': json.loads(metadata_json) if metadata_json else {}
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting pattern history: {e}")
            return []
    
    def should_send_clarifier(self, response: str, context: Dict) -> bool:
        """Determine if a clarifier question should be sent"""
        # Don't clarify skips
        if response.lower() in ['skip', 'skipped', '🫥']:
            return False
        
        # Short vague responses get clarifiers
        vague_responses = ['yes', 'no', 'idk', 'maybe', 'sure', 'ok', 'k']
        if response.lower().strip() in vague_responses:
            return True
        
        # Very short responses (< 5 words) might need clarification
        word_count = len(response.split())
        if word_count <= 5:
            # But only if they're not already clear tags
            clear_tags = ['fomo', 'revenge', 'whale follow', 'taking profits', 
                         'stop loss', 'dca', 'averaging down', 'panic sell']
            if not any(tag in response.lower() for tag in clear_tags):
                return True
        
        return False
    
    async def generate_clarifier_context(self, response: str, pattern_type: str) -> Dict:
        """Generate context for clarifier question"""
        clarifier_map = {
            'position_size': {
                'fomo': "Saw something specific or just market vibes?",
                'alpha': "Your find or following someone?",
                'whales': "Which wallet caught your eye?"
            },
            'repeat_token': {
                'revenge': "Same setup or pure emotion?",
                'adding': "Planned DCA or catching knife?",
                'new': "What changed your mind?"
            },
            'hold_time': {
                'moon': "Got a target or just vibing?",
                'flip': "Exit plan or watching price?",
                'no plan': "What usually makes you exit?"
            },
            'dust_trade': {
                'testing': "Testing what exactly?",
                'broke': "Saving the rest for something?",
                'gas': "Expecting a quick flip?"
            },
            'round_number': {
                'clean': "Always trade round numbers?",
                'fomo': "Price or position size FOMO?",
                'lucky': "Your go-to lucky number?"
            },
            'late_night': {
                'degen': "Best or worst trades at night?",
                'global': "Following Asia markets?",
                'insomnia': "Trading keeping you up?"
            }
        }
        
        # Get relevant clarifier options
        options = clarifier_map.get(pattern_type, {})
        
        # Match response to best clarifier
        response_lower = response.lower()
        for key, clarifier in options.items():
            if key in response_lower:
                return {
                    'should_clarify': True,
                    'clarifier_question': clarifier,
                    'original_response': response
                }
        
        # Generic clarifier for unmatched responses
        if len(response.split()) <= 3:
            return {
                'should_clarify': True,
                'clarifier_question': "Tell me more?",
                'original_response': response
            }
        
        return {'should_clarify': False}


# Factory function
def create_conversation_manager(db_connection=None, db_path=None) -> ConversationManager:
    """Create conversation manager instance"""
    return ConversationManager(db_connection, db_path) 