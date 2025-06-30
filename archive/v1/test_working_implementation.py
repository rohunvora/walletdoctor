#!/usr/bin/env python3
"""
Test the working Cielo replacement
"""

import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from src.services.cielo_replacement_working import get_complete_pnl_working

async def test_wallet(wallet: str):
    """Test a single wallet"""
    
    print(f"\n{'='*60}")
    print(f"Testing: {wallet}")
    print(f"{'='*60}")
    
    try:
        result = await get_complete_pnl_working(wallet)
        
        tokens = result['data']['items']
        stats = result['total_stats']
        metadata = result['metadata']
        
        print(f"\n✅ SUCCESS")
        print(f"Tokens found: {len(tokens)}")
        print(f"Total P&L: ${stats['realized_pnl_usd']:,.2f}")
        print(f"Win rate: {stats['winrate']:.1f}%")
        print(f"Total buy volume: ${stats['total_buy_usd']:,.2f}")
        print(f"API calls: {metadata['api_calls']}")
        print(f"Time taken: {metadata['elapsed_seconds']:.1f}s")
        
        if tokens:
            print(f"\nTop 5 tokens by P&L:")
            for i, token in enumerate(tokens[:5], 1):
                print(f"{i}. {token['token_symbol']:10s} ${token['total_pnl_usd']:>10,.2f} ({token['roi_percentage']:>+7.1f}%)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    wallets = [
        "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
        "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2", 
        "215nhcAHjQQGgwpQSJQ7zR26etbjjtVdW74NLzwEgQjP"
    ]
    
    print("=== WORKING CIELO REPLACEMENT TEST ===")
    
    for wallet in wallets:
        await test_wallet(wallet)
        await asyncio.sleep(2)  # Rate limiting between wallets

if __name__ == "__main__":
    asyncio.run(main())