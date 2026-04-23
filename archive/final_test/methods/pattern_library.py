"""패턴/연결선 라이브러리 — hub-spoke 같은 연결 구조 design 지원.

v8까지 있던 shape_library는 독립 도형 (삼각/원/육각) 만 커버 → hub-spoke, flowchart 등
"연결이 중요한" design 약했다. v9에서 추가:

1. Connection Line Generator — 두 점 (hub, card 중심) → bezier SVG path
2. Background Patterns — circuit, topographic, dot_grid 등 타일링 패턴
3. Hub Enhancement — 중심 허브의 크기/글로우 강조
"""
from __future__ import annotations

import math


# ════════════════════════════════════════════════════════════
# Connection Line — 곡선 베지에 path
# ════════════════════════════════════════════════════════════

def bezier_path(p1: tuple[float, float], p2: tuple[float, float], curvature: float = 0.25) -> str:
    """두 점 사이의 SVG 베지에 곡선 path.

    p1, p2: (x, y) in 0-100 percent coordinates (상대 좌표).
    curvature: 휘어지는 정도. 0=직선, 0.3=부드러운 곡선.
    """
    x1, y1 = p1
    x2, y2 = p2
    mx = (x1 + x2) / 2
    my = (y1 + y2) / 2
    dx = x2 - x1
    dy = y2 - y1
    length = math.sqrt(dx * dx + dy * dy)
    if length < 0.1:
        return f"M{x1:.2f},{y1:.2f} L{x2:.2f},{y2:.2f}"
    # 수직 방향으로 제어점을 오프셋
    nx = -dy / length
    ny = dx / length
    cx = mx + nx * length * curvature
    cy = my + ny * length * curvature
    return f"M{x1:.2f},{y1:.2f} Q{cx:.2f},{cy:.2f} {x2:.2f},{y2:.2f}"


def render_connections(
    hub_center: tuple[float, float],
    card_centers: list[tuple[float, float]],
    color: str = "#4ADEDE",
    stroke_width: float = 0.4,
    opacity: float = 0.5,
    glow: bool = True,
) -> str:
    """허브 → 각 카드 중심으로 SVG 연결선 일괄 생성 (whole-slide SVG overlay)."""
    if not card_centers:
        return ""
    paths = []
    for c in card_centers:
        d = bezier_path(hub_center, c, curvature=0.2)
        paths.append(
            f'<path d="{d}" stroke="{color}" stroke-width="{stroke_width}" '
            f'fill="none" stroke-linecap="round" opacity="{opacity}"/>'
        )
    filter_def = ""
    filter_attr = ""
    if glow:
        filter_def = f'''<defs>
  <filter id="neon-glow" x="-50%" y="-50%" width="200%" height="200%">
    <feGaussianBlur stdDeviation="0.6" result="coloredBlur"/>
    <feMerge>
      <feMergeNode in="coloredBlur"/>
      <feMergeNode in="SourceGraphic"/>
    </feMerge>
  </filter>
</defs>'''
        filter_attr = 'filter="url(#neon-glow)"'
    return f'''<svg viewBox="0 0 100 100" preserveAspectRatio="none" style="position:absolute;inset:0;width:100%;height:100%;z-index:3;pointer-events:none;">
  {filter_def}
  <g {filter_attr}>
    {"".join(paths)}
  </g>
</svg>'''


# ════════════════════════════════════════════════════════════
# Background Patterns
# ════════════════════════════════════════════════════════════

