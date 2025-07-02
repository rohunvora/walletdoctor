"""
Unit tests for position tracking data models
WAL-601: Position Tracking Data Model
"""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.lib.position_models import (
    Position, PositionPnL, PositionSnapshot,
    PriceConfidence, CostBasisMethod
)


class TestPosition:
    """Test Position dataclass functionality"""
    
    def test_position_creation(self):
        """Test creating a basic position"""
        position = Position(
            position_id="wallet1:mint1:1706438400",
            wallet="wallet1",
            token_mint="mint1",
            token_symbol="TEST",
            balance=Decimal("1000"),
            cost_basis=Decimal("0.01"),
            cost_basis_usd=Decimal("10.00")
        )
        
        assert position.wallet == "wallet1"
        assert position.token_mint == "mint1"
        assert position.token_symbol == "TEST"
        assert position.balance == Decimal("1000")
        assert position.cost_basis == Decimal("0.01")
        assert position.cost_basis_usd == Decimal("10.00")
        assert position.cost_basis_method == CostBasisMethod.WEIGHTED_AVG
        assert position.is_closed is False
        assert position.decimals == 9
    
    def test_position_auto_id_generation(self):
        """Test automatic position_id generation"""
        position = Position(
            position_id="",  # Empty ID should trigger auto-generation
            wallet="wallet1",
            token_mint="mint1",
            token_symbol="TEST",
            balance=Decimal("1000"),
            cost_basis=Decimal("0.01"),
            cost_basis_usd=Decimal("10.00")
        )
        
        # Check format: wallet:mint:timestamp
        parts = position.position_id.split(":")
        assert len(parts) == 3
        assert parts[0] == "wallet1"
        assert parts[1] == "mint1"
        assert parts[2].isdigit()  # Timestamp
    
    def test_position_numeric_conversion(self):
        """Test automatic conversion of numeric types to Decimal"""
        position = Position(
            position_id="test",
            wallet="wallet1",
            token_mint="mint1",
            token_symbol="TEST",
            balance=1000.5,  # Float
            cost_basis=0.01,  # Float
            cost_basis_usd=10  # Int
        )
        
        assert isinstance(position.balance, Decimal)
        assert position.balance == Decimal("1000.5")
        assert isinstance(position.cost_basis, Decimal)
        assert position.cost_basis == Decimal("0.01")
        assert isinstance(position.cost_basis_usd, Decimal)
        assert position.cost_basis_usd == Decimal("10")
    
    def test_position_to_dict(self):
        """Test serialization to dictionary"""
        now = datetime.utcnow()
        position = Position(
            position_id="wallet1:mint1:1706438400",
            wallet="wallet1",
            token_mint="mint1",
            token_symbol="TEST",
            balance=Decimal("1000.123456"),
            cost_basis=Decimal("0.01"),
            cost_basis_usd=Decimal("10.00"),
            opened_at=now,
            last_trade_at=now,
            trade_count=5,
            decimals=6
        )
        
        data = position.to_dict()
        
        assert data["position_id"] == "wallet1:mint1:1706438400"
        assert data["wallet"] == "wallet1"
        assert data["token_mint"] == "mint1"
        assert data["token_symbol"] == "TEST"
        assert data["balance"] == "1000.123456"
        assert data["cost_basis"] == "0.01"
        assert data["cost_basis_usd"] == "10.00"
        assert data["cost_basis_method"] == "weighted_avg"
        assert data["is_closed"] is False
        assert data["closed_at"] is None
        assert data["trade_count"] == 5
        assert data["decimals"] == 6
        assert data["opened_at"].endswith("Z")  # ISO format with Z
        assert data["last_trade_at"].endswith("Z")
    
    def test_closed_position(self):
        """Test closed position handling"""
        closed_time = datetime.utcnow()
        position = Position(
            position_id="wallet1:mint1:1706438400",
            wallet="wallet1",
            token_mint="mint1",
            token_symbol="TEST",
            balance=Decimal("0"),
            cost_basis=Decimal("0.01"),
            cost_basis_usd=Decimal("10.00"),
            is_closed=True,
            closed_at=closed_time
        )
        
        data = position.to_dict()
        assert data["is_closed"] is True
        assert data["closed_at"] is not None
        assert data["closed_at"].endswith("Z")


