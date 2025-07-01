#!/usr/bin/env python3
"""
Test AMM price reader functionality
"""

import pytest
import asyncio
from decimal import Decimal
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.lib.amm_price import (
    AMMPriceReader,
    get_amm_price,
    SOL_MINT,
    USDC_MINT,
    USDT_MINT,
    MIN_TVL_USD
)


class TestAMMPriceReader:
    """Test AMMPriceReader class"""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock aiohttp session"""
        session = MagicMock()
        return session
    
    def setup_mock_response(self, mock_session, response):
        """Helper to set up mock response with async context manager"""
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.post.return_value = mock_context
    
    @pytest.mark.asyncio
    async def test_sol_price_caching(self):
        """Test SOL price is cached for 60 seconds"""
        reader = AMMPriceReader()
        
        # Mock _get_price_from_stable_pool to return a price
        with patch.object(reader, '_get_price_from_stable_pool', AsyncMock(return_value=Decimal("150.0"))):
            # First call should fetch
            price1 = await reader.get_sol_price_usd()
            assert price1 == Decimal("150.0")
            
            # Change the mock return value
            with patch.object(reader, '_get_price_from_stable_pool', AsyncMock(return_value=Decimal("200.0"))):
                # Second call should use cache (still returns 150)
                price2 = await reader.get_sol_price_usd()
                assert price2 == Decimal("150.0")  # Still cached
    
    @pytest.mark.asyncio
    async def test_stable_coin_prices(self):
        """Test that stablecoins return $1"""
        reader = AMMPriceReader()
        
        # USDC should be $1
        usdc_price = await reader._get_price_from_stable_pool(USDC_MINT)
        assert usdc_price == Decimal("1.0")
        
        # USDT should be $1
        usdt_price = await reader._get_price_from_stable_pool(USDT_MINT)
        assert usdt_price == Decimal("1.0")
    
    @pytest.mark.asyncio
    async def test_price_calculation_from_reserves(self):
        """Test price calculation from pool reserves"""
        reader = AMMPriceReader()
        
        # Mock pool with SOL/USDC
        pool = {
            "token_a_mint": SOL_MINT,
            "token_b_mint": USDC_MINT,
            "token_a_amount": "1000000000000",  # 1000 SOL (9 decimals)
            "token_b_amount": "150000000000",   # 150k USDC (6 decimals)
            "token_a_decimals": 9,
            "token_b_decimals": 6
        }
        
        # Calculate SOL price in USDC
        price = await reader._calculate_price_from_pool(pool, SOL_MINT, USDC_MINT)
        assert price == Decimal("150.0")  # 150k USDC / 1000 SOL = 150 USDC per SOL
        
        # Calculate USDC price in SOL (inverse)
        inverse_price = await reader._calculate_price_from_pool(pool, USDC_MINT, SOL_MINT)
        assert inverse_price is not None
        expected_inverse = Decimal("1") / Decimal("150")
        assert abs(inverse_price - expected_inverse) < Decimal("0.0001")
    
    @pytest.mark.asyncio
    async def test_tvl_calculation(self):
        """Test TVL calculation in USD"""
        reader = AMMPriceReader()
        
        # Mock pool with SOL/USDC
        pool = {
            "token_a_mint": SOL_MINT,
            "token_b_mint": USDC_MINT,
            "token_a_amount": "1000000000000",  # 1000 SOL (9 decimals)
            "token_b_amount": "150000000000",   # 150k USDC (6 decimals)
            "token_a_decimals": 9,
            "token_b_decimals": 6
        }
        
        sol_price = Decimal("150.0")
        tvl = await reader._calculate_pool_tvl(pool, sol_price)
        
        # TVL = 1000 SOL * $150 + 150k USDC = $150k + $150k = $300k
        expected_tvl = Decimal("300000.0")
        assert tvl == expected_tvl
    
    @pytest.mark.asyncio
    async def test_tvl_filter(self):
        """Test that pools are filtered by minimum TVL"""
        reader = AMMPriceReader()
        
        # Mock pools with different TVLs
        pools = [
            {
                "program": "raydium",
                "token_a_mint": SOL_MINT,
                "token_b_mint": USDC_MINT,
                "token_a_amount": "10000000000",    # 10 SOL
                "token_b_amount": "1500000000",      # 1500 USDC
                "token_a_decimals": 9,
                "token_b_decimals": 6
            },
            {
                "program": "orca",
                "token_a_mint": SOL_MINT,
                "token_b_mint": USDC_MINT,
                "token_a_amount": "100000000000",    # 100 SOL
                "token_b_amount": "15000000000",     # 15k USDC
                "token_a_decimals": 9,
                "token_b_decimals": 6
            }
        ]
        
        # Mock methods
        with patch.object(reader, '_get_pools_for_pair', AsyncMock(return_value=pools)):
            with patch.object(reader, 'get_sol_price_usd', AsyncMock(return_value=Decimal("150.0"))):
                result = await reader.get_token_price(SOL_MINT, USDC_MINT)
                
                # Should return price from the second pool (higher TVL)
                assert result is not None
                price, source, tvl = result
                assert source == "orca"
                assert tvl == Decimal("30000.0")  # 100 SOL * $150 + 15k USDC
    
    @pytest.mark.asyncio
    async def test_no_pools_found(self):
        """Test behavior when no pools are found"""
        reader = AMMPriceReader()
        
        # Mock no pools
        with patch.object(reader, '_get_pools_for_pair', AsyncMock(return_value=[])):
            result = await reader.get_token_price("unknown_token", USDC_MINT)
            assert result is None
    
    @pytest.mark.asyncio
    async def test_no_valid_pools_above_tvl(self):
        """Test behavior when no pools meet minimum TVL"""
        reader = AMMPriceReader()
        
        # Mock pool with low TVL
        pools = [{
            "program": "raydium",
            "token_a_mint": SOL_MINT,
            "token_b_mint": USDC_MINT,
            "token_a_amount": "1000000000",      # 1 SOL
            "token_b_amount": "150000000",       # 150 USDC
            "token_a_decimals": 9,
            "token_b_decimals": 6
        }]
        
        with patch.object(reader, '_get_pools_for_pair', AsyncMock(return_value=pools)):
            with patch.object(reader, 'get_sol_price_usd', AsyncMock(return_value=Decimal("150.0"))):
                result = await reader.get_token_price(SOL_MINT, USDC_MINT)
                # TVL = 1 SOL * $150 + 150 USDC = $300, which is < $5000
                assert result is None
    
    @pytest.mark.asyncio
    async def test_same_token_price(self):
        """Test that same token returns price of 1"""
        reader = AMMPriceReader()
        
        result = await reader.get_token_price(USDC_MINT, USDC_MINT)
        assert result is not None
        price, source, tvl = result
        assert price == Decimal("1.0")
        assert source == "self"
    
    @pytest.mark.asyncio
    async def test_no_sol_price_available(self):
        """Test behavior when SOL price cannot be determined"""
        reader = AMMPriceReader()
        
        pools = [{
            "program": "raydium",
            "token_a_mint": "token_mint",
            "token_b_mint": USDC_MINT,
            "token_a_amount": "1000000",
            "token_b_amount": "1000000",
            "token_a_decimals": 6,
            "token_b_decimals": 6
        }]
        
        with patch.object(reader, '_get_pools_for_pair', AsyncMock(return_value=pools)):
            with patch.object(reader, 'get_sol_price_usd', AsyncMock(return_value=None)):
                result = await reader.get_token_price("token_mint", USDC_MINT)
                assert result is None  # Can't calculate TVL without SOL price
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager"""
        async with AMMPriceReader() as reader:
            assert reader.session is not None
            assert reader._owns_session is True
    
    @pytest.mark.asyncio
    async def test_convenience_function(self):
        """Test get_amm_price convenience function"""
        with patch('src.lib.amm_price.AMMPriceReader') as mock_reader_class:
            mock_reader = MagicMock()
            mock_reader.__aenter__ = AsyncMock(return_value=mock_reader)
            mock_reader.__aexit__ = AsyncMock(return_value=None)
            mock_reader.get_token_price = AsyncMock(return_value=(Decimal("150.0"), "raydium", Decimal("10000")))
            mock_reader_class.return_value = mock_reader
            
            result = await get_amm_price(SOL_MINT, USDC_MINT)
            assert result is not None
            price, source, tvl = result
            assert price == Decimal("150.0")
    
    def test_get_stats(self):
        """Test statistics tracking"""
        reader = AMMPriceReader()
        reader.request_count = 5
        reader._sol_price_usd = Decimal("150.0")
        
        stats = reader.get_stats()
        assert stats["request_count"] == 5
        assert stats["sol_price"] == 150.0
        assert stats["cache_size"] == 0

    @pytest.mark.asyncio
    async def test_pump_fun_token_detection(self):
        """Test pump.fun token detection and pool creation"""
        async with AMMPriceReader() as reader:
            # Test pump token
            pump_mint = "GuFK1iRQPCSRxPxWhw94SrDtLYaf7oDT68uuDDpjpump"
            pools = await reader._find_pools_for_token(pump_mint)
            
            assert len(pools) == 1
            assert pools[0]["program"] == "pump_amm"
            assert pools[0]["token_a_mint"] == pump_mint
            assert pools[0]["token_b_mint"] == "So11111111111111111111111111111111111111112"
    
    @pytest.mark.asyncio
    async def test_pump_pool_realistic_values(self):
        """Test pump.fun pool returns realistic values"""
        async with AMMPriceReader() as reader:
            pump_mint = "GuFK1iRQPCSRxPxWhw94SrDtLYaf7oDT68uuDDpjpump"
            pool = await reader._get_pump_fun_pool(pump_mint)
            
            assert pool is not None
            # Check real reserves are small
            real_sol = Decimal(pool["token_b_amount"]) / Decimal(10**9)
            assert real_sol < 1  # Less than 1 SOL in real reserves
            
            # Check virtual reserves exist
            assert "virtual_sol_reserves" in pool
            assert "virtual_token_reserves" in pool
    
    @pytest.mark.asyncio
    async def test_tvl_calculation_pump_pool(self):
        """Test TVL calculation for pump.fun pools uses only real reserves"""
        async with AMMPriceReader() as reader:
            sol_price = Decimal("150.0")
            
            pool = {
                "program": "pump_amm",
                "token_a_mint": "GuFK1iRQPCSRxPxWhw94SrDtLYaf7oDT68uuDDpjpump",
                "token_b_mint": "So11111111111111111111111111111111111111112",
                "token_a_amount": "100000000000",      # 100K tokens real
                "token_b_amount": "42000000",          # 0.042 SOL real
                "token_a_decimals": 6,
                "token_b_decimals": 9,
                "virtual_sol_reserves": "30000000000",  # 30 SOL virtual (not used for TVL)
                "virtual_token_reserves": "900000000000000"
            }
            
            tvl = await reader._calculate_pool_tvl(pool, sol_price)
            
            # TVL should be based on real reserves only: 0.042 SOL * 150 * 2 = $12.6
            expected_tvl = Decimal("0.042") * sol_price * 2
            assert abs(tvl - expected_tvl) < 1  # Within $1
    
    @pytest.mark.asyncio
    async def test_price_calculation_with_virtual_reserves(self):
        """Test price calculation includes virtual reserves"""
        async with AMMPriceReader() as reader:
            pool = {
                "program": "pump_amm",
                "token_a_mint": "GuFK1iRQPCSRxPxWhw94SrDtLYaf7oDT68uuDDpjpump",
                "token_b_mint": "So11111111111111111111111111111111111111112",
                "token_a_amount": "100000000000",      # 100K tokens real
                "token_b_amount": "42000000",          # 0.042 SOL real
                "token_a_decimals": 6,
                "token_b_decimals": 9,
                "virtual_sol_reserves": "30000000000",  # 30 SOL virtual
                "virtual_token_reserves": "900000000000000"  # 900M tokens virtual
            }
            
            price = await reader._calculate_price_from_pool(
                pool,
                "GuFK1iRQPCSRxPxWhw94SrDtLYaf7oDT68uuDDpjpump",
                "So11111111111111111111111111111111111111112"
            )
            
            # Price should use total reserves (real + virtual)
            # Total SOL: 30.042, Total tokens: 900.1M
            # Price = 30.042 / 900100000 = 0.0000000334 SOL per token
            assert price is not None
            assert price < Decimal("0.00001")  # Very small price as expected
    
    @pytest.mark.asyncio
    async def test_low_tvl_fallback(self):
        """Test fallback to low TVL pools"""
        async with AMMPriceReader() as reader:
            # Mock pool finding
            reader._find_pools_for_token = AsyncMock(return_value=[{
                "program": "pump_amm",
                "token_a_mint": "test_token",
                "token_b_mint": "So11111111111111111111111111111111111111112",
                "token_a_amount": "10000000000",   # Small amounts
                "token_b_amount": "1000000",       # 0.001 SOL
                "token_a_decimals": 6,
                "token_b_decimals": 9
            }])
            
            # Mock SOL price
            reader.get_sol_price_usd = AsyncMock(return_value=Decimal("150.0"))
            
            # Mock pool calculation methods
            reader._calculate_pool_tvl = AsyncMock(return_value=Decimal("300"))  # $300 TVL (below MIN_TVL)
            reader._calculate_price_from_pool = AsyncMock(return_value=Decimal("0.00001"))
            
            result = await reader.get_token_price("test_token")
            
            # Should still return a price with medium confidence
            assert result is not None
            price, source, tvl = result
            assert "medium" in source or "low" in source  # Should indicate lower confidence
            assert tvl == Decimal("300")
    
    @pytest.mark.asyncio
    async def test_raydium_pool_for_rdmp(self):
        """Test RDMP token gets Raydium pool with correct reserves"""
        async with AMMPriceReader() as reader:
            rdmp_mint = "1HE8MZKhpbJiNvjJTrXdV395qEmPEqJme6P5DLBboop"
            pools = await reader._find_pools_for_token(rdmp_mint)
            
            assert len(pools) == 1
            assert pools[0]["program"] == "raydium"
            assert pools[0]["token_a_mint"] == rdmp_mint
            
            # Check reserves are substantial
            sol_amount = Decimal(pools[0]["token_b_amount"]) / Decimal(10**9)
            assert sol_amount > 1000  # More than 1000 SOL
    
    @pytest.mark.asyncio 
    async def test_confidence_levels(self):
        """Test different confidence levels based on TVL"""
        async with AMMPriceReader() as reader:
            reader.get_sol_price_usd = AsyncMock(return_value=Decimal("150.0"))
            reader._calculate_price_from_pool = AsyncMock(return_value=Decimal("0.00001"))
            
            # Test high TVL pool (> $1000)
            reader._find_pools_for_token = AsyncMock(return_value=[{
                "program": "raydium",
                "token_a_mint": "test",
                "token_b_mint": "So11111111111111111111111111111111111111112",
                "token_a_amount": "1000000000000",
                "token_b_amount": "10000000000",  # 10 SOL = $1500 TVL
                "token_a_decimals": 6,
                "token_b_decimals": 9
            }])
            
            result = await reader.get_token_price("test")
            assert result is not None
            _, source, _ = result
            assert "medium" not in source and "low" not in source
            
            # Test medium TVL pool ($100-$1000)
            reader._find_pools_for_token = AsyncMock(return_value=[{
                "program": "pump_amm",
                "token_a_mint": "test2",
                "token_b_mint": "So11111111111111111111111111111111111111112",
                "token_a_amount": "100000000000",
                "token_b_amount": "300000000",  # 0.3 SOL = $45 * 2 = $90 TVL (below MIN)
                "token_a_decimals": 6,
                "token_b_decimals": 9
            }])
            reader._calculate_pool_tvl = AsyncMock(return_value=Decimal("200"))  # $200 TVL
            
            result = await reader.get_token_price("test2")
            assert result is not None
            _, source, _ = result
            assert "medium" in source or "low" in source


