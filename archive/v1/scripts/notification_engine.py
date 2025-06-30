#!/usr/bin/env python3
"""
Notification Engine - Format and send swap notifications to Telegram
"""

import logging
from typing import Dict, Optional
from datetime import datetime
import os
try:
    from .transaction_parser import SwapTransaction
    from .price_service import PriceService
    from .token_metadata import TokenMetadataService, TokenMetadata
    from .link_generator import LinkGenerator
except ImportError:
    from transaction_parser import SwapTransaction
    from price_service import PriceService
    from token_metadata import TokenMetadataService, TokenMetadata
    from link_generator import LinkGenerator

logger = logging.getLogger(__name__)

class NotificationEngine:
    def __init__(self, pnl_service=None):
        self.sol_mint = "So11111111111111111111111111111111111111112"
        self.price_service = PriceService()
        self.metadata_service = TokenMetadataService()
        self.link_generator = LinkGenerator()
        self.pnl_service = pnl_service
        
    async def format_enriched_notification(self, swap: SwapTransaction, wallet_name: str = None) -> str:
        """Format an enriched swap notification matching Ray Silver format"""
        try:
            # Determine emoji and action
            if swap.action == "BUY":
                emoji = "🟢"
                action_text = "BUY"
            else:
                emoji = "🔴"
                action_text = "SELL"
            
            # Get token metadata
            token_in_meta = await self.metadata_service.get_token_metadata(swap.token_in)
            token_out_meta = await self.metadata_service.get_token_metadata(swap.token_out)
            
            # Get the non-SOL token for display and links
            if swap.action == "BUY":
                main_token = token_out_meta
                main_token_mint = swap.token_out
                main_token_amount = swap.amount_out
            else:
                main_token = token_in_meta
                main_token_mint = swap.token_in
                main_token_amount = swap.amount_in
            
            # Use wallet name or truncated address
            wallet_display = wallet_name or self._truncate_address(swap.wallet_address)
            
            # Get USD values and SOL price
            usd_values = await self.price_service.calculate_usd_values(
                sol_amount=swap.amount_in if swap.token_in == self.sol_mint else swap.amount_out,
                token_amount=main_token_amount,
                token_mint=main_token_mint,
                timestamp=swap.timestamp,
                is_buy=(swap.action == "BUY")
            )
            
            # Build the message in Ray Silver format
            # Line 1: 🔴 SELL IKON on Meteora DAMM V2
            message = f"{emoji} {action_text} {main_token.symbol} on {swap.dex}\n"
            
            # Line 2: 🔹 POW
            message += f"🔹 {wallet_display}\n\n"
            
            # Line 3: 🔹POW swapped 1,698,053.01 ($1,945.34) IKON for 12.78 SOL @$0.00114
            if swap.action == "SELL":
                # Format token amount with USD
                token_amount_str = self._format_amount(swap.amount_in)
                if usd_values['token_usd']:
                    token_amount_str += f" (${usd_values['token_usd']:,.2f})"
                
                # Format SOL amount
                sol_amount_str = self._format_amount(swap.amount_out) if swap.amount_out > 0 else "? "
                
                # Calculate price per token
                price_str = ""
                if usd_values['price_per_token']:
                    price_str = f" @${usd_values['price_per_token']:.6f}".rstrip('0').rstrip('.')
                
                message += f"🔹{wallet_display} swapped {token_amount_str} {token_in_meta.symbol} for {sol_amount_str} SOL{price_str}"
            else:  # BUY
                # Format SOL amount
                sol_amount_str = self._format_amount(swap.amount_in) if swap.amount_in > 0 else "? "
                
                # Format token amount with USD
                token_amount_str = self._format_amount(swap.amount_out)
                if usd_values['token_usd']:
                    token_amount_str += f" (${usd_values['token_usd']:,.2f})"
                
                # Calculate price per token
                price_str = ""
                if usd_values['price_per_token']:
                    price_str = f" @${usd_values['price_per_token']:.6f}".rstrip('0').rstrip('.')
                
                message += f"🔹{wallet_display} swapped {sol_amount_str} SOL for {token_amount_str} {token_out_meta.symbol}{price_str}"
            
            # Add P&L data if available
            if self.pnl_service:
                pnl_lines = await self._format_pnl_lines(swap, main_token_mint)
                if pnl_lines:
                    message += f"\n{pnl_lines}"
            
            # Add market cap and links line
            message += "\n\n"
            
            # Get market cap
            mc = await self.metadata_service.get_market_cap(main_token_mint)
            mc_str = self.metadata_service.format_market_cap(mc)
            
            # Generate platform links
            links = self.link_generator.generate_platform_links_text(main_token_mint, ['DS', 'PH'])
            
            # Line 4: 🔗 #IKON | MC: $1.15M | DS | PH
            message += f"🔗 #{main_token.symbol} | MC: {mc_str} | {links}\n"
            
            # Line 5: Token address
            message += f"{main_token_mint}"
            
            return message
            
        except Exception as e:
            logger.error(f"Error formatting enriched notification: {e}")
            # Fallback to basic format
            return self.format_basic_swap_notification(swap, wallet_name)
    
    def format_basic_swap_notification(self, swap: SwapTransaction, wallet_name: str = None) -> str:
        """Format a basic swap notification (fallback)"""
        try:
            # Determine emoji and action
            if swap.action == "BUY":
                emoji = "🟢"
                action_text = "BUY"
            else:
                emoji = "🔴"
                action_text = "SELL"
            
            # Get token symbols (basic version)
            token_in_symbol = self._get_token_symbol(swap.token_in)
            token_out_symbol = self._get_token_symbol(swap.token_out)
            
            # Format amounts
            amount_in_formatted = self._format_amount(swap.amount_in)
            amount_out_formatted = self._format_amount(swap.amount_out)
            
            # Use wallet name or truncated address
            wallet_display = wallet_name or self._truncate_address(swap.wallet_address)
            
            # Build notification message - handle missing amounts gracefully
            if swap.action == "SELL" and swap.amount_out == 0:
                # For sells where we can't detect SOL amount
                message = f"{emoji} {action_text} {token_in_symbol} on {swap.dex}\n"
                message += f"🔹 {wallet_display}\n\n"
                message += f"🔹{wallet_display} sold {amount_in_formatted} {token_in_symbol}"
            elif swap.action == "BUY" and swap.amount_in == 0:
                # For buys where we can't detect SOL amount
                message = f"{emoji} {action_text} {token_out_symbol} on {swap.dex}\n"
                message += f"🔹 {wallet_display}\n\n"
                message += f"🔹{wallet_display} bought {amount_out_formatted} {token_out_symbol}"
            else:
                # Normal case with both amounts
                message = f"{emoji} {action_text} {token_out_symbol} on {swap.dex}\n"
                message += f"🔹 {wallet_display}\n\n"
                message += f"🔹{wallet_display} swapped {amount_in_formatted} {token_in_symbol} for {amount_out_formatted} {token_out_symbol}"
            
            return message
            
        except Exception as e:
            logger.error(f"Error formatting notification: {e}")
            return f"⚠️ Transaction detected but formatting failed: {swap.signature}"
    
    def _get_token_symbol(self, mint_address: str) -> str:
        """Get token symbol from mint address (basic version for Phase 1)"""
        if mint_address == self.sol_mint:
            return "SOL"
        
        # For Phase 1, just show truncated mint address
        # This will be enhanced in Phase 2 with actual token metadata
        return self._truncate_address(mint_address)
    
    def _truncate_address(self, address: str) -> str:
        """Truncate an address for display"""
        if len(address) <= 8:
            return address
        return f"{address[:4]}...{address[-4:]}"
    
    def _format_amount(self, amount: float) -> str:
        """Format amount for display"""
        if amount == 0:
            return "0"
        
        if amount >= 1_000_000:
            return f"{amount/1_000_000:.2f}M"
        elif amount >= 1_000:
            return f"{amount/1_000:.2f}K"
        elif amount >= 1:
            return f"{amount:,.2f}"
        else:
            return f"{amount:.6f}"
    
    async def _format_pnl_lines(self, swap: SwapTransaction, token_mint: str) -> Optional[str]:
        """Format P&L data lines like Ray Silver"""
        try:
            # Get P&L data from Cielo
            pnl_data = await self.pnl_service.get_token_pnl_data(swap.wallet_address, token_mint)
            
            if not pnl_data:
                return None
            
            lines = []
            
            # For SELLs, show % sold and realized P&L
            if swap.action == "SELL":
                # Calculate % sold (approximate based on current balance)
                if pnl_data.get('current_balance', 0) > 0:
                    total_held = pnl_data['current_balance'] + swap.amount_in
                    percent_sold = (swap.amount_in / total_held) * 100 if total_held > 0 else 100
                    lines.append(f"➖Sold: {percent_sold:.0f}%")
                
                # Show total P&L (realized + unrealized) for better clarity
                total_pnl_sol = pnl_data.get('total_pnl_sol', 0)
                if total_pnl_sol == 0:
                    # Fallback: calculate from realized + unrealized
                    total_pnl_sol = pnl_data.get('realized_pnl_sol', 0) + pnl_data.get('unrealized_pnl_sol', 0)
                
                if total_pnl_sol != 0:
                    roi = pnl_data.get('roi_percentage', 0)
                    
                    # Format P&L with proper emoji
                    pnl_emoji = "📈" if total_pnl_sol > 0 else "📉"
                    pnl_sign = "+" if total_pnl_sol > 0 else ""
                    
                    lines.append(f"{pnl_emoji}PnL: {pnl_sign}{total_pnl_sol:.2f} SOL ({pnl_sign}{roi:.1f}%)")
            
            # Show holdings and unrealized P&L for both BUY and SELL
            if pnl_data.get('has_open_position') and pnl_data.get('current_balance', 0) > 0:
                balance = pnl_data['current_balance']
                balance_str = self._format_amount(balance)
                
                # Calculate % of supply if possible
                holding_info = f"✊Holds: {balance_str}"
                
                # Add unrealized P&L if exists
                if pnl_data.get('unrealized_pnl_sol', 0) != 0:
                    upnl_sol = pnl_data['unrealized_pnl_sol']
                    upnl_emoji = "📈" if upnl_sol > 0 else "📉"
                    upnl_sign = "+" if upnl_sol > 0 else ""
                    
                    holding_info += f" {upnl_emoji}uPnL: {upnl_sign}{upnl_sol:.2f} SOL"
                
                lines.append(holding_info)
            
            return '\n'.join(lines) if lines else None
            
        except Exception as e:
            logger.error(f"Error formatting P&L lines: {e}")
            return None
    
    async def send_notification(self, message: str, chat_id: int, bot_token: str):
        """Send notification to Telegram"""
        try:
            import aiohttp
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            
            data = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True  # Don't preview links
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as response:
                    if response.status == 200:
                        logger.info(f"Notification sent successfully to chat {chat_id}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to send notification: {response.status} - {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return False

# Utility function for testing
async def test_notification():
    """Test the notification engine"""
    from .transaction_parser import SwapTransaction
    
    # Create a test swap
    test_swap = SwapTransaction(
        signature="test123",
        timestamp=int(datetime.now().timestamp()),
        wallet_address="34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
        action="BUY",
        token_in="So11111111111111111111111111111111111111112",  # SOL
        token_out="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # BONK
        amount_in=5.2,
        amount_out=2847392.0,
        dex="Raydium",
        program_id="675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
        slot=123456
    )
    
    engine = NotificationEngine()
    message = engine.format_basic_swap_notification(test_swap, "POW")
    
    print("Test notification:")
    print(message)

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_notification()) 