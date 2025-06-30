#!/usr/bin/env python3
"""Test blockchain fetcher and save output as JSON"""

import json
import sys
from blockchain_fetcher import fetch_wallet_trades

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_blockchain_fetcher.py <wallet_address>")
        sys.exit(1)
        
    wallet = sys.argv[1]
    output_file = f"{wallet[:8]}_trades.json"
    
    print(f"Fetching trades for wallet: {wallet}")
    
    def print_progress(msg):
        print(f"[Progress] {msg}")
        
    try:
        trades = fetch_wallet_trades(wallet, print_progress)
        
        # Calculate summary
        total_trades = len(trades)
        priced_trades = [t for t in trades if t.get('priced', False) and t.get('value_usd', 0) > 0]
        total_volume = sum(t['value_usd'] for t in trades if t['value_usd'])
        
        print(f"\nSummary:")
        print(f"Total trades: {total_trades}")
        print(f"Priced trades: {len(priced_trades)}")
        print(f"Total volume: ${total_volume:,.2f}")
        
        # Save to JSON
        with open(output_file, 'w') as f:
            json.dump({
                'wallet': wallet,
                'summary': {
                    'total_trades': total_trades,
                    'priced_trades': len(priced_trades),
                    'total_volume': float(total_volume)
                },
                'trades': trades
            }, f, indent=2)
            
        print(f"\nOutput saved to: {output_file}")
        
        # Show sample trades
        if trades:
            print("\nSample trades:")
            for i, trade in enumerate(trades[:3]):
                print(f"  {i+1}. {trade['action']} {trade['amount']:.2f} {trade['token']} @ ${trade.get('price', 0):.4f} = ${trade.get('value_usd', 0):.2f}")
                
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 