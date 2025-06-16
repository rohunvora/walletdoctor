#!/usr/bin/env python3
"""
Wallet Monitor - Real-time Solana wallet transaction monitoring
"""

import asyncio
import json
import logging
import os
import websockets
from typing import Dict, List, Callable, Optional
from datetime import datetime
import base64

logger = logging.getLogger(__name__)

class SolanaWalletMonitor:
    def __init__(self, rpc_url: str = None):
        self.rpc_url = rpc_url or f"wss://mainnet.helius-rpc.com/?api-key={os.getenv('HELIUS_KEY')}"
        self.websocket = None
        self.subscriptions: Dict[str, int] = {}  # wallet_address -> subscription_id
        self.callbacks: Dict[str, List[Callable]] = {}  # wallet_address -> list of callback functions
        self.is_running = False
        
    async def connect(self):
        """Establish WebSocket connection to Solana RPC"""
        try:
            self.websocket = await websockets.connect(self.rpc_url)
            self.is_running = True
            logger.info(f"Connected to Solana WebSocket: {self.rpc_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            return False
    
    async def disconnect(self):
        """Close WebSocket connection"""
        self.is_running = False
        if self.websocket:
            await self.websocket.close()
            logger.info("WebSocket connection closed")
    
    async def subscribe_wallet(self, wallet_address: str, callback: Callable):
        """Subscribe to account changes for a wallet"""
        if not self.websocket:
            raise Exception("WebSocket not connected")
        
        # Add callback to list
        if wallet_address not in self.callbacks:
            self.callbacks[wallet_address] = []
        self.callbacks[wallet_address].append(callback)
        
        # Skip if already subscribed
        if wallet_address in self.subscriptions:
            logger.info(f"Already subscribed to wallet: {wallet_address}")
            return
        
        # Subscribe to account changes
        subscribe_request = {
            "jsonrpc": "2.0",
            "id": len(self.subscriptions) + 1,
            "method": "accountSubscribe",
            "params": [
                wallet_address,
                {
                    "encoding": "base64",
                    "commitment": "confirmed"
                }
            ]
        }
        
        await self.websocket.send(json.dumps(subscribe_request))
        logger.info(f"Subscribed to wallet: {wallet_address}")
    
    async def unsubscribe_wallet(self, wallet_address: str):
        """Unsubscribe from wallet monitoring"""
        if wallet_address in self.subscriptions:
            subscription_id = self.subscriptions[wallet_address]
            
            unsubscribe_request = {
                "jsonrpc": "2.0",
                "id": 999,
                "method": "accountUnsubscribe",
                "params": [subscription_id]
            }
            
            await self.websocket.send(json.dumps(unsubscribe_request))
            del self.subscriptions[wallet_address]
            del self.callbacks[wallet_address]
            
            logger.info(f"Unsubscribed from wallet: {wallet_address}")
    
    async def listen(self):
        """Listen for WebSocket messages and process them"""
        if not self.websocket:
            raise Exception("WebSocket not connected")
        
        logger.info("Starting to listen for wallet updates...")
        
        try:
            async for message in self.websocket:
                await self._process_message(json.loads(message))
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
            self.is_running = False
        except Exception as e:
            logger.error(f"Error in listen loop: {e}")
            self.is_running = False
    
    async def _process_message(self, message: dict):
        """Process incoming WebSocket messages"""
        try:
            # Handle subscription confirmations
            if "result" in message and isinstance(message.get("result"), int):
                # This is a subscription confirmation
                subscription_id = message["result"]
                logger.info(f"Subscription confirmed with ID: {subscription_id}")
                return
            
            # Handle account notifications
            if "method" in message and message["method"] == "accountNotification":
                await self._handle_account_notification(message)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def _handle_account_notification(self, message: dict):
        """Handle account change notifications"""
        try:
            params = message.get("params", {})
            if not params:
                return
            
            # Extract account info
            result = params.get("result", {})
            context = result.get("context", {})
            value = result.get("value", {})
            
            # Get the account that changed
            account_key = value.get("account", {}).get("owner")  # This might need adjustment
            
            # For now, just log the notification
            logger.info(f"Account notification received: {json.dumps(message, indent=2)}")
            
            # TODO: Parse transaction data and call appropriate callbacks
            # This will be implemented in the transaction parser
            
        except Exception as e:
            logger.error(f"Error handling account notification: {e}")
    
    async def start_monitoring(self, wallets_and_callbacks: List[tuple]):
        """Start monitoring multiple wallets
        
        Args:
            wallets_and_callbacks: List of (wallet_address, callback_function) tuples
        """
        if not await self.connect():
            return False
        
        # Subscribe to all wallets
        for wallet_address, callback in wallets_and_callbacks:
            await self.subscribe_wallet(wallet_address, callback)
        
        # Start listening
        await self.listen()
        
        return True

# Test callback function
async def test_callback(wallet_address: str, transaction_data: dict):
    """Test callback for development"""
    logger.info(f"Transaction detected for {wallet_address}: {transaction_data}")

# Main function for testing
async def main():
    """Test the wallet monitor"""
    logging.basicConfig(level=logging.INFO)
    
    monitor = SolanaWalletMonitor()
    
    # Test with a known active wallet
    test_wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    
    try:
        await monitor.start_monitoring([(test_wallet, test_callback)])
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    finally:
        await monitor.disconnect()

if __name__ == "__main__":
    asyncio.run(main()) 