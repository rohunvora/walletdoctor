#!/usr/bin/env python3
"""
Blockchain Fetcher V3 Streaming - Yields partial results for real-time updates
Based on BlockchainFetcherV3 but with async generators for streaming
"""

import os
import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional, Callable, Tuple
from decimal import Decimal
import time
import logging

# Import base classes and utilities from V3
from .blockchain_fetcher_v3 import (
    BlockchainFetcherV3, Trade, Metrics, HELIUS_KEY, 
    SIGNATURE_PAGE_LIMIT, TX_BATCH_SIZE, logger
)

# Streaming event types
STREAM_EVENT_PROGRESS = "progress"
STREAM_EVENT_TRADES = "trades"
STREAM_EVENT_METADATA = "metadata"
STREAM_EVENT_COMPLETE = "complete"
STREAM_EVENT_ERROR = "error"


class BlockchainFetcherV3Stream(BlockchainFetcherV3):
    """Streaming version of V3 fetcher that yields partial results"""
    
    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None, 
                 skip_pricing: bool = False, parallel_pages: int = 40,
                 batch_size: int = 100):
        """
        Initialize streaming fetcher
        
        Args:
            progress_callback: Optional callback for progress messages
            skip_pricing: Skip price fetching for faster results
            parallel_pages: Number of pages to fetch concurrently
            batch_size: Number of trades to yield per batch
        """
        super().__init__(progress_callback, skip_pricing, parallel_pages)
        self.batch_size = batch_size
        self._yielded_trades = 0
        self._total_signatures = 0
        
    async def fetch_wallet_trades_stream(self, wallet_address: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Fetch and yield trades for a wallet in streaming fashion
        
        Yields:
            Dict with event type and data:
            - {"type": "progress", "data": {"message": str, "percentage": float}}
            - {"type": "trades", "data": {"trades": List[Trade], "batch_num": int}}
            - {"type": "metadata", "data": {"updated_trades": List[Trade]}}
            - {"type": "complete", "data": {"summary": dict, "metrics": dict}}
            - {"type": "error", "data": {"error": str}}
        """
        if not HELIUS_KEY:
            yield {
                "type": STREAM_EVENT_ERROR,
                "data": {"error": "HELIUS_KEY environment variable not set"}
            }
            return
            
        try:
            start_time = time.time()
            step_times = {}
            
            # Yield initial progress
            yield {
                "type": STREAM_EVENT_PROGRESS,
                "data": {
                    "message": f"Starting fetch for wallet: {wallet_address}",
                    "percentage": 0.0,
                    "step": "initializing"
                }
            }
            
            # Step 1: Fetch signatures with progress updates
            step_start = time.time()
            signatures = []
            async for sig_batch in self._fetch_signatures_stream(wallet_address):
                signatures.extend(sig_batch)
                self._total_signatures = len(signatures)
                
                yield {
                    "type": STREAM_EVENT_PROGRESS,
                    "data": {
                        "message": f"Fetched {len(signatures)} signatures",
                        "percentage": min(len(signatures) / 10000 * 20, 20),  # Cap at 20% for signatures
                        "step": "fetching_signatures",
                        "signatures_count": len(signatures)
                    }
                }
            
            step_times['fetch_signatures'] = time.time() - step_start
            
            # Step 2: Fetch transactions in batches and yield trades
            step_start = time.time()
            all_trades = []
            batch_num = 0
            
            async for tx_batch in self._fetch_transactions_stream(signatures):
                # Extract trades from this batch of transactions
                trades = await self._extract_trades_with_dedup(tx_batch, wallet_address)
                
                if trades:
                    all_trades.extend(trades)
                    
                    # Yield trades in configured batch sizes
                    while len(trades) >= self.batch_size:
                        batch_to_yield = trades[:self.batch_size]
                        trades = trades[self.batch_size:]
                        batch_num += 1
                        
                        # Convert to dict format
                        trades_dict = [t.to_dict() for t in batch_to_yield]
                        
                        yield {
                            "type": STREAM_EVENT_TRADES,
                            "data": {
                                "trades": trades_dict,
                                "batch_num": batch_num,
                                "total_yielded": self._yielded_trades + len(batch_to_yield)
                            }
                        }
                        
                        self._yielded_trades += len(batch_to_yield)
                        
                        # Progress update
                        progress = 20 + (self._yielded_trades / max(self._total_signatures, 1)) * 40
                        yield {
                            "type": STREAM_EVENT_PROGRESS,
                            "data": {
                                "message": f"Processing trades: {self._yielded_trades} completed",
                                "percentage": min(progress, 60),  # Cap at 60% for trades
                                "step": "processing_trades",
                                "trades_count": self._yielded_trades
                            }
                        }
            
            # Yield any remaining trades
            if trades:
                batch_num += 1
                trades_dict = [t.to_dict() for t in trades]
                yield {
                    "type": STREAM_EVENT_TRADES,
                    "data": {
                        "trades": trades_dict,
                        "batch_num": batch_num,
                        "total_yielded": self._yielded_trades + len(trades)
                    }
                }
                self._yielded_trades += len(trades)
            
            step_times['fetch_transactions'] = time.time() - step_start
            
            # Step 3: Fetch metadata and update trades
            step_start = time.time()
            yield {
                "type": STREAM_EVENT_PROGRESS,
                "data": {
                    "message": "Fetching token metadata...",
                    "percentage": 65,
                    "step": "fetching_metadata"
                }
            }
            
            await self._fetch_token_metadata(all_trades)
            step_times['fetch_metadata'] = time.time() - step_start
            
            # Yield metadata update event
            # In a real implementation, we'd track which trades were updated
            # For now, signal that metadata is complete
            yield {
                "type": STREAM_EVENT_METADATA,
                "data": {
                    "message": "Token metadata fetched",
                    "trades_updated": len(all_trades)
                }
            }
            
            # Step 4: Apply dust filter
            step_start = time.time()
            filtered_trades = self._apply_dust_filter(all_trades)
            step_times['dust_filter'] = time.time() - step_start
            dust_filtered_count = len(all_trades) - len(filtered_trades)
            
            yield {
                "type": STREAM_EVENT_PROGRESS,
                "data": {
                    "message": f"Applied dust filter: {dust_filtered_count} trades filtered",
                    "percentage": 70,
                    "step": "filtering",
                    "dust_filtered": dust_filtered_count
                }
            }
            
            # Step 5: Price fetching (if not skipped)
            if not self.skip_pricing:
                step_start = time.time()
                yield {
                    "type": STREAM_EVENT_PROGRESS,
                    "data": {
                        "message": "Fetching prices...",
                        "percentage": 75,
                        "step": "fetching_prices"
                    }
                }
                
                await self._fetch_prices_with_cache(filtered_trades)
                step_times['fetch_prices'] = time.time() - step_start
                
                yield {
                    "type": STREAM_EVENT_PROGRESS,
                    "data": {
                        "message": "Prices fetched",
                        "percentage": 90,
                        "step": "prices_complete"
                    }
                }
            else:
                step_times['fetch_prices'] = 0
                yield {
                    "type": STREAM_EVENT_PROGRESS,
                    "data": {
                        "message": "Skipping price fetching",
                        "percentage": 90,
                        "step": "prices_skipped"
                    }
                }
            
            # Step 6: Calculate P&L
            step_start = time.time()
            final_trades = self._calculate_pnl(filtered_trades)
            step_times['calculate_pnl'] = time.time() - step_start
            
            # Calculate summary statistics
            total_time = time.time() - start_time
            summary = self._calculate_summary(wallet_address, final_trades, total_time)
            
            # Yield complete event with summary
            yield {
                "type": STREAM_EVENT_COMPLETE,
                "data": {
                    "summary": summary,
                    "metrics": {
                        "signatures_fetched": self.metrics.signatures_fetched,
                        "trades_parsed": self.metrics.signatures_parsed,
                        "events_swap_rows": self.metrics.events_swap_rows,
                        "fallback_rows": self.metrics.fallback_rows,
                        "dust_filtered": self.metrics.dust_rows,
                        "unpriced_rows": self.metrics.unpriced_rows
                    },
                    "timing": step_times,
                    "total_time": total_time
                }
            }
            
        except Exception as e:
            logger.error(f"Error in streaming fetch: {e}")
            yield {
                "type": STREAM_EVENT_ERROR,
                "data": {"error": str(e)}
            }
    
    async def _fetch_signatures_stream(self, wallet: str) -> AsyncGenerator[List[str], None]:
        """Fetch signatures and yield them in batches"""
        page = 0
        consecutive_empty_pages = 0
        before_sig = None
        batch_signatures = []
        
        while True:
            page += 1
            
            # Warn at 120 pages
            if page > 120:
                logger.warning(f"Large wallet: {page} pages for {wallet}")
            
            # Fetch single page of signatures
            signatures, next_before_sig, is_empty, hit_rate_limit = await self._fetch_single_page(
                wallet, page, before_sig
            )
            
            if hit_rate_limit:
                # Simple exponential backoff
                wait_time = min(5 * (2 ** min(page // 10, 3)), 20)
                await asyncio.sleep(wait_time)
                page -= 1  # Retry same page
                continue
            
            if signatures:
                batch_signatures.extend(signatures)
                consecutive_empty_pages = 0
                self.metrics.signatures_fetched += len(signatures)
                
                # Yield batch when we have enough
                if len(batch_signatures) >= 1000:
                    yield batch_signatures
                    batch_signatures = []
            else:
                consecutive_empty_pages += 1
                if consecutive_empty_pages > 5:
                    break
            
            # Update before_sig for next page
            if next_before_sig:
                before_sig = next_before_sig
            else:
                # No more pages
                break
        
        # Yield any remaining signatures
        if batch_signatures:
            yield batch_signatures
    
    async def _fetch_transactions_stream(self, signatures: List[str]) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Fetch transactions in batches and yield them"""
        total_batches = (len(signatures) + TX_BATCH_SIZE - 1) // TX_BATCH_SIZE
        
        # Process in chunks to yield results faster
        chunk_size = min(self.parallel_pages, 40)
        
        for batch_idx in range(0, len(signatures), TX_BATCH_SIZE * chunk_size):
            batch_end = min(batch_idx + TX_BATCH_SIZE * chunk_size, len(signatures))
            chunk_sigs = signatures[batch_idx:batch_end]
            
            # Create tasks for this chunk
            tasks = []
            for i in range(0, len(chunk_sigs), TX_BATCH_SIZE):
                sigs_end = min(i + TX_BATCH_SIZE, len(chunk_sigs))
                batch_sigs = chunk_sigs[i:sigs_end]
                batch_num = (batch_idx + i) // TX_BATCH_SIZE + 1
                
                task = self._fetch_single_batch(batch_sigs, batch_num, total_batches)
                tasks.append(task)
            
            # Fetch chunk in parallel
            chunk_results = await asyncio.gather(*tasks)
            
            # Yield all transactions from this chunk
            chunk_transactions = []
            for transactions in chunk_results:
                chunk_transactions.extend(transactions)
            
            if chunk_transactions:
                yield chunk_transactions
    
    def _calculate_summary(self, wallet: str, trades: List[Trade], elapsed_time: float) -> Dict[str, Any]:
        """Calculate summary statistics"""
        # Calculate analytics
        total_volume = sum(t.value_usd for t in trades if t.value_usd)
        total_pnl = sum(t.pnl_usd for t in trades)
        
        # Get unique tokens
        unique_tokens = set()
        for trade in trades:
            unique_tokens.add(trade.token_in_symbol)
            unique_tokens.add(trade.token_out_symbol)
        
        # Calculate from/to slots
        if trades:
            from_slot = min(t.slot for t in trades)
            to_slot = max(t.slot for t in trades)
        else:
            from_slot = to_slot = 0
        
        return {
            "wallet": wallet,
            "total_trades": len(trades),
            "total_volume": float(total_volume) if total_volume else 0.0,
            "total_pnl_usd": float(total_pnl),
            "unique_tokens": len(unique_tokens),
            "from_slot": from_slot,
            "to_slot": to_slot,
            "elapsed_seconds": round(elapsed_time, 2),
            "priced_trades": sum(1 for t in trades if t.priced),
            "metrics": {
                "signatures_fetched": self.metrics.signatures_fetched,
                "signatures_parsed": self.metrics.signatures_parsed,
                "events_swap_rows": self.metrics.events_swap_rows,
                "fallback_rows": self.metrics.fallback_rows,
                "dust_filtered": self.metrics.dust_rows
            }
        }


# Convenience function for testing
async def test_streaming_fetcher(wallet_address: str):
    """Test the streaming fetcher"""
    async with BlockchainFetcherV3Stream(skip_pricing=True) as fetcher:
        trade_count = 0
        
        async for event in fetcher.fetch_wallet_trades_stream(wallet_address):
            event_type = event["type"]
            data = event["data"]
            
            if event_type == STREAM_EVENT_PROGRESS:
                print(f"Progress: {data['message']} ({data['percentage']:.1f}%)")
            elif event_type == STREAM_EVENT_TRADES:
                trade_count += len(data["trades"])
                print(f"Received batch {data['batch_num']}: {len(data['trades'])} trades (total: {trade_count})")
            elif event_type == STREAM_EVENT_METADATA:
                print(f"Metadata: {data['message']}")
            elif event_type == STREAM_EVENT_COMPLETE:
                print(f"Complete! Summary: {data['summary']['total_trades']} trades in {data['total_time']:.1f}s")
            elif event_type == STREAM_EVENT_ERROR:
                print(f"Error: {data['error']}")


if __name__ == "__main__":
    # Test with a wallet
    import sys
    wallet = sys.argv[1] if len(sys.argv) > 1 else "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
    asyncio.run(test_streaming_fetcher(wallet)) 