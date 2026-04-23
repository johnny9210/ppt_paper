"""Style Normalizer prompt — 독립 생성된 카드들 간 CSS 속성값 통일."""

NORMALIZE_PROMPT = """아래 HTML은 슬라이드의 카드들을 독립 생성 후 합친 것입니다.
카드마다 CSS 값이 미세하게 다릅니다. **CSS 값만 통일**해주세요.

```html
{html}
```

★★★ 수정 범위 — 이것만 변경:
- background의 rgba 알파값 → 모든 카드 동일
- border 색상/두께 → 모든 카드 동일
- border-radius → 모든 카드 동일
- box-shadow → 모든 카드 동일
- backdrop-filter → 모든 카드 동일

★★★ 절대 변경 금지:
- position, left, top, width, height
- z-index
- div 구조 (추가/삭제/이동 금지)
- 텍스트 내용
- 배경 레이어 (z-index:0 영역)

★ 입력 HTML 구조 그대로, CSS 속성 값만 통일
★ 전체 HTML 출력, <style>과 <div>만"""
