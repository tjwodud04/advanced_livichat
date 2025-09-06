# services/retrieval_adapter.py
from typing import List, Dict

def search_preview(query: str) -> List[Dict]:
    """
    실제 구현:
    - gpt-4o-mini-search-preview 또는 기존 검색/인용 API와 연동
    - URL/제목이 annotation으로 포함된 결과를 받아서 1~2개로 축약
    지금은 목 데이터 반환.
    """
    results = [
        {"title": "Breathing Exercise (5m)", "url": "https://example.com/breathing"},
        {"title": "Lo-fi playlist", "url": "https://example.com/lofi"}
    ]
    return results[:2]

def to_suggestion_card(query: str, reason: str) -> Dict:
    items = search_preview(query)
    card = {
        "type": "suggestion",
        "title": items[0]["title"] if items else "Suggestion",
        "reason": reason,
        "url": items[0]["url"] if items else None,
        "alt": items[1:] if len(items) > 1 else []
    }
    return card
