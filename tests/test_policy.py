# tests/test_policy.py
from services.session_manager import SM
from services.policy import should_proactively_suggest, DEFAULTS
import time

def test_cooldown_blocks():
    sid = "t1"
    st = SM.get(sid)
    st.settings["proactive"] = True
    base = 1_000_000
    st.last_proactive_ts = base
    # 10초 후 → 아직 쿨다운
    action, why = should_proactively_suggest(sid, now=base + 10_000)
    assert action == "none" and "cooldown" in why

def test_silence_triggers_hint():
    sid = "t2"
    st = SM.get(sid)
    now = time.time() * 1000
    st.last_user_utter_ts = now - (DEFAULTS["silence_ms"] + 1_000)
    action, why = should_proactively_suggest(sid, now=now)
    assert action == "hint"

def test_emotion_triggers():
    sid = "t3"
    st = SM.get(sid)
    now = time.time() * 1000
    st.emotions.clear()
    st.emotions.append({"label":"sadness","conf":0.8,"intensity":0.6,"ts":now})
    action, why = should_proactively_suggest(sid, now=now)
    assert action == "recommend"
