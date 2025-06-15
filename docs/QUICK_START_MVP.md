# WalletDoctor MVP - Quick Start Guide

## 🚀 Get Running in 5 Minutes

### Prerequisites
- Python 3.8+
- Helius API key (get from https://helius.dev)
- Cielo API key (get from https://cielo.finance)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Set Environment Variables
```bash
export HELIUS_KEY="your-helius-key"
export CIELO_KEY="your-cielo-key"
```

### Step 3: Initialize Database
```bash
python scripts/db_migrations.py
```

### Step 4: Start the Web App
```bash
python web_app_v2.py
```

Open http://localhost:5002 in your browser.

## 🎮 Try It Out

### Web Interface Flow
1. **Enter a wallet address** (try a known trader's wallet)
2. **See instant stats** - Win rate & average P&L appear immediately
3. **Click "+ Note" on any trade** to add your thoughts
4. **Watch insights appear** based on your annotations
5. **Click "Check New Trades"** to refresh and see comparisons

### CLI Commands
```bash
# Get instant baseline
python scripts/coach.py instant <wallet-address>

# Add annotation
python scripts/coach.py annotate BONK "FOMO buy at the top"

# Check for new trades
python scripts/coach.py refresh

# See your evolution
python scripts/coach.py evolution
```

## 📊 What's Different?

### Old Way
```bash
python scripts/coach.py analyze <wallet>
# Wait... wait... wait...
# Either see nothing or get overwhelmed with stats
```

### New Way
```bash
python scripts/coach.py instant <wallet>
# Immediately see:
# - Win Rate: 28.5%
# - Average P&L: -$45.20
# - Top winners & losers
# - Prompt to add notes for insights
```

## 🧪 Testing the MVP

### Test Annotation Flow
1. Load any wallet with trades
2. Add a note to a losing trade: "FOMO'd into green candles"
3. Add a note to another similar loss: "Chased the pump again"
4. Watch the system recognize your FOMO pattern

### Test Comparison Engine
1. After loading trades, run refresh:
   ```bash
   python scripts/coach.py refresh
   ```
2. See how new trades compare to your average
3. Get suggestions based on similar past trades

### Test Evolution Tracking
1. Add several annotations over time
2. Run:
   ```bash
   python scripts/coach.py evolution
   ```
3. See your progress and pattern changes

## 🐛 Common Issues

### "No module named 'scripts'"
Run from the project root directory, not from within scripts/

### "No data found"
Make sure the wallet has trading activity. Try a known active trader.

### "API rate limited"
The free tier has limits. Wait a minute and try again.

## 💡 Key Features to Explore

1. **Instant Stats** - No waiting for 30+ trades
2. **Interactive Annotations** - Your notes power the insights
3. **Personal Comparisons** - New trades vs your average
4. **Pattern Recognition** - System learns from your annotations
5. **Evolution Tracking** - See improvement over time

## 🎯 MVP Philosophy

**Before**: "Analyze everything, show harsh truths"
**After**: "Start simple, grow with the user"

The magic happens when users start annotating. Each note makes the coaching smarter and more personalized.

## 📈 Next Steps

1. Try the web interface with your own wallet
2. Add honest annotations to 5-10 trades
3. Watch how insights evolve with your input
4. Share feedback on what patterns you discover

**Remember**: The more you annotate, the smarter it gets! 