/**
 * Type definitions for WalletDoctor Trades Export API v0.7.0
 * Auto-generated from JSONSchema - DO NOT EDIT
 */

// Token flow in/out of a trade
export interface TokenFlow {
  amount: number;
  mint: string;
  symbol: string;
}

// Individual trade record
export interface Trade {
  action: 'buy' | 'sell';
  amount: number;
  dex: string;
  fees_usd: number;
  pnl_usd: number;
  position_closed: boolean;
  price: number;
  priced: boolean;
  signature: string;
  timestamp: string; // ISO 8601 date-time
  token: string;
  token_in: TokenFlow;
  token_out: TokenFlow;
  tx_type: string;
  value_usd: number;
}

// Main export response
export interface ExportResponse {
  wallet: string;
  signatures: string[];
  trades: Trade[];
}

// Error response
export interface ErrorResponse {
  error: string;
  message: string;
  code?: string;
}

// Retry error response (5xx)
export interface RetryErrorResponse extends ErrorResponse {
  retry_after: number;
}

// API Configuration
export interface WalletDoctorConfig {
  apiKey: string;
  baseUrl?: string;
  timeout?: number;
  retryConfig?: RetryConfig;
}

// Retry configuration
export interface RetryConfig {
  maxRetries?: number;
  initialDelay?: number;
  maxDelay?: number;
  backoffMultiplier?: number;
}

// Request options
export interface RequestOptions {
  signal?: any; // AbortSignal for request cancellation
  headers?: Record<string, string>;
} 