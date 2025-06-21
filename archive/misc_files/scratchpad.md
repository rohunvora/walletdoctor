# WalletDoctor Development Scratchpad

## Current Project Status (Updated: Dec 2024)

### What WalletDoctor Is Now
A web-based Solana trading analyzer that provides harsh, direct insights about trading behavior. Deployed on Railway with a Flask frontend. No fluff, no generic advice - just brutal truths backed by data.

### Core Value Proposition
- **Before**: "Consider improving your risk management strategy"
- **After**: "You hold losers 3.2x longer than winners. This cost you $127,453."

### Core Features
1. **Data Collection**: Fetches wallet data from Helius (transactions) and Cielo (P&L)
2. **Statistical Analysis**: Shows win rates, P&L, hold times, top gainers/losers
3. **Harsh Insights**: Brutal truths about trading patterns with specific fixes
4. **Position Size Analysis**: Shows which entry sizes are profitable vs unprofitable
5. **Web Interface**: Simple UI for wallet analysis and AI-powered follow-up questions

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Web Frontend  │ --> │  Flask Backend   │ --> │   Coach CLI     │
│  (Railway/Flask)│     │   (web_app.py)   │     │  (coach.py)     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                           |
                                ┌──────────────────────────┴───────────────┐
                                │                                          │
                        ┌───────v────────┐                      ┌─────────v────────┐
                        │  Data Fetching │                      │  Harsh Insights  │
                        │  (data.py)     │                      │(harsh_insights.py)│
                        └────────────────┘                      └──────────────────┘
                                |                                         |
                        ┌───────v────────┐                      ┌─────────v────────┐
                        │ Helius/Cielo   │                      │ Pattern Analysis │
                        │     APIs       │                      │ Position Sizing  │
                        └────────────────┘                      └──────────────────┘
```

## Key Files

### Core System
- `coach.py` - Main CLI with commands (load, stats, analyze, quick-analyze)
- `web_app.py` - Flask web interface with timeout protection
- `harsh_insights.py` - Generates brutal, actionable insights (NEW!)
- `data.py` - API integrations for Helius and Cielo
- `transforms.py` - Data normalization
- `analytics.py` - Basic statistical calculations
- `llm.py` - OpenAI integration for follow-up questions

### Database Schema
```sql
-- tx table (transactions)
signature, timestamp, fee, type, source, slot, token_mint, 
token_amount, native_amount, from_address, to_address, transfer_type

-- pnl table (profit/loss)
mint, symbol, realizedPnl, unrealizedPnl, totalPnl, 
avgBuyPrice, avgSellPrice, quantity, totalBought, totalSold,
holdTimeSeconds, numSwaps
```

## Current Insights We Generate

### 1. Position Size Sweet Spot (NEW!)
```
💰 YOUR POSITION SIZE SWEET SPOT
Best size range: $1K-5K (Total P&L: $127,453)
Worst size range: >$50K (Total P&L: -$84,291)
$1K-5K win rate: 47%
>$50K win rate: 18%
THE FIX: Stick to $1K-5K positions. Your >$50K trades are ego, not edge.
```

### 2. Hold Time Analysis
```
⏰ YOUR PROFITABLE TIME WINDOW
<10min: 18% win rate, -$67k total
2-6hr: 52% win rate, +$89k total ← YOUR ZONE
>24hr: 22% win rate, -$94k total
THE FIX: Set alerts at 2hr and 6hr. That's your zone.
```

### 3. Bag Holding Detection
```
❌ YOUR WORST HABIT: Bag Holding
You hold losers 3.2x longer than winners
Worst bag: XCCOM held for 15.2 hours, lost $24,016
COST: This habit cost you $127,453
THE FIX: Set stop losses at -10%. No exceptions.
```

### 4. Overtrading Detection
```
🎰 REALITY CHECK: You're Not Trading, You're Gambling
800 tokens traded (≈27 per day)
Median hold time: 9.9 minutes
Quick trade win rate: 18%
THE FIX: Maximum 5 trades per day. Minimum 1 hour hold.
```

### 5. Swap Frequency Impact
```
🔄 OVERTRADING EACH POSITION
Low swap (≤5) P&L: $87,234
High swap (>5) P&L: -$45,123
The more you touch it, the more you lose
THE FIX: Plan your trade, trade your plan. Max 3 adjustments.
```

## What We CANNOT Do (Being Honest)

- Revenge trading sequences (no individual trade timestamps)
- Time-of-day patterns (no entry timestamps)
- Following influencer calls (no external data)
- Market cap analysis (no mcap data)
- Buying after pumps (no price history)

## Deployment

- **Platform**: Railway
- **URL**: web-production-87548.up.railway.app
- **Environment Variables Required**:
  - HELIUS_KEY (blockchain data)
  - CIELO_KEY (P&L data)
  - OPENAI_API_KEY (follow-up questions)

## Recent Evolution

### Phase 1: Basic Functionality ✓
- Flask web interface
- Basic wallet analysis
- Database storage

### Phase 2: Performance Fix ✓
- Fixed 30-second timeout issue
- Created `quick-analyze` command
- Separated heavy processing from web requests

### Phase 3: Harsh Insights ✓
- Removed generic AI slop
- Created direct, brutal feedback
- Added position size analysis
- Focus on actionable fixes

### Phase 4: Current Focus
- Better visual presentation
- HTML/rich text formatting
- Mobile optimization
- Potentially PDF reports

## Key Design Principles

1. **Brutal Honesty**: "You're gambling" not "consider reducing frequency"
2. **Specific Numbers**: "$127,453 lost" not "significant losses"
3. **One Clear Fix**: Not a paragraph of suggestions
4. **Real Examples**: Your actual worst trades, not hypotheticals
5. **No Hallucination**: Only insights we can prove with data

## Success Metrics

- **Before**: Generic ChatGPT-style trading advice
- **After**: Specific patterns with dollar costs and clear fixes
- **Impact**: Insights that actually change behavior

## Next Steps

1. **Visual Impact**: HTML formatting, charts, better UI
2. **Mobile Experience**: Responsive design
3. **Export Options**: PDF reports, CSV data
4. **Social Proof**: Share cards for brutal truths

## Technical Debt

- DuckDB connection management (minor)
- No proper error boundaries in web UI
- Limited test coverage
- Manual deployment process

## Lessons Learned

1. **Data Quality > Feature Quantity**: Better to do 5 things well than 20 poorly
2. **Direct Language Works**: Traders want truth, not comfort
3. **Position Sizing Matters**: Most actionable insight we can provide
4. **Speed Matters**: 30-second timeout taught us to optimize 