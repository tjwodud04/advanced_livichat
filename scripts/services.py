# scripts/services.py
import base64
import asyncio
import threading
import json
import requests
import datetime
import random
import re
import time
from typing import Dict, Any, List, Tuple, Literal, Optional

from flask import jsonify, abort, request, Response, stream_with_context
from openai import AsyncOpenAI

from scripts.config import (
    VERCEL_TOKEN, VERCEL_PROJ_ID,
    CHARACTER_SYSTEM_PROMPTS, CHARACTER_VOICE,
    EMOTION_LINKS, HISTORY_MAX_LEN
)
from scripts.utils import (
    remove_empty_parentheses, markdown_to_html_links,
    extract_first_markdown_url, remove_emojis
)

# ▼ 프로액티브 정책(쿨다운/거절률/개인화 밴딧) — 별도 모듈
from scripts.proactive import ProactivePolicy, SuggestionType

# ======================================================================================
# 글로벌 상태
# ======================================================================================
conversation_history: List[Dict[str, Any]] = []
history_lock = threading.Lock()

# 프로액티브 정책/세션 상태
_policy = ProactivePolicy()
_last_user_utter_ts: Dict[str, float] = {}  # session_id -> last user ts

# ======================================================================================
# 링크 후처리 유틸
# ======================================================================================
URL_RE    = re.compile(r'(https?://[^\s<>"\']+)', re.IGNORECASE)
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
        link_htmls = [f'<a href="{href}" target="_blank">🔗 {label}</a>' for href, label in links]
        cleaned += "<br>" + " ".join(link_htmls)
    return cleaned

# ======================================================================================
# 프로액티브 카드 관련 헬퍼
# ======================================================================================
def _session_id_from_request() -> str:
    # 세션 식별자 우선순위: form > header > fallback
    return (
        request.form.get("session_id")
        or request.headers.get("X-SESSION-ID")
        or "default-session"
    )

def _topic_hint_from_text(text: str) -> Optional[str]:
    """아주 가벼운 토픽 힌트 추출 (키워드 기반)"""
    t = (text or "").lower()
    if any(k in t for k in ["study", "과제", "공부", "레포트", "task", "코딩", "개발", "debug"]):
        return "work/study"
    if any(k in t for k in ["불안", "초조", "스트레스", "anxious", "stress"]):
        return "stress"
    if any(k in t for k in ["운동", "스트레칭", "걷기", "산책"]):
        return "health"
    return None

