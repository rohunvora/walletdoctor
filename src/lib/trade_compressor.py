"""
Trade Compressor - v0.7.2-compact implementation
Compresses enriched trade data to fit within ChatGPT connector limits
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)


class TradeCompressor:
    """Compresses trade data from v0.7.1 to v0.7.2-compact format"""
    
    # Field map defines the order of fields in compressed arrays
    FIELD_MAP = ["ts", "act", "tok", "amt", "p_sol", "p_usd", "val", "pnl"]
    
    # Action mapping
    ACTIONS = ["sell", "buy"]  # 0=sell, 1=buy
    
    # Constants
    SOL_MINT = "So11111111111111111111111111111111111111112"
    
    def compress_trades(self, trades: List[Dict], wallet: str, schema_version: str = "v0.7.2-compact") -> Dict[str, Any]:
        """
        Compress trades from verbose format to compact array format
        
        Args:
            trades: List of enriched trade dictionaries
            wallet: Wallet address
            schema_version: Target schema version
            
        Returns:
            Compressed trade data following v0.7.2-compact schema
        """
        compressed_trades = []
        total_trades = len(trades)
        
        for trade in trades:
            compressed_trade = self._compress_single_trade(trade)
            if compressed_trade:
                compressed_trades.append(compressed_trade)
        
        # Build response
        response = {
            "wallet": wallet,
            "schema_version": schema_version,
            "field_map": self.FIELD_MAP,
            "trades": compressed_trades,
            "constants": {
                "actions": self.ACTIONS,
                "sol_mint": self.SOL_MINT
            },
            "summary": {
                "total": total_trades,
                "included": len(compressed_trades)
            }
        }
        
        # Log compression stats
        original_size = self._estimate_original_size(trades)
        compressed_size = self._estimate_compressed_size(response)
        compression_ratio = original_size / compressed_size if compressed_size > 0 else 0
        
        logger.info(
            f"Trade compression complete: "
            f"trades={total_trades}, "
            f"original_size={original_size:,} bytes, "
            f"compressed_size={compressed_size:,} bytes, "
            f"ratio={compression_ratio:.1f}x"
        )
        
        return response
    
    def _compress_single_trade(self, trade: Dict) -> Optional[List]:
        """Compress a single trade to array format"""
        try:
            # Parse timestamp to Unix timestamp
            timestamp_str = trade.get("timestamp", "")
            if timestamp_str:
                # Handle ISO format with or without Z
                if timestamp_str.endswith("Z"):
                    timestamp_str = timestamp_str[:-1] + "+00:00"
                dt = datetime.fromisoformat(timestamp_str)
                unix_ts = int(dt.timestamp())
            else:
                unix_ts = 0
            
            # Map action to 0/1
            action = trade.get("action", "")
            action_idx = 1 if action == "buy" else 0  # 0=sell, 1=buy
            
            # Get token symbol (prefer short symbol over mint address)
            token = trade.get("token", "")
            if not token and trade.get("token_out", {}).get("symbol"):
                token = trade["token_out"]["symbol"]
            
            # Get numeric fields
            amount = trade.get("amount", 0)
            
            # Get enriched fields (may be null)
            price_sol = trade.get("price_sol")
            price_usd = trade.get("price_usd") 
            value_usd = trade.get("value_usd")
            pnl_usd = trade.get("pnl_usd")
            
            # Format decimals efficiently
            price_sol_str = self._format_decimal(price_sol) if price_sol else ""
            price_usd_str = self._format_decimal(price_usd) if price_usd else ""
            value_usd_str = self._format_decimal(value_usd) if value_usd else ""
            pnl_usd_str = self._format_decimal(pnl_usd) if pnl_usd else ""
            
            # Build compressed array
            # [ts, act, tok, amt, p_sol, p_usd, val, pnl]
            compressed = [
                unix_ts,
                action_idx,
                token,
                amount,
                price_sol_str,
                price_usd_str,
                value_usd_str,
                pnl_usd_str
            ]
            
            return compressed
            
        except Exception as e:
            logger.error(f"Error compressing trade: {e}")
            return None
    
    def _format_decimal(self, value: Any) -> str:
        """Format decimal/float values efficiently"""
        if value is None:
            return ""
        
        # Convert to string and remove unnecessary zeros
        if isinstance(value, str):
            # Already a string, just clean it
            try:
                decimal_value = Decimal(value)
            except:
                return value
        else:
            decimal_value = Decimal(str(value))
        
        # Handle scientific notation
        formatted = f"{decimal_value:.15f}".rstrip('0').rstrip('.')
        
        # For very small numbers, limit precision
        if '.' in formatted and len(formatted.split('.')[1]) > 8:
            # Keep max 8 decimal places for readability
            parts = formatted.split('.')
            formatted = f"{parts[0]}.{parts[1][:8]}"
        
        return formatted
    
    def _estimate_original_size(self, trades: List[Dict]) -> int:
        """Estimate size of original JSON format"""
        # Rough estimate: ~770 bytes per trade
        return len(trades) * 770
    
    def _estimate_compressed_size(self, response: Dict) -> int:
        """Estimate size of compressed format"""
        # More accurate: sum actual field lengths
        size = 100  # Headers and structure
        
        for trade in response["trades"]:
            # Each field plus delimiters
            for field in trade:
                if isinstance(field, str):
                    size += len(field) + 3  # quotes + comma
                else:
                    size += len(str(field)) + 2  # number + comma
            size += 4  # array brackets and newline
        
        return size 