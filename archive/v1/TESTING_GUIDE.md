# Testing Guide for Pagination Implementation

## Overview
This guide helps you thoroughly test the pagination approach for surfacing losing trades.

## 🧪 Test Scripts Available

### 1. **test_pagination_comprehensive.py**
The main test script with detailed logging.

```bash
# Test default wallet
python3 test_pagination_comprehensive.py

# Test specific wallet
python3 test_pagination_comprehensive.py <wallet_address>
```

**What it tests:**
- Individual timeframes (max, 30d, 7d, 1d)
- Automatic loser detection with fallback
- API response times
- Pagination efficiency

### 2. **test_telegram_bot.py**
Tests telegram bot integration.

```bash
python3 test_telegram_bot.py
```

## 📊 Key Logging Points

### Pagination Progress
Look for these log patterns:
```
[13:16:20] 🔍 PAGINATION: Starting fetch for rp8ntGS7...
[13:16:20]   - Timeframe: max
[13:16:20]   - Max pages: 10
[13:16:20]   - Target losers: 5
```

### Page-by-Page Results
```
[13:16:20]   ✅ Page 1: 50 items (50W/0L)
[13:16:20]   📊 Total so far: 50 items, 0 losers
[13:16:20]   ➡️  Next page cursor: 2...
```

### Loser Detection
```
[13:16:36]   💔 First loser this page: BCT ($-3,144)
[13:16:37]   🎯 Found 11 losers, stopping pagination
```

### Timeframe Fallback
```
[13:16:36] ⚠️  Not enough losers (0/5), trying shorter timeframe...
[13:16:36] 🕐 Trying timeframe: 30d
```

## 🎯 What to Verify

### 1. **Loser Surfacing**
- ✅ Losers appear even for wallets with many winners
- ✅ At least 5 losers are found (or all available if < 5)
- ✅ Pagination stops early when losers found

### 2. **Timeframe Fallback**
- ✅ System tries max → 30d → 7d → 1d
- ✅ Stops at first timeframe with sufficient losers
- ✅ Clear logging of which timeframe was used

### 3. **Performance**
- ✅ Pages fetched efficiently (stops at 5 losers)
- ✅ Total time reasonable (<30s for most wallets)
- ✅ API calls minimized

### 4. **UI Messages**
When testing via web app or telegram:
- ✅ Shows "Showing last 30 days" when timeframe narrowed
- ✅ Displays "Fetched X pages to find losing trades"
- ✅ Warning messages for truncated history

## 🔍 Common Test Scenarios

### Normal Wallet (Few Trades)
- Expected: Single page fetch, all trades shown
- Timeframe: max (all-time)
- Pages: 1

### Power Wallet (Many Winners)
- Expected: Multiple pages until losers found
- Timeframe: Likely falls back to 30d or 7d
- Pages: 3-5 typical

### Extreme Wallet (Hundreds of Winners)
- Expected: Falls back to shorter timeframes
- Timeframe: 7d or 1d
- Message: "Historical losers outside this period are not displayed"

## 🐛 Troubleshooting

### No Losers Found
```
[13:16:36] ⚠️  WARNING: Could not find 5 losers even with shortest timeframe
```
- This wallet may genuinely have no losing trades
- Check aggregated stats to verify

### API Timeouts
```
❌ Cielo API error: Read timed out
```
- Normal for aggregated stats endpoint (can be slow)
- Token fetching should still work

### High Page Count
If fetching > 5 pages:
- Check if wallet has extreme number of winners
- Consider if timeframe fallback is working properly

## 📱 Testing with Telegram Bot

1. Start the bot:
```bash
python3 telegram_bot_simple.py
```

2. In Telegram, send:
```
/analyze <wallet_address>
```

3. Watch for:
- Loading progress messages
- Window info in results
- Losers being displayed
- Response time

## 🚀 Deployment Testing

After pushing changes:
1. Wait 2-3 minutes for Railway deployment
2. Test via production bot
3. Check Railway logs for detailed output

## 💡 Pro Tips

1. **Use Known Test Wallets**
   - `rp8ntGS7P2k3faTvsRSWxQLa3B68DetNbwe1GHLiTUK` - Has losers after ~3 pages

2. **Monitor Log Patterns**
   - Winners/Losers ratio per page
   - Cursor progression
   - Timeframe fallback triggers

3. **Test Edge Cases**
   - Very new wallets (< 10 trades)
   - Only-winners wallets
   - Wallets with exactly 100 winners

4. **Verify Data Accuracy**
   - Compare with Cielo website
   - Check that losers match expected values
   - Ensure no duplicate tokens 

## Testing Conversational Features

### Test the State-Based Memory System

1. **Test Duplicate Prevention**:
   ```
   - Make a trade in token A
   - Bot asks a question
   - Make another trade in token A
   - Bot should NOT ask again (waiting for answer)
   ```

2. **Test Risk Context**:
   ```
   - Make a large trade (>20% of portfolio)
   - Bot should include exposure % in question
   - Make a trade with large P&L (>10 SOL)
   - Bot should mention P&L in question
   ```

3. **Test Answer Tracking**:
   ```
   - Make a trade and get a question
   - Reply with your reason
   - Make another trade in same token
   - Bot should ask a new question (not repeat)
   ```

4. **Test Persistence**:
   ```
   - Make a trade and get a question
   - Restart the bot
   - Make another trade in same token
   - Bot should still remember unanswered question
   ```

### Test Text-First Mode 