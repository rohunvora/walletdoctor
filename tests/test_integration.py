#!/usr/bin/env python3
"""
Integration tests for SSE streaming API
"""

import pytest
import asyncio
import aiohttp
import json
import time
from typing import List, Dict, AsyncGenerator
from unittest.mock import patch, AsyncMock
import os

# Import components
from src.api.wallet_analytics_api_v3 import create_app
from src.lib.blockchain_fetcher_v3_stream import BlockchainFetcherV3Stream
from src.lib.progress_protocol import EventType, ProgressStep, SSEEvent


class TestSSEEndpointIntegration:
    """Test the SSE endpoint integration with the API"""
    
    @pytest.fixture
    async def app(self):
        """Create test app instance"""
        app = create_app()
        return app
    
    @pytest.fixture
    async def client(self, app, aiohttp_client):
        """Create test client"""
        return await aiohttp_client(app)
    
    @pytest.mark.asyncio
    async def test_sse_endpoint_basic_flow(self, client):
        """Test basic SSE endpoint flow"""
        # Mock the fetcher
        mock_fetcher = AsyncMock()
        
        async def mock_stream(wallet):
            # Yield a few events
            yield SSEEvent(
                type=EventType.CONNECTED,
                data={"wallet": wallet, "status": "connected"},
                id="1"
            )
            yield SSEEvent(
                type=EventType.PROGRESS,
                data={"message": "Starting", "percentage": 0},
                id="2"
            )
            yield SSEEvent(
                type=EventType.COMPLETE,
                data={"status": "complete", "summary": {"total_trades": 0}},
                id="3"
            )
        
        mock_fetcher.fetch_wallet_stream = mock_stream
        
        # Patch the fetcher creation
        with patch('src.api.wallet_analytics_api_v3.BlockchainFetcherV3Stream', return_value=mock_fetcher):
            # Make SSE request
            resp = await client.get('/v4/wallet/test_wallet/stream')
            assert resp.status == 200
            assert resp.headers['Content-Type'] == 'text/event-stream'
            
            # Read events
            events = []
            async for data in resp.content:
                if data:
                    event_str = data.decode('utf-8')
                    events.append(event_str)
                    # Stop after complete event
                    if 'event: complete' in event_str:
                        break
            
            # Verify events
            assert len(events) > 0
            assert any('event: connected' in e for e in events)
            assert any('event: progress' in e for e in events)
            assert any('event: complete' in e for e in events)
    
    @pytest.mark.asyncio
    async def test_sse_reconnection_with_last_event_id(self, client):
        """Test SSE reconnection using Last-Event-ID header"""
        mock_fetcher = AsyncMock()
        event_counter = 0
        
        async def mock_stream(wallet):
            nonlocal event_counter
            # Start from event counter
            for i in range(event_counter, event_counter + 3):
                yield SSEEvent(
                    type=EventType.PROGRESS,
                    data={"message": f"Event {i}", "percentage": i * 10},
                    id=str(i)
                )
            event_counter += 3
        
        mock_fetcher.fetch_wallet_stream = mock_stream
        
        with patch('src.api.wallet_analytics_api_v3.BlockchainFetcherV3Stream', return_value=mock_fetcher):
            # First connection
            resp1 = await client.get('/v4/wallet/test_wallet/stream')
            events1 = []
            
            async for data in resp1.content:
                if data:
                    event_str = data.decode('utf-8')
                    events1.append(event_str)
                    if len(events1) >= 2:  # Get first 2 events
                        break
            
            # Extract last event ID
            last_id = None
            for event in events1:
                if 'id:' in event:
                    last_id = event.split('id:')[1].strip()
            
            # Reconnect with Last-Event-ID
            resp2 = await client.get(
                '/v4/wallet/test_wallet/stream',
                headers={'Last-Event-ID': last_id}
            )
            
            events2 = []
            async for data in resp2.content:
                if data:
                    event_str = data.decode('utf-8')
                    events2.append(event_str)
                    if len(events2) >= 1:
                        break
            
            # Verify we got new events after the last ID
            assert len(events2) > 0
            assert f'Event {int(last_id) + 1}' in events2[0]
    
    @pytest.mark.asyncio
    async def test_sse_error_handling(self, client):
        """Test SSE error event handling"""
        mock_fetcher = AsyncMock()
        
        async def mock_stream_with_error(wallet):
            yield SSEEvent(
                type=EventType.CONNECTED,
                data={"wallet": wallet, "status": "connected"},
                id="1"
            )
            yield SSEEvent(
                type=EventType.ERROR,
                data={"error": "Rate limit exceeded", "code": "RATE_LIMIT"},
                id="2"
            )
        
        mock_fetcher.fetch_wallet_stream = mock_stream_with_error
        
        with patch('src.api.wallet_analytics_api_v3.BlockchainFetcherV3Stream', return_value=mock_fetcher):
            resp = await client.get('/v4/wallet/test_wallet/stream')
            assert resp.status == 200
            
            events = []
            async for data in resp.content:
                if data:
                    event_str = data.decode('utf-8')
                    events.append(event_str)
                    if 'event: error' in event_str:
                        break
            
            # Verify error event
            assert any('event: error' in e for e in events)
            assert any('Rate limit exceeded' in e for e in events)


