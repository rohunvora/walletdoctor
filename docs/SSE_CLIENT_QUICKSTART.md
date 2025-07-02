# SSE Client Quick Start

Quick examples to get started with the WalletDoctor SSE streaming API.

## Browser Example (Copy & Paste)

```html
<!DOCTYPE html>
<html>
<head>
    <title>WalletDoctor SSE Demo</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        #progress { width: 100%; height: 20px; background: #f0f0f0; }
        #progress-bar { height: 100%; background: #4CAF50; width: 0%; transition: width 0.3s; }
        #trades { margin-top: 20px; }
        .trade { padding: 5px; border-bottom: 1px solid #eee; }
        .buy { color: green; }
        .sell { color: red; }
    </style>
</head>
<body>
    <h1>WalletDoctor SSE Streaming Demo</h1>
    
    <input type="text" id="wallet" placeholder="Enter wallet address" style="width: 400px;">
    <button onclick="startStream()">Analyze Wallet</button>
    
    <div id="status"></div>
    <div id="progress"><div id="progress-bar"></div></div>
    <div id="summary"></div>
    <div id="trades"></div>

    <script>
    let eventSource;

    function startStream() {
        // Close any existing connection
        if (eventSource) {
            eventSource.close();
        }

        const wallet = document.getElementById('wallet').value;
        if (!wallet) {
            alert('Please enter a wallet address');
            return;
        }

        // Clear previous results
        document.getElementById('trades').innerHTML = '';
        document.getElementById('summary').innerHTML = '';
        document.getElementById('status').textContent = 'Connecting...';

        // Create SSE connection
        eventSource = new EventSource(`/v4/wallet/${wallet}/stream`);

        eventSource.addEventListener('connected', (event) => {
            const data = JSON.parse(event.data);
            document.getElementById('status').textContent = `Connected to wallet: ${data.wallet}`;
        });

        eventSource.addEventListener('progress', (event) => {
            const data = JSON.parse(event.data);
            document.getElementById('status').textContent = data.message;
            document.getElementById('progress-bar').style.width = data.percentage + '%';
        });

        eventSource.addEventListener('trades', (event) => {
            const data = JSON.parse(event.data);
            const tradesDiv = document.getElementById('trades');
            
            data.trades.forEach(trade => {
                const tradeDiv = document.createElement('div');
                tradeDiv.className = `trade ${trade.type}`;
                tradeDiv.innerHTML = `
                    <strong>${trade.type.toUpperCase()}</strong>
                    ${trade.token_in_amount} ${trade.token_in_symbol} → 
                    ${trade.token_out_amount} ${trade.token_out_symbol}
                    ($${trade.value_usd?.toFixed(2) || 'N/A'})
                `;
                tradesDiv.appendChild(tradeDiv);
            });

            document.getElementById('status').textContent = 
                `Received batch ${data.batch_num}: ${data.total_yielded} trades total`;
        });

        eventSource.addEventListener('complete', (event) => {
            const data = JSON.parse(event.data);
            document.getElementById('summary').innerHTML = `
                <h2>Analysis Complete</h2>
                <p>Total Trades: ${data.summary.total_trades}</p>
                <p>Total Volume: $${data.summary.total_volume?.toFixed(2) || '0'}</p>
                <p>Total P&L: $${data.summary.total_pnl_usd?.toFixed(2) || '0'}</p>
                <p>Win Rate: ${data.summary.win_rate?.toFixed(1) || '0'}%</p>
                <p>Time: ${data.elapsed_seconds}s</p>
            `;
            document.getElementById('status').textContent = 'Analysis complete!';
            eventSource.close();
        });

        eventSource.addEventListener('error', (event) => {
            if (event.data) {
                const data = JSON.parse(event.data);
                document.getElementById('status').textContent = `Error: ${data.error}`;
            }
        });

        eventSource.onerror = (error) => {
            document.getElementById('status').textContent = 'Connection error - retrying...';
        };
    }
    </script>
</body>
</html>
```

## Node.js Example