if __name__ == "__main__":
    # Run basic tests
    print("Testing AMMPriceReader...")
    
    async def run_tests():
        test = TestAMMPriceReader()
        
        await test.test_sol_price_caching()
        print("✅ SOL price caching test passed")
        
        await test.test_stable_coin_prices()
        print("✅ Stablecoin prices test passed")
        
        await test.test_price_calculation_from_reserves()
        print("✅ Price calculation test passed")
        
        await test.test_tvl_calculation()
        print("✅ TVL calculation test passed")
        
        await test.test_pump_fun_token_detection()
        print("✅ Pump.fun token detection test passed")
        
        await test.test_pump_pool_realistic_values()
        print("✅ Pump.fun pool returns realistic values test passed")
        
        await test.test_tvl_calculation_pump_pool()
        print("✅ TVL calculation for pump.fun pools uses only real reserves test passed")
        
        await test.test_price_calculation_with_virtual_reserves()
        print("✅ Price calculation includes virtual reserves test passed")
        
        await test.test_low_tvl_fallback()
        print("✅ Fallback to low TVL pools test passed")
        
        await test.test_raydium_pool_for_rdmp()
        print("✅ RDMP token gets Raydium pool with correct reserves test passed")
        
        await test.test_confidence_levels()
        print("✅ Different confidence levels based on TVL test passed")
    
    asyncio.run(run_tests())
    
    print("\n✅ All basic tests passed!")
    print("\nRun 'pytest tests/test_amm_price.py -v' for full test suite") 