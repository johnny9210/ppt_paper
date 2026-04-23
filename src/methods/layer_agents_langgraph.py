"""
Method F: Vision-Grounded Layer-Decomposed Multi-Agent with LangGraph

핵심:
1. 모든 layer agent가 원본 디자인 이미지를 직접 봄 (Vision-Grounded)
2. LangGraph StateGraph로 Cards Agent → Content/Icons Agent 좌표 전달
3. 프로덕션 검증 CSS 패턴 주입 (다중 그라디언트, 글로우, 타이포 디테일)
4. Stage 1 (BG + Cards) 병렬, Stage 2 (Content + Icons) 병렬
"""

import base64
import json
import re
import tempfile
from pathlib import Path
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from openai import OpenAI


# ══════════════════════════════════════
# State Definition
# ══════════════════════════════════════

class LayerAgentState(TypedDict):
    """LangGraph state for Layer-Decomposed Multi-Agent pipeline."""

    # Input
    image_b64: str
    slide_id: str
    slide_type: str
    content: dict
    style: dict
    model: str

    # Stage 0: Visual CoT Analysis
    analysis: str
    css_specs: str  # CSS Extraction: 이미지에서 추출한 구체적 CSS 값

    # Stage 1: Parallel (BG + Cards)
    bg_html: str
    cards_html: str
    card_bboxes: list[dict]

    # Stage 2: Parallel (Content + Icons)
    content_html: str
    icons_html: str

    # Output
    assembled: str


# ══════════════════════════════════════
# Prompts
# ══════════════════════════════════════

PRECISE_ANALYSIS_PROMPT = """이 디자인 이미지(1280x720px 슬라이드)를 레이어별로 분석하고, 각 요소의 위치를 % 단위로 정확히 명시해주세요.

**슬라이드 크기: 1280x720px. 모든 위치/크기를 % 단위로 표시.**

4개 레이어로 분해:

**Layer 0 - Background**:
- 배경 유형 (solid/gradient_linear/gradient_radial/pattern)
- 주요 색상값 (정확한 hex/rgba)
- 그라디언트: 방향, color stops (색상 + 위치%), opacity
- 장식 도형: {{shape, left%, top%, width%, height%, color, opacity, blur}}
- 광원/글로우: {{type, left%, top%, radius%, color, opacity}}
- 도트 패턴/텍스처 여부

**Layer 1 - Cards**:
- 각 카드: {{id, left%, top%, width%, height%, style, border_radius_px, bg_color(rgba), border(color+width), shadow(값 그대로)}}

**Layer 2 - Content** (텍스트 영역만):
- 제목: {{left%, top%, width%, font_size_rem, font_weight, color, letter_spacing}}
- 부제: {{left%, top%, width%, font_size_rem, color}}
- 본문/목록: {{left%, top%, width%, height%, items_count, line_height}}
- 태그/라벨: {{left%, top%, text, bg_color, text_color, border_radius_px}}

**Layer 3 - Icons**:
- 각 아이콘: {{id, left%, top%, size_px, shape, bg_color, icon_color, suggested_fa_icon, shadow}}
- 장식: {{type, left%, top%, width%, height%, color, opacity}}

**전체 테마** (정확한 색상값):
- primary_color, accent_color, background_color, text_color, muted_text_color

JSON으로 출력. 색상은 이미지에서 보이는 실제 값으로."""


