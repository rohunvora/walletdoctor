#!/usr/bin/env python3
"""
Comprehensive test suite for the Trading Coach
Tests edge cases, data quality issues, and blind spots
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.trading_coach import TradingCoach, TradingPattern

class TestTradingCoachEdgeCases:
    """Test edge cases and blind spots"""
    
    @pytest.fixture
    def mock_cielo_data(self):
        """Mock Cielo API responses for different scenarios"""
        return {
            'normal': [
                {
                    'token_symbol': 'BONK',
                    'token_name': 'Bonk',
                    'num_swaps': 5,
                    'total_buy_usd': 750,
                    'total_pnl_usd': 150,
                    'roi_percentage': 20.0
                }
            ],
            'empty': [],
            'single_trade': [
                {
                    'token_symbol': 'LONE',
                    'token_name': 'Lonely Token',
                    'num_swaps': 1,
                    'total_buy_usd': 1500,
                    'total_pnl_usd': -1400,
                    'roi_percentage': -93.33
                }
            ],
            'extreme_losses': [
                {
                    'token_symbol': f'REKT{i}',
                    'token_name': f'Rekt Token {i}',
                    'num_swaps': 2,
                    'total_buy_usd': 3000,
                    'total_pnl_usd': -2850,
                    'roi_percentage': -95.0
                } for i in range(10)
            ],
            'extreme_wins': [
                {
                    'token_symbol': f'MOON{i}',
                    'token_name': f'Moon Token {i}',
                    'num_swaps': 1,
                    'total_buy_usd': 150,
                    'total_pnl_usd': 15000,
                    'roi_percentage': 10000.0
                } for i in range(5)
            ],
            'zero_trades': [
                {
                    'token_symbol': 'GHOST',
                    'token_name': 'Ghost Token',
                    'num_swaps': 0,
                    'total_buy_usd': 0,
                    'total_pnl_usd': 0,
                    'roi_percentage': 0
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_new_trader_no_history(self):
        """Test: Brand new trader with no history"""
        coach = TradingCoach('test_key')
        
        with patch.object(coach, '_fetch_cielo_data', return_value=[]):
            result = await coach.get_coaching_for_trade('new_wallet', 10.0)
            
            assert result['success']
            assert "No historical data" in result['message']
            assert "new position size" in result['coaching']
            assert result['emoji'] == '🆕'
    
    @pytest.mark.asyncio
    async def test_extreme_loss_pattern(self, mock_cielo_data):
        """Test: User with extreme losses at this position size"""
        coach = TradingCoach('test_key')
        
        with patch.object(coach, '_fetch_cielo_data', return_value=mock_cielo_data['extreme_losses']):
            result = await coach.get_coaching_for_trade('loss_wallet', 20.0)
            
            assert result['success']
            assert result['statistics']['win_rate'] == 0
            assert result['statistics']['avg_roi'] < -90
            assert "challenging" in result['coaching'] or "losses" in result['coaching']
            assert result['emoji'] in ['⚠️', '🤔']
    
    @pytest.mark.asyncio
    async def test_single_outlier_trade(self, mock_cielo_data):
        """Test: User with only one trade at this size (could be lucky/unlucky)"""
        coach = TradingCoach('test_key')
        
        with patch.object(coach, '_fetch_cielo_data', return_value=mock_cielo_data['single_trade']):
            result = await coach.get_coaching_for_trade('single_wallet', 10.0)
            
            assert result['success']
            assert "Limited history" in result['coaching'] or "1 times" in result['message']
    
    @pytest.mark.asyncio
    async def test_extreme_variance_trades(self, mock_cielo_data):
        """Test: Mix of huge wins and huge losses"""
        mixed_data = mock_cielo_data['extreme_wins'] + mock_cielo_data['extreme_losses']
        coach = TradingCoach('test_key')
        
        with patch.object(coach, '_fetch_cielo_data', return_value=mixed_data):
            result = await coach.get_coaching_for_trade('variance_wallet', 1.0)
            
            # Should recognize high variance pattern
            assert result['success']
            stats = result['statistics']
            assert stats['win_rate'] == 33.33  # 5 wins out of 15 total
    
    @pytest.mark.asyncio
    async def test_zero_sol_amount(self):
        """Test: User tries to trade 0 SOL"""
        coach = TradingCoach('test_key')
        
        result = await coach.get_coaching_for_trade('wallet', 0.0)
        
        # Should handle gracefully
        assert result['success']
        assert "No historical data" in result['message']
    
    @pytest.mark.asyncio
    async def test_huge_sol_amount(self):
        """Test: Whale trying to trade 10,000 SOL"""
        coach = TradingCoach('test_key')
        
        with patch.object(coach, '_fetch_cielo_data', return_value=[]):
            result = await coach.get_coaching_for_trade('whale_wallet', 10000.0)
            
            # Should handle large amounts
            assert result['success']
            assert "10000" in result['message'] or "new position size" in result['message']
    
    @pytest.mark.asyncio
    async def test_api_timeout(self):
        """Test: Cielo API timeout"""
        coach = TradingCoach('test_key')
        
        with patch.object(coach, '_fetch_cielo_data', side_effect=asyncio.TimeoutError()):
            result = await coach.get_coaching_for_trade('timeout_wallet', 10.0)
            
            assert not result['success']
            assert "Unable to fetch" in result['message']
    
    @pytest.mark.asyncio
    async def test_malformed_api_response(self):
        """Test: Cielo returns malformed data"""
        coach = TradingCoach('test_key')
        
        malformed_data = [
            {
                'token_symbol': 'BAD',
                # Missing required fields
            }
        ]
        
        with patch.object(coach, '_fetch_cielo_data', return_value=malformed_data):
            result = await coach.get_coaching_for_trade('bad_wallet', 10.0)
            
            # Should handle gracefully
            assert 'success' in result  # Should not crash


class TestBlindSpots:
    """Test for blind spots in the coaching logic"""
    
    def test_time_based_patterns(self):
        """BLIND SPOT: No consideration of WHEN trades happened"""
        # Current system doesn't distinguish between:
        # - 10 losses last week vs 10 losses last year
        # - Morning trades vs evening trades
        # - Weekend vs weekday patterns
        assert True  # Marking this blind spot
    
    def test_market_condition_context(self):
        """BLIND SPOT: No market condition awareness"""
        # System doesn't know if losses were during:
        # - Bear market vs bull market
        # - High volatility vs low volatility
        # - Specific market events
        assert True  # Marking this blind spot
    
    def test_token_category_patterns(self):
        """BLIND SPOT: No token category analysis"""
        # Doesn't distinguish between:
        # - Memecoins vs utility tokens
        # - New launches vs established tokens
        # - Different sectors (AI, gaming, DeFi)
        assert True  # Marking this blind spot
    
    def test_exit_strategy_patterns(self):
        """BLIND SPOT: Only considers entry, not exit patterns"""
        # Doesn't analyze:
        # - Did user take profits or hold to zero?
        # - Quick flips vs long holds
        # - Partial exits vs full exits
        assert True  # Marking this blind spot
    
    def test_correlated_trades(self):
        """BLIND SPOT: Treats all trades as independent"""
        # Doesn't consider:
        # - Trading the same token multiple times
        # - Trading correlated tokens
        # - Revenge trading patterns
        assert True  # Marking this blind spot


class TestDataQualityIssues:
    """Test data quality edge cases"""
    
    @pytest.mark.asyncio
    async def test_sol_price_volatility(self):
        """Test: SOL price changes significantly between trades"""
        coach = TradingCoach('test_key')
        
        # If SOL was $50 during historical trades but $150 now
        # 10 SOL then ≠ 10 SOL now in USD terms
        
        old_trades = [{
            'token_symbol': 'OLD',
            'num_swaps': 1,
            'total_buy_usd': 500,  # Was 10 SOL at $50
            'total_pnl_usd': 100,
            'roi_percentage': 20.0
        }]
        
        coach._sol_price = 150  # Current price
        
        with patch.object(coach, '_fetch_cielo_data', return_value=old_trades):
            patterns = await coach._get_similar_patterns('wallet', 10.0, tolerance=0.5)
            
            # 10 SOL now = $1500, but trade was $500
            # Should not match due to USD difference
            assert len(patterns) == 0
    
    @pytest.mark.asyncio 
    async def test_incomplete_cielo_data(self):
        """Test: Cielo missing some trades (API limits, errors)"""
        coach = TradingCoach('test_key')
        
        # Cielo only returns 136 tokens but user traded 198
        partial_data = [{'token_symbol': f'TOKEN{i}', 'num_swaps': 1, 
                        'total_buy_usd': 1500, 'total_pnl_usd': -100,
                        'roi_percentage': -6.67} for i in range(136)]
        
        with patch.object(coach, '_fetch_cielo_data', return_value=partial_data):
            result = await coach.get_coaching_for_trade('partial_wallet', 10.0)
            
            # Should still work with partial data
            assert result['success']
            # But might give incomplete picture


class TestUserExperienceEdgeCases:
    """Test UX edge cases"""
    
    @pytest.mark.asyncio
    async def test_user_spam_requests(self):
        """Test: User rapidly checking patterns"""
        coach = TradingCoach('test_key')
        
        # First request should hit API
        with patch.object(coach, '_fetch_cielo_data', return_value=[]) as mock_fetch:
            await coach.get_coaching_for_trade('spam_wallet', 10.0)
            assert mock_fetch.called
            
            # Second request should use cache
            mock_fetch.reset_mock()
            await coach.get_coaching_for_trade('spam_wallet', 10.0)
            assert not mock_fetch.called  # Used cache
    
    @pytest.mark.asyncio
    async def test_misleading_patterns(self):
        """Test: Patterns that might mislead users"""
        coach = TradingCoach('test_key')
        
        # All wins were one lucky token
        lucky_token_data = [
            {
                'token_symbol': 'LUCKY',
                'num_swaps': 10,
                'total_buy_usd': 1500,
                'total_pnl_usd': 15000,
                'roi_percentage': 1000.0
            }
        ] + [
            {
                'token_symbol': f'LOSS{i}',
                'num_swaps': 1,
                'total_buy_usd': 150,
                'total_pnl_usd': -145,
                'roi_percentage': -96.67
            } for i in range(9)
        ]
        
        with patch.object(coach, '_fetch_cielo_data', return_value=lucky_token_data):
            result = await coach.get_coaching_for_trade('lucky_wallet', 1.0)
            
            # High win rate might be misleading
            stats = result['statistics']
            # Only 1 out of 10 different tokens won
            assert stats['win_rate'] == 10.0


# Performance test
class TestPerformance:
    """Test performance with large datasets"""
    
    @pytest.mark.asyncio
    async def test_large_trading_history(self):
        """Test: User with 1000+ trades"""
        coach = TradingCoach('test_key')
        
        # Generate large dataset
        large_data = [{
            'token_symbol': f'TOKEN{i}',
            'num_swaps': 5,
            'total_buy_usd': 1500,
            'total_pnl_usd': 100 if i % 3 == 0 else -50,
            'roi_percentage': 6.67 if i % 3 == 0 else -3.33
        } for i in range(1000)]
        
        import time
        start = time.time()
        
        with patch.object(coach, '_fetch_cielo_data', return_value=large_data):
            result = await coach.get_coaching_for_trade('large_wallet', 10.0)
        
        duration = time.time() - start
        
        assert result['success']
        assert duration < 1.0  # Should complete within 1 second


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, '-v'])