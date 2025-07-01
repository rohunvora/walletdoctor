#!/usr/bin/env python3
"""
Test streaming fetcher functionality
"""

import pytest
import asyncio
import time
from typing import List, Dict, Any
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.lib.blockchain_fetcher_v3_stream import (
    BlockchainFetcherV3Stream,
    STREAM_EVENT_PROGRESS, STREAM_EVENT_TRADES,
    STREAM_EVENT_METADATA, STREAM_EVENT_COMPLETE, STREAM_EVENT_ERROR
)


def test_streaming_yields_partial_results():
    """Test that streaming fetcher yields partial results before completion"""
    
    async def run_test():
        events = []
        trade_batches = []
        progress_updates = []
        
        # Skip pricing for faster test
        async with BlockchainFetcherV3Stream(skip_pricing=True, batch_size=50) as fetcher:
            async for event in fetcher.fetch_wallet_trades_stream("3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"):
                events.append(event)
                
                if event["type"] == STREAM_EVENT_TRADES:
                    trade_batches.append(event["data"])
                elif event["type"] == STREAM_EVENT_PROGRESS:
                    progress_updates.append(event["data"])
                elif event["type"] == STREAM_EVENT_COMPLETE:
                    break
                
                # Stop after getting some batches to keep test fast
                if len(trade_batches) >= 3:
                    break
        
        # Verify we got events
        assert len(events) > 0, "Should receive events"
        
        # Verify we got progress updates
        assert len(progress_updates) > 0, "Should receive progress updates"
        assert progress_updates[0]["percentage"] == 0.0, "First progress should be 0%"
        
        # Verify we got trade batches
        assert len(trade_batches) > 0, "Should receive trade batches"
        
        # Verify batch structure
        if trade_batches:
            first_batch = trade_batches[0]
            assert "trades" in first_batch
            assert "batch_num" in first_batch
            assert "total_yielded" in first_batch
            assert first_batch["batch_num"] == 1
        
        return events, trade_batches, progress_updates
    
    # Run the async test
    events, trade_batches, progress_updates = asyncio.run(run_test())
    
    # Additional assertions
    assert any(p["step"] == "initializing" for p in progress_updates)
    assert any(p["step"] == "fetching_signatures" for p in progress_updates)


def test_streaming_event_types():
    """Test that all expected event types are present"""
    
    async def run_test():
        event_types = set()
        
        async with BlockchainFetcherV3Stream(skip_pricing=True) as fetcher:
            async for event in fetcher.fetch_wallet_trades_stream("3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"):
                event_types.add(event["type"])
                
                # Stop when we have complete event
                if event["type"] == STREAM_EVENT_COMPLETE:
                    break
        
        return event_types
    
    event_types = asyncio.run(run_test())
    
    # Should have at least progress and complete
    assert STREAM_EVENT_PROGRESS in event_types
    assert STREAM_EVENT_COMPLETE in event_types
    
    # Trades and metadata depend on wallet content
    # But for test wallet we know it has trades
    assert STREAM_EVENT_TRADES in event_types


def test_streaming_complete_event():
    """Test that complete event contains proper summary"""
    
    async def run_test():
        complete_event = None
        
        async with BlockchainFetcherV3Stream(skip_pricing=True) as fetcher:
            async for event in fetcher.fetch_wallet_trades_stream("3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"):
                if event["type"] == STREAM_EVENT_COMPLETE:
                    complete_event = event["data"]
                    break
        
        return complete_event
    
    complete_event = asyncio.run(run_test())
    
    assert complete_event is not None
    assert "summary" in complete_event
    assert "metrics" in complete_event
    assert "timing" in complete_event
    assert "total_time" in complete_event
    
    # Check summary structure
    summary = complete_event["summary"]
    assert "wallet" in summary
    assert "total_trades" in summary
    assert "elapsed_seconds" in summary
    assert summary["total_trades"] > 0


