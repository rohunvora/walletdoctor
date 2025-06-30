#!/usr/bin/env python3
"""
Optimized Cielo replacement with caching, parallel requests, and token metadata enrichment
"""

import os
import asyncio
import aiohttp
import logging
import json
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib

from .cielo_replacement import TokenPnL, CieloReplacement
from .swap_parser_advanced import AdvancedSwapParser, SwapDetails

logger = logging.getLogger(__name__)

class OptimizedCieloReplacement(CieloReplacement):
    """Optimized version with caching and parallel processing"""
    
    def __init__(self, helius_api_key: str, cache_dir: str = "/tmp/cielo_cache"):
        super().__init__(helius_api_key)
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.parser = AdvancedSwapParser()
        
    async def get_all_token_pnl(self, wallet: str, use_cache: bool = True) -> Dict:
        """Get P&L data with caching and optimization"""
        
        # Check cache first
        if use_cache:
            cached_data = await self._load_from_cache(wallet)
            if cached_data:
                logger.info(f"Using cached data for {wallet}")
                return cached_data
        
        logger.info(f"Fetching fresh data for {wallet}")
        
        # Fetch all data in parallel
        results = await asyncio.gather(
            self._fetch_all_transactions_optimized(wallet),
            self._fetch_token_metadata_batch(wallet),
            self._fetch_current_sol_price(),
            return_exceptions=True
        )
        
        transactions, token_metadata, sol_price = results
        
        if isinstance(transactions, Exception):
            raise transactions
        
        # Update SOL price if fetched successfully
        if not isinstance(sol_price, Exception) and sol_price:
            self._sol_price = sol_price
        
        # Parse swaps using advanced parser
        swaps = await self._parse_swaps_parallel(transactions, wallet)
        
        # Calculate P&L from swaps
        token_data = self._calculate_pnl_from_swaps(swaps, wallet)
        
        # Enrich with metadata
        if not isinstance(token_metadata, Exception):
            self._enrich_token_metadata(token_data, token_metadata)
        
        # Get current prices and balances in parallel
        await self._add_current_data_parallel(token_data, wallet)
        
        # Sort and prepare final result
        sorted_tokens = sorted(token_data.values(), key=lambda x: x.roi_percentage, reverse=True)
        total_stats = self._calculate_total_stats(sorted_tokens)
        
        result = {
            "data": {
                "items": [self._token_to_dict(token) for token in sorted_tokens],
                "total": len(sorted_tokens)
            },
            "total_stats": total_stats,
            "metadata": {
                "wallet": wallet,
                "timestamp": int(datetime.now().timestamp()),
                "sol_price": self._sol_price,
                "data_complete": True
            }
        }
        
        # Cache the result
        if use_cache:
            await self._save_to_cache(wallet, result)
        
        return result
    
    async def _fetch_all_transactions_optimized(self, wallet: str) -> List[Dict]:
        """Fetch transactions with parallel requests"""
        
        # First, get a sample to estimate total count
        sample_txs = await self._fetch_transaction_batch(wallet, limit=10)
        if not sample_txs:
            return []
        
        # Fetch in parallel batches
        batch_size = 100
        max_concurrent = 5
        all_transactions = []
        
        async def fetch_batch(before_sig):
            return await self._fetch_transaction_batch(wallet, before_sig, batch_size)
        
        # Use a queue for parallel fetching
        active_tasks = []
        before_signature = None
        
        while True:
            # Start new tasks up to max_concurrent
            while len(active_tasks) < max_concurrent and (before_signature is None or before_signature):
                task = asyncio.create_task(fetch_batch(before_signature))
                active_tasks.append((task, before_signature))
                before_signature = None  # Will be updated from results
            
            if not active_tasks:
                break
            
            # Wait for any task to complete
            done, pending = await asyncio.wait(
                [task for task, _ in active_tasks],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Process completed tasks
            for task in done:
                try:
                    transactions = await task
                    if transactions:
                        all_transactions.extend(transactions)
                        # Update before_signature for next batch
                        if len(transactions) == batch_size:
                            before_signature = transactions[-1].get('signature')
                except Exception as e:
                    logger.error(f"Batch fetch error: {e}")
            
            # Remove completed tasks
            active_tasks = [(t, sig) for t, sig in active_tasks if t not in done]
        
        return all_transactions
    
    async def _fetch_transaction_batch(self, wallet: str, before_sig: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Fetch a single batch of transactions"""
        
        url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
        params = {
            "api-key": self.helius_key,
            "limit": limit,
            "type": "SWAP"
        }
        
        if before_sig:
            params["before"] = before_sig
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Helius API error: {response.status}")
                        return []
            except Exception as e:
                logger.error(f"Transaction fetch error: {e}")
                return []
    
    async def _parse_swaps_parallel(self, transactions: List[Dict], wallet: str) -> List[SwapDetails]:
        """Parse swaps in parallel batches"""
        
        # Split into chunks for parallel processing
        chunk_size = 50
        chunks = [transactions[i:i + chunk_size] for i in range(0, len(transactions), chunk_size)]
        
        async def parse_chunk(chunk):
            return [
                swap for tx in chunk
                if (swap := self.parser.parse_transaction(tx, wallet)) is not None
            ]
        
        # Parse all chunks in parallel
        tasks = [parse_chunk(chunk) for chunk in chunks]
        results = await asyncio.gather(*tasks)
        
        # Flatten results
        all_swaps = []
        for chunk_swaps in results:
            all_swaps.extend(chunk_swaps)
        
        return sorted(all_swaps, key=lambda x: x.timestamp)
    
    def _calculate_pnl_from_swaps(self, swaps: List[SwapDetails], wallet: str) -> Dict[str, TokenPnL]:
        """Calculate P&L from parsed swaps"""
        
        token_data = defaultdict(lambda: {
            'buys': [],
            'sells': [],
            'first_trade': float('inf'),
            'last_trade': 0,
            'info': {}
        })
        
        for swap in swaps:
            mint = swap.token_mint
            
            # Update trade times
            token_data[mint]['first_trade'] = min(token_data[mint]['first_trade'], swap.timestamp)
            token_data[mint]['last_trade'] = max(token_data[mint]['last_trade'], swap.timestamp)
            
            # Store token info
            if not token_data[mint]['info']:
                token_data[mint]['info'] = {
                    'symbol': swap.token_symbol,
                    'name': swap.token_name,
                    'decimals': swap.token_decimals
                }
            
            # Categorize swap
            if swap.swap_type == 'buy':
                token_data[mint]['buys'].append({
                    'amount': swap.token_amount,
                    'usd_value': swap.usd_value,
                    'price': swap.price_per_token,
                    'timestamp': swap.timestamp
                })
            else:
                token_data[mint]['sells'].append({
                    'amount': swap.token_amount,
                    'usd_value': swap.usd_value,
                    'price': swap.price_per_token,
                    'timestamp': swap.timestamp
                })
        
        # Convert to TokenPnL objects
        result = {}
        for mint, data in token_data.items():
            if not data['buys']:
                continue
            
            # Calculate totals
            total_buy_amount = sum(b['amount'] for b in data['buys'])
            total_buy_usd = sum(b['usd_value'] for b in data['buys'])
            total_sell_amount = sum(s['amount'] for s in data['sells'])
            total_sell_usd = sum(s['usd_value'] for s in data['sells'])
            
            # Calculate averages
            avg_buy_price = total_buy_usd / total_buy_amount if total_buy_amount > 0 else 0
            avg_sell_price = total_sell_usd / total_sell_amount if total_sell_amount > 0 else 0
            
            # Calculate realized P&L (only on sold portion)
            if total_sell_amount > 0 and total_buy_amount > 0:
                # Cost basis of sold tokens
                sold_cost_basis = (total_sell_amount / total_buy_amount) * total_buy_usd
                realized_pnl = total_sell_usd - sold_cost_basis
            else:
                realized_pnl = 0
            
            roi_percentage = (realized_pnl / total_buy_usd * 100) if total_buy_usd > 0 else 0
            
            # Calculate holding
            holding_amount = total_buy_amount - total_sell_amount
            
            # Calculate holding time
            holding_time = self._calculate_holding_time(data['buys'], data['sells'], data['last_trade'])
            
            token_pnl = TokenPnL(
                num_swaps=len(data['buys']),
                total_buy_usd=total_buy_usd,
                total_buy_amount=total_buy_amount,
                total_sell_usd=total_sell_usd,
                total_sell_amount=total_sell_amount,
                average_buy_price=avg_buy_price,
                average_sell_price=avg_sell_price,
                total_pnl_usd=realized_pnl,
                roi_percentage=roi_percentage,
                unrealized_pnl_usd=0,
                unrealized_roi_percentage=0,
                token_price=0,
                token_address=mint,
                token_symbol=data['info'].get('symbol', 'Unknown'),
                token_name=data['info'].get('name', 'Unknown Token'),
                first_trade=int(data['first_trade']),
                last_trade=int(data['last_trade']),
                holding_time_seconds=holding_time,
                holding_amount=holding_amount,
                holding_amount_usd=0
            )
            
            result[mint] = token_pnl
        
        return result
    
    def _calculate_holding_time(self, buys: List[Dict], sells: List[Dict], last_trade: int) -> int:
        """Calculate weighted average holding time"""
        
        if not sells:
            # Still holding - time from first buy to now
            if buys:
                return int(datetime.now().timestamp()) - buys[0]['timestamp']
            return 0
        
        # Calculate weighted average holding time for sold tokens
        total_time = 0
        total_amount = 0
        
        # Simple approximation: FIFO matching
        buy_queue = sorted(buys, key=lambda x: x['timestamp'])
        sell_queue = sorted(sells, key=lambda x: x['timestamp'])
        
        for sell in sell_queue:
            remaining_sell = sell['amount']
            
            while remaining_sell > 0 and buy_queue:
                buy = buy_queue[0]
                
                if buy['amount'] <= remaining_sell:
                    # Entire buy consumed
                    hold_time = sell['timestamp'] - buy['timestamp']
                    total_time += hold_time * buy['amount']
                    total_amount += buy['amount']
                    remaining_sell -= buy['amount']
                    buy_queue.pop(0)
                else:
                    # Partial buy consumed
                    hold_time = sell['timestamp'] - buy['timestamp']
                    total_time += hold_time * remaining_sell
                    total_amount += remaining_sell
                    buy['amount'] -= remaining_sell
                    remaining_sell = 0
        
        return int(total_time / total_amount) if total_amount > 0 else 0
    
    async def _fetch_token_metadata_batch(self, wallet: str) -> Dict[str, Dict]:
        """Fetch token metadata for all tokens traded by wallet"""
        
        # This would ideally use a token metadata service
        # For now, return empty dict - metadata will come from transactions
        return {}
    
    async def _fetch_current_sol_price(self) -> Optional[float]:
        """Fetch current SOL price"""
        
        try:
            async with aiohttp.ClientSession() as session:
                # Use Jupiter price API
                url = "https://price.jup.ag/v6/price"
                params = {"ids": "So11111111111111111111111111111111111111112"}
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        sol_data = data.get('data', {}).get('So11111111111111111111111111111111111111112', {})
                        return sol_data.get('price', 150.0)
        except Exception as e:
            logger.error(f"Error fetching SOL price: {e}")
        
        return None
    
    async def _add_current_data_parallel(self, token_data: Dict[str, TokenPnL], wallet: str):
        """Add current prices and balances in parallel"""
        
        # Get tokens that need prices (those with holdings)
        tokens_with_holdings = [
            token for token in token_data.values() 
            if token.holding_amount > 0
        ]
        
        if not tokens_with_holdings:
            return
        
        # Fetch balances and prices in parallel
        results = await asyncio.gather(
            self._get_token_balances(wallet),
            self._fetch_token_prices_batch([t.token_address for t in tokens_with_holdings]),
            return_exceptions=True
        )
        
        balances, prices = results
        
        # Update token data
        for token in tokens_with_holdings:
            # Update balance if available
            if not isinstance(balances, Exception) and token.token_address in balances:
                token.holding_amount = balances[token.token_address]
            
            # Update price and unrealized P&L
            if not isinstance(prices, Exception) and token.token_address in prices:
                current_price = prices[token.token_address]
                token.token_price = current_price
                token.holding_amount_usd = token.holding_amount * current_price
                
                # Calculate unrealized P&L
                if token.total_buy_amount > 0:
                    holding_cost_basis = (token.holding_amount / token.total_buy_amount) * token.total_buy_usd
                    token.unrealized_pnl_usd = token.holding_amount_usd - holding_cost_basis
                    token.unrealized_roi_percentage = (token.unrealized_pnl_usd / holding_cost_basis * 100) if holding_cost_basis > 0 else 0
                
                # Update total P&L
                token.total_pnl_usd = token.total_pnl_usd + token.unrealized_pnl_usd
                token.roi_percentage = (token.total_pnl_usd / token.total_buy_usd * 100) if token.total_buy_usd > 0 else 0
    
    async def _fetch_token_prices_batch(self, mints: List[str]) -> Dict[str, float]:
        """Fetch prices for multiple tokens in batches"""
        
        prices = {}
        batch_size = 50
        
        async with aiohttp.ClientSession() as session:
            for i in range(0, len(mints), batch_size):
                batch = mints[i:i + batch_size]
                mint_str = ",".join(batch)
                
                try:
                    async with session.get(
                        self.jupiter_price_api,
                        params={"ids": mint_str}
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            for mint, price_data in data.get('data', {}).items():
                                prices[mint] = price_data.get('price', 0)
                except Exception as e:
                    logger.error(f"Price fetch error: {e}")
                
                await asyncio.sleep(0.1)  # Rate limiting
        
        return prices
    
    def _enrich_token_metadata(self, token_data: Dict[str, TokenPnL], metadata: Dict[str, Dict]):
        """Enrich tokens with additional metadata"""
        
        for mint, token in token_data.items():
            if mint in metadata:
                meta = metadata[mint]
                token.token_symbol = meta.get('symbol', token.token_symbol)
                token.token_name = meta.get('name', token.token_name)
    
    def _token_to_dict(self, token: TokenPnL) -> Dict:
        """Convert TokenPnL to dict matching Cielo's format exactly"""
        
        return {
            "num_swaps": token.num_swaps,
            "total_buy_usd": token.total_buy_usd,
            "total_buy_amount": token.total_buy_amount,
            "total_sell_usd": token.total_sell_usd,
            "total_sell_amount": token.total_sell_amount,
            "average_buy_price": token.average_buy_price,
            "average_sell_price": token.average_sell_price,
            "total_pnl_usd": token.total_pnl_usd,
            "roi_percentage": token.roi_percentage,
            "unrealized_pnl_usd": token.unrealized_pnl_usd,
            "unrealized_roi_percentage": token.unrealized_roi_percentage,
            "token_price": token.token_price,
            "token_address": token.token_address,
            "token_symbol": token.token_symbol,
            "token_name": token.token_name,
            "chain": token.chain,
            "is_honeypot": token.is_honeypot,
            "first_trade": token.first_trade,
            "last_trade": token.last_trade,
            "holding_time_seconds": token.holding_time_seconds,
            "holding_amount": token.holding_amount,
            "holding_amount_usd": token.holding_amount_usd
        }
    
    async def _load_from_cache(self, wallet: str) -> Optional[Dict]:
        """Load cached data if fresh enough"""
        
        cache_file = os.path.join(self.cache_dir, f"{wallet}.json")
        
        if not os.path.exists(cache_file):
            return None
        
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            # Check if cache is fresh (less than 5 minutes old)
            cache_time = data.get('metadata', {}).get('timestamp', 0)
            if datetime.now().timestamp() - cache_time < 300:
                return data
        except Exception as e:
            logger.error(f"Cache load error: {e}")
        
        return None
    
    async def _save_to_cache(self, wallet: str, data: Dict):
        """Save data to cache"""
        
        cache_file = os.path.join(self.cache_dir, f"{wallet}.json")
        
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Cache save error: {e}")

# Convenience function
async def get_complete_pnl_optimized(wallet: str, helius_key: Optional[str] = None, use_cache: bool = True) -> Dict:
    """Get complete P&L data with optimizations"""
    
    helius_key = helius_key or os.getenv('HELIUS_API_KEY')
    if not helius_key:
        raise ValueError("Helius API key required")
    
    replacement = OptimizedCieloReplacement(helius_key)
    return await replacement.get_all_token_pnl(wallet, use_cache)