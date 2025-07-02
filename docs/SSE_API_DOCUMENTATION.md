# SSE Streaming API Documentation

## Overview

The WalletDoctor API v4 provides Server-Sent Events (SSE) streaming for real-time wallet analysis. This allows clients to receive trade data as it's processed rather than waiting for the complete analysis.

## Endpoints

### `GET /v4/wallet/{wallet_address}/stream`

Stream wallet trades via Server-Sent Events.

#### Parameters

- **wallet_address** (path, required): Solana wallet address to analyze

#### Headers

- **X-API-Key** (optional in dev, required in prod): API authentication key
- **Last-Event-ID** (optional): Resume from specific event ID

#### Response

- **Status**: 200 OK
- **Content-Type**: text/event-stream
- **Headers**:
  - `Cache-Control: no-cache`
  - `X-Stream-ID: <uuid>`

#### Event Stream Format

The SSE stream emits the following event types:

##### 1. Connected Event
```
event: connected
data: {"stream_id": "550e8400-e29b-41d4-a716", "wallet": "3JoVBi...", "timestamp": 1234567890}
```

##### 2. Progress Event
```
event: progress
data: {"message": "Fetched 1000 signatures", "percentage": 15.5, "step": "fetching_signatures", "trades_found": 0}
```

##### 3. Trade Event
```
event: trade
data: {"signature": "3xY7...", "timestamp": 1234567890, "token_in": "SOL", "token_out": "USDC", "amount_in": 1.5, "amount_out": 45.0, "price": 30.0, "value_usd": 45.0, "pnl_usd": null}
```

##### 4. Heartbeat Event
```
event: heartbeat
data: {"timestamp": 1234567890}
```

##### 5. Complete Event
```
event: complete
data: {"trades_found": 1234, "duration": 15.3, "summary": {"total_volume": 50000, "total_pnl_usd": 1250.5, "priced_trades": 1200}}
```

##### 6. Error Event
```
event: error
data: {"error": "Rate limit exceeded", "code": "RATE_LIMIT", "details": {"retry_after": 60}}
```

## Example Usage

### JavaScript EventSource
```javascript
const evtSource = new EventSource('/v4/wallet/3JoVBi.../stream', {
  headers: {
    'X-API-Key': 'wd_your_api_key'
  }
});

evtSource.addEventListener('trade', (event) => {
  const trade = JSON.parse(event.data);
  console.log('New trade:', trade);
});

evtSource.addEventListener('complete', (event) => {
  const summary = JSON.parse(event.data);
  console.log('Analysis complete:', summary);
  evtSource.close();
});

evtSource.addEventListener('error', (event) => {
  const error = JSON.parse(event.data);
  console.error('Stream error:', error);
  evtSource.close();
});
```

### Python aiohttp
```python
async with aiohttp.ClientSession() as session:
    async with session.get(
        'https://api.walletdoctor.com/v4/wallet/3JoVBi.../stream',
        headers={'X-API-Key': 'wd_your_api_key'}
    ) as response:
        async for line in response.content:
            if line.startswith(b'event:'):
                event_type = line.decode().split(':', 1)[1].strip()
            elif line.startswith(b'data:'):
                data = json.loads(line.decode().split(':', 1)[1])
                if event_type == 'trade':
                    process_trade(data)
                elif event_type == 'complete':
                    print(f"Complete: {data['trades_found']} trades")
                    break
```

## Performance Characteristics

- **First-byte latency**: <1 second for wallets with <10k trades
- **Chunking**: Trades are delivered in batches of ~100 for smooth rendering
- **Heartbeat**: Sent every 30 seconds to keep connection alive
- **Max duration**: Streams auto-terminate after 10 minutes

## Rate Limits

- **Requests**: 50 per minute per API key
- **Concurrent streams**: 10 per API key
- **Retry-After**: Included in 429 responses

## Error Handling

| Error Code | Description | Action |
|------------|-------------|--------|
| RATE_LIMIT | Rate limit exceeded | Wait for retry_after seconds |
| WALLET_NOT_FOUND | Invalid wallet address | Check wallet format |
| DATA_FETCH_ERROR | Blockchain API error | Retry with backoff |
| SERVICE_UNAVAILABLE | Service overloaded | Retry later |
| INTERNAL_ERROR | Unexpected error | Contact support |

## Migration from v3

To migrate from the v3 batch API to v4 streaming:

1. Change endpoint from `POST /v4/analyze` to `GET /v4/wallet/{address}/stream`
2. Replace JSON parsing with SSE event handling
3. Process trades incrementally instead of waiting for complete response
4. Add reconnection logic using Last-Event-ID header 