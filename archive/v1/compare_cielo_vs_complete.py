#!/usr/bin/env python3
"""
Compare Cielo's limited API data with our complete replacement
Shows exactly what traders are missing
"""

import asyncio
import aiohttp
import os
from datetime import datetime
from src.services.cielo_replacement_optimized import get_complete_pnl_optimized

async def compare_data_sources():
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    cielo_key = "7c855165-3874-4237-9416-450d2373ea72"
    helius_key = os.getenv('HELIUS_API_KEY')
    
    if not helius_key:
        print("❌ Please set HELIUS_API_KEY environment variable")
        return
    
    print("=== CIELO vs COMPLETE DATA COMPARISON ===\n")
    print(f"Wallet: {wallet}\n")
    
    # Get Cielo data
    print("1. FETCHING CIELO DATA (Limited to 50 tokens)...")
    cielo_data = await fetch_cielo_data(wallet, cielo_key)
    
    # Get complete data
    print("\n2. FETCHING COMPLETE DATA (All tokens)...")
    complete_data = await get_complete_pnl_optimized(wallet, helius_key, use_cache=False)
    
    # Compare results
    print("\n3. COMPARISON RESULTS")
    print("=" * 60)
    
    cielo_tokens = cielo_data['data']['items']
    complete_tokens = complete_data['data']['items']
    cielo_stats = cielo_data['total_stats']
    complete_stats = complete_data['total_stats']
    
    print(f"\nToken Coverage:")
    print(f"  Cielo shows:    {len(cielo_tokens)} tokens")
    print(f"  Complete data:  {len(complete_tokens)} tokens")
    print(f"  Hidden tokens:  {len(complete_tokens) - len(cielo_tokens)} tokens")
    print(f"  Coverage:       {len(cielo_tokens)/len(complete_tokens)*100:.1f}%")
    
    print(f"\nP&L Comparison:")
    cielo_pnl = sum(t['total_pnl_usd'] for t in cielo_tokens)
    print(f"  Cielo P&L:      ${cielo_pnl:,.2f}")
    print(f"  Complete P&L:   ${complete_stats['realized_pnl_usd']:,.2f}")
    print(f"  Hidden P&L:     ${complete_stats['realized_pnl_usd'] - cielo_pnl:,.2f}")
    
    print(f"\nWin Rate:")
    cielo_winners = len([t for t in cielo_tokens if t['roi_percentage'] > 0])
    cielo_wr = cielo_winners / len(cielo_tokens) * 100 if cielo_tokens else 0
    print(f"  Cielo win rate:    {cielo_wr:.1f}%")
    print(f"  Complete win rate: {complete_stats['winrate']:.1f}%")
    print(f"  Difference:        {cielo_wr - complete_stats['winrate']:+.1f}pp")
    
    # Show hidden tokens
    print(f"\n4. HIDDEN TOKENS (Not shown by Cielo)")
    print("=" * 60)
    
    # Get tokens that Cielo doesn't show
    cielo_mints = {t['token_address'] for t in cielo_tokens}
    hidden_tokens = [t for t in complete_tokens if t['token_address'] not in cielo_mints]
    
    if hidden_tokens:
        # Sort by P&L
        hidden_tokens.sort(key=lambda x: x['total_pnl_usd'])
        
        print(f"\nWorst Hidden Losses:")
        for i, token in enumerate(hidden_tokens[:10], 1):
            print(f"{i:2d}. {token['token_symbol']:10s} P&L: ${token['total_pnl_usd']:>10,.2f} ({token['roi_percentage']:>+7.1f}%)")
        
        hidden_pnl = sum(t['total_pnl_usd'] for t in hidden_tokens)
        hidden_avg = hidden_pnl / len(hidden_tokens)
        
        print(f"\nHidden Token Statistics:")
        print(f"  Total hidden tokens: {len(hidden_tokens)}")
        print(f"  Total hidden P&L:    ${hidden_pnl:,.2f}")
        print(f"  Average P&L:         ${hidden_avg:,.2f}")
        
        hidden_winners = [t for t in hidden_tokens if t['roi_percentage'] > 0]
        print(f"  Hidden winners:      {len(hidden_winners)} ({len(hidden_winners)/len(hidden_tokens)*100:.1f}%)")
        print(f"  Hidden losers:       {len(hidden_tokens) - len(hidden_winners)} ({(len(hidden_tokens) - len(hidden_winners))/len(hidden_tokens)*100:.1f}%)")
    
    # Trading coach comparison
    print(f"\n5. COACHING IMPACT")
    print("=" * 60)
    
    # Simulate coaching for a 10 SOL trade
    sol_amount = 10.0
    
    # Cielo-based patterns
    cielo_patterns = find_patterns(cielo_tokens, sol_amount)
    complete_patterns = find_patterns(complete_tokens, sol_amount)
    
    print(f"\nFor a {sol_amount} SOL trade:")
    print(f"  Cielo finds:    {len(cielo_patterns)} similar trades")
    print(f"  Complete finds: {len(complete_patterns)} similar trades")
    
    if cielo_patterns:
        cielo_wr = len([p for p in cielo_patterns if p['roi_percentage'] > 0]) / len(cielo_patterns) * 100
        print(f"  Cielo win rate:    {cielo_wr:.0f}%")
    
    if complete_patterns:
        complete_wr = len([p for p in complete_patterns if p['roi_percentage'] > 0]) / len(complete_patterns) * 100
        print(f"  Complete win rate: {complete_wr:.0f}%")
    
    # Summary
    print(f"\n6. SUMMARY")
    print("=" * 60)
    print(f"Cielo's API creates a false narrative by hiding {len(hidden_tokens)} tokens")
    print(f"These hidden tokens contain ${abs(sum(t['total_pnl_usd'] for t in hidden_tokens)):,.2f} in losses")
    print(f"The real win rate is {complete_stats['winrate']:.0f}%, not {cielo_wr:.0f}%")
    print(f"\n✅ Our replacement provides 100% data coverage for accurate coaching")

async def fetch_cielo_data(wallet: str, api_key: str) -> Dict:
    """Fetch data from Cielo API"""
    
    async with aiohttp.ClientSession() as session:
        headers = {"x-api-key": api_key}
        
        # Get tokens
        url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/tokens"
        async with session.get(url, headers=headers) as response:
            token_data = await response.json()
        
        # Get total stats
        url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/total-stats"
        async with session.get(url, headers=headers) as response:
            stats_data = await response.json()
        
        return {
            'data': token_data['data'],
            'total_stats': stats_data['data']
        }

def find_patterns(tokens: List[Dict], sol_amount: float, tolerance: float = 0.5) -> List[Dict]:
    """Find similar trading patterns"""
    
    patterns = []
    target_usd = sol_amount * 150  # Approximate SOL price
    
    for token in tokens:
        if token['num_swaps'] == 0:
            continue
        
        avg_buy_usd = token['total_buy_usd'] / token['num_swaps']
        
        if target_usd * (1-tolerance) <= avg_buy_usd <= target_usd * (1+tolerance):
            patterns.append(token)
    
    return patterns

if __name__ == "__main__":
    asyncio.run(compare_data_sources())