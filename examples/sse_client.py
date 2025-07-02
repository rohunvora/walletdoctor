#!/usr/bin/env python3
"""
SSE Client Examples for WalletDoctor API

This module provides both Python and JavaScript examples for consuming
the Server-Sent Events (SSE) streaming endpoint.
"""

import asyncio
import aiohttp
import json
import time
from typing import Optional, Dict, Any, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
import sys


class EventType(str, Enum):
    """SSE event types matching the server protocol"""
    CONNECTED = "connected"
    PROGRESS = "progress"
    TRADES = "trades"
    METADATA = "metadata"
    COMPLETE = "complete"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


@dataclass
class SSEEvent:
    """Parsed SSE event"""
    event: str
    data: Dict[str, Any]
    id: Optional[str] = None
    retry: Optional[int] = None


class SSEClient:
    """
    Python SSE client with automatic reconnection and progress tracking
    """
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.reconnect_delay = 1.0  # Start with 1 second
        self.max_reconnect_delay = 60.0  # Max 60 seconds
        self.reconnect_attempts = 0
        self.last_event_id: Optional[str] = None
        
        # Progress tracking
        self.progress_callback: Optional[Callable[[float, str], None]] = None
        self.trades_received = 0
        self.start_time: Optional[float] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    def set_progress_callback(self, callback: Callable[[float, str], None]):
        """Set callback for progress updates (percentage, message)"""
        self.progress_callback = callback
        
    def parse_sse_line(self, line: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse a single SSE line into field and value"""
        if not line or not line.strip():
            return None, None
            
        if ':' not in line:
            return None, None
            
        field, _, value = line.partition(':')
        # Remove single leading space if present
        if value.startswith(' '):
            value = value[1:]
            
        return field.strip(), value.strip()
        
    def parse_sse_event(self, lines: list) -> Optional[SSEEvent]:
        """Parse SSE lines into an event object"""
        event_type = None
        event_data = None
        event_id = None
        retry = None
        
        for line in lines:
            field, value = self.parse_sse_line(line)
            
            if field == 'event':
                event_type = value
            elif field == 'data':
                if value:  # Add null check
                    try:
                        event_data = json.loads(value)
                    except json.JSONDecodeError:
                        event_data = value
            elif field == 'id':
                event_id = value
            elif field == 'retry':
                if value:  # Add null check
                    try:
                        retry = int(value)
                    except ValueError:
                        pass
                    
        if event_type and event_data:
            return SSEEvent(
                event=event_type,
                data=event_data if isinstance(event_data, dict) else {"raw": event_data},  # Ensure dict
                id=event_id,
                retry=retry
            )
            
        return None
        
    async def stream_wallet(self, wallet_address: str, **params) -> None:
        """
        Stream wallet data with automatic reconnection
        
        Args:
            wallet_address: Solana wallet address
            **params: Additional query parameters (skip_pricing, days, etc.)
        """
        url = f"{self.base_url}/v5/wallet/{wallet_address}/stream"
        
        # Add default params
        if 'skip_pricing' not in params:
            params['skip_pricing'] = 'true'
            
        headers = {}
        if self.last_event_id:
            headers['Last-Event-ID'] = self.last_event_id
            
        while True:
            try:
                self.start_time = time.time()
                await self._connect_and_stream(url, headers, params)
                
                # Reset reconnection state on successful completion
                self.reconnect_delay = 1.0
                self.reconnect_attempts = 0
                break
                
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                self.reconnect_attempts += 1
                print(f"\n❌ Connection error (attempt {self.reconnect_attempts}): {e}")
                
                # Exponential backoff with jitter
                jitter = 0.1 * self.reconnect_delay
                sleep_time = min(self.reconnect_delay + jitter, self.max_reconnect_delay)
                
                print(f"⏳ Reconnecting in {sleep_time:.1f}s...")
                await asyncio.sleep(sleep_time)
                
                # Increase delay for next attempt
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
                
    async def _connect_and_stream(self, url: str, headers: Dict[str, str], params: Dict[str, Any]) -> None:
        """Internal method to handle the actual streaming"""
        if not self.session:
            raise RuntimeError("Session not initialized. Use async context manager.")
            
        async with self.session.get(url, headers=headers, params=params) as response:
            response.raise_for_status()
            
            buffer = []
            async for line in response.content:
                line_str = line.decode('utf-8').rstrip('\n\r')
                
                if line_str:
                    buffer.append(line_str)
                else:
                    # Empty line signals end of event
                    if buffer:
                        event = self.parse_sse_event(buffer)
                        if event:
                            await self.handle_event(event)
                        buffer = []
                        
    async def handle_event(self, event: SSEEvent) -> None:
        """Handle incoming SSE event"""
        # Update last event ID for reconnection
        if event.id:
            self.last_event_id = event.id
            
        # Update retry interval if specified
        if event.retry:
            self.reconnect_delay = event.retry / 1000.0  # Convert ms to seconds
            
        # Handle different event types
        if event.event == EventType.CONNECTED:
            print(f"\n✅ Connected to wallet: {event.data.get('wallet', 'unknown')}")
            print(f"📅 Timestamp: {event.data.get('timestamp', 'unknown')}")
            
        elif event.event == EventType.PROGRESS:
            percentage = event.data.get('percentage', 0)
            message = event.data.get('message', '')
            step = event.data.get('step', '')
            
            # Create progress bar
            bar_width = 40
            filled = int(bar_width * percentage / 100)
            bar = '█' * filled + '░' * (bar_width - filled)
            
            # Print progress
            sys.stdout.write(f"\r[{bar}] {percentage:5.1f}% - {message}")
            sys.stdout.flush()
            
            # Call callback if set
            if self.progress_callback:
                self.progress_callback(percentage, message)
                
        elif event.event == EventType.TRADES:
            trades = event.data.get('trades', [])
            batch_num = event.data.get('batch_num', 0)
            total_yielded = event.data.get('total_yielded', 0)
            has_more = event.data.get('has_more', True)
            
            self.trades_received = total_yielded
            
            # Clear progress line and show trades info
            sys.stdout.write('\r' + ' ' * 80 + '\r')
            print(f"📊 Received batch {batch_num}: {len(trades)} trades (total: {total_yielded})")
            
            # Show sample trade
            if trades:
                sample = trades[0]
                print(f"   Sample: {sample.get('signature', 'N/A')[:8]}... "
                      f"{sample.get('type', 'unknown')} "
                      f"{sample.get('amount', 0):.4f} {sample.get('symbol', 'N/A')}")
                      
        elif event.event == EventType.METADATA:
            message = event.data.get('message', '')
            trades_updated = event.data.get('trades_updated', 0)
            print(f"\n🔍 {message} ({trades_updated} trades)")
            
        elif event.event == EventType.COMPLETE:
            elapsed = event.data.get('elapsed_seconds', 0)
            summary = event.data.get('summary', {})
            metrics = event.data.get('metrics', {})
            
            print(f"\n\n✅ Streaming complete in {elapsed:.2f}s")
            print(f"📈 Summary:")
            print(f"   Total trades: {summary.get('total_trades', 0)}")
            print(f"   Unique tokens: {summary.get('unique_tokens', 0)}")
            print(f"   P&L: ${summary.get('total_pnl', 0):.2f}")
            print(f"   Win rate: {summary.get('win_rate', 0):.1f}%")
            
            if metrics:
                print(f"\n⚡ Performance metrics:")
                for key, value in metrics.items():
                    print(f"   {key}: {value}")
                    
        elif event.event == EventType.ERROR:
            error_msg = event.data.get('error', 'Unknown error')
            error_code = event.data.get('code', '')
            print(f"\n❌ Error: {error_msg} (Code: {error_code})")
            
        elif event.event == EventType.HEARTBEAT:
            # Don't print heartbeats, just update timestamp
            pass


# JavaScript client example
JAVASCRIPT_EXAMPLE = """
// JavaScript EventSource Example for WalletDoctor SSE API

class WalletDoctorSSEClient {
    constructor(baseUrl = 'http://localhost:5000') {
        this.baseUrl = baseUrl;
        this.eventSource = null;
        this.reconnectDelay = 1000; // Start with 1 second
        this.maxReconnectDelay = 60000; // Max 60 seconds
        this.reconnectAttempts = 0;
        this.progressElement = null;
        this.tradesElement = null;
        this.startTime = null;
    }
    
    // Set DOM elements for visualization
    setElements(progressEl, tradesEl) {
        this.progressElement = progressEl;
        this.tradesElement = tradesEl;
    }
    
    // Connect to SSE endpoint
    async connect(walletAddress, params = {}) {
        // Build query string
        const queryParams = new URLSearchParams({
            skip_pricing: 'true',
            ...params
        });
        
        const url = `${this.baseUrl}/v5/wallet/${walletAddress}/stream?${queryParams}`;
        
        // Close existing connection
        if (this.eventSource) {
            this.eventSource.close();
        }
        
        this.startTime = Date.now();
        this.eventSource = new EventSource(url);
        
        // Set up event handlers
        this.eventSource.addEventListener('connected', (e) => this.handleConnected(e));
        this.eventSource.addEventListener('progress', (e) => this.handleProgress(e));
        this.eventSource.addEventListener('trades', (e) => this.handleTrades(e));
        this.eventSource.addEventListener('metadata', (e) => this.handleMetadata(e));
        this.eventSource.addEventListener('complete', (e) => this.handleComplete(e));
        this.eventSource.addEventListener('error', (e) => this.handleError(e));
        this.eventSource.addEventListener('heartbeat', (e) => this.handleHeartbeat(e));
        
        // Connection error handling
        this.eventSource.onerror = (error) => {
            console.error('SSE connection error:', error);
            this.handleConnectionError();
        };
        
        // Reset reconnect state on successful connection
        this.eventSource.onopen = () => {
            console.log('SSE connection established');
            this.reconnectDelay = 1000;
            this.reconnectAttempts = 0;
        };
    }
    
    // Event handlers
    handleConnected(event) {
        const data = JSON.parse(event.data);
        console.log('✅ Connected to wallet:', data.wallet);
        this.updateProgress(0, 'Connected, starting analysis...');
    }
    
    handleProgress(event) {
        const data = JSON.parse(event.data);
        const { percentage, message, step } = data;
        
        console.log(`Progress: ${percentage.toFixed(1)}% - ${message}`);
        this.updateProgress(percentage, message);
    }
    
    handleTrades(event) {
        const data = JSON.parse(event.data);
        const { trades, batch_num, total_yielded, has_more } = data;
        
        console.log(`Received batch ${batch_num}: ${trades.length} trades (total: ${total_yielded})`);
        this.appendTrades(trades);
    }
    
    handleMetadata(event) {
        const data = JSON.parse(event.data);
        console.log(`Metadata: ${data.message} (${data.trades_updated} trades)`);
    }
    
    handleComplete(event) {
        const data = JSON.parse(event.data);
        const { elapsed_seconds, summary, metrics } = data;
        
        console.log('✅ Streaming complete!');
        console.log('Summary:', summary);
        console.log('Metrics:', metrics);
        
        this.updateProgress(100, `Complete! ${summary.total_trades} trades analyzed in ${elapsed_seconds.toFixed(2)}s`);
        this.showSummary(summary);
    }
    
    handleError(event) {
        const data = JSON.parse(event.data);
        console.error('Error:', data.error, data.code);
        this.updateProgress(0, `Error: ${data.error}`);
    }
    
    handleHeartbeat(event) {
        // Heartbeat received - connection is alive
    }
    
    handleConnectionError() {
        this.reconnectAttempts++;
        
        // Exponential backoff
        const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), this.maxReconnectDelay);
        
        console.log(`Reconnecting in ${delay/1000}s (attempt ${this.reconnectAttempts})...`);
        this.updateProgress(0, `Connection lost. Reconnecting in ${delay/1000}s...`);
        
        setTimeout(() => {
            // Reconnect with same parameters
            // In real app, you'd store the wallet and params
            console.log('Attempting reconnection...');
        }, delay);
    }
    
    // UI update methods
    updateProgress(percentage, message) {
        if (this.progressElement) {
            this.progressElement.innerHTML = `
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${percentage}%"></div>
                </div>
                <div class="progress-text">${percentage.toFixed(1)}% - ${message}</div>
            `;
        }
    }
    
    appendTrades(trades) {
        if (this.tradesElement && trades.length > 0) {
            const tradesHtml = trades.map(trade => `
                <div class="trade-item">
                    <span class="trade-type ${trade.type}">${trade.type}</span>
                    <span class="trade-amount">${trade.amount.toFixed(4)} ${trade.symbol}</span>
                    <span class="trade-price">$${(trade.price || 0).toFixed(4)}</span>
                </div>
            `).join('');
            
            this.tradesElement.innerHTML += tradesHtml;
            
            // Auto-scroll to bottom
            this.tradesElement.scrollTop = this.tradesElement.scrollHeight;
        }
    }
    
    showSummary(summary) {
        if (this.tradesElement) {
            const summaryHtml = `
                <div class="summary">
                    <h3>Analysis Complete</h3>
                    <p>Total Trades: ${summary.total_trades}</p>
                    <p>Unique Tokens: ${summary.unique_tokens}</p>
                    <p>Total P&L: $${summary.total_pnl.toFixed(2)}</p>
                    <p>Win Rate: ${summary.win_rate.toFixed(1)}%</p>
                </div>
            `;
            
            this.tradesElement.innerHTML = summaryHtml + this.tradesElement.innerHTML;
        }
    }
    
    // Disconnect
    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }
}

