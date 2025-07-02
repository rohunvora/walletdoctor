# Micro-Experiment #1: Why Zero Signatures?

## 🎯 Single Question
**Why does the Helius API return no signatures for the small wallet?**

## 🔧 What We Added
Two lines in `BlockchainFetcherV3Fast._fetch_signature_page()`:
```python
logger.info(f"[CHECK] helius_url={url}")
logger.info(f"[CHECK] helius_resp_first_200B={resp_text[:200]}")
sys.stdout.flush(); sys.stderr.flush()  # Hard flush
```

## 🧪 Test Command
```bash
# One cold call only
curl -i -m 10 -H "X-Api-Key:$KEY" "$URL/v4/positions/export-gpt/$SMALL"

# Grab the evidence
railway logs --since 2m | grep "\[CHECK\] helius" > helius_check.log
```

## 📊 Expected Findings

### Case 1: Auth Issue
```
[CHECK] helius_url=https://mainnet.helius-rpc.com/?api-key=None
[CHECK] helius_resp_first_200B={"message":"Missing or invalid API key"}
```
**Fix**: HELIUS_KEY env var not set in Railway

### Case 2: Empty Result
```
[CHECK] helius_url=https://mainnet.helius-rpc.com/?api-key=xxx
[CHECK] helius_resp_first_200B={"jsonrpc":"2.0","result":[],"id":1}
```
**Fix**: Wrong cluster or wallet has no mainnet activity

### Case 3: Valid Data
```
[CHECK] helius_url=https://mainnet.helius-rpc.com/?api-key=xxx
[CHECK] helius_resp_first_200B={"jsonrpc":"2.0","result":[{"signature":"5abc...","slot":123...}],"id":1}
```
**Fix**: Parser bug after Helius call

## ⏱️ Time Budget
- Deploy: ~2 min
- Test: 30 sec
- Log check: 30 sec
- **Total**: < 5 minutes

---
*One file, one deploy, one answer* 