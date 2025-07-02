#!/usr/bin/env python3
"""
Progress Event Protocol for SSE streaming

Defines the schema and logic for progress events sent via Server-Sent Events
"""

from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
import json
import time


class EventType(str, Enum):
    """SSE event types"""
    CONNECTED = "connected"
    PROGRESS = "progress"
    TRADES = "trades"
    METADATA = "metadata"
    COMPLETE = "complete"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class ProgressStep(str, Enum):
    """Progress step identifiers"""
    INITIALIZING = "initializing"
    FETCHING_SIGNATURES = "fetching_signatures"
    FETCHING_TRANSACTIONS = "fetching_transactions"
    PROCESSING_TRADES = "processing_trades"
    FETCHING_METADATA = "fetching_metadata"
    FILTERING = "filtering"
    FETCHING_PRICES = "fetching_prices"
    CALCULATING_PNL = "calculating_pnl"
    COMPLETE = "complete"


@dataclass
class SSEEvent:
    """Base SSE event structure"""
    type: EventType
    data: Dict[str, Any]
    id: Optional[str] = None
    retry: Optional[int] = None
    
    def to_sse_format(self) -> str:
        """Convert to SSE wire format"""
        lines = []
        
        # Add optional id
        if self.id:
            lines.append(f"id: {self.id}")
        
        # Add event type
        lines.append(f"event: {self.type.value}")
        
        # Add data as JSON
        lines.append(f"data: {json.dumps(self.data)}")
        
        # Add retry if specified
        if self.retry:
            lines.append(f"retry: {self.retry}")
        
        # SSE events are separated by double newline
        return "\n".join(lines) + "\n\n"
    
    @classmethod
    def from_dict(cls, event_dict: Dict[str, Any]) -> 'SSEEvent':
        """Create SSEEvent from dictionary"""
        return cls(
            type=EventType(event_dict['type']),
            data=event_dict['data'],
            id=event_dict.get('id'),
            retry=event_dict.get('retry')
        )


@dataclass
class ProgressData:
    """Progress event data structure"""
    message: str
    percentage: float
    step: ProgressStep
    timestamp: float = field(default_factory=time.time)
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {
            "message": self.message,
            "percentage": round(self.percentage, 1),
            "step": self.step.value,
            "timestamp": int(self.timestamp)
        }
        if self.details:
            result.update(self.details)
        return result


@dataclass
class TradesData:
    """Trades event data structure"""
    trades: List[Dict[str, Any]]
    batch_num: int
    total_yielded: int
    has_more: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "trades": self.trades,
            "batch_num": self.batch_num,
            "total_yielded": self.total_yielded,
            "has_more": self.has_more
        }


@dataclass
class ErrorData:
    """Error event data structure"""
    error: str
    code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {
            "error": self.error,
            "timestamp": int(self.timestamp)
        }
        if self.code:
            result["code"] = self.code
        if self.details:
            result["details"] = self.details
        return result


class ProgressCalculator:
    """Calculate progress percentage based on steps and metrics"""
    
    # Weight for each step (must sum to 100)
    STEP_WEIGHTS = {
        ProgressStep.FETCHING_SIGNATURES: 15,
        ProgressStep.FETCHING_TRANSACTIONS: 35,
        ProgressStep.PROCESSING_TRADES: 15,
        ProgressStep.FETCHING_METADATA: 10,
        ProgressStep.FILTERING: 5,
        ProgressStep.FETCHING_PRICES: 15,
        ProgressStep.CALCULATING_PNL: 5,
    }
    
    def __init__(self):
        self.step_progress: Dict[ProgressStep, float] = {}
        self.current_step: Optional[ProgressStep] = None
        
    def update_step_progress(self, step: ProgressStep, progress: float) -> float:
        """
        Update progress for a specific step
        
        Args:
            step: The current step
            progress: Progress within the step (0-100)
            
        Returns:
            Overall progress percentage
        """
        self.current_step = step
        self.step_progress[step] = min(max(progress, 0), 100)
        return self.calculate_overall_progress()
    
    def calculate_overall_progress(self) -> float:
        """Calculate overall progress across all steps"""
        total_progress = 0.0
        
        # Sum up weighted progress for each step
        for step, weight in self.STEP_WEIGHTS.items():
            step_progress = self.step_progress.get(step, 0.0)
            total_progress += (step_progress / 100.0) * weight
        
        return min(total_progress, 100.0)
    
    def estimate_step_progress(self, current: int, total: int) -> float:
        """
        Estimate progress within a step based on current/total
        
        Args:
            current: Current item count
            total: Total expected items (0 if unknown)
            
        Returns:
            Step progress percentage (0-100)
        """
        if total <= 0:
            # Unknown total - use logarithmic scale
            if current <= 0:
                return 0.0
            elif current < 100:
                return current * 0.5  # Slow initial progress
            elif current < 1000:
                return 50 + (current - 100) / 18  # Medium progress
            else:
                return min(95, 50 + 50 * (1 - 1000 / current))  # Asymptotic to 95%
        else:
            # Known total - linear progress
            return min(100.0, (current / total) * 100.0)


