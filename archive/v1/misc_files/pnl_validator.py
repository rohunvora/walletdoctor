"""
P&L Data Validator - Ensures consistency across different P&L calculations
"""

import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class PnLValidator:
    """Validates and reconciles P&L data from multiple sources"""
    
    def __init__(self, sol_price: float = 175.0):
        self.sol_price = sol_price
    
    def validate_and_reconcile_pnl(self, 
                                  trade_data: Dict,
                                  notification_pnl: Optional[Dict] = None) -> Dict:
        """
        Validate P&L data and ensure consistency
        Returns reconciled P&L data with clear labeling
        """
        try:
            # Extract base data
            action = trade_data.get('action', 'SELL')
            sol_amount = trade_data.get('sol_amount', 0)
            token_symbol = trade_data.get('token_symbol', 'Unknown')
            
            # Get Cielo P&L data if available
            realized_pnl_usd = trade_data.get('realized_pnl_usd', 0)
            total_pnl_usd = trade_data.get('total_pnl_usd', 0)
            unrealized_pnl_usd = trade_data.get('unrealized_pnl_usd', 0)
            roi_percentage = trade_data.get('roi_percentage', 0)
            
            # Convert to SOL
            realized_pnl_sol = realized_pnl_usd / self.sol_price if self.sol_price > 0 else 0
            total_pnl_sol = total_pnl_usd / self.sol_price if self.sol_price > 0 else 0
            unrealized_pnl_sol = unrealized_pnl_usd / self.sol_price if self.sol_price > 0 else 0
            
            # Validate consistency
            issues = []
            
            # Check 1: Total P&L should equal realized + unrealized
            calculated_total = realized_pnl_usd + unrealized_pnl_usd
            if abs(calculated_total - total_pnl_usd) > 1.0:  # Allow $1 tolerance
                issues.append(f"Total P&L mismatch: {total_pnl_usd:.2f} != {calculated_total:.2f}")
            
            # Check 2: For full sells (no remaining position), total should equal realized
            if action == 'SELL' and unrealized_pnl_usd == 0:
                if abs(total_pnl_usd - realized_pnl_usd) > 1.0:
                    issues.append("Full sell but total != realized P&L")
            
            # Check 3: ROI percentage should align with P&L
            if roi_percentage != 0:
                # Basic sanity check
                if (roi_percentage > 0 and total_pnl_usd < 0) or (roi_percentage < 0 and total_pnl_usd > 0):
                    issues.append(f"ROI sign mismatch: {roi_percentage}% vs ${total_pnl_usd:.2f}")
            
            # Log any issues found
            if issues:
                logger.warning(f"P&L validation issues for {token_symbol}: {'; '.join(issues)}")
            
            # Build reconciled data with clear labeling
            reconciled = {
                'token_symbol': token_symbol,
                'action': action,
                
                # Realized P&L (from closed positions)
                'realized_pnl_sol': realized_pnl_sol,
                'realized_pnl_usd': realized_pnl_usd,
                'realized_pnl_formatted': self._format_pnl(realized_pnl_sol, realized_pnl_usd),
                
                # Unrealized P&L (from open positions)
                'unrealized_pnl_sol': unrealized_pnl_sol,
                'unrealized_pnl_usd': unrealized_pnl_usd,
                'unrealized_pnl_formatted': self._format_pnl(unrealized_pnl_sol, unrealized_pnl_usd),
                
                # Total P&L (realized + unrealized)
                'total_pnl_sol': total_pnl_sol,
                'total_pnl_usd': total_pnl_usd,
                'total_pnl_formatted': self._format_pnl(total_pnl_sol, total_pnl_usd),
                
                # Additional context
                'roi_percentage': roi_percentage,
                'has_issues': len(issues) > 0,
                'validation_issues': issues,
                
                # Clear explanation for bot to use
                'explanation': self._generate_pnl_explanation(
                    action, realized_pnl_usd, unrealized_pnl_usd, total_pnl_usd
                )
            }
            
            return reconciled
            
        except Exception as e:
            logger.error(f"Error validating P&L: {e}")
            return {
                'has_issues': True,
                'validation_issues': [str(e)],
                'explanation': "P&L data unavailable"
            }
    
    def _format_pnl(self, sol_amount: float, usd_amount: float) -> str:
        """Format P&L for display with both SOL and USD"""
        sol_sign = "+" if sol_amount >= 0 else ""
        usd_sign = "+" if usd_amount >= 0 else "-"
        
        return f"{sol_sign}{sol_amount:.2f} SOL ({usd_sign}${abs(usd_amount):.2f})"
    
    def _generate_pnl_explanation(self, action: str, 
                                 realized_usd: float, 
                                 unrealized_usd: float,
                                 total_usd: float) -> str:
        """Generate clear explanation of P&L situation"""
        
        if action == 'SELL':
            if unrealized_usd == 0:
                # Full exit
                if realized_usd >= 0:
                    return f"You fully exited with a profit of ${realized_usd:.2f}"
                else:
                    return f"You fully exited with a loss of ${abs(realized_usd):.2f}"
            else:
                # Partial sell
                if realized_usd >= 0:
                    return f"You took ${realized_usd:.2f} in profits and still hold a position worth ${unrealized_usd:.2f}"
                else:
                    return f"You realized a loss of ${abs(realized_usd):.2f} but still hold a position"
        
        else:  # BUY
            if total_usd != 0:
                return f"Your total position P&L is ${total_usd:.2f}"
            else:
                return "New position opened"
    
    def compare_notification_vs_bot_pnl(self, 
                                       notification_pnl_sol: float,
                                       bot_pnl_usd: float,
                                       pnl_type: str = "total") -> Tuple[bool, str]:
        """
        Compare P&L shown in notification vs bot message
        Returns (is_consistent, explanation)
        """
        # Convert notification SOL P&L to USD
        notification_pnl_usd = notification_pnl_sol * self.sol_price
        
        # Check if they're reasonably close (within 10%)
        if abs(bot_pnl_usd) < 1:  # Very small amounts
            tolerance = 1.0  # $1 tolerance
        else:
            tolerance = abs(bot_pnl_usd) * 0.1  # 10% tolerance
        
        difference = abs(notification_pnl_usd - bot_pnl_usd)
        
        if difference <= tolerance:
            return True, "P&L data is consistent"
        else:
            return False, (f"P&L mismatch: Notification shows {notification_pnl_sol:.2f} SOL "
                         f"(${notification_pnl_usd:.2f}) but bot shows ${bot_pnl_usd:.2f}")


# Usage example
def validate_trade_pnl(trade_data: Dict) -> Dict:
    """Helper function to validate P&L for a trade"""
    validator = PnLValidator()
    return validator.validate_and_reconcile_pnl(trade_data) 