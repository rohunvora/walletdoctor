#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
import asyncio
import aiohttp
import json
from datetime import datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.services.cielo_replacement_complete import CompleteCieloReplacement

load_dotenv()

CIELO_API_KEY = os.getenv("CIELO_KEY")
if not CIELO_API_KEY:
    print("Error: CIELO_KEY not found in .env")
    sys.exit(1)

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

async def fetch_cielo_data(wallet_address):
    """Fetch data from Cielo API"""
    headers = {
        "X-API-KEY": CIELO_API_KEY,
        "accept": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        url = f"https://api.cielo.finance/v1/portfolio/holdings/{wallet_address}?mint=So11111111111111111111111111111111111111112"
        
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    print(f"Cielo API error for {wallet_address}: {response.status}")
                    return None
        except Exception as e:
            print(f"Error fetching Cielo data for {wallet_address}: {e}")
            return None

async def test_wallet(wallet_address):
    """Test a single wallet - compare Cielo vs our replacement"""
    print(f"\n{'='*80}")
    print(f"Testing wallet: {wallet_address}")
    print(f"{'='*80}")
    
    # Fetch from Cielo
    print("\n1. Fetching from Cielo API...")
    cielo_data = await fetch_cielo_data(wallet_address)
    
    if cielo_data and cielo_data.get("data"):
        cielo_tokens = len(cielo_data["data"])
        cielo_total_pnl = sum(float(t.get("totalPnl", 0)) for t in cielo_data["data"])
        cielo_total_invested = sum(float(t.get("totalInvested", 0)) for t in cielo_data["data"])
        
        print(f"   - Tokens shown: {cielo_tokens}")
        print(f"   - Total P&L shown: ${cielo_total_pnl:,.2f}")
        print(f"   - Total invested: ${cielo_total_invested:,.2f}")
        
        # Show top 5 tokens
        print("\n   Top 5 tokens by P&L:")
        sorted_tokens = sorted(cielo_data["data"], key=lambda x: float(x.get("totalPnl", 0)), reverse=True)
        for i, token in enumerate(sorted_tokens[:5]):
            print(f"   {i+1}. {token['tokenSymbol']}: ${float(token['totalPnl']):,.2f}")
    else:
        print("   - No data from Cielo API")
        cielo_tokens = 0
        cielo_total_pnl = 0
    
    # Fetch from our replacement
    print("\n2. Fetching from our replacement (complete data)...")
    service = CompleteCieloReplacement(HELIUS_API_KEY)
    
    try:
        complete_data = await service.get_all_token_pnl(wallet_address)
        
        if complete_data and complete_data.get("data"):
            our_tokens = len(complete_data["data"])
            our_total_pnl = sum(float(t.get("totalPnl", 0)) for t in complete_data["data"])
            our_total_invested = sum(float(t.get("totalInvested", 0)) for t in complete_data["data"])
            
            print(f"   - Tokens found: {our_tokens}")
            print(f"   - Total P&L actual: ${our_total_pnl:,.2f}")
            print(f"   - Total invested: ${our_total_invested:,.2f}")
            
            # Show top 5 tokens
            print("\n   Top 5 tokens by P&L:")
            sorted_tokens = sorted(complete_data["data"], key=lambda x: float(x.get("totalPnl", 0)), reverse=True)
            for i, token in enumerate(sorted_tokens[:5]):
                print(f"   {i+1}. {token['tokenSymbol']}: ${float(token['totalPnl']):,.2f}")
            
            # Show comparison
            print(f"\n3. Comparison:")
            print(f"   - Hidden tokens: {our_tokens - cielo_tokens} ({(our_tokens - cielo_tokens) / our_tokens * 100:.1f}% of all tokens)")
            print(f"   - Hidden P&L: ${our_total_pnl - cielo_total_pnl:,.2f}")
            print(f"   - Cielo shows: {cielo_tokens}/{our_tokens} tokens")
            
            # Show some hidden losers if any
            if our_tokens > cielo_tokens:
                cielo_mints = {t["tokenMint"] for t in cielo_data.get("data", [])}
                hidden_tokens = [t for t in complete_data["data"] if t["tokenMint"] not in cielo_mints]
                hidden_losers = sorted([t for t in hidden_tokens if float(t["totalPnl"]) < 0], 
                                     key=lambda x: float(x["totalPnl"]))
                
                if hidden_losers:
                    print(f"\n   Hidden losses (top 5):")
                    for i, token in enumerate(hidden_losers[:5]):
                        print(f"   - {token['tokenSymbol']}: ${float(token['totalPnl']):,.2f}")
            
        else:
            print("   - No data from our replacement")
            
    except Exception as e:
        print(f"   - Error: {e}")
    
    # Show metadata if available
    if 'complete_data' in locals() and complete_data and complete_data.get("metadata"):
        meta = complete_data["metadata"]
        print(f"\n4. Data quality check:")
        print(f"   - Total transactions processed: {meta.get('total_transactions', 'N/A')}")
        print(f"   - Data completeness: {meta.get('data_completeness', 'N/A')}")

async def main():
    """Test all user wallets"""
    print("Cielo API vs Complete Data Comparison")
    print("=====================================")
    print(f"Testing {len(USER_WALLETS)} wallets...")
    
    for wallet in USER_WALLETS:
        await test_wallet(wallet)
        await asyncio.sleep(1)  # Rate limiting
    
    print(f"\n{'='*80}")
    print("Test complete!")

if __name__ == "__main__":
    asyncio.run(main())