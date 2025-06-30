# Coach L GPT Functions Reference

All functions are called by GPT when it needs additional context. Each function stub below is copy-paste ready for the OpenAI Playground.

## 1. fetch_last_n_trades

Retrieves the user's most recent trades in chronological order.

```assistant
fetch_last_n_trades({
  "n": 10
})
```

```json
{
  "status": "success",
  "data": [
    {
      "action": "BUY",
      "token_symbol": "BONK",
      "sol_amount": 2.5,
      "token_amount": 5000000,
      "market_cap": 450000000,
      "market_cap_formatted": "$450M",
      "trade_pct_bankroll": 25.0,
      "timestamp": "2024-12-11T10:30:00Z"
    },
    {
      "action": "SELL",
      "token_symbol": "WIF",
      "sol_amount": 3.2,
      "token_amount": 80000,
      "market_cap": 2400000,
      "market_cap_formatted": "$2.4M",
      "entry_market_cap": 1200000,
      "market_cap_multiplier": 2.0,
      "realized_pnl_usd": 152.00,
      "trade_pct_bankroll": 45.7,
      "timestamp": "2024-12-11T11:15:00Z"
    }
  ]
}
```

## 2. fetch_trades_by_token

Gets all trades for a specific token symbol.

```assistant
fetch_trades_by_token({
  "token": "PEPE",
  "n": 5
})
```

```json
{
  "status": "success",
  "data": [
    {
      "action": "BUY",
      "token_symbol": "PEPE",
      "sol_amount": 1.0,
      "market_cap": 1000000,
      "market_cap_formatted": "$1M",
      "trade_pct_bankroll": 20.0,
      "timestamp": "2024-12-10T14:00:00Z"
    },
    {
      "action": "BUY",
      "token_symbol": "PEPE",
      "sol_amount": 2.0,
      "market_cap": 1500000,
      "market_cap_formatted": "$1.5M",
      "trade_pct_bankroll": 33.3,
      "timestamp": "2024-12-11T09:00:00Z"
    },
    {
      "action": "SELL",
      "token_symbol": "PEPE",
      "sol_amount": 4.5,
      "market_cap": 3000000,
      "market_cap_formatted": "$3M",
      "entry_market_cap": 1250000,
      "market_cap_multiplier": 2.4,
      "realized_pnl_usd": 180.00,
      "timestamp": "2024-12-11T16:00:00Z"
    }
  ]
}
```

## 3. fetch_trades_by_time

Retrieves trades within a specific hour range (useful for pattern detection).

```assistant
fetch_trades_by_time({
  "start_hour": 22,
  "end_hour": 6,
  "n": 20
})
```

```json
{
  "status": "success",
  "data": [
    {
      "action": "BUY",
      "token_symbol": "DEGEN",
      "sol_amount": 3.0,
      "market_cap": 500000,
      "trade_pct_bankroll": 60.0,
      "timestamp": "2024-12-11T02:30:00Z"
    },
    {
      "action": "SELL",
      "token_symbol": "DEGEN",
      "sol_amount": 1.8,
      "realized_pnl_usd": -114.00,
      "timestamp": "2024-12-11T03:15:00Z"
    }
  ],
  "summary": {
    "total_trades": 2,
    "win_rate": 0.0,
    "total_pnl_usd": -114.00,
    "avg_trade_size_pct": 45.0
  }
}
```

## 4. fetch_token_balance

Gets current token balance (essential after partial sells).

```assistant
fetch_token_balance({
  "token": "WIF"
})
```

```json
{
  "status": "success",
  "data": {
    "token_symbol": "WIF",
    "balance": 120000,
    "estimated_value_sol": 4.8,
    "estimated_value_usd": 456.00,
    "last_trade": "SELL",
    "last_trade_timestamp": "2024-12-11T11:15:00Z"
  }
}
```

## 5. fetch_wallet_stats

Overall wallet performance metrics.

```assistant
fetch_wallet_stats({})
```

```json
{
  "status": "success",
  "data": {
    "total_swaps": 147,
    "win_rate": 0.23,
    "total_pnl_usd": -1250.50,
    "total_pnl_sol": -13.16,
    "avg_trade_size_usd": 95.50,
    "avg_position_pct": 28.3,
    "wallet_age_days": 45,
    "best_performer": {
      "token": "PEPE",
      "pnl_usd": 450.00,
      "roi_pct": 180.0
    },
    "worst_performer": {
      "token": "RUG",
      "pnl_usd": -380.00,
      "roi_pct": -95.0
    }
  }
}
```

## 6. fetch_token_pnl

Detailed P&L data for a specific token.

```assistant
fetch_token_pnl({
  "token": "BONK"
})
```

```json
{
  "status": "success",
  "data": {
    "token_symbol": "BONK",
    "total_trades": 8,
    "buy_trades": 5,
    "sell_trades": 3,
    "avg_buy_price": 0.0000234,
    "avg_sell_price": 0.0000456,
    "realized_pnl_usd": 234.50,
    "unrealized_pnl_usd": 120.00,
    "total_pnl_usd": 354.50,
    "roi_percentage": 94.9,
    "win_rate": 0.667,
    "current_position": 2500000,
    "position_value_usd": 237.50
  }
}
```

## 7. fetch_market_cap_context

Market cap analysis for risk/reward assessment.

```assistant
fetch_market_cap_context({
  "token": "BRETT"
})
```

```json
{
  "status": "success",
  "data": {
    "token_symbol": "BRETT",
    "current_market_cap": 4200000,
    "current_market_cap_formatted": "$4.2M",
    "entry_market_cap": 2100000,
    "entry_market_cap_formatted": "$2.1M",
    "market_cap_multiplier": 2.0,
    "market_cap_tier": "small",
    "risk_level": "high",
    "typical_targets": {
      "2x": "$8.4M",
      "3x": "$12.6M",
      "5x": "$21M"
    },
    "historical_context": {
      "similar_tokens_5x_rate": 0.12,
      "similar_tokens_rug_rate": 0.45,
      "avg_mcap_at_rug": "$850K"
    }
  }
}
```

## Usage Notes

1. **Always check status**: Ensure `"status": "success"` before using data
2. **Handle empty results**: Some queries may return empty arrays
3. **Token symbols are case-insensitive**: "BONK" = "bonk" = "Bonk"
4. **Time ranges use 24-hour format**: 0-23 for hours
5. **All USD values use current SOL price**: Calculated at query time
6. **Market cap tiers**:
   - Micro: < $100K
   - Small: $100K - $1M
   - Mid: $1M - $10M
   - Large: > $10M

## Error Responses

```json
{
  "status": "error",
  "error": "No trades found for token FAKE",
  "data": null
}
```

## Tips for Testing

- Use `fetch_wallet_stats` first to understand overall performance
- Call `fetch_token_balance` after any partial sell scenario
- Use `fetch_trades_by_time` to detect behavioral patterns
- Always call `fetch_market_cap_context` when user asks about risk/reward
- Chain calls intelligently: stats → specific token → market context 