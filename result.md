# LayerAgent — 결과 해석 한 번에 읽기

> 비행기에서 쭉 읽으시면 됩니다. 어려운 표현 빼고 핵심만 정리했습니다.

---

## 0. 한 줄 요약

> **LayerAgent는 GPT-4o 같은 베이스 모델 위에서, 다층 디자인을 만들 때 구조와 시각 풍부성을 늘려준다. 다만 모든 경우에서 1등은 아니고, GPT-5.4 같은 최신 모델 single-pass에는 진다.**

이 한 줄이 이 논문 전체 결과를 다 담고 있습니다.

---

## 1. 큰 그림 — 결과는 어떻게 정리되었나

논문은 결과를 **두 표**로 나눠서 봅니다.

| 표 | 무엇을 보는가 | 누구랑 비교? |
|---|---|---|
| **Table 1** | "같은 모델로 베이스라인보다 좋아지는가" | GPT-4o single-pass / visual_cot / cot_h_rag |
| **Table 2** | "모델 자체가 더 비싼 frontier보다 가성비 있는가" | GPT-5.4 / Claude 4.6 Opus single-pass |

**왜 두 표를 나누었나**: 한 표 안에 섞으면 "이게 LayerAgent 효과인지, 단순히 모델 차이인지" 헷갈리기 때문. 그래서 **같은 모델 비교**랑 **다른 모델 비교**를 분리한 것.

---

## 2. Table 1 — 같은 GPT-4o 위에서 본 효과

### 2.1 결과 (N=10 다층 dark-glass 슬라이드)

| 지표 | 무엇을 보나 | single_pass | LayerAgent | 차이 |
|---|---|:---:|:---:|---|
| VEC | 시각 element 개수 | 9.1 | **20.9** | **2.3배 많음** |
| EDC | 스타일 다양성 | 3.0 | **9.7** | **3.2배 다양함** |
| CRP | CSS 효과 풍부함 | 23.6 | **51.5** | **2.2배 풍부함** |
| CLIP | 의미적 유사도 | 0.450 | **0.492** | LayerAgent 우세 |
| LPIPS ↓ (낮을수록 좋음) | 인간 perception 거리 | 0.653 | **0.589** | LayerAgent 우세 |
| SSIM | 픽셀 유사도 | **0.493** | 0.470 | single_pass가 0.023 높음 |

### 2.2 어떻게 읽나

**좋은 결과**: LayerAgent가 8개 자동 지표 중 **7개에서 1위**. DOM 구조 5개(시각 element 개수, 스타일 다양성 등) 모두 2배 이상 차이.

**SSIM만 졌는데 괜찮은가요?**
- 차이가 0.023밖에 안 됨
- N=10에서 표준편차가 ~0.10이라서, 사실상 noise 수준
- 그래서 *"명확한 우위로 해석하지 않는다"*고 정직하게 인정

**왜 SSIM은 single_pass가 잘하나?**
- SSIM은 픽셀 단위 유사도 측정
- single_pass는 픽셀 *모방*에 강함 (이미지를 그대로 따라 그리듯)
- 하지만 z-index 부재, 계층 단순화는 SSIM에 패널티가 없음
- 즉 **"눈에는 비슷한데 코드로 보면 평면"인 결과**도 SSIM은 후하게 줌
- 그래서 SSIM에서 진다고 해서 "구조가 더 좋다"는 뜻은 아님

### 2.3 visual_cot, cot_h_rag는 왜 single_pass보다도 못한가?

이게 사실 핵심 발견 중 하나입니다.

- **visual_cot** (시각 분석 → 코드 생성 2단계): VEC 7.3 < single_pass 9.1
- **cot_h_rag** (CoT + CSS 패턴 RAG 주입): LPIPS·CLIP에서 **꼴찌**

**왜?** 단순 2단계 CoT나 CSS 패턴 주입은:
- 토큰 예산을 더 많이 쓰지만 시각 효과를 늘리지 못함
- 오히려 텍스트가 빠지거나 일관성이 깨짐
- → **단순 prompt 트릭으로는 안 된다**는 게 이 결과의 메시지

**그래서 LayerAgent의 가치는?**
> "단순히 prompt만 바꿔서는 안 되고, **분해 + DesignSpec + Library + Style Normalizer + Text Inserter 통합**이 필요하다"

다만 paper는 *어느 컴포넌트가 정확히 얼마나 기여했는지*는 D₂ (Text Inserter)만 측정. 나머지 3개는 시스템 수준 효과만 본 상태.

