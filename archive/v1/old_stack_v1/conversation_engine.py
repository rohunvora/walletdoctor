"""
Conversation Engine - Central hub for processing all inputs and generating responses
"""

import logging
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict
import json

# Add enhanced context builder import
from enhanced_context_builder import EnhancedContextBuilder, ContextScope

logger = logging.getLogger(__name__)


class InputType(Enum):
    """Types of inputs the engine can process"""
    TRADE = "trade"
    MESSAGE = "message"
    COMMAND = "command"
    TIME_EVENT = "time_event"


@dataclass
class ConversationInput:
    """Unified input structure for all interaction types"""
    type: InputType
    user_id: int
    timestamp: datetime
    data: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage/serialization"""
        return {
            "type": self.type.value,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data
        }


# DEPRECATED: Keeping for backward compatibility during transition
@dataclass
class ConversationContext:
    """Full context for generating a response - DEPRECATED: Use EnhancedContext"""
    current_input: ConversationInput
    conversation_history: List[Dict[str, Any]]
    user_state: Dict[str, Any]
    trading_stats: Dict[str, Any]
    
    def to_json(self) -> str:
        """Convert to JSON for GPT consumption - DEPRECATED, use to_structured()"""
        return json.dumps({
            "current_event": {
                "type": self.current_input.type.value,
                "data": self.current_input.data,
                "timestamp": self.current_input.timestamp.isoformat()
            },
            "conversation_history": self.conversation_history,
            "user_state": self.user_state,
            "trading_stats": self.trading_stats
        }, indent=2)
    
    def to_structured(self) -> str:
        """Convert to structured format - DEPRECATED: Use EnhancedContext.to_gpt_format()"""
        # This is kept for backward compatibility but should not be used
        logger.warning("Using deprecated ConversationContext.to_structured() - migrate to EnhancedContext")
        sections = []
        
        # Current trade/event section
        sections.append(self._format_current_event())
        
        # Recent patterns section
        if self.trading_stats.get("patterns"):
            sections.append(self._format_patterns())
        
        # Conversation history section
        if self.conversation_history:
            sections.append(self._format_conversation_history())
        
        # User profile section
        sections.append(self._format_user_profile())
        
        return "\n\n".join(sections)
    
    def _format_current_event(self) -> str:
        """Format the current event with metadata"""
        event_type = self.current_input.type.value
        timestamp = self.current_input.timestamp.isoformat()
        data = self.current_input.data
        
        # Determine significance based on event type and data
        significance = "normal"
        if event_type == "trade":
            pnl = data.get("pnl_usd", 0)
            if abs(pnl) > 500:
                significance = "high"
            elif data.get("amount_sol", 0) > 10:
                significance = "high"
        
        section = f"## CURRENT_EVENT\n"
        section += f'<{event_type}_data timestamp="{timestamp}" significance="{significance}">\n'
        section += json.dumps(data, indent=2)
        section += f'\n</{event_type}_data>'
        
        # Add human-readable summary for trades
        if event_type == "trade":
            section += f"\n\n**Summary**: {self._summarize_trade(data)}"
        
        return section
    
    def _format_patterns(self) -> str:
        """Format detected trading patterns"""
        patterns = self.trading_stats.get("patterns", [])
        confidence = "high" if len(patterns) >= 3 else "medium"
        
        section = f"## RECENT_PATTERNS\n"
        section += f'<patterns confidence="{confidence}">\n'
        
        for pattern in patterns:
            section += f"- {pattern}\n"
        
        # Add favorite tokens if available
        fav_tokens = self.trading_stats.get("favorite_tokens", [])
        if fav_tokens:
            section += f"\n**Frequently Traded**: {', '.join(fav_tokens)}\n"
        
        section += '</patterns>'
        return section
    
    def _format_conversation_history(self) -> str:
        """Format conversation history with relevance filtering"""
        # Select most relevant messages, not just most recent
        relevant_messages = self._select_relevant_messages()
        
        section = f"## CONVERSATION_HISTORY\n"
        section += f'<messages count="{len(relevant_messages)}">\n'
        
        for msg in relevant_messages:
            role = msg.get("role", "user")
            content = msg.get("summary", msg.get("content", ""))
            timestamp = msg.get("timestamp", "")
            
            # Format based on role
            if role == "user":
                section += f"**User** ({self._format_time_ago(timestamp)}): {content}\n"
            else:
                section += f"**Coach**: {content}\n"
        
        section += '</messages>'
        return section
    
    def _format_user_profile(self) -> str:
        """Format user profile and current state"""
        positions = self.user_state.get("positions", {})
        total_positions = self.user_state.get("total_positions", 0)
        exposure = self.user_state.get("total_exposure_pct", 0)
        
        # Get trading stats
        win_rate = self.trading_stats.get("win_rate", 0)
        total_trades = self.trading_stats.get("total_trades", 0)
        avg_size = self.trading_stats.get("avg_position_size", 0)
        
        section = f"## USER_PROFILE\n"
        section += f'<profile trades_this_week="{total_trades}" win_rate="{win_rate:.0%}">\n'
        
        # Current positions
        if positions:
            section += "\n**Active Positions**:\n"
            for token, pos_data in positions.items():
                pnl = pos_data.get("pnl_usd", 0)
                size = pos_data.get("size_pct", 0)
                pnl_sign = "+" if pnl >= 0 else "-"
                section += f"- {token}: {size:.1f}% of portfolio ({pnl_sign}${abs(pnl):.0f})\n"
        
        # Trading style indicators
        section += f"\n**Trading Style**:\n"
        section += f"- Average position: {avg_size:.1f} SOL\n"
        section += f"- Total exposure: {exposure:.1f}%\n"
        
        section += '</profile>'
        return section
    
    def _summarize_trade(self, trade_data: Dict) -> str:
        """Create human-readable trade summary"""
        action = trade_data.get("action", "UNKNOWN")
        token = trade_data.get("token_symbol", "UNKNOWN")
        amount = trade_data.get("amount_sol", 0)
        pnl = trade_data.get("pnl_usd")
        
        if action.upper() == "BUY":
            return f"Bought {amount:.2f} SOL worth of {token}"
        else:  # SELL
            if pnl is not None:
                pnl_sign = "+" if pnl >= 0 else ""
                return f"Sold {token} for {pnl_sign}${abs(pnl):.0f} ({pnl_sign}{trade_data.get('pnl_pct', 0):.1f}%)"
            else:
                return f"Sold {amount:.2f} SOL worth of {token}"
    
    def _select_relevant_messages(self) -> List[Dict]:
        """Select most relevant messages from history"""
        if not self.conversation_history:
            return []
        
        # Start with last 10 messages
        recent = self.conversation_history[-10:]
        
        # If current event is a trade, find messages about the same token
        if self.current_input.type == InputType.TRADE:
            current_token = self.current_input.data.get("token_symbol")
            if current_token:
                # Look for messages mentioning this token
                token_messages = [
                    msg for msg in self.conversation_history
                    if current_token in msg.get("summary", msg.get("content", ""))
                ]
                # Add up to 3 most recent token-specific messages
                for msg in token_messages[-3:]:
                    if msg not in recent:
                        recent.insert(0, msg)
        
        # Limit to 7 messages total for context window efficiency
        return recent[-7:]
    
    def _format_time_ago(self, timestamp_str: str) -> str:
        """Format timestamp as human-readable time ago"""
        if not timestamp_str:
            return "recently"
        
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            now = datetime.now(timestamp.tzinfo or timezone.utc)
            delta = now - timestamp
            
            if delta.days > 0:
                return f"{delta.days}d ago"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600}h ago"
            elif delta.seconds > 60:
                return f"{delta.seconds // 60}m ago"
            else:
                return "just now"
        except:
            return "recently"


class ConversationEngine:
    """Main conversation engine that handles all interactions"""
    
    def __init__(self, state_manager, conversation_manager, gpt_client=None, pattern_service=None, pnl_service=None):
        self.state_manager = state_manager
        self.conversation_manager = conversation_manager
        self.gpt_client = gpt_client
        
        # Enhanced context builder (replaces old context building)
        self.enhanced_context_builder = EnhancedContextBuilder(
            state_manager=state_manager,
            conversation_manager=conversation_manager,
            pattern_service=pattern_service,
            pnl_service=pnl_service
        )
        
        # Response control flags
        self.paused_users = set()
        self.last_trade_response = {}  # Track last response time per user
        self.MIN_TRADE_INTERVAL = 30  # Minimum seconds between trade responses
        
        # Conversation threading
        self.active_threads = {}  # user_id -> thread_id
        
    async def process_input(self, input_type: InputType, data: Dict, user_id: int) -> Optional[str]:
        """Process any input and generate appropriate response"""
        
        # Check if user is paused and handle accordingly
        if self.is_paused(user_id):
            if input_type == InputType.MESSAGE:
                # User messaged while paused - offer to resume
                return await self._handle_paused_user_message(user_id, data.get("text", ""))
            else:
                # Don't process trades/commands while paused
                return None
        
        # Natural language intent detection for messages
        if input_type == InputType.MESSAGE:
            message_text = data.get("text", "").lower().strip()
            
            # Pause intent - more natural variations
            pause_triggers = [
                "pause", "stop", "quiet", "shut up", "shh", "chill",
                "too much", "overwhelming", "annoying", "take a break",
                "leave me alone", "stop messaging", "mute", "silence",
                "enough", "too many", "calm down", "give me space"
            ]
            if any(trigger in message_text for trigger in pause_triggers):
                self.pause_user(user_id)
                return "Got it, taking a break 🤐 Hit me up whenever."
            
            # Clear intent - more natural variations  
            clear_triggers = [
                "clear", "reset", "start over", "fresh start", "new start",
                "wipe", "clean slate", "start fresh", "begin again",
                "forget everything", "new conversation", "restart"
            ]
            if any(trigger in message_text for trigger in clear_triggers):
                await self.clear_conversation(user_id)
                return "Clean slate! What's the next move? 🌱"
            
            # Help intent
            help_triggers = [
                "help", "what can you do", "commands", "how do i",
                "instructions", "guide", "tutorial", "how to use",
                "what do you do", "features", "options"
            ]
            if any(trigger in message_text for trigger in help_triggers):
                return self._get_help_message()
        
        # Rate limiting for trades
        if input_type == InputType.TRADE:
            last_response_time = self.last_trade_response.get(user_id, 0)
            if time.time() - last_response_time < self.MIN_TRADE_INTERVAL:
                return None  # Skip this trade
            self.last_trade_response[user_id] = time.time()
        
        # Build enhanced context using new unified system
        enhanced_context = await self._build_enhanced_context(input_type, data, user_id)
        
        # Generate response
        if self.gpt_client and self.gpt_client.is_available():
            try:
                # Use enhanced context with anonymization for GPT
                context_for_gpt = enhanced_context.to_gpt_format(anonymize=True)
                response = await self.gpt_client.generate_response(context_for_gpt)
                if response:
                    # Store the conversation
                    await self._store_conversation(user_id, input_type, data, response)
                    # Log performance metrics
                    metrics = enhanced_context.get_performance_metrics()
                    logger.info(f"Context build: {metrics['build_time_ms']:.1f}ms, {metrics['context_size_bytes']} bytes")
                    return response
            except Exception as e:
                logger.error(f"Error generating GPT response: {e}")
        
        # Fallback response
        return self._get_fallback_response(input_type, data)
    
    async def _handle_paused_user_message(self, user_id: int, message_text: str) -> str:
        """Handle messages from paused users"""
        message_lower = message_text.lower().strip()
        
        # More natural resume triggers
        resume_triggers = [
            "resume", "start", "yes", "ready", "back", "continue",
            "turn on", "enable", "watch", "track", "i'm back",
            "let's go", "start again", "unpause", "activate",
            "wake up", "come back", "talk to me"
        ]
        if any(trigger in message_lower for trigger in resume_triggers):
            self.resume_user(user_id)
            return "Back in action! 📈 What's moving in the market?"
        
        # They're just chatting while paused
        return "Still on break here. Say 'resume' when you want trade alerts again."
    
    def _get_help_message(self) -> str:
        """Natural help message without commands"""
        return (
            "I watch your trades and help spot patterns 📊\n\n"
            "Just trade normally and I'll check in. You can:\n"
            "• Chat anytime about trades\n"
            "• Say 'pause' to stop alerts\n"
            "• Say 'clear' to start fresh\n\n"
            "No commands needed - just talk!"
        )
    
    async def _build_enhanced_context(self, input_type: InputType, data: Dict, user_id: int):
        """Build enhanced context using new unified system"""
        
        # Determine appropriate scope based on input type
        if input_type == InputType.TRADE:
            scope = ContextScope.TRADE_FOCUSED  # Rich trading data for trades
        elif input_type == InputType.MESSAGE:
            scope = ContextScope.FULL  # Full context for conversations
        else:
            scope = ContextScope.MINIMAL  # Minimal for commands/events
        
        # Use enhanced context builder
        return await self.enhanced_context_builder.build_context(
            input_type=input_type.value,
            input_data=data,
            user_id=user_id,
            scope=scope
        )
    
    # DEPRECATED: Keeping for backward compatibility
    async def _build_context(self, input_type: InputType, data: Dict, user_id: int) -> ConversationContext:
        """Build comprehensive context for response generation"""
        start_time = time.time()
        
        # Create input object
        conversation_input = ConversationInput(
            type=input_type,
            user_id=user_id,
            timestamp=datetime.now(),
            data=data
        )
        
        # Parallel fetch all context data
        history_task = self.conversation_manager.get_conversation_history(user_id, limit=10)
        positions_task = self._get_user_positions(user_id)
        stats_task = self._get_user_stats(user_id)
        
        try:
            history, positions, stats = await asyncio.gather(
                history_task,
                positions_task,
                stats_task,
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Error gathering context: {e}")
            history, positions, stats = [], {}, {}
        
        # Handle exceptions from gather
        if isinstance(history, Exception):
            logger.error(f"Error getting conversation history: {history}")
            history = []
        if isinstance(positions, Exception):
            logger.error(f"Error getting user positions: {positions}")
            positions = {}
        if isinstance(stats, Exception):
            logger.error(f"Error getting user stats: {stats}")
            stats = {}
        
        elapsed_ms = (time.time() - start_time) * 1000
        if elapsed_ms > 50:
            logger.warning(f"Context build took {elapsed_ms:.1f}ms - optimize!")
        
        return ConversationContext(
            current_input=conversation_input,
            conversation_history=history,
            user_state=positions,
            trading_stats=stats
        )
    
    def _should_respond(self, context: ConversationContext) -> bool:
        """Determine if we should generate a response"""
        user_id = context.current_input.user_id
        input_type = context.current_input.type
        
        # Check if user is paused
        if user_id in self.paused_users:
            return False
        
        # Always respond to direct messages
        if input_type == InputType.MESSAGE:
            return True
        
        # Always respond to commands
        if input_type == InputType.COMMAND:
            return True
        
        # For trades, check if there's been recent conversation
        if input_type == InputType.TRADE:
            last_response = self.last_trade_response.get(user_id)
            if last_response:
                time_since_last = (datetime.now() - last_response).total_seconds()
                # Don't spam - wait at least 30 seconds between trade responses
                if time_since_last < 30:
                    return False
            
            # Check if there's an unanswered question
            if self._has_unanswered_question(context):
                return False
                
            return True
        
        # For time events, use specific logic
        if input_type == InputType.TIME_EVENT:
            event_type = context.current_input.data.get("event_type")
            if event_type == "position_check":
                # Only check positions if held > 1 hour
                return self._should_check_position(context)
        
        return False
    
    async def _generate_response(self, context: ConversationContext) -> str:
        """Generate response using GPT or fallback"""
        if self.gpt_client:
            try:
                # Convert context to structured format for GPT
                context_structured = context.to_structured()
                
                # Log that we're attempting GPT generation
                logger.info(f"Attempting GPT generation for user {context.current_input.user_id}")
                
                # Generate response with GPT
                gpt_response = await self.gpt_client.generate_response(context_structured)
                
                if gpt_response:
                    logger.info(f"GPT response generated successfully")
                    return gpt_response
                else:
                    logger.info("GPT returned None, using fallback")
                    return self._get_fallback_response(context)
                    
            except Exception as e:
                logger.error(f"GPT generation failed: {e}")
                return self._get_fallback_response(context)
        else:
            return self._get_fallback_response(context)
    
    def _get_fallback_response(self, input_type: InputType, data: Dict) -> str:
        """Generate simple fallback response when GPT unavailable"""
        if input_type == InputType.TRADE:
            action = data.get("action", "trade")
            token = data.get("token_symbol", "this token")
            amount = data.get("amount_sol", 0)
            pnl = data.get("pnl_usd")
            
            # Check if this is a favorite token (would need context)
            # For now, just use dynamic responses based on data
            
            if action.upper() == "BUY":
                if amount > 5:
                    return f"{token} with {amount} SOL? Big moves 👀 What's the play?"
                elif amount < 1:
                    return f"Testing the waters with {token}? Smart. What caught your eye?"
                else:
                    return f"{token} for {amount} SOL. What's got you interested?"
            else:  # SELL
                if pnl and pnl > 0:
                    return f"Nice! +${pnl:.0f} on {token} 🔥 Good timing or just lucky?"
                elif pnl and pnl < -100:
                    return f"Ouch. -${abs(pnl):.0f} on {token}. Stop loss or changed your mind?"
                elif pnl and pnl < 0:
                    return f"Out of {token} at -${abs(pnl):.0f}. What happened?"
                else:
                    return f"Closed {token}. Quick flip or cutting losses?"
        
        elif input_type == InputType.MESSAGE:
            text = data.get("text", "").lower()
            if "twitter" in text or "ct" in text:
                return "Twitter calls... how's that strategy working out? 😅"
            elif "pump" in text or "moon" in text:
                return "The eternal search for pumps. Found any good ones lately?"
            elif "loss" in text or "lost" in text or "rekt" in text:
                return "Rough day? What's the damage?"
            elif "profit" in text or "gain" in text or "made" in text:
                return "Let's hear the win! How much we talking?"
            elif any(greeting in text for greeting in ["hey", "hi", "hello", "sup", "yo"]):
                return "What's good? Market treating you well today?"
            else:
                return "Tell me more. What's your thinking?"
        
        elif input_type == InputType.COMMAND:
            return "What's on your mind?"
        else:
            return "Been quiet on the trades. Market got you waiting?"
    
    async def _store_conversation(self, user_id: int, input_type: InputType, data: Dict, response: str):
        """Store the conversation turn"""
        try:
            # Get or create thread ID for this user
            thread_id = self.active_threads.get(user_id)
            if not thread_id:
                thread_id = f"thread_{user_id}_{datetime.now().timestamp()}"
                self.active_threads[user_id] = thread_id
            
            # Store user input
            if input_type == InputType.MESSAGE:
                await self.conversation_manager.store_message(
                    user_id=user_id,
                    thread_id=thread_id,
                    role="user",
                    content=data.get("text", "")
                )
            elif input_type == InputType.TRADE:
                # Format trade as message
                trade_summary = f"Trade: {data.get('action', '')} {data.get('amount_sol', '')} SOL of {data.get('token_symbol', '')}"
                if data.get('pnl_usd') is not None:
                    trade_summary += f" (P&L: ${data.get('pnl_usd'):,.2f})"
                
                await self.conversation_manager.store_message(
                    user_id=user_id,
                    thread_id=thread_id,
                    role="user",
                    content=trade_summary
                )
            
            # Store bot response
            await self.conversation_manager.store_message(
                user_id=user_id,
                thread_id=thread_id,
                role="assistant",
                content=response
            )
            
        except Exception as e:
            logger.error(f"Error storing conversation: {e}")
    
    async def _get_user_positions(self, user_id: int) -> Dict[str, Any]:
        """Get current positions from state manager"""
        try:
            notebooks = await self.state_manager.get_all_notebooks(user_id)
            positions = {}
            total_exposure = 0
            
            for token, data in notebooks.items():
                if data.get("last_side") == "buy" and data.get("exposure_pct", 0) > 0:
                    positions[token] = {
                        "size_pct": data.get("exposure_pct", 0),
                        "pnl_sol": data.get("live_pnl_sol", 0),
                        "pnl_usd": data.get("live_pnl_sol", 0) * 175,  # Approximate USD
                        "entry_time": data.get("last_trade_time"),
                        "last_reason": data.get("last_reason"),
                        "unanswered_question": data.get("unanswered_question", False)
                    }
                    total_exposure += data.get("exposure_pct", 0)
            
            # Add summary stats
            return {
                "positions": positions,
                "total_positions": len(positions),
                "total_exposure_pct": total_exposure,
                "largest_position": max(positions.keys(), 
                                      key=lambda k: positions[k]["size_pct"]) if positions else None
            }
        except Exception as e:
            logger.error(f"Error getting user positions: {e}")
            return {"positions": {}, "total_positions": 0, "total_exposure_pct": 0}
    
    async def _get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user trading statistics including patterns"""
        try:
            import duckdb
            db = duckdb.connect(self.state_manager.db_path)
            
            # Get recent trading patterns
            patterns = db.execute("""
                WITH recent_trades AS (
                    SELECT 
                        token_symbol,
                        action,
                        sol_amount,
                        pnl_usd,
                        timestamp,
                        COUNT(*) OVER (PARTITION BY token_symbol) as times_traded,
                        AVG(sol_amount) OVER (PARTITION BY user_id) as avg_size,
                        COUNT(CASE WHEN pnl_usd < 0 THEN 1 END) OVER () as recent_losses
                    FROM user_trades
                    WHERE user_id = ?
                    AND timestamp > CURRENT_TIMESTAMP - INTERVAL '7 days'
                    ORDER BY timestamp DESC
                    LIMIT 20
                )
                SELECT 
                    token_symbol,
                    times_traded,
                    MAX(sol_amount) as max_position,
                    MIN(pnl_usd) as worst_loss,
                    MAX(pnl_usd) as best_gain,
                    COUNT(DISTINCT token_symbol) as unique_tokens,
                    SUM(CASE WHEN action = 'SELL' AND pnl_usd < 0 THEN 1 ELSE 0 END) as stop_losses
                FROM recent_trades
                GROUP BY token_symbol, times_traded
                ORDER BY times_traded DESC
                LIMIT 5
            """, [user_id]).fetchall()
            
            # Extract insights
            favorite_tokens = []
            trading_patterns = []
            
            for row in patterns:
                token, times, max_pos, worst_loss, best_gain, _, losses = row
                if times >= 3:
                    favorite_tokens.append(token)
                    trading_patterns.append(f"Traded {token} {times} times this week")
                if worst_loss and worst_loss < -100:
                    trading_patterns.append(f"Lost ${abs(worst_loss):.0f} on {token}")
                if best_gain and best_gain > 100:
                    trading_patterns.append(f"Made ${best_gain:.0f} on {token}")
            
            # Get overall stats
            overall = db.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    AVG(sol_amount) as avg_size,
                    SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) as win_rate,
                    SUM(pnl_usd) as total_pnl
                FROM user_trades
                WHERE user_id = ?
                AND timestamp > CURRENT_TIMESTAMP - INTERVAL '30 days'
            """, [user_id]).fetchone()
            
            db.close()
            
            return {
                "favorite_tokens": favorite_tokens,
                "patterns": trading_patterns,
                "total_trades": overall[0] if overall else 0,
                "avg_position_size": overall[1] if overall else 0,
                "win_rate": overall[2] if overall else 0,
                "total_pnl": overall[3] if overall else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {}
    
    def _has_unanswered_question(self, context: ConversationContext) -> bool:
        """Check if there's an unanswered question for this user"""
        # Look at conversation history to see if last bot message was a question
        history = context.conversation_history
        
        if not history:
            return False
            
        # Find the last bot message
        last_bot_msg = None
        for msg in reversed(history):
            if msg.get('role') == 'assistant':
                last_bot_msg = msg
                break
                
        if not last_bot_msg:
            return False
            
        # Check if it ends with a question mark
        bot_text = last_bot_msg.get('summary', '')
        if '?' in bot_text:
            # Check if there's been a user response after this question
            bot_index = history.index(last_bot_msg)
            if bot_index == len(history) - 1:
                # Bot message is the last message - question is unanswered
                return True
                
        return False
    
    def _should_check_position(self, context: ConversationContext) -> bool:
        """Determine if we should check on a position"""
        # TODO: Implement position checking logic
        return False
    
    def pause_user(self, user_id: int):
        """Pause responses for a user"""
        self.paused_users.add(user_id)
        logger.info(f"Paused responses for user {user_id}")
    
    def resume_user(self, user_id: int):
        """Resume responses for a user"""
        self.paused_users.discard(user_id)
        logger.info(f"Resumed responses for user {user_id}")
    
    def is_paused(self, user_id: int) -> bool:
        """Check if user is paused"""
        return user_id in self.paused_users

    async def clear_conversation(self, user_id: int):
        """Clear conversation history for a user"""
        # Remove active thread
        self.active_threads.pop(user_id, None)
        
        # Clear response timing
        self.last_trade_response.pop(user_id, None)
        
        logger.info(f"Cleared conversation for user {user_id}")
        
    async def get_conversation_summary(self, user_id: int) -> str:
        """Get a summary of the user's recent conversations"""
        try:
            # Get last 20 messages
            history = await self.conversation_manager.get_conversation_history(
                user_id=user_id,
                limit=20
            )
            
            if not history:
                return "No recent conversations"
                
            # Count interactions
            trades = sum(1 for msg in history if msg['type'] == 'trade')
            messages = sum(1 for msg in history if msg['type'] == 'message')
            
            # Find topics discussed
            tokens_mentioned = set()
            for msg in history:
                if msg['type'] == 'trade':
                    token = msg['content'].get('token_symbol')
                    if token:
                        tokens_mentioned.add(token)
                        
            summary = f"Recent activity: {trades} trades, {messages} messages"
            if tokens_mentioned:
                summary += f"\nTokens discussed: {', '.join(sorted(tokens_mentioned))}"
                
            return summary
            
        except Exception as e:
            logger.error(f"Error getting conversation summary: {e}")
            return "Unable to generate summary"


# Factory function
def create_conversation_engine(state_manager, conversation_manager, gpt_client=None, 
                             pattern_service=None, pnl_service=None) -> ConversationEngine:
    """Create conversation engine instance with enhanced context support"""
    return ConversationEngine(
        state_manager=state_manager, 
        conversation_manager=conversation_manager, 
        gpt_client=gpt_client,
        pattern_service=pattern_service,
        pnl_service=pnl_service
    ) 