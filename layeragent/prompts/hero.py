"""Hero Detail agent prompt."""

HERO_DETAIL_PROMPT = """이 슬라이드 이미지에서 **빨간 사각형으로 표시된 HERO 영역 {hero_idx}**를 HTML+CSS로 재현하라.

★★★ **빨간 사각형은 영역 표시용 overlay 일 뿐, 실제 디자인 요소가 아니다.**
- `border: 2px solid red` 같은 빨간 테두리를 hero CSS 에 넣지 말 것
- 빨간색을 hero 배경/테두리/그림자로 사용하지 말 것
- hero 의 실제 색은 palette 의 accent / bg_primary 에서 가져오기

{facts_block}

★ 위 결정론적 측정값 반영:
- OCR이 hero 텍스트의 실제 픽셀 높이를 알려줬다면 그 값을 font-size로 써라
- Palette accent 색을 큰 값에 사용 — 채도 죽이지 말 것
- 고채도 영역 비율 50%+이면 accent 과감히 사용

★ Hero 영역 특징:
- 큰 placeholder 숫자/제목이 있는 standalone 박스
- 프레임/테두리 색상 (실제 이미지 관찰)

★ Global context:
- 전체 팔레트: {palette_hint}
- Aesthetic: {aesthetic_hint}

★★★ **정규화된 class 이름**:
- 컨테이너: `.hero-{hero_idx}`
- 메인 큰 값: **`.hero-value`**
- 서브타이틀: **`.hero-subtitle`**

구조:
```
<div class="hero-{hero_idx}">
  <div class="hero-value">값자리</div>
  <div class="hero-subtitle">서브자리</div>
</div>
```

★ 크기: width:100%; height:100%; position:relative; display:flex; flex-direction:column; align-items:center; justify-content:center;
★ 텍스트 placeholder는 넣어도 OK (Text Inserter가 교체)
★ <style>과 <div>로만"""
