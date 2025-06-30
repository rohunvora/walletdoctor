# Price History & Peak Tracking Implementation

## Overview

This document describes the price history and peak tracking system implemented in the Pocket Trading Coach bot. The system provides real-time price monitoring, historical context, and peak alerts to help traders make better decisions.

## Architecture

### Database Schema

#### price_snapshots table
Stores time-series price data for all monitored tokens:
```sql
CREATE TABLE price_snapshots (
    token_address TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    price_sol REAL,
    price_usd REAL,
    market_cap REAL,
    volume_24h REAL,
    liquidity_usd REAL,
    PRIMARY KEY (token_address, timestamp)
)
```

#### user_positions table
Tracks user positions with peak information:
```sql
CREATE TABLE user_positions (
    user_id BIGINT NOT NULL,
    wallet_address TEXT NOT NULL,
    token_address TEXT NOT NULL,
    token_symbol TEXT NOT NULL,
    -- Position details
    token_balance REAL DEFAULT 0,
    avg_entry_price_sol REAL,
    avg_entry_price_usd REAL,
    avg_entry_market_cap REAL,
    total_invested_sol REAL DEFAULT 0,
    total_invested_usd REAL DEFAULT 0,
    -- Peak tracking
    peak_price_sol REAL,
    peak_price_usd REAL,
    peak_market_cap REAL,
    peak_timestamp TIMESTAMP,
    peak_multiplier_from_entry REAL,
    -- Metadata
    first_buy_timestamp TIMESTAMP,
    last_buy_timestamp TIMESTAMP,
    last_update_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (user_id, token_address)
)
```

### Core Components

#### PriceHistoryService (price_history_service.py)
- Fetches price data from Birdeye API with DexScreener fallback
- Stores snapshots in database with mutex for thread safety
- Provides methods for querying historical prices
- Implements 1-minute cache to reduce API calls

Key methods:
- `fetch_and_store_price_data()` - Main entry point
- `get_sol_price()` - Get current SOL price for conversions
- `fetch_historical_prices()` - Query price history
- `get_price_at_timestamp()` - Find price at specific time

#### Continuous Monitoring
The bot automatically:
1. Starts monitoring when users buy tokens
2. Fetches prices every minute
3. Updates peak prices when new highs are reached
4. Sends alerts at milestone multipliers (3x, 5x, 10x, etc.)
5. Persists monitoring across bot restarts

#### AI Context Integration
Price data is integrated into the AI coaching system:
- Trade prompts include real-time price context
- AI has access to `fetch_price_context` tool
- Coach can comment on FOMO, peaks, and drawdowns

## API Integration

### Birdeye API
Primary data source with three endpoints:
1. `/defi/price` - Current price
2. `/defi/v3/token/market-data` - Market data (mcap, volume)
3. `/defi/token_overview` - Token overview

### DexScreener Fallback
Used when Birdeye fails (common for new tokens):
- Endpoint: `/latest/dex/tokens/{address}`
- Provides price, market cap, volume, liquidity

## Performance Considerations

- **Caching**: 1-minute TTL for API responses
- **Database**: DuckDB with mutex for concurrent writes
- **Monitoring**: Async tasks for each monitored token
- **Rate Limiting**: Respects API limits with delays

## Usage Examples

### Manual Token Tracking
```
/watch DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263
```

### Peak Alerts
When a position reaches milestones:
```
🚀 BONK hit 3x from your entry!
Consider taking some profits to lock in gains.
```

### AI Coaching with Price Context
```
User: [Buys token]
Bot: Chasing a 50% pump? That's FOMO territory.
```

## Configuration

### Environment Variables
- `BIRDEYE_API_KEY` - Required for Birdeye API
- No additional config needed for DexScreener

### Database Initialization
Tables are created automatically by `init_db()` in telegram_bot_coach.py

## Future Enhancements

1. **Data Retention** - Implement 30-day cleanup policy
2. **Advanced Alerts** - Round-trip detection, volume alerts
3. **Chart Generation** - Visual price charts in Telegram
4. **Multi-chain Support** - Extend beyond Solana 