class EventBuilder:
    """Helper class to build SSE events"""
    
    @staticmethod
    def connected(wallet: str, request_id: Optional[str] = None) -> SSEEvent:
        """Build connected event"""
        return SSEEvent(
            type=EventType.CONNECTED,
            data={
                "status": "connected",
                "wallet": wallet,
                "timestamp": int(time.time())
            },
            id=request_id
        )
    
    @staticmethod
    def progress(progress_data: ProgressData, request_id: Optional[str] = None) -> SSEEvent:
        """Build progress event"""
        return SSEEvent(
            type=EventType.PROGRESS,
            data=progress_data.to_dict(),
            id=request_id
        )
    
    @staticmethod
    def trades(trades_data: TradesData, request_id: Optional[str] = None) -> SSEEvent:
        """Build trades event"""
        return SSEEvent(
            type=EventType.TRADES,
            data=trades_data.to_dict(),
            id=request_id
        )
    
    @staticmethod
    def metadata(updated_count: int, message: str = "Token metadata updated", 
                 request_id: Optional[str] = None) -> SSEEvent:
        """Build metadata event"""
        return SSEEvent(
            type=EventType.METADATA,
            data={
                "message": message,
                "trades_updated": updated_count,
                "timestamp": int(time.time())
            },
            id=request_id
        )
    
    @staticmethod
    def complete(summary: Dict[str, Any], metrics: Dict[str, Any], 
                 elapsed_seconds: float, request_id: Optional[str] = None) -> SSEEvent:
        """Build complete event"""
        return SSEEvent(
            type=EventType.COMPLETE,
            data={
                "status": "complete",
                "summary": summary,
                "metrics": metrics,
                "elapsed_seconds": round(elapsed_seconds, 2),
                "timestamp": int(time.time())
            },
            id=request_id
        )
    
    @staticmethod
    def error(error_data: ErrorData, request_id: Optional[str] = None) -> SSEEvent:
        """Build error event"""
        return SSEEvent(
            type=EventType.ERROR,
            data=error_data.to_dict(),
            id=request_id
        )
    
    @staticmethod
    def heartbeat(request_id: Optional[str] = None) -> SSEEvent:
        """Build heartbeat event"""
        return SSEEvent(
            type=EventType.HEARTBEAT,
            data={"timestamp": int(time.time())},
            id=request_id
        )


def validate_event_schema(event: Union[SSEEvent, Dict[str, Any]]) -> bool:
    """
    Validate that an event follows the expected schema
    
    Args:
        event: SSEEvent instance or dictionary representation
        
    Returns:
        True if valid, raises ValueError if invalid
    """
    if isinstance(event, dict):
        event = SSEEvent.from_dict(event)
    
    # Check event type
    if not isinstance(event.type, EventType):
        raise ValueError(f"Invalid event type: {event.type}")
    
    # Check data is present
    if not isinstance(event.data, dict):
        raise ValueError("Event data must be a dictionary")
    
    # Type-specific validation
    if event.type == EventType.PROGRESS:
        required = ["message", "percentage", "step"]
        for field in required:
            if field not in event.data:
                raise ValueError(f"Progress event missing required field: {field}")
        
        if not 0 <= event.data["percentage"] <= 100:
            raise ValueError("Progress percentage must be between 0 and 100")
        
        if event.data["step"] not in [s.value for s in ProgressStep]:
            raise ValueError(f"Invalid progress step: {event.data['step']}")
    
    elif event.type == EventType.TRADES:
        required = ["trades", "batch_num", "total_yielded"]
        for field in required:
            if field not in event.data:
                raise ValueError(f"Trades event missing required field: {field}")
        
        if not isinstance(event.data["trades"], list):
            raise ValueError("Trades must be a list")
    
    elif event.type == EventType.ERROR:
        if "error" not in event.data:
            raise ValueError("Error event must contain error message")
    
    elif event.type == EventType.COMPLETE:
        required = ["summary", "metrics"]
        for field in required:
            if field not in event.data:
                raise ValueError(f"Complete event missing required field: {field}")
    
    return True


# Example usage
if __name__ == "__main__":
    # Create progress calculator
    calc = ProgressCalculator()
    
    # Update progress for signature fetching
    overall = calc.update_step_progress(ProgressStep.FETCHING_SIGNATURES, 50)
    print(f"Overall progress: {overall:.1f}%")
    
    # Create and format SSE event
    progress = ProgressData(
        message="Fetched 5000 signatures",
        percentage=overall,
        step=ProgressStep.FETCHING_SIGNATURES,
        details={"signatures_count": 5000}
    )
    
    event = EventBuilder.progress(progress, request_id="req-123")
    print("\nSSE Format:")
    print(event.to_sse_format()) 