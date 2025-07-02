"""
Unit tests for cost basis calculator
WAL-602: Cost Basis Calculator Tests

Includes property-based testing with hypothesis
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from hypothesis import given, strategies as st, assume, settings
from hypothesis.strategies import composite

from src.lib.cost_basis_calculator import (
    CostBasisCalculator, BuyRecord, CostBasisResult,
    DUST_THRESHOLD_USD
)
from src.lib.position_models import CostBasisMethod


# Hypothesis strategies for property-based testing
@composite
def decimal_strategy(draw, min_value=0.0001, max_value=1000000, places=8):
    """Generate reasonable decimal values for testing"""
    value = draw(st.floats(min_value=min_value, max_value=max_value, allow_nan=False))
    return Decimal(str(round(value, places)))


@composite
def buy_record_strategy(draw):
    """Generate valid BuyRecord objects"""
    base_time = datetime(2024, 1, 1)
    return BuyRecord(
        timestamp=base_time + timedelta(days=draw(st.integers(0, 365))),
        amount=draw(decimal_strategy(min_value=0.1, max_value=1000000)),
        price_per_token=draw(decimal_strategy(min_value=0.0001, max_value=10000)),
        total_cost_usd=draw(decimal_strategy(min_value=0.01, max_value=1000000)),
        remaining_amount=draw(decimal_strategy(min_value=0, max_value=1000000)),
        tx_signature=draw(st.text(min_size=44, max_size=44, alphabet="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")),
        slot=draw(st.integers(min_value=1, max_value=300000000))
    )


class TestCostBasisCalculator:
    """Test cost basis calculation functionality"""
    
    def test_init_with_default_method(self, monkeypatch):
        """Test initialization with feature flag default"""
        # Test FIFO
        monkeypatch.setenv("COST_BASIS_METHOD", "fifo")
        # Need to reload the feature flags module to pick up env change
        import src.config.feature_flags
        import importlib
        importlib.reload(src.config.feature_flags)
        calc = CostBasisCalculator()
        assert calc.method == CostBasisMethod.FIFO
        
        # Test weighted average
        monkeypatch.setenv("COST_BASIS_METHOD", "weighted_avg")
        importlib.reload(src.config.feature_flags)
        calc = CostBasisCalculator()
        assert calc.method == CostBasisMethod.WEIGHTED_AVG
    
    def test_init_with_explicit_method(self):
        """Test initialization with explicit method"""
        calc = CostBasisCalculator(CostBasisMethod.FIFO)
        assert calc.method == CostBasisMethod.FIFO
        
        calc = CostBasisCalculator(CostBasisMethod.WEIGHTED_AVG)
        assert calc.method == CostBasisMethod.WEIGHTED_AVG


class TestFIFOCalculation:
    """Test FIFO cost basis calculations"""
    
    def test_fifo_simple_case(self):
        """Test basic FIFO calculation"""
        calc = CostBasisCalculator(CostBasisMethod.FIFO)
        
        buys = [
            BuyRecord(
                timestamp=datetime(2024, 1, 1),
                amount=Decimal("100"),
                price_per_token=Decimal("1.0"),
                total_cost_usd=Decimal("100"),
                remaining_amount=Decimal("100"),
                tx_signature="tx1",
                slot=1000
            ),
            BuyRecord(
                timestamp=datetime(2024, 1, 2),
                amount=Decimal("100"),
                price_per_token=Decimal("2.0"),
                total_cost_usd=Decimal("200"),
                remaining_amount=Decimal("100"),
                tx_signature="tx2",
                slot=2000
            )
        ]
        
        # Sell 150 tokens - should use all of first buy + 50 from second
        result = calc.calculate_fifo(buys, Decimal("150"))
        
        assert result.method_used == CostBasisMethod.FIFO
        # Cost: 100 * $1 + 50 * $2 = $200
        assert result.total_cost_basis_usd == Decimal("200.00")
        # Average: $200 / 150 = $1.333...
        assert result.cost_basis_per_token == Decimal("1.33333333")
    
    def test_fifo_partial_sells(self):
        """Test FIFO with multiple partial sells"""
        calc = CostBasisCalculator(CostBasisMethod.FIFO)
        
        buys = [
            BuyRecord(
                timestamp=datetime(2024, 1, 1),
                amount=Decimal("100"),
                price_per_token=Decimal("1.0"),
                total_cost_usd=Decimal("100"),
                remaining_amount=Decimal("50"),  # Already sold 50
                tx_signature="tx1",
                slot=1000
            ),
            BuyRecord(
                timestamp=datetime(2024, 1, 2),
                amount=Decimal("100"),
                price_per_token=Decimal("2.0"),
                total_cost_usd=Decimal("200"),
                remaining_amount=Decimal("100"),  # None sold yet
                tx_signature="tx2",
                slot=2000
            )
        ]
        
        # Sell 75 tokens - should use remaining 50 from first + 25 from second
        result = calc.calculate_fifo(buys, Decimal("75"))
        
        # Cost: 50 * $1 + 25 * $2 = $100
        assert result.total_cost_basis_usd == Decimal("100.00")
        assert result.cost_basis_per_token == Decimal("1.33333333")
    
    def test_fifo_insufficient_buys(self):
        """Test FIFO when sell amount exceeds buy history"""
        calc = CostBasisCalculator(CostBasisMethod.FIFO)
        
        buys = [
            BuyRecord(
                timestamp=datetime(2024, 1, 1),
                amount=Decimal("100"),
                price_per_token=Decimal("1.0"),
                total_cost_usd=Decimal("100"),
                remaining_amount=Decimal("100"),
                tx_signature="tx1",
                slot=1000
            )
        ]
        
        # Try to sell 150 but only have 100
        result = calc.calculate_fifo(buys, Decimal("150"))
        
        assert result.total_cost_basis_usd == Decimal("100.00")
        assert result.cost_basis_per_token == Decimal("1.00000000")
        assert "Insufficient buy history" in result.notes[0]
    
    def test_fifo_empty_buys(self):
        """Test FIFO with no buy history"""
        calc = CostBasisCalculator(CostBasisMethod.FIFO)
        
        result = calc.calculate_fifo([], Decimal("100"))
        
        assert result.cost_basis_per_token == Decimal("0")
        assert result.total_cost_basis_usd == Decimal("0")
        assert "No buys" in result.notes[0]
    
    @given(
        buys=st.lists(buy_record_strategy(), min_size=1, max_size=10),
        sell_amount=decimal_strategy(min_value=0.1, max_value=10000)
    )
    @settings(max_examples=50)
    def test_fifo_property_cost_never_negative(self, buys, sell_amount):
        """Property: FIFO cost basis should never be negative"""
        calc = CostBasisCalculator(CostBasisMethod.FIFO)
        result = calc.calculate_fifo(buys, sell_amount)
        
        assert result.cost_basis_per_token >= 0
        assert result.total_cost_basis_usd >= 0


class TestWeightedAverageCalculation:
    """Test weighted average cost basis calculations"""
    
    def test_weighted_avg_simple_case(self):
        """Test basic weighted average calculation"""
        calc = CostBasisCalculator(CostBasisMethod.WEIGHTED_AVG)
        
        buys = [
            BuyRecord(
                timestamp=datetime(2024, 1, 1),
                amount=Decimal("100"),
                price_per_token=Decimal("1.0"),
                total_cost_usd=Decimal("100"),
                remaining_amount=Decimal("100"),
                tx_signature="tx1",
                slot=1000
            ),
            BuyRecord(
                timestamp=datetime(2024, 1, 2),
                amount=Decimal("100"),
                price_per_token=Decimal("2.0"),
                total_cost_usd=Decimal("200"),
                remaining_amount=Decimal("100"),
                tx_signature="tx2",
                slot=2000
            )
        ]
        
        result = calc.calculate_weighted_average(buys)
        
        assert result.method_used == CostBasisMethod.WEIGHTED_AVG
        # Total cost: $300, Total amount: 200
        # Average: $300 / 200 = $1.50
        assert result.cost_basis_per_token == Decimal("1.50000000")
        assert result.total_cost_basis_usd == Decimal("300.00")
    
    def test_weighted_avg_different_amounts(self):
        """Test weighted average with different purchase amounts"""
        calc = CostBasisCalculator(CostBasisMethod.WEIGHTED_AVG)
        
        buys = [
            BuyRecord(
                timestamp=datetime(2024, 1, 1),
                amount=Decimal("300"),
                price_per_token=Decimal("1.0"),
                total_cost_usd=Decimal("300"),
                remaining_amount=Decimal("300"),
                tx_signature="tx1",
                slot=1000
            ),
            BuyRecord(
                timestamp=datetime(2024, 1, 2),
                amount=Decimal("100"),
                price_per_token=Decimal("3.0"),
                total_cost_usd=Decimal("300"),
                remaining_amount=Decimal("100"),
                tx_signature="tx2",
                slot=2000
            )
        ]
        
        result = calc.calculate_weighted_average(buys)
        
        # Total cost: $600, Total amount: 400
        # Average: $600 / 400 = $1.50
        assert result.cost_basis_per_token == Decimal("1.50000000")
        assert result.total_cost_basis_usd == Decimal("600.00")
    
    def test_weighted_avg_empty_buys(self):
        """Test weighted average with no buy history"""
        calc = CostBasisCalculator(CostBasisMethod.WEIGHTED_AVG)
        
        result = calc.calculate_weighted_average([])
        
        assert result.cost_basis_per_token == Decimal("0")
        assert result.total_cost_basis_usd == Decimal("0")
        assert "No buy history" in result.notes[0]
    
    @given(buys=st.lists(buy_record_strategy(), min_size=1, max_size=10))
    @settings(max_examples=50)
    def test_weighted_avg_property_consistent(self, buys):
        """Property: Weighted average should be consistent regardless of order"""
        calc = CostBasisCalculator(CostBasisMethod.WEIGHTED_AVG)
        
        # Calculate with original order
        result1 = calc.calculate_weighted_average(buys)
        
        # Calculate with reversed order
        result2 = calc.calculate_weighted_average(list(reversed(buys)))
        
        # Should get same result regardless of order
        assert result1.cost_basis_per_token == result2.cost_basis_per_token
        assert result1.total_cost_basis_usd == result2.total_cost_basis_usd


class TestPositionCalculation:
    """Test cost basis calculation for positions"""
    
    def test_position_with_no_sells(self):
        """Test position calculation when no sells have occurred"""
        calc = CostBasisCalculator(CostBasisMethod.FIFO)
        
        buys = [
            BuyRecord(
                timestamp=datetime(2024, 1, 1),
                amount=Decimal("100"),
                price_per_token=Decimal("1.0"),
                total_cost_usd=Decimal("100"),
                remaining_amount=Decimal("100"),
                tx_signature="tx1",
                slot=1000
            )
        ]
        
        result = calc.calculate_for_position(buys, Decimal("100"))
        
        # No sells, so should use weighted average even for FIFO
        assert result.cost_basis_per_token == Decimal("1.00000000")
        assert result.total_cost_basis_usd == Decimal("100.00")
    
    def test_position_after_partial_sell(self):
        """Test position calculation after partial sells"""
        calc = CostBasisCalculator(CostBasisMethod.FIFO)
        
        buys = [
            BuyRecord(
                timestamp=datetime(2024, 1, 1),
                amount=Decimal("100"),
                price_per_token=Decimal("1.0"),
                total_cost_usd=Decimal("100"),
                remaining_amount=Decimal("100"),
                tx_signature="tx1",
                slot=1000
            ),
            BuyRecord(
                timestamp=datetime(2024, 1, 2),
                amount=Decimal("100"),
                price_per_token=Decimal("2.0"),
                total_cost_usd=Decimal("200"),
                remaining_amount=Decimal("100"),
                tx_signature="tx2",
                slot=2000
            )
        ]
        
        # Current balance is 50 (sold 150 of 200)
        result = calc.calculate_for_position(buys, Decimal("50"))
        
        # FIFO: sold all of first buy + 50 from second
        # Remaining: 50 tokens from second buy at $2 each
        assert result.cost_basis_per_token == Decimal("2.00000000")
        assert result.total_cost_basis_usd == Decimal("100.00")
    
    def test_position_airdrop(self):
        """Test position from airdrop (no purchases)"""
        calc = CostBasisCalculator(CostBasisMethod.WEIGHTED_AVG)
        
        result = calc.calculate_for_position([], Decimal("1000"))
        
        assert result.cost_basis_per_token == Decimal("0")
        assert result.total_cost_basis_usd == Decimal("0")
        assert "Airdrop" in result.notes[0]
    
    def test_position_dust_amount(self):
        """Test position with dust amount"""
        calc = CostBasisCalculator(CostBasisMethod.WEIGHTED_AVG)
        
        buys = [
            BuyRecord(
                timestamp=datetime(2024, 1, 1),
                amount=Decimal("100"),
                price_per_token=Decimal("1.0"),
                total_cost_usd=Decimal("100"),
                remaining_amount=Decimal("100"),
                tx_signature="tx1",
                slot=1000
            )
        ]
        
        # Balance less than dust threshold
        result = calc.calculate_for_position(buys, Decimal("0.000001"))
        
        assert result.cost_basis_per_token == Decimal("0")
        assert result.total_cost_basis_usd == Decimal("0")
        assert "Dust amount" in result.notes[0]
    
    def test_position_closed(self):
        """Test closed position (zero balance)"""
        calc = CostBasisCalculator(CostBasisMethod.FIFO)
        
        buys = [
            BuyRecord(
                timestamp=datetime(2024, 1, 1),
                amount=Decimal("100"),
                price_per_token=Decimal("1.0"),
                total_cost_usd=Decimal("100"),
                remaining_amount=Decimal("0"),
                tx_signature="tx1",
                slot=1000
            )
        ]
        
        result = calc.calculate_for_position(buys, Decimal("0"))
        
        assert result.cost_basis_per_token == Decimal("0")
        assert result.total_cost_basis_usd == Decimal("0")
        assert "Position closed" in result.notes[0]


class TestRealizedPnL:
    """Test realized P&L calculations"""
    
    def test_realized_pnl_profit(self):
        """Test realized P&L calculation for profitable trade"""
        calc = CostBasisCalculator(CostBasisMethod.FIFO)
        
        buys = [
            BuyRecord(
                timestamp=datetime(2024, 1, 1),
                amount=Decimal("100"),
                price_per_token=Decimal("1.0"),
                total_cost_usd=Decimal("100"),
                remaining_amount=Decimal("100"),
                tx_signature="tx1",
                slot=1000
            )
        ]
        
        # Sell 50 tokens at $3 each
        result = calc.calculate_realized_pnl(buys, Decimal("50"), Decimal("3.0"))
        
        assert result.cost_basis_per_token == Decimal("1.00000000")
        assert result.total_cost_basis_usd == Decimal("50.00")
        # Revenue: 50 * $3 = $150
        # Cost: 50 * $1 = $50
        # Profit: $100
        assert result.realized_pnl_usd == Decimal("100.00")
    
    def test_realized_pnl_loss(self):
        """Test realized P&L calculation for losing trade"""
        calc = CostBasisCalculator(CostBasisMethod.WEIGHTED_AVG)
        
        buys = [
            BuyRecord(
                timestamp=datetime(2024, 1, 1),
                amount=Decimal("100"),
                price_per_token=Decimal("2.0"),
                total_cost_usd=Decimal("200"),
                remaining_amount=Decimal("100"),
                tx_signature="tx1",
                slot=1000
            )
        ]
        
        # Sell 50 tokens at $1 each (loss)
        result = calc.calculate_realized_pnl(buys, Decimal("50"), Decimal("1.0"))
        
        assert result.cost_basis_per_token == Decimal("2.00000000")
        assert result.total_cost_basis_usd == Decimal("100.00")
        # Revenue: 50 * $1 = $50
        # Cost: 50 * $2 = $100
        # Loss: -$50
        assert result.realized_pnl_usd == Decimal("-50.00")
    
    @given(
        buys=st.lists(buy_record_strategy(), min_size=1, max_size=5),
        sell_amount=decimal_strategy(min_value=0.1, max_value=100),
        sell_price=decimal_strategy(min_value=0.0001, max_value=1000)
    )
    @settings(max_examples=50)
    def test_realized_pnl_property_consistency(self, buys, sell_amount, sell_price):
        """Property: P&L should equal revenue minus cost basis"""
        calc = CostBasisCalculator(CostBasisMethod.FIFO)
        
        result = calc.calculate_realized_pnl(buys, sell_amount, sell_price)
        
        revenue = sell_amount * sell_price
        expected_pnl = revenue - result.total_cost_basis_usd
        
        # Allow for small rounding differences
        assert abs(result.realized_pnl_usd - expected_pnl) <= Decimal("0.01")


class TestBuyRecordUpdates:
    """Test updating buy records after sells"""
    
    def test_update_buys_fifo(self):
        """Test updating buy records for FIFO after a sell"""
        calc = CostBasisCalculator(CostBasisMethod.FIFO)
        
        buys = [
            BuyRecord(
                timestamp=datetime(2024, 1, 1),
                amount=Decimal("100"),
                price_per_token=Decimal("1.0"),
                total_cost_usd=Decimal("100"),
                remaining_amount=Decimal("100"),
                tx_signature="tx1",
                slot=1000
            ),
            BuyRecord(
                timestamp=datetime(2024, 1, 2),
                amount=Decimal("100"),
                price_per_token=Decimal("2.0"),
                total_cost_usd=Decimal("200"),
                remaining_amount=Decimal("100"),
                tx_signature="tx2",
                slot=2000
            )
        ]
        
        # Sell 150 tokens
        updated_buys = calc.update_buys_after_sell(buys, Decimal("150"))
        
        # First buy should be fully consumed
        assert updated_buys[0].remaining_amount == Decimal("0")
        # Second buy should have 50 remaining
        assert updated_buys[1].remaining_amount == Decimal("50")
    
    def test_update_buys_weighted_avg(self):
        """Test that weighted average doesn't update remaining amounts"""
        calc = CostBasisCalculator(CostBasisMethod.WEIGHTED_AVG)
        
        buys = [
            BuyRecord(
                timestamp=datetime(2024, 1, 1),
                amount=Decimal("100"),
                price_per_token=Decimal("1.0"),
                total_cost_usd=Decimal("100"),
                remaining_amount=Decimal("100"),
                tx_signature="tx1",
                slot=1000
            )
        ]
        
        # Sell 50 tokens
        updated_buys = calc.update_buys_after_sell(buys, Decimal("50"))
        
        # Weighted average shouldn't change remaining amounts
        assert updated_buys[0].remaining_amount == Decimal("100")


