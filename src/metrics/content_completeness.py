"""
Metric: Content Completeness Rate (CCR)
입력 콘텐츠 데이터의 텍스트가 생성된 HTML에 실제로 존재하는 비율.

Reference-free: 입력 content dict와 생성 HTML만으로 측정.
Deterministic: 문자열 매칭 기반.
"""

from __future__ import annotations

import re
from bs4 import BeautifulSoup


def _extract_text_items(content: dict) -> list[dict]:
    """콘텐츠 딕셔너리에서 평가할 텍스트 항목 추출.

    speaker_script, infographic_script 등 슬라이드에 렌더링하지 않는 필드는 제외.
    """
    skip_keys = {"speaker_script", "infographic_script"}
    items = []

    def _add(key: str, value: str, importance: str = "normal"):
        text = value.strip()
        if text and len(text) >= 2:  # 1글자는 노이즈
            items.append({"key": key, "text": text, "importance": importance})

    for k, v in content.items():
        if k in skip_keys:
            continue

        if k == "title":
            _add("title", v, "high")
        elif k == "subtitle":
            _add("subtitle", v, "high")
        elif k == "description":
            _add("description", v, "normal")
        elif k == "columns" and isinstance(v, list):
            for i, col in enumerate(v):
                if isinstance(col, dict):
                    if "title" in col:
                        _add(f"column_{i}_title", col["title"], "high")
                    if "description" in col:
                        _add(f"column_{i}_desc", col["description"], "normal")
                    if "metric" in col:
                        _add(f"column_{i}_metric", col["metric"], "normal")
        elif k == "items" and isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    if "title" in item:
                        _add(f"item_{i}_title", item["title"], "high")
                    if "description" in item:
                        _add(f"item_{i}_desc", item["description"], "normal")
        elif k == "left" and isinstance(v, dict):
            if "label" in v:
                _add("left_label", v["label"], "high")
            if "items" in v and isinstance(v["items"], list):
                for i, item in enumerate(v["items"]):
                    if isinstance(item, str):
                        _add(f"left_item_{i}", item, "normal")
                    elif isinstance(item, dict) and "text" in item:
                        _add(f"left_item_{i}", item["text"], "normal")
        elif k == "right" and isinstance(v, dict):
            if "label" in v:
                _add("right_label", v["label"], "high")
            if "items" in v and isinstance(v["items"], list):
                for i, item in enumerate(v["items"]):
                    if isinstance(item, str):
                        _add(f"right_item_{i}", item, "normal")
                    elif isinstance(item, dict) and "text" in item:
                        _add(f"right_item_{i}", item["text"], "normal")
        elif isinstance(v, str) and k not in ("presenter", "date"):
            _add(k, v, "normal")

    return items


def _normalize(text: str) -> str:
    """비교를 위한 텍스트 정규화."""
    text = re.sub(r'\s+', ' ', text).strip()
    return text.lower()


def _check_presence(text: str, html_text: str) -> float:
    """텍스트가 HTML에 존재하는 정도를 0~1로 반환.

    전체 일치: 1.0
    앞부분 일치 (긴 텍스트가 잘린 경우): 부분 점수
    미존재: 0.0
    """
    norm_text = _normalize(text)
    norm_html = _normalize(html_text)

    # 전체 일치
    if norm_text in norm_html:
        return 1.0

    # 앞 15글자 이상 매칭 (긴 description이 잘린 경우)
    if len(norm_text) > 15:
        prefix = norm_text[:15]
        if prefix in norm_html:
            return 0.7  # 부분 점수

    # 핵심 키워드 매칭 (제목 등 짧은 텍스트)
    if len(norm_text) <= 30:
        words = [w for w in norm_text.split() if len(w) >= 2]
        if words:
            matched = sum(1 for w in words if w in norm_html)
            ratio = matched / len(words)
            if ratio >= 0.6:
                return ratio * 0.8  # 키워드 매칭은 최대 0.8

    return 0.0


def content_completeness_rate(content: dict, html: str) -> dict:
    """Content Completeness Rate 계산.

    Args:
        content: 슬라이드 콘텐츠 딕셔너리 (slide_contents[i]["content"])
        html: 생성된 HTML 코드

    Returns:
        dict with:
        - rate: 0.0 ~ 1.0 (1.0 = 모든 콘텐츠가 HTML에 존재)
        - high_importance_rate: 중요 항목(title 등)의 존재율
        - total_items: 평가 대상 텍스트 항목 수
        - found_items: 존재 확인된 항목 수
        - detail: 항목별 결과
    """
    # HTML에서 텍스트 추출
    soup = BeautifulSoup(html, 'html.parser')
    html_text = soup.get_text(separator=' ')

    items = _extract_text_items(content)

    if not items:
        return {
            "rate": 1.0,
            "high_importance_rate": 1.0,
            "total_items": 0,
            "found_items": 0,
            "detail": [],
        }

    detail = []
    total_score = 0
    high_total = 0
    high_score = 0

    for item in items:
        score = _check_presence(item["text"], html_text)
        detail.append({
            "key": item["key"],
            "text": item["text"][:50],
            "importance": item["importance"],
            "score": round(score, 2),
        })
        total_score += score

        if item["importance"] == "high":
            high_total += 1
            high_score += score

    rate = total_score / len(items) if items else 1.0
    high_rate = high_score / high_total if high_total > 0 else 1.0

    return {
        "rate": round(rate, 4),
        "high_importance_rate": round(high_rate, 4),
        "total_items": len(items),
        "found_items": sum(1 for d in detail if d["score"] > 0),
        "detail": detail,
    }
