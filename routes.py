# routes.py
from flask import Blueprint, request, jsonify
import time
from services.session_manager import SM
from services.policy import should_proactively_suggest
from services.retrieval_adapter import to_suggestion_card
from services.nlg_adapter import build_emphetic_prompt, rationale_for

bp = Blueprint("api", __name__)

@bp.post("/session")
def new_session():
    payload = request.get_json(silent=True) or {}
    sid = payload.get("sid") or f"sid_{int(time.time()*1000)}"
    SM.get(sid)  # ensure created
    return jsonify({"sid": sid})

@bp.post("/settings")
def update_settings():
    data = request.get_json(silent=True) or {}
    sid = data["sid"]
    st = SM.get(sid)
    st.settings.update({
        "proactive": bool(data.get("proactive", st.settings["proactive"])),
        "frequency": data.get("frequency", st.settings["frequency"])
    })
    return jsonify({"ok": True, "settings": st.settings})

@bp.post("/emotion")
def push_emotion():
    data = request.get_json(silent=True) or {}
    sid = data["sid"]
    SM.push_emotion(
        sid=sid,
        label=data["label"],
        conf=float(data.get("conf", 1.0)),
        intensity=float(data.get("intensity", 0.0)),
        ts=float(data.get("ts", time.time()*1000))
    )
    return jsonify({"ok": True})

@bp.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    sid = data["sid"]
    user_text = data.get("text", "").strip()
    if not user_text:
        return jsonify({"error": "empty text"}), 400

    # 1) 히스토리 저장
    now_ms = time.time() * 1000
    SM.upsert_turn(sid, "user", user_text, {"ts": now_ms})

    # 2) 간단 NLG 더미(실제 LLM 호출로 대체 가능)
    st = SM.get(sid)
    last_emo = st.emotions[-1]["label"] if st.emotions else "neutral"
    hist_text = "\n".join([f'{t["role"]}: {t["text"]}' for t in st.history])
    prompt = build_emphetic_prompt(hist_text, last_emo)  # noqa: F841 (미사용 경고 회피)
    reply = "I hear you. Let's take it one step at a time."

    # 3) 정책 검사
    action, why = should_proactively_suggest(sid)
    payload = {"reply": reply, "proactive": {"action": action, "why": why}}

    if action != "none":
        reason = rationale_for(action, why)
        query = f"{last_emo} relief short activity"
        card = to_suggestion_card(query, reason)
        payload["proactive"]["card"] = card

    # 4) 에이전트 응답 저장
    SM.upsert_turn(sid, "assistant", reply, {"ts": time.time()*1000, "proactive_action": action})

    return jsonify(payload)

@bp.post("/events")
def log_event():
    # 프런트에서 클릭/표시/거절 등의 이벤트를 수집하여 간단 집계에 활용
    # 여기서는 수신만 수행
    return jsonify({"ok": True})
