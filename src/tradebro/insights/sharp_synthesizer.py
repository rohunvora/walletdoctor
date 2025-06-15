"""
Sharp Insight Synthesizer

Delivers psychologically penetrating insights that make traders feel truly understood.
The goal: They read it and think "Holy shit, this is exactly me."
"""

from typing import List, Dict, Tuple
from dataclasses import dataclass
from src.tradebro.features.realistic_patterns import TradingPattern


@dataclass
class TraderArchetype:
    """A sharp, accurate psychological profile"""
    name: str
    tagline: str
    inner_monologue: str  # What they're really thinking
    core_delusion: str  # The lie they tell themselves
    hidden_fear: str  # What actually drives them
    telltale_signs: List[str]  # Behaviors that give them away
    cost_of_denial: str  # What ignoring this costs
    the_hard_truth: str  # What they need to hear
    the_simple_fix: str  # One thing that changes everything


class SharpSynthesizer:
    """Creates insights so accurate they're uncomfortable"""
    
    def __init__(self, patterns: List[TradingPattern], summary_stats: Dict):
        self.patterns = patterns
        self.stats = summary_stats
        self.archetype = self._identify_archetype()
        
    def _identify_archetype(self) -> TraderArchetype:
        """Identify the trader's psychological archetype"""
        
        # Analyze pattern combinations for psychological profiles
        pattern_names = [p.pattern_name for p in self.patterns]
        severities = [p.severity for p in self.patterns]
        
        # The Revenge Trader
        if any('Revenge' in name for name in pattern_names) or \
           (any('Position Size' in name for name in pattern_names) and 
            any('Overtrading' in name for name in pattern_names)):
            return TraderArchetype(
                name="The Revenge Trader",
                tagline="You trade to be right, not to make money",
                inner_monologue="'I'll show the market. This next trade will make it all back.'",
                core_delusion="Your next trade will be different because you 'learned your lesson'",
                hidden_fear="Admitting you're just gambling would mean facing your losses",
                telltale_signs=[
                    "Position size increases after losses",
                    "Trade frequency spikes on red days",
                    "You check prices obsessively after closing positions",
                    "You remember every 'almost' win but forget the losses"
                ],
                cost_of_denial=f"${abs(self.stats.get('total_pnl', 0)):,.0f} and counting",
                the_hard_truth="You're not trading, you're using the market as an emotional punching bag",
                the_simple_fix="One rule: After any loss, reduce next position by 50%. No exceptions."
            )
        
        # The FOMO Degen
        elif any('Quick Flip' in name for name in pattern_names) and \
             any('Overtrading' in name for name in pattern_names):
            return TraderArchetype(
                name="The FOMO Degen",
                tagline="You're afraid of missing out on everything, so you miss out on profits",
                inner_monologue="'Everyone else is getting rich. Why not me? Maybe this one...'",
                core_delusion="The next pump is always the 'big one' you've been waiting for",
                hidden_fear="Others are getting rich while you're not in the trade",
                telltale_signs=[
                    "You have 47 Telegram groups open",
                    "You buy within 30 seconds of seeing a green candle",
                    "Your average hold time is measured in minutes",
                    "You've never met a pump you didn't chase"
                ],
                cost_of_denial=f"While chasing 100x, you've lost {abs(self.stats.get('total_pnl', 0)/1000):.1f}x",
                the_hard_truth="Your FOMO has made you everyone else's exit liquidity",
                the_simple_fix="New rule: 1 hour cooldown before entering any trade. Set a timer."
            )
        
        # The Hope Addict
        elif any('Disposition' in name for name in pattern_names) and \
             self.stats.get('win_rate', 0) < 35:
            return TraderArchetype(
                name="The Hope Addict",
                tagline="You're married to your bags and hope is your strategy",
                inner_monologue="'It has to come back. I just need to wait. Diamond hands!'",
                core_delusion="Holding longer turns losses into wins",
                hidden_fear="Taking a loss means admitting you were wrong",
                telltale_signs=[
                    "You have tokens from 2021 you're 'waiting to recover'",
                    "You say 'it's not a loss until you sell'",
                    "You average down into death spirals",
                    "Your portfolio is a graveyard of 'what ifs'"
                ],
                cost_of_denial="Your refusal to take small losses has created massive ones",
                the_hard_truth="Hope is not a strategy. Your bags aren't coming back.",
                the_simple_fix="Brutal rule: Any position down 10% gets cut. No exceptions, no hope."
            )
        
        # The Chaos Trader
        elif len(self.patterns) >= 5 and any('critical' in severities):
            return TraderArchetype(
                name="The Chaos Trader",
                tagline="You have no system, just vibes and copium",
                inner_monologue="'I know what I'm doing. I just need to focus more.'",
                core_delusion="Experience will eventually lead to profits",
                hidden_fear="Having rules would mean admitting you've been gambling",
                telltale_signs=[
                    "Every trade has a different strategy",
                    "You can't explain why you entered most positions",
                    "Your position sizes are based on 'feeling'",
                    "You've been 'learning' for years with no improvement"
                ],
                cost_of_denial="Another year of this and you'll have donated a house down payment to the market",
                the_hard_truth="You're not a trader, you're a gambler in denial",
                the_simple_fix="Pick ONE strategy. Trade it 100 times. No deviations."
            )
        
        # Default: The Undisciplined Trader
        else:
            return TraderArchetype(
                name="The Undisciplined Trader",
                tagline="You know what to do, you just don't do it",
                inner_monologue="'I know I shouldn't but... just this once.'",
                core_delusion="Tomorrow you'll follow your rules",
                hidden_fear="Discipline means no more excitement",
                telltale_signs=[
                    "You have rules written down somewhere",
                    "You break them 'just this once' daily",
                    "You know better but do it anyway",
                    "Your losses are predictable and preventable"
                ],
                cost_of_denial="The gap between knowing and doing has cost you a fortune",
                the_hard_truth="You don't need more knowledge, you need self-control",
                the_simple_fix="Start with ONE unbreakable rule. Master it for 30 days."
            )
    
    def generate_hook(self) -> str:
        """Generate the sharp, accurate hook that makes them feel seen"""
        
        a = self.archetype
        total_loss = abs(self.stats.get('total_pnl', 0))
        trade_count = self.stats.get('total_trades', 0)
        win_rate = self.stats.get('win_rate', 0)
        
        hook = f"""
🎯 {a.name.upper()}: {a.tagline}
════════════════════════════════════════════════════════════════════════════════

Inner Voice: {a.inner_monologue}

The Lie You Tell Yourself: {a.core_delusion}

What You're Really Afraid Of: {a.hidden_fear}

Dead Giveaways You're This Type:
{chr(10).join(f'  ✓ {sign}' for sign in a.telltale_signs[:3])}

What This Denial Has Cost You: {a.cost_of_denial}

The Hard Truth: {a.the_hard_truth}

The One Change That Fixes Everything:
→ {a.the_simple_fix}

This isn't another trading tip. This is about breaking the pattern that's 
destroying your account. You've lost ${total_loss:,.0f} across {trade_count} trades 
with a {win_rate:.0f}% win rate.

The market isn't your problem. You are.

Ready to stop lying to yourself? Let's talk about:
• "Why do I keep doing this even though I know better?"
• "Show me my worst habits with real examples"
• "What would my P&L look like if I actually followed rules?"
• "How do I break this pattern for good?"
"""
        
        return hook
    
    def generate_follow_up_responses(self) -> Dict[str, str]:
        """Pre-generate responses to likely follow-up questions"""
        
        responses = {}
        
        # "Why do I keep doing this?"
        responses["why_pattern"] = f"""
The psychology behind {self.archetype.name}:

1. **Emotional Regulation**: You're using trading to manage feelings, not make money.
   - Winning feels like validation
   - Losing triggers shame/anger
   - Trading gives you control (illusion)

2. **Dopamine Addiction**: Your brain is hooked on the action, not the profits.
   - The possibility of winning is more exciting than winning
   - Losses make you chase the high harder
   - You need bigger risks for the same rush

3. **Identity Protection**: Admitting failure threatens your self-image.
   - "I'm smart, I should be good at this"
   - Each loss is a narcissistic injury
   - Doubling down protects your ego

The fix isn't trying harder. It's changing the game you're playing.
"""
        
        # "Show me examples"
        responses["examples"] = f"""
Here are your {self.archetype.name} patterns in action:

{self._generate_specific_examples()}

Notice the pattern? It's the same mistake in different costumes.
"""
        
        return responses
    
    def _generate_specific_examples(self) -> str:
        """Generate specific examples based on patterns"""
        
        examples = []
        
        for pattern in self.patterns[:3]:
            if 'Position Size' in pattern.pattern_name:
                examples.append("🔴 That time you went all-in on BONK because 'everyone was buying'")
            elif 'Quick Flip' in pattern.pattern_name:
                examples.append("🔴 The 47 trades you made last Tuesday trying to 'scalp' your way to profit")
            elif 'Disposition' in pattern.pattern_name:
                examples.append("🔴 Still holding that LUNA bag from 2022 'waiting for the comeback'")
        
        return "\n".join(examples) if examples else "Your entire trade history is the example." 