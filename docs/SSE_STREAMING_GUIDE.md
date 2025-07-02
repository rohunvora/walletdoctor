# SSE Streaming API Guide

## Overview

The WalletDoctor SSE (Server-Sent Events) streaming API provides real-time progress updates and streaming trade data for wallet analytics. This allows clients to receive immediate feedback and process results as they become available, rather than waiting for the entire analysis to complete.

## Benefits

- **Instant Feedback**: First results delivered in ~100ms
- **Progressive Loading**: Display trades as they stream in
- **Memory Efficient**: No need to buffer entire response
- **Progress Tracking**: Real-time progress updates
- **Resilient**: Automatic reconnection support

## API Endpoint

```
GET /v4/wallet/{wallet_address}/stream
```

### Headers
- `Accept: text/event-stream` (optional, but recommended)
- `Last-Event-ID: {id}` (for reconnection)

### Query Parameters
- `skip_pricing=true` - Skip price fetching for faster results (optional)

## Event Types

The SSE stream emits several event types:

### 1. Connected Event
Emitted when the stream connection is established.

```
event: connected
id: 1
data: {
  "status": "connected",
  "wallet": "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
  "timestamp": 1234567890
}
```

### 2. Progress Event
Provides progress updates throughout the analysis.

```
event: progress
id: 2
data: {
  "message": "Fetching signatures...",
  "percentage": 25.5,
  "step": "fetching_signatures",
  "timestamp": 1234567891,
  "signatures_count": 1250
}
```

Progress steps and their weights:
- `initializing` - Setup and validation
- `fetching_signatures` (15%) - Retrieving transaction signatures
- `fetching_transactions` (35%) - Fetching full transaction data
- `processing_trades` (35%) - Parsing and extracting trades
- `calculating_analytics` (15%) - Computing final analytics

### 3. Trades Event
Streams batches of parsed trades.

```
event: trades
id: 3
data: {
  "trades": [
    {
      "signature": "5KQZ...",
      "timestamp": 1234567890,
      "type": "buy",
      "token_in_symbol": "SOL",
      "token_in_amount": 1.5,
      "token_out_symbol": "USDC",
      "token_out_amount": 150.0,
      "value_usd": 150.0,
      "price_usd": 100.0
    }
  ],
  "batch_num": 1,
  "total_yielded": 100,
  "has_more": true,
  "timestamp": 1234567892
}
```

### 4. Complete Event
Signals the end of streaming with summary statistics.

```
event: complete
id: 4
data: {
  "status": "complete",
  "summary": {
    "wallet": "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2",
    "total_trades": 5478,
    "unique_tokens": 42,
    "total_volume": 125430.50,
    "total_pnl_usd": 15234.67,
    "win_rate": 65.5,
    "priced_trades": 5400
  },
  "metrics": {
    "api_calls": 120,
    "cache_hits": 80,
    "fetch_time": 12.5,
    "total_time": 15.8
  },
  "elapsed_seconds": 15.8,
  "timestamp": 1234567905
}
```

### 5. Error Event
Emitted when an error occurs.

```
event: error
id: 5
data: {
  "error": "Rate limit exceeded",
  "code": "RATE_LIMIT",
  "details": {
    "retry_after": 60
  },
  "timestamp": 1234567893
}
```

## Client Examples

### cURL
```bash
curl -N -H "Accept: text/event-stream" \
  "https://api.walletdoctor.com/v4/wallet/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2/stream"
```

