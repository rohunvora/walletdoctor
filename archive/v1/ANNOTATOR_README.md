# Trade History Annotator Bot 🎯

**"Spotify Wrapped for your trades"** - A one-time experience to annotate your trading history for AI analysis.

## What It Does

1. **Analyzes** your wallet for notable trades (last 30 days)
2. **Selects** 5-7 interesting trades (biggest win, biggest loss, etc.)
3. **Guides** you through adding your reasoning for each trade
4. **Exports** an annotated CSV for ChatGPT analysis

## Quick Start

```bash
# 1. Run the bot
python3 telegram_bot_annotator.py

# 2. In Telegram, message your bot:
/start

# 3. Send your wallet address

# 4. Annotate each trade (or skip)

# 5. Get your CSV export!
```

## The Flow

```
User: /start
Bot: Welcome! Drop your wallet address...

User: 34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya
Bot: Found 5 notable trades. Let's review...

Bot: Trade #1: BONK
     Bought: $500 @ $1.2M mcap
     Sold: $1,200 @ $3.1M mcap (+140%)
     Held: 3 days
     🏆 Your biggest winner!
     
     What was your thinking here?

User: saw whale wallets accumulating, X account started promoting

Bot: ✓ Saved. Next trade...

[... continues for 5-7 trades ...]

Bot: ✅ Annotation Complete! 
     📊 Here's your CSV [file]
     
     💡 Take this to ChatGPT and ask:
     • "Analyze my trading patterns"
     • "What's my most costly mistake?"
     • "Build me trading rules"
```

## Key Features

- **One-time experience** - No accounts, no persistence
- **Smart selection** - Shows your most educational trades
- **Fast** - Complete in under 10 minutes
- **Private** - Everything is ephemeral
- **Actionable** - Export ready for AI analysis

## The Export

CSV includes:
- Date, token, buy/sell amounts
- Market cap at entry/exit
- P&L percentage
- Hold duration
- **Your reasoning** (the magic ingredient!)

## Test It

```bash
# See example flow without running bot
python3 test_annotator_flow.py
```

## Philosophy

> "The best trading insights come from understanding your own patterns"

This tool doesn't analyze for you - it helps you build the dataset for deeper analysis with AI.

## Technical Notes

- Uses existing `diary_api.py` for trade data
- Ephemeral sessions (no database needed)
- Simple conversation flow with timeout
- Exports clean CSV for further analysis

---

Ship it! 🚀