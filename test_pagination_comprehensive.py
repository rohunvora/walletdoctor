#!/usr/bin/env python3
"""
Comprehensive test script for pagination approach to surface losers.
Tests different wallet types and provides clear logging.
"""

import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add scripts directory to path
sys.path.append('scripts')

from data import fetch_cielo_pnl_with_timeframe, fetch_cielo_pnl_stream_losers, fetch_cielo_aggregated_pnl

# Test wallets with different characteristics
TEST_WALLETS = {
    "Normal Trader": "rp8ntGS7P2k3faTvsRSWxQLa3B68DetNbwe1GHLiTUK",
    # Add more test wallets here as needed
    # "High Volume": "...",
    # "All Winners": "...",
}

def print_header(title: str):
    """Print a formatted header"""
    print(f"\n{'='*80}")
    print(f"🧪 {title}")
    print(f"{'='*80}\n")

def test_single_wallet(wallet_address: str, wallet_name: str = "Unknown"):
    """Test a single wallet comprehensively"""
    print_header(f"Testing: {wallet_name}")
    print(f"📍 Wallet: {wallet_address}")
    print(f"🕐 Time: {datetime.now()}\n")
    
    # First, get aggregated stats
    print("📊 Fetching aggregated stats...")
    agg_pnl = fetch_cielo_aggregated_pnl(wallet_address)
    
    if agg_pnl.get('status') == 'ok' and 'data' in agg_pnl:
        agg_data = agg_pnl['data']
        print(f"\n📈 Wallet Overview:")
        print(f"   - Tokens traded: {agg_data.get('tokens_traded', 'N/A')}")
        print(f"   - Win rate: {agg_data.get('winrate', 'N/A')}%")
        print(f"   - Realized PnL: ${agg_data.get('realized_pnl_usd', 0):,.0f}")
        print(f"   - Combined PnL: ${agg_data.get('combined_pnl_usd', 0):,.0f}")
    
    # Test individual timeframes
    print("\n🔬 Testing individual timeframes:")
    timeframes = ["max", "30d", "7d", "1d"]
    
    for tf in timeframes:
        print(f"\n--- Timeframe: {tf} (max 1 page) ---")
        start_time = time.time()
        data = fetch_cielo_pnl_with_timeframe(wallet_address, tf, max_pages=1)
        elapsed = time.time() - start_time
        
        if data.get('status') == 'ok':
            items = data['data']['items']
            losers = [item for item in items if item.get('total_pnl_usd', 0) < 0]
            winners = [item for item in items if item.get('total_pnl_usd', 0) > 0]
            
            print(f"   ⏱️  Time: {elapsed:.2f}s")
            print(f"   📊 Results: {len(winners)}W / {len(losers)}L (total: {len(items)})")
            
            if losers:
                print(f"   💔 First loser: {losers[0].get('token_symbol')} (${losers[0].get('total_pnl_usd', 0):,.0f})")
    
    # Test automatic loser detection
    print("\n🎯 Testing automatic loser detection:")
    start_time = time.time()
    data, timeframe_used = fetch_cielo_pnl_stream_losers(wallet_address)
    elapsed = time.time() - start_time
    
    print(f"\n⏱️  Total time: {elapsed:.2f}s")
    
    if data.get('status') == 'ok':
        items = data['data']['items']
        losers = [item for item in items if item.get('total_pnl_usd', 0) < 0]
        winners = [item for item in items if item.get('total_pnl_usd', 0) > 0]
        
        print(f"\n📊 Final Results:")
        print(f"   - Timeframe used: {timeframe_used}")
        print(f"   - Pages fetched: {data['data'].get('pages_fetched', 0)}")
        print(f"   - Total tokens: {len(items)}")
        print(f"   - Winners: {len(winners)}")
        print(f"   - Losers: {len(losers)}")
        
        if losers:
            print(f"\n💔 Top 5 Losers:")
            for i, loser in enumerate(losers[:5]):
                print(f"   {i+1}. {loser.get('token_symbol')}: ${loser.get('total_pnl_usd', 0):,.0f}")
        
        if timeframe_used != "max":
            print(f"\n⚠️  Note: Using {timeframe_used} timeframe - historical data truncated")
    
    print(f"\n✅ Test complete for {wallet_name}")

def main():
    """Run comprehensive tests"""
    # Check if API key is set
    if not os.getenv('CIELO_KEY'):
        print("❌ CIELO_KEY not set in .env file")
        sys.exit(1)
    
    print_header("COMPREHENSIVE PAGINATION TEST")
    print(f"🔑 API Key: {os.getenv('CIELO_KEY')[:8]}...")
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test each wallet
    for wallet_name, wallet_address in TEST_WALLETS.items():
        test_single_wallet(wallet_address, wallet_name)
        print("\n" + "-"*80)
    
    # Allow testing custom wallet from command line
    if len(sys.argv) > 1:
        custom_wallet = sys.argv[1]
        test_single_wallet(custom_wallet, "Custom Wallet")
    
    print("\n🎉 All tests complete!")
    print("\n💡 Tips for thorough testing:")
    print("   1. Test wallets with different trading patterns")
    print("   2. Watch for timeframe fallbacks (max → 30d → 7d)")
    print("   3. Check that losers are properly surfaced")
    print("   4. Monitor API call efficiency (pages fetched)")
    print("   5. Verify UI messages match the data fetched")

if __name__ == "__main__":
    main() 