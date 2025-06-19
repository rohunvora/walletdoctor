"""
AI Context Module - Context-aware trading coach intelligence
Transforms raw trade data + conversation history into rich context for GPT-4
"""

import asyncio
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging
import time
import json
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

@dataclass
class ContextPack:
    """Rich context bundle for AI understanding"""
    
    # Core trade data
    user_id: int
    token_symbol: str
    token_address: str
    action: str  # "BUY" or "SELL"
    sol_amount: float
    timestamp: datetime
    
    # Pattern context
    pattern_type: str
    pattern_data: Dict[str, Any]
    pattern_confidence: float
    
    # Position context
    current_pnl_usd: float
    unrealized_pnl_usd: float
    position_size_ratio: float  # vs user average
    times_traded_token: int
    win_rate_token: float
    
    # Conversation context
    recent_messages: List[Dict[str, Any]]  # Last 3-5 messages
    unanswered_questions: List[str]
    last_response_tag: Optional[str]
    last_response_confidence: float
    
    # User patterns
    user_avg_position_size: float
    user_typical_hold_time: float
    user_total_trades: int
    user_overall_pnl: float
    
    # Timing context
    trade_hour: int
    time_since_last_trade: float  # hours
    is_rapid_sequence: bool
    
    def to_anonymized_dict(self) -> Dict[str, Any]:
        """Convert to dict with sensitive data anonymized for OpenAI"""
        data = asdict(self)
        
        # Remove sensitive identifiers
        data.pop('user_id', None)
        data.pop('token_address', None) 
        
        # Round financial values
        data['sol_amount'] = round(data['sol_amount'], 2)
        data['current_pnl_usd'] = round(data['current_pnl_usd'], 2)
        data['unrealized_pnl_usd'] = round(data['unrealized_pnl_usd'], 2)
        data['user_overall_pnl'] = round(data['user_overall_pnl'], 2)
        
        # Anonymize messages (keep structure, remove details)
        if data.get('recent_messages'):
            data['recent_messages'] = [
                {
                    'type': msg.get('type', 'unknown'),
                    'timestamp': msg.get('timestamp', ''),
                    'tag': msg.get('tag', ''),
                    'confidence': msg.get('confidence', 0)
                }
                for msg in data['recent_messages']
            ]
        
        return data