---

## 3. Table 1b — MLLM 판사가 본 결과 (반전)

### 3.1 결과 (GPT-5.4가 채점, 1-7점, N=48)

| 항목 | cot_h_rag | LayerAgent | **single_pass** | visual_cot |
|---|:---:|:---:|:---:|:---:|
| Visual Fidelity (시각 충실도) | 1.73 | 1.65 | **2.17** | 2.08 |
| **Layer Structure (계층 구조)** | 3.00 | **3.58** | 3.46 | 3.08 |
| Content Completeness (콘텐츠 완성도) | 3.77 | 2.35 | **3.81** | 3.60 |
| Design Quality (디자인 품질) | 3.40 | 2.79 | **3.75** | 3.29 |
| **평균** | 2.97 | 2.59 | **3.30** | 3.02 |

### 3.2 어떻게 읽나

**놀라운 부분**: 자동 지표에서 7-1로 LayerAgent가 이겼는데, 사람 흉내 내는 MLLM 판사는 **single_pass가 평균 우세**.

**LayerAgent는 "Layer Structure" 한 축에서만** 우세 (3.58 vs 3.46).

### 3.3 왜 이런 일이 일어나나?

LayerAgent는 layer 수와 시각 element를 많이 commit. 근데 그렇다고 **"발표하기 좋은 슬라이드"**가 자동으로 되는 건 아님:
- 텍스트가 카드 영역을 넘쳐서 가려짐 (overflow)
- 카드가 너무 빽빽해서 dense
- 콘텐츠가 시각적으로 *읽히지 않음*

→ **"layer 수 회복" ≠ "발표 가능한 슬라이드"**

**이걸 paper는 어떻게 처리하나?**
- 숨기지 않고 **honest scope**로 명시
- "LayerAgent는 *편집 가능한 구조 회복*에 정렬된 시스템"
- "*발표 가능한 슬라이드*까지 가려면 Visual Critic + 보수적 Text Inserter 추가 필요" (향후 연구)

### 3.4 String-CCR vs Visual CC 모순

가장 흥미로운 발견 (paper §7.3):
- **LayerAgent string-CCR = 0.99** — 텍스트 99%가 HTML 코드에 *문자열로 존재*
- **LayerAgent MLLM CC = 2.35** — 그러나 시각적으로 *읽히지 않음* (4 메서드 중 최악)

→ **"코드에 텍스트가 있다 ≠ 사람이 읽을 수 있다"**

이건 디자인-투-코드 평가가 가진 *근본적 메트릭 진화 필요성*을 보여줍니다. 향후 *Visual CCR* (OCR로 가시 텍스트 측정)이 필요.

---

## 4. Table 2 — 더 비싼 frontier 모델과 비교

### 4.1 결과 (N=10 dark-glass)

| Method | CLIP↑ | LPIPS↓ | 슬라이드당 비용 | 시간 |
|---|:---:|:---:|:---:|:---:|
| LayerAgent (GPT-4o) | 0.492 | 0.589 | **$0.232** | **60초** |
| single-pass GPT-5.4 | **0.578** | **0.411** | $0.075 | 85초 |
| single-pass Claude 4.6 Opus | 0.525 | 0.502 | $0.421 | 108초 |

### 4.2 두 가지 결론 — 정직하게

#### vs Claude Opus → cost-sensitive 대안 ✓
- 자동 지표는 Opus가 *조금 우세* (LPIPS 0.502 vs 0.589)
- 그러나 **비용 45% 절감**, **시간 44% 절감**
- 결론: "Opus 수준 품질이 필요한데 비용이 부담일 때, LayerAgent가 대안"

#### vs GPT-5.4 → 솔직히 졌다 ✗
- GPT-5.4가 **모든 지표에서 1위**
- 비용도 **GPT-5.4가 1/3**
- 결론: "**LayerAgent가 frontier를 능가한다**라는 강한 주장은 본 데이터로 지지 안 됨"

### 4.3 왜 이걸 솔직히 인정하는 게 좋은가?

논문에서 **부정 결과를 숨기지 않은 점이 오히려 신뢰도를 높임**.

- 만약 GPT-5.4 결과를 빼고 Opus 비교만 보여줬다면? → reviewer가 "왜 GPT-5.4랑 비교 안 했나" 즉시 공격
- 정직하게 보고 → "GPT-5.4에는 졌다는 honest scope" → 반박 어려움