def _build_action_button(label: str, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """프론트엔드에서 버튼 클릭 시 action/payload 전송해 실행"""
    return {"label": label, "action": action, "payload": payload}

def _build_suggestion_card(s_types: List[SuggestionType], emotion: str, reason: str) -> Dict[str, Any]:
    """실행형 버튼 2~3개 포함한 제안 카드"""
    title = f"지금 도움이 될 수도 있어요 ({emotion})"
    desc  = f"근거: {reason}"

    buttons: List[Dict[str, Any]] = []
    card_type = "info"
    url_main: Optional[str] = None
    alt_links: List[Dict[str, str]] = []

    for t in s_types:
        if t == "music":
            card_type = "music"
            url_main = "https://www.youtube.com/watch?v=jfKfPfyJRdk"
            buttons.append(_build_action_button("로파이 재생", "play_audio", {"url": url_main}))
        elif t == "breathing":
            buttons.append(_build_action_button("3분 호흡 가이드", "start_breathing", {"duration_sec": 180}))
            alt_links.append({"title": "호흡 가이드 읽기", "url": "https://www.healthline.com/health/box-breathing"})
        elif t == "timer":
            buttons.append(_build_action_button("5분 스트레칭 타이머", "start_timer", {"duration_sec": 300}))
        elif t == "memo":
            buttons.append(_build_action_button("지금 메모하기", "open_memo", {"template": "방금 느낀 감정/생각 한 줄"}))
        elif t == "info":
            url_main = url_main or "https://www.healthline.com/health/mental-health/self-soothing"
            buttons.append(_build_action_button("짧은 읽을거리", "open_link", {"url": url_main}))

    random.shuffle(buttons)
    buttons = buttons[: max(2, min(3, len(buttons)))]
    return {
        "type": "proactive_suggestion",
        "title": title,
        "desc": desc,
        "buttons": buttons,
        "emotion": emotion,
        "timestamp": int(time.time()),
        # 카드 간단 스키마(프론트 호환용)
        "url": url_main,
        "alt": alt_links,
        "reason": reason,
        "card_type": card_type,
        "type_key": card_type
    }

# ======================================================================================
# 공통 I/O
# ======================================================================================
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

# ======================================================================================
# 메인 처리(단발 완성 응답) — 기존 API와 호환
# ======================================================================================
async def process_chat(req):
    try:
        if 'audio' not in req.files:
            return jsonify(error="오디오 파일이 필요합니다."), 400
        api_key   = req.headers.get('X-API-KEY')
        character = req.form.get('character', 'kei')
        session_id = _session_id_from_request()
        client   = get_openai_client(api_key)

        # 1) Whisper STT
        audio_file = req.files['audio']
        stt_result = await client.audio.transcriptions.create(
            file=("audio.webm", audio_file.read()),
            model="whisper-1",
            response_format="text"
        )
        user_text = stt_result or ""

        # 2) 감정 분석 (JSON)
        emotion_resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": '다음 문장에서 불교의 칠정(희,노,애,낙,애(사랑),오,욕)에 대해 '
                               'JSON 형식({"percent": {...}, "top_emotion": "감정"})으로 분석해줘.'
                },
                {"role": "user", "content": user_text}
            ],
            temperature=0.0,
            max_tokens=200,
            response_format={"type": "json_object"}
        )
        emotion_data    = json.loads(emotion_resp.choices[0].message.content)
        emotion_percent = emotion_data.get("percent", {})
        top_emotion     = emotion_data.get("top_emotion", "희")

        # 3) 메인 답변 생성
        system_prompt = CHARACTER_SYSTEM_PROMPTS[character]
        with history_lock:
            messages = [{"role": "system", "content": system_prompt}] + conversation_history[-HISTORY_MAX_LEN:]

        needs_web_search = top_emotion in ["노", "애", "오"]
        ai_text = ""
        audio_b64 = ""
        youtube_link = None

        # =====================[ 웹 검색 분기 ]=====================
        if needs_web_search:
            user_prompt = (
                f"{user_text}\n"
                f"(사용자가 '{top_emotion}' 감정을 느끼고 있습니다. 따뜻한 위로의 말과 함께 웹 검색을 사용해 관련된 위로가 되는 유튜브 음악 URL을 찾아 제안해주세요.)\n"
                "아래와 같은 구조로 2~3문장 이내로 답변하세요:\n"
                "1. 공감의 한마디\n"
                "2. 상황에 어울리는 제안(이럴 때는 ~ 어떤가요?)\n"
                "3. 제안에 대한 간단한 설명"
            )
            messages.append({"role": "user", "content": user_prompt})

            search_response = await client.chat.completions.create(
                model="gpt-4o-mini-search-preview",
                messages=messages,
            )
            result = search_response.choices[0]
            content = result.message.content
            annotations = getattr(result.message, 'annotations', None) or []

            ai_text = content
            link_list: List[str] = []
            for ann in annotations:
                if getattr(ann, "type", None) == "url_citation":
                    url = ann.url_citation.url
                    start = ann.url_citation.start_index
                    end = ann.url_citation.end_index
                    link_text = content[start:end]
                    a_tag = f'<a href="{url}" target="_blank">{link_text}</a>'
                    ai_text = ai_text[:start] + a_tag + ai_text[end:]
                    link_list.append(url)

            ai_text = markdown_to_html_links(ai_text)
            # (옵션) 링크 과다시 제한
            # ai_text = _limit_links(ai_text)

            if link_list:
                youtube_link = link_list[0]
            else:
                youtube_link = extract_first_markdown_url(content)
                if not youtube_link:
                    candidates = EMOTION_LINKS.get(top_emotion, [])
                    if candidates:
                        _, youtube_link = random.choice(candidates)
                    else:
                        youtube_link = None
            if youtube_link and youtube_link not in ai_text:
                ai_text += f'<br><a href="{youtube_link}" target="_blank">▶️ 추천 음악 바로 듣기</a>'

            # TTS 텍스트(링크 제거/이모지 제거)
            tts_text = remove_empty_parentheses(content)
            tts_text = remove_emojis(tts_text)
            offset = 0
            for ann in annotations:
                if getattr(ann, "type", None) == "url_citation":
                    start = ann.url_citation.start_index - offset
                    end = ann.url_citation.end_index - offset
                    tts_text = tts_text[:start] + tts_text[end:]
                    offset += (end - start)
            tts_text = tts_text.strip()

            audio_response = await client.audio.speech.create(
                model="gpt-4o-mini-tts",
                voice=CHARACTER_VOICE[character],
                input=tts_text
            )
            audio_b64 = base64.b64encode(audio_response.content).decode()

        # =====================[ 일반 분기 ]=====================
        else:
            if top_emotion in ["희", "낙", "애(사랑)"]:
                user_prompt = (
                    f"{user_text}\n"
                    f"(사용자가 '{top_emotion}' 감정을 느끼고 있습니다. 어떤 상황인지 구체적으로 질문하며 공감해주세요.)\n"
                )
            elif top_emotion == "욕":
                user_prompt = (
                    f"{user_text}\n"
                    f"(사용자가 '{top_emotion}' 감정을 느끼고 있습니다. 응원의 메시지를 보내주세요.)\n"
                )
            else:
                user_prompt = (
                    f"{user_text}\n"
                    "아래와 같은 구조로 2~3문장 이내로 답변하세요:\n"
                    "1. 공감의 한마디\n"
                    "2. 상황에 어울리는 제안(이럴 때는 ~ 어떤가요?)\n"
                    "3. 제안에 대한 간단한 설명"
                )
            messages.append({"role": "user", "content": user_prompt})

            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.7,
                max_tokens=512,
            )
            ai_text = response.choices[0].message.content or ""
            ai_text = remove_emojis(ai_text)
            if not ai_text:
                ai_text = "아직 답변을 준비하지 못했어요. 다시 한 번 말씀해주시겠어요?"

            # (옵션) 링크 후처리
            # ai_text = markdown_to_html_links(ai_text)
            # ai_text = _limit_links(ai_text)

            tts_text = re.sub(r'링크:.*', '', ai_text).strip()
            tts_text = remove_emojis(tts_text)

            audio_response = await client.audio.speech.create(
                model="gpt-4o-mini-tts",
                voice=CHARACTER_VOICE[character],
                input=tts_text
            )
            audio_b64 = base64.b64encode(audio_response.content).decode()
            youtube_link = None

        # 4) 대화 기록 갱신
        now_kst_iso = datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"
        with history_lock:
            conversation_history.append({"role": "user", "content": user_text, "ts": now_kst_iso})
            conversation_history.append({"role": "assistant", "content": ai_text, "ts": now_kst_iso})
            if len(conversation_history) > HISTORY_MAX_LEN:
                conversation_history[:] = conversation_history[-HISTORY_MAX_LEN:]

        # ---------------- 프로액티브 판단/카드 생성 ----------------
        last_ts = _last_user_utter_ts.get(session_id, 0.0)
        now_ts  = time.time()
        silence_sec = now_ts - last_ts if last_ts > 0 else 0.0
        _last_user_utter_ts[session_id] = now_ts

        topic_hint = _topic_hint_from_text(user_text)
        suggest_res = _policy.should_suggest(
            sid=session_id,
            emotion=top_emotion,
            last_utter_silence_sec=silence_sec,
            topic=topic_hint
        )

        proactive_card: Optional[Dict[str, Any]] = None
        if suggest_res.get("ok"):
            s_types = _policy.choose_suggestion_types(session_id)
            reason  = f"감정={top_emotion}, 침묵={int(silence_sec)}s, topic={topic_hint or '-'}"
            proactive_card = _build_suggestion_card(s_types, top_emotion, reason)
            _policy.stamp_suggested(session_id, reason)

        # 로그 업로드 (비동기)
        log_data = {
            "timestamp": now_kst_iso,
            "session_id": session_id,
            "character": character,
            "user_text": user_text,
            "emotion_percent": emotion_percent,
            "top_emotion": top_emotion,
            "ai_text": ai_text,
            "proactive_card": proactive_card or None
        }
        now = datetime.datetime.now(datetime.timezone.utc)
        blob_name = f"logs/{now.strftime('%Y-%m-%dT%H-%M-%SZ')}_{character}.json"
        asyncio.create_task(asyncio.to_thread(upload_log_to_vercel_blob, blob_name, log_data))

        # 응답
        return jsonify({
            "user_text": user_text,
            "ai_text": remove_empty_parentheses(ai_text),
            "audio": audio_b64,
            "emotion_percent": emotion_percent,
            "top_emotion": top_emotion,
            "link": youtube_link,
            "proactive_card": proactive_card
        })

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": f"Failed to process request: {e}"}), 500

