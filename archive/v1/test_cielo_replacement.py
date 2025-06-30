#!/usr/bin/env python3
"""
Test the complete Cielo API replacement
Shows how we can get ALL tokens, not just top 50
"""

import asyncio
import os
from datetime import datetime
from src.services.cielo_replacement import get_complete_token_pnl

async def test_replacement():
    print("=== CIELO API REPLACEMENT TEST ===\n")
    
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    # Get Helius API key
    helius_key = os.getenv('HELIUS_API_KEY')
    if not helius_key:
        print("❌ Please set HELIUS_API_KEY environment variable")
        return
    
    print(f"Fetching complete P&L data for wallet: {wallet[:8]}...")
    print("This will get ALL tokens, not just top 50\n")
    
    try:
        # Get complete data
        result = await get_complete_token_pnl(wallet, helius_key)
        
        tokens = result['data']['items']
        total_stats = result['total_stats']
        
        print(f"✅ Found {len(tokens)} total tokens (vs Cielo's 50)")
        print("\n=== TOTAL STATS (ALL TOKENS) ===")
        print(f"Tokens traded: {total_stats['tokens_traded']}")
        print(f"Total P&L: ${total_stats['realized_pnl_usd']:,.2f}")
        print(f"Win rate: {total_stats['winrate']:.1f}%")
        print(f"ROI: {total_stats['realized_roi_percentage']:.1f}%")
        print(f"Total buy volume: ${total_stats['total_buy_usd']:,.2f}")
        print(f"Total sell volume: ${total_stats['total_sell_usd']:,.2f}")
        
        # Show top winners
        print("\n=== TOP 10 WINNERS ===")
        winners = sorted(tokens, key=lambda x: x['total_pnl_usd'], reverse=True)[:10]
        for i, token in enumerate(winners, 1):
            print(f"{i}. {token['token_symbol']}: ${token['total_pnl_usd']:,.2f} ({token['roi_percentage']:+.1f}%)")
        
        # Show top losers
        print("\n=== TOP 10 LOSERS ===")
        losers = sorted(tokens, key=lambda x: x['total_pnl_usd'])[:10]
        for i, token in enumerate(losers, 1):
            print(f"{i}. {token['token_symbol']}: ${token['total_pnl_usd']:,.2f} ({token['roi_percentage']:+.1f}%)")
        
        # Show tokens 51-60 (that Cielo hides)
        print("\n=== TOKENS 51-60 (HIDDEN BY CIELO) ===")
        if len(tokens) > 50:
            for i in range(50, min(60, len(tokens))):
                token = tokens[i]
                print(f"{i+1}. {token['token_symbol']}: ${token['total_pnl_usd']:,.2f} ({token['roi_percentage']:+.1f}%)")
        
        # Compare with Cielo's limited view
        print("\n=== COMPARISON WITH CIELO ===")
        top_50_pnl = sum(t['total_pnl_usd'] for t in tokens[:50])
        hidden_pnl = total_stats['realized_pnl_usd'] - top_50_pnl
        
        print(f"Cielo shows (top 50): ${top_50_pnl:,.2f}")
        print(f"Hidden tokens: ${hidden_pnl:,.2f}")
        print(f"Reality (all tokens): ${total_stats['realized_pnl_usd']:,.2f}")
        
        # Save complete data for analysis
        output_file = f"complete_pnl_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        import json
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n✅ Complete data saved to: {output_file}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_replacement())