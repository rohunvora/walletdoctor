#!/usr/bin/env python3
"""
Unit tests for /v4/trades/export-gpt endpoint
Tests the GPT integration trades export functionality
"""

import os
import sys
import unittest
from unittest.mock import patch, AsyncMock

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.api.wallet_analytics_api_v4_gpt import app


class TestTradesExport(unittest.TestCase):
    """Test cases for the trades export endpoint"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.app = app.test_client()
        self.app.testing = True
        self.valid_api_key = "wd_12345678901234567890123456789012"
        self.test_wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
        
    def test_trades_export_requires_api_key(self):
        """Test that API key is required"""
        response = self.app.get(f"/v4/trades/export-gpt/{self.test_wallet}")
        self.assertEqual(response.status_code, 401)
        
    def test_trades_export_invalid_wallet(self):
        """Test validation of wallet address"""
        response = self.app.get(
            "/v4/trades/export-gpt/invalid",
            headers={"X-Api-Key": self.valid_api_key}
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("Wallet address must be at least 32 characters", data["message"])
        
    @patch('src.api.wallet_analytics_api_v4_gpt.run_async')
    def test_trades_export_success(self, mock_run_async):
        """Test successful trades export"""
        # Mock the blockchain fetcher response
        mock_result = {
            "signatures": ["sig1", "sig2", "sig3"] * 600,  # 1800 signatures
            "trades": [{"action": "buy", "amount": 100}] * 1100  # 1100 trades
        }
        mock_run_async.return_value = mock_result
        
        response = self.app.get(
            f"/v4/trades/export-gpt/{self.test_wallet}",
            headers={"X-Api-Key": self.valid_api_key}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        # Verify response structure
        self.assertIn("wallet", data)
        self.assertIn("signatures", data)
        self.assertIn("trades", data)
        
        # Verify data content
        self.assertEqual(data["wallet"], self.test_wallet)
        self.assertGreater(len(data["signatures"]), 1000)
        self.assertGreater(len(data["trades"]), 1000)
        
    @patch('src.api.wallet_analytics_api_v4_gpt.run_async')
    def test_trades_export_empty_response(self, mock_run_async):
        """Test empty wallet response"""
        mock_result = {
            "signatures": [],
            "trades": []
        }
        mock_run_async.return_value = mock_result
        
        response = self.app.get(
            f"/v4/trades/export-gpt/{self.test_wallet}",
            headers={"X-Api-Key": self.valid_api_key}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        self.assertEqual(len(data["signatures"]), 0)
        self.assertEqual(len(data["trades"]), 0)
        
    @patch('src.api.wallet_analytics_api_v4_gpt.run_async')
    def test_trades_export_error_handling(self, mock_run_async):
        """Test error handling in trades export"""
        mock_run_async.side_effect = Exception("Blockchain error")
        
        response = self.app.get(
            f"/v4/trades/export-gpt/{self.test_wallet}",
            headers={"X-Api-Key": self.valid_api_key}
        )
        
        self.assertEqual(response.status_code, 500)
        data = response.get_json()
        self.assertIn("error", data)
        self.assertIn("Internal server error", data["error"])


if __name__ == '__main__':
    unittest.main() 