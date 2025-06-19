"""
Enhanced Context Builder - Unified context system for GPT interactions

Combines the rich data collection of ContextPack with the clean formatting 
of ConversationContext for optimal GPT understanding and performance.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from enum import Enum

logger = logging.getLogger(__name__)


class ContextScope(Enum):
    """Scope of context to build"""
    FULL = "full"           # Complete context for complex responses
    TRADE_FOCUSED = "trade"  # Trade-centric for quick responses
    MINIMAL = "minimal"     # Essential data only for fast responses


@dataclass
class EnhancedContext:
    """Unified context that combines rich data with optimal formatting"""
    
    # Core identification (never sent to GPT)
    user_id: int
    context_id: str
    timestamp: datetime
    scope: ContextScope
    
    # Current event data
    current_event: Dict[str, Any]
    event_significance: str  # "low", "medium", "high", "critical"
    
    # Trading context (rich financial data)
    trade_context: Dict[str, Any]  # P&L, position ratios, etc.
    position_context: Dict[str, Any]  # Current positions and exposure
    
    # Pattern and behavior context
    pattern_context: Dict[str, Any]  # Detected patterns with confidence
    user_profile: Dict[str, Any]  # Trading stats and preferences
    
    # Conversation context
    conversation_context: Dict[str, Any]  # Recent messages and threads
    timing_context: Dict[str, Any]  # Time-based patterns and indicators
    
    # Performance tracking
    build_time_ms: float
    data_sources: List[str]  # Which services provided data
    
    def to_gpt_format(self, anonymize: bool = True) -> str:
        """Convert to GPT-optimized format with optional anonymization"""
        if anonymize:
            return self._to_anonymized_structured()
        else:
            return self._to_full_structured()
    
    def _to_anonymized_structured(self) -> str:
        """Create anonymized, structured format for GPT"""
        sections = []
        
        # Current event section (anonymized)
        sections.append(self._format_current_event_anonymized())
        
        # Trading context (financial data anonymized)
        if self.trade_context and self.scope in [ContextScope.FULL, ContextScope.TRADE_FOCUSED]:
            sections.append(self._format_trade_context_anonymized())
        
        # Pattern context
        if self.pattern_context:
            sections.append(self._format_pattern_context())
        
        # Conversation context (content anonymized)
        if self.conversation_context and self.scope == ContextScope.FULL:
            sections.append(self._format_conversation_context_anonymized())
        
        # User profile (stats only, no identifiers)
        sections.append(self._format_user_profile_anonymized())
        
        # Timing context
        if self.timing_context:
            sections.append(self._format_timing_context())
        
        return "\n\n".join(sections)
    
    def _format_current_event_anonymized(self) -> str:
        """Format current event with sensitive data removed"""
        event = self.current_event.copy()
        
        # Remove sensitive identifiers
        event.pop('user_id', None)
        event.pop('wallet_address', None)
        event.pop('token_address', None)
        
        # Round financial values
        if 'amount_sol' in event:
            event['amount_sol'] = round(float(event['amount_sol']), 2)
        if 'pnl_usd' in event:
            event['pnl_usd'] = round(float(event['pnl_usd']), 0)
        
        timestamp = self.current_event.get('timestamp', self.timestamp.isoformat())
        
        section = f"## CURRENT_EVENT\n"
        section += f'<event significance="{self.event_significance}" timestamp="{timestamp}">\n'
        section += json.dumps(event, indent=2)
        section += '\n</event>'
        
        # Add human-readable summary
        if event.get('type') == 'trade':
            section += f"\n\n**Summary**: {self._summarize_trade_anonymized(event)}"
        
        return section
    
    def _format_trade_context_anonymized(self) -> str:
        """Format trading context with financial precision"""
        trade = self.trade_context.copy()
        
        # Round financial values for privacy/clarity
        for key in ['current_pnl_usd', 'unrealized_pnl_usd', 'user_overall_pnl']:
            if key in trade:
                trade[key] = round(float(trade[key]), 0)
        
        for key in ['position_size_ratio', 'win_rate_token']:
            if key in trade:
                trade[key] = round(float(trade[key]), 2)
        
        confidence = "high" if trade.get('pattern_confidence', 0) > 0.7 else "medium"
        
        section = f"## TRADING_CONTEXT\n"
        section += f'<trade_data confidence="{confidence}">\n'
        
        # P&L information
        current_pnl = trade.get('current_pnl_usd', 0)
        unrealized_pnl = trade.get('unrealized_pnl_usd', 0)
        
        if current_pnl != 0:
            pnl_status = "PROFIT" if current_pnl > 0 else "LOSS"
            section += f"**Position P&L**: {pnl_status} ${abs(current_pnl):.0f}\n"
        
        if unrealized_pnl != 0:
            unrealized_status = "UP" if unrealized_pnl > 0 else "DOWN"
            section += f"**Unrealized P&L**: {unrealized_status} ${abs(unrealized_pnl):.0f}\n"
        
        # Position sizing context
        size_ratio = trade.get('position_size_ratio', 1.0)
        if size_ratio > 1.5:
            section += f"**Position Size**: {size_ratio:.1f}x larger than typical\n"
        elif size_ratio < 0.7:
            section += f"**Position Size**: {size_ratio:.1f}x smaller than typical\n"
        
        # Token-specific history
        times_traded = trade.get('times_traded_token', 1)
        if times_traded > 1:
            section += f"**Token History**: {times_traded} previous trades"
            win_rate = trade.get('win_rate_token', 0)
            if win_rate > 0:
                section += f" ({win_rate:.0%} win rate)"
            section += "\n"
        
        section += '</trade_data>'
        return section
    
    def _format_pattern_context(self) -> str:
        """Format detected patterns with confidence levels"""
        patterns = self.pattern_context
        
        section = f"## PATTERN_ANALYSIS\n"
        confidence = patterns.get('overall_confidence', 'medium')
        section += f'<patterns confidence="{confidence}">\n'
        
        # Primary pattern
        primary = patterns.get('primary_pattern')
        if primary:
            section += f"**Primary Pattern**: {primary['type']} "
            section += f"(confidence: {primary.get('confidence', 0):.0%})\n"
        
        # Recent patterns list
        recent_patterns = patterns.get('recent_patterns', [])
        if recent_patterns:
            section += "\n**Recent Behaviors**:\n"
            for pattern in recent_patterns[:5]:  # Top 5
                section += f"- {pattern}\n"
        
        # Velocity indicators
        velocity = patterns.get('velocity_indicators', {})
        if velocity.get('is_rapid_sequence'):
            section += f"\n**Trading Velocity**: Rapid sequence detected\n"
        
        section += '</patterns>'
        return section
    
    def _format_conversation_context_anonymized(self) -> str:
        """Format recent conversation with content anonymized"""
        convo = self.conversation_context
        
        messages = convo.get('relevant_messages', [])
        if not messages:
            return ""
        
        section = f"## CONVERSATION_HISTORY\n"
        section += f'<messages count="{len(messages)}">\n'
        
        for msg in messages:
            role = msg.get('role', 'user')
            # Anonymize content but keep structure
            content = msg.get('summary', msg.get('content', ''))
            if len(content) > 100:
                content = content[:97] + "..."
            
            timestamp = msg.get('timestamp', '')
            time_ago = self._format_time_ago(timestamp)
            
            if role == 'user':
                tag = msg.get('tag', '')
                tag_display = f" [tag: {tag}]" if tag else ""
                section += f"**User** ({time_ago}): {content}{tag_display}\n"
            else:
                section += f"**Coach**: {content}\n"
        
        # Unanswered questions
        unanswered = convo.get('unanswered_questions', [])
        if unanswered:
            section += f"\n**Open Questions**: {len(unanswered)} pending responses\n"
        
        section += '</messages>'
        return section
    
    def _format_user_profile_anonymized(self) -> str:
        """Format user stats without identifiers"""
        profile = self.user_profile
        positions = self.position_context
        
        section = f"## USER_PROFILE\n"
        
        # Trading stats
        win_rate = profile.get('win_rate', 0)
        total_trades = profile.get('total_trades_week', 0)
        
        section += f'<profile trades_this_week="{total_trades}" win_rate="{win_rate:.0%}">\n'
        
        # Current positions (anonymized)
        active_positions = positions.get('positions', {})
        if active_positions:
            section += "\n**Active Positions**:\n"
            for token, pos_data in list(active_positions.items())[:5]:  # Top 5
                pnl = pos_data.get('pnl_usd', 0)
                size = pos_data.get('size_pct', 0)
                pnl_sign = "+" if pnl >= 0 else ""
                section += f"- {token}: {size:.1f}% portfolio ({pnl_sign}${pnl:.0f})\n"
        
        # Trading style indicators
        section += f"\n**Trading Style**:\n"
        avg_size = profile.get('avg_position_size', 0)
        total_exposure = positions.get('total_exposure_pct', 0)
        
        section += f"- Average position: {avg_size:.1f} SOL\n"
        section += f"- Total exposure: {total_exposure:.1f}%\n"
        
        section += '</profile>'
        return section
    
    def _format_timing_context(self) -> str:
        """Format timing and market context"""
        timing = self.timing_context
        
        section = f"## TIMING_CONTEXT\n"
        section += '<timing>\n'
        
        # Time of day context
        hour = timing.get('trade_hour', datetime.now().hour)
        if 22 <= hour or hour <= 6:
            section += f"**Time**: Late night trade ({hour}:00)\n"
        elif 6 < hour < 9:
            section += f"**Time**: Early morning trade ({hour}:00)\n"
        
        # Sequence timing
        time_since_last = timing.get('time_since_last_trade', 0)
        if time_since_last < 0.5:  # Less than 30 minutes
            section += f"**Sequence**: Quick follow-up ({time_since_last*60:.0f}m since last)\n"
        elif time_since_last > 24:  # More than a day
            section += f"**Sequence**: Return after break ({time_since_last:.0f}h gap)\n"
        
        # Market context
        if timing.get('market_conditions'):
            section += f"**Market**: {timing['market_conditions']}\n"
        
        section += '</timing>'
        return section
    
    def _summarize_trade_anonymized(self, event: Dict) -> str:
        """Create human-readable trade summary without sensitive data"""
        action = event.get('action', 'UNKNOWN')
        token = event.get('token_symbol', 'TOKEN')
        amount = event.get('amount_sol', 0)
        pnl = event.get('pnl_usd')
        
        if action.upper() == 'BUY':
            return f"Bought {amount} SOL worth of {token}"
        else:  # SELL
            if pnl is not None:
                pnl_sign = "+" if pnl >= 0 else ""
                pnl_pct = event.get('pnl_pct', 0)
                return f"Sold {token} for {pnl_sign}${abs(pnl):.0f} ({pnl_sign}{pnl_pct:.1f}%)"
            else:
                return f"Sold {amount} SOL worth of {token}"
    
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
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get context building performance metrics"""
        return {
            'build_time_ms': self.build_time_ms,
            'data_sources': self.data_sources,
            'scope': self.scope.value,
            'timestamp': self.timestamp.isoformat(),
            'context_size_bytes': len(self.to_gpt_format().encode('utf-8'))
        }


