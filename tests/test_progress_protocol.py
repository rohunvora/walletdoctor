#!/usr/bin/env python3
"""
Tests for progress event protocol
"""

import pytest
import json
import time
from unittest.mock import patch

from src.lib.progress_protocol import (
    EventType, ProgressStep, SSEEvent, ProgressData, TradesData, ErrorData,
    ProgressCalculator, EventBuilder, validate_event_schema
)


class TestEventType:
    """Test event type enum"""
    
    def test_all_event_types(self):
        """Test all event types are defined"""
        assert EventType.CONNECTED == "connected"
        assert EventType.PROGRESS == "progress"
        assert EventType.TRADES == "trades"
        assert EventType.METADATA == "metadata"
        assert EventType.COMPLETE == "complete"
        assert EventType.ERROR == "error"
        assert EventType.HEARTBEAT == "heartbeat"


class TestProgressStep:
    """Test progress step enum"""
    
    def test_all_progress_steps(self):
        """Test all progress steps are defined"""
        steps = [
            ProgressStep.INITIALIZING,
            ProgressStep.FETCHING_SIGNATURES,
            ProgressStep.FETCHING_TRANSACTIONS,
            ProgressStep.PROCESSING_TRADES,
            ProgressStep.FETCHING_METADATA,
            ProgressStep.FILTERING,
            ProgressStep.FETCHING_PRICES,
            ProgressStep.CALCULATING_PNL,
            ProgressStep.COMPLETE
        ]
        
        # Verify all steps have string values
        for step in steps:
            assert isinstance(step.value, str)
            assert step.value == step.value.lower()


class TestSSEEvent:
    """Test SSE event structure"""
    
    def test_create_event(self):
        """Test creating SSE event"""
        event = SSEEvent(
            type=EventType.PROGRESS,
            data={"message": "Test", "percentage": 50},
            id="test-123"
        )
        
        assert event.type == EventType.PROGRESS
        assert event.data["message"] == "Test"
        assert event.id == "test-123"
        assert event.retry is None
    
    def test_to_sse_format(self):
        """Test SSE wire format conversion"""
        event = SSEEvent(
            type=EventType.PROGRESS,
            data={"message": "Test", "percentage": 50},
            id="test-123",
            retry=5000
        )
        
        sse_format = event.to_sse_format()
        lines = sse_format.strip().split('\n')
        
        assert "id: test-123" in lines
        assert "event: progress" in lines
        assert 'data: {"message": "Test", "percentage": 50}' in lines
        assert "retry: 5000" in lines
        assert sse_format.endswith('\n\n')
    
    def test_to_sse_format_minimal(self):
        """Test SSE format with minimal fields"""
        event = SSEEvent(
            type=EventType.HEARTBEAT,
            data={"timestamp": 123456}
        )
        
        sse_format = event.to_sse_format()
        lines = sse_format.strip().split('\n')
        
        assert "event: heartbeat" in lines
        assert 'data: {"timestamp": 123456}' in lines
        assert "id:" not in sse_format
        assert "retry:" not in sse_format
    
    def test_from_dict(self):
        """Test creating event from dictionary"""
        event_dict = {
            'type': 'progress',
            'data': {'message': 'Test'},
            'id': 'test-456'
        }
        
        event = SSEEvent.from_dict(event_dict)
        assert event.type == EventType.PROGRESS
        assert event.data['message'] == 'Test'
        assert event.id == 'test-456'


class TestProgressData:
    """Test progress data structure"""
    
    def test_create_progress_data(self):
        """Test creating progress data"""
        data = ProgressData(
            message="Processing",
            percentage=75.5,
            step=ProgressStep.PROCESSING_TRADES,
            details={"count": 100}
        )
        
        assert data.message == "Processing"
        assert data.percentage == 75.5
        assert data.step == ProgressStep.PROCESSING_TRADES
        assert isinstance(data.timestamp, float)
        assert data.timestamp > 0
        assert data.details == {"count": 100}
    
    def test_to_dict(self):
        """Test converting progress data to dict"""
        data = ProgressData(
            message="Processing",
            percentage=75.5,
            step=ProgressStep.PROCESSING_TRADES,
            timestamp=1234567890,
            details={"count": 100}
        )
        
        result = data.to_dict()
        assert result["message"] == "Processing"
        assert result["percentage"] == 75.5  # Rounded to 1 decimal
        assert result["step"] == "processing_trades"
        assert result["timestamp"] == 1234567890
        assert result["count"] == 100  # Details merged in


