"""LLM prompt construction for narrative weaving only."""
from typing import List, Dict, Any

SYSTEM = """You are Tradebro, an elite trading coach.
Your ONLY job is to weave pre-analyzed insights into a tight, empathic narrative.

Rules:
1. Keep total response under 280 words
2. Use short, punchy sentences  
3. No generic advice or platitudes
4. Mirror the exact numbers given in bullets
5. Add connecting tissue between insights, not new analysis
6. End with ONE specific action item

Write like a calm mentor who's seen it all."""


def make_messages(header: str, bullets: List[str], context: Dict[str, Any] = None) -> List[Dict[str, str]]:
    """
    Construct messages for OpenAI chat completion.
    
    Args:
        header: Summary line with key metrics
        bullets: Pre-analyzed insight strings
        context: Optional additional context
    
    Returns:
        List of message dicts for OpenAI API
    """
    # Format the bullets
    bullet_text = "\n".join(f"• {b}" for b in bullets)
    
    # Build user message
    user_content = f"""Wallet Analysis:
{header}

Key findings:
{bullet_text}

Weave these specific insights into a cohesive narrative. 
Focus on the psychology behind the numbers.
What's the trader's core problem? What ONE thing should they fix first?"""
    
    # Add context if provided
    if context:
        user_content += f"\n\nAdditional context: {context}"
    
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user_content}
    ]


def make_quick_assessment(metrics: Dict[str, float]) -> str:
    """
    Generate a one-line assessment without calling LLM.
    Used for quick feedback or when LLM is unavailable.
    """
    assessments = []
    
    # Critical issues (ordered by severity)
    if metrics.get("win_rate", 100) < 30:
        assessments.append("⚠️ Critical: Win rate below 30%")
    elif metrics.get("profit_factor", 1) < 0.8:
        assessments.append("🔴 Losing more than winning")
    elif metrics.get("revenge_trading_risk", 0) > 50:
        assessments.append("😤 Revenge trading detected")
    elif metrics.get("fee_burn", 0) > 100:
        assessments.append("💸 Excessive fees eating profits")
    elif metrics.get("overtrading_score", 0) > 40:
        assessments.append("⚡ Overtrading alert")
    
    # Positive indicators
    if metrics.get("profit_factor", 0) > 2:
        assessments.append("✅ Strong profit factor")
    if metrics.get("win_rate", 0) > 60:
        assessments.append("🎯 Excellent win rate")
    
    return assessments[0] if assessments else "📊 Analyzing patterns..."


def format_for_cli(response: str) -> str:
    """
    Format LLM response for CLI display.
    Adds visual breaks and emphasis.
    """
    lines = response.strip().split("\n")
    formatted = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Add emphasis to key phrases
        if any(phrase in line.lower() for phrase in ["but", "however", "problem", "fix"]):
            formatted.append(f"\n{line}\n")
        else:
            formatted.append(line)
    
    return "\n".join(formatted)


def format_for_web(response: str) -> Dict[str, Any]:
    """
    Format LLM response for web display.
    Splits into sections for better rendering.
    """
    lines = response.strip().split("\n")
    
    # Try to identify sections
    main_insight = []
    action_item = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Look for action item (usually last paragraph or starts with action words)
        if any(line.lower().startswith(word) for word in ["fix", "start", "focus", "try", "stop"]):
            action_item = line
        else:
            main_insight.append(line)
    
    return {
        "main": " ".join(main_insight),
        "action": action_item or "Review your biggest losses and identify patterns.",
        "severity": _assess_severity(response)
    }


def _assess_severity(response: str) -> str:
    """Assess severity level from response content."""
    response_lower = response.lower()
    
    if any(word in response_lower for word in ["critical", "severe", "dangerous", "burning"]):
        return "critical"
    elif any(word in response_lower for word in ["problem", "issue", "concern", "leak"]):
        return "warning"
    elif any(word in response_lower for word in ["good", "strong", "excellent"]):
        return "success"
    else:
        return "info" 