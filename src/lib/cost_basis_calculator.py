"""
Cost basis calculation for position tracking
WAL-602: Cost Basis Calculator

Supports FIFO and Weighted Average methods for calculating
the cost basis of token positions.
"""

from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from src.lib.position_models import CostBasisMethod
from src.config.feature_flags import get_cost_basis_method


# Constants
DUST_THRESHOLD_USD = Decimal("0.01")  # Positions worth less than 1 cent
MAX_DECIMAL_PLACES = 8  # Maximum precision for calculations


@dataclass
class BuyRecord:
    """Record of a token purchase for cost basis tracking"""
    timestamp: datetime
    amount: Decimal  # Token amount
    price_per_token: Decimal  # Price in USD per token
    total_cost_usd: Decimal  # Total USD spent
    remaining_amount: Decimal  # Amount not yet sold (for FIFO)
    tx_signature: str
    slot: int
    
    @classmethod
    def from_trade(cls, trade: Dict[str, Any]) -> "BuyRecord":
        """Create BuyRecord from a trade dict"""
        amount = Decimal(str(trade["amount"]))
        
        # Handle None or invalid value_usd
        value_usd = trade.get("value_usd", 0)
        if value_usd is None or value_usd == "":
            total_cost = Decimal("0")
        else:
            try:
                total_cost = Decimal(str(value_usd))
            except (ValueError, InvalidOperation):
                # If conversion fails, default to 0
                total_cost = Decimal("0")
                
        price_per_token = total_cost / amount if amount > 0 else Decimal("0")
        
        return cls(
            timestamp=trade["timestamp"],
            amount=amount,
            price_per_token=price_per_token,
            total_cost_usd=total_cost,
            remaining_amount=amount,  # Initially all unsold
            tx_signature=trade["signature"],
            slot=trade.get("slot", 0)
        )


@dataclass
class CostBasisResult:
    """Result of cost basis calculation"""
    cost_basis_per_token: Decimal
    total_cost_basis_usd: Decimal
    method_used: CostBasisMethod
    realized_pnl_usd: Optional[Decimal] = None
    notes: List[str] = field(default_factory=list)