class EnhancedContextBuilder:
    """Unified context builder that combines all data sources efficiently"""
    
    def __init__(self, state_manager, conversation_manager, pattern_service=None, pnl_service=None):
        self.state_manager = state_manager
        self.conversation_manager = conversation_manager
        self.pattern_service = pattern_service
        self.pnl_service = pnl_service
        
    async def build_context(self, 
                           input_type: str, 
                           input_data: Dict[str, Any], 
                           user_id: int,
                           scope: ContextScope = ContextScope.FULL) -> EnhancedContext:
        """Build enhanced context with unified data collection"""
        
        start_time = time.time()
        data_sources = []
        
        # Generate unique context ID
        context_id = f"ctx_{user_id}_{int(start_time * 1000)}"
        
        # Determine event significance
        significance = self._assess_event_significance(input_type, input_data)
        
        # Prepare parallel data collection tasks based on scope
        tasks = []
        
        # Always get current event data
        current_event = self._format_current_event(input_type, input_data, user_id)
        
        # State manager data (positions, user stats)
        if scope in [ContextScope.FULL, ContextScope.TRADE_FOCUSED]:
            tasks.append(self._get_position_data(user_id))
            tasks.append(self._get_user_stats(user_id))
            data_sources.extend(['state_manager_positions', 'state_manager_stats'])
        
        # Conversation data (for full context)
        if scope == ContextScope.FULL:
            tasks.append(self._get_conversation_data(user_id, input_data))
            data_sources.append('conversation_manager')
        
        # Pattern data (for trade-focused and full)
        if scope in [ContextScope.FULL, ContextScope.TRADE_FOCUSED] and self.pattern_service:
            tasks.append(self._get_pattern_data(user_id, input_data))
            data_sources.append('pattern_service')
        
        # P&L data (for trade-focused and full)
        if scope in [ContextScope.FULL, ContextScope.TRADE_FOCUSED] and self.pnl_service:
            tasks.append(self._get_pnl_data(user_id, input_data))
            data_sources.append('pnl_service')
        
        # Execute all data collection in parallel
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error in parallel data collection: {e}")
            results = [None] * len(tasks)
        
        # Process results
        position_data = {}
        user_stats = {}
        conversation_data = {}
        pattern_data = {}
        trade_data = {}
        
        result_idx = 0
        
        if scope in [ContextScope.FULL, ContextScope.TRADE_FOCUSED]:
            # Position data
            if result_idx < len(results) and not isinstance(results[result_idx], Exception):
                position_data = results[result_idx] or {}
            result_idx += 1
            
            # User stats
            if result_idx < len(results) and not isinstance(results[result_idx], Exception):
                user_stats = results[result_idx] or {}
            result_idx += 1
        
        if scope == ContextScope.FULL:
            # Conversation data
            if result_idx < len(results) and not isinstance(results[result_idx], Exception):
                conversation_data = results[result_idx] or {}
            result_idx += 1
        
        if scope in [ContextScope.FULL, ContextScope.TRADE_FOCUSED] and self.pattern_service:
            # Pattern data
            if result_idx < len(results) and not isinstance(results[result_idx], Exception):
                pattern_data = results[result_idx] or {}
            result_idx += 1
        
        if scope in [ContextScope.FULL, ContextScope.TRADE_FOCUSED] and self.pnl_service:
            # P&L data
            if result_idx < len(results) and not isinstance(results[result_idx], Exception):
                trade_data = results[result_idx] or {}
            result_idx += 1
        
        # Build timing context
        timing_data = self._build_timing_context(input_data, user_stats)
        
        # Calculate build time
        build_time_ms = (time.time() - start_time) * 1000
        
        # Log performance warning if too slow
        if build_time_ms > 50:
            logger.warning(f"Context build took {build_time_ms:.1f}ms - exceeds 50ms target")
        
        return EnhancedContext(
            user_id=user_id,
            context_id=context_id,
            timestamp=datetime.now(),
            scope=scope,
            current_event=current_event,
            event_significance=significance,
            trade_context=trade_data,
            position_context=position_data,
            pattern_context=pattern_data,
            user_profile=user_stats,
            conversation_context=conversation_data,
            timing_context=timing_data,
            build_time_ms=build_time_ms,
            data_sources=data_sources
        )
    
    def _assess_event_significance(self, input_type: str, input_data: Dict) -> str:
        """Assess the significance of the current event"""
        if input_type == 'trade':
            pnl = abs(input_data.get('pnl_usd', 0))
            amount = input_data.get('amount_sol', 0)
            
            if pnl > 1000 or amount > 20:
                return "critical"
            elif pnl > 500 or amount > 10:
                return "high"
            elif pnl > 100 or amount > 2:
                return "medium"
            else:
                return "low"
        elif input_type == 'message':
            # Could analyze message content for urgency indicators
            return "medium"
        else:
            return "low"
    
    def _format_current_event(self, input_type: str, input_data: Dict, user_id: int) -> Dict[str, Any]:
        """Format current event data"""
        return {
            'type': input_type,
            'data': input_data.copy(),
            'user_id': user_id,
            'timestamp': datetime.now().isoformat()
        }
    
    async def _get_position_data(self, user_id: int) -> Dict[str, Any]:
        """Get user position data from state manager"""
        try:
            # Get notebooks directly from state manager's internal structure
            # This is a temporary solution for testing
            notebooks = {}
            if hasattr(self.state_manager, 'notebooks') and user_id in self.state_manager.notebooks:
                notebooks = self.state_manager.notebooks[user_id]
            
            # Process notebooks into position format
            positions = {}
            total_exposure = 0
            
            for token, notebook in notebooks.items():
                if notebook.get("exposure_pct", 0) > 0:
                    pnl_usd = notebook.get("live_pnl_sol", 0) * 175  # Approximate SOL to USD
                    positions[token] = {
                        "size_pct": notebook.get("exposure_pct", 0),
                        "pnl_usd": pnl_usd
                    }
                    total_exposure += notebook.get("exposure_pct", 0)
            
            return {
                "positions": positions,
                "total_positions": len(positions),
                "total_exposure_pct": total_exposure,
                "largest_position": max(positions.keys(), key=lambda k: positions[k]["size_pct"]) if positions else None
            }
        except Exception as e:
            logger.error(f"Error getting position data: {e}")
            return {}
    
    async def _get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user trading statistics from database"""
        try:
            import duckdb
            db = duckdb.connect('pocket_coach.db')
            
            # Get overall trading stats for the past week
            week_stats = db.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN pnl_usd < 0 THEN 1 ELSE 0 END) as losses,
                    AVG(sol_amount) as avg_position_size,
                    SUM(pnl_usd) as total_pnl
                FROM user_trades
                WHERE user_id = ?
                AND timestamp > CURRENT_TIMESTAMP - INTERVAL '7 days'
                AND action = 'SELL'  -- Only count completed trades
            """, [user_id]).fetchone()
            
            total_trades = week_stats[0] if week_stats[0] else 0
            wins = week_stats[1] if week_stats[1] else 0
            losses = week_stats[2] if week_stats[2] else 0
            avg_size = float(week_stats[3]) if week_stats[3] else 0
            total_pnl = float(week_stats[4]) if week_stats[4] else 0
            
            # Calculate win rate
            win_rate = float(wins / total_trades) if total_trades > 0 else 0
            
            # Get favorite tokens (most traded)
            favorite_tokens_result = db.execute("""
                SELECT token_symbol, COUNT(*) as trade_count
                FROM user_trades
                WHERE user_id = ?
                AND timestamp > CURRENT_TIMESTAMP - INTERVAL '30 days'
                GROUP BY token_symbol
                ORDER BY trade_count DESC
                LIMIT 5
            """, [user_id]).fetchall()
            
            favorite_tokens = [row[0] for row in favorite_tokens_result if row[0]]
            
            # Get recent trading session info
            session_info = db.execute("""
                SELECT COUNT(*) as session_trades
                FROM user_trades
                WHERE user_id = ?
                AND timestamp > CURRENT_TIMESTAMP - INTERVAL '24 hours'
            """, [user_id]).fetchone()
            
            session_trades = session_info[0] if session_info else 0
            
            db.close()
            
            return {
                'win_rate': win_rate,
                'total_trades_week': total_trades,
                'avg_position_size': avg_size,
                'total_wins': wins,
                'total_losses': losses,
                'favorite_tokens': favorite_tokens,
                'week_pnl': total_pnl,
                'session_trades': session_trades
            }
            
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            # Return minimal stats on error
            return {
                'win_rate': 0,
                'total_trades_week': 0,
                'avg_position_size': 0,
                'total_wins': 0,
                'total_losses': 0,
                'favorite_tokens': []
            }
    
    async def _get_conversation_data(self, user_id: int, input_data: Dict) -> Dict[str, Any]:
        """Get recent conversation data"""
        try:
            history = await self.conversation_manager.get_conversation_history(user_id, limit=10)
            
            # Filter for relevance if current event is a trade
            relevant_messages = history
            if input_data.get('token_symbol'):
                token = input_data['token_symbol']
                # Add token-specific messages
                token_messages = [
                    msg for msg in history
                    if token in str(msg.get('content', ''))
                ]
                relevant_messages = token_messages[-3:] + history[-5:]
            
            return {
                'relevant_messages': relevant_messages[-7:],  # Last 7 for context window
                'unanswered_questions': [],  # Would need to detect from conversation
                'last_response': history[-1] if history else None
            }
        except Exception as e:
            logger.error(f"Error getting conversation data: {e}")
            return {}
    
    async def _get_pattern_data(self, user_id: int, input_data: Dict) -> Dict[str, Any]:
        """Get pattern detection data from pattern service"""
        try:
            if not self.pattern_service:
                logger.warning("Pattern service not available")
                return {}
            
            # Get recent patterns from pattern service
            patterns = await self.pattern_service.get_recent_patterns(user_id, limit=10)
            
            # Process patterns into structured format
            result = {
                'recent_patterns': [],
                'primary_pattern': None,
                'overall_confidence': 'low',
                'velocity_indicators': {}
            }
            
            if patterns:
                # Extract pattern descriptions
                pattern_descriptions = []
                for pattern in patterns:
                    if isinstance(pattern, dict):
                        pattern_type = pattern.get('pattern_type', '')
                        details = pattern.get('details', {})
                        
                        # Build human-readable descriptions
                        if pattern_type == 'repeated_token':
                            token = details.get('token_symbol', 'Unknown')
                            count = details.get('trade_count', 0)
                            pattern_descriptions.append(f"Traded {token} {count} times recently")
                        elif pattern_type == 'position_size':
                            ratio = details.get('size_ratio', 1.0)
                            if ratio > 1.5:
                                pattern_descriptions.append(f"Position sizing {ratio:.1f}x larger than usual")
                            elif ratio < 0.7:
                                pattern_descriptions.append(f"Position sizing {ratio:.1f}x smaller than usual")
                        elif pattern_type == 'time_pattern':
                            time_desc = details.get('description', '')
                            if time_desc:
                                pattern_descriptions.append(time_desc)
                        elif pattern_type == 'loss_chasing':
                            pattern_descriptions.append("Chasing losses detected")
                        elif pattern_type == 'rapid_trading':
                            pattern_descriptions.append("Rapid trading sequence detected")
                
                result['recent_patterns'] = pattern_descriptions[:5]  # Top 5
                
                # Set primary pattern (most recent/relevant)
                if patterns and len(patterns) > 0:
                    primary = patterns[0]
                    if isinstance(primary, dict):
                        result['primary_pattern'] = {
                            'type': primary.get('pattern_type', 'unknown'),
                            'confidence': primary.get('confidence', 0.5)
                        }
                        
                        # Set overall confidence based on primary pattern
                        confidence_score = primary.get('confidence', 0.5)
                        if confidence_score > 0.8:
                            result['overall_confidence'] = 'high'
                        elif confidence_score > 0.6:
                            result['overall_confidence'] = 'medium'
                        else:
                            result['overall_confidence'] = 'low'
            
            # Check for rapid trading velocity
            try:
                import duckdb
                db = duckdb.connect('pocket_coach.db')
                
                # Count trades in last hour
                recent_trades = db.execute("""
                    SELECT COUNT(*) as trade_count
                    FROM user_trades
                    WHERE user_id = ?
                    AND timestamp > CURRENT_TIMESTAMP - INTERVAL '1 hour'
                """, [user_id]).fetchone()
                
                trades_last_hour = recent_trades[0] if recent_trades else 0
                
                result['velocity_indicators'] = {
                    'is_rapid_sequence': trades_last_hour >= 5,
                    'trades_last_hour': trades_last_hour
                }
                
                db.close()
                
            except Exception as e:
                logger.error(f"Error checking velocity: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting pattern data: {e}")
            return {}
    
    async def _get_pnl_data(self, user_id: int, input_data: Dict) -> Dict[str, Any]:
        """Get P&L and position data from actual P&L service"""
        try:
            if not self.pnl_service:
                logger.warning("P&L service not available")
                return {}
            
            # Get token from input data
            token_symbol = input_data.get('token_symbol')
            token_address = input_data.get('token_address') or input_data.get('token_in') or input_data.get('token_out')
            
            if not token_symbol and not token_address:
                return {}
            
            # Get current P&L for the trade/position
            result = {}
            
            # If this is a trade event, get the P&L from the trade data
            if input_data.get('pnl_usd') is not None:
                result['current_pnl_usd'] = float(input_data.get('pnl_usd', 0))
                result['current_pnl_pct'] = float(input_data.get('pnl_pct', 0)) if input_data.get('pnl_pct') else 0
            
            # Get overall user P&L from P&L service
            try:
                overall_pnl = await self.pnl_service.get_total_pnl_for_user(user_id)
                result['user_overall_pnl'] = float(overall_pnl) if overall_pnl else 0
            except Exception as e:
                logger.error(f"Error getting overall P&L: {e}")
                result['user_overall_pnl'] = 0
            
            # Get token-specific trading history
            if token_symbol:
                try:
                    import duckdb
                    db = duckdb.connect('pocket_coach.db')
                    
                    # Get token trading stats
                    token_stats = db.execute("""
                        SELECT 
                            COUNT(*) as times_traded,
                            SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
                            AVG(sol_amount) as avg_size,
                            SUM(pnl_usd) as total_pnl
                        FROM user_trades
                        WHERE user_id = ?
                        AND token_symbol = ?
                        AND action = 'SELL'
                    """, [user_id, token_symbol]).fetchone()
                    
                    if token_stats and token_stats[0] > 0:
                        times_traded, wins, avg_size, total_pnl = token_stats
                        result['times_traded_token'] = int(times_traded)
                        result['win_rate_token'] = float(wins / times_traded) if times_traded > 0 else 0
                        result['token_total_pnl'] = float(total_pnl) if total_pnl else 0
                    
                    # Get user's average position size for comparison
                    avg_position = db.execute("""
                        SELECT AVG(sol_amount)
                        FROM user_trades
                        WHERE user_id = ?
                        AND action = 'BUY'
                        AND timestamp > CURRENT_TIMESTAMP - INTERVAL '30 days'
                    """, [user_id]).fetchone()
                    
                    if avg_position and avg_position[0]:
                        current_size = float(input_data.get('amount_sol', 0))
                        avg_size = float(avg_position[0])
                        if avg_size > 0:
                            result['position_size_ratio'] = current_size / avg_size
                    
                    db.close()
                    
                except Exception as e:
                    logger.error(f"Error getting token stats: {e}")
            
            # Get unrealized P&L from current positions
            if hasattr(self.state_manager, 'notebooks') and user_id in self.state_manager.notebooks:
                notebooks = self.state_manager.notebooks[user_id]
                if token_symbol and token_symbol in notebooks:
                    notebook = notebooks[token_symbol]
                    if notebook.get("exposure_pct", 0) > 0:
                        # Calculate unrealized P&L
                        live_pnl_sol = notebook.get("live_pnl_sol", 0)
                        sol_price = 175  # Would get from price service
                        result['unrealized_pnl_usd'] = float(live_pnl_sol * sol_price)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting P&L data: {e}")
            return {}
    
    def _build_timing_context(self, input_data: Dict, user_stats: Dict) -> Dict[str, Any]:
        """Build timing and market context"""
        now = datetime.now()
        
        return {
            'trade_hour': now.hour,
            'time_since_last_trade': 0.5,  # Would calculate from last trade
            'market_conditions': None,  # Could add market data
            'is_weekend': now.weekday() >= 5,
            'session_trades': 1  # Would track from user stats
        } 