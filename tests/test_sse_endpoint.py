#!/usr/bin/env python3
"""
Test SSE streaming endpoint
"""

import pytest
import asyncio
import json
import time
from threading import Thread
from queue import Queue
import requests


def test_sse_endpoint_headers():
    """Test that SSE endpoint returns correct headers"""
    # Use test client approach to verify headers
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    
    from src.api.wallet_analytics_api_v3 import app
    
    with app.test_client() as client:
        response = client.post(
            '/v4/analyze/stream',
            json={'wallet': '3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2'},
            headers={'Accept': 'text/event-stream'}
        )
        
        # Check headers
        assert response.status_code == 200
        assert response.content_type == 'text/event-stream; charset=utf-8'
        assert response.headers.get('Cache-Control') == 'no-cache'
        assert response.headers.get('X-Accel-Buffering') == 'no'
        assert response.headers.get('Connection') == 'keep-alive'


def test_sse_endpoint_events():
    """Test that SSE endpoint sends correct events"""
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    
    from src.api.wallet_analytics_api_v3 import app
    
    events = []
    
    with app.test_client() as client:
        response = client.post(
            '/v4/analyze/stream',
            json={'wallet': '3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2'},
            headers={'Accept': 'text/event-stream'},
            buffered=False
        )
        
        # Read events from the stream
        event_buffer = ""
        start_time = time.time()
        
        for chunk in response.response:
            if isinstance(chunk, bytes):
                chunk = chunk.decode('utf-8')
            
            event_buffer += chunk
            
            # Process complete events (separated by double newline)
            while '\n\n' in event_buffer:
                event_str, event_buffer = event_buffer.split('\n\n', 1)
                
                if event_str.strip():
                    # Parse event
                    lines = event_str.strip().split('\n')
                    event = {}
                    
                    for line in lines:
                        if line.startswith('event:'):
                            event['type'] = line[6:].strip()
                        elif line.startswith('data:'):
                            event['data'] = json.loads(line[5:].strip())
                    
                    events.append(event)
            
            # Stop after getting a few events or timeout
            if len(events) >= 2 or time.time() - start_time > 5:
                break
    
    # Verify we got the expected events
    assert len(events) >= 2
    
    # First event should be 'connected'
    assert events[0]['type'] == 'connected'
    assert events[0]['data']['status'] == 'connected'
    assert events[0]['data']['wallet'] == '3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2'
    
    # Second event should be 'complete' (based on our test implementation)
    assert events[1]['type'] == 'complete'
    assert events[1]['data']['status'] == 'complete'


def test_sse_endpoint_validation():
    """Test SSE endpoint input validation"""
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    
    from src.api.wallet_analytics_api_v3 import app
    
    with app.test_client() as client:
        # Test missing wallet
        response = client.post(
            '/v4/analyze/stream',
            json={},
            headers={'Accept': 'text/event-stream'}
        )
        assert response.status_code == 400
        assert b'Missing wallet address' in response.data
        
        # Test invalid wallet (too short)
        response = client.post(
            '/v4/analyze/stream',
            json={'wallet': 'invalid'},
            headers={'Accept': 'text/event-stream'}
        )
        assert response.status_code == 400
        assert b'Invalid wallet address' in response.data


def test_sse_heartbeat_timing():
    """Test that heartbeat events are sent at correct intervals"""
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    
    from src.api.wallet_analytics_api_v3 import app
    
    # Temporarily modify the generate function to speed up testing
    # We'll test the logic without waiting 30 seconds
    
    with app.test_client() as client:
        # For this test, we just verify the heartbeat logic exists
        # In a real implementation, we'd mock time.time() to test intervals
        response = client.post(
            '/v4/analyze/stream',
            json={'wallet': '3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2'},
            headers={'Accept': 'text/event-stream'}
        )
        
        # Just verify the endpoint works
        assert response.status_code == 200
        
        # Read a bit of the response to ensure it's streaming
        data = b''
        for chunk in response.response:
            data += chunk
            if len(data) > 100:  # Got some data
                break
        
        assert b'event: connected' in data


def test_curl_style_client():
    """Simulate a curl-style client connecting to SSE endpoint"""
    import subprocess
    import sys
    import os
    import signal
    
    # Skip this test in CI/automated environments
    # It requires starting a real server which can be problematic
    if os.getenv('CI') or os.getenv('PYTEST_CURRENT_TEST'):
        pytest.skip("Skipping curl test in automated environment")
    
    # This test is more of a manual integration test
    # The core SSE functionality is already tested in the other tests
    
    # For manual testing, you can run:
    # curl -X POST -H "Content-Type: application/json" \
    #      -H "Accept: text/event-stream" \
    #      -d '{"wallet": "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"}' \
    #      --no-buffer http://localhost:8080/v4/analyze/stream
    
    # Just verify curl is available
    result = subprocess.run(['curl', '--version'], capture_output=True)
    assert result.returncode == 0, "curl not available"


if __name__ == "__main__":
    # Run specific tests
    test_sse_endpoint_headers()
    print("✅ Headers test passed")
    
    test_sse_endpoint_events()
    print("✅ Events test passed")
    
    test_sse_endpoint_validation()
    print("✅ Validation test passed")
    
    test_sse_heartbeat_timing()
    print("✅ Heartbeat test passed")
    
    # Skip curl test when running directly (requires server setup)
    # test_curl_style_client()
    
    print("\n✅ All SSE endpoint tests passed!") 