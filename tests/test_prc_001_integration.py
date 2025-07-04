"""
Unit tests for PRC-001 SOL spot pricing integration

Tests the UnrealizedPnLCalculator SOL spot pricing functionality
that was added as part of PRC-001 implementation.
"""

import pytest
from unittest.mock import patch, Mock
from decimal import Decimal
from datetime import datetime, timezone

from src.lib.unrealized_pnl_calculator import UnrealizedPnLCalculator
from src.lib.position_models import Position, PriceConfidence, CostBasisMethod


class TestPRC001SolSpotPricing:
    """Test PRC-001 SOL spot pricing integration"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.calculator = UnrealizedPnLCalculator()
        
        # Sample positions
        self.positions = [
            Position(
                position_id="test1",
                wallet="test_wallet",
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                token_symbol="USDC",
                balance=Decimal("1000.0"),
                cost_basis=Decimal("1.0"),
                cost_basis_usd=Decimal("1000.0"),
                cost_basis_method=CostBasisMethod.WEIGHTED_AVG
            ),
            Position(
                position_id="test2", 
                wallet="test_wallet",
                token_mint="So11111111111111111111111111111111111111112",
                token_symbol="SOL",
                balance=Decimal("5.0"),
                cost_basis=Decimal("100.0"),
                cost_basis_usd=Decimal("500.0"),
                cost_basis_method=CostBasisMethod.WEIGHTED_AVG
            )
        ]
    
    @pytest.mark.asyncio
    @patch('src.config.feature_flags.should_calculate_unrealized_pnl')
    @patch('src.config.feature_flags.should_use_sol_spot_pricing')
    @patch('src.lib.sol_price_fetcher.get_sol_price_usd')
    async def test_sol_spot_pricing_enabled(self, mock_sol_price, mock_feature_flag, mock_pnl_enabled):
        """Test SOL spot pricing when feature flag is enabled"""
        # Enable P&L calculation and SOL spot pricing
        mock_pnl_enabled.return_value = True
        mock_feature_flag.return_value = True
        
        # Mock SOL price
        mock_sol_price.return_value = Decimal("180.0")
        
        # Calculate P&L
        results = await self.calculator.calculate_batch_unrealized_pnl(self.positions)
        
        # Verify function calls
        mock_feature_flag.assert_called_once()
        mock_sol_price.assert_called_once()
        
        # Should have 2 results
        assert len(results) == 2
        
        # Check first position (USDC with balance 1000, cost basis $1000)
        usdc_result = results[0]
        assert usdc_result.position.token_symbol == "USDC"
        assert usdc_result.current_price_usd == Decimal("180.0")
        assert usdc_result.current_value_usd == Decimal("180000.0")  # 1000 * 180
        assert usdc_result.unrealized_pnl_usd == Decimal("179000.0")  # 180000 - 1000
        assert usdc_result.price_confidence == PriceConfidence.ESTIMATED
        assert usdc_result.price_source == "sol_spot_price"
        assert usdc_result.error is None
        
        # Check second position (SOL with balance 5, cost basis $500)
        sol_result = results[1]
        assert sol_result.position.token_symbol == "SOL"
        assert sol_result.current_price_usd == Decimal("180.0")
        assert sol_result.current_value_usd == Decimal("900.0")  # 5 * 180
        assert sol_result.unrealized_pnl_usd == Decimal("400.0")  # 900 - 500
        assert sol_result.price_confidence == PriceConfidence.ESTIMATED
        assert sol_result.price_source == "sol_spot_price"
        assert sol_result.error is None
    
    @pytest.mark.asyncio
    @patch('src.config.feature_flags.should_use_sol_spot_pricing')
    @patch('src.lib.sol_price_fetcher.get_sol_price_usd')
    async def test_sol_spot_pricing_disabled(self, mock_sol_price, mock_feature_flag):
        """Test that SOL spot pricing is skipped when feature flag is disabled"""
        # Disable SOL spot pricing
        mock_feature_flag.return_value = False
        
        # Calculate P&L - should fall back to existing logic
        results = await self.calculator.calculate_batch_unrealized_pnl(self.positions)
        
        # Verify SOL price was NOT called
        mock_feature_flag.assert_called_once()
        mock_sol_price.assert_not_called()
        
        # Results depend on fallback logic, but SOL price shouldn't be used
        assert len(results) == 2
    
    @pytest.mark.asyncio
    @patch('src.config.feature_flags.should_use_sol_spot_pricing')
    @patch('src.lib.sol_price_fetcher.get_sol_price_usd')
    async def test_sol_price_fetch_failure(self, mock_sol_price, mock_feature_flag):
        """Test graceful degradation when SOL price fetch fails"""
        # Enable SOL spot pricing
        mock_feature_flag.return_value = True
        
        # Mock SOL price failure
        mock_sol_price.return_value = None
        
        # Calculate P&L
        results = await self.calculator.calculate_batch_unrealized_pnl(self.positions)
        
        # Verify function calls
        mock_feature_flag.assert_called_once()
        mock_sol_price.assert_called_once()
        
        # Should have 2 results with no pricing
        assert len(results) == 2
        
        for result in results:
            assert result.current_price_usd is None
            assert result.current_value_usd is None
            assert result.unrealized_pnl_usd is None
            assert result.unrealized_pnl_pct is None
            assert result.price_confidence == PriceConfidence.UNAVAILABLE
            assert result.price_source is None
            assert result.error == "SOL price unavailable"
    
    @pytest.mark.asyncio
    @patch('src.config.feature_flags.should_use_sol_spot_pricing')
    @patch('src.lib.sol_price_fetcher.get_sol_price_usd')
    async def test_zero_balance_position(self, mock_sol_price, mock_feature_flag):
        """Test handling of positions with zero balance"""
        # Enable SOL spot pricing
        mock_feature_flag.return_value = True
        mock_sol_price.return_value = Decimal("180.0")
        
        # Create position with zero balance
        zero_balance_position = Position(
            position_id="test_zero",
            wallet="test_wallet", 
            token_mint="test_mint",
            token_symbol="TEST",
            balance=Decimal("0.0"),
            cost_basis=Decimal("1.0"),
            cost_basis_usd=Decimal("100.0"),
            cost_basis_method=CostBasisMethod.WEIGHTED_AVG
        )
        
        # Calculate P&L
        results = await self.calculator.calculate_batch_unrealized_pnl([zero_balance_position])
        
        # Should have 1 result with no pricing due to zero balance
        assert len(results) == 1
        result = results[0]
        
        assert result.current_price_usd is None
        assert result.current_value_usd is None
        assert result.unrealized_pnl_usd is None
        assert result.price_confidence == PriceConfidence.UNAVAILABLE
        assert result.error == "No token balance"
    
    @pytest.mark.asyncio
    @patch('src.config.feature_flags.should_use_sol_spot_pricing')
    @patch('src.lib.sol_price_fetcher.get_sol_price_usd')
    async def test_percentage_calculation(self, mock_sol_price, mock_feature_flag):
        """Test percentage gain/loss calculation with SOL pricing"""
        # Enable SOL spot pricing
        mock_feature_flag.return_value = True
        mock_sol_price.return_value = Decimal("200.0")
        
        # Position with cost basis for percentage calculation
        position = Position(
            position_id="test_pct",
            wallet="test_wallet",
            token_mint="test_mint", 
            token_symbol="TEST",
            balance=Decimal("10.0"),
            cost_basis=Decimal("150.0"),
            cost_basis_usd=Decimal("1500.0"),  # $150 per token * 10 tokens
            cost_basis_method=CostBasisMethod.WEIGHTED_AVG
        )
        
        # Calculate P&L
        results = await self.calculator.calculate_batch_unrealized_pnl([position])
        
        result = results[0]
        assert result.current_value_usd == Decimal("2000.0")  # 10 * $200
        assert result.unrealized_pnl_usd == Decimal("500.0")  # $2000 - $1500
        
        # Percentage: (500 / 1500) * 100 = 33.33%
        expected_pct = (Decimal("500") / Decimal("1500")) * Decimal("100")
        assert result.unrealized_pnl_pct is not None
        assert abs(result.unrealized_pnl_pct - expected_pct) < Decimal("0.01")
    
    @pytest.mark.asyncio
    @patch('src.config.feature_flags.should_use_sol_spot_pricing')
    async def test_skip_pricing_takes_precedence(self, mock_feature_flag):
        """Test that skip_pricing=True takes precedence over SOL spot pricing"""
        # Enable SOL spot pricing
        mock_feature_flag.return_value = True
        
        # Calculate P&L with skip_pricing=True
        results = await self.calculator.calculate_batch_unrealized_pnl(
            self.positions, 
            skip_pricing=True
        )
        
        # SOL pricing feature flag should not even be checked
        mock_feature_flag.assert_not_called()
        
        # Should have 2 results with no pricing
        assert len(results) == 2
        for result in results:
            assert result.current_price_usd is None
            assert result.current_value_usd is None
            assert result.price_confidence == PriceConfidence.UNAVAILABLE 