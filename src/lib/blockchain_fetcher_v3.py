#!/usr/bin/env python3
"""
Blockchain Fetcher V3 - Full implementation with expert recommendations
- Removes source=UNKNOWN query (404 fix)
- Implements tokenTransfers fallback parser
- Proper hop deduplication
- Dust filter
- Birdeye price caching
- Response envelope
- Comprehensive metrics
"""

import os
import asyncio
import aiohttp
from aiohttp import ClientTimeout
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional, Set, Tuple, Callable
from dataclasses import dataclass, field
from collections import defaultdict
import time

# Environment variables
HELIUS_KEY = os.getenv("HELIUS_KEY")
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY")

# Constants
HELIUS_BASE = "https://api.helius.xyz/v0"
HELIUS_RPS = 50  # Updated for paid plan
BIRDEYE_RPS = 1
DUST_THRESHOLD = Decimal("0.0000001")  # 10^-7
SOL_MINT = "So11111111111111111111111111111111111111112"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Trade structure - one per transaction signature"""

    signature: str
    slot: int
    timestamp: datetime
    token_in_mint: str
    token_in_symbol: str
    token_in_amount: Decimal
    token_out_mint: str
    token_out_symbol: str
    token_out_amount: Decimal
    price_usd: Optional[Decimal]
    value_usd: Optional[Decimal]
    pnl_usd: Decimal = Decimal("0")
    fees_usd: Decimal = Decimal("0")
    dex: str = "UNKNOWN"
    priced: bool = False
    tx_type: str = "swap"

    def _round_decimal(self, value: Optional[Decimal], places: int = 4) -> Optional[float]:
        """Round decimal to specified places using banker's rounding"""
        if value is None:
            return None
        # Use quantize for banker's rounding (ROUND_HALF_EVEN)
        rounded = value.quantize(Decimal(f'0.{"0" * places}'))
        return float(rounded)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        # Determine action based on SOL
        if self.token_out_mint == SOL_MINT:
            action = "sell"
            token = self.token_in_symbol
            amount = self._round_decimal(self.token_in_amount, 6)  # Keep 6 decimals for amounts
        else:
            action = "buy"
            token = self.token_out_symbol
            amount = self._round_decimal(self.token_out_amount, 6)  # Keep 6 decimals for amounts

        return {
            "timestamp": self.timestamp.isoformat(),
            "signature": self.signature,
            "action": action,
            "token": token,
            "amount": amount,
            "token_in": {
                "mint": self.token_in_mint,
                "symbol": self.token_in_symbol,
                "amount": self._round_decimal(self.token_in_amount, 6)  # Keep 6 decimals for amounts
            },
            "token_out": {
                "mint": self.token_out_mint,
                "symbol": self.token_out_symbol,
                "amount": self._round_decimal(self.token_out_amount, 6)  # Keep 6 decimals for amounts
            },
            "price": self._round_decimal(self.price_usd, 4),
            "value_usd": self._round_decimal(self.value_usd, 4),
            "pnl_usd": self._round_decimal(self.pnl_usd, 4),
            "fees_usd": self._round_decimal(self.fees_usd, 4),
            "priced": self.priced,
            "dex": self.dex,
            "tx_type": self.tx_type,
        }


@dataclass
class Metrics:
    """Metrics tracking"""

    signatures_fetched: int = 0
    signatures_parsed: int = 0
    events_swap_rows: int = 0
    fallback_rows: int = 0
    dup_rows: int = 0
    parser_errors: int = 0
    dust_rows: int = 0
    unpriced_rows: int = 0

    def log_summary(self, logger_func: Callable[[str], None]):
        """Log metrics summary"""
        logger_func("\n=== METRICS ===")
        logger_func(f"signatures_fetched: {self.signatures_fetched}")
        logger_func(f"signatures_parsed: {self.signatures_parsed}")
        logger_func(f"events_swap_rows: {self.events_swap_rows}")
        logger_func(f"fallback_rows: {self.fallback_rows}")
        logger_func(f"dup_rows: {self.dup_rows}")
        logger_func(f"dust_rows: {self.dust_rows}")
        logger_func(f"parser_errors: {self.parser_errors}")
        logger_func(f"unpriced_rows: {self.unpriced_rows}")

        # Calculate percentages
        if self.signatures_fetched > 0:
            parse_rate = (self.signatures_parsed / self.signatures_fetched) * 100
            logger_func(f"Parse rate: {parse_rate:.1f}%")


class RateLimiter:
    def __init__(self, calls_per_second: int):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0

    async def acquire(self):
        current = asyncio.get_event_loop().time()
        elapsed = current - self.last_call
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self.last_call = asyncio.get_event_loop().time()


