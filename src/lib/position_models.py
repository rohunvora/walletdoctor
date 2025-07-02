"""
Position tracking data models for unrealized P&L calculation
WAL-601: Position Tracking Data Model
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any
from enum import Enum


class PriceConfidence(Enum):
    """Price confidence levels based on source and age"""
    HIGH = "high"       # Direct AMM/DEX price, < 60s old
    ESTIMATED = "est"   # Secondary source or 60s-5min old
    STALE = "stale"     # > 5 minutes old
    UNAVAILABLE = "unavailable"  # No price data


class CostBasisMethod(Enum):
    """Cost basis calculation methods"""
    FIFO = "fifo"                   # First In, First Out
    WEIGHTED_AVG = "weighted_avg"   # Weighted Average


@dataclass
class Position:
    """
    Represents an open token position for a wallet
    Tracks holdings and cost basis information
    """
    position_id: str  # Format: {wallet}:{mint}:{opened_timestamp}
    wallet: str
    token_mint: str
    token_symbol: str
    balance: Decimal  # Current token balance
    cost_basis: Decimal  # Average cost per token (in SOL or USD)
    cost_basis_usd: Decimal  # Total USD invested
    cost_basis_method: CostBasisMethod = CostBasisMethod.WEIGHTED_AVG
    
    # Tracking metadata
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_trade_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_update_slot: int = 0
    last_update_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Position state
    is_closed: bool = False
    closed_at: Optional[datetime] = None
    
    # Additional metadata
    trade_count: int = 0  # Number of trades in this position
    decimals: int = 9  # Token decimals for display
    
    def __post_init__(self):
        """Ensure Decimal types and generate position_id if needed"""
        if isinstance(self.balance, (int, float)):
            self.balance = Decimal(str(self.balance))
        if isinstance(self.cost_basis, (int, float)):
            self.cost_basis = Decimal(str(self.cost_basis))
        if isinstance(self.cost_basis_usd, (int, float)):
            self.cost_basis_usd = Decimal(str(self.cost_basis_usd))
        
        # Generate position_id if not provided
        if not self.position_id:
            timestamp = int(self.opened_at.timestamp())
            self.position_id = f"{self.wallet}:{self.token_mint}:{timestamp}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "position_id": self.position_id,
            "wallet": self.wallet,
            "token_mint": self.token_mint,
            "token_symbol": self.token_symbol,
            "balance": str(self.balance),
            "decimals": self.decimals,
            "cost_basis": str(self.cost_basis),
            "cost_basis_usd": str(self.cost_basis_usd),
            "cost_basis_method": self.cost_basis_method.value,
            "opened_at": self.opened_at.isoformat() + "Z",
            "last_trade_at": self.last_trade_at.isoformat() + "Z",
            "last_update_slot": self.last_update_slot,
            "last_update_time": self.last_update_time.isoformat() + "Z",
            "is_closed": self.is_closed,
            "closed_at": self.closed_at.isoformat() + "Z" if self.closed_at else None,
            "trade_count": self.trade_count,
        }


@dataclass
class PositionPnL:
    """
    Represents P&L calculations for a position
    Includes current market values and unrealized gains/losses
    """
    position: Position
    current_price_usd: Decimal
    current_value_usd: Decimal
    unrealized_pnl_usd: Decimal
    unrealized_pnl_pct: Decimal
    price_confidence: PriceConfidence
    last_price_update: datetime
    
    # Additional price metadata
    price_source: str = "unknown"  # e.g., "helius_amm", "birdeye", "coingecko"
    price_age_seconds: int = 0
    
    def __post_init__(self):
        """Ensure Decimal types and calculate derived fields"""
        if isinstance(self.current_price_usd, (int, float)):
            self.current_price_usd = Decimal(str(self.current_price_usd))
        if isinstance(self.current_value_usd, (int, float)):
            self.current_value_usd = Decimal(str(self.current_value_usd))
        if isinstance(self.unrealized_pnl_usd, (int, float)):
            self.unrealized_pnl_usd = Decimal(str(self.unrealized_pnl_usd))
        if isinstance(self.unrealized_pnl_pct, (int, float)):
            self.unrealized_pnl_pct = Decimal(str(self.unrealized_pnl_pct))
        
        # Calculate price age if not set
        if self.price_age_seconds == 0 and self.last_price_update:
            now = datetime.now(timezone.utc) if self.last_price_update.tzinfo else datetime.utcnow()
            self.price_age_seconds = int((now - self.last_price_update).total_seconds())
    
    @classmethod
    def calculate(cls, position: Position, current_price_usd: Decimal, 
                  price_confidence: PriceConfidence, price_source: str = "unknown") -> "PositionPnL":
        """
        Calculate P&L for a position given current price
        
        Args:
            position: The position to calculate P&L for
            current_price_usd: Current token price in USD
            price_confidence: Confidence level of the price
            price_source: Source of the price data
            
        Returns:
            PositionPnL object with calculated values
        """
        current_value_usd = position.balance * current_price_usd
        unrealized_pnl_usd = current_value_usd - position.cost_basis_usd
        
        # Calculate percentage gain/loss
        if position.cost_basis_usd > 0:
            unrealized_pnl_pct = (unrealized_pnl_usd / position.cost_basis_usd) * Decimal("100")
        else:
            # If cost basis is 0 (e.g., airdrop), use 100% if positive value
            unrealized_pnl_pct = Decimal("100") if current_value_usd > 0 else Decimal("0")
        
        return cls(
            position=position,
            current_price_usd=current_price_usd,
            current_value_usd=current_value_usd,
            unrealized_pnl_usd=unrealized_pnl_usd,
            unrealized_pnl_pct=unrealized_pnl_pct,
            price_confidence=price_confidence,
            last_price_update=datetime.now(timezone.utc),
            price_source=price_source
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "position_id": self.position.position_id,
            "token_symbol": self.position.token_symbol,
            "token_mint": self.position.token_mint,
            "balance": str(self.position.balance),
            "decimals": self.position.decimals,
            "cost_basis_usd": str(self.position.cost_basis_usd),
            "current_price_usd": str(self.current_price_usd),
            "current_value_usd": str(self.current_value_usd),
            "unrealized_pnl_usd": str(self.unrealized_pnl_usd),
            "unrealized_pnl_pct": str(self.unrealized_pnl_pct),
            "price_confidence": self.price_confidence.value,
            "price_age_seconds": self.price_age_seconds,
            "last_price_update": self.last_price_update.isoformat() + "Z",
            "price_source": self.price_source,
        }


@dataclass
class PositionSnapshot:
    """
    Represents a point-in-time snapshot of all positions
    Used for historical tracking and performance analysis
    """
    wallet: str
    timestamp: datetime
    positions: list[PositionPnL]
    total_value_usd: Decimal
    total_unrealized_pnl_usd: Decimal
    total_unrealized_pnl_pct: Decimal
    
    @classmethod
    def from_positions(cls, wallet: str, position_pnls: list[PositionPnL]) -> "PositionSnapshot":
        """Create snapshot from list of position P&Ls"""
        # Explicitly cast sums to Decimal to satisfy type checker
        total_value = Decimal(str(sum(p.current_value_usd for p in position_pnls))) if position_pnls else Decimal("0")
        total_cost_basis = Decimal(str(sum(p.position.cost_basis_usd for p in position_pnls))) if position_pnls else Decimal("0")
        total_unrealized_pnl = Decimal(str(sum(p.unrealized_pnl_usd for p in position_pnls))) if position_pnls else Decimal("0")
        
        if total_cost_basis > 0:
            total_unrealized_pnl_pct = (total_unrealized_pnl / total_cost_basis) * Decimal("100")
        else:
            total_unrealized_pnl_pct = Decimal("0")
        
        return cls(
            wallet=wallet,
            timestamp=datetime.now(timezone.utc),
            positions=position_pnls,
            total_value_usd=total_value,
            total_unrealized_pnl_usd=total_unrealized_pnl,
            total_unrealized_pnl_pct=total_unrealized_pnl_pct
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "wallet": self.wallet,
            "timestamp": self.timestamp.isoformat() + "Z",
            "positions": [p.to_dict() for p in self.positions],
            "summary": {
                "total_positions": len(self.positions),
                "total_value_usd": str(self.total_value_usd),
                "total_unrealized_pnl_usd": str(self.total_unrealized_pnl_usd),
                "total_unrealized_pnl_pct": f"{self.total_unrealized_pnl_pct:.2f}",  # Format to 2 decimals
            }
        } 