"""
Helius Price Extractor
Extract token prices from DEX swap transactions without Birdeye API calls
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, Optional, List, Tuple, Any
from collections import defaultdict
import time

logger = logging.getLogger(__name__)

# Constants
SOL_MINT = "So11111111111111111111111111111111111111112"
WSOL_MINT = "So11111111111111111111111111111111111111112"  # Same as SOL
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"

# Stable coins (always $1)
STABLE_COINS = {
    USDC_MINT: Decimal("1.0"),
    USDT_MINT: Decimal("1.0"),
    "USDC": Decimal("1.0"),
    "USDT": Decimal("1.0"),
}

# Price cache TTL
PRICE_CACHE_TTL_HOURS = 6


class HeliusPriceExtractor:
    """Extract token prices from Helius transaction data"""
    
    def __init__(self):
        # In-memory price cache: mint -> (price_usd, timestamp)
        self.price_cache: Dict[str, Tuple[Decimal, datetime]] = {}
        self.sol_price_cache: Dict[int, Decimal] = {}  # slot -> SOL price
        
    def extract_price_from_transaction(
        self, 
        transaction: Dict[str, Any], 
        token_mint: str,
        sol_price_usd: Optional[Decimal] = None
    ) -> Optional[Tuple[Decimal, str]]:
        """
        Extract price for a token from transaction data
        
        Returns:
            Tuple of (price_usd, source) or None
        """
        # Check if stable coin
        if token_mint in STABLE_COINS:
            return STABLE_COINS[token_mint], "stable"
            
        # Extract slot and timestamp
        slot = transaction.get("slot", 0)
        timestamp = datetime.fromtimestamp(
            transaction.get("timestamp", time.time()), 
            tz=timezone.utc
        )
        
        # Get SOL price if not provided
        if sol_price_usd is None:
            sol_price_usd = self._get_sol_price_at_slot(slot, timestamp)
            if sol_price_usd is None:
                logger.debug(f"[PRICE] No SOL price for slot {slot}")
                return None
                
        # Look for swap events
        swap_data = self._find_best_swap(transaction, token_mint)
        if swap_data:
            price = self._calculate_price_from_swap(swap_data, token_mint, sol_price_usd)
            if price:
                logger.info(f"[PRICE] {token_mint[:8]}: ${price:.6f} from swap (SOL=${sol_price_usd})")
                # Cache the price
                self.price_cache[token_mint] = (price, timestamp)
                return price, "helius_swap"
                
        # Check token transfers for implicit pricing
        price = self._extract_from_transfers(transaction, token_mint, sol_price_usd)
        if price:
            logger.info(f"[PRICE] {token_mint[:8]}: ${price:.6f} from transfers")
            self.price_cache[token_mint] = (price, timestamp)
            return price, "helius_transfer"
            
        return None
        
    def get_cached_price(self, token_mint: str) -> Optional[Tuple[Decimal, str, datetime]]:
        """
        Get price from cache if within TTL
        
        Returns:
            Tuple of (price_usd, source, timestamp) or None
        """
        if token_mint in self.price_cache:
            price, timestamp = self.price_cache[token_mint]
            age_hours = (datetime.now(timezone.utc) - timestamp).total_seconds() / 3600
            
            if age_hours <= PRICE_CACHE_TTL_HOURS:
                logger.debug(f"[PRICE] {token_mint[:8]}: Using cached ${price:.6f} (age: {age_hours:.1f}h)")
                return price, "helius_cached", timestamp
                
        return None
        
    def _find_best_swap(self, transaction: Dict[str, Any], token_mint: str) -> Optional[Dict]:
        """Find the best swap event for the token"""
        events = transaction.get("events", {})
        
        # Check different swap types
        swap_events = []
        
        # Jupiter/Raydium swaps
        if "swap" in events:
            swap = events["swap"]
            if self._involves_token(swap, token_mint):
                swap_events.append(swap)
                
        # Check native instructions for DEX swaps
        instructions = transaction.get("instructions", [])
        for inst in instructions:
            if inst.get("programId") in ["JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB", "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"]:
                # Jupiter or Raydium
                if "innerInstructions" in inst:
                    for inner in inst["innerInstructions"]:
                        if self._is_swap_instruction(inner, token_mint):
                            swap_events.append(inner)
                            
        # Return swap with largest volume
        if swap_events:
            return max(swap_events, key=lambda s: self._get_swap_volume(s))
            
        return None
        
    def _involves_token(self, swap_data: Dict, token_mint: str) -> bool:
        """Check if swap involves the token"""
        token_inputs = swap_data.get("tokenInputs", [])
        token_outputs = swap_data.get("tokenOutputs", [])
        
        for token in token_inputs + token_outputs:
            if token.get("mint") == token_mint:
                return True
                
        return False
        
    def _calculate_price_from_swap(
        self, 
        swap_data: Dict, 
        token_mint: str,
        sol_price_usd: Decimal
    ) -> Optional[Decimal]:
        """Calculate token price from swap data"""
        token_inputs = swap_data.get("tokenInputs", [])
        token_outputs = swap_data.get("tokenOutputs", [])
        
        # Find token and SOL amounts
        token_amount = None
        sol_amount = None
        is_buy = False  # True if buying token with SOL
        
        for token in token_inputs:
            if token.get("mint") == token_mint:
                token_amount = Decimal(str(token.get("tokenAmount", 0)))
                is_buy = False
            elif token.get("mint") in [SOL_MINT, WSOL_MINT]:
                sol_amount = Decimal(str(token.get("tokenAmount", 0)))
                
        for token in token_outputs:
            if token.get("mint") == token_mint:
                token_amount = Decimal(str(token.get("tokenAmount", 0)))
                is_buy = True
            elif token.get("mint") in [SOL_MINT, WSOL_MINT]:
                sol_amount = Decimal(str(token.get("tokenAmount", 0)))
                
        if token_amount and sol_amount and token_amount > 0:
            # Price = SOL_amount / token_amount * SOL_price
            if is_buy:
                # Bought token with SOL: price = SOL_spent / tokens_received
                token_price_in_sol = sol_amount / token_amount
            else:
                # Sold token for SOL: price = SOL_received / tokens_sold
                token_price_in_sol = sol_amount / token_amount
                
            price_usd = token_price_in_sol * sol_price_usd
            
            # Sanity check
            if price_usd > 0 and price_usd < Decimal("1000000"):  # Max $1M per token
                return price_usd
                
        return None
        
    def _extract_from_transfers(
        self, 
        transaction: Dict, 
        token_mint: str,
        sol_price_usd: Decimal
    ) -> Optional[Decimal]:
        """Extract price from token transfers (fallback)"""
        transfers = transaction.get("tokenTransfers", [])
        
        # Look for paired transfers (token <-> SOL)
        token_transfers = [t for t in transfers if t.get("mint") == token_mint]
        sol_transfers = [t for t in transfers if t.get("mint") in [SOL_MINT, WSOL_MINT]]
        
        if token_transfers and sol_transfers:
            # Simple heuristic: assume largest transfers are paired
            token_transfer = max(token_transfers, key=lambda t: Decimal(str(t.get("tokenAmount", 0))))
            sol_transfer = max(sol_transfers, key=lambda t: Decimal(str(t.get("tokenAmount", 0))))
            
            token_amount = Decimal(str(token_transfer.get("tokenAmount", 0)))
            sol_amount = Decimal(str(sol_transfer.get("tokenAmount", 0)))
            
            if token_amount > 0 and sol_amount > 0:
                token_price_in_sol = sol_amount / token_amount
                price_usd = token_price_in_sol * sol_price_usd
                
                if price_usd > 0 and price_usd < Decimal("1000000"):
                    return price_usd
                    
        return None
        
    def _get_swap_volume(self, swap_data: Dict) -> Decimal:
        """Get swap volume for sorting"""
        total = Decimal("0")
        
        for token in swap_data.get("tokenInputs", []) + swap_data.get("tokenOutputs", []):
            amount = Decimal(str(token.get("tokenAmount", 0)))
            # Rough estimate - could be improved with actual prices
            total += amount
            
        return total
        
    def _is_swap_instruction(self, instruction: Dict, token_mint: str) -> bool:
        """Check if instruction is a swap involving the token"""
        # This is a simplified check - could be expanded
        accounts = instruction.get("accounts", [])
        return any(token_mint in acc for acc in accounts)
        
    def _get_sol_price_at_slot(self, slot: int, timestamp: datetime) -> Optional[Decimal]:
        """Get SOL price at a specific slot"""
        # Check cache first
        if slot in self.sol_price_cache:
            return self.sol_price_cache[slot]
            
        # Use a recent SOL price
        # TODO: This should fetch from Pyth or another source
        default_sol_price = Decimal("145.0")  # Recent SOL price
        
        # Cache it
        self.sol_price_cache[slot] = default_sol_price
        
        return default_sol_price
        
    def extract_prices_from_trades(
        self, 
        trades: List[Dict[str, Any]],
        transactions: List[Dict[str, Any]]
    ) -> Dict[str, Optional[Decimal]]:
        """
        Extract prices for all unique tokens in trades
        
        Returns:
            Dict of mint -> price_usd (or None)
        """
        # Build transaction lookup
        tx_by_sig = {tx["signature"]: tx for tx in transactions if "signature" in tx}
        
        # Collect unique mints
        unique_mints = set()
        for trade in trades:
            unique_mints.add(trade.get("token_in_mint", ""))
            unique_mints.add(trade.get("token_out_mint", ""))
        unique_mints.discard("")  # Remove empty
        unique_mints.discard(SOL_MINT)  # SOL price handled separately
        
        # Extract prices
        prices = {}
        coverage_stats = {"found": 0, "cached": 0, "missing": 0}
        
        for mint in unique_mints:
            # Try to find price from any transaction
            price_found = False
            
            # Check all transactions for this mint
            for trade in trades:
                if trade.get("token_in_mint") == mint or trade.get("token_out_mint") == mint:
                    sig = trade.get("signature")
                    if sig and sig in tx_by_sig:
                        tx = tx_by_sig[sig]
                        result = self.extract_price_from_transaction(tx, mint)
                        if result:
                            prices[mint] = result[0]
                            coverage_stats["found"] += 1
                            price_found = True
                            break
                            
            # Check cache if not found
            if not price_found:
                cached = self.get_cached_price(mint)
                if cached:
                    prices[mint] = cached[0]
                    coverage_stats["cached"] += 1
                else:
                    prices[mint] = None
                    coverage_stats["missing"] += 1
                    
        # Log coverage stats
        total = len(unique_mints)
        if total > 0:
            logger.info(
                f"[PRICE] Coverage: {coverage_stats['found']}/{total} from swaps, "
                f"{coverage_stats['cached']}/{total} from cache, "
                f"{coverage_stats['missing']}/{total} missing"
            )
            
        return prices


# Global instance
_extractor = None

def get_helius_price_extractor() -> HeliusPriceExtractor:
    """Get or create the global price extractor instance"""
    global _extractor
    if _extractor is None:
        _extractor = HeliusPriceExtractor()
    return _extractor 