#!/usr/bin/env python3
"""
Test the Trade Annotator flow
Shows how the bot guides users through annotation
"""

import asyncio
from diary_api import get_notable_trades, format_market_cap_short


async def test_flow():
    """Simulate the annotation flow"""
    print("TRADE HISTORY ANNOTATOR - Test Flow")
    print("=" * 50)
    
    # Test wallet
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    print("\nUSER: /start")
    print("\nBOT: 🎯 **Trade History Annotator**")
    print("I'll help you create an annotated dataset of your trades for AI analysis.")
    print("Just drop your wallet address and we'll review your most notable trades together.")
    print("_One-time experience. No data saved._")
    
    print(f"\nUSER: {wallet}")
    print("\nBOT: 🔍 Analyzing your trading history...")
    
    # Fetch notable trades
    trades = await get_notable_trades(wallet, days=30, max_trades=5)
    
    if not trades:
        print("\nBOT: 😕 No trades found in the last 30 days.")
        return
    
    print(f"\nBOT: ✅ Found **{len(trades)} notable trades** from the last 30 days.")
    print("Let's add your reasoning to each one.")
    
    # Simulate annotation loop
    annotations = {}
    
    for trade in trades[:3]:  # Show first 3 for demo
        print("\n" + "-" * 50)
        print(f"\nBOT: **Trade #{trade['index']}: {trade['token']}**")
        print(f"💰 Bought: ${trade['entry_usd']:.0f} @ {trade['entry_mcap_formatted']} mcap")
        
        if trade['status'] == 'closed':
            print(f"💸 Sold: ${trade['exit_usd']:.0f} @ {trade['exit_mcap_formatted']} mcap", end="")
            if trade['pnl_pct'] > 0:
                print(f" (+{trade['pnl_pct']:.0f}%)")
            else:
                print(f" ({trade['pnl_pct']:.0f}%)")
        else:
            print("📊 Status: Still holding")
        
        print(f"⏱️ Held: {trade['held_days']} days")
        
        # Show reason
        reasons = {
            'biggest_winner': "🏆 Your biggest winner!",
            'biggest_loser': "📉 Your biggest loss.",
            'largest_position': "🐋 Your largest position.",
            'underwater_position': "🌊 Currently underwater."
        }
        if trade['selection_reason'] in reasons:
            print(f"\n_{reasons[trade['selection_reason']]}_")
        
        print("\n**What was your thinking here?** (or 'skip')")
        
        # Simulate user responses
        if trade['selection_reason'] == 'biggest_winner':
            annotation = "saw whale wallets accumulating, X account with 50k followers started promoting"
        elif trade['selection_reason'] == 'biggest_loser':
            annotation = "FOMO'd in after it already pumped, no real research"
        else:
            annotation = "followed a trader I trust, seemed like good risk/reward"
        
        print(f"\nUSER: {annotation}")
        print("BOT: ✓ Saved")
        annotations[trade['index']] = annotation
    
    # Show completion
    print("\n" + "=" * 50)
    print("\nBOT: ✅ **Annotation Complete!**")
    print(f"Annotated {len(annotations)}/{len(trades)} trades")
    print("📊 Your annotated history is ready!")
    
    # Show CSV preview
    print("\nCSV Preview:")
    print("-" * 50)
    print("date,token,direction,amount_usd,mcap_entry,mcap_exit,pnl_pct,held_days,your_reasoning")
    
    for trade in trades[:3]:
        if trade['index'] in annotations:
            if trade['status'] == 'closed':
                print(f"2024-01-15,{trade['token']},buy/sell,{trade['entry_usd']:.0f},"
                      f"{trade.get('entry_mcap', '')},{trade.get('exit_mcap', '')},"
                      f"{trade.get('pnl_pct', 0):.1f},{trade['held_days']},"
                      f"\"{annotations[trade['index']]}\"")
    
    print("\n" + "=" * 50)
    print("\n💡 **Take this to ChatGPT and try:**")
    print("• \"Analyze my trading patterns. What works? What doesn't?\"")
    print("• \"What's my most costly mistake pattern?\"")
    print("• \"Build me trading rules based on what works\"")


if __name__ == "__main__":
    asyncio.run(test_flow())