CSS_EXTRACTION_PROMPT = """이 디자인 이미지에서 **CSS 코드로 직접 사용할 수 있는 구체적 값**을 추출하세요.

추상적 설명이 아니라 **복사해서 바로 쓸 수 있는 CSS 코드 스니펫**으로 출력하세요.

## Layer 0 - Background CSS
```css
/* 메인 배경 그라디언트 */
background: linear-gradient(방향deg, 정확한색1 0%, 정확한색2 50%, 정확한색3 100%);

/* 글로우 1 (위치, 크기, 색상을 이미지에서 읽어서) */
.glow-1 { left:__%; top:__%; width:__px; height:__px;
  background: radial-gradient(circle, rgba(R,G,B,알파) 0%, transparent 70%); }

/* 글로우 2 */
.glow-2 { ... }

/* 도트/그리드 패턴 (있는 경우) */
background-image: radial-gradient(circle, rgba(255,255,255,0.03) 1px, transparent 1px);
background-size: __px __px;

/* 장식 라인 (있는 경우) */
.line { left:__%; top:__%; width:__%; height:__px;
  background: linear-gradient(90deg, transparent, rgba(R,G,B,0.3), transparent); }
```

## Layer 1 - Card CSS
```css
/* 카드 공통 스타일 */
.card {
  background: rgba(R,G,B, 알파);
  backdrop-filter: blur(__px);
  border: __px solid rgba(R,G,B, 알파);
  border-radius: __px;
  box-shadow: 0 __px __px rgba(R,G,B, 알파), inset 0 1px 0 rgba(255,255,255,알파);
}

/* 카드 상단 네온 라인 (있는 경우) */
.card-top-line { height:2px; background: linear-gradient(90deg, 색1, 색2); }

/* 카드 하단 반사 (있는 경우) */
.card-reflection { ... }
```

## Layer 3 - Icon/장식 CSS
```css
/* 아이콘 배지 */
.icon-badge {
  width:__px; height:__px; border-radius:__%|px;
  background: linear-gradient(135deg, rgba(R,G,B,알파), rgba(R,G,B,알파));
  box-shadow: 0 0 __px rgba(R,G,B, 알파);
}

/* 연결 라인/화살표 (있는 경우) */
.connector { height:__px; background: linear-gradient(90deg, 색1, 색2);
  box-shadow: 0 0 __px rgba(R,G,B,알파); }

/* 스텝 라벨 (있는 경우) */
.step-label { font-size:__rem; color:rgba(R,G,B,알파);
  border:1px solid rgba(R,G,B,알파); border-radius:__px; }
```

## 색상 팔레트 (이미지에서 추출한 정확한 값)
- primary: #______
- accent: #______
- bg_dark: #______
- bg_mid: #______
- card_bg: rgba(__, __, __, __)
- card_border: rgba(__, __, __, __)
- glow_color_1: rgba(__, __, __, __)
- glow_color_2: rgba(__, __, __, __)
- text_bright: #______
- text_muted: rgba(__, __, __, __)

★ 모든 색상값은 이미지에서 실제로 보이는 값을 추출하세요. 추측하지 마세요.
★ CSS 코드 블록으로 출력하세요."""


# ── Background Agent ──

BG_PROMPT = """이 디자인 이미지의 **배경(Layer 0)만** HTML+CSS로 구현하세요. z-index: 0~9.

[분석 참고 - Layer 0]
{analysis}

[★★★ 이미지에서 추출한 CSS 값 — 이 값을 그대로 사용하세요]
{css_specs}

[테마 컬러]
primary: {primary}, accent: {accent}, bg: {bg_color}

★★★ 위 CSS 값을 최대한 그대로 복사해서 사용하세요! 새로 만들지 말고 추출된 값을 적용!
★★★ CSS 효과를 최대한 많이 사용하세요 — gradient, shadow, opacity, transform 등.

## 반드시 구현할 CSS 효과 패턴:

### 1. 메인 배경 (최소 2~3겹 그라디언트)
```css
background: linear-gradient(135deg, #0a0e1a 0%, #0f172a 40%, #1a1f3a 100%);
```

### 2. 광원 글로우 (최소 2~3개)
```css
/* 좌상단 글로우 */
.glow-1 {{ position:absolute; left:10%; top:20%; width:300px; height:300px; border-radius:50%;
  background:radial-gradient(circle, rgba({primary},0.2) 0%, transparent 70%); }}
/* 우하단 글로우 */
.glow-2 {{ position:absolute; right:10%; bottom:15%; width:250px; height:250px; border-radius:50%;
  background:radial-gradient(circle, rgba({accent},0.15) 0%, transparent 70%); }}
```

### 3. 도트 패턴
```css
.dots {{ position:absolute; inset:0;
  background-image:radial-gradient(circle, rgba(255,255,255,0.03) 1px, transparent 1px);
  background-size:24px 24px; }}
```

### 4. 장식 라인/도형
```css
/* 수평 네온 라인 */
.line {{ position:absolute; width:80%; height:1px; left:10%;
  background:linear-gradient(90deg, transparent, rgba({accent},0.3), transparent); }}
/* 장식 원 */
.circle {{ position:absolute; border-radius:50%; border:1px solid rgba({accent},0.1);
  width:200px; height:200px; }}
```

### 5. 그리드/메시 패턴
```css
.grid {{ position:absolute; inset:0; opacity:0.03;
  background-image: linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px);
  background-size:40px 40px; }}
```

★ 위 패턴을 조합해서 이미지와 최대한 비슷한 배경을 만드세요.
★ 카드/텍스트/아이콘은 만들지 마세요. 배경+장식만.
★ CSS 선택자: .{slide_id}-bg
{common_rules}"""

