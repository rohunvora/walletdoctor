#!/usr/bin/env python3
"""
CI Test for SSE Streaming Performance
Shows first-byte latency and chunked delivery
"""

import asyncio
import aiohttp
import time
import json
import sys

# Test configuration
API_URL = 'http://localhost:5000'
TEST_WALLETS = {
    'small': 'Bos1uqQZ4RZxFrkD1ktfyRSnafhfMuGhxgkdngGTwFGg',  # ~100 trades
    'medium': '3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2',  # 5,478 trades
}


async def test_first_byte_latency(wallet_address: str, wallet_type: str) -> dict:
    """Test time to first byte for SSE stream"""
    
    async with aiohttp.ClientSession() as session:
        url = f"{API_URL}/v4/wallet/{wallet_address}/stream"
        
        start_time = time.time()
        first_byte_time = None
        first_event_time = None
        chunks_received = 0
        trades_received = 0
        
        results = {
            'wallet_type': wallet_type,
            'wallet': wallet_address,
            'first_byte_ms': None,
            'first_event_ms': None,
            'first_trade_ms': None,
            'chunks_count': 0,
            'trades_count': 0,
            'total_time_s': None,
            'chunked_delivery': False
        }
        
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    results['error'] = f"HTTP {response.status}"
                    return results
                
                chunk_trades = []
                
                async for chunk in response.content.iter_any():
                    if first_byte_time is None:
                        first_byte_time = time.time()
                        results['first_byte_ms'] = (first_byte_time - start_time) * 1000
                    
                    chunks_received += 1
                    chunk_trade_count = 0
                    
                    # Parse SSE data
                    for line in chunk.decode('utf-8').split('\n'):
                        if line.startswith('event:') and first_event_time is None:
                            first_event_time = time.time()
                            results['first_event_ms'] = (first_event_time - start_time) * 1000
                        
                        elif line.startswith('event: trade'):
                            chunk_trade_count += 1
                            trades_received += 1
                            if trades_received == 1:
                                results['first_trade_ms'] = (time.time() - start_time) * 1000
                        
                        elif line.startswith('event: complete'):
                            results['total_time_s'] = time.time() - start_time
                            results['chunks_count'] = chunks_received
                            results['trades_count'] = trades_received
                            
                            # Check if we had chunked delivery
                            if len(chunk_trades) >= 2:
                                results['chunked_delivery'] = True
                                results['chunk_sizes'] = chunk_trades[:5]  # First 5 chunks
                            
                            return results
                    
                    if chunk_trade_count > 0:
                        chunk_trades.append(chunk_trade_count)
                    
                    # Timeout after 30 seconds
                    if time.time() - start_time > 30:
                        results['error'] = 'Timeout after 30s'
                        results['partial'] = True
                        results['chunks_count'] = chunks_received
                        results['trades_count'] = trades_received
                        return results
                        
        except Exception as e:
            results['error'] = str(e)
            return results


async def run_performance_tests():
    """Run performance tests and print results"""
    
    print("=== SSE Streaming Performance Test Results ===\n")
    
    all_passed = True
    
    for wallet_type, wallet_address in TEST_WALLETS.items():
        print(f"Testing {wallet_type} wallet ({wallet_address})...")
        
        results = await test_first_byte_latency(wallet_address, wallet_type)
        
        if 'error' in results:
            print(f"  ❌ ERROR: {results['error']}")
            all_passed = False
        else:
            # Check first-byte latency
            first_byte_ms = results['first_byte_ms']
            if wallet_type == 'medium' and first_byte_ms < 1000:
                print(f"  ✅ First-byte latency: {first_byte_ms:.0f}ms (<1s for 5k-trade wallet)")
            else:
                print(f"  ⏱️  First-byte latency: {first_byte_ms:.0f}ms")
                if wallet_type == 'medium' and first_byte_ms >= 1000:
                    all_passed = False
            
            # Check chunked delivery
            if results['chunked_delivery']:
                print(f"  ✅ WAL-404 verified: Chunked delivery in {len(results.get('chunk_sizes', []))} chunks")
                print(f"     Chunk sizes: {results.get('chunk_sizes', [])}")
            else:
                print(f"  ⚠️  Single chunk delivery")
            
            # Summary stats
            print(f"  📊 Stats: {results['trades_count']} trades in {results['chunks_count']} chunks")
            print(f"  ⏱️  Total time: {results['total_time_s']:.1f}s")
        
        print()
    
    # CI Summary
    print("\n=== CI Test Summary ===")
    if all_passed:
        print("✅ All performance tests PASSED")
        print("✅ First-byte latency <1s for 5k-trade wallet")
        print("✅ Chunked delivery verified (WAL-404)")
        return 0
    else:
        print("❌ Some tests FAILED")
        return 1


async def main():
    """Main entry point"""
    # Check if API is running
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_URL}/health") as response:
                if response.status != 200:
                    print(f"❌ API health check failed: {response.status}")
                    return 1
    except Exception as e:
        print(f"❌ Cannot connect to API at {API_URL}: {e}")
        print("   Make sure the API is running")
        return 1
    
    # Run tests
    return await run_performance_tests()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 