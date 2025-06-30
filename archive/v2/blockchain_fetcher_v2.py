#!/usr/bin/env python3
"""
Blockchain Fetcher V2 - Implementing expert recommendations
- Collapses multi-hop trades to avoid duplication
- Proper guard clauses for missing fields
- Queries both SWAP and UNKNOWN source swaps
"""

import os
import asyncio
import aiohttp
from aiohttp import ClientTimeout
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional, Set, Tuple, Callable
from dataclasses import dataclass
from collections import defaultdict

# Environment variables
HELIUS_KEY = os.getenv("HELIUS_KEY", "09cd02b2-f35d-4d54-ac9b-a9033919d6ee")
BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE3MzU3Nzg0NTl9.Y6D9KikVO__nDv2fEwqyEseQS_gYxvtETvB9Y8rJl6E")

# Constants
HELIUS_BASE = "https://api.helius.xyz/v0"
HELIUS_RPS = 10
BIRDEYE_RPS = 1
MAX_RETRIES = 3
RETRY_DELAY = 1

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DEX sources to track
DEX_SOURCES = [
    'RAYDIUM', 'JUPITER', 'ORCA', 'PHOENIX', 'METEORA',
    'PUMP_AMM', 'FLUXBEAM', 'MOONSHOT', 'BONKSWAP'
]

@dataclass
class Trade:
    """Simplified trade structure - one per transaction signature"""
    signature: str
    slot: int
    timestamp: datetime
    action: str  # 'buy' or 'sell' 
    token_in_mint: str
    token_in_symbol: str
    token_in_amount: Decimal
    token_out_mint: str
    token_out_symbol: str
    token_out_amount: Decimal
    price_usd: Optional[Decimal]
    value_usd: Optional[Decimal]
    fees_usd: Decimal
    dex: str
    route_hops: int  # Number of hops in the route
    priced: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        # Determine if this is a buy or sell based on SOL
        sol_mint = 'So11111111111111111111111111111111111111112'
        
        if self.token_out_mint == sol_mint:
            # Selling token for SOL
            return {
                'timestamp': self.timestamp.isoformat(),
                'action': 'sell',
                'token': self.token_in_symbol,
                'amount': float(self.token_in_amount),
                'price': float(self.price_usd) if self.price_usd else None,
                'value_usd': float(self.value_usd) if self.value_usd else None,
                'pnl_usd': 0.0,  # Calculated later
                'fees_usd': float(self.fees_usd),
                'priced': self.priced
            }
        else:
            # Buying token with SOL (or token-to-token)
            return {
                'timestamp': self.timestamp.isoformat(),
                'action': 'buy',
                'token': self.token_out_symbol,
                'amount': float(self.token_out_amount),
                'price': float(self.price_usd) if self.price_usd else None,
                'value_usd': float(self.value_usd) if self.value_usd else None,
                'pnl_usd': 0.0,
                'fees_usd': float(self.fees_usd),
                'priced': self.priced
            }

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

