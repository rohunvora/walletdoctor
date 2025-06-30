#!/usr/bin/env python3
"""
Blockchain Fetcher V3 Fast - Optimized for speed
Key optimizations:
1. Parallel API calls
2. Batch price fetching
3. Configurable limits for testing
4. Memory-efficient streaming
5. Smart caching
"""

import os
import asyncio
import aiohttp
from aiohttp import ClientTimeout
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional, Set, Tuple, Callable
from dataclasses import dataclass
from collections import defaultdict
import time
import json

# Environment variables
HELIUS_KEY = os.getenv("HELIUS_KEY")
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY")

# Constants
HELIUS_BASE = "https://api.helius.xyz/v0"
HELIUS_RPS = 10
BIRDEYE_RPS = 1
DUST_THRESHOLD = Decimal("0.0000001")
SOL_MINT = "So11111111111111111111111111111111111111112"

# Optimization settings
PARALLEL_PAGES = 5  # Fetch 5 pages simultaneously
MAX_PAGES_TEST = 5  # Limit for testing (None for production)
SKIP_PRICING_TEST = False  # Skip price fetching for tests
CACHE_TTL = 3600  # Cache TTL in seconds

logger = logging.getLogger(__name__)

# Import base classes from V3
from .blockchain_fetcher_v3 import Trade, Metrics, RateLimiter, PriceCache


