#!/usr/bin/env python3
"""
Test Helius supply fetcher functionality
"""

import pytest
import asyncio
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.lib.helius_supply import (
    HeliusSupplyFetcher,
    get_token_supply_at_slot,
    SOL_MINT,
    SOL_SUPPLY
)


class TestHeliusSupplyFetcher:
    """Test HeliusSupplyFetcher class"""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock aiohttp session"""
        session = MagicMock()
        session.post = MagicMock()
        return session
    
    def setup_mock_response(self, mock_session, response):
        """Helper to set up mock response with async context manager"""
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.post.return_value = mock_context
    
    @pytest.mark.asyncio
    async def test_sol_special_case(self):
        """Test that SOL returns fixed supply"""
        fetcher = HeliusSupplyFetcher()
        
        # SOL should return fixed supply without RPC call
        supply = await fetcher.get_token_supply(SOL_MINT)
        assert supply == SOL_SUPPLY
        assert fetcher.request_count == 0  # No RPC request made
    
    @pytest.mark.asyncio
    async def test_get_token_supply_success(self, mock_session):
        """Test successful token supply fetch"""
        # Mock response
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "value": {
                    "amount": "5034935318581863",
                    "decimals": 6,
                    "uiAmount": 5034935318.581863,
                    "uiAmountString": "5034935318.581863"
                }
            }
        })
        mock_resp.raise_for_status = MagicMock()
        
        self.setup_mock_response(mock_session, mock_resp)
        
        fetcher = HeliusSupplyFetcher(session=mock_session)
        
        # Test USDC supply
        usdc_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        supply = await fetcher.get_token_supply(usdc_mint)
        
        assert supply == Decimal("5034935318.581863")
        assert fetcher.request_count == 1
        
        # Verify RPC call
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert "getTokenSupply" in str(call_args)
        assert usdc_mint in str(call_args)
    
    @pytest.mark.asyncio
    async def test_get_token_supply_with_slot(self, mock_session):
        """Test token supply fetch at specific slot"""
        # Mock response
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "context": {"slot": 250000000},
                "value": {
                    "amount": "1000000000",
                    "decimals": 6,
                    "uiAmountString": "1000.0"
                }
            }
        })
        mock_resp.raise_for_status = MagicMock()
        
        self.setup_mock_response(mock_session, mock_resp)
        
        fetcher = HeliusSupplyFetcher(session=mock_session)
        
        # Test with specific slot
        supply = await fetcher.get_token_supply("test_mint", slot=250000000)
        
        assert supply == Decimal("1000.0")
        
        # Verify slot parameter in RPC call
        call_args = mock_session.post.call_args
        json_data = call_args[1]["json"]
        assert len(json_data["params"]) == 2
        assert json_data["params"][1]["minContextSlot"] == 250000000
    
    @pytest.mark.asyncio
    async def test_get_token_supply_error(self, mock_session):
        """Test handling of RPC errors"""
        # Mock error response
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "jsonrpc": "2.0",
            "id": 1,
            "error": {
                "code": -32602,
                "message": "Invalid params: missing field `mint`"
            }
        })
        mock_resp.raise_for_status = MagicMock()
        
        self.setup_mock_response(mock_session, mock_resp)
        
        fetcher = HeliusSupplyFetcher(session=mock_session)
        
        # Should return None on error
        supply = await fetcher.get_token_supply("invalid_mint")
        assert supply is None
    
    @pytest.mark.asyncio
    async def test_rate_limit_retry(self, mock_session):
        """Test rate limit handling with retry"""
        # First response: rate limited
        mock_resp_429 = MagicMock()
        mock_resp_429.status = 429
        mock_resp_429.headers = {"Retry-After": "1"}
        
        # Second response: success
        mock_resp_200 = MagicMock()
        mock_resp_200.status = 200
        mock_resp_200.json = AsyncMock(return_value={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "value": {
                    "uiAmountString": "100.0"
                }
            }
        })
        mock_resp_200.raise_for_status = MagicMock()
        
        # Mock to return 429 first, then 200
        mock_context_429 = MagicMock()
        mock_context_429.__aenter__ = AsyncMock(return_value=mock_resp_429)
        mock_context_429.__aexit__ = AsyncMock(return_value=None)
        
        mock_context_200 = MagicMock()
        mock_context_200.__aenter__ = AsyncMock(return_value=mock_resp_200)
        mock_context_200.__aexit__ = AsyncMock(return_value=None)
        
        mock_session.post.side_effect = [mock_context_429, mock_context_200]
        
        fetcher = HeliusSupplyFetcher(session=mock_session)
        
        # Should retry and succeed
        supply = await fetcher.get_token_supply("test_mint")
        assert supply == Decimal("100.0")
        assert fetcher.request_count == 2  # Initial + retry
    
    @pytest.mark.asyncio
    async def test_batch_supply_fetch(self, mock_session):
        """Test batch supply fetching"""
        # Mock responses for batch
        responses = []
        for i in range(3):
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "value": {
                        "uiAmountString": f"{(i + 1) * 100}.0"
                    }
                }
            })
            mock_resp.raise_for_status = MagicMock()
            responses.append(mock_resp)
        
        # SOL will be handled specially, so only 2 RPC calls
        mock_contexts = []
        for resp in responses[:2]:
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=resp)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_contexts.append(mock_context)
        
        mock_session.post.side_effect = mock_contexts
        
        fetcher = HeliusSupplyFetcher(session=mock_session)
        
        # Test batch
        requests = [
            (SOL_MINT, None),  # Special case
            ("mint1", None),
            ("mint2", 250000000),
        ]
        
        results = await fetcher.get_token_supply_batch(requests)
        
        assert len(results) == 3
        assert results[(SOL_MINT, None)] == SOL_SUPPLY  # Fixed value
        assert results[("mint1", None)] == Decimal("100.0")
        assert results[("mint2", 250000000)] == Decimal("200.0")
    
    @pytest.mark.asyncio
    async def test_get_token_metadata(self, mock_session):
        """Test token metadata fetching"""
        # Mock metadata response
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "value": {
                    "data": {
                        "parsed": {
                            "info": {
                                "decimals": 6,
                                "supply": "5034935318581863",
                                "mintAuthority": "BJE5MMbqXjVwjAF4c8FbKKPKLi1BLNK4vwJnmi7xyF8z",
                                "freezeAuthority": None,
                                "isInitialized": True
                            }
                        }
                    }
                }
            }
        })
        mock_resp.raise_for_status = MagicMock()
        
        self.setup_mock_response(mock_session, mock_resp)
        
        fetcher = HeliusSupplyFetcher(session=mock_session)
        
        metadata = await fetcher.get_token_metadata("test_mint")
        
        assert metadata is not None
        assert metadata["decimals"] == 6
        assert metadata["supply"] == "5034935318581863"
        assert metadata["isInitialized"] is True
    
    @pytest.mark.asyncio
    async def test_no_helius_key_error(self):
        """Test error when HELIUS_KEY not set"""
        # Temporarily remove HELIUS_KEY
        original_key = os.environ.pop("HELIUS_KEY", None)
        
        try:
            async with HeliusSupplyFetcher() as fetcher:
                with pytest.raises(ValueError, match="HELIUS_KEY environment variable not set"):
                    await fetcher.get_token_supply("test_mint")
        finally:
            # Restore key if it existed
            if original_key:
                os.environ["HELIUS_KEY"] = original_key
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager"""
        async with HeliusSupplyFetcher() as fetcher:
            assert fetcher.session is not None
            assert fetcher._owns_session is True
        
        # Session should be closed after exit
        # (can't easily test this without mocking)
    
    @pytest.mark.asyncio
    async def test_convenience_function(self, mock_session):
        """Test get_token_supply_at_slot convenience function"""
        # Mock response
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "value": {
                    "uiAmountString": "500.0"
                }
            }
        })
        mock_resp.raise_for_status = MagicMock()
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session_instance = MagicMock()
            # Set up mock response with async context manager
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            mock_session_instance.post.return_value = mock_context
            mock_session_instance.close = AsyncMock()
            mock_session_class.return_value = mock_session_instance
            
            # Test convenience function
            supply = await get_token_supply_at_slot("test_mint", 123456)
            
            assert supply == Decimal("500.0")
    
    def test_get_stats(self):
        """Test statistics tracking"""
        fetcher = HeliusSupplyFetcher()
        fetcher.request_count = 5
        
        stats = fetcher.get_stats()
        assert stats["request_count"] == 5
        assert stats["rpc_endpoint"] == "https://mainnet.helius-rpc.com"


if __name__ == "__main__":
    # Set test HELIUS_KEY if not set
    if not os.getenv("HELIUS_KEY"):
        os.environ["HELIUS_KEY"] = "test_key"
    
    # Run tests
    print("Testing HeliusSupplyFetcher...")
    asyncio.run(TestHeliusSupplyFetcher().test_sol_special_case())
    print("✅ SOL special case test passed")
    
    print("\n✅ All basic tests passed!")
    print("\nRun 'pytest tests/test_helius_supply.py -v' for full test suite") 