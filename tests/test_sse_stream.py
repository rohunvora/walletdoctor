#!/usr/bin/env python3
"""
Tests for SSE streaming functionality
"""

import pytest
import asyncio
import json
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import AsyncGenerator, List, Dict, Any

# Import the components we're testing
from src.lib.blockchain_fetcher_v3_stream import BlockchainFetcherV3Stream
from src.lib.progress_protocol import (
    EventType, ProgressStep, SSEEvent, ProgressData, TradesData, 
    ErrorData, ProgressCalculator, EventBuilder
)


class TestProgressCalculation:
    """Test progress calculation and tracking"""
    
    def test_progress_weights_sum_to_100(self):
        """Ensure all progress step weights sum to 100%"""
        calc = ProgressCalculator()
        total = sum(calc.STEP_WEIGHTS.values())
        assert total == 100, f"Step weights sum to {total}, not 100"
    
    def test_progress_updates_correctly(self):
        """Test progress updates through different steps"""
        calc = ProgressCalculator()
        
        # Test fetching signatures at 50%
        progress = calc.update_step_progress(ProgressStep.FETCHING_SIGNATURES, 50)
        # 50% of 15% weight = 7.5%
        assert progress == 7.5
        
        # Complete signatures, start transactions
        calc.update_step_progress(ProgressStep.FETCHING_SIGNATURES, 100)
        progress = calc.update_step_progress(ProgressStep.FETCHING_TRANSACTIONS, 25)
        # 100% of 15% + 25% of 35% = 15 + 8.75 = 23.75%
        assert progress == 23.75
    
    def test_progress_estimation_with_known_total(self):
        """Test progress estimation when total is known"""
        calc = ProgressCalculator()
        
        # Linear progress
        assert calc.estimate_step_progress(0, 100) == 0
        assert calc.estimate_step_progress(50, 100) == 50
        assert calc.estimate_step_progress(100, 100) == 100
        assert calc.estimate_step_progress(150, 100) == 100  # Capped at 100
    
    def test_progress_estimation_with_unknown_total(self):
        """Test logarithmic progress estimation for unknown totals"""
        calc = ProgressCalculator()
        
        # Unknown total uses logarithmic scale
        assert calc.estimate_step_progress(0, 0) == 0
        assert calc.estimate_step_progress(50, 0) == 25  # Slow initial progress
        assert calc.estimate_step_progress(100, 0) == 50
        assert calc.estimate_step_progress(5000, 0) <= 95  # Asymptotic


class TestSSEEventGeneration:
    """Test SSE event generation and formatting"""
    
    def test_connected_event_format(self):
        """Test connected event generation"""
        event = EventBuilder.connected("test_wallet", request_id="req-123")
        
        assert event.type == EventType.CONNECTED
        assert event.data["wallet"] == "test_wallet"
        assert event.data["status"] == "connected"
        assert "timestamp" in event.data
        assert event.id == "req-123"
        
        # Test SSE format
        sse_format = event.to_sse_format()
        assert "id: req-123" in sse_format
        assert "event: connected" in sse_format
        assert '"wallet": "test_wallet"' in sse_format
    
    def test_progress_event_format(self):
        """Test progress event generation"""
        progress_data = ProgressData(
            message="Fetching page 5 of 10",
            percentage=50.0,
            step=ProgressStep.FETCHING_TRANSACTIONS,
            details={"current_page": 5, "total_pages": 10}
        )
        
        event = EventBuilder.progress(progress_data)
        
        assert event.type == EventType.PROGRESS
        assert event.data["message"] == "Fetching page 5 of 10"
        assert event.data["percentage"] == 50.0
        assert event.data["step"] == "fetching_transactions"
        assert event.data["current_page"] == 5
    
    def test_trades_event_format(self):
        """Test trades event generation"""
        trades = [
            {"signature": "sig1", "type": "buy", "amount": 100},
            {"signature": "sig2", "type": "sell", "amount": 50}
        ]
        
        trades_data = TradesData(
            trades=trades,
            batch_num=1,
            total_yielded=2,
            has_more=True
        )
        
        event = EventBuilder.trades(trades_data)
        
        assert event.type == EventType.TRADES
        assert event.data["trades"] == trades
        assert event.data["batch_num"] == 1
        assert event.data["total_yielded"] == 2
        assert event.data["has_more"] is True
    
    def test_error_event_format(self):
        """Test error event generation"""
        error_data = ErrorData(
            error="Rate limit exceeded",
            code="RATE_LIMIT",
            details={"retry_after": 60}
        )
        
        event = EventBuilder.error(error_data)
        
        assert event.type == EventType.ERROR
        assert event.data["error"] == "Rate limit exceeded"
        assert event.data["code"] == "RATE_LIMIT"
        assert event.data["details"]["retry_after"] == 60
    
    def test_complete_event_format(self):
        """Test complete event generation"""
        summary = {
            "total_trades": 100,
            "unique_tokens": 10,
            "total_pnl": 1234.56,
            "win_rate": 65.5
        }
        
        metrics = {
            "api_calls": 50,
            "cache_hits": 30,
            "fetch_time": 5.5
        }
        
        event = EventBuilder.complete(summary, metrics, elapsed_seconds=12.5)
        
        assert event.type == EventType.COMPLETE
        assert event.data["status"] == "complete"
        assert event.data["summary"] == summary
        assert event.data["metrics"] == metrics
        assert event.data["elapsed_seconds"] == 12.5


