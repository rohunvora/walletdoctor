#!/usr/bin/env python3
"""
Complete replacement for Cielo's token P&L API using Helius and other sources
Recreates the exact data structure with ALL tokens, not just top 50
"""

import os
import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, asdict
import json

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

class CieloReplacement:
    """Complete replacement for Cielo's P&L API with full data access"""
    
    def __init__(self, helius_api_key: str):
        self.helius_key = helius_api_key
        self.jupiter_price_api = "https://price.jup.ag/v6/price"
        self.birdeye_api = "https://public-api.birdeye.so"
        self._price_cache = {}
        self._token_info_cache = {}
        
    async def get_all_token_pnl(self, wallet: str) -> Dict:
        """Get P&L data for ALL tokens traded, not just top 50"""
        
        logger.info(f"Fetching complete P&L data for wallet {wallet}")
        
        # Step 1: Get all transactions from Helius
        transactions = await self._fetch_all_transactions(wallet)
        logger.info(f"Found {len(transactions)} total transactions")
        
        # Step 2: Parse swaps and calculate P&L
        token_data = await self._calculate_token_pnl(transactions, wallet)
        logger.info(f"Calculated P&L for {len(token_data)} tokens")
        
        # Step 3: Get current prices and calculate unrealized P&L
        await self._add_current_prices(token_data, wallet)
        
        # Step 4: Sort by ROI (like Cielo does with their top 50)
        sorted_tokens = sorted(token_data.values(), key=lambda x: x.roi_percentage, reverse=True)
        
        # Step 5: Calculate total stats
        total_stats = self._calculate_total_stats(sorted_tokens)
        
        # Return in Cielo's exact format
        return {
            "data": {
                "items": [asdict(token) for token in sorted_tokens],
                "total": len(sorted_tokens)
            },
            "total_stats": total_stats
        }
    
    async def _fetch_all_transactions(self, wallet: str) -> List[Dict]:
        """Fetch ALL transactions using Helius with proper pagination"""
        
        all_transactions = []
        url = "https://api.helius.xyz/v0/addresses/{}/transactions"
        
        async with aiohttp.ClientSession() as session:
            before_signature = None
            consecutive_empty = 0
            
            while consecutive_empty < 3:
                params = {
                    "api-key": self.helius_key,
                    "limit": 100,
                    "commitment": "confirmed",
                    "type": "SWAP"  # Focus on swaps
                }
                
                if before_signature:
                    params["before"] = before_signature
                
                try:
                    async with session.get(
                        url.format(wallet), 
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        if response.status != 200:
                            logger.error(f"Helius API error: {response.status}")
                            break
                        
                        data = await response.json()
                        
                        if not data:
                            consecutive_empty += 1
                            continue
                        
                        consecutive_empty = 0
                        all_transactions.extend(data)
                        
                        if len(data) < 100:
                            break
                        
                        before_signature = data[-1].get("signature")
                        
                except Exception as e:
                    logger.error(f"Error fetching transactions: {e}")
                    break
                
                await asyncio.sleep(0.1)  # Rate limiting
        
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
        
        # Parse each transaction
        for tx in transactions:
            if tx.get('type') != 'SWAP':
                continue
                
            # Extract swap details
            swap_data = self._parse_swap_transaction(tx, wallet)
            if not swap_data:
                continue
            
            token_mint = swap_data['token_mint']
            timestamp = tx.get('timestamp', 0)
            
            # Update first/last trade times
            token_data[token_mint]['first_trade'] = min(
                token_data[token_mint]['first_trade'], 
                timestamp
            )
            token_data[token_mint]['last_trade'] = max(
                token_data[token_mint]['last_trade'], 
                timestamp
            )
            
            # Store token metadata
            if not token_data[token_mint]['token_info']:
                token_data[token_mint]['token_info'] = {
                    'symbol': swap_data.get('token_symbol', 'Unknown'),
                    'name': swap_data.get('token_name', 'Unknown Token'),
                    'address': token_mint
                }
            
            # Categorize as buy or sell
            if swap_data['type'] == 'buy':
                token_data[token_mint]['buys'].append({
                    'amount': swap_data['token_amount'],
                    'sol_amount': swap_data['sol_amount'],
                    'usd_value': swap_data['sol_amount'] * 150,  # Approximate SOL price
                    'timestamp': timestamp
                })
            else:
                token_data[token_mint]['sells'].append({
                    'amount': swap_data['token_amount'],
                    'sol_amount': swap_data['sol_amount'],
                    'usd_value': swap_data['sol_amount'] * 150,
                    'timestamp': timestamp
                })
        
        # Convert to TokenPnL objects
        result = {}
        for token_mint, data in token_data.items():
            if not data['buys']:  # Skip if no buys
                continue
                
            # Calculate aggregated values
            total_buy_amount = sum(b['amount'] for b in data['buys'])
            total_buy_usd = sum(b['usd_value'] for b in data['buys'])
            total_sell_amount = sum(s['amount'] for s in data['sells'])
            total_sell_usd = sum(s['usd_value'] for s in data['sells'])
            
            # Calculate averages
            avg_buy_price = total_buy_usd / total_buy_amount if total_buy_amount > 0 else 0
            avg_sell_price = total_sell_usd / total_sell_amount if total_sell_amount > 0 else 0
            
            # Calculate P&L
            realized_pnl = total_sell_usd - (total_sell_amount / total_buy_amount * total_buy_usd) if total_buy_amount > 0 else 0
            roi_percentage = (realized_pnl / total_buy_usd * 100) if total_buy_usd > 0 else 0
            
            # Calculate holding
            holding_amount = total_buy_amount - total_sell_amount
            
            # Calculate holding time
            if data['sells']:
                # Time from first buy to last sell
                first_buy_time = min(b['timestamp'] for b in data['buys'])
                last_sell_time = max(s['timestamp'] for s in data['sells'])
                holding_time = last_sell_time - first_buy_time
            else:
                # Still holding - time from first buy to now
                first_buy_time = min(b['timestamp'] for b in data['buys'])
                holding_time = int(datetime.now().timestamp()) - first_buy_time
            
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
                unrealized_pnl_usd=0,  # Will be calculated with current prices
                unrealized_roi_percentage=0,
                token_price=0,  # Will be fetched
                token_address=token_mint,
                token_symbol=data['token_info'].get('symbol', 'Unknown'),
                token_name=data['token_info'].get('name', 'Unknown Token'),
                first_trade=int(data['first_trade']),
                last_trade=int(data['last_trade']),
                holding_time_seconds=holding_time,
                holding_amount=holding_amount,
                holding_amount_usd=0  # Will be calculated
            )
            
            result[token_mint] = token_pnl
        
        return result
    
    def _parse_swap_transaction(self, tx: Dict, wallet: str) -> Optional[Dict]:
        """Parse a swap transaction to extract details"""
        
        # This is simplified - in production you'd need to handle different DEX formats
        # Check for token transfers in and out
        token_in = None
        token_out = None
        sol_amount = 0
        
        # Parse native SOL transfers
        native_transfers = tx.get('nativeTransfers', [])
        for transfer in native_transfers:
            if transfer.get('fromUserAccount') == wallet:
                sol_amount += abs(transfer.get('amount', 0)) / 1e9
            elif transfer.get('toUserAccount') == wallet:
                sol_amount -= abs(transfer.get('amount', 0)) / 1e9
        
        # Parse token transfers
        token_transfers = tx.get('tokenTransfers', [])
        for transfer in token_transfers:
            if transfer.get('fromUserAccount') == wallet:
                token_out = {
                    'mint': transfer.get('mint'),
                    'amount': transfer.get('tokenAmount', 0),
                    'symbol': transfer.get('tokenStandard', 'Unknown')
                }
            elif transfer.get('toUserAccount') == wallet:
                token_in = {
                    'mint': transfer.get('mint'),
                    'amount': transfer.get('tokenAmount', 0),
                    'symbol': transfer.get('tokenStandard', 'Unknown')
                }
        
        # Determine if this is a buy or sell
        if sol_amount > 0 and token_in:
            # Sold SOL, got token = BUY
            return {
                'type': 'buy',
                'token_mint': token_in['mint'],
                'token_amount': token_in['amount'],
                'token_symbol': token_in['symbol'],
                'sol_amount': sol_amount
            }
        elif sol_amount < 0 and token_out:
            # Got SOL, sold token = SELL
            return {
                'type': 'sell',
                'token_mint': token_out['mint'],
                'token_amount': token_out['amount'],
                'token_symbol': token_out['symbol'],
                'sol_amount': abs(sol_amount)
            }
        
        return None
    
    async def _add_current_prices(self, token_data: Dict[str, TokenPnL], wallet: str):
        """Add current token prices and calculate unrealized P&L"""
        
        # Get token balances
        balances = await self._get_token_balances(wallet)
        
        # Get current prices for tokens with holdings
        mints_to_price = [
            token.token_address for token in token_data.values() 
            if token.holding_amount > 0
        ]
        
        if not mints_to_price:
            return
        
        prices = await self._fetch_token_prices(mints_to_price)
        
        # Update token data with current values
        for token in token_data.values():
            if token.holding_amount > 0 and token.token_address in prices:
                current_price = prices[token.token_address]
                token.token_price = current_price
                token.holding_amount_usd = token.holding_amount * current_price
                
                # Calculate unrealized P&L
                cost_basis = (token.holding_amount / token.total_buy_amount * token.total_buy_usd) if token.total_buy_amount > 0 else 0
                token.unrealized_pnl_usd = token.holding_amount_usd - cost_basis
                token.unrealized_roi_percentage = (token.unrealized_pnl_usd / cost_basis * 100) if cost_basis > 0 else 0
                
                # Update total P&L to include unrealized
                token.total_pnl_usd = token.total_pnl_usd + token.unrealized_pnl_usd
                token.roi_percentage = (token.total_pnl_usd / token.total_buy_usd * 100) if token.total_buy_usd > 0 else 0
    
    async def _get_token_balances(self, wallet: str) -> Dict[str, float]:
        """Get current token balances for wallet"""
        
        url = f"https://api.helius.xyz/v0/addresses/{wallet}/balances"
        
        async with aiohttp.ClientSession() as session:
            params = {"api-key": self.helius_key}
            
            try:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        return {}
                    
                    data = await response.json()
                    
                    balances = {}
                    for token in data.get('tokens', []):
                        mint = token.get('mint')
                        amount = token.get('amount', 0) / (10 ** token.get('decimals', 0))
                        balances[mint] = amount
                    
                    return balances
                    
            except Exception as e:
                logger.error(f"Error fetching balances: {e}")
                return {}
    
    async def _fetch_token_prices(self, mints: List[str]) -> Dict[str, float]:
        """Fetch current prices for multiple tokens"""
        
        prices = {}
        
        # Try Jupiter Price API first
        async with aiohttp.ClientSession() as session:
            # Jupiter accepts comma-separated mints
            mint_str = ",".join(mints[:50])  # Limit to 50 at a time
            
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
                logger.error(f"Error fetching prices: {e}")
        
        return prices
    
    def _calculate_total_stats(self, tokens: List[TokenPnL]) -> Dict:
        """Calculate total statistics matching Cielo's format"""
        
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
async def get_complete_token_pnl(wallet: str, helius_key: Optional[str] = None) -> Dict:
    """Get complete token P&L data for a wallet"""
    
    helius_key = helius_key or os.getenv('HELIUS_API_KEY')
    if not helius_key:
        raise ValueError("Helius API key required")
    
    replacement = CieloReplacement(helius_key)
    return await replacement.get_all_token_pnl(wallet)