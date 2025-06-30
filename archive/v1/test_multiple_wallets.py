#!/usr/bin/env python3
"""
Test the Cielo replacement with multiple wallets
"""

import asyncio
import os
import traceback
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.services.cielo_replacement_optimized import get_complete_pnl_optimized

async def test_wallet(wallet: str, helius_key: str):
    """Test a single wallet and report results"""
    
    print(f"\n{'='*70}")
    print(f"Testing wallet: {wallet}")
    print(f"{'='*70}")
    
    try:
        start_time = datetime.now()
        
        # Get complete data
        result = await get_complete_pnl_optimized(wallet, helius_key, use_cache=False)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        tokens = result['data']['items']
        total_stats = result['total_stats']
        
        print(f"\n✅ SUCCESS - Fetched in {elapsed:.1f}s")
        print(f"\nResults:")
        print(f"  Total tokens: {len(tokens)}")
        print(f"  Total P&L: ${total_stats['realized_pnl_usd']:,.2f}")
        print(f"  Win rate: {total_stats['winrate']:.1f}%")
        print(f"  Total swaps: {total_stats['total_swaps']}")
        
        # Show top winners and losers
        if tokens:
            print(f"\nTop 3 Winners:")
            winners = sorted(tokens, key=lambda x: x['total_pnl_usd'], reverse=True)[:3]
            for i, token in enumerate(winners, 1):
                print(f"  {i}. {token['token_symbol']:10s} ${token['total_pnl_usd']:>10,.2f} ({token['roi_percentage']:>+7.1f}%)")
            
            print(f"\nTop 3 Losers:")
            losers = sorted(tokens, key=lambda x: x['total_pnl_usd'])[:3]
            for i, token in enumerate(losers, 1):
                print(f"  {i}. {token['token_symbol']:10s} ${token['total_pnl_usd']:>10,.2f} ({token['roi_percentage']:>+7.1f}%)")
        
        return True, result
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        print(f"\nFull traceback:")
        traceback.print_exc()
        return False, str(e)

async def main():
    wallets = [
        "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
        "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2", 
        "215nhcAHjQQGgwpQSJQ7zR26etbjjtVdW74NLzwEgQjP"
    ]
    
    helius_key = os.getenv('HELIUS_API_KEY') or os.getenv('HELIUS_KEY')
    if not helius_key:
        print("❌ Please set HELIUS_API_KEY or HELIUS_KEY environment variable")
        return
    
    print("=== TESTING CIELO REPLACEMENT WITH MULTIPLE WALLETS ===")
    print(f"Testing {len(wallets)} wallets...")
    
    results = []
    for wallet in wallets:
        success, data = await test_wallet(wallet, helius_key)
        results.append((wallet, success, data))
    
    # Summary
    print(f"\n\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    
    successful = sum(1 for _, success, _ in results if success)
    print(f"\nSuccess rate: {successful}/{len(wallets)} wallets")
    
    for wallet, success, data in results:
        status = "✅" if success else "❌"
        print(f"\n{status} {wallet}")
        if success and isinstance(data, dict):
            stats = data['total_stats']
            print(f"   - Tokens: {stats['tokens_traded']}")
            print(f"   - P&L: ${stats['realized_pnl_usd']:,.2f}")
            print(f"   - Win rate: {stats['winrate']:.1f}%")
        else:
            print(f"   - Error: {data}")

if __name__ == "__main__":
    asyncio.run(main())