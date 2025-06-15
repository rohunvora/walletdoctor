# Pagination Update: Surfacing Losing Trades

## Overview
Updated the Cielo API integration to properly surface losing trades for wallets with many winning trades using pagination and timeframe filtering.

## Problem
The Cielo API returns trades sorted by PnL descending (winners first) with a hard cap of 50-100 items per page. For wallets with many winners, losing trades were hidden beyond the first page.

## Solution
Implemented pagination with smart timeframe fallback:

1. **Pagination**: Fetch multiple pages using `next_object` cursor
2. **Timeframe fallback**: If insufficient losers found, try shorter timeframes (max → 30d → 7d → 1d)
3. **Early stopping**: Stop paginating once 5 losers are found

## Implementation Details

### Key Functions (in `scripts/data.py`):
- `fetch_cielo_pnl_with_timeframe()`: Fetches PnL data with pagination for a specific timeframe
- `fetch_cielo_pnl_stream_losers()`: Automatically tries different timeframes to find losers
- `fetch_cielo_pnl_smart()`: Updated to use pagination approach

### Database Changes:
- Updated `data_window_info` table to store timeframe instead of window_days
- Added `pages_fetched` column to track pagination effort

### UI Updates:
- Shows which timeframe was used (e.g., "Showing last 30 days")
- Displays number of pages fetched
- Clear warnings when historical data is truncated

## User Experience

### Normal Wallet (<100 winners lifetime)
- Shows full history as before
- No change in experience

### Power Wallet (100+ winners but losers found within reasonable pages)
- Shows appropriate timeframe (30d or 7d)
- Message: "Showing last 30 days. Found losers after 3 pages."

### Extreme Wallet (many pages of winners)
- Falls back to shorter timeframes
- Message: "Showing last 7 days. This wallet's full history required too many pages to find losing trades."

## Performance
- Small wallets: ~200ms (single API call)
- Large wallets: ~1s per page, typically 3-5 pages max
- Fallback to shorter timeframes keeps response times reasonable

## API Usage
- 5 credits per page fetched
- Smart early stopping minimizes API usage
- Typical usage: 5-25 credits per wallet load 