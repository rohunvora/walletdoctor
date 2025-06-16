"""
Nudge Engine - Swappable architecture for conversational trading coach
Today: Rule-based question generation
Tomorrow: AI-powered with one config change  
"""

from typing import Dict, Tuple, Optional, List
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import logging
import asyncio
import re
import time
import os
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class NudgeEngine:
    """
    Question-based nudge generator
    Designed to be swappable - rules today, AI tomorrow
    """
    
    def __init__(self, strategy: str = "rules", config: Dict = None):
        """
        Initialize nudge engine
        
        Args:
            strategy: "rules" or "ai" - determines generation method
            config: Additional configuration (API keys, endpoints, etc.)
        """
        self.strategy = strategy
        self.config = config or {}
        self.question_templates = self._load_question_templates()
        
        # Text-first mode configuration
        self.text_first_mode = self.config.get("text_first_mode", True)
        
        # Initialize OpenAI client if API key provided
        self.openai_client = None
        openai_api_key = self.config.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
        if openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=openai_api_key)
        
        # Regex patterns for fallback tagging
        self.tag_patterns = {
            # Emotional/psychological patterns
            r'\b(fomo|fear|missing out|late to)\b': 'fomo',
            r'\b(revenge|angry|mad|recover|get back)\b': 'revenge_trade',
            r'\b(panic|scared|dump|crash)\b': 'panic_sell',
            r'\b(gut|feel|vibe|feeling|instinct)\b': 'intuition',
            
            # Following others
            r'\b(whale|follow|copy|wallet|smart money|insider)\b': 'whale_follow',
            r'\b(everyone|they|people|crowd|hype)\b': 'crowd_follow',
            
            # Price action
            r'\b(dip|discount|cheap|low|bottom)\b': 'buying_dip',
            r'\b(pump|moon|rocket|flying|rip)\b': 'chasing_pump',
            r'\b(profit|gains|cash out|green|up)\b': 'taking_profits',
            r'\b(stop|loss|cut|red|down)\b': 'stop_loss',
            
            # Strategy
            r'\b(test|try|experiment|small|toe)\b': 'testing',
            r'\b(news|announcement|alpha|catalyst)\b': 'news_based',
            r'\b(dca|average|adding|accumulate)\b': 'adding_position',
            
            # Uncertainty  
            r'\b(idk|dunno|maybe|perhaps|guess|hope)\b': 'uncertain',
            r'\b(no idea|no clue|not sure|don\'t know)\b': 'uncertain_exit',
            r'\b(target|goal|exit|plan)\b.*\b(no|none|idk|dunno)\b': 'no_target'
        }
    
    def get_nudge(self, context: Dict) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
        """
        Main interface - returns question and optional keyboard
        
        Args:
            context: Trade context with pattern data
            
        Returns:
            Tuple of (question_text, inline_keyboard or None)
        """
        if self.strategy == "ai":
            return self._ai_nudge(context)
        else:
            return self._rule_based_nudge(context)
    
    def _rule_based_nudge(self, context: Dict) -> Tuple[str, InlineKeyboardMarkup]:
        """Generate question-based nudge using templates"""
        pattern_type = context["pattern_type"]
        pattern_data = context["pattern_data"]
        previous_response = context.get("previous_response")
        
        if pattern_type not in self.question_templates:
            return "Interesting trade!", None
        
        template = self.question_templates[pattern_type]
        
        # Handle BUY vs SELL for action-specific patterns
        if pattern_type in ["repeat_token", "position_size"]:
            action = pattern_data.get("action", "BUY")
            if action == "SELL":
                # Check if this is a final exit for repeat_token
                if pattern_type == "repeat_token":
                    is_final = pattern_data.get("is_final_exit", False)
                    is_partial = pattern_data.get("is_partial_exit", False)
                    
                    # Check P&L to determine profit or loss
                    total_pnl = pattern_data.get("total_pnl", 0)
                    unrealized_pnl = pattern_data.get("unrealized_pnl_usd", 0)
                    
                    # Use total P&L if available, otherwise unrealized
                    pnl = total_pnl if total_pnl != 0 else unrealized_pnl
                    is_loss = pnl < 0
                    
                    if is_final:
                        if is_loss and "sell_question_final_loss" in template:
                            question = template["sell_question_final_loss"].format(**pattern_data)
                        elif "sell_question_final" in template:
                            question = template["sell_question_final"].format(**pattern_data)
                        else:
                            question = template["sell_question_loss" if is_loss else "sell_question"].format(**pattern_data)
                    elif is_partial:
                        if is_loss and "sell_question_partial_loss" in template:
                            question = template["sell_question_partial_loss"].format(**pattern_data)
                        elif "sell_question_partial" in template:
                            question = template["sell_question_partial"].format(**pattern_data)
                        else:
                            question = template["sell_question_loss" if is_loss else "sell_question"].format(**pattern_data)
                    else:
                        # For position_size, check P&L for sells
                        if pattern_type == "position_size":
                            # Try to get P&L from pattern data
                            pnl = pattern_data.get("pnl_usd", 0) or pattern_data.get("total_pnl", 0)
                            is_loss = pnl < 0
                            
                            if is_loss and "sell_question_loss" in template:
                                question = template["sell_question_loss"].format(**pattern_data)
                            else:
                                question = template["sell_question"].format(**pattern_data)
                        else:
                            # Default sell question based on P&L
                            if is_loss and "sell_question_loss" in template:
                                question = template["sell_question_loss"].format(**pattern_data)
                            else:
                                question = template["sell_question"].format(**pattern_data)
                else:
                    question = template["sell_question"].format(**pattern_data)
                    
                buttons = template["sell_buttons"]
            else:
                question = template["buy_question"].format(**pattern_data)
                buttons = template["buy_buttons"]
        else:
            # For other patterns, use single question/buttons
            question = template["question"].format(**pattern_data)
            buttons = template["buttons"]
        
        # Add insightful memory callback if available
        if previous_response and previous_response.get("confidence", 0) > 0.7:
            # Pass conversation_manager if available in context
            conversation_manager = context.get("conversation_manager")
            memory_callback = self._format_memory_callback(
                previous_response, 
                context,
                conversation_manager
            )
            if memory_callback:
                question += memory_callback
        
        # Create keyboard based on mode
        if self.text_first_mode:
            # Text-first mode: minimal UI, no corny prompt
            keyboard = None  # No buttons in text-first mode
        else:
            # Button mode: Create full keyboard
            keyboard = self._create_keyboard(buttons)
        
        return question, keyboard
    
    def _format_memory_callback(self, previous_response: Dict, current_context: Dict, 
                               conversation_manager=None) -> str:
        """Format memory callback with actual trade history, not just responses"""
        from datetime import datetime
        import asyncio
        
        prev_text = previous_response.get('text', '')
        prev_metadata = previous_response.get('metadata', {})
        prev_tag = prev_metadata.get('tag', 'unknown')
        
        current_action = current_context.get('pattern_data', {}).get('action', 'BUY')
        pattern_type = current_context.get('pattern_type')
        token_address = current_context.get('pattern_data', {}).get('token_address')
        user_id = current_context.get('user_id')
        
        # If we have conversation_manager, get actual trade history
        if conversation_manager and token_address and user_id:
            try:
                # Get last actual trade (not response) for this token
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create task to run async method
                    last_trade_task = asyncio.create_task(
                        conversation_manager.get_last_trade(user_id, token_address)
                    )
                    last_trade = asyncio.run_coroutine_threadsafe(
                        last_trade_task, loop
                    ).result(timeout=1.0)
                else:
                    last_trade = asyncio.run(
                        conversation_manager.get_last_trade(user_id, token_address)
                    )
                
                if last_trade:
                    # Use actual trade data
                    prev_action = last_trade['action']
                    prev_timestamp = last_trade['timestamp']
                    
                    # Calculate time difference
                    time_diff = ""
                    if prev_timestamp:
                        try:
                            prev_dt = datetime.fromisoformat(str(prev_timestamp)) if isinstance(prev_timestamp, str) else prev_timestamp
                            hours_ago = (datetime.now() - prev_dt).total_seconds() / 3600
                            
                            if hours_ago < 1:
                                mins_ago = int(hours_ago * 60)
                                time_diff = f"{mins_ago}min ago"
                            elif hours_ago < 24:
                                time_diff = f"{int(hours_ago)}h ago"
                            else:
                                days_ago = int(hours_ago / 24)
                                time_diff = f"{days_ago}d ago"
                        except:
                            pass
                    
                    # Format based on actual trade history
                    if pattern_type == 'repeat_token' and current_action == 'SELL':
                        if prev_action == 'SELL':
                            return f"\n\n📉 Sold {time_diff} too. Exiting completely?"
                        else:  # prev was BUY
                            if prev_text:
                                return f"\n\n🔄 Bought {time_diff}: \"{prev_text}\" — how'd that work out?"
                            else:
                                return f"\n\n🔄 Bought {time_diff}. Taking profits?"
                    
                    elif pattern_type == 'repeat_token' and current_action == 'BUY':
                        if prev_action == 'SELL':
                            return f"\n\n📈 Sold {time_diff}. Back for more?"
                        else:  # prev was BUY
                            return f"\n\n🔄 Bought {time_diff} too. Adding to position?"
                    
                    elif pattern_type == 'position_size' and current_action == 'SELL':
                        # Check if this might be final exit
                        position_task = asyncio.create_task(
                            conversation_manager.get_token_position_history(user_id, token_address)
                        )
                        position = asyncio.run_coroutine_threadsafe(
                            position_task, loop
                        ).result(timeout=1.0)
                        
                        if position and position['sell_count'] > 1:
                            return f"\n\n📊 Sell #{position['sell_count']} on this token. Final exit?"
                        elif time_diff:
                            return f"\n\n🔄 {prev_action} {time_diff}"
                
            except Exception as e:
                logger.debug(f"Could not fetch trade history: {e}")
                # Fall back to response-based callback
        
        # Original response-based callback as fallback
        prev_timestamp = previous_response.get('timestamp')
        
        # Calculate time difference
        time_diff = ""
        if prev_timestamp:
            try:
                prev_dt = datetime.fromisoformat(prev_timestamp) if isinstance(prev_timestamp, str) else prev_timestamp
                hours_ago = (datetime.now() - prev_dt).total_seconds() / 3600
                
                if hours_ago < 1:
                    mins_ago = int(hours_ago * 60)
                    time_diff = f"{mins_ago}min ago"
                elif hours_ago < 24:
                    time_diff = f"{int(hours_ago)}h ago"
                else:
                    days_ago = int(hours_ago / 24)
                    time_diff = f"{days_ago}d ago"
            except:
                pass
        
        # Contextual memory callbacks based on pattern and tag combination
        if current_action == 'SELL' and prev_tag in ['fomo', 'whale_follow']:
            return f"\n\n🔄 {time_diff}: \"{prev_text}\" — how'd that work out?"
        
        elif pattern_type == 'repeat_token' and prev_tag == 'revenge_trade':
            return f"\n\n⚠️ Last revenge trade here didn't end well..."
        
        elif pattern_type == 'repeat_token' and current_action == 'BUY':
            if prev_tag in ['stop_loss', 'panic_sell']:
                return f"\n\n📉 Last exit: \"{prev_text}\""
            else:
                return f"\n\n🔄 {time_diff}: \"{prev_text}\" — same thesis?"
        
        elif prev_tag in ['uncertain_exit', 'no_target'] and current_action == 'SELL':
            return f"\n\n📊 Still \"{prev_text}\" or found your target?"
        
        elif pattern_type == 'position_size' and prev_tag == 'testing':
            return f"\n\n🧪 Last \"test\" at this size: \"{prev_text}\""
        
        # Time-based callbacks
        elif time_diff:
            if "min" in time_diff:
                return f"\n\n💭 Just {time_diff}: \"{prev_text}\" — still true?"
            elif "h" in time_diff and int(time_diff.split('h')[0]) < 6:
                return f"\n\n🕐 {time_diff}: \"{prev_text}\" — quick change?"
            else:
                return f"\n\n📅 {time_diff}: \"{prev_text}\""
        
        # Fallback: Simple callback without being lazy
        return f"\n\nLast time you said: \"{prev_text}\""
    
    def _ai_nudge(self, context: Dict) -> Tuple[str, InlineKeyboardMarkup]:
        """Placeholder for AI-powered nudge generation"""
        # This is where GPT-4 or fine-tuned model would generate
        # For now, just fall back to rules
        return self._rule_based_nudge(context)
    
    def _finetuned_nudge(self, context: Dict) -> Tuple[str, InlineKeyboardMarkup]:
        """Fine-tuned model nudge generation (future implementation)"""  
        # TODO: Implement fine-tuned model
        # For now, fall back to rules
        return self._rule_based_nudge(context)
    
    def _create_keyboard(self, button_options: List[str]) -> InlineKeyboardMarkup:
        """Create inline keyboard from button options"""
        keyboard = []
        row = []
        
        for i, option in enumerate(button_options):
            callback_data = f"note:{option.lower().replace(' ', '_')}"
            button = InlineKeyboardButton(option, callback_data=callback_data)
            row.append(button)
            
            # Two buttons per row, start new row after every 2 buttons
            if len(row) == 2 or i == len(button_options) - 1:
                keyboard.append(row)
                row = []
        
        return InlineKeyboardMarkup(keyboard)
    
    def _create_minimal_keyboard(self) -> InlineKeyboardMarkup:
        """Create a minimal keyboard with a skip button"""
        keyboard = [
            [InlineKeyboardButton("🫥 Skip", callback_data="skip")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def _load_question_templates(self) -> Dict:
        """Load question templates with trader-native buttons"""
        return {
            "position_size": {
                "buy_question": "Big jump in size ({ratio:.1f}×)—what's the thinking?",
                "sell_question": "Large sell ({ratio:.1f}×)—taking profits or panic?",
                "sell_question_loss": "Large sell ({ratio:.1f}×)—cutting losses or panic?",
                "buy_buttons": ["FOMO", "Alpha", "Good wallets", "Other..."],
                "sell_buttons": ["Taking profits", "Stop loss", "Panic sell", "Other..."]
            },
            
            "repeat_token": {
                "buy_question": "{token_symbol} again? What's different this time?",
                "sell_question": "Taking some {token_symbol} profits?",
                "sell_question_loss": "Cutting {token_symbol} losses?",  # For losses
                "sell_question_final": "Closing out {token_symbol} completely?",  # For final exits
                "sell_question_final_loss": "Giving up on {token_symbol}?",  # For final loss exits
                "sell_question_partial": "Trimming {token_symbol} position?",  # For partial sells
                "sell_question_partial_loss": "Reducing {token_symbol} exposure?",  # For partial loss sells
                "buy_buttons": ["Revenge", "New alpha", "Adding dip", "Other..."],
                "sell_buttons": ["Taking profits", "Stop loss", "Getting out", "Other..."]
            },
            
            "hold_time": {
                "question": "Still holding—what's the plan?",
                "buttons": ["Moon bag", "Quick flip", "No plan", "Other..."]
            },
            
            "dust_trade": {
                "question": "Tiny position—testing waters?",
                "buttons": ["Testing", "All I got", "Gas money", "Other..."]
            },
            
            "round_number": {
                "question": "Exactly {sol_amount:.0f} SOL—special reason?",
                "buttons": ["Clean math", "FOMO", "Lucky number", "Other..."]
            },
            
            "late_night": {
                "question": "{hour}AM trade—couldn't wait?",
                "buttons": ["Degen hours", "Global play", "Can't sleep", "Other..."]
            },
            
            # Default for unknown patterns
            "default": {
                "question": "What's the play here?",
                "buttons": ["FOMO", "Alpha", "Testing", "Other..."]
            }
        }
    
    def update_strategy(self, new_strategy: str):
        """Hot-swap the nudge generation strategy"""
        if new_strategy in ["rules", "gpt4", "finetuned"]:
            self.strategy = new_strategy
            logger.info(f"Nudge engine strategy updated to: {new_strategy}")
        else:
            raise ValueError(f"Invalid strategy: {new_strategy}")
    
    async def extract_tag_from_text(self, user_text: str, context: Dict) -> Dict[str, any]:
        """
        Extract a tag from user's free text response
        
        Args:
            user_text: Raw text from user
            context: Trade context for additional info
            
        Returns:
            Dict with tag, confidence, and method used
        """
        start_time = time.time()
        
        # Store context for regex fallback
        self.config['current_pattern_type'] = context.get('pattern_type')
        self.config['current_action'] = context.get('pattern_data', {}).get('action', 'BUY')
        
        # Try GPT first if available
        if self.openai_client:
            try:
                tag_result = await asyncio.wait_for(
                    self._gpt_extract_tag(user_text, context),
                    timeout=2.0
                )
                tag_result['latency'] = time.time() - start_time
                tag_result['method'] = 'gpt'
                return tag_result
            except asyncio.TimeoutError:
                logger.warning("GPT tagging timed out after 2s, falling back to regex")
            except Exception as e:
                logger.error(f"GPT tagging error: {e}, falling back to regex")
        
        # Fallback to regex
        tag_result = self._regex_extract_tag(user_text)
        tag_result['latency'] = time.time() - start_time
        tag_result['method'] = 'regex'
        return tag_result
    
    async def _gpt_extract_tag(self, user_text: str, context: Dict) -> Dict[str, any]:
        """Extract tag using GPT-4o-mini with better context"""
        action = context.get('pattern_data', {}).get('action', 'BUY')
        token = context.get('pattern_data', {}).get('token_symbol', 'token')
        pattern_type = context.get('pattern_type', 'unknown')
        
        # Map pattern types to what they're really asking about
        pattern_context = {
            'position_size': 'their reasoning for the unusual size of this trade',
            'repeat_token': 'why they are trading this token again', 
            'hold_time': 'their exit strategy or holding plan',
            'round_number': 'why they chose this exact round amount',
            'late_night': 'why they are trading at this late hour',
            'dust_trade': 'why such a small position size'
        }
        
        context_hint = pattern_context.get(pattern_type, 'their trading decision')
        
        # Action-specific tags
        buy_tags = """
- fomo (fear of missing out)
- whale_follow (following other traders)
- buying_dip (buying on price drop)
- news_based (reacting to news/announcement)
- alpha_tip (insider info or tip)
- dca_strategy (dollar cost averaging)
- testing (experimenting with small size)
- intuition (gut feeling)
- revenge_trade (trying to recover losses)
- adding_position (increasing existing position)"""

        sell_tags = """
- taking_profits (securing gains)
- stop_loss (cutting losses)
- panic_sell (emotional selling)
- uncertain_exit (unsure about targets)
- no_target (no specific price target)
- portfolio_rebalance (adjusting holdings)"""

        common_tags = """
- uncertain (general uncertainty)
- complex_strategy (multiple reasons/strategies)
- other (doesn't fit categories)"""
        
        relevant_tags = sell_tags if action == 'SELL' else buy_tags
        
        prompt = f"""Extract a 2-3 word tag from this trader's response about {context_hint}.

Context: Trader just made a {action} trade of {token}
Pattern detected: {pattern_type}
Trader's response: "{user_text}"

Based on the response meaning and context, which tag best fits?

{relevant_tags}
{common_tags}

Analyze what the trader is ACTUALLY saying. Look for:
- Multiple strategies mentioned → complex_strategy
- DCA/averaging mentions → dca_strategy  
- Tips/insider info → alpha_tip
- News/endorsements → news_based
- Testing small → testing

Priority: If both DCA and alpha/tip/insider info mentioned → alpha_tip (more specific)

Examples:
- "DCA'ing small, got alpha tip about endorsement" → alpha_tip
- "yeah idk how high it goes" → uncertain_exit
- "whales are buying hard" → whale_follow
- "testing the waters" → testing
- "averaging in slowly" → dca_strategy
- "heard Marc Andressen might endorse" → alpha_tip

Return ONLY the most fitting tag, nothing else. Use snake_case."""

        response = await self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=20
        )
        
        tag = response.choices[0].message.content.strip().lower()
        tag = re.sub(r'[^a-z0-9_]', '_', tag)  # Clean to snake_case
        
        return {
            'tag': tag,
            'confidence': 0.9,  # High confidence for GPT
            'original_text': user_text
        }
    
    def _regex_extract_tag(self, user_text: str) -> Dict[str, any]:
        """Extract tag using regex patterns with context awareness"""
        user_text_lower = user_text.lower()
        
        # Pattern-specific regex based on context
        context_pattern_type = self.config.get('current_pattern_type')
        action = self.config.get('current_action', 'BUY')
        
        # Special handling for certain responses
        if context_pattern_type == 'position_size' and action == 'SELL':
            # For large sells, check exit-specific patterns first
            exit_patterns = {
                r'\b(profit|gains|green|up|cash)\b': 'taking_profits',
                r'\b(stop|loss|cut|limit|protection)\b': 'stop_loss', 
                r'\b(panic|scared|dump|fear)\b': 'panic_sell',
                r'(idk|dunno).*\b(high|far|target|exit)\b': 'uncertain_exit',
                r'\b(no|don\'t have).*\b(target|plan|idea)\b': 'no_target'
            }
            
            for pattern, tag in exit_patterns.items():
                if re.search(pattern, user_text_lower):
                    return {
                        'tag': tag,
                        'confidence': 0.75,
                        'original_text': user_text
                    }
        
        # Check general patterns
        for pattern, tag in self.tag_patterns.items():
            if re.search(pattern, user_text_lower):
                return {
                    'tag': tag,
                    'confidence': 0.7,  # Lower confidence for regex
                    'original_text': user_text
                }
        
        # Default if no pattern matches
        return {
            'tag': 'other',
            'confidence': 0.5,
            'original_text': user_text
        }
    
    def format_tag_response(self, tag_info: Dict) -> str:
        """Format the bot's response after tagging - more conversational for rich responses"""
        tag = tag_info['tag']
        confidence = tag_info['confidence']
        original_text = tag_info.get('original_text', '')
        
        # Convert snake_case to readable format
        readable_tag = tag.replace('_', ' ')
        
        # Detect rich/detailed responses
        word_count = len(original_text.split())
        has_specific_details = any(indicator in original_text.lower() for indicator in [
            'alpha', 'tip', 'endorsed', 'dca', 'target', 'until', 'holding',
            'shakeout', 'volatile', 'because', 'since', 'but', 'although'
        ])
        
        # For short, simple responses
        if word_count <= 10 and not has_specific_details:
            if confidence >= 0.8:
                return f"**{readable_tag}** noted"
            else:
                return f"_{readable_tag}?_"
        
        # For rich, detailed responses - be more conversational
        if word_count > 30 or has_specific_details:
            tag_responses = {
                'news_based': [
                    "Insider alpha play — bold move with this volatility",
                    "Trading on tips — hope the source is solid", 
                    "News catalyst trade noted — what's your stop loss?",
                    "Alpha tip + DCA strategy. Interesting combo"
                ],
                'alpha_tip': [
                    "Insider alpha 👀 — how confident in that source?",
                    "Trading on tips in this volatility — brave or reckless?",
                    "Alpha play noted — what's the timeline on this?",
                    "Exclusive info trade — hope it pans out"
                ],
                'dca_strategy': [
                    "DCA'ing through volatility — respect the discipline",
                    "Averaging in systematically. What's your target size?",
                    "Dollar cost averaging play — patient approach",
                    "Building position gradually — smart in this chop"
                ],
                'complex_strategy': [
                    "Multi-layered approach — playing 4D chess here",
                    "Combining strategies — sophisticated or overthinking?",
                    "Complex reasoning noted — lot of moving parts",
                    "Multiple angles on this trade — interesting"
                ],
                'adding_position': [
                    "DCA'ing through the chaos — respect the conviction",
                    "Averaging in despite volatility. Iron hands or stubbornness?",
                    "Building position gradually — smart or catching knives?"
                ],
                'testing': [
                    "Testing with volatility this high? Brave",
                    "Small position to test the thesis — sensible"
                ],
                'intuition': [
                    "Gut feel in this market — living dangerously",
                    "Trusting instincts over charts. Sometimes works"
                ],
                'whale_follow': [
                    "Following smart money — they wrong sometimes too",
                    "Whale watching pays... until it doesn't"
                ]
            }
            
            # Get contextual response based on tag
            responses = tag_responses.get(tag, [])
            if responses:
                import random
                response = random.choice(responses)
                return f"{response}"
            
            # Fallback for unmatched tags - still conversational
            return f"**{readable_tag}** — interesting reasoning"
        
        # Medium responses - acknowledge but don't overdo it
        if confidence >= 0.8:
            return f"**{readable_tag}** — got it"
        else:
            return f"_{readable_tag}_ noted"
    
    def generate_clarifier(self, user_response: str, pattern_type: str, context: Dict) -> Optional[str]:
        """
        Generate a follow-up clarifier question based on user response
        
        Args:
            user_response: The user's initial response
            pattern_type: The pattern type that triggered the original question
            context: Additional context about the trade
            
        Returns:
            Clarifier question string or None if no clarifier needed
        """
        # Normalize response
        response_lower = user_response.lower().strip()
        
        # Pattern-specific clarifiers
        clarifier_map = {
            'position_size': {
                'fomo': "Gut feel or saw flow?",
                'alpha': "Your find or following someone?", 
                'good wallets': "Which wallet caught your eye?",
                'whale': "Specific whale or just vibes?",
                'testing': "Testing what thesis?"
            },
            'repeat_token': {
                'revenge': "Same setup or pure emotion?",
                'new alpha': "What changed?",
                'adding dip': "Planned DCA or catching knife?",
                'different': "Different how?",
                'again': "Why this time?"
            },
            'hold_time': {
                'moon bag': "Got a target?",
                'quick flip': "Exit plan?",
                'no plan': "What usually makes you exit?",
                'waiting': "For what signal?",
                'holding': "Until when?"
            },
            'dust_trade': {
                'testing': "Testing what exactly?",
                'all i got': "Saving rest for something?",
                'gas money': "Quick flip expected?",
                'small': "Why so small?",
                'broke': "Capital management or just broke?"
            },
            'round_number': {
                'clean math': "Always trade rounds?",
                'fomo': "Price or size FOMO?",
                'lucky number': "Your go-to number?",
                'round': "Superstition or strategy?",
                'exact': "Calculated or coincidence?"
            },
            'late_night': {
                'degen hours': "Best trades at night?",
                'global play': "Following Asia?",
                "can't sleep": "Trading keeping you up?",
                'insomnia': "Always trade when can't sleep?",
                'late': "Time zone or lifestyle?"
            }
        }
        
        # Get relevant clarifiers for this pattern
        pattern_clarifiers = clarifier_map.get(pattern_type, {})
        
        # Check for exact matches first
        if response_lower in pattern_clarifiers:
            return pattern_clarifiers[response_lower]
        
        # Check for partial matches
        for key, clarifier in pattern_clarifiers.items():
            if key in response_lower:
                return clarifier
        
        # Generic clarifiers for very short responses
        if len(response_lower.split()) <= 2:
            generic_clarifiers = {
                'yes': "Yes to what specifically?",
                'no': "No because?",
                'maybe': "What would decide it?",
                'idk': "Best guess?",
                'sure': "Sure about?",
                'ok': "Ok but why?",
                'fine': "Fine or FINE?",
                'whatever': "Whatever = don't care?"
            }
            
            if response_lower in generic_clarifiers:
                return generic_clarifiers[response_lower]
            
            # Very generic for any short response
            return "Tell me more?"
        
        # No clarifier needed for longer, clear responses
        return None
    
    async def should_clarify(self, user_response: str, pattern_type: str) -> bool:
        """
        Determine if a clarifier question should be sent
        
        Simple heuristic: clarify short/vague responses
        """
        # Skip clarifying skips
        if user_response.lower() in ['skip', 'skipped', '🫥']:
            return False
        
        # Always clarify very short responses
        word_count = len(user_response.split())
        if word_count <= 2:
            return True
        
        # Clarify vague responses
        vague_terms = ['maybe', 'idk', 'sure', 'ok', 'yeah', 'nah', 'meh']
        if any(term in user_response.lower() for term in vague_terms):
            return True
        
        # Clarify if response is just a tag we've seen before (might be button mashing)
        common_tags = ['fomo', 'revenge', 'alpha', 'testing', 'whale']
        if user_response.lower() in common_tags and word_count == 1:
            return True
        
        return False


class ButtonEvolution:
    """Tracks user vocabulary to evolve button options"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def get_user_vocabulary(self, user_id: int, pattern_type: str = None) -> List[str]:
        """Get most common user phrases for button suggestions"""
        try:
            # Get user's most common responses
            query = """
                SELECT user_response, COUNT(*) as frequency
                FROM trade_notes
                WHERE user_id = ?
            """
            params = [user_id]
            
            if pattern_type:
                query += " AND pattern_type = ?"
                params.append(pattern_type)
            
            query += """
                GROUP BY user_response
                ORDER BY frequency DESC
                LIMIT 3
            """
            
            result = self.db.execute(query, params).fetchall()
            return [response[0] for response in result if response[0] != "Other"]
            
        except Exception as e:
            logger.error(f"Error getting user vocabulary: {e}")
            return []
    
    def suggest_adaptive_buttons(self, user_id: int, pattern_type: str, 
                               default_buttons: List[str]) -> List[str]:
        """Adapt buttons based on user's vocabulary"""
        user_vocab = self.get_user_vocabulary(user_id, pattern_type)
        
        if not user_vocab:
            return default_buttons
        
        # Replace generic buttons with user's common phrases
        adaptive_buttons = default_buttons.copy()
        
        # Replace the first few buttons with user's vocabulary, keep "Other..."
        for i, vocab_term in enumerate(user_vocab):
            if i < len(adaptive_buttons) - 1:  # Keep "Other..." at the end
                adaptive_buttons[i] = vocab_term
        
        return adaptive_buttons


# Factory function for easy instantiation
def create_nudge_engine(strategy: str = "rules", config: Dict = None, db_connection=None) -> NudgeEngine:
    """Factory function to create nudge engine with optional button evolution"""
    engine = NudgeEngine(strategy, config)
    
    if db_connection:
        engine.button_evolution = ButtonEvolution(db_connection)
    
    return engine 