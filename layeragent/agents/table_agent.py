"""Table Agent — slide_type=table 일 때 content.headers/rows 를 절대 좌표 HTML 표로 렌더.

card-based 파이프라인을 우회하는 단일 노드. analyzer 가 cards=[] 로 비워두므로
card_detail / hero_detail 은 자연스럽게 no-op 가 된다.
"""
from __future__ import annotations

import html as _html

from ..utils.common import filter_content


def _esc(v) -> str:
    return _html.escape(str(v if v is not None else ""), quote=True)


def _table_css(palette: dict) -> str:
    accent = palette.get("accent", "#3B82F6")
    text_bright = palette.get("text_bright", "#F1F5F9")
    text_muted = palette.get("text_muted", "rgba(241,245,249,0.7)")
    frame = palette.get("frame_color", "rgba(255,255,255,0.12)")
    return f"""
    .lt-table-wrap {{
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 1.5%;
      box-sizing: border-box;
    }}
    .lt-table {{
      width: 100%;
      max-height: 100%;
      border-collapse: separate;
      border-spacing: 0;
      background: rgba(15, 23, 42, 0.55);
      border: 1px solid {frame};
      border-radius: 14px;
      box-shadow: 0 12px 36px rgba(0,0,0,0.35);
      backdrop-filter: blur(14px);
      overflow: hidden;
      font-family: 'Noto Sans KR', sans-serif;
      color: {text_bright};
    }}
    .lt-table thead th {{
      background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0));
      color: {accent};
      font-weight: 700;
      font-size: 0.95rem;
      text-align: left;
      padding: 14px 18px;
      letter-spacing: 0.04em;
      border-bottom: 1px solid {frame};
    }}
    .lt-table tbody td {{
      padding: 12px 18px;
      font-size: 0.85rem;
      color: {text_bright};
      border-bottom: 1px solid {frame};
      word-break: keep-all;
      overflow-wrap: anywhere;
    }}
    .lt-table tbody tr:last-child td {{
      border-bottom: none;
    }}
    .lt-table tbody tr:nth-child(even) td {{
      background: rgba(255,255,255,0.02);
    }}
    .lt-table tbody td:first-child {{
      color: {text_muted};
      font-weight: 600;
    }}
    """


def _bbox_for_table(has_title: bool) -> tuple[float, float, float, float]:
    """타이틀 있으면 위 12% 비우고, 없으면 슬라이드 안쪽 패딩만."""
    top = 14.0 if has_title else 6.0
    return (6.0, top, 88.0, 100.0 - top - 6.0)


def table_agent(state) -> dict:
    """slide_type=table 면 table_html 반환, 아니면 빈 문자열."""
    if (state.get("slide_type") or "").lower() != "table":
        return {"table_html": ""}

    content = filter_content(state.get("content", {}))
    headers = content.get("headers", []) or []
    rows = content.get("rows", []) or []
    if not headers or not rows:
        return {"table_html": ""}

    spec = state.get("design_spec", {}) or {}
    palette = spec.get("palette", {}) or {}

    th_html = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body_rows = []
    for row in rows:
        cells = list(row) if isinstance(row, (list, tuple)) else [row]
        # 헤더 길이에 맞춰 자르거나 패딩
        if len(cells) < len(headers):
            cells = cells + [""] * (len(headers) - len(cells))
        else:
            cells = cells[: len(headers)]
        tds = "".join(f"<td>{_esc(c)}</td>" for c in cells)
        body_rows.append(f"<tr>{tds}</tr>")

    has_title = bool(content.get("title"))
    left, top, width, height = _bbox_for_table(has_title)

    table = f"""<style>{_table_css(palette)}</style>
<div style="position:absolute;left:{left:.1f}%;top:{top:.1f}%;width:{width:.1f}%;height:{height:.1f}%;z-index:9;">
  <div class="lt-table-wrap">
    <table class="lt-table">
      <thead><tr>{th_html}</tr></thead>
      <tbody>{''.join(body_rows)}</tbody>
    </table>
  </div>
</div>"""
    return {"table_html": table}
