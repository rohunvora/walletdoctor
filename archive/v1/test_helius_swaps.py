#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
import asyncio
import aiohttp
from collections import defaultdict

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

async def analyze_wallet_swaps(wallet):
    """Analyze swaps for a wallet using Helius API"""
    print(f"\n{'='*70}")
    print(f"Analyzing swaps for: {wallet}")
    print(f"{'='*70}")
    
    async with aiohttp.ClientSession() as session:
        # Fetch parsed transactions
        url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
        params = {
            "api-key": HELIUS_API_KEY,
            "limit": 100,
            "type": "SWAP"
        }
        
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    swaps = await response.json()
                    print(f"\n✓ Found {len(swaps)} recent swaps")
                    
                    if swaps:
                        # Analyze swap data
                        token_stats = defaultdict(lambda: {"buy_count": 0, "sell_count": 0, "buy_sol": 0, "sell_sol": 0})
                        
                        for swap in swaps:
                            # Parse swap details
                            description = swap.get('description', '')
                            native_transfers = swap.get('nativeTransfers', [])
                            token_transfers = swap.get('tokenTransfers', [])
                            
                            # Simple analysis based on description
                            if 'swapped' in description.lower():
                                parts = description.split(' ')
                                if len(parts) >= 6:  # Basic format: "wallet swapped X TOKEN1 for Y TOKEN2"
                                    token_from = parts[3] if len(parts) > 3 else "Unknown"
                                    token_to = parts[6] if len(parts) > 6 else "Unknown"
                                    
                                    # Count swaps
                                    if token_from == "SOL":
                                        token_stats[token_to]["buy_count"] += 1
                                    elif token_to == "SOL":
                                        token_stats[token_from]["sell_count"] += 1
                        
                        # Show summary
                        print("\n📊 Token Activity Summary:")
                        active_tokens = [(token, stats) for token, stats in token_stats.items() 
                                       if stats["buy_count"] > 0 or stats["sell_count"] > 0]
                        
                        for token, stats in sorted(active_tokens, key=lambda x: x[1]["buy_count"] + x[1]["sell_count"], reverse=True)[:10]:
                            total_trades = stats["buy_count"] + stats["sell_count"]
                            print(f"   {token}: {total_trades} trades (Buys: {stats['buy_count']}, Sells: {stats['sell_count']})")
                        
                        # Show recent swaps
                        print("\n📈 Recent Swaps (last 5):")
                        for i, swap in enumerate(swaps[:5]):
                            desc = swap.get('description', 'No description')
                            timestamp = swap.get('timestamp', 0)
                            signature = swap.get('signature', '')[:8] + "..."
                            print(f"   {i+1}. {desc}")
                            print(f"      Signature: {signature}")
                    
                else:
                    error_text = await response.text()
                    print(f"✗ API Error {response.status}: {error_text}")
                    
        except Exception as e:
            print(f"✗ Error: {e}")

async def main():
    print("Helius Swap Analysis")
    print("===================")
    print(f"Analyzing {len(USER_WALLETS)} wallets...\n")
    
    for wallet in USER_WALLETS:
        await analyze_wallet_swaps(wallet)
        await asyncio.sleep(0.5)  # Rate limiting
    
    print(f"\n{'='*70}")
    print("Analysis complete!")
    print("\nNote: The Cielo replacement would provide more detailed P&L analysis")
    print("by calculating exact buy/sell amounts and current token prices.")

if __name__ == "__main__":
    asyncio.run(main())