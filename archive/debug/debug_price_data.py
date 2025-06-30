#!/usr/bin/env python3
"""
Debug script to test price data availability from Birdeye.
Tests:
1. What percentage of tokens have price data?
2. How many API calls are needed for a typical wallet?
3. Are there patterns in missing price data?
"""

import os
import sys
import json
import requests
import time
from datetime import datetime
from collections import defaultdict

HELIUS_KEY = os.getenv("HELIUS_KEY")
BIRDEYE_KEY = os.getenv("BIRDEYE_API_KEY")

if not HELIUS_KEY:
    print("Error: HELIUS_KEY environment variable not set")
    sys.exit(1)

class PriceDebugger:
    def __init__(self):
        self.stats = {
            'total_tokens': 0,
            'unique_tokens': set(),
            'price_success': 0,
            'price_failures': 0,
            'price_api_calls': 0,
            'tokens_missing_price': [],
            'token_categories': defaultdict(int)
        }
        
    def log(self, message):
        """Log with timestamp"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
    def test_price_availability(self, mint, timestamp):
        """Test if price data is available for a token at a specific time"""
        self.stats['price_api_calls'] += 1
        
        if not BIRDEYE_KEY:
            self.log("  ⚠️  No BIRDEYE_API_KEY set, skipping price test")
            return False
            
        # Known stablecoins
        if mint in ["EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"]:
            self.stats['price_success'] += 1
            return True
            
        try:
            url = f"https://public-api.birdeye.so/defi/historical_price_unix"
            params = {
                "address": mint,
                "type": "1m",
                "time_from": timestamp - 60,
                "time_to": timestamp + 60
            }
            headers = {"X-API-KEY": BIRDEYE_KEY}
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("data") and data["data"].get("items"):
                    self.stats['price_success'] += 1
                    return True
                else:
                    self.stats['price_failures'] += 1
                    self.stats['tokens_missing_price'].append(mint)
                    return False
            else:
                self.log(f"  ❌ Price API error {response.status_code} for {mint}")
                self.stats['price_failures'] += 1
                return False
                
        except Exception as e:
            self.log(f"  ❌ Price lookup error: {e}")
            self.stats['price_failures'] += 1
            return False
            
    def analyze_wallet_tokens(self, wallet_address):
        """Analyze all tokens traded by a wallet"""
        self.log(f"\n🔍 Analyzing tokens for wallet: {wallet_address}")
        
        url = f"https://api.helius.xyz/v0/addresses/{wallet_address}/transactions"
        params = {
            "api-key": HELIUS_KEY,
            "limit": 100,
            "type": "SWAP"
        }
        
        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            transactions = response.json()
            
            self.log(f"  Found {len(transactions)} swap transactions")
            
            tokens_to_test = []  # (mint, timestamp) tuples
            
            for tx in transactions:
                events = tx.get('events', {})
                swap = events.get('swap', {})
                timestamp = tx.get('timestamp', 0)
                
                # Collect all token mints from the swap
                token_inputs = swap.get('tokenInputs', [])
                token_outputs = swap.get('tokenOutputs', [])
                
                for token in token_inputs + token_outputs:
                    mint = token.get('mint')
                    if mint:
                        self.stats['unique_tokens'].add(mint)
                        tokens_to_test.append((mint, timestamp))
                        
                # Also check innerSwaps
                inner_swaps = swap.get('innerSwaps', [])
                for inner in inner_swaps:
                    for token in inner.get('tokenInputs', []) + inner.get('tokenOutputs', []):
                        mint = token.get('mint')
                        if mint:
                            self.stats['unique_tokens'].add(mint)
                            tokens_to_test.append((mint, timestamp))
                            
            self.log(f"  Found {len(self.stats['unique_tokens'])} unique tokens")
            
            # Test a sample of token/timestamp pairs
            if BIRDEYE_KEY:
                sample_size = min(20, len(tokens_to_test))
                self.log(f"  Testing price availability for {sample_size} token instances...")
                
                for i, (mint, timestamp) in enumerate(tokens_to_test[:sample_size]):
                    self.test_price_availability(mint, timestamp)
                    time.sleep(0.1)  # Rate limit
                    
                    if (i + 1) % 5 == 0:
                        self.log(f"    Tested {i + 1}/{sample_size}...")
                        
        except Exception as e:
            self.log(f"  ❌ Error analyzing wallet: {e}")
            
    def print_summary(self):
        """Print analysis summary"""
        print("\n" + "="*60)
        print("PRICE DATA AVAILABILITY SUMMARY")
        print("="*60)
        
        print(f"\nToken Statistics:")
        print(f"  Unique tokens found: {len(self.stats['unique_tokens'])}")
        print(f"  Price lookups attempted: {self.stats['price_api_calls']}")
        print(f"  Successful price lookups: {self.stats['price_success']}")
        print(f"  Failed price lookups: {self.stats['price_failures']}")
        
        if self.stats['price_api_calls'] > 0:
            success_rate = self.stats['price_success'] / self.stats['price_api_calls'] * 100
            print(f"  Price data availability: {success_rate:.1f}%")
            
        if self.stats['tokens_missing_price']:
            print(f"\nTokens without price data ({len(self.stats['tokens_missing_price'])}):")
            for mint in self.stats['tokens_missing_price'][:5]:
                print(f"  - {mint}")
            if len(self.stats['tokens_missing_price']) > 5:
                print(f"  ... and {len(self.stats['tokens_missing_price']) - 5} more")
                
        print(f"\nEstimated API calls for full history:")
        print(f"  Unique tokens: {len(self.stats['unique_tokens'])}")
        print(f"  Est. price lookups needed: ~{len(self.stats['unique_tokens']) * 10}")
        print(f"  (Assuming ~10 trades per token average)")


def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_price_data.py <wallet_address>")
        sys.exit(1)
        
    wallet = sys.argv[1]
    debugger = PriceDebugger()
    
    # Analyze the wallet
    debugger.analyze_wallet_tokens(wallet)
    
    # Print summary
    debugger.print_summary()
    
    # Save detailed stats
    debug_file = f"{wallet[:8]}_price_debug.json"
    with open(debug_file, 'w') as f:
        # Convert set to list for JSON serialization
        stats_copy = debugger.stats.copy()
        stats_copy['unique_tokens'] = list(stats_copy['unique_tokens'])
        json.dump(stats_copy, f, indent=2)
    print(f"\n📄 Detailed stats saved to: {debug_file}")


if __name__ == "__main__":
    main() 