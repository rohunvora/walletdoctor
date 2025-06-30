# Cielo Finance API Reverse Engineering Summary

## Key Findings

### 1. API Limitations
- **Hard limit of 50 tokens** returned by the `/pnl/tokens` endpoint
- Pagination is **completely broken** - all page/offset parameters return the same first 50 tokens
- No alternative endpoints found for accessing complete data

### 2. Token Selection Methodology
The API appears to select the "top 50" tokens based on some ranking, likely:
- Sorted by absolute P&L or trading volume
- Biased towards profitable trades (visible average: +$1,181 per token)
- Excludes most losing trades (hidden average: -$1,921 per token)

### 3. Data Structure & Calculations

#### P&L Calculation Mystery (rasmr token example)
- Simple P&L: sell_usd - buy_usd = -$22,623
- Reported P&L: +$2,279
- Discrepancy: $24,903

**Hypothesis**: Cielo includes unrealized gains on partial sells or uses mark-to-market accounting for positions that were partially closed.

#### Field Calculations
- `average_buy_price` = `total_buy_usd` / `total_buy_amount` ✓
- `average_sell_price` = `total_sell_usd` / `total_sell_amount` ✓
- `roi_percentage` = (`total_pnl_usd` / `total_buy_usd`) * 100
- `holding_time_seconds` = Complex calculation, not simply last_trade - first_trade

### 4. Data Coverage Impact
For wallet `34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya`:
- **Total tokens**: 136
- **Visible tokens**: 50 (37%)
- **Hidden tokens**: 86 (63%)
- **Visible P&L**: +$59,064 (profitable subset)
- **Hidden P&L**: -$165,185 (losing trades)
- **True P&L**: -$106,121 (massive difference!)

### 5. Why This Matters for Coaching
The coaching system shows:
- "72% win rate" based on 50 visible tokens
- Reality: 24% win rate across all 136 tokens
- Users see cherry-picked successful trades
- Massive losses are completely hidden

### 6. Technical Details

#### Working Endpoints
- `/api/v1/{wallet}/pnl/tokens` - Returns top 50 tokens
- `/api/v1/{wallet}/pnl/total-stats` - Returns accurate totals

#### Broken Features
- Pagination: `page`, `p`, `offset`, `skip` all ignored
- Limit parameter: Max 50 regardless of value
- No CSV export or full data download

#### Authentication
- Header: `x-api-key: {uuid}`
- No rate limiting observed during testing

### 7. Recommendations

1. **For Accurate Coaching**: 
   - Always show data incompleteness warnings
   - Reference total stats for context
   - Mention that most losses may be hidden

2. **For Complete Data**:
   - Contact Cielo support about pagination
   - Consider using Helius for full transaction history
   - Build own P&L calculation engine

3. **For Users**:
   - Be aware that Cielo shows a biased view
   - The "top tokens" view hides most losses
   - Check total stats for real performance

## Conclusion

Cielo's API design (intentionally or not) creates a **heavily biased view** of trading performance by showing only the top 50 tokens. This makes traders appear more successful than they actually are, hiding 63% of trades which contain the bulk of losses. The broken pagination prevents access to complete data, making accurate analysis impossible through their API alone.