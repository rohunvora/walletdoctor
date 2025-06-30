#!/usr/bin/env python3
"""Test fetching complete trading history from Helius"""

import asyncio
import os
import aiohttp

async def test_helius_history():
    """Test fetching transaction history from Helius"""
    
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    helius_key = os.getenv('HELIUS_KEY')
    
    if not helius_key:
        print("❌ HELIUS_KEY not found in environment")
        return
    
    print(f"=== FETCHING COMPLETE HISTORY FOR {wallet[:8]}... ===\n")
    
    # Fetch recent transactions to test
    url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
    params = {
        "api-key": helius_key,
        "limit": 10,
        "type": "SWAP"  # Just swaps/trades
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                print(f"❌ Error: {response.status}")
                return
                
            data = await response.json()
            
            print(f"Found {len(data)} recent SWAP transactions")
            
            # Analyze the transactions
            unique_tokens = set()
            for tx in data:
                # Extract token info from swap
                if 'tokenTransfers' in tx:
                    for transfer in tx['tokenTransfers']:
                        if 'tokenAmount' in transfer and transfer['tokenAmount'] > 0:
                            mint = transfer.get('mint', 'Unknown')
                            unique_tokens.add(mint)
                
                # Show transaction details
                timestamp = tx.get('timestamp', 0)
                from datetime import datetime
                date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                print(f"\n{date}")
                print(f"  Signature: {tx['signature'][:20]}...")
                print(f"  Type: {tx.get('type', 'Unknown')}")
                
                if 'tokenTransfers' in tx:
                    for transfer in tx['tokenTransfers']:
                        amount = transfer.get('tokenAmount', 0)
                        mint = transfer.get('mint', 'Unknown')[:20]
                        from_addr = transfer.get('fromUserAccount', '')[:8]
                        to_addr = transfer.get('toUserAccount', '')[:8]
                        
                        if from_addr == wallet[:8]:
                            print(f"  → Sent {amount} of {mint}...")
                        elif to_addr == wallet[:8]:
                            print(f"  ← Received {amount} of {mint}...")
    
    print(f"\n\nUnique tokens in these {len(data)} transactions: {len(unique_tokens)}")
    print("\nTo get all 135 tokens, we need to:")
    print("1. Paginate through ALL historical transactions (not just recent)")
    print("2. Parse all SWAP transactions to extract tokens traded")
    print("3. Store this data in the diary for pattern matching")

if __name__ == "__main__":
    asyncio.run(test_helius_history())