### JavaScript (Browser)
```javascript
const eventSource = new EventSource(
  'https://api.walletdoctor.com/v4/wallet/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2/stream'
);

// Handle different event types
eventSource.addEventListener('connected', (event) => {
  const data = JSON.parse(event.data);
  console.log('Connected to wallet:', data.wallet);
});

eventSource.addEventListener('progress', (event) => {
  const data = JSON.parse(event.data);
  updateProgressBar(data.percentage);
  updateStatusMessage(data.message);
});

eventSource.addEventListener('trades', (event) => {
  const data = JSON.parse(event.data);
  appendTradesToTable(data.trades);
  console.log(`Received batch ${data.batch_num}: ${data.trades.length} trades`);
});

eventSource.addEventListener('complete', (event) => {
  const data = JSON.parse(event.data);
  displaySummary(data.summary);
  eventSource.close();
});

eventSource.addEventListener('error', (event) => {
  const data = JSON.parse(event.data);
  console.error('Stream error:', data.error);
  eventSource.close();
});

// Handle connection errors
eventSource.onerror = (error) => {
  console.error('EventSource failed:', error);
  eventSource.close();
};
```

### JavaScript (Node.js)
```javascript
const EventSource = require('eventsource');

const url = 'https://api.walletdoctor.com/v4/wallet/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2/stream';
const eventSource = new EventSource(url);

let trades = [];
let lastEventId = null;

eventSource.on('connected', (event) => {
  const data = JSON.parse(event.data);
  console.log(`Connected to wallet: ${data.wallet}`);
});

eventSource.on('progress', (event) => {
  const data = JSON.parse(event.data);
  process.stdout.write(`\r${data.message} (${data.percentage.toFixed(1)}%)`);
  lastEventId = event.lastEventId;
});

eventSource.on('trades', (event) => {
  const data = JSON.parse(event.data);
  trades.push(...data.trades);
  lastEventId = event.lastEventId;
});

eventSource.on('complete', (event) => {
  const data = JSON.parse(event.data);
  console.log('\n\nAnalysis complete!');
  console.log(`Total trades: ${data.summary.total_trades}`);
  console.log(`Total P&L: $${data.summary.total_pnl_usd.toFixed(2)}`);
  eventSource.close();
});

eventSource.on('error', (event) => {
  if (event.type === 'error') {
    console.error('Connection error, retrying...');
    // EventSource will automatically reconnect
  } else {
    const data = JSON.parse(event.data);
    console.error('Stream error:', data.error);
    eventSource.close();
  }
});
```

### Python
```python
import json
import sseclient
import requests

def stream_wallet_analysis(wallet_address):
    url = f"https://api.walletdoctor.com/v4/wallet/{wallet_address}/stream"
    headers = {'Accept': 'text/event-stream'}
    
    response = requests.get(url, headers=headers, stream=True)
    client = sseclient.SSEClient(response)
    
    trades = []
    
    for event in client.events():
        data = json.loads(event.data)
        
        if event.event == 'connected':
            print(f"Connected to wallet: {data['wallet']}")
        
        elif event.event == 'progress':
            print(f"\r{data['message']} ({data['percentage']:.1f}%)", end='', flush=True)
        
        elif event.event == 'trades':
            trades.extend(data['trades'])
            print(f"\nReceived batch {data['batch_num']}: {len(data['trades'])} trades")
        
        elif event.event == 'complete':
            print("\n\nAnalysis complete!")
            print(f"Total trades: {data['summary']['total_trades']}")
            print(f"Total P&L: ${data['summary']['total_pnl_usd']:.2f}")
            break
        
        elif event.event == 'error':
            print(f"\nError: {data['error']}")
            break
    
    return trades

# Usage
if __name__ == "__main__":
    wallet = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
    trades = stream_wallet_analysis(wallet)
```

