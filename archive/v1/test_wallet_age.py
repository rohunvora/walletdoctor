#!/usr/bin/env python3
"""Quick test to check wallet age and transaction count"""

import requests
import os
from datetime import datetime

wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
api_key = os.getenv('HELIUS_KEY')

if not api_key:
    print("No API key")
    exit(1)

# Get first page to check newest
url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
response = requests.get(url, params={"api-key": api_key, "limit": 10})

if response.status_code == 200:
    data = response.json()
    if data:
        newest = datetime.fromtimestamp(data[0]['timestamp'])
        print(f"Newest transaction: {newest}")

# Get transactions with large limit to see how far back we can go quickly
response = requests.get(url, params={"api-key": api_key, "limit": 100})

if response.status_code == 200:
    data = response.json()
    print(f"\nGot {len(data)} transactions in one request")
    
    if data:
        oldest = min(tx['timestamp'] for tx in data)
        newest = max(tx['timestamp'] for tx in data)
        
        oldest_date = datetime.fromtimestamp(oldest)
        newest_date = datetime.fromtimestamp(newest)
        
        print(f"Date range: {oldest_date} to {newest_date}")
        print(f"Days: {(newest_date - oldest_date).days}")
        
        # Count unique tokens
        tokens = set()
        swaps = 0
        for tx in data:
            if 'SWAP' in tx.get('type', ''):
                swaps += 1
            for transfer in tx.get('tokenTransfers', []):
                mint = transfer.get('mint', '')
                if mint and mint != 'So11111111111111111111111111111111111111112':
                    tokens.add(mint)
        
        print(f"Swaps: {swaps}")
        print(f"Unique tokens in these {len(data)} txs: {len(tokens)}")
        
        # Check if this is a new wallet
        days_old = (datetime.now() - oldest_date).days
        print(f"\nWallet age: ~{days_old} days")
        
        if days_old < 30:
            print("⚠️  This wallet is less than 30 days old!")
            print("That might explain why we only see 7 tokens instead of 135")
else:
    print(f"Error: {response.status_code}")
    print(response.text[:200])