class TestPositionPnL:
    """Test PositionPnL dataclass functionality"""
    
    def test_pnl_creation(self):
        """Test creating a PositionPnL object"""
        position = Position(
            position_id="test",
            wallet="wallet1",
            token_mint="mint1",
            token_symbol="TEST",
            balance=Decimal("1000"),
            cost_basis=Decimal("0.01"),
            cost_basis_usd=Decimal("10.00")
        )
        
        pnl = PositionPnL(
            position=position,
            current_price_usd=Decimal("0.02"),
            current_value_usd=Decimal("20.00"),
            unrealized_pnl_usd=Decimal("10.00"),
            unrealized_pnl_pct=Decimal("100.00"),
            price_confidence=PriceConfidence.HIGH,
            last_price_update=datetime.utcnow(),
            price_source="helius_amm"
        )
        
        assert pnl.position == position
        assert pnl.current_price_usd == Decimal("0.02")
        assert pnl.current_value_usd == Decimal("20.00")
        assert pnl.unrealized_pnl_usd == Decimal("10.00")
        assert pnl.unrealized_pnl_pct == Decimal("100.00")
        assert pnl.price_confidence == PriceConfidence.HIGH
        assert pnl.price_source == "helius_amm"
    
    def test_pnl_calculate_profit(self):
        """Test P&L calculation for profitable position"""
        position = Position(
            position_id="test",
            wallet="wallet1",
            token_mint="mint1",
            token_symbol="TEST",
            balance=Decimal("1000"),
            cost_basis=Decimal("0.01"),
            cost_basis_usd=Decimal("10.00")
        )
        
        pnl = PositionPnL.calculate(
            position=position,
            current_price_usd=Decimal("0.02"),
            price_confidence=PriceConfidence.HIGH,
            price_source="birdeye"
        )
        
        assert pnl.current_value_usd == Decimal("20.00")  # 1000 * 0.02
        assert pnl.unrealized_pnl_usd == Decimal("10.00")  # 20 - 10
        assert pnl.unrealized_pnl_pct == Decimal("100.00")  # 100% gain
    
    def test_pnl_calculate_loss(self):
        """Test P&L calculation for losing position"""
        position = Position(
            position_id="test",
            wallet="wallet1",
            token_mint="mint1",
            token_symbol="TEST",
            balance=Decimal("1000"),
            cost_basis=Decimal("0.01"),
            cost_basis_usd=Decimal("10.00")
        )
        
        pnl = PositionPnL.calculate(
            position=position,
            current_price_usd=Decimal("0.005"),
            price_confidence=PriceConfidence.ESTIMATED,
            price_source="coingecko"
        )
        
        assert pnl.current_value_usd == Decimal("5.00")  # 1000 * 0.005
        assert pnl.unrealized_pnl_usd == Decimal("-5.00")  # 5 - 10
        assert pnl.unrealized_pnl_pct == Decimal("-50.00")  # 50% loss
    
    def test_pnl_calculate_airdrop(self):
        """Test P&L calculation for airdropped tokens (0 cost basis)"""
        position = Position(
            position_id="test",
            wallet="wallet1",
            token_mint="mint1",
            token_symbol="AIRDROP",
            balance=Decimal("10000"),
            cost_basis=Decimal("0"),
            cost_basis_usd=Decimal("0")
        )
        
        pnl = PositionPnL.calculate(
            position=position,
            current_price_usd=Decimal("0.001"),
            price_confidence=PriceConfidence.STALE
        )
        
        assert pnl.current_value_usd == Decimal("10.00")  # 10000 * 0.001
        assert pnl.unrealized_pnl_usd == Decimal("10.00")  # All profit
        assert pnl.unrealized_pnl_pct == Decimal("100.00")  # 100% for airdrops
    
    def test_pnl_to_dict(self):
        """Test P&L serialization to dictionary"""
        position = Position(
            position_id="wallet1:mint1:1706438400",
            wallet="wallet1",
            token_mint="mint1",
            token_symbol="TEST",
            balance=Decimal("1000"),
            cost_basis=Decimal("0.01"),
            cost_basis_usd=Decimal("10.00"),
            decimals=6
        )
        
        pnl = PositionPnL(
            position=position,
            current_price_usd=Decimal("0.02"),
            current_value_usd=Decimal("20.00"),
            unrealized_pnl_usd=Decimal("10.00"),
            unrealized_pnl_pct=Decimal("100.00"),
            price_confidence=PriceConfidence.HIGH,
            last_price_update=datetime.utcnow(),
            price_source="helius_amm",
            price_age_seconds=45
        )
        
        data = pnl.to_dict()
        
        assert data["position_id"] == "wallet1:mint1:1706438400"
        assert data["token_symbol"] == "TEST"
        assert data["token_mint"] == "mint1"
        assert data["balance"] == "1000"
        assert data["decimals"] == 6
        assert data["cost_basis_usd"] == "10.00"
        assert data["current_price_usd"] == "0.02"
        assert data["current_value_usd"] == "20.00"
        assert data["unrealized_pnl_usd"] == "10.00"
        assert data["unrealized_pnl_pct"] == "100.00"
        assert data["price_confidence"] == "high"
        assert data["price_age_seconds"] == 45
        assert data["price_source"] == "helius_amm"
        assert data["last_price_update"].endswith("Z")
    
    def test_price_age_calculation(self):
        """Test automatic price age calculation"""
        position = Position(
            position_id="test",
            wallet="wallet1",
            token_mint="mint1",
            token_symbol="TEST",
            balance=Decimal("1000"),
            cost_basis=Decimal("0.01"),
            cost_basis_usd=Decimal("10.00")
        )
        
        # Create with a price from 2 minutes ago
        two_minutes_ago = datetime.utcnow() - timedelta(minutes=2)
        pnl = PositionPnL(
            position=position,
            current_price_usd=Decimal("0.02"),
            current_value_usd=Decimal("20.00"),
            unrealized_pnl_usd=Decimal("10.00"),
            unrealized_pnl_pct=Decimal("100.00"),
            price_confidence=PriceConfidence.ESTIMATED,
            last_price_update=two_minutes_ago
        )
        
        # Price age should be around 120 seconds
        assert 118 <= pnl.price_age_seconds <= 122


