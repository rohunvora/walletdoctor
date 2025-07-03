# Basic Trade Analysis Prompt

## Prompt Template

```
Analyze the following Solana wallet trading data and provide key insights:

{{WALLET_DATA}}

Please provide:
1. Overall performance summary (total P&L, win rate)
2. Top 5 most profitable trades
3. Top 5 biggest losses
4. Most frequently traded tokens
5. Trading patterns or notable behaviors

Format your response with clear sections and bullet points.
```

## Token Estimation

- **Input tokens**: ~2,000-5,000 (depends on wallet activity)
- **Output tokens**: ~500-800
- **Total cost**: ~$0.10-0.20 (GPT-4 pricing)

## Example Usage

```javascript
const trades = await client.exportTrades('34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya');
const prompt = basicAnalysisTemplate.replace('{{WALLET_DATA}}', JSON.stringify(trades, null, 2));
```

## Example Output

**⚠️ EXAMPLE OUTPUT - NOT FROM REAL ANALYSIS ⚠️**

### Overall Performance Summary
- **Total P&L**: -$215,706.61
- **Win Rate**: 20.5%
- **Total Trades**: 145
- **Average Trade Size**: $1,250

### Top 5 Most Profitable Trades
1. BONK - Profit: $12,500 (sold at 0.0000315)
2. WIF - Profit: $8,200 (sold at peak)
3. JUP - Profit: $5,100 (early exit)
4. MYRO - Profit: $3,800 (2x return)
5. SAMO - Profit: $2,100 (quick flip)

### Top 5 Biggest Losses
1. LUNA - Loss: -$45,000 (held too long)
2. FTT - Loss: -$32,000 (caught in collapse)
3. BONK - Loss: -$18,500 (bought at top)
4. STEP - Loss: -$12,000 (no stop loss)
5. ORCA - Loss: -$8,900 (market downturn)

### Most Frequently Traded Tokens
- BONK: 45 trades
- SOL: 38 trades
- USDC: 25 trades
- WIF: 18 trades
- JUP: 12 trades

### Trading Patterns
- **FOMO Trading**: Tends to buy during price spikes
- **No Stop Losses**: Holds losing positions too long
- **Memecoin Focus**: 60% of trades in meme tokens
- **Small Wins, Big Losses**: Takes profits early but lets losses run

**⚠️ END EXAMPLE OUTPUT ⚠️** 