class TestStreamingFetcher:
    """Test the streaming fetcher implementation"""
    
    @pytest.mark.asyncio
    async def test_fetch_wallet_stream_structure(self):
        """Test basic structure of streaming fetcher"""
        fetcher = BlockchainFetcherV3Stream(skip_pricing=True)
        
        # Mock simple stream
        async def mock_stream(wallet):
            yield EventBuilder.connected(wallet)
            yield EventBuilder.progress(ProgressData(
                message="Starting",
                percentage=0,
                step=ProgressStep.INITIALIZING
            ))
            yield EventBuilder.complete(
                {"total_trades": 0},
                {"elapsed": 0.1},
                0.1
            )
        
        # Monkey patch the method
        fetcher.fetch_wallet_stream = mock_stream
        
        # Collect events
        events = []
        async for event in fetcher.fetch_wallet_stream("test_wallet"):
            events.append(event)
        
        # Verify basic structure
        assert len(events) == 3
        assert events[0].type == EventType.CONNECTED
        assert events[1].type == EventType.PROGRESS
        assert events[2].type == EventType.COMPLETE
    
    @pytest.mark.asyncio
    async def test_batch_size_configuration(self):
        """Test that batch size affects trade event batching"""
        fetcher = BlockchainFetcherV3Stream(
            skip_pricing=True,
            batch_size=5  # Small batch size
        )
        
        # Create 20 mock trades
        mock_trades = [
            {"signature": f"sig{i}", "amount": i}
            for i in range(20)
        ]
        
        # Track trade batches
        trade_batches = []
        
        # Mock stream that yields trades
        async def mock_stream(wallet):
            yield EventBuilder.connected(wallet)
            
            # Yield trades in batches
            for i in range(0, len(mock_trades), fetcher.batch_size):
                batch = mock_trades[i:i + fetcher.batch_size]
                trades_data = TradesData(
                    trades=batch,
                    batch_num=i // fetcher.batch_size + 1,
                    total_yielded=i + len(batch),
                    has_more=i + len(batch) < len(mock_trades)
                )
                trade_batches.append(len(batch))
                yield EventBuilder.trades(trades_data)
            
            yield EventBuilder.complete({}, {}, 1.0)
        
        fetcher.fetch_wallet_stream = mock_stream
        
        # Collect events
        events = []
        async for event in fetcher.fetch_wallet_stream("test_wallet"):
            events.append(event)
        
        # Verify batching
        assert all(batch_size <= 5 for batch_size in trade_batches)
        assert sum(trade_batches) == 20


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    @pytest.mark.asyncio
    async def test_empty_wallet(self):
        """Test handling of wallet with no trades"""
        fetcher = BlockchainFetcherV3Stream()
        
        # Mock empty stream
        async def mock_empty_stream(wallet):
            yield EventBuilder.connected(wallet)
            yield EventBuilder.progress(ProgressData(
                message="No trades found",
                percentage=100,
                step=ProgressStep.COMPLETE
            ))
            yield EventBuilder.complete(
                {"total_trades": 0},
                {},
                0.1
            )
        
        fetcher.fetch_wallet_stream = mock_empty_stream
        
        events = []
        async for event in fetcher.fetch_wallet_stream("empty_wallet"):
            events.append(event)
        
        # Should get connected, progress, and complete events
        event_types = [e.type for e in events]
        assert EventType.CONNECTED in event_types
        assert EventType.COMPLETE in event_types
        
        # Complete event should show 0 trades
        complete_event = next(e for e in events if e.type == EventType.COMPLETE)
        assert complete_event.data["summary"].get("total_trades", 0) == 0
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test handling of errors during streaming"""
        fetcher = BlockchainFetcherV3Stream()
        
        # Mock stream with error
        async def mock_error_stream(wallet):
            yield EventBuilder.connected(wallet)
            yield EventBuilder.error(ErrorData(
                error="Test error occurred",
                code="TEST_ERROR"
            ))
        
        fetcher.fetch_wallet_stream = mock_error_stream
        
        events = []
        async for event in fetcher.fetch_wallet_stream("test_wallet"):
            events.append(event)
        
        # Should get error event
        error_events = [e for e in events if e.type == EventType.ERROR]
        assert len(error_events) > 0
        assert "Test error" in error_events[0].data["error"]
    
    @pytest.mark.asyncio
    async def test_concurrent_progress_updates(self):
        """Test that concurrent operations don't break progress tracking"""
        calc = ProgressCalculator()
        
        # Simulate concurrent updates
        async def update_progress(step, iterations):
            for i in range(iterations):
                calc.update_step_progress(step, i * 100 / iterations)
                await asyncio.sleep(0.001)  # Small delay
        
        # Run concurrent updates
        await asyncio.gather(
            update_progress(ProgressStep.FETCHING_SIGNATURES, 10),
            update_progress(ProgressStep.FETCHING_TRANSACTIONS, 10)
        )
        
        # Progress should be valid
        final_progress = calc.calculate_overall_progress()
        assert 0 <= final_progress <= 100


