"""
Feature flags for P6: Unrealized P&L and Position Tracking
Allows gradual rollout and easy rollback of new functionality
"""

import os
from typing import Dict, Any


class FeatureFlags:
    """
    Centralized feature flag management for P6 features
    
    Environment variables override default values:
    - POSITIONS_ENABLED=true
    - UNREALIZED_PNL_ENABLED=true
    - STREAMING_POSITIONS=true
    - BALANCE_VERIFICATION=true
    - COST_BASIS_METHOD=fifo
    - PRICE_SOL_SPOT_ONLY=true
    """
    
    def __init__(self):
        # Default feature flag values (all disabled for safety)
        self._flags = {
            "positions_enabled": False,          # Master switch for position tracking
            "unrealized_pnl_enabled": False,     # Enable unrealized P&L calculation
            "streaming_positions": False,        # SSE position updates
            "balance_verification": False,       # On-chain balance verification
            "cost_basis_method": "weighted_avg", # "weighted_avg" or "fifo"
            "price_sol_spot_only": False,        # Use SOL spot price for all current_price_usd values
            "token_price_enabled": False,        # Use CoinGecko for per-token pricing (PRC-002)
            "price_helius_only": False,          # WAL-512: Feature flag for Helius-only pricing (no Birdeye)
            "price_enrich_trades": False,        # TRD-002: Feature flag for enriching trade data with prices and P&L
            "trades_compact": False,             # v0.7.2: Compress trade responses for ChatGPT connector limits
            "analytics_summary": False           # v0.8.0: Enable analytics summary endpoint
        }
        
        # Override with environment variables if present
        self._load_from_env()
    
    def _load_from_env(self):
        """Load feature flags from environment variables"""
        # Boolean flags
        bool_flags = [
            "positions_enabled",
            "unrealized_pnl_enabled", 
            "streaming_positions",
            "balance_verification",
            "price_sol_spot_only",
            "token_price_enabled",
            "price_helius_only",
            "price_enrich_trades",
            "trades_compact",
            "analytics_summary"
        ]
        
        for flag in bool_flags:
            env_key = flag.upper()
            env_value = os.getenv(env_key)
            if env_value is not None:
                self._flags[flag] = env_value.lower() in ("true", "1", "yes", "on")
        
        # String flags
        cost_basis = os.getenv("COST_BASIS_METHOD")
        if cost_basis in ("fifo", "weighted_avg"):
            self._flags["cost_basis_method"] = cost_basis
    
    @property
    def positions_enabled(self) -> bool:
        """Master switch for all position tracking features"""
        return self._flags["positions_enabled"]
    
    @property
    def unrealized_pnl_enabled(self) -> bool:
        """Enable unrealized P&L calculations (requires positions_enabled)"""
        return self._flags["positions_enabled"] and self._flags["unrealized_pnl_enabled"]
    
    @property
    def streaming_positions(self) -> bool:
        """Enable SSE streaming of position updates (requires positions_enabled)"""
        return self._flags["positions_enabled"] and self._flags["streaming_positions"]
    
    @property
    def balance_verification(self) -> bool:
        """Enable on-chain balance verification (requires positions_enabled)"""
        return self._flags["positions_enabled"] and self._flags["balance_verification"]
    
    @property
    def cost_basis_method(self) -> str:
        """Cost basis calculation method: 'weighted_avg' or 'fifo'"""
        return self._flags["cost_basis_method"]
    
    @property
    def price_sol_spot_only(self) -> bool:
        """Use SOL spot price for all current_price_usd values (PRC-001)"""
        return self._flags["price_sol_spot_only"]
    
    @property
    def token_price_enabled(self) -> bool:
        """Use CoinGecko for per-token pricing (PRC-002)"""
        return self._flags["token_price_enabled"]
    
    @property
    def price_helius_only(self) -> bool:
        """WAL-512: Feature flag for Helius-only pricing (no Birdeye)"""
        return self._flags["price_helius_only"]
    
    @property
    def price_enrich_trades(self) -> bool:
        """TRD-002: Feature flag for enriching trade data with prices and P&L"""
        return self._flags["price_enrich_trades"]
    
    @property
    def trades_compact(self) -> bool:
        """v0.7.2: Feature flag for compressing trade responses"""
        return self._flags["trades_compact"]
    
    @property
    def analytics_summary(self) -> bool:
        """v0.8.0: Feature flag for analytics summary endpoint"""
        return self._flags["analytics_summary"]
    
    def get_all(self) -> Dict[str, Any]:
        """Get all feature flag values"""
        return {
            "positions_enabled": self.positions_enabled,
            "unrealized_pnl_enabled": self.unrealized_pnl_enabled,
            "streaming_positions": self.streaming_positions,
            "balance_verification": self.balance_verification,
            "cost_basis_method": self.cost_basis_method,
            "price_sol_spot_only": self.price_sol_spot_only,
            "token_price_enabled": self.token_price_enabled,
            "price_helius_only": self.price_helius_only,
            "price_enrich_trades": self.price_enrich_trades,
            "trades_compact": self.trades_compact,
            "analytics_summary": self.analytics_summary
        }
    
    def is_enabled(self, feature: str) -> bool:
        """Check if a specific feature is enabled"""
        return getattr(self, feature, False)
    
    def __repr__(self) -> str:
        """String representation of current feature flags"""
        flags = self.get_all()
        return f"FeatureFlags({', '.join(f'{k}={v}' for k, v in flags.items())})"


# Global instance
FEATURE_FLAGS = FeatureFlags()


# Convenience functions for common checks
def positions_enabled() -> bool:
    """Check if position tracking is enabled"""
    return FEATURE_FLAGS.positions_enabled


def should_calculate_unrealized_pnl() -> bool:
    """Check if unrealized P&L should be calculated"""
    return FEATURE_FLAGS.unrealized_pnl_enabled


def should_stream_positions() -> bool:
    """Check if position updates should be streamed"""
    return FEATURE_FLAGS.streaming_positions


def should_verify_balances() -> bool:
    """Check if on-chain balance verification is enabled"""
    return FEATURE_FLAGS.balance_verification


def get_cost_basis_method() -> str:
    """Get the configured cost basis calculation method"""
    return FEATURE_FLAGS.cost_basis_method


def should_use_sol_spot_pricing() -> bool:
    """Check if SOL spot pricing should be used for current_price_usd (PRC-001)"""
    return FEATURE_FLAGS.price_sol_spot_only


def should_use_token_pricing() -> bool:
    """Check if CoinGecko token pricing should be used (PRC-002)"""
    return FEATURE_FLAGS.token_price_enabled


def price_helius_only() -> bool:
    """WAL-512: Feature flag for Helius-only pricing (no Birdeye)"""
    return FEATURE_FLAGS.price_helius_only


def price_enrich_trades() -> bool:
    """TRD-002: Feature flag for enriching trade data with prices and P&L"""
    return FEATURE_FLAGS.price_enrich_trades


def trades_compact() -> bool:
    """v0.7.2: Feature flag for compressing trade responses"""
    return FEATURE_FLAGS.trades_compact


def analytics_summary() -> bool:
    """v0.8.0: Feature flag for analytics summary endpoint"""
    return FEATURE_FLAGS.analytics_summary 