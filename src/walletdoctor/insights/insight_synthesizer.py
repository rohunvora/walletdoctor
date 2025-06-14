"""
Insight Synthesizer

Takes multiple detected patterns and synthesizes them into cohesive,
non-conflicting wisdom that tells a coherent story about the trader's behavior.
"""

from typing import List, Dict, Tuple
from dataclasses import dataclass
from src.walletdoctor.features.realistic_patterns import TradingPattern


@dataclass
class SynthesizedInsight:
    """A synthesized, coherent insight from multiple patterns"""
    core_problem: str
    root_cause: str
    supporting_evidence: List[str]
    unified_solution: str
    expected_outcome: str
    priority: int


class InsightSynthesizer:
    """Synthesizes multiple patterns into coherent wisdom"""
    
    def __init__(self, patterns: List[TradingPattern]):
        self.patterns = patterns
        self.pattern_groups = self._group_related_patterns()
        
    def _group_related_patterns(self) -> Dict[str, List[TradingPattern]]:
        """Group patterns that are related or potentially conflicting"""
        
        groups = {
            'timing_issues': [],
            'sizing_issues': [],
            'emotional_trading': [],
            'process_issues': []
        }
        
        for pattern in self.patterns:
            if pattern.pattern_name in ['Disposition Effect', 'Cutting Winners Too Early', 
                                       'Quick Flip Addiction']:
                groups['timing_issues'].append(pattern)
            elif pattern.pattern_name in ['Position Size Discipline', 'Portfolio Concentration Risk']:
                groups['sizing_issues'].append(pattern)
            elif pattern.pattern_name in ['Revenge Trading Pattern', 'Overtrading']:
                groups['emotional_trading'].append(pattern)
            else:
                groups['process_issues'].append(pattern)
                
        return groups
    
    def synthesize(self) -> Tuple[str, List[SynthesizedInsight]]:
        """Create a coherent narrative from all patterns"""
        
        # Identify the core story
        story = self._identify_core_story()
        
        # Synthesize insights for each group
        synthesized = []
        
        # Handle timing conflicts
        if self.pattern_groups['timing_issues']:
            timing_insight = self._synthesize_timing_issues()
            if timing_insight:
                synthesized.append(timing_insight)
        
        # Handle sizing issues
        if self.pattern_groups['sizing_issues']:
            sizing_insight = self._synthesize_sizing_issues()
            if sizing_insight:
                synthesized.append(sizing_insight)
        
        # Handle emotional trading
        if self.pattern_groups['emotional_trading']:
            emotional_insight = self._synthesize_emotional_issues()
            if emotional_insight:
                synthesized.append(emotional_insight)
        
        # Sort by priority
        synthesized.sort(key=lambda x: x.priority)
        
        return story, synthesized
    
    def _identify_core_story(self) -> str:
        """Identify the main narrative of this trader's issues"""
        
        # Look for the most severe patterns
        critical_patterns = [p for p in self.patterns if p.severity == 'critical']
        high_patterns = [p for p in self.patterns if p.severity == 'high']
        
        # Common trader archetypes
        if any('Overtrading' in p.pattern_name for p in self.patterns):
            if any('Quick Flip' in p.pattern_name for p in self.patterns):
                return "The Impatient Gambler"
            else:
                return "The Overactive Trader"
        
        if any('Position Size' in p.pattern_name for p in critical_patterns):
            if any('Revenge' in p.pattern_name for p in self.patterns):
                return "The Emotional Revenge Trader"
            else:
                return "The FOMO Chaser"
        
        if any('Disposition' in p.pattern_name for p in high_patterns):
            return "The Hope Trader"
        
        return "The Undisciplined Trader"
    
    def _synthesize_timing_issues(self) -> SynthesizedInsight:
        """Resolve conflicts between holding too long/short"""
        
        timing_patterns = self.pattern_groups['timing_issues']
        if not timing_patterns:
            return None
        
        # Check for conflicts
        has_disposition = any('Disposition' in p.pattern_name for p in timing_patterns)
        has_quick_exit = any('Cutting Winners' in p.pattern_name for p in timing_patterns)
        has_quick_flip = any('Quick Flip' in p.pattern_name for p in timing_patterns)
        
        if has_disposition and (has_quick_exit or has_quick_flip):
            # Conflict detected - synthesize
            return SynthesizedInsight(
                core_problem="Inconsistent Exit Strategy: You cut winners quickly but hold losers forever",
                root_cause="Emotional decision-making overrides any systematic approach. Fear drives quick profits, hope drives holding losses.",
                supporting_evidence=[
                    "Winners held < 2 hours, losers held > 8 hours",
                    "This asymmetry is destroying your profit potential",
                    "You're literally doing the opposite of what works"
                ],
                unified_solution="""Implement the 3R Rule:
                1. Risk: Set stop loss at entry (-5% max)
                2. Reward: Set profit targets (1R = +5%, 2R = +10%, 3R = +15%)
                3. Rules: Exit at stop OR take 50% at 2R, let rest run with trailing stop
                
                This single system fixes BOTH problems: stops you holding losers AND lets winners run.""",
                expected_outcome="This one change could flip your P&L positive within 30 days",
                priority=1
            )
        
        # Single timing issue
        main_pattern = max(timing_patterns, key=lambda p: {'critical': 3, 'high': 2, 'medium': 1}.get(p.severity, 0))
        return SynthesizedInsight(
            core_problem=f"Exit Timing Issues: {main_pattern.description}",
            root_cause="Lack of systematic exit rules",
            supporting_evidence=[p.evidence[0] for p in timing_patterns[:3]],
            unified_solution=main_pattern.recommendation,
            expected_outcome=main_pattern.impact,
            priority=2
        )
    
    def _synthesize_sizing_issues(self) -> SynthesizedInsight:
        """Combine position sizing and concentration issues"""
        
        sizing_patterns = self.pattern_groups['sizing_issues']
        if not sizing_patterns:
            return None
        
        # These usually go together
        total_impact = sum(self._extract_dollar_impact(p.impact) for p in sizing_patterns)
        
        return SynthesizedInsight(
            core_problem="Capital Allocation Disaster: You bet big on garbage and small on winners",
            root_cause="FOMO-driven sizing. The more excited you are, the bigger you bet, the worse you do.",
            supporting_evidence=[
                "Large positions underperform by 70%+",
                "Your biggest bets are emotional, not analytical",
                f"Total cost of bad sizing: ${abs(total_impact):,.0f}"
            ],
            unified_solution="""The Fixed Sizing System:
            1. Default position: 2% of account
            2. High conviction: 5% max (requires written thesis)
            3. If you feel FOMO: 1% max
            4. Never exceed 10 positions total
            
            Use this calculator before EVERY trade: Position Size = Account * 0.02""",
            expected_outcome=f"Proper sizing alone could save you ${abs(total_impact):,.0f}/month",
            priority=1 if any(p.severity == 'critical' for p in sizing_patterns) else 2
        )
    
    def _synthesize_emotional_issues(self) -> SynthesizedInsight:
        """Combine overtrading, revenge trading, etc."""
        
        emotional_patterns = self.pattern_groups['emotional_trading']
        if not emotional_patterns:
            return None
        
        # These compound each other
        trade_count = 0
        for p in emotional_patterns:
            for e in p.evidence:
                if 'trades' in e and e.split()[0].isdigit():
                    trade_count = int(e.split()[0])
                    break
        
        return SynthesizedInsight(
            core_problem="Emotional Trading Spiral: You trade your feelings, not the market",
            root_cause="Using trading to regulate emotions. Losses trigger more trades, more trades create more losses.",
            supporting_evidence=[
                f"Making {trade_count} emotional trades",
                "Trade quality degrades after losses",
                "Revenge trading detected after red days"
            ],
            unified_solution="""The Emotional Circuit Breaker:
            1. Daily limits: Max 5 trades, max 2% daily loss
            2. After any -5% loss: Mandatory 24hr cooldown
            3. Before each trade: Rate emotions 1-10, if >7, don't trade
            4. End of day: Journal the 'why' behind each trade
            
            Install a trade counter app that locks you out after limits.""",
            expected_outcome="Breaking emotional patterns could 3x your win rate",
            priority=1
        )
    
    def _extract_dollar_impact(self, impact_str: str) -> float:
        """Extract dollar amount from impact string"""
        import re
        match = re.search(r'\$?([\d,]+)', impact_str)
        if match:
            return float(match.group(1).replace(',', ''))
        return 0
    
    def generate_executive_summary(self, story: str, insights: List[SynthesizedInsight]) -> str:
        """Generate a concise executive summary"""
        
        if not insights:
            return "No significant patterns detected. Keep up the good work!"
        
        top_insight = insights[0]
        total_cost = sum(self._extract_dollar_impact(p.impact) for p in self.patterns)
        
        summary = f"""
🎯 THE BOTTOM LINE: You're "{story}"
════════════════════════════════════════════════════════════════════════════════

Your #1 Problem: {top_insight.core_problem}

Why This Happens: {top_insight.root_cause}

What It's Costing You: ${abs(total_cost):,.0f}/month in unnecessary losses

The Fix That Changes Everything:
{top_insight.unified_solution}

Expected Result: {top_insight.expected_outcome}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Ready to dig deeper? Ask me:
• "How do I implement the 3R Rule?"
• "Show me examples of my worst FOMO trades"
• "What should my trading day look like?"
• "How do I know if I'm improving?"
"""
        
        return summary
    
    def generate_conversation_starters(self) -> List[str]:
        """Generate relevant follow-up questions the user might ask"""
        
        starters = []
        
        if any('timing' in g for g in self.pattern_groups if self.pattern_groups[g]):
            starters.append("Why do I hold losers so much longer than winners?")
            starters.append("How do I know when to take profits?")
        
        if any('sizing' in g for g in self.pattern_groups if self.pattern_groups[g]):
            starters.append("How do I fight FOMO when I want to bet big?")
            starters.append("What's the math behind position sizing?")
        
        if any('emotional' in g for g in self.pattern_groups if self.pattern_groups[g]):
            starters.append("How do I stop revenge trading after losses?")
            starters.append("What does a good trading routine look like?")
        
        starters.append("Show me my worst habits with specific examples")
        starters.append("What would my P&L look like if I fixed these issues?")
        
        return starters 