**Karpathy식 정직 정착**: 어떤 이긴 결과든, *졌을 때를 함께 보고*하면 이긴 결과의 신뢰도도 올라감.

### 4.4 Operational implication (어떤 상황에 뭘 쓸까)

| 상황 | 추천 |
|---|---|
| 품질·비용 둘 다 우선 | **GPT-5.4 single-pass** (가장 빠르고 좋음) |
| Opus 급 품질이 필요한데 비용 절감 | **LayerAgent (GPT-4o)** |
| 최저 비용, 품질 양보 OK | **GPT-4o single-pass** ($0.015/slide, 10초) |

---

## 5. Table 3 — Layout별 sweet spot 분석

### 5.1 결과 (9 layout family)

| Layout | LayerAgent LTED | LTED Δ | LayerAgent MLLM | MLLM Δ | 두 축 합의? |
|---|:---:|:---:|:---:|:---:|:---:|
| **dark-glass** (10) | **0.551** | **+0.27** | **4.15** | **+0.12** | ✓ **LayerAgent 우세** |
| pyramid (5) | 0.764 | +0.17 | 1.90 | −1.50 | 불일치 |
| mekko (5) | 0.753 | +0.08 | 2.15 | −1.50 | 불일치 |
| process_flow (5) | 0.818 | +0.06 | 2.30 | −1.60 | 불일치 |
| harvey_table (3) | 0.910 | +0.06 | 2.75 | −0.75 | 불일치 |
| matrix_2x2 (5) | 0.917 | +0.01 | 2.05 | −0.45 | 불일치 |
| waterfall (5) | 0.662 | −0.03 | 2.45 | −0.35 | ✓ **single_pass 우세** |
| line_chart (5) | 0.845 | −0.03 | 2.20 | −0.40 | ✓ **single_pass 우세** |
| bar_chart (5) | 0.733 | −0.09 | 1.90 | −1.10 | ✓ **single_pass 우세** |

(Δ = LayerAgent − best baseline. 양수면 LayerAgent 우세, 음수면 single_pass 우세)

### 5.2 어떻게 읽나

**3가지 패턴**이 보입니다:

1. **dark-glass** (다층 디자인) → 두 축 모두 LayerAgent 우세 = **sweet spot**
2. **bar/line/waterfall** (평면 차트) → 두 축 모두 single_pass 우세 = **분해의 비용이 이득보다 큼**
3. **중간 6개 layout** (pyramid, mekko, harvey_table 등) → **두 축 disagree** — LTED는 LayerAgent를 우세로, MLLM은 single_pass를 우세로 봄

### 5.3 왜 평면 차트에서는 LayerAgent가 지나?

- 평면 차트는 본래 layer가 적음 (예: bar 차트는 그냥 바 + 축 + 라벨)
- LayerAgent는 *기본적으로 layer를 늘리려고 설계됨*
- 평면 디자인을 굳이 다층으로 분해하면 → 오버엔지니어링 → 발표 가능성 하락
- → **layout-conditional routing 필요**: Analyzer가 layout 판별 후 다층이면 LayerAgent, 평면이면 single_pass

### 5.4 honest thesis

> "LayerAgent는 *모든 경우의 SOTA*가 아니라, *다층 디자인에서 PGG를 완화하는 구조적 방법*이다."

이게 이 논문의 가장 중요한 주장. *전체 도메인에서 우월하다*고 주장하지 않고 *sweet spot에서만 효과*라고 명확히 좁힘.

---

## 6. §6.3 — Trivial baseline check

### 6.1 의도

> "LayerAgent의 same-model 우세가 *진짜 분해 효과인지*, 아니면 *단순 prompt 조정으로도 가능한지*?"

이걸 확인하기 위해 **single_pass에 z-index 명시 한 줄만 추가** (`single_pass_zexplicit`).

### 6.2 결과 (N=10, legacy LTED/Recall ⚠)

| Method | LTED ↓ | Layer Recall ↑ | avg layer count |
|---|:---:|:---:|:---:|
| single_pass | 0.823 | 0.224 | (낮음) |
| **single_pass_zexplicit** | 0.844 | 0.292 | 3.8 |
| **LayerAgent** | **0.551** | **0.759** | **8.5** |

### 6.3 어떻게 읽나

- z-explicit prompt: Recall이 0.224 → 0.292로 *살짝* 올라감
- 하지만 LayerAgent의 0.759와는 여전히 큰 차이
- avg layer count(vocabulary 무관): 3.8 vs 8.5