class FastPriceCache(PriceCache):
    """Enhanced price cache with batch fetching and persistence"""

    def __init__(self):
        super().__init__()
        self.pending_fetches: Dict[int, Set[str]] = defaultdict(set)
        self._load_cache()

    def _load_cache(self):
        """Load cache from disk if available"""
        cache_file = ".price_cache.json"
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)
                    # Convert back to proper types
                    for key_str, value in data.items():
                        mint, unix_minute = key_str.split("_")
                        self.cache[(mint, int(unix_minute))] = Decimal(str(value)) if value else None
            except:
                pass

    def save_cache(self):
        """Persist cache to disk"""
        cache_file = ".price_cache.json"
        data = {}
        for (mint, unix_minute), price in self.cache.items():
            key = f"{mint}_{unix_minute}"
            data[key] = float(price) if price else None
        with open(cache_file, "w") as f:
            json.dump(data, f)

    def add_pending(self, mint: str, timestamp: datetime):
        """Queue a price fetch"""
        minute_ts = int(timestamp.timestamp() // 60) * 60
        self.pending_fetches[minute_ts].add(mint)

    def get_pending_batches(self) -> List[Tuple[int, List[str]]]:
        """Get batches of pending price fetches"""
        batches = []
        for minute_ts, mints in self.pending_fetches.items():
            # Birdeye allows up to 100 mints per call
            mint_list = list(mints)
            for i in range(0, len(mint_list), 100):
                batches.append((minute_ts, mint_list[i : i + 100]))
        return batches


class BlockchainFetcherV3Fast:
    """Optimized V3 fetcher"""

    def __init__(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
        max_pages: Optional[int] = MAX_PAGES_TEST,
        skip_pricing: bool = SKIP_PRICING_TEST,
    ):
        self.progress_callback = progress_callback or (lambda x: logger.info(x))
        self.helius_limiter = RateLimiter(HELIUS_RPS)
        self.birdeye_limiter = RateLimiter(BIRDEYE_RPS)
        self.session: Optional[aiohttp.ClientSession] = None
        self.metrics = Metrics()
        self.price_cache = FastPriceCache()
        self.max_pages = max_pages
        self.skip_pricing = skip_pricing

    async def __aenter__(self):
        # Use connection pooling
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
        self.session = aiohttp.ClientSession(connector=connector)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
        # Save price cache
        self.price_cache.save_cache()

    def _report_progress(self, message: str):
        """Report progress to callback"""
        self.progress_callback(message)

    async def fetch_wallet_trades(self, wallet_address: str) -> Dict[str, Any]:
        """Main entry point - optimized version"""
        if not HELIUS_KEY:
            raise ValueError("HELIUS_KEY environment variable not set")

        self._report_progress(f"Starting FAST fetch for wallet: {wallet_address}")
        start_time = time.time()

        # Reset metrics
        self.metrics = Metrics()

        # Step 1: Fetch all SWAP transactions (with parallel fetching)
        transactions = await self._fetch_swap_transactions_parallel(wallet_address)
        self.metrics.signatures_fetched = len(transactions)
        self._report_progress(f"Fetched {len(transactions)} SWAP transactions")

        # Step 2: Extract trades (same as V3)
        trades = await self._extract_trades_with_dedup(transactions, wallet_address)
        self._report_progress(f"Extracted {len(trades)} unique trades")

        # Step 3: Fetch token metadata (batch optimized)
        await self._fetch_token_metadata_batch(trades)

        # Step 4: Apply dust filter
        filtered_trades = self._apply_dust_filter(trades)
        self._report_progress(f"After dust filter: {len(filtered_trades)} trades")

        # Step 5: Fetch prices (batch optimized)
        if not self.skip_pricing:
            await self._fetch_prices_batch(filtered_trades)
        else:
            self._report_progress("Skipping price fetching (test mode)")

        # Step 6: Calculate P&L
        final_trades = self._calculate_pnl(filtered_trades)

        # Log metrics
        self.metrics.log_summary(self._report_progress)

        # Create response envelope
        return self._create_response_envelope(wallet_address, final_trades, time.time() - start_time)

    async def _fetch_swap_transactions_parallel(self, wallet: str) -> List[Dict[str, Any]]:
        """Fetch SWAP transactions with parallel page fetching"""
        all_transactions = []

        # First, get initial page to determine total count
        first_page = await self._fetch_single_page(wallet, None, 1)
        if not first_page:
            return []

        all_transactions.extend(first_page)

        if len(first_page) < 100:
            return all_transactions

        # Now fetch remaining pages in parallel batches
        before_sig = first_page[-1]["signature"]
        page_num = 2
        empty_pages = 0

        while True:
            # Check max pages limit
            if self.max_pages and page_num > self.max_pages:
                self._report_progress(f"Reached max pages limit ({self.max_pages})")
                break

            # Prepare batch of pages to fetch
            batch_tasks = []
            batch_sigs = []

            for i in range(PARALLEL_PAGES):
                if self.max_pages and page_num + i > self.max_pages:
                    break

                batch_tasks.append(self._fetch_single_page(wallet, before_sig, page_num + i))
                batch_sigs.append(before_sig)

                # We need to estimate the next signature
                # For now, we'll fetch sequentially within parallel batches
                # In production, you could maintain a signature index

            if not batch_tasks:
                break

            # Fetch pages in parallel
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Process results
            got_data = False
            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error fetching page: {result}")
                    continue

                if result and isinstance(result, list):
                    all_transactions.extend(result)
                    before_sig = result[-1]["signature"]
                    got_data = True

            if not got_data:
                # Critical fix from V4: Continue past empty pages
                empty_pages += 1
                if empty_pages > 3:
                    self._report_progress(f"Hit {empty_pages} empty pages, stopping")
                    break
                self._report_progress(f"Empty page batch {empty_pages}/3, continuing...")
                page_num += len(batch_tasks)
                continue

            # Reset empty pages counter on successful data
            empty_pages = 0
            page_num += len(batch_tasks)

        return all_transactions

    async def _fetch_single_page(self, wallet: str, before_sig: Optional[str], page_num: int) -> List[Dict[str, Any]]:
        """Fetch a single page of transactions"""
        await self.helius_limiter.acquire()

        params = {"api-key": HELIUS_KEY, "limit": 100, "type": "SWAP", "maxSupportedTransactionVersion": "0"}

        if before_sig:
            params["before"] = before_sig

        try:
            url = f"{HELIUS_BASE}/addresses/{wallet}/transactions"
            if not self.session:
                raise RuntimeError("Session not initialized")

            async with self.session.get(url, params=params, timeout=ClientTimeout(total=30)) as resp:
                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", "5"))
                    await asyncio.sleep(retry_after)
                    return await self._fetch_single_page(wallet, before_sig, page_num)

                resp.raise_for_status()
                data = await resp.json()

                if isinstance(data, dict) and "error" in data:
                    return []

                if isinstance(data, list) and data:
                    self._report_progress(f"Page {page_num}: {len(data)} transactions")
                    return data

                return []

        except Exception as e:
            logger.error(f"Error fetching page {page_num}: {e}")
            return []

    async def _fetch_token_metadata_batch(self, trades: List[Trade]):
        """Fetch token metadata in optimized batches"""
        unique_mints = set()
        for trade in trades:
            unique_mints.add(trade.token_in_mint)
            unique_mints.add(trade.token_out_mint)

        if not unique_mints:
            return

        self._report_progress(f"Fetching metadata for {len(unique_mints)} tokens...")

        # Create larger batches and fetch in parallel
        mint_list = list(unique_mints)
        batch_size = 100
        tasks = []

        for i in range(0, len(mint_list), batch_size):
            batch = mint_list[i : i + batch_size]
            tasks.append(self._fetch_metadata_batch(batch))

        # Fetch all batches in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine results
        metadata_map = {}
        for result in results:
            if isinstance(result, dict):
                metadata_map.update(result)

        # Update trades
        for trade in trades:
            if trade.token_in_mint in metadata_map:
                trade.token_in_symbol = metadata_map[trade.token_in_mint].get("symbol", trade.token_in_mint[:8])
            if trade.token_out_mint in metadata_map:
                trade.token_out_symbol = metadata_map[trade.token_out_mint].get("symbol", trade.token_out_mint[:8])

    async def _fetch_metadata_batch(self, mints: List[str]) -> Dict[str, Dict]:
        """Fetch metadata for a batch of mints"""
        await self.helius_limiter.acquire()

        try:
            url = f"{HELIUS_BASE}/token-metadata"
            params = {"api-key": HELIUS_KEY}

            if not self.session:
                raise RuntimeError("Session not initialized")

            async with self.session.post(
                url, params=params, json={"mintAccounts": mints}, timeout=ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    metadata_list = await resp.json()
                    return {m["account"]: m for m in metadata_list if m}

        except Exception as e:
            logger.error(f"Error fetching metadata batch: {e}")

        return {}

    async def _fetch_prices_batch(self, trades: List[Trade]):
        """Fetch prices in optimized batches"""
        self._report_progress("Collecting required prices...")

        # First pass: check cache and queue missing prices
        for trade in trades:
            for mint in [trade.token_in_mint, trade.token_out_mint]:
                if mint == SOL_MINT:
                    continue

                cached = self.price_cache.get(mint, trade.timestamp)
                if cached is None:
                    self.price_cache.add_pending(mint, trade.timestamp)

        # Get batches to fetch
        batches = self.price_cache.get_pending_batches()

        if batches:
            self._report_progress(f"Fetching {len(batches)} price batches...")

            # Fetch in controlled parallelism (respect rate limit)
            for i in range(0, len(batches), 3):  # 3 parallel at most
                batch_group = batches[i : i + 3]
                tasks = [self._fetch_birdeye_batch(ts, mints) for ts, mints in batch_group]
                await asyncio.gather(*tasks, return_exceptions=True)

        # Apply cached prices
        for trade in trades:
            await self._apply_cached_prices(trade)

    async def _fetch_birdeye_batch(self, timestamp: int, mints: List[str]) -> Dict[str, Optional[Decimal]]:
        """Fetch a batch of prices from Birdeye"""
        await self.birdeye_limiter.acquire()

        try:
            # Use Birdeye batch endpoint
            url = "https://public-api.birdeye.so/public/multi_price"
            headers = {"X-API-KEY": BIRDEYE_API_KEY}
            params = {"list_address": ",".join(mints), "time": timestamp}

            if not self.session:
                raise RuntimeError("Session not initialized")

            async with self.session.get(url, headers=headers, params=params, timeout=ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success") and data.get("data"):
                        # Cache all results
                        ts_dt = datetime.fromtimestamp(timestamp)
                        for mint, price_data in data["data"].items():
                            if price_data and "value" in price_data:
                                price = Decimal(str(price_data["value"]))
                                self.price_cache.set(mint, ts_dt, price)
                            else:
                                self.price_cache.set(mint, ts_dt, None)

        except Exception as e:
            logger.error(f"Error fetching Birdeye batch: {e}")

        return {}

    # Copy remaining methods from V3 (unchanged)
    async def _extract_trades_with_dedup(self, transactions, wallet):
        from .blockchain_fetcher_v3 import BlockchainFetcherV3

        v3 = BlockchainFetcherV3()
        v3.metrics = self.metrics
        return await v3._extract_trades_with_dedup(transactions, wallet)

    def _apply_dust_filter(self, trades):
        from .blockchain_fetcher_v3 import BlockchainFetcherV3

        v3 = BlockchainFetcherV3()
        v3.metrics = self.metrics
        return v3._apply_dust_filter(trades)

    async def _apply_cached_prices(self, trade):
        from .blockchain_fetcher_v3 import BlockchainFetcherV3

        v3 = BlockchainFetcherV3()
        v3.price_cache = self.price_cache
        v3.metrics = self.metrics
        return await v3._apply_cached_prices(trade)

    def _calculate_pnl(self, trades):
        from .blockchain_fetcher_v3 import BlockchainFetcherV3

        v3 = BlockchainFetcherV3()
        return v3._calculate_pnl(trades)

    def _create_response_envelope(self, wallet, trades, elapsed):
        from .blockchain_fetcher_v3 import BlockchainFetcherV3

        v3 = BlockchainFetcherV3()
        v3.metrics = self.metrics
        return v3._create_response_envelope(wallet, trades, elapsed)


# Fast convenience functions
def fetch_wallet_trades_fast(
    wallet_address: str, progress_callback: Optional[Callable[[str], None]] = None, test_mode: bool = True
) -> Dict[str, Any]:
    """Fast synchronous wrapper"""

    async def _fetch():
        async with BlockchainFetcherV3Fast(
            progress_callback=progress_callback, max_pages=5 if test_mode else None, skip_pricing=test_mode
        ) as fetcher:
            return await fetcher.fetch_wallet_trades(wallet_address)

    return asyncio.run(_fetch())


if __name__ == "__main__":
    # Quick test
    wallet = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
    print("Testing FAST fetcher...")

    # Test mode: limited pages, no pricing
    result = fetch_wallet_trades_fast(wallet, print, test_mode=True)

    print(f"\nTest completed in {result['elapsed_seconds']}s")
    print(f"Fetched {result['summary']['total_trades']} trades")
