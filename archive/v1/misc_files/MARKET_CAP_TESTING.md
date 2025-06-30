# Market Cap-Centric Trading - Testing Guide

## 🧪 Testing Overview

This guide covers how to test the new market cap-centric trading features in the Pocket Trading Coach bot.

## 1. Mock Testing (No Dependencies Required)

Run the mock test to see simulated functionality:
```bash
python3 test_market_cap_mock.py
```

This demonstrates:
- Market cap capture for BUY trades
- Entry/exit mcap tracking with multipliers
- Coach L's market cap-aware responses

## 2. Manual Testing with Live Bot

### Prerequisites
- Bot must be running: `./management/start_bot.sh`
- Connected wallet: `/connect YOUR_WALLET`
- Environment variables set (TELEGRAM_BOT_TOKEN, HELIUS_KEY, etc.)

### Test Scenarios

#### Scenario 1: BUY Trade Market Cap
1. **Action**: Buy any token on Solana
2. **Expected Notification**:
   ```
   🟢 Bought BONK at $1.2M mcap (0.500 SOL)
   🔴 BUY BONK on Raydium
   [Full notification details...]
   ```
3. **Verify**: Market cap is shown in first message

#### Scenario 2: SELL Trade with Multiplier
1. **Action**: Sell a token you previously bought
2. **Expected Notification**:
   ```
   🔴 Sold WIF at $5.4M mcap (2.7x from $2M entry) +$230
   🔴 SELL WIF on Raydium
   [Full notification details...]
   ```
3. **Verify**: Shows entry mcap, exit mcap, and multiplier

#### Scenario 3: Test GPT Market Cap Tool
1. **Action**: Ask the bot about market cap
2. **Test Messages**:
   - "what's the mcap on WIF?"
   - "show me market cap context for BONK"
   - "how many x am I up on PEPE?"
3. **Expected**: Bot uses `fetch_market_cap_context` tool and provides analysis

### Coach L Response Testing

#### Test 1: Micro Cap Entry
- **Trade**: Buy token with <$100K market cap
- **Expected Coach Response**: "Sub-100k degen play. What's your target - $1M for a 10x?"

#### Test 2: High Market Cap Entry
- **Trade**: Buy token with >$50M market cap
- **Expected Coach Response**: "Getting in at $50M? The easy money was at $5M. What's the upside?"

#### Test 3: Profitable Exit
- **Trade**: Sell token at 3x+ from entry
- **Expected Coach Response**: "Solid 3x from $2M to $6M. Taking it all or keeping a moon bag?"

## 3. Database Verification

Check that market cap data is stored correctly:

```sql
-- Connect to database
sqlite3 pocket_coach.db

-- View recent trades with market cap
SELECT 
    json_extract(data, '$.token_symbol') as token,
    json_extract(data, '$.action') as action,
    json_extract(data, '$.market_cap') as mcap,
    json_extract(data, '$.market_cap_formatted') as mcap_fmt
FROM diary 
WHERE entry_type = 'trade'
ORDER BY timestamp DESC 
LIMIT 5;
```

## 4. API Testing

Test market cap fetching directly:

```python
# Test script to verify market cap API
import asyncio
from scripts.token_metadata import TokenMetadataService

async def test():
    service = TokenMetadataService()
    
    # Test with known token
    bonk_mint = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
    mcap = await service.get_market_cap(bonk_mint)
    print(f"BONK mcap: {service.format_market_cap(mcap)}")

asyncio.run(test())
```

## 5. Edge Cases to Test

### Case 1: No Market Cap Data
- Trade a brand new token (< 5 min old)
- Expected: Shows "Unknown" but doesn't crash

### Case 2: First Buy (No Entry Data)
- Sell a token without prior BUY in diary
- Expected: Shows current mcap without multiplier

### Case 3: Multiple Entries
- Buy same token multiple times at different mcaps
- Expected: Uses most recent BUY for entry mcap

## 6. Performance Testing

Monitor for:
- API response time (should cache for 5-10 min)
- No duplicate API calls for same token
- Graceful fallback if APIs fail

## 🎯 Success Criteria

✅ All trades show market cap in notifications
✅ SELL trades show mcap progression (entry → exit)
✅ Coach L comments use mcap context appropriately
✅ GPT can fetch and analyze mcap data on request
✅ Data persists in diary for historical analysis

## 📊 Sample Test Results

From mock test output:
```
BUY: 🟢 Bought BONK at $1.2M mcap (0.500 SOL)
SELL: 🔴 Sold BONK at $3.2M mcap (2.7x from $1.2M entry) +$230
```

This demonstrates the transformation from generic notifications to market cap-aware trading context that helps traders understand risk/reward instantly. 