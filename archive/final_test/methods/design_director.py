"""Design Director Agent — 전체 이미지 분석 후 공유 DesignSpec 생성.

다운스트림의 Base BG / Atmosphere / Decoration / Hero / Card Agent 모두가 이 spec을 참조한다.

DesignSpec이란 실제로 "디자인 언어"다:
- typography (serif vs sans, weight system, letter-spacing 성향)
- palette (bg, accent, frame, text 색 hex — CV에서 검증됨)
- frame_system (hero/card 프레임 스타일)
- decorative_motif (어떤 기하 도형이 어떤 스타일로?)
- atmosphere (ambient glow, vignette 유무)

이 agent는 판단만 한다. HTML을 만들지 않는다.
"""
from __future__ import annotations

import json
import re
from typing import TypedDict

from .cv_extractors import visual_facts, format_facts_as_prompt
from src.methods import crop_layer_agent as _la


class DesignSpec(TypedDict, total=False):
    typography: dict       # {hero_family, body_family, hero_weight, style_hint}
    palette: dict          # {bg_primary, bg_secondary, accent, frame_color, text_bright, text_muted}
    frame_system: dict     # {hero_frame, card_frame, bottom_accent_bar}
    decorative_motif: str  # "geometric_triangles_circles" | "neon_grid" | "minimal" | ...
    atmosphere: dict       # {has_radial_glow, glow_origin, glow_color}
    aesthetic_label: str   # "luxury-dark-gold" | "corporate-blue" | ...


DESIGN_DIRECTOR_PROMPT = """너는 디자인 디렉터다. 이 슬라이드 이미지를 분석해서 **디자인 언어 spec**을 결정하라.
후속 agent(배경/카드/hero/장식)가 이 spec을 참조해서 일관되게 구현한다.

{facts_block}

위 CV 측정값과 이미지를 모두 활용하라.

다음 **DesignSpec JSON**을 출력하라:
```json
{
  "aesthetic_label": "짧은 라벨 (예: 'luxury-dark-gold', 'neon-cyber', 'flat-corporate')",

  "typography": {
    "hero_family": "serif | sans-serif | display | slab",
    "hero_weight": 400-900 정수,
    "hero_style_hint": "uppercase | italic | condensed | normal 중 골라 자연어 한 줄",
    "body_family": "sans-serif | serif (본문용)",
    "body_weight": 400-700 정수,
    "letter_spacing_hint": "tight | normal | wide"
  },

  "palette": {
    "bg_primary": "#hex",
    "bg_secondary": "#hex",
    "accent": "#hex",
    "accent_soft": "#hex rgba 낮은 채도",
    "frame_color": "rgba(...) — hero/card 프레임에 쓸 색",
    "text_bright": "#hex",
    "text_muted": "rgba(...)"
  },

  "frame_system": {
    "hero_frame": "자연어 1-2줄. 예: '1px solid gold hairline + inset 60px gold glow'",
    "card_frame": "자연어 1-2줄. 예: '1px rgba white border + 2px accent bottom bar'",
    "bottom_accent_bar": true | false
  },

  "decorative_motif": {
    "style": "geometric-triangles-circles-hexagons | ambient-glow-only | minimal | neon-lines 중 하나",
    "density": "sparse | moderate | dense",
    "detected_shapes": ["triangle", "circle", "hexagon"] (실제로 이미지에서 보이는 것들)
  },

  "atmosphere": {
    "has_radial_glow": true | false,
    "glow_origin": "top-left | top-center | top-right | center | none",
    "glow_color": "#hex rgba 형태",
    "background_depth": "flat | subtle-gradient | multi-layer"
  }
}
```

★ 값을 추측하지 말 것. CV facts + 이미지 직접 관찰로만.
★ JSON만 출력. 설명 없이."""


def run_design_director(image_b64: str, analysis: dict, model: str = "gpt-4o") -> DesignSpec:
    """전체 이미지에 대한 DesignSpec 생성."""
    facts = visual_facts(image_b64)
    facts_block = format_facts_as_prompt(facts)

    raw = _la._vision_call(image_b64, DESIGN_DIRECTOR_PROMPT.replace("{facts_block}", facts_block), model, max_tokens=2000)

    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return _fallback_spec(facts)
    try:
        spec = json.loads(m.group(0))
    except Exception:
        return _fallback_spec(facts)
    return spec  # type: ignore


def _fallback_spec(facts: dict) -> DesignSpec:
    palette = facts.get("palette", [])
    bg_prim = palette[0]["hex"] if palette else "#0A1530"
    bg_sec = palette[1]["hex"] if len(palette) > 1 else "#1C2D49"
    accent = next((p["hex"] for p in palette if p.get("role_guess") == "accent"), "#D4AF37")
    return {  # type: ignore
        "aesthetic_label": "unknown",
        "typography": {"hero_family": "sans-serif", "hero_weight": 800, "hero_style_hint": "normal",
                       "body_family": "sans-serif", "body_weight": 500, "letter_spacing_hint": "normal"},
        "palette": {"bg_primary": bg_prim, "bg_secondary": bg_sec, "accent": accent,
                    "accent_soft": accent + "55", "frame_color": "rgba(255,255,255,0.15)",
                    "text_bright": "#F5F5F0", "text_muted": "rgba(200,200,200,0.7)"},
        "frame_system": {"hero_frame": "subtle glass frame", "card_frame": "1px rgba white border",
                         "bottom_accent_bar": False},
        "decorative_motif": {"style": "minimal", "density": "sparse", "detected_shapes": []},
        "atmosphere": {"has_radial_glow": False, "glow_origin": "none",
                       "glow_color": "rgba(255,255,255,0.05)", "background_depth": "flat"},
    }


def spec_to_prompt_hint(spec: DesignSpec) -> str:
    """DesignSpec을 다운스트림 agent 프롬프트에 넣기 좋은 형태로."""
    pal = spec.get("palette", {})
    typo = spec.get("typography", {})
    frame = spec.get("frame_system", {})
    motif = spec.get("decorative_motif", {})
    atmos = spec.get("atmosphere", {})

    lines = [
        "**Design Director가 결정한 디자인 언어 (반드시 준수)**:",
        f"- Aesthetic: {spec.get('aesthetic_label', 'unknown')}",
        f"- Typography: hero={typo.get('hero_family','sans')}/w{typo.get('hero_weight',800)}/{typo.get('hero_style_hint','normal')}, body={typo.get('body_family','sans')}",
        f"- Palette: bg={pal.get('bg_primary','#000')} / accent={pal.get('accent','#888')} / frame={pal.get('frame_color','')} / text_bright={pal.get('text_bright','#fff')}",
        f"- Frame: hero={frame.get('hero_frame','')}; card={frame.get('card_frame','')}; bottom_bar={frame.get('bottom_accent_bar', False)}",
        f"- Motif: {motif.get('style','minimal')} (density {motif.get('density','sparse')}, shapes {motif.get('detected_shapes',[])})",
        f"- Atmosphere: glow={atmos.get('has_radial_glow',False)} from {atmos.get('glow_origin','none')} color {atmos.get('glow_color','')}, depth={atmos.get('background_depth','flat')}",
    ]
    return "\n".join(lines)