class CostBasisCalculator:
    """
    Calculates cost basis for token positions using FIFO or Weighted Average
    
    FIFO: First-In-First-Out - sells use oldest purchases first
    Weighted Average: All purchases averaged together
    """
    
    def __init__(self, method: Optional[CostBasisMethod] = None):
        """
        Initialize calculator with specified method
        
        Args:
            method: Cost basis method to use. If None, uses feature flag setting
        """
        if method is None:
            method_str = get_cost_basis_method()
            self.method = CostBasisMethod(method_str)
        else:
            self.method = method
    
    def calculate_fifo(self, buys: List[BuyRecord], sell_amount: Decimal) -> CostBasisResult:
        """
        Calculate cost basis using FIFO (First-In-First-Out) method
        
        Args:
            buys: List of buy records in chronological order
            sell_amount: Amount of tokens being sold
            
        Returns:
            CostBasisResult with FIFO cost basis
        """
        if not buys or sell_amount <= 0:
            return CostBasisResult(
                cost_basis_per_token=Decimal("0"),
                total_cost_basis_usd=Decimal("0"),
                method_used=CostBasisMethod.FIFO,
                notes=["No buys or invalid sell amount"]
            )
        
        remaining_to_sell = sell_amount
        total_cost = Decimal("0")
        used_buys = []
        
        # Process buys in chronological order (FIFO)
        for buy in sorted(buys, key=lambda b: b.timestamp):
            if remaining_to_sell <= 0:
                break
            
            # Skip if this buy has no remaining amount
            if buy.remaining_amount <= 0:
                continue
            
            # Calculate how much from this buy to use
            amount_from_this_buy = min(buy.remaining_amount, remaining_to_sell)
            cost_from_this_buy = amount_from_this_buy * buy.price_per_token
            
            total_cost += cost_from_this_buy
            remaining_to_sell -= amount_from_this_buy
            
            # Track which buys were used
            used_buys.append({
                "tx": buy.tx_signature[:8],
                "amount": float(amount_from_this_buy),
                "price": float(buy.price_per_token)
            })
        
        # Check if we had enough tokens to sell
        if remaining_to_sell > DUST_THRESHOLD_USD:
            notes = [f"Warning: Insufficient buy history, missing {remaining_to_sell:.6f} tokens"]
        else:
            notes = [f"Used {len(used_buys)} buy transactions for FIFO"]
        
        # Calculate average cost basis
        actual_sold = sell_amount - remaining_to_sell
        cost_basis_per_token = total_cost / actual_sold if actual_sold > 0 else Decimal("0")
        
        return CostBasisResult(
            cost_basis_per_token=cost_basis_per_token.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN),
            total_cost_basis_usd=total_cost.quantize(Decimal("0.01"), rounding=ROUND_DOWN),
            method_used=CostBasisMethod.FIFO,
            notes=notes
        )
    
    def calculate_weighted_average(self, buys: List[BuyRecord]) -> CostBasisResult:
        """
        Calculate cost basis using Weighted Average method
        
        Args:
            buys: List of all buy records
            
        Returns:
            CostBasisResult with weighted average cost basis
        """
        if not buys:
            return CostBasisResult(
                cost_basis_per_token=Decimal("0"),
                total_cost_basis_usd=Decimal("0"),
                method_used=CostBasisMethod.WEIGHTED_AVG,
                notes=["No buy history"]
            )
        
        total_amount = Decimal("0")
        total_cost = Decimal("0")
        
        for buy in buys:
            # Use original amount, not remaining (for weighted avg)
            total_amount += buy.amount
            total_cost += buy.total_cost_usd
        
        # Calculate weighted average
        if total_amount > 0:
            cost_basis_per_token = total_cost / total_amount
            notes = [f"Averaged across {len(buys)} purchases"]
        else:
            cost_basis_per_token = Decimal("0")
            notes = ["Zero total amount in buys"]
        
        return CostBasisResult(
            cost_basis_per_token=cost_basis_per_token.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN),
            total_cost_basis_usd=total_cost.quantize(Decimal("0.01"), rounding=ROUND_DOWN),
            method_used=CostBasisMethod.WEIGHTED_AVG,
            notes=notes
        )
    
    def calculate_for_position(self, buys: List[BuyRecord], 
                             current_balance: Decimal) -> CostBasisResult:
        """
        Calculate cost basis for a current position
        
        Args:
            buys: List of buy records
            current_balance: Current token balance
            
        Returns:
            CostBasisResult for the position
        """
        # Handle edge cases
        if not buys:
            # Airdrop case - no purchases
            return CostBasisResult(
                cost_basis_per_token=Decimal("0"),
                total_cost_basis_usd=Decimal("0"),
                method_used=self.method,
                notes=["Airdrop or no purchase history"]
            )
        
        if current_balance <= 0:
            # No balance - position closed
            return CostBasisResult(
                cost_basis_per_token=Decimal("0"),
                total_cost_basis_usd=Decimal("0"),
                method_used=self.method,
                notes=["Position closed (zero balance)"]
            )
        
        # Check for dust amount
        total_buy_amount = sum(buy.amount for buy in buys)
        if current_balance < DUST_THRESHOLD_USD and total_buy_amount > 0:
            # Dust amount - treat as zero
            return CostBasisResult(
                cost_basis_per_token=Decimal("0"),
                total_cost_basis_usd=Decimal("0"),
                method_used=self.method,
                notes=[f"Dust amount: {current_balance:.8f} tokens"]
            )
        
        # Calculate based on method
        if self.method == CostBasisMethod.FIFO:
            # For positions, we need to calculate what was sold
            total_bought = sum(buy.amount for buy in buys)
            total_sold = total_bought - current_balance
            
            if total_sold > 0:
                # Calculate cost basis of remaining tokens after FIFO sells
                result = self.calculate_fifo(buys, total_sold)
                
                # Remaining cost basis
                total_cost = sum(buy.total_cost_usd for buy in buys)
                remaining_cost = total_cost - result.total_cost_basis_usd
                cost_basis_per_token = remaining_cost / current_balance if current_balance > 0 else Decimal("0")
                
                return CostBasisResult(
                    cost_basis_per_token=cost_basis_per_token.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN),
                    total_cost_basis_usd=remaining_cost.quantize(Decimal("0.01"), rounding=ROUND_DOWN),
                    method_used=CostBasisMethod.FIFO,
                    notes=[f"FIFO basis for {current_balance:.6f} remaining tokens"]
                )
            else:
                # No sells yet, use weighted average of all buys
                return self.calculate_weighted_average(buys)
        else:
            # Weighted average method
            result = self.calculate_weighted_average(buys)
            # Adjust total cost for current balance
            result.total_cost_basis_usd = (result.cost_basis_per_token * current_balance).quantize(
                Decimal("0.01"), rounding=ROUND_DOWN
            )
            return result
    
    def calculate_realized_pnl(self, buys: List[BuyRecord], 
                              sell_amount: Decimal,
                              sell_price_per_token: Decimal) -> CostBasisResult:
        """
        Calculate realized P&L for a sell transaction
        
        Args:
            buys: List of buy records
            sell_amount: Amount of tokens sold
            sell_price_per_token: Price per token in USD
            
        Returns:
            CostBasisResult including realized P&L
        """
        # Calculate cost basis
        if self.method == CostBasisMethod.FIFO:
            result = self.calculate_fifo(buys, sell_amount)
        else:
            # For weighted average, calculate basis then apply to sell amount
            avg_result = self.calculate_weighted_average(buys)
            result = CostBasisResult(
                cost_basis_per_token=avg_result.cost_basis_per_token,
                total_cost_basis_usd=(avg_result.cost_basis_per_token * sell_amount).quantize(
                    Decimal("0.01"), rounding=ROUND_DOWN
                ),
                method_used=CostBasisMethod.WEIGHTED_AVG,
                notes=avg_result.notes
            )
        
        # Calculate realized P&L
        sell_value = sell_amount * sell_price_per_token
        result.realized_pnl_usd = (sell_value - result.total_cost_basis_usd).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )
        
        return result
    
    def update_buys_after_sell(self, buys: List[BuyRecord], 
                              sell_amount: Decimal) -> List[BuyRecord]:
        """
        Update buy records after a sell (for FIFO tracking)
        
        Args:
            buys: List of buy records
            sell_amount: Amount sold
            
        Returns:
            Updated list of buy records with remaining amounts adjusted
        """
        if self.method != CostBasisMethod.FIFO:
            # Only FIFO needs to track remaining amounts
            return buys
        
        remaining_to_sell = sell_amount
        updated_buys = []
        
        for buy in sorted(buys, key=lambda b: b.timestamp):
            updated_buy = BuyRecord(
                timestamp=buy.timestamp,
                amount=buy.amount,
                price_per_token=buy.price_per_token,
                total_cost_usd=buy.total_cost_usd,
                remaining_amount=buy.remaining_amount,
                tx_signature=buy.tx_signature,
                slot=buy.slot
            )
            
            if remaining_to_sell > 0 and updated_buy.remaining_amount > 0:
                amount_to_deduct = min(updated_buy.remaining_amount, remaining_to_sell)
                updated_buy.remaining_amount -= amount_to_deduct
                remaining_to_sell -= amount_to_deduct
            
            updated_buys.append(updated_buy)
        
        return updated_buys 