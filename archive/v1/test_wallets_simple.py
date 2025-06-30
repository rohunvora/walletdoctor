#!/usr/bin/env python3
"""
Simple test of Cielo replacement with rate limiting
"""

import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.services.cielo_replacement_fixed import get_complete_pnl_safe

async def test_single_wallet(wallet: str):
    """Test a single wallet"""
    
    print(f"\nTesting wallet: {wallet[:8]}...")
    
    try:
        start = datetime.now()
        result = await get_complete_pnl_safe(wallet)
        elapsed = (datetime.now() - start).total_seconds()
        
        tokens = result['data']['items']
        stats = result['total_stats']
        
        print(f"✅ Success in {elapsed:.1f}s")
        print(f"   Tokens: {len(tokens)}")
        print(f"   P&L: ${stats['realized_pnl_usd']:,.2f}")
        print(f"   Win rate: {stats['winrate']:.1f}%")
        
        # Show top token if any
        if tokens:
            top = tokens[0]
            print(f"   Top token: {top['token_symbol']} (${top['total_pnl_usd']:,.2f})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

async def main():
    wallets = [
        "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
        "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2", 
        "215nhcAHjQQGgwpQSJQ7zR26etbjjtVdW74NLzwEgQjP"
    ]
    
    print("=== TESTING CIELO REPLACEMENT ===")
    print("Testing with rate limiting and error handling\n")
    
    # Test sequentially to avoid rate limits
    success_count = 0
    for wallet in wallets:
        if await test_single_wallet(wallet):
            success_count += 1
        # Wait between wallets
        await asyncio.sleep(2)
    
    print(f"\n✅ Completed: {success_count}/{len(wallets)} successful")

if __name__ == "__main__":
    asyncio.run(main())