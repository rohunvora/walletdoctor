"""
Minimal Helius API mock for unit testing

Provides in-process mock responses for GPT export tests to avoid network calls.
"""

from typing import Dict, Any, List
import asyncio
from datetime import datetime, timezone


class HeliusMock:
    """Mock Helius API for testing"""
    
    # Small wallet test data
    SMALL_WALLET = "34zYDgjy9Uyj9NZnDVKBB45urkbBV4h5LzxWjXJg9VCya"
    
    # Mock transaction data for small wallet
    SMALL_WALLET_TRADES = [
        {
            "signature": "mock_sig_1",
            "timestamp": 1706438400,  # 2024-01-27T15:30:00Z
            "slot": 250000000,
            "type": "swap",
            "source": "pump",
            "feePayer": SMALL_WALLET,
            "tokenTransfers": [
                {
                    "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
                    "fromUserAccount": None,
                    "toUserAccount": SMALL_WALLET,
                    "fromTokenAccount": "pump_vault",
                    "toTokenAccount": "wallet_ata",
                    "tokenAmount": 1000000.123456,
                    "tokenStandard": "Fungible"
                }
            ],
            "nativeTransfers": [
                {
                    "fromUserAccount": SMALL_WALLET,
                    "toUserAccount": "pump_vault",
                    "amount": 25500000  # 0.0255 SOL
                }
            ],
            "accountData": [],
            "transactionError": None,
            "events": {
                "pump": [{
                    "innerInstructionIndex": 1,
                    "instructionIndex": 0,
                    "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
                    "solAmount": 25500000,
                    "tokenAmount": 1000000123456,
                    "isBuy": True,
                    "user": SMALL_WALLET,
                    "timestamp": 1706438400,
                    "slot": 250000000
                }]
            }
        },
        {
            "signature": "mock_sig_2",
            "timestamp": 1706450000,  # 2024-01-27T18:00:00Z
            "slot": 250001000,
            "type": "swap",
            "source": "jupiter",
            "feePayer": SMALL_WALLET,
            "tokenTransfers": [
                {
                    "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                    "fromUserAccount": None,
                    "toUserAccount": SMALL_WALLET,
                    "fromTokenAccount": "jupiter_vault",
                    "toTokenAccount": "wallet_ata",
                    "tokenAmount": 100.0,
                    "tokenStandard": "Fungible"
                }
            ],
            "nativeTransfers": [
                {
                    "fromUserAccount": SMALL_WALLET,
                    "toUserAccount": "jupiter_vault",
                    "amount": 100000000  # 0.1 SOL
                }
            ],
            "accountData": [],
            "transactionError": None,
            "events": {}
        }
    ]
    
    def __init__(self):
        """Initialize mock with test data"""
        self.call_count = 0
        self.delay = 0  # Can add artificial delay for performance testing
    
    async def fetch_wallet_trades(self, wallet_address: str) -> Dict[str, Any]:
        """Mock fetch_wallet_trades method"""
        self.call_count += 1
        
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        
        if wallet_address == self.SMALL_WALLET:
            return {
                "trades": self.SMALL_WALLET_TRADES,
                "total": len(self.SMALL_WALLET_TRADES)
            }
        
        # Unknown wallet returns empty
        return {
            "trades": [],
            "total": 0
        }
    
    def reset(self):
        """Reset mock state"""
        self.call_count = 0
        self.delay = 0


# Global instance for easy patching
helius_mock = HeliusMock()


def patch_helius_api():
    """
    Patch the Helius API with mock for testing
    
    Usage:
        with patch('src.lib.blockchain_fetcher_v3_fast.BlockchainFetcherV3Fast') as mock_class:
            mock_class.return_value.__aenter__.return_value = helius_mock
            # Run tests
    """
    return helius_mock 