class TestTradesData:
    """Test trades data structure"""
    
    def test_create_trades_data(self):
        """Test creating trades data"""
        trades = [
            {"signature": "sig1", "amount": 100},
            {"signature": "sig2", "amount": 200}
        ]
        
        data = TradesData(
            trades=trades,
            batch_num=1,
            total_yielded=2,
            has_more=True
        )
        
        assert data.trades == trades
        assert data.batch_num == 1
        assert data.total_yielded == 2
        assert data.has_more is True
    
    def test_to_dict(self):
        """Test converting trades data to dict"""
        trades = [{"signature": "sig1"}]
        data = TradesData(
            trades=trades,
            batch_num=3,
            total_yielded=100,
            has_more=False
        )
        
        result = data.to_dict()
        assert result["trades"] == trades
        assert result["batch_num"] == 3
        assert result["total_yielded"] == 100
        assert result["has_more"] is False


class TestErrorData:
    """Test error data structure"""
    
    def test_create_error_data(self):
        """Test creating error data"""
        data = ErrorData(
            error="Something went wrong",
            code="ERR_001",
            details={"traceback": "..."}
        )
        
        assert data.error == "Something went wrong"
        assert data.code == "ERR_001"
        assert data.details == {"traceback": "..."}
        assert isinstance(data.timestamp, float)
        assert data.timestamp > 0
    
    def test_to_dict(self):
        """Test converting error data to dict"""
        data = ErrorData(
            error="Test error",
            code="TEST_ERR",
            details={"info": "debug"},
            timestamp=1234567890
        )
        
        result = data.to_dict()
        assert result["error"] == "Test error"
        assert result["code"] == "TEST_ERR"
        assert result["details"] == {"info": "debug"}
        assert result["timestamp"] == 1234567890
    
    def test_to_dict_minimal(self):
        """Test converting minimal error data to dict"""
        data = ErrorData(
            error="Simple error",
            timestamp=1234567890
        )
        
        result = data.to_dict()
        assert result["error"] == "Simple error"
        assert result["timestamp"] == 1234567890
        assert "code" not in result
        assert "details" not in result


class TestProgressCalculator:
    """Test progress calculator"""
    
    def test_step_weights(self):
        """Test step weights sum to 100"""
        calc = ProgressCalculator()
        total_weight = sum(calc.STEP_WEIGHTS.values())
        assert total_weight == 100
    
    def test_update_step_progress(self):
        """Test updating progress for a step"""
        calc = ProgressCalculator()
        
        # Update signatures to 50%
        overall = calc.update_step_progress(ProgressStep.FETCHING_SIGNATURES, 50)
        
        # Should be 50% of 15% weight = 7.5%
        assert overall == 7.5
        assert calc.current_step == ProgressStep.FETCHING_SIGNATURES
        assert calc.step_progress[ProgressStep.FETCHING_SIGNATURES] == 50
    
    def test_update_multiple_steps(self):
        """Test updating multiple steps"""
        calc = ProgressCalculator()
        
        # Complete signatures (15% weight)
        calc.update_step_progress(ProgressStep.FETCHING_SIGNATURES, 100)
        
        # Half transactions (35% weight)
        overall = calc.update_step_progress(ProgressStep.FETCHING_TRANSACTIONS, 50)
        
        # Should be 15% + (50% of 35%) = 32.5%
        assert overall == 32.5
    
    def test_progress_clamping(self):
        """Test progress values are clamped to 0-100"""
        calc = ProgressCalculator()
        
        # Test negative
        calc.update_step_progress(ProgressStep.FETCHING_SIGNATURES, -50)
        assert calc.step_progress[ProgressStep.FETCHING_SIGNATURES] == 0
        
        # Test over 100
        calc.update_step_progress(ProgressStep.FETCHING_SIGNATURES, 150)
        assert calc.step_progress[ProgressStep.FETCHING_SIGNATURES] == 100
    
    def test_estimate_step_progress_known_total(self):
        """Test estimating progress with known total"""
        calc = ProgressCalculator()
        
        # Linear progress
        assert calc.estimate_step_progress(0, 100) == 0
        assert calc.estimate_step_progress(25, 100) == 25
        assert calc.estimate_step_progress(50, 100) == 50
        assert calc.estimate_step_progress(100, 100) == 100
        assert calc.estimate_step_progress(150, 100) == 100  # Capped
    
    def test_estimate_step_progress_unknown_total(self):
        """Test estimating progress with unknown total"""
        calc = ProgressCalculator()
        
        # Logarithmic scale
        assert calc.estimate_step_progress(0, 0) == 0
        assert calc.estimate_step_progress(50, 0) == 25  # 50 * 0.5
        assert calc.estimate_step_progress(100, 0) == 50
        # For 1000, it goes to the else branch: min(95, 50 + 50 * (1 - 1000/1000)) = 50
        assert calc.estimate_step_progress(1000, 0) == 50
        assert calc.estimate_step_progress(10000, 0) <= 95  # Asymptotic