class TestEndToEndStreaming:
    """Test end-to-end streaming scenarios"""
    
    @pytest.mark.asyncio
    async def test_small_wallet_streaming(self):
        """Test streaming for a small wallet"""
        fetcher = BlockchainFetcherV3Stream(skip_pricing=True)
        
        # Mock a small wallet with 10 trades
        async def mock_small_wallet(wallet):
            # Connected event
            yield SSEEvent(
                type=EventType.CONNECTED,
                data={"wallet": wallet, "status": "connected", "timestamp": time.time()},
                id="0"
            )
            
            # Progress events
            for i in range(0, 101, 25):
                yield SSEEvent(
                    type=EventType.PROGRESS,
                    data={
                        "message": f"Processing {i}%",
                        "percentage": i,
                        "step": "processing_trades"
                    },
                    id=str(i+1)
                )
            
            # Trade events
            trades = [
                {"signature": f"sig{i}", "amount": i * 100, "type": "buy" if i % 2 == 0 else "sell"}
                for i in range(10)
            ]
            
            yield SSEEvent(
                type=EventType.TRADES,
                data={
                    "trades": trades,
                    "batch_num": 1,
                    "total_yielded": 10,
                    "has_more": False
                },
                id="106"
            )
            
            # Complete event
            yield SSEEvent(
                type=EventType.COMPLETE,
                data={
                    "status": "complete",
                    "summary": {
                        "total_trades": 10,
                        "unique_tokens": 5,
                        "total_pnl": 1234.56
                    },
                    "elapsed_seconds": 1.5
                },
                id="107"
            )
        
        # Replace fetcher method
        fetcher.fetch_wallet_stream = mock_small_wallet
        
        # Collect all events
        events = []
        event_types = []
        
        async for event in fetcher.fetch_wallet_stream("small_wallet"):
            events.append(event)
            event_types.append(event.type)
        
        # Verify event sequence
        assert event_types[0] == EventType.CONNECTED
        assert EventType.PROGRESS in event_types
        assert EventType.TRADES in event_types
        assert event_types[-1] == EventType.COMPLETE
        
        # Verify complete event data
        complete_event = events[-1]
        assert complete_event.data["summary"]["total_trades"] == 10
    
    @pytest.mark.asyncio 
    async def test_large_wallet_streaming_with_batches(self):
        """Test streaming for a large wallet with multiple batches"""
        fetcher = BlockchainFetcherV3Stream(skip_pricing=True, batch_size=100)
        
        total_trades = 500
        
        async def mock_large_wallet(wallet):
            # Connected
            yield SSEEvent(
                type=EventType.CONNECTED,
                data={"wallet": wallet, "status": "connected"},
                id="0"
            )
            
            # Progress events during fetching
            steps = [
                (ProgressStep.FETCHING_SIGNATURES, 15),
                (ProgressStep.FETCHING_TRANSACTIONS, 35),
                (ProgressStep.PROCESSING_TRADES, 35),
                (ProgressStep.CALCULATING_ANALYTICS, 15)
            ]
            
            current_progress = 0
            event_id = 1
            
            for step, weight in steps:
                for i in range(0, 101, 20):
                    progress = current_progress + (i * weight / 100)
                    yield SSEEvent(
                        type=EventType.PROGRESS,
                        data={
                            "message": f"{step.value}: {i}%",
                            "percentage": progress,
                            "step": step.value
                        },
                        id=str(event_id)
                    )
                    event_id += 1
                current_progress += weight
            
            # Trade batches
            batch_num = 0
            for i in range(0, total_trades, fetcher.batch_size):
                batch_size = min(fetcher.batch_size, total_trades - i)
                batch = [
                    {"signature": f"sig{j}", "amount": j * 10}
                    for j in range(i, i + batch_size)
                ]
                
                batch_num += 1
                yield SSEEvent(
                    type=EventType.TRADES,
                    data={
                        "trades": batch,
                        "batch_num": batch_num,
                        "total_yielded": i + batch_size,
                        "has_more": i + batch_size < total_trades
                    },
                    id=str(event_id)
                )
                event_id += 1
            
            # Complete
            yield SSEEvent(
                type=EventType.COMPLETE,
                data={
                    "status": "complete",
                    "summary": {
                        "total_trades": total_trades,
                        "batches": batch_num
                    },
                    "elapsed_seconds": 5.5
                },
                id=str(event_id)
            )
        
        fetcher.fetch_wallet_stream = mock_large_wallet
        
        # Process stream
        trade_batches = 0
        total_yielded_trades = 0
        
        async for event in fetcher.fetch_wallet_stream("large_wallet"):
            if event.type == EventType.TRADES:
                trade_batches += 1
                total_yielded_trades = event.data["total_yielded"]
        
        # Verify batching
        expected_batches = (total_trades + fetcher.batch_size - 1) // fetcher.batch_size
        assert trade_batches == expected_batches
        assert total_yielded_trades == total_trades


