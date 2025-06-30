#!/usr/bin/env python3
"""
Fixed Cielo replacement with proper rate limiting and error handling
"""

import os
import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional
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

class RateLimitedCieloReplacement:
    """Cielo replacement with proper rate limiting"""
    
    def __init__(self, helius_api_key: str):
        self.helius_key = helius_api_key
        self._sol_price = 150.0
        self._last_request_time = 0
        self._min_request_interval = 0.5  # 500ms between requests
        
    async def get_all_token_pnl(self, wallet: str) -> Dict:
        """Get P&L data for ALL tokens with rate limiting"""
        
        logger.info(f"Fetching P&L data for wallet {wallet}")
        
        # Fetch all transactions with rate limiting
        transactions = await self._fetch_all_transactions_safe(wallet)
        
        if not transactions:
            logger.warning(f"No transactions found for {wallet}")
            return self._empty_result()
        
        logger.info(f"Found {len(transactions)} transactions")
        
        # Parse swaps
        token_data = await self._calculate_token_pnl(transactions, wallet)
        
        if not token_data:
            logger.warning(f"No token data calculated for {wallet}")
            return self._empty_result()
        
        logger.info(f"Calculated P&L for {len(token_data)} tokens")
        
        # Sort by ROI
        sorted_tokens = sorted(token_data.values(), key=lambda x: x.roi_percentage, reverse=True)
        
        # Calculate total stats
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
                "data_complete": True
            }
        }
    
    async def _rate_limit(self):
        """Enforce rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            await asyncio.sleep(sleep_time)
        
        self._last_request_time = time.time()
    
    async def _fetch_all_transactions_safe(self, wallet: str) -> List[Dict]:
        """Fetch transactions with proper rate limiting and error handling"""
        
        all_transactions = []
        url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
        
        async with aiohttp.ClientSession() as session:
            before_signature = None
            consecutive_errors = 0
            max_consecutive_errors = 3
            
            while consecutive_errors < max_consecutive_errors:
                await self._rate_limit()
                
                params = {
                    "api-key": self.helius_key,
                    "limit": 100,
                    "type": "SWAP"
                }
                
                if before_signature:
                    params["before"] = before_signature
                
                try:
                    async with session.get(
                        url, 
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        
                        if response.status == 429:
                            # Rate limited - wait exponentially
                            wait_time = min(60, 2 ** consecutive_errors)
                            logger.warning(f"Rate limited, waiting {wait_time}s")
                            await asyncio.sleep(wait_time)
                            consecutive_errors += 1
                            continue
                        
                        if response.status != 200:
                            logger.error(f"Helius API error: {response.status}")
                            consecutive_errors += 1
                            continue
                        
                        data = await response.json()
                        
                        if not data:
                            # No more data
                            break
                        
                        consecutive_errors = 0  # Reset on success
                        all_transactions.extend(data)
                        
                        if len(data) < 100:
                            # Last page
                            break
                        
                        before_signature = data[-1].get("signature")
                        
                except asyncio.TimeoutError:
                    logger.error("Request timeout")
                    consecutive_errors += 1
                except Exception as e:
                    logger.error(f"Error fetching transactions: {e}")
                    consecutive_errors += 1
        
        return all_transactions
    
    async def _calculate_token_pnl(self, transactions: List[Dict], wallet: str) -> Dict[str, TokenPnL]:
        """Calculate P&L for each token from transactions"""
        
        token_data = defaultdict(lambda: {
            'buys': [],
            'sells': [],
            'first_trade': float('inf'),
            'last_trade': 0,
            'token_info': {}
        })
        
        for tx in transactions:
            swap_data = self._parse_swap_simple(tx, wallet)
            if not swap_data:
                continue
            
            token_mint = swap_data['token_mint']
            timestamp = tx.get('timestamp', 0)
            
            # Update times
            token_data[token_mint]['first_trade'] = min(
                token_data[token_mint]['first_trade'], 
                timestamp
            )
            token_data[token_mint]['last_trade'] = max(
                token_data[token_mint]['last_trade'], 
                timestamp
            )
            
            # Store token info
            if not token_data[token_mint]['token_info']:
                token_data[token_mint]['token_info'] = {
                    'symbol': swap_data.get('token_symbol', 'Unknown'),
                    'name': swap_data.get('token_name', 'Unknown Token'),
                    'address': token_mint
                }
            
            # Categorize trade
            if swap_data['type'] == 'buy':
                token_data[token_mint]['buys'].append({
                    'amount': swap_data['token_amount'],
                    'sol_amount': swap_data['sol_amount'],
                    'usd_value': swap_data['sol_amount'] * self._sol_price,
                    'timestamp': timestamp
                })
            else:
                token_data[token_mint]['sells'].append({
                    'amount': swap_data['token_amount'],
                    'sol_amount': swap_data['sol_amount'],
                    'usd_value': swap_data['sol_amount'] * self._sol_price,
                    'timestamp': timestamp
                })
        
        # Convert to TokenPnL
        result = {}
        for token_mint, data in token_data.items():
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
            
            # Calculate P&L
            if total_sell_amount > 0 and total_buy_amount > 0:
                sold_ratio = min(1.0, total_sell_amount / total_buy_amount)
                cost_basis = sold_ratio * total_buy_usd
                realized_pnl = total_sell_usd - cost_basis
            else:
                realized_pnl = 0
            
            roi_percentage = (realized_pnl / total_buy_usd * 100) if total_buy_usd > 0 else 0
            
            # Calculate holding
            holding_amount = max(0, total_buy_amount - total_sell_amount)
            
            # Calculate holding time
            if data['first_trade'] != float('inf'):
                if data['sells']:
                    # Average time between buys and sells
                    avg_sell_time = sum(s['timestamp'] for s in data['sells']) / len(data['sells'])
                    avg_buy_time = sum(b['timestamp'] for b in data['buys']) / len(data['buys'])
                    holding_time = int(avg_sell_time - avg_buy_time)
                else:
                    # Still holding
                    holding_time = int(datetime.now().timestamp()) - int(data['first_trade'])
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
                roi_percentage=roi_percentage,
                unrealized_pnl_usd=0,
                unrealized_roi_percentage=0,
                token_price=0,
                token_address=token_mint,
                token_symbol=data['token_info'].get('symbol', 'Unknown'),
                token_name=data['token_info'].get('name', 'Unknown Token'),
                first_trade=int(data['first_trade']) if data['first_trade'] != float('inf') else 0,
                last_trade=int(data['last_trade']),
                holding_time_seconds=max(0, holding_time),
                holding_amount=holding_amount,
                holding_amount_usd=0
            )
            
            result[token_mint] = token_pnl
        
        return result
    
    def _parse_swap_simple(self, tx: Dict, wallet: str) -> Optional[Dict]:
        """Simple swap parser focusing on essential data"""
        
        # Check for SOL transfers
        sol_change = 0
        native_transfers = tx.get('nativeTransfers', [])
        
        for transfer in native_transfers:
            if transfer.get('fromUserAccount') == wallet:
                sol_change -= abs(transfer.get('amount', 0)) / 1e9
            elif transfer.get('toUserAccount') == wallet:
                sol_change += abs(transfer.get('amount', 0)) / 1e9
        
        if abs(sol_change) < 0.001:  # No significant SOL movement
            return None
        
        # Find token transfers
        token_transfers = tx.get('tokenTransfers', [])
        
        for transfer in token_transfers:
            mint = transfer.get('mint')
            if not mint:
                continue
            
            # Skip wrapped SOL
            if mint == 'So11111111111111111111111111111111111111112':
                continue
            
            amount = float(transfer.get('tokenAmount', 0))
            if amount <= 0:
                continue
            
            # Determine trade direction
            if transfer.get('fromUserAccount') == wallet and sol_change > 0:
                # Sold token for SOL
                return {
                    'type': 'sell',
                    'token_mint': mint,
                    'token_amount': amount,
                    'token_symbol': self._extract_symbol(transfer),
                    'token_name': mint[:8],  # Use short address as name
                    'sol_amount': abs(sol_change)
                }
            elif transfer.get('toUserAccount') == wallet and sol_change < 0:
                # Bought token with SOL
                return {
                    'type': 'buy',
                    'token_mint': mint,
                    'token_amount': amount,
                    'token_symbol': self._extract_symbol(transfer),
                    'token_name': mint[:8],
                    'sol_amount': abs(sol_change)
                }
        
        return None
    
    def _extract_symbol(self, transfer: Dict) -> str:
        """Extract token symbol from transfer data"""
        # Try different fields
        symbol = transfer.get('tokenSymbol')
        if symbol:
            return symbol
        
        # Try token standard
        standard = transfer.get('tokenStandard')
        if standard and standard != 'Fungible':
            return standard
        
        # Use mint address prefix
        mint = transfer.get('mint', '')
        return mint[:6] if mint else 'Unknown'
    
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
    
    def _empty_result(self) -> Dict:
        """Return empty result structure"""
        return {
            "data": {
                "items": [],
                "total": 0
            },
            "total_stats": self._calculate_total_stats([]),
            "metadata": {
                "timestamp": int(datetime.now().timestamp()),
                "sol_price": self._sol_price,
                "data_complete": True
            }
        }

# Convenience function
async def get_complete_pnl_safe(wallet: str, helius_key: Optional[str] = None) -> Dict:
    """Get complete P&L data with rate limiting"""
    
    helius_key = helius_key or os.getenv('HELIUS_API_KEY') or os.getenv('HELIUS_KEY')
    if not helius_key:
        raise ValueError("Helius API key required")
    
    replacement = RateLimitedCieloReplacement(helius_key)
    return await replacement.get_all_token_pnl(wallet)