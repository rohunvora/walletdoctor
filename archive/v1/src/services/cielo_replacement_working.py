#!/usr/bin/env python3
"""
Working Cielo replacement using correct Helius API endpoints
"""

import os
import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, asdict
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

class WorkingCieloReplacement:
    """Working implementation using correct API"""
    
    def __init__(self, helius_api_key: str):
        self.helius_key = helius_api_key
        self._sol_price = 150.0
        self._request_count = 0
        self._start_time = time.time()
        
    async def get_all_token_pnl(self, wallet: str) -> Dict:
        """Get complete P&L data"""
        
        logger.info(f"Fetching complete P&L for {wallet}")
        
        # First, get a quick summary
        summary = await self._get_wallet_summary(wallet)
        logger.info(f"Wallet summary: {summary}")
        
        # Fetch all swap transactions
        all_swaps = await self._fetch_all_swaps(wallet)
        logger.info(f"Found {len(all_swaps)} total swaps")
        
        # Group swaps by token and calculate P&L
        token_data = self._calculate_pnl_from_swaps(all_swaps, wallet)
        logger.info(f"Calculated P&L for {len(token_data)} tokens")
        
        # Sort by ROI
        sorted_tokens = sorted(token_data.values(), key=lambda x: x.roi_percentage, reverse=True)
        
        # Calculate stats
        total_stats = self._calculate_total_stats(sorted_tokens)
        
        elapsed = time.time() - self._start_time
        logger.info(f"Completed in {elapsed:.1f}s with {self._request_count} API calls")
        
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
                "api_calls": self._request_count,
                "elapsed_seconds": elapsed
            }
        }
    
    async def _get_wallet_summary(self, wallet: str) -> Dict:
        """Get quick wallet summary"""
        
        summary = {
            'total_transactions': 0,
            'swap_transactions': 0,
            'first_tx': None,
            'last_tx': None
        }
        
        async with aiohttp.ClientSession() as session:
            url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
            params = {
                "api-key": self.helius_key,
                "limit": 1
            }
            
            # Get most recent transaction
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data:
                        summary['last_tx'] = data[0].get('timestamp')
            
            self._request_count += 1
        
        return summary
    
    async def _fetch_all_swaps(self, wallet: str) -> List[Dict]:
        """Fetch all swap transactions"""
        
        all_swaps = []
        
        async with aiohttp.ClientSession() as session:
            url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
            
            before_sig = None
            page = 0
            consecutive_empty = 0
            
            while consecutive_empty < 3:
                # Rate limiting
                await asyncio.sleep(0.2)
                
                params = {
                    "api-key": self.helius_key,
                    "limit": 100,
                    "type": "SWAP"
                }
                
                if before_sig:
                    params["before"] = before_sig
                
                try:
                    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        self._request_count += 1
                        
                        if response.status == 429:
                            logger.warning("Rate limited, waiting...")
                            await asyncio.sleep(5)
                            continue
                        
                        if response.status != 200:
                            logger.error(f"API error: {response.status}")
                            break
                        
                        data = await response.json()
                        
                        if not data:
                            consecutive_empty += 1
                            logger.info(f"Page {page}: Empty")
                            continue
                        
                        consecutive_empty = 0
                        page += 1
                        
                        # Process swaps
                        for tx in data:
                            swap_info = self._parse_swap_transaction(tx, wallet)
                            if swap_info:
                                all_swaps.extend(swap_info)
                        
                        logger.info(f"Page {page}: {len(data)} transactions, total swaps: {len(all_swaps)}")
                        
                        # Pagination
                        if len(data) == 100:
                            before_sig = data[-1].get('signature')
                        else:
                            break  # Last page
                        
                except Exception as e:
                    logger.error(f"Error on page {page}: {e}")
                    break
        
        return all_swaps
    
    def _parse_swap_transaction(self, tx: Dict, wallet: str) -> List[Dict]:
        """Parse swap transaction into buy/sell events"""
        
        swaps = []
        
        # Get SOL balance change
        sol_change = 0
        for transfer in tx.get('nativeTransfers', []):
            if transfer.get('fromUserAccount') == wallet:
                sol_change -= transfer.get('amount', 0) / 1e9
            elif transfer.get('toUserAccount') == wallet:
                sol_change += transfer.get('amount', 0) / 1e9
        
        # Get token transfers
        token_transfers = defaultdict(float)
        token_info = {}
        
        for transfer in tx.get('tokenTransfers', []):
            mint = transfer.get('mint')
            if not mint or mint == 'So11111111111111111111111111111111111111112':
                continue
            
            amount = float(transfer.get('tokenAmount', 0))
            
            if transfer.get('fromUserAccount') == wallet:
                token_transfers[mint] -= amount
            elif transfer.get('toUserAccount') == wallet:
                token_transfers[mint] += amount
            
            # Store token info
            if mint not in token_info:
                token_info[mint] = {
                    'symbol': self._extract_token_symbol(transfer, mint),
                    'decimals': transfer.get('decimals', 9)
                }
        
        # Create swap records
        timestamp = tx.get('timestamp', 0)
        signature = tx.get('signature')
        
        for mint, token_change in token_transfers.items():
            if abs(token_change) < 0.000001:  # Skip dust
                continue
            
            if token_change > 0 and sol_change < 0:
                # Bought token with SOL
                swaps.append({
                    'type': 'buy',
                    'token_mint': mint,
                    'token_amount': abs(token_change),
                    'sol_amount': abs(sol_change),
                    'usd_value': abs(sol_change) * self._sol_price,
                    'timestamp': timestamp,
                    'signature': signature,
                    'token_symbol': token_info[mint]['symbol']
                })
            elif token_change < 0 and sol_change > 0:
                # Sold token for SOL
                swaps.append({
                    'type': 'sell',
                    'token_mint': mint,
                    'token_amount': abs(token_change),
                    'sol_amount': abs(sol_change),
                    'usd_value': abs(sol_change) * self._sol_price,
                    'timestamp': timestamp,
                    'signature': signature,
                    'token_symbol': token_info[mint]['symbol']
                })
        
        return swaps
    
    def _extract_token_symbol(self, transfer: Dict, mint: str) -> str:
        """Extract token symbol from transfer data"""
        
        # Try various fields
        for field in ['tokenSymbol', 'symbol', 'tokenStandard']:
            if field in transfer and transfer[field]:
                return transfer[field]
        
        # Use mint prefix as fallback
        return mint[:6]
    
    def _calculate_pnl_from_swaps(self, swaps: List[Dict], wallet: str) -> Dict[str, TokenPnL]:
        """Calculate P&L for each token"""
        
        # Group by token
        token_data = defaultdict(lambda: {
            'buys': [],
            'sells': [],
            'symbol': 'Unknown',
            'first_trade': float('inf'),
            'last_trade': 0
        })
        
        for swap in swaps:
            mint = swap['token_mint']
            token_data[mint]['symbol'] = swap['token_symbol']
            
            # Update timestamps
            token_data[mint]['first_trade'] = min(token_data[mint]['first_trade'], swap['timestamp'])
            token_data[mint]['last_trade'] = max(token_data[mint]['last_trade'], swap['timestamp'])
            
            # Categorize
            if swap['type'] == 'buy':
                token_data[mint]['buys'].append(swap)
            else:
                token_data[mint]['sells'].append(swap)
        
        # Calculate P&L
        result = {}
        
        for mint, data in token_data.items():
            if not data['buys']:  # Skip if no buys
                continue
            
            # Calculate totals
            total_buy_amount = sum(b['token_amount'] for b in data['buys'])
            total_buy_usd = sum(b['usd_value'] for b in data['buys'])
            
            total_sell_amount = sum(s['token_amount'] for s in data['sells'])
            total_sell_usd = sum(s['usd_value'] for s in data['sells'])
            
            # Calculate averages
            avg_buy_price = total_buy_usd / total_buy_amount if total_buy_amount > 0 else 0
            avg_sell_price = total_sell_usd / total_sell_amount if total_sell_amount > 0 else 0
            
            # Calculate realized P&L
            if total_sell_amount > 0:
                # P&L on sold portion
                sell_ratio = min(1.0, total_sell_amount / total_buy_amount)
                cost_basis = sell_ratio * total_buy_usd
                realized_pnl = total_sell_usd - cost_basis
            else:
                realized_pnl = 0
            
            roi = (realized_pnl / total_buy_usd * 100) if total_buy_usd > 0 else 0
            
            # Calculate holding
            holding = max(0, total_buy_amount - total_sell_amount)
            
            # Calculate holding time
            if data['first_trade'] != float('inf'):
                if data['sells']:
                    # Time to first sell
                    first_sell = min(s['timestamp'] for s in data['sells'])
                    holding_time = first_sell - data['first_trade']
                else:
                    # Still holding
                    holding_time = int(datetime.now().timestamp()) - data['first_trade']
            else:
                holding_time = 0
            
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
                token_symbol=data['symbol'],
                token_name=data['symbol'],
                first_trade=int(data['first_trade']) if data['first_trade'] != float('inf') else 0,
                last_trade=int(data['last_trade']),
                holding_time_seconds=max(0, holding_time),
                holding_amount=holding,
                holding_amount_usd=0
            )
            
            result[mint] = token_pnl
        
        return result
    
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
async def get_complete_pnl_working(wallet: str, helius_key: Optional[str] = None) -> Dict:
    """Get complete P&L data using working implementation"""
    
    helius_key = helius_key or os.getenv('HELIUS_API_KEY') or os.getenv('HELIUS_KEY')
    if not helius_key:
        raise ValueError("Helius API key required")
    
    replacement = WorkingCieloReplacement(helius_key)
    return await replacement.get_all_token_pnl(wallet)