class TestEventBuilder:
    """Test event builder helper"""
    
    def test_connected_event(self):
        """Test building connected event"""
        event = EventBuilder.connected("wallet123", request_id="req-123")
        
        assert event.type == EventType.CONNECTED
        assert event.data["status"] == "connected"
        assert event.data["wallet"] == "wallet123"
        assert "timestamp" in event.data
        assert event.id == "req-123"
    
    def test_progress_event(self):
        """Test building progress event"""
        progress_data = ProgressData(
            message="Test",
            percentage=50,
            step=ProgressStep.PROCESSING_TRADES
        )
        
        event = EventBuilder.progress(progress_data, request_id="req-123")
        
        assert event.type == EventType.PROGRESS
        assert event.data["message"] == "Test"
        assert event.data["percentage"] == 50
        assert event.data["step"] == "processing_trades"
        assert event.id == "req-123"
    
    def test_trades_event(self):
        """Test building trades event"""
        trades_data = TradesData(
            trades=[{"sig": "123"}],
            batch_num=1,
            total_yielded=10
        )
        
        event = EventBuilder.trades(trades_data)
        
        assert event.type == EventType.TRADES
        assert event.data["trades"] == [{"sig": "123"}]
        assert event.data["batch_num"] == 1
        assert event.data["total_yielded"] == 10
        assert event.id is None  # No request ID provided
    
    def test_metadata_event(self):
        """Test building metadata event"""
        event = EventBuilder.metadata(
            updated_count=50,
            message="Updated tokens",
            request_id="req-123"
        )
        
        assert event.type == EventType.METADATA
        assert event.data["message"] == "Updated tokens"
        assert event.data["trades_updated"] == 50
        assert "timestamp" in event.data
        assert event.id == "req-123"
    
    def test_complete_event(self):
        """Test building complete event"""
        summary = {"total_trades": 100}
        metrics = {"elapsed": 5.5}
        
        event = EventBuilder.complete(
            summary=summary,
            metrics=metrics,
            elapsed_seconds=5.5,
            request_id="req-123"
        )
        
        assert event.type == EventType.COMPLETE
        assert event.data["status"] == "complete"
        assert event.data["summary"] == summary
        assert event.data["metrics"] == metrics
        assert event.data["elapsed_seconds"] == 5.5
        assert "timestamp" in event.data
        assert event.id == "req-123"
    
    def test_error_event(self):
        """Test building error event"""
        error_data = ErrorData(
            error="Test error",
            code="TEST_001"
        )
        
        event = EventBuilder.error(error_data)
        
        assert event.type == EventType.ERROR
        assert event.data["error"] == "Test error"
        assert event.data["code"] == "TEST_001"
        assert "timestamp" in event.data
    
    def test_heartbeat_event(self):
        """Test building heartbeat event"""
        event = EventBuilder.heartbeat(request_id="req-123")
        
        assert event.type == EventType.HEARTBEAT
        assert "timestamp" in event.data
        assert event.id == "req-123"


