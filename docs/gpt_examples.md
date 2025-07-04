# WalletDoctor GPT Integration Examples

Complete examples for integrating WalletDoctor API with ChatGPT and other AI systems.

## 📊 Trading Activity Analysis

**API Version**: v0.7.0 (stable trades endpoint)  
**Wallet**: `34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya`  
**Features**: Trade history with volume analysis (P&L pending TRD-002)

### Basic Trades Request

```bash
curl -X GET "https://web-production-2bb2f.up.railway.app/v4/trades/export-gpt/34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya" \
  -H "X-Api-Key: wd_test1234567890abcdef1234567890ab" \
  -H "Accept: application/json"
```

### Response Format (v0.7.0)

```json
{
  "wallet": "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
  "signatures": [
    "5s53x9ETa3YhzV6NTVGC3ezHWKqASdakKq3UXdLXKbWRWrFqXZeCvwfoGaEPc3Zr1dsQddyz9aWdpnbVhGRxCqwX",
    "4NyzTh42S1bGswq8BNHvsm3PxM9NBYcmYgqk1n89HjiiKWHz2sT9Ut4rmuNHjeErTBAwoQV8aYP4oM54"
  ],
  "trades": [
    {
      "action": "buy",
      "amount": 101109.031893,
      "dex": "JUPITER",
      "fees_usd": 0.0,
      "pnl_usd": 0.0,
      "price": null,
      "priced": false,
      "signature": "5s53x9ETa3YhzV6NTVGC3ezHWKqASdakKq3UXdLXKbWRWrFqXZeCvwfoGaEPc3Zr1dsQddyz9aWdpnbVhGRxCqwX",
      "timestamp": "2025-06-09T18:37:09",
      "token": "vRseBFqT",
      "token_in": {
        "amount": 249.75,
        "mint": "So11111111111111111111111111111111111111112",
        "symbol": "So111111"
      },
      "token_out": {
        "amount": 101109.031893,
        "mint": "vRseBFqTy9QLmmo5qGiwo74AVpdqqMTnxPqWoWMpump",
        "symbol": "vRseBFqT"
      },
      "tx_type": "swap",
      "value_usd": null
    }
  ]
}
```

### What's Available Now vs Coming Soon

✅ **Available Now (v0.7.0)**:
- Complete trade history with signatures
- Token swap details (token_in/token_out)
- DEX identification
- Timestamps for time analysis
- Buy/sell action classification

⏳ **Coming Soon (TRD-002)**:
- `price`: Token price at trade time
- `value_usd`: Notional value in USD
- `pnl_usd`: Realized P&L per trade
- `fees_usd`: Actual transaction fees

## 💡 Trading Insights Examples

### 1. Volume Analysis (Available Now)

```python
import requests
from collections import defaultdict
from datetime import datetime

def analyze_trading_volume(wallet: str) -> dict:
    """Analyze SOL volume from trades"""
    url = f"https://web-production-2bb2f.up.railway.app/v4/trades/export-gpt/{wallet}"
    headers = {"X-Api-Key": "wd_test1234567890abcdef1234567890ab"}
    
    resp = requests.get(url, headers=headers)
    data = resp.json()
    
    sol_volume = 0
    token_volumes = defaultdict(float)
    
    for trade in data["trades"]:
        # Calculate SOL volume
        if trade["token_in"]["symbol"] == "So111111":
            sol_spent = trade["token_in"]["amount"]
            sol_volume += sol_spent
            token_volumes[trade["token"]] += sol_spent
        elif trade["token_out"]["symbol"] == "So111111":
            sol_received = trade["token_out"]["amount"]
            sol_volume += sol_received
            token_volumes[trade["token"]] += sol_received
    
    return {
        "total_sol_volume": sol_volume,
        "trades_count": len(data["trades"]),
        "top_tokens_by_volume": sorted(
            token_volumes.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
    }

# Example usage
result = analyze_trading_volume("34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya")
print(f"Total SOL Volume: {result['total_sol_volume']:,.2f}")
print(f"Total Trades: {result['trades_count']:,}")
```

### 2. Trading Pattern Analysis

```python
def analyze_trading_patterns(wallet: str) -> dict:
    """Analyze trading behavior patterns"""
    url = f"https://web-production-2bb2f.up.railway.app/v4/trades/export-gpt/{wallet}"
    headers = {"X-Api-Key": "wd_test1234567890abcdef1234567890ab"}
    
    resp = requests.get(url, headers=headers)
    trades = resp.json()["trades"]
    
    # Buy/Sell ratio
    buys = sum(1 for t in trades if t["action"] == "buy")
    sells = sum(1 for t in trades if t["action"] == "sell")
    
    # Hour analysis
    hour_counts = defaultdict(int)
    for trade in trades:
        hour = datetime.fromisoformat(trade["timestamp"]).hour
        hour_counts[hour] += 1
    
    # DEX usage
    dex_counts = defaultdict(int)
    for trade in trades:
        dex_counts[trade["dex"]] += 1
    
    return {
        "buy_sell_ratio": buys / sells if sells > 0 else buys,
        "most_active_hours": sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3],
        "preferred_dexes": sorted(dex_counts.items(), key=lambda x: x[1], reverse=True)[:3],
        "total_buys": buys,
        "total_sells": sells
    }
```

