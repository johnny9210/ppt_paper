"""
Method E: Layer-Decomposed Multi-Agent Generation

Visual CoT → 4개 레이어 agent가 각각 담당 영역만 생성 → Assembler가 합침.

Agent 1 (Background):  배경, 그라디언트, 패턴, 장식 도형  (z: 0-9)
Agent 2 (Cards):       카드, 컨테이너, 프레임              (z: 10-19)
Agent 3 (Content):     텍스트, 제목, 본문, 목록             (z: 20-29)
Agent 4 (Icons):       아이콘 배지, 이모지, 장식 요소        (z: 30-39)
"""

import json
import re
from openai import OpenAI


# ══════════════════════════════════════
# Step 1: Visual CoT — 전체 구조 분석
# ══════════════════════════════════════

ANALYSIS_PROMPT = """이 디자인 이미지를 레이어별로 분석해주세요.

4개 레이어로 분해:

**Layer 0 - Background (배경)**:
- 배경 색상/그라디언트 (유형, 방향, 색상)
- 배경 패턴 (도트, 라인 등)
- 대형 장식 도형 (원, 사각형 등 배경 장식)
- 분위기 광원 (ambient glow)

**Layer 1 - Cards (카드/컨테이너)**:
- 카드 수, 위치 (좌상단 기준 %), 크기 (%)
- 카드 스타일 (glassmorphism / solid / gradient border)
- 그림자 깊이, 모서리 반경, 테두리, 투명도

**Layer 2 - Content (텍스트)**:
- 제목: 위치, 크기, 굵기
- 부제목/설명: 위치, 크기
- 본문/목록: 위치, 항목 수
- 태그/라벨: 위치, 스타일
- (텍스트 내용은 분석하지 마세요 — 위치와 스타일만)

**Layer 3 - Icons (아이콘/장식)**:
- 아이콘 배지: 수, 위치, 크기, 색상, 형태 (원형/사각형)
- 적합한 FontAwesome 아이콘 이름 추천
- 작은 장식 요소 (액센트 라인, 구분선 등)

전체에 적용될 색상:
- primary_color, accent_color, background_color, text_color

JSON으로 출력해주세요."""


# ══════════════════════════════════════
# 각 레이어 Agent 프롬프트
# ══════════════════════════════════════

BG_AGENT_PROMPT = """당신은 슬라이드 배경 전문 디자이너입니다.

아래 분석의 "Layer 0 - Background" 부분만 HTML+CSS로 구현하세요.

[분석]
{analysis}

[테마 컬러]
primary: {primary}, accent: {accent}, background: {background}, text: {text_color}

규칙:
- 이 div 안의 모든 요소는 position: absolute, z-index 0~9 사용
- 배경 그라디언트, 패턴, 장식 도형, 광원 효과만 구현
- 카드, 텍스트, 아이콘은 만들지 마세요
- 컨테이너: width:100%, height:100%, position:absolute, inset:0
- CSS 선택자는 .{slide_id}-bg 로 스코핑
- <style>과 <div> HTML만 출력, 설명 없이
- ❌ clip-path 금지, ❌ filter:blur() 금지, ❌ transparent gradient stop 금지"""

CARDS_AGENT_PROMPT = """당신은 슬라이드 카드/컨테이너 전문 디자이너입니다.

아래 분석의 "Layer 1 - Cards" 부분만 HTML+CSS로 구현하세요.

[분석]
{analysis}

[테마 컬러]
primary: {primary}, accent: {accent}, background: {background}, text: {text_color}

규칙:
- 이 div 안의 모든 요소는 position: absolute, z-index 10~19 사용
- 카드 컨테이너 구조만 구현 (텍스트, 아이콘은 넣지 마세요)
- 카드 안은 비워두세요 — 텍스트는 Layer 2 Agent가 담당
- 글래스모피즘: backdrop-filter: blur(12px); background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); border-radius: 16px;
- 기본 카드: background:#fff; border-radius:16px; box-shadow: 0 2px 8px rgba(0,0,0,0.06);
- 컨테이너: width:100%, height:100%, position:absolute, inset:0
- CSS 선택자는 .{slide_id}-cards 로 스코핑
- <style>과 <div> HTML만 출력, 설명 없이
- ❌ 글래스모피즘 오버레이 (alpha<0.1) 금지 — alpha>=0.08 사용"""

