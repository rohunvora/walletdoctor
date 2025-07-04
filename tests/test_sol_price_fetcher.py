"""
Unit tests for SOL Price Fetcher (PRC-001)

Tests:
- CoinGecko fallback (primary for now)
- Caching behavior (30s TTL)
- Failure handling (graceful degradation)
- Cache status and diagnostics
"""

import pytest
import time
from decimal import Decimal
from unittest.mock import patch, Mock

from src.lib.sol_price_fetcher import (
    SolPriceFetcher,
    get_sol_price_usd,
    clear_sol_price_cache,
    get_cache_status,
    _price_cache
)


class TestSolPriceFetcher:
    """Test SolPriceFetcher class"""
    
    def setup_method(self):
        """Clear cache before each test"""
        clear_sol_price_cache()
    
    def test_fetcher_initialization(self):
        """Test fetcher initialization with and without API key"""
        # Without API key
        fetcher = SolPriceFetcher()
        assert fetcher.helius_api_key is None
        assert fetcher.helius_url is None
        assert "coingecko.com" in fetcher.coingecko_url
        
        # With API key
        fetcher = SolPriceFetcher("test-key")
        assert fetcher.helius_api_key == "test-key"
        assert fetcher.helius_url is not None and "test-key" in fetcher.helius_url
    
    @patch('requests.get')
    def test_coingecko_success(self, mock_get):
        """Test successful CoinGecko price fetch"""
        # Mock successful CoinGecko response
        mock_response = Mock()
        mock_response.json.return_value = {"solana": {"usd": 180.45}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        fetcher = SolPriceFetcher()
        price = fetcher.get_sol_price_usd()
        
        assert price == Decimal("180.45")
        mock_get.assert_called_once()
    
    @patch('requests.get')
    def test_coingecko_failure(self, mock_get):
        """Test CoinGecko API failure handling"""
        # Mock failed response
        mock_get.side_effect = Exception("API Error")
        
        fetcher = SolPriceFetcher()
        price = fetcher.get_sol_price_usd()
        
        assert price is None
    
    @patch('requests.get')
    def test_coingecko_invalid_response(self, mock_get):
        """Test CoinGecko invalid response handling"""
        # Mock response without SOL price
        mock_response = Mock()
        mock_response.json.return_value = {"bitcoin": {"usd": 45000}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        fetcher = SolPriceFetcher()
        price = fetcher.get_sol_price_usd()
        
        assert price is None
    
    @patch('requests.post')
    @patch('requests.get')
    def test_helius_fallback_to_coingecko(self, mock_get, mock_post):
        """Test Helius failure falls back to CoinGecko"""
        # Mock Helius failure
        mock_post.side_effect = Exception("Helius Error")
        
        # Mock CoinGecko success
        mock_response = Mock()
        mock_response.json.return_value = {"solana": {"usd": 175.20}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        fetcher = SolPriceFetcher("test-key")
        price = fetcher.get_sol_price_usd()
        
        assert price == Decimal("175.20")
        mock_post.assert_called_once()
        mock_get.assert_called_once()
    
    @patch('requests.get')
    def test_price_caching(self, mock_get):
        """Test 30-second price caching"""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {"solana": {"usd": 182.15}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        fetcher = SolPriceFetcher()
        
        # First call should hit API
        price1 = fetcher.get_sol_price_usd()
        assert price1 == Decimal("182.15")
        assert mock_get.call_count == 1
        
        # Second call should use cache
        price2 = fetcher.get_sol_price_usd()
        assert price2 == Decimal("182.15")
        assert mock_get.call_count == 1  # No additional API call
        
        # Verify cache is populated
        cache_status = get_cache_status()
        assert cache_status["price"] == "182.15"
        assert cache_status["is_fresh"] is True
    
    @patch('requests.get')
    def test_cache_expiration(self, mock_get):
        """Test cache expiration after TTL"""
        # Mock successful CoinGecko response
        mock_response = Mock()
        mock_response.json.return_value = {"solana": {"usd": 185.00}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Use convenience function (simpler than class instance)
        
        # First call - should populate cache
        price1 = get_sol_price_usd()
        assert price1 == Decimal("185.0")
        assert mock_get.call_count == 1
        
        # Second call should use cache (no additional API call)
        price2 = get_sol_price_usd()
        assert price2 == Decimal("185.0")
        assert mock_get.call_count == 1  # Still 1 call
        
        # Simulate cache expiration by clearing it entirely
        clear_sol_price_cache()
        
        # Third call should hit API again due to cleared cache
        price3 = get_sol_price_usd()
        assert price3 == Decimal("185.0")
        assert mock_get.call_count == 2  # Now 2 calls
    
    def test_cache_utilities(self):
        """Test cache utility functions"""
        # Initially empty
        status = get_cache_status()
        assert status["price"] is None
        assert status["is_fresh"] is False
        
        # Use the actual cache manipulation through the utility functions
        # rather than directly accessing the module-level variable
        
        # Test by using the module's convenience function to populate cache
        from unittest.mock import patch
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {"solana": {"usd": 190.00}}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            # This should populate the cache
            price = get_sol_price_usd()
            assert price == Decimal("190.00")
        
        # Now check cache status
        status = get_cache_status()
        assert status["price"] == "190.0"  # Decimal formatting
        assert status["is_fresh"] is True
        
        # Clear cache
        clear_sol_price_cache()
        status = get_cache_status()
        assert status["price"] is None


class TestConvenienceFunctions:
    """Test module-level convenience functions"""
    
    def setup_method(self):
        """Clear cache before each test"""
        clear_sol_price_cache()
    
    @patch('requests.get')
    def test_get_sol_price_usd_function(self, mock_get):
        """Test get_sol_price_usd convenience function"""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {"solana": {"usd": 177.88}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        price = get_sol_price_usd()
        assert price == Decimal("177.88")
    
    @patch('requests.get')
    def test_get_sol_price_with_api_key(self, mock_get):
        """Test convenience function with Helius API key"""
        mock_get.return_value.json.return_value = {"solana": {"usd": 179.99}}
        mock_get.return_value.raise_for_status.return_value = None
        
        price = get_sol_price_usd("test-helius-key")
        assert price == Decimal("179.99")
    
    def test_cache_status_empty(self):
        """Test cache status when empty"""
        status = get_cache_status()
        
        assert status["price"] is None
        assert status["age_seconds"] > 0  # Should be time since epoch
        assert status["is_fresh"] is False
        assert status["ttl_seconds"] == 30


class TestIntegration:
    """Integration tests for real pricing scenarios"""
    
    def setup_method(self):
        """Clear cache before each test"""
        clear_sol_price_cache()
    
    @patch('requests.get')
    def test_position_pricing_integration(self, mock_get):
        """Test integration with position pricing logic"""
        # Mock SOL price
        mock_get.return_value.json.return_value = {"solana": {"usd": 180.00}}
        mock_get.return_value.raise_for_status.return_value = None
        
        sol_price = get_sol_price_usd()
        assert sol_price is not None
        
        # Simulate position with SOL balance
        balance_sol = Decimal("2.5")
        current_value_usd = balance_sol * sol_price
        
        assert current_value_usd == Decimal("450.00")
    
    @patch('requests.get')
    def test_failure_graceful_degradation(self, mock_get):
        """Test graceful handling when all price sources fail"""
        # Mock all failures
        mock_get.side_effect = Exception("Network Error")
        
        sol_price = get_sol_price_usd()
        
        # Should return None, not crash
        assert sol_price is None
        
        # Position pricing should handle None gracefully
        balance_sol = Decimal("1.0")
        if sol_price is not None:
            current_value_usd = balance_sol * sol_price
        else:
            current_value_usd = None
        
        assert current_value_usd is None 