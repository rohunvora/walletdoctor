#!/usr/bin/env python3
"""
Progress tracking for long-running API operations
"""

import time
import uuid
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class ProgressInfo:
    """Information about a long-running operation"""
    token: str
    status: str = "pending"  # pending, fetching, complete, error
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    pages_fetched: int = 0
    total_pages: int = 0
    trades_found: int = 0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to API response format"""
        return {
            "token": self.token,
            "status": self.status,
            "pages": self.pages_fetched,
            "total": self.total_pages,
            "trades": self.trades_found,
            "error": self.error,
            "age_seconds": int(time.time() - self.created_at)
        }
    
    def is_expired(self, ttl_seconds: int = 300) -> bool:
        """Check if this progress entry has expired (default 5 minutes)"""
        return time.time() - self.created_at > ttl_seconds


class ProgressTracker:
    """Track progress of long-running operations"""
    
    def __init__(self, ttl_seconds: int = 300):
        """Initialize tracker with TTL in seconds (default 5 minutes)"""
        self.ttl_seconds = ttl_seconds
        self._progress: Dict[str, ProgressInfo] = {}
        self._lock = Lock()
    
    def create_progress(self) -> str:
        """Create a new progress tracking token"""
        token = str(uuid.uuid4())
        with self._lock:
            self._progress[token] = ProgressInfo(token=token)
            self._clean_expired()
        return token
    
    def update_progress(
        self, 
        token: str,
        status: Optional[str] = None,
        pages_fetched: Optional[int] = None,
        total_pages: Optional[int] = None,
        trades_found: Optional[int] = None,
        error: Optional[str] = None
    ) -> bool:
        """Update progress for a token. Returns False if token not found."""
        with self._lock:
            if token not in self._progress:
                return False
            
            progress = self._progress[token]
            progress.updated_at = time.time()
            
            if status is not None:
                progress.status = status
            if pages_fetched is not None:
                progress.pages_fetched = pages_fetched
            if total_pages is not None:
                progress.total_pages = total_pages
            if trades_found is not None:
                progress.trades_found = trades_found
            if error is not None:
                progress.error = error
                progress.status = "error"
            
            return True
    
    def get_progress(self, token: str) -> Optional[Dict[str, Any]]:
        """Get progress for a token. Returns None if not found or expired."""
        with self._lock:
            self._clean_expired()
            
            if token not in self._progress:
                return None
            
            return self._progress[token].to_dict()
    
    def delete_progress(self, token: str) -> bool:
        """Delete progress for a token. Returns False if not found."""
        with self._lock:
            if token in self._progress:
                del self._progress[token]
                return True
            return False
    
    def _clean_expired(self):
        """Remove expired progress entries (must be called with lock held)"""
        expired_tokens = [
            token for token, progress in self._progress.items()
            if progress.is_expired(self.ttl_seconds)
        ]
        for token in expired_tokens:
            del self._progress[token]


# Global instance
_progress_tracker = ProgressTracker()


def get_progress_tracker() -> ProgressTracker:
    """Get the global progress tracker instance"""
    return _progress_tracker 