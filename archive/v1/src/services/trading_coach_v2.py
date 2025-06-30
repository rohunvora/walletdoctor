#!/usr/bin/env python3
"""
Trading Coach Service V2 - With edge case fixes and improvements
Addresses: confidence scoring, variance warnings, time relevance
"""

import os
import aiohttp
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio
import statistics

logger = logging.getLogger(__name__)

@dataclass
class TradingPattern:
    """Historical trading pattern with improvements"""
    symbol: str
    avg_buy_sol: float
    roi_percentage: float
    pnl_sol: float
    num_trades: int
    days_ago: int  # New: time relevance
    
    @property
    def emoji(self) -> str:
        return '🟢' if self.roi_percentage > 0 else '🔴'
    
    @property
    def recency_weight(self) -> float:
        """Weight based on how recent the trade is"""
        if self.days_ago <= 7:
            return 1.0
        elif self.days_ago <= 30:
            return 0.7
        else:
            return 0.4
    
    @property
    def formatted_line(self) -> str:
        roi_sign = '+' if self.roi_percentage > 0 else ''
        pnl_sign = '+' if self.pnl_sol > 0 else ''
        
        # Add time indicator for old trades
        time_indicator = ''
        if self.days_ago > 30:
            time_indicator = ' 📅'
        elif self.days_ago > 7:
            time_indicator = ' 🕐'
            
        return f"{self.emoji} {self.symbol}: {self.avg_buy_sol:.1f} SOL → {roi_sign}{self.roi_percentage:.1f}% ({pnl_sign}{self.pnl_sol:.1f} SOL){time_indicator}"