class BlockchainFetcherV2:
    """Improved fetcher implementing expert recommendations"""
    
    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None):
        self.progress_callback = progress_callback or (lambda x: logger.info(x))
        self.helius_limiter = RateLimiter(HELIUS_RPS)
        self.birdeye_limiter = RateLimiter(BIRDEYE_RPS)
        self.session: Optional[aiohttp.ClientSession] = None
        self.empty_pages = 0
        
        # Metrics tracking
        self.metrics = {
            'signatures_fetched': 0,
            'signatures_parsed': 0,
            'swap_rows_written': 0,
            'unknown_rows': 0,
            'parser_errors': 0
        }
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    def _report_progress(self, message: str):
        """Report progress to callback"""
        self.progress_callback(message)
        
    def _report_metrics(self):
        """Report final metrics"""
        self._report_progress("\n=== METRICS ===")
        for key, value in self.metrics.items():
            self._report_progress(f"{key}: {value}")
            
        # Calculate percentages
        if self.metrics['signatures_fetched'] > 0:
            parse_rate = (self.metrics['signatures_parsed'] / self.metrics['signatures_fetched']) * 100
            self._report_progress(f"Parse rate: {parse_rate:.1f}%")
            
        if self.metrics['swap_rows_written'] > 0:
            unknown_rate = (self.metrics['unknown_rows'] / self.metrics['swap_rows_written']) * 100
            self._report_progress(f"Unknown source rate: {unknown_rate:.1f}%")
            
    async def fetch_wallet_trades(self, wallet_address: str) -> List[Dict[str, Any]]:
        """Main entry point - fetches all trades for a wallet"""
        if not HELIUS_KEY:
            raise ValueError("HELIUS_KEY environment variable not set")
            
        self._report_progress(f"Starting fetch for wallet: {wallet_address}")
        
        # Reset metrics
        self.metrics = {
            'signatures_fetched': 0,
            'signatures_parsed': 0,
            'swap_rows_written': 0,
            'unknown_rows': 0,
            'parser_errors': 0
        }
        
        # Step 1: Fetch SWAP transactions
        self._report_progress("Pass 1: Fetching type=SWAP transactions...")
        swap_transactions = await self._fetch_transactions(wallet_address, tx_type="SWAP")
        
        # Step 2: Fetch UNKNOWN source swaps
        self._report_progress("Pass 2: Fetching type=SWAP&source=UNKNOWN transactions...")
        unknown_swaps = await self._fetch_transactions(wallet_address, tx_type="SWAP", source="UNKNOWN")
        
        # Combine and deduplicate
        all_transactions = swap_transactions + unknown_swaps
        unique_signatures = {tx['signature'] for tx in all_transactions}
        self.metrics['signatures_fetched'] = len(unique_signatures)
        
        # Deduplicate by signature
        seen = set()
        unique_transactions = []
        for tx in all_transactions:
            if tx['signature'] not in seen:
                seen.add(tx['signature'])
                unique_transactions.append(tx)
                
        self._report_progress(f"Total unique transactions: {len(unique_transactions)}")
        
        # Step 3: Extract trades (collapsing multi-hop)
        all_trades = await self._extract_all_trades(unique_transactions)
        self._report_progress(f"Extracted {len(all_trades)} trades")
        
        # Step 4: Fetch token metadata
        await self._fetch_token_metadata(all_trades)
        
        # Step 5: Fetch prices
        await self._fetch_all_prices(all_trades)
        
        # Step 6: Calculate P&L
        trades_with_pnl = self._calculate_pnl(all_trades)
        
        # Report metrics
        self._report_metrics()
        
        # Convert to dictionaries
        return [trade.to_dict() for trade in trades_with_pnl]
        
    async def _fetch_transactions(self, wallet: str, tx_type: str, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch transactions with proper pagination"""
        transactions = []
        before_sig = None
        page = 0
        empty_pages = 0
        
        while True:
            page += 1
            await self.helius_limiter.acquire()
            
            params = {
                "api-key": HELIUS_KEY,
                "limit": 100,
                "type": tx_type,
                "maxSupportedTransactionVersion": "0"
            }
            
            if source:
                params["source"] = source
                
            if before_sig:
                params["before"] = before_sig
                
            try:
                url = f"{HELIUS_BASE}/addresses/{wallet}/transactions"
                if not self.session:
                    raise RuntimeError("Session not initialized")
                    
                async with self.session.get(url, params=params, timeout=ClientTimeout(total=30)) as resp:
                    if resp.status == 429:
                        retry_after = int(resp.headers.get('Retry-After', '5'))
                        self._report_progress(f"Rate limited, waiting {retry_after}s...")
                        await asyncio.sleep(retry_after)
                        continue
                        
                    resp.raise_for_status()
                    data = await resp.json()
                    
                    if isinstance(data, dict) and 'error' in data:
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
                    
                    source_info = f" source={source}" if source else ""
                    self._report_progress(f"Page {page}: {len(data)} {tx_type}{source_info} transactions")
                    
                    before_sig = data[-1]['signature']
                    
            except Exception as e:
                logger.error(f"Error fetching transactions: {e}")
                self.metrics['parser_errors'] += 1
                break
                
        return transactions
        
    async def _extract_all_trades(self, transactions: List[Dict[str, Any]]) -> List[Trade]:
        """Extract trades from all transactions"""
        all_trades = []
        
        for tx in transactions:
            if tx.get('transactionError'):
                continue
                
            try:
                trade = self._extract_trade_from_transaction(tx)
                if trade:
                    all_trades.append(trade)
                    self.metrics['signatures_parsed'] += 1
                    self.metrics['swap_rows_written'] += 1
                    
                    if tx.get('source') == 'UNKNOWN':
                        self.metrics['unknown_rows'] += 1
                        
            except Exception as e:
                logger.error(f"Error parsing transaction {tx.get('signature', 'unknown')}: {e}")
                self.metrics['parser_errors'] += 1
                
        return all_trades
        
    def _extract_trade_from_transaction(self, tx: Dict[str, Any]) -> Optional[Trade]:
        """Extract single trade from transaction (collapsing multi-hop)"""
        timestamp = datetime.fromtimestamp(tx['timestamp'])
        slot = tx['slot']
        signature = tx['signature']
        dex = tx.get('source', 'UNKNOWN')
        
        # Get swap events
        events = tx.get('events', {})
        swap = events.get('swap', {})
        
        if not swap:
            # Try fallback parsing for transactions without swap events
            return self._parse_from_token_transfers(tx)
            
        # Get all hops
        inner_swaps = swap.get('innerSwaps', [])
        hops = inner_swaps if inner_swaps else [swap]
        
        if not hops:
            return None
            
        # Extract first input and last output (collapsing multi-hop)
        try:
            first_hop = hops[0]
            last_hop = hops[-1]
            
            # Get input from first hop
            if first_hop.get('nativeInput'):
                # SOL input
                token_in_mint = 'So11111111111111111111111111111111111111112'
                token_in_symbol = 'SOL'
                token_in_amount = Decimal(str(first_hop['nativeInput']['amount'])) / Decimal('1e9')
            elif first_hop.get('tokenInputs'):
                # Token input
                token_in = first_hop['tokenInputs'][0]
                if 'rawTokenAmount' not in token_in:
                    return None  # Guard clause
                token_in_mint = token_in['mint']
                token_in_symbol = token_in_mint[:8]  # Will be updated later
                raw_amount = token_in['rawTokenAmount']
                token_in_amount = self._safe_token_amount(raw_amount)
                if token_in_amount is None:
                    return None
            else:
                return None
                
            # Get output from last hop
            if last_hop.get('nativeOutput'):
                # SOL output
                token_out_mint = 'So11111111111111111111111111111111111111112'
                token_out_symbol = 'SOL'
                token_out_amount = Decimal(str(last_hop['nativeOutput']['amount'])) / Decimal('1e9')
            elif last_hop.get('tokenOutputs'):
                # Token output
                token_out = last_hop['tokenOutputs'][-1]  # Last output
                if 'rawTokenAmount' not in token_out:
                    return None  # Guard clause
                token_out_mint = token_out['mint']
                token_out_symbol = token_out_mint[:8]  # Will be updated later
                raw_amount = token_out['rawTokenAmount']
                token_out_amount = self._safe_token_amount(raw_amount)
                if token_out_amount is None:
                    return None
            else:
                return None
                
            # Create single trade representing entire route
            return Trade(
                signature=signature,
                slot=slot,
                timestamp=timestamp,
                action='swap',  # Will be determined later based on SOL side
                token_in_mint=token_in_mint,
                token_in_symbol=token_in_symbol,
                token_in_amount=token_in_amount,
                token_out_mint=token_out_mint,
                token_out_symbol=token_out_symbol,
                token_out_amount=token_out_amount,
                price_usd=None,
                value_usd=None,
                fees_usd=Decimal('0'),
                dex=dex,
                route_hops=len(hops),
                priced=True
            )
            
        except (KeyError, IndexError, TypeError) as e:
            logger.debug(f"Failed to parse swap data: {e}")
            return None
            
    def _safe_token_amount(self, raw: Dict[str, Any]) -> Optional[Decimal]:
        """Safely extract token amount with guard clause"""
        try:
            amount = Decimal(str(raw['tokenAmount']))
            decimals = int(raw['decimals'])
            return amount / Decimal(f'1e{decimals}')
        except (KeyError, TypeError, ValueError):
            return None
            
    def _parse_from_token_transfers(self, tx: Dict[str, Any]) -> Optional[Trade]:
        """Fallback parser using token transfers for transactions without swap events"""
        # Similar to previous implementation but returns single Trade
        # This is a simplified version - implement full logic if needed
        return None
        
    async def _fetch_token_metadata(self, trades: List[Trade]):
        """Fetch token metadata for all unique tokens"""
        unique_mints = set()
        for trade in trades:
            unique_mints.add(trade.token_in_mint)
            unique_mints.add(trade.token_out_mint)
            
        if not unique_mints:
            return
            
        self._report_progress(f"Fetching metadata for {len(unique_mints)} tokens...")
        
        # Batch requests
        for batch_start in range(0, len(unique_mints), 100):
            batch = list(unique_mints)[batch_start:batch_start + 100]
            await self.helius_limiter.acquire()
            
            try:
                url = f"{HELIUS_BASE}/token-metadata"
                params = {"api-key": HELIUS_KEY}
                
                if not self.session:
                    raise RuntimeError("Session not initialized")
                    
                async with self.session.post(
                    url,
                    params=params,
                    json={"mintAccounts": batch},
                    timeout=ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        metadata_list = await resp.json()
                        
                        # Create lookup
                        metadata_map = {m['account']: m for m in metadata_list if m}
                        
                        # Update trades
                        for trade in trades:
                            if trade.token_in_mint in metadata_map:
                                trade.token_in_symbol = metadata_map[trade.token_in_mint].get('symbol', trade.token_in_mint[:8])
                            if trade.token_out_mint in metadata_map:
                                trade.token_out_symbol = metadata_map[trade.token_out_mint].get('symbol', trade.token_out_mint[:8])
                                
            except Exception as e:
                logger.error(f"Error fetching token metadata: {e}")
                
    async def _fetch_all_prices(self, trades: List[Trade]):
        """Fetch historical prices for all trades"""
        # Implementation similar to previous version
        # For brevity, not fully implemented here
        self._report_progress("Fetching prices...")
        # TODO: Implement price fetching
        
    def _calculate_pnl(self, trades: List[Trade]) -> List[Trade]:
        """Calculate P&L using FIFO accounting"""
        # Sort by timestamp
        sorted_trades = sorted(trades, key=lambda x: x.timestamp)
        
        # Group by token
        positions = defaultdict(list)  # token -> list of (amount, cost_basis)
        
        for trade in sorted_trades:
            # Simplified P&L calculation
            # TODO: Implement full FIFO logic
            pass
            
        return sorted_trades

# Convenience function
def fetch_wallet_trades_v2(wallet_address: str, progress_callback: Optional[Callable[[str], None]] = None) -> List[Dict[str, Any]]:
    """Synchronous wrapper for async fetch"""
    async def _fetch():
        async with BlockchainFetcherV2(progress_callback) as fetcher:
            return await fetcher.fetch_wallet_trades(wallet_address)
            
    return asyncio.run(_fetch())

if __name__ == "__main__":
    # Test with sample wallet
    def print_progress(msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        
    wallet = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
    print(f"Fetching trades for wallet: {wallet}")
    
    trades = fetch_wallet_trades_v2(wallet, print_progress)
    print(f"\nFetched {len(trades)} trades") 