### 3. TypeScript Integration

```typescript
interface Trade {
  action: "buy" | "sell";
  amount: number;
  token: string;
  timestamp: string;
  dex: string;
  token_in: {
    amount: number;
    mint: string;
    symbol: string;
  };
  token_out: {
    amount: number;
    mint: string;
    symbol: string;
  };
}

interface TradeInsights {
  tradingFrequency: number;
  buyBias: number;
  topTokens: Array<{token: string; count: number}>;
  activeHours: Array<{hour: number; count: number}>;
}

class WalletDoctorClient {
  constructor(
    private apiKey: string,
    private baseUrl: string = "https://web-production-2bb2f.up.railway.app"
  ) {}

  async getTrades(wallet: string): Promise<{trades: Trade[]}> {
    const response = await fetch(`${this.baseUrl}/v4/trades/export-gpt/${wallet}`, {
      headers: {
        "X-Api-Key": this.apiKey,
        "Accept": "application/json"
      }
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return response.json();
  }

  analyzeTrading(trades: Trade[]): TradeInsights {
    const buys = trades.filter(t => t.action === "buy").length;
    const sells = trades.filter(t => t.action === "sell").length;
    
    // Token frequency
    const tokenCounts = trades.reduce((acc, trade) => {
      acc[trade.token] = (acc[trade.token] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    
    // Hour analysis
    const hourCounts = trades.reduce((acc, trade) => {
      const hour = new Date(trade.timestamp).getUTCHours();
      acc[hour] = (acc[hour] || 0) + 1;
      return acc;
    }, {} as Record<number, number>);
    
    return {
      tradingFrequency: trades.length,
      buyBias: buys / (buys + sells),
      topTokens: Object.entries(tokenCounts)
        .sort(([,a], [,b]) => b - a)
        .slice(0, 5)
        .map(([token, count]) => ({token, count})),
      activeHours: Object.entries(hourCounts)
        .sort(([,a], [,b]) => b - a)
        .slice(0, 3)
        .map(([hour, count]) => ({hour: Number(hour), count}))
    };
  }
}

// Example usage
const client = new WalletDoctorClient("wd_test1234567890abcdef1234567890ab");
const {trades} = await client.getTrades("34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya");
const insights = client.analyzeTrading(trades);

console.log(`Trading frequency: ${insights.tradingFrequency} trades`);
console.log(`Buy bias: ${(insights.buyBias * 100).toFixed(1)}%`);
```

## 🎯 ChatGPT Action Configuration

### OpenAPI Schema Import

```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "WalletDoctor Trades API",
    "version": "0.7.0"
  },
  "servers": [
    {
      "url": "https://web-production-2bb2f.up.railway.app"
    }
  ],
  "paths": {
    "/v4/trades/export-gpt/{wallet}": {
      "get": {
        "operationId": "getWalletTrades",
        "summary": "Get wallet trades for analysis",
        "parameters": [
          {
            "name": "wallet",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string"
            }
          }
        ],
        "security": [
          {
            "ApiKeyAuth": []
          }
        ]
      }
    }
  },
  "components": {
    "securitySchemes": {
      "ApiKeyAuth": {
        "type": "apiKey",
        "in": "header",
        "name": "X-Api-Key"
      }
    }
  }
}
```

### Test with Demo Data

```bash
# Quick volume check
curl -H "X-Api-Key: wd_test1234567890abcdef1234567890ab" \
  "https://web-production-2bb2f.up.railway.app/v4/trades/export-gpt/34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya" \
  | jq '{
    total_trades: .trades | length,
    buys: [.trades[] | select(.action == "buy")] | length,
    sells: [.trades[] | select(.action == "sell")] | length,
    first_trade_date: .trades[-1].timestamp,
    last_trade_date: .trades[0].timestamp
  }'
```

**Expected Output**:
```json
{
  "total_trades": 1107,
  "buys": 718,
  "sells": 389,
  "first_trade_date": "2025-05-16T07:11:45",
  "last_trade_date": "2025-06-09T20:17:55"
}
```

### Demo Wallets for Testing

| Size | Wallet Address | Trades | Use Case |
|------|---------------|--------|----------|
| Small | `34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya` | ~1,100 | Quick testing, examples |
| Medium | `AAXTYrQR6CHDGhJYz4uSgJ6dq7JTySTR6WyAq8QKZnF8` | ~2,300 | Performance testing |

## 🚀 Production Status

✅ **Trades Endpoint Ready**
- Stable v0.7.0 format
- Fast response times (<2s)
- Reliable trade history
- No accuracy issues

⏳ **Positions Endpoint (Beta)**
- Known accuracy issues (POS-003)
- Currently disabled in production
- Use trades endpoint instead

🔧 **Coming Soon (TRD-002)**
- Price enrichment for all trades
- P&L calculations
- Enhanced fee tracking

**Result**: ChatGPT can now provide sophisticated trading behavior analysis with the stable trades endpoint! 🎉 