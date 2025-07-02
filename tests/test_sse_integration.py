#!/usr/bin/env python3
"""
Integration tests for SSE streaming API
"""

import asyncio
import aiohttp
import json
import time
from typing import List, Dict, Any
import pytest
import os

# Test configuration
API_BASE_URL = os.getenv('API_URL', 'http://localhost:5000')
TEST_WALLETS = [
    '3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2',  # Medium wallet
    'Bos1uqQZ4RZxFrkD1ktfyRSnafhfMuGhxgkdngGTwFGg',  # Small wallet
]


async def test_sse_connection():
    """Test basic SSE connection"""
    async with aiohttp.ClientSession() as session:
        url = f"{API_BASE_URL}/v4/wallet/{TEST_WALLETS[1]}/stream"
        
        async with session.get(url) as response:
            assert response.status == 200
            assert response.headers.get('Content-Type') == 'text/event-stream'
            
            # Read first few events
            events = []
            async for line in response.content:
                if line.startswith(b'event:'):
                    event_type = line.decode().split(':', 1)[1].strip()
                    events.append(event_type)
                    
                if len(events) >= 3:
                    break
            
            # Should get connected event first
            assert 'connected' in events


async def test_sse_trade_streaming():
    """Test streaming trade data"""
    async with aiohttp.ClientSession() as session:
        url = f"{API_BASE_URL}/v4/wallet/{TEST_WALLETS[1]}/stream"
        
        async with session.get(url) as response:
            assert response.status == 200
            
            trades = []
            events = []
            start_time = time.time()
            
            async for line in response.content:
                line_str = line.decode().strip()
                
                if line_str.startswith('event:'):
                    event_type = line_str.split(':', 1)[1].strip()
                    events.append(event_type)
                    
                elif line_str.startswith('data:'):
                    data_str = line_str.split(':', 1)[1].strip()
                    if data_str:
                        try:
                            data = json.loads(data_str)
                            if event_type == 'trade':
                                trades.append(data)
                        except json.JSONDecodeError:
                            pass
                
                # Stop after complete event or timeout
                if 'complete' in events or time.time() - start_time > 30:
                    break
            
            # Verify we got events
            assert 'connected' in events
            assert len(trades) > 0 or 'complete' in events


async def test_sse_progress_events():
    """Test progress event emission"""
    async with aiohttp.ClientSession() as session:
        url = f"{API_BASE_URL}/v4/wallet/{TEST_WALLETS[0]}/stream"
        
        async with session.get(url) as response:
            assert response.status == 200
            
            progress_events = []
            start_time = time.time()
            
            async for line in response.content:
                if time.time() - start_time > 10:  # 10 second timeout
                    break
                    
                line_str = line.decode().strip()
                
                if line_str.startswith('event: progress'):
                    # Next line should be data
                    data_line = await response.content.readline()
                    data_str = data_line.decode().strip()
                    if data_str.startswith('data:'):
                        try:
                            data = json.loads(data_str.split(':', 1)[1])
                            progress_events.append(data)
                        except:
                            pass
                
                elif line_str.startswith('event: complete'):
                    break
            
            # Should have progress events for medium wallet
            assert len(progress_events) > 0


async def test_sse_error_handling():
    """Test error event on invalid wallet"""
    async with aiohttp.ClientSession() as session:
        url = f"{API_BASE_URL}/v4/wallet/invalid-wallet/stream"
        
        async with session.get(url) as response:
            # Should still return 200 and send error via SSE
            assert response.status == 200
            
            error_found = False
            async for line in response.content:
                line_str = line.decode().strip()
                
                if line_str.startswith('event: error'):
                    error_found = True
                    # Read data line
                    data_line = await response.content.readline()
                    data_str = data_line.decode().strip()
                    if data_str.startswith('data:'):
                        data = json.loads(data_str.split(':', 1)[1])
                        assert 'error' in data
                        assert 'code' in data
                    break
            
            assert error_found


async def test_sse_heartbeat():
    """Test heartbeat events during long streams"""
    async with aiohttp.ClientSession() as session:
        url = f"{API_BASE_URL}/v4/wallet/{TEST_WALLETS[0]}/stream"
        
        async with session.get(url) as response:
            assert response.status == 200
            
            heartbeats = []
            start_time = time.time()
            
            async for line in response.content:
                if time.time() - start_time > 35:  # Wait for at least one heartbeat
                    break
                    
                line_str = line.decode().strip()
                
                if line_str.startswith('event: heartbeat'):
                    data_line = await response.content.readline()
                    data_str = data_line.decode().strip()
                    if data_str.startswith('data:'):
                        data = json.loads(data_str.split(':', 1)[1])
                        heartbeats.append(data)
                
                elif line_str.startswith('event: complete'):
                    break
            
            # Should have at least one heartbeat if stream took >30s
            if time.time() - start_time > 30:
                assert len(heartbeats) > 0