// Example usage:
const client = new WalletDoctorSSEClient();
client.setElements(
    document.getElementById('progress'),
    document.getElementById('trades')
);

// Connect to wallet stream
client.connect('3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2', {
    days: 30,
    skip_pricing: true
});

// CSS for visualization
const styles = `
<style>
.progress-bar {
    width: 100%;
    height: 20px;
    background: #f0f0f0;
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 10px;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #4CAF50, #45a049);
    transition: width 0.3s ease;
}

.progress-text {
    font-size: 14px;
    color: #666;
}

.trade-item {
    display: flex;
    justify-content: space-between;
    padding: 8px;
    border-bottom: 1px solid #eee;
}

.trade-type {
    font-weight: bold;
    text-transform: uppercase;
}

.trade-type.buy { color: #4CAF50; }
.trade-type.sell { color: #f44336; }

.trade-amount { color: #666; }
.trade-price { font-weight: 500; }

.summary {
    background: #f9f9f9;
    padding: 15px;
    border-radius: 8px;
    margin-bottom: 20px;
}

.summary h3 {
    margin-top: 0;
    color: #333;
}

.summary p {
    margin: 5px 0;
    color: #666;
}
</style>
`;
"""


async def main():
    """Example usage of SSE client"""
    # Example wallet address
    wallet = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
    
    async with SSEClient() as client:
        # Set progress callback
        def on_progress(percentage: float, message: str):
            # Custom progress handling
            if percentage >= 100:
                print("\n🎉 Analysis complete!")
                
        client.set_progress_callback(on_progress)
        
        # Stream wallet data
        try:
            await client.stream_wallet(
                wallet,
                days=30,
                skip_pricing=True
            )
        except KeyboardInterrupt:
            print("\n\n⚠️  Streaming interrupted by user")
        except Exception as e:
            print(f"\n\n❌ Streaming error: {e}")


def print_javascript_example():
    """Print the JavaScript example code"""
    print("\n" + "="*80)
    print("JAVASCRIPT CLIENT EXAMPLE")
    print("="*80)
    print(JAVASCRIPT_EXAMPLE)
    print("="*80 + "\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="SSE Client for WalletDoctor API")
    parser.add_argument("wallet", nargs="?", help="Wallet address to analyze")
    parser.add_argument("--days", type=int, default=30, help="Number of days to analyze")
    parser.add_argument("--js-example", action="store_true", help="Print JavaScript example")
    
    args = parser.parse_args()
    
    if args.js_example:
        print_javascript_example()
    elif args.wallet:
        # Run Python client
        asyncio.run(main())
    else:
        print("Usage: python sse_client.py <wallet_address> [--days N]")
        print("   Or: python sse_client.py --js-example")
        print("\nExample:")
        print("  python sse_client.py 3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2 --days 30") 