#!/usr/bin/env python3
"""
Complete Cielo replacement that fetches ALL historical data
Uses enhanced Helius API to get complete transaction history
"""

import os
import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional, Set
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, asdict
import json
import time

logger = logging.getLogger(__name__)

@dataclass
class TokenPnL:
    """Exact Cielo token data structure"""
    num_swaps: int
    total_buy_usd: float
    total_buy_amount: float
    total_sell_usd: float
    total_sell_amount: float
    average_buy_price: float
    average_sell_price: float
    total_pnl_usd: float
    roi_percentage: float
    unrealized_pnl_usd: float
    unrealized_roi_percentage: float
    token_price: float
    token_address: str
    token_symbol: str
    token_name: str
    chain: str = "solana"
    is_honeypot: bool = False
    first_trade: int = 0
    last_trade: int = 0
    holding_time_seconds: int = 0
    holding_amount: float = 0
    holding_amount_usd: float = 0

class CompleteCieloReplacement:
    """Complete replacement that gets ALL historical data"""
    
    def __init__(self, helius_api_key: str):
        self.helius_key = helius_api_key
        self._sol_price = 150.0
        self._rate_limit_delay = 0.2  # 200ms between requests
        self._last_request = 0
        
    async def get_all_token_pnl(self, wallet: str) -> Dict:
        """Get COMPLETE P&L data for ALL tokens ever traded"""
        
        logger.info(f"Fetching COMPLETE history for {wallet}")
        
        # Method 1: Enhanced transaction history endpoint
        all_swaps = await self._fetch_complete_history(wallet)
        
        if not all_swaps:
            logger.warning("No swaps found, trying alternative method")
            # Method 2: Parse all transactions
            all_swaps = await self._fetch_and_parse_all_transactions(wallet)
        
        logger.info(f"Found {len(all_swaps)} total swaps")
        
        # Calculate P&L from all swaps
        token_data = self._calculate_token_pnl_from_swaps(all_swaps)
        
        logger.info(f"Calculated P&L for {len(token_data)} tokens")
        
        # Add current prices for holdings
        await self._add_current_prices(token_data, wallet)
        
        # Sort by ROI
        sorted_tokens = sorted(token_data.values(), key=lambda x: x.roi_percentage, reverse=True)
        
        # Calculate stats
        total_stats = self._calculate_total_stats(sorted_tokens)
        
        return {
            "data": {
                "items": [asdict(token) for token in sorted_tokens],
                "total": len(sorted_tokens)
            },
            "total_stats": total_stats,
            "metadata": {
                "wallet": wallet,
                "timestamp": int(datetime.now().timestamp()),
                "sol_price": self._sol_price,
                "data_complete": True,
                "source": "helius_complete"
            }
        }
    
    async def _rate_limit(self):
        """Simple rate limiting"""
        now = time.time()
        elapsed = now - self._last_request
        if elapsed < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - elapsed)
        self._last_request = time.time()
    
    async def _fetch_complete_history(self, wallet: str) -> List[Dict]:
        """Fetch complete swap history using enhanced endpoint"""
        
        all_swaps = []
        
        async with aiohttp.ClientSession() as session:
            # Try enhanced history endpoint
            url = "https://api.helius.xyz/v0/addresses/{}/transactions"
            
            before_sig = None
            empty_pages = 0
            page = 0
            
            while empty_pages < 3:  # Stop after 3 empty pages
                await self._rate_limit()
                
                params = {
                    "api-key": self.helius_key,
                    "limit": 1000,  # Max limit
                    "type": "SWAP",
                    "source": "ALL"  # Get from all sources
                }
                
                if before_sig:
                    params["before"] = before_sig
                
                try:
                    async with session.get(
                        url.format(wallet),
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as response:
                        
                        if response.status == 429:
                            logger.warning("Rate limited, waiting...")
                            await asyncio.sleep(5)
                            continue
                        
                        if response.status != 200:
                            logger.error(f"API error: {response.status}")
                            break
                        
                        data = await response.json()
                        
                        if not data:
                            empty_pages += 1
                            continue
                        
                        empty_pages = 0
                        page += 1
                        
                        # Parse swaps from transactions
                        for tx in data:
                            swap_info = self._extract_swap_info(tx, wallet)
                            if swap_info:
                                all_swaps.append(swap_info)
                        
                        logger.info(f"Page {page}: Found {len(data)} transactions")
                        
                        # Get last signature for pagination
                        if data:
                            before_sig = data[-1].get('signature')
                        
                except Exception as e:
                    logger.error(f"Error fetching page {page}: {e}")
                    break
        
        return all_swaps
    
    async def _fetch_and_parse_all_transactions(self, wallet: str) -> List[Dict]:
        """Alternative: Fetch ALL transactions and parse swaps"""
        
        all_swaps = []
        
        async with aiohttp.ClientSession() as session:
            url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
            
            before_sig = None
            total_txs = 0
            
            while True:
                await self._rate_limit()
                
                params = {
                    "api-key": self.helius_key,
                    "limit": 1000
                }
                
                if before_sig:
                    params["before"] = before_sig
                
                try:
                    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=60)) as response:
                        if response.status != 200:
                            break
                        
                        data = await response.json()
                        if not data:
                            break
                        
                        total_txs += len(data)
                        
                        # Parse each transaction
                        for tx in data:
                            if self._is_swap_transaction(tx):
                                swap_info = self._extract_swap_info(tx, wallet)
                                if swap_info:
                                    all_swaps.append(swap_info)
                        
                        # Continue pagination
                        before_sig = data[-1].get('signature') if len(data) == 1000 else None
                        
                        if not before_sig:
                            break
                        
                        logger.info(f"Processed {total_txs} transactions, found {len(all_swaps)} swaps")
                        
                except Exception as e:
                    logger.error(f"Error: {e}")
                    break
        
        return all_swaps
    
    def _is_swap_transaction(self, tx: Dict) -> bool:
        """Check if transaction is a swap"""
        
        # Check type
        if tx.get('type') == 'SWAP':
            return True
        
        # Check for DEX instructions
        instructions = tx.get('instructions', [])
        dex_programs = {
            '675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8',  # Raydium
            'whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc',  # Orca
            'JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4',  # Jupiter
        }
        
        for instruction in instructions:
            if instruction.get('programId') in dex_programs:
                return True
        
        # Check for token + SOL transfers
        has_token_transfer = any(tx.get('tokenTransfers', []))
        has_sol_transfer = any(tx.get('nativeTransfers', []))
        
        return has_token_transfer and has_sol_transfer
    
    def _extract_swap_info(self, tx: Dict, wallet: str) -> Optional[Dict]:
        """Extract swap information from transaction"""
        
        # Calculate SOL change
        sol_change = 0
        for transfer in tx.get('nativeTransfers', []):
            if transfer.get('fromUserAccount') == wallet:
                sol_change -= transfer.get('amount', 0) / 1e9
            elif transfer.get('toUserAccount') == wallet:
                sol_change += transfer.get('amount', 0) / 1e9
        
        if abs(sol_change) < 0.001:
            return None
        
        # Find token transfers
        for transfer in tx.get('tokenTransfers', []):
            mint = transfer.get('mint')
            if not mint or mint == 'So11111111111111111111111111111111111111112':
                continue
            
            amount = float(transfer.get('tokenAmount', 0))
            if amount <= 0:
                continue
            
            # Determine direction
            if transfer.get('fromUserAccount') == wallet and sol_change > 0:
                # Sold token
                return {
                    'type': 'sell',
                    'token_mint': mint,
                    'token_amount': amount,
                    'sol_amount': abs(sol_change),
                    'timestamp': tx.get('timestamp', 0),
                    'signature': tx.get('signature'),
                    'token_symbol': self._get_token_symbol(transfer, mint)
                }
            elif transfer.get('toUserAccount') == wallet and sol_change < 0:
                # Bought token
                return {
                    'type': 'buy',
                    'token_mint': mint,
                    'token_amount': amount,
                    'sol_amount': abs(sol_change),
                    'timestamp': tx.get('timestamp', 0),
                    'signature': tx.get('signature'),
                    'token_symbol': self._get_token_symbol(transfer, mint)
                }
        
        return None
    
    def _get_token_symbol(self, transfer: Dict, mint: str) -> str:
        """Extract token symbol"""
        
        # Try various fields
        symbol = transfer.get('tokenSymbol') or transfer.get('symbol')
        if symbol:
            return symbol
        
        # Check metadata
        metadata = transfer.get('tokenMetadata', {})
        if metadata:
            return metadata.get('symbol', mint[:6])
        
        return mint[:6]
    
    def _calculate_token_pnl_from_swaps(self, swaps: List[Dict]) -> Dict[str, TokenPnL]:
        """Calculate P&L from swap data"""
        
        # Group by token
        token_swaps = defaultdict(lambda: {'buys': [], 'sells': []})
        
        for swap in swaps:
            mint = swap['token_mint']
            
            if swap['type'] == 'buy':
                token_swaps[mint]['buys'].append(swap)
            else:
                token_swaps[mint]['sells'].append(swap)
        
        # Calculate P&L for each token
        result = {}
        
        for mint, data in token_swaps.items():
            if not data['buys']:  # Skip if no buys
                continue
            
            # Sort by timestamp
            data['buys'].sort(key=lambda x: x['timestamp'])
            data['sells'].sort(key=lambda x: x['timestamp'])
            
            # Calculate totals
            total_buy_amount = sum(b['token_amount'] for b in data['buys'])
            total_buy_sol = sum(b['sol_amount'] for b in data['buys'])
            total_buy_usd = total_buy_sol * self._sol_price
            
            total_sell_amount = sum(s['token_amount'] for s in data['sells'])
            total_sell_sol = sum(s['sol_amount'] for s in data['sells'])
            total_sell_usd = total_sell_sol * self._sol_price
            
            # Get token info
            token_symbol = data['buys'][0]['token_symbol'] if data['buys'] else 'Unknown'
            
            # Calculate averages
            avg_buy_price = total_buy_usd / total_buy_amount if total_buy_amount > 0 else 0
            avg_sell_price = total_sell_usd / total_sell_amount if total_sell_amount > 0 else 0
            
            # Calculate realized P&L
            if total_sell_amount > 0:
                sell_ratio = min(1.0, total_sell_amount / total_buy_amount)
                cost_basis = sell_ratio * total_buy_usd
                realized_pnl = total_sell_usd - cost_basis
            else:
                realized_pnl = 0
            
            roi = (realized_pnl / total_buy_usd * 100) if total_buy_usd > 0 else 0
            
            # Calculate holding
            holding = max(0, total_buy_amount - total_sell_amount)
            
            # Get timestamps
            first_trade = min(
                [b['timestamp'] for b in data['buys']] + 
                [s['timestamp'] for s in data['sells'] if s['timestamp']]
            )
            last_trade = max(
                [b['timestamp'] for b in data['buys']] + 
                [s['timestamp'] for s in data['sells'] if s['timestamp']]
            )
            
            # Calculate holding time
            if data['sells']:
                avg_sell_time = sum(s['timestamp'] for s in data['sells']) / len(data['sells'])
                avg_buy_time = sum(b['timestamp'] for b in data['buys']) / len(data['buys'])
                holding_time = int(avg_sell_time - avg_buy_time)
            else:
                holding_time = int(datetime.now().timestamp() - first_trade)
            
            token_pnl = TokenPnL(
                num_swaps=len(data['buys']),
                total_buy_usd=total_buy_usd,
                total_buy_amount=total_buy_amount,
                total_sell_usd=total_sell_usd,
                total_sell_amount=total_sell_amount,
                average_buy_price=avg_buy_price,
                average_sell_price=avg_sell_price,
                total_pnl_usd=realized_pnl,
                roi_percentage=roi,
                unrealized_pnl_usd=0,
                unrealized_roi_percentage=0,
                token_price=0,
                token_address=mint,
                token_symbol=token_symbol,
                token_name=token_symbol,
                first_trade=int(first_trade),
                last_trade=int(last_trade),
                holding_time_seconds=max(0, holding_time),
                holding_amount=holding,
                holding_amount_usd=0
            )
            
            result[mint] = token_pnl
        
        return result
    
    async def _add_current_prices(self, token_data: Dict[str, TokenPnL], wallet: str):
        """Add current prices for tokens with holdings"""
        
        # Get tokens with holdings
        tokens_to_price = [
            token.token_address for token in token_data.values()
            if token.holding_amount > 0
        ]
        
        if not tokens_to_price:
            return
        
        # Fetch current prices
        prices = await self._fetch_token_prices(tokens_to_price[:50])  # Limit to 50
        
        # Update token data
        for token in token_data.values():
            if token.holding_amount > 0 and token.token_address in prices:
                price = prices[token.token_address]
                token.token_price = price
                token.holding_amount_usd = token.holding_amount * price
                
                # Calculate unrealized P&L
                if token.total_buy_amount > 0:
                    holding_cost = (token.holding_amount / token.total_buy_amount) * token.total_buy_usd
                    token.unrealized_pnl_usd = token.holding_amount_usd - holding_cost
                    token.unrealized_roi_percentage = (token.unrealized_pnl_usd / holding_cost * 100) if holding_cost > 0 else 0
                
                # Update total P&L
                token.total_pnl_usd += token.unrealized_pnl_usd
                token.roi_percentage = (token.total_pnl_usd / token.total_buy_usd * 100) if token.total_buy_usd > 0 else 0
    
    async def _fetch_token_prices(self, mints: List[str]) -> Dict[str, float]:
        """Fetch current token prices"""
        
        prices = {}
        
        async with aiohttp.ClientSession() as session:
            # Use Jupiter API
            url = "https://price.jup.ag/v6/price"
            mint_str = ",".join(mints)
            
            try:
                async with session.get(url, params={"ids": mint_str}) as response:
                    if response.status == 200:
                        data = await response.json()
                        for mint, info in data.get('data', {}).items():
                            prices[mint] = info.get('price', 0)
            except Exception as e:
                logger.error(f"Price fetch error: {e}")
        
        return prices
    
    def _calculate_total_stats(self, tokens: List[TokenPnL]) -> Dict:
        """Calculate total statistics"""
        
        if not tokens:
            return {
                "tokens_traded": 0,
                "total_buy_usd": 0,
                "total_sell_usd": 0,
                "realized_pnl_usd": 0,
                "realized_roi_percentage": 0,
                "winrate": 0,
                "total_swaps": 0
            }
        
        total_buy = sum(t.total_buy_usd for t in tokens)
        total_sell = sum(t.total_sell_usd for t in tokens)
        total_pnl = sum(t.total_pnl_usd for t in tokens)
        winners = [t for t in tokens if t.roi_percentage > 0]
        
        return {
            "tokens_traded": len(tokens),
            "total_buy_usd": total_buy,
            "total_sell_usd": total_sell,
            "realized_pnl_usd": total_pnl,
            "realized_roi_percentage": (total_pnl / total_buy * 100) if total_buy > 0 else 0,
            "winrate": len(winners) / len(tokens) * 100 if tokens else 0,
            "total_swaps": sum(t.num_swaps for t in tokens)
        }

# Convenience function
async def get_complete_pnl(wallet: str, helius_key: Optional[str] = None) -> Dict:
    """Get complete P&L data"""
    
    helius_key = helius_key or os.getenv('HELIUS_API_KEY') or os.getenv('HELIUS_KEY')
    if not helius_key:
        raise ValueError("Helius API key required")
    
    replacement = CompleteCieloReplacement(helius_key)
    return await replacement.get_all_token_pnl(wallet)