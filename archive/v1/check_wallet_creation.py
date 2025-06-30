#!/usr/bin/env python3
"""Check when this wallet was actually created"""

import requests
import os
from datetime import datetime

wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
api_key = os.getenv('HELIUS_KEY')

print(f"Checking wallet: {wallet}\n")

# Get the very first transaction
url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"

# Get oldest transactions first
params = {
    "api-key": api_key,
    "limit": 100
}

all_transactions = []
before = None

# Fetch all to find the oldest
print("Fetching all transactions to find wallet creation...")
while True:
    if before:
        params["before"] = before
    
    response = requests.get(url, params=params)
    if response.status_code != 200:
        break
        
    data = response.json()
    if not data:
        break
        
    all_transactions.extend(data)
    print(f"  Fetched {len(all_transactions)} transactions...")
    
    # For the last batch, check if we should continue
    if len(data) < 100:
        break
        
    before = data[-1]['signature']

if all_transactions:
    # Find the oldest transaction
    oldest_tx = min(all_transactions, key=lambda x: x['timestamp'])
    oldest_time = datetime.fromtimestamp(oldest_tx['timestamp'])
    
    newest_tx = max(all_transactions, key=lambda x: x['timestamp'])
    newest_time = datetime.fromtimestamp(newest_tx['timestamp'])
    
    print(f"\n✅ Wallet Creation: {oldest_time}")
    print(f"📅 Latest Activity: {newest_time}")
    print(f"⏱️  Active for: {(newest_time - oldest_time).days} days")
    print(f"📊 Total transactions: {len(all_transactions)}")
    
    # Count transaction types
    tx_types = {}
    for tx in all_transactions:
        tx_type = tx.get('type', 'UNKNOWN')
        tx_types[tx_type] = tx_types.get(tx_type, 0) + 1
    
    print(f"\nTransaction breakdown:")
    for tx_type, count in sorted(tx_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {tx_type}: {count}")
    
    print(f"\n💡 This wallet has only been active since {oldest_time.strftime('%B %d, %Y')}")
    print(f"   Cielo might be showing data from:")
    print(f"   - A different wallet you used before")
    print(f"   - Aggregated data across multiple wallets")
    print(f"   - Historical data that predates this wallet")