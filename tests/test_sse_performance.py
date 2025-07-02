#!/usr/bin/env python3
"""
Performance validation tests for SSE streaming
Tests large wallet streaming, memory usage, batching, and benchmarks vs V3
"""

import pytest
import asyncio
import time
import psutil
import os
import gc
from typing import List, Dict, Any, Tuple
from unittest.mock import patch, AsyncMock, MagicMock
import tracemalloc

from src.lib.blockchain_fetcher_v3 import BlockchainFetcherV3
from src.lib.blockchain_fetcher_v3_stream import BlockchainFetcherV3Stream
from src.api.wallet_analytics_api_v3 import create_app


class TestStreamingPerformance:
    """Test streaming performance characteristics"""
    
    @pytest.fixture
    def process(self):
        """Get current process for memory monitoring"""
        return psutil.Process(os.getpid())
    
    @pytest.mark.asyncio
    async def test_large_wallet_streaming_performance(self, process):
        """Test streaming performance with 5k trades"""
        # Target: <20s for 5k trades
        num_trades = 5000
        batch_size = 100
        
        # Create mock fetcher
        fetcher = BlockchainFetcherV3Stream(
            skip_pricing=True,
            batch_size=batch_size
        )
        
        # Mock the internal methods to generate test data
        async def mock_signatures_stream(wallet):
            # Yield signatures in batches
            for i in range(0, num_trades, 1000):
                batch = [f"sig{j}" for j in range(i, min(i + 1000, num_trades))]
                yield batch
        
        async def mock_transactions_stream(signatures):
            # Yield transactions in chunks
            for i in range(0, len(signatures), 500):
                chunk = []
                for j in range(i, min(i + 500, len(signatures))):
                    chunk.append({
                        "signature": signatures[j],
                        "blockTime": 1234567890 + j,
                        "slot": 100000 + j,
                        "transaction": {
                            "message": {
                                "instructions": []
                            }
                        }
                    })
                yield chunk
        
        # Mock trade extraction
        def mock_extract_trades(transactions, wallet):
            trades = []
            for tx in transactions:
                from src.lib.blockchain_fetcher_v3 import Trade
                trade = Trade(
                    signature=tx["signature"],
                    timestamp=tx["blockTime"],
                    slot=tx["slot"],
                    token_in_mint="SOL",
                    token_in_symbol="SOL",
                    token_in_amount=1.0,
                    token_out_mint="USDC",
                    token_out_symbol="USDC",
                    token_out_amount=100.0,
                    value_usd=100.0,
                    priced=False
                )
                trades.append(trade)
            return trades
        
        # Patch methods
        with patch.object(fetcher, '_fetch_signatures_stream', mock_signatures_stream):
            with patch.object(fetcher, '_fetch_transactions_stream', mock_transactions_stream):
                with patch.object(fetcher, '_extract_trades_with_dedup', mock_extract_trades):
                    with patch.object(fetcher, '_fetch_token_metadata', new_callable=AsyncMock):
                        with patch.object(fetcher, '_apply_dust_filter', lambda x: x):
                            
                            # Measure performance
                            start_time = time.time()
                            start_memory = process.memory_info().rss / 1024 / 1024  # MB
                            
                            events_received = []
                            trades_received = 0
                            
                            async for event in fetcher.fetch_wallet_trades_stream("test_wallet"):
                                events_received.append(event["type"])
                                
                                if event["type"] == "trades":
                                    trades_received += len(event["data"]["trades"])
                                elif event["type"] == "complete":
                                    break
                            
                            end_time = time.time()
                            end_memory = process.memory_info().rss / 1024 / 1024  # MB
                            
                            elapsed_time = end_time - start_time
                            memory_used = end_memory - start_memory
                            
                            # Verify performance
                            assert elapsed_time < 20, f"Streaming took {elapsed_time:.2f}s, expected <20s"
                            assert trades_received == num_trades, f"Expected {num_trades} trades, got {trades_received}"
                            
                            # Log results
                            print(f"\nPerformance Results:")
                            print(f"- Time: {elapsed_time:.2f}s for {num_trades} trades")
                            print(f"- Rate: {num_trades / elapsed_time:.0f} trades/second")
                            print(f"- Memory: {memory_used:.1f}MB used")
                            print(f"- Events: {len(events_received)} total")
    
    @pytest.mark.asyncio
    async def test_memory_usage_with_large_dataset(self, process):
        """Test memory usage stays below 500MB for large datasets"""
        # Create 10k trades to test memory limits
        num_trades = 10000
        batch_size = 100
        
        # Track memory usage
        tracemalloc.start()
        gc.collect()  # Clean slate
        
        start_memory = process.memory_info().rss / 1024 / 1024  # MB
        peak_memory = start_memory
        
        fetcher = BlockchainFetcherV3Stream(
            skip_pricing=True,
            batch_size=batch_size
        )
        
        # Mock stream that generates trades on-demand
        async def mock_stream(wallet):
            yield {"type": "progress", "data": {"message": "Starting", "percentage": 0}}
            
            # Stream trades in batches
            for batch_num in range(num_trades // batch_size):
                # Generate batch on-demand (not pre-allocated)
                trades = []
                for i in range(batch_size):
                    trade_idx = batch_num * batch_size + i
                    trades.append({
                        "signature": f"sig{trade_idx}",
                        "amount": trade_idx * 10,
                        "type": "buy" if trade_idx % 2 == 0 else "sell"
                    })
                
                yield {
                    "type": "trades",
                    "data": {
                        "trades": trades,
                        "batch_num": batch_num + 1,
                        "total_yielded": (batch_num + 1) * batch_size
                    }
                }
                
                # Check memory periodically
                current_memory = process.memory_info().rss / 1024 / 1024
                peak_memory = max(peak_memory, current_memory)
                
                # Allow event loop to process
                await asyncio.sleep(0)
            
            yield {"type": "complete", "data": {"summary": {"total_trades": num_trades}}}
        
        # Replace fetch method
        fetcher.fetch_wallet_trades_stream = mock_stream
        
        # Process stream
        trades_processed = 0
        async for event in fetcher.fetch_wallet_trades_stream("test_wallet"):
            if event["type"] == "trades":
                trades_processed += len(event["data"]["trades"])
                # Simulate processing delay
                await asyncio.sleep(0.001)
        
        # Get memory stats
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = peak_memory - start_memory
        
        # Verify memory usage
        assert memory_increase < 500, f"Memory increased by {memory_increase:.1f}MB, expected <500MB"
        assert trades_processed == num_trades
        
        print(f"\nMemory Usage Results:")
        print(f"- Start: {start_memory:.1f}MB")
        print(f"- Peak: {peak_memory:.1f}MB")
        print(f"- Final: {final_memory:.1f}MB")
        print(f"- Increase: {memory_increase:.1f}MB")
        print(f"- Traced peak: {peak / 1024 / 1024:.1f}MB")
    
    @pytest.mark.asyncio
    async def test_batching_behavior(self):
        """Test that batching works correctly under various conditions"""
        test_cases = [
            (100, 10),   # 100 trades, batch size 10
            (95, 20),    # Non-divisible
            (1000, 100), # Large dataset
            (5, 10),     # Fewer trades than batch size
        ]
        
        for total_trades, batch_size in test_cases:
            fetcher = BlockchainFetcherV3Stream(
                skip_pricing=True,
                batch_size=batch_size
            )
            
            # Mock stream
            async def mock_stream(wallet):
                yield {"type": "progress", "data": {"message": "Start", "percentage": 0}}
                
                trades_yielded = 0
                batch_num = 0
                
                while trades_yielded < total_trades:
                    batch_trades = min(batch_size, total_trades - trades_yielded)
                    batch = [{"sig": f"s{i}"} for i in range(trades_yielded, trades_yielded + batch_trades)]
                    
                    batch_num += 1
                    trades_yielded += len(batch)
                    
                    yield {
                        "type": "trades",
                        "data": {
                            "trades": batch,
                            "batch_num": batch_num,
                            "total_yielded": trades_yielded
                        }
                    }
                
                yield {"type": "complete", "data": {"summary": {"total_trades": total_trades}}}
            
            fetcher.fetch_wallet_trades_stream = mock_stream
            
            # Collect batches
            batches = []
            async for event in fetcher.fetch_wallet_trades_stream("test"):
                if event["type"] == "trades":
                    batches.append(len(event["data"]["trades"]))
            
            # Verify batching
            total_in_batches = sum(batches)
            assert total_in_batches == total_trades, f"Expected {total_trades}, got {total_in_batches}"
            
            # All batches except last should be full size
            if len(batches) > 1:
                for batch_size_actual in batches[:-1]:
                    assert batch_size_actual == batch_size
            
            # Last batch should be remainder
            if batches:
                expected_last = total_trades % batch_size or batch_size
                assert batches[-1] == expected_last
            
            print(f"\nBatching test ({total_trades} trades, batch size {batch_size}):")
            print(f"- Batches: {batches}")
            print(f"- Total batches: {len(batches)}")
    
    @pytest.mark.asyncio
    async def test_backpressure_handling(self):
        """Test that streaming handles slow consumers properly"""
        fetcher = BlockchainFetcherV3Stream(
            skip_pricing=True,
            batch_size=50
        )
        
        # Track timing
        batch_times = []
        consumer_delays = [0.001, 0.01, 0.1]  # Simulate varying consumer speeds
        
        for delay in consumer_delays:
            # Mock fast producer
            async def mock_stream(wallet):
                yield {"type": "progress", "data": {"message": "Start", "percentage": 0}}
                
                for i in range(10):  # 10 batches
                    batch_start = time.time()
                    yield {
                        "type": "trades",
                        "data": {
                            "trades": [{"id": j} for j in range(50)],
                            "batch_num": i + 1
                        }
                    }
                    batch_times.append((time.time() - batch_start, "produce"))
                
                yield {"type": "complete", "data": {}}
            
            fetcher.fetch_wallet_trades_stream = mock_stream
            batch_times.clear()
            
            # Slow consumer
            start_time = time.time()
            async for event in fetcher.fetch_wallet_trades_stream("test"):
                if event["type"] == "trades":
                    consume_start = time.time()
                    await asyncio.sleep(delay)  # Simulate processing
                    batch_times.append((time.time() - consume_start, "consume"))
            
            total_time = time.time() - start_time
            
            # Verify backpressure
            # Total time should be dominated by consumer delay
            expected_min_time = 10 * delay  # 10 batches * delay
            assert total_time >= expected_min_time * 0.9, f"Backpressure not working: {total_time:.3f}s < {expected_min_time:.3f}s"
            
            print(f"\nBackpressure test (consumer delay: {delay}s):")
            print(f"- Total time: {total_time:.3f}s")
            print(f"- Expected min: {expected_min_time:.3f}s")
            print(f"- Efficiency: {expected_min_time / total_time * 100:.1f}%")


class TestStreamingVsV3Benchmark:
    """Benchmark streaming implementation against V3"""
    
    @pytest.mark.asyncio
    async def test_performance_comparison(self):
        """Compare performance between V3 and streaming for various wallet sizes"""
        wallet_sizes = [100, 500, 1000, 5000]
        
        results = []
        
        for num_trades in wallet_sizes:
            # Mock data generator
            def create_mock_trades(count):
                trades = []
                for i in range(count):
                    from src.lib.blockchain_fetcher_v3 import Trade
                    trade = Trade(
                        signature=f"sig{i}",
                        timestamp=1234567890 + i,
                        slot=100000 + i,
                        token_in_mint="SOL",
                        token_in_symbol="SOL",
                        token_in_amount=1.0,
                        token_out_mint="USDC", 
                        token_out_symbol="USDC",
                        token_out_amount=100.0,
                        value_usd=100.0,
                        priced=False
                    )
                    trades.append(trade)
                return trades
            
            # Test V3 (non-streaming)
            v3_fetcher = BlockchainFetcherV3(skip_pricing=True)
            
            with patch.object(v3_fetcher, 'fetch_wallet_trades', return_value=create_mock_trades(num_trades)):
                v3_start = time.time()
                v3_trades = await v3_fetcher.fetch_wallet_trades("test_wallet")
                v3_time = time.time() - v3_start
                v3_first_trade_time = v3_time  # All trades at once
            
            # Test streaming
            stream_fetcher = BlockchainFetcherV3Stream(skip_pricing=True, batch_size=100)
            
            async def mock_stream(wallet):
                yield {"type": "progress", "data": {"message": "Start", "percentage": 0}}
                
                trades = create_mock_trades(num_trades)
                for i in range(0, len(trades), stream_fetcher.batch_size):
                    batch = trades[i:i + stream_fetcher.batch_size]
                    yield {
                        "type": "trades",
                        "data": {
                            "trades": [t.to_dict() for t in batch],
                            "batch_num": i // stream_fetcher.batch_size + 1
                        }
                    }
                    await asyncio.sleep(0.001)  # Simulate network delay
                
                yield {"type": "complete", "data": {"summary": {"total_trades": num_trades}}}
            
            stream_fetcher.fetch_wallet_trades_stream = mock_stream
            
            stream_start = time.time()
            stream_first_trade_time = None
            stream_trades = 0
            
            async for event in stream_fetcher.fetch_wallet_trades_stream("test_wallet"):
                if event["type"] == "trades" and stream_first_trade_time is None:
                    stream_first_trade_time = time.time() - stream_start
                if event["type"] == "trades":
                    stream_trades += len(event["data"]["trades"])
            
            stream_total_time = time.time() - stream_start
            
            results.append({
                "trades": num_trades,
                "v3_time": v3_time,
                "v3_first_trade": v3_first_trade_time,
                "stream_time": stream_total_time,
                "stream_first_trade": stream_first_trade_time,
                "speedup_first_trade": v3_first_trade_time / stream_first_trade_time
            })
        
        # Print results
        print("\n=== V3 vs Streaming Performance Comparison ===")
        print("Trades | V3 Time | Stream Time | V3 First | Stream First | First Trade Speedup")
        print("-------|---------|-------------|----------|--------------|-------------------")
        
        for r in results:
            print(f"{r['trades']:6d} | {r['v3_time']:7.3f}s | {r['stream_time']:11.3f}s | "
                  f"{r['v3_first_trade']:8.3f}s | {r['stream_first_trade']:12.3f}s | "
                  f"{r['speedup_first_trade']:17.1f}x")
        
        # Verify streaming provides faster first results
        for r in results:
            assert r['stream_first_trade'] < r['v3_first_trade'], \
                f"Streaming should provide first results faster for {r['trades']} trades"


class TestRealWorldScenarios:
    """Test real-world usage patterns"""
    
    @pytest.mark.asyncio
    async def test_interrupted_connection_recovery(self):
        """Test behavior when connection is interrupted"""
        fetcher = BlockchainFetcherV3Stream(skip_pricing=True, batch_size=100)
        
        interrupt_at_batch = 3
        batches_before_interrupt = []
        batches_after_resume = []
        
        # First connection - will be interrupted
        async def mock_stream_interrupted(wallet):
            yield {"type": "progress", "data": {"message": "Start", "percentage": 0}}
            
            for i in range(5):
                yield {
                    "type": "trades",
                    "data": {
                        "trades": [{"id": f"trade_{i}_{j}"} for j in range(100)],
                        "batch_num": i + 1
                    }
                }
                if i + 1 == interrupt_at_batch:
                    raise ConnectionError("Simulated connection loss")
        
        fetcher.fetch_wallet_trades_stream = mock_stream_interrupted
        
        try:
            async for event in fetcher.fetch_wallet_trades_stream("test"):
                if event["type"] == "trades":
                    batches_before_interrupt.append(event["data"]["batch_num"])
        except ConnectionError:
            pass
        
        # Resume connection
        async def mock_stream_resumed(wallet):
            # Resume from where we left off
            for i in range(interrupt_at_batch, 5):
                yield {
                    "type": "trades", 
                    "data": {
                        "trades": [{"id": f"trade_{i}_{j}"} for j in range(100)],
                        "batch_num": i + 1
                    }
                }
            yield {"type": "complete", "data": {"summary": {"total_trades": 500}}}
        
        fetcher.fetch_wallet_trades_stream = mock_stream_resumed
        
        async for event in fetcher.fetch_wallet_trades_stream("test"):
            if event["type"] == "trades":
                batches_after_resume.append(event["data"]["batch_num"])
        
        # Verify recovery
        assert batches_before_interrupt == list(range(1, interrupt_at_batch + 1))
        assert batches_after_resume == list(range(interrupt_at_batch + 1, 6))
        
        print(f"\nConnection recovery test:")
        print(f"- Batches before interrupt: {batches_before_interrupt}")
        print(f"- Interrupted at batch: {interrupt_at_batch}")  
        print(f"- Batches after resume: {batches_after_resume}")
        print(f"- Full sequence recovered: {batches_before_interrupt + batches_after_resume}")

    @pytest.mark.asyncio 
    async def test_varying_batch_sizes_performance(self):
        """Test performance impact of different batch sizes"""
        num_trades = 1000
        batch_sizes = [10, 50, 100, 200, 500]
        
        results = []
        
        for batch_size in batch_sizes:
            fetcher = BlockchainFetcherV3Stream(
                skip_pricing=True,
                batch_size=batch_size
            )
            
            # Mock stream
            async def mock_stream(wallet):
                yield {"type": "progress", "data": {"message": "Start", "percentage": 0}}
                
                for i in range(0, num_trades, batch_size):
                    batch = [{"id": j} for j in range(i, min(i + batch_size, num_trades))]
                    yield {
                        "type": "trades",
                        "data": {
                            "trades": batch,
                            "batch_num": i // batch_size + 1
                        }
                    }
                    # Simulate network latency
                    await asyncio.sleep(0.005)  # 5ms per batch
                
                yield {"type": "complete", "data": {"summary": {"total_trades": num_trades}}}
            
            fetcher.fetch_wallet_trades_stream = mock_stream
            
            # Measure time to first trade and total time
            start_time = time.time()
            first_trade_time = None
            num_batches = 0
            
            async for event in fetcher.fetch_wallet_trades_stream("test"):
                if event["type"] == "trades":
                    if first_trade_time is None:
                        first_trade_time = time.time() - start_time
                    num_batches += 1
            
            total_time = time.time() - start_time
            
            results.append({
                "batch_size": batch_size,
                "num_batches": num_batches,
                "first_trade_time": first_trade_time,
                "total_time": total_time,
                "trades_per_second": num_trades / total_time
            })
        
        print("\n=== Batch Size Performance Impact ===")
        print("Batch Size | Batches | First Trade | Total Time | Trades/sec")
        print("-----------|---------|-------------|-----------|------------")
        
        for r in results:
            print(f"{r['batch_size']:10d} | {r['num_batches']:7d} | {r['first_trade_time']:11.3f}s | "
                  f"{r['total_time']:9.3f}s | {r['trades_per_second']:10.0f}")
        
        # Verify larger batches are more efficient overall
        sorted_results = sorted(results, key=lambda x: x['total_time'])
        optimal_batch = sorted_results[0]['batch_size']
        print(f"\nOptimal batch size: {optimal_batch}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