class RateLimitedFetcher:
    """Semaphore-based rate limiter for concurrent requests"""
    
    def __init__(self, max_concurrent: int = 10):
        """Initialize with max concurrent requests (default 10 for Helius)"""
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent
        self._active_requests = 0
        self._total_requests = 0
        self._rate_limit_hits = 0
    
    async def __aenter__(self):
        """Acquire semaphore for request"""
        await self.semaphore.acquire()
        self._active_requests += 1
        self._total_requests += 1
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release semaphore after request"""
        self._active_requests -= 1
        self.semaphore.release()
        
        # If we got a 429, track it
        if exc_type and hasattr(exc_val, 'status') and exc_val.status == 429:
            self._rate_limit_hits += 1
    
    @property
    def active_count(self) -> int:
        """Get current number of active requests"""
        return self._active_requests
    
    @property
    def stats(self) -> Dict[str, int]:
        """Get rate limiter statistics"""
        return {
            "max_concurrent": self.max_concurrent,
            "active_requests": self._active_requests,
            "total_requests": self._total_requests,
            "rate_limit_hits": self._rate_limit_hits
        }


class PriceCache:
    """Birdeye price cache keyed by (mint, unix_minute)"""

    def __init__(self):
        self.cache: Dict[Tuple[str, int], Optional[Decimal]] = {}

    def get_key(self, mint: str, timestamp: datetime) -> Tuple[str, int]:
        """Get cache key for mint and timestamp"""
        unix_minute = int(timestamp.timestamp() // 60) * 60
        return (mint, unix_minute)

    def get(self, mint: str, timestamp: datetime) -> Optional[Decimal]:
        """Get cached price"""
        key = self.get_key(mint, timestamp)
        return self.cache.get(key)

    def set(self, mint: str, timestamp: datetime, price: Optional[Decimal]):
        """Cache price"""
        key = self.get_key(mint, timestamp)
        self.cache[key] = price


class BlockchainFetcherV3:
    """V3 fetcher with all expert recommendations"""

    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None, skip_pricing: bool = False, parallel_pages: int = 40):
        self.progress_callback = progress_callback or (lambda x: logger.info(x))
        self.helius_limiter = RateLimiter(HELIUS_RPS)
        self.helius_rate_limited_fetcher = RateLimitedFetcher(max_concurrent=40)  # Updated for paid plan (50 RPS with buffer)
        self.birdeye_limiter = RateLimiter(BIRDEYE_RPS)
        self.session: Optional[aiohttp.ClientSession] = None
        self.metrics = Metrics()
        self.price_cache = PriceCache()
        self.skip_pricing = skip_pricing
        self.parallel_pages = parallel_pages  # Number of pages to fetch concurrently

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _report_progress(self, message: str):
        """Report progress to callback"""
        self.progress_callback(message)

    async def fetch_wallet_trades(self, wallet_address: str) -> Dict[str, Any]:
        """Fetch and analyze trades for a wallet"""
        if not HELIUS_KEY:
            raise ValueError("HELIUS_KEY environment variable not set")

        self._report_progress(f"Starting fetch for wallet: {wallet_address}")
        start_time = time.time()
        step_times = {}

        # Step 1: Fetch all SWAP transactions
        step_start = time.time()
        self._report_progress("Step 1: Fetching SWAP transactions...")
        transactions = await self._fetch_swap_transactions(wallet_address)
        self.metrics.signatures_fetched = len(transactions)
        step_times['fetch_transactions'] = time.time() - step_start
        self._report_progress(f"✓ Fetched {len(transactions)} SWAP transactions in {step_times['fetch_transactions']:.1f}s")

        # Step 2: Extract trades with deduplication
        step_start = time.time()
        self._report_progress("Step 2: Extracting trades...")
        trades = await self._extract_trades_with_dedup(transactions, wallet_address)
        step_times['extract_trades'] = time.time() - step_start
        self._report_progress(f"✓ Extracted {len(trades)} unique trades in {step_times['extract_trades']:.1f}s")

        # Step 3: Fetch token metadata
        step_start = time.time()
        self._report_progress("Step 3: Fetching token metadata...")
        await self._fetch_token_metadata(trades)
        step_times['fetch_metadata'] = time.time() - step_start
        self._report_progress(f"✓ Fetched metadata in {step_times['fetch_metadata']:.1f}s")

        # Step 4: Apply dust filter
        step_start = time.time()
        self._report_progress("Step 4: Applying dust filter...")
        filtered_trades = self._apply_dust_filter(trades)
        step_times['dust_filter'] = time.time() - step_start
        self._report_progress(f"✓ After dust filter: {len(filtered_trades)} trades in {step_times['dust_filter']:.1f}s")

        # Step 5: Fetch prices
        if not self.skip_pricing:
            step_start = time.time()
            self._report_progress("Step 5: Fetching prices...")
            await self._fetch_prices_with_cache(filtered_trades)
            step_times['fetch_prices'] = time.time() - step_start
            self._report_progress(f"✓ Fetched prices in {step_times['fetch_prices']:.1f}s")
        else:
            self._report_progress("Step 5: Skipping price fetching (skip_pricing=True)")

        # Step 6: Calculate P&L
        step_start = time.time()
        self._report_progress("Step 6: Calculating P&L...")
        final_trades = self._calculate_pnl(filtered_trades)
        step_times['calculate_pnl'] = time.time() - step_start
        self._report_progress(f"✓ Calculated P&L in {step_times['calculate_pnl']:.1f}s")

        # Log timing summary
        total_time = time.time() - start_time
        self._report_progress("\n=== TIMING SUMMARY ===")
        for step, duration in step_times.items():
            percentage = (duration / total_time) * 100
            self._report_progress(f"{step}: {duration:.1f}s ({percentage:.1f}%)")
        if self.skip_pricing:
            self._report_progress("fetch_prices: SKIPPED (skip_pricing=True)")
        self._report_progress(f"TOTAL: {total_time:.1f}s")
        self._report_progress("===================\n")

        # Log metrics
        self.metrics.log_summary(self._report_progress)

        # Create response envelope
        return self._create_response_envelope(wallet_address, final_trades, total_time)

    async def _fetch_single_page(
        self, wallet: str, page_num: int, before_sig: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str], bool, bool]:
        """
        Fetch a single page of transactions
        Returns: (transactions, next_before_sig, is_empty, hit_rate_limit)
        """
        # Task 1: No source parameter
        params = {"api-key": HELIUS_KEY, "limit": 100, "type": "SWAP", "maxSupportedTransactionVersion": "0"}
        
        if before_sig:
            params["before"] = before_sig
        
        try:
            url = f"{HELIUS_BASE}/addresses/{wallet}/transactions"
            if not self.session:
                raise RuntimeError("Session not initialized")
            
            # Use semaphore-based rate limiter for concurrent request control
            async with self.helius_rate_limited_fetcher:
                async with self.session.get(url, params=params, timeout=ClientTimeout(total=30)) as resp:
                    if resp.status == 429:
                        # Return flag indicating rate limit hit - don't retry here
                        retry_after = int(resp.headers.get("Retry-After", "5"))
                        self._report_progress(f"Page {page_num}: Rate limited (retry after {retry_after}s)")
                        return [], before_sig, False, True
                    
                    resp.raise_for_status()
                    json_data = await resp.json()
                    
                    # Handle error responses
                    if isinstance(json_data, dict) and "error" in json_data:
                        self._report_progress(f"Page {page_num}: API error: {json_data.get('error', 'Unknown error')}")
                        return [], None, True, False
                    
                    # Ensure we have a list
                    if not isinstance(json_data, list):
                        self._report_progress(f"Page {page_num}: Unexpected response format")
                        return [], None, True, False
                    
                    data: List[Dict[str, Any]] = json_data
                    
                    if not data:
                        self._report_progress(f"Page {page_num}: Empty page")
                        return [], before_sig, True, False
                    
                    self._report_progress(f"Page {page_num}: {len(data)} transactions")
                    next_before = data[-1]["signature"] if data else None
                    return data, next_before, False, False
                    
        except Exception as e:
            logger.error(f"Error fetching page {page_num}: {e}")
            self.metrics.parser_errors += 1
            return [], None, True, False
    
    async def _fetch_pages_parallel(
        self, wallet: str, start_page: int, before_sigs: List[Optional[str]], num_pages: int
    ) -> Tuple[List[List[Dict[str, Any]]], List[Optional[str]]]:
        """
        Fetch multiple pages in parallel with batch-wide 429 handling
        Returns: (list of transaction lists, list of next before_sigs)
        """
        # Exponential backoff delays for retries
        backoff_delays = [5, 10, 20]
        retry_count = 0
        
        while retry_count <= len(backoff_delays):
            tasks = []
            for i in range(num_pages):
                page_num = start_page + i
                before_sig = before_sigs[i] if i < len(before_sigs) else None
                task = self._fetch_single_page(wallet, page_num, before_sig)
                tasks.append(task)
            
            # Gather all results
            results = await asyncio.gather(*tasks)
            
            # Check if any page hit rate limit
            any_rate_limited = any(hit_rate_limit for _, _, _, hit_rate_limit in results)
            
            if any_rate_limited and retry_count < len(backoff_delays):
                # Batch hit rate limit - wait and retry entire batch
                wait_time = backoff_delays[retry_count]
                self._report_progress(f"Batch hit rate limit, waiting {wait_time}s before retry (attempt {retry_count + 1}/3)...")
                await asyncio.sleep(wait_time)
                retry_count += 1
                continue
            
            # No rate limit or max retries reached - return results
            all_transactions = []
            next_sigs = []
            
            for transactions, next_sig, is_empty, hit_rate_limit in results:
                all_transactions.append(transactions)
                next_sigs.append(next_sig)
            
            return all_transactions, next_sigs
        
        # Should never reach here, but return empty results if we do
        return [[] for _ in range(num_pages)], [None for _ in range(num_pages)]

    async def _fetch_swap_transactions(self, wallet: str) -> List[Dict[str, Any]]:
        """Fetch all SWAP transactions using parallel fetching"""
        all_transactions = []
        page = 0
        consecutive_empty_pages = 0
        batch_num = 0
        warned_100_pages = False  # Track if we've already warned
        seen_before_sigs: Set[str] = set()  # WAL-315: Track seen signatures for loop detection
        
        # Start with first page to establish pattern
        self._report_progress(f"Starting parallel fetch with {self.parallel_pages} concurrent pages...")
        
        # Initial fetch to get first before_sig
        first_page_data, first_before_sig, is_empty, hit_rate_limit = await self._fetch_single_page(wallet, 1, None)
        if first_page_data:
            all_transactions.extend(first_page_data)
            page = 1
        
        if is_empty or not first_before_sig:
            self._report_progress("No transactions found")
            return all_transactions
        
        # Add first signature to seen set
        if first_before_sig:
            seen_before_sigs.add(first_before_sig)
        
        # Now fetch in parallel batches
        current_before_sigs = [first_before_sig]
        
        while current_before_sigs and any(sig is not None for sig in current_before_sigs):
            # Check hard cap on pages
            if page >= 150:
                logger.error(f"Hit hard cap of 150 pages for wallet {wallet}, stopping pagination")
                self._report_progress("ERROR: Hit 150 page hard cap, stopping")
                break
            
            # Warn when crossing 100 pages
            if page >= 100 and not warned_100_pages:
                logger.warning(f"Fetched 100+ pages for wallet {wallet}, continuing...")
                self._report_progress("WARNING: Reached 100 pages, continuing...")
                warned_100_pages = True
            
            batch_num += 1
            batch_start = page + 1
            
            # Determine how many pages to fetch in this batch
            num_pages_to_fetch = min(self.parallel_pages, len(current_before_sigs) * 2)  # Allow for growth
            
            # Don't exceed 150 page hard cap
            if batch_start + num_pages_to_fetch - 1 > 150:
                num_pages_to_fetch = max(0, 150 - batch_start + 1)
                if num_pages_to_fetch <= 0:
                    logger.error(f"Would exceed 150 page hard cap, stopping")
                    break
            
            self._report_progress(f"Batch {batch_num}: Fetching pages {batch_start} to {batch_start + num_pages_to_fetch - 1}")
            
            # Prepare before_sigs for this batch
            batch_before_sigs = []
            for i in range(num_pages_to_fetch):
                if i < len(current_before_sigs) and current_before_sigs[i] is not None:
                    batch_before_sigs.append(current_before_sigs[i])
                else:
                    batch_before_sigs.append(None)
            
            # Fetch pages in parallel
            batch_transactions, next_before_sigs = await self._fetch_pages_parallel(
                wallet, batch_start, batch_before_sigs, num_pages_to_fetch
            )
            
            # Process results
            batch_had_data = False
            new_before_sigs = []
            
            for i, (transactions, next_sig) in enumerate(zip(batch_transactions, next_before_sigs)):
                if transactions:
                    all_transactions.extend(transactions)
                    batch_had_data = True
                    consecutive_empty_pages = 0
                    if next_sig:
                        # WAL-315: Check for loop detection
                        if next_sig in seen_before_sigs:
                            logger.error(f"Loop detected: signature {next_sig[:8]}... already seen, stopping pagination")
                            self._report_progress(f"ERROR: Loop detected with signature {next_sig[:8]}..., stopping")
                            # Force exit from both loops
                            current_before_sigs = []
                            break
                        seen_before_sigs.add(next_sig)
                        new_before_sigs.append(next_sig)
                else:
                    consecutive_empty_pages += 1
                    # Continue past empty pages (WAL-314: changed from 3 to 5)
                    if next_sig and consecutive_empty_pages <= 5:
                        # WAL-315: Check for loop even on empty pages
                        if next_sig in seen_before_sigs:
                            logger.error(f"Loop detected on empty page: signature {next_sig[:8]}... already seen")
                            self._report_progress(f"ERROR: Loop detected with signature {next_sig[:8]}..., stopping")
                            current_before_sigs = []
                            break
                        seen_before_sigs.add(next_sig)
                        new_before_sigs.append(next_sig)
                
                page += 1
                
                # Check if we just crossed 100 pages
                if page >= 100 and not warned_100_pages:
                    logger.warning(f"Fetched 100+ pages for wallet {wallet}, continuing...")
                    self._report_progress("WARNING: Reached 100 pages, continuing...")
                    warned_100_pages = True
            
            # Check if we should stop (WAL-314: changed from 3 to 5)
            if not batch_had_data and consecutive_empty_pages > 5:
                self._report_progress(f"Hit {consecutive_empty_pages} consecutive empty pages, stopping")
                break
            
            # Update before_sigs for next batch
            current_before_sigs = new_before_sigs
            
            # Progress report
            self._report_progress(f"Batch {batch_num} complete: Total {len(all_transactions)} transactions so far")
        
        self._report_progress(f"Parallel fetch complete: {len(all_transactions)} total transactions in {page} pages")
        return all_transactions

    async def _extract_trades_with_dedup(self, transactions: List[Dict[str, Any]], wallet: str) -> List[Trade]:
        """Extract trades with deduplication (one per signature)"""
        trades_by_sig: Dict[str, Trade] = {}

        for tx in transactions:
            if tx.get("transactionError"):
                continue

            try:
                # Try primary parser first
                trade = self._parse_with_events_swap(tx)

                # If no trade from events.swap, try fallback
                if not trade:
                    trade = self._parse_from_token_transfers(tx, wallet)
                    if trade:
                        self.metrics.fallback_rows += 1
                else:
                    self.metrics.events_swap_rows += 1

                if trade:
                    # Task 3: Deduplication - one trade per signature
                    if trade.signature in trades_by_sig:
                        self.metrics.dup_rows += 1
                    else:
                        trades_by_sig[trade.signature] = trade
                        self.metrics.signatures_parsed += 1

            except Exception as e:
                logger.error(f"Error parsing transaction {tx.get('signature', 'unknown')}: {e}")
                self.metrics.parser_errors += 1

        return list(trades_by_sig.values())

    def _parse_with_events_swap(self, tx: Dict[str, Any]) -> Optional[Trade]:
        """Parse using events.swap (existing logic)"""
        events = tx.get("events", {})
        swap = events.get("swap", {})

        if not swap:
            return None

        timestamp = datetime.fromtimestamp(tx["timestamp"])
        signature = tx["signature"]
        slot = tx["slot"]
        dex = tx.get("source", "UNKNOWN")

        # Get all hops
        inner_swaps = swap.get("innerSwaps", [])
        hops = inner_swaps if inner_swaps else [swap]

        if not hops:
            return None

        try:
            # Task 3: Collapse hops - first input, last output
            first_hop = hops[0]
            last_hop = hops[-1]

            # Get first input
            if first_hop.get("nativeInput"):
                token_in_mint = SOL_MINT
                token_in_symbol = "SOL"
                token_in_amount = Decimal(str(first_hop["nativeInput"]["amount"])) / Decimal("1e9")
            elif first_hop.get("tokenInputs"):
                token_in = first_hop["tokenInputs"][0]
                if "rawTokenAmount" not in token_in:
                    return None
                token_in_mint = token_in["mint"]
                token_in_symbol = token_in_mint[:8]
                token_in_amount = self._safe_token_amount(token_in["rawTokenAmount"])
                if token_in_amount is None:
                    return None
            else:
                return None

            # Get last output
            if last_hop.get("nativeOutput"):
                token_out_mint = SOL_MINT
                token_out_symbol = "SOL"
                token_out_amount = Decimal(str(last_hop["nativeOutput"]["amount"])) / Decimal("1e9")
            elif last_hop.get("tokenOutputs"):
                token_out = last_hop["tokenOutputs"][-1]
                if "rawTokenAmount" not in token_out:
                    return None
                token_out_mint = token_out["mint"]
                token_out_symbol = token_out_mint[:8]
                token_out_amount = self._safe_token_amount(token_out["rawTokenAmount"])
                if token_out_amount is None:
                    return None
            else:
                return None

            return Trade(
                signature=signature,
                slot=slot,
                timestamp=timestamp,
                token_in_mint=token_in_mint,
                token_in_symbol=token_in_symbol,
                token_in_amount=token_in_amount,
                token_out_mint=token_out_mint,
                token_out_symbol=token_out_symbol,
                token_out_amount=token_out_amount,
                price_usd=None,
                value_usd=None,
                dex=dex,
            )

        except (KeyError, IndexError, TypeError):
            return None

    def _parse_from_token_transfers(self, tx: Dict[str, Any], wallet: str) -> Optional[Trade]:
        """Task 2: Fallback parser using tokenTransfers"""
        # Get fungible token transfers
        transfers = [t for t in tx.get("tokenTransfers", []) if t.get("tokenStandard") == "Fungible"]

        if not transfers:
            return None

        # Separate outgoing and incoming
        outgoing = [t for t in transfers if t.get("fromUserAccount") == wallet]
        incoming = [t for t in transfers if t.get("toUserAccount") == wallet]

        if not (outgoing and incoming):
            return None

        # Find largest transfers (expert's heuristic)
        try:
            leg_out = max(outgoing, key=lambda t: int(t.get("tokenAmount", 0)))
            leg_in = max(incoming, key=lambda t: int(t.get("tokenAmount", 0)))

            # Skip if same mint (not a swap)
            if leg_out.get("mint") == leg_in.get("mint"):
                return None

            # Extract amounts
            out_amount = Decimal(str(leg_out.get("tokenAmount", 0)))
            out_decimals = int(leg_out.get("decimals", 0))
            out_amount = out_amount / Decimal(f"1e{out_decimals}")

            in_amount = Decimal(str(leg_in.get("tokenAmount", 0)))
            in_decimals = int(leg_in.get("decimals", 0))
            in_amount = in_amount / Decimal(f"1e{in_decimals}")

            return Trade(
                signature=tx["signature"],
                slot=tx["slot"],
                timestamp=datetime.fromtimestamp(tx["timestamp"]),
                token_in_mint=leg_out.get("mint"),
                token_in_symbol=leg_out.get("mint", "")[:8],
                token_in_amount=out_amount,
                token_out_mint=leg_in.get("mint"),
                token_out_symbol=leg_in.get("mint", "")[:8],
                token_out_amount=in_amount,
                price_usd=None,
                value_usd=None,
                dex=tx.get("source", "UNKNOWN"),
            )

        except (ValueError, KeyError):
            return None

    def _safe_token_amount(self, raw: Dict[str, Any]) -> Optional[Decimal]:
        """Safely extract token amount"""
        try:
            amount = Decimal(str(raw["tokenAmount"]))
            decimals = int(raw["decimals"])
            return amount / Decimal(f"1e{decimals}")
        except (KeyError, TypeError, ValueError):
            return None

    def _apply_dust_filter(self, trades: List[Trade]) -> List[Trade]:
        """Task 4: Filter out dust trades"""
        filtered = []

        for trade in trades:
            # Check if either amount is dust
            min_amount = min(trade.token_in_amount, trade.token_out_amount)

            if min_amount < DUST_THRESHOLD:
                self.metrics.dust_rows += 1
            else:
                filtered.append(trade)

        return filtered

    async def _fetch_token_metadata(self, trades: List[Trade]):
        """Fetch token symbols"""
        unique_mints = set()
        for trade in trades:
            unique_mints.add(trade.token_in_mint)
            unique_mints.add(trade.token_out_mint)

        if not unique_mints:
            return

        self._report_progress(f"Fetching metadata for {len(unique_mints)} tokens...")

        # Batch requests
        for batch_start in range(0, len(unique_mints), 100):
            batch = list(unique_mints)[batch_start : batch_start + 100]
            await self.helius_limiter.acquire()

            try:
                url = f"{HELIUS_BASE}/token-metadata"
                params = {"api-key": HELIUS_KEY}

                if not self.session:
                    raise RuntimeError("Session not initialized")

                # Use semaphore-based rate limiter for token metadata requests
                async with self.helius_rate_limited_fetcher:
                    async with self.session.post(
                        url, params=params, json={"mintAccounts": batch}, timeout=ClientTimeout(total=30)
                    ) as resp:
                        if resp.status == 200:
                            metadata_list = await resp.json()

                            # Create lookup
                            metadata_map = {m["account"]: m for m in metadata_list if m}

                            # Update trades
                            for trade in trades:
                                if trade.token_in_mint in metadata_map:
                                    trade.token_in_symbol = metadata_map[trade.token_in_mint].get(
                                        "symbol", trade.token_in_mint[:8]
                                    )
                                if trade.token_out_mint in metadata_map:
                                    trade.token_out_symbol = metadata_map[trade.token_out_mint].get(
                                        "symbol", trade.token_out_mint[:8]
                                    )

            except Exception as e:
                logger.error(f"Error fetching token metadata: {e}")

    async def _fetch_prices_with_cache(self, trades: List[Trade]):
        """Task 5: Fetch prices with caching"""
        self._report_progress("Fetching prices...")
        
        # Count unique tokens needing prices
        unique_tokens = set()
        for trade in trades:
            if trade.token_in_mint != SOL_MINT:
                unique_tokens.add(trade.token_in_mint)
            if trade.token_out_mint != SOL_MINT:
                unique_tokens.add(trade.token_out_mint)
        
        self._report_progress(f"  - {len(trades)} trades have {len(unique_tokens)} unique tokens")

        # Group by minute for efficient fetching
        trades_by_minute: Dict[int, List[Trade]] = defaultdict(list)
        for trade in trades:
            minute_ts = int(trade.timestamp.timestamp() // 60) * 60
            trades_by_minute[minute_ts].append(trade)
        
        self._report_progress(f"  - Grouped into {len(trades_by_minute)} time buckets")

        # Track statistics
        cache_hits = 0
        cache_misses = 0
        api_calls = 0
        tokens_fetched = 0

        # Process each minute
        for idx, (minute_ts, minute_trades) in enumerate(trades_by_minute.items()):
            # Collect unique mints for this minute
            mints_needed = set()

            for trade in minute_trades:
                # Check cache first
                if trade.token_in_mint != SOL_MINT:
                    cached_price = self.price_cache.get(trade.token_in_mint, trade.timestamp)
                    if cached_price is None:
                        mints_needed.add(trade.token_in_mint)
                        cache_misses += 1
                    else:
                        cache_hits += 1

                if trade.token_out_mint != SOL_MINT:
                    cached_price = self.price_cache.get(trade.token_out_mint, trade.timestamp)
                    if cached_price is None:
                        mints_needed.add(trade.token_out_mint)
                        cache_misses += 1
                    else:
                        cache_hits += 1

            # Fetch missing prices
            if mints_needed:
                api_calls += 1
                tokens_fetched += len(mints_needed)
                
                if idx % 10 == 0:  # Log progress every 10 buckets
                    self._report_progress(
                        f"  - Progress: {idx+1}/{len(trades_by_minute)} buckets, "
                        f"{api_calls} API calls, {tokens_fetched} tokens fetched"
                    )
                
                prices = await self._fetch_birdeye_prices(minute_ts, list(mints_needed))

                # Cache results
                for mint, price in prices.items():
                    self.price_cache.set(mint, datetime.fromtimestamp(minute_ts), price)

            # Apply prices to trades
            for trade in minute_trades:
                await self._apply_cached_prices(trade)
        
        # Log final statistics
        self._report_progress(f"  - Price fetching complete:")
        self._report_progress(f"    - Cache hits: {cache_hits}")
        self._report_progress(f"    - Cache misses: {cache_misses}")
        self._report_progress(f"    - Cache hit rate: {(cache_hits / (cache_hits + cache_misses) * 100):.1f}%")
        self._report_progress(f"    - API calls made: {api_calls}")
        self._report_progress(f"    - Total tokens fetched: {tokens_fetched}")

    async def _fetch_birdeye_prices(self, timestamp: int, mints: List[str]) -> Dict[str, Optional[Decimal]]:
        """Fetch prices from Birdeye"""
        prices = {}

        if not BIRDEYE_API_KEY:
            self._report_progress("    - WARNING: No BIRDEYE_API_KEY set, skipping price fetch")
            return prices

        # Log the request details
        start_time = time.time()
        dt = datetime.fromtimestamp(timestamp)
        self._report_progress(
            f"    - Fetching prices for {len(mints)} tokens at {dt.strftime('%Y-%m-%d %H:%M')} "
            f"(waiting for rate limit...)"
        )

        await self.birdeye_limiter.acquire()
        
        wait_time = time.time() - start_time
        if wait_time > 0.1:
            self._report_progress(f"    - Rate limit wait: {wait_time:.1f}s")

        try:
            url = "https://public-api.birdeye.so/public/multi_price"
            headers = {"X-API-KEY": BIRDEYE_API_KEY}
            params = {"list_address": ",".join(mints), "time": timestamp}

            if not self.session:
                raise RuntimeError("Session not initialized")

            async with self.session.get(url, headers=headers, params=params, timeout=ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success") and data.get("data"):
                        for mint, price_data in data["data"].items():
                            if price_data and "value" in price_data:
                                prices[mint] = Decimal(str(price_data["value"]))
                            else:
                                prices[mint] = None
                    
                    fetch_time = time.time() - start_time
                    self._report_progress(
                        f"    - Got {len(prices)}/{len(mints)} prices in {fetch_time:.1f}s"
                    )
                else:
                    self._report_progress(f"    - ERROR: Birdeye returned status {resp.status}")

        except Exception as e:
            logger.error(f"Error fetching Birdeye prices: {e}")
            self._report_progress(f"    - ERROR: {str(e)}")

        return prices

    async def _fetch_batch_prices(self, mints: List[str], timestamps: List[int]) -> Dict[str, Optional[float]]:
        """Fetch prices for multiple mints at multiple timestamps"""
        if not BIRDEYE_API_KEY:
            logger.warning("No BIRDEYE_API_KEY set, returning None prices")
            return {mint: None for mint in mints}
        
        all_prices = {}
        
        # Process each unique timestamp
        for timestamp in set(timestamps):
            # Get unique mints for this timestamp
            unique_mints = list(set(mints))
            
            # Process in batches of 100 (Birdeye limit)
            for i in range(0, len(unique_mints), 100):
                batch = unique_mints[i:i+100]
                
                # Check cache first
                uncached_mints = []
                dt = datetime.fromtimestamp(timestamp)
                
                for mint in batch:
                    cached_price = self.price_cache.get(mint, dt)
                    if cached_price is not None:
                        all_prices[mint] = float(cached_price)
                    else:
                        uncached_mints.append(mint)
                
                # Fetch uncached prices
                if uncached_mints:
                    prices = await self._fetch_birdeye_prices(timestamp, uncached_mints)
                    
                    # Cache and store results
                    for mint, price in prices.items():
                        self.price_cache.set(mint, dt, price)
                        all_prices[mint] = float(price) if price is not None else None
        
        return all_prices

    async def _apply_cached_prices(self, trade: Trade):
        """Apply cached prices to trade"""
        sol_price = Decimal("100")  # Fallback SOL price

        # Get SOL price for this minute
        cached_sol = self.price_cache.get(SOL_MINT, trade.timestamp)
        if cached_sol:
            sol_price = cached_sol

        # Price the trade
        if trade.token_in_mint == SOL_MINT:
            # Selling SOL for token
            trade.value_usd = trade.token_in_amount * sol_price
            if trade.token_out_amount > 0:
                trade.price_usd = trade.value_usd / trade.token_out_amount
            trade.priced = True
        elif trade.token_out_mint == SOL_MINT:
            # Selling token for SOL
            trade.value_usd = trade.token_out_amount * sol_price
            if trade.token_in_amount > 0:
                trade.price_usd = trade.value_usd / trade.token_in_amount
            trade.priced = True
        else:
            # Token-to-token
            in_price = self.price_cache.get(trade.token_in_mint, trade.timestamp)
            out_price = self.price_cache.get(trade.token_out_mint, trade.timestamp)

            if in_price and out_price:
                in_value = trade.token_in_amount * in_price
                out_value = trade.token_out_amount * out_price
                trade.value_usd = (in_value + out_value) / 2  # Average
                trade.priced = True
            else:
                trade.priced = False
                self.metrics.unpriced_rows += 1

    def _calculate_pnl(self, trades: List[Trade]) -> List[Trade]:
        """Calculate P&L using FIFO"""
        # Sort by timestamp
        sorted_trades = sorted(trades, key=lambda x: x.timestamp)

        # Track positions by token
        positions: Dict[str, List[Tuple[Decimal, Decimal]]] = defaultdict(list)  # token -> [(amount, cost_basis)]

        for trade in sorted_trades:
            if trade.token_out_mint == SOL_MINT:
                # Selling token
                token = trade.token_in_mint
                amount_to_sell = trade.token_in_amount
                proceeds = trade.value_usd or Decimal("0")

                cost_basis = Decimal("0")
                remaining = amount_to_sell

                # FIFO matching
                while remaining > 0 and positions[token]:
                    position_amount, position_cost = positions[token][0]

                    if position_amount <= remaining:
                        # Use entire position
                        cost_basis += position_cost
                        remaining -= position_amount
                        positions[token].pop(0)
                    else:
                        # Use partial position
                        used_fraction = remaining / position_amount
                        cost_basis += position_cost * used_fraction
                        positions[token][0] = (position_amount - remaining, position_cost * (1 - used_fraction))
                        remaining = 0

                trade.pnl_usd = proceeds - cost_basis if proceeds else Decimal("0")

            else:
                # Buying token
                token = trade.token_out_mint
                amount = trade.token_out_amount
                cost = trade.value_usd or Decimal("0")

                positions[token].append((amount, cost))
                trade.pnl_usd = Decimal("0")

        return sorted_trades

    def _create_response_envelope(self, wallet: str, trades: List[Trade], elapsed_time: float) -> Dict[str, Any]:
        """Task 6: Create response envelope"""
        # Calculate summary stats
        total_pnl = sum(t.pnl_usd for t in trades)
        winning_trades = [t for t in trades if t.pnl_usd > 0]
        win_rate = len(winning_trades) / len(trades) * 100 if trades else 0

        # Get slot range
        slots = [t.slot for t in trades]
        from_slot = min(slots) if slots else 0
        to_slot = max(slots) if slots else 0

        return {
            "wallet": wallet,
            "from_slot": from_slot,
            "to_slot": to_slot,
            "elapsed_seconds": round(elapsed_time, 2),
            "summary": {
                "total_trades": len(trades),
                "total_pnl_usd": float(total_pnl),
                "win_rate": round(win_rate, 2),
                "priced_trades": len([t for t in trades if t.priced]),
                "metrics": {
                    "signatures_fetched": self.metrics.signatures_fetched,
                    "signatures_parsed": self.metrics.signatures_parsed,
                    "events_swap_rows": self.metrics.events_swap_rows,
                    "fallback_rows": self.metrics.fallback_rows,
                    "dust_filtered": self.metrics.dust_rows,
                },
            },
            "trades": [trade.to_dict() for trade in trades],
        }


# Convenience function
def fetch_wallet_trades_v3(
    wallet_address: str, progress_callback: Optional[Callable[[str], None]] = None
) -> Dict[str, Any]:
    """Synchronous wrapper for async fetch"""

    async def _fetch():
        async with BlockchainFetcherV3(progress_callback) as fetcher:
            return await fetcher.fetch_wallet_trades(wallet_address)

    return asyncio.run(_fetch())


if __name__ == "__main__":
    # Test with sample wallet
    def print_progress(msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    wallet = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
    print(f"Fetching trades for wallet: {wallet}")

    result = fetch_wallet_trades_v3(wallet, print_progress)

    print(f"\n=== RESPONSE ENVELOPE ===")
    print(f"Wallet: {result['wallet']}")
    print(f"Total trades: {result['summary']['total_trades']}")
    print(f"Elapsed: {result['elapsed_seconds']}s")
    print(f"Size: {len(str(result)) / 1024:.1f} KB")
