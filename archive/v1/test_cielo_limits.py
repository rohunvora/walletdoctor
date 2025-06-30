#!/usr/bin/env python3
"""
Test Cielo API capabilities and rate limits before full implementation
"""

import asyncio
import os
import aiohttp
import time

async def test_cielo_api():
    api_key = os.getenv('CIELO_KEY')
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    print("=== TESTING CIELO API CAPABILITIES ===\n")
    
    async with aiohttp.ClientSession() as session:
        # Test 1: Basic wallet stats
        print("1. Testing wallet stats endpoint...")
        url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/total-stats"
        
        try:
            async with session.get(url, headers=headers) as response:
                print(f"   Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ Success! Total P&L: ${data.get('pnl', 0):,.2f}")
                else:
                    text = await response.text()
                    print(f"   ❌ Error: {text[:100]}")
        except Exception as e:
            print(f"   ❌ Exception: {e}")
        
        # Test 2: Token list
        print("\n2. Testing token list endpoint...")
        url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/tokens"
        
        try:
            start = time.time()
            async with session.get(url, headers=headers, params={'limit': 200}) as response:
                elapsed = time.time() - start
                print(f"   Status: {response.status} (took {elapsed:.2f}s)")
                
                if response.status == 200:
                    data = await response.json()
                    tokens = data.get('data', [])
                    print(f"   ✅ Got {len(tokens)} tokens")
                    
                    # Check if we got all 135
                    if len(tokens) >= 135:
                        print(f"   🎉 Successfully retrieved all {len(tokens)} tokens!")
                    else:
                        print(f"   ⚠️  Only got {len(tokens)} tokens, expected 135")
                else:
                    text = await response.text()
                    print(f"   ❌ Error: {text[:100]}")
        except Exception as e:
            print(f"   ❌ Exception: {e}")
        
        # Test 3: Rate limit check - try multiple requests
        print("\n3. Testing rate limits...")
        success_count = 0
        
        for i in range(5):
            try:
                async with session.get(url, headers=headers, params={'limit': 10}) as response:
                    if response.status == 200:
                        success_count += 1
                        print(f"   Request {i+1}: ✅ Success")
                    elif response.status == 429:
                        print(f"   Request {i+1}: ⚠️  Rate limited!")
                        break
                    else:
                        print(f"   Request {i+1}: ❌ Error {response.status}")
                
                await asyncio.sleep(0.5)  # Small delay between requests
                
            except Exception as e:
                print(f"   Request {i+1}: ❌ Exception: {e}")
        
        print(f"\n   Successfully completed {success_count}/5 requests")
        
        # Test 4: Check if we can get individual token trades
        if success_count > 0:
            print("\n4. Testing individual token trades...")
            
            # Get one token to test with
            url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/tokens"
            async with session.get(url, headers=headers, params={'limit': 1}) as response:
                if response.status == 200:
                    data = await response.json()
                    tokens = data.get('data', [])
                    
                    if tokens:
                        token = tokens[0]
                        token_address = token.get('address', '')
                        symbol = token.get('symbol', 'UNKNOWN')
                        
                        print(f"   Testing with token: {symbol}")
                        
                        # Try to get trades for this token
                        trades_url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/tokens/{token_address}/trades"
                        
                        start = time.time()
                        async with session.get(trades_url, headers=headers) as trade_response:
                            elapsed = time.time() - start
                            print(f"   Status: {trade_response.status} (took {elapsed:.2f}s)")
                            
                            if trade_response.status == 200:
                                trade_data = await trade_response.json()
                                trades = trade_data.get('data', [])
                                print(f"   ✅ Got {len(trades)} trades for {symbol}")
                            else:
                                print(f"   ❌ Could not get trades")
    
    print("\n=== SUMMARY ===")
    print("Based on these tests, we can determine if Cielo is viable for full historical data")

if __name__ == "__main__":
    asyncio.run(test_cielo_api())