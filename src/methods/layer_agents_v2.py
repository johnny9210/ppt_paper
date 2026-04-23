"""
Method E v2: Layer-Decomposed Multi-Agent with Precise Coordinates

개선점 (v1 대비):
1. Visual CoT 분석에서 % 단위 정밀 좌표를 추출
2. 모든 agent가 같은 좌표를 공유 → 정렬 보장
3. 저장된 디자인 이미지 사용 (Gemini 재호출 불필요)
4. 각 agent에 구체적 CSS 패턴 + 금지 규칙 포함
"""

import base64
import json
import re
from pathlib import Path
from openai import OpenAI


# ══════════════════════════════════════
# Step 1: 정밀 좌표 분석
# ══════════════════════════════════════

PRECISE_ANALYSIS_PROMPT = """이 디자인 이미지(1280×720px 슬라이드)를 레이어별로 분석하고, 각 요소의 위치를 % 단위로 정확히 명시해주세요.

**슬라이드 크기: 1280×720px. 모든 위치/크기를 % 단위로 표시.**

4개 레이어로 분해:

**Layer 0 - Background**:
- 배경 유형 (solid/gradient_linear/gradient_radial/pattern)
- 색상, 방향
- 장식 도형: {shape, left%, top%, width%, height%, color, opacity}

**Layer 1 - Cards**:
- 각 카드: {id, left%, top%, width%, height%, style(glassmorphism/solid/gradient_border), border_radius, shadow, bg_color, border}

**Layer 2 - Content** (텍스트 영역만, 내용은 무시):
- 제목: {left%, top%, width%, height%, font_size_rem, font_weight, color}
- 부제: {left%, top%, width%, height%, font_size_rem, color}
- 본문/목록: {left%, top%, width%, height%, items_count}
- 태그/라벨: {left%, top%, text, bg_color, text_color}

**Layer 3 - Icons**:
- 각 아이콘: {id, left%, top%, size_px, shape(circle/rounded), bg_color, suggested_fa_icon}
- 장식: {type(accent_line/divider/bar), left%, top%, width%, height%, color}

**전체 테마**:
- primary_color, accent_color, background_color, text_color

JSON으로 출력. 좌표는 반드시 % 단위로."""


# ══════════════════════════════════════
# 레이어별 Agent 프롬프트
# ══════════════════════════════════════

COMMON_RULES = """
공통 규칙:
- 컨테이너: width:100%; height:100%; position:absolute; inset:0;
- 이 레이어의 모든 자식 요소: position:absolute; 좌표는 분석의 % 값 그대로 사용
- <style>과 <div>로 구성된 HTML만 출력 (설명 없이)
- JavaScript 금지, <img> 태그 금지
금지 CSS:
- ❌ clip-path, ❌ filter:blur(), ❌ box-shadow 3개 이상
- ❌ transparent gradient stop (rgba(배경색,0) 대신 사용)
- ❌ 풀사이즈 장식 div에 그라디언트 금지"""

BG_PROMPT = """슬라이드 배경(Layer 0)만 HTML+CSS로 구현하세요. z-index: 0~9.

[분석 — Layer 0 부분만 참고]
{analysis}

[테마 컬러]
primary: {primary}, accent: {accent}, bg: {bg_color}

★ 분석의 좌표(% 단위)를 정확히 따르세요.
★ 배경 그라디언트, 패턴, 장식 도형만 구현. 카드/텍스트/아이콘은 만들지 마세요.
★ CSS 선택자: .{slide_id}-bg
{common_rules}"""

CARDS_PROMPT = """슬라이드 카드/컨테이너(Layer 1)만 HTML+CSS로 구현하세요. z-index: 10~19.

[분석 — Layer 1 부분만 참고]
{analysis}

[테마 컬러]
primary: {primary}, accent: {accent}, bg: {bg_color}

★ 분석의 좌표(% 단위)를 정확히 따르세요.
★ 카드 구조만 구현. 카드 안에 텍스트/아이콘을 넣지 마세요 (다른 레이어가 담당).
★ 글래스모피즘: backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px); background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15); border-radius:16px;
★ 기본 카드: background:#fff; border-radius:16px; box-shadow:0 2px 8px rgba(0,0,0,0.06); border:1px solid #E2E8F0;
★ CSS 선택자: .{slide_id}-cards
{common_rules}"""

