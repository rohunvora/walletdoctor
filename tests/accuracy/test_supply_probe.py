#!/usr/bin/env python3
"""
WAL-511b: Supply Probe
Fetch getTokenSupply at specific slots and verify minimal deviation
"""

import pytest
import asyncio
import os
import logging
from decimal import Decimal
from typing import Optional
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from src.lib.helius_supply import get_token_supply_at_slot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test configuration - both tokens have fixed supply
TEST_DATA = {
    "fakeout": {
        "mint": "GuFK1iRQPCSRxPxWhw94SrDtLYaf7oDT68uuDDpjpump",
        "symbol": "fakeout",
        "expected_supply": 998739928,  # From previous test output
        "max_deviation": 0.001  # 0.1%
    },
    "RDMP": {
        "mint": "1HE8MZKhpbJiNvjJTrXdV395qEmPEqJme6P5DLBboop",
        "symbol": "RDMP",
        "expected_supply": 999967668,  # Actual supply from chain
        "max_deviation": 0.001  # 0.1%
    }
}

# Check if required keys are available
HELIUS_KEY_AVAILABLE = bool(os.getenv("HELIUS_KEY"))


async def get_current_supply(token_mint: str) -> Optional[Decimal]:
    """Get current token supply"""
    try:
        supply = await get_token_supply_at_slot(token_mint, slot=None)
        return supply
    except Exception as e:
        logger.error(f"Failed to get token supply: {e}")
        return None


async def get_supply_at_slot(token_mint: str, slot: int) -> Optional[Decimal]:
    """Get token supply at specific slot"""
    try:
        supply = await get_token_supply_at_slot(token_mint, slot=slot)
        return supply
    except Exception as e:
        logger.error(f"Failed to get token supply at slot {slot}: {e}")
        return None


@pytest.mark.skipif(
    not HELIUS_KEY_AVAILABLE,
    reason="HELIUS_KEY environment variable not set"
)
class TestSupplyProbe:
    """Test token supply accuracy"""
    
    @pytest.mark.asyncio
    async def test_fakeout_supply_consistency(self):
        """Test fakeout token supply consistency"""
        token_data = TEST_DATA["fakeout"]
        
        # Get current supply
        current_supply = await get_current_supply(token_data["mint"])
        assert current_supply is not None, "Could not get current supply"
        
        logger.info(f"{token_data['symbol']} current supply: {current_supply:,.0f}")
        
        # Check deviation from expected
        expected = Decimal(str(token_data["expected_supply"]))
        deviation = abs(current_supply - expected) / expected
        
        logger.info(f"Supply deviation: {deviation*100:.3f}%")
        
        assert deviation <= token_data["max_deviation"], \
            f"Supply deviation {deviation*100:.3f}% exceeds {token_data['max_deviation']*100}% tolerance"
    
    @pytest.mark.asyncio
    async def test_rdmp_supply_consistency(self):
        """Test RDMP token supply consistency"""
        token_data = TEST_DATA["RDMP"]
        
        # Get current supply
        current_supply = await get_current_supply(token_data["mint"])
        assert current_supply is not None, "Could not get current supply"
        
        logger.info(f"{token_data['symbol']} current supply: {current_supply:,.0f}")
        
        # Check deviation from expected
        expected = Decimal(str(token_data["expected_supply"]))
        deviation = abs(current_supply - expected) / expected
        
        logger.info(f"Supply deviation: {deviation*100:.3f}%")
        
        assert deviation <= token_data["max_deviation"], \
            f"Supply deviation {deviation*100:.3f}% exceeds {token_data['max_deviation']*100}% tolerance"
    
    @pytest.mark.asyncio
    async def test_supply_at_historical_slots(self):
        """Test that supply remains consistent at historical slots"""
        # Test slots from different time periods
        test_slots = [
            248000000,  # Older slot
            249000000,  # Mid slot
            250000000,  # Recent slot
        ]
        
        for token_name, token_data in TEST_DATA.items():
            supplies = []
            
            for slot in test_slots:
                supply = await get_supply_at_slot(token_data["mint"], slot)
                if supply:
                    supplies.append(supply)
                    logger.info(f"{token_name} supply at slot {slot}: {supply:,.0f}")
            
            if len(supplies) >= 2:
                # Check that all supplies are the same (fixed supply tokens)
                first_supply = supplies[0]
                for supply in supplies[1:]:
                    deviation = abs(supply - first_supply) / first_supply
                    assert deviation <= 0.0001, \
                        f"{token_name} supply changed between slots: {deviation*100:.4f}% deviation"


if __name__ == "__main__":
    # Run tests
    asyncio.run(pytest.main([__file__, "-v"])) 