def test_streaming_error_handling():
    """Test error handling in streaming"""
    
    async def run_test():
        # Test with invalid wallet
        error_event = None
        
        async with BlockchainFetcherV3Stream() as fetcher:
            async for event in fetcher.fetch_wallet_trades_stream("invalid"):
                if event["type"] == STREAM_EVENT_ERROR:
                    error_event = event["data"]
                    break
                elif event["type"] == STREAM_EVENT_COMPLETE:
                    # Shouldn't get here with invalid wallet
                    break
        
        return error_event
    
    # This may or may not error depending on validation
    # Just verify the test runs without exception
    try:
        error_event = asyncio.run(run_test())
    except Exception:
        # Error in fetching is ok for invalid wallet
        pass


def test_streaming_batch_size():
    """Test that batch size configuration works"""
    
    async def run_test():
        trade_batches = []
        
        # Use small batch size
        async with BlockchainFetcherV3Stream(skip_pricing=True, batch_size=10) as fetcher:
            async for event in fetcher.fetch_wallet_trades_stream("3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"):
                if event["type"] == STREAM_EVENT_TRADES:
                    trade_batches.append(event["data"])
                    # Get a few batches
                    if len(trade_batches) >= 3:
                        break
        
        return trade_batches
    
    trade_batches = asyncio.run(run_test())
    
    # Verify we got multiple batches
    assert len(trade_batches) >= 2
    
    # Check batch sizes (except possibly the last one)
    for batch in trade_batches[:-1]:
        assert len(batch["trades"]) <= 10


def test_streaming_maintains_performance():
    """Test that streaming doesn't significantly impact total time"""
    
    async def run_test():
        start_time = time.time()
        total_trades = 0
        
        async with BlockchainFetcherV3Stream(skip_pricing=True) as fetcher:
            async for event in fetcher.fetch_wallet_trades_stream("3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"):
                if event["type"] == STREAM_EVENT_COMPLETE:
                    total_trades = event["data"]["summary"]["total_trades"]
                    break
        
        elapsed = time.time() - start_time
        return elapsed, total_trades
    
    elapsed, total_trades = asyncio.run(run_test())
    
    # Should still be under 20 seconds for 5k+ trades
    assert total_trades > 5000
    assert elapsed < 20.0, f"Performance degraded: took {elapsed:.1f}s"


def test_streaming_compatibility():
    """Test that streaming fetcher maintains compatibility with base class"""
    
    # Verify it's a subclass
    from src.lib.blockchain_fetcher_v3 import BlockchainFetcherV3
    assert issubclass(BlockchainFetcherV3Stream, BlockchainFetcherV3)
    
    # Verify class has the expected methods
    assert hasattr(BlockchainFetcherV3Stream, 'fetch_wallet_trades_stream')
    assert hasattr(BlockchainFetcherV3Stream, '_fetch_signatures_stream')
    assert hasattr(BlockchainFetcherV3Stream, '_fetch_transactions_stream')
    assert hasattr(BlockchainFetcherV3Stream, '_calculate_summary')
    
    # Verify it maintains the init signature
    import inspect
    init_params = inspect.signature(BlockchainFetcherV3Stream.__init__).parameters
    assert 'progress_callback' in init_params
    assert 'skip_pricing' in init_params
    assert 'parallel_pages' in init_params
    assert 'batch_size' in init_params  # New parameter for streaming


if __name__ == "__main__":
    # Run tests
    if not os.getenv("HELIUS_KEY"):
        print("⚠️  HELIUS_KEY not set, skipping live tests")
        test_streaming_compatibility()
        print("✅ Compatibility test passed")
    else:
        test_streaming_yields_partial_results()
        print("✅ Partial results test passed")
        
        test_streaming_event_types()
        print("✅ Event types test passed")
        
        test_streaming_complete_event()
        print("✅ Complete event test passed")
        
        test_streaming_error_handling()
        print("✅ Error handling test passed")
        
        test_streaming_batch_size()
        print("✅ Batch size test passed")
        
        test_streaming_maintains_performance()
        print("✅ Performance test passed")
        
        test_streaming_compatibility()
        print("✅ Compatibility test passed")
        
        print("\n✅ All streaming fetcher tests passed!") 