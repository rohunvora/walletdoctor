#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
import asyncio
import aiohttp

load_dotenv()

HELIUS_API_KEY = os.getenv("HELIUS_KEY")
if not HELIUS_API_KEY:
    print("Error: HELIUS_KEY not found in .env")
    sys.exit(1)

USER_WALLETS = [
    "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
    "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2", 
    "215nhcAHjQQGgwpQSJQ7zR26etbjjtVdW74NLzwEgQjP",
    "9xdv9Jt2ef3UmLPn8VLsSZ41Gr79Nj55nqjsekt5ASM"
]

async def check_wallet_activity(wallet):
    """Check if wallet has any transaction activity"""
    print(f"\n{'='*60}")
    print(f"Checking wallet: {wallet}")
    print(f"{'='*60}")
    
    async with aiohttp.ClientSession() as session:
        # Check basic transaction history
        url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
        params = {
            "api-key": HELIUS_API_KEY,
            "limit": 10
        }
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✓ Found {len(data)} recent transactions")
                    
                    # Show first few transaction types
                    for i, tx in enumerate(data[:3]):
                        tx_type = tx.get('type', 'Unknown')
                        description = tx.get('description', 'No description')
                        print(f"  {i+1}. {tx_type}: {description}")
                else:
                    print(f"✗ API Error {response.status}: {await response.text()}")
                    
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Try enhanced transactions endpoint
        print("\nChecking enhanced transactions...")
        url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
        params = {
            "api-key": HELIUS_API_KEY,
            "limit": 10,
            "type": "SWAP"
        }
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✓ Found {len(data)} swap transactions")
                else:
                    error_text = await response.text()
                    print(f"✗ API Error {response.status}: {error_text}")
                    
        except Exception as e:
            print(f"✗ Error: {e}")

async def main():
    print("Wallet Activity Check")
    print("====================")
    print(f"Testing {len(USER_WALLETS)} wallets with Helius API...\n")
    
    for wallet in USER_WALLETS:
        await check_wallet_activity(wallet)
        await asyncio.sleep(0.5)  # Rate limiting

if __name__ == "__main__":
    asyncio.run(main())