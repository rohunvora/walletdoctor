#!/usr/bin/env python3
"""
Transaction Parser - Parse Solana transactions to identify swaps
"""

import logging
import json
import base64
import requests
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class SwapTransaction:
    """Represents a parsed swap transaction"""
    signature: str
    timestamp: int
    wallet_address: str
    action: str  # "BUY" or "SELL"
    token_in: str  # Token mint address
    token_out: str  # Token mint address
    amount_in: float
    amount_out: float
    dex: str  # DEX name
    program_id: str
    slot: int

# Known DEX program IDs
DEX_PROGRAMS = {
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "Jupiter",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium",
    "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM": "Raydium",
    "27haf8L6oxUeXrHrgEgsexjSY5hbVUWEmvv9Nyxg8vQv": "Raydium",
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P": "Pump.fun",
    "PumpFun11111111111111111111111111111111111": "Pump.fun",
    "BSfD6SHZigAfDWSjzD5Q41jw8LmKwtmjskPH9XW1mrRW": "Pump.fun",  # Pump.fun AMM
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": "Meteora",
    "Dooar9JkhdZ7J3LHN3A7YCuoGRUggXhQaG4kijfLGU2j": "Meteora DAMM",
}

# Solana native token
SOL_MINT = "So11111111111111111111111111111111111111112"

