"""
Unit tests for PRC-002: Token Price Service

Tests CoinGecko integration, caching, rate limiting, and graceful degradation.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from decimal import Decimal
import time
import asyncio
import aiohttp

from src.lib.token_price_service import TokenPriceService, KNOWN_TOKENS


class TestTokenPriceService:
    """Test TokenPriceService functionality"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.service = TokenPriceService()
        
        # Test token addresses
        self.sol_mint = "So11111111111111111111111111111111111111112"
        self.usdc_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        self.bonk_mint = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
        self.unknown_mint = "UnknownTokenMint12345"
        
    @pytest.mark.asyncio
    async def test_known_token_lookup(self):
        """Test price lookup for known tokens"""
        # Mock aiohttp response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"solana": {"usd": 180.50}})
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        self.service._session = mock_session
        
        price = await self.service.get_token_price_usd(self.sol_mint)
        assert price == Decimal("180.50")
        
    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Test that cached prices are returned without API calls"""
        # Pre-populate cache
        self.service._cache_price(self.bonk_mint, Decimal("0.00003145"))
        
        # No API call should be made
        price = await self.service.get_token_price_usd(self.bonk_mint)
        assert price == Decimal("0.00003145")
        
    @pytest.mark.asyncio
    async def test_unknown_token_by_contract(self):
        """Test price lookup by contract address for unknown tokens"""
        # Mock response for contract lookup
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            self.unknown_mint.lower(): {"usd": 0.123}
        })
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        self.service._session = mock_session
        
        price = await self.service.get_token_price_usd(self.unknown_mint)
        assert price == Decimal("0.123")
        
    @pytest.mark.asyncio
    async def test_batch_price_fetch(self):
        """Test batch price fetching for multiple tokens"""
        # Mock batch price response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "solana": {"usd": 180.0},
            "usd-coin": {"usd": 1.0},
            "bonk": {"usd": 0.00003}
        })
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        self.service._session = mock_session
        
        prices = await self.service.get_batch_prices([
            self.sol_mint,
            self.usdc_mint,
            self.bonk_mint
        ])
        
        assert prices[self.sol_mint] == Decimal("180.0")
        assert prices[self.usdc_mint] == Decimal("1.0")
        assert prices[self.bonk_mint] == Decimal("0.00003")
        
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting protection"""
        # Set low rate limit for testing
        self.service._rate_limit_calls = 2
        
        # Record some API calls to simulate hitting limit
        self.service._record_api_call()
        self.service._record_api_call()
        
        # Next call should be rate limited
        assert not self.service._check_rate_limit()
        
        # Should return None when rate limited
        price = await self.service.get_token_price_usd(self.unknown_mint, force_refresh=True)
        assert price is None
        
    @pytest.mark.asyncio
    async def test_network_error_handling(self):
        """Test graceful handling of network errors"""
        # Mock network error
        mock_response = AsyncMock()
        mock_response.status = 500
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        self.service._session = mock_session
        
        price = await self.service.get_token_price_usd(self.sol_mint)
        assert price is None
        
    @pytest.mark.asyncio
    async def test_stale_cache_fallback(self):
        """Test fallback to stale cache when API fails"""
        # Pre-populate cache with stale entry
        self.service._price_cache[self.sol_mint] = (
            Decimal("180.0"),
            time.time() - 100000  # Very old timestamp
        )
        
        # Mock API failure
        mock_response = AsyncMock()
        mock_response.status = 503
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        self.service._session = mock_session
        
        # Should return stale cached price
        price = await self.service.get_token_price_usd(self.sol_mint)
        assert price == Decimal("180.0")
        
    @pytest.mark.asyncio
    async def test_decimal_precision(self):
        """Test that decimal precision is preserved"""
        # Mock response with many decimal places
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "bonk": {"usd": 0.00003145678901234}
        })
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        self.service._session = mock_session
        
        price = await self.service.get_token_price_usd(self.bonk_mint)
        # Should preserve full precision
        assert price == Decimal("0.00003145678901234")
        
    def test_cache_statistics(self):
        """Test cache statistics reporting"""
        # Add some cached prices
        now = time.time()
        self.service._price_cache[self.sol_mint] = (Decimal("180.0"), now)
        self.service._price_cache[self.usdc_mint] = (Decimal("1.0"), now - 100000)  # Stale
        
        stats = self.service.get_cache_stats()
        
        assert stats["total_cached"] == 2
        assert stats["fresh_cached"] == 1
        assert stats["stale_cached"] == 1
        assert stats["api_calls_in_window"] == 0
        
    @pytest.mark.asyncio
    async def test_symbol_fallback(self):
        """Test fallback to symbol search when contract not found"""
        # Mock empty response for contract lookup
        mock_contract_response = AsyncMock()
        mock_contract_response.status = 200
        mock_contract_response.json = AsyncMock(return_value={})
        
        # Mock symbol search response
        mock_search_response = AsyncMock()
        mock_search_response.status = 200
        mock_search_response.json = AsyncMock(return_value={
            "coins": [
                {"id": "test-token", "symbol": "TEST"},
                {"id": "other-token", "symbol": "OTHER"}
            ]
        })
        
        # Mock price lookup response
        mock_price_response = AsyncMock()
        mock_price_response.status = 200
        mock_price_response.json = AsyncMock(return_value={
            "test-token": {"usd": 5.67}
        })
        
        # Set up mock session with different responses for different URLs
        mock_session = AsyncMock()
        
        async def mock_get(url, **kwargs):
            if "token_price/solana" in url:
                return mock_contract_response
            elif "search" in url:
                return mock_search_response
            else:  # price lookup
                return mock_price_response
        
        mock_session.get = mock_get
        self.service._session = mock_session
        
        price = await self.service.get_token_price_usd(self.unknown_mint, "TEST")
        assert price == Decimal("5.67") 