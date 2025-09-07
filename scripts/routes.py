import time
from flask import render_template, request, Blueprint, jsonify

# 기존 단일 응답 처리
from scripts.services import process_chat
# NEW: 스트리밍/피드백 핸들러
from scripts.services import stream_chat, proactive_feedback

bp = Blueprint("api", __name__)

def register_routes(app):
    @app.route('/')
    def index():
        return render_template('index.html')

    # 기존: 한 번에 JSON으로 응답
    @app.route('/scripts/chat', methods=['POST'])
    async def chat_once():
        return await process_chat(request)

    # NEW: 스트리밍 응답 (SSE 스타일, 토큰/최종 패킷 순차 수신)
    @app.route('/scripts/chat_stream', methods=['POST'])
    async def chat_stream():
        return await stream_chat(request)

    # NEW: 프로액티브 카드 수용/거절 피드백 수집
    @app.route('/proactive/feedback', methods=['POST'])
    def proactive_feedback_route():
        return proactive_feedback()