CONTENT_AGENT_PROMPT = """당신은 슬라이드 텍스트 배치 전문가입니다.

아래 분석의 "Layer 2 - Content" 위치 정보와 콘텐츠 데이터를 사용하여 텍스트를 배치하세요.

[분석]
{analysis}

[삽입할 콘텐츠]
{content_json}

[테마 컬러]
primary: {primary}, accent: {accent}, text: {text_color}

규칙:
- 이 div 안의 모든 요소는 position: absolute, z-index 20~29 사용
- 텍스트만 배치 (배경, 카드, 아이콘은 만들지 마세요)
- 분석의 위치/크기 정보에 맞게 텍스트를 배치
- 제목: font-size 2rem~2.5rem, font-weight 700-800
- 부제목: font-size 1rem~1.2rem, font-weight 400-500
- 본문: font-size 0.85rem~0.95rem, line-height 1.6
- 태그: font-size 0.75rem, padding 4px 12px, border-radius 12px, 배경색
- 텍스트가 넘치면 font-size를 줄이세요
- 컨테이너: width:100%, height:100%, position:absolute, inset:0
- CSS 선택자는 .{slide_id}-content 로 스코핑
- <style>과 <div> HTML만 출력, 설명 없이"""

ICONS_AGENT_PROMPT = """당신은 슬라이드 아이콘/장식 전문가입니다.

아래 분석의 "Layer 3 - Icons" 부분만 HTML+CSS로 구현하세요.

[분석]
{analysis}

[테마 컬러]
primary: {primary}, accent: {accent}

규칙:
- 이 div 안의 모든 요소는 position: absolute, z-index 30~39 사용
- 아이콘은 반드시 FontAwesome (<i class="fas fa-...">) 또는 이모지 사용
- ❌ <img> 태그 금지
- ❌ ::before/::after로 아이콘 그리기 금지
- 원형 배지: width/height 48px, border-radius 50%, display:flex, align-items:center, justify-content:center
- 액센트 라인: width 48px, height 4px, border-radius 2px
- 컨테이너: width:100%, height:100%, position:absolute, inset:0
- CSS 선택자는 .{slide_id}-icons 로 스코핑
- <style>과 <div> HTML만 출력, 설명 없이"""


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


def _call_agent(client: OpenAI, prompt: str, model: str = "gpt-4o") -> str:
    resp = client.chat.completions.create(
        model=model, max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_html(resp.choices[0].message.content)


def generate(
    client: OpenAI,
    image_b64: str,
    slide_id: str,
    slide_type: str,
    content: dict,
    style: dict,
    model: str = "gpt-4o",
) -> dict:
    """Layer-Decomposed Multi-Agent Generation."""

    primary = style.get("primary_color", "#3B82F6")
    accent = style.get("accent_color", "#60A5FA")
    background = style.get("background", "#0F172A")
    text_color = style.get("text_color", "#F1F5F9")

    # ── Step 1: Visual CoT 분석 ──
    resp = client.chat.completions.create(
        model=model, max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                {"type": "text", "text": ANALYSIS_PROMPT},
            ],
        }],
    )
    analysis = resp.choices[0].message.content

    fmt = {"analysis": analysis, "primary": primary, "accent": accent,
           "background": background, "text_color": text_color, "slide_id": slide_id}

    # ── Step 2: 4 Layer Agents (각각 독립 생성) ──
    bg_html = _call_agent(client, BG_AGENT_PROMPT.format(**fmt), model)
    cards_html = _call_agent(client, CARDS_AGENT_PROMPT.format(**fmt), model)

    content_json = json.dumps(content, ensure_ascii=False, indent=2)
    content_prompt = CONTENT_AGENT_PROMPT.format(**fmt, content_json=content_json)
    content_html = _call_agent(client, content_prompt, model)

    icons_html = _call_agent(client, ICONS_AGENT_PROMPT.format(**fmt), model)

    # ── Step 3: Assembler — 기계적 합침 ──
    assembled = f"""<style>
.{slide_id} {{
    width: 1280px;
    height: 720px;
    position: relative;
    overflow: hidden;
    font-family: 'Noto Sans KR', sans-serif;
}}
</style>
<div class="slide-container {slide_id}" style="width:1280px;height:720px;position:relative;overflow:hidden;font-family:'Noto Sans KR',sans-serif;">
    <!-- Layer 0: Background (z: 0-9) -->
    <div style="position:absolute;inset:0;z-index:0;">
        {bg_html}
    </div>
    <!-- Layer 1: Cards (z: 10-19) -->
    <div style="position:absolute;inset:0;z-index:10;">
        {cards_html}
    </div>
    <!-- Layer 2: Content (z: 20-29) -->
    <div style="position:absolute;inset:0;z-index:20;">
        {content_html}
    </div>
    <!-- Layer 3: Icons (z: 30-39) -->
    <div style="position:absolute;inset:0;z-index:30;">
        {icons_html}
    </div>
</div>"""

    return {
        "analysis": analysis,
        "bg_html": bg_html,
        "cards_html": cards_html,
        "content_html": content_html,
        "icons_html": icons_html,
        "assembled_html": assembled,
    }
