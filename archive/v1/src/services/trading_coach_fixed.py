#!/usr/bin/env python3
"""
Trading Coach Service - FIXED version that handles Cielo's broken pagination
"""

import os
import aiohttp
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio

logger = logging.getLogger(__name__)

@dataclass
class TradingPattern:
    """Historical trading pattern"""
    symbol: str
    avg_buy_sol: float
    roi_percentage: float
    pnl_sol: float
    num_trades: int
    
    @property
    def emoji(self) -> str:
        return '🟢' if self.roi_percentage > 0 else '🔴'
    
    @property
    def formatted_line(self) -> str:
        roi_sign = '+' if self.roi_percentage > 0 else ''
        pnl_sign = '+' if self.pnl_sol > 0 else ''
        return f"{self.emoji} {self.symbol}: {self.avg_buy_sol:.1f} SOL → {roi_sign}{self.roi_percentage:.1f}% ({pnl_sign}{self.pnl_sol:.1f} SOL)"

class TradingCoach:
    """Provides pattern-based coaching using historical trade data"""
    
    def __init__(self, cielo_api_key: str):
        self.cielo_key = cielo_api_key
        self._cache = {}
        self._sol_price = 150.0  # Default SOL price, updated dynamically
        
    async def get_coaching_for_trade(
        self,
        wallet: str,
        sol_amount: float,
        token_symbol: Optional[str] = None
    ) -> Dict:
        """
        Get coaching advice for a potential trade
        """
        try:
            # Get historical data
            patterns = await self._get_similar_patterns(wallet, sol_amount)
            
            # Generate coaching response
            return self._generate_coaching(patterns, sol_amount, token_symbol)
            
        except Exception as e:
            logger.error(f"Error generating coaching: {str(e)}")
            return {
                'success': False,
                'message': "Unable to fetch trading history at the moment.",
                'coaching': "Trade carefully!",
                'error': str(e)
            }
    
    async def _get_similar_patterns(self, wallet: str, target_sol: float, tolerance: float = 0.5) -> List[TradingPattern]:
        """Find historical trades with similar SOL amounts"""
        
        # Get token P&L data from Cielo
        token_data = await self._fetch_cielo_data(wallet)
        
        # Convert to patterns
        patterns = []
        target_usd = target_sol * self._sol_price
        
        for token in token_data:
            if token['num_swaps'] == 0:
                continue
                
            avg_buy_usd = token['total_buy_usd'] / token['num_swaps']
            
            # Check if within tolerance range
            if target_usd * (1-tolerance) <= avg_buy_usd <= target_usd * (1+tolerance):
                pattern = TradingPattern(
                    symbol=token['token_symbol'],
                    avg_buy_sol=avg_buy_usd / self._sol_price,
                    roi_percentage=token['roi_percentage'],
                    pnl_sol=token['total_pnl_usd'] / self._sol_price,
                    num_trades=token['num_swaps']
                )
                patterns.append(pattern)
        
        # Sort by ROI descending
        patterns.sort(key=lambda p: p.roi_percentage, reverse=True)
        
        return patterns
    
    async def _fetch_cielo_data(self, wallet: str) -> List[Dict]:
        """Fetch token P&L data from Cielo API with caching - FIXED VERSION"""
        
        cache_key = f"cielo_{wallet}"
        
        # Check cache (5 minute expiry for real-time trading)
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            if datetime.now().timestamp() - timestamp < 300:  # 5 minutes
                return data
        
        # Fetch from API - ONLY FIRST PAGE since pagination is broken
        all_tokens = []
        
        async with aiohttp.ClientSession() as session:
            url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/tokens"
            headers = {"x-api-key": self.cielo_key}
            
            # Don't use pagination - just get first page
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"Cielo API error: {response.status}")
                
                data = await response.json()
                items = data['data']['items']
                
                # Only use the first page of results
                all_tokens = items
                
                logger.info(f"Fetched {len(all_tokens)} tokens from Cielo (first page only due to API bug)")
        
        # Cache the result
        self._cache[cache_key] = (all_tokens, datetime.now().timestamp())
        logger.info(f"Cached {len(all_tokens)} tokens for wallet {wallet[:8]}...")
        
        return all_tokens
    
    async def update_sol_price(self):
        """Update SOL price from Cielo or another source"""
        try:
            # You could fetch this from Cielo token price endpoint
            # For now using a reasonable default
            self._sol_price = 150.0
        except Exception as e:
            logger.error(f"Error updating SOL price: {e}")
    
    def _generate_coaching(
        self, 
        patterns: List[TradingPattern], 
        sol_amount: float,
        token_symbol: Optional[str] = None
    ) -> Dict:
        """Generate coaching message from patterns"""
        
        if not patterns:
            return {
                'success': True,
                'message': f"No historical data for ~{sol_amount:.1f} SOL trades.",
                'coaching': "This is a new position size for you. Start carefully and set clear stops.",
                'emoji': '🆕',
                'show_trade_button': True
            }
        
        # Calculate statistics
        total = len(patterns)
        winners = [p for p in patterns if p.roi_percentage > 0]
        win_rate = len(winners) / total * 100
        avg_roi = sum(p.roi_percentage for p in patterns) / total
        total_pnl_sol = sum(p.pnl_sol for p in patterns)
        
        # Build pattern message
        show_count = min(5, len(patterns))
        pattern_lines = [p.formatted_line for p in patterns[:show_count]]
        
        message_parts = [
            f"**Last {show_count} times you bought with ~{sol_amount:.1f} SOL:**",
            "",
            *pattern_lines
        ]
        
        if total > show_count:
            message_parts.append(f"... and {total - show_count} more trades")
        
        message_parts.extend([
            "",
            f"📊 **Stats**: {win_rate:.0f}% win rate, {avg_roi:+.1f}% avg ROI, {total_pnl_sol:+.1f} SOL total"
        ])
        
        # Generate contextual coaching
        if win_rate < 30:
            coaching = "This position size has been challenging. Consider reducing size or improving entry timing."
            emoji = '⚠️'
            show_button = True
        elif win_rate > 70:
            coaching = "Great track record with this size! Trust your process."
            emoji = '✅'
            show_button = True
        elif avg_roi < -20:
            coaching = "Significant losses at this size. What will you do differently this time?"
            emoji = '🤔'
            show_button = True
        elif total < 3:
            coaching = "Limited history with this size. Consider starting with a smaller test position."
            emoji = '📊'
            show_button = True
        else:
            coaching = "Mixed results with this pattern. What's your edge?"
            emoji = '🎯'
            show_button = True
        
        # Add token-specific insight if provided
        if token_symbol:
            message_parts.insert(0, f"🪙 **Considering {token_symbol}**")
        
        return {
            'success': True,
            'message': "\n".join(message_parts),
            'coaching': coaching,
            'emoji': emoji,
            'statistics': {
                'total_patterns': total,
                'win_rate': win_rate,
                'avg_roi': avg_roi,
                'total_pnl_sol': total_pnl_sol
            },
            'show_trade_button': show_button
        }
    
    async def get_wallet_summary(self, wallet: str) -> Dict:
        """Get overall trading summary for a wallet"""
        
        try:
            # Use Cielo's total stats endpoint
            async with aiohttp.ClientSession() as session:
                url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/total-stats"
                headers = {"x-api-key": self.cielo_key}
                
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        raise Exception(f"Cielo API error: {response.status}")
                    
                    data = await response.json()
                    stats = data['data']
                    
                    return {
                        'success': True,
                        'total_pnl_usd': stats['realized_pnl_usd'],
                        'total_pnl_sol': stats['realized_pnl_usd'] / self._sol_price,
                        'roi_percentage': stats['realized_roi_percentage'],
                        'tokens_traded': stats['tokens_traded'],
                        'win_rate': stats['winrate'],
                        'avg_holding_hours': stats['average_holding_time_seconds'] / 3600
                    }
                    
        except Exception as e:
            logger.error(f"Error fetching wallet summary: {e}")
            return {'success': False, 'error': str(e)}


# Convenience function for bot integration
async def get_trade_coaching(
    wallet: str,
    sol_amount: float,
    token_symbol: Optional[str] = None,
    cielo_key: Optional[str] = None
) -> Dict:
    """
    Get coaching for a trade - main entry point for bot
    """
    
    cielo_key = cielo_key or os.getenv('CIELO_KEY')
    if not cielo_key:
        return {
            'success': False,
            'message': "Trading coach not configured",
            'coaching': "Contact admin to enable coaching",
            'show_trade_button': True
        }
    
    coach = TradingCoach(cielo_key)
    return await coach.get_coaching_for_trade(wallet, sol_amount, token_symbol)