_PATTERNS = {
    "circuit_grid": '''<svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="position:absolute;inset:0;pointer-events:none;">
  <defs>
    <pattern id="p-circuit" x="0" y="0" width="80" height="80" patternUnits="userSpaceOnUse">
      <path d="M 0,20 L 30,20 L 30,40 L 60,40 L 60,15 L 80,15" stroke="{stroke}" stroke-width="0.6" fill="none" opacity="{opacity}"/>
      <path d="M 10,0 L 10,30 L 50,30 L 50,55 L 75,55 L 75,80" stroke="{stroke}" stroke-width="0.6" fill="none" opacity="{opacity}"/>
      <circle cx="30" cy="20" r="1.5" fill="{stroke}" opacity="{opacity}"/>
      <circle cx="60" cy="40" r="1.5" fill="{stroke}" opacity="{opacity}"/>
      <circle cx="50" cy="30" r="1.5" fill="{stroke}" opacity="{opacity}"/>
      <circle cx="75" cy="55" r="1.5" fill="{stroke}" opacity="{opacity}"/>
    </pattern>
  </defs>
  <rect width="100%" height="100%" fill="url(#p-circuit)"/>
</svg>''',

    "topographic_lines": '''<svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="position:absolute;inset:0;pointer-events:none;">
  <defs>
    <pattern id="p-topo" x="0" y="0" width="200" height="80" patternUnits="userSpaceOnUse">
      <path d="M 0,20 Q 50,10 100,20 T 200,20" stroke="{stroke}" stroke-width="0.6" fill="none" opacity="{opacity}"/>
      <path d="M 0,40 Q 50,30 100,40 T 200,40" stroke="{stroke}" stroke-width="0.6" fill="none" opacity="{opacity}"/>
      <path d="M 0,60 Q 50,50 100,60 T 200,60" stroke="{stroke}" stroke-width="0.6" fill="none" opacity="{opacity}"/>
    </pattern>
  </defs>
  <rect width="100%" height="100%" fill="url(#p-topo)"/>
</svg>''',

    "dot_grid": '''<svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="position:absolute;inset:0;pointer-events:none;">
  <defs>
    <pattern id="p-dots" x="0" y="0" width="30" height="30" patternUnits="userSpaceOnUse">
      <circle cx="15" cy="15" r="1" fill="{stroke}" opacity="{opacity}"/>
    </pattern>
  </defs>
  <rect width="100%" height="100%" fill="url(#p-dots)"/>
</svg>''',

    "hex_grid": '''<svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style="position:absolute;inset:0;pointer-events:none;">
  <defs>
    <pattern id="p-hex" x="0" y="0" width="60" height="52" patternUnits="userSpaceOnUse">
      <polygon points="30,4 55,18 55,38 30,52 5,38 5,18" stroke="{stroke}" stroke-width="0.6" fill="none" opacity="{opacity}"/>
    </pattern>
  </defs>
  <rect width="100%" height="100%" fill="url(#p-hex)"/>
</svg>''',
}


def background_pattern(pattern_name: str, stroke: str = "#4ADEDE", opacity: float = 0.15) -> str:
    """name → 배경 패턴 SVG overlay (position:absolute inset:0)."""
    if pattern_name not in _PATTERNS:
        return ""
    return _PATTERNS[pattern_name].format(stroke=stroke, opacity=opacity)


# aesthetic_label 또는 motif → 적합한 배경 패턴 이름 매핑
def pattern_for_aesthetic(aesthetic: str, motif: dict) -> str | None:
    """디자인 언어에서 적합한 배경 패턴 추천. 없으면 None."""
    aes = (aesthetic or "").lower()
    motif_style = (motif or {}).get("style", "").lower()
    shapes = [s.lower() for s in (motif or {}).get("detected_shapes", [])]

    if "cyber" in aes or "neon" in aes or "tech" in aes or "circuit" in motif_style:
        return "circuit_grid"
    if "topograph" in aes or "map" in aes or "layer" in aes:
        return "topographic_lines"
    if "hex" in motif_style or "hexagon" in shapes:
        return "hex_grid"
    if "dot" in aes or motif_style == "dot":
        return "dot_grid"
    return None


# ════════════════════════════════════════════════════════════
# Hub Enhancement — hub-spoke 중심부 강조
# ════════════════════════════════════════════════════════════

def hub_enhancement_html(
    cx_pct: float, cy_pct: float, size_pct: float = 18.0,
    accent: str = "#4ADEDE", inner_icon: str = "globe",
) -> str:
    """Hub 중심에 크고 강한 글로우 + 아이콘."""
    from .icon_library import concept_to_fa_class
    fa_cls = concept_to_fa_class(inner_icon)
    return f'''<div style="position:absolute;left:{cx_pct - size_pct/2:.1f}%;top:{cy_pct - size_pct/2:.1f}%;
                        width:{size_pct}%;aspect-ratio:1;z-index:15;display:flex;
                        align-items:center;justify-content:center;border-radius:50%;
                        background:radial-gradient(circle, rgba(74,222,222,0.25) 0%, transparent 70%);
                        box-shadow:0 0 60px {accent}55, 0 0 120px {accent}30, inset 0 0 40px {accent}44;
                        border:2px solid {accent};">
  <i class="fas fa-{fa_cls}" style="font-size:3rem;color:{accent};filter:drop-shadow(0 0 10px {accent});"></i>
</div>'''