```javascript
// npm install eventsource

const EventSource = require('eventsource');

function analyzeWallet(walletAddress) {
    const url = `http://localhost:5000/v4/wallet/${walletAddress}/stream`;
    const eventSource = new EventSource(url);

    console.log(`Starting analysis for wallet: ${walletAddress}\n`);

    let tradeCount = 0;

    eventSource.on('connected', (event) => {
        console.log('✓ Connected to stream');
    });

    eventSource.on('progress', (event) => {
        const data = JSON.parse(event.data);
        process.stdout.write(`\r${data.message} (${data.percentage.toFixed(1)}%)`);
    });

    eventSource.on('trades', (event) => {
        const data = JSON.parse(event.data);
        tradeCount += data.trades.length;
        // Clear the progress line
        process.stdout.write('\r' + ' '.repeat(80) + '\r');
        console.log(`Received batch ${data.batch_num}: ${data.trades.length} trades (${tradeCount} total)`);
    });

    eventSource.on('complete', (event) => {
        const data = JSON.parse(event.data);
        console.log('\n=== Analysis Complete ===');
        console.log(`Total trades: ${data.summary.total_trades}`);
        console.log(`Total P&L: $${data.summary.total_pnl_usd?.toFixed(2) || '0'}`);
        console.log(`Win rate: ${data.summary.win_rate?.toFixed(1) || '0'}%`);
        console.log(`Time: ${data.elapsed_seconds}s`);
        eventSource.close();
        process.exit(0);
    });

    eventSource.on('error', (event) => {
        if (event.type === 'error') {
            console.error('\nConnection error, retrying...');
        } else if (event.data) {
            const data = JSON.parse(event.data);
            console.error(`\nError: ${data.error}`);
            eventSource.close();
            process.exit(1);
        }
    });
}

// Usage
const wallet = process.argv[2] || '3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2';
analyzeWallet(wallet);
```

## Python Example

```python
# pip install sseclient-py requests

import sseclient
import requests
import json
import sys

def analyze_wallet(wallet_address):
    url = f"http://localhost:5000/v4/wallet/{wallet_address}/stream"
    
    print(f"Starting analysis for wallet: {wallet_address}\n")
    
    response = requests.get(url, stream=True, headers={'Accept': 'text/event-stream'})
    client = sseclient.SSEClient(response)
    
    trade_count = 0
    
    try:
        for event in client.events():
            data = json.loads(event.data)
            
            if event.event == 'connected':
                print("✓ Connected to stream")
            
            elif event.event == 'progress':
                print(f"\r{data['message']} ({data['percentage']:.1f}%)", end='', flush=True)
            
            elif event.event == 'trades':
                trade_count += len(data['trades'])
                print(f"\rReceived batch {data['batch_num']}: {len(data['trades'])} trades ({trade_count} total)")
            
            elif event.event == 'complete':
                print("\n\n=== Analysis Complete ===")
                print(f"Total trades: {data['summary']['total_trades']}")
                print(f"Total P&L: ${data['summary'].get('total_pnl_usd', 0):.2f}")
                print(f"Win rate: {data['summary'].get('win_rate', 0):.1f}%")
                print(f"Time: {data['elapsed_seconds']}s")
                break
            
            elif event.event == 'error':
                print(f"\nError: {data['error']}")
                break
                
    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user")
    except Exception as e:
        print(f"\nConnection error: {e}")

if __name__ == "__main__":
    wallet = sys.argv[1] if len(sys.argv) > 1 else "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
    analyze_wallet(wallet)
```

## Testing with cURL

```bash
# Basic streaming
curl -N "http://localhost:5000/v4/wallet/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2/stream"

# With skip pricing for faster results
curl -N "http://localhost:5000/v4/wallet/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2/stream?skip_pricing=true"

# Pretty print with jq (requires jq installed)
curl -N "http://localhost:5000/v4/wallet/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2/stream" | \
while IFS= read -r line; do
    if [[ $line == data:* ]]; then
        echo "$line" | cut -d' ' -f2- | jq '.'
    else
        echo "$line"
    fi
done
```

## Key Points

1. **Connection Management**: Always close the EventSource when done
2. **Error Handling**: Implement both SSE error events and connection errors
3. **Progress Updates**: Use progress events to update UI
4. **Incremental Display**: Show trades as they arrive for better UX
5. **Reconnection**: EventSource automatically reconnects on connection loss

## Next Steps

- See the full [SSE Streaming Guide](SSE_STREAMING_GUIDE.md) for advanced usage
- Check out the [examples](../examples/) directory for more client implementations
- Read about the [Progress Protocol](SSE_STREAMING_GUIDE.md#event-types) for event details 