# ── Cards Agent ──

CARDS_PROMPT = """이 디자인 이미지의 **카드/컨테이너(Layer 1)만** HTML+CSS로 구현하세요. z-index: 10~19.

[분석 참고 - Layer 1]
{analysis}

[★★★ 이미지에서 추출한 CSS 값 — 카드 부분을 그대로 사용하세요]
{css_specs}

[슬라이드 타입: {slide_type}]
[콘텐츠 구조 힌트: {content_structure}]

[테마 컬러]
primary: {primary}, accent: {accent}, bg: {bg_color}

★★★ 위 CSS 값의 카드 스타일을 그대로 복사해서 사용하세요!
★★★ CSS 효과를 최대한 많이 사용하세요.

## 반드시 적용할 카드 CSS 패턴:

### 1. 글래스모피즘 카드 (다크 테마)
```css
.card {{
  background: rgba(15,23,42,0.6);
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(148,163,184,0.12);
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.05);
}}
```

### 2. 네온 보더 글로우
```css
.card-glow {{
  border: 1px solid rgba({primary},0.3);
  box-shadow: 0 0 15px rgba({primary},0.1), inset 0 0 15px rgba({primary},0.05);
}}
```

### 3. 그라디언트 상단 액센트
```css
.card::before {{
  content:''; position:absolute; top:0; left:10%; right:10%; height:2px;
  background: linear-gradient(90deg, transparent, rgba({accent},0.5), transparent);
  border-radius:2px;
}}
```

### 4. 카드 내부 구분선
```css
.card-divider {{
  width:80%; height:1px; margin:12px auto;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
}}
```

### 5. 카드 하단 반사/글로우
```css
.card-reflection {{
  position:absolute; bottom:-20px; left:10%; right:10%; height:20px;
  background: linear-gradient(180deg, rgba({primary},0.1), transparent);
  border-radius:0 0 16px 16px;
}}
```

★ 위 패턴을 조합해서 카드를 풍부하게 구현하세요.

★ 카드 안에 텍스트/아이콘 넣지 마세요 (다른 레이어 담당).
★ CSS 선택자: .{slide_id}-cards
{common_rules}

★★★ 중요: 이미지에서 보이는 **모든 콘텐츠 영역**을 카드로 감지하세요!
- 컬럼 레이아웃 = 각 컬럼이 하나의 카드 (테두리가 없어도)
- 비교 레이아웃 = 좌/우 각각이 카드
- 목차 = 각 항목이 카드
- 눈에 보이는 카드뿐 아니라 **텍스트가 배치될 구역**도 bbox로 출력
- 콘텐츠 데이터가 {expected_cards}개 항목이므로 최소 {expected_cards}개 bbox 필요
- **cover 슬라이드**: 카드 없이 장식 요소만 구현. bbox는 빈 배열 [] 출력

★★★ HTML 출력 후 반드시 카드 bounding box를 JSON으로 출력:
```json
[
  {{"card_id": "card_1", "left": 5, "top": 15, "width": 28, "height": 75, "padding": 3, "content_area": {{"left": 8, "top": 18, "width": 22, "height": 69}}}}
]
```
★ content_area 계산: left+padding, top+padding, width-padding*2, height-padding*2
★ padding은 2~4% (border-radius/여백 고려)
★ 모든 값은 슬라이드(1280x720) 대비 % 단위"""

# ── Content Agent ──