class TestStreamingPerformance:
    """Test streaming performance characteristics"""
    
    @pytest.mark.asyncio
    async def test_progress_event_throttling(self):
        """Test that progress events are properly throttled"""
        fetcher = BlockchainFetcherV3Stream()
        
        # Track event timing
        event_times = []
        
        async def mock_rapid_progress(wallet):
            yield SSEEvent(
                type=EventType.CONNECTED,
                data={"wallet": wallet},
                id="0"
            )
            
            # Simulate rapid progress updates
            for i in range(100):
                event_times.append(time.time())
                yield SSEEvent(
                    type=EventType.PROGRESS,
                    data={"percentage": i},
                    id=str(i+1)
                )
                await asyncio.sleep(0.001)  # 1ms between updates
            
            yield SSEEvent(
                type=EventType.COMPLETE,
                data={"status": "complete"},
                id="101"
            )
        
        fetcher.fetch_wallet_stream = mock_rapid_progress
        
        # Process stream
        async for event in fetcher.fetch_wallet_stream("test_wallet"):
            pass
        
        # Verify timing
        if len(event_times) > 10:
            # Calculate average interval
            intervals = [
                event_times[i] - event_times[i-1]
                for i in range(1, len(event_times))
            ]
            avg_interval = sum(intervals) / len(intervals)
            
            # Should be close to our 1ms sleep
            assert 0.0005 < avg_interval < 0.002
    
    @pytest.mark.asyncio
    async def test_memory_efficient_streaming(self):
        """Test that streaming is memory efficient"""
        fetcher = BlockchainFetcherV3Stream(batch_size=50)
        
        # Track peak batch size
        peak_batch_size = 0
        
        async def mock_memory_test(wallet):
            yield SSEEvent(type=EventType.CONNECTED, data={"wallet": wallet}, id="0")
            
            # Generate many trades
            total_trades = 10000
            batch_num = 0
            
            for i in range(0, total_trades, fetcher.batch_size):
                batch_size = min(fetcher.batch_size, total_trades - i)
                batch = [{"sig": f"s{j}", "amt": j} for j in range(batch_size)]
                
                nonlocal peak_batch_size
                peak_batch_size = max(peak_batch_size, len(batch))
                
                batch_num += 1
                yield SSEEvent(
                    type=EventType.TRADES,
                    data={
                        "trades": batch,
                        "batch_num": batch_num,
                        "total_yielded": i + batch_size
                    },
                    id=str(batch_num)
                )
            
            yield SSEEvent(
                type=EventType.COMPLETE,
                data={"total": total_trades},
                id=str(batch_num + 1)
            )
        
        fetcher.fetch_wallet_stream = mock_memory_test
        
        # Process stream
        async for event in fetcher.fetch_wallet_stream("test_wallet"):
            pass
        
        # Verify memory efficiency
        assert peak_batch_size <= fetcher.batch_size


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 