class AIContextCollector:
    """Collects context data from existing services"""
    
    def __init__(self, state_manager, pattern_service, conversation_manager=None, pnl_service=None):
        self.state_manager = state_manager
        self.pattern_service = pattern_service
        self.conversation_manager = conversation_manager
        self.pnl_service = pnl_service
    
    async def build_context_pack(self, trade_context: Dict, detected_patterns: List[Dict]) -> ContextPack:
        """Build complete context pack from trade data and patterns"""
        
        user_id = trade_context['user_id']
        token_address = trade_context['token_address']
        token_symbol = trade_context['token_symbol']
        
        # Get primary pattern (highest confidence)
        primary_pattern = max(detected_patterns, key=lambda p: p.get('confidence', 0)) if detected_patterns else {
            'type': 'unknown',
            'data': {},
            'confidence': 0.0
        }
        
        # Collect position context
        position_context = await self._get_position_context(user_id, token_address, trade_context)
        
        # Collect conversation context  
        conversation_context = await self._get_conversation_context(user_id, token_address)
        
        # Collect user patterns
        user_patterns = await self._get_user_patterns(trade_context['wallet_address'])
        
        # Build timing context
        timing_context = self._get_timing_context(trade_context)
        
        return ContextPack(
            # Core trade data
            user_id=user_id,
            token_symbol=token_symbol,
            token_address=token_address,
            action=trade_context['action'],
            sol_amount=trade_context['sol_amount'],
            timestamp=trade_context['timestamp'],
            
            # Pattern context
            pattern_type=primary_pattern['type'],
            pattern_data=primary_pattern['data'],
            pattern_confidence=primary_pattern['confidence'],
            
            # Position context
            current_pnl_usd=position_context['current_pnl_usd'],
            unrealized_pnl_usd=position_context['unrealized_pnl_usd'],
            position_size_ratio=position_context['position_size_ratio'],
            times_traded_token=position_context['times_traded_token'],
            win_rate_token=position_context['win_rate_token'],
            
            # Conversation context
            recent_messages=conversation_context['recent_messages'],
            unanswered_questions=conversation_context['unanswered_questions'],
            last_response_tag=conversation_context['last_response_tag'],
            last_response_confidence=conversation_context['last_response_confidence'],
            
            # User patterns
            user_avg_position_size=user_patterns['avg_position_size'],
            user_typical_hold_time=user_patterns['avg_winner_hold_minutes'],
            user_total_trades=user_patterns['total_trades'],
            user_overall_pnl=user_patterns.get('overall_pnl', 0.0),
            
            # Timing context
            trade_hour=timing_context['hour'],
            time_since_last_trade=timing_context['time_since_last'],
            is_rapid_sequence=timing_context['is_rapid_sequence']
        )
    
    async def _get_position_context(self, user_id: int, token_address: str, trade_context: Dict) -> Dict[str, Any]:
        """Collect position and P&L context"""
        context = {
            'current_pnl_usd': 0.0,
            'unrealized_pnl_usd': 0.0,
            'position_size_ratio': 1.0,
            'times_traded_token': 1,
            'win_rate_token': 0.0
        }
        
        try:
            # Try P&L service first
            if self.pnl_service:
                pnl_data = await self.pnl_service.get_token_pnl_data(
                    trade_context['wallet_address'], 
                    token_address
                )
                if pnl_data:
                    context.update({
                        'current_pnl_usd': pnl_data.get('realized_pnl_usd', 0.0),
                        'unrealized_pnl_usd': pnl_data.get('unrealized_pnl_usd', 0.0),
                        'times_traded_token': pnl_data.get('total_trades', 1),
                        'win_rate_token': pnl_data.get('win_rate', 0.0)
                    })
        except Exception as e:
            logger.warning(f"Could not collect P&L context: {e}")
        
        try:
            # Get user baselines for position size ratio
            user_baselines = self.pattern_service.get_user_baselines(trade_context['wallet_address'])
            avg_size = user_baselines.get('avg_position_size', 0)
            
            # Only calculate ratio if we have meaningful average (not default)
            if avg_size > 0:
                context['position_size_ratio'] = trade_context['sol_amount'] / avg_size
            else:
                # No meaningful average yet, don't make false claims
                context['position_size_ratio'] = 1.0  # Neutral ratio
        except Exception as e:
            logger.warning(f"Could not collect user baselines: {e}")
            # Use pattern data if available as fallback
            pattern_data = trade_context.get('pattern_data', {})
            if 'ratio' in pattern_data:
                context['position_size_ratio'] = pattern_data['ratio']
        
        return context
    
    async def _get_conversation_context(self, user_id: int, token_address: str) -> Dict[str, Any]:
        """Collect recent conversation context"""
        context = {
            'recent_messages': [],
            'unanswered_questions': [],
            'last_response_tag': None,
            'last_response_confidence': 0.0
        }
        
        try:
            if self.conversation_manager:
                # Get recent user notes (last 3 days for context)
                recent_notes = await self.conversation_manager.get_user_notes(user_id, days=3)
                
                # Filter for this token if possible and convert to expected format
                token_notes = []
                for note in recent_notes:
                    if note.get('token_symbol') == token_address or not token_address:
                        token_notes.append({
                            'type': 'user_response',
                            'timestamp': note.get('timestamp', ''),
                            'tag': note.get('pattern_type', ''),
                            'confidence': 1.0,
                            'text': note.get('response', '')
                        })
                
                context['recent_messages'] = token_notes[-5:]  # Last 5 messages
                
                # Get last response details using the conversation manager method
                last_response = await self.conversation_manager.get_last_response(
                    user_id, token_address
                )
                if last_response:
                    context['last_response_tag'] = last_response.get('pattern_type')
                    context['last_response_confidence'] = last_response.get('confidence', 0.0)
            
            # Get open questions from state manager
            notebook = await self.state_manager.get_notebook(user_id, token_address)
            if notebook.get('unanswered_question'):
                context['unanswered_questions'] = [notebook.get('question_msg_id')]
                
        except Exception as e:
            logger.warning(f"Could not collect conversation context: {e}")
        
        return context
    
    async def _get_user_patterns(self, wallet_address: str) -> Dict[str, Any]:
        """Collect user's overall trading patterns"""
        try:
            patterns = self.pattern_service.get_user_baselines(wallet_address)
            # Ensure all required fields exist
            return {
                'avg_position_size': patterns.get('avg_position_size', 1.0),
                'avg_winner_hold_minutes': patterns.get('avg_winner_hold_minutes', 0),
                'total_trades': patterns.get('total_trades', 0),
                'overall_pnl': patterns.get('overall_pnl', 0.0)
            }
        except Exception as e:
            logger.warning(f"Could not collect user patterns: {e}")
            return {
                'avg_position_size': 1.0,
                'avg_winner_hold_minutes': 0,
                'total_trades': 0,
                'overall_pnl': 0.0
            }
    
    def _get_timing_context(self, trade_context: Dict) -> Dict[str, Any]:
        """Collect timing and sequence context"""
        now = trade_context['timestamp']
        
        return {
            'hour': now.hour,
            'time_since_last': 0.0,  # TODO: Calculate from last trade
            'is_rapid_sequence': False  # TODO: Detect rapid trading
        }


