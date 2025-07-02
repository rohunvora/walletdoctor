#!/usr/bin/env python3
"""
WAL-317a Performance Test
Test the 5,478-trade wallet to verify <20s performance
"""

import asyncio
import time
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.lib.blockchain_fetcher_v3 import BlockchainFetcherV3


async def test_performance():
    """Test performance with the 5,478-trade wallet"""
    
    # The wallet with 5,478 trades
    test_wallet = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
    
    print(f"🧪 WAL-317a Performance Test")
    print(f"Testing wallet: {test_wallet}")
    print(f"Expected trades: ~5,478")
    print(f"Target time: <20 seconds")
    print("="*60)
    
    # Track progress messages
    progress_messages = []
    def capture_progress(msg):
        progress_messages.append(msg)
        print(msg)
    
    # Start timing
    start_time = time.time()
    
    try:
        async with BlockchainFetcherV3(
            progress_callback=capture_progress,
            skip_pricing=True  # Skip pricing for performance test
        ) as fetcher:
            result = await fetcher.fetch_wallet_trades(test_wallet)
            
        elapsed_time = time.time() - start_time
        
        # Extract results
        total_trades = result['summary']['total_trades']
        metrics = result['summary']['metrics']
        
        print(f"\n{'='*60}")
        print(f"📊 RESULTS")
        print(f"{'='*60}")
        print(f"Total time: {elapsed_time:.1f}s")
        print(f"Total trades: {total_trades}")
        print(f"Signatures fetched: {metrics['signatures_fetched']}")
        print(f"Parse rate: {metrics['signatures_parsed']/metrics['signatures_fetched']*100:.1f}%")
        
        # Check performance
        print(f"\n📈 PERFORMANCE ANALYSIS")
        if elapsed_time < 20:
            print(f"✅ SUCCESS! Completed in {elapsed_time:.1f}s (target: <20s)")
            return True
        else:
            print(f"❌ FAILED! Took {elapsed_time:.1f}s (target: <20s)")
            
            # Analyze bottlenecks
            print(f"\n🔍 Bottleneck Analysis:")
            
            # Find time for each step
            step_times = {}
            for i, msg in enumerate(progress_messages):
                if "✓" in msg and "in" in msg and "s" in msg:
                    try:
                        # Extract step name and time
                        parts = msg.split("in")
                        time_str = parts[-1].strip().replace("s", "")
                        step_time = float(time_str)
                        
                        if "signatures" in msg.lower():
                            step_times["signatures"] = step_time
                        elif "transactions" in msg.lower():
                            step_times["transactions"] = step_time
                        elif "metadata" in msg.lower():
                            step_times["metadata"] = step_time
                    except:
                        pass
            
            for step, duration in step_times.items():
                percentage = (duration / elapsed_time) * 100
                print(f"  {step}: {duration:.1f}s ({percentage:.1f}%)")
            
            return False
            
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"\n❌ ERROR: {e}")
        print(f"Failed after {elapsed_time:.1f}s")
        return False


async def main():
    """Run the performance test"""
    
    # Check for API key
    if not os.getenv("HELIUS_KEY"):
        print("❌ Please set HELIUS_KEY environment variable")
        return 1
    
    # Run test
    success = await test_performance()
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code) 