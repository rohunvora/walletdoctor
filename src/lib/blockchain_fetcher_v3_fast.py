#!/usr/bin/env python3
"""
Blockchain Fetcher V3 Fast - Optimized for speed
Key optimizations:
1. RPC endpoint with 1000-signature pages
2. Parallel transaction batch fetching
3. Smart price caching with batch fetching
4. Memory-efficient streaming
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

# Set up logger first
logger = logging.getLogger(__name__)

# Environment variables
HELIUS_KEY = os.getenv("HELIUS_KEY")
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY")

# Log warning if keys are missing but don't fail at import time
if not HELIUS_KEY:
    logger.warning("HELIUS_KEY environment variable not set - trading endpoints will fail")
if not BIRDEYE_API_KEY:
    logger.warning("BIRDEYE_API_KEY environment variable not set - price fetching may fail")

# Constants
HELIUS_BASE = "https://api.helius.xyz/v0"
HELIUS_RPC_BASE = "https://mainnet.helius-rpc.com"
HELIUS_RPS = 50  # Updated for paid plan
BIRDEYE_RPS = 1
DUST_THRESHOLD = Decimal("0.0000001")
SOL_MINT = "So11111111111111111111111111111111111111112"
SIGNATURE_PAGE_LIMIT = 1000  # RPC supports up to 1000 signatures per page
TX_BATCH_SIZE = 100  # Batch size for transaction fetching

logger = logging.getLogger(__name__)

# Import base classes from V3
from .blockchain_fetcher_v3 import (
    Trade, Metrics, RateLimiter, PriceCache, 
    BlockchainFetcherV3, RateLimitedFetcher
)


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
    """Optimized V3 fetcher using RPC endpoint"""

    def __init__(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
        skip_pricing: bool = False,
    ):
        # Check for required keys at runtime
        if not HELIUS_KEY:
            raise ValueError("HELIUS_KEY environment variable is required for blockchain fetching")
        if not skip_pricing and not BIRDEYE_API_KEY:
            raise ValueError("BIRDEYE_API_KEY environment variable is required for price fetching")
            
        self.progress_callback = progress_callback or (lambda x: logger.info(x))
        self.helius_limiter = RateLimiter(HELIUS_RPS)
        self.birdeye_limiter = RateLimiter(BIRDEYE_RPS)
        self.helius_rate_limited_fetcher = RateLimitedFetcher(max_concurrent=40)
        self.session: Optional[aiohttp.ClientSession] = None
        self.metrics = Metrics()
        self.price_cache = FastPriceCache()
        self.skip_pricing = skip_pricing

    async def __aenter__(self):
        # Use connection pooling
        connector = aiohttp.TCPConnector(limit=40, limit_per_host=40)
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
        """Main entry point - optimized version using RPC"""
        self._report_progress(f"Starting FAST fetch for wallet: {wallet_address}")
        start_time = time.time()

        # Reset metrics
        self.metrics = Metrics()

        # Step 1: Fetch all signatures using RPC (1000 per page)
        signatures = await self._fetch_all_signatures(wallet_address)
        self.metrics.signatures_fetched = len(signatures)
        self._report_progress(f"Fetched {len(signatures)} signatures")

        # Step 2: Batch fetch full transactions
        transactions = await self._fetch_transactions_batch(signatures)
        self._report_progress(f"Fetched {len(transactions)} SWAP transactions")

        # Step 3: Extract trades
        trades = await self._extract_trades_with_dedup(transactions, wallet_address)
        self._report_progress(f"Extracted {len(trades)} unique trades")

        # Step 4: Fetch token metadata (batch optimized)
        await self._fetch_token_metadata_batch(trades)

        # Step 5: Apply dust filter
        filtered_trades = self._apply_dust_filter(trades)
        self._report_progress(f"After dust filter: {len(filtered_trades)} trades")

        # Step 6: Fetch prices (batch optimized)
        if not self.skip_pricing:
            await self._fetch_prices_batch(filtered_trades)
        else:
            self._report_progress("Skipping price fetching")

        # Step 7: Calculate P&L
        final_trades = self._calculate_pnl(filtered_trades)

        # Log metrics
        self.metrics.log_summary(self._report_progress)

        # Create response envelope with transactions
        response = self._create_response_envelope(wallet_address, final_trades, time.time() - start_time)
        
        # Add transactions for Helius price extraction
        if os.getenv('PRICE_HELIUS_ONLY', '').lower() == 'true':
            response['transactions'] = transactions
            logger.info(f"[PRICE] Including {len(transactions)} transactions for Helius price extraction")
        
        return response

    async def _fetch_all_signatures(self, wallet: str) -> List[str]:
        """Fetch all transaction signatures using RPC with 1000-sig pages"""
        all_signatures = []
        page = 0
        before_sig = None
        
        self._report_progress(f"Fetching signatures with {SIGNATURE_PAGE_LIMIT}-sig pages...")
        
        while True:
            page += 1
            
            # Fetch single page of signatures
            signatures, next_before_sig = await self._fetch_signature_page(wallet, before_sig)
            
            if signatures:
                all_signatures.extend(signatures)
                self._report_progress(f"Page {page}: {len(signatures)} signatures (total: {len(all_signatures)})")
            else:
                break
            
            # Update before_sig for next page
            if next_before_sig:
                before_sig = next_before_sig
            else:
                break
        
        self._report_progress(f"Signature fetch complete: {len(all_signatures)} total signatures in {page} pages")
        return all_signatures

    async def _fetch_signature_page(self, wallet: str, before_sig: Optional[str] = None) -> Tuple[List[str], Optional[str]]:
        """Fetch a single page of signatures using RPC"""
        url = f"{HELIUS_RPC_BASE}/?api-key={HELIUS_KEY}"
        headers = {"Content-Type": "application/json"}
        
        params = {"limit": SIGNATURE_PAGE_LIMIT}
        if before_sig:
            params["before"] = before_sig
            
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [wallet, params]
        }

        try:
            async with self.helius_rate_limited_fetcher:
                async with self.session.post(url, headers=headers, json=body, timeout=ClientTimeout(total=30)) as resp:
                    if resp.status == 429:
                        retry_after = int(resp.headers.get("Retry-After", "5"))
                        await asyncio.sleep(retry_after)
                        return await self._fetch_signature_page(wallet, before_sig)

                    resp.raise_for_status()
                    json_data = await resp.json()

                    if "result" not in json_data:
                        return [], None
                    
                    result = json_data["result"]
                    if not result:
                        return [], None
                    
                    # Extract signatures
                    signatures = [item["signature"] for item in result if "signature" in item]
                    
                    # Get next before signature from last item
                    next_before = result[-1]["signature"] if result else None
                    return signatures, next_before
                    
        except Exception as e:
            logger.error(f"Error fetching signatures: {e}")
            return [], None

    async def _fetch_transactions_batch(self, signatures: List[str]) -> List[Dict[str, Any]]:
        """Batch fetch full transactions in parallel"""
        all_transactions = []
        
        # Create all batch tasks
        batch_tasks = []
        for batch_idx in range(0, len(signatures), TX_BATCH_SIZE):
            batch_end = min(batch_idx + TX_BATCH_SIZE, len(signatures))
            batch_sigs = signatures[batch_idx:batch_end]
            batch_num = batch_idx // TX_BATCH_SIZE + 1
            
            task = self._fetch_single_batch(batch_sigs, batch_num)
            batch_tasks.append(task)
        
        # Process batches in parallel with controlled concurrency
        chunk_size = 40
        total_batches = len(batch_tasks)
        
        for i in range(0, len(batch_tasks), chunk_size):
            chunk = batch_tasks[i:i + chunk_size]
            chunk_results = await asyncio.gather(*chunk)
            
            for transactions in chunk_results:
                all_transactions.extend(transactions)
            
            processed = min(i + chunk_size, len(batch_tasks))
            self._report_progress(f"Processed {processed}/{total_batches} transaction batches...")
        
        return all_transactions

    async def _fetch_single_batch(self, batch_sigs: List[str], batch_num: int) -> List[Dict[str, Any]]:
        """Fetch a single batch of transactions"""
        try:
            url = f"{HELIUS_BASE}/transactions"
            params = {"api-key": HELIUS_KEY}
            body = {"transactions": batch_sigs}
            
            async with self.helius_rate_limited_fetcher:
                async with self.session.post(url, params=params, json=body, timeout=ClientTimeout(total=60)) as resp:
                    if resp.status == 429:
                        retry_after = int(resp.headers.get("Retry-After", "5"))
                        await asyncio.sleep(retry_after)
                        return await self._fetch_single_batch(batch_sigs, batch_num)
                    
                    resp.raise_for_status()
                    batch_data = await resp.json()
                    
                    # Filter valid swap transactions
                    valid_transactions = []
                    for tx in batch_data:
                        if tx and isinstance(tx, dict) and "signature" in tx:
                            # Check if it's a SWAP transaction
                            if "events" in tx and "swap" in tx.get("events", {}):
                                valid_transactions.append(tx)
                            elif "tokenTransfers" in tx and len(tx.get("tokenTransfers", [])) >= 2:
                                valid_transactions.append(tx)
                    
                    return valid_transactions
                    
        except Exception as e:
            logger.error(f"Error fetching transaction batch {batch_num}: {e}")
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
        try:
            url = f"{HELIUS_BASE}/token-metadata"
            params = {"api-key": HELIUS_KEY}

            async with self.helius_rate_limited_fetcher:
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
        
        # Count unique tokens to price
        unique_mints = set()
        cache_hits = 0
        cache_misses = 0

        # First pass: check cache and queue missing prices
        for trade in trades:
            for mint in [trade.token_in_mint, trade.token_out_mint]:
                if mint == SOL_MINT:
                    continue
                unique_mints.add(mint)

                cached = self.price_cache.get(mint, trade.timestamp)
                if cached is None:
                    cache_misses += 1
                    self.price_cache.add_pending(mint, trade.timestamp)
                else:
                    cache_hits += 1

        logger.info(f"[RCA] Unique mints: {len(unique_mints)}, Cache hits: {cache_hits}, Cache misses: {cache_misses}")

        # Get batches to fetch
        batches = self.price_cache.get_pending_batches()

        if batches:
            self._report_progress(f"Fetching {len(batches)} price batches...")
            logger.info(f"[RCA] Created {len(batches)} Birdeye batches for {cache_misses} missing prices")
            
            batch_start = time.time()
            batch_count = 0

            # Fetch in controlled parallelism (respect rate limit)
            for i in range(0, len(batches), 3):  # 3 parallel at most
                batch_group = batches[i : i + 3]
                group_start = time.time()
                
                tasks = [self._fetch_birdeye_batch(ts, mints, batch_num=i+j+1) for j, (ts, mints) in enumerate(batch_group)]
                await asyncio.gather(*tasks, return_exceptions=True)
                
                batch_count += len(batch_group)
                group_elapsed = time.time() - group_start
                logger.info(f"[RCA] Batch group {i//3 + 1}: {len(batch_group)} batches in {group_elapsed:.2f}s")
            
            total_elapsed = time.time() - batch_start
            logger.info(f"[RCA] All {batch_count} Birdeye batches completed in {total_elapsed:.2f}s")

        # Apply cached prices
        for trade in trades:
            await self._apply_cached_prices(trade)

    async def _fetch_birdeye_batch(self, timestamp: int, mints: List[str], batch_num: int = 0) -> Dict[str, Optional[Decimal]]:
        """Fetch a batch of prices from Birdeye"""
        start_time = time.time()
        await self.birdeye_limiter.acquire()
        acquire_time = time.time() - start_time
        
        if acquire_time > 0.1:
            logger.info(f"[RCA] Batch {batch_num}: Rate limit delay {acquire_time:.2f}s")

        try:
            # Use Birdeye batch endpoint
            url = "https://public-api.birdeye.so/public/multi_price"
            headers = {"X-API-KEY": BIRDEYE_API_KEY}
            params = {"list_address": ",".join(mints), "time": timestamp}
            
            logger.info(f"[RCA] Batch {batch_num}: Requesting prices for {len(mints)} tokens")

            if not self.session:
                raise RuntimeError("Session not initialized")

            async with self.session.get(url, headers=headers, params=params, timeout=ClientTimeout(total=30)) as resp:
                elapsed = time.time() - start_time
                logger.info(f"[RCA] Batch {batch_num}: Response status={resp.status} in {elapsed:.2f}s")
                
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success") and data.get("data"):
                        # Cache all results
                        ts_dt = datetime.fromtimestamp(timestamp)
                        success_count = 0
                        for mint, price_data in data["data"].items():
                            if price_data and "value" in price_data:
                                price = Decimal(str(price_data["value"]))
                                self.price_cache.set(mint, ts_dt, price)
                                success_count += 1
                            else:
                                self.price_cache.set(mint, ts_dt, None)
                        
                        logger.info(f"[RCA] Batch {batch_num}: Priced {success_count}/{len(mints)} tokens")
                elif resp.status == 429:
                    retry_after = resp.headers.get("Retry-After", "unknown")
                    logger.warning(f"[RCA] Batch {batch_num}: Rate limited! Retry-After: {retry_after}")
                else:
                    logger.warning(f"[RCA] Batch {batch_num}: Unexpected status {resp.status}")

        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            logger.error(f"[RCA] Batch {batch_num}: Timeout after {elapsed:.2f}s")
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[RCA] Batch {batch_num}: Error after {elapsed:.2f}s: {e}")

        return {}

    # Copy remaining methods from V3 (unchanged)
    async def _extract_trades_with_dedup(self, transactions, wallet):
        v3 = BlockchainFetcherV3()
        v3.metrics = self.metrics
        return await v3._extract_trades_with_dedup(transactions, wallet)

    def _apply_dust_filter(self, trades):
        v3 = BlockchainFetcherV3()
        v3.metrics = self.metrics
        return v3._apply_dust_filter(trades)

    async def _apply_cached_prices(self, trade):
        v3 = BlockchainFetcherV3()
        v3.price_cache = self.price_cache
        v3.metrics = self.metrics
        return await v3._apply_cached_prices(trade)

    def _calculate_pnl(self, trades):
        v3 = BlockchainFetcherV3()
        return v3._calculate_pnl(trades)

    def _create_response_envelope(self, wallet, trades, elapsed):
        v3 = BlockchainFetcherV3()
        v3.metrics = self.metrics
        return v3._create_response_envelope(wallet, trades, elapsed)


# Fast convenience functions
def fetch_wallet_trades_fast(
    wallet_address: str, progress_callback: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    """Fast synchronous wrapper"""

    async def _fetch():
        async with BlockchainFetcherV3Fast(
            progress_callback=progress_callback,
            skip_pricing=False
        ) as fetcher:
            return await fetcher.fetch_wallet_trades(wallet_address)

    return asyncio.run(_fetch())


if __name__ == "__main__":
    # Quick test
    wallet = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
    print("Testing FAST fetcher with RPC endpoint...")

    result = fetch_wallet_trades_fast(wallet, print)

    print(f"\nCompleted in {result['elapsed_seconds']}s")
    print(f"Fetched {result['summary']['total_trades']} trades")