CONTENT_PROMPT_WITH_BBOX = """이 디자인 이미지의 **텍스트(Layer 2)만** HTML+CSS로 구현하세요. z-index: 20~29.

[분석 참고 - Layer 2]
{analysis}

[슬라이드 타입: {slide_type}]

[카드 Bounding Box — 텍스트를 이 영역 안에 배치]
{card_bboxes_json}

[삽입할 텍스트 콘텐츠]
{content_json}

[테마 컬러]
text: {text_color}, primary: {primary}, accent: {accent}

★★★ 이미지를 직접 보고 텍스트의 시각적 스타일(크기, 굵기, 색상, 간격)을 정확히 재현하세요!

슬라이드 타입별 배치 규칙:
- **cover**: 제목 + 부제목만 배치. bbox 무시. 제목은 left:5%~8%, top:30%~40%, font-size:2.5rem~3.5rem, font-weight:800. 부제목은 제목 아래 font-size:1rem~1.2rem. presenter/date는 하단에 작게. 나머지 텍스트 무시.
- **table_of_contents**: 각 항목을 해당 카드 content_area 안에 배치. 번호 + 제목 + 설명.
- **three_column**: 각 컬럼 데이터를 해당 카드 content_area에 배치. 전체 제목은 카드 위에.
- **comparison**: 좌/우 데이터를 해당 카드 content_area에 배치. 전체 제목은 상단에.
- **기타**: 제목은 상단, 본문은 카드 content_area 안에.

★★★ 핵심: bbox가 N개면, 콘텐츠 항목을 순서대로 bbox에 1:1 매핑!
- card_1 → 첫번째 항목/컬럼, card_2 → 두번째, ...
- 전체 제목(title)은 카드 위 영역에 별도 배치

타이포그래피 CSS 레시피:
- 메인 제목: font-size:2rem~3rem; font-weight:800; letter-spacing:-0.03em; text-shadow:0 4px 20px rgba(0,0,0,0.28); color:#f8fbff;
- 부제목: font-size:1rem~1.2rem; font-weight:400; color:rgba(226,232,240,0.88); letter-spacing:0.01em;
- 카드 제목: font-size:0.95rem~1.1rem; font-weight:700; color:#e2e8f0;
- 카드 본문: font-size:0.8rem~0.88rem; color:rgba(148,163,184,0.9); line-height:1.55;
- 강조 수치/메트릭: font-size:1.2rem; font-weight:700; color:{primary};
- 태그: font-size:0.72rem; font-weight:600; padding:4px 14px; border-radius:12px; background:rgba(59,130,246,0.15); color:{accent}; letter-spacing:0.08em;

★ 텍스트만 배치. 배경/카드/아이콘 만들지 마세요.
★ 텍스트 넘침 시: font-size 축소 → line-height 축소 → 텍스트 말줄임
★ 모든 텍스트 컨테이너에 overflow:hidden 적용
★ 카드 안 텍스트는 content_area의 상단 30%에 제목, 나머지에 본문 — 수직으로 분배
★ CSS 선택자: .{slide_id}-content
{common_rules}"""

# ── Icons Agent ──

ICONS_PROMPT_WITH_BBOX = """이 디자인 이미지의 **아이콘/장식(Layer 3)만** HTML+CSS로 구현하세요. z-index: 30~39.

[분석 참고 - Layer 3]
{analysis}

[카드 Bounding Box — 아이콘을 카드 영역 기준 배치]
{card_bboxes_json}

[테마 컬러]
primary: {primary}, accent: {accent}

★★★ CSS 효과를 최대한 풍부하게 사용하세요! 최소 8개 이상의 CSS 효과 속성을 포함.

## 반드시 적용할 아이콘/장식 CSS 패턴:

### 1. 아이콘 배지 (글로우 + 그라디언트)
```css
.icon-badge {{
  width:56px; height:56px; border-radius:50%;
  display:flex; align-items:center; justify-content:center;
  background: linear-gradient(135deg, rgba({primary},0.25), rgba({accent},0.15));
  border: 1px solid rgba({accent},0.2);
  box-shadow: 0 0 20px rgba({primary},0.2), 0 4px 12px rgba(0,0,0,0.3);
}}
.icon-badge i {{ font-size:1.4rem; color:{accent}; text-shadow: 0 0 8px rgba({accent},0.4); }}
```

### 2. 연결 라인 (타임라인/플로우)
```css
.connector {{
  position:absolute; height:2px;
  background: linear-gradient(90deg, rgba({primary},0.5), rgba({accent},0.3));
  box-shadow: 0 0 8px rgba({accent},0.2);
}}
```

### 3. 글로우 노드 (포인트)
```css
.glow-node {{
  width:10px; height:10px; border-radius:50%;
  background: {accent};
  box-shadow: 0 0 12px rgba({accent},0.5), 0 0 24px rgba({accent},0.2);
}}
```

### 4. 스텝 라벨
```css
.step-label {{
  font-size:0.65rem; font-weight:600; letter-spacing:0.1em; text-transform:uppercase;
  color: rgba({accent},0.7); padding:2px 8px;
  border:1px solid rgba({accent},0.2); border-radius:4px;
  background: rgba({primary},0.1);
}}
```

### 5. 장식 라인/바
```css
.accent-line {{
  height:3px; border-radius:2px;
  background: linear-gradient(90deg, {primary}, {accent}, transparent);
  box-shadow: 0 0 6px rgba({accent},0.3);
}}
.divider {{
  width:80%; height:1px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.08), transparent);
}}
```

★ FontAwesome (<i class="fas fa-...">) 또는 이모지만 사용
★ <img> 금지, ::before/::after 아이콘 금지
★ CSS 선택자: .{slide_id}-icons
{common_rules}"""


