# Expected Conversation Flow - Live Test

## Initial Contact
```
You: /start
Bot: Yo! I'm your pocket trading coach 👋

I watch trades and help spot patterns. Been trading long or just getting started?

You: been trading for a while
Bot: Nice! Drop your wallet address and I'll start tracking your moves. 
     I'll learn your patterns and help you spot habits (good and bad) 📊

You: [paste your wallet address]
Bot: Got it! Watching that wallet now 👁️

Go ahead and trade normally. I'll jump in when I spot something interesting.

Few things:
• I learn from YOUR patterns, not the market
• Say 'pause' if I'm too chatty
• Just talk normally - no commands

GL out there! 🚀
```

## During Trades
```
[You make a trade - bot detects it within 5 seconds]

Bot: BONK for 2.5 SOL. What's got you interested?

You: twitter was going crazy about it
Bot: Twitter calls... how's that strategy working out? 😅

You: actually pretty well lately
Bot: Fair enough! What's your exit plan?

[Later you sell]
Bot: Nice! +$180 on BONK 🔥 Good timing or just lucky?

You: saw the momentum shifting
Bot: Smart. Reading the room pays off 📊
```

## Natural Commands
```
You: this is too much, pause for now
Bot: Got it, taking a break 🤐 Hit me up whenever.

[Later]
You: hey I'm back
Bot: Back in action! 📈 What's moving in the market?

You: let's start fresh
Bot: Clean slate! What's the next move? 🌱
```

## What You Should Test

### 1. Personality
- Does it feel like texting a friend?
- Are responses specific to your trades?
- Does it roast you (gently) when appropriate?

### 2. Natural Language
Try variations:
- "chill out", "too many messages", "give me space" → should pause
- "reset", "new start", "wipe the slate" → should clear
- "sup", "yo", "hey" → should respond naturally

### 3. Trading Context
- Make a small trade → should ask about strategy
- Make a big trade → should comment on size
- Lose money → should empathize with specific amount
- Win money → should celebrate with specific amount

### 4. Conversation Flow
- Does it remember the conversation?
- Can you have back-and-forth dialogue?
- Does it reference your previous messages?

## Red Flags to Look For

❌ Responses feel robotic or generic  
❌ Doesn't mention trade amounts/tokens specifically  
❌ Can't understand variations of "pause/clear"  
❌ Asks for commands instead of natural conversation  
❌ Doesn't show personality - too polite  

## Success Signals

✅ You forget you're talking to a bot  
✅ Responses feel tailored to your specific trades  
✅ Natural conversation without thinking about commands  
✅ Shows personality - gentle roasting, celebrates wins  
✅ References actual amounts and token names  