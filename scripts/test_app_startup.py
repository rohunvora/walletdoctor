#!/usr/bin/env python3
"""
Test app startup to identify import/configuration errors
"""

import sys
import os
import logging

# Set up debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_imports():
    """Test if all imports work"""
    try:
        logger.info("Testing imports...")
        
        # Test basic imports
        import flask
        logger.info("✓ Flask imported")
        
        import redis
        logger.info("✓ Redis imported")
        
        # Test app imports
        from src.lib.blockchain_fetcher_v3_fast import BlockchainFetcherV3Fast
        logger.info("✓ BlockchainFetcherV3Fast imported")
        
        from src.lib.position_builder import PositionBuilder
        logger.info("✓ PositionBuilder imported")
        
        from src.lib.unrealized_pnl_calculator import UnrealizedPnLCalculator
        logger.info("✓ UnrealizedPnLCalculator imported")
        
        from src.config.feature_flags import positions_enabled
        logger.info("✓ Feature flags imported")
        
        # Test the actual app
        from src.api.wallet_analytics_api_v4_gpt import app
        logger.info("✓ App imported successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_app_creation():
    """Test if app can be created"""
    try:
        logger.info("\nTesting app creation...")
        
        # Set minimal env vars
        os.environ["POSITIONS_ENABLED"] = "true"
        os.environ["UNREALIZED_PNL_ENABLED"] = "true"
        
        from src.api.wallet_analytics_api_v4_gpt import app
        
        # Test routes
        with app.test_client() as client:
            # Test health endpoint
            logger.info("Testing /health endpoint...")
            response = client.get("/health")
            logger.info(f"Health response: {response.status_code}")
            if response.status_code == 200:
                logger.info(f"Health data: {response.json}")
            
            # Test diagnostics endpoint
            logger.info("\nTesting /v4/diagnostics endpoint...")
            response = client.get("/v4/diagnostics")
            logger.info(f"Diagnostics response: {response.status_code}")
            if response.status_code == 200:
                data = response.json
                logger.info(f"Helius key present: {data.get('helius_key_present')}")
                logger.info(f"Birdeye key present: {data.get('birdeye_key_present')}")
                logger.info(f"Redis ping: {data.get('redis_ping')}")
        
        return True
        
    except Exception as e:
        logger.error(f"App creation failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Run startup tests"""
    logger.info("=" * 60)
    logger.info("App Startup Test")
    logger.info("=" * 60)
    
    # Test imports
    if not test_imports():
        logger.error("Import test failed!")
        return 1
    
    # Test app creation
    if not test_app_creation():
        logger.error("App creation test failed!")
        return 1
    
    logger.info("\n✅ All tests passed! App should be able to start.")
    return 0


if __name__ == "__main__":
    sys.exit(main()) 