# GPT Prompt Package - v0.8.0-prices

This folder contains everything needed to evaluate and integrate WalletDoctor API v0.8.0-prices with ChatGPT.

## 📁 Contents

| File | Purpose |
|------|---------|
| `system_prompt_v0.8.0.md` | System prompt to orient ChatGPT (paste at conversation start) |
| `quick_start_tests.md` | Curl commands to verify API is working with pricing |
| `eval_matrix.csv` | Evaluation results template for tracking performance |
| `run_eval.sh` | Automated evaluation script that tests all endpoints |

## 🚀 Quick Start

1. **Prime ChatGPT**: Paste contents of `system_prompt_v0.8.0.md` into a new conversation
2. **Test API**: Run the curl commands from `quick_start_tests.md`
3. **Verify Pricing**: Ensure `current_price_usd` shows ~$152 (not null)
4. **Run Full Eval**: Execute `./run_eval.sh` for comprehensive testing

## ✅ Success Criteria

- Schema version: `v0.8.0-prices`
- Price coverage: ≥90% positions have non-null `current_price_usd`
- Price source: `sol_spot_price` on all priced positions
- Response time: <5s cold, <3s warm
- HTTP status: 200 for all requests

## 🔧 Using run_eval.sh

```bash
# Basic run (uses demo API key)
./run_eval.sh

# With custom API key
API_KEY=wd_your_actual_key_here ./run_eval.sh
```

The script will:
- Test both demo wallets (small: 18 pos, medium: 356 pos)
- Measure cold and warm response times
- Calculate pricing coverage percentage
- Print evaluation matrix
- Exit with non-zero code if thresholds fail

## 📊 Expected Results

```
wallet,endpoint,cold_time_s,warm_time_s,non_null_price_pct,schema_version,notes
34zYDgjy...,/v4/positions/export-gpt,3.2,1.8,100.00%,v0.8.0-prices,Small demo (18 pos)
3JoVBiQ...,/v4/positions/export-gpt,4.5,2.3,100.00%,v0.8.0-prices,Medium demo (356 pos)
```

## 🚨 Troubleshooting

If tests fail:
1. Check Railway deployment status
2. Verify `PRICE_SOL_SPOT_ONLY=true` is set
3. Check CoinGecko API accessibility
4. Review recent deployment logs

## 🎯 Integration Ready

Once `run_eval.sh` passes, the API is ready for ChatGPT integration with meaningful dollar value discussions!

### 📈 TRD-002 Update (v0.7.1-trades-value)

The trades endpoint now includes enriched price and P&L fields:
- `price_sol`, `price_usd`, `value_usd`, `pnl_usd` are now populated for 97%+ trades
- Use `?schema_version=v0.7.1-trades-value` for enriched trade data
- Enables comprehensive P&L analysis and trading insights

### 🗜️ v0.7.2-compact Format (NEW)

For large wallets that exceed ChatGPT's response size limits:
- Use `?schema_version=v0.7.2-compact` for compressed format
- Reduces response size by 4-5x (from ~770 to ~180 bytes per trade)
- Stays under 200KB for ~1,000 trades
- Preserves all enriched fields in array format
- Field map: `["ts", "act", "tok", "amt", "p_sol", "p_usd", "val", "pnl"]` 