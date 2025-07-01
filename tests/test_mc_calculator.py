#!/usr/bin/env python3
"""
Test MC calculator functionality
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.lib.mc_calculator import (
    MarketCapCalculator,
    MarketCapResult,
    calculate_market_cap,
    CONFIDENCE_HIGH,
    CONFIDENCE_EST,
    CONFIDENCE_UNAVAILABLE,
    SOL_MINT,
    USDC_MINT
)
from src.lib.mc_cache import MarketCapData


class TestMarketCapCalculator:
    """Test MarketCapCalculator class"""
    
    @pytest.fixture
    def mock_cache(self):
        """Create a mock cache"""
        cache = MagicMock()
        cache.get = MagicMock(return_value=None)
        cache.set = MagicMock(return_value=True)
        return cache
    
    @pytest.mark.asyncio
    async def test_primary_sources_success(self, mock_cache):
        """Test successful MC calculation with primary sources"""
        calculator = MarketCapCalculator(mock_cache)
        
        # Mock supply and price
        with patch('src.lib.mc_calculator.get_token_supply_at_slot', AsyncMock(return_value=Decimal("1000000"))):
            with patch('src.lib.mc_calculator.get_amm_price', AsyncMock(
                return_value=(Decimal("0.50"), "raydium", Decimal("100000"))
            )):
                result = await calculator.calculate_market_cap("test_token", slot=12345)
                
                assert result.value == 500000.0  # 1M * 0.50
                assert result.confidence == CONFIDENCE_HIGH
                assert result.source == "helius_raydium"
                assert result.supply == 1000000.0
                assert result.price == 0.50
    
    @pytest.mark.asyncio
    async def test_no_supply_data(self, mock_cache):
        """Test when supply data is not available"""
        calculator = MarketCapCalculator(mock_cache)
        
        # Mock no supply
        with patch('src.lib.mc_calculator.get_token_supply_at_slot', AsyncMock(return_value=None)):
            with patch('src.lib.mc_calculator.get_market_cap_from_birdeye', AsyncMock(return_value=None)):
                with patch('src.lib.mc_calculator.get_birdeye_price', AsyncMock(return_value=None)):
                    result = await calculator.calculate_market_cap("test_token")
                    
                    assert result.value is None
                    assert result.confidence == CONFIDENCE_UNAVAILABLE
                    assert result.source is None
    
    @pytest.mark.asyncio
    async def test_no_price_data(self, mock_cache):
        """Test when price data is not available"""
        calculator = MarketCapCalculator(mock_cache)
        
        # Mock supply but no price
        with patch('src.lib.mc_calculator.get_token_supply_at_slot', AsyncMock(return_value=Decimal("1000000"))):
            with patch('src.lib.mc_calculator.get_amm_price', AsyncMock(return_value=None)):
                with patch('src.lib.mc_calculator.get_market_cap_from_birdeye', AsyncMock(return_value=None)):
                    with patch('src.lib.mc_calculator.get_birdeye_price', AsyncMock(return_value=None)):
                        result = await calculator.calculate_market_cap("test_token")
                        
                        assert result.value is None
                        assert result.confidence == CONFIDENCE_UNAVAILABLE
    
    @pytest.mark.asyncio
    async def test_birdeye_direct_mc_fallback(self, mock_cache):
        """Test fallback to Birdeye direct market cap"""
        calculator = MarketCapCalculator(mock_cache)
        
        # Primary sources fail
        with patch('src.lib.mc_calculator.get_token_supply_at_slot', AsyncMock(return_value=Decimal("1000000"))):
            with patch('src.lib.mc_calculator.get_amm_price', AsyncMock(return_value=None)):
                # Birdeye has direct MC
                with patch('src.lib.mc_calculator.get_market_cap_from_birdeye', AsyncMock(
                    return_value=(86000000000.0, "birdeye_mc")
                )):
                    result = await calculator.calculate_market_cap("test_token", timestamp=12345)
                    
                    assert result.value == 86000000000.0
                    assert result.confidence == CONFIDENCE_EST
                    assert result.source == "birdeye_mc"
                    assert result.supply is None  # Not available from direct MC
                    assert result.price is None
    
    @pytest.mark.asyncio
    async def test_birdeye_price_fallback(self, mock_cache):
        """Test fallback to Birdeye price + Helius supply"""
        calculator = MarketCapCalculator(mock_cache)
        
        # Primary AMM price fails, but supply works
        with patch('src.lib.mc_calculator.get_token_supply_at_slot', AsyncMock(return_value=Decimal("1000000"))):
            with patch('src.lib.mc_calculator.get_amm_price', AsyncMock(return_value=None)):
                # No direct MC from Birdeye
                with patch('src.lib.mc_calculator.get_market_cap_from_birdeye', AsyncMock(return_value=None)):
                    # But Birdeye has price
                    with patch('src.lib.mc_calculator.get_birdeye_price', AsyncMock(
                        return_value=(Decimal("2.50"), "birdeye_current", {"liquidity": 50000})
                    )):
                        # DexScreener not used since Birdeye works
                        with patch('src.lib.mc_calculator.get_market_cap_from_dexscreener', AsyncMock(return_value=None)):
                            with patch('src.lib.mc_calculator.get_dexscreener_price', AsyncMock(return_value=None)):
                                result = await calculator.calculate_market_cap("test_token", timestamp=12345)
                                
                                assert result.value == 2500000.0  # 1M * 2.50
                                assert result.confidence == CONFIDENCE_EST
                                assert result.source == "helius_birdeye_current"
                                assert result.supply == 1000000.0
                                assert result.price == 2.50
    
    @pytest.mark.asyncio
    async def test_dexscreener_direct_mc_fallback(self, mock_cache):
        """Test fallback to DexScreener direct market cap"""
        calculator = MarketCapCalculator(mock_cache)
        
        # Primary sources and Birdeye fail
        with patch('src.lib.mc_calculator.get_token_supply_at_slot', AsyncMock(return_value=Decimal("1000000"))):
            with patch('src.lib.mc_calculator.get_amm_price', AsyncMock(return_value=None)):
                with patch('src.lib.mc_calculator.get_market_cap_from_birdeye', AsyncMock(return_value=None)):
                    with patch('src.lib.mc_calculator.get_birdeye_price', AsyncMock(return_value=None)):
                        # DexScreener has direct MC
                        with patch('src.lib.mc_calculator.get_market_cap_from_dexscreener', AsyncMock(
                            return_value=(45000000000.0, "dexscreener_mc")
                        )):
                            result = await calculator.calculate_market_cap("test_token", timestamp=12345)
                            
                            assert result.value == 45000000000.0
                            assert result.confidence == CONFIDENCE_EST
                            assert result.source == "dexscreener_mc"
                            assert result.supply is None  # Not available from direct MC
                            assert result.price is None
    
    @pytest.mark.asyncio
    async def test_dexscreener_price_fallback(self, mock_cache):
        """Test fallback to DexScreener price + Helius supply"""
        calculator = MarketCapCalculator(mock_cache)
        
        # All other sources fail except DexScreener price
        with patch('src.lib.mc_calculator.get_token_supply_at_slot', AsyncMock(return_value=Decimal("1000000"))):
            with patch('src.lib.mc_calculator.get_amm_price', AsyncMock(return_value=None)):
                with patch('src.lib.mc_calculator.get_market_cap_from_birdeye', AsyncMock(return_value=None)):
                    with patch('src.lib.mc_calculator.get_birdeye_price', AsyncMock(return_value=None)):
                        with patch('src.lib.mc_calculator.get_market_cap_from_dexscreener', AsyncMock(return_value=None)):
                            # DexScreener has price
                            with patch('src.lib.mc_calculator.get_dexscreener_price', AsyncMock(
                                return_value=(Decimal("3.75"), "dexscreener", {"liquidity": 25000})
                            )):
                                result = await calculator.calculate_market_cap("test_token", timestamp=12345)
                                
                                assert result.value == 3750000.0  # 1M * 3.75
                                assert result.confidence == CONFIDENCE_EST
                                assert result.source == "helius_dexscreener"
                                assert result.supply == 1000000.0
                                assert result.price == 3.75
    
    @pytest.mark.asyncio
    async def test_cache_hit(self, mock_cache):
        """Test cache hit scenario"""
        # Setup cache hit
        cached_data = MarketCapData(
            value=123456.78,
            confidence=CONFIDENCE_HIGH,
            timestamp=int(datetime.now().timestamp()),
            source="cached_source"
        )
        mock_cache.get.return_value = cached_data
        
        calculator = MarketCapCalculator(mock_cache)
        result = await calculator.calculate_market_cap("test_token", timestamp=12345)
        
        assert result.value == 123456.78
        assert result.confidence == CONFIDENCE_HIGH
        assert result.source == "cache_cached_source"
        
        # Verify cache was checked
        mock_cache.get.assert_called_once_with("test_token", 12345)
    
    @pytest.mark.asyncio
    async def test_cache_miss_and_store(self, mock_cache):
        """Test cache miss followed by successful calculation and storage"""
        mock_cache.get.return_value = None
        calculator = MarketCapCalculator(mock_cache)
        
        timestamp = int(datetime.now().timestamp())
        
        # Mock primary sources
        with patch('src.lib.mc_calculator.get_token_supply_at_slot', AsyncMock(return_value=Decimal("1000000"))):
            with patch('src.lib.mc_calculator.get_amm_price', AsyncMock(
                return_value=(Decimal("2.0"), "orca", Decimal("500000"))
            )):
                result = await calculator.calculate_market_cap("test_token", timestamp=timestamp)
                
                assert result.value == 2000000.0
                
                # Verify cache was stored
                mock_cache.set.assert_called_once()
                call_args = mock_cache.set.call_args
                assert call_args[0][0] == "test_token"
                assert call_args[0][1] == timestamp
                stored_data = call_args[0][2]
                assert stored_data.value == 2000000.0
                assert stored_data.confidence == CONFIDENCE_HIGH
    
    @pytest.mark.asyncio
    async def test_batch_market_caps(self, mock_cache):
        """Test batch MC calculation"""
        calculator = MarketCapCalculator(mock_cache)
        
        # Mock different results for different tokens
        async def mock_supply(mint, slot):
            if mint == "token1":
                return Decimal("1000000")
            elif mint == "token2":
                return Decimal("5000000")
            return None
        
        async def mock_price(mint, quote, slot):
            if mint == "token1":
                return (Decimal("1.0"), "raydium", Decimal("100000"))
            elif mint == "token2":
                return (Decimal("0.1"), "orca", Decimal("50000"))
            return None
        
        with patch('src.lib.mc_calculator.get_token_supply_at_slot', mock_supply):
            with patch('src.lib.mc_calculator.get_amm_price', mock_price):
                with patch('src.lib.mc_calculator.get_market_cap_from_birdeye', AsyncMock(return_value=None)):
                    with patch('src.lib.mc_calculator.get_birdeye_price', AsyncMock(return_value=None)):
                        requests = [
                            ("token1", 100, 1000),
                            ("token2", 200, 2000),
                            ("token3", 300, 3000),  # Will fail
                        ]
                        
                        results = await calculator.get_batch_market_caps(requests)
                        
                        assert len(results) == 3
                        assert results["token1"].value == 1000000.0
                        assert results["token2"].value == 500000.0
                        assert results["token3"].value is None
                        assert results["token3"].confidence == CONFIDENCE_UNAVAILABLE
    
    @pytest.mark.asyncio
    async def test_sol_market_cap(self):
        """Test SOL market cap calculation"""
        # SOL has special handling in supply fetcher
        with patch('src.lib.mc_calculator.get_token_supply_at_slot', AsyncMock(
            return_value=Decimal("574207458.192302894")
        )):
            with patch('src.lib.mc_calculator.get_amm_price', AsyncMock(
                return_value=(Decimal("150.0"), "raydium", Decimal("10000000"))
            )):
                result = await calculate_market_cap(SOL_MINT, use_cache=False)
                
                assert result.value is not None
                assert result.value == pytest.approx(86131118728.8, rel=0.01)
                assert result.confidence == CONFIDENCE_HIGH
    
    @pytest.mark.asyncio
    async def test_convenience_function_with_cache_error(self):
        """Test convenience function when cache is not available"""
        with patch('src.lib.mc_calculator.get_cache', side_effect=Exception("Cache error")):
            with patch('src.lib.mc_calculator.get_token_supply_at_slot', AsyncMock(
                return_value=Decimal("1000")
            )):
                with patch('src.lib.mc_calculator.get_amm_price', AsyncMock(
                    return_value=(Decimal("5.0"), "test", Decimal("1000"))
                )):
                    # Should still work without cache
                    result = await calculate_market_cap("test_token", use_cache=True)
                    
                    assert result.value == 5000.0
                    assert result.confidence == CONFIDENCE_HIGH
    
    @pytest.mark.asyncio
    async def test_primary_source_exception_handling(self, mock_cache):
        """Test exception handling in primary sources"""
        calculator = MarketCapCalculator(mock_cache)
        
        # Mock exception in supply fetcher
        with patch('src.lib.mc_calculator.get_token_supply_at_slot', 
                  AsyncMock(side_effect=Exception("RPC error"))):
            with patch('src.lib.mc_calculator.get_market_cap_from_birdeye', AsyncMock(return_value=None)):
                with patch('src.lib.mc_calculator.get_birdeye_price', AsyncMock(return_value=None)):
                    result = await calculator.calculate_market_cap("test_token")
                    
                    assert result.value is None
                    assert result.confidence == CONFIDENCE_UNAVAILABLE
    
    @pytest.mark.asyncio
    async def test_fallback_exception_handling(self, mock_cache):
        """Test exception handling in fallback sources"""
        calculator = MarketCapCalculator(mock_cache)
        
        # Primary sources fail
        with patch('src.lib.mc_calculator.get_token_supply_at_slot', AsyncMock(return_value=Decimal("1000000"))):
            with patch('src.lib.mc_calculator.get_amm_price', AsyncMock(return_value=None)):
                # Birdeye fails with exception
                with patch('src.lib.mc_calculator.get_market_cap_from_birdeye', 
                          AsyncMock(side_effect=Exception("Birdeye error"))):
                    result = await calculator.calculate_market_cap("test_token")
                    
                    assert result.value is None
                    assert result.confidence == CONFIDENCE_UNAVAILABLE
    
    @pytest.mark.asyncio
    async def test_cache_exception_handling(self):
        """Test exception handling in cache operations"""
        # Mock cache that throws on get
        mock_cache = MagicMock()
        mock_cache.get.side_effect = Exception("Redis error")
        
        calculator = MarketCapCalculator(mock_cache)
        
        # Should continue to primary sources despite cache error
        with patch('src.lib.mc_calculator.get_token_supply_at_slot', AsyncMock(
            return_value=Decimal("1000")
        )):
            with patch('src.lib.mc_calculator.get_amm_price', AsyncMock(
                return_value=(Decimal("1.0"), "test", Decimal("1000"))
            )):
                result = await calculator.calculate_market_cap("test_token", timestamp=12345)
                
                assert result.value == 1000.0
                assert result.confidence == CONFIDENCE_HIGH
    
    def test_market_cap_result_dataclass(self):
        """Test MarketCapResult dataclass"""
        result = MarketCapResult(
            value=1000000.0,
            confidence=CONFIDENCE_HIGH,
            source="test_source",
            supply=1000000.0,
            price=1.0,
            timestamp=12345
        )
        
        assert result.value == 1000000.0
        assert result.confidence == CONFIDENCE_HIGH
        assert result.source == "test_source"
        assert result.supply == 1000000.0
        assert result.price == 1.0
        assert result.timestamp == 12345

    @pytest.mark.asyncio
    @patch('src.lib.mc_calculator.get_jupiter_price')
    @patch('src.lib.mc_calculator.get_dexscreener_price')
    @patch('src.lib.mc_calculator.get_market_cap_from_dexscreener')
    @patch('src.lib.mc_calculator.get_birdeye_price')
    @patch('src.lib.mc_calculator.get_market_cap_from_birdeye')
    @patch('src.lib.mc_calculator.get_amm_price')
    @patch('src.lib.mc_calculator.get_token_supply_at_slot')
    async def test_jupiter_fallback(
        self,
        mock_get_supply,
        mock_get_amm_price,
        mock_get_market_cap_from_birdeye,
        mock_get_birdeye_price,
        mock_get_market_cap_from_dexscreener,
        mock_get_dexscreener_price,
        mock_get_jupiter_price
    ):
        """Test Jupiter fallback when AMM and Birdeye fail"""
        # Setup - supply available but AMM and Birdeye fail
        mock_get_supply.return_value = Decimal("1000000")  # 1M tokens
        mock_get_amm_price.return_value = None  # No AMM price
        mock_get_market_cap_from_birdeye.return_value = None  # No direct MC
        mock_get_birdeye_price.return_value = None  # No Birdeye price
        
        # Jupiter succeeds
        mock_get_jupiter_price.return_value = (
            Decimal("0.5"),  # price
            "jupiter_quote",  # source
            {"priceImpactPct": 0.01}  # metadata
        )
        
        calculator = MarketCapCalculator()
        result = await calculator.calculate_market_cap("test_token")
        
        assert result.value == 500000  # 1M * 0.5
        assert result.confidence == "est"
        assert result.source == "helius_jupiter_quote"
        assert result.supply == 1000000
        assert result.price == 0.5
        
        # Verify Jupiter was called with both quote and price API
        assert mock_get_jupiter_price.call_count == 1
        mock_get_jupiter_price.assert_called_with("test_token", USDC_MINT, use_quote=True)
    
    @pytest.mark.asyncio
    @patch('src.lib.mc_calculator.get_jupiter_price')
    @patch('src.lib.mc_calculator.get_dexscreener_price')  
    @patch('src.lib.mc_calculator.get_market_cap_from_dexscreener')
    @patch('src.lib.mc_calculator.get_birdeye_price')
    @patch('src.lib.mc_calculator.get_market_cap_from_birdeye')
    @patch('src.lib.mc_calculator.get_amm_price')
    @patch('src.lib.mc_calculator.get_token_supply_at_slot')
    async def test_jupiter_quote_fallback_to_price_api(
        self,
        mock_get_supply,
        mock_get_amm_price,
        mock_get_market_cap_from_birdeye,
        mock_get_birdeye_price,
        mock_get_market_cap_from_dexscreener,
        mock_get_dexscreener_price,
        mock_get_jupiter_price
    ):
        """Test Jupiter falls back from quote to price API"""
        # Setup - supply available but AMM and Birdeye fail
        mock_get_supply.return_value = Decimal("1000000")
        mock_get_amm_price.return_value = None
        mock_get_market_cap_from_birdeye.return_value = None
        mock_get_birdeye_price.return_value = None
        
        # Jupiter quote API fails, price API succeeds
        mock_get_jupiter_price.side_effect = [
            None,  # Quote API fails
            (Decimal("0.5"), "jupiter_price", {})  # Price API succeeds
        ]
        
        calculator = MarketCapCalculator()
        result = await calculator.calculate_market_cap("test_token")
        
        assert result.value == 500000
        assert result.confidence == "est"
        assert result.source == "helius_jupiter_price"
        
        # Verify both APIs were tried
        assert mock_get_jupiter_price.call_count == 2
        mock_get_jupiter_price.assert_any_call("test_token", USDC_MINT, use_quote=True)
        mock_get_jupiter_price.assert_any_call("test_token", USDC_MINT, use_quote=False)


if __name__ == "__main__":
    # Run basic tests
    print("Testing MarketCapCalculator...")
    
    async def run_tests():
        test = TestMarketCapCalculator()
        
        # Create a mock cache manually
        mock_cache = MagicMock()
        mock_cache.get = MagicMock(return_value=None)
        mock_cache.set = MagicMock(return_value=True)
        
        # Test primary sources
        await test.test_primary_sources_success(mock_cache)
        print("✅ Primary sources test passed")
        
        # Test cache hit
        await test.test_cache_hit(mock_cache)
        print("✅ Cache hit test passed")
        
        # Test Birdeye fallback
        await test.test_birdeye_direct_mc_fallback(mock_cache)
        print("✅ Birdeye direct MC fallback test passed")
        
        # Test SOL
        await test.test_sol_market_cap()
        print("✅ SOL market cap test passed")
    
    asyncio.run(run_tests())
    
    print("\n✅ All basic tests passed!")
    print("\nRun 'pytest tests/test_mc_calculator.py -v' for full test suite") 