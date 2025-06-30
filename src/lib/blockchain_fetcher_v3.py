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
HELIUS_RPS = 10
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        # Determine action based on SOL
        if self.token_out_mint == SOL_MINT:
            action = "sell"
            token = self.token_in_symbol
            amount = float(self.token_in_amount)
        else:
            action = "buy"
            token = self.token_out_symbol
            amount = float(self.token_out_amount)

        return {
            "timestamp": self.timestamp.isoformat(),
            "signature": self.signature,
            "action": action,
            "token": token,
            "amount": amount,
            "price": float(self.price_usd) if self.price_usd else None,
            "value_usd": float(self.value_usd) if self.value_usd else None,
            "pnl_usd": float(self.pnl_usd),
            "fees_usd": float(self.fees_usd),
            "priced": self.priced,
            "dex": self.dex,
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

    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None):
        self.progress_callback = progress_callback or (lambda x: logger.info(x))
        self.helius_limiter = RateLimiter(HELIUS_RPS)
        self.birdeye_limiter = RateLimiter(BIRDEYE_RPS)
        self.session: Optional[aiohttp.ClientSession] = None
        self.metrics = Metrics()
        self.price_cache = PriceCache()

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
        """
        Main entry point - returns response envelope with trades
        """
        if not HELIUS_KEY:
            raise ValueError("HELIUS_KEY environment variable not set")

        self._report_progress(f"Starting fetch for wallet: {wallet_address}")
        start_time = time.time()

        # Reset metrics
        self.metrics = Metrics()

        # Step 1: Fetch all SWAP transactions (no source parameter)
        transactions = await self._fetch_swap_transactions(wallet_address)
        self.metrics.signatures_fetched = len(transactions)
        self._report_progress(f"Fetched {len(transactions)} SWAP transactions")

        # Step 2: Extract trades with deduplication
        trades = await self._extract_trades_with_dedup(transactions, wallet_address)
        self._report_progress(f"Extracted {len(trades)} unique trades")

        # Step 3: Fetch token metadata
        await self._fetch_token_metadata(trades)

        # Step 4: Apply dust filter
        filtered_trades = self._apply_dust_filter(trades)
        self._report_progress(f"After dust filter: {len(filtered_trades)} trades")

        # Step 5: Fetch prices with cache
        await self._fetch_prices_with_cache(filtered_trades)

        # Step 6: Calculate P&L
        final_trades = self._calculate_pnl(filtered_trades)

        # Log metrics
        self.metrics.log_summary(self._report_progress)

        # Create response envelope
        return self._create_response_envelope(wallet_address, final_trades, time.time() - start_time)

    async def _fetch_swap_transactions(self, wallet: str) -> List[Dict[str, Any]]:
        """Fetch all SWAP transactions (no source filter)"""
        transactions = []
        before_sig = None
        page = 0
        empty_pages = 0

        while True:
            page += 1
            await self.helius_limiter.acquire()

            # Task 1: No source parameter
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
                        self._report_progress(f"Rate limited, waiting {retry_after}s...")
                        await asyncio.sleep(retry_after)
                        continue

                    resp.raise_for_status()
                    data = await resp.json()

                    if isinstance(data, dict) and "error" in data:
                        self._report_progress(f"API error: {data.get('error', 'Unknown error')}")
                        break

                    if not data:
                        empty_pages += 1
                        if empty_pages > 3:
                            self._report_progress(f"Hit {empty_pages} empty pages, stopping")
                            break
                        self._report_progress(f"Empty page {empty_pages}/3, continuing...")
                        continue

                    empty_pages = 0
                    transactions.extend(data)
                    self._report_progress(f"Page {page}: {len(data)} transactions")

                    before_sig = data[-1]["signature"]

            except Exception as e:
                logger.error(f"Error fetching transactions: {e}")
                self.metrics.parser_errors += 1
                break

        return transactions

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

        # Group by minute for efficient fetching
        trades_by_minute: Dict[int, List[Trade]] = defaultdict(list)
        for trade in trades:
            minute_ts = int(trade.timestamp.timestamp() // 60) * 60
            trades_by_minute[minute_ts].append(trade)

        # Process each minute
        for minute_ts, minute_trades in trades_by_minute.items():
            # Collect unique mints for this minute
            mints_needed = set()

            for trade in minute_trades:
                # Check cache first
                if trade.token_in_mint != SOL_MINT:
                    cached_price = self.price_cache.get(trade.token_in_mint, trade.timestamp)
                    if cached_price is None:
                        mints_needed.add(trade.token_in_mint)

                if trade.token_out_mint != SOL_MINT:
                    cached_price = self.price_cache.get(trade.token_out_mint, trade.timestamp)
                    if cached_price is None:
                        mints_needed.add(trade.token_out_mint)

            # Fetch missing prices
            if mints_needed:
                prices = await self._fetch_birdeye_prices(minute_ts, list(mints_needed))

                # Cache results
                for mint, price in prices.items():
                    self.price_cache.set(mint, datetime.fromtimestamp(minute_ts), price)

            # Apply prices to trades
            for trade in minute_trades:
                await self._apply_cached_prices(trade)

    async def _fetch_birdeye_prices(self, timestamp: int, mints: List[str]) -> Dict[str, Optional[Decimal]]:
        """Fetch prices from Birdeye"""
        prices = {}

        if not BIRDEYE_API_KEY:
            return prices

        await self.birdeye_limiter.acquire()

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

        except Exception as e:
            logger.error(f"Error fetching Birdeye prices: {e}")

        return prices

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
