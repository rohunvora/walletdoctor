/**
 * Basic usage example for WalletDoctor TypeScript client
 */

import { WalletDoctorClient, WalletDoctorError } from '../src';

async function main() {
  // Initialize client
  const client = new WalletDoctorClient({
    // Replace with your actual API key
    apiKey: 'wd_12345678901234567890123456789012',
    // Optional: override base URL
    // baseUrl: 'https://your-deployment.railway.app',
    // Optional: custom retry configuration
    retryConfig: {
      maxRetries: 3,
      initialDelay: 1000,
      maxDelay: 16000,
      backoffMultiplier: 2,
    }
  });

  try {
    // Export trades for a wallet
    const wallet = '34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya';
    console.log(`Fetching trades for wallet: ${wallet}`);
    
    const startTime = Date.now();
    const result = await client.exportTrades(wallet);
    const duration = Date.now() - startTime;
    
    // Display results
    console.log(`✅ Success! Retrieved data in ${duration}ms`);
    console.log(`Wallet: ${result.wallet}`);
    console.log(`Signatures: ${result.signatures.length}`);
    console.log(`Trades: ${result.trades.length}`);
    
    // Show first few trades
    console.log('\nFirst 5 trades:');
    result.trades.slice(0, 5).forEach((trade, i) => {
      console.log(`${i + 1}. ${trade.action} ${trade.amount} ${trade.token} at ${trade.timestamp}`);
      console.log(`   Price: $${trade.price}, Value: $${trade.value_usd}`);
      console.log(`   P&L: $${trade.pnl_usd}`);
    });
    
    // Calculate summary stats
    const totalValue = result.trades.reduce((sum, t) => sum + t.value_usd, 0);
    const totalPnL = result.trades.reduce((sum, t) => sum + t.pnl_usd, 0);
    const buys = result.trades.filter(t => t.action === 'buy').length;
    const sells = result.trades.filter(t => t.action === 'sell').length;
    
    console.log('\n📊 Summary:');
    console.log(`Total trades: ${result.trades.length}`);
    console.log(`Buys: ${buys}, Sells: ${sells}`);
    console.log(`Total volume: $${totalValue.toFixed(2)}`);
    console.log(`Total P&L: $${totalPnL.toFixed(2)}`);
    
  } catch (error) {
    if (error instanceof WalletDoctorError) {
      console.error(`❌ API Error (${error.statusCode}): ${error.message}`);
      if (error.code) {
        console.error(`Error code: ${error.code}`);
      }
    } else {
      console.error('❌ Unexpected error:', error);
    }
  }
}

// Run the example
main().catch(console.error); 