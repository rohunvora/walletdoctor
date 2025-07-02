"""
Position Builder Service
WAL-603: Build positions from trade history

Processes trades chronologically to build position objects
with accurate cost basis and balance tracking.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Tuple, Optional, Any
from collections import defaultdict
from dataclasses import dataclass, field
import logging

from src.lib.position_models import Position, CostBasisMethod
from src.lib.cost_basis_calculator import (
    CostBasisCalculator, BuyRecord, CostBasisResult, DUST_THRESHOLD_USD
)
from src.config.feature_flags import get_cost_basis_method, positions_enabled

logger = logging.getLogger(__name__)

# Constants
SOL_MINT = "So11111111111111111111111111111111111111112"
SOL_SYMBOL = "SOL"
ZERO = Decimal("0")
# WAL-606e: Spam token filter thresholds
MIN_POOL_SOL = Decimal("0.01")  # Minimum pooled SOL for valid tokens


@dataclass
class TokenTradeGroup:
    """Groups trades by token for position building"""
    token_mint: str
    token_symbol: str
    trades: List[Dict[str, Any]] = field(default_factory=list)
    buys: List[BuyRecord] = field(default_factory=list)
    current_balance: Decimal = ZERO
    total_bought: Decimal = ZERO
    total_sold: Decimal = ZERO
    total_invested_usd: Decimal = ZERO  # WAL-606e: Track total invested
    first_trade_time: Optional[datetime] = None
    last_trade_time: Optional[datetime] = None
    
    def add_trade(self, trade: Dict[str, Any]):
        """Add a trade to this token group"""
        self.trades.append(trade)
        
        # Update timestamps
        trade_time = trade.get("timestamp")
        if isinstance(trade_time, str):
            trade_time = datetime.fromisoformat(trade_time.replace("Z", "+00:00"))
        
        if trade_time:
            if self.first_trade_time is None or trade_time < self.first_trade_time:
                self.first_trade_time = trade_time
            if self.last_trade_time is None or trade_time > self.last_trade_time:
                self.last_trade_time = trade_time


class PositionBuilder:
    """
    Builds position objects from trade history
    
    Processes trades chronologically to track:
    - Token balances
    - Cost basis (FIFO or weighted average)
    - Open/closed positions
    - Realized P&L
    """
    
    def __init__(self, cost_basis_method: Optional[CostBasisMethod] = None):
        """
        Initialize position builder
        
        Args:
            cost_basis_method: Method to use for cost basis calculation
        """
        if cost_basis_method is None:
            method_str = get_cost_basis_method()
            self.cost_basis_method = CostBasisMethod(method_str)
        else:
            self.cost_basis_method = cost_basis_method
        
        self.calculator = CostBasisCalculator(self.cost_basis_method)
    
    def build_positions_from_trades(self, trades: List[Dict[str, Any]], 
                                   wallet: str) -> List[Position]:
        """
        Build positions from a list of trades
        
        Args:
            trades: List of trade dictionaries
            wallet: Wallet address
            
        Returns:
            List of Position objects (open positions only)
        """
        if not positions_enabled():
            logger.warning("Position tracking is disabled via feature flag")
            return []
        
        # Group trades by token
        token_groups = self._group_trades_by_token(trades)
        
        # Build position for each token
        positions = []
        spam_filtered = 0
        
        # Track SOL balance changes for native position
        sol_balance = ZERO
        for trade in trades:
            # Track SOL balance changes
            if trade.get("token_in", {}).get("mint") == SOL_MINT:
                sol_balance -= Decimal(str(trade.get("token_in", {}).get("amount", 0)))
            if trade.get("token_out", {}).get("mint") == SOL_MINT:
                sol_balance += Decimal(str(trade.get("token_out", {}).get("amount", 0)))
        
        # Create SOL position if balance > 0.01
        if sol_balance > Decimal("0.01"):
            sol_position = Position(
                position_id="",  # Will be auto-generated
                wallet=wallet,
                token_mint=SOL_MINT,
                token_symbol=SOL_SYMBOL,
                balance=sol_balance,
                cost_basis=ZERO,  # Native token, no cost basis
                cost_basis_usd=ZERO,
                cost_basis_method=self.cost_basis_method,
                opened_at=datetime.utcnow(),
                last_trade_at=datetime.utcnow(),
                last_update_slot=0,
                last_update_time=datetime.utcnow(),
                is_closed=False,
                trade_count=0,  # Not tracking individual SOL trades
                decimals=9  # SOL has 9 decimals
            )
            positions.append(sol_position)
        
        # Build positions for other tokens
        raw_positions_count = len(token_groups)
        logger.info(f"[FILTER-BEFORE] positions={raw_positions_count}")
        
        for token_mint, group in token_groups.items():
            position = self._build_position_for_token(wallet, group)
            if position and not position.is_closed:
                # WAL-606e: Check if this is a spam token
                if self._is_spam_token(group):
                    spam_filtered += 1
                    logger.debug(f"Filtered spam token {group.token_symbol}: no buys or low TVL")
                    continue
                positions.append(position)
            elif position is None:
                logger.debug(f"Token {group.token_symbol} returned None position (likely balance <= 0)")
            else:
                logger.debug(f"Token {group.token_symbol} position is closed")
        
        logger.info(f"[FILTER-AFTER] positions={len(positions)} filtered={spam_filtered}")
        logger.info(f"Built {len(positions)} open positions from {len(trades)} trades (filtered {spam_filtered} spam tokens)")
        return positions
    
    def _is_spam_token(self, group: TokenTradeGroup) -> bool:
        """
        WAL-606e: Check if a token is spam (airdrop with no buys or very low TVL)
        
        Args:
            group: Token trade group
            
        Returns:
            True if token should be filtered as spam
        """
        # Check if there are no buy trades (airdrop only)
        if not group.buys or group.total_invested_usd == ZERO:
            # This is an airdrop - check if it has meaningful TVL
            # For now, we'll filter all airdrops as we don't have pool data
            # In production, we'd check pool SOL < MIN_POOL_SOL
            return True
        
        return False
    
    def _group_trades_by_token(self, trades: List[Dict[str, Any]]) -> Dict[str, TokenTradeGroup]:
        """
        Group trades by token mint address
        
        Args:
            trades: List of trades
            
        Returns:
            Dictionary mapping token mint to TokenTradeGroup
        """
        groups: Dict[str, TokenTradeGroup] = {}
        
        for trade in trades:
            # Determine which token (not SOL) is involved
            token_mint, token_symbol = self._extract_token_info(trade)
            
            if token_mint == SOL_MINT:
                # Skip SOL-only trades (shouldn't happen)
                continue
            
            # Create group if needed
            if token_mint not in groups:
                groups[token_mint] = TokenTradeGroup(
                    token_mint=token_mint,
                    token_symbol=token_symbol
                )
            
            # Add trade to group
            groups[token_mint].add_trade(trade)
        
        return groups
    
    def _extract_token_info(self, trade: Dict[str, Any]) -> Tuple[str, str]:
        """
        Extract the non-SOL token from a trade
        
        Args:
            trade: Trade dictionary
            
        Returns:
            Tuple of (token_mint, token_symbol)
        """
        # Check token_in first
        if trade.get("token_in", {}).get("mint") != SOL_MINT:
            return (
                trade["token_in"]["mint"],
                trade["token_in"].get("symbol", "UNKNOWN")
            )
        # Otherwise must be token_out
        elif trade.get("token_out", {}).get("mint") != SOL_MINT:
            return (
                trade["token_out"]["mint"], 
                trade["token_out"].get("symbol", "UNKNOWN")
            )
        else:
            # Both are SOL? Shouldn't happen
            logger.warning(f"Trade {trade.get('signature', 'unknown')} has SOL on both sides")
            return (SOL_MINT, SOL_SYMBOL)
    
    def _build_position_for_token(self, wallet: str, 
                                  group: TokenTradeGroup) -> Optional[Position]:
        """
        Build a position for a single token from its trades
        
        Args:
            wallet: Wallet address
            group: Token trade group
            
        Returns:
            Position object or None if position is closed/dust
        """
        # Sort trades chronologically
        sorted_trades = sorted(group.trades, key=lambda t: t["timestamp"])
        
        # Process each trade
        for trade in sorted_trades:
            self._process_trade_for_position(trade, group)
        
        # Check if position is closed or dust
        if group.current_balance <= 0:
            logger.debug(f"Position for {group.token_symbol} is closed: balance={group.current_balance}, buys={len(group.buys)}, trades={len(group.trades)}")
            return None
        
        # Calculate cost basis for remaining balance
        cost_basis_result = self.calculator.calculate_for_position(
            group.buys, group.current_balance
        )
        
        # Create position object
        position = Position(
            position_id="",  # Will be auto-generated
            wallet=wallet,
            token_mint=group.token_mint,
            token_symbol=group.token_symbol,
            balance=group.current_balance,
            cost_basis=cost_basis_result.cost_basis_per_token,
            cost_basis_usd=cost_basis_result.total_cost_basis_usd,
            cost_basis_method=self.cost_basis_method,
            opened_at=group.first_trade_time or datetime.utcnow(),
            last_trade_at=group.last_trade_time or datetime.utcnow(),
            last_update_slot=sorted_trades[-1].get("slot", 0) if sorted_trades else 0,
            last_update_time=datetime.utcnow(),
            is_closed=False,
            trade_count=len(group.trades),
            decimals=self._get_token_decimals(sorted_trades)
        )
        
        # Add remaining balance info to last trade
        if sorted_trades:
            sorted_trades[-1]["remaining_balance"] = group.current_balance
            sorted_trades[-1]["position_id"] = position.position_id
        
        return position
    
    def _process_trade_for_position(self, trade: Dict[str, Any], 
                                    group: TokenTradeGroup):
        """
        Process a single trade for position tracking
        
        Args:
            trade: Trade dictionary
            group: Token trade group to update
        """
        action = trade.get("action", "").lower()
        
        if action == "buy":
            # Add to position
            amount = Decimal(str(trade.get("amount", 0)))
            group.current_balance += amount
            group.total_bought += amount
            
            # WAL-606e: Track invested amount
            value_usd = trade.get("value_usd")
            if value_usd is not None:
                group.total_invested_usd += Decimal(str(value_usd))
            
            # Create buy record for cost basis
            buy_record = BuyRecord.from_trade(trade)
            group.buys.append(buy_record)
            
            # Update trade with position info
            trade["remaining_balance"] = group.current_balance
            trade["cost_basis_method"] = self.cost_basis_method.value
            trade["position_closed"] = False
            
        elif action == "sell":
            # Reduce position
            amount = Decimal(str(trade.get("amount", 0)))
            group.current_balance -= amount
            group.total_sold += amount
            
            # Calculate realized P&L if we have cost basis
            if group.buys and trade.get("price"):
                sell_price = Decimal(str(trade["price"]))
                result = self.calculator.calculate_realized_pnl(
                    group.buys, amount, sell_price
                )
                trade["pnl_usd"] = float(result.realized_pnl_usd)
                
                # Update buy records for FIFO
                if self.cost_basis_method == CostBasisMethod.FIFO:
                    group.buys = self.calculator.update_buys_after_sell(
                        group.buys, amount
                    )
            
            
            # Update trade with position info
            trade["remaining_balance"] = group.current_balance
            trade["cost_basis_method"] = self.cost_basis_method.value
            trade["position_closed"] = group.current_balance <= 0
            
            # If position is closed, clear buy records for clean slate
            if group.current_balance <= 0:
                group.buys = []
    
    def _get_token_decimals(self, trades: List[Dict[str, Any]]) -> int:
        """
        Extract token decimals from trade data
        
        Args:
            trades: List of trades for a token
            
        Returns:
            Token decimals (default 9)
        """
        # Try to find decimals in any trade
        for trade in trades:
            # Get the non-SOL token from the trade
            token_mint, _ = self._extract_token_info(trade)
            
            # Check token_in
            if trade.get("token_in", {}).get("mint") == token_mint:
                decimals = trade.get("token_in", {}).get("decimals")
                if decimals is not None:
                    return decimals
            
            # Check token_out
            if trade.get("token_out", {}).get("mint") == token_mint:
                decimals = trade.get("token_out", {}).get("decimals")
                if decimals is not None:
                    return decimals
        
        # Default to 9 (common for Solana tokens)
        return 9
    
    def get_position_history(self, trades: List[Dict[str, Any]], 
                           wallet: str, 
                           token_mint: str) -> List[Dict[str, Any]]:
        """
        Get historical position snapshots for a specific token
        
        Args:
            trades: All trades for the wallet
            wallet: Wallet address
            token_mint: Token mint to track
            
        Returns:
            List of position snapshots over time
        """
        # Filter trades for this token
        token_trades = [
            t for t in trades 
            if self._extract_token_info(t)[0] == token_mint
        ]
        
        if not token_trades:
            return []
        
        # Sort chronologically
        token_trades.sort(key=lambda t: t["timestamp"])
        
        # Build snapshots after each trade
        snapshots = []
        group = TokenTradeGroup(
            token_mint=token_mint,
            token_symbol=self._extract_token_info(token_trades[0])[1]
        )
        
        for trade in token_trades:
            # Process trade
            group.add_trade(trade)
            self._process_trade_for_position(trade, group)
            
            # Create snapshot
            if group.current_balance > 0:
                cost_basis_result = self.calculator.calculate_for_position(
                    group.buys, group.current_balance
                )
                
                snapshot = {
                    "timestamp": trade["timestamp"],
                    "after_trade": trade["signature"],
                    "action": trade["action"],
                    "balance": float(group.current_balance),
                    "cost_basis_per_token": float(cost_basis_result.cost_basis_per_token),
                    "cost_basis_usd": float(cost_basis_result.total_cost_basis_usd),
                    "total_bought": float(group.total_bought),
                    "total_sold": float(group.total_sold)
                }
                snapshots.append(snapshot)
        
        return snapshots
    
    def calculate_portfolio_summary(self, positions: List[Position]) -> Dict[str, Any]:
        """
        Calculate summary statistics for a portfolio of positions
        
        Args:
            positions: List of Position objects
            
        Returns:
            Portfolio summary dictionary
        """
        if not positions:
            return {
                "total_positions": 0,
                "total_cost_basis_usd": 0.0,
                "tokens": []
            }
        
        total_cost = sum(p.cost_basis_usd for p in positions)
        
        # Group by token for summary
        token_summary = []
        for position in positions:
            token_summary.append({
                "symbol": position.token_symbol,
                "mint": position.token_mint,
                "balance": float(position.balance),
                "cost_basis_usd": float(position.cost_basis_usd),
                "cost_basis_per_token": float(position.cost_basis),
                "last_trade": position.last_trade_at.isoformat() if position.last_trade_at else None
            })
        
        return {
            "total_positions": len(positions),
            "total_cost_basis_usd": float(total_cost),
            "cost_basis_method": self.cost_basis_method.value,
            "tokens": sorted(token_summary, key=lambda t: t["cost_basis_usd"], reverse=True)
        } 