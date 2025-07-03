# Chain-of-Thought Trade Analysis Prompt

## Prompt Template

```
I need to analyze this Solana wallet's trading performance using a step-by-step approach. Let me think through this systematically.

Trading Data:
{{WALLET_DATA}}

I'll analyze this data step by step:

Step 1: Data Overview
- First, let me count the total number of trades and unique tokens
- Calculate the date range of trading activity
- Identify the types of transactions (buys vs sells)

Step 2: Performance Metrics
- Calculate total P&L by summing all pnl_usd values
- Determine win rate (profitable trades / total trades)
- Find average trade size and median trade size
- Calculate profit factor (gross profits / gross losses)

Step 3: Token Analysis
- Group trades by token symbol
- Calculate P&L per token
- Identify which tokens were most/least profitable
- Analyze hold times per token (time between buy and sell)

Step 4: Pattern Recognition
- Look for time-based patterns (day of week, time of day)
- Identify FOMO indicators (buying after price increases)
- Check for revenge trading (increased size after losses)
- Analyze position sizing patterns

Step 5: Risk Analysis
- Calculate maximum drawdown
- Identify largest single-day losses
- Check for proper position sizing
- Look for stop-loss usage patterns

Step 6: Behavioral Insights
- Identify psychological patterns in the trading
- Look for consistency in strategy
- Check for emotional trading indicators
- Analyze learning/improvement over time

Based on this analysis, provide:
1. Comprehensive performance report
2. Identified strengths and weaknesses
3. Specific actionable recommendations
4. Risk management suggestions
```

## Token Estimation

- **Input tokens**: ~3,000-6,000 (depends on wallet activity)
- **Output tokens**: ~1,500-2,500 (detailed analysis)
- **Total cost**: ~$0.30-0.50 (GPT-4 pricing)

## Token Cost Breakdown

| Component | Input Tokens | Output Tokens | Cost |
|-----------|--------------|---------------|------|
| Prompt structure | 500 | - | $0.015 |
| Trade data (small wallet) | 2,500 | - | $0.075 |
| Step-by-step analysis | - | 1,000 | $0.040 |
| Recommendations | - | 500 | $0.020 |
| **Total (small wallet)** | **3,000** | **1,500** | **$0.15** |
| **Total (large wallet)** | **6,000** | **2,500** | **$0.38** |

*Costs based on GPT-4 pricing: $0.03/1K input tokens, $0.06/1K output tokens*

## Example Usage

```javascript
const trades = await client.exportTrades(wallet);
const prompt = chainOfThoughtTemplate.replace('{{WALLET_DATA}}', JSON.stringify(trades, null, 2));

// For GPT-4 with higher token limit
const response = await openai.createChatCompletion({
  model: "gpt-4-1106-preview",
  messages: [{ role: "user", content: prompt }],
  max_tokens: 3000,
  temperature: 0.7
});
```

## Example Output

**⚠️ EXAMPLE OUTPUT - NOT FROM REAL ANALYSIS ⚠️**

Let me analyze this wallet's trading performance step by step.

### Step 1: Data Overview
- Total trades: 145
- Unique tokens traded: 23
- Date range: 2024-01-15 to 2024-12-20 (11 months)
- Buy transactions: 89 (61.4%)
- Sell transactions: 56 (38.6%)

### Step 2: Performance Metrics
- Total P&L: -$215,706.61
- Win rate: 20.5% (30 profitable / 145 total)
- Average trade size: $1,487.63
- Median trade size: $450.00
- Profit factor: 0.09 (extremely poor)

### Step 3: Token Analysis
Most profitable tokens:
- BONK: +$5,200 (12 trades)
- WIF: +$3,100 (8 trades)
- JUP: +$1,800 (5 trades)

Biggest losers:
- LUNA: -$45,000 (2 trades)
- FTT: -$32,000 (3 trades)
- STEP: -$28,500 (15 trades)

Average hold time: 3.2 days (shows short-term trading focus)

### Step 4: Pattern Recognition
- **Time patterns**: 73% of buys happen between 2-4 AM UTC (possible FOMO during Asian market pumps)
- **FOMO indicator**: 81% of buys occur after 20%+ price increase in previous 24h
- **Revenge trading**: Position sizes increase 3.5x on average after losses
- **Size patterns**: No consistent position sizing strategy detected

### Step 5: Risk Analysis
- Maximum drawdown: -$125,000 (58% of capital)
- Largest daily loss: -$45,000 (LUNA collapse)
- Position sizing: Ranges from 0.5% to 45% of portfolio (no risk management)
- Stop losses: No evidence of stop-loss usage in any trades

### Step 6: Behavioral Insights
- **Psychological patterns**: Classic FOMO buyer, enters after momentum
- **Strategy consistency**: No consistent strategy; appears purely reactive
- **Emotional indicators**: Revenge trading and martingale-like behavior
- **Learning curve**: No improvement over time; repeating same mistakes

### Recommendations
1. **Implement strict position sizing**: Never risk more than 2% per trade
2. **Use stop losses**: Set stops at -5% to -10% maximum
3. **Avoid FOMO**: Wait for pullbacks instead of chasing pumps
4. **Trade journal**: Track why you enter/exit each trade
5. **Reduce frequency**: Quality over quantity in trade selection

**⚠️ END EXAMPLE OUTPUT ⚠️** 