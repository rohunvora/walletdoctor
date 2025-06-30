#!/usr/bin/env python3
"""
State Manager - Token notebooks and open questions for consistent conversation state
Persists to disk on critical events and maintains user isolation
"""

import asyncio
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, Optional, List
import duckdb

logger = logging.getLogger(__name__)


class StateManager:
    """Manages conversation state with token notebooks and open questions"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.notebooks = {}  # {user_id: {token: notebook}}
        self.open_questions = {}  # {user_id: [questions]}
        self.user_locks = {}  # {user_id: asyncio.Lock()}
        self.portfolio_cache = {}  # {user_id: (value, timestamp)}
        self.CACHE_TTL = 15  # seconds
        
        # Ensure database schema exists
        self._ensure_schema()
        
        # Load existing state from disk
        self._load_from_disk()
        
        logger.info(f"StateManager initialized with {len(self.notebooks)} users")
    
    def _ensure_schema(self):
        """Create state storage table if it doesn't exist"""
        try:
            db = duckdb.connect(self.db_path)
            db.execute("""
                CREATE TABLE IF NOT EXISTS state_notebooks (
                    user_id BIGINT PRIMARY KEY,
                    state_json TEXT,
                    last_update TIMESTAMP
                )
            """)
            db.close()
            logger.info("State notebooks schema ready")
        except Exception as e:
            logger.error(f"Error creating schema: {e}")
    
    def _load_from_disk(self):
        """Load saved state from database on startup"""
        try:
            db = duckdb.connect(self.db_path)
            result = db.execute("SELECT user_id, state_json FROM state_notebooks").fetchall()
            
            for user_id, state_json in result:
                try:
                    state_data = json.loads(state_json)
                    self.notebooks[user_id] = state_data.get("notebooks", {})
                    self.open_questions[user_id] = state_data.get("open_questions", [])
                    logger.info(f"Loaded state for user {user_id}")
                except Exception as e:
                    logger.error(f"Error loading state for user {user_id}: {e}")
            
            db.close()
            logger.info(f"Loaded state for {len(self.notebooks)} users from disk")
            
        except Exception as e:
            logger.error(f"Error loading state from disk: {e}")
    
    async def get_notebook(self, user_id: int, token: str) -> Dict:
        """Get notebook for user+token with proper isolation"""
        # Ensure user has a lock
        if user_id not in self.user_locks:
            self.user_locks[user_id] = asyncio.Lock()
        
        async with self.user_locks[user_id]:
            # Lazy initialize user if needed
            if user_id not in self.notebooks:
                self.notebooks[user_id] = {}
                logger.info(f"Created new notebook collection for user {user_id}")
            
            # Initialize token notebook if needed
            if token not in self.notebooks[user_id]:
                self.notebooks[user_id][token] = {
                    "last_side": None,
                    "last_size_multiple": 1.0,
                    "last_reason": None,
                    "exposure_pct": 0,
                    "live_pnl_sol": 0,
                    "unanswered_question": False,
                    "question_uuid": None,
                    "question_msg_id": None,
                    "last_update": datetime.now().isoformat()
                }
                logger.info(f"Created new notebook for user {user_id}, token {token}")
            
            # Return a copy to prevent external modification
            return self.notebooks[user_id][token].copy()
    
    async def update_notebook(self, user_id: int, token: str, updates: Dict):
        """Update notebook with new data"""
        if user_id not in self.user_locks:
            self.user_locks[user_id] = asyncio.Lock()
        
        async with self.user_locks[user_id]:
            if user_id not in self.notebooks:
                self.notebooks[user_id] = {}
            
            if token not in self.notebooks[user_id]:
                # Initialize if doesn't exist
                await self.get_notebook(user_id, token)
            
            # Update fields
            notebook = self.notebooks[user_id][token]
            notebook.update(updates)
            notebook["last_update"] = datetime.now().isoformat()
            
            logger.info(f"Updated notebook for {user_id}/{token}: {updates.keys()}")
    
    async def add_open_question(self, user_id: int, msg_id: str, 
                              token: str, question: str) -> str:
        """Add question to open queue and persist immediately"""
        question_uuid = str(uuid.uuid4())
        
        if user_id not in self.user_locks:
            self.user_locks[user_id] = asyncio.Lock()
        
        async with self.user_locks[user_id]:
            # Initialize if needed
            if user_id not in self.open_questions:
                self.open_questions[user_id] = []
            
            # Add to open questions
            self.open_questions[user_id].append({
                "uuid": question_uuid,  # Our ID for reliability
                "msg_id": msg_id,       # Telegram's ID for threading
                "token": token,
                "question": question,
                "timestamp": datetime.now().isoformat()
            })
            
            # Update notebook
            if user_id in self.notebooks and token in self.notebooks[user_id]:
                notebook = self.notebooks[user_id][token]
                notebook["unanswered_question"] = True
                notebook["question_uuid"] = question_uuid
                notebook["question_msg_id"] = msg_id
                notebook["last_update"] = datetime.now().isoformat()
            
            # CRITICAL: Persist immediately for reliability
            await self._persist_user(user_id)
            
            logger.info(f"Added open question for {user_id}/{token}: {question[:50]}...")
        
        return question_uuid
    
    async def mark_question_answered(self, user_id: int, 
                                   question_uuid: str, reason: str):
        """Mark question as answered and persist immediately"""
        if user_id not in self.user_locks:
            self.user_locks[user_id] = asyncio.Lock()
        
        async with self.user_locks[user_id]:
            # Remove from open questions
            if user_id in self.open_questions:
                self.open_questions[user_id] = [
                    q for q in self.open_questions[user_id] 
                    if q["uuid"] != question_uuid
                ]
            
            # Update notebook
            for token, notebook in self.notebooks.get(user_id, {}).items():
                if notebook.get("question_uuid") == question_uuid:
                    notebook["unanswered_question"] = False
                    notebook["last_reason"] = reason
                    notebook["question_uuid"] = None
                    notebook["question_msg_id"] = None
                    notebook["last_update"] = datetime.now().isoformat()
                    logger.info(f"Marked question answered for {user_id}/{token}: {reason}")
                    break
            
            # CRITICAL: Persist immediately
            await self._persist_user(user_id)
    
    async def find_open_question_for_user(self, user_id: int) -> Optional[str]:
        """Find the most recent open question for a user"""
        if user_id in self.open_questions and self.open_questions[user_id]:
            # Return the most recent question UUID
            return self.open_questions[user_id][-1]["uuid"]
        return None
    
    def get_nudge_decision(self, notebook: Dict, new_trade: Dict) -> str:
        """Ultra-simple decision logic - no feature creep!"""
        
        # Rule 1: Never duplicate
        if notebook.get("unanswered_question", False):
            return "skip"
        
        # Rule 2: Risk outliers get context
        exposure = notebook.get("exposure_pct", 0)
        live_pnl = notebook.get("live_pnl_sol", 0)
        
        if exposure > 20 or abs(live_pnl) > 10:
            return "ask_with_risk"
        
        # Rule 3: Everything else gets standard
        return "ask_standard"
    
    async def get_portfolio_value(self, user_id: int) -> float:
        """Get cached portfolio value or calculate"""
        now = datetime.now()
        
        # Check cache
        if user_id in self.portfolio_cache:
            value, timestamp = self.portfolio_cache[user_id]
            if (now - timestamp).seconds < self.CACHE_TTL:
                return value
        
        # TODO: Pull from P&L service once integrated
        # For now, return placeholder to avoid breaking risk calcs
        value = 100.0
        
        # Cache the value
        self.portfolio_cache[user_id] = (value, now)
        return value
    
    async def _persist_user(self, user_id: int):
        """Save one user's state to disk immediately"""
        try:
            db = duckdb.connect(self.db_path)
            
            state_json = json.dumps({
                "notebooks": self.notebooks.get(user_id, {}),
                "open_questions": self.open_questions.get(user_id, [])
            })
            
            db.execute("""
                INSERT INTO state_notebooks (user_id, state_json, last_update)
                VALUES (?, ?, ?)
                ON CONFLICT (user_id) DO UPDATE SET
                    state_json = EXCLUDED.state_json,
                    last_update = EXCLUDED.last_update
            """, [user_id, state_json, datetime.now()])
            
            db.close()
            logger.info(f"Persisted state for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error persisting state for user {user_id}: {e}")
    
    async def persist_all(self):
        """Persist all users' state (for graceful shutdown)"""
        logger.info("Persisting all user states...")
        for user_id in self.notebooks.keys():
            await self._persist_user(user_id)
        logger.info(f"Persisted state for {len(self.notebooks)} users")
    
    async def shutdown(self):
        """Graceful shutdown - save everything"""
        await self.persist_all()
        logger.info("StateManager shutdown complete")