class AIIntentClassifier:
    """GPT-4 powered intent classification for trading messages"""
    
    def __init__(self, openai_client: AsyncOpenAI, config: Dict = None):
        self.client = openai_client
        self.config = config or {}
        self.timeout = self.config.get('timeout', 3.0)  # Increased timeout for better reliability
        self.model = self.config.get('model', 'gpt-4o-mini')
    
    async def classify_intent(self, context_pack: ContextPack, user_message: str = None) -> Dict[str, Any]:
        """
        Classify user intent based on full context
        
        Returns:
            {
                'intent': str,  # stop_loss, profit_taking, hold_decision, etc.
                'confidence': float,
                'reasoning': str,
                'suggested_response': str,
                'latency': float
            }
        """
        start_time = time.time()
        
        try:
            # Build context-aware prompt
            prompt = self._build_classification_prompt(context_pack, user_message)
            
            # Call GPT-4 with timeout
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self._get_system_prompt()},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300,
                    temperature=0.1
                ),
                timeout=self.timeout
            )
            
            # Parse response
            result = self._parse_classification_response(response.choices[0].message.content)
            result['latency'] = time.time() - start_time
            result['method'] = 'gpt4'
            
            return result
            
        except asyncio.TimeoutError:
            logger.warning(f"GPT classification timed out after {self.timeout}s")
            return self._timeout_fallback(context_pack, time.time() - start_time)
        except Exception as e:
            logger.error(f"GPT classification error: {e}")
            return self._error_fallback(context_pack, time.time() - start_time, str(e))
    
    def _get_system_prompt(self) -> str:
        """System prompt for intent classification"""
        return """You are an expert trading psychology analyst. Your job is to understand trader intent from context.

TASK: Classify the trader's intent based on their current trade and full context.

INTENTS:
- stop_loss: Cutting losses, damage control
- profit_taking: Securing gains, taking money off table  
- position_sizing: Testing, adding to position, scaling
- fomo_chase: Fear of missing out, chasing momentum
- revenge_trading: Trading emotionally after losses
- uncertain_exit: Unsure about exit strategy
- strategic_move: Planned, thesis-driven trade

RESPONSE FORMAT (JSON):
{
    "intent": "intent_name",
    "confidence": 0.85,
    "reasoning": "Brief explanation of why",
    "key_signals": ["signal1", "signal2"]
}

Be concise and focus on the strongest signals from the context."""
    
    def _build_classification_prompt(self, context_pack: ContextPack, user_message: str = None) -> str:
        """Build context-aware classification prompt"""
        
        # Anonymize context for OpenAI
        ctx = context_pack.to_anonymized_dict()
        
        prompt_parts = [
            f"CURRENT TRADE: {ctx['action']} {ctx['sol_amount']} SOL of {ctx['token_symbol']}",
            f"PATTERN: {ctx['pattern_type']} (confidence: {ctx['pattern_confidence']:.2f})",
        ]
        
        # Add P&L context
        if ctx['current_pnl_usd'] != 0:
            pnl_status = "UP" if ctx['current_pnl_usd'] > 0 else "DOWN"
            prompt_parts.append(f"POSITION P&L: {pnl_status} ${abs(ctx['current_pnl_usd']):.0f}")
        
        if ctx['unrealized_pnl_usd'] != 0:
            unrealized_status = "UP" if ctx['unrealized_pnl_usd'] > 0 else "DOWN"
            prompt_parts.append(f"UNREALIZED P&L: {unrealized_status} ${abs(ctx['unrealized_pnl_usd']):.0f}")
        
        # Add position size context
        if ctx['position_size_ratio'] > 2.0:
            prompt_parts.append(f"POSITION SIZE: {ctx['position_size_ratio']:.1f}x larger than usual")
        elif ctx['position_size_ratio'] < 0.5:
            prompt_parts.append(f"POSITION SIZE: {ctx['position_size_ratio']:.1f}x smaller than usual")
        
        # Add repeat trading context
        if ctx['times_traded_token'] > 1:
            prompt_parts.append(f"REPEAT TRADE: {ctx['times_traded_token']} times on this token")
            if ctx['win_rate_token'] > 0:
                prompt_parts.append(f"TOKEN WIN RATE: {ctx['win_rate_token']:.1%}")
        
        # Add timing context
        if ctx['trade_hour'] >= 22 or ctx['trade_hour'] <= 6:
            prompt_parts.append(f"TIMING: Late night trade at {ctx['trade_hour']}:00")
        
        # Add conversation context
        if ctx.get('last_response_tag'):
            prompt_parts.append(f"RECENT TAG: {ctx['last_response_tag']}")
        
        # Add user message if provided
        if user_message:
            prompt_parts.append(f"USER MESSAGE: '{user_message}'")
        
        return "\n".join(prompt_parts)
    
    def _parse_classification_response(self, response_text: str) -> Dict[str, Any]:
        """Parse GPT response into structured result"""
        try:
            # Try to parse as JSON
            if response_text.strip().startswith('{'):
                parsed = json.loads(response_text)
                return {
                    'intent': parsed.get('intent', 'unknown'),
                    'confidence': float(parsed.get('confidence', 0.5)),
                    'reasoning': parsed.get('reasoning', ''),
                    'key_signals': parsed.get('key_signals', []),
                    'suggested_response': ''
                }
        except json.JSONDecodeError:
            pass
        
        # Fallback parsing
        lines = response_text.strip().split('\n')
        intent = 'unknown'
        confidence = 0.5
        reasoning = response_text[:100]
        
        for line in lines:
            if 'intent' in line.lower():
                intent = line.split(':')[-1].strip().strip('"').strip("'")
            elif 'confidence' in line.lower():
                try:
                    confidence = float(line.split(':')[-1].strip())
                except:
                    pass
        
        return {
            'intent': intent,
            'confidence': confidence,
            'reasoning': reasoning,
            'key_signals': [],
            'suggested_response': ''
        }
    
    def _timeout_fallback(self, context_pack: ContextPack, latency: float) -> Dict[str, Any]:
        """Fallback when GPT times out"""
        # Simple heuristic based on P&L
        if context_pack.current_pnl_usd < -50 or context_pack.unrealized_pnl_usd < -50:
            intent = 'stop_loss'
            confidence = 0.6
        elif context_pack.current_pnl_usd > 50 or context_pack.unrealized_pnl_usd > 50:
            intent = 'profit_taking'
            confidence = 0.6
        else:
            intent = 'unknown'
            confidence = 0.3
        
        return {
            'intent': intent,
            'confidence': confidence,
            'reasoning': 'GPT timeout - heuristic fallback',
            'key_signals': ['timeout_fallback'],
            'suggested_response': '',
            'latency': latency,
            'method': 'fallback'
        }
    
    def _error_fallback(self, context_pack: ContextPack, latency: float, error: str) -> Dict[str, Any]:
        """Fallback when GPT errors"""
        return {
            'intent': 'unknown',
            'confidence': 0.1,
            'reasoning': f'GPT error: {error}',
            'key_signals': ['error_fallback'],
            'suggested_response': '',
            'latency': latency,
            'method': 'error'
        }


# Factory function for easy integration
def create_ai_context_system(state_manager, pattern_service, openai_client, 
                           conversation_manager=None, pnl_service=None, config=None) -> Tuple[AIContextCollector, AIIntentClassifier]:
    """Create AI context system components"""
    collector = AIContextCollector(
        state_manager=state_manager,
        pattern_service=pattern_service,
        conversation_manager=conversation_manager,
        pnl_service=pnl_service
    )
    
    classifier = AIIntentClassifier(
        openai_client=openai_client,
        config=config or {}
    )
    
    return collector, classifier 