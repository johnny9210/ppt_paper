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

★★★ **시각 충실도 (Visual Fidelity)**: 이 카드의 모든 시각 구조를 빠짐없이 재현하라:
- **외곽 테두리**: 카드 자체의 border / gradient outline / corner 처리
- **내부 nested 패널**: 카드 안에 또 다른 박스/패널이 있다면 그것도 div + border 로 재현
- **헤더 pill / 라벨 칩**: 아이콘과 제목이 묶여있는 둥근 막대 형태가 보이면 그 막대를 wrapper div 로 만들고 그 안에 .card-icon + .card-value 를 배치
- **하단 장식 (bottom accent)**: 작은 pill / 버튼 / 그라디언트 막대가 아래쪽에 있으면 별도 div 로 재현
- **다중 그라디언트, glow, blur**: backdrop-filter / multiple box-shadow / linear-gradient + radial-gradient 조합으로 풍부하게 표현

★★★ **정규화된 class 이름 (시맨틱 슬롯)**:
- 컨테이너: `.card-{card_idx}` (필수, 외곽)
- 아이콘 슬롯: **`.card-icon`** (이름 고정 — 텍스트로 채워질 슬롯)
- 값/제목 슬롯: **`.card-value`** (이름 고정)
- 라벨/설명 슬롯: **`.card-label`** (이름 고정)

★ 위 3개 시맨틱 슬롯을 **추가 wrapper div 로 자유롭게 감싸도 좋다** — 헤더 pill, content panel, 장식 박스 등은 임의 클래스 이름 (.card-header, .card-body, .card-accent 등) 으로 만들어 nested structure 재현.

기본 구조 (단순 카드일 때):
```
<div class="card-{card_idx}">
  <div class="card-icon">아이콘자리</div>
  <div class="card-value">값자리</div>
  <div class="card-label">라벨자리</div>
</div>
```

확장 구조 예시 (헤더 pill + 내부 panel + 하단 accent 가 보이는 카드):
```
<div class="card-{card_idx}">
  <div class="card-header">             <!-- 헤더 pill -->
    <div class="card-icon">아이콘자리</div>
    <div class="card-value">값자리</div>
  </div>
  <div class="card-body">               <!-- 내부 nested panel -->
    <div class="card-label">라벨자리</div>
  </div>
  <div class="card-accent"></div>       <!-- 하단 장식 pill -->
</div>
```

★★★ **`.card-label` 의 진행바화 금지** — 진짜 텍스트 라벨로 사용:
- height 고정 + 작은 값 (height:6~12px) + width 고정 (width:80%) + background gradient 조합 = 진행바 모양 금지
- 라벨은 텍스트가 들어가는 컨테이너이므로 height 는 line-height 로 결정

★ 빨간 사각형 안만, 바깥 요소 만들지 말 것
★ 크기: width:100%; height:100%; position:relative;
★ 가로형 long card 면 flex-row, 세로형 tall card 면 flex-column
★ 텍스트 내용은 넣지 마세요 (Text Inserter가 채움)
★ <style>과 <div>로만"""
