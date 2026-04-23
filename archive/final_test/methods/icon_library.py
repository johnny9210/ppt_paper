"""Icon concept → FontAwesome class 매핑 라이브러리.

SVG 생성을 VLM에 맡기지 않는다 (불가능). 대신:
1. Icon Agent가 이미지 보고 개념 단어 (shield/globe/handshake/...) 출력
2. 이 라이브러리가 개념 → 실제 FA 클래스로 매핑
3. `<i class="fas fa-{class}">`로 실제 렌더 (이미 CDN 붙어있음)

FontAwesome 6.5+ 기준. Slide 디자인에서 자주 쓰이는 400+ 개념.
"""
from __future__ import annotations

# 개념 → FontAwesome Free 아이콘 클래스
# (카테고리별 그룹핑; 여러 동의어가 같은 아이콘 가리킬 수 있음)

CONCEPT_TO_FA: dict[str, str] = {
    # Business / analytics
    "chart": "chart-line", "graph": "chart-line", "analytics": "chart-bar",
    "data": "database", "metric": "gauge-high", "kpi": "gauge-high",
    "growth": "arrow-trend-up", "trend_up": "arrow-trend-up", "trending": "arrow-trend-up",
    "decline": "arrow-trend-down", "revenue": "dollar-sign", "money": "sack-dollar",
    "coin": "coins", "chart_pie": "chart-pie", "pie": "chart-pie",
    "report": "file-lines", "presentation": "chart-simple", "dashboard": "gauge",
    "statistics": "chart-column", "stats": "chart-column",

    # Security / trust
    "shield": "shield-halved", "security": "shield-halved", "lock": "lock",
    "unlock": "lock-open", "key": "key", "fingerprint": "fingerprint",
    "verified": "circle-check", "check": "check", "checkmark": "check",

    # Global / network
    "globe": "globe", "earth": "globe", "world": "earth-americas",
    "network": "network-wired", "cloud": "cloud", "server": "server",
    "wifi": "wifi", "signal": "signal", "satellite": "satellite-dish",
    "broadcast": "tower-broadcast", "stream": "satellite-dish",

    # People / collaboration
    "user": "user", "person": "user", "people": "users", "team": "users",
    "handshake": "handshake", "deal": "handshake", "partnership": "handshake",
    "customer": "user-tie", "agent": "user-headset", "crowd": "people-group",

    # Documents / files
    "document": "file-lines", "file": "file", "pdf": "file-pdf",
    "folder": "folder", "archive": "box-archive", "library": "book",
    "notebook": "book", "note": "note-sticky", "clipboard": "clipboard-list",

    # Time / schedule
    "clock": "clock", "time": "clock", "schedule": "calendar-days",
    "calendar": "calendar", "deadline": "hourglass-end", "timer": "stopwatch",
    "alarm": "bell", "notification": "bell",

    # Communication
    "mail": "envelope", "email": "envelope", "message": "message",
    "chat": "comments", "comment": "comment", "phone": "phone",
    "microphone": "microphone", "megaphone": "bullhorn",

    # Development / AI
    "code": "code", "terminal": "terminal", "api": "plug",
    "robot": "robot", "ai": "microchip", "brain": "brain",
    "gear": "gear", "settings": "sliders", "tool": "wrench",
    "database_dev": "database", "bug": "bug",

    # Creative / design
    "palette": "palette", "brush": "paintbrush", "design": "pen-ruler",
    "camera": "camera", "image": "image", "video": "video",
    "music": "music", "star": "star", "heart": "heart",

    # Navigation / arrows
    "arrow_up": "arrow-up", "arrow_down": "arrow-down",
    "arrow_right": "arrow-right", "arrow_left": "arrow-left",
    "chevron_right": "chevron-right", "play": "play", "forward": "forward",
    "back": "arrow-rotate-left", "refresh": "arrows-rotate",

    # Process / workflow
    "process": "gears", "workflow": "diagram-project", "pipeline": "conveyor-belt",
    "automation": "bolt", "lightning": "bolt", "rocket": "rocket",
    "launch": "rocket", "target": "bullseye", "goal": "bullseye",
    "flag": "flag", "milestone": "flag-checkered",

    # Architecture / infra
    "building": "building", "city": "city", "office": "building",
    "factory": "industry", "warehouse": "warehouse", "home": "house",
    "store": "shop", "shopping": "cart-shopping", "bag": "bag-shopping",

    # Science / research
    "flask": "flask", "science": "flask", "research": "microscope",
    "atom": "atom", "dna": "dna", "test_tube": "vial",

    # Transportation
    "truck": "truck", "delivery": "truck-fast", "ship": "ship",
    "plane": "plane", "car": "car", "bike": "bicycle",

    # Misc
    "idea": "lightbulb", "innovation": "lightbulb", "question": "circle-question",
    "info": "circle-info", "warning": "triangle-exclamation", "error": "circle-xmark",
    "success": "circle-check", "gift": "gift", "award": "award",
    "trophy": "trophy", "medal": "medal", "crown": "crown",
}


