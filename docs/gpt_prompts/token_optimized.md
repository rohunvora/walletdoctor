# Token-Optimized Trade Analysis Prompt

## Prompt Template

```
Analyze trades. Focus: P&L, patterns, mistakes.

Data:
{{WALLET_DATA}}

Output format:
1. Stats: total P&L, win%, avg size
2. Best/worst 3 trades
3. Top 3 patterns
4. Fix: 3 actions

Be concise.
```

## Token Estimation

- **Input tokens**: ~1,500-3,500 (minimal prompt + data)
- **Output tokens**: ~200-300 (concise format)
- **Total cost**: ~$0.05-0.12 (GPT-4 pricing)

## Cost Comparison

| Template Type | Input Tokens | Output Tokens | Total Cost |
|--------------|--------------|---------------|------------|
| Basic Analysis | 3,000 | 650 | $0.13 |
| Chain-of-Thought | 4,500 | 2,000 | $0.26 |
| **Token-Optimized** | **2,000** | **250** | **$0.08** |

*Savings: 69% cheaper than chain-of-thought, 38% cheaper than basic*

## Compression Techniques

1. **Prompt Compression**:
   - Remove filler words
   - Use abbreviations
   - Implicit instructions

2. **Data Compression**:
   ```javascript
   // Reduce JSON size by removing whitespace
   const compactData = JSON.stringify(trades);
   
   // Or send only essential fields
   const essentialData = {
     trades: trades.trades.map(t => ({
       a: t.action,
       t: t.token,
       p: t.pnl_usd,
       v: t.value_usd,
       ts: t.timestamp
     }))
   };
   ```

3. **Output Control**:
   - Specify "Be concise"
   - Use structured format
   - Limit examples

## Example Usage

```javascript
// Minimal data approach
const minimalTrades = {
  wallet: trades.wallet,
  summary: {
    total_trades: trades.trades.length,
    total_pnl: trades.trades.reduce((sum, t) => sum + t.pnl_usd, 0)
  },
  trades: trades.trades.map(t => ({
    action: t.action,
    token: t.token,
    pnl_usd: t.pnl_usd,
    value_usd: t.value_usd
  }))
};

const prompt = tokenOptimizedTemplate.replace('{{WALLET_DATA}}', JSON.stringify(minimalTrades));
```

## Example Output

**⚠️ EXAMPLE OUTPUT - NOT FROM REAL ANALYSIS ⚠️**

**Stats:**
- P&L: -$215,706
- Win: 20.5% (30/145)
- Avg: $1,487

**Best 3:**
1. BONK +$12,500
2. WIF +$8,200
3. JUP +$5,100

**Worst 3:**
1. LUNA -$45,000
2. FTT -$32,000
3. BONK -$18,500

**Patterns:**
1. FOMO buying (81% after pumps)
2. No stops (0% use)
3. Revenge sizing (3.5x after loss)

**Fix:**
1. Max 2% per trade
2. Set -10% stops always
3. Wait for -20% dips

**⚠️ END EXAMPLE OUTPUT ⚠️**

## When to Use

- ✅ High-volume analysis (many wallets)
- ✅ Real-time monitoring
- ✅ Cost-sensitive applications
- ✅ Quick screening before deep analysis
- ❌ Detailed behavioral insights needed
- ❌ Educational/explanatory content
- ❌ Complex pattern recognition 