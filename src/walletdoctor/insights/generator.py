"""Insight generator that transforms metrics into actionable insights."""
import importlib
import yaml
from pathlib import Path
from typing import Dict, List, Tuple, Any

# Load rules from YAML
_RULES_PATH = Path(__file__).with_name("rules.yaml")
_RULES = yaml.safe_load(_RULES_PATH.read_text()) if _RULES_PATH.exists() else {}


def rank_signals(metrics: Dict[str, float]) -> List[Tuple[str, float, float]]:
    """
    Rank metrics by importance based on thresholds and weights.
    
    Returns list of (metric_name, value, weight) tuples, sorted by weight.
    """
    scored = []
    
    for metric_name, value in metrics.items():
        if metric_name not in _RULES:
            continue
            
        rule = _RULES[metric_name]
        threshold = rule["threshold"]
        weight = rule["weight"]
        inverse = rule.get("inverse", False)
        
        # Check if metric triggers the rule
        if inverse:
            # Triggers when value is BELOW threshold
            if value < threshold:
                scored.append((metric_name, value, weight))
        else:
            # Triggers when value is ABOVE threshold
            if value >= threshold:
                scored.append((metric_name, value, weight))
    
    # Sort by weight (highest first) and return top insights
    return sorted(scored, key=lambda x: x[2], reverse=True)


def render(
    metrics: Dict[str, float], 
    extras: Dict[str, Any] = None,
    max_insights: int = 5
) -> List[str]:
    """
    Render top insights as formatted strings.
    
    Args:
        metrics: Dictionary of metric_name -> value
        extras: Additional context for templates (e.g., extra_pnl)
        max_insights: Maximum number of insights to return
    
    Returns:
        List of formatted insight strings
    """
    if extras is None:
        extras = {}
    
    # Get ranked signals
    ranked = rank_signals(metrics)[:max_insights]
    
    # Render each insight
    insights = []
    for metric_name, value, _ in ranked:
        rule = _RULES[metric_name]
        template = rule["template"]
        
        # Check if this rule requires extras
        required_extras = rule.get("requires_extra", [])
        missing_extras = [e for e in required_extras if e not in extras]
        
        if missing_extras:
            # Skip this insight if required extras are missing
            continue
        
        # Format the template
        try:
            insight = template.format(value=value, **extras)
            # Clean up multiline templates
            insight = " ".join(insight.split())
            insights.append(insight)
        except KeyError as e:
            # Skip if template has missing variables
            continue
    
    return insights


def get_insight_metadata(metric_name: str) -> Dict[str, Any]:
    """Get metadata for a specific insight rule."""
    if metric_name not in _RULES:
        return {}
    
    rule = _RULES[metric_name]
    return {
        "threshold": rule["threshold"],
        "weight": rule["weight"],
        "inverse": rule.get("inverse", False),
        "requires_extra": rule.get("requires_extra", [])
    }


def calculate_extras(df) -> Dict[str, float]:
    """
    Calculate additional context values that insights might need.
    
    This is where you'd calculate things like:
    - extra_pnl: Additional P&L from holding winners longer
    - peer_comparison: How metrics compare to average trader
    - etc.
    """
    extras = {}
    
    # Example: Calculate extra P&L from holding winners longer
    # This is a simplified calculation - you'd want more sophisticated logic
    if hasattr(df, "filter") and "pnl" in df.columns and "hold_minutes" in df.columns:
        winners = df.filter(df["pnl"] > 0)
        if not winners.is_empty():
            # Estimate: 2% extra per hour of holding
            avg_hold = float(winners["hold_minutes"].mean())
            if avg_hold < 60:  # Less than 1 hour average
                potential_hours = 1 - (avg_hold / 60)
                extras["extra_pnl"] = potential_hours * 2  # 2% per hour estimate
    
    return extras


def format_header(metrics: Dict[str, float]) -> str:
    """
    Format a summary header for the insights.
    
    Returns formatted header string with key metrics.
    """
    parts = []
    
    # Net P&L
    if "total_pnl" in metrics:
        pnl = metrics["total_pnl"]
        pnl_str = f"{'+'if pnl >= 0 else ''}{pnl:.0f} SOL"
        if "total_pnl_pct" in metrics:
            pnl_str += f" ({metrics['total_pnl_pct']:+.1f}%)"
        parts.append(f"Net P&L: {pnl_str}")
    
    # Win rate
    if "win_rate" in metrics:
        parts.append(f"Win rate: {metrics['win_rate']:.0f}%")
    
    # Trade count
    if "trade_count" in metrics:
        parts.append(f"Trades: {int(metrics['trade_count'])}")
    
    return " | ".join(parts) if parts else "Analyzing wallet performance..."


def generate_full_report(
    metrics: Dict[str, float],
    extras: Dict[str, Any] = None,
    max_insights: int = 5
) -> Dict[str, Any]:
    """
    Generate a complete insight report.
    
    Returns dictionary with:
    - header: Summary line
    - insights: List of insight strings
    - metadata: Additional context
    """
    if extras is None:
        extras = calculate_extras(metrics.get("_dataframe"))
    
    # Remove internal keys
    clean_metrics = {k: v for k, v in metrics.items() if not k.startswith("_")}
    
    return {
        "header": format_header(clean_metrics),
        "insights": render(clean_metrics, extras, max_insights),
        "metadata": {
            "total_metrics": len(clean_metrics),
            "triggered_insights": len(rank_signals(clean_metrics)),
            "showing": min(max_insights, len(rank_signals(clean_metrics)))
        }
    } 