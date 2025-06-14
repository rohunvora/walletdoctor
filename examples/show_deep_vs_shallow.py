#!/usr/bin/env python3
"""Show the difference between shallow and deep analysis."""

print("="*60)
print("SHALLOW vs DEEP ANALYSIS")
print("="*60)

# The same data
data = {
    "win_rate": 26,
    "profit_factor": 1.31,
    "avg_winner_hold": 293,  # minutes
    "avg_loser_hold": 373,   # minutes
    "largest_loss": 59224,
    "position_variance": 2808  # %
}

print("\n📊 RAW DATA:")
for k, v in data.items():
    print(f"   {k}: {v}")

print("\n" + "-"*60)
print("\n❌ SHALLOW INSIGHTS (what you got):\n")

print("1. Your win rate is only 26%. Focus on better entry setups.")
print("2. Your largest loss was $59,224. Size down.")
print("3. You hold losers for 373 min average. Cut losses quicker.")
print("4. Position sizes vary 2808%. Be more consistent.")

print("\n" + "-"*60)
print("\n✅ DEEP INSIGHTS (what you need):\n")

print("""1. PATTERN: You hold losers 27% longer than winners (373 vs 293 min)
   WHY: Classic loss aversion. You can't admit you're wrong.
   SUBCONSCIOUS: "If I don't sell, it's not a real loss"
   FIX: Hard stop at -5%. No exceptions. Your ego isn't worth $59K.

2. PATTERN: 26% win rate BUT 1.31 profit factor 
   WHY: You're not bad at finding winners—you found GOONC (+$204K).
       You're bad at everything else.
   SUBCONSCIOUS: "I just need one big win to make it all back"
   FIX: You're not a VC. Stop betting like one.

3. PATTERN: 2,808% position variance + $59K loss
   WHY: After small losses, you 10x your size to "get even"
   SUBCONSCIOUS: "The market owes me"
   FIX: The market owes you nothing. Max 2% per trade or quit.

THE REAL PROBLEM: You're not trading—you're in a toxic relationship
with the market. You hold losers like an ex you can't let go. You
revenge trade like you're settling a score. You cut winners early
because you don't believe you deserve them.

This isn't about strategy. It's about psychology.
Fix your mind or the market will break it.""")

print("\n" + "="*60)
print("\nWhich analysis would actually change your behavior?")
print("Which one shows you the 'train of thought' from data to insight?")
print("Which one is harsh enough to break through your patterns?")
print("\nThat's what WalletDoctor should deliver.")
print("="*60) 