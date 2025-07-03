import fetch from 'node-fetch';
import {
  WalletDoctorConfig,
  ExportResponse,
  ErrorResponse,
  RetryErrorResponse,
  RequestOptions,
} from './types';

/**
 * WalletDoctor API Client for TypeScript
 * Provides easy access to the trades export endpoint with automatic retry logic
 */
export class WalletDoctorClient {
  private config: Required<WalletDoctorConfig>;

  constructor(config: WalletDoctorConfig) {
    this.config = {
      apiKey: config.apiKey,
      baseUrl: config.baseUrl || 'https://web-production-2bb2f.up.railway.app',
      timeout: config.timeout || 30000,
      retryConfig: {
        maxRetries: config.retryConfig?.maxRetries ?? 3,
        initialDelay: config.retryConfig?.initialDelay ?? 1000,
        maxDelay: config.retryConfig?.maxDelay ?? 16000,
        backoffMultiplier: config.retryConfig?.backoffMultiplier ?? 2,
      },
    };

    // Validate API key format
    if (!this.config.apiKey.startsWith('wd_') || this.config.apiKey.length !== 35) {
      throw new Error('API key must start with "wd_" followed by 32 characters');
    }
  }

  /**
   * Export trades for a given wallet address
   * @param wallet Solana wallet address
   * @param options Optional request configuration
   * @returns Export response with trades and signatures
   */
  async exportTrades(
    wallet: string,
    options?: RequestOptions
  ): Promise<ExportResponse> {
    // Validate wallet address
    if (!wallet || wallet.length < 32 || wallet.length > 44) {
      throw new Error('Invalid wallet address');
    }

    const url = `${this.config.baseUrl}/v4/trades/export-gpt/${wallet}`;
    
    return this.makeRequestWithRetry(url, options);
  }

  /**
   * Make HTTP request with automatic retry logic
   */
  private async makeRequestWithRetry(
    url: string,
    options?: RequestOptions,
    attempt: number = 1
  ): Promise<ExportResponse> {
    const headers = {
      'X-Api-Key': this.config.apiKey,
      'Accept': 'application/json',
      ...options?.headers,
    };

    try {
      const response = await fetch(url, {
        method: 'GET',
        headers,
        signal: options?.signal,
        // @ts-ignore - node-fetch timeout option
        timeout: this.config.timeout,
      });

      // Success
      if (response.ok) {
        return await response.json() as ExportResponse;
      }

      // Handle errors
      const errorBody = await response.json() as ErrorResponse;

      // Don't retry client errors (4xx)
      if (response.status >= 400 && response.status < 500) {
        throw new WalletDoctorError(
          errorBody.message || 'Client error',
          response.status,
          errorBody.code
        );
      }

      // Server error (5xx) - check if we should retry
      const maxRetries = this.config.retryConfig?.maxRetries ?? 3;
      if (response.status >= 500 && attempt <= maxRetries) {
        const retryError = errorBody as RetryErrorResponse;
        const delay = this.calculateRetryDelay(attempt, retryError.retry_after);
        
        // Use console.warn if available (Node.js/browser), otherwise skip logging
        if (typeof console !== 'undefined' && console.warn) {
          console.warn(
            `Request failed (${response.status}), retrying in ${delay}ms...`,
            `Attempt ${attempt}/${maxRetries}`
          );
        }

        await this.sleep(delay);
        return this.makeRequestWithRetry(url, options, attempt + 1);
      }

      // Max retries exceeded or non-retryable error
      throw new WalletDoctorError(
        errorBody.message || 'Server error',
        response.status,
        errorBody.code
      );

    } catch (error: any) {
      // Network errors, timeouts, etc.
      if (error instanceof WalletDoctorError) {
        throw error;
      }

      // Retry network errors if we haven't exceeded max attempts
      const maxRetries = this.config.retryConfig?.maxRetries ?? 3;
      if (attempt <= maxRetries) {
        const delay = this.calculateRetryDelay(attempt);
        
        // Use console.warn if available
        if (typeof console !== 'undefined' && console.warn) {
          console.warn(
            `Network error: ${error.message}, retrying in ${delay}ms...`,
            `Attempt ${attempt}/${maxRetries}`
          );
        }

        await this.sleep(delay);
        return this.makeRequestWithRetry(url, options, attempt + 1);
      }

      throw new WalletDoctorError(
        `Network error: ${error.message}`,
        0,
        'NETWORK_ERROR'
      );
    }
  }

  /**
   * Calculate retry delay with exponential backoff
   */
  private calculateRetryDelay(attempt: number, retryAfter?: number): number {
    if (retryAfter) {
      return retryAfter * 1000; // Convert to milliseconds
    }

    const initialDelay = this.config.retryConfig?.initialDelay ?? 1000;
    const backoffMultiplier = this.config.retryConfig?.backoffMultiplier ?? 2;
    const maxDelay = this.config.retryConfig?.maxDelay ?? 16000;

    const exponentialDelay = initialDelay * Math.pow(backoffMultiplier, attempt - 1);

    return Math.min(exponentialDelay, maxDelay);
  }

  /**
   * Sleep helper for retry delays
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => {
      // Use setTimeout if available (Node.js/browser)
      if (typeof setTimeout !== 'undefined') {
        setTimeout(resolve, ms);
      } else {
        // Fallback: immediate resolve if no timer available
        resolve();
      }
    });
  }
}

/**
 * Custom error class for WalletDoctor API errors
 */
export class WalletDoctorError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public code?: string
  ) {
    super(message);
    this.name = 'WalletDoctorError';
  }
} 