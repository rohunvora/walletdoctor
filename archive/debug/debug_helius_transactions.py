#!/usr/bin/env python3
"""
Debug script to examine raw Helius transaction data and understand structure.
"""

import requests
import json
import sys
import os

HELIUS_KEY = os.getenv("HELIUS_KEY")

if not HELIUS_KEY:
    print("Error: HELIUS_KEY environment variable not set")
    sys.exit(1)

def fetch_transactions(wallet, limit=10):
    """Fetch a few transactions to examine their structure."""
    url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
    params = {
        "api-key": HELIUS_KEY,
        "limit": limit
    }
    
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error: {e}")
        return []

def analyze_transaction(tx):
    """Analyze a single transaction to understand its structure."""
    print(f"\n{'='*80}")
    print(f"Signature: {tx.get('signature', 'N/A')[:16]}...")
    print(f"Type: {tx.get('type', 'N/A')}")
    print(f"Source: {tx.get('source', 'N/A')}")
    print(f"Description: {tx.get('description', 'N/A')}")
    
    # Check for events
    events = tx.get('events', {})
    if events:
        print(f"\nEvents found: {list(events.keys())}")
        
        # Check for swap
        if 'swap' in events:
            swap = events['swap']
            print("\nSwap Details:")
            if swap.get('nativeInput'):
                print(f"  Native Input: {swap['nativeInput']['amount'] / 1e9:.4f} SOL")
            if swap.get('nativeOutput'):
                print(f"  Native Output: {swap['nativeOutput']['amount'] / 1e9:.4f} SOL")
            if swap.get('tokenInputs'):
                for ti in swap['tokenInputs']:
                    print(f"  Token Input: {ti['mint'][:8]}... Amount: {ti['rawTokenAmount']['tokenAmount']}")
            if swap.get('tokenOutputs'):
                for to in swap['tokenOutputs']:
                    print(f"  Token Output: {to['mint'][:8]}... Amount: {to['rawTokenAmount']['tokenAmount']}")
    
    # Check native transfers
    native_transfers = tx.get('nativeTransfers', [])
    if native_transfers:
        print(f"\nNative Transfers: {len(native_transfers)}")
        for nt in native_transfers[:2]:  # Show first 2
            print(f"  From: {nt['fromUserAccount'][:8]}... To: {nt['toUserAccount'][:8]}... Amount: {nt['amount'] / 1e9:.4f} SOL")
    
    # Check token transfers
    token_transfers = tx.get('tokenTransfers', [])
    if token_transfers:
        print(f"\nToken Transfers: {len(token_transfers)}")
        for tt in token_transfers[:2]:  # Show first 2
            print(f"  Token: {tt['mint'][:8]}... From: {tt['fromUserAccount'][:8]}... To: {tt['toUserAccount'][:8]}...")
    
    # Check instructions
    instructions = tx.get('instructions', [])
    if instructions:
        print(f"\nInstructions: {len(instructions)}")
        for inst in instructions[:3]:  # Show first 3
            print(f"  Program: {inst.get('programId', 'N/A')[:8]}... Name: {inst.get('innerInstructions', [{}])[0].get('name', 'N/A') if inst.get('innerInstructions') else 'N/A'}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_helius_transactions.py <wallet_address>")
        sys.exit(1)
    
    wallet = sys.argv[1]
    print(f"Fetching transactions for wallet: {wallet}")
    
    transactions = fetch_transactions(wallet, limit=20)
    
    if not transactions:
        print("No transactions found")
        return
    
    print(f"\nFound {len(transactions)} transactions")
    
    # Group by type and source
    type_counts = {}
    source_counts = {}
    swap_count = 0
    
    for tx in transactions:
        tx_type = tx.get('type', 'Unknown')
        tx_source = tx.get('source', 'Unknown')
        
        type_counts[tx_type] = type_counts.get(tx_type, 0) + 1
        source_counts[tx_source] = source_counts.get(tx_source, 0) + 1
        
        if 'swap' in tx.get('events', {}):
            swap_count += 1
    
    print(f"\nTransaction Types:")
    for tx_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {tx_type}: {count}")
    
    print(f"\nTransaction Sources:")
    for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {source}: {count}")
    
    print(f"\nTransactions with swap events: {swap_count}")
    
    # Show detailed analysis of first few transactions
    print(f"\n\nDetailed Analysis of First 5 Transactions:")
    for tx in transactions[:5]:
        analyze_transaction(tx)
    
    # Save full data for manual inspection
    output_file = f"{wallet[:8]}_debug.json"
    with open(output_file, 'w') as f:
        json.dump(transactions, f, indent=2)
    print(f"\n\nFull transaction data saved to {output_file}")

if __name__ == "__main__":
    main() 