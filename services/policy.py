# services/policy.py
import time
from typing import Literal, Tuple
from services.session_manager import SM, SessionState

Action = Literal["none", "hint", "assist", "recommend"]

DEFAULTS = {
    "sad_thr": 0.5,
    "ang_thr": 0.6,
    "silence_ms": 15000,    # 15s
    "cooldown_ms": 45000,   # 45s
}

def _recent_emotion(st: SessionState):
    return st.emotions[-1] if st.emotions else None

def should_proactively_suggest(sid: str, now: float = None) -> Tuple[Action, str]:
    st = SM.get(sid)
    if not st.settings.get("proactive", True):
        return "none", "proactive disabled by user"

    now = now or time.time() * 1000
    if now - st.last_proactive_ts < DEFAULTS["cooldown_ms"]:
        return "none", "cooldown active"

    # 침묵 기반 트리거
    if st.last_user_utter_ts and (now - st.last_user_utter_ts) > DEFAULTS["silence_ms"]:
        st.last_proactive_ts = now
        return "hint", "prolonged silence"

    emo = _recent_emotion(st)
    if not emo:
        return "none", "no emotion signal"

    label, intensity = emo["label"], emo["intensity"]
    if label == "sadness" and intensity >= DEFAULTS["sad_thr"]:
        st.last_proactive_ts = now
        return "recommend", "sadness detected"
    if label == "anger" and intensity >= DEFAULTS["ang_thr"]:
        st.last_proactive_ts = now
        return "assist", "anger detected"

    return "none", "no policy hit"
