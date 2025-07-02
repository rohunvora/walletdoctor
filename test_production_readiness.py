#!/usr/bin/env python3
"""
Test production readiness features
"""

import os
import sys
import asyncio
import aiohttp
from typing import Dict, Any

# Test configuration
API_BASE_URL = os.getenv('API_URL', 'http://localhost:5000')
TEST_WALLET = '3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2'


async def test_no_auth():
    """Test endpoints require authentication"""
    print("\n1. Testing authentication requirement...")
    
    async with aiohttp.ClientSession() as session:
        # Test without API key
        url = f"{API_BASE_URL}/v4/wallet/{TEST_WALLET}/stream"
        try:
            async with session.get(url) as response:
                assert response.status == 401, f"Expected 401, got {response.status}"
                data = await response.json()
                assert 'error' in data
                print("✅ Authentication required - working correctly")
        except Exception as e:
            print(f"❌ Authentication test failed: {e}")


async def test_invalid_api_key():
    """Test invalid API key rejection"""
    print("\n2. Testing invalid API key...")
    
    async with aiohttp.ClientSession() as session:
        # Test with invalid key
        url = f"{API_BASE_URL}/v4/wallet/{TEST_WALLET}/stream"
        headers = {'X-API-Key': 'invalid-key'}
        
        try:
            async with session.get(url, headers=headers) as response:
                assert response.status == 401, f"Expected 401, got {response.status}"
                data = await response.json()
                assert 'error' in data
                print("✅ Invalid API key rejected - working correctly")
        except Exception as e:
            print(f"❌ Invalid API key test failed: {e}")


async def test_rate_limiting():
    """Test rate limiting"""
    print("\n3. Testing rate limiting...")
    
    # Generate valid test key
    api_key = "wd_test1234567890abcdef1234567890ab"  # 35 chars total
    
    async with aiohttp.ClientSession() as session:
        headers = {'X-API-Key': api_key}
        url = f"{API_BASE_URL}/v4/wallet/{TEST_WALLET}"
        
        # Make rapid requests
        hit_limit = False
        for i in range(60):  # Try to exceed 50/min limit
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status == 429:
                        hit_limit = True
                        data = await response.json()
                        assert 'error' in data
                        assert 'Retry-After' in response.headers
                        print(f"✅ Rate limit hit after {i+1} requests - working correctly")
                        break
            except Exception as e:
                print(f"Request {i+1} failed: {e}")
        
        if not hit_limit:
            print("⚠️  Rate limit not hit - may need to adjust test or limits")


async def test_concurrent_streams():
    """Test concurrent stream limiting"""
    print("\n4. Testing concurrent stream limits...")
    
    api_key = "wd_test1234567890abcdef1234567890ab"
    headers = {'X-API-Key': api_key}
    url = f"{API_BASE_URL}/v4/wallet/{TEST_WALLET}/stream"
    
    streams = []
    try:
        # Try to open many concurrent streams
        for i in range(12):  # Try to exceed 10 concurrent limit
            stream = asyncio.create_task(stream_wallet(url, headers))
            streams.append(stream)
            await asyncio.sleep(0.1)
        
        # Wait a bit
        await asyncio.sleep(2)
        
        # Check results
        results = await asyncio.gather(*streams, return_exceptions=True)
        
        # Count successful vs rate limited
        successful = sum(1 for r in results if r is True)
        rate_limited = sum(1 for r in results if isinstance(r, Exception) and '429' in str(r))
        
        print(f"Successful streams: {successful}, Rate limited: {rate_limited}")
        
        if rate_limited > 0:
            print("✅ Concurrent stream limiting - working correctly")
        else:
            print("⚠️  No streams were rate limited")
            
    except Exception as e:
        print(f"❌ Concurrent stream test failed: {e}")
    finally:
        # Cancel remaining streams
        for stream in streams:
            if not stream.done():
                stream.cancel()


async def stream_wallet(url: str, headers: Dict[str, str]) -> bool:
    """Helper to stream wallet data"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 429:
                raise Exception(f"429 Rate Limited")
            if response.status != 200:
                raise Exception(f"Status {response.status}")
            
            # Read a few events
            count = 0
            async for line in response.content:
                if line.startswith(b'data: '):
                    count += 1
                    if count > 5:  # Read just a few events
                        break
            
            return True


async def test_monitoring_endpoint():
    """Test monitoring endpoint"""
    print("\n5. Testing monitoring endpoint...")
    
    async with aiohttp.ClientSession() as session:
        url = f"{API_BASE_URL}/metrics"
        
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    text = await response.text()
                    if 'walletdoctor_active_streams' in text:
                        print("✅ Monitoring endpoint accessible - working correctly")
                    else:
                        print("⚠️  Monitoring endpoint returns unexpected format")
                elif response.status == 403:
                    print("✅ Monitoring endpoint restricted - working correctly")
                else:
                    print(f"⚠️  Monitoring endpoint returned status {response.status}")
        except Exception as e:
            print(f"❌ Monitoring test failed: {e}")


async def test_error_handling():
    """Test error handling"""
    print("\n6. Testing error handling...")
    
    api_key = "wd_test1234567890abcdef1234567890ab"
    headers = {'X-API-Key': api_key}
    
    async with aiohttp.ClientSession() as session:
        # Test invalid wallet
        url = f"{API_BASE_URL}/v4/wallet/invalid-wallet/stream"
        
        try:
            async with session.get(url, headers=headers) as response:
                if response.status >= 400:
                    data = await response.json()
                    assert 'error' in data
                    assert 'code' in data  # Should have error code
                    print("✅ Error handling - structured errors working correctly")
                else:
                    print(f"⚠️  Invalid wallet returned status {response.status}")
        except Exception as e:
            print(f"❌ Error handling test failed: {e}")


async def test_security_headers():
    """Test security headers"""
    print("\n7. Testing security headers...")
    
    async with aiohttp.ClientSession() as session:
        url = f"{API_BASE_URL}/health"
        
        try:
            async with session.get(url) as response:
                headers = response.headers
                
                security_headers = {
                    'X-Content-Type-Options': 'nosniff',
                    'X-Frame-Options': 'DENY',
                    'X-XSS-Protection': '1; mode=block'
                }
                
                missing = []
                for header, expected in security_headers.items():
                    if header not in headers:
                        missing.append(header)
                    elif headers[header] != expected:
                        missing.append(f"{header} (wrong value)")
                
                if not missing:
                    print("✅ Security headers - all present and correct")
                else:
                    print(f"⚠️  Missing/incorrect security headers: {', '.join(missing)}")
                    
        except Exception as e:
            print(f"❌ Security headers test failed: {e}")


async def main():
    """Run all tests"""
    print("=== Production Readiness Tests ===")
    print(f"Testing API at: {API_BASE_URL}")
    
    tests = [
        test_no_auth,
        test_invalid_api_key,
        test_rate_limiting,
        test_concurrent_streams,
        test_monitoring_endpoint,
        test_error_handling,
        test_security_headers
    ]
    
    for test in tests:
        try:
            await test()
        except Exception as e:
            print(f"Test {test.__name__} failed with exception: {e}")
    
    print("\n=== Tests Complete ===")


if __name__ == '__main__':
    # Check if API is accessible
    import requests
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"API health check failed with status {response.status_code}")
            print("Make sure the API is running")
            sys.exit(1)
    except Exception as e:
        print(f"Cannot reach API at {API_BASE_URL}: {e}")
        print("Make sure the API is running")
        sys.exit(1)
    
    # Run tests
    asyncio.run(main()) 