COMMON_RULES = """
공통 규칙:
- 컨테이너: width:100%; height:100%; position:absolute; inset:0;
- 모든 자식 요소: position:absolute; 좌표는 % 값 사용
- <style>과 <div>로 구성된 HTML만 출력 (설명 없이)
- JavaScript 금지, <img> 태그 금지
금지 CSS:
- clip-path 금지, box-shadow 3개 이상 중첩 금지
- transparent gradient stop 금지 (배경색의 rgba 0 버전 사용)"""


LAYER_SYSTEM_PROMPT = """당신은 디자인 이미지를 HTML + CSS 코드로 변환하는 전문 개발자입니다.

<output_rules>
★ 최우선 규칙: <style>과 <div>로 구성된 순수 HTML 코드만 출력하세요.
코드 외의 모든 텍스트(설명, 마크다운, 사고 과정)를 절대 출력하지 마세요.
</output_rules>

<styling_rules>
### CSS 작성 원칙
- 모든 커스텀 스타일은 <style> 블록에 작성
- 인라인 style은 position/size 위주로 최소 사용
- 시각 효과는 반드시 <style> 블록에 클래스로 정의

### 슬라이드 크기
- 1280px × 720px, font-family: 'Noto Sans KR', sans-serif

### 디자인 패턴 (이미지에서 판단 어려울 때 참고)
- 카드: background:rgba(15,23,42,0.6); backdrop-filter:blur(16px); border:1px solid rgba(148,163,184,0.15); border-radius:16px; box-shadow:0 4px 24px rgba(0,0,0,0.25);
- 아이콘 배지: 48-56px, 브랜드 색상 배경, border-radius:50%, 중앙 정렬
- 하단 바: height:4-8px, 전체 너비, 브랜드 색상 그라디언트
- 액센트 라인: width:48px, height:3px, 브랜드 색상, border-radius:2px
- FontAwesome 아이콘: <i class="fas fa-icon-name"></i>
- 네온 글로우: box-shadow: 0 0 20px rgba(color, 0.3)
- 글래스모피즘: backdrop-filter:blur(16px); background:rgba(15,23,42,0.5); border:1px solid rgba(255,255,255,0.1);

### ★ 시각 효과 최대화 원칙
디자인 이미지의 시각적 스타일을 최우선으로 따르세요.
이미지에서 보이는 그라디언트, 글로우, 그림자, 테두리, 패턴, 장식을 CSS로 풍부하게 재현하세요.
CSS 효과(gradient, box-shadow, opacity, backdrop-filter, transform, border-radius)를 적극 활용하세요.
</styling_rules>

<constraints>
- <style> + <div> 형식만 출력
- JavaScript 사용 금지
- <img> 태그 사용 금지
- clip-path 사용 금지
- filter:blur() 사용 금지
- box-shadow 3개 이상 중첩 금지
- ::before/::after로 아이콘 그리기 금지 — FontAwesome 또는 이모지만 사용
</constraints>"""


# ══════════════════════════════════════
# Utility Functions
# ══════════════════════════════════════

def _extract_html(text: str) -> str:
    """LLM 출력에서 HTML 부분만 추출."""
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


