#!/usr/bin/env python3
"""
Advanced swap parser that handles all major Solana DEXes
Extracts token metadata and calculates exact swap amounts
"""

import logging
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Known DEX program IDs
DEX_PROGRAMS = {
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium AMM V4",
    "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1": "Raydium CLMM",
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": "Raydium CPMM", 
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "Orca Whirlpool",
    "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP": "Orca V2",
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "Jupiter v6",
    "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB": "Jupiter v4",
    "JUP3c2Uh3WA4Ng34tw6kPd2G4C5BB21Xo36Je1s32Ph": "Jupiter v3",
}

@dataclass
class SwapDetails:
    """Parsed swap transaction details"""
    signature: str
    timestamp: int
    wallet: str
    dex: str
    swap_type: str  # 'buy' or 'sell'
    token_mint: str
    token_symbol: str
    token_name: str
    token_amount: float
    token_decimals: int
    sol_amount: float
    usd_value: float
    price_per_token: float
    fee_sol: float
    
class AdvancedSwapParser:
    """Parse swap transactions from all major Solana DEXes"""
    
    def __init__(self, sol_price: float = 150.0):
        self.sol_price = sol_price
        self._token_cache = {}
    
    def parse_transaction(self, tx: Dict, wallet: str) -> Optional[SwapDetails]:
        """Parse a transaction and extract swap details if it's a swap"""
        
        # Check if it's a swap transaction
        if tx.get('type') != 'SWAP':
            return None
        
        # Identify the DEX
        dex_name = self._identify_dex(tx)
        if not dex_name:
            return None
        
        # Parse based on transaction structure
        return self._parse_swap_details(tx, wallet, dex_name)
    
    def _identify_dex(self, tx: Dict) -> Optional[str]:
        """Identify which DEX was used"""
        
        instructions = tx.get('instructions', [])
        account_data = tx.get('accountData', [])
        
        # Check instructions for DEX programs
        for instruction in instructions:
            program_id = instruction.get('programId')
            if program_id in DEX_PROGRAMS:
                return DEX_PROGRAMS[program_id]
        
        # Check account data for DEX programs
        for account in account_data:
            if account.get('account') in DEX_PROGRAMS:
                return DEX_PROGRAMS[account['account']]
        
        # Check for Jupiter aggregation
        if any('jupiter' in str(i.get('programId', '')).lower() for i in instructions):
            return "Jupiter Aggregator"
        
        return None
    
    def _parse_swap_details(self, tx: Dict, wallet: str, dex: str) -> Optional[SwapDetails]:
        """Extract swap details from transaction"""
        
        try:
            # Get basic transaction info
            signature = tx.get('signature', '')
            timestamp = tx.get('timestamp', 0)
            fee = tx.get('fee', 0) / 1e9  # Convert lamports to SOL
            
            # Parse token transfers
            token_changes = self._analyze_token_changes(tx, wallet)
            if not token_changes:
                return None
            
            # Determine swap direction and amounts
            swap_info = self._determine_swap_info(token_changes, tx, wallet)
            if not swap_info:
                return None
            
            # Get token metadata
            token_info = self._get_token_metadata(swap_info['token_mint'], tx)
            
            # Calculate USD values and price
            sol_usd = swap_info['sol_amount'] * self.sol_price
            price_per_token = sol_usd / swap_info['token_amount'] if swap_info['token_amount'] > 0 else 0
            
            return SwapDetails(
                signature=signature,
                timestamp=timestamp,
                wallet=wallet,
                dex=dex,
                swap_type=swap_info['type'],
                token_mint=swap_info['token_mint'],
                token_symbol=token_info['symbol'],
                token_name=token_info['name'],
                token_amount=swap_info['token_amount'],
                token_decimals=token_info['decimals'],
                sol_amount=swap_info['sol_amount'],
                usd_value=sol_usd,
                price_per_token=price_per_token,
                fee_sol=fee
            )
            
        except Exception as e:
            logger.debug(f"Error parsing swap details: {e}")
            return None
    
    def _analyze_token_changes(self, tx: Dict, wallet: str) -> Dict[str, Dict]:
        """Analyze token balance changes for the wallet"""
        
        changes = {}
        
        # Native SOL changes
        sol_change = 0
        for transfer in tx.get('nativeTransfers', []):
            if transfer.get('fromUserAccount') == wallet:
                sol_change -= transfer.get('amount', 0) / 1e9
            elif transfer.get('toUserAccount') == wallet:
                sol_change += transfer.get('amount', 0) / 1e9
        
        if sol_change != 0:
            changes['SOL'] = {
                'mint': 'So11111111111111111111111111111111111111112',
                'change': sol_change,
                'decimals': 9,
                'symbol': 'SOL'
            }
        
        # SPL token changes
        for transfer in tx.get('tokenTransfers', []):
            mint = transfer.get('mint')
            if not mint:
                continue
            
            amount = float(transfer.get('tokenAmount', 0))
            
            if transfer.get('fromUserAccount') == wallet:
                # Token sent from wallet
                if mint not in changes:
                    changes[mint] = {
                        'mint': mint,
                        'change': 0,
                        'decimals': transfer.get('decimals', 0),
                        'symbol': 'Unknown'
                    }
                changes[mint]['change'] -= amount
                
            elif transfer.get('toUserAccount') == wallet:
                # Token received by wallet
                if mint not in changes:
                    changes[mint] = {
                        'mint': mint,
                        'change': 0,
                        'decimals': transfer.get('decimals', 0),
                        'symbol': 'Unknown'
                    }
                changes[mint]['change'] += amount
        
        return changes
    
    def _determine_swap_info(self, changes: Dict[str, Dict], tx: Dict, wallet: str) -> Optional[Dict]:
        """Determine swap type and amounts from balance changes"""
        
        # Find what was given and what was received
        given = [(k, v) for k, v in changes.items() if v['change'] < 0]
        received = [(k, v) for k, v in changes.items() if v['change'] > 0]
        
        if not given or not received:
            return None
        
        # Simple swap: 1 token given, 1 token received
        if len(given) == 1 and len(received) == 1:
            given_token, given_data = given[0]
            received_token, received_data = received[0]
            
            # Determine if it's a buy or sell based on SOL involvement
            if given_token == 'SOL' or given_data['mint'] == 'So11111111111111111111111111111111111111112':
                # Gave SOL, received token = BUY
                return {
                    'type': 'buy',
                    'token_mint': received_data['mint'],
                    'token_amount': abs(received_data['change']),
                    'sol_amount': abs(given_data['change'])
                }
            elif received_token == 'SOL' or received_data['mint'] == 'So11111111111111111111111111111111111111112':
                # Gave token, received SOL = SELL
                return {
                    'type': 'sell',
                    'token_mint': given_data['mint'],
                    'token_amount': abs(given_data['change']),
                    'sol_amount': abs(received_data['change'])
                }
        
        # Complex swap through routing - need to trace through
        # This is simplified - in production you'd trace the full route
        sol_change = changes.get('SOL', {}).get('change', 0)
        
        if sol_change > 0:
            # Net received SOL = likely a sell
            # Find the token that was sold
            for token, data in given:
                if token != 'SOL':
                    return {
                        'type': 'sell',
                        'token_mint': data['mint'],
                        'token_amount': abs(data['change']),
                        'sol_amount': abs(sol_change)
                    }
        elif sol_change < 0:
            # Net gave SOL = likely a buy
            # Find the token that was bought
            for token, data in received:
                if token != 'SOL':
                    return {
                        'type': 'buy',
                        'token_mint': data['mint'],
                        'token_amount': abs(data['change']),
                        'sol_amount': abs(sol_change)
                    }
        
        return None
    
    def _get_token_metadata(self, mint: str, tx: Dict) -> Dict:
        """Get token metadata from transaction or cache"""
        
        if mint in self._token_cache:
            return self._token_cache[mint]
        
        # Try to extract from transaction data
        token_info = {
            'symbol': 'Unknown',
            'name': 'Unknown Token',
            'decimals': 9
        }
        
        # Check token transfers for metadata
        for transfer in tx.get('tokenTransfers', []):
            if transfer.get('mint') == mint:
                token_info['symbol'] = transfer.get('tokenStandard', 'Unknown')
                token_info['decimals'] = transfer.get('decimals', 9)
                break
        
        # Check instructions for token metadata
        for instruction in tx.get('instructions', []):
            if instruction.get('type') == 'TOKEN_METADATA':
                parsed = instruction.get('parsed', {})
                if parsed.get('mint') == mint:
                    token_info['symbol'] = parsed.get('symbol', token_info['symbol'])
                    token_info['name'] = parsed.get('name', token_info['name'])
        
        self._token_cache[mint] = token_info
        return token_info

def parse_all_swaps(transactions: List[Dict], wallet: str, sol_price: float = 150.0) -> List[SwapDetails]:
    """Parse all swap transactions for a wallet"""
    
    parser = AdvancedSwapParser(sol_price)
    swaps = []
    
    for tx in transactions:
        swap = parser.parse_transaction(tx, wallet)
        if swap:
            swaps.append(swap)
    
    # Sort by timestamp
    swaps.sort(key=lambda x: x.timestamp)
    
    return swaps