# WalletDoctor TypeScript Client

TypeScript client library for the WalletDoctor trades export API. Features automatic retry logic, TypeScript types, and easy integration.

## Installation

This is a private package within the WalletDoctor monorepo. To use it in your project:

```bash
# From the repository root
cd clients/ts
npm install
npm run build
```

## Quick Start

```typescript
import { WalletDoctorClient } from '@walletdoctor/client-ts';

const client = new WalletDoctorClient({
  apiKey: 'wd_your_api_key_here'
});

const trades = await client.exportTrades('34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya');
console.log(`Found ${trades.trades.length} trades`);
```

## Configuration

### Basic Configuration

```typescript
const client = new WalletDoctorClient({
  apiKey: 'wd_your_32_character_key_here',  // Required
  baseUrl: 'https://your-deployment.com',   // Optional (defaults to production)
  timeout: 30000,                            // Optional timeout in ms (default: 30s)
});
```

### Advanced Configuration with Retry

```typescript
const client = new WalletDoctorClient({
  apiKey: 'wd_your_api_key_here',
  retryConfig: {
    maxRetries: 3,           // Maximum retry attempts (default: 3)
    initialDelay: 1000,      // Initial retry delay in ms (default: 1s)
    maxDelay: 16000,         // Maximum retry delay in ms (default: 16s)
    backoffMultiplier: 2,    // Exponential backoff multiplier (default: 2)
  }
});
```

## API Methods

### exportTrades(wallet, options?)

Export all trades for a given wallet address.

**Parameters:**
- `wallet` (string): Solana wallet address (32-44 characters)
- `options` (RequestOptions): Optional request configuration

**Returns:** `Promise<ExportResponse>`

**Example:**
```typescript
try {
  const result = await client.exportTrades('wallet_address', {
    signal: abortController.signal,  // Optional: cancellation
    headers: {                        // Optional: additional headers
      'X-Custom-Header': 'value'
    }
  });
  
  console.log(`Wallet: ${result.wallet}`);
  console.log(`Total trades: ${result.trades.length}`);
  
  // Process trades
  result.trades.forEach(trade => {
    console.log(`${trade.action} ${trade.amount} ${trade.token} at ${trade.price}`);
  });
} catch (error) {
  if (error instanceof WalletDoctorError) {
    console.error(`API Error (${error.statusCode}): ${error.message}`);
  }
}
```

## Error Handling

The client throws `WalletDoctorError` for all API errors:

```typescript
import { WalletDoctorError } from '@walletdoctor/client-ts';

try {
  const trades = await client.exportTrades(wallet);
} catch (error) {
  if (error instanceof WalletDoctorError) {
    switch (error.statusCode) {
      case 403:
        console.error('Authentication failed:', error.message);
        break;
      case 400:
        console.error('Invalid wallet address:', error.message);
        break;
      case 500:
      case 502:
      case 503:
        console.error('Server error (will retry):', error.message);
        break;
      default:
        console.error(`Error ${error.statusCode}: ${error.message}`);
    }
  } else {
    console.error('Unexpected error:', error);
  }
}
```

## Automatic Retry

The client automatically retries on:
- Network errors
- 5xx server errors
- Timeout errors

Retries use exponential backoff with jitter. You can monitor retry attempts in the console:
```
Request failed (502), retrying in 2000ms... Attempt 1/3
Request failed (502), retrying in 4000ms... Attempt 2/3
```

## Types

All TypeScript types are exported:

```typescript
import {
  ExportResponse,
  Trade,
  TokenFlow,
  ErrorResponse,
  WalletDoctorConfig,
  RetryConfig,
  RequestOptions
} from '@walletdoctor/client-ts';
```

### ExportResponse
```typescript
interface ExportResponse {
  wallet: string;
  signatures: string[];
  trades: Trade[];
}
```

### Trade
```typescript
interface Trade {
  action: 'buy' | 'sell';
  amount: number;
  dex: string;
  fees_usd: number;
  pnl_usd: number;
  position_closed: boolean;
  price: number;
  priced: boolean;
  signature: string;
  timestamp: string;
  token: string;
  token_in: TokenFlow;
  token_out: TokenFlow;
  tx_type: string;
  value_usd: number;
}
```

## Examples

See the `examples/` directory for more usage examples:
- `basic-usage.ts` - Simple trade export with summary stats

Run an example:
```bash
cd clients/ts
npm run build
node dist/examples/basic-usage.js
```

## Development

```bash
# Install dependencies
npm install

# Build TypeScript
npm run build

# Run tests
npm test

# Lint code
npm run lint
```

## Schema Version

This client is built for API schema version **0.7.0**. The schema is frozen until the completion of POS-001 and PRC-001 features.

## License

MIT 