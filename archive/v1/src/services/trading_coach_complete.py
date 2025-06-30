#!/usr/bin/env python3
"""
Trading Coach using COMPLETE data from our Cielo replacement
No more hidden losses - shows the full picture
"""

import os
import logging
from typing import List, Dict, Optional
from datetime import datetime

from .cielo_replacement_optimized import get_complete_pnl_optimized

logger = logging.getLogger(__name__)

class CompleteDataCoach:
    """Trading coach with access to ALL historical data"""
    
    def __init__(self, helius_api_key: str):
        self.helius_key = helius_api_key
        self._sol_price = 150.0
        
    async def get_coaching_for_trade(
        self,
        wallet: str,
        sol_amount: float,
        token_symbol: Optional[str] = None
    ) -> Dict:
        """Get coaching advice based on COMPLETE trading history"""
        
        try:
            # Get complete P&L data (all tokens, not just top 50)
            logger.info(f"Fetching complete trading history for {wallet}")
            pnl_data = await get_complete_pnl_optimized(wallet, self.helius_key)
            
            tokens = pnl_data['data']['items']
            total_stats = pnl_data['total_stats']
            
            # Find similar patterns
            patterns = self._find_similar_patterns(tokens, sol_amount)
            
            # Generate coaching with complete data
            return self._generate_complete_coaching(
                patterns,
                sol_amount,
                token_symbol,
                total_stats,
                len(tokens)
            )
            
        except Exception as e:
            logger.error(f"Error in complete data coaching: {str(e)}")
            return {
                'success': False,
                'message': "Unable to fetch complete trading history.",
                'coaching': "Trade carefully!",
                'error': str(e)
            }
    
    def _find_similar_patterns(self, tokens: List[Dict], target_sol: float, tolerance: float = 0.5) -> List[Dict]:
        """Find historical trades with similar SOL amounts"""
        
        patterns = []
        target_usd = target_sol * self._sol_price
        
        for token in tokens:
            if token['num_swaps'] == 0:
                continue
            
            avg_buy_usd = token['total_buy_usd'] / token['num_swaps']
            
            # Check if within tolerance range
            if target_usd * (1-tolerance) <= avg_buy_usd <= target_usd * (1+tolerance):
                patterns.append({
                    'symbol': token['token_symbol'],
                    'avg_buy_sol': avg_buy_usd / self._sol_price,
                    'roi_percentage': token['roi_percentage'],
                    'pnl_sol': token['total_pnl_usd'] / self._sol_price,
                    'num_trades': token['num_swaps'],
                    'total_buy_usd': token['total_buy_usd'],
                    'total_sell_usd': token['total_sell_usd']
                })
        
        # Sort by ROI descending
        patterns.sort(key=lambda p: p['roi_percentage'], reverse=True)
        
        return patterns
    
    def _generate_complete_coaching(
        self,
        patterns: List[Dict],
        sol_amount: float,
        token_symbol: Optional[str],
        total_stats: Dict,
        total_tokens: int
    ) -> Dict:
        """Generate coaching with COMPLETE data context"""
        
        if not patterns:
            message = f"No historical data for ~{sol_amount:.1f} SOL trades."
            
            # Add context about overall trading
            if total_tokens > 0:
                message += f"\n\nYour overall stats: {total_stats['winrate']:.0f}% win rate on {total_tokens} tokens."
            
            return {
                'success': True,
                'message': message,
                'coaching': "This is a new position size for you. Consider your overall win rate when sizing.",
                'emoji': '🆕',
                'statistics': {
                    'total_tokens_analyzed': total_tokens,
                    'complete_data': True
                }
            }
        
        # Calculate statistics
        total = len(patterns)
        winners = [p for p in patterns if p['roi_percentage'] > 0]
        win_rate = len(winners) / total * 100
        avg_roi = sum(p['roi_percentage'] for p in patterns) / total
        total_pnl_sol = sum(p['pnl_sol'] for p in patterns)
        
        # Build message
        message_parts = []
        
        if token_symbol:
            message_parts.append(f"🪙 **Considering {token_symbol}**")
        
        message_parts.extend([
            f"**Found {total} similar trades (~{sol_amount:.1f} SOL) in COMPLETE history:**",
            ""
        ])
        
        # Show top patterns
        show_count = min(5, len(patterns))
        for pattern in patterns[:show_count]:
            emoji = '🟢' if pattern['roi_percentage'] > 0 else '🔴'
            roi_sign = '+' if pattern['roi_percentage'] > 0 else ''
            pnl_sign = '+' if pattern['pnl_sol'] > 0 else ''
            
            message_parts.append(
                f"{emoji} {pattern['symbol']}: {pattern['avg_buy_sol']:.1f} SOL → "
                f"{roi_sign}{pattern['roi_percentage']:.1f}% ({pnl_sign}{pattern['pnl_sol']:.1f} SOL)"
            )
        
        if total > show_count:
            message_parts.append(f"... and {total - show_count} more trades")
        
        # Add statistics
        message_parts.extend([
            "",
            f"📊 **Pattern Stats**: {win_rate:.0f}% win rate, {avg_roi:+.1f}% avg ROI",
            f"💰 **Total P&L at this size**: {total_pnl_sol:+.1f} SOL"
        ])
        
        # Add overall context
        message_parts.extend([
            "",
            f"📈 **Overall Wallet Performance**:",
            f"• {total_tokens} tokens traded (100% analyzed)",
            f"• {total_stats['winrate']:.0f}% overall win rate",
            f"• ${total_stats['realized_pnl_usd']:,.0f} total P&L",
            "",
            "✅ **This analysis includes ALL your trades, not just winners**"
        ])
        
        # Generate coaching based on COMPLETE data
        if win_rate < 30:
            coaching = f"Poor track record at this size: {win_rate:.0f}% wins. Consider smaller positions."
            emoji = '🚨'
        elif win_rate > 70:
            coaching = f"Strong performance at this size: {win_rate:.0f}% wins. Stay disciplined."
            emoji = '✅'
        elif avg_roi < -20:
            coaching = "Heavy losses at this size. Review your entry criteria."
            emoji = '⚠️'
        elif total < 5:
            coaching = f"Limited data ({total} trades). Proceed with caution."
            emoji = '📊'
        else:
            coaching = f"Mixed results: {win_rate:.0f}% wins. Focus on high-conviction plays."
            emoji = '🎯'
        
        # Add specific insights
        if total_pnl_sol < -10:
            coaching += f" You've lost {abs(total_pnl_sol):.1f} SOL at this position size."
        elif total_pnl_sol > 10:
            coaching += f" You've made {total_pnl_sol:.1f} SOL at this position size."
        
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
                'total_tokens_analyzed': total_tokens,
                'complete_data': True,
                'data_source': 'helius_complete'
            }
        }

# Convenience function
async def get_complete_trade_coaching(
    wallet: str,
    sol_amount: float,
    token_symbol: Optional[str] = None,
    helius_key: Optional[str] = None
) -> Dict:
    """Get coaching based on COMPLETE trading history"""
    
    helius_key = helius_key or os.getenv('HELIUS_API_KEY')
    if not helius_key:
        return {
            'success': False,
            'message': "Helius API key not configured",
            'coaching': "Contact admin to enable complete data coaching",
        }
    
    coach = CompleteDataCoach(helius_key)
    return await coach.get_coaching_for_trade(wallet, sol_amount, token_symbol)