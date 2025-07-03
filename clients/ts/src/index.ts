/**
 * WalletDoctor TypeScript Client
 * 
 * Example usage:
 * ```typescript
 * import { WalletDoctorClient } from '@walletdoctor/client-ts';
 * 
 * const client = new WalletDoctorClient({
 *   apiKey: 'wd_your_api_key_here'
 * });
 * 
 * const trades = await client.exportTrades('wallet_address');
 * console.log(`Found ${trades.trades.length} trades`);
 * ```
 */

export { WalletDoctorClient, WalletDoctorError } from './client';
export * from './types'; 