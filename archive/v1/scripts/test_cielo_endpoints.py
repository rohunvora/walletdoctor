#!/usr/bin/env python3
"""
Test all relevant Cielo Finance endpoints to understand what data is available
"""

import os
import asyncio
import aiohttp
import json
from datetime import datetime

WALLET = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
BASE_URL = "https://feed-api.cielo.finance/api/v1"

async def test_endpoint(session, endpoint_name, url, headers):
    """Test a single endpoint and return the response"""
    print(f"\n{'='*60}")
    print(f"Testing: {endpoint_name}")
    print(f"URL: {url}")
    
    try:
        async with session.get(url, headers=headers) as response:
            status = response.status
            data = await response.json()
            
            print(f"Status: {status}")
            
            if status == 200:
                # Pretty print the response structure
                if isinstance(data, dict):
                    print(f"Response keys: {list(data.keys())}")
                    
                    # Show sample data if it's a list
                    for key, value in data.items():
                        if isinstance(value, list) and len(value) > 0:
                            print(f"\n{key} (showing first item of {len(value)}):")
                            print(json.dumps(value[0], indent=2)[:500] + "...")
                        elif isinstance(value, dict):
                            print(f"\n{key}:")
                            print(json.dumps(value, indent=2)[:500] + "...")
                        else:
                            print(f"{key}: {value}")
                else:
                    print(f"Response type: {type(data)}")
                    print(json.dumps(data, indent=2)[:1000] + "...")
                    
                return {"endpoint": endpoint_name, "status": "success", "data": data}
            else:
                print(f"Error: {data}")
                return {"endpoint": endpoint_name, "status": "error", "error": data}
                
    except Exception as e:
        print(f"Exception: {str(e)}")
        return {"endpoint": endpoint_name, "status": "exception", "error": str(e)}

async def test_all_endpoints(api_key):
    """Test all relevant Cielo endpoints"""
    
    headers = {
        "accept": "application/json",
        "x-api-key": api_key  # Try x-api-key first
    }
    
    endpoints = [
        # Core wallet stats
        ("Trading Stats", f"{BASE_URL}/{WALLET}/trading-stats"),
        
        # PNL endpoints
        ("Token PNL", f"{BASE_URL}/{WALLET}/pnl/tokens"),
        ("Total PNL Stats", f"{BASE_URL}/{WALLET}/pnl/total-stats"),
        
        # Portfolio
        ("Wallet Portfolio", f"{BASE_URL}/{WALLET}/portfolio"),
        
        # Token specific (test with a known token if first endpoints work)
        # We'll add token-specific queries based on what we find
    ]
    
    results = []
    
    async with aiohttp.ClientSession() as session:
        # First, test with x-api-key header
        print("Testing with x-api-key header...")
        for name, url in endpoints:
            result = await test_endpoint(session, name, url, headers)
            results.append(result)
            
            # If we get auth error, try different header
            if result["status"] == "error" and "API Key" in str(result.get("error", "")):
                print("\nTrying with Authorization Bearer header...")
                alt_headers = {
                    "accept": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
                result = await test_endpoint(session, f"{name} (Bearer)", url, alt_headers)
                results.append(result)
    
    return results

def analyze_results(results):
    """Analyze what we can use from Cielo"""
    print("\n" + "="*60)
    print("ANALYSIS: What we can use from Cielo")
    print("="*60)
    
    successful = [r for r in results if r["status"] == "success"]
    
    if not successful:
        print("\n❌ No successful API calls. Check your API key.")
        return
    
    print(f"\n✅ Successfully accessed {len(successful)} endpoints")
    
    for result in successful:
        endpoint = result["endpoint"]
        data = result["data"]
        
        print(f"\n### {endpoint}")
        
        if "Trading Stats" in endpoint:
            print("Can provide:")
            print("- Overall ROI and win rate")
            print("- Total trades count")
            print("- Trading behavior metrics")
            
        elif "Token PNL" in endpoint:
            print("Can provide:")
            print("- Individual token P&L")
            print("- Token addresses traded")
            print("- Potentially trade details")
            
        elif "Portfolio" in endpoint:
            print("Can provide:")
            print("- Current holdings")
            print("- Token values")
            print("- Portfolio composition")
    
    print("\n" + "="*60)
    print("LIMITATIONS for Pattern Coaching")
    print("="*60)
    print("\nWhat Cielo likely CANNOT provide:")
    print("- Historical market cap at time of trade")
    print("- SOL amount per trade")
    print("- Trade-by-trade history with timestamps")
    print("- Pattern matching by market cap ranges")
    print("\nWhat we'd need to build ourselves:")
    print("- Pattern detection (similar mcap/SOL amounts)")
    print("- Historical market cap lookup")
    print("- Coaching message generation")

async def main():
    # Check for API key
    api_key = os.getenv('CIELO_API_KEY')
    
    if not api_key:
        print("❌ CIELO_API_KEY environment variable not found")
        print("\nTo test Cielo endpoints, please:")
        print("1. Get an API key from https://developer.cielo.finance")
        print("2. Set it: export CIELO_API_KEY='your-key-here'")
        print("3. Run this script again")
        return
    
    print("🔍 Testing Cielo Finance API Endpoints")
    print(f"Wallet: {WALLET}")
    print(f"API Key: {api_key[:10]}..." if len(api_key) > 10 else "***")
    
    # Test all endpoints
    results = await test_all_endpoints(api_key)
    
    # Analyze what we can use
    analyze_results(results)
    
    # Save results for reference
    with open('cielo_api_test_results.json', 'w') as f:
        json.dump({
            "wallet": WALLET,
            "timestamp": datetime.now().isoformat(),
            "results": results
        }, f, indent=2)
    
    print("\n💾 Full results saved to cielo_api_test_results.json")

if __name__ == "__main__":
    asyncio.run(main())