class TestBuyRecordCreation:
    """Test BuyRecord creation from trade data"""
    
    def test_from_trade_with_value(self):
        """Test creating BuyRecord from trade with value_usd"""
        trade = {
            "timestamp": datetime(2024, 1, 1),
            "amount": "100.5",
            "value_usd": "201.0",
            "signature": "abc123",
            "slot": 12345
        }
        
        record = BuyRecord.from_trade(trade)
        
        assert record.amount == Decimal("100.5")
        assert record.total_cost_usd == Decimal("201.0")
        assert record.price_per_token == Decimal("2.0")
        assert record.remaining_amount == Decimal("100.5")
        assert record.tx_signature == "abc123"
        assert record.slot == 12345
    
    def test_from_trade_without_value(self):
        """Test creating BuyRecord from trade without value_usd"""
        trade = {
            "timestamp": datetime(2024, 1, 1),
            "amount": "100",
            "signature": "abc123"
        }
        
        record = BuyRecord.from_trade(trade)
        
        assert record.amount == Decimal("100")
        assert record.total_cost_usd == Decimal("0")
        assert record.price_per_token == Decimal("0")
        assert record.slot == 0


class TestEdgeCases:
    """Test edge cases and special scenarios"""
    
    def test_zero_price_buys(self):
        """Test handling of zero-price buys (airdrops)"""
        calc = CostBasisCalculator(CostBasisMethod.FIFO)
        
        buys = [
            BuyRecord(
                timestamp=datetime(2024, 1, 1),
                amount=Decimal("1000"),
                price_per_token=Decimal("0"),
                total_cost_usd=Decimal("0"),
                remaining_amount=Decimal("1000"),
                tx_signature="airdrop",
                slot=1000
            )
        ]
        
        result = calc.calculate_fifo(buys, Decimal("500"))
        
        assert result.cost_basis_per_token == Decimal("0")
        assert result.total_cost_basis_usd == Decimal("0")
    
    def test_mixed_purchases_and_airdrops(self):
        """Test cost basis with mix of purchases and airdrops"""
        calc = CostBasisCalculator(CostBasisMethod.WEIGHTED_AVG)
        
        buys = [
            BuyRecord(
                timestamp=datetime(2024, 1, 1),
                amount=Decimal("100"),
                price_per_token=Decimal("1.0"),
                total_cost_usd=Decimal("100"),
                remaining_amount=Decimal("100"),
                tx_signature="buy1",
                slot=1000
            ),
            BuyRecord(
                timestamp=datetime(2024, 1, 2),
                amount=Decimal("100"),
                price_per_token=Decimal("0"),  # Airdrop
                total_cost_usd=Decimal("0"),
                remaining_amount=Decimal("100"),
                tx_signature="airdrop",
                slot=2000
            )
        ]
        
        result = calc.calculate_weighted_average(buys)
        
        # Total cost: $100, Total amount: 200
        # Average: $100 / 200 = $0.50
        assert result.cost_basis_per_token == Decimal("0.50000000")
        assert result.total_cost_basis_usd == Decimal("100.00")
    
    def test_very_large_numbers(self):
        """Test handling of very large token amounts"""
        calc = CostBasisCalculator(CostBasisMethod.FIFO)
        
        buys = [
            BuyRecord(
                timestamp=datetime(2024, 1, 1),
                amount=Decimal("1000000000000"),  # 1 trillion
                price_per_token=Decimal("0.000001"),
                total_cost_usd=Decimal("1000000"),  # $1M
                remaining_amount=Decimal("1000000000000"),
                tx_signature="whale",
                slot=1000
            )
        ]
        
        # Sell half
        result = calc.calculate_fifo(buys, Decimal("500000000000"))
        
        assert result.cost_basis_per_token == Decimal("0.00000100")
        assert result.total_cost_basis_usd == Decimal("500000.00")
    
    def test_very_small_numbers(self):
        """Test handling of very small token amounts"""
        calc = CostBasisCalculator(CostBasisMethod.WEIGHTED_AVG)
        
        buys = [
            BuyRecord(
                timestamp=datetime(2024, 1, 1),
                amount=Decimal("0.00000001"),  # Tiny amount
                price_per_token=Decimal("1000000"),  # High price
                total_cost_usd=Decimal("0.01"),
                remaining_amount=Decimal("0.00000001"),
                tx_signature="dust",
                slot=1000
            )
        ]
        
        result = calc.calculate_weighted_average(buys)
        
        assert result.cost_basis_per_token == Decimal("1000000.00000000")
    
    @given(
        num_buys=st.integers(min_value=1, max_value=10),
        sell_ratio=st.floats(min_value=0.1, max_value=0.9)
    )
    @settings(max_examples=20)
    def test_property_fifo_order_matters(self, num_buys, sell_ratio):
        """Property: FIFO results depend on chronological order"""
        calc = CostBasisCalculator(CostBasisMethod.FIFO)
        
        # Create buys with increasing prices
        buys = []
        base_time = datetime(2024, 1, 1)
        for i in range(num_buys):
            buys.append(BuyRecord(
                timestamp=base_time + timedelta(days=i),
                amount=Decimal("100"),
                price_per_token=Decimal(str(i + 1)),
                total_cost_usd=Decimal(str((i + 1) * 100)),
                remaining_amount=Decimal("100"),
                tx_signature=f"tx{i}",
                slot=1000 + i
            ))
        
        total_amount = Decimal(str(num_buys * 100))
        sell_amount = total_amount * Decimal(str(sell_ratio))
        
        # Calculate with normal order (should use cheaper buys first)
        result_normal = calc.calculate_fifo(buys, sell_amount)
        
        # Calculate with reversed order (should use expensive buys first)
        result_reversed = calc.calculate_fifo(list(reversed(buys)), sell_amount)
        
        # FIFO with normal order should have lower cost basis
        assert result_normal.cost_basis_per_token <= result_reversed.cost_basis_per_token


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 