# ======================================================================================
# 스트리밍 처리(SSE 스타일) — /scripts/chat_stream 에서 사용
# ======================================================================================
async def stream_chat(req):
    """
    토큰 단위로 전송 후, 마지막에 최종 패킷(ai_text/html, audio_b64, emotion, proactive_card) 송신
    Front: fetch('/scripts/chat_stream', ...) + ReadableStream 파싱(chat.js 참고)
    """
    if 'audio' not in req.files:
        return jsonify(error="오디오 파일이 필요합니다."), 400

    api_key   = req.headers.get('X-API-KEY')
    character = req.form.get('character', 'kei')
    session_id = _session_id_from_request()
    client    = get_openai_client(api_key)

    # 1) STT
    audio_file = req.files['audio']
    stt_result = await client.audio.transcriptions.create(
        file=("audio.webm", audio_file.read()),
        model="whisper-1",
        response_format="text"
    )
    user_text = stt_result or ""

    # 2) 감정 분석
    emotion_resp = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system",
             "content": '다음 문장에서 불교의 칠정(희,노,애,낙,애(사랑),오,욕)에 대해 '
                        'JSON 형식({"percent": {...}, "top_emotion": "감정"})으로 분석해줘.'},
            {"role": "user", "content": user_text}
        ],
        temperature=0.0,
        max_tokens=200,
        response_format={"type": "json_object"}
    )
    emotion_data    = json.loads(emotion_resp.choices[0].message.content)
    emotion_percent = emotion_data.get("percent", {})
    top_emotion     = emotion_data.get("top_emotion", "희")

    # 3) 스트리밍용 메시지 구성
    system_prompt = CHARACTER_SYSTEM_PROMPTS[character]
    with history_lock:
        messages = [{"role": "system", "content": system_prompt}] + conversation_history[-HISTORY_MAX_LEN:]
        messages.append({"role": "user", "content": user_text})

    needs_web_search = top_emotion in ["노", "애", "오"]
    if needs_web_search:
        messages[-1] = {"role": "user", "content":
            f"{user_text}\n(따뜻한 위로 + 관련 유튜브 음악 URL 제안)\n2~3문장으로 요약 답변"}
        model_name = "gpt-4o-mini-search-preview"
    else:
        model_name = "gpt-4o"

    async def event_stream():
        # LLM 스트림
        stream = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.7,
            max_tokens=512,
            stream=True
        )
        full_text: List[str] = []

        async for chunk in stream:
            delta = chunk.choices[0].delta.get("content")
            if delta:
                full_text.append(delta)
                yield f"event: token\ndata: {json.dumps({'token': delta}, ensure_ascii=False)}\n\n"

        final_text = "".join(full_text).strip() or "아직 답변을 준비하지 못했어요. 다시 말씀해주시겠어요?"
        final_text_noemoji = remove_emojis(final_text)

        # --- 후처리 동시 실행: 링크/카드/로그/TTS ---
        async def build_final_payload():
            # 링크 HTML화
            ai_text_html = markdown_to_html_links(final_text_noemoji)
            # ai_text_html = _limit_links(ai_text_html)  # (옵션)

            # 프로액티브 카드
            proactive_card = None
            try:
                topic_hint = _topic_hint_from_text(user_text)
                last_ts = _last_user_utter_ts.get(session_id, 0.0)
                now_ts  = time.time()
                silence_sec = now_ts - last_ts if last_ts > 0 else 0.0
                _last_user_utter_ts[session_id] = now_ts

                suggest_res = _policy.should_suggest(session_id, top_emotion, silence_sec, topic_hint)
                if suggest_res.get("ok"):
                    s_types = _policy.choose_suggestion_types(session_id)
                    reason  = f"감정={top_emotion}, 침묵={int(silence_sec)}s, topic={topic_hint or '-'}"
                    proactive_card = _build_suggestion_card(s_types, top_emotion, reason)
                    _policy.stamp_suggested(session_id, reason)
            except Exception:
                proactive_card = None

            # 로그 업로드
            now_kst_iso = datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"
            log_data = {
                "timestamp": now_kst_iso,
                "session_id": session_id,
                "character": character,
                "user_text": user_text,
                "emotion_percent": emotion_percent,
                "top_emotion": top_emotion,
                "ai_text": ai_text_html,
                "proactive_card": proactive_card
            }
            now = datetime.datetime.now(datetime.timezone.utc)
            blob_name = f"logs/{now.strftime('%Y-%m-%dT%H-%M-%SZ')}_{character}.json"
            asyncio.create_task(asyncio.to_thread(upload_log_to_vercel_blob, blob_name, log_data))

            # TTS
            audio_b64 = ""
            try:
                tts_text = re.sub(r'링크:.*', '', final_text_noemoji).strip()
                audio_response = await client.audio.speech.create(
                    model="gpt-4o-mini-tts",
                    voice=CHARACTER_VOICE[character],
                    input=tts_text
                )
                audio_b64 = base64.b64encode(audio_response.content).decode()
            except Exception:
                pass

            return {
                "ai_text": ai_text_html,
                "audio": audio_b64,
                "emotion_percent": emotion_percent,
                "top_emotion": top_emotion,
                "proactive_card": proactive_card
            }

        payload = await build_final_payload()
        yield f"event: final\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

# ======================================================================================
# 프로액티브 피드백 수집 — /proactive/feedback
# ======================================================================================
def proactive_feedback():
    """
    JSON: {"session_id": "...", "suggestion_type": "music|breathing|timer|memo|info", "accepted": true/false}
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        session_id = data.get("session_id") or _session_id_from_request()
        suggestion_type = data.get("suggestion_type", "info")
        accepted = bool(data.get("accepted", False))

        stype: SuggestionType = suggestion_type if suggestion_type in ["music","breathing","timer","memo","info"] else "info"
        _policy.feedback(session_id, stype, accepted)
        st = _policy.state_of(session_id)
        return jsonify({"ok": True, "weights": st.pref_weights, "accepts": st.accepts, "rejects": st.rejects})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500
