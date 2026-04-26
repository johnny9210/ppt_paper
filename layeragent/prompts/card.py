"""Card Detail agent prompt (bbox-highlighted + CV facts + DesignSpec)."""

CARD_DETAIL_PROMPT = """이 슬라이드 이미지에서 **빨간 사각형으로 표시된 카드 {card_idx}**를 HTML+CSS로 재현하라.

★★★ **빨간 사각형은 영역 표시용 overlay 일 뿐, 실제 디자인 요소가 아니다.**
- `border: 2px solid red` 같은 빨간 테두리를 카드 CSS 에 넣지 말 것
- 빨간색을 카드 배경/테두리/그림자로 사용하지 말 것
- 카드의 실제 색은 palette 에서 가져오기

{facts_block}

★ 위 결정론적 측정값을 반영 (VLM이 추측하지 말 것):
- CSS 색상은 palette에서 가져오기 (role에 맞게)
- 글자 크기는 OCR 높이에서 유도 (1rem ≈ 16px)
- 채도가 높다고 나오면 rgba alpha 낮추지 말 것

★ Global context (빨간 네모 바깥도 관찰):
- 전체 팔레트: {palette_hint}
- Aesthetic: {aesthetic_hint}
- 다른 카드들과 일관된 스타일

★★★ **정규화된 class 이름 필수**:
- 컨테이너: `.card-{card_idx}`
- 아이콘: **`.card-icon`** (다른 이름 금지)
- 값: **`.card-value`** (다른 이름 금지)
- 라벨: **`.card-label`** (다른 이름 금지)

구조:
```
<div class="card-{card_idx}">
  <div class="card-icon">아이콘자리</div>
  <div class="card-value">값자리</div>
  <div class="card-label">라벨자리</div>
</div>
```

★★★ **`.card-value` 와 `.card-label` 은 둘 다 순수 텍스트 컨테이너**:
- background, background-color 사용 금지 (검은 칩/바 모양 금지)
- box-shadow, border 등 시각 장식 금지
- height/width 고정 금지 (height:8px, width:80% 같은 진행바 모양 금지)
- "값을 강조하기 위한 chip / pill / 박스" 만들지 말 것 — 텍스트 자체가 강조 수단
- `.card-value`: font-size 큼(20-32px), color: 밝은 대비
- `.card-label`: font-size 12~16px, color: muted, line-height 1.3

★ 빨간 사각형 안만, 바깥 요소 만들지 말 것
★ 크기: width:100%; height:100%; position:relative;
★ 가로형 long card 면 flex-row, 세로형 tall card 면 flex-column
★ 텍스트 내용은 넣지 마세요 (Text Inserter가 채움)
★ <style>과 <div>로만"""
