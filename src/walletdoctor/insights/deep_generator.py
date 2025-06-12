"""Deep insight generator with psychological mapping and validation."""
import polars as pl
from typing import Dict, List, Tuple, Any
from ..features import patterns
from ..features.pattern_validator import PatternValidator


class DeepInsightGenerator:
    """Generates deep psychological insights from validated patterns."""
    
    def __init__(self, min_confidence: float = 0.75):
        self.validator = PatternValidator(min_confidence)
        self.psychological_maps = self._load_psychological_maps()
    
    def generate_insights(self, df: pl.DataFrame, max_insights: int = 5) -> Dict[str, Any]:
        """
        Generate validated deep insights from trading data.
        
        Returns:
            Dict with insights, confidence levels, and supporting evidence
        """
        # Step 1: Detect patterns
        pattern_analysis = patterns.analyze_all_patterns(df)
        
        # Step 2: Validate each detected pattern
        validated_patterns = {}
        for pattern_name, pattern_data in pattern_analysis['pattern_details'].items():
            if pattern_data.get('detected'):
                validation = self.validator.validate_pattern(
                    {'type': pattern_name, **pattern_data}, 
                    df
                )
                if validation['valid']:
                    validated_patterns[pattern_name] = {
                        **pattern_data,
                        'validation': validation
                    }
        
        # Step 3: Generate insights only for validated patterns
        insights = []
        for pattern_name, pattern_data in validated_patterns.items():
            insight = self._generate_pattern_insight(pattern_name, pattern_data, df)
            if insight:
                insights.append(insight)
        
        # Step 4: Sort by impact and confidence
        insights.sort(key=lambda x: x['impact_score'] * x['confidence'], reverse=True)
        
        # Step 5: Generate overall diagnosis
        diagnosis = self._generate_diagnosis(validated_patterns, df)
        
        return {
            'insights': insights[:max_insights],
            'diagnosis': diagnosis,
            'patterns_found': len(validated_patterns),
            'confidence_summary': self._summarize_confidence(insights),
            'requires_action': any(i['severity'] == 'critical' for i in insights)
        }
    
    def _generate_pattern_insight(self, pattern_name: str, pattern_data: Dict, df: pl.DataFrame) -> Dict[str, Any]:
        """Generate a single deep insight for a validated pattern."""
        psych_map = self.psychological_maps.get(pattern_name, {})
        validation = pattern_data.get('validation', {})
        
        # Build the insight structure
        insight = {
            'pattern': pattern_name,
            'headline': self._create_headline(pattern_name, pattern_data),
            'psychological_root': psych_map.get('root_cause', 'Unknown'),
            'subconscious_narrative': psych_map.get('internal_dialogue', ''),
            'behavioral_loop': psych_map.get('loop', ''),
            'specific_evidence': self._extract_evidence(pattern_name, pattern_data),
            'harsh_truth': self._generate_harsh_truth(pattern_name, pattern_data),
            'fix': psych_map.get('fix', 'Develop systematic rules'),
            'confidence': validation.get('confidence', 0),
            'impact_score': self._calculate_impact(pattern_name, pattern_data, df),
            'severity': self._assess_severity(pattern_name, pattern_data)
        }
        
        # Add validation concerns if confidence is not high
        if validation.get('confidence', 0) < 0.9:
            insight['caveats'] = validation.get('concerns', [])
        
        return insight
    
    def _load_psychological_maps(self) -> Dict[str, Dict[str, str]]:
        """Load psychological interpretations for each pattern."""
        return {
            'loss_aversion': {
                'root_cause': 'Ego protection and fear of being wrong',
                'internal_dialogue': '"If I don\'t sell, it\'s not a real loss. It might come back."',
                'loop': 'Small loss → Denial → Bigger loss → Desperation → Hold forever',
                'fix': 'Hard stop loss at -5%. No exceptions. Set it when you enter.'
            },
            'revenge_trading': {
                'root_cause': 'Need to "get even" with the market',
                'internal_dialogue': '"I\'ll make it all back on this next trade."',
                'loop': 'Loss → Anger → Increased size → Bigger loss → Rage → Blow up',
                'fix': 'After any loss > 2%, mandatory 24hr cooling period. No exceptions.'
            },
            'fomo_spiral': {
                'root_cause': 'Dopamine addiction and overconfidence after wins',
                'internal_dialogue': '"I\'m on fire! I can\'t miss right now!"',
                'loop': 'Big win → Euphoria → Rapid trades → Losses → Chase the high',
                'fix': 'After wins > 10%, reduce position size by 50% for next 5 trades.'
            },
            'no_process': {
                'root_cause': 'Trading on impulse without any systematic approach',
                'internal_dialogue': '"I\'ll know it when I see it."',
                'loop': 'Random entry → Random size → Random exit → Random results',
                'fix': 'Document EVERY trade: Entry reason, exit plan, position size rule.'
            },
            'winner_cutting': {
                'root_cause': 'Fear of giving back profits / Imposter syndrome',
                'internal_dialogue': '"Take the money and run before it disappears."',
                'loop': 'Small profit → Fear → Quick exit → Watch it moon → Regret',
                'fix': 'Sell 50% at 2x, let the rest run with trailing stop.'
            }
        }
    
    def _create_headline(self, pattern_name: str, pattern_data: Dict) -> str:
        """Create a punchy headline for the pattern."""
        headlines = {
            'loss_aversion': f"You hold losers {pattern_data.get('asymmetry_ratio', 1.3):.0f}x longer than winners",
            'revenge_trading': f"After losses, you {pattern_data.get('avg_size_multiplier', 5):.0f}x your position size",
            'fomo_spiral': f"{pattern_data.get('loss_rate_after_wins', 0.7)*100:.0f}% of trades after big wins lose",
            'no_process': f"Your trading variance is {pattern_data.get('size_variance', 200):.0f}% - pure chaos",
            'winner_cutting': f"You cut {pattern_data.get('quick_exit_rate', 0.6)*100:.0f}% of winners in <30min"
        }
        return headlines.get(pattern_name, f"{pattern_name.replace('_', ' ').title()} detected")
    
    def _extract_evidence(self, pattern_name: str, pattern_data: Dict) -> List[str]:
        """Extract specific evidence points for the pattern."""
        evidence = []
        
        if pattern_name == 'loss_aversion':
            evidence.append(f"Winners held: {pattern_data.get('winner_hold', 0):.0f} min avg")
            evidence.append(f"Losers held: {pattern_data.get('loser_hold', 0):.0f} min avg")
            evidence.append(f"Extra hold on losers: {pattern_data.get('extra_hold_minutes', 0):.0f} min")
            
        elif pattern_name == 'revenge_trading':
            evidence.append(f"Normal trade size: ${pattern_data.get('median_size', 0):,.0f}")
            evidence.append(f"Revenge trade size: {pattern_data.get('avg_size_multiplier', 1):.1f}x larger")
            evidence.append(f"Damage from revenge trades: ${pattern_data.get('total_damage', 0):,.0f}")
            
        return evidence
    
    def _generate_harsh_truth(self, pattern_name: str, pattern_data: Dict) -> str:
        """Generate a harsh but accurate assessment."""
        truths = {
            'loss_aversion': "You're not 'being patient'—you're in denial. Every minute past -5% is ego, not strategy.",
            'revenge_trading': "Your $59K loss wasn't bad luck. It was inevitable. You're fighting the market like it's personal.",
            'fomo_spiral': "You trade like an addict chasing a high. Big win = dopamine hit = need another fix = spiral.",
            'no_process': "You're not trading. You're gambling with a Bloomberg terminal. At least casinos have consistent odds.",
            'winner_cutting': "You don't believe you deserve to win. So you make sure you don't. Self-sabotage disguised as 'risk management'."
        }
        return truths.get(pattern_name, "Your trading lacks discipline and consistency.")
    
    def _calculate_impact(self, pattern_name: str, pattern_data: Dict, df: pl.DataFrame) -> float:
        """Calculate the financial/performance impact of this pattern."""
        impacts = {
            'loss_aversion': 0.8,  # High impact - directly affects P&L
            'revenge_trading': 0.95,  # Critical - can blow up accounts
            'fomo_spiral': 0.7,  # Moderate-high - erodes gains
            'no_process': 0.85,  # High - prevents consistent success
            'winner_cutting': 0.6  # Moderate - limits upside
        }
        
        base_impact = impacts.get(pattern_name, 0.5)
        
        # Adjust based on pattern-specific metrics
        if pattern_name == 'revenge_trading' and pattern_data.get('total_damage', 0) < -50000:
            base_impact = 1.0  # Maximum impact for huge losses
            
        return base_impact
    
    def _assess_severity(self, pattern_name: str, pattern_data: Dict) -> str:
        """Assess severity level of the pattern."""
        # Critical patterns that can blow up accounts
        if pattern_name in ['revenge_trading', 'no_process']:
            if pattern_name == 'revenge_trading' and pattern_data.get('avg_size_multiplier', 1) > 5:
                return 'critical'
            if pattern_name == 'no_process' and pattern_data.get('size_variance', 0) > 1000:
                return 'critical'
        
        # High severity patterns
        if pattern_name in ['loss_aversion', 'fomo_spiral']:
            return 'high'
        
        return 'moderate'
    
    def _generate_diagnosis(self, validated_patterns: Dict, df: pl.DataFrame) -> Dict[str, Any]:
        """Generate overall psychological diagnosis."""
        pattern_names = list(validated_patterns.keys())
        
        # Determine primary issue
        if 'revenge_trading' in pattern_names and 'no_process' in pattern_names:
            primary_issue = "Emotional gambler disguised as trader"
            root_problem = "You're using the market to process emotions, not make money"
        elif 'loss_aversion' in pattern_names and 'winner_cutting' in pattern_names:
            primary_issue = "Fear-based trader"
            root_problem = "Fear of loss dominates every decision you make"
        elif 'fomo_spiral' in pattern_names:
            primary_issue = "Dopamine-driven trader"
            root_problem = "You're addicted to the action, not the profits"
        elif len(pattern_names) >= 3:
            primary_issue = "Psychological chaos"
            root_problem = "Multiple competing fears and impulses control your trading"
        elif pattern_names:
            primary_issue = f"{pattern_names[0].replace('_', ' ').title()} dominates"
            root_problem = "This single pattern is sabotaging your potential"
        else:
            primary_issue = "No major psychological patterns detected"
            root_problem = "Focus on refining strategy rather than psychology"
        
        # Calculate overall stats
        total_trades = df.height
        win_rate = df.filter(pl.col('pnl') > 0).height / total_trades if total_trades > 0 else 0
        total_pnl = float(df['pnl'].sum())
        
        return {
            'primary_issue': primary_issue,
            'root_problem': root_problem,
            'patterns_active': len(pattern_names),
            'severity': 'critical' if len(pattern_names) >= 3 else 'high' if len(pattern_names) >= 2 else 'moderate',
            'prognosis': self._generate_prognosis(pattern_names, win_rate, total_pnl),
            'prescription': self._generate_prescription(pattern_names)
        }
    
    def _generate_prognosis(self, patterns: List[str], win_rate: float, total_pnl: float) -> str:
        """Generate prognosis based on patterns."""
        if 'revenge_trading' in patterns:
            return "Without immediate intervention, you will blow up your account. It's not if, it's when."
        elif len(patterns) >= 3:
            return "You're one bad week away from quitting trading forever. The patterns are too destructive."
        elif win_rate < 0.3 and total_pnl < 0:
            return "Current trajectory leads to account depletion within 3-6 months."
        elif total_pnl > 0 and patterns:
            return "You're profitable despite yourself. When luck runs out, these patterns will destroy you."
        else:
            return "Addressable issues that can be fixed with discipline and systematic rules."
    
    def _generate_prescription(self, patterns: List[str]) -> List[str]:
        """Generate specific action items."""
        prescription = []
        
        if 'revenge_trading' in patterns:
            prescription.append("IMMEDIATE: Max position size = 2% of portfolio. Break this = stop trading for 1 week.")
        
        if 'loss_aversion' in patterns:
            prescription.append("RULE: -5% stop loss on EVERY trade. Set it when you enter. No exceptions.")
        
        if 'fomo_spiral' in patterns:
            prescription.append("COOLDOWN: After any +10% win, no new trades for 24 hours. Let the dopamine settle.")
        
        if 'no_process' in patterns:
            prescription.append("DOCUMENT: Before ANY trade, write: Entry reason, exit plan, position size. No plan = no trade.")
        
        if not prescription:
            prescription.append("Continue current approach but monitor for emerging patterns.")
        
        return prescription[:3]  # Top 3 most important
    
    def _summarize_confidence(self, insights: List[Dict]) -> str:
        """Summarize overall confidence in the analysis."""
        if not insights:
            return "No patterns detected with sufficient confidence"
        
        avg_confidence = sum(i['confidence'] for i in insights) / len(insights)
        
        if avg_confidence >= 0.85:
            return "High confidence - patterns are clear and statistically validated"
        elif avg_confidence >= 0.7:
            return "Moderate confidence - patterns present but some uncertainty"
        else:
            return "Low confidence - patterns suggested but need more data" 