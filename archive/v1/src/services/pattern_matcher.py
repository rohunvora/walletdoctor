#!/usr/bin/env python3
"""
Pattern Matcher Service - Combines Helius and Cielo data for intelligent trade coaching
"""

import os
import asyncio
import aiohttp
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import json
from dataclasses import dataclass
from collections import defaultdict
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TradePattern:
    """Represents a historical trade pattern for comparison"""
    token_address: str
    token_symbol: str
    token_name: str
    market_cap_usd: float
    sol_amount: float
    usd_amount: float
    trade_type: str  # 'buy' or 'sell'
    timestamp: int
    pnl_usd: float
    roi_percentage: float
    outcome_emoji: str  # 🟢 for profit, 🔴 for loss

class PatternMatcher:
    """Hybrid pattern matching using Helius for trade data and Cielo for P&L"""
    
    def __init__(self, helius_key: str, cielo_key: str):
        self.helius_key = helius_key
        self.cielo_key = cielo_key
        self._cache = {}
        
    async def find_similar_trades(
        self, 
        wallet: str,
        current_market_cap: float,
        current_sol_amount: float,
        mcap_tolerance: float = 0.5,  # ±50% market cap
        sol_tolerance: float = 0.3,    # ±30% SOL amount
        limit: int = 5
    ) -> Dict:
        """
        Find historical trades with similar patterns and return coaching insights
        """
        try:
            # Step 1: Get P&L data from Cielo (cached)
            cielo_data = await self._get_cielo_pnl_data(wallet)
            
            # Step 2: Get detailed trade history from Helius
            trades_with_mcap = await self._get_helius_trades_with_mcap(wallet)
            
            # Step 3: Merge data sources
            enriched_trades = self._merge_data_sources(trades_with_mcap, cielo_data)
            
            # Step 4: Find similar patterns
            similar_trades = self._find_pattern_matches(
                enriched_trades,
                current_market_cap,
                current_sol_amount,
                mcap_tolerance,
                sol_tolerance
            )
            
            # Step 5: Format coaching response
            coaching_data = self._format_coaching_response(
                similar_trades[:limit],
                current_market_cap,
                current_sol_amount
            )
            
            return coaching_data
            
        except Exception as e:
            logger.error(f"Error in pattern matching: {str(e)}")
            return self._error_response(str(e))
    
    async def _get_cielo_pnl_data(self, wallet: str) -> Dict[str, Dict]:
        """Get P&L data from Cielo API with caching"""
        cache_key = f"cielo_pnl_{wallet}"
        
        # Check cache (1 hour expiry)
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if datetime.now().timestamp() - timestamp < 3600:
                logger.info("Using cached Cielo data")
                return cached_data
        
        async with aiohttp.ClientSession() as session:
            url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/tokens"
            headers = {"x-api-key": self.cielo_key}
            
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"Cielo API error: {response.status}")
                
                data = await response.json()
                
                # Process into lookup dict by token address
                pnl_by_token = {}
                for item in data['data']['items']:
                    pnl_by_token[item['token_address']] = {
                        'symbol': item['token_symbol'],
                        'name': item['token_name'],
                        'pnl_usd': item['total_pnl_usd'],
                        'roi_percentage': item['roi_percentage'],
                        'num_swaps': item['num_swaps'],
                        'avg_buy_usd': item['total_buy_usd'] / item['num_swaps'] if item['num_swaps'] > 0 else 0
                    }
                
                # Cache the result
                self._cache[cache_key] = (pnl_by_token, datetime.now().timestamp())
                logger.info(f"Cached P&L data for {len(pnl_by_token)} tokens")
                
                return pnl_by_token
    
    async def _get_helius_trades_with_mcap(self, wallet: str) -> List[Dict]:
        """Get trade history with market cap data from Helius"""
        trades = []
        
        async with aiohttp.ClientSession() as session:
            # Get recent transactions
            url = "https://api.helius.xyz/v0/addresses/{}/transactions"
            params = {
                "api-key": self.helius_key,
                "limit": 100,
                "type": "SWAP"
            }
            
            async with session.get(url.format(wallet), params=params) as response:
                if response.status != 200:
                    raise Exception(f"Helius API error: {response.status}")
                
                transactions = await response.json()
                
                # Process each swap transaction
                for tx in transactions:
                    if tx.get('type') != 'SWAP':
                        continue
                    
                    # Extract trade details
                    for swap in tx.get('tokenTransfers', []):
                        if swap['fromUserAccount'] == wallet or swap['toUserAccount'] == wallet:
                            # This is a trade involving our wallet
                            trade = {
                                'signature': tx['signature'],
                                'timestamp': tx['timestamp'],
                                'token_address': swap['mint'],
                                'is_buy': swap['toUserAccount'] == wallet,
                                'token_amount': swap['tokenAmount'],
                                'decimals': swap.get('decimals', 0)
                            }
                            
                            # Get SOL amount from the paired transfer
                            sol_amount = self._extract_sol_amount(tx, wallet)
                            trade['sol_amount'] = sol_amount
                            
                            # Get market cap (would need additional API call or estimation)
                            trade['market_cap_usd'] = await self._estimate_market_cap(
                                swap['mint'], 
                                tx['timestamp']
                            )
                            
                            trades.append(trade)
                
                logger.info(f"Found {len(trades)} trades from Helius")
                return trades
    
    def _extract_sol_amount(self, tx: Dict, wallet: str) -> float:
        """Extract SOL amount from transaction"""
        # Look for SOL transfers in the same transaction
        for transfer in tx.get('nativeTransfers', []):
            if transfer['fromUserAccount'] == wallet or transfer['toUserAccount'] == wallet:
                return abs(transfer['amount']) / 1e9  # Convert lamports to SOL
        
        # Fallback: estimate from instruction data
        return 0.0
    
    async def _estimate_market_cap(self, token_address: str, timestamp: int) -> float:
        """Estimate market cap at time of trade"""
        # In production, this would:
        # 1. Check historical price data
        # 2. Get token supply
        # 3. Calculate mcap = price * supply
        
        # For now, return a placeholder
        # You could integrate with Birdeye or other price APIs here
        return 1_000_000  # $1M placeholder
    
    def _merge_data_sources(self, helius_trades: List[Dict], cielo_pnl: Dict[str, Dict]) -> List[TradePattern]:
        """Merge Helius and Cielo data into TradePattern objects"""
        patterns = []
        
        for trade in helius_trades:
            token_address = trade['token_address']
            
            if token_address in cielo_pnl:
                pnl_data = cielo_pnl[token_address]
                
                pattern = TradePattern(
                    token_address=token_address,
                    token_symbol=pnl_data['symbol'],
                    token_name=pnl_data['name'],
                    market_cap_usd=trade['market_cap_usd'],
                    sol_amount=trade['sol_amount'],
                    usd_amount=trade['sol_amount'] * 150,  # Estimate USD value
                    trade_type='buy' if trade['is_buy'] else 'sell',
                    timestamp=trade['timestamp'],
                    pnl_usd=pnl_data['pnl_usd'],
                    roi_percentage=pnl_data['roi_percentage'],
                    outcome_emoji='🟢' if pnl_data['roi_percentage'] > 0 else '🔴'
                )
                
                patterns.append(pattern)
        
        logger.info(f"Created {len(patterns)} trade patterns")
        return patterns
    
    def _find_pattern_matches(
        self,
        all_patterns: List[TradePattern],
        target_mcap: float,
        target_sol: float,
        mcap_tolerance: float,
        sol_tolerance: float
    ) -> List[TradePattern]:
        """Find trades matching the target pattern"""
        matches = []
        
        mcap_low = target_mcap * (1 - mcap_tolerance)
        mcap_high = target_mcap * (1 + mcap_tolerance)
        sol_low = target_sol * (1 - sol_tolerance)
        sol_high = target_sol * (1 + sol_tolerance)
        
        for pattern in all_patterns:
            if pattern.trade_type != 'buy':
                continue
                
            if (mcap_low <= pattern.market_cap_usd <= mcap_high and
                sol_low <= pattern.sol_amount <= sol_high):
                matches.append(pattern)
        
        # Sort by timestamp (most recent first)
        matches.sort(key=lambda x: x.timestamp, reverse=True)
        
        logger.info(f"Found {len(matches)} matching patterns")
        return matches
    
    def _format_coaching_response(
        self, 
        similar_trades: List[TradePattern],
        current_mcap: float,
        current_sol: float
    ) -> Dict:
        """Format the coaching response for the user"""
        
        if not similar_trades:
            return {
                'success': True,
                'message': f"No similar trades found (looking for ~${current_mcap/1e6:.1f}M mcap with ~{current_sol:.1f} SOL)",
                'patterns': [],
                'coaching_prompt': "This looks like a new pattern for you. What's your thesis?"
            }
        
        # Calculate statistics
        total_pnl = sum(t.pnl_usd for t in similar_trades)
        avg_roi = sum(t.roi_percentage for t in similar_trades) / len(similar_trades)
        win_rate = sum(1 for t in similar_trades if t.roi_percentage > 0) / len(similar_trades) * 100
        
        # Format pattern descriptions
        patterns = []
        for trade in similar_trades:
            pattern_text = (
                f"{trade.outcome_emoji} {trade.token_symbol}: "
                f"{trade.sol_amount:.1f} SOL → "
                f"{'+' if trade.roi_percentage > 0 else ''}{trade.roi_percentage:.1f}% "
                f"({'+' if trade.pnl_usd > 0 else ''}{trade.pnl_usd:.0f} USD)"
            )
            patterns.append(pattern_text)
        
        # Create coaching message
        mcap_range = f"{current_mcap/1e6*0.5:.1f}-{current_mcap/1e6*1.5:.1f}M"
        sol_range = f"{current_sol*0.7:.1f}-{current_sol*1.3:.1f}"
        
        coaching_message = (
            f"Last {len(similar_trades)} times you bought {mcap_range} mcap coins with {sol_range} SOL:\n"
            f"{chr(10).join(patterns)}\n\n"
            f"Stats: {win_rate:.0f}% win rate, {avg_roi:.1f}% avg ROI\n"
        )
        
        # Generate coaching prompt based on performance
        if win_rate < 30:
            coaching_prompt = "This pattern hasn't worked well for you. What's different this time?"
        elif win_rate > 70:
            coaching_prompt = "This pattern has worked well! Sticking to what works?"
        else:
            coaching_prompt = "Mixed results with this pattern. What's your edge here?"
        
        return {
            'success': True,
            'message': coaching_message,
            'patterns': patterns,
            'statistics': {
                'pattern_count': len(similar_trades),
                'win_rate': win_rate,
                'avg_roi': avg_roi,
                'total_pnl': total_pnl
            },
            'coaching_prompt': coaching_prompt,
            'metadata': {
                'mcap_range': mcap_range,
                'sol_range': sol_range,
                'pattern': f"~${current_mcap/1e6:.1f}M mcap with ~{current_sol:.1f} SOL"
            }
        }
    
    def _error_response(self, error: str) -> Dict:
        """Format error response"""
        return {
            'success': False,
            'message': f"Unable to find patterns: {error}",
            'patterns': [],
            'coaching_prompt': "Try again or adjust your search parameters."
        }


# Convenience function for direct use
async def get_trade_patterns(
    wallet: str,
    current_market_cap: float,
    current_sol_amount: float,
    helius_key: Optional[str] = None,
    cielo_key: Optional[str] = None
) -> Dict:
    """
    Get pattern-based coaching for a potential trade
    
    Args:
        wallet: Wallet address
        current_market_cap: Market cap of token being considered
        current_sol_amount: SOL amount being considered
        helius_key: Helius API key (or from env)
        cielo_key: Cielo API key (or from env)
    
    Returns:
        Coaching data with similar historical patterns
    """
    helius_key = helius_key or os.getenv('HELIUS_KEY')
    cielo_key = cielo_key or os.getenv('CIELO_KEY')
    
    if not helius_key or not cielo_key:
        return {
            'success': False,
            'message': "API keys not configured",
            'patterns': [],
            'coaching_prompt': "Please configure HELIUS_KEY and CIELO_KEY"
        }
    
    matcher = PatternMatcher(helius_key, cielo_key)
    return await matcher.find_similar_trades(
        wallet,
        current_market_cap,
        current_sol_amount
    )