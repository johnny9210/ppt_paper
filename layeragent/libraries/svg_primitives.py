"""SVG primitive 라이브러리 — 차트가 아닌 UI 원시 요소 전담.

VLM 에게 생성시키면 실패하는 것들:
- progress bar / gauge / percentage arc
- numbered step indicator (roadmap 1,2,3,4,5)
- KPI card frame (골드 bottom bar 등)
- sparkline (작은 트렌드 미니 차트)

이 모듈은 deterministic SVG 생성 — VLM 불필요.
"""
from __future__ import annotations


def progress_bar(
    percent: float, color: str = "#D4AF37", bg_color: str = "rgba(255,255,255,0.1)",
    height_px: int = 8, radius_px: int = 4,
) -> str:
    """수평 progress bar HTML snippet. percent: 0~100."""
    pct = max(0.0, min(100.0, float(percent)))
    return f'''<div style="width:100%;height:{height_px}px;background:{bg_color};
                border-radius:{radius_px}px;overflow:hidden;position:relative;">
      <div style="width:{pct}%;height:100%;background:{color};
                  border-radius:{radius_px}px;
                  box-shadow:0 0 8px {color};"></div>
    </div>'''


def percentage_gauge(percent: float, color: str = "#D4AF37", size_px: int = 80) -> str:
    """원형 gauge (SVG arc). percent 0~100."""
    pct = max(0.0, min(100.0, float(percent)))
    r = 40
    circumference = 2 * 3.14159 * r
    offset = circumference * (1 - pct / 100)
    return f'''<svg width="{size_px}" height="{size_px}" viewBox="0 0 100 100">
      <circle cx="50" cy="50" r="{r}" stroke="rgba(255,255,255,0.1)" stroke-width="8" fill="none"/>
      <circle cx="50" cy="50" r="{r}" stroke="{color}" stroke-width="8" fill="none"
              stroke-dasharray="{circumference:.1f}" stroke-dashoffset="{offset:.1f}"
              transform="rotate(-90 50 50)" stroke-linecap="round"/>
      <text x="50" y="55" text-anchor="middle" fill="{color}" font-size="18" font-weight="700">{int(pct)}%</text>
    </svg>'''


def numbered_circle(n: int, accent: str = "#D4AF37", size_px: int = 40,
                     active: bool = True) -> str:
    """Roadmap 타임라인 위의 번호 원 (1,2,3,4,5...)."""
    stroke = accent if active else "rgba(255,255,255,0.3)"
    bg = f"rgba(0,0,0,0.4)"
    text_color = accent if active else "rgba(255,255,255,0.5)"
    return f'''<div style="width:{size_px}px;height:{size_px}px;border-radius:50%;
                background:{bg};border:2px solid {stroke};display:inline-flex;
                align-items:center;justify-content:center;
                box-shadow:0 0 12px {stroke}55;
                font-weight:700;color:{text_color};font-size:{int(size_px*0.45)}px;">{n}</div>'''


def step_indicator_row(n_steps: int, current_step: int = 0,
                        accent: str = "#D4AF37", container_width_pct: float = 80.0) -> str:
    """Timeline 위에 N개 번호 원 + 연결선 한번에. position:absolute 권장 배치."""
    if n_steps <= 0:
        return ""
    circles = ""
    for i in range(n_steps):
        x_pct = (i / max(n_steps - 1, 1)) * 100
        circles += f'''<div style="position:absolute;left:{x_pct:.1f}%;top:50%;
                        transform:translate(-50%,-50%);">
      {numbered_circle(i + 1, accent=accent, size_px=36, active=(i <= current_step))}
    </div>'''
    line = f'''<div style="position:absolute;left:0;top:50%;width:100%;height:3px;
                  background:linear-gradient(to right, {accent}88, {accent}44);
                  transform:translateY(-50%);border-radius:2px;"></div>'''
    return f'''<div style="position:relative;width:{container_width_pct}%;height:40px;margin:0 auto;">
      {line}{circles}
    </div>'''


def sparkline(values: list[float], color: str = "#D4AF37",
               width_px: int = 120, height_px: int = 30) -> str:
    """간단 라인 스파크라인. values 정규화."""
    if not values or len(values) < 2:
        return ""
    vmin, vmax = min(values), max(values)
    rng = max(vmax - vmin, 1e-6)
    pts = []
    for i, v in enumerate(values):
        x = (i / (len(values) - 1)) * width_px
        y = height_px - ((v - vmin) / rng) * height_px
        pts.append(f"{x:.1f},{y:.1f}")
    pts_str = " ".join(pts)
    return f'''<svg width="{width_px}" height="{height_px}" viewBox="0 0 {width_px} {height_px}">
      <polyline points="{pts_str}" stroke="{color}" stroke-width="2" fill="none"
                stroke-linecap="round" stroke-linejoin="round"
                style="filter:drop-shadow(0 0 3px {color}88);"/>
    </svg>'''


def bar_chart_inline(values: list[float], labels: list[str] | None = None,
                     color: str = "#D4AF37", width_px: int = 300, height_px: int = 180) -> str:
    """기본 막대 차트 SVG."""
    if not values:
        return ""
    vmax = max(values) or 1
    n = len(values)
    bar_w = width_px / (n * 1.8)
    gap = bar_w * 0.8
    bars = ""
    for i, v in enumerate(values):
        h = (v / vmax) * (height_px - 30)
        x = gap / 2 + i * (bar_w + gap)
        y = height_px - h - 20
        bars += f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}" opacity="0.85" rx="3"/>'
        if labels and i < len(labels):
            bars += f'<text x="{x + bar_w/2:.1f}" y="{height_px - 4}" text-anchor="middle" fill="rgba(255,255,255,0.7)" font-size="10">{labels[i]}</text>'
    return f'''<svg width="{width_px}" height="{height_px}" viewBox="0 0 {width_px} {height_px}">
      {bars}
    </svg>'''


def kpi_card_frame(accent: str = "#D4AF37", frame_color: str = "rgba(212,175,55,0.35)") -> str:
    """KPI 카드 상단 레이블 + 하단 accent bar 래핑용 frame."""
    return f'''<div style="position:absolute;inset:0;border:1px solid {frame_color};
                border-radius:12px;pointer-events:none;"></div>
      <div style="position:absolute;bottom:0;left:0;right:0;height:4px;
                  background:{accent};"></div>'''