class TransactionParser:
    def __init__(self):
        self.helius_key = os.getenv('HELIUS_KEY')
        self.rpc_url = f"https://mainnet.helius-rpc.com/?api-key={self.helius_key}"
    
    async def parse_transaction(self, signature: str) -> Optional[SwapTransaction]:
        """Parse a transaction signature to extract swap information"""
        try:
            # Get transaction details from Helius
            transaction_data = await self._get_transaction_data(signature)
            
            if not transaction_data:
                return None
            
            # Check if this is a swap transaction
            swap_info = self._extract_swap_info(transaction_data)
            
            if swap_info:
                return SwapTransaction(**swap_info)
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing transaction {signature}: {e}")
            return None
    
    async def _get_transaction_data(self, signature: str) -> Optional[dict]:
        """Fetch transaction data from Helius RPC"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransaction",
                "params": [
                    signature,
                    {
                        "encoding": "json",
                        "commitment": "confirmed",
                        "maxSupportedTransactionVersion": 0
                    }
                ]
            }
            
            # Use aiohttp for async requests
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(self.rpc_url, json=payload) as response:
                    response.raise_for_status()
                    result = await response.json()
                    return result.get("result")
            
        except Exception as e:
            logger.error(f"Error fetching transaction data: {e}")
            return None
    
    def _extract_swap_info(self, transaction_data: dict) -> Optional[dict]:
        """Extract swap information from transaction data"""
        try:
            if not transaction_data:
                logger.debug("No transaction data provided")
                return None
            
            # Get transaction metadata
            meta = transaction_data.get("meta", {})
            transaction = transaction_data.get("transaction", {})
            
            if meta.get("err"):
                # Transaction failed
                logger.debug("Transaction failed")
                return None
            
            # Get account keys and instructions
            message = transaction.get("message", {})
            account_keys = message.get("accountKeys", [])
            instructions = message.get("instructions", [])
            
            logger.debug(f"Found {len(instructions)} instructions in transaction")
            
            # Look for swap instructions
            for idx, instruction in enumerate(instructions):
                program_id_index = instruction.get("programIdIndex")
                if program_id_index is None:
                    continue
                
                program_id = account_keys[program_id_index]
                dex_name = DEX_PROGRAMS.get(program_id)
                
                logger.debug(f"Instruction {idx}: Program ID {program_id} -> {dex_name}")
                
                if dex_name:
                    # This is a DEX instruction, try to parse it
                    swap_info = self._parse_swap_instruction(
                        instruction, 
                        account_keys, 
                        meta, 
                        transaction_data,
                        dex_name,
                        program_id
                    )
                    
                    if swap_info:
                        return swap_info
            
            logger.debug("No DEX instructions found")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting swap info: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _parse_swap_instruction(self, instruction: dict, account_keys: list, 
                               meta: dict, transaction_data: dict, 
                               dex_name: str, program_id: str) -> Optional[dict]:
        """Parse a specific swap instruction"""
        try:
            # Get pre and post token balances
            pre_balances = meta.get("preTokenBalances", [])
            post_balances = meta.get("postTokenBalances", [])
            
            logger.debug(f"Pre-balances: {len(pre_balances)}, Post-balances: {len(post_balances)}")
            
            # Get the main account (fee payer, usually the wallet we're tracking)
            fee_payer = account_keys[0]
            logger.debug(f"Fee payer: {fee_payer}")
            
            # Find token balance changes
            balance_changes = self._calculate_balance_changes(pre_balances, post_balances)
            logger.debug(f"Balance changes: {len(balance_changes)}")
            
            # Also get SOL balance changes from lamport balances
            sol_change = self._calculate_sol_balance_change(meta, fee_payer, account_keys)
            logger.debug(f"SOL balance change: {sol_change}")
            
            # Identify the swap
            swap_details = self._identify_swap_from_changes(balance_changes, fee_payer, sol_change)
            
            if swap_details:
                logger.debug(f"Swap identified: {swap_details}")
                return {
                    "signature": transaction_data.get("transaction", {}).get("signatures", [""])[0],
                    "timestamp": transaction_data.get("blockTime", 0),
                    "wallet_address": fee_payer,
                    "action": swap_details["action"],
                    "token_in": swap_details["token_in"],
                    "token_out": swap_details["token_out"],
                    "amount_in": swap_details["amount_in"],
                    "amount_out": swap_details["amount_out"],
                    "dex": dex_name,
                    "program_id": program_id,
                    "slot": transaction_data.get("slot", 0)
                }
            else:
                logger.debug("No swap details identified")
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing swap instruction: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _calculate_balance_changes(self, pre_balances: list, post_balances: list) -> dict:
        """Calculate token balance changes from pre/post balances"""
        changes = {}
        
        # Create lookup for pre-balances
        pre_lookup = {
            (balance["accountIndex"], balance["mint"]): balance["uiTokenAmount"]["uiAmount"]
            for balance in pre_balances
        }
        
        # Calculate changes based on post-balances
        for post_balance in post_balances:
            account_index = post_balance["accountIndex"]
            mint = post_balance["mint"]
            post_amount = post_balance["uiTokenAmount"]["uiAmount"]
            owner = post_balance.get("owner", "")
            
            pre_amount = pre_lookup.get((account_index, mint), 0)
            # Handle None values
            if post_amount is None:
                post_amount = 0
            if pre_amount is None:
                pre_amount = 0
            change = post_amount - pre_amount
            
            if change != 0:
                changes[(account_index, mint)] = {
                    "mint": mint,
                    "change": change,
                    "account_index": account_index,
                    "owner": owner
                }
        
        return changes
    
    def _calculate_sol_balance_change(self, meta: dict, wallet_address: str, account_keys: list) -> float:
        """Calculate SOL balance change from lamport balances"""
        try:
            pre_balances = meta.get("preBalances", [])
            post_balances = meta.get("postBalances", [])
            
            # Find the wallet's account index
            wallet_index = None
            for i, account in enumerate(account_keys):
                if account == wallet_address:
                    wallet_index = i
                    break
            
            if wallet_index is None:
                logger.debug(f"Wallet {wallet_address} not found in account keys")
                return 0.0
            
            # Get pre and post lamport balances
            pre_lamports = pre_balances[wallet_index] if wallet_index < len(pre_balances) else 0
            post_lamports = post_balances[wallet_index] if wallet_index < len(post_balances) else 0
            
            # Convert lamports to SOL (1 SOL = 1,000,000,000 lamports)
            lamport_change = post_lamports - pre_lamports
            sol_change = lamport_change / 1_000_000_000
            
            logger.debug(f"Lamport change: {lamport_change}, SOL change: {sol_change}")
            return sol_change
            
        except Exception as e:
            logger.error(f"Error calculating SOL balance change: {e}")
            return 0.0
    
    def _identify_swap_from_changes(self, balance_changes: dict, wallet_address: str, sol_change: float) -> Optional[dict]:
        """Identify swap details from balance changes"""
        try:
            logger.debug(f"All balance changes: {balance_changes}")
            logger.debug(f"Looking for wallet: {wallet_address}")
            logger.debug(f"SOL change: {sol_change}")
            
            # Find changes for the wallet's token accounts (only owned by the user)
            wallet_changes = []
            for change in balance_changes.values():
                # Only include changes where the user owns the token account
                if change.get("owner") == wallet_address:
                    wallet_changes.append(change)
            
            logger.debug(f"Wallet changes: {wallet_changes}")
            
            if len(wallet_changes) < 1:
                # Should have at least 1 token change for a swap
                logger.debug(f"Expected at least 1 token change, got {len(wallet_changes)}")
                return None
            
            # Find the non-SOL token change
            user_token_change = None
            for change in wallet_changes:
                if change["mint"] != SOL_MINT:  # Non-SOL token
                    user_token_change = change
                    break
            
            if not user_token_change:
                logger.debug("No non-SOL token change found")
                return None
            
            if user_token_change["change"] < 0:
                # User lost tokens = SELL
                action = "SELL"
                token_in = user_token_change["mint"]  # Token being sold
                token_out = SOL_MINT  # Receiving SOL
                amount_in = abs(user_token_change["change"])
                # Use SOL balance change (should be positive for a sell)
                amount_out = abs(sol_change) if sol_change > 0 else 0
            else:
                # User gained tokens = BUY
                action = "BUY"
                token_in = SOL_MINT  # Spending SOL
                token_out = user_token_change["mint"]  # Token being bought
                # Use SOL balance change (should be negative for a buy)
                amount_in = abs(sol_change) if sol_change < 0 else 0
                amount_out = user_token_change["change"]
            
            return {
                "action": action,
                "token_in": token_in,
                "token_out": token_out,
                "amount_in": amount_in,
                "amount_out": amount_out
            }
            
        except Exception as e:
            logger.error(f"Error identifying swap: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

# Utility function to monitor recent transactions for a wallet
async def monitor_wallet_transactions(wallet_address: str, callback_func):
    """Monitor recent transactions for a wallet and parse swaps"""
    parser = TransactionParser()
    
    try:
        # Get recent transactions (this is a simplified version)
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [
                wallet_address,
                {"limit": 10}
            ]
        }
        
        response = requests.post(parser.rpc_url, json=payload)
        result = response.json().get("result", [])
        
        for tx_info in result:
            signature = tx_info["signature"]
            swap = await parser.parse_transaction(signature)
            
            if swap:
                await callback_func(swap)
                
    except Exception as e:
        logger.error(f"Error monitoring wallet transactions: {e}")

# Test function
async def test_parser():
    """Test the transaction parser"""
    logging.basicConfig(level=logging.INFO)
    
    parser = TransactionParser()
    
    # Test with a known swap transaction signature
    test_signature = "your_test_signature_here"
    swap = await parser.parse_transaction(test_signature)
    
    if swap:
        logger.info(f"Parsed swap: {swap}")
    else:
        logger.info("No swap found in transaction")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_parser()) 