class TestEventValidation:
    """Test event schema validation"""
    
    def test_validate_valid_event(self):
        """Test validating a valid event"""
        event = SSEEvent(
            type=EventType.PROGRESS,
            data={
                "message": "Test",
                "percentage": 50,
                "step": "fetching_signatures"
            }
        )
        
        assert validate_event_schema(event) is True
    
    def test_validate_from_dict(self):
        """Test validating event from dictionary"""
        event_dict = {
            'type': 'progress',
            'data': {
                'message': 'Test',
                'percentage': 50,
                'step': 'fetching_signatures'
            }
        }
        
        assert validate_event_schema(event_dict) is True
    
    def test_validate_invalid_type(self):
        """Test validating event with invalid type"""
        event = SSEEvent(
            type="invalid_type",  # type: ignore
            data={}
        )
        
        with pytest.raises(ValueError, match="Invalid event type"):
            validate_event_schema(event)
    
    def test_validate_missing_data(self):
        """Test validating event without data"""
        event = SSEEvent(
            type=EventType.PROGRESS,
            data=None  # type: ignore
        )
        
        with pytest.raises(ValueError, match="Event data must be a dictionary"):
            validate_event_schema(event)
    
    def test_validate_progress_missing_fields(self):
        """Test validating progress event with missing fields"""
        event = SSEEvent(
            type=EventType.PROGRESS,
            data={"message": "Test"}  # Missing percentage and step
        )
        
        with pytest.raises(ValueError, match="missing required field"):
            validate_event_schema(event)
    
    def test_validate_progress_invalid_percentage(self):
        """Test validating progress event with invalid percentage"""
        event = SSEEvent(
            type=EventType.PROGRESS,
            data={
                "message": "Test",
                "percentage": 150,  # Out of range
                "step": "fetching_signatures"
            }
        )
        
        with pytest.raises(ValueError, match="percentage must be between 0 and 100"):
            validate_event_schema(event)
    
    def test_validate_progress_invalid_step(self):
        """Test validating progress event with invalid step"""
        event = SSEEvent(
            type=EventType.PROGRESS,
            data={
                "message": "Test",
                "percentage": 50,
                "step": "invalid_step"
            }
        )
        
        with pytest.raises(ValueError, match="Invalid progress step"):
            validate_event_schema(event)
    
    def test_validate_trades_event(self):
        """Test validating trades event"""
        event = SSEEvent(
            type=EventType.TRADES,
            data={
                "trades": [{"sig": "123"}],
                "batch_num": 1,
                "total_yielded": 10
            }
        )
        
        assert validate_event_schema(event) is True
    
    def test_validate_trades_missing_fields(self):
        """Test validating trades event with missing fields"""
        event = SSEEvent(
            type=EventType.TRADES,
            data={"trades": []}  # Missing batch_num and total_yielded
        )
        
        with pytest.raises(ValueError, match="missing required field"):
            validate_event_schema(event)
    
    def test_validate_trades_invalid_type(self):
        """Test validating trades event with invalid trades type"""
        event = SSEEvent(
            type=EventType.TRADES,
            data={
                "trades": "not_a_list",
                "batch_num": 1,
                "total_yielded": 10
            }
        )
        
        with pytest.raises(ValueError, match="Trades must be a list"):
            validate_event_schema(event)
    
    def test_validate_error_event(self):
        """Test validating error event"""
        event = SSEEvent(
            type=EventType.ERROR,
            data={"error": "Test error"}
        )
        
        assert validate_event_schema(event) is True
    
    def test_validate_error_missing_message(self):
        """Test validating error event without error message"""
        event = SSEEvent(
            type=EventType.ERROR,
            data={}
        )
        
        with pytest.raises(ValueError, match="Error event must contain error message"):
            validate_event_schema(event)
    
    def test_validate_complete_event(self):
        """Test validating complete event"""
        event = SSEEvent(
            type=EventType.COMPLETE,
            data={
                "summary": {"total": 100},
                "metrics": {"time": 5}
            }
        )
        
        assert validate_event_schema(event) is True
    
    def test_validate_complete_missing_fields(self):
        """Test validating complete event with missing fields"""
        event = SSEEvent(
            type=EventType.COMPLETE,
            data={"summary": {}}  # Missing metrics
        )
        
        with pytest.raises(ValueError, match="missing required field"):
            validate_event_schema(event)
    
    def test_validate_heartbeat_event(self):
        """Test validating heartbeat event"""
        event = SSEEvent(
            type=EventType.HEARTBEAT,
            data={"timestamp": 123456}
        )
        
        assert validate_event_schema(event) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
