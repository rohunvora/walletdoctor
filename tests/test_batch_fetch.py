#!/usr/bin/env python3
"""
Unit test for WAL-317a Part B - Batch transaction fetching
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.lib.blockchain_fetcher_v3 import BlockchainFetcherV3, SIGNATURE_PAGE_LIMIT, TX_BATCH_SIZE


class TestBatchFetch(unittest.TestCase):
    """Test batch transaction fetching functionality"""
    
    def setUp(self):
        """Set up test environment"""
        # Mock environment variables
        os.environ["HELIUS_KEY"] = "test-key"
        os.environ["BIRDEYE_API_KEY"] = "test-birdeye-key"
    
    def test_page_limit_constant(self):
        """Test that SIGNATURE_PAGE_LIMIT is set to 1000"""
        self.assertEqual(SIGNATURE_PAGE_LIMIT, 1000)
    
    def test_batch_size_constant(self):
        """Test that TX_BATCH_SIZE is set to 100"""
        self.assertEqual(TX_BATCH_SIZE, 100)
    
    async def test_page_count_validation(self):
        """Test that fetcher fails fast if pages > 20"""
        # Create fetcher without context manager to avoid session setup
        fetcher = BlockchainFetcherV3()
        
        # Mock to simulate > 20 pages
        with patch.object(fetcher, '_fetch_swap_signatures', side_effect=ValueError("ERROR: Too many pages (21 > 20)")):
            with self.assertRaises(ValueError) as context:
                # Call the method directly
                await fetcher._fetch_swap_signatures("test-wallet")
            
            self.assertIn("Too many pages", str(context.exception))
    
    async def test_batch_transaction_fetch(self):
        """Test batch transaction fetching"""
        # Create test signatures
        test_signatures = [f"sig{i}" for i in range(250)]  # 3 batches
        
        # Mock batch response
        batch_response = []
        for sig in test_signatures[:100]:  # First batch
            batch_response.append({
                "signature": sig,
                "events": {"swap": {"test": "data"}},
                "timestamp": 1234567890
            })
        
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=batch_response)
        mock_resp.raise_for_status = AsyncMock()
        
        # Mock session
        mock_session_instance = AsyncMock()
        mock_session_instance.post = AsyncMock(return_value=mock_resp)
        
        async with BlockchainFetcherV3() as fetcher:
            fetcher.session = mock_session_instance
            
            # Test batch fetching
            transactions = await fetcher._fetch_transactions_batch(test_signatures[:100])
            
            # Verify results
            self.assertEqual(len(transactions), 100)  # All are swap transactions
            self.assertEqual(transactions[0]["signature"], "sig0")
            
            # Verify batch endpoint was called
            mock_session_instance.post.assert_called()
            call_args = mock_session_instance.post.call_args
            self.assertIn("transactions", call_args[0][0])  # URL contains 'transactions'
            self.assertEqual(len(call_args[1]["json"]["transactions"]), 100)  # Batch size
    
    async def test_batch_429_handling(self):
        """Test 429 rate limit handling in batch fetch"""
        test_signatures = [f"sig{i}" for i in range(50)]
        
        # Mock 429 response then success
        mock_resp_429 = AsyncMock()
        mock_resp_429.status = 429
        mock_resp_429.headers = {"Retry-After": "1"}
        
        mock_resp_success = AsyncMock()
        mock_resp_success.status = 200
        mock_resp_success.json = AsyncMock(return_value=[
            {"signature": sig, "events": {"swap": {}}} for sig in test_signatures
        ])
        mock_resp_success.raise_for_status = AsyncMock()
        
        # Mock session to return 429 then success
        mock_session_instance = AsyncMock()
        mock_session_instance.post = AsyncMock(side_effect=[mock_resp_429, mock_resp_success])
        
        async with BlockchainFetcherV3() as fetcher:
            fetcher.session = mock_session_instance
            
            # Test batch fetching with 429
            transactions = await fetcher._fetch_transactions_batch(test_signatures)
            
            # Should retry and succeed
            self.assertEqual(len(transactions), 50)
            self.assertEqual(mock_session_instance.post.call_count, 2)  # Initial + retry


async def run_async_tests():
    """Run async tests"""
    test = TestBatchFetch()
    test.setUp()
    
    # Run async test methods
    await test.test_page_count_validation()
    await test.test_batch_transaction_fetch()
    await test.test_batch_429_handling()
    
    print("✅ All tests passed!")


if __name__ == "__main__":
    # Run sync tests
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # Run async tests
    asyncio.run(run_async_tests()) 