"""Layout Analyzer prompt."""
ANALYZER_PROMPT = """이 슬라이드 디자인 이미지(1280x720)를 분석하세요. 이미지 비율(0~1) 좌표로 위치를 알려주세요.

먼저 **layout_type** 판단:
- horizontal_row, grid, hub_spoke, pyramid, split, vertical_stack
- **split_hero_stats**: 한쪽에 큰 hero 박스 + 다른 쪽에 여러 stat 카드
- **hero_only**: 단일 hero 박스 중심
- freeform

그다음 **요소 타입** 식별:

1. **hero_blocks**: 크고 standalone한 히어로 영역 (큰 placeholder 숫자/제목, 두드러진 배경/테두리)
2. **cards**: 비슷한 크기로 반복되는 정보 블록
3. **decorations**: 장식/구조 요소 (shape, spotlight, gradient_panel, frame_accent, timeline_line, glow_node, connector, hub_circle)
4. **background**: 전반적 배경 (primary_color, secondary_color, gradient_direction, pattern_type)

JSON:
```json
{
  "layout_type": "...",
  "global_palette": {
    "bg_primary": "#hex", "bg_secondary": "#hex", "accent": "#hex",
    "text_primary": "#hex", "text_accent": "#hex"
  },
  "aesthetic": "자유서술 (예: 'luxury dark gold with geometric decorations')",
  "hero_blocks": [{"id": "hero_1", "x1": 0.xx, "y1": 0.xx, "x2": 0.xx, "y2": 0.xx,
                   "style_hint": "gold frame with XXXX placeholder"}],
  "cards": [{"id": "card_1", "x1": 0.xx, "y1": 0.xx, "x2": 0.xx, "y2": 0.xx,
             "shape": "rect|chevron|pill|hex|circle",
             "has_icon": true|false,
             "header_band": {"present": true|false, "color": "#hex"},
             "footer_band": {"present": true|false, "color": "#hex", "kind": "quarter|date|label|none"}}],
  "decorations": [{"type": "shape", "subtype": "triangle", "x": 0.xx, "y": 0.xx, "size": 0.xx}],
  "background": {"primary_color": "#hex", "gradient_direction": "135deg", "pattern_type": "geometric-mix"},
  "cards_have_icons": true|false
}
```

★ hero_blocks와 cards는 상호 배타적
★ hero는 크기·독립성·타이포 중요도로 구분
★ **`cards_have_icons`** — 카드 안에 *그림 아이콘 (글리프, 픽토그램, 동그란 컬러 뱃지)* 이 보이면 true. 헤더에 텍스트만 (예: '1. Diagnose') 보이고 아이콘 없으면 false. *숫자 뱃지나 step 번호는 아이콘 아님.*
★ **`cards[i].shape`** — 카드의 외곽 형태. 사각형이면 `rect`, 오른쪽 화살표 모양이면 `chevron`, 알약이면 `pill`, 육각형이면 `hex`. 다른 도형이면 `rect`.
★ **`cards[i].header_band`** — 카드 위쪽에 **다른 색의 띠**가 있으면 `present:true` 그리고 그 색을 hex로. 없으면 `present:false`.
★ **`cards[i].footer_band`** — 카드 아래쪽에 분리된 라벨 영역(분기/날짜/태그)이 있으면 `present:true` + 색 + 종류.
★ JSON만 출력, 설명 없이"""