async def test_concurrent_streams():
    """Test multiple concurrent SSE streams"""
    async def stream_wallet(session: aiohttp.ClientSession, wallet: str) -> Dict[str, Any]:
        url = f"{API_BASE_URL}/v4/wallet/{wallet}/stream"
        result = {
            'wallet': wallet,
            'events': [],
            'trades': 0,
            'errors': 0,
            'duration': 0
        }
        
        start_time = time.time()
        
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    result['errors'] += 1
                    return result
                
                async for line in response.content:
                    line_str = line.decode().strip()
                    
                    if line_str.startswith('event:'):
                        event_type = line_str.split(':', 1)[1].strip()
                        result['events'].append(event_type)
                        
                        if event_type == 'trade':
                            result['trades'] += 1
                        elif event_type == 'complete':
                            break
                    
                    # Timeout after 30 seconds
                    if time.time() - start_time > 30:
                        break
                        
        except Exception as e:
            result['errors'] += 1
            result['error_message'] = str(e)
        
        result['duration'] = time.time() - start_time
        return result
    
    # Test concurrent streams
    async with aiohttp.ClientSession() as session:
        tasks = [
            stream_wallet(session, wallet)
            for wallet in TEST_WALLETS[:2]  # Test with 2 wallets
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Verify all streams completed
        for result in results:
            assert len(result['events']) > 0
            assert 'connected' in result['events']
            assert result['errors'] == 0


async def test_stream_cancellation():
    """Test client disconnection handling"""
    async with aiohttp.ClientSession() as session:
        url = f"{API_BASE_URL}/v4/wallet/{TEST_WALLETS[0]}/stream"
        
        async with session.get(url) as response:
            assert response.status == 200
            
            # Read a few events then cancel
            event_count = 0
            async for line in response.content:
                if line.startswith(b'event:'):
                    event_count += 1
                    
                if event_count >= 5:
                    # Cancel the stream
                    response.close()
                    break
            
            assert event_count >= 5


async def test_sse_reconnection():
    """Test reconnection with Last-Event-ID"""
    async with aiohttp.ClientSession() as session:
        url = f"{API_BASE_URL}/v4/wallet/{TEST_WALLETS[1]}/stream"
        
        # First connection
        last_event_id = None
        async with session.get(url) as response:
            assert response.status == 200
            
            event_count = 0
            async for line in response.content:
                line_str = line.decode().strip()
                
                if line_str.startswith('id:'):
                    last_event_id = line_str.split(':', 1)[1].strip()
                
                if line_str.startswith('event:'):
                    event_count += 1
                    
                if event_count >= 3:
                    break
        
        # Reconnect with Last-Event-ID
        if last_event_id:
            headers = {'Last-Event-ID': last_event_id}
            async with session.get(url, headers=headers) as response:
                assert response.status == 200
                
                # Should continue from where we left off
                # (In full implementation, would verify no duplicate events)


@pytest.mark.asyncio
async def test_all():
    """Run all integration tests"""
    print("=== SSE Integration Tests ===")
    
    tests = [
        ("Basic Connection", test_sse_connection),
        ("Trade Streaming", test_sse_trade_streaming),
        ("Progress Events", test_sse_progress_events),
        ("Error Handling", test_sse_error_handling),
        ("Heartbeat", test_sse_heartbeat),
        ("Concurrent Streams", test_concurrent_streams),
        ("Stream Cancellation", test_stream_cancellation),
        ("Reconnection", test_sse_reconnection)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            print(f"\n{test_name}...", end='', flush=True)
            await test_func()
            print(" ✅ PASSED")
            passed += 1
        except Exception as e:
            print(f" ❌ FAILED: {e}")
            failed += 1
    
    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    return failed == 0


if __name__ == "__main__":
    # Check if API is running
    import requests
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"API health check failed: {response.status_code}")
            exit(1)
    except Exception as e:
        print(f"Cannot reach API at {API_BASE_URL}: {e}")
        print("Make sure the API is running")
        exit(1)
    
    # Run tests
    success = asyncio.run(test_all())
    exit(0 if success else 1) 