#!/usr/bin/env python3
"""
Test DexScreener client functionality
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime
import time
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.lib.dexscreener_client import (
    DexScreenerClient,
    get_dexscreener_price,
    get_market_cap_from_dexscreener,
    SOL_MINT,
    USDC_MINT,
    SOLANA_CHAIN
)


class TestDexScreenerClient:
    """Test DexScreenerClient class"""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock aiohttp session"""
        session = MagicMock()
        session.get = AsyncMock()
        return session
    
    @pytest.fixture
    def mock_response(self):
        """Create a mock response"""
        response = MagicMock()
        response.status = 200
        response.headers = {}
        response.json = AsyncMock()
        response.raise_for_status = MagicMock()
        return response
    
    @pytest.mark.asyncio
    async def test_get_token_pairs_success(self, mock_session, mock_response):
        """Test successful token pairs fetch"""
        # Setup mock response
        mock_response.json.return_value = {
            "pairs": [
                {
                    "chainId": "solana",
                    "pairAddress": "pair1",
                    "baseToken": {"address": SOL_MINT, "symbol": "SOL"},
                    "quoteToken": {"address": USDC_MINT, "symbol": "USDC"},
                    "priceUsd": "150.50",
                    "liquidity": {"usd": 1000000},
                    "volume": {"h24": 5000000},
                    "marketCap": 86000000000
                },
                {
                    "chainId": "ethereum",  # Should be filtered out
                    "pairAddress": "pair2"
                }
            ]
        }
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = DexScreenerClient(mock_session)
        result = await client.get_token_pairs(SOL_MINT)
        
        assert result is not None
        assert len(result) == 1  # Only Solana pair
        assert result[0]["chainId"] == "solana"
        assert result[0]["pairAddress"] == "pair1"
    
    @pytest.mark.asyncio
    async def test_get_token_price_success(self, mock_session, mock_response):
        """Test successful token price fetch"""
        # Setup mock response
        mock_response.json.return_value = {
            "pairs": [
                {
                    "chainId": "solana",
                    "baseToken": {"address": SOL_MINT},
                    "quoteToken": {"address": USDC_MINT},
                    "priceUsd": "150.50",
                    "liquidity": {"usd": 1000000},
                    "volume": {"h24": 5000000},
                    "priceChange": {"h24": 5.2},
                    "txns": {"h24": {"buys": 100, "sells": 80}},
                    "fdv": 90000000000,
                    "marketCap": 86000000000,
                    "pairAddress": "test_pair",
                    "dexId": "raydium"
                }
            ]
        }
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = DexScreenerClient(mock_session)
        result = await client.get_token_price(SOL_MINT, USDC_MINT)
        
        assert result is not None
        price, metadata = result
        assert price == Decimal("150.50")
        assert metadata["liquidity"] == 1000000
        assert metadata["volume24h"] == 5000000
        assert metadata["priceChange24h"] == 5.2
        assert metadata["txCount24h"] == 180
        assert metadata["marketCap"] == 86000000000
        assert metadata["source"] == "dexscreener"
    
    @pytest.mark.asyncio
    async def test_get_token_price_no_pairs(self, mock_session, mock_response):
        """Test token price when no pairs found"""
        mock_response.json.return_value = {"pairs": []}
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = DexScreenerClient(mock_session)
        result = await client.get_token_price("invalid_token")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_market_cap_success(self, mock_session, mock_response):
        """Test successful market cap fetch"""
        # Setup mock response
        mock_response.json.return_value = {
            "pairs": [
                {
                    "chainId": "solana",
                    "liquidity": {"usd": 1000000},
                    "marketCap": 86000000000,
                    "fdv": 90000000000
                }
            ]
        }
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = DexScreenerClient(mock_session)
        result = await client.get_market_cap(SOL_MINT)
        
        assert result is not None
        market_cap, source = result
        assert market_cap == 86000000000.0
        assert source == "dexscreener_mc"
    
    @pytest.mark.asyncio
    async def test_get_market_cap_fdv_fallback(self, mock_session, mock_response):
        """Test market cap fallback to FDV"""
        # Setup mock response with no MC but FDV
        mock_response.json.return_value = {
            "pairs": [
                {
                    "chainId": "solana",
                    "liquidity": {"usd": 1000000},
                    "marketCap": 0,  # No market cap
                    "fdv": 90000000000  # But has FDV
                }
            ]
        }
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = DexScreenerClient(mock_session)
        result = await client.get_market_cap(SOL_MINT)
        
        assert result is not None
        market_cap, source = result
        assert market_cap == 90000000000.0
        assert source == "dexscreener_fdv"
    
    @pytest.mark.asyncio
    async def test_404_handling(self, mock_session, mock_response):
        """Test 404 error handling"""
        mock_response.status = 404
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = DexScreenerClient(mock_session)
        result = await client.get_token_pairs("unknown_token")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_search_tokens(self, mock_session, mock_response):
        """Test token search functionality"""
        # Setup mock response
        mock_response.json.return_value = {
            "pairs": [
                {
                    "chainId": "solana",
                    "baseToken": {"symbol": "BONK", "name": "Bonk"},
                    "pairAddress": "bonk_pair"
                },
                {
                    "chainId": "ethereum",  # Should be filtered
                    "baseToken": {"symbol": "BONK", "name": "Bonk ETH"}
                }
            ]
        }
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = DexScreenerClient(mock_session)
        results = await client.search_tokens("bonk")
        
        assert results is not None
        assert len(results) == 1  # Only Solana result
        assert results[0]["baseToken"]["symbol"] == "BONK"
    
    @pytest.mark.asyncio
    async def test_batch_get_prices(self, mock_session, mock_response):
        """Test batch price fetching"""
        tokens = ["token1", "token2", "token3"]
        
        # Mock different responses for each token
        responses = [
            {"pairs": [{"chainId": "solana", "baseToken": {"address": "token1"}, 
                       "quoteToken": {"address": USDC_MINT}, "priceUsd": "1.0",
                       "liquidity": {"usd": 100}}]},
            {"pairs": [{"chainId": "solana", "baseToken": {"address": "token2"},
                       "quoteToken": {"address": USDC_MINT}, "priceUsd": "2.0",
                       "liquidity": {"usd": 200}}]},
            {"pairs": []}  # No pairs for token3
        ]
        
        call_count = 0
        async def mock_json():
            nonlocal call_count
            result = responses[call_count % len(responses)]
            call_count += 1
            return result
        
        mock_response.json = mock_json
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = DexScreenerClient(mock_session)
        results = await client.batch_get_prices(tokens)
        
        assert len(results) == 3
        assert results["token1"][0] == Decimal("1.0")
        assert results["token2"][0] == Decimal("2.0")
        assert results["token3"] is None
    
    @pytest.mark.asyncio
    async def test_retry_logic(self, mock_session, mock_response):
        """Test retry logic on timeout"""
        # First call times out, second succeeds
        timeout_response = AsyncMock(side_effect=asyncio.TimeoutError())
        success_response = mock_response
        success_response.json.return_value = {"pairs": []}
        
        mock_session.get.side_effect = [timeout_response, success_response]
        
        client = DexScreenerClient(mock_session)
        
        # Should retry and eventually succeed
        result = await client.get_token_pairs(SOL_MINT)
        assert result is None  # Empty pairs but no error
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test context manager functionality"""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = MagicMock()
            mock_session.close = AsyncMock()
            mock_session_class.return_value = mock_session
            
            async with DexScreenerClient() as client:
                assert client.session is mock_session
                assert client._owns_session is True
            
            # Verify session was closed
            mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_dexscreener_price_convenience(self):
        """Test convenience function for getting price"""
        with patch('src.lib.dexscreener_client.DexScreenerClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get_token_price.return_value = (Decimal("150.0"), {"test": "data"})
            mock_client_class.return_value = mock_client
            
            result = await get_dexscreener_price(SOL_MINT, USDC_MINT)
            
            assert result is not None
            price, source, metadata = result
            assert price == Decimal("150.0")
            assert source == "dexscreener"
            assert metadata == {"test": "data"}
    
    @pytest.mark.asyncio
    async def test_get_market_cap_convenience(self):
        """Test convenience function for market cap"""
        with patch('src.lib.dexscreener_client.DexScreenerClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get_market_cap.return_value = (86000000000.0, "dexscreener_mc")
            mock_client_class.return_value = mock_client
            
            result = await get_market_cap_from_dexscreener(SOL_MINT)
            
            assert result is not None
            market_cap, source = result
            assert market_cap == 86000000000.0
            assert source == "dexscreener_mc"
    
    def test_client_stats(self):
        """Test client statistics"""
        client = DexScreenerClient()
        client.request_count = 5
        
        stats = client.get_stats()
        assert stats["request_count"] == 5
        assert stats["base_url"] == "https://api.dexscreener.com/latest"
        assert stats["rate_limited"] is False


if __name__ == "__main__":
    # Run basic tests
    print("Testing DexScreenerClient...")
    
    async def run_tests():
        test = TestDexScreenerClient()
        
        # Create mocks manually
        mock_session = MagicMock()
        mock_session.get = AsyncMock()
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {}
        mock_response.json = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        
        # Test successful price fetch
        await test.test_get_token_price_success(mock_session, mock_response)
        print("✅ Token price fetch test passed")
        
        # Test market cap
        await test.test_get_market_cap_success(mock_session, mock_response)
        print("✅ Market cap test passed")
        
        # Test search
        await test.test_search_tokens(mock_session, mock_response)
        print("✅ Token search test passed")
    
    asyncio.run(run_tests())
    
    print("\n✅ All basic tests passed!")
    print("\nRun 'pytest tests/test_dexscreener_client.py -v' for full test suite") 