# Test Contexts for Prompt Development

Use these realistic contexts to test your prompt changes in OpenAI's interface.

## 1. Fresh Buy Trade (Like REFLECT)
```json
{
  "wallet_address": "34zY...VCya",
  "current_event": {
    "type": "trade",
    "data": {
      "action": "BUY",
      "token_symbol": "REFLECT",
      "sol_amount": 0.524044,
      "token_amount": 715776.12,
      "bankroll_before_sol": 5.75,
      "bankroll_after_sol": 5.226,
      "trade_pct_bankroll": 9.11,
      "dex": "pump.fun",
      "timestamp": "2024-01-15T17:44:00"
    }
  },
  "recent_chat": []
}
```

## 2. Partial Sell (50% Exit)
```json
{
  "wallet_address": "34zY...VCya",
  "current_event": {
    "type": "trade",
    "data": {
      "action": "SELL",
      "token_symbol": "REFLECT",
      "sol_amount": 0.452708,
      "token_amount": 357888.06,
      "bankroll_before_sol": 5.226,
      "bankroll_after_sol": 5.679,
      "trade_pct_bankroll": 8.66,
      "dex": "pump.fun",
      "timestamp": "2024-01-15T17:45:00"
    }
  },
  "recent_chat": [
    {"role": "assistant", "content": "You just bought 715,776.12 REFLECT using 0.524 SOL, which is 9.11% of your bankroll. Watch liquidity on Pump.fun.", "timestamp": "2024-01-15T17:44:30"}
  ]
}
```

## 3. User Asking About Performance
```json
{
  "wallet_address": "34zY...VCya",
  "current_event": {
    "type": "message",
    "data": {"text": "how were my last 5 trades?"},
    "timestamp": "2024-01-15T17:42:00"
  },
  "bankroll_before_sol": 5.75,
  "recent_chat": []
}
```

## 4. Late Night Degen Trade
```json
{
  "wallet_address": "34zY...VCya",
  "current_event": {
    "type": "trade",
    "data": {
      "action": "BUY",
      "token_symbol": "BONK",
      "sol_amount": 2.5,
      "token_amount": 125000000,
      "bankroll_before_sol": 10.2,
      "bankroll_after_sol": 7.7,
      "trade_pct_bankroll": 24.5,
      "dex": "raydium",
      "timestamp": "2024-01-15T03:30:00"
    }
  },
  "recent_chat": [
    {"role": "user", "content": "can't sleep", "timestamp": "2024-01-15T03:28:00"},
    {"role": "assistant", "content": "3am trading rarely ends well. What's keeping you up?", "timestamp": "2024-01-15T03:28:30"}
  ]
}
```

## 5. Big Loss Exit
```json
{
  "wallet_address": "34zY...VCya",
  "current_event": {
    "type": "trade",
    "data": {
      "action": "SELL",
      "token_symbol": "WIF",
      "sol_amount": 0.85,
      "token_amount": 500000,
      "bankroll_before_sol": 4.2,
      "bankroll_after_sol": 5.05,
      "trade_pct_bankroll": 20.24,
      "dex": "pump.fun",
      "timestamp": "2024-01-15T14:22:00"
    }
  },
  "recent_chat": [
    {"role": "user", "content": "fuck this", "timestamp": "2024-01-15T14:21:00"}
  ]
}
```

## 6. Casual Greeting
```json
{
  "wallet_address": "34zY...VCya",
  "current_event": {
    "type": "message",
    "data": {"text": "hey"},
    "timestamp": "2024-01-15T19:15:00"
  },
  "bankroll_before_sol": 6.2056,
  "recent_chat": [
    {"role": "user", "content": "hey", "timestamp": "2024-01-15T15:30:00"},
    {"role": "assistant", "content": "Still sitting on that REFLECT position. Market's moving - you watching or sleeping?", "timestamp": "2024-01-15T15:30:30"}
  ]
}
```

## 7. After Multiple Losses
```json
{
  "wallet_address": "34zY...VCya",
  "current_event": {
    "type": "message",
    "data": {"text": "why do I keep losing money?"},
    "timestamp": "2024-01-15T20:00:00"
  },
  "bankroll_before_sol": 3.2,
  "recent_chat": [
    {"role": "assistant", "content": "Down 40% on that WIF trade. Cut losses or riding to zero?", "timestamp": "2024-01-15T19:55:00"}
  ]
}
```

## 8. Repeated Token Pattern
```json
{
  "wallet_address": "34zY...VCya",
  "current_event": {
    "type": "trade",
    "data": {
      "action": "BUY",
      "token_symbol": "PEPE",
      "sol_amount": 0.3,
      "token_amount": 850000000,
      "bankroll_before_sol": 5.679,
      "bankroll_after_sol": 5.379,
      "trade_pct_bankroll": 5.28,
      "dex": "raydium",
      "timestamp": "2024-01-15T19:00:00"
    }
  },
  "recent_chat": [
    {"role": "user", "content": "PEPE looking good again", "timestamp": "2024-01-15T18:59:00"}
  ]
}
```

## 9. Small/Dust Trade
```json
{
  "wallet_address": "34zY...VCya",
  "current_event": {
    "type": "trade",
    "data": {
      "action": "BUY",
      "token_symbol": "MYRO",
      "sol_amount": 0.05,
      "token_amount": 2500,
      "bankroll_before_sol": 3.2,
      "bankroll_after_sol": 3.15,
      "trade_pct_bankroll": 1.56,
      "dex": "pump.fun",
      "timestamp": "2024-01-15T21:00:00"
    }
  },
  "recent_chat": []
}
```

## Function Tool Definitions for OpenAI Interface

### fetch_last_n_trades
```json
{
  "name": "fetch_last_n_trades",
  "description": "Get user's recent trades",
  "strict": false,
  "parameters": {
    "type": "object",
    "properties": {
      "n": {
        "type": "integer",
        "description": "Number of trades to fetch"
      }
    },
    "additionalProperties": false,
    "required": ["n"]
  }
}
```

### fetch_trades_by_token
```json
{
  "name": "fetch_trades_by_token",
  "description": "Get trades for specific token",
  "strict": false,
  "parameters": {
    "type": "object",
    "properties": {
      "token": {
        "type": "string",
        "description": "Token symbol"
      },
      "n": {
        "type": "integer",
        "description": "Number of trades"
      }
    },
    "additionalProperties": false,
    "required": ["token"]
  }
}
```

### fetch_trades_by_time
```json
{
  "name": "fetch_trades_by_time",
  "description": "Get trades within hour range (e.g., 2-6 for late night)",
  "strict": false,
  "parameters": {
    "type": "object",
    "properties": {
      "start_hour": {
        "type": "integer",
        "description": "Start hour (0-23)"
      },
      "end_hour": {
        "type": "integer",
        "description": "End hour (0-23)"
      },
      "n": {
        "type": "integer",
        "description": "Number of trades"
      }
    },
    "additionalProperties": false,
    "required": ["start_hour", "end_hour"]
  }
}
```

### fetch_token_balance
```json
{
  "name": "fetch_token_balance",
  "description": "Get current balance for a token",
  "strict": false,
  "parameters": {
    "type": "object",
    "properties": {
      "token": {
        "type": "string",
        "description": "Token symbol"
      }
    },
    "additionalProperties": false,
    "required": ["token"]
  }
}
``` 