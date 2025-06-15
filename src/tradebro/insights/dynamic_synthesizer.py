"""
Dynamic Insight Synthesizer

No pre-defined archetypes or templates. Forces the LLM to actually understand
the trader's unique patterns and write fresh, specific insights.
"""

from typing import List, Dict, Any
from dataclasses import dataclass
import json


@dataclass
class TradingBehaviorData:
    """Raw behavioral data for LLM analysis"""
    patterns: List[Dict[str, Any]]  # Pattern data without labels
    metrics: Dict[str, float]  # Raw metrics
    specific_examples: List[Dict[str, Any]]  # Actual trades/behaviors
    
    def to_analysis_prompt(self) -> str:
        """Convert to prompt for o1/o3 analysis"""
        return f"""Analyze this trader's behavior patterns:

METRICS:
{json.dumps(self.metrics, indent=2)}

DETECTED PATTERNS:
{json.dumps([{
    'behavior': p.get('description'),
    'frequency': p.get('evidence'),
    'cost': p.get('impact')
} for p in self.patterns], indent=2)}

SPECIFIC EXAMPLES:
{json.dumps(self.specific_examples, indent=2)}

Identify:
1. The core psychological driver behind these patterns
2. What specific fear or desire motivates their worst habits
3. The one behavioral change that would have the biggest impact
4. Why they keep repeating these patterns despite losing money
"""


class DynamicSynthesizer:
    """Generates unique insights without templates"""
    
    def __init__(self, pattern_data: Dict[str, Any], llm_client=None):
        self.data = pattern_data
        self.llm = llm_client  # Could be o1/o3 for analysis, GPT-4 for writing
        
    def analyze_behavior(self, raw_data: TradingBehaviorData) -> Dict[str, Any]:
        """Use o1/o3 to deeply analyze the behavioral patterns"""
        
        # This would call o1/o3 with the analysis prompt
        # For now, returning structure of what it would generate
        
        analysis = {
            "core_behavior": "Not a label, but a unique description of THIS trader",
            "psychological_driver": "The specific fear/desire driving them",
            "pattern_connections": "How their behaviors reinforce each other",
            "blind_spots": "What they can't see about themselves",
            "leverage_point": "The ONE change that breaks the cycle"
        }
        
        return analysis
    
    def write_hook(self, analysis: Dict[str, Any], stats: Dict[str, float]) -> str:
        """Use GPT-4 to write a compelling, unique hook"""
        
        # This would be the GPT-4 prompt
        writing_prompt = f"""Based on this behavioral analysis, write a sharp, psychologically accurate 
hook that will make the trader feel truly seen. No generic labels or archetypes.

Analysis: {json.dumps(analysis, indent=2)}
Stats: Lost ${abs(stats.get('total_pnl', 0)):,.0f} over {stats.get('total_trades', 0)} trades

Requirements:
- Start with their specific behavior, not a label
- Include a detail so specific they'll wonder how you knew
- Call out the lie they tell themselves
- One simple fix that addresses the root cause
- End with questions they're already asking themselves

Make it feel like you're reading their mind, not their data."""
        
        # Placeholder for what GPT-4 would generate
        # Each output would be unique to the trader
        
        return """[Unique, non-templated insight based on their specific patterns]"""
    
    def generate_conversation_flow(self, analysis: Dict[str, Any]) -> Dict[str, str]:
        """Generate natural follow-up responses"""
        
        # Instead of pre-written responses, generate based on analysis
        flow = {
            "questions": [
                # Generated based on their specific patterns
            ],
            "response_framework": {
                # Guidelines for generating responses, not the responses themselves
            }
        }
        
        return flow


# Example of how this would work in practice
def example_usage():
    """Show how the dynamic approach works"""
    
    # Raw data from pattern detection
    raw_data = TradingBehaviorData(
        patterns=[
            {
                "description": "Increases position size by 3x after losses",
                "evidence": ["15 instances in last month", "Average size: $500 → $1500"],
                "impact": "$8,234 additional losses"
            },
            {
                "description": "Exits winning positions in under 5 minutes",
                "evidence": ["73% of winners sold < 5min", "Missed avg 40% upside"],
                "impact": "$3,421 missed profits"
            }
        ],
        metrics={
            "total_pnl": -12453,
            "win_rate": 0.31,
            "avg_hold_time_minutes": 8.3,
            "trades_per_day": 47
        },
        specific_examples=[
            {
                "token": "BONK",
                "bought_after": "seeing 5 green candles",
                "sold_after": "first red candle",
                "loss": -234,
                "time_held": "3 minutes"
            }
        ]
    )
    
    # What o1/o3 might analyze
    deep_analysis = {
        "core_behavior": "You're not trading, you're playing a slot machine where you control when to pull out. You pull the lever harder after losses (3x position size) but cash out the second you see green (5 min holds).",
        
        "psychological_driver": "Deep fear of being the sucker. You'd rather take a small win than risk being the one holding the bag. But this fear makes you the exact sucker you're afraid of being.",
        
        "pattern_connections": "Your revenge sizing after losses directly causes your quick exits on winners - you're so overleveraged that any green feels like a gift you must take immediately.",
        
        "blind_spots": "You think you're being 'disciplined' by taking quick profits. You don't realize you've trained yourself to be everyone's exit liquidity.",
        
        "leverage_point": "Force a 30-minute hold on EVERY position. This single friction breaks both the revenge sizing (you'll think twice about 3x size if you must hold) and the quick exit pattern."
    }
    
    # What GPT-4 might write
    unique_hook = """
You bought BONK after seeing 5 green candles and sold after the first red one. 
Three minutes. $234 loss.

This wasn't a trade - it was a $234 donation to someone with more patience than you.

Here's what's actually happening: You're so terrified of being the sucker holding 
the bag that you've become the sucker providing exit liquidity. You revenge-size 
after losses (3x your normal) then panic-sell winners because you're overleveraged 
and any profit feels like a miracle.

You've lost $12,453 playing hot potato with 1,247 trades. That's not trading, 
it's expensive entertainment.

The fix is stupidly simple: 30-minute minimum hold on everything. 

Can't do it? Then you're not a trader, you're a gambler who likes buttons.

Questions you're asking yourself:
• "Why do I always sell right before it moons?"
• "How do I stop revenge trading after losses?"
• "What would happen if I actually held for once?"
"""
    
    return unique_hook 