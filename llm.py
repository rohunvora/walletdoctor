# llm.py
import os
import json
from typing import Dict, Any, List, Optional
from openai import OpenAI

OPENAI_KEY = os.environ.get("OPENAI_KEY", "")

class TradingCoach:
    """OpenAI-powered trading coach for wallet analysis insights."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = OpenAI(api_key=api_key or OPENAI_KEY)
        self.context = """You are an experienced Solana trading coach analyzing wallet performance.
        Your role is to provide data-driven insights without hype or speculation.
        Focus on:
        1. Identifying patterns in trading behavior
        2. Highlighting risk management issues
        3. Suggesting concrete improvements
        4. Being direct but constructive
        
        Always base your analysis on the provided metrics and data."""
    
    def analyze_wallet(
        self,
        user_question: str,
        metrics: Dict[str, Any],
        detailed_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate analysis based on wallet metrics and user question.
        
        Args:
            user_question: The user's specific question
            metrics: Summary metrics from analytics
            detailed_data: Additional detailed data if needed
        
        Returns:
            Coach's analysis as a string
        """
        # Format metrics for prompt
        metrics_text = self._format_metrics(metrics)
        
        # Build prompt
        prompt = f"""{self.context}

User Question: {user_question}

Wallet Metrics:
{metrics_text}

Based on this data, provide a focused analysis addressing the user's question.
Be specific and actionable. Reference the numbers to support your points."""

        if detailed_data:
            prompt += f"\n\nAdditional Context:\n{json.dumps(detailed_data, indent=2)}"
        
        # Get response
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": self.context},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        return response.choices[0].message.content
    
    def _format_metrics(self, metrics: Dict[str, Any]) -> str:
        """Format metrics dictionary into readable text."""
        formatted = []
        
        # Win rate metrics
        if 'win_rate' in metrics:
            wr = metrics['win_rate']
            formatted.append(f"Win Rate: {wr.get('win_rate', 0):.1%} ({wr.get('winning_trades', 0)}/{wr.get('total_trades', 0)} trades)")
            formatted.append(f"Avg Win: ${wr.get('avg_win', 0):,.2f}")
            formatted.append(f"Avg Loss: ${wr.get('avg_loss', 0):,.2f}")
            formatted.append(f"Profit Factor: {wr.get('profit_factor', 0):.2f}")
        
        # Hold patterns
        if 'hold_patterns' in metrics:
            hp = metrics['hold_patterns']
            formatted.append(f"\nHold Duration (avg): {hp.get('avg_hold_hours', 0):.1f} hours")
            formatted.append(f"Quick Flips (<1h): {hp.get('quick_flips_ratio', 0):.1%}")
            if 'hold_buckets' in hp:
                formatted.append("Hold Distribution:")
                for bucket, count in hp['hold_buckets'].items():
                    formatted.append(f"  {bucket}: {count} trades")
        
        # Portfolio metrics
        if 'portfolio' in metrics:
            pm = metrics['portfolio']
            formatted.append(f"\nTotal Realized PnL: ${pm.get('total_realized_pnl', 0):,.2f}")
            formatted.append(f"Total Unrealized PnL: ${pm.get('total_unrealized_pnl', 0):,.2f}")
            formatted.append(f"Active Positions: {pm.get('active_positions', 0)}")
            if pm.get('sharpe_ratio', 0) != 0:
                formatted.append(f"Sharpe Ratio: {pm.get('sharpe_ratio', 0):.2f}")
        
        # Slippage
        if 'slippage' in metrics:
            slip = metrics['slippage']
            formatted.append(f"\nAvg Slippage: {slip.get('avg_slippage_pct', 0):.2%}")
            formatted.append(f"Total Swaps: {slip.get('total_swaps', 0)}")
        
        return '\n'.join(formatted)
    
    def suggest_improvements(
        self,
        metrics: Dict[str, Any],
        leak_trades: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """
        Generate specific improvement suggestions based on metrics.
        
        Returns list of actionable suggestions.
        """
        suggestions = []
        
        # Analyze win rate
        if 'win_rate' in metrics:
            wr = metrics['win_rate']['win_rate']
            pf = metrics['win_rate'].get('profit_factor', 0)
            
            if wr < 0.4:
                suggestions.append("🎯 Improve entry timing: Your win rate is below 40%. Consider waiting for stronger confirmations before entering trades.")
            
            if pf < 1.0:
                suggestions.append("📊 Risk/Reward: Your average loss exceeds average win. Set tighter stops or target higher reward trades.")
        
        # Analyze hold patterns
        if 'hold_patterns' in metrics:
            qf_ratio = metrics['hold_patterns'].get('quick_flips_ratio', 0)
            avg_hold = metrics['hold_patterns'].get('avg_hold_hours', 0)
            
            if qf_ratio > 0.7:
                suggestions.append("⏱️ Patience pays: 70%+ quick flips suggest overtrading. Try holding winners longer to maximize gains.")
            
            if avg_hold < 0.5:
                suggestions.append("🔍 Due diligence: Very short holds indicate FOMO trading. Research tokens before buying.")
        
        # Analyze losses
        if leak_trades and len(leak_trades) > 0:
            worst_loss = leak_trades[0].get('realizedPnl', 0)
            if worst_loss < -5000:
                suggestions.append(f"🛡️ Risk management: Your largest loss was ${worst_loss:,.2f}. Use position sizing to limit max loss to 2-5% of portfolio.")
        
        return suggestions
    
    def format_for_chat(self, content: str) -> str:
        """Format content for display in chat interface."""
        # Add some structure to make it more readable
        lines = content.split('\n')
        formatted_lines = []
        
        for line in lines:
            if line.strip():
                # Add emphasis to key points
                if any(keyword in line.lower() for keyword in ['recommendation:', 'suggestion:', 'key insight:']):
                    formatted_lines.append(f"**{line}**")
                else:
                    formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)

# Preset prompts for common analyses
ANALYSIS_PROMPTS = {
    'general': "Analyze my overall trading performance and suggest improvements.",
    'risk': "Evaluate my risk management and position sizing.",
    'timing': "Analyze my entry and exit timing patterns.",
    'losses': "Review my biggest losses and how to avoid them.",
    'psychology': "Identify any psychological patterns affecting my trading."
}

def get_quick_insight(metrics: Dict[str, Any]) -> str:
    """Generate a quick one-line insight from metrics."""
    insights = []
    
    if 'win_rate' in metrics:
        wr = metrics['win_rate']['win_rate']
        if wr < 0.3:
            insights.append("⚠️ Critical: Win rate below 30%")
        elif wr > 0.6:
            insights.append("✅ Strong: Win rate above 60%")
    
    if 'hold_patterns' in metrics:
        avg_hold = metrics['hold_patterns'].get('avg_hold_hours', 0)
        if avg_hold < 1:
            insights.append("⚡ Hyperactive: Average hold under 1 hour")
        elif avg_hold > 168:
            insights.append("💎 Diamond hands: Average hold over 1 week")
    
    if 'portfolio' in metrics:
        total_pnl = metrics['portfolio'].get('total_realized_pnl', 0)
        if total_pnl < -10000:
            insights.append("🔴 Heavy losses: Down over $10K")
        elif total_pnl > 10000:
            insights.append("🟢 Profitable: Up over $10K")
    
    return " | ".join(insights) if insights else "📊 Analyzing wallet performance..." 