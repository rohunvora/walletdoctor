#!/usr/bin/env python3
"""
Blockchain Fetcher Module - Fetches all trading activity from Helius API
Handles all DEXs, proper pagination, and returns trade dictionaries
"""

import os
import sys
import time
import logging
import asyncio
import aiohttp
from aiohttp import ClientTimeout
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional, Callable, Set, Tuple
from collections import defaultdict
from dataclasses import dataclass, asdict
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Configuration from environment
HELIUS_KEY = os.getenv("HELIUS_KEY")
BIRDEYE_KEY = os.getenv("BIRDEYE_API_KEY") 
HELIUS_BASE = os.getenv("HELIUS_BASE", "https://api.helius.xyz/v0")
BIRDEYE_BASE = os.getenv("BIRDEYE_BASE", "https://public-api.birdeye.so")

# Rate limiting
HELIUS_RPS = 20  # Requests per second
BIRDEYE_RPS = 100  # Requests per second
MAX_CONCURRENT = 15  # Max concurrent requests

# DEX sources to query (query each separately due to API limitations)
DEX_SOURCES = ["JUPITER", "RAYDIUM", "ORCA", "PHOENIX", "LIFINITY", "METEORA", "PUMP_AMM"]

# Known token addresses
KNOWN_TOKENS = {
    "So11111111111111111111111111111111111111112": {"symbol": "SOL", "decimals": 9},
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": {"symbol": "USDC", "decimals": 6},
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": {"symbol": "USDT", "decimals": 6},
}

# Cache for token metadata and prices
token_cache = {}
price_cache = {}
failed_log_count = 0
MAX_FAILED_LOGS = 100


@dataclass
class Trade:
    """Trade data structure"""
    signature: str
    slot: int
    timestamp: datetime
    action: str  # 'buy' or 'sell'
    token_mint: str
    token_symbol: str
    token_amount: Decimal
    sol_amount: Optional[Decimal]
    other_mint: Optional[str]  # For token-to-token swaps
    other_amount: Optional[Decimal]
    price_usd: Optional[Decimal]
    value_usd: Optional[Decimal]
    fees_usd: Decimal
    dex: str
    hop_idx: int = 0
    leg_idx: int = 0
    priced: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'action': self.action,
            'token': self.token_symbol,
            'amount': float(self.token_amount),
            'price': float(self.price_usd) if self.price_usd else None,
            'value_usd': float(self.value_usd) if self.value_usd else None,
            'pnl_usd': 0.0,  # Calculated later
            'fees_usd': float(self.fees_usd),
            'priced': self.priced
        }


class RateLimiter:
    """Simple rate limiter for API calls"""
    def __init__(self, calls_per_second: int):
        self.calls_per_second = calls_per_second
        self.semaphore = asyncio.Semaphore(calls_per_second)
        self.last_call = 0
        
    async def acquire(self):
        async with self.semaphore:
            now = time.time()
            time_since_last = now - self.last_call
            if time_since_last < 1.0 / self.calls_per_second:
                await asyncio.sleep(1.0 / self.calls_per_second - time_since_last)
            self.last_call = time.time()