CONTENT_PROMPT = """슬라이드 텍스트(Layer 2)만 HTML+CSS로 구현하세요. z-index: 20~29.

[분석 — Layer 2 부분만 참고]
{analysis}

[삽입할 텍스트 콘텐츠]
{content_json}

[테마 컬러]
text: {text_color}, primary: {primary}, accent: {accent}

★ 분석의 좌표(% 단위)를 정확히 따르세요.
★ 텍스트만 배치. 배경/카드/아이콘은 만들지 마세요.
★ 제목: font-weight 700-800, 분석의 font_size 사용
★ 본문: line-height 1.6
★ 태그: padding 4px 12px, border-radius 12px, font-size 0.75rem
★ 텍스트가 영역을 넘을 것 같으면 font-size를 줄이세요.
★ 텍스트가 있는 컨테이너는 불투명 배경(alpha>=0.8) 사용하지 마세요 — 배경이 보여야 합니다.
★ CSS 선택자: .{slide_id}-content
{common_rules}"""

ICONS_PROMPT = """슬라이드 아이콘/장식(Layer 3)만 HTML+CSS로 구현하세요. z-index: 30~39.

[분석 — Layer 3 부분만 참고]
{analysis}

[테마 컬러]
primary: {primary}, accent: {accent}

★ 분석의 좌표(% 단위)를 정확히 따르세요.
★ 아이콘은 반드시 FontAwesome (<i class="fas fa-...">) 또는 이모지만 사용.
★ ❌ <img> 금지, ❌ ::before/::after로 아이콘 그리기 금지
★ 원형 배지: border-radius:50%; display:flex; align-items:center; justify-content:center;
★ 액센트 라인: width/height + border-radius 2px + background color
★ CSS 선택자: .{slide_id}-icons
{common_rules}"""


def _extract_html(text: str) -> str:
    text = text.strip()
    if "```html" in text:
        text = text.split("```html", 1)[1].split("```")[0]
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1]
    start = re.search(r"<(?:style|div|!DOCTYPE)", text, re.IGNORECASE)
    if start and start.start() > 0:
        text = text[start.start():]
    return text.strip()


def _call(client: OpenAI, prompt: str, model: str = "gpt-4o") -> str:
    resp = client.chat.completions.create(
        model=model, max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_html(resp.choices[0].message.content)


def generate_from_saved_image(
    client: OpenAI,
    image_path: str,
    slide_id: str,
    slide_type: str,
    content: dict,
    style: dict,
    model: str = "gpt-4o",
) -> dict:
    """저장된 디자인 이미지에서 Layer Agents v2 실행."""

    img_bytes = Path(image_path).read_bytes()
    b64 = base64.b64encode(img_bytes).decode()

    primary = style.get("primary_color", "#3B82F6")
    accent = style.get("accent_color", "#60A5FA")
    bg_color = style.get("background", "#0F172A")
    text_color = style.get("text_color", "#F1F5F9")

    # ── Step 1: 정밀 좌표 분석 ──
    resp = client.chat.completions.create(
        model=model, max_tokens=3000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": PRECISE_ANALYSIS_PROMPT},
            ],
        }],
    )
    analysis = resp.choices[0].message.content

    # ── Step 2: 4 Layer Agents ──
    fmt = {
        "analysis": analysis, "primary": primary, "accent": accent,
        "bg_color": bg_color, "text_color": text_color,
        "slide_id": slide_id, "common_rules": COMMON_RULES,
    }

    bg_html = _call(client, BG_PROMPT.format(**fmt), model)
    cards_html = _call(client, CARDS_PROMPT.format(**fmt), model)

    content_json = json.dumps(content, ensure_ascii=False, indent=2)
    content_html = _call(client, CONTENT_PROMPT.format(**fmt, content_json=content_json), model)

    icons_html = _call(client, ICONS_PROMPT.format(**fmt), model)

    # ── Step 3: 기계적 합침 ──
    assembled = f"""<div class="slide-container {slide_id}" style="width:1280px;height:720px;position:relative;overflow:hidden;font-family:'Noto Sans KR',sans-serif;">
    <div style="position:absolute;inset:0;z-index:0;">{bg_html}</div>
    <div style="position:absolute;inset:0;z-index:10;">{cards_html}</div>
    <div style="position:absolute;inset:0;z-index:20;">{content_html}</div>
    <div style="position:absolute;inset:0;z-index:30;">{icons_html}</div>
</div>"""

    return {
        "analysis": analysis,
        "layers": {"bg": bg_html, "cards": cards_html, "content": content_html, "icons": icons_html},
        "assembled": assembled,
    }
