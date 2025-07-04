# Trade Insights Prompts v1.0

Ready-to-use prompts for analyzing Solana wallet trading activity using the `/v4/trades/export-gpt` endpoint.

## System Prompt

```
You are a Solana trading analyst. When given trade data from the WalletDoctor API, analyze patterns and provide actionable insights. Focus on:

1. Trading frequency and volume patterns
2. Token preferences and diversification
3. DEX usage patterns
4. Time-based trading behavior
5. Buy/sell ratios and strategy indicators

Present insights in a conversational, helpful tone. Use emojis sparingly for clarity. Always end with a question to engage further analysis.

Note: The current API does not provide price or P&L data, so focus on volume and behavioral patterns only.
```

## User Prompt Templates

### Template 1: Basic Trading Overview

```
Analyze this wallet's trading activity and give me a comprehensive overview:
[PASTE API RESPONSE HERE]

Focus on:
- Trading frequency and patterns
- Most traded tokens
- Preferred DEXes
- Buy vs sell behavior
```

### Template 2: Time-Based Analysis

```
Looking at this trading data, what can you tell me about when and how often this wallet trades?
[PASTE API RESPONSE HERE]

I'm particularly interested in:
- Most active trading hours
- Daily/weekly patterns
- Any clustering of activity
- Suggestions for optimal trading times
```

### Template 3: Token Strategy Analysis  

```
Based on this trade history, what tokens does this wallet focus on and what's their strategy?
[PASTE API RESPONSE HERE]

Please analyze:
- Top tokens by trade count
- Buy/sell ratios per token
- Token rotation patterns
- Concentration vs diversification
```

## Example Analysis Output

Based on the demo wallet data:

```
## 📊 Your Trading Activity Analysis

I've analyzed your 1,107 trades and here's what stands out:

### Trading Style
You're an active trader averaging 46 trades per day with a clear buying bias (1.85 buy/sell ratio). Your total volume of 19,082 SOL shows significant market participation.

### Timing Patterns  
You're most active during:
- 7:00 UTC (82 trades) - Early European morning
- 3:00 UTC (71 trades) - Late US evening  
- 21:00 UTC (71 trades) - US afternoon

This suggests you're either trading across time zones or using automated strategies during off-peak hours.

### DEX Strategy
Your DEX usage is well-distributed:
- METEORA: 30.1% (good for stable pairs)
- SYSTEM_PROGRAM: 28.4% (direct transfers)
- PUMP_AMM: 23.8% (new token launches)

This diversification helps with slippage and access to different liquidity pools.

### Token Focus
Your top 5 tokens account for significant volume:
- CfVs3waH: Heavy accumulation (343 buys vs 12 sells)
- EPjFWdd5: More balanced (31 buys, 20 sells)
- 3dk9CNre: Moderate accumulation pattern

The strong buy bias on CfVs3waH suggests either building a position or averaging down.

Would you like me to dive deeper into any specific token's trading pattern or analyze a particular time period?
```

## Prompt Engineering Tips

1. **Without P&L Data**: Focus on volume, frequency, and patterns rather than profitability
2. **Token Names**: Use shortened token addresses when symbols aren't available
3. **Actionable Insights**: Always suggest what the patterns might mean
4. **Engagement**: End with specific questions to guide further analysis

## Size Limits

Keep responses under 2KB to ensure smooth ChatGPT interactions:
- Limit token analysis to top 5-7
- Summarize time patterns rather than listing all hours
- Focus on most significant findings

## Future Enhancement

Once TRD-002 is implemented with price/P&L data, these prompts can be extended to include:
- Win rate analysis
- Profit/loss patterns
- Risk metrics
- Position sizing recommendations 