class BlockchainFetcher:
    """Main fetcher class with async operations"""
    
    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None):
        self.progress_callback = progress_callback or (lambda x: logger.info(x))
        self.helius_limiter = RateLimiter(HELIUS_RPS)
        self.birdeye_limiter = RateLimiter(BIRDEYE_RPS)
        self.session: Optional[aiohttp.ClientSession] = None
        self.empty_pages = 0
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    def _report_progress(self, message: str):
        """Report progress to callback"""
        self.progress_callback(message)
        
    async def fetch_wallet_trades(self, wallet_address: str) -> List[Dict[str, Any]]:
        """
        Main entry point - fetches all trades for a wallet
        Returns list of trade dictionaries ready for analytics
        """
        if not HELIUS_KEY:
            raise ValueError("HELIUS_KEY environment variable not set")
            
        self._report_progress(f"Starting fetch for wallet: {wallet_address}")
        
        # Step 1: Fetch all transactions
        all_transactions = await self._fetch_all_transactions(wallet_address)
        self._report_progress(f"Fetched {len(all_transactions)} total transactions")
        
        # Step 2: Extract trades from transactions
        all_trades = await self._extract_all_trades(all_transactions)
        self._report_progress(f"Extracted {len(all_trades)} trades")
        
        # Step 3: Fetch token metadata
        await self._fetch_token_metadata(all_trades)
        
        # Step 4: Fetch prices
        await self._fetch_all_prices(all_trades)
        
        # Step 5: Calculate P&L using FIFO
        trades_with_pnl = self._calculate_pnl(all_trades)
        
        # Convert to dictionaries
        return [trade.to_dict() for trade in trades_with_pnl]
        
    async def _fetch_all_transactions(self, wallet: str) -> List[Dict[str, Any]]:
        """Fetch all transactions for a wallet with proper pagination"""
        all_transactions = []
        
        # Fetch all SWAP transactions (don't filter by source in API)
        self._report_progress("Fetching all SWAP transactions...")
        swap_transactions = await self._fetch_swap_transactions(wallet)
        
        # Filter by source client-side
        transactions_by_source = defaultdict(list)
        unknown_source_swaps = []
        
        for tx in swap_transactions:
            source = tx.get('source', 'UNKNOWN')
            if source in DEX_SOURCES:
                transactions_by_source[source].append(tx)
            else:
                unknown_source_swaps.append(tx)
                
        # Report counts by source
        for source, txs in transactions_by_source.items():
            self._report_progress(f"Found {len(txs)} {source} transactions")
            
        if unknown_source_swaps:
            self._report_progress(f"Found {len(unknown_source_swaps)} UNKNOWN source swaps")
            
        return swap_transactions
        
    async def _fetch_swap_transactions(self, wallet: str) -> List[Dict[str, Any]]:
        """Fetch all SWAP type transactions"""
        transactions = []
        before_sig = None
        page = 0
        
        while True:
            page += 1
            await self.helius_limiter.acquire()
            
            params = {
                "api-key": HELIUS_KEY,
                "limit": 100,  # Max allowed for enhanced API
                "type": "SWAP",
                "maxSupportedTransactionVersion": "0"  # Critical for v1.18+ transactions
            }
                
            if before_sig:
                params["before"] = before_sig
                
            try:
                url = f"{HELIUS_BASE}/addresses/{wallet}/transactions"
                if not self.session:
                    raise RuntimeError("Session not initialized")
                async with self.session.get(url, params=params, timeout=ClientTimeout(total=30)) as resp:
                    if resp.status == 429:
                        # Rate limited - wait and retry
                        retry_after = int(resp.headers.get('Retry-After', '5'))
                        self._report_progress(f"Rate limited, waiting {retry_after}s...")
                        await asyncio.sleep(retry_after)
                        continue
                        
                    resp.raise_for_status()
                    data = await resp.json()
                    
                    # Handle error response
                    if isinstance(data, dict) and 'error' in data:
                        self._report_progress(f"API error: {data.get('error', 'Unknown error')}")
                        break
                        
                    if not data:
                        # Empty response - continue paginating!
                        self.empty_pages += 1
                        if self.empty_pages > 3:
                            self._report_progress(f"Hit {self.empty_pages} empty pages, stopping pagination")
                            break
                        self._report_progress(f"Empty page {self.empty_pages}/3, continuing...")
                        continue
                    
                    # Reset empty counter on successful page
                    self.empty_pages = 0
                    transactions.extend(data)
                    self._report_progress(f"Fetched page {page} with {len(data)} SWAP transactions")
                    
                    # Set up for next page - always use last signature
                    before_sig = data[-1]['signature']
                    
            except Exception as e:
                logger.error(f"Error fetching SWAP transactions: {e}")
                break
                
        return transactions
        
    async def _fetch_transactions_for_source(self, wallet: str, source: str, swap_only: bool = False) -> List[Dict[str, Any]]:
        """Fetch transactions for a specific DEX source"""
        # This method is no longer used - keeping for backward compatibility
        return []
        
    async def _extract_all_trades(self, transactions: List[Dict[str, Any]]) -> List[Trade]:
        """Extract trades from all transactions"""
        all_trades = []
        
        for tx in transactions:
            if tx.get('transactionError'):
                continue
                
            trades = self._extract_trades_from_transaction(tx)
            all_trades.extend(trades)
            
        return all_trades
        
    def _extract_trades_from_transaction(self, tx: Dict[str, Any]) -> List[Trade]:
        """Extract trades from a single transaction"""
        trades = []
        timestamp = datetime.fromtimestamp(tx['timestamp'])
        slot = tx['slot']
        signature = tx['signature']
        dex = tx.get('source', 'UNKNOWN')
        
        # Get swap events
        events = tx.get('events', {})
        swap = events.get('swap', {})
        
        if not swap and tx.get('type') == 'SWAP':
            # No swap event - try DEX-specific parsing
            if dex == 'PUMP_AMM':
                trades = self._parse_pump_amm_transaction(tx)
            elif dex in ['JUPITER', 'METEORA']:
                trades = self._parse_from_balance_changes(tx)
            else:
                # Fallback to balance change parsing
                trades = self._parse_from_balance_changes(tx)
                
            if not trades:
                # Log first 100 failed parses
                global failed_log_count
                if failed_log_count < MAX_FAILED_LOGS:
                    logger.warning(f"SWAP transaction without swap event: {signature}")
                    failed_log_count += 1
            return trades
            
        # First check innerSwaps (modern DEXs)
        inner_swaps = swap.get('innerSwaps', [])
        if inner_swaps:
            for hop_idx, inner_swap in enumerate(inner_swaps):
                hop_trades = self._parse_swap_data(inner_swap, signature, slot, timestamp, dex, hop_idx)
                trades.extend(hop_trades)
        else:
            # Fall back to main swap data
            main_trades = self._parse_swap_data(swap, signature, slot, timestamp, dex, 0)
            trades.extend(main_trades)
            
        return trades
        
    def _parse_swap_data(self, swap_data: Dict[str, Any], signature: str, slot: int, 
                        timestamp: datetime, dex: str, hop_idx: int) -> List[Trade]:
        """Parse swap data into Trade objects"""
        trades = []
        
        native_input = swap_data.get('nativeInput', {})
        native_output = swap_data.get('nativeOutput', {})
        token_inputs = swap_data.get('tokenInputs', [])
        token_outputs = swap_data.get('tokenOutputs', [])
        
        # SOL -> Token
        if native_input and token_outputs:
            sol_amount = Decimal(str(native_input['amount'])) / Decimal('1e9')
            for leg_idx, token_out in enumerate(token_outputs):
                mint = token_out['mint']
                decimals = token_out['rawTokenAmount']['decimals']
                amount = Decimal(str(token_out['rawTokenAmount']['tokenAmount'])) / Decimal(f'1e{decimals}')
                
                trade = Trade(
                    signature=signature,
                    slot=slot,
                    timestamp=timestamp,
                    action='buy',
                    token_mint=mint,
                    token_symbol=mint[:8],  # Temporary, will be updated
                    token_amount=amount,
                    sol_amount=sol_amount,
                    other_mint=None,
                    other_amount=None,
                    price_usd=None,
                    value_usd=None,
                    fees_usd=Decimal('0'),  # Will calculate later
                    dex=dex,
                    hop_idx=hop_idx,
                    leg_idx=leg_idx
                )
                trades.append(trade)
                
        # Token -> SOL
        elif token_inputs and native_output:
            sol_amount = Decimal(str(native_output['amount'])) / Decimal('1e9')
            for leg_idx, token_in in enumerate(token_inputs):
                mint = token_in['mint']
                decimals = token_in['rawTokenAmount']['decimals']
                amount = Decimal(str(token_in['rawTokenAmount']['tokenAmount'])) / Decimal(f'1e{decimals}')
                
                trade = Trade(
                    signature=signature,
                    slot=slot,
                    timestamp=timestamp,
                    action='sell',
                    token_mint=mint,
                    token_symbol=mint[:8],  # Temporary, will be updated
                    token_amount=amount,
                    sol_amount=sol_amount,
                    other_mint=None,
                    other_amount=None,
                    price_usd=None,
                    value_usd=None,
                    fees_usd=Decimal('0'),
                    dex=dex,
                    hop_idx=hop_idx,
                    leg_idx=leg_idx
                )
                trades.append(trade)
                
        # Token -> Token
        elif token_inputs and token_outputs:
            # For token-to-token, create both sell and buy sides
            for leg_idx, (token_in, token_out) in enumerate(zip(token_inputs, token_outputs)):
                # Sell side
                mint_in = token_in['mint']
                decimals_in = token_in['rawTokenAmount']['decimals']
                amount_in = Decimal(str(token_in['rawTokenAmount']['tokenAmount'])) / Decimal(f'1e{decimals_in}')
                
                sell_trade = Trade(
                    signature=signature,
                    slot=slot,
                    timestamp=timestamp,
                    action='sell',
                    token_mint=mint_in,
                    token_symbol=mint_in[:8],
                    token_amount=amount_in,
                    sol_amount=None,
                    other_mint=token_outputs[0]['mint'],  # What we're buying
                    other_amount=None,
                    price_usd=None,
                    value_usd=None,
                    fees_usd=Decimal('0'),
                    dex=dex,
                    hop_idx=hop_idx,
                    leg_idx=leg_idx * 2  # Even numbers for sells
                )
                trades.append(sell_trade)
                
                # Buy side
                mint_out = token_out['mint']
                decimals_out = token_out['rawTokenAmount']['decimals']
                amount_out = Decimal(str(token_out['rawTokenAmount']['tokenAmount'])) / Decimal(f'1e{decimals_out}')
                
                buy_trade = Trade(
                    signature=signature,
                    slot=slot,
                    timestamp=timestamp,
                    action='buy',
                    token_mint=mint_out,
                    token_symbol=mint_out[:8],
                    token_amount=amount_out,
                    sol_amount=None,
                    other_mint=mint_in,  # What we sold
                    other_amount=amount_in,
                    price_usd=None,
                    value_usd=None,
                    fees_usd=Decimal('0'),
                    dex=dex,
                    hop_idx=hop_idx,
                    leg_idx=leg_idx * 2 + 1  # Odd numbers for buys
                )
                trades.append(buy_trade)
                
        return trades
        
    def _parse_pump_amm_transaction(self, tx: Dict[str, Any]) -> List[Trade]:
        """Parse PUMP_AMM transactions from token transfers"""
        trades = []
        timestamp = datetime.fromtimestamp(tx['timestamp'])
        slot = tx['slot']
        signature = tx['signature']
        dex = 'PUMP_AMM'
        
        # Get token transfers
        token_transfers = tx.get('tokenTransfers', [])
        if not token_transfers:
            return trades
            
        # Get the fee payer (user)
        fee_payer = tx.get('feePayer')
        if not fee_payer:
            return trades
            
        # Track transfers by user
        user_sent = []
        user_received = []
        
        for tt in token_transfers:
            if tt.get('fromUserAccount') == fee_payer:
                user_sent.append(tt)
            elif tt.get('toUserAccount') == fee_payer:
                user_received.append(tt)
                
        # Process transfers to identify trades
        # Look for patterns: user sends token A and receives token B
        
        # Find non-SOL tokens sent
        tokens_sent = [t for t in user_sent if t.get('mint') != 'So11111111111111111111111111111111111111112']
        # Find SOL received
        sol_received = [t for t in user_received if t.get('mint') == 'So11111111111111111111111111111111111111112']
        
        if tokens_sent and sol_received:
            # Sold token for SOL
            for token_transfer in tokens_sent:
                mint = token_transfer.get('mint')
                amount = Decimal(str(token_transfer.get('tokenAmount', 0)))
                
                # Sum all SOL received
                sol_amount = sum(Decimal(str(t.get('tokenAmount', 0))) for t in sol_received)
                
                trade = Trade(
                    signature=signature,
                    slot=slot,
                    timestamp=timestamp,
                    action='sell',
                    token_mint=mint,
                    token_symbol=mint[:8],
                    token_amount=amount,
                    sol_amount=sol_amount,
                    other_mint=None,
                    other_amount=None,
                    price_usd=None,
                    value_usd=None,
                    fees_usd=Decimal('0'),
                    dex=dex,
                    hop_idx=0,
                    leg_idx=0
                )
                trades.append(trade)
                
        # Find SOL sent
        sol_sent = [t for t in user_sent if t.get('mint') == 'So11111111111111111111111111111111111111112']
        # Find non-SOL tokens received
        tokens_received = [t for t in user_received if t.get('mint') != 'So11111111111111111111111111111111111111112']
        
        if sol_sent and tokens_received:
            # Bought token with SOL
            for token_transfer in tokens_received:
                mint = token_transfer.get('mint')
                amount = Decimal(str(token_transfer.get('tokenAmount', 0)))
                
                # Sum all SOL sent
                sol_amount = sum(Decimal(str(t.get('tokenAmount', 0))) for t in sol_sent)
                
                trade = Trade(
                    signature=signature,
                    slot=slot,
                    timestamp=timestamp,
                    action='buy',
                    token_mint=mint,
                    token_symbol=mint[:8],
                    token_amount=amount,
                    sol_amount=sol_amount,
                    other_mint=None,
                    other_amount=None,
                    price_usd=None,
                    value_usd=None,
                    fees_usd=Decimal('0'),
                    dex=dex,
                    hop_idx=0,
                    leg_idx=0
                )
                trades.append(trade)
                
        return trades
        
    def _parse_from_balance_changes(self, tx: Dict[str, Any]) -> List[Trade]:
        """Generic parser using token transfers"""
        trades = []
        timestamp = datetime.fromtimestamp(tx['timestamp'])
        slot = tx['slot']
        signature = tx['signature']
        dex = tx.get('source', 'UNKNOWN')
        
        # Get token transfers
        token_transfers = tx.get('tokenTransfers', [])
        if not token_transfers:
            return trades
            
        # Get the fee payer (user)
        fee_payer = tx.get('feePayer')
        if not fee_payer:
            return trades
            
        # Track transfers by user
        user_sent = []
        user_received = []
        
        for tt in token_transfers:
            if tt.get('fromUserAccount') == fee_payer:
                user_sent.append(tt)
            elif tt.get('toUserAccount') == fee_payer:
                user_received.append(tt)
                
        # Group by mint
        sent_by_mint = {}
        received_by_mint = {}
        
        for t in user_sent:
            mint = t.get('mint')
            if mint:
                if mint not in sent_by_mint:
                    sent_by_mint[mint] = Decimal('0')
                sent_by_mint[mint] += Decimal(str(t.get('tokenAmount', 0)))
                
        for t in user_received:
            mint = t.get('mint')
            if mint:
                if mint not in received_by_mint:
                    received_by_mint[mint] = Decimal('0')
                received_by_mint[mint] += Decimal(str(t.get('tokenAmount', 0)))
                
        # Identify trades
        sol_mint = 'So11111111111111111111111111111111111111112'
        
        # Remove SOL from regular tokens
        sol_sent = sent_by_mint.pop(sol_mint, Decimal('0'))
        sol_received = received_by_mint.pop(sol_mint, Decimal('0'))
        
        # Token -> SOL trades
        if sent_by_mint and sol_received > 0:
            for mint, amount in sent_by_mint.items():
                trade = Trade(
                    signature=signature,
                    slot=slot,
                    timestamp=timestamp,
                    action='sell',
                    token_mint=mint,
                    token_symbol=mint[:8],
                    token_amount=amount,
                    sol_amount=sol_received,
                    other_mint=None,
                    other_amount=None,
                    price_usd=None,
                    value_usd=None,
                    fees_usd=Decimal('0'),
                    dex=dex,
                    hop_idx=0,
                    leg_idx=0
                )
                trades.append(trade)
                
        # SOL -> Token trades
        elif sol_sent > 0 and received_by_mint:
            for mint, amount in received_by_mint.items():
                trade = Trade(
                    signature=signature,
                    slot=slot,
                    timestamp=timestamp,
                    action='buy',
                    token_mint=mint,
                    token_symbol=mint[:8],
                    token_amount=amount,
                    sol_amount=sol_sent,
                    other_mint=None,
                    other_amount=None,
                    price_usd=None,
                    value_usd=None,
                    fees_usd=Decimal('0'),
                    dex=dex,
                    hop_idx=0,
                    leg_idx=0
                )
                trades.append(trade)
                
        # Token -> Token trades
        elif len(sent_by_mint) == 1 and len(received_by_mint) == 1:
            sent_mint, sent_amount = list(sent_by_mint.items())[0]
            received_mint, received_amount = list(received_by_mint.items())[0]
            
            # Create sell trade
            trade = Trade(
                signature=signature,
                slot=slot,
                timestamp=timestamp,
                action='sell',
                token_mint=sent_mint,
                token_symbol=sent_mint[:8],
                token_amount=sent_amount,
                sol_amount=None,
                other_mint=received_mint,
                other_amount=received_amount,
                price_usd=None,
                value_usd=None,
                fees_usd=Decimal('0'),
                dex=dex,
                hop_idx=0,
                leg_idx=0
            )
            trades.append(trade)
            
            # Create buy trade
            trade = Trade(
                signature=signature,
                slot=slot,
                timestamp=timestamp,
                action='buy',
                token_mint=received_mint,
                token_symbol=received_mint[:8],
                token_amount=received_amount,
                sol_amount=None,
                other_mint=sent_mint,
                other_amount=sent_amount,
                price_usd=None,
                value_usd=None,
                fees_usd=Decimal('0'),
                dex=dex,
                hop_idx=0,
                leg_idx=1
            )
            trades.append(trade)
            
        return trades
        
    async def _fetch_token_metadata(self, trades: List[Trade]):
        """Fetch token metadata for all unique tokens"""
        unique_mints = set()
        for trade in trades:
            unique_mints.add(trade.token_mint)
            if trade.other_mint:
                unique_mints.add(trade.other_mint)
                
        # Remove already known tokens
        unknown_mints = [mint for mint in unique_mints if mint not in KNOWN_TOKENS and mint not in token_cache]
        
        if not unknown_mints:
            # Update symbols from cache
            for trade in trades:
                if trade.token_mint in KNOWN_TOKENS:
                    trade.token_symbol = KNOWN_TOKENS[trade.token_mint]['symbol']
                elif trade.token_mint in token_cache:
                    trade.token_symbol = token_cache[trade.token_mint]['symbol']
            return
            
        self._report_progress(f"Fetching metadata for {len(unknown_mints)} tokens...")
        
        # Batch fetch metadata (max 100 per request)
        for i in range(0, len(unknown_mints), 100):
            batch = unknown_mints[i:i+100]
            await self.helius_limiter.acquire()
            
            try:
                url = f"{HELIUS_BASE}/token-metadata?api-key={HELIUS_KEY}"
                payload = {
                    "mintAccounts": batch
                }
                
                if not self.session:
                    raise RuntimeError("Session not initialized")
                async with self.session.post(url, json=payload, timeout=ClientTimeout(total=30)) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    
                    for metadata in data:
                        mint = metadata.get('account')
                        # Try onChainMetadata first, then legacy
                        on_chain = metadata.get('onChainMetadata', {}).get('metadata', {}).get('data', {})
                        legacy = metadata.get('legacyMetadata', {})
                        
                        symbol = on_chain.get('symbol') or legacy.get('symbol', mint[:8] if mint else 'UNKNOWN')
                        
                        # Get decimals from onChainAccountInfo
                        decimals = metadata.get('onChainAccountInfo', {}).get('accountInfo', {}).get('data', {}).get('parsed', {}).get('info', {}).get('decimals', 9)
                        
                        if mint:
                            token_cache[mint] = {'symbol': symbol, 'decimals': decimals}
                            
            except Exception as e:
                logger.error(f"Error fetching token metadata: {e}")
                
        # Update trade symbols
        for trade in trades:
            if trade.token_mint in KNOWN_TOKENS:
                trade.token_symbol = KNOWN_TOKENS[trade.token_mint]['symbol']
            elif trade.token_mint in token_cache:
                trade.token_symbol = token_cache[trade.token_mint]['symbol']
                
    async def _fetch_all_prices(self, trades: List[Trade]):
        """Fetch USD prices for all trades"""
        if not BIRDEYE_KEY:
            self._report_progress("Warning: BIRDEYE_API_KEY not set, using fallback prices")
            self._apply_fallback_prices(trades)
            return
            
        # Group trades by minute bucket for efficient batching
        minute_buckets = defaultdict(list)
        for trade in trades:
            minute_ts = int(trade.timestamp.timestamp() // 60) * 60
            minute_buckets[minute_ts].append(trade)
            
        self._report_progress(f"Fetching prices for {len(minute_buckets)} time buckets...")
        
        # Process each minute bucket
        for minute_ts, bucket_trades in minute_buckets.items():
            # Get unique mints for this minute
            unique_mints = set()
            for trade in bucket_trades:
                unique_mints.add(trade.token_mint)
                if trade.other_mint:
                    unique_mints.add(trade.other_mint)
                if trade.sol_amount:
                    unique_mints.add("So11111111111111111111111111111111111111112")
                    
            # Fetch prices for all mints in this minute
            prices = await self._fetch_prices_for_minute(minute_ts, list(unique_mints))
            
            # Apply prices to trades
            for trade in bucket_trades:
                await self._apply_prices_to_trade(trade, prices, minute_ts)
                
    async def _fetch_prices_for_minute(self, minute_ts: int, mints: List[str]) -> Dict[str, Decimal]:
        """Fetch prices for multiple tokens at a specific minute"""
        prices = {}
        
        # Check cache first
        for mint in mints[:]:
            cache_key = f"{mint}_{minute_ts}"
            if cache_key in price_cache:
                prices[mint] = price_cache[cache_key]
                mints.remove(mint)
                
        if not mints:
            return prices
            
        # Batch fetch remaining prices
        for mint in mints:
            # Handle stablecoins
            if mint in ["EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"]:
                prices[mint] = Decimal('1')
                price_cache[f"{mint}_{minute_ts}"] = Decimal('1')
                continue
                
            await self.birdeye_limiter.acquire()
            
            try:
                url = f"{BIRDEYE_BASE}/defi/historical_price_unix"
                params = {
                    "address": mint,
                    "type": "1m",
                    "time_from": minute_ts - 60,
                    "time_to": minute_ts + 60
                }
                headers = {"X-API-KEY": BIRDEYE_KEY}
                
                if not self.session:
                    raise RuntimeError("Session not initialized")
                async with self.session.get(url, params=params, headers=headers, timeout=ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Handle both response formats
                        if data.get('data'):
                            if isinstance(data['data'], dict) and 'value' in data['data']:
                                # Single price format
                                price = Decimal(str(data['data']['value']))
                                prices[mint] = price
                                price_cache[f"{mint}_{minute_ts}"] = price
                            elif data['data'].get('items'):
                                # Array format
                                price = Decimal(str(data['data']['items'][0]['value']))
                                prices[mint] = price
                                price_cache[f"{mint}_{minute_ts}"] = price
                            
            except Exception as e:
                logger.debug(f"Price lookup failed for {mint}: {e}")
                
        return prices
        
    async def _apply_prices_to_trade(self, trade: Trade, prices: Dict[str, Decimal], minute_ts: int):
        """Apply USD prices to a trade"""
        sol_mint = "So11111111111111111111111111111111111111112"
        
        # Get SOL price if needed
        sol_price = prices.get(sol_mint)
        
        if trade.sol_amount and sol_price:
            # SOL-based trade
            trade.value_usd = trade.sol_amount * sol_price
            trade.price_usd = trade.value_usd / trade.token_amount if trade.token_amount else Decimal('0')
            trade.fees_usd = trade.value_usd * Decimal('0.003')
            
        elif trade.other_mint:
            # Token-to-token trade
            token_price = prices.get(trade.token_mint)
            other_price = prices.get(trade.other_mint)
            
            if token_price and trade.action == 'sell':
                trade.value_usd = trade.token_amount * token_price
                trade.price_usd = token_price
                trade.fees_usd = trade.value_usd * Decimal('0.0015')  # Half fee for each side
                
            elif other_price and trade.other_amount and trade.action == 'buy':
                trade.value_usd = trade.other_amount * other_price
                trade.price_usd = trade.value_usd / trade.token_amount if trade.token_amount else Decimal('0')
                trade.fees_usd = trade.value_usd * Decimal('0.0015')
                
            else:
                # Can't price this trade
                trade.priced = False
                trade.value_usd = Decimal('0')
                trade.price_usd = Decimal('0')
                trade.fees_usd = Decimal('0')
        else:
            # Can't price this trade
            trade.priced = False
            trade.value_usd = Decimal('0')
            trade.price_usd = Decimal('0')
            trade.fees_usd = Decimal('0')
            
    def _apply_fallback_prices(self, trades: List[Trade]):
        """Apply fallback prices when Birdeye API not available"""
        sol_price = Decimal('150')  # Fallback SOL price
        
        for trade in trades:
            if trade.sol_amount:
                trade.value_usd = trade.sol_amount * sol_price
                trade.price_usd = trade.value_usd / trade.token_amount if trade.token_amount else Decimal('0')
                trade.fees_usd = trade.value_usd * Decimal('0.003')
            else:
                # Can't price token-to-token without API
                trade.priced = False
                trade.value_usd = Decimal('0')
                trade.price_usd = Decimal('0') 
                trade.fees_usd = Decimal('0')
                
    def _calculate_pnl(self, trades: List[Trade]) -> List[Trade]:
        """Calculate P&L using FIFO accounting"""
        # Group by token
        trades_by_token = defaultdict(list)
        for trade in trades:
            trades_by_token[trade.token_symbol].append(trade)
            
        results = []
        
        for token, token_trades in trades_by_token.items():
            holdings = []  # FIFO queue of (amount, price) tuples
            
            for trade in sorted(token_trades, key=lambda x: (x.timestamp, x.hop_idx, x.leg_idx)):
                if trade.action == 'buy':
                    if trade.priced and trade.price_usd:
                        holdings.append((trade.token_amount, trade.price_usd))
                        
                else:  # sell
                    if not trade.priced:
                        continue
                        
                    remaining_to_sell = trade.token_amount
                    total_cost_basis = Decimal('0')
                    
                    while remaining_to_sell > 0 and holdings:
                        holding_amount, holding_price = holdings[0]
                        
                        if holding_amount <= remaining_to_sell:
                            total_cost_basis += holding_amount * holding_price
                            remaining_to_sell -= holding_amount
                            holdings.pop(0)
                        else:
                            total_cost_basis += remaining_to_sell * holding_price
                            holdings[0] = (holding_amount - remaining_to_sell, holding_price)
                            remaining_to_sell = 0
                            
                    # Update P&L in trade object
                    revenue = trade.token_amount * trade.price_usd if trade.price_usd else Decimal('0')
                    trade.pnl_usd = revenue - total_cost_basis
                    
                results.append(trade)
                
        return sorted(results, key=lambda x: (x.timestamp, x.hop_idx, x.leg_idx))


# Synchronous wrapper for easy API integration
def fetch_wallet_trades(wallet_address: str, progress_callback: Optional[Callable[[str], None]] = None) -> List[Dict[str, Any]]:
    """
    Synchronous wrapper to fetch wallet trades
    
    Args:
        wallet_address: Solana wallet address
        progress_callback: Optional callback for progress updates
        
    Returns:
        List of trade dictionaries
    """
    async def _fetch():
        async with BlockchainFetcher(progress_callback) as fetcher:
            return await fetcher.fetch_wallet_trades(wallet_address)
            
    return asyncio.run(_fetch())


if __name__ == "__main__":
    # Test with command line
    if len(sys.argv) < 2:
        print("Usage: python blockchain_fetcher.py <wallet_address>")
        sys.exit(1)
        
    wallet = sys.argv[1]
    print(f"Fetching trades for wallet: {wallet}")
    
    def print_progress(msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        
    try:
        trades = fetch_wallet_trades(wallet, print_progress)
        print(f"\nFetched {len(trades)} trades")
        
        # Show summary
        if trades:
            total_value = sum(t['value_usd'] for t in trades if t['value_usd'])
            print(f"Total volume: ${total_value:,.2f}")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1) 