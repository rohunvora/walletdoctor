"""
Test scenarios for the Pocket Trading Coach bot
Includes both real bugs we've hit and critical untested behaviors
"""

from datetime import datetime, timedelta
from typing import List
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_bot_scenarios import TestScenario, TradeEvent, Message, UserProfile


def create_test_scenarios() -> List[TestScenario]:
    """Create all test scenarios - real bugs + untested behaviors"""
    scenarios = []
    
    # Default test user profile
    default_profile = UserProfile(
        typical_position_size_pct=(5.0, 10.0),
        typical_mcap_range=(500_000, 2_000_000),
        typical_hold_time=timedelta(hours=2),
        goal="100 sol"
    )
    
    # Base timestamp for scenarios
    base_time = datetime.now() - timedelta(hours=1)
    
    # ==================================================================
    # CORE FUNCTIONALITY TESTS
    # ==================================================================
    
    # 1. FINNA Wrong P&L - Duplicate trades bug
    finna_trades = [
        TradeEvent(
            action="BUY",
            token="FINNA",
            amount_sol=10.022,
            signature="unique_buy_sig",
            timestamp=base_time,
            market_cap=771_000,
            bankroll_before=43.5,
            bankroll_after=33.478
        ),
        TradeEvent(
            action="SELL",
            token="FINNA",
            amount_sol=6.594,
            signature="duplicate_sell_sig",
            timestamp=base_time + timedelta(seconds=3),
            market_cap=776_000,
            bankroll_before=31.594,
            bankroll_after=33.468,
            duplicates=11  # This is the bug - same trade processed 11 times
        )
    ]
    
    scenarios.append(TestScenario(
        name="P&L Calculation Accuracy",
        description="Bot should correctly deduplicate trades and show accurate loss",
        user_profile=default_profile,
        trades=finna_trades,
        messages=[
            Message(
                text="finna pnl?",
                timestamp=base_time + timedelta(seconds=10),
                must_contain=["3.4"],  # Just check the number
                must_not_contain=["6.6", "profit"],
                expected_tools=["calculate_token_pnl_from_trades"],
                context_note="Should calculate correct P&L despite duplicates"
            )
        ]
    ))
    
    # 2. Context Preservation with Enhanced Primitives
    scenarios.append(TestScenario(
        name="Follow-up Context with likely_referencing_trade",
        description="Bot should use likely_referencing_trade for follow-ups",
        user_profile=default_profile,
        trades=finna_trades[:1],  # Just the buy
        messages=[
            Message(
                text="why risky?",
                timestamp=base_time + timedelta(seconds=10),
                must_contain=["FINNA", "mcap"],  # Should reference the trade
                must_not_contain=["OSCAR"],
                context_note="Should reference FINNA from likely_referencing_trade"
            )
        ]
    ))
    
    # 3. Position State Primitive Test
    partial_sell_trades = [
        TradeEvent(
            action="BUY",
            token="BONK",
            amount_sol=10.0,
            signature="bonk_buy_1",
            timestamp=base_time,
            market_cap=1_500_000,
            bankroll_before=40.0,
            bankroll_after=30.0
        ),
        TradeEvent(
            action="SELL",
            token="BONK",
            amount_sol=3.0,  # Selling 30%
            signature="bonk_sell_1",
            timestamp=base_time + timedelta(minutes=30),
            market_cap=1_800_000,
            bankroll_before=30.0,
            bankroll_after=33.0
        )
    ]
    
    scenarios.append(TestScenario(
        name="Position State Tracking",
        description="Bot should use position_state primitive for accurate info",
        user_profile=default_profile,
        trades=partial_sell_trades,
        messages=[
            Message(
                text="just sold some bonk",
                timestamp=base_time + timedelta(minutes=31),
                must_contain=["30%", "took", "off"],  # From position_state
                must_not_contain=["fully exited", "all out"],
                context_note="Should use position_state showing 30% sold"
            )
        ]
    ))
    
    # 4. User Patterns Comparison
    scenarios.append(TestScenario(
        name="Pattern Comparison vs User History",
        description="Bot should compare trade to user_patterns",
        user_profile=UserProfile(
            typical_position_size_pct=(5.0, 10.0),
            typical_mcap_range=(500_000, 2_000_000),
            goal="100 sol"
        ),
        trades=[
            TradeEvent(
                action="BUY",
                token="POPCAT",
                amount_sol=8.25,  # 25% of bankroll - 2.5x typical!
                signature="popcat_large_buy",
                timestamp=base_time,
                market_cap=1_200_000,
                bankroll_before=33.0,
                bankroll_after=24.75
            )
        ],
        messages=[
            Message(
                text="just bought popcat",
                timestamp=base_time + timedelta(seconds=1),
                must_contain=["25%", "typical"],  # Should compare to typical
                context_note="trade_analysis shows position_size_vs_typical: 2.5"
            )
        ]
    ))
    
    # 5. Rapid Trade Sequence Handling
    rapid_trades = [
        TradeEvent(
            action="BUY",
            token="WIF",
            amount_sol=5.0,
            signature="wif_buy_1",
            timestamp=base_time,
            market_cap=5_000_000,
            bankroll_before=40.0,
            bankroll_after=35.0
        ),
        TradeEvent(
            action="SELL",
            token="WIF",
            amount_sol=5.5,
            signature="wif_sell_1",
            timestamp=base_time + timedelta(minutes=2),  # Quick flip
            market_cap=5_500_000,
            bankroll_before=35.0,
            bankroll_after=40.5
        ),
        TradeEvent(
            action="BUY",
            token="BONK",
            amount_sol=3.0,
            signature="bonk_buy_rapid",
            timestamp=base_time + timedelta(minutes=3),  # Another quick trade
            market_cap=2_000_000,
            bankroll_before=40.5,
            bankroll_after=37.5
        )
    ]
    
    scenarios.append(TestScenario(
        name="Rapid Trade Sequence Recognition",
        description="Bot should notice rapid trading pattern from trade_sequence",
        user_profile=default_profile,
        trades=rapid_trades,
        messages=[
            Message(
                text="",
                timestamp=base_time + timedelta(minutes=3, seconds=1),
                must_contain=["quick", "fast", "rapid"],  # Should notice timing
                context_note="trade_sequence shows 2-3 minute gaps"
            )
        ]
    ))
    
    # ==================================================================
    # NEW SYSTEM IMPROVEMENT TESTS
    # ==================================================================
    
    # 6. Analytics Tool Usage - Time-based Query
    scenarios.append(TestScenario(
        name="Analytics Time Query",
        description="Bot should use query_time_range for time-based questions",
        user_profile=default_profile,
        trades=rapid_trades,  # Has trades today
        messages=[
            Message(
                text="how am i doing today?",
                timestamp=datetime.now(),
                expected_tools=["query_time_range"],
                must_contain=["today", "sol"],
                context_note="Should use analytics tool for accurate data"
            )
        ]
    ))
    
    # 7. Goal Progress Tracking
    goal_profile = UserProfile(
        typical_position_size_pct=(5.0, 10.0),
        typical_mcap_range=(500_000, 2_000_000),
        goal="50 sol"  # Achievable goal
    )
    
    scenarios.append(TestScenario(
        name="Goal Progress with Analytics",
        description="Bot should use get_goal_progress for goal questions",
        user_profile=goal_profile,
        initial_bankroll=40.0,
        trades=[
            TradeEvent(
                action="SELL",
                token="MYRO",
                amount_sol=12.0,  # Big win!
                signature="myro_win",
                timestamp=base_time,
                market_cap=900_000,
                bankroll_before=40.0,
                bankroll_after=52.0
            )
        ],
        messages=[
            Message(
                text="hit my goal?",
                timestamp=base_time + timedelta(seconds=10),
                expected_tools=["get_goal_progress"],
                must_contain=["50 sol", "hit", "reached"],
                context_note="Should recognize goal achievement"
            )
        ]
    ))
    
    # 8. Market Cap Pattern Recognition
    mcap_sensitive_profile = UserProfile(
        typical_position_size_pct=(5.0, 10.0),
        typical_mcap_range=(100_000, 500_000),  # Low cap trader
        goal="100 sol"
    )
    
    scenarios.append(TestScenario(
        name="Market Cap Deviation Detection",
        description="Bot notices trades outside typical mcap range",
        user_profile=mcap_sensitive_profile,
        trades=[
            TradeEvent(
                action="BUY",
                token="BRETT",
                amount_sol=5.0,
                signature="brett_high_mcap",
                timestamp=base_time,
                market_cap=15_000_000,  # 30x typical!
                bankroll_before=33.0,
                bankroll_after=28.0
            )
        ],
        messages=[
            Message(
                text="bought brett",
                timestamp=base_time + timedelta(seconds=5),
                must_contain=["15m", "high", "typical"],
                context_note="trade_analysis shows mcap_vs_typical: 30.0"
            )
        ]
    ))
    
    # 9. Timing Pattern Detection
    night_trader_profile = UserProfile(
        typical_position_size_pct=(5.0, 10.0),
        typical_mcap_range=(500_000, 2_000_000),
        goal="100 sol"
    )
    
    scenarios.append(TestScenario(
        name="Unusual Trading Time Detection",
        description="Bot notices trades at unusual times for user",
        user_profile=night_trader_profile,
        trades=[
            TradeEvent(
                action="BUY",
                token="PEPE",
                amount_sol=2.0,
                signature="pepe_morning",
                timestamp=datetime.now().replace(hour=9),  # 9 AM - unusual!
                market_cap=1_000_000,
                bankroll_before=33.0,
                bankroll_after=31.0
            )
        ],
        messages=[
            Message(
                text="morning trade",
                timestamp=datetime.now().replace(hour=9) + timedelta(seconds=5),
                must_contain=["morning", "early", "unusual"],
                context_note="trade_analysis shows is_unusual_time: true"
            )
        ]
    ))
    
    # 10. Period Comparison
    scenarios.append(TestScenario(
        name="Week-over-Week Comparison",
        description="Bot should use compare_periods for improvement questions",
        user_profile=default_profile,
        trades=rapid_trades,  # Some recent trades
        messages=[
            Message(
                text="am i doing better than last week?",
                timestamp=datetime.now(),
                expected_tools=["compare_periods"],
                must_contain=["week", "better", "worse"],
                context_note="Should use analytics for accurate comparison"
            )
        ]
    ))
    
    # 11. Complex Position Management
    complex_position_trades = [
        TradeEvent(
            action="BUY",
            token="SNEK",
            amount_sol=5.0,
            signature="snek_buy_1",
            timestamp=base_time,
            market_cap=800_000,
            bankroll_before=40.0,
            bankroll_after=35.0
        ),
        TradeEvent(
            action="BUY",
            token="SNEK",
            amount_sol=5.0,
            signature="snek_buy_2", 
            timestamp=base_time + timedelta(minutes=10),
            market_cap=1_200_000,
            bankroll_before=35.0,
            bankroll_after=30.0
        ),
        TradeEvent(
            action="SELL",
            token="SNEK",
            amount_sol=2.5,  # Selling 25% of position
            signature="snek_partial_1",
            timestamp=base_time + timedelta(minutes=20),
            market_cap=1_500_000,
            bankroll_before=30.0,
            bankroll_after=32.5
        ),
        TradeEvent(
            action="SELL",
            token="SNEK",
            amount_sol=2.5,  # Another 25%
            signature="snek_partial_2",
            timestamp=base_time + timedelta(minutes=30),
            market_cap=1_400_000,
            bankroll_before=32.5,
            bankroll_after=35.0
        )
    ]
    
    scenarios.append(TestScenario(
        name="Complex Position Tracking",
        description="Bot tracks position through multiple buys and partial sells",
        user_profile=default_profile,
        trades=complex_position_trades,
        messages=[
            Message(
                text="snek position update?",
                timestamp=base_time + timedelta(minutes=31),
                must_contain=["50%", "sold", "5", "sol", "remaining"],
                context_note="position_state should show complex position accurately"
            )
        ]
    ))
    
    # 12. Notification Hints Usage
    scenarios.append(TestScenario(
        name="Trade Notification Intelligence",
        description="Bot uses notification_hints to highlight important aspects",
        user_profile=default_profile,
        trades=[
            TradeEvent(
                action="BUY",
                token="PONKE",
                amount_sol=7.0,  # 21% of bankroll
                signature="ponke_large",
                timestamp=base_time,
                market_cap=12_000_000,  # High mcap
                bankroll_before=33.0,
                bankroll_after=26.0
            )
        ],
        messages=[
            Message(
                text="",  # Trade notification
                timestamp=base_time + timedelta(seconds=1),
                must_contain=["21%", "12m"],  # Should mention both notable aspects
                context_note="notification_hints includes large position and high mcap"
            )
        ]
    ))
    
    return scenarios


# Make scenarios available for import
all_scenarios = create_test_scenarios()
core_scenarios = all_scenarios[:5]  # First 5 are core functionality
system_improvement_scenarios = all_scenarios[5:]  # Rest test new improvements 