def concept_to_fa_class(concept: str, fallback: str = "circle") -> str:
    """개념 단어 → FA 클래스 이름. 없으면 fallback."""
    key = (concept or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key in CONCEPT_TO_FA:
        return CONCEPT_TO_FA[key]
    # 부분 매칭 시도
    for k, v in CONCEPT_TO_FA.items():
        if k in key or key in k:
            return v
    return fallback


def fa_icon_html(concept: str, size_rem: float = 1.75, color: str = "currentColor") -> str:
    """개념 → <i class="fas fa-..."> HTML 조각."""
    fa = concept_to_fa_class(concept)
    return f'<i class="fas fa-{fa}" style="font-size:{size_rem}rem;color:{color};"></i>'


# 기하 장식 primitive — SVG path 라이브러리
SHAPE_LIBRARY: dict[str, str] = {
    "triangle_outline": '<svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg"><polygon points="50,10 90,90 10,90" stroke="{stroke}" stroke-width="2" fill="none" opacity="{opacity}"/></svg>',
    "triangle_filled": '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><polygon points="50,10 90,90 10,90" fill="{fill}" opacity="{opacity}"/></svg>',
    "circle_outline": '<svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="42" stroke="{stroke}" stroke-width="2" fill="none" opacity="{opacity}"/></svg>',
    "circle_filled": '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="45" fill="{fill}" opacity="{opacity}"/></svg>',
    "hexagon_outline": '<svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg"><polygon points="50,8 88,30 88,70 50,92 12,70 12,30" stroke="{stroke}" stroke-width="2" fill="none" opacity="{opacity}"/></svg>',
    "diamond_outline": '<svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg"><polygon points="50,10 90,50 50,90 10,50" stroke="{stroke}" stroke-width="2" fill="none" opacity="{opacity}"/></svg>',
    "square_outline": '<svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="10" y="10" width="80" height="80" stroke="{stroke}" stroke-width="2" fill="none" opacity="{opacity}"/></svg>',
    "corner_bracket_tl": '<svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg"><polyline points="5,40 5,5 40,5" stroke="{stroke}" stroke-width="2" fill="none" opacity="{opacity}"/></svg>',
    "corner_bracket_tr": '<svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg"><polyline points="60,5 95,5 95,40" stroke="{stroke}" stroke-width="2" fill="none" opacity="{opacity}"/></svg>',
    "corner_bracket_bl": '<svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg"><polyline points="5,60 5,95 40,95" stroke="{stroke}" stroke-width="2" fill="none" opacity="{opacity}"/></svg>',
    "corner_bracket_br": '<svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg"><polyline points="60,95 95,95 95,60" stroke="{stroke}" stroke-width="2" fill="none" opacity="{opacity}"/></svg>',
    "gold_hairline_frame": '<div style="position:absolute;inset:0;border:1px solid {stroke};opacity:{opacity};pointer-events:none;"></div>',
    "bottom_accent_bar": '<div style="position:absolute;left:0;right:0;bottom:0;height:3px;background:{fill};opacity:{opacity};pointer-events:none;"></div>',
}


def shape_html(
    shape_name: str,
    stroke: str = "#D4AF37",
    fill: str = "#D4AF37",
    opacity: float = 0.35,
    x_pct: float = 0.0, y_pct: float = 0.0,
    size_pct: float = 10.0,
) -> str:
    """기하 도형 → HTML/SVG 조각 (position:absolute로 감싸서 반환)."""
    if shape_name not in SHAPE_LIBRARY:
        return ""
    svg = SHAPE_LIBRARY[shape_name].format(stroke=stroke, fill=fill, opacity=opacity)
    if shape_name.startswith("gold_hairline") or shape_name.startswith("bottom_accent"):
        return svg  # 이미 div 형태
    return f'<div style="position:absolute;left:{x_pct:.1f}%;top:{y_pct:.1f}%;width:{size_pct:.1f}%;height:{size_pct:.1f}%;pointer-events:none;">{svg}</div>'