### Python (Async)
```python
import aiohttp
import asyncio
import json
from aiohttp_sse_client import client as sse_client

async def stream_wallet_analysis(wallet_address):
    url = f"https://api.walletdoctor.com/v4/wallet/{wallet_address}/stream"
    
    async with aiohttp.ClientSession() as session:
        async with sse_client.EventSource(url) as event_source:
            trades = []
            
            async for event in event_source:
                if event.type == 'message':
                    continue
                    
                data = json.loads(event.data)
                
                if event.type == 'connected':
                    print(f"Connected to wallet: {data['wallet']}")
                
                elif event.type == 'progress':
                    print(f"\r{data['message']} ({data['percentage']:.1f}%)", end='')
                
                elif event.type == 'trades':
                    trades.extend(data['trades'])
                    # Process trades incrementally
                    await process_trades_batch(data['trades'])
                
                elif event.type == 'complete':
                    print(f"\n\nAnalysis complete!")
                    print(f"Total: {data['summary']['total_trades']} trades")
                    break
                
                elif event.type == 'error':
                    print(f"\nError: {data['error']}")
                    break
            
            return trades

async def process_trades_batch(trades):
    # Process each batch as it arrives
    for trade in trades:
        # Your processing logic here
        pass

# Usage
if __name__ == "__main__":
    wallet = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
    asyncio.run(stream_wallet_analysis(wallet))
```

## Reconnection and Resumption

The SSE protocol supports automatic reconnection. When reconnecting, include the `Last-Event-ID` header with the ID of the last successfully received event:

```javascript
// Browser EventSource handles this automatically
const eventSource = new EventSource(url);

// For manual reconnection
let lastEventId = null;

eventSource.addEventListener('trades', (event) => {
  lastEventId = event.lastEventId;
  // Process trades...
});

// On reconnection
const reconnectUrl = `${url}${lastEventId ? `?last_event_id=${lastEventId}` : ''}`;
```

## Migration Guide: V3 to SSE Streaming

### Before (V3 API)
```javascript
// V3: Wait for entire response
const response = await fetch('/v3/wallet/analytics', {
  method: 'POST',
  body: JSON.stringify({ wallet_address })
});
const result = await response.json();
displayResults(result.trades); // All trades at once
```

### After (SSE Streaming)
```javascript
// SSE: Progressive loading
const eventSource = new EventSource(`/v4/wallet/${wallet_address}/stream`);

eventSource.addEventListener('trades', (event) => {
  const batch = JSON.parse(event.data);
  appendTrades(batch.trades); // Display trades as they arrive
});

eventSource.addEventListener('complete', (event) => {
  const summary = JSON.parse(event.data).summary;
  displaySummary(summary);
  eventSource.close();
});
```

### Key Differences

| Feature | V3 API | SSE Streaming |
|---------|--------|---------------|
| First results | After full processing | ~100ms |
| Memory usage | Buffers entire response | Streams in batches |
| Progress feedback | None | Real-time updates |
| Error handling | Single error response | Error events during stream |
| Reconnection | Manual retry | Automatic with Last-Event-ID |

## Performance Characteristics

- **Latency**: First trade batch typically arrives in 100-200ms
- **Throughput**: Can process 30,000+ trades/second
- **Batch Size**: Default 100 trades per batch
- **Memory**: Constant memory usage regardless of wallet size

## Best Practices

1. **Handle All Event Types**: Always implement handlers for all event types, especially errors
2. **Progress UI**: Update your UI with progress events for better UX
3. **Incremental Display**: Show trades as they arrive rather than waiting
4. **Error Recovery**: Implement reconnection logic for network issues
5. **Resource Cleanup**: Always close the EventSource when done

## Troubleshooting

### No Events Received
- Check that your client accepts `text/event-stream`
- Verify the wallet address is valid
- Ensure you're not behind a proxy that buffers SSE

### Slow Streaming
- The API adapts to client consumption speed
- Process events quickly to maintain high throughput
- Consider increasing batch size for large wallets

### Connection Drops
- EventSource automatically reconnects
- Server maintains state for resumption
- Check for rate limiting if drops persist

## Rate Limiting

The streaming API uses the same rate limits as the standard API:
- 50 requests per second per API key
- Streaming connections count as 1 request
- Progress/trade events don't count against limits

## Support

For issues or questions:
- GitHub Issues: https://github.com/walletdoctor/api/issues
- Discord: https://discord.gg/walletdoctor
- Email: support@walletdoctor.com 