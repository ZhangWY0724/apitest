from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass

from clients import ExternalApiClient


@dataclass
class SessionContext:
    session_id: str
    platform: str
    client: ExternalApiClient
    last_active: float = 0.0


class SessionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, SessionContext] = {}

    def create(self, platform: str, client: ExternalApiClient) -> SessionContext:
        with self._lock:
            if len(self._sessions) > 100:
                now = time.time()
                expired_keys = [
                    session_id
                    for session_id, context in self._sessions.items()
                    if now - context.last_active > 86400
                ]
                for session_id in expired_keys:
                    self._sessions.pop(session_id, None)

            session_id = str(uuid.uuid4())
            context = SessionContext(
                session_id=session_id,
                platform=platform,
                client=client,
                last_active=time.time(),
            )
            self._sessions[session_id] = context
            return context

    def get(self, session_id: str) -> SessionContext:
        with self._lock:
            context = self._sessions.get(session_id)
            if not context:
                raise KeyError("session 不存在或已过期")
            context.last_active = time.time()
            return context

    def remove(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
