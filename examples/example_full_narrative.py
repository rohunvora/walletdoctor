#!/usr/bin/env python3
"""Example of what the full narrative output would look like with LLM integration."""

# This is what the LLM would generate from the insights we just saw

EXAMPLE_NARRATIVE = """
You're profitable, but you're leaving money on the table through poor discipline.

Your $59,224 loss on XBT tells the whole story. You're swinging for home runs 
with position sizes that vary by 2,808%. One bad trade shouldn't erase weeks 
of work, but yours do.

The 26% win rate isn't the problem—plenty of traders profit with low win rates. 
The problem is you hold losers 80 minutes longer than winners. You're quick to 
take profits but slow to admit mistakes. That's fear talking, not strategy.

Your biggest leak? Position sizing. When GOONC printed $204K, you got greedy. 
When XBT dumped, you were overexposed. The market rewards consistency, not 
gambling.

Fix the position sizing first. Cap every trade at 2% portfolio risk. That one 
change turns your $59K disaster into a $6K lesson. Do that for 30 days and 
watch your equity curve smooth out.
"""

if __name__ == "__main__":
    print("Example Tradebro Output with Full LLM Narrative")
    print("="*60)
    print()
    print("┌─ Wallet Doctor — Analysis ─┐")
    print("| Net P&L: +$332,499 (+18%)  |")
    print("| Win rate: 26% | Trades: 790 |")
    print("└────────────────────────────┘")
    print()
    print(EXAMPLE_NARRATIVE)
    print()
    print("─" * 60)
    print("Word count:", len(EXAMPLE_NARRATIVE.split()))
    print("Characters:", len(EXAMPLE_NARRATIVE))
    print()
    print("Notice how the LLM:")
    print("• Weaves the metrics into a story")
    print("• Identifies the psychological pattern")
    print("• Ends with ONE specific action")
    print("• Stays under 280 words")
    print()
    print("This is the power of separating analysis from narrative!") 