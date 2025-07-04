"""
Trade Enricher - TRD-002 implementation
Enriches trades with price_sol, price_usd, value_usd, and pnl_usd fields
"""

import logging
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from collections import defaultdict
from datetime import datetime
import asyncio

from src.lib.blockchain_fetcher_v3 import Trade
from src.lib.sol_price_fetcher import get_sol_price_usd

logger = logging.getLogger(__name__)

SOL_MINT = "So11111111111111111111111111111111111111112"


class TradeEnricher:
    """Enriches trades with price and P&L data"""
    
    def __init__(self):
        # FIFO cost basis tracking: token_mint -> [(amount, cost_per_token)]
        self.cost_basis: Dict[str, List[Tuple[Decimal, Decimal]]] = defaultdict(list)
        self.enrichment_stats = {
            "trades_processed": 0,
            "trades_priced": 0,
            "trades_with_pnl": 0,
            "null_sol_prices": 0,
            "errors": 0
        }
    
    async def enrich_trades(self, trades: List[Dict]) -> List[Dict]:
        """
        Enrich trades with price_sol, price_usd, value_usd, and pnl_usd
        
        Args:
            trades: List of trade dictionaries from the API
            
        Returns:
            List of enriched trade dictionaries
        """
        # Sort trades by timestamp for FIFO calculation
        sorted_trades = sorted(trades, key=lambda t: t.get("timestamp", ""))
        
        enriched_trades = []
        for trade in sorted_trades:
            try:
                enriched = await self._enrich_single_trade(trade)
                enriched_trades.append(enriched)
                self.enrichment_stats["trades_processed"] += 1
            except Exception as e:
                logger.error(f"Error enriching trade {trade.get('signature', 'unknown')}: {e}")
                self.enrichment_stats["errors"] += 1
                # Return trade with null values on error
                enriched = trade.copy()
                enriched["price_sol"] = None
                enriched["price_usd"] = None
                enriched["value_usd"] = None
                enriched["pnl_usd"] = None
                enriched_trades.append(enriched)
        
        logger.info(f"Trade enrichment stats: {self.enrichment_stats}")
        return enriched_trades
    
    async def _enrich_single_trade(self, trade: Dict) -> Dict:
        """Enrich a single trade with pricing data"""
        enriched = trade.copy()
        
        # Parse trade data
        action = trade.get("action", "")
        token_in = trade.get("token_in", {})
        token_out = trade.get("token_out", {})
        timestamp_str = trade.get("timestamp", "")
        
        if not all([action, token_in, token_out, timestamp_str]):
            raise ValueError("Missing required trade fields")
        
        # Parse timestamp
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except:
            timestamp = datetime.utcnow()
        
        # Get SOL price at trade time
        # Note: This uses cached spot price, not historical price
        sol_price_usd = get_sol_price_usd()
        if not sol_price_usd:
            self.enrichment_stats["null_sol_prices"] += 1
            logger.warning(f"No SOL price available for {timestamp_str}")
            enriched["price_sol"] = None
            enriched["price_usd"] = None
            enriched["value_usd"] = None
            enriched["pnl_usd"] = None
            return enriched
        
        # Calculate prices based on trade direction
        if action == "buy":
            # Buying token with SOL (or other token)
            if token_in["mint"] == SOL_MINT:
                # Buying with SOL
                sol_amount = Decimal(str(token_in["amount"]))
                token_amount = Decimal(str(token_out["amount"]))
                
                if token_amount > 0:
                    price_sol = sol_amount / token_amount
                    price_usd = price_sol * sol_price_usd
                    value_usd = sol_amount * sol_price_usd
                    
                    enriched["price_sol"] = str(price_sol)
                    enriched["price_usd"] = str(price_usd)
                    enriched["value_usd"] = str(value_usd)
                    
                    # Track cost basis for this token
                    self._add_cost_basis(token_out["mint"], token_amount, price_usd)
                    
                    # No P&L on buys
                    enriched["pnl_usd"] = "0"
                    self.enrichment_stats["trades_priced"] += 1
                else:
                    raise ValueError("Token amount is zero")
            else:
                # Token-to-token swap, skip for now
                enriched["price_sol"] = None
                enriched["price_usd"] = None
                enriched["value_usd"] = None
                enriched["pnl_usd"] = None
                
        elif action == "sell":
            # Selling token for SOL (or other token)
            if token_out["mint"] == SOL_MINT:
                # Selling for SOL
                token_amount = Decimal(str(token_in["amount"]))
                sol_amount = Decimal(str(token_out["amount"]))
                
                if token_amount > 0:
                    price_sol = sol_amount / token_amount
                    price_usd = price_sol * sol_price_usd
                    value_usd = sol_amount * sol_price_usd
                    
                    enriched["price_sol"] = str(price_sol)
                    enriched["price_usd"] = str(price_usd)
                    enriched["value_usd"] = str(value_usd)
                    
                    # Calculate P&L using FIFO
                    pnl_usd = self._calculate_fifo_pnl(
                        token_in["mint"], 
                        token_amount, 
                        price_usd
                    )
                    enriched["pnl_usd"] = str(pnl_usd)
                    
                    if pnl_usd != Decimal("0"):
                        self.enrichment_stats["trades_with_pnl"] += 1
                    
                    self.enrichment_stats["trades_priced"] += 1
                else:
                    raise ValueError("Token amount is zero")
            else:
                # Token-to-token swap, skip for now
                enriched["price_sol"] = None
                enriched["price_usd"] = None
                enriched["value_usd"] = None
                enriched["pnl_usd"] = None
        
        return enriched
    
    def _add_cost_basis(self, token_mint: str, amount: Decimal, price_per_token: Decimal):
        """Add to cost basis tracking for FIFO"""
        self.cost_basis[token_mint].append((amount, price_per_token))
    
    def _calculate_fifo_pnl(self, token_mint: str, sell_amount: Decimal, sell_price_per_token: Decimal) -> Decimal:
        """Calculate P&L using FIFO cost basis"""
        if token_mint not in self.cost_basis or not self.cost_basis[token_mint]:
            # No cost basis, P&L is 0
            return Decimal("0")
        
        total_proceeds = sell_amount * sell_price_per_token
        total_cost = Decimal("0")
        remaining_to_sell = sell_amount
        
        # Process FIFO queue
        while remaining_to_sell > 0 and self.cost_basis[token_mint]:
            buy_amount, buy_price = self.cost_basis[token_mint][0]
            
            if buy_amount <= remaining_to_sell:
                # Use entire buy lot
                total_cost += buy_amount * buy_price
                remaining_to_sell -= buy_amount
                self.cost_basis[token_mint].pop(0)
            else:
                # Use partial buy lot
                total_cost += remaining_to_sell * buy_price
                # Update remaining amount in the lot
                self.cost_basis[token_mint][0] = (
                    buy_amount - remaining_to_sell,
                    buy_price
                )
                remaining_to_sell = 0
        
        # If we couldn't match all sells to buys, add remaining at sell price (conservative)
        if remaining_to_sell > 0:
            total_cost += remaining_to_sell * sell_price_per_token
        
        return total_proceeds - total_cost 