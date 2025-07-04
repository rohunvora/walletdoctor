#!/usr/bin/env python3
"""
Demo script for TRD-002: Trade Value Enrichment

Shows how the enriched trades endpoint works with the new fields.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import requests
import json
from decimal import Decimal


def test_trade_enrichment():
    """Test trade enrichment with v0.7.1 schema"""
    
    # Configuration
    api_url = "https://web-production-2bb2f.up.railway.app"
    api_key = "wd_test1234567890abcdef1234567890ab"
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    print("=== TRD-002 Trade Enrichment Demo ===\n")
    
    # First, fetch with v0.7.0 (no enrichment)
    print("1. Fetching with v0.7.0 schema (original)...")
    response = requests.get(
        f"{api_url}/v4/trades/export-gpt/{wallet}",
        headers={"X-Api-Key": api_key},
        params={"schema_version": "v0.7.0"}
    )
    
    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return
    
    data_v070 = response.json()
    print(f"   Schema: {data_v070.get('schema_version', 'unknown')}")
    print(f"   Trades: {len(data_v070.get('trades', []))}")
    
    # Check a sample trade
    if data_v070.get('trades'):
        sample = data_v070['trades'][0]
        print(f"   Sample trade:")
        print(f"     Action: {sample.get('action')}")
        print(f"     price_usd: {sample.get('price_usd')}")
        print(f"     value_usd: {sample.get('value_usd')}")
        print(f"     pnl_usd: {sample.get('pnl_usd')}")
    
    # Now fetch with v0.7.1 (with enrichment if enabled)
    print("\n2. Fetching with v0.7.1-trades-value schema (enriched)...")
    response = requests.get(
        f"{api_url}/v4/trades/export-gpt/{wallet}",
        headers={"X-Api-Key": api_key},
        params={"schema_version": "v0.7.1-trades-value"}
    )
    
    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return
    
    data_v071 = response.json()
    print(f"   Schema: {data_v071.get('schema_version', 'unknown')}")
    print(f"   Trades: {len(data_v071.get('trades', []))}")
    
    # Analyze enriched trades
    trades = data_v071.get('trades', [])
    if trades:
        # Count enriched trades
        enriched_count = sum(1 for t in trades if t.get('price_usd') is not None)
        coverage = (enriched_count / len(trades)) * 100 if trades else 0
        
        print(f"\n3. Enrichment Analysis:")
        print(f"   Total trades: {len(trades)}")
        print(f"   Enriched trades: {enriched_count}")
        print(f"   Coverage: {coverage:.1f}%")
        
        # Find trades with P&L
        trades_with_pnl = [t for t in trades if t.get('pnl_usd') and Decimal(t['pnl_usd']) != 0]
        print(f"   Trades with P&L: {len(trades_with_pnl)}")
        
        # Show some enriched examples
        print(f"\n4. Sample Enriched Trades:")
        
        # Find a buy trade
        buy_trades = [t for t in trades if t.get('action') == 'buy' and t.get('price_usd')]
        if buy_trades:
            buy = buy_trades[0]
            print(f"\n   Buy Trade:")
            print(f"     Token: {buy.get('token')}")
            print(f"     Amount: {buy.get('amount')}")
            print(f"     price_sol: {buy.get('price_sol')}")
            print(f"     price_usd: {buy.get('price_usd')}")
            print(f"     value_usd: {buy.get('value_usd')}")
            
        # Find a sell trade with P&L
        if trades_with_pnl:
            sell = trades_with_pnl[0]
            print(f"\n   Sell Trade with P&L:")
            print(f"     Token: {sell.get('token')}")
            print(f"     Amount: {sell.get('amount')}")
            print(f"     price_usd: {sell.get('price_usd')}")
            print(f"     value_usd: {sell.get('value_usd')}")
            print(f"     pnl_usd: ${sell.get('pnl_usd')}")
            
            # Determine if profit or loss
            pnl = Decimal(sell.get('pnl_usd', '0'))
            if pnl > 0:
                print(f"     Result: PROFIT 🟢")
            else:
                print(f"     Result: LOSS 🔴")
    
    print("\n5. Feature Flag Status:")
    print("   Note: If all values are null, PRICE_ENRICH_TRADES may be disabled")
    print("   Enable with: PRICE_ENRICH_TRADES=true in Railway environment")


if __name__ == "__main__":
    test_trade_enrichment() 