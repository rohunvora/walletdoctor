"""
Unrealized P&L Calculator
WAL-604: Calculate unrealized P&L for open positions

Integrates with market cap service to get current prices
and calculates unrealized gains/losses.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass

from src.lib.position_models import Position, PositionPnL, PriceConfidence
from src.lib.mc_calculator import MarketCapCalculator, MarketCapResult, calculate_market_cap
from src.lib.mc_calculator import CONFIDENCE_HIGH, CONFIDENCE_EST, CONFIDENCE_UNAVAILABLE
from src.config.feature_flags import should_calculate_unrealized_pnl

logger = logging.getLogger(__name__)

# Constants
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOL_MINT = "So11111111111111111111111111111111111111112"
ZERO = Decimal("0")

# Price freshness thresholds
PRICE_FRESH_SECONDS = 60      # < 1 minute = fresh
PRICE_RECENT_SECONDS = 300    # < 5 minutes = recent  
PRICE_STALE_SECONDS = 900     # < 15 minutes = stale
# > 15 minutes = very stale

# Batch processing
DEFAULT_BATCH_SIZE = 20
MAX_CONCURRENT_REQUESTS = 5


@dataclass
class UnrealizedPnLResult:
    """Result from unrealized P&L calculation"""
    position: Position
    current_price_usd: Optional[Decimal]
    current_value_usd: Optional[Decimal]
    unrealized_pnl_usd: Optional[Decimal]
    unrealized_pnl_pct: Optional[Decimal]
    price_confidence: PriceConfidence
    price_source: Optional[str]
    last_price_update: datetime
    error: Optional[str] = None


class UnrealizedPnLCalculator:
    """
    Calculates unrealized P&L for positions
    
    Integrates with market cap service for current prices
    and provides confidence scoring based on price age.
    """
    
    def __init__(self, market_cap_calculator: Optional[MarketCapCalculator] = None):
        """
        Initialize calculator
        
        Args:
            market_cap_calculator: Optional MC calculator instance
        """
        self.mc_calculator = market_cap_calculator or MarketCapCalculator()
        
    async def calculate_unrealized_pnl(
        self, 
        position: Position,
        current_price_usd: Optional[Decimal] = None
    ) -> UnrealizedPnLResult:
        """
        Calculate unrealized P&L for a single position
        
        Args:
            position: Position to calculate P&L for
            current_price_usd: Optional current price (will fetch if not provided)
            
        Returns:
            UnrealizedPnLResult with calculations and confidence
        """
        if not should_calculate_unrealized_pnl():
            logger.warning("Unrealized P&L calculation is disabled via feature flag")
            return self._create_error_result(
                position, 
                "Unrealized P&L disabled"
            )
        
        try:
            # Get current price if not provided
            if current_price_usd is None:
                price_result = await self._fetch_current_price(position.token_mint)
                if price_result is None:
                    return self._create_error_result(
                        position,
                        "Price unavailable"
                    )
                current_price_usd, confidence, source, timestamp = price_result
            else:
                # Use provided price with high confidence
                confidence = PriceConfidence.HIGH
                source = "provided"
                timestamp = datetime.now(timezone.utc)
            
            # Calculate current value
            current_value_usd = position.balance * current_price_usd
            
            # Calculate unrealized P&L
            unrealized_pnl_usd = current_value_usd - position.cost_basis_usd
            
            # Calculate percentage
            if position.cost_basis_usd > 0:
                unrealized_pnl_pct = (unrealized_pnl_usd / position.cost_basis_usd) * Decimal("100")
            else:
                # 100% gain if cost basis is 0 (e.g., airdrop)
                unrealized_pnl_pct = Decimal("100") if unrealized_pnl_usd > 0 else ZERO
            
            # Create PositionPnL object
            position_pnl = PositionPnL(
                position=position,
                current_price_usd=current_price_usd,
                current_value_usd=current_value_usd,
                unrealized_pnl_usd=unrealized_pnl_usd,
                unrealized_pnl_pct=unrealized_pnl_pct,
                price_confidence=confidence,
                last_price_update=timestamp
            )
            
            # Return result
            return UnrealizedPnLResult(
                position=position,
                current_price_usd=current_price_usd,
                current_value_usd=current_value_usd,
                unrealized_pnl_usd=unrealized_pnl_usd,
                unrealized_pnl_pct=unrealized_pnl_pct,
                price_confidence=confidence,
                price_source=source,
                last_price_update=timestamp
            )
            
        except Exception as e:
            logger.error(f"Error calculating unrealized P&L for {position.token_symbol}: {e}")
            return self._create_error_result(position, str(e))
    
    async def calculate_batch_unrealized_pnl(
        self,
        positions: List[Position],
        batch_size: int = DEFAULT_BATCH_SIZE,
        skip_pricing: bool = False
    ) -> List[UnrealizedPnLResult]:
        """
        Calculate unrealized P&L for multiple positions in batch
        
        Args:
            positions: List of positions
            batch_size: Number of positions per batch
            skip_pricing: If True, skip price fetching (beta mode)
            
        Returns:
            List of UnrealizedPnLResult objects
        """
        if not positions:
            return []
        
        results = []
        
        # If skip_pricing, return positions without prices
        if skip_pricing:
            for position in positions:
                results.append(UnrealizedPnLResult(
                    position=position,
                    current_price_usd=None,
                    current_value_usd=None,
                    unrealized_pnl_usd=None,
                    unrealized_pnl_pct=None,
                    price_confidence=PriceConfidence.UNAVAILABLE,
                    price_source=None,
                    last_price_update=datetime.now(timezone.utc),
                    error=None
                ))
            return results
        
        # Process in batches to avoid overwhelming the API
        for i in range(0, len(positions), batch_size):
            batch = positions[i:i + batch_size]
            
            # Create tasks for this batch
            tasks = [
                self.calculate_unrealized_pnl(position)
                for position in batch
            ]
            
            # Execute batch concurrently
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle results
            for position, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Batch calculation error for {position.token_symbol}: {result}")
                    results.append(self._create_error_result(position, str(result)))
                else:
                    results.append(result)
        
        return results
    
    async def _fetch_current_price(
        self,
        token_mint: str
    ) -> Optional[Tuple[Decimal, PriceConfidence, str, datetime]]:
        """
        Fetch current price for a token
        
        Args:
            token_mint: Token mint address
            
        Returns:
            Tuple of (price, confidence, source, timestamp) or None
        """
        try:
            # Use market cap calculator to get price
            mc_result = await self.mc_calculator.calculate_market_cap(
                token_mint,
                slot=None,  # Current slot
                timestamp=None  # Current time
            )
            
            if mc_result.price is None:
                logger.warning(f"No price available for {token_mint}")
                return None
            
            # Convert confidence from MC service to our enum
            confidence = self._convert_confidence(
                mc_result.confidence,
                mc_result.timestamp
            )
            
            return (
                Decimal(str(mc_result.price)),
                confidence,
                mc_result.source or "unknown",
                datetime.fromtimestamp(mc_result.timestamp, tz=timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"Error fetching price for {token_mint}: {e}")
            return None
    
    def _convert_confidence(
        self,
        mc_confidence: str,
        timestamp: int
    ) -> PriceConfidence:
        """
        Convert market cap confidence to price confidence
        considering both source and age
        
        Args:
            mc_confidence: Confidence from MC service
            timestamp: Unix timestamp of price
            
        Returns:
            PriceConfidence enum value
        """
        # Calculate age
        now = datetime.now(timezone.utc)
        price_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        age_seconds = (now - price_time).total_seconds()
        
        # Start with MC confidence
        if mc_confidence == CONFIDENCE_UNAVAILABLE:
            return PriceConfidence.UNAVAILABLE
        
        # Degrade confidence based on age
        if mc_confidence == CONFIDENCE_HIGH:
            if age_seconds < PRICE_FRESH_SECONDS:
                return PriceConfidence.HIGH
            elif age_seconds < PRICE_RECENT_SECONDS:
                return PriceConfidence.ESTIMATED
            else:
                return PriceConfidence.STALE
        else:  # CONFIDENCE_EST
            if age_seconds < PRICE_RECENT_SECONDS:
                return PriceConfidence.ESTIMATED
            else:
                return PriceConfidence.STALE
    
    def _create_error_result(
        self,
        position: Position,
        error: str
    ) -> UnrealizedPnLResult:
        """Create an error result for a position"""
        return UnrealizedPnLResult(
            position=position,
            current_price_usd=None,
            current_value_usd=None,
            unrealized_pnl_usd=None,
            unrealized_pnl_pct=None,
            price_confidence=PriceConfidence.UNAVAILABLE,
            price_source=None,
            last_price_update=datetime.now(timezone.utc),
            error=error
        )
    
    async def calculate_portfolio_unrealized_pnl(
        self,
        positions: List[Position]
    ) -> Dict[str, Any]:
        """
        Calculate aggregate unrealized P&L for a portfolio
        
        Args:
            positions: List of positions
            
        Returns:
            Dictionary with portfolio-level statistics
        """
        if not positions:
            return {
                "total_cost_basis_usd": 0.0,
                "total_current_value_usd": 0.0,
                "total_unrealized_pnl_usd": 0.0,
                "total_unrealized_pnl_pct": 0.0,
                "positions_with_prices": 0,
                "positions_without_prices": 0,
                "confidence_breakdown": {
                    "high": 0,
                    "est": 0,
                    "stale": 0,
                    "unavailable": 0
                }
            }
        
        # Calculate P&L for all positions
        results = await self.calculate_batch_unrealized_pnl(positions)
        
        # Aggregate statistics
        total_cost_basis = sum(p.cost_basis_usd for p in positions)
        total_current_value = ZERO
        total_unrealized_pnl = ZERO
        positions_with_prices = 0
        confidence_breakdown = {
            "high": 0,
            "est": 0,
            "stale": 0,
            "unavailable": 0
        }
        
        for result in results:
            if result.current_value_usd is not None:
                total_current_value += result.current_value_usd
                total_unrealized_pnl += result.unrealized_pnl_usd or ZERO
                positions_with_prices += 1
            
            # Track confidence
            confidence_key = result.price_confidence.value
            confidence_breakdown[confidence_key] += 1
        
        # Calculate overall percentage
        total_pnl_pct = ZERO
        if total_cost_basis > 0:
            total_pnl_pct = (total_unrealized_pnl / total_cost_basis) * Decimal("100")
        
        return {
            "total_cost_basis_usd": float(total_cost_basis),
            "total_current_value_usd": float(total_current_value),
            "total_unrealized_pnl_usd": float(total_unrealized_pnl),
            "total_unrealized_pnl_pct": float(total_pnl_pct),
            "positions_with_prices": positions_with_prices,
            "positions_without_prices": len(positions) - positions_with_prices,
            "confidence_breakdown": confidence_breakdown,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def get_price_age_label(self, timestamp: datetime) -> str:
        """
        Get human-readable label for price age
        
        Args:
            timestamp: Price timestamp
            
        Returns:
            Age label (fresh, recent, stale, very stale)
        """
        now = datetime.now(timezone.utc)
        age_seconds = (now - timestamp).total_seconds()
        
        if age_seconds < PRICE_FRESH_SECONDS:
            return "fresh"
        elif age_seconds < PRICE_RECENT_SECONDS:
            return "recent"
        elif age_seconds < PRICE_STALE_SECONDS:
            return "stale"
        else:
            return "very stale"
    
    async def create_position_pnl_list(
        self,
        positions: List[Position],
        skip_pricing: bool = False
    ) -> List[PositionPnL]:
        """
        Create PositionPnL objects for a list of positions
        
        Args:
            positions: List of Position objects
            skip_pricing: If True, skip price fetching (beta mode)
            
        Returns:
            List of PositionPnL objects
        """
        # Log for RCA validation
        logger.info(f"[RCA] Starting price fetch for {len(positions)} positions (skip_pricing={skip_pricing})")
        
        # Count unique tokens
        unique_tokens = set(p.token_mint for p in positions)
        logger.info(f"[RCA] Unique tokens to price: {len(unique_tokens)}")
        
        start_time = asyncio.get_event_loop().time()
        results = await self.calculate_batch_unrealized_pnl(positions, skip_pricing=skip_pricing)
        elapsed = asyncio.get_event_loop().time() - start_time
        
        logger.info(f"[RCA] Price fetch completed in {elapsed:.2f}s")
        
        position_pnls = []
        for result in results:
            if (result.error is None and 
                result.current_price_usd is not None and
                result.current_value_usd is not None and
                result.unrealized_pnl_usd is not None and
                result.unrealized_pnl_pct is not None):
                position_pnl = PositionPnL(
                    position=result.position,
                    current_price_usd=result.current_price_usd,
                    current_value_usd=result.current_value_usd,
                    unrealized_pnl_usd=result.unrealized_pnl_usd,
                    unrealized_pnl_pct=result.unrealized_pnl_pct,
                    price_confidence=result.price_confidence,
                    last_price_update=result.last_price_update
                )
                position_pnls.append(position_pnl)
        
        return position_pnls 