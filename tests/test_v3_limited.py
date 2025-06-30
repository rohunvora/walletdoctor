#!/usr/bin/env python3
"""Test V3 with limited pages to verify parsing rates"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.lib.blockchain_fetcher_v3 import BlockchainFetcherV3

WALLET = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"

class LimitedFetcherV3(BlockchainFetcherV3):
    """V3 fetcher with page limit for testing"""
    
    def __init__(self, max_pages=10, **kwargs):
        super().__init__(**kwargs)
        self.max_pages = max_pages
        
    async def _fetch_swap_transactions(self, wallet: str):
        """Override to limit pages"""
        transactions = []
        before_sig = None
        page = 0
        empty_pages = 0
        
        while page < self.max_pages:  # Add page limit
            page += 1
            await self.helius_limiter.acquire()
            
            params = {
                "api-key": "09cd02b2-f35d-4d54-ac9b-a9033919d6ee",
                "limit": 100,
                "type": "SWAP",
                "maxSupportedTransactionVersion": "0"
            }
            
            if before_sig:
                params["before"] = before_sig
                
            try:
                url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
                if not self.session:
                    raise RuntimeError("Session not initialized")
                    
                async with self.session.get(url, params=params) as resp:
                    if resp.status == 429:
                        retry_after = int(resp.headers.get('Retry-After', '5'))
                        self._report_progress(f"Rate limited, waiting {retry_after}s...")
                        await asyncio.sleep(retry_after)
                        continue
                        
                    resp.raise_for_status()
                    data = await resp.json()
                    
                    if isinstance(data, dict) and 'error' in data:
                        self._report_progress(f"API error: {data.get('error', 'Unknown error')}")
                        break
                        
                    if not data:
                        empty_pages += 1
                        if empty_pages > 3:
                            self._report_progress(f"Hit {empty_pages} empty pages, stopping")
                            break
                        self._report_progress(f"Empty page {empty_pages}/3, continuing...")
                        continue
                    
                    empty_pages = 0
                    transactions.extend(data)
                    self._report_progress(f"Page {page}: {len(data)} transactions")
                    
                    before_sig = data[-1]['signature']
                    
            except Exception as e:
                self._report_progress(f"Error: {e}")
                self.metrics.parser_errors += 1
                break
                
        self._report_progress(f"Stopped at page limit: {self.max_pages}")
        return transactions

async def test_with_pages(max_pages):
    """Test with specified number of pages"""
    print(f"\nTesting V3 with {max_pages} pages...")
    print("=" * 60)
    
    async with LimitedFetcherV3(max_pages=max_pages, progress_callback=print) as fetcher:
        result = await fetcher.fetch_wallet_trades(WALLET)
        
    metrics = result['summary']['metrics']
    total_trades = result['summary']['total_trades']
    
    print(f"\nRESULTS FOR {max_pages} PAGES:")
    print(f"  Transactions: {metrics['signatures_fetched']}")
    print(f"  Trades parsed: {total_trades}")
    print(f"  Parse rate: {metrics['signatures_parsed']/metrics['signatures_fetched']*100:.1f}%")
    print(f"  Events.swap: {metrics['events_swap_rows']}")
    print(f"  Fallback: {metrics['fallback_rows']}")
    
    # Estimate for full dataset (86 pages)
    trades_per_page = total_trades / max_pages
    estimated_total = trades_per_page * 86
    
    print(f"\nESTIMATE FOR FULL DATASET:")
    print(f"  {trades_per_page:.1f} trades/page × 86 pages = {estimated_total:.0f} trades")
    
    return total_trades, estimated_total

async def main():
    """Test with different page counts"""
    
    # Test with 10 pages
    trades_10, estimate_10 = await test_with_pages(10)
    
    # Test with 20 pages for better estimate
    trades_20, estimate_20 = await test_with_pages(20)
    
    print("\n" + "=" * 60)
    print("FINAL ANALYSIS")
    print("=" * 60)
    
    avg_estimate = (estimate_10 + estimate_20) / 2
    print(f"\nAverage estimate: {avg_estimate:.0f} trades")
    print(f"Expert's range: 900-1,100 trades")
    
    if 800 <= avg_estimate <= 1200:
        print(f"\n✅ SUCCESS! Our implementation is on track!")
    else:
        print(f"\n⚠️  Something may be off - investigate further")

if __name__ == "__main__":
    asyncio.run(main()) 