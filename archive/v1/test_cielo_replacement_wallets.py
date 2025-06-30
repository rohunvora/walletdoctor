#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
import asyncio
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.services.cielo_replacement_complete import CompleteCieloReplacement

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

async def analyze_wallet(wallet_address):
    """Analyze a single wallet with our complete replacement"""
    print(f"\n{'='*80}")
    print(f"Analyzing wallet: {wallet_address}")
    print(f"{'='*80}")
    
    service = CompleteCieloReplacement(HELIUS_API_KEY)
    
    try:
        print("\nFetching complete trading history...")
        data = await service.get_all_token_pnl(wallet_address)
        
        if data and data.get("data") and data["data"].get("items"):
            tokens = data["data"]["items"]
            print(f"\n✓ Found {len(tokens)} tokens traded")
            
            # Calculate totals
            total_pnl = sum(float(t.get("total_pnl_usd", 0)) for t in tokens)
            total_invested = sum(float(t.get("total_buy_usd", 0)) for t in tokens)
            profitable_tokens = sum(1 for t in tokens if float(t.get("total_pnl_usd", 0)) > 0)
            losing_tokens = sum(1 for t in tokens if float(t.get("total_pnl_usd", 0)) < 0)
            
            print(f"\n📊 Portfolio Summary:")
            print(f"   Total P&L: ${total_pnl:,.2f}")
            print(f"   Total Invested: ${total_invested:,.2f}")
            print(f"   Win Rate: {profitable_tokens}/{len(tokens)} ({profitable_tokens/len(tokens)*100:.1f}%)")
            print(f"   Profitable tokens: {profitable_tokens}")
            print(f"   Losing tokens: {losing_tokens}")
            
            # Top winners
            print(f"\n💰 Top 5 Winners:")
            winners = sorted(tokens, key=lambda x: float(x.get("total_pnl_usd", 0)), reverse=True)[:5]
            for i, token in enumerate(winners):
                pnl = float(token.get("total_pnl_usd", 0))
                symbol = token.get("token_symbol", "Unknown")
                roi = float(token.get("roi_percentage", 0))
                print(f"   {i+1}. {symbol}: ${pnl:,.2f} ({roi:.1f}% ROI)")
            
            # Top losers
            print(f"\n💸 Top 5 Losers:")
            losers = sorted(tokens, key=lambda x: float(x.get("total_pnl_usd", 0)))[:5]
            for i, token in enumerate(losers):
                pnl = float(token.get("total_pnl_usd", 0))
                symbol = token.get("token_symbol", "Unknown")
                roi = float(token.get("roi_percentage", 0))
                print(f"   {i+1}. {symbol}: ${pnl:,.2f} ({roi:.1f}% ROI)")
            
            # Current holdings
            holdings = [t for t in tokens if float(t.get("holding_amount", 0)) > 0]
            if holdings:
                print(f"\n📈 Current Holdings ({len(holdings)} tokens):")
                holdings_sorted = sorted(holdings, key=lambda x: float(x.get("holding_amount_usd", 0)), reverse=True)[:5]
                for token in holdings_sorted:
                    symbol = token.get("token_symbol", "Unknown")
                    value = float(token.get("holding_amount_usd", 0))
                    unrealized_pnl = float(token.get("unrealized_pnl_usd", 0))
                    print(f"   - {symbol}: ${value:,.2f} (Unrealized P&L: ${unrealized_pnl:,.2f})")
            
            # Metadata
            if data.get("metadata"):
                meta = data["metadata"]
                print(f"\n📋 Data Quality:")
                print(f"   Total transactions: {meta.get('total_transactions', 'N/A')}")
                print(f"   Data completeness: {meta.get('data_completeness', 'N/A')}")
                
        else:
            print("\n❌ No trading data found for this wallet")
            
    except Exception as e:
        print(f"\n❌ Error analyzing wallet: {e}")

async def main():
    """Analyze all user wallets"""
    print("Complete Wallet Analysis using Cielo Replacement")
    print("===============================================")
    print(f"Analyzing {len(USER_WALLETS)} wallets...\n")
    
    for wallet in USER_WALLETS:
        await analyze_wallet(wallet)
        await asyncio.sleep(1)  # Rate limiting
    
    print(f"\n{'='*80}")
    print("Analysis complete!")

if __name__ == "__main__":
    asyncio.run(main())