#!/usr/bin/env python3
"""
Trading Coach Service - ACCURATE version that acknowledges data limitations
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
        self._sol_price = 150.0
        
    async def get_coaching_for_trade(
        self,
        wallet: str,
        sol_amount: float,
        token_symbol: Optional[str] = None
    ) -> Dict:
        """Get coaching advice for a potential trade"""
        try:
            # First, get the complete wallet stats to understand the full picture
            wallet_stats = await self._get_wallet_stats(wallet)
            
            # Get patterns from available data
            patterns = await self._get_similar_patterns(wallet, sol_amount)
            
            # Generate coaching with context about data limitations
            return self._generate_accurate_coaching(
                patterns, 
                sol_amount, 
                token_symbol,
                wallet_stats
            )
            
        except Exception as e:
            logger.error(f"Error generating coaching: {str(e)}")
            return {
                'success': False,
                'message': "Unable to fetch trading history at the moment.",
                'coaching': "Trade carefully!",
                'error': str(e)
            }
    
    async def _get_wallet_stats(self, wallet: str) -> Dict:
        """Get overall wallet statistics"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/total-stats"
                headers = {"x-api-key": self.cielo_key}
                
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        return None
                    
                    data = await response.json()
                    return data['data']
        except:
            return None
    
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
        """Fetch available token data from Cielo API"""
        
        cache_key = f"cielo_{wallet}"
        
        # Check cache
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            if datetime.now().timestamp() - timestamp < 300:
                return data
        
        # Fetch from API
        async with aiohttp.ClientSession() as session:
            url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/tokens"
            headers = {"x-api-key": self.cielo_key}
            
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"Cielo API error: {response.status}")
                
                data = await response.json()
                items = data['data']['items']
                
                # Cache the result
                self._cache[cache_key] = (items, datetime.now().timestamp())
                
                return items
    
    def _generate_accurate_coaching(
        self, 
        patterns: List[TradingPattern], 
        sol_amount: float,
        token_symbol: Optional[str],
        wallet_stats: Optional[Dict]
    ) -> Dict:
        """Generate coaching with accurate context"""
        
        # Data availability warning
        total_tokens = wallet_stats.get('tokens_traded', 0) if wallet_stats else 0
        available_tokens = 50  # Cielo API limitation
        
        if not patterns:
            message = f"No historical data for ~{sol_amount:.1f} SOL trades in available data."
            
            if total_tokens > available_tokens:
                message += f"\n\n⚠️ Note: Analysis based on {available_tokens}/{total_tokens} tokens due to API limitations."
            
            return {
                'success': True,
                'message': message,
                'coaching': "This is a new position size in the available data. Trade carefully.",
                'emoji': '🆕',
                'show_trade_button': True,
                'data_complete': False
            }
        
        # Calculate statistics from available patterns
        total = len(patterns)
        winners = [p for p in patterns if p.roi_percentage > 0]
        win_rate = len(winners) / total * 100
        avg_roi = sum(p.roi_percentage for p in patterns) / total
        total_pnl_sol = sum(p.pnl_sol for p in patterns)
        
        # Build message
        show_count = min(5, len(patterns))
        pattern_lines = [p.formatted_line for p in patterns[:show_count]]
        
        message_parts = []
        
        if token_symbol:
            message_parts.append(f"🪙 **Considering {token_symbol}**")
            
        message_parts.extend([
            f"**Found {total} similar trades in available data (~{sol_amount:.1f} SOL):**",
            "",
            *pattern_lines
        ])
        
        if total > show_count:
            message_parts.append(f"... and {total - show_count} more trades")
        
        # Add statistics
        message_parts.extend([
            "",
            f"📊 **Stats (from available data)**: {win_rate:.0f}% win rate, {avg_roi:+.1f}% avg ROI"
        ])
        
        # Add data completeness warning
        if total_tokens > available_tokens:
            completeness = (available_tokens / total_tokens) * 100
            message_parts.extend([
                "",
                f"⚠️ **Data Coverage**: Showing {available_tokens}/{total_tokens} tokens ({completeness:.0f}% of total history)"
            ])
            
            # Add overall wallet context if very different
            if wallet_stats:
                overall_wr = wallet_stats.get('winrate', 0)
                overall_roi = wallet_stats.get('realized_roi_percentage', 0)
                
                message_parts.extend([
                    f"📈 **Full Wallet Stats**: {overall_wr:.0f}% win rate, {overall_roi:+.1f}% ROI",
                    "",
                    "⚡ For complete analysis, contact Cielo support about API pagination."
                ])
        
        # Generate coaching based on available data
        if win_rate < 30:
            coaching = "Low win rate at this size (in available data). Consider position sizing carefully."
            emoji = '⚠️'
        elif win_rate > 70:
            coaching = "Strong performance at this size (in available data). Maintain discipline."
            emoji = '✅'
        elif total < 3:
            coaching = "Limited data points. Results may not be statistically significant."
            emoji = '📊'
        else:
            coaching = "Mixed results. Focus on your current market read."
            emoji = '🎯'
        
        return {
            'success': True,
            'message': "\n".join(message_parts),
            'coaching': coaching,
            'emoji': emoji,
            'statistics': {
                'total_patterns': total,
                'win_rate': win_rate,
                'avg_roi': avg_roi,
                'total_pnl_sol': total_pnl_sol,
                'data_complete': total_tokens <= available_tokens,
                'coverage_percent': (available_tokens / total_tokens * 100) if total_tokens > 0 else 100
            },
            'show_trade_button': True
        }

# Convenience function
async def get_trade_coaching(
    wallet: str,
    sol_amount: float,
    token_symbol: Optional[str] = None,
    cielo_key: Optional[str] = None
) -> Dict:
    """Get coaching for a trade with accurate data disclosure"""
    
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