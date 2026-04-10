"""
User Session and Token Store

In-memory session management for API authentication.
Provides token blacklisting for logout functionality.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Set


@dataclass
class UserSession:
    """Active user session"""
    user_id: str
    username: str
    role: str
    permission_level: str
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    client_ip: Optional[str] = None


class SessionStore:
    """
    In-memory session and token store.

    Thread-safe session management with token blacklisting support.
    """

    def __init__(self):
        self._sessions: Dict[str, UserSession] = {}  # session_id -> session
        self._user_sessions: Dict[str, Set[str]] = {}  # user_id -> set of session_ids
        self._blacklisted_tokens: Set[str] = set()
        self._lock = threading.Lock()

    def create_session(
        self,
        user_id: str,
        username: str,
        role: str,
        permission_level: str,
        client_ip: Optional[str] = None,
    ) -> str:
        """
        Create a new session for a user.

        Args:
            user_id: User identifier
            username: Username
            role: User role
            permission_level: Permission level (L0-L3)
            client_ip: Client IP address

        Returns:
            Session ID
        """
        import secrets
        session_id = secrets.token_urlsafe(32)

        with self._lock:
            session = UserSession(
                user_id=user_id,
                username=username,
                role=role,
                permission_level=permission_level,
                client_ip=client_ip,
            )
            self._sessions[session_id] = session

            if user_id not in self._user_sessions:
                self._user_sessions[user_id] = set()
            self._user_sessions[user_id].add(session_id)

        return session_id

    def get_session(self, session_id: str) -> Optional[UserSession]:
        """
        Get a session by ID, updating last accessed time.

        Args:
            session_id: Session identifier

        Returns:
            UserSession if found, None otherwise
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.last_accessed = time.time()
            return session

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session (logout).

        Args:
            session_id: Session identifier

        Returns:
            True if session was deleted
        """
        with self._lock:
            session = self._sessions.pop(session_id, None)
            if session and session.user_id in self._user_sessions:
                self._user_sessions[session.user_id].discard(session_id)
            return session is not None

    def delete_user_sessions(self, user_id: str) -> int:
        """
        Delete all sessions for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of sessions deleted
        """
        with self._lock:
            session_ids = self._user_sessions.pop(user_id, set())
            for session_id in session_ids:
                self._sessions.pop(session_id, None)
            return len(session_ids)

    def blacklist_token(self, token_jti: str) -> None:
        """
        Add a token to the blacklist (for logout).

        Args:
            token_jti: JWT token ID (jti claim)
        """
        with self._lock:
            self._blacklisted_tokens.add(token_jti)

    def is_token_blacklisted(self, token_jti: str) -> bool:
        """
        Check if a token is blacklisted.

        Args:
            token_jti: JWT token ID (jti claim)

        Returns:
            True if blacklisted
        """
        return token_jti in self._blacklisted_tokens

    def get_user_session_count(self, user_id: str) -> int:
        """Get number of active sessions for a user."""
        with self._lock:
            return len(self._user_sessions.get(user_id, set()))

    def cleanup_expired_sessions(self, max_idle_seconds: float = 3600) -> int:
        """
        Remove sessions that have been idle too long.

        Args:
            max_idle_seconds: Maximum idle time before cleanup

        Returns:
            Number of sessions removed
        """
        import time
        now = time.time()
        removed = 0

        with self._lock:
            expired_session_ids = [
                sid for sid, session in self._sessions.items()
                if now - session.last_accessed > max_idle_seconds
            ]

            for session_id in expired_session_ids:
                session = self._sessions.pop(session_id, None)
                if session and session.user_id in self._user_sessions:
                    self._user_sessions[session.user_id].discard(session_id)
                    removed += 1

        return removed


# Global session store
session_store = SessionStore()


__all__ = [
    "SessionStore",
    "UserSession",
    "session_store",
]
