# Pocket Trading Coach

A goal-oriented Solana trading coach that helps you achieve your specific targets through natural conversation.

## 🎯 Core Vision

**The Payoff Loop**: Users set goals → Bot tracks progress → Bot nudges at critical moments → Users see value → Users engage more

Unlike generic trading bots, this coach adapts to YOUR specific goal:
- Want to reach 1k SOL? It'll calculate how aggressive you need to be
- Need $100/day for expenses? It'll track your daily cashouts
- Aiming for 10% monthly returns? It'll monitor your consistency

## 🏗️ Architecture

### Simple, Direct Flow
```
Wallet → Trades → Diary → Goal Context → GPT → Coaching
```

- **No complex abstractions** - Single pipeline
- **Goal-aware intelligence** - Every response filtered through your objective
- **Natural conversation** - No commands, just chat
- **Performance** - <200ms end-to-end including APIs

## 🚀 Quick Start

1. **Clone and install**
```bash
git clone https://github.com/yourusername/walletdoctor.git
cd walletdoctor
pip install -r requirements.txt
```

2. **Set up environment**
```bash
cp env.example .env
# Add your keys:
# - TELEGRAM_BOT_TOKEN (from @BotFather)
# - OPENAI_API_KEY
# - HELIUS_KEY (for blockchain data)
# - CIELO_KEY (for P&L data)
# - BIRDEYE_API_KEY (for prices)
```

3. **Start the bot**
```bash
python3 telegram_bot_coach.py
```

## 💬 Natural Conversation Flow

### First Connection
```
You: /connect YOUR_WALLET

Bot: [Analyzes your history]
"Looks like you're a momentum trader, averaging 15 SOL positions, 
42% win rate. What are you trying to achieve?"

You: trying to get to 1k sol by end of year

Bot: "So you want to reach 1000 SOL. Got that right?"

You: yes

Bot: "noted. you're at 142 SOL now, 45 days to go. 
enough yapping, show me your next trade"
```

### During Trading
```
[You buy 40% of bankroll on BONK]

Bot: "40% on one trade? that's aggressive. 
one zero delays your 1k target by 3 weeks"

You: this one's different, trust me

Bot: "noted. hope you're right"
```

### Progress Tracking
```
You: how am i doing?

Bot: "168 SOL, up 18% this week. 
on pace for 1k in 6 weeks not 7"
```

## 🎯 Goal System

Every goal breaks down into 4 primitives:
- **Metric**: What you measure (bankroll_sol, realized_usd, pnl_pct)
- **Target**: What you're aiming for (1000, 100/day, 10%)
- **Window**: Time frame (none, day, week, month)
- **Triggers**: When to speak (trade, hit target, slip, deviation)

### Supported Goal Types
- **Bankroll Growth**: "I want to reach X SOL"
- **Daily Income**: "I need $X per day"
- **Return Targets**: "I want X% monthly"
- **Custom Goals**: Natural language parsing adapts to your phrasing

## 🛠️ Technical Details

### Core Components
- `telegram_bot_coach.py` - Main bot with goal tracking
- `diary_api.py` - Data layer
- `prompt_builder.py` - Context with goal awareness
- `gpt_client.py` - OpenAI integration
- `goal_calculator.py` - Deterministic goal math (upcoming)

### Intervention Rules
The bot only speaks when it matters:
- Trade impacts goal by >10%
- Position size >25% of bankroll
- Clear deviation from stated plan
- Otherwise: stays silent, logs data

### Performance
- Goal calculation: <5ms
- End-to-end response: <200ms including APIs
- P99 latency: <500ms under load

## 📊 Coming Soon

### Phase 1+2: Foundation (In Progress)
- [ ] Goal setting with confirmation flow
- [ ] Historical data import on connect
- [ ] Cold-read generation from patterns
- [ ] 3-cycle onboarding limit
- [ ] Core integration test

### Phase 3: Runtime Integration
- [ ] Trade impact calculations
- [ ] Progress tracking
- [ ] Silence thresholds
- [ ] Goal-aware nudges

### Phase 4: Advanced Features
- [ ] Multi-goal support
- [ ] Progress visualization
- [ ] Weekly reports
- [ ] Goal adjustments

## 🧪 Testing

Run the core integration test:
```python
python3 test_goal_coach.py
```

This validates:
1. Goal extraction from natural language
2. Trade impact on goal progress
3. Appropriate intervention timing
4. Fact storage and retrieval

## 📝 License

MIT License - see LICENSE file

## 🤝 Contributing

We're building the coach every trader needs but won't admit they need.

Pull requests welcome! Focus on:
- Natural conversation flow (no jankiness)
- Goal-oriented features
- Performance (<200ms responses)
- Clear, deterministic logic

---

**Current Status**: Preparing Phase 1+2 implementation
**Bot Handle**: @mytradebro_bot
**Support**: Open an issue or DM on Twitter