import time

from flask import render_template, request, Blueprint, jsonify
from scripts.services import process_chat
# ❶ 추가 import (위 services.py에 붙인 헬퍼 사용)
from scripts.services import (
    SM, should_proactively_suggest, build_suggestion_card, rationale_for
)

bp = Blueprint("api", __name__)

def register_routes(app):
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/scripts/chat', methods=['POST'])
    async def chat():
        return await process_chat(request) 
    
# ❷ (추가) 세션/감정 엔드포인트 — 기존 코드와 충돌 없으면 그대로 더해도 됨
@bp.post("/session")
def new_session():
    payload = request.get_json(silent=True) or {}
    sid = payload.get("sid") or f"sid_{int(time.time()*1000)}"
    SM.get(sid)  # ensure created
    return jsonify({"sid": sid})

@bp.post("/emotion")
def push_emotion():
    data = request.get_json(silent=True) or {}
    SM.push_emotion(
        sid=data["sid"],
        label=data.get("label","neutral"),
        conf=float(data.get("conf",1.0)),
        intensity=float(data.get("intensity",0.0)),
        ts=float(data.get("ts", time.time()*1000))
    )
    return jsonify({"ok": True})

# ❸ (수정) /chat: 응답에 proactive.card를 조건부 포함
@bp.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    sid = data.get("sid")
    text = (data.get("text") or "").strip()
    if not sid or not text:
        return jsonify({"error":"bad request"}), 400

    # 기존 로직 그대로 두고, 사용자 턴만 기록
    SM.upsert_turn(sid, "user", text, {"ts": time.time()*1000})

    # (예시) 기존 답변 로직 유지 — 아래 reply는 너의 기존 코드 값을 쓰면 됨
    reply = "I hear you. Let's take it one step at a time."

    # 정책 평가 → 카드 생성(있으면)
    action, why = should_proactively_suggest(sid)
    payload = {"reply": reply, "proactive": {"action": action, "why": why}}

    if action != "none":
        reason = rationale_for(action, why)
        # 최근 감정에 맞춘 간단 질의 (없으면 그냥 generic)
        st = SM.get(sid)
        last_emo = (st.emotions[-1]["label"] if st.emotions else "mood")
        query = f"{last_emo} relief short activity"
        payload["proactive"]["card"] = build_suggestion_card(query, reason)

    # 에이전트 턴 로그(선택)
    SM.upsert_turn(sid, "assistant", reply, {"ts": time.time()*1000, "proactive_action": action})
    return jsonify(payload)