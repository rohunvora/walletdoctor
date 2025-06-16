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
            r'\b(fomo|fear)\b': 'fomo',
            r'\b(revenge|angry|mad)\b': 'revenge',
            r'\b(whale|follow|copy)\b': 'whale_follow',
            r'\b(dip|discount|cheap)\b': 'buying_dip',
            r'\b(pump|moon|rocket)\b': 'chasing_pump',
            r'\b(profit|gains|cash out)\b': 'taking_profits',
            r'\b(stop|loss|cut|panic)\b': 'stop_loss',
            r'\b(news|announcement|alpha)\b': 'news_based',
            r'\b(gut|feel|vibe)\b': 'intuition',
            r'\b(test|try|experiment)\b': 'testing'
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
                question = template["sell_question"].format(**pattern_data)
                buttons = template["sell_buttons"]
            else:
                question = template["buy_question"].format(**pattern_data)
                buttons = template["buy_buttons"]
        else:
            # For other patterns, use single question/buttons
            question = template["question"].format(**pattern_data)
            buttons = template["buttons"]
        
        # Add memory callback if available
        if previous_response and previous_response.get("confidence", 0) > 0.7:
            question += f"\n\nLast time you said: '{previous_response['text']}'"
        
        # Create keyboard based on mode
        if self.text_first_mode:
            # Text-first mode: minimal UI, no corny prompt
            keyboard = None  # No buttons in text-first mode
        else:
            # Button mode: Create full keyboard
            keyboard = self._create_keyboard(buttons)
        
        return question, keyboard
    
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
                "buy_buttons": ["FOMO", "Alpha", "Good wallets", "Other..."],
                "sell_buttons": ["Taking profits", "Stop loss", "Panic sell", "Other..."]
            },
            
            "repeat_token": {
                "buy_question": "{token_symbol} again? What's different this time?",
                "sell_question": "Taking some {token_symbol} profits?",
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
        """Extract tag using GPT-4o-mini"""
        action = context.get('pattern_data', {}).get('action', 'BUY')
        token = context.get('pattern_data', {}).get('token_symbol', 'token')
        
        prompt = f"""Extract a 2-3 word tag from this trader's response about their {action} trade of {token}.

Trader said: "{user_text}"

Common tags: fomo, revenge_trade, whale_follow, buying_dip, taking_profits, stop_loss, news_based, testing, intuition

Return ONLY the tag, nothing else. Use snake_case."""

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
        """Extract tag using regex patterns"""
        user_text_lower = user_text.lower()
        
        # Check each pattern
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
        """Format the bot's response after tagging"""
        tag = tag_info['tag']
        confidence = tag_info['confidence']
        
        # Convert snake_case to readable format
        readable_tag = tag.replace('_', ' ')
        
        # More natural, less corny responses
        if confidence >= 0.8:
            return f"**{readable_tag}** noted"
        else:
            # Lower confidence, more tentative
            return f"_{readable_tag}?_"


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