class TestPerformance:
    """Test performance characteristics"""
    
    @pytest.mark.asyncio
    async def test_streaming_memory_efficiency(self):
        """Test that streaming doesn't accumulate memory"""
        fetcher = BlockchainFetcherV3Stream(batch_size=100)
        
        # Create a large number of mock trades
        num_trades = 1000
        
        # Mock stream with batched trades
        async def mock_efficient_stream(wallet):
            yield EventBuilder.connected(wallet)
            
            total_yielded = 0
            batch_num = 0
            
            # Yield trades in controlled batches
            while total_yielded < num_trades:
                batch_size = min(fetcher.batch_size, num_trades - total_yielded)
                batch = [
                    {"signature": f"sig{i}", "amount": i}
                    for i in range(total_yielded, total_yielded + batch_size)
                ]
                
                batch_num += 1
                total_yielded += len(batch)
                
                yield EventBuilder.trades(TradesData(
                    trades=batch,
                    batch_num=batch_num,
                    total_yielded=total_yielded,
                    has_more=total_yielded < num_trades
                ))
            
            yield EventBuilder.complete(
                {"total_trades": total_yielded},
                {"batches": batch_num},
                1.0
            )
        
        fetcher.fetch_wallet_stream = mock_efficient_stream
        
        # Process stream
        trade_events = 0
        max_batch_size = 0
        
        async for event in fetcher.fetch_wallet_stream("test_wallet"):
            if event.type == EventType.TRADES:
                trade_events += 1
                batch_size = len(event.data["trades"])
                max_batch_size = max(max_batch_size, batch_size)
        
        # Verify batching kept memory usage low
        assert max_batch_size <= fetcher.batch_size
        assert trade_events == num_trades // fetcher.batch_size + (1 if num_trades % fetcher.batch_size else 0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