def _extract_bbox_json(text: str) -> list[dict]:
    """Cards Agent 출력에서 bounding box JSON 추출."""
    json_match = re.search(r'```json\s*\n?(.*?)```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass
    array_match = re.search(r'\[\s*\{.*?"card_id".*?\}\s*\]', text, re.DOTALL)
    if array_match:
        try:
            return json.loads(array_match.group(0))
        except json.JSONDecodeError:
            pass
    return []


def _get_openai_client() -> OpenAI:
    """OpenAI client singleton."""
    if not hasattr(_get_openai_client, "_client"):
        _get_openai_client._client = OpenAI()
    return _get_openai_client._client


def _vision_call(client: OpenAI, image_b64: str, prompt: str, model: str = "gpt-4o", max_tokens: int = 12000, system_prompt: str = None) -> str:
    """Vision LLM 호출 — 이미지 + 텍스트 프롬프트 + 선택적 system prompt."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            {"type": "text", "text": prompt},
        ],
    })
    resp = client.chat.completions.create(
        model=model, max_tokens=max_tokens, messages=messages,
    )
    return resp.choices[0].message.content


def _filter_content(content: dict) -> dict:
    """슬라이드에 렌더링하지 않을 필드 제거."""
    skip = {"speaker_script", "infographic_script"}
    return {k: v for k, v in content.items() if k not in skip}


def _get_content_structure(content: dict, slide_type: str) -> tuple[str, int]:
    """콘텐츠 구조 힌트 + 예상 카드 수 계산."""
    filtered = _filter_content(content)

    if slide_type == "cover":
        return "커버: title + subtitle만 표시 (카드 불필요, 배경 위에 직접 배치)", 0

    if "columns" in filtered:
        n = len(filtered["columns"])
        return f"컬럼 {n}개: 각 컬럼에 emoji, title, description, metric", n
    if "items" in filtered:
        n = len(filtered["items"])
        return f"항목 {n}개: 각 항목에 number, title, description", n
    if "left" in filtered and "right" in filtered:
        return "좌우 비교: left(label+items), right(label+items)", 2

    return f"일반: keys={list(filtered.keys())}", 1


# ══════════════════════════════════════
# LangGraph Nodes
# ══════════════════════════════════════

def visual_cot_analyzer(state: LayerAgentState) -> dict:
    """Stage 0a: Vision LLM으로 이미지를 4개 레이어로 정밀 분석."""
    client = _get_openai_client()
    model = state.get("model", "gpt-4o")
    raw = _vision_call(client, state["image_b64"], PRECISE_ANALYSIS_PROMPT, model, max_tokens=4000)
    return {"analysis": raw}


def css_extractor(state: LayerAgentState) -> dict:
    """Stage 0b: 이미지에서 구체적 CSS 값을 추출. 각 agent가 '상상'이 아닌 '복사'로 CSS를 적용."""
    client = _get_openai_client()
    model = state.get("model", "gpt-4o")
    raw = _vision_call(client, state["image_b64"], CSS_EXTRACTION_PROMPT, model, max_tokens=6000)
    return {"css_specs": raw}


def background_agent(state: LayerAgentState) -> dict:
    """Stage 1a: Vision-Grounded 배경 생성 + CSS specs 참조."""
    client = _get_openai_client()
    model = state.get("model", "gpt-4o")
    style = state.get("style", {})

    prompt = BG_PROMPT.format(
        analysis=state["analysis"],
        css_specs=state.get("css_specs", ""),
        primary=style.get("primary_color", "#3B82F6"),
        accent=style.get("accent_color", "#60A5FA"),
        bg_color=style.get("background", "#0F172A"),
        slide_id=state["slide_id"],
        common_rules=COMMON_RULES,
    )

    raw = _vision_call(client, state["image_b64"], prompt, model, max_tokens=12000, system_prompt=LAYER_SYSTEM_PROMPT)
    return {"bg_html": _extract_html(raw)}


def cards_agent(state: LayerAgentState) -> dict:
    """Stage 1b: Vision-Grounded 카드 생성 + bbox JSON."""
    client = _get_openai_client()
    model = state.get("model", "gpt-4o")
    style = state.get("style", {})
    content = _filter_content(state.get("content", {}))
    slide_type = state.get("slide_type", "")

    content_structure, expected_cards = _get_content_structure(content, slide_type)

    prompt = CARDS_PROMPT.format(
        analysis=state["analysis"],
        css_specs=state.get("css_specs", ""),
        slide_type=slide_type,
        content_structure=content_structure,
        expected_cards=expected_cards,
        primary=style.get("primary_color", "#3B82F6"),
        accent=style.get("accent_color", "#60A5FA"),
        bg_color=style.get("background", "#0F172A"),
        slide_id=state["slide_id"],
        common_rules=COMMON_RULES,
    )

    raw = _vision_call(client, state["image_b64"], prompt, model, max_tokens=12000, system_prompt=LAYER_SYSTEM_PROMPT)
    return {
        "cards_html": _extract_html(raw),
        "card_bboxes": _extract_bbox_json(raw),
    }


def content_agent(state: LayerAgentState) -> dict:
    """Stage 2a: Text-only 텍스트 배치 — bbox 좌표만으로 정확히 배치.

    이미지를 주지 않음: VLM이 이미지를 보면 bbox 좌표 대신 이미지 기반으로
    배치하려 해서 좌표와 충돌함. bbox가 유일한 위치 정보 소스.
    """
    client = _get_openai_client()
    model = state.get("model", "gpt-4o")
    style = state.get("style", {})
    content = _filter_content(state.get("content", {}))
    slide_type = state.get("slide_type", "")

    card_bboxes_json = json.dumps(state.get("card_bboxes", []), ensure_ascii=False, indent=2)
    content_json = json.dumps(content, ensure_ascii=False, indent=2)

    prompt = CONTENT_PROMPT_WITH_BBOX.format(
        analysis=state["analysis"],
        slide_type=slide_type,
        card_bboxes_json=card_bboxes_json,
        content_json=content_json,
        text_color=style.get("text_color", "#F1F5F9"),
        primary=style.get("primary_color", "#3B82F6"),
        accent=style.get("accent_color", "#60A5FA"),
        slide_id=state["slide_id"],
        common_rules=COMMON_RULES,
    )

    resp = client.chat.completions.create(
        model=model, max_tokens=12000,
        messages=[{"role": "user", "content": prompt}],
    )
    return {"content_html": _extract_html(resp.choices[0].message.content)}


def icons_agent(state: LayerAgentState) -> dict:
    """Stage 2b: Text-only 아이콘 배치 — bbox 좌표만으로 배치.

    Content Agent와 같은 이유로 이미지 없이 bbox + 분석 텍스트만 사용.
    """
    client = _get_openai_client()
    model = state.get("model", "gpt-4o")
    style = state.get("style", {})

    card_bboxes_json = json.dumps(state.get("card_bboxes", []), ensure_ascii=False, indent=2)

    prompt = ICONS_PROMPT_WITH_BBOX.format(
        analysis=state["analysis"],
        card_bboxes_json=card_bboxes_json,
        primary=style.get("primary_color", "#3B82F6"),
        accent=style.get("accent_color", "#60A5FA"),
        slide_id=state["slide_id"],
        common_rules=COMMON_RULES,
    )

    resp = client.chat.completions.create(
        model=model, max_tokens=12000,
        messages=[{"role": "user", "content": prompt}],
    )
    return {"icons_html": _extract_html(resp.choices[0].message.content)}


def assembler(state: LayerAgentState) -> dict:
    """4개 레이어를 기계적으로 합침."""
    slide_id = state["slide_id"]
    assembled = f"""<div class="slide-container {slide_id}" style="width:1280px;height:720px;position:relative;overflow:hidden;font-family:'Noto Sans KR',sans-serif;">
    <div style="position:absolute;inset:0;z-index:0;">{state.get('bg_html', '')}</div>
    <div style="position:absolute;inset:0;z-index:10;">{state.get('cards_html', '')}</div>
    <div style="position:absolute;inset:0;z-index:20;">{state.get('content_html', '')}</div>
    <div style="position:absolute;inset:0;z-index:30;">{state.get('icons_html', '')}</div>
</div>"""
    return {"assembled": assembled}


CSS_ENHANCE_PROMPT = """당신은 CSS 시각 효과 전문가입니다.

[원본 디자인 이미지] (이미지)

[현재 HTML 코드]
```html
{assembled_html}
```

원본 디자인 이미지를 보고, 현재 HTML에 **부족한 CSS 시각 효과를 추가**하세요.

★★★ 추가할 CSS 효과:
1. **배경 그라디언트**: 원본의 그라디언트 방향, 색상, 정지점을 정확히 재현
   - 다중 배경: background: linear-gradient(...), radial-gradient(circle at X% Y%, rgba(...) 0%, transparent 50%);
   - 글로우: 별도 div에 radial-gradient + opacity
2. **카드 효과**: 원본의 카드 스타일을 강화
   - 글래스모피즘: backdrop-filter:blur(16px); background:rgba(15,23,42,0.6); border:1px solid rgba(148,163,184,0.12);
   - 그림자: box-shadow: 0 4px 24px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.05);
   - 보더 글로우: border:1px solid rgba(59,130,246,0.3);
3. **장식 효과**: 원본에 보이는 장식 요소
   - 네온 라인: background:linear-gradient(90deg, primary, accent); height:2px;
   - 도트 패턴: background-image:radial-gradient(circle, rgba(255,255,255,0.05) 1px, transparent 1px); background-size:20px 20px;
   - 글로우 노드: border-radius:50%; box-shadow:0 0 12px rgba(accent,0.4);
4. **색상 풍부성**: 원본의 미묘한 색조 차이를 재현
   - text-shadow: 0 2px 10px rgba(0,0,0,0.3); (제목)
   - letter-spacing: -0.02em; (제목)
   - 뮤트 텍스트: color:rgba(148,163,184,0.7);

★★★ 절대 하지 말 것:
- 구조 변경 (div 추가/삭제, position, z-index 변경 금지)
- 텍스트 내용 변경
- 레이아웃 변경 (width, height, left, top 변경 금지)
- JavaScript 추가

★ CSS 속성만 추가/수정하여 시각 품질을 높이세요.
★ 수정된 전체 HTML을 출력하세요.
★ <style>과 <div>로 구성된 HTML만 출력 (설명 없이)"""


def css_agent(state: LayerAgentState) -> dict:
    """Stage 3: 원본 디자인 이미지를 보면서 CSS 시각 효과를 보강.

    구조(position, z-index, layout)는 건드리지 않고 CSS 효과만 추가.
    """
    client = _get_openai_client()
    model = state.get("model", "gpt-4o")

    prompt = CSS_ENHANCE_PROMPT.format(
        assembled_html=state.get("assembled", ""),
    )

    raw = _vision_call(client, state["image_b64"], prompt, model, max_tokens=10000)
    enhanced = _extract_html(raw)

    if not enhanced or len(enhanced) < 100:
        return {"css_enhanced": state.get("assembled", "")}

    return {"css_enhanced": enhanced}


# ══════════════════════════════════════
# Pipeline Builder
# ══════════════════════════════════════

def build_layer_pipeline() -> StateGraph:
    """Build the Vision-Grounded Layer-Decomposed Multi-Agent pipeline.

    Flow:
      visual_cot_analyzer (이미지 → 좌표 분석)
        ├→ background_agent  (Vision → BG HTML)                    Stage 1 병렬
        └→ cards_agent       (Vision → Cards HTML + bbox)           Stage 1 병렬
             ├→ content_agent  (Text-only + bbox → Content HTML)    Stage 2 병렬
             └→ icons_agent    (Text-only + bbox → Icons HTML)      Stage 2 병렬
                  └→ assembler → css_agent → END
    """
    graph = StateGraph(LayerAgentState)

    graph.add_node("visual_cot_analyzer", visual_cot_analyzer)
    graph.add_node("css_extractor", css_extractor)
    graph.add_node("background_agent", background_agent)
    graph.add_node("cards_agent", cards_agent)
    graph.add_node("content_agent", content_agent)
    graph.add_node("icons_agent", icons_agent)
    graph.add_node("assembler", assembler)

    # Stage 0: Analyzer + CSS Extractor 병렬
    graph.add_edge(START, "visual_cot_analyzer")
    graph.add_edge(START, "css_extractor")

    # Stage 1: 둘 다 완료 후 BG + Cards 병렬
    graph.add_edge("visual_cot_analyzer", "background_agent")
    graph.add_edge("visual_cot_analyzer", "cards_agent")
    graph.add_edge("css_extractor", "background_agent")
    graph.add_edge("css_extractor", "cards_agent")

    graph.add_edge("background_agent", "assembler")
    graph.add_edge("cards_agent", "content_agent")
    graph.add_edge("cards_agent", "icons_agent")

    graph.add_edge("content_agent", "assembler")
    graph.add_edge("icons_agent", "assembler")
    graph.add_edge("assembler", END)

    return graph.compile()


_pipeline = None

def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_layer_pipeline()
    return _pipeline


# ══════════════════════════════════════
# Public API
# ══════════════════════════════════════

def generate_from_saved_image(
    image_path: str,
    slide_id: str,
    slide_type: str,
    content: dict,
    style: dict,
    model: str = "gpt-4o",
) -> dict:
    """저장된 디자인 이미지에서 Vision-Grounded LangGraph Layer Agents 실행."""

    img_bytes = Path(image_path).read_bytes()
    b64 = base64.b64encode(img_bytes).decode()

    pipeline = get_pipeline()

    result = pipeline.invoke({
        "image_b64": b64,
        "slide_id": slide_id,
        "slide_type": slide_type,
        "content": content,
        "style": style,
        "model": model,
    })

    return {
        "analysis": result.get("analysis", ""),
        "card_bboxes": result.get("card_bboxes", []),
        "layers": {
            "bg": result.get("bg_html", ""),
            "cards": result.get("cards_html", ""),
            "content": result.get("content_html", ""),
            "icons": result.get("icons_html", ""),
        },
        "assembled": result.get("assembled", ""),
    }
