#!/usr/bin/env python3
"""
Test Jupiter client functionality
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

from src.lib.jupiter_client import (
    JupiterClient,
    get_jupiter_price,
    SOL_MINT,
    USDC_MINT,
    TOKEN_DECIMALS
)


class TestJupiterClient:
    """Test JupiterClient class"""
    
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
    async def test_get_token_price_success(self, mock_session, mock_response):
        """Test successful token price fetch from Price API"""
        # Setup mock response
        mock_response.json.return_value = {
            "data": {
                SOL_MINT: {
                    "id": SOL_MINT,
                    "price": 150.50,
                    "vsToken": USDC_MINT,
                    "vsTokenSymbol": "USDC",
                    "confidence": 0.99,
                    "depth": {
                        "buy": 1000000,
                        "sell": 1000000
                    }
                }
            },
            "timeTaken": 0.05
        }
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = JupiterClient(mock_session)
        result = await client.get_token_price(SOL_MINT)
        
        assert result is not None
        price, metadata = result
        assert price == Decimal("150.50")
        assert metadata["vsToken"] == USDC_MINT
        assert metadata["confidence"] == 0.99
        assert metadata["source"] == "jupiter_price_v4"
    
    @pytest.mark.asyncio
    async def test_get_token_price_not_found(self, mock_session, mock_response):
        """Test token price not found"""
        mock_response.json.return_value = {
            "data": {},
            "timeTaken": 0.05
        }
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = JupiterClient(mock_session)
        result = await client.get_token_price("invalid_token")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_quote_success(self, mock_session, mock_response):
        """Test successful swap quote"""
        # Setup mock response
        mock_response.json.return_value = {
            "inputMint": USDC_MINT,
            "outputMint": SOL_MINT,
            "inAmount": "100000000",  # 100 USDC
            "outAmount": "664451",    # ~0.664 SOL
            "priceImpactPct": 0.01,
            "routePlan": [
                {
                    "ammKey": "raydium_pool",
                    "label": "Raydium",
                    "inputMint": USDC_MINT,
                    "outputMint": SOL_MINT,
                    "inAmount": "100000000",
                    "outAmount": "664451"
                }
            ]
        }
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = JupiterClient(mock_session)
        quote = await client.get_quote(
            input_mint=USDC_MINT,
            output_mint=SOL_MINT,
            amount=100000000
        )
        
        assert quote is not None
        assert quote["inAmount"] == "100000000"
        assert quote["outAmount"] == "664451"
        assert quote["priceImpactPct"] == 0.01
        assert len(quote["routePlan"]) == 1
    
    @pytest.mark.asyncio
    async def test_get_token_price_via_quote(self, mock_session, mock_response):
        """Test price calculation via quote API"""
        # Setup mock quote response
        mock_response.json.return_value = {
            "inputMint": USDC_MINT,
            "outputMint": SOL_MINT,
            "inAmount": "100000000",   # 100 USDC (6 decimals)
            "outAmount": "664451686",  # ~0.664 SOL (9 decimals)
            "priceImpactPct": 0.01,
            "routePlan": []
        }
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = JupiterClient(mock_session)
        result = await client.get_token_price_via_quote(SOL_MINT)
        
        assert result is not None
        price, metadata = result
        
        # Price should be ~150.50 (100 USDC / 0.664 SOL)
        assert price == pytest.approx(Decimal("150.50"), rel=0.01)
        assert metadata["inputMint"] == USDC_MINT
        assert metadata["outputMint"] == SOL_MINT
        assert metadata["priceImpactPct"] == 0.01
        assert metadata["source"] == "jupiter_quote_v6"
    
    @pytest.mark.asyncio
    async def test_batch_get_prices(self, mock_session, mock_response):
        """Test batch price fetching"""
        tokens = ["token1", "token2", "token3"]
        
        # Setup mock response
        mock_response.json.return_value = {
            "data": {
                "token1": {"price": 1.0, "vsToken": USDC_MINT},
                "token2": {"price": 2.0, "vsToken": USDC_MINT},
                # token3 not found
            }
        }
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = JupiterClient(mock_session)
        results = await client.batch_get_prices(tokens)
        
        assert len(results) == 3
        assert results["token1"] is not None
        assert results["token1"][0] == Decimal("1.0")
        assert results["token2"] is not None
        assert results["token2"][0] == Decimal("2.0")
        assert results["token3"] is None
    
    @pytest.mark.asyncio
    async def test_get_token_list(self, mock_session, mock_response):
        """Test token list fetching"""
        # Setup mock response - Jupiter returns a list directly
        mock_response.json.return_value = [
            {
                "address": SOL_MINT,
                "symbol": "SOL",
                "name": "Solana",
                "decimals": 9,
                "logoURI": "https://..."
            },
            {
                "address": USDC_MINT,
                "symbol": "USDC",
                "name": "USD Coin",
                "decimals": 6,
                "logoURI": "https://..."
            }
        ]
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = JupiterClient(mock_session)
        tokens = await client.get_token_list()
        
        assert tokens is not None
        assert len(tokens) == 2
        assert tokens[0]["symbol"] == "SOL"
        assert tokens[1]["symbol"] == "USDC"
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, mock_session, mock_response):
        """Test rate limiting behavior"""
        mock_response.json.return_value = {"data": {}}
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        client = JupiterClient(mock_session)
        
        # Make two rapid requests
        start_time = time.time()
        await client.get_token_price("token1")
        await client.get_token_price("token2")
        elapsed = time.time() - start_time
        
        # Should have delayed at least RATE_LIMIT_DELAY
        assert elapsed >= 0.1  # RATE_LIMIT_DELAY is 0.1
    
    @pytest.mark.asyncio
    async def test_retry_on_429(self, mock_session, mock_response):
        """Test retry on rate limit (429)"""
        # First response is 429, second is success
        rate_limited = MagicMock()
        rate_limited.status = 429
        rate_limited.headers = {"Retry-After": "1"}
        
        success = mock_response
        success.json.return_value = {
            "data": {SOL_MINT: {"price": 150.0}}
        }
        
        mock_session.get.return_value.__aenter__.side_effect = [rate_limited, success]
        
        client = JupiterClient(mock_session)
        
        start_time = time.time()
        result = await client.get_token_price(SOL_MINT)
        elapsed = time.time() - start_time
        
        assert result is not None
        assert elapsed >= 1.0  # Should have waited
    
    @pytest.mark.asyncio
    async def test_get_jupiter_price_convenience(self):
        """Test convenience function"""
        with patch('src.lib.jupiter_client.JupiterClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get_token_price.return_value = (Decimal("150.0"), {"test": "data"})
            mock_client_class.return_value = mock_client
            
            result = await get_jupiter_price(SOL_MINT)
            
            assert result is not None
            price, source, metadata = result
            assert price == Decimal("150.0")
            assert source == "jupiter_price"
            assert metadata == {"test": "data"}
    
    @pytest.mark.asyncio
    async def test_get_jupiter_price_via_quote(self):
        """Test convenience function with quote API"""
        with patch('src.lib.jupiter_client.JupiterClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get_token_price_via_quote.return_value = (Decimal("151.0"), {"quote": "data"})
            mock_client_class.return_value = mock_client
            
            result = await get_jupiter_price(SOL_MINT, use_quote=True)
            
            assert result is not None
            price, source, metadata = result
            assert price == Decimal("151.0")
            assert source == "jupiter_quote"
            assert metadata == {"quote": "data"}
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test context manager functionality"""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = MagicMock()
            mock_session.close = AsyncMock()
            mock_session_class.return_value = mock_session
            
            async with JupiterClient() as client:
                assert client.session is mock_session
                assert client._owns_session is True
            
            # Verify session was closed
            mock_session.close.assert_called_once()
    
    def test_client_stats(self):
        """Test client statistics"""
        client = JupiterClient()
        client.request_count = 5
        
        stats = client.get_stats()
        assert stats["request_count"] == 5
        assert stats["price_api"] == "https://price.jup.ag/v4"
        assert stats["quote_api"] == "https://quote-api.jup.ag/v6"


if __name__ == "__main__":
    # Run basic tests
    print("Testing JupiterClient...")
    
    async def run_tests():
        test = TestJupiterClient()
        
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
        
        # Test quote
        await test.test_get_quote_success(mock_session, mock_response)
        print("✅ Quote fetch test passed")
        
        # Test batch prices
        await test.test_batch_get_prices(mock_session, mock_response)
        print("✅ Batch price test passed")
    
    asyncio.run(run_tests())
    
    print("\n✅ All basic tests passed!")
    print("\nRun 'pytest tests/test_jupiter_client.py -v' for full test suite") 