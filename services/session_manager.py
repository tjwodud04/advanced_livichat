# services/session_manager.py
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Any

MAX_TURNS = 10

@dataclass
class SessionState:
    history: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=MAX_TURNS))
    emotions: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=MAX_TURNS))
    settings: Dict[str, Any] = field(default_factory=lambda: {
        "proactive": True,
        "frequency": "normal"  # or "low"
    })
    last_proactive_ts: float = 0.0
    last_user_utter_ts: float = 0.0

class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}

    def get(self, sid: str) -> SessionState:
        if sid not in self._sessions:
            self._sessions[sid] = SessionState()
        return self._sessions[sid]

    def upsert_turn(self, sid: str, role: str, text: str, meta: Dict[str, Any]):
        st = self.get(sid)
        st.history.append({"role": role, "text": text, "meta": meta})
        if role == "user":
            st.last_user_utter_ts = meta.get("ts", 0.0)

    def push_emotion(self, sid: str, label: str, conf: float, intensity: float, ts: float):
        st = self.get(sid)
        st.emotions.append({"label": label, "conf": conf, "intensity": intensity, "ts": ts})
        st.last_user_utter_ts = ts

SM = SessionManager()
