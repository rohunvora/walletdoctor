"""
GPT Export Schema Validator

Validates the structure and content of GPT export responses against schema v1.1
"""

from typing import Dict, Any, List, Tuple, Optional
from decimal import Decimal
import json
from datetime import datetime


class SchemaValidationError(Exception):
    """Raised when schema validation fails"""
    pass


class GPTExportValidator:
    """Validates GPT export responses against schema v1.1"""
    
    REQUIRED_TOP_LEVEL_FIELDS = {
        "schema_version", "wallet", "timestamp", "positions", 
        "summary", "price_sources"
    }
    
    REQUIRED_POSITION_FIELDS = {
        "position_id", "token_symbol", "token_mint", "balance",
        "decimals", "cost_basis_usd", "current_price_usd",
        "current_value_usd", "unrealized_pnl_usd", "unrealized_pnl_pct",
        "price_confidence", "price_age_seconds", "opened_at", "last_trade_at"
    }
    
    REQUIRED_SUMMARY_FIELDS = {
        "total_positions", "total_value_usd", "total_unrealized_pnl_usd",
        "total_unrealized_pnl_pct", "stale_price_count"
    }
    
    VALID_PRICE_CONFIDENCE = {"high", "medium", "low", "est", "stale"}
    
    def __init__(self, tolerance: float = 0.005):
        """
        Initialize validator
        
        Args:
            tolerance: Allowed tolerance for monetary values (default 0.5%)
        """
        self.tolerance = tolerance
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate(self, response: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """
        Validate a GPT export response
        
        Args:
            response: The API response to validate
            
        Returns:
            (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []
        
        try:
            # Check schema version
            if response.get("schema_version") != "1.1":
                self.errors.append(f"Invalid schema version: {response.get('schema_version')}")
            
            # Check required top-level fields
            self._check_required_fields(response, self.REQUIRED_TOP_LEVEL_FIELDS, "top-level")
            
            # Validate timestamp
            self._validate_timestamp(response.get("timestamp"))
            
            # Validate wallet address
            wallet = response.get("wallet", "")
            if len(wallet) < 32:
                self.errors.append(f"Invalid wallet address length: {len(wallet)}")
            
            # Validate positions
            positions = response.get("positions", [])
            if not isinstance(positions, list):
                self.errors.append("Positions must be a list")
            else:
                for i, position in enumerate(positions):
                    self._validate_position(position, i)
            
            # Validate summary
            summary = response.get("summary", {})
            self._validate_summary(summary, positions)
            
            # Validate price sources
            self._validate_price_sources(response.get("price_sources", {}))
            
            # Check staleness flags if present
            if "stale" in response:
                if response["stale"] and "age_seconds" not in response:
                    self.errors.append("Missing age_seconds when stale=true")
                if "age_seconds" in response and response["age_seconds"] < 0:
                    self.errors.append("age_seconds cannot be negative")
            
        except Exception as e:
            self.errors.append(f"Validation error: {str(e)}")
        
        return len(self.errors) == 0, self.errors, self.warnings
    
    def _check_required_fields(self, obj: Dict[str, Any], required: set, context: str):
        """Check that all required fields are present"""
        missing = required - set(obj.keys())
        if missing:
            self.errors.append(f"Missing required fields in {context}: {missing}")
    
    def _validate_timestamp(self, timestamp: Optional[str]):
        """Validate ISO format timestamp"""
        if not timestamp:
            self.errors.append("Missing timestamp")
            return
        
        try:
            # Should be able to parse as ISO format
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            self.errors.append(f"Invalid timestamp format: {timestamp}")
    
    def _validate_position(self, position: Dict[str, Any], index: int):
        """Validate a single position"""
        context = f"position[{index}]"
        
        # Check required fields
        self._check_required_fields(position, self.REQUIRED_POSITION_FIELDS, context)
        
        # Validate numeric fields
        numeric_fields = [
            "balance", "cost_basis_usd", "current_price_usd",
            "current_value_usd", "unrealized_pnl_usd"
        ]
        
        for field in numeric_fields:
            value = position.get(field)
            if value is not None:
                try:
                    Decimal(value)
                except:
                    self.errors.append(f"Invalid numeric value in {context}.{field}: {value}")
        
        # Validate decimals
        decimals = position.get("decimals")
        if decimals is not None:
            if not isinstance(decimals, int) or decimals < 0 or decimals > 18:
                self.errors.append(f"Invalid decimals in {context}: {decimals}")
        
        # Validate price confidence
        confidence = position.get("price_confidence")
        if confidence and confidence not in self.VALID_PRICE_CONFIDENCE:
            self.errors.append(f"Invalid price_confidence in {context}: {confidence}")
        
        # Validate price age
        age = position.get("price_age_seconds")
        if age is not None and (not isinstance(age, (int, float)) or age < 0):
            self.errors.append(f"Invalid price_age_seconds in {context}: {age}")
        
        # Validate dates
        for date_field in ["opened_at", "last_trade_at"]:
            date_str = position.get(date_field)
            if date_str:
                try:
                    datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except ValueError:
                    self.errors.append(f"Invalid date format in {context}.{date_field}: {date_str}")
        
        # Validate percentage format
        pnl_pct = position.get("unrealized_pnl_pct")
        if pnl_pct is not None:
            try:
                float(pnl_pct)
            except:
                self.errors.append(f"Invalid percentage in {context}.unrealized_pnl_pct: {pnl_pct}")
    
    def _validate_summary(self, summary: Dict[str, Any], positions: List[Dict[str, Any]]):
        """Validate summary section"""
        self._check_required_fields(summary, self.REQUIRED_SUMMARY_FIELDS, "summary")
        
        # Validate position count
        reported_count = summary.get("total_positions")
        actual_count = len(positions)
        if reported_count != actual_count:
            self.errors.append(f"Position count mismatch: summary={reported_count}, actual={actual_count}")
        
        # Validate stale price count
        stale_count = summary.get("stale_price_count", 0)
        actual_stale = sum(1 for p in positions if p.get("price_confidence") == "stale")
        if stale_count != actual_stale:
            self.errors.append(f"Stale price count mismatch: summary={stale_count}, actual={actual_stale}")
        
        # Validate totals (with tolerance)
        if positions:
            # Calculate expected totals
            expected_value = sum(Decimal(p.get("current_value_usd", "0")) for p in positions)
            expected_pnl = sum(Decimal(p.get("unrealized_pnl_usd", "0")) for p in positions)
            
            # Check against reported totals
            reported_value = Decimal(summary.get("total_value_usd", "0"))
            reported_pnl = Decimal(summary.get("total_unrealized_pnl_usd", "0"))
            
            # Allow small tolerance for rounding
            if abs(reported_value - expected_value) > expected_value * Decimal(str(self.tolerance)):
                self.errors.append(
                    f"Total value mismatch: summary={reported_value}, "
                    f"calculated={expected_value}, tolerance={self.tolerance}"
                )
            
            if abs(reported_pnl - expected_pnl) > abs(expected_pnl) * Decimal(str(self.tolerance)):
                self.errors.append(
                    f"Total P&L mismatch: summary={reported_pnl}, "
                    f"calculated={expected_pnl}, tolerance={self.tolerance}"
                )
    
    def _validate_price_sources(self, price_sources: Dict[str, Any]):
        """Validate price sources section"""
        if not price_sources:
            self.errors.append("Missing price_sources section")
            return
        
        required = {"primary", "primary_hint", "fallback", "fallback_hint"}
        missing = required - set(price_sources.keys())
        if missing:
            self.errors.append(f"Missing required price source fields: {missing}")
        
        # Check URLs are present
        primary = price_sources.get("primary", "")
        fallback = price_sources.get("fallback", "")
        
        if not primary.startswith("http"):
            self.warnings.append(f"Primary price source may be invalid: {primary}")
        
        if not fallback.startswith("http"):
            self.warnings.append(f"Fallback price source may be invalid: {fallback}")


def validate_gpt_export(response: Dict[str, Any], tolerance: float = 0.005) -> Tuple[bool, List[str], List[str]]:
    """
    Convenience function to validate a GPT export response
    
    Args:
        response: The API response to validate
        tolerance: Allowed tolerance for monetary values
        
    Returns:
        (is_valid, errors, warnings)
    """
    validator = GPTExportValidator(tolerance)
    return validator.validate(response) 