class TradingCoachV2:
    """Improved Trading Coach with edge case handling"""
    
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
        """Get coaching with improved edge case handling"""
        
        # Edge case: Invalid amounts
        if sol_amount <= 0:
            return {
                'success': True,
                'message': "Invalid trade amount.",
                'coaching': "Please enter a positive SOL amount.",
                'emoji': '❌',
                'show_trade_button': False
            }
        
        # Edge case: Dust amounts
        if sol_amount < 0.1:
            return {
                'success': True,
                'message': f"Dust amount ({sol_amount:.3f} SOL) detected.",
                'coaching': "Consider a larger position for meaningful gains after fees.",
                'emoji': '🔍',
                'show_trade_button': True
            }
        
        try:
            # Get historical patterns
            patterns = await self._get_similar_patterns(wallet, sol_amount)
            
            # Generate improved coaching
            return self._generate_enhanced_coaching(patterns, sol_amount, token_symbol)
            
        except Exception as e:
            logger.error(f"Error generating coaching: {str(e)}")
            return {
                'success': False,
                'message': "Unable to fetch trading history.",
                'coaching': "Trade carefully! System temporarily unavailable.",
                'emoji': '⚠️',
                'error': str(e),
                'show_trade_button': True
            }
    
    async def _get_similar_patterns(self, wallet: str, target_sol: float, tolerance: float = 0.5) -> List[TradingPattern]:
        """Get patterns with time data"""
        
        token_data = await self._fetch_cielo_data(wallet)
        patterns = []
        target_usd = target_sol * self._sol_price
        now = datetime.now().timestamp()
        
        for token in token_data:
            if token['num_swaps'] == 0:
                continue
                
            avg_buy_usd = token['total_buy_usd'] / token['num_swaps']
            
            # Check if within tolerance
            if target_usd * (1-tolerance) <= avg_buy_usd <= target_usd * (1+tolerance):
                # Calculate days ago
                last_trade = token.get('last_trade', token.get('first_trade', now))
                days_ago = (now - last_trade) / 86400
                
                pattern = TradingPattern(
                    symbol=token['token_symbol'],
                    avg_buy_sol=avg_buy_usd / self._sol_price,
                    roi_percentage=token['roi_percentage'],
                    pnl_sol=token['total_pnl_usd'] / self._sol_price,
                    num_trades=token['num_swaps'],
                    days_ago=int(days_ago)
                )
                patterns.append(pattern)
        
        # Sort by recency-weighted ROI
        patterns.sort(key=lambda p: p.roi_percentage * p.recency_weight, reverse=True)
        
        return patterns
    
    async def _fetch_cielo_data(self, wallet: str) -> List[Dict]:
        """Fetch with improved error handling"""
        
        cache_key = f"cielo_{wallet}"
        
        # Check cache
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            if datetime.now().timestamp() - timestamp < 300:
                return data
        
        all_tokens = []
        page = 1
        max_pages = 10
        
        async with aiohttp.ClientSession() as session:
            while page <= max_pages:
                try:
                    url = f"https://feed-api.cielo.finance/api/v1/{wallet}/pnl/tokens"
                    headers = {"x-api-key": self.cielo_key}
                    params = {"page": page}
                    
                    async with session.get(url, headers=headers, params=params, timeout=10) as response:
                        if response.status != 200:
                            logger.error(f"Cielo API error: {response.status}")
                            break
                        
                        data = await response.json()
                        items = data['data']['items']
                        
                        if not items:
                            break
                            
                        all_tokens.extend(items)
                        
                        # Check for next page
                        paging = data['data'].get('paging', {})
                        if not paging.get('has_next_page', False):
                            break
                            
                        page += 1
                        
                except asyncio.TimeoutError:
                    logger.error("Cielo API timeout")
                    break
                except Exception as e:
                    logger.error(f"Cielo API error: {e}")
                    break
        
        # Cache even partial results
        if all_tokens:
            self._cache[cache_key] = (all_tokens, datetime.now().timestamp())
            
        return all_tokens
    
    def _calculate_confidence(self, pattern_count: int) -> Tuple[str, str]:
        """Calculate confidence level"""
        if pattern_count == 0:
            return "❓", "No historical data"
        elif pattern_count == 1:
            return "⚠️", "Very low confidence (1 trade)"
        elif pattern_count < 3:
            return "⚠️", "Low confidence (limited data)"
        elif pattern_count < 10:
            return "📊", "Medium confidence"
        else:
            return "✅", "High confidence"
    
    def _calculate_variance_warning(self, patterns: List[TradingPattern]) -> Optional[str]:
        """Detect high variance patterns"""
        if len(patterns) < 3:
            return None
            
        rois = [p.roi_percentage for p in patterns]
        mean_roi = statistics.mean(rois)
        stdev_roi = statistics.stdev(rois)
        
        # Coefficient of variation
        if mean_roi != 0:
            cv = abs(stdev_roi / mean_roi)
        else:
            cv = float('inf') if stdev_roi > 0 else 0
        
        # Generate warning
        if cv > 2 or stdev_roi > 100:
            return f"⚠️ **High variance warning!** Results range from {min(rois):.0f}% to {max(rois):.0f}%"
        elif cv > 1 or stdev_roi > 50:
            return f"📊 Note: Results vary from {min(rois):.0f}% to {max(rois):.0f}%"
        
        return None
    
    def _generate_enhanced_coaching(
        self, 
        patterns: List[TradingPattern], 
        sol_amount: float,
        token_symbol: Optional[str] = None
    ) -> Dict:
        """Generate coaching with improvements"""
        
        # Get confidence level
        confidence_emoji, confidence_text = self._calculate_confidence(len(patterns))
        
        if not patterns:
            return {
                'success': True,
                'message': f"{confidence_emoji} No historical data for ~{sol_amount:.1f} SOL trades.",
                'coaching': "This is a new position size. Start with clear risk management.",
                'emoji': '🆕',
                'show_trade_button': True,
                'confidence': confidence_text
            }
        
        # Calculate statistics
        total = len(patterns)
        
        # Weight by recency
        weighted_rois = []
        total_weight = 0
        for p in patterns:
            weight = p.recency_weight
            weighted_rois.extend([p.roi_percentage] * int(weight * 10))
            total_weight += weight
        
        # Stats with recency weighting
        winners = [p for p in patterns if p.roi_percentage > 0]
        win_rate = len(winners) / total * 100
        
        # Use both mean and median
        avg_roi = statistics.mean([p.roi_percentage for p in patterns])
        if len(patterns) >= 3:
            median_roi = statistics.median([p.roi_percentage for p in patterns])
        else:
            median_roi = avg_roi
            
        total_pnl_sol = sum(p.pnl_sol for p in patterns)
        
        # Count recent vs old
        recent_count = sum(1 for p in patterns if p.days_ago <= 7)
        old_count = sum(1 for p in patterns if p.days_ago > 30)
        
        # Build message
        show_count = min(5, len(patterns))
        pattern_lines = [p.formatted_line for p in patterns[:show_count]]
        
        message_parts = []
        
        if token_symbol:
            message_parts.append(f"🪙 **Considering {token_symbol}**")
            
        message_parts.extend([
            f"**Last {show_count} times you bought with ~{sol_amount:.1f} SOL:**",
            "",
            *pattern_lines
        ])
        
        if total > show_count:
            message_parts.append(f"... and {total - show_count} more trades")
        
        # Add time relevance
        if recent_count < total / 2:
            time_note = f"📅 Note: Only {recent_count}/{total} trades are from the last week"
            message_parts.append(time_note)
        
        # Statistics with median if different
        stats_line = f"📊 **Stats**: {win_rate:.0f}% win rate, "
        if abs(median_roi - avg_roi) > 20 and len(patterns) >= 3:
            stats_line += f"{avg_roi:+.1f}% avg ROI (median: {median_roi:+.1f}%)"
        else:
            stats_line += f"{avg_roi:+.1f}% avg ROI"
        stats_line += f", {total_pnl_sol:+.1f} SOL total"
        
        message_parts.append("")
        message_parts.append(stats_line)
        
        # Add variance warning
        variance_warning = self._calculate_variance_warning(patterns)
        if variance_warning:
            message_parts.append("")
            message_parts.append(variance_warning)
        
        # Confidence level
        message_parts.append(f"\n{confidence_emoji} {confidence_text}")
        
        # Generate coaching
        if total == 1:
            coaching = "Only one historical trade at this size. Consider this limited data."
            emoji = '📊'
        elif win_rate < 30:
            coaching = "This position size has been challenging. Consider reducing size or waiting for better setups."
            emoji = '⚠️'
        elif win_rate > 70 and recent_count >= 3:
            coaching = "Recent success with this size! Stick to your winning strategy."
            emoji = '✅'
        elif old_count > recent_count:
            coaching = "Most data is older. Market conditions may have changed."
            emoji = '🕐'
        elif variance_warning and 'High variance' in variance_warning:
            coaching = "Results highly unpredictable at this size. Consider your risk tolerance."
            emoji = '🎲'
        else:
            coaching = "Mixed results. What's your edge in current market conditions?"
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
                'median_roi': median_roi,
                'total_pnl_sol': total_pnl_sol,
                'recent_count': recent_count,
                'confidence': confidence_text
            },
            'show_trade_button': True
        }

# Convenience function
async def get_enhanced_trade_coaching(
    wallet: str,
    sol_amount: float,
    token_symbol: Optional[str] = None,
    cielo_key: Optional[str] = None
) -> Dict:
    """Get enhanced coaching with edge case handling"""
    
    cielo_key = cielo_key or os.getenv('CIELO_KEY')
    if not cielo_key:
        return {
            'success': False,
            'message': "Trading coach not configured",
            'coaching': "Contact admin to enable coaching",
            'show_trade_button': True
        }
    
    coach = TradingCoachV2(cielo_key)
    return await coach.get_coaching_for_trade(wallet, sol_amount, token_symbol)