**결론**: prompt에 z-index 한 줄 추가하는 정도로는 LayerAgent와 같은 효과 안 나옴. *분해 자체*가 필요한 메커니즘.

### 6.4 caveat

- 이 표는 legacy LTED/Recall (vocabulary-aligned) 기반 → caveat 적용
- 다만 prompt 변형은 vocabulary와 무관하므로 *방향성*은 robust
- 강한 인과 주장은 Table 1 + ablation과 함께 해석 권고

---

## 7. §6.7 — Ablation (현재 D₂만 측정됨)

### 7.1 D₂ 결과 (legacy N=5)

Text Inserter를 빼면 어떻게 되나?

| 조건 | CCR (텍스트 보존) | CSS Richness | Joint Pass |
|---|:---:|:---:|:---:|
| **D (full)** | **0.78** | **54.4** | **0.6** |
| D₂ (no_text_inserter) | 0.09 | 52.2 | 0.0 |
| Δ | **−0.69** | −2.2 | −0.6 |

### 7.2 어떻게 읽나

Text Inserter를 빼면:
- **CCR이 0.78 → 0.09로 폭락** — 콘텐츠 80%가 누락됨
- CSS Richness는 그대로 — 시각 생성은 영향 없음

**해석**: Card Detail Agent가 시각 생성 *동시에* 텍스트 삽입 부담까지 받으면 → **시각에 attention 분산** → 콘텐츠 누락.

→ **시각 단계와 콘텐츠 단계를 분리하는 것이 효과적**임을 보임.

### 7.3 한계

- legacy N=5 pilot 결과 (정식 N=48 framework 미실행)
- 다른 ablation (D₁ no_style_norm, D₃ no_cv_facts, D₄ no_designspec, D₅ no_library 등) **미수행**
- → `later.md` 참조 (비행 후 D₄ 우선 측정)

---

## 8. §3 — PGG 현상 가시화 (legacy 진단)

### 8.1 perception vs generation layer 수

같은 GPT-4o에게 두 가지 질문:

| 질문 | 결과 |
|---|---|
| 1) "이 이미지의 계층을 자연어로 설명하라" | 5–8개 layer 인식 |
| 2) "이 이미지를 HTML로 변환하라" | 평균 1.6개만 commit (single_pass) |

**같은 모델인데** perception은 layer를 보지만 generation은 평면화.

→ "VLM이 못 본 게 아니라, 봤지만 코드로 옮길 때 잃는다"

이게 PGG 현상의 핵심 motivation.

### 8.2 LayerAgent 효과 (legacy N=10 dark-glass)

| 지표 | single_pass | LayerAgent |
|---|:---:|:---:|
| 평균 layer 수 | 0–4개 | 5–10개 |
| Layer Recall (vocab-aligned ⚠) | 0.195 | 0.676 |
| LTED (vocab-aligned ⚠) | 0.82 | 0.55 |

LayerAgent가 perception이 보장한 5–8 layer 중 평균 5.4개를 commit (single_pass는 1.6개만).

**caveat**: Layer Recall/LTED는 vocabulary-aligned라 절대값은 caveat 적용. 다만 *layer 수 자체*는 vocabulary와 무관하므로 그 비교는 robust.

---

## 9. 메트릭 disagreement (§6.6) — 5축이 서로 다른 답을 줌

### 9.1 같은 데이터에 5축이 다른 ranking

| 축 | Same-model 우승 | Cross-model 우승 |
|---|---|---|
| ① DOM-based 구조 | LayerAgent | GPT-5.4 |
| ② Render-based 시각 유사도 | LayerAgent (CLIP/LPIPS) / single_pass (SSIM) | GPT-5.4 |
| ③ MLLM judge | single_pass | (미측정) |
| ④ Vocabulary-aligned legacy ⚠ | LayerAgent | LayerAgent |
| ⑤ String CCR | LayerAgent | (미측정) |

### 9.2 어떻게 읽나

**결함이 아니라 본질**: 디자인-투-코드 평가는 단일 축으로 환원 불가.

- 픽셀 충실 복제가 중요? → 축 ②
- 편집 가능한 구조 회복이 중요? → 축 ①
- 발표 가능한 슬라이드가 중요? → 축 ③

**use case별 metric selection 권고** — 어느 축이 정답이라고 정하지 말고 *동반 보고*.

---

## 10. 흔한 질문 (FAQ)

### Q1. "LayerAgent가 좋다고 결론 못 내리는 거 아닌가요?"

좋다 vs 안 좋다의 *스펙트럼*이 아니라 **언제 좋고 언제 안 좋은지**를 정직하게 보여주는 논문입니다.

- **좋은 곳**: same-model GPT-4o + 다층 dark-glass → 8개 자동 지표 7개 1위
- **안 좋은 곳**: GPT-5.4 single-pass / 평면 차트 / MLLM judge holistic 차원

### Q2. "GPT-5.4가 더 좋으면 LayerAgent 의미 없는 거 아닌가요?"

아닙니다. 두 가지 이유:

1. **PGG라는 *현상* 자체를 처음 정의·측정**한 논문 — 이건 LayerAgent 효과와 별개의 기여
2. **method contribution**도 *cost-sensitive setting*에서 의미 있음 (Opus보다 절반 비용에 비슷한 fidelity)

### Q3. "MLLM judge에서 졌으니 망한 거 아닌가요?"

망한 게 아닙니다. 오히려:
- 각 메트릭 축이 다른 차원을 측정한다는 *multi-family disagreement*가 본 paper의 RQ3 발견
- LayerAgent는 *편집 가능한 구조 회복*에 정렬된 시스템 (DOM-based ①에 강함)
- 발표 가능성(축 ③)에서의 약점은 *limitations + 향후 연구*로 흡수

### Q4. "Sweet spot에서만 좋다는 게 약점 아닌가요?"

오히려 강점입니다. **layout-conditional routing 권고**가 paper의 운영 권고:
- Analyzer가 layout 판별
- 다층 디자인 → LayerAgent
- 평면 차트 → single_pass

이렇게 두 메서드를 *상보적으로* 운영하는 시스템 설계가 가능. *모든 디자인에 LayerAgent를 강요*하지 않는 게 정직.

### Q5. "그래서 reviewer가 가장 공격할 것 같은 부분?"

세 가지:

1. **Ablation D₂만 측정됨** → `later.md`로 D₄ 추가 측정 권고
2. **MLLM judge 단일 (GPT-5.4)** → cross-judge (Claude/Gemini) 미수행
3. **N=48 통계 검증력** → paired Wilcoxon p<0.05는 sweet spot N=10에서만

→ 전부 §8 한계에 명시되어 있음. reviewer가 짚으면 *"맞다, 향후 연구"*로 답변 가능.

### Q6. "이 논문의 가장 큰 장점은?"

**부정 결과를 정직하게 보고했다는 점**.

- GPT-5.4에 졌다고 인정
- MLLM judge에서 졌다고 인정
- 평면 차트에서 졌다고 인정
- 인과 가설을 가설로만 두고 직접 검증 안 했다고 인정
- ablation 미수행 한계 인정

이렇게 정직한 paper는 *오히려 reviewer가 신뢰*. "이 사람들은 자기 한계를 안다"는 신호.

---

## 11. 한 페이지 요약

| 측면 | 결과 |
|---|---|
| **Same-model 자동 지표 (Table 1, N=10)** | LayerAgent 8개 중 7개 1위 |
| **MLLM judge (Table 1b, N=48)** | single_pass 평균 우세 |
| **Cross-model vs Opus** | LayerAgent 비용 45%·시간 44% 절감, fidelity는 다소 낮음 — cost-sensitive 대안 |
| **Cross-model vs GPT-5.4** | GPT-5.4가 품질·비용 모두 우세 — LayerAgent 우세 미관찰 |
| **Sweet spot (Table 3)** | dark-glass에서만 두 축 합의로 LayerAgent 우세 |
| **평면 차트** | bar/line/waterfall에서는 single_pass가 우세 |
| **Trivial baseline** | prompt engineering으로는 LayerAgent 격차 안 닫힘 |
| **D₂ ablation** | Text Inserter 빼면 콘텐츠 80% 누락 — 단계 분리 효과 입증 |

---

## 12. 한 줄 thesis 다시 — 외우면 좋음

> **"LayerAgent는 모든 경우의 SOTA가 아니라, 다층 디자인에서 PGG를 완화하는 구조적 방법이다."**

이 한 줄이 paper 전체 결과를 요약합니다. 교수님께 설명하실 때도 이 한 줄로 시작하시면 됩니다.

---

비행 잘 하시고, 혹시 비행 중에 더 궁금한 부분 생기면 메모해두세요. 돌아오신 후 보강하겠습니다 ✈️