class TestPositionSnapshot:
    """Test PositionSnapshot functionality"""
    
    def test_snapshot_from_positions(self):
        """Test creating snapshot from position P&Ls"""
        # Create test positions
        positions = []
        for i in range(3):
            position = Position(
                position_id=f"wallet1:mint{i}:1706438400",
                wallet="wallet1",
                token_mint=f"mint{i}",
                token_symbol=f"TEST{i}",
                balance=Decimal("1000"),
                cost_basis=Decimal("0.01"),
                cost_basis_usd=Decimal("10.00")
            )
            
            pnl = PositionPnL(
                position=position,
                current_price_usd=Decimal("0.02"),
                current_value_usd=Decimal("20.00"),
                unrealized_pnl_usd=Decimal("10.00"),
                unrealized_pnl_pct=Decimal("100.00"),
                price_confidence=PriceConfidence.HIGH,
                last_price_update=datetime.utcnow()
            )
            positions.append(pnl)
        
        snapshot = PositionSnapshot.from_positions("wallet1", positions)
        
        assert snapshot.wallet == "wallet1"
        assert len(snapshot.positions) == 3
        assert snapshot.total_value_usd == Decimal("60.00")  # 3 * 20
        assert snapshot.total_unrealized_pnl_usd == Decimal("30.00")  # 3 * 10
        assert snapshot.total_unrealized_pnl_pct == Decimal("100.00")  # 30/30 * 100
    
    def test_snapshot_mixed_pnl(self):
        """Test snapshot with mixed profit/loss positions"""
        positions = []
        
        # Profitable position
        pos1 = Position(
            position_id="wallet1:mint1:1",
            wallet="wallet1",
            token_mint="mint1",
            token_symbol="PROFIT",
            balance=Decimal("1000"),
            cost_basis=Decimal("0.01"),
            cost_basis_usd=Decimal("10.00")
        )
        pnl1 = PositionPnL(
            position=pos1,
            current_price_usd=Decimal("0.02"),
            current_value_usd=Decimal("20.00"),
            unrealized_pnl_usd=Decimal("10.00"),
            unrealized_pnl_pct=Decimal("100.00"),
            price_confidence=PriceConfidence.HIGH,
            last_price_update=datetime.utcnow()
        )
        positions.append(pnl1)
        
        # Losing position
        pos2 = Position(
            position_id="wallet1:mint2:2",
            wallet="wallet1",
            token_mint="mint2",
            token_symbol="LOSS",
            balance=Decimal("2000"),
            cost_basis=Decimal("0.01"),
            cost_basis_usd=Decimal("20.00")
        )
        pnl2 = PositionPnL(
            position=pos2,
            current_price_usd=Decimal("0.005"),
            current_value_usd=Decimal("10.00"),
            unrealized_pnl_usd=Decimal("-10.00"),
            unrealized_pnl_pct=Decimal("-50.00"),
            price_confidence=PriceConfidence.ESTIMATED,
            last_price_update=datetime.utcnow()
        )
        positions.append(pnl2)
        
        snapshot = PositionSnapshot.from_positions("wallet1", positions)
        
        assert snapshot.total_value_usd == Decimal("30.00")  # 20 + 10
        assert snapshot.total_unrealized_pnl_usd == Decimal("0.00")  # 10 + (-10)
        assert snapshot.total_unrealized_pnl_pct == Decimal("0.00")  # 0/30 * 100
    
    def test_snapshot_to_dict(self):
        """Test snapshot serialization"""
        position = Position(
            position_id="wallet1:mint1:1706438400",
            wallet="wallet1",
            token_mint="mint1",
            token_symbol="TEST",
            balance=Decimal("1000"),
            cost_basis=Decimal("0.01"),
            cost_basis_usd=Decimal("10.00")
        )
        
        pnl = PositionPnL(
            position=position,
            current_price_usd=Decimal("0.02"),
            current_value_usd=Decimal("20.00"),
            unrealized_pnl_usd=Decimal("10.00"),
            unrealized_pnl_pct=Decimal("100.00"),
            price_confidence=PriceConfidence.HIGH,
            last_price_update=datetime.utcnow()
        )
        
        snapshot = PositionSnapshot.from_positions("wallet1", [pnl])
        data = snapshot.to_dict()
        
        assert data["wallet"] == "wallet1"
        assert data["timestamp"].endswith("Z")
        assert len(data["positions"]) == 1
        assert data["summary"]["total_positions"] == 1
        assert data["summary"]["total_value_usd"] == "20.00"
        assert data["summary"]["total_unrealized_pnl_usd"] == "10.00"
        assert data["summary"]["total_unrealized_pnl_pct"] == "100.00"
    
    def test_empty_snapshot(self):
        """Test snapshot with no positions"""
        snapshot = PositionSnapshot.from_positions("wallet1", [])
        
        assert snapshot.wallet == "wallet1"
        assert len(snapshot.positions) == 0
        assert snapshot.total_value_usd == Decimal("0")
        assert snapshot.total_unrealized_pnl_usd == Decimal("0")
        assert snapshot.total_unrealized_pnl_pct == Decimal("0")
        
        data = snapshot.to_dict()
        assert data["summary"]["total_positions"] == 0
        assert data["summary"]["total_value_usd"] == "0"


class TestEnums:
    """Test enum functionality"""
    
    def test_price_confidence_values(self):
        """Test PriceConfidence enum values"""
        assert PriceConfidence.HIGH.value == "high"
        assert PriceConfidence.ESTIMATED.value == "est"
        assert PriceConfidence.STALE.value == "stale"
        assert PriceConfidence.UNAVAILABLE.value == "unavailable"
    
    def test_cost_basis_method_values(self):
        """Test CostBasisMethod enum values"""
        assert CostBasisMethod.FIFO.value == "fifo"
        assert CostBasisMethod.WEIGHTED_AVG.value == "weighted_avg"


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 