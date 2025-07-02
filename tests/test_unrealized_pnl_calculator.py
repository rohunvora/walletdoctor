"""
Test Unrealized P&L Calculator
WAL-604: Tests for unrealized P&L calculation with price integration
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from typing import Optional

from src.lib.unrealized_pnl_calculator import (
    UnrealizedPnLCalculator, UnrealizedPnLResult,
    PRICE_FRESH_SECONDS, PRICE_RECENT_SECONDS, PRICE_STALE_SECONDS
)
from src.lib.position_models import Position, PositionPnL, PriceConfidence, CostBasisMethod
from src.lib.mc_calculator import MarketCapResult
from src.lib.mc_calculator import CONFIDENCE_HIGH, CONFIDENCE_EST, CONFIDENCE_UNAVAILABLE

# Test constants
TEST_WALLET = "TestWallet123"
BONK_MINT = "DezXAZ8z7PnrnRJjz3wXBoHHuJjWKjH8vJFKfPQoKEWF"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


@pytest.fixture
def test_position():
    """Create a test position"""
    return Position(
        position_id="test_position_1",
        wallet=TEST_WALLET,
        token_mint=BONK_MINT,
        token_symbol="BONK",
        balance=Decimal("100000"),
        cost_basis=Decimal("0.00001"),
        cost_basis_usd=Decimal("1.0"),
        cost_basis_method=CostBasisMethod.FIFO,
        opened_at=datetime.now(timezone.utc),
        last_trade_at=datetime.now(timezone.utc),
        last_update_slot=1000,
        last_update_time=datetime.now(timezone.utc),
        is_closed=False,
        trade_count=1,
        decimals=5
    )


@pytest.fixture
def mock_mc_calculator():
    """Create a mock market cap calculator"""
    calculator = Mock(spec=["calculate_market_cap"])
    calculator.calculate_market_cap = AsyncMock()
    return calculator


@pytest.fixture
def calculator(mock_mc_calculator):
    """Create calculator with mocked MC service"""
    return UnrealizedPnLCalculator(mock_mc_calculator)


class TestUnrealizedPnLCalculator:
    """Test unrealized P&L calculator functionality"""
    
    @pytest.mark.asyncio
    async def test_calculate_with_price_gain(self, calculator, test_position, mock_mc_calculator):
        """Test calculation with price appreciation"""
        # Mock current price higher than cost basis
        mock_mc_calculator.calculate_market_cap.return_value = MarketCapResult(
            value=20000.0,  # Market cap
            confidence=CONFIDENCE_HIGH,
            source="helius_amm",
            supply=1000000000.0,
            price=0.00002,  # Current price (doubled)
            timestamp=int(datetime.now(timezone.utc).timestamp())
        )
        
        # Enable feature flag
        with patch("src.lib.unrealized_pnl_calculator.should_calculate_unrealized_pnl", return_value=True):
            result = await calculator.calculate_unrealized_pnl(test_position)
        
        # Verify calculations
        assert result.error is None
        assert result.current_price_usd == Decimal("0.00002")
        assert result.current_value_usd == Decimal("2.0")  # 100k * 0.00002
        assert result.unrealized_pnl_usd == Decimal("1.0")  # 2.0 - 1.0
        assert result.unrealized_pnl_pct == Decimal("100")  # 100% gain
        assert result.price_confidence == PriceConfidence.HIGH
        assert result.price_source == "helius_amm"
    
    @pytest.mark.asyncio
    async def test_calculate_with_price_loss(self, calculator, test_position, mock_mc_calculator):
        """Test calculation with price depreciation"""
        # Mock current price lower than cost basis
        mock_mc_calculator.calculate_market_cap.return_value = MarketCapResult(
            value=5000.0,
            confidence=CONFIDENCE_HIGH,
            source="helius_amm",
            supply=1000000000.0,
            price=0.000005,  # Current price (halved)
            timestamp=int(datetime.now(timezone.utc).timestamp())
        )
        
        with patch("src.lib.unrealized_pnl_calculator.should_calculate_unrealized_pnl", return_value=True):
            result = await calculator.calculate_unrealized_pnl(test_position)
        
        assert result.error is None
        assert result.current_price_usd == Decimal("0.000005")
        assert result.current_value_usd == Decimal("0.5")  # 100k * 0.000005
        assert result.unrealized_pnl_usd == Decimal("-0.5")  # 0.5 - 1.0
        assert result.unrealized_pnl_pct == Decimal("-50")  # -50% loss
    
    @pytest.mark.asyncio
    async def test_calculate_with_provided_price(self, calculator, test_position):
        """Test calculation with externally provided price"""
        provided_price = Decimal("0.00003")
        
        with patch("src.lib.unrealized_pnl_calculator.should_calculate_unrealized_pnl", return_value=True):
            result = await calculator.calculate_unrealized_pnl(test_position, provided_price)
        
        assert result.error is None
        assert result.current_price_usd == provided_price
        assert result.current_value_usd == Decimal("3.0")  # 100k * 0.00003
        assert result.unrealized_pnl_usd == Decimal("2.0")  # 3.0 - 1.0
        assert result.unrealized_pnl_pct == Decimal("200")  # 200% gain
        assert result.price_confidence == PriceConfidence.HIGH
        assert result.price_source == "provided"
    
    @pytest.mark.asyncio
    async def test_price_unavailable(self, calculator, test_position, mock_mc_calculator):
        """Test handling when price is unavailable"""
        mock_mc_calculator.calculate_market_cap.return_value = MarketCapResult(
            value=None,
            confidence=CONFIDENCE_UNAVAILABLE,
            source=None,
            supply=None,
            price=None,
            timestamp=int(datetime.now(timezone.utc).timestamp())
        )
        
        with patch("src.lib.unrealized_pnl_calculator.should_calculate_unrealized_pnl", return_value=True):
            result = await calculator.calculate_unrealized_pnl(test_position)
        
        assert result.error == "Price unavailable"
        assert result.current_price_usd is None
        assert result.current_value_usd is None
        assert result.unrealized_pnl_usd is None
        assert result.unrealized_pnl_pct is None
        assert result.price_confidence == PriceConfidence.UNAVAILABLE
    
    @pytest.mark.asyncio
    async def test_feature_flag_disabled(self, calculator, test_position):
        """Test behavior when feature flag is disabled"""
        with patch("src.lib.unrealized_pnl_calculator.should_calculate_unrealized_pnl", return_value=False):
            result = await calculator.calculate_unrealized_pnl(test_position)
        
        assert result.error == "Unrealized P&L disabled"
        assert result.price_confidence == PriceConfidence.UNAVAILABLE
    
    @pytest.mark.asyncio
    async def test_airdrop_position(self, calculator, mock_mc_calculator):
        """Test position with zero cost basis (airdrop)"""
        airdrop_position = Position(
            position_id="airdrop_1",
            wallet=TEST_WALLET,
            token_mint=BONK_MINT,
            token_symbol="BONK",
            balance=Decimal("50000"),
            cost_basis=Decimal("0"),
            cost_basis_usd=Decimal("0"),
            cost_basis_method=CostBasisMethod.FIFO,
            opened_at=datetime.now(timezone.utc),
            last_trade_at=datetime.now(timezone.utc),
            last_update_slot=1000,
            last_update_time=datetime.now(timezone.utc),
            is_closed=False,
            trade_count=0,
            decimals=5
        )
        
        mock_mc_calculator.calculate_market_cap.return_value = MarketCapResult(
            value=10000.0,
            confidence=CONFIDENCE_HIGH,
            source="helius_amm",
            supply=1000000000.0,
            price=0.00001,
            timestamp=int(datetime.now(timezone.utc).timestamp())
        )
        
        with patch("src.lib.unrealized_pnl_calculator.should_calculate_unrealized_pnl", return_value=True):
            result = await calculator.calculate_unrealized_pnl(airdrop_position)
        
        assert result.error is None
        assert result.current_value_usd == Decimal("0.5")  # 50k * 0.00001
        assert result.unrealized_pnl_usd == Decimal("0.5")  # All profit
        assert result.unrealized_pnl_pct == Decimal("100")  # 100% gain
    
    @pytest.mark.asyncio
    async def test_batch_calculation(self, calculator, test_position, mock_mc_calculator):
        """Test batch calculation of multiple positions"""
        positions = [
            test_position,
            Position(
                position_id="test_position_2",
                wallet=TEST_WALLET,
                token_mint=USDC_MINT,
                token_symbol="USDC",
                balance=Decimal("1000"),
                cost_basis=Decimal("1.0"),
                cost_basis_usd=Decimal("1000"),
                cost_basis_method=CostBasisMethod.FIFO,
                opened_at=datetime.now(timezone.utc),
                last_trade_at=datetime.now(timezone.utc),
                last_update_slot=2000,
                last_update_time=datetime.now(timezone.utc),
                is_closed=False,
                trade_count=1,
                decimals=6
            )
        ]
        
        # Mock different prices for each token
        mock_mc_calculator.calculate_market_cap.side_effect = [
            MarketCapResult(
                value=20000.0,
                confidence=CONFIDENCE_HIGH,
                source="helius_amm",
                supply=1000000000.0,
                price=0.00002,
                timestamp=int(datetime.now(timezone.utc).timestamp())
            ),
            MarketCapResult(
                value=1000000000.0,
                confidence=CONFIDENCE_HIGH,
                source="helius_amm",
                supply=1000000000.0,
                price=1.0,
                timestamp=int(datetime.now(timezone.utc).timestamp())
            )
        ]
        
        with patch("src.lib.unrealized_pnl_calculator.should_calculate_unrealized_pnl", return_value=True):
            results = await calculator.calculate_batch_unrealized_pnl(positions, batch_size=2)
        
        assert len(results) == 2
        
        # First position (BONK)
        assert results[0].unrealized_pnl_usd == Decimal("1.0")
        assert results[0].unrealized_pnl_pct == Decimal("100")
        
        # Second position (USDC)
        assert results[1].unrealized_pnl_usd == Decimal("0")
        assert results[1].unrealized_pnl_pct == Decimal("0")
    
    def test_confidence_conversion_fresh(self, calculator):
        """Test confidence conversion for fresh prices"""
        now = int(datetime.now(timezone.utc).timestamp())
        
        # High confidence, fresh price
        confidence = calculator._convert_confidence(CONFIDENCE_HIGH, now)
        assert confidence == PriceConfidence.HIGH
        
        # Estimated confidence, fresh price
        confidence = calculator._convert_confidence(CONFIDENCE_EST, now)
        assert confidence == PriceConfidence.ESTIMATED
    
    def test_confidence_conversion_recent(self, calculator):
        """Test confidence conversion for recent prices"""
        recent_time = int((datetime.now(timezone.utc) - timedelta(seconds=120)).timestamp())
        
        # High confidence, recent price -> degraded to ESTIMATED
        confidence = calculator._convert_confidence(CONFIDENCE_HIGH, recent_time)
        assert confidence == PriceConfidence.ESTIMATED
        
        # Estimated confidence, recent price -> stays ESTIMATED
        confidence = calculator._convert_confidence(CONFIDENCE_EST, recent_time)
        assert confidence == PriceConfidence.ESTIMATED
    
    def test_confidence_conversion_stale(self, calculator):
        """Test confidence conversion for stale prices"""
        stale_time = int((datetime.now(timezone.utc) - timedelta(seconds=600)).timestamp())
        
        # High confidence, stale price -> degraded to STALE
        confidence = calculator._convert_confidence(CONFIDENCE_HIGH, stale_time)
        assert confidence == PriceConfidence.STALE
        
        # Estimated confidence, stale price -> STALE
        confidence = calculator._convert_confidence(CONFIDENCE_EST, stale_time)
        assert confidence == PriceConfidence.STALE
    
    def test_confidence_conversion_unavailable(self, calculator):
        """Test confidence conversion for unavailable prices"""
        confidence = calculator._convert_confidence(CONFIDENCE_UNAVAILABLE, 0)
        assert confidence == PriceConfidence.UNAVAILABLE
    
    @pytest.mark.asyncio
    async def test_portfolio_aggregation(self, calculator, mock_mc_calculator):
        """Test portfolio-level P&L aggregation"""
        positions = [
            Position(
                position_id="pos1",
                wallet=TEST_WALLET,
                token_mint=BONK_MINT,
                token_symbol="BONK",
                balance=Decimal("100000"),
                cost_basis=Decimal("0.00001"),
                cost_basis_usd=Decimal("1.0"),
                cost_basis_method=CostBasisMethod.FIFO,
                opened_at=datetime.now(timezone.utc),
                last_trade_at=datetime.now(timezone.utc),
                last_update_slot=1000,
                last_update_time=datetime.now(timezone.utc),
                is_closed=False,
                trade_count=1
            ),
            Position(
                position_id="pos2",
                wallet=TEST_WALLET,
                token_mint=USDC_MINT,
                token_symbol="USDC",
                balance=Decimal("1000"),
                cost_basis=Decimal("1.0"),
                cost_basis_usd=Decimal("1000"),
                cost_basis_method=CostBasisMethod.FIFO,
                opened_at=datetime.now(timezone.utc),
                last_trade_at=datetime.now(timezone.utc),
                last_update_slot=2000,
                last_update_time=datetime.now(timezone.utc),
                is_closed=False,
                trade_count=1
            )
        ]
        
        # Mock prices
        mock_mc_calculator.calculate_market_cap.side_effect = [
            MarketCapResult(
                value=20000.0,
                confidence=CONFIDENCE_HIGH,
                source="helius_amm",
                supply=1000000000.0,
                price=0.00002,  # BONK doubled
                timestamp=int(datetime.now(timezone.utc).timestamp())
            ),
            MarketCapResult(
                value=900000000.0,
                confidence=CONFIDENCE_HIGH,
                source="helius_amm",
                supply=1000000000.0,
                price=0.9,  # USDC down 10%
                timestamp=int(datetime.now(timezone.utc).timestamp())
            )
        ]
        
        with patch("src.lib.unrealized_pnl_calculator.should_calculate_unrealized_pnl", return_value=True):
            summary = await calculator.calculate_portfolio_unrealized_pnl(positions)
        
        assert summary["total_cost_basis_usd"] == 1001.0
        assert summary["total_current_value_usd"] == 902.0  # 2.0 + 900
        assert summary["total_unrealized_pnl_usd"] == -99.0  # 1.0 + (-100)
        assert summary["total_unrealized_pnl_pct"] == pytest.approx(-9.89, rel=0.01)
        assert summary["positions_with_prices"] == 2
        assert summary["positions_without_prices"] == 0
        assert summary["confidence_breakdown"]["high"] == 2
    
    def test_price_age_labels(self, calculator):
        """Test price age labeling"""
        now = datetime.now(timezone.utc)
        
        # Fresh price
        fresh_time = now - timedelta(seconds=30)
        assert calculator.get_price_age_label(fresh_time) == "fresh"
        
        # Recent price
        recent_time = now - timedelta(seconds=180)
        assert calculator.get_price_age_label(recent_time) == "recent"
        
        # Stale price
        stale_time = now - timedelta(seconds=600)
        assert calculator.get_price_age_label(stale_time) == "stale"
        
        # Very stale price
        very_stale_time = now - timedelta(seconds=1200)
        assert calculator.get_price_age_label(very_stale_time) == "very stale"
    
    @pytest.mark.asyncio
    async def test_create_position_pnl_list(self, calculator, test_position, mock_mc_calculator):
        """Test creating PositionPnL objects from positions"""
        positions = [test_position]
        
        mock_mc_calculator.calculate_market_cap.return_value = MarketCapResult(
            value=20000.0,
            confidence=CONFIDENCE_HIGH,
            source="helius_amm",
            supply=1000000000.0,
            price=0.00002,
            timestamp=int(datetime.now(timezone.utc).timestamp())
        )
        
        with patch("src.lib.unrealized_pnl_calculator.should_calculate_unrealized_pnl", return_value=True):
            pnl_list = await calculator.create_position_pnl_list(positions)
        
        assert len(pnl_list) == 1
        assert isinstance(pnl_list[0], PositionPnL)
        assert pnl_list[0].position == test_position
        assert pnl_list[0].unrealized_pnl_usd == Decimal("1.0")
    
    @pytest.mark.asyncio
    async def test_error_handling(self, calculator, test_position, mock_mc_calculator):
        """Test error handling in price fetching"""
        # Mock exception in MC calculator
        mock_mc_calculator.calculate_market_cap.side_effect = Exception("API error")
        
        with patch("src.lib.unrealized_pnl_calculator.should_calculate_unrealized_pnl", return_value=True):
            result = await calculator.calculate_unrealized_pnl(test_position)
        
        assert result.error == "Price unavailable"
        assert result.current_price_usd is None
        assert result.price_confidence == PriceConfidence.UNAVAILABLE
    
    @pytest.mark.asyncio
    async def test_empty_portfolio(self, calculator):
        """Test portfolio calculation with no positions"""
        with patch("src.lib.unrealized_pnl_calculator.should_calculate_unrealized_pnl", return_value=True):
            summary = await calculator.calculate_portfolio_unrealized_pnl([])
        
        assert summary["total_cost_basis_usd"] == 0.0
        assert summary["total_current_value_usd"] == 0.0
        assert summary["total_unrealized_pnl_usd"] == 0.0
        assert summary["positions_with_prices"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 