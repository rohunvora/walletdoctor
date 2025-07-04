"""
Test PRC-001 graceful degradation scenarios

Verifies that when SOL price fetching fails, positions are still returned
with current_price_usd=null without dropping positions entirely.
"""

import pytest
from unittest.mock import patch, Mock
from decimal import Decimal

from src.lib.sol_price_fetcher import (
    get_sol_price_usd, 
    clear_sol_price_cache,
    SolPriceFetcher
)


class TestPRC001GracefulDegradation:
    """Test graceful degradation when price sources fail"""
    
    def setup_method(self):
        """Clear cache before each test"""
        clear_sol_price_cache()
    
    @patch('requests.get')
    def test_coingecko_network_failure(self, mock_get):
        """Test handling when CoinGecko API is unreachable"""
        # Mock network error
        mock_get.side_effect = Exception("Network unreachable")
        
        price = get_sol_price_usd()
        
        # Should return None gracefully
        assert price is None
        mock_get.assert_called_once()
    
    @patch('requests.get')
    def test_coingecko_invalid_json_response(self, mock_get):
        """Test handling when CoinGecko returns invalid JSON"""
        # Mock invalid JSON response
        mock_response = Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        price = get_sol_price_usd()
        
        assert price is None
    
    @patch('requests.get')
    def test_coingecko_missing_solana_data(self, mock_get):
        """Test handling when CoinGecko response lacks SOL price"""
        # Mock response with other coins but no SOL
        mock_response = Mock()
        mock_response.json.return_value = {
            "bitcoin": {"usd": 45000},
            "ethereum": {"usd": 3000}
            # No "solana" key
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        price = get_sol_price_usd()
        
        assert price is None
    
    @patch('requests.get')
    def test_coingecko_http_error(self, mock_get):
        """Test handling when CoinGecko returns HTTP error"""
        # Mock HTTP 500 error
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 500 Internal Server Error")
        mock_get.return_value = mock_response
        
        price = get_sol_price_usd()
        
        assert price is None
    
    @patch('requests.post')
    @patch('requests.get') 
    def test_all_sources_fail(self, mock_get, mock_post):
        """Test behavior when both Helius and CoinGecko fail"""
        # Mock Helius failure
        mock_post.side_effect = Exception("Helius API error")
        
        # Mock CoinGecko failure
        mock_get.side_effect = Exception("CoinGecko API error")
        
        fetcher = SolPriceFetcher("test-helius-key")
        price = fetcher.get_sol_price_usd()
        
        assert price is None
        mock_post.assert_called_once()  # Helius attempted
        mock_get.assert_called_once()   # CoinGecko attempted
    
    def test_price_unavailable_integration(self):
        """Test integration: positions returned with null pricing when SOL price unavailable"""
        import asyncio
        from src.lib.unrealized_pnl_calculator import UnrealizedPnLCalculator
        from src.lib.position_models import Position, CostBasisMethod, PriceConfidence
        
        async def run_test():
            calculator = UnrealizedPnLCalculator()
            
            # Create test position
            position = Position(
                position_id="test",
                wallet="test_wallet",
                token_mint="test_mint",
                token_symbol="TEST",
                balance=Decimal("100.0"),
                cost_basis=Decimal("1.0"),
                cost_basis_usd=Decimal("100.0"),
                cost_basis_method=CostBasisMethod.WEIGHTED_AVG
            )
            
            # Mock feature flags to enable SOL pricing, but price fetch fails
            with patch('src.config.feature_flags.should_calculate_unrealized_pnl', return_value=True):
                with patch('src.config.feature_flags.should_use_sol_spot_pricing', return_value=True):
                    with patch('src.lib.sol_price_fetcher.get_sol_price_usd', return_value=None):
                        results = await calculator.calculate_batch_unrealized_pnl([position])
            
            # Verify graceful degradation - positions preserved but without pricing
            assert len(results) == 1
            result = results[0]
            
            # Position should be preserved
            assert result.position.token_symbol == "TEST"
            assert result.position.balance == Decimal("100.0")
            
            # But pricing should be unavailable
            assert result.current_price_usd is None
            assert result.current_value_usd is None
            assert result.unrealized_pnl_usd is None
            assert result.unrealized_pnl_pct is None
            assert result.price_confidence == PriceConfidence.UNAVAILABLE
            assert result.price_source is None
            assert result.error == "SOL price unavailable"
            
            return True
        
        # Run the async test
        result = asyncio.run(run_test())
        assert result is True
    
    @patch('requests.get')
    def test_partial_failure_recovery(self, mock_get):
        """Test that cache helps with partial failures"""
        # First call succeeds
        mock_response_success = Mock()
        mock_response_success.json.return_value = {"solana": {"usd": 175.50}}
        mock_response_success.raise_for_status.return_value = None
        
        # Second call fails
        mock_response_fail = Mock()
        mock_response_fail.raise_for_status.side_effect = Exception("Temporary failure")
        
        # Set up responses: success, then failure
        mock_get.side_effect = [mock_response_success, mock_response_fail]
        
        # First call should succeed and cache the price
        price1 = get_sol_price_usd()
        assert price1 == Decimal("175.5")
        
        # Second call should use cache despite API failure
        price2 = get_sol_price_usd()
        assert price2 == Decimal("175.5")  # From cache
        
        # Only one API call should have been made (cache hit on second)
        assert mock_get.call_count == 1 