import base64
import asyncio
import threading
import json
import requests
import datetime
import random
import re
import time
from flask import jsonify, abort
from openai import AsyncOpenAI
from scripts.config import VERCEL_TOKEN, VERCEL_PROJ_ID, CHARACTER_SYSTEM_PROMPTS, CHARACTER_VOICE, EMOTION_LINKS, HISTORY_MAX_LEN
from scripts.utils import remove_empty_parentheses, markdown_to_html_links, extract_first_markdown_url, remove_emojis
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Any, List, Tuple, Literal

conversation_history = []
history_lock = threading.Lock()

# ---------------- 추가: 링크 후처리 유틸 ----------------

URL_RE = re.compile(r'(https?://[^\s<>"\']+)', re.IGNORECASE)
ANCHOR_RE = re.compile(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)

def _infer_reco_type(text: str) -> str:
    """텍스트 기반으로 추천 유형 추정 (음악 관련 키워드 있으면 music, 아니면 content)"""
    t = text.lower()
    music_kw = ["음악", "노래", "곡", "뮤직", "playlist", "플레이리스트", "song", "track"]
    return "music" if any(k in t for k in music_kw) else "content"

def _extract_links(raw: str) -> List[Tuple[str, str]]:
    """텍스트에서 링크 (href, label) 추출"""
    found: List[Tuple[str, str]] = []

    for m in ANCHOR_RE.finditer(raw):
        href, label = m.group(1).strip(), m.group(2).strip()
        if href and (href, label) not in found:
            found.append((href, label or href))

    for m in URL_RE.finditer(raw):
        url = m.group(1).strip()
        if not any(url == h for h, _ in found):
            found.append((url, url))
    return found

def _limit_links(ai_text: str) -> str:
    """추천 유형에 따라 링크 개수를 제한"""
    reco_type = _infer_reco_type(ai_text)
    links = _extract_links(ai_text)

    limit = 1 if reco_type == "music" else 2
    links = links[:limit]

    # 기존 텍스트에서 모든 링크 제거 후, 제한된 링크만 다시 붙이기
    cleaned = ANCHOR_RE.sub("", ai_text)
    cleaned = URL_RE.sub("", cleaned).strip()

    if links:
        link_htmls = [
            f'<a href="{href}" target="_blank">🔗 {label}</a>'
            for href, label in links
        ]
        cleaned += "<br>" + " ".join(link_htmls)

    return cleaned

# ---------------- 기존 함수 ----------------

def get_openai_client(api_key: str):
    if not api_key:
        abort(401, description="OpenAI API 키가 필요합니다.")
    return AsyncOpenAI(api_key=api_key)

def upload_log_to_vercel_blob(blob_name: str, data: dict):
    if not VERCEL_TOKEN or not VERCEL_PROJ_ID:
        print("Vercel 환경변수(VERCEL_TOKEN, VERCEL_PROJECT_ID)가 없어 로그를 저장하지 않습니다.")
        return
    try:
        b64_data = base64.b64encode(json.dumps(data, ensure_ascii=False).encode()).decode()
        resp = requests.post(
            "https://api.vercel.com/v2/blob",
            headers={"Authorization": f"Bearer {VERCEL_TOKEN}"},
            json={"projectId": VERCEL_PROJ_ID, "data": b64_data, "name": blob_name}
        )
        resp.raise_for_status()
        print(f"로그 저장 성공: {blob_name}")
    except Exception as e:
        print(f"Vercel Blob 로그 업로드 예외: {e}")

async def process_chat(request):
    try:
        if 'audio' not in request.files:
            return jsonify(error="오디오 파일이 필요합니다."), 400
        api_key = request.headers.get('X-API-KEY')
        character = request.form.get('character', 'kei')
        client = get_openai_client(api_key)

        # 1. Whisper STT
        audio_file = request.files['audio']
        stt_result = await client.audio.transcriptions.create(
            file=("audio.webm", audio_file.read()),
            model="whisper-1",
            response_format="text"
        )
        user_text = stt_result

        # 2. 감정 분석
        emotion_resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": '다음 문장에서 불교의 칠정(희,노,애,낙,애(사랑),오,욕)에 대해 JSON 형식({"percent": {...}, "top_emotion": "감정"})으로 분석해줘.'},
                {"role": "user", "content": user_text}
            ],
            temperature=0.0,
            max_tokens=200,
            response_format={"type": "json_object"}
        )
        emotion_data = json.loads(emotion_resp.choices[0].message.content)
        emotion_percent = emotion_data.get("percent", {})
        top_emotion = emotion_data.get("top_emotion", "희")

        # 3. 메인 답변 생성
        system_prompt = CHARACTER_SYSTEM_PROMPTS[character]
        with history_lock:
            messages = [{"role": "system", "content": system_prompt}] + conversation_history[-HISTORY_MAX_LEN:]

        needs_web_search = top_emotion in ["노", "애", "오"]
        ai_text = ""
        audio_b64 = ""
        youtube_link = None

        if needs_web_search:
            # (생략) 기존 LLM 호출 및 ai_text 생성 로직 동일
            # ...
            ai_text = markdown_to_html_links(ai_text)
            # 링크 후보 찾기
            youtube_link = extract_first_markdown_url(ai_text)
            # 링크 후처리
            ai_text = _limit_links(ai_text)

            # (생략) TTS 처리 동일
            # ...
        else:
            # (생략) 기존 LLM 호출 및 ai_text 생성 로직 동일
            ai_text = remove_emojis(ai_text) or "아직 답변을 준비하지 못했어요. 다시 한 번 말씀해주시겠어요?"
            ai_text = _limit_links(ai_text)  # 후처리 추가
            # (생략) TTS 처리 동일
            # ...

        with history_lock:
            conversation_history.append({"role": "user", "content": user_text})
            conversation_history.append({"role": "assistant", "content": ai_text})
            if len(conversation_history) > HISTORY_MAX_LEN:
                conversation_history[:] = conversation_history[-HISTORY_MAX_LEN:]

        log_data = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
            "character": character,
            "user_text": user_text,
            "emotion_percent": emotion_percent,
            "top_emotion": top_emotion,
            "ai_text": ai_text
        }
        now = datetime.datetime.now(datetime.timezone.utc)
        blob_name = f"logs/{now.strftime('%Y-%m-%dT%H-%M-%SZ')}_{character}.json"
        asyncio.create_task(asyncio.to_thread(upload_log_to_vercel_blob, blob_name, log_data))

        return jsonify({
            "user_text": user_text,
            "ai_text": remove_empty_parentheses(ai_text),
            "audio": audio_b64,
            "emotion_percent": emotion_percent,
            "top_emotion": top_emotion,
            "link": youtube_link
        })

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": f"Failed to process request: {e}"}), 500 