# Testing utilities
async def test_state_manager():
    """Test basic functionality"""
    import tempfile
    import os
    
    # Create temporary database with unique name
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_state.db')
    
    try:
        # Test 1: Basic notebook operations
        manager = StateManager(db_path)
        
        # Get notebook for user 123, token BONK
        notebook = await manager.get_notebook(123, "BONK")
        assert notebook["unanswered_question"] == False
        print("✓ Notebook creation works")
        
        # Add open question
        q_uuid = await manager.add_open_question(123, "msg_456", "BONK", "BONK again?")
        notebook = await manager.get_notebook(123, "BONK")
        assert notebook["unanswered_question"] == True
        print("✓ Open question tracking works")
        
        # Test persistence - create new manager
        manager2 = StateManager(db_path)
        notebook2 = await manager2.get_notebook(123, "BONK")
        assert notebook2["unanswered_question"] == True
        print("✓ Persistence works")
        
        # Mark answered
        await manager2.mark_question_answered(123, q_uuid, "taking profits")
        notebook3 = await manager2.get_notebook(123, "BONK")
        assert notebook3["unanswered_question"] == False
        assert notebook3["last_reason"] == "taking profits"
        print("✓ Answer tracking works")
        
        # Test user isolation
        notebook_user2 = await manager2.get_notebook(456, "BONK")
        assert notebook_user2["unanswered_question"] == False
        print("✓ User isolation works")
        
        # Test decision logic
        decision1 = manager2.get_nudge_decision({"unanswered_question": True}, {})
        assert decision1 == "skip"
        print("✓ Skip logic works")
        
        decision2 = manager2.get_nudge_decision({"unanswered_question": False, "exposure_pct": 25}, {})
        assert decision2 == "ask_with_risk"
        print("✓ Risk detection works")
        
        print("\n✅ All tests passed!")
        
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_state_manager()) 