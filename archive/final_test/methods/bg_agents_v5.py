"""BG 3-split: Base BG + Atmosphere + Decoration 각각 전담 agent.

기존 Background Agent(v1)는 배경+글로우+장식+패턴을 다 했음 → 모두 어정쩡.
이제 3개로 분리:
- Base BG Agent: flat 배경+gradient만
- Atmosphere Agent: radial glow, vignette, ambient
- Decoration Agent: 기하 도형 (삼각형, 원, 육각형 등)

모두 DesignSpec + 전체 이미지 + Analyzer 결과를 본다.
"""
from __future__ import annotations

import json

from .design_director import spec_to_prompt_hint, DesignSpec
from src.methods import crop_layer_agent as _la


# ════════════════════════════════════════════════════════════
# Base BG Agent — 배경색/gradient만
# ════════════════════════════════════════════════════════════

BASE_BG_PROMPT = """이 슬라이드 이미지의 **가장 바깥 배경 레이어만** HTML+CSS로 구현하라.

{spec_hint}

범위:
- ✓ 베이스 배경색, 그라디언트 (linear/radial)
- ✗ 글로우·앰비언트 라이트 (Atmosphere Agent 담당)
- ✗ 기하 도형 (Decoration Agent 담당)
- ✗ 카드/hero (별도 agent 담당)

★ 컨테이너: position:absolute; inset:0; z-index:0;
★ CSS 선택자: .{slide_id}-bg-base
★ palette.bg_primary + bg_secondary 사용. DesignSpec과 일치.
★ <style>과 <div>로만"""


def base_bg_agent(state) -> dict:
    model = state.get("model", "gpt-4o")
    spec: DesignSpec = state.get("design_spec", {})
    sid = state["slide_id"]
    raw = _la._vision_call(
        state["image_b64"],
        BASE_BG_PROMPT.format(spec_hint=spec_to_prompt_hint(spec), slide_id=sid),
        model, max_tokens=2000,
    )
    return {"bg_base_html": _la._extract_html(raw)}


# ════════════════════════════════════════════════════════════
# Atmosphere Agent — radial glow, ambient, vignette
# ════════════════════════════════════════════════════════════

ATMOSPHERE_PROMPT = """이 슬라이드 이미지의 **앰비언트 빛 레이어**만 HTML+CSS로 구현하라.

{spec_hint}

범위:
- ✓ radial-gradient 큰 빛 (origin: DesignSpec.atmosphere.glow_origin)
- ✓ 소프트 vignette
- ✓ 배경 위에 *겹쳐지는* 부드러운 색 번짐
- ✗ 기하 도형 (삼각형 등) 만들지 말 것
- ✗ 선명한 도형/라인 만들지 말 것

★ 모든 요소는 `filter: blur(N)` 또는 radial-gradient 로 부드럽게.
★ 투명도(alpha) 0.1~0.25 권장. 배경을 완전히 가리면 안 됨.
★ DesignSpec.atmosphere.has_radial_glow 가 false 면 빈 결과 OK.
★ 컨테이너: position:absolute; inset:0; z-index:1; pointer-events:none;
★ CSS 선택자: .{slide_id}-atmos
★ <style>과 <div>로만"""


def atmosphere_agent(state) -> dict:
    model = state.get("model", "gpt-4o")
    spec: DesignSpec = state.get("design_spec", {})
    atmos = spec.get("atmosphere", {})
    if not atmos.get("has_radial_glow", False):
        return {"atmosphere_html": ""}

    sid = state["slide_id"]
    raw = _la._vision_call(
        state["image_b64"],
        ATMOSPHERE_PROMPT.format(spec_hint=spec_to_prompt_hint(spec), slide_id=sid),
        model, max_tokens=1500,
    )
    return {"atmosphere_html": _la._extract_html(raw)}


# ════════════════════════════════════════════════════════════
# Decoration Agent — 기하 도형 (삼각형/원/육각형)
# ════════════════════════════════════════════════════════════

DECORATION_PROMPT = """이 슬라이드 이미지의 **기하 장식 도형들**만 HTML+CSS로 구현하라.

{spec_hint}

**Analyzer가 감지한 장식 목록**:
{decorations_json}

범위:
- ✓ 삼각형, 원, 육각형, 다이아몬드 등 *경계선이 있는* 장식 도형
- ✓ 각 도형의 이미지상 실제 위치 (Analyzer 좌표 존중)
- ✓ DesignSpec.decorative_motif에 맞는 스타일 (stroke-only outline / filled / semi-transparent 등)
- ✗ 배경색·그라디언트·글로우 만들지 말 것 (다른 agent 담당)
- ✗ 카드·텍스트 만들지 말 것

★ 도형 간 일관성 — 같은 stroke width, 같은 색, 같은 불투명도.
  DesignSpec.palette.frame_color 또는 accent_soft 사용.
★ DesignSpec.decorative_motif.style 이 "minimal" 이면 빈 결과 OK (억지로 만들지 말 것).
★ 각 도형은 div + CSS clip-path 또는 border tricks 로. SVG도 OK.
★ 컨테이너: position:absolute; inset:0; z-index:2; pointer-events:none;
★ CSS 선택자: .{slide_id}-decor
★ <style>과 <div>로만"""


def decoration_agent(state) -> dict:
    model = state.get("model", "gpt-4o")
    spec: DesignSpec = state.get("design_spec", {})
    analysis = state.get("analysis", {})
    decor_meta = analysis.get("decorations", [])
    motif_style = spec.get("decorative_motif", {}).get("style", "minimal")

    # motif가 minimal이거나 장식 감지 안 되면 skip
    if motif_style == "minimal" and not decor_meta:
        return {"decoration_html": ""}

    sid = state["slide_id"]
    raw = _la._vision_call(
        state["image_b64"],
        DECORATION_PROMPT.format(
            spec_hint=spec_to_prompt_hint(spec),
            slide_id=sid,
            decorations_json=json.dumps(decor_meta, ensure_ascii=False, indent=2)[:2000],
        ),
        model, max_tokens=2500,
    )
    return {"decoration_html": _la._extract_html(raw)}
