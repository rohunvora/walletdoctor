#!/usr/bin/env python3
"""
SSE Error Handling and Error Boundaries
"""

import asyncio
import logging
import traceback
from typing import AsyncGenerator, Dict, Any, Optional, Callable
from functools import wraps
import time

from src.lib.progress_protocol import EventBuilder, ErrorData

logger = logging.getLogger(__name__)


class StreamingError(Exception):
    """Base exception for streaming errors"""
    def __init__(self, message: str, code: str = "STREAM_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class RateLimitError(StreamingError):
    """Rate limit exceeded error"""
    def __init__(self, retry_after: int = 60):
        super().__init__(
            "Rate limit exceeded",
            code="RATE_LIMIT",
            details={"retry_after": retry_after}
        )


class WalletNotFoundError(StreamingError):
    """Wallet not found or invalid"""
    def __init__(self, wallet: str):
        super().__init__(
            f"Wallet not found: {wallet}",
            code="WALLET_NOT_FOUND",
            details={"wallet": wallet}
        )


class DataFetchError(StreamingError):
    """Error fetching data from blockchain"""
    def __init__(self, message: str, source: str):
        super().__init__(
            message,
            code="DATA_FETCH_ERROR",
            details={"source": source}
        )


def create_error_boundary(stream_generator: Callable) -> Callable:
    """
    Create an error boundary for streaming generators
    
    Wraps a streaming generator to catch and convert exceptions to error events
    """
    @wraps(stream_generator)
    async def error_boundary_wrapper(*args, **kwargs) -> AsyncGenerator[Any, None]:
        start_time = time.time()
        error_count = 0
        last_error_time = 0
        
        try:
            # Yield from the original generator
            async for event in stream_generator(*args, **kwargs):
                yield event
                
        except asyncio.CancelledError:
            # Clean cancellation
            logger.info("Stream cancelled by client")
            raise
            
        except RateLimitError as e:
            # Rate limit error - client should retry
            logger.warning(f"Rate limit error: {e}")
            error_data = ErrorData(
                error=str(e),
                code=e.code,
                details=e.details
            )
            yield EventBuilder.error(error_data).to_sse_format()
            
        except WalletNotFoundError as e:
            # Invalid wallet - client error
            logger.warning(f"Wallet not found: {e}")
            error_data = ErrorData(
                error=str(e),
                code=e.code,
                details=e.details
            )
            yield EventBuilder.error(error_data).to_sse_format()
            
        except DataFetchError as e:
            # Data fetch error - may be transient
            logger.error(f"Data fetch error: {e}")
            error_count += 1
            
            # Implement circuit breaker pattern
            current_time = time.time()
            if error_count > 3 and (current_time - last_error_time) < 60:
                logger.error("Circuit breaker triggered - too many errors")
                error_data = ErrorData(
                    error="Service temporarily unavailable",
                    code="SERVICE_UNAVAILABLE",
                    details={"retry_after": 60}
                )
                yield EventBuilder.error(error_data).to_sse_format()
            else:
                last_error_time = current_time
                error_data = ErrorData(
                    error=str(e),
                    code=e.code,
                    details=e.details
                )
                yield EventBuilder.error(error_data).to_sse_format()
                
        except Exception as e:
            # Unexpected error - log full traceback
            logger.error(f"Unexpected streaming error: {e}", exc_info=True)
            
            # Send generic error to client (don't leak internals)
            error_data = ErrorData(
                error="An unexpected error occurred",
                code="INTERNAL_ERROR",
                details={"request_id": kwargs.get('request_id', 'unknown')}
            )
            yield EventBuilder.error(error_data).to_sse_format()
            
        finally:
            # Log stream duration
            duration = time.time() - start_time
            logger.info(f"Stream ended after {duration:.2f}s, errors: {error_count}")
    
    return error_boundary_wrapper


def handle_helius_error(error: Exception) -> StreamingError:
    """Convert Helius API errors to streaming errors"""
    error_msg = str(error).lower()
    
    if "429" in error_msg or "rate limit" in error_msg:
        return RateLimitError(retry_after=60)
    elif "404" in error_msg or "not found" in error_msg:
        return DataFetchError("Transaction not found", "helius")
    elif "500" in error_msg or "502" in error_msg or "503" in error_msg:
        return DataFetchError("Helius service unavailable", "helius")
    else:
        return DataFetchError(f"Helius API error: {error}", "helius")


def handle_birdeye_error(error: Exception) -> StreamingError:
    """Convert Birdeye API errors to streaming errors"""
    error_msg = str(error).lower()
    
    if "429" in error_msg or "rate limit" in error_msg:
        return RateLimitError(retry_after=30)
    elif "404" in error_msg:
        return DataFetchError("Price data not available", "birdeye")
    else:
        return DataFetchError(f"Birdeye API error: {error}", "birdeye")


async def with_timeout(coro, timeout: float, error_msg: str):
    """Execute coroutine with timeout"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        raise DataFetchError(f"Timeout: {error_msg}", "timeout")


async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0
) -> Any:
    """
    Retry a function with exponential backoff
    
    Args:
        func: Async function to retry
        max_retries: Maximum number of retries
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
    """
    delay = initial_delay
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            last_error = e
            
            if attempt < max_retries:
                # Log retry
                logger.warning(
                    f"Retry {attempt + 1}/{max_retries} after {delay:.1f}s: {e}"
                )
                
                # Wait with backoff
                await asyncio.sleep(delay)
                
                # Increase delay
                delay = min(delay * exponential_base, max_delay)
            else:
                # Final attempt failed
                logger.error(f"All {max_retries} retries failed: {e}")
    
    # Raise the last error
    raise last_error


# Monitoring and alerting helpers
class ErrorMetrics:
    """Track error metrics for monitoring"""
    
    def __init__(self):
        self.error_counts: Dict[str, int] = {}
        self.last_errors: Dict[str, float] = {}
        self.start_time = time.time()
    
    def record_error(self, error_code: str):
        """Record an error occurrence"""
        self.error_counts[error_code] = self.error_counts.get(error_code, 0) + 1
        self.last_errors[error_code] = time.time()
    
    def get_error_rate(self, error_code: str, window: float = 60) -> float:
        """Get error rate per minute"""
        count = self.error_counts.get(error_code, 0)
        duration = time.time() - self.start_time
        
        if duration < window:
            # Extrapolate for short durations
            return (count / duration) * 60
        else:
            # Use actual rate
            return count / (duration / 60)
    
    def should_alert(self, error_code: str, threshold: float = 10) -> bool:
        """Check if error rate exceeds alert threshold"""
        return self.get_error_rate(error_code) > threshold


# Global error metrics
error_metrics = ErrorMetrics()


def log_streaming_error(error: StreamingError, context: Dict[str, Any]):
    """Log streaming error with context"""
    error_metrics.record_error(error.code)
    
    logger.error(
        "streaming_error",
        extra={
            'error_code': error.code,
            'error_message': str(error),
            'error_details': error.details,
            'wallet': context.get('wallet'),
            'request_id': context.get('request_id'),
            'duration': context.get('duration'),
            'trades_yielded': context.get('trades_yielded', 0)
        }
    )
    
    # Check if we should alert
    if error_metrics.should_alert(error.code):
        logger.critical(
            f"High error rate for {error.code}: "
            f"{error_metrics.get_error_rate(error.code):.1f} errors/min"
        ) 