#!/usr/bin/env python3
"""
Debug script to validate assumptions about Helius API issues.
Tests:
1. How many swaps have innerSwaps vs simple swap events?
2. Are we missing transactions when not using filters?
3. What percentage of tokens have missing price data?
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

class DebugLogger:
    def __init__(self):
        self.stats = {
            'total_transactions': 0,
            'swap_transactions': 0,
            'has_swap_event': 0,
            'has_inner_swaps': 0,
            'multi_hop_swaps': 0,
            'missing_swap_event': 0,
            'token_metadata_failures': 0,
            'price_lookup_failures': 0,
            'dex_sources': defaultdict(int),
            'swap_types': defaultdict(int),
            'unparseable_swaps': []
        }
        
    def log(self, message):
        """Log with timestamp"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
    def analyze_transaction(self, tx):
        """Analyze a single transaction for swap patterns"""
        self.stats['total_transactions'] += 1
        
        # Check if it's a swap by type
        if tx.get('type') == 'SWAP':
            self.stats['swap_transactions'] += 1
            
        # Check for swap events
        events = tx.get('events', {})
        swap = events.get('swap')
        
        if swap:
            self.stats['has_swap_event'] += 1
            
            # Check for innerSwaps
            inner_swaps = swap.get('innerSwaps', [])
            if inner_swaps:
                self.stats['has_inner_swaps'] += 1
                if len(inner_swaps) > 1:
                    self.stats['multi_hop_swaps'] += 1
                    self.log(f"  → Multi-hop swap found: {len(inner_swaps)} hops in tx {tx['signature'][:8]}...")
                    
            # Track DEX sources
            source = tx.get('source', 'UNKNOWN')
            self.stats['dex_sources'][source] += 1
            
            # Analyze swap structure
            self._analyze_swap_structure(swap, tx['signature'])
            
        else:
            # Transaction marked as SWAP but no swap event
            if tx.get('type') == 'SWAP':
                self.stats['missing_swap_event'] += 1
                self.log(f"  ⚠️  SWAP transaction without swap event: {tx['signature'][:8]}...")
                
    def _analyze_swap_structure(self, swap, signature):
        """Analyze swap event structure"""
        # Check what type of swap inputs/outputs exist
        has_native_input = bool(swap.get('nativeInput'))
        has_native_output = bool(swap.get('nativeOutput'))
        has_token_inputs = bool(swap.get('tokenInputs'))
        has_token_outputs = bool(swap.get('tokenOutputs'))
        
        swap_type = []
        if has_native_input and has_token_outputs:
            swap_type.append('SOL→Token')
        if has_token_inputs and has_native_output:
            swap_type.append('Token→SOL')
        if has_token_inputs and has_token_outputs:
            swap_type.append('Token→Token')
            
        if swap_type:
            self.stats['swap_types'][','.join(swap_type)] += 1
        else:
            self.stats['unparseable_swaps'].append(signature[:8])
            
    def print_summary(self):
        """Print analysis summary"""
        print("\n" + "="*60)
        print("HELIUS API DEBUG SUMMARY")
        print("="*60)
        
        print(f"\nTransaction Analysis:")
        print(f"  Total fetched: {self.stats['total_transactions']}")
        print(f"  Type=SWAP: {self.stats['swap_transactions']} ({self.stats['swap_transactions']/max(1,self.stats['total_transactions'])*100:.1f}%)")
        print(f"  Has swap event: {self.stats['has_swap_event']} ({self.stats['has_swap_event']/max(1,self.stats['total_transactions'])*100:.1f}%)")
        print(f"  Missing swap event: {self.stats['missing_swap_event']}")
        
        print(f"\nSwap Complexity:")
        print(f"  Simple swaps: {self.stats['has_swap_event'] - self.stats['has_inner_swaps']}")
        print(f"  Has innerSwaps: {self.stats['has_inner_swaps']} ({self.stats['has_inner_swaps']/max(1,self.stats['has_swap_event'])*100:.1f}% of swaps)")
        print(f"  Multi-hop (2+ hops): {self.stats['multi_hop_swaps']}")
        
        print(f"\nDEX Sources:")
        for source, count in sorted(self.stats['dex_sources'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {source}: {count}")
            
        print(f"\nSwap Types:")
        for swap_type, count in self.stats['swap_types'].items():
            print(f"  {swap_type}: {count}")
            
        if self.stats['unparseable_swaps']:
            print(f"\nUnparseable swaps: {len(self.stats['unparseable_swaps'])} transactions")
            print(f"  Examples: {', '.join(self.stats['unparseable_swaps'][:5])}")


def test_with_filters(wallet_address, logger):
    """Test fetching with type=SWAP filter"""
    logger.log("\n🔍 Testing WITH type=SWAP filter...")
    
    url = f"https://api.helius.xyz/v0/addresses/{wallet_address}/transactions"
    params = {
        "api-key": HELIUS_KEY,
        "limit": 100,
        "type": "SWAP"  # Server-side filter
    }
    
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        transactions = response.json()
        
        logger.log(f"  Fetched {len(transactions)} SWAP transactions")
        
        for tx in transactions:
            logger.analyze_transaction(tx)
            
        return len(transactions)
        
    except Exception as e:
        logger.log(f"  ❌ Error: {e}")
        return 0


def test_without_filters(wallet_address, logger):
    """Test fetching ALL transactions"""
    logger.log("\n🔍 Testing WITHOUT filters (ALL transactions)...")
    
    url = f"https://api.helius.xyz/v0/addresses/{wallet_address}/transactions"
    params = {
        "api-key": HELIUS_KEY,
        "limit": 100
        # No type filter
    }
    
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        transactions = response.json()
        
        logger.log(f"  Fetched {len(transactions)} total transactions")
        
        swap_count = 0
        for tx in transactions:
            if tx.get('type') == 'SWAP' or tx.get('events', {}).get('swap'):
                swap_count += 1
                
        logger.log(f"  Found {swap_count} swap transactions")
        
        return swap_count
        
    except Exception as e:
        logger.log(f"  ❌ Error: {e}")
        return 0


def test_completeness(wallet_address, logger):
    """Test completeness using getSignaturesForAddress"""
    logger.log("\n🔍 Testing completeness with signatures endpoint...")
    
    # Get signatures using standard RPC
    rpc_url = f"https://api.helius.xyz/v0/rpc"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [
            wallet_address,
            {"limit": 100}
        ]
    }
    
    try:
        response = requests.post(
            f"{rpc_url}?api-key={HELIUS_KEY}",
            json=payload,
            headers=headers,
            timeout=20
        )
        result = response.json()
        
        if 'result' in result:
            signature_count = len(result['result'])
            logger.log(f"  Found {signature_count} signatures via RPC")
            
            # Count how many are likely swaps based on success status
            successful = sum(1 for sig in result['result'] if sig.get('err') is None)
            logger.log(f"  Successful transactions: {successful}")
            
            return signature_count
        else:
            logger.log(f"  ❌ RPC Error: {result.get('error', 'Unknown error')}")
            return 0
            
    except Exception as e:
        logger.log(f"  ❌ Error: {e}")
        return 0


def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_helius_v4.py <wallet_address>")
        sys.exit(1)
        
    wallet = sys.argv[1]
    logger = DebugLogger()
    
    print(f"🔍 Debugging Helius API for wallet: {wallet}")
    print("="*60)
    
    # Test 1: With filters
    filtered_count = test_with_filters(wallet, logger)
    time.sleep(0.5)
    
    # Test 2: Without filters
    all_count = test_without_filters(wallet, logger)
    time.sleep(0.5)
    
    # Test 3: Completeness check
    signature_count = test_completeness(wallet, logger)
    
    # Print summary
    logger.print_summary()
    
    # Final analysis
    print("\n" + "="*60)
    print("KEY FINDINGS:")
    print("="*60)
    
    if filtered_count < all_count:
        print(f"⚠️  Filter might miss swaps: {filtered_count} with filter vs {all_count} without")
    else:
        print(f"✅ Filter appears complete: {filtered_count} swaps found")
        
    if logger.stats['has_inner_swaps'] > 0:
        percentage = logger.stats['has_inner_swaps'] / max(1, logger.stats['has_swap_event']) * 100
        print(f"⚠️  {percentage:.1f}% of swaps have innerSwaps array (multi-hop trades)")
        print(f"   Current code would miss {logger.stats['multi_hop_swaps']} multi-hop transactions!")
    else:
        print("✅ No multi-hop swaps detected")
        
    if logger.stats['missing_swap_event'] > 0:
        print(f"⚠️  {logger.stats['missing_swap_event']} transactions marked as SWAP but missing swap event")
        
    # Save detailed debug data
    debug_file = f"{wallet[:8]}_debug_v4.json"
    with open(debug_file, 'w') as f:
        json.dump(logger.stats, f, indent=2)
    print(f"\n📄 Detailed stats saved to: {debug_file}")


if __name__ == "__main__":
    main() 