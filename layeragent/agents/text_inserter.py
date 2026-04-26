"""Text Inserter — 완성된 HTML 구조에 content 텍스트만 삽입 (RQ2의 핵심 stage).

v10 개선:
- Placeholder-leak gate: 출력에 "라벨자리", "placeholder", "값자리" 같은 placeholder 텍스트가
  남아있으면 재생성 (최대 1회)
- CJK word-break 자동 보정: 한국어 텍스트 컨테이너에 word-break 스타일 주입
- Structure-preservation gate: LLM이 .slide-container / .card-wrap-N / .hero-wrap-N 같은
  레이아웃 wrapper 를 떨궜으면 출력 reject → 입력 HTML 그대로 사용 (CJK guard 만 주입).
  prior bug: prompt 의 "구조 변경 금지" 지시를 LLM 이 무시하여 카드 절대 좌표가 사라졌음.
"""
from __future__ import annotations

import json
import re

from ..prompts.text_insert import TEXT_INSERT_PROMPT
from ..utils.common import extract_html, filter_content
from ..utils.llm import text_call


# Placeholder leak 패턴 — 실제 콘텐츠 대신 이런 단어가 남아있으면 실패
PLACEHOLDER_PATTERNS = [
    r"라벨자리", r"값자리", r"아이콘자리", r"숫자자리", r"제목자리",
    r"subtitle placeholder", r"title placeholder", r"stat label placeholder",
    r"placeholder자리", r"\bplaceholder\b", r"\bXXXX\b", r"\bxxxx\b",
]
_LEAK_RE = re.compile("|".join(PLACEHOLDER_PATTERNS), re.IGNORECASE)

_STRUCTURAL_CLASS_RE = re.compile(
    r'class\s*=\s*"[^"]*\b(slide-container|(?:card|hero)-wrap-\d+)\b[^"]*"'
)


def _structural_classes(html: str) -> set[str]:
    """입력 HTML 에서 레이아웃을 결정하는 핵심 class 이름들을 추출."""
    return {m.group(1) for m in _STRUCTURAL_CLASS_RE.finditer(html or "")}


def _structure_preserved(input_html: str, output_html: str) -> tuple[bool, set[str]]:
    """LLM 출력이 입력의 핵심 wrapper class 들을 보존했는지 검사."""
    needed = _structural_classes(input_html)
    if not needed:
        return True, set()
    got = _structural_classes(output_html)
    missing = needed - got
    return (not missing), missing


def _detect_placeholder_leak(html: str) -> list[str]:
    """HTML 본문에서 leak 패턴들을 찾아 반환."""
    # style 태그는 제외 (CSS comment에 placeholder란 단어가 있을 수 있음)
    body = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    matches = _LEAK_RE.findall(body)
    return list(set(matches))


def _inject_cjk_word_break(html: str) -> str:
    """카드/hero/title 컨테이너에 한국어 줄바꿈 가드 CSS 주입.

    .card-value / .hero-value 는 숫자+단위 토큰("+180%", "8.5만") 이 한 단위라
    overflow-wrap:anywhere 로 분해되면 가독성 무너짐. 값(value) 만 break-word
    로, 라벨/설명 텍스트는 anywhere 유지.
    """
    cjk_css = (
        "\n  /* v10 CJK guard — long Korean labels can wrap mid-character */\n"
        "  .card-1, .card-2, .card-3, .card-4, .card-5, .card-6, .card-7, .card-8,\n"
        "  .card-icon, .card-label, .hero-1, .hero-2, .hero-subtitle {\n"
        "    word-break: keep-all;\n"
        "    overflow-wrap: anywhere;\n"
        "    hyphens: none;\n"
        "  }\n"
        "  /* 값 토큰은 절대 분해 금지 (예: +180%, 8.5만, ₩128억) */\n"
        "  .card-value, .hero-value {\n"
        "    word-break: keep-all;\n"
        "    overflow-wrap: normal;\n"
        "    white-space: nowrap;\n"
        "    hyphens: none;\n"
        "  }\n"
    )
    # 첫 <style> 안에 추가 (없으면 삽입)
    if "<style>" in html:
        return html.replace("<style>", "<style>" + cjk_css, 1)
    # style 없으면 div 앞에 하나 추가
    return f"<style>{cjk_css}</style>\n" + html


def text_inserter(state) -> dict:
    html = state.get("assembled", "")
    if not html:
        return {"assembled": html}

    if state.get("ablation") == "no_text_inserter":
        return {"assembled": _inject_cjk_word_break(html)}

    content = filter_content(state.get("content", {}))
    content_json = json.dumps(content, ensure_ascii=False, indent=2)
    prompt = TEXT_INSERT_PROMPT.format(html=html, content_json=content_json)

    raw = text_call(prompt, state.get("model", "gpt-4o"), max_tokens=16000)
    result = extract_html(raw)
    if not result or len(result) < 100:
        return {"assembled": _inject_cjk_word_break(html)}

    # Structure-preservation gate — LLM이 wrapper class들을 떨궜으면 reject
    ok, missing = _structure_preserved(html, result)
    if not ok:
        print(f"[text_inserter] dropped wrappers: {sorted(missing)} → using input")
        return {"assembled": _inject_cjk_word_break(html)}

    # Placeholder leak 탐지 → 재생성 시도 (1회)
    leaks = _detect_placeholder_leak(result)
    if leaks:
        retry_prompt = prompt + (
            f"\n\n★★★ 이전 출력에 placeholder 문자열이 그대로 남았다: {', '.join(leaks)}\n"
            "모든 placeholder 를 실제 콘텐츠 값으로 **반드시** 교체하라.\n"
            "빈 div 는 비워두는 것이 아니라, content JSON 의 해당 필드 값으로 채워라."
        )
        raw2 = text_call(retry_prompt, state.get("model", "gpt-4o"), max_tokens=16000)
        result2 = extract_html(raw2)
        if (result2 and len(result2) > 100
                and not _detect_placeholder_leak(result2)
                and _structure_preserved(html, result2)[0]):
            result = result2
        # 재시도 후에도 leak 남으면 regex로 빈 문자열 치환
        result = _LEAK_RE.sub("", result)

    return {"assembled": _inject_cjk_word_break(result)}
