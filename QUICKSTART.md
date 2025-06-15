# 🏥 Tradebro Bot - Quick Start

## 🎯 5-Minute Setup

### 1️⃣ Get Your Bot Token (2 min)
```
1. Open Telegram
2. Message @BotFather
3. Send: /newbot
4. Name it: My Tradebro
5. Username: mytradebro_bot
6. Copy the token!
```

### 2️⃣ Configure Bot (1 min)
```bash
# Add your token to .env file
echo "TELEGRAM_BOT_TOKEN=YOUR_TOKEN_HERE" > .env
```

### 3️⃣ Install & Run (2 min)
```bash
# Install dependencies
pip3 install --user --break-system-packages python-telegram-bot python-dotenv

# Run your bot!
python3 telegram_bot.py
```

## 💬 Using Your Bot

### First Time:
```
You: /start
Bot: Welcome to Tradebro! Send me your wallet address

You: 34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya
Bot: Found 47 trades! Here are your biggest losses...
     [Button: Add note for BONK]
     [Button: Add note for WIF]

You: [Click BONK button]
Bot: Tell me about your BONK trade (lost $3,200)

You: FOMO'd in at 2am after Twitter pump
Bot: Got it! I'll remember this pattern
```

### Daily Use:
```
/patterns - See your trading patterns
/recent   - Quick annotate recent trades  
/monitor  - Start real-time alerts
/help     - All commands
```

## 🎮 Bot Features

### 📊 Pattern Analysis
```
You: /patterns
Bot: Your Trading Patterns:
     
     1. "FOMO at 2am after Twitter"
        📈 Occurrences: 5
        💸 Total Loss: $8,400
        🪙 Tokens: BONK, WIF, PEPE
```

### 🚨 Smart Alerts (Coming Soon)
```
Bot: ⚠️ Pattern Alert for DOGE
     Loss: $1,200
     
     🔴 Social Media FOMO Pattern!
     
     Remember your past mistakes:
     This matches patterns you've documented.
     
     Take a breath. Is this trade different?
```

## 🐛 Troubleshooting

### Bot won't start?
- Check token is correct in .env
- Make sure no spaces around = in .env
- Try: `cat .env` to verify

### Can't load wallet?
- Need HELIUS_KEY and CIELO_KEY in .env
- Or use existing data in coach.db

### Python errors?
- Needs Python 3.12 or earlier
- Try: `python3.12 telegram_bot.py`

## 🎯 Pro Tips

1. **Be Specific** in annotations:
   - ❌ "Bad trade"
   - ✅ "Revenge trade after BONK loss, angry"

2. **Add Context**:
   - Time of day
   - Emotional state
   - What triggered it

3. **Review Weekly**:
   - Check /patterns every Sunday
   - Notice recurring themes
   - Set rules to avoid them

## 🚀 Next Level

Want monitoring alerts?
```bash
# Run monitoring service (separate terminal)
python3 telegram_monitor.py
```

---

**Need help?** The bot is designed to learn YOUR patterns. The more honest detail you provide, the better it can help prevent future losses! 