# LayerAgent Paper — 평가 방법론과 개념 정리

본 문서는 `paper_draft_ko.md`에 들어있는 평가 protocol과 핵심 개념을 자세히 설명합니다. paper 본문에 분산되어 있는 내용을 한 곳에 모아 reference로 사용할 수 있도록 정리했습니다.

---

## 목차

1. [핵심 개념 — PGG, self-vocabulary scoring, multi-family disagreement, sweet spot](#1-핵심-개념)
2. [Multi-family Evaluation Protocol 전체 구조](#2-multi-family-evaluation-protocol)
3. [축 ① DOM-based Structural Metrics (VEC/EDC/VLC/CRP/HD/SC)](#3-축--dom-based-structural-metrics)
4. [축 ② Render-based Visual Similarity (SSIM/CLIP/LPIPS)](#4-축--render-based-visual-similarity)
5. [축 ③ Multimodal LLM-as-Judge (4 criteria)](#5-축--multimodal-llm-as-judge)
6. [축 ④ Content Completeness (CCR)](#6-축--content-completeness)
7. [Legacy sanity check (Layer Recall, LTED)](#7-legacy-sanity-check)
8. [데이터셋과 비교 메서드](#8-데이터셋과-비교-메서드)
9. [결과 보고 구조 (Table 1~4)](#9-결과-보고-구조)
10. [사전등록 가설 (부록 A)](#10-사전등록-가설)
11. [Ablation flags](#11-ablation-flags)
12. [실험 인프라](#12-실험-인프라)
13. [Limitations](#13-limitations)

---

## 1. 핵심 개념

### 1.1 PGG (Perception–Generation Gap, 지각-생성 간극)

**정의 (paper §3.1)**: PGG는 메트릭 이름이 *아니라* **현상(phenomenon)의 이름**이다.

> 동일 VLM이 슬라이드 이미지로부터 5–8개 layer를 *자연어로 인식*하지만, 같은 이미지를 HTML로 변환할 때는 시각 element와 스타일 계층의 *일부만 코드로 commit*하는 현상.

**왜 메트릭이 아니라 현상으로 정의했나**:
- 메트릭 이름이 곧 현상 이름이 되면 *circular*해짐 ("PGG metric으로 PGG를 정의" 류)
- 본 paper는 PGG를 직접 표적하는 단일 신규 메트릭을 *제안하지 않음*
- 대신 PGG의 정도를 multi-family protocol로 *간접 측정*

**메커니즘 가설 (§7.1, 가설 수준)**:
> 단일 VLM이 전체 슬라이드를 한 호출로 처리할 때, 레이아웃·색·텍스트·아이콘·CSS 재질·z-index·border·shadow·alpha를 모두 *하나의 자기회귀 토큰 시퀀스*로 산출해야 한다. 생성 capacity가 동시에 경쟁하는 상황에서 *없어도 정상 렌더링되는 시각 효과*(`backdrop-filter`, `box-shadow`, multi-layer 등)가 가장 먼저 단순화될 가능성이 높다.

이는 *capacity allocation 문제*로 해석되며, 직접 인과 검증(token budget 외생적 통제 실험)은 향후 작업.

---

### 1.2 Self-vocabulary scoring 위험

**문제 (paper §3.1, §5.3)**:
초기 분석에서 사용한 Layer Recall/LTED는 *generation tree를 class name regex*로 파싱한다. 본 연구의 정규식은 LayerAgent의 class name (`card-wrap`, `bg-base`, `atmos`, `decor`)에 정렬되어 있다.

**결과적 편향**:
- Claude Opus가 사용하는 `glass-card`/`node-inner`/`hub-content` 같은 *시각적으로 풍부한* class name은 정규식에 매칭되지 않음 → frontier에 거짓 negative 보고
- 동일 시각 출력이라도 LayerAgent에 *self-favoring*하는 결과를 만듦

**대응**:
- Layer Recall/LTED는 *main claim에서 강등* → sanity check 용도로만 사용
- main claim은 class-name-independent한 multi-family protocol로 보고

---

### 1.3 Multi-family disagreement

**개념 (paper §1.2, §6.6)**: 동일 데이터에 대해 5개 메트릭 축이 *서로 다른 ranking*을 산출하는 현상.

**예시 (N=48 mixed)**:
- Render-based SSIM: single_pass 0.675 > LayerAgent 0.593
- DOM-based + class-name-aligned legacy (LTED↓, Layer Recall↑): LayerAgent 0.744 / 0.405 > single_pass 0.823 / 0.212
- Multimodal LLM-as-judge: single_pass 3.30 > LayerAgent 2.59

**해석**: 결함이 아니라 *multi-objective 평가의 본질*. 각 축은 다른 use case에 정렬됨:
- 픽셀 충실 복제 (가족 ②)
- 편집 가능한 구조 회복 (가족 ①)
- 발표 가능한 슬라이드 품질 (가족 ③)

---

### 1.4 Sweet spot

**정의 (paper §5.1)**: 본 연구의 시스템 설계 대상으로 정한 *디자인 분포*.

**정성적 정의**: "다크 테마 + 글래스모피즘 + 네온 글로우 + 복합 그라디언트의 다층 레이아웃" (10 dark-glass design subset).

**정량 정의의 부재** (limitation):
- layer 수 threshold, complexity score 등 *객관적 기준은 paper에 명시되어 있지 않음*
- 사실상 dark-glass subset = sweet spot이라는 *데이터셋 정체성*에 의존

**사용 위치**:
- Table 1 (§6.1, N=10 dark-glass)에서 same-model 효과 측정의 기준
- §6.4 sweet spot 통합 분석
- §6.5 per-layout breakdown에서 "두 축이 합의하여 LayerAgent 우세 선언"되는 유일한 layout family

**평면 차트 layout (sweet spot 외)**: bar/line/waterfall에서는 *single_pass 우세*. → layout-conditional routing 권고.

---

### 1.5 N=10 vs N=48 분리 원칙

**원칙 (paper §1.2 L75)**:
- **Table 1 (§6.1, N=10 dark-glass)**: sweet spot에서의 same-model 효과를 multi-family metric으로 보고
- **§1.2·§6.5 (N=48 mixed)**: 평면 차트 포함 layout 일반화 분석

**중요**: 두 데이터셋 절대 수치는 design 분포가 다르므로 *직접 비교가 아니다*.

**예시 차이**:
- N=10 dark-glass SSIM (Table 1): single_pass 0.493, LayerAgent 0.470
- N=48 mixed SSIM (§1.2): single_pass 0.675, LayerAgent 0.593

---

### 1.6 Honest scope

**Framing (paper 초록)**:
> 본 논문의 핵심 기여는 *frontier SOTA 경신*이 아니라 *PGG 현상의 정의와 same-model 조건에서 layer-wise decomposition 효과의 분석*이다.

**구체 범위**:
- LayerAgent의 우위는 (i) same-model GPT-4o 조건 + (ii) 다층 dark-glass sweet spot에서 두 축이 합의하는 범위에 한정
- GPT-5.4 single-pass와 평면 차트 layout에서는 LayerAgent의 우위가 관찰되지 않음
- LayerAgent는 비용이 큰 frontier (Claude Opus 등)에 대한 *cost-sensitive 대안*으로서 의미를 가짐

---

## 2. Multi-family Evaluation Protocol

### 2.1 신규성 위치 (paper §5.3)

> 본 protocol의 *신규성은 기존 metric의 발명이 아니라 기존 render-based 및 DOM-based 평가를 결합하고 class-name-independent하게 정렬하여 method-specific vocabulary bias를 줄인 구성*에 있다.

즉:
- SSIM, CLIP, LPIPS — 기존 표준 메트릭
- VEC/EDC/CRP/HD/SC — DOM computed-style의 plain count 변형 (acronym은 본 논문 측정 convention)
- MLLM-as-judge — WebDevJudge 2025 best practice 채택
- **신규 기여**: 다섯 축을 동반 보고하고, class-name-aligned legacy를 sanity check로 강등한 *protocol 구성*

### 2.2 4 main axes + 1 sanity check 구성

| 축 | 이름 | 코드 | 답하는 질문 |
|---|---|---|---|
| ① | DOM-based Structural Metrics | `experiments/metrics/dom_structure.py` | "코드가 시각적으로 풍부한 element를 만드는가?" |
| ② | Render-based Visual Similarity | `experiments/metrics/visual_similarity.py` | "렌더된 결과가 reference처럼 보이는가?" |
| ③ | Multimodal LLM-as-Judge | `experiments/metrics/single_method_judge.py` | "출력이 발표 가능한 슬라이드인가?" |
| ④ | Content Completeness (auxiliary) | — | "콘텐츠 문자열이 코드에 살아남는가?" |
| Legacy | Class-name-aligned (sanity check만) | `experiments/probing/layer_tree.py` | ⚠ self-vocabulary scoring 위험 |

---

## 3. 축 ① DOM-based Structural Metrics

### 3.1 측정 원리

Playwright로 렌더링한 DOM에 JS injection하여 *모든 가시 element의 computed style + bounding box*를 추출. **Class name이나 사전 정의된 layer label에 의존하지 않으며**, 모든 메서드에 동일하게 적용 (method-agnostic).

### 3.2 메트릭 6개

#### VEC (Visual Element Count) ↑
- **정의**: 비자명 styling을 가진 가시 element 수
- **"비자명 styling" 기준**: 배경 / 테두리 / 그림자 / filter 중 하나라도 보유
- **의미**: 시각적으로 의미 있는 element 개수

#### EDC (Element Diversity Count) ↑
- **정의**: distinct *style fingerprint* 튜플의 가짓수
- **Style fingerprint**: `(bg, border, radius, shadow, backdrop, opacity)`
- **의미**: 카드 간 스타일 다양성. 같은 카드가 반복되면 fingerprint 1개로 카운트.

#### VLC (Visual Layer Count) ↑
- **정의**: distinct *effective z-band* 수
- **계산**: explicit z-index OR DOM depth band 중 효과적 z 범주
- **의미**: 실제 렌더링되는 z-축 계층 수

#### CRP (CSS Rich Properties) ↑
- **정의**: rich CSS property의 *총 사용 횟수*
- **Rich property 예시**: backdrop-filter, multi-shadow, gradient, transform, opacity<1, border-radius
- **의미**: 시각 효과의 누적 풍부성

#### HD (Hierarchy Depth) ↑
- **정의**: 가시 element 중 max DOM nesting depth
- **의미**: 코드 구조의 계층 깊이

#### SC (Spatial Coverage) ↑
- **정의**: 슬라이드 영역 중 가시 element가 차지하는 면적 비율
- **의미**: 화면 활용도

### 3.3 paper 수치 (Table 1, N=10 dark-glass)

| Metric | A. single_pass | B. visual_cot | C. cot_h_rag | D. LayerAgent |
|---|:---:|:---:|:---:|:---:|
| VEC ↑ | 9.1 | 7.3 | 9.8 | **20.9** (2.3×) |
| EDC ↑ | 3.0 | 2.7 | 3.5 | **9.7** (3.2×) |
| VLC ↑ | 1.5 | 1.5 | 2.4 | **2.9** (1.9×) |
| CRP ↑ | 23.6 | 18.3 | 28.1 | **51.5** (2.2×) |
| HD ↑ | 4.9 | 4.8 | 5.5 | **7.0** |

### 3.4 Reproducibility 한계 (paper에 명시 안 됨)

- 정확한 threshold (예: opacity<1, font-size 등)는 코드에 있고 paper에는 prose 정의만
- Style fingerprint binning rule (rgba normalization, border-width quantization)도 마찬가지
- "rich CSS property" 전체 list는 코드 reference로 미루어짐

---

## 4. 축 ② Render-based Visual Similarity

기존 표준 메트릭 그대로 사용.

### SSIM ↑ (Structural Similarity Index)
- **계산**: skimage 라이브러리
- **의미**: local window 기반 픽셀 휘도/대비/구조 유사도
- **특성**: 카드 위치만 비슷해도 점수가 높음. z-index 부재·계층 단순화는 SSIM에 패널티 없이 통과 → single_pass에 유리

### CLIP ↑ (CLIP image embedding cosine similarity)
- **모델**: open_clip ViT-B/32
- **의미**: semantic-level 유사도 (의미적 유사성)
- **표준**: AutoPresent / Design2Code / SlideCoder에서 사용

### LPIPS ↓ (Learned Perceptual Image Patch Similarity)
- **모델**: AlexNet deep feature
- **의미**: perceptual-level distance (인간 perception 흉내)
- **참고**: Zhang et al., CVPR 2018

### Block-Match, Position (도메인 미지원)
- OCR-based 메트릭이지만 다크 + 한국어 + blur 도메인에서 모든 메서드 0
- *도메인 미지원*으로 결과 보고하지 않음

---

## 5. 축 ③ Multimodal LLM-as-Judge

### 5.1 Judge 설정 (paper §5.3)

- **Judge model**: GPT-5.4 (Azure) — generator(GPT-4o)와 다른 model family로 self-evaluation bias 차단 (Zheng et al., 2023)
- **Input**: reference image + generated PNG + generated HTML 처음 3,000자 (tool-grounded)
- **Best practice**: WebDevJudge 2025의 *code+visual modality* 권고 따름
- **Scale**: 1–7점

### 5.2 4 Criteria

#### VF (Visual Fidelity) ↑
- 렌더링 결과가 reference image와 시각적으로 얼마나 유사한가

#### LS (Layer Structure) ↑
- 코드의 계층 구조가 reference의 layer 구조를 얼마나 보존하는가

#### CC (Content Completeness) ↑
- 입력 콘텐츠 텍스트가 *시각적으로 읽힐 수 있게* 표현되었는가
- (string-CCR과 다름 — visual visibility 반영)

#### DQ (Design Quality) ↑
- 슬라이드 자체의 발표 가능성, 폴리시, 균형

### 5.3 paper 수치 (Table 1b, N=48 main_eval)

| Criterion | cot_h_rag | layeragent | **single_pass** | visual_cot |
|---|:---:|:---:|:---:|:---:|
| VF ↑ | 1.73 ± 0.61 | 1.65 ± 0.93 | **2.17 ± 0.69** | 2.08 ± 0.68 |
| LS ↑ | 3.00 ± 0.80 | **3.58 ± 0.96** | 3.46 ± 0.68 | 3.08 ± 0.65 |
| CC ↑ | 3.77 ± 1.69 | 2.35 ± 1.49 | **3.81 ± 1.72** | 3.60 ± 1.51 |
| DQ ↑ | 3.40 ± 0.82 | 2.79 ± 1.01 | **3.75 ± 0.79** | 3.29 ± 0.90 |
| **Average** | 2.97 | 2.59 | **3.30** | 3.02 |

→ **MLLM judge에서는 single_pass가 평균 우세**. LayerAgent는 *Layer Structure 축에서만* 좁게 우세.

### 5.4 Reproducibility 한계

- **Judge prompt 본문이 paper에 없음** — 4 criteria 각각의 정확한 rubric (1점 vs 7점이 무엇을 의미하는지) 미공개
- 가장 큰 reproducibility gap. 향후 부록으로 추가 권고.

---

## 6. 축 ④ Content Completeness (auxiliary)

### CCR (Content Coverage Ratio) ↑
- **정의**: 입력 텍스트가 HTML에 *문자열로* 등장하는 비율
- **계산**: 코드 reference (`experiments/metrics/`)
- **한계**: 시각 가시성 미반영
- **MLLM judge CC와의 차이**:
  - LayerAgent string-CCR = 0.99 (텍스트 *주입*은 됨)
  - LayerAgent MLLM CC = 2.35 (그러나 *시각적으로 읽히지 않음*: overflow, dense 겹침 등)
  - → **string-level 매칭은 시각 가시성을 underdetermine한다** (paper §7.3)

### 향후 — Visual CCR
- Playwright 렌더링 후 OCR로 가시 텍스트 추출 → input 콘텐츠와 매칭
- 현재 OCR이 본 도메인(다크/한국어/blur)에서 무력화
- visual-aware OCR (mPLUG-DocOwl, Florence-2 등) 채택이 선결 과제

---

## 7. Legacy sanity check

⚠ **본 paper의 main claim에 사용되지 않음**. self-vocabulary scoring 위험 때문.

### 7.1 Layer Recall ↑
- **수식**: $\mathrm{Recall} = |\mathrm{types}(T_P) \cap \mathrm{types}(T_G)| / |\mathrm{types}(T_P)|$
- **$T_P$**: VLM이 자연어로 기술한 perception tree
- **$T_G$**: HTML을 class name regex로 파싱한 generation tree
- **27개 canonical type**: paper에서 mention만 됨, 전체 list는 코드 reference만

### 7.2 LTED (Layer Tree Edit Distance) ↓
- **수식**: $\mathrm{LTED} = \sum_k |m_P(k) - m_G(k)| / (\sum_k m_P(k) + m_G(k))$
- **$m_P, m_G$**: (z-band, type) multiset의 element multiplicity
- **범위**: 0 = 동일, 1 = disjoint

### 7.3 사용 한정 위치
- §3.2 (현상 가시화 — perception layer count 비교)
- §6.1c (보조 표)
- §6.3 (prompt 변형 robustness sanity check — *prompt 변형이 vocabulary와 무관하므로 방향성은 robust*)
- §6.4·§6.5 (sweet spot 분석 한 다리 — 다른 다리는 vocab-free MLLM judge)

### 7.4 Class name regex 예시
- LayerAgent: `card-wrap`, `bg-base`, `atmos`, `decor`
- Claude Opus: `glass-card`, `node-inner`, `hub-content` (정규식 매칭 안 됨 → 거짓 negative)

---

## 8. 데이터셋과 비교 메서드

### 8.1 데이터셋 구성 (N=48 mixed)

#### (A) 10 dark-glass design — Sweet spot
다크 테마 + 글래스모피즘 + 네온 글로우 + 복합 그라디언트의 다층 레이아웃.

| # | layout | 구조 | 복잡도 |
|---|---|---|:---:|
| 01 | timeline | 4노드 + 카드 + 네온 라인 | 높음 |
| 02 | dashboard | 3 메트릭 카드 + 차트 | 중간 |
| 03 | comparison_split | 좌우 분할 + VS 배지 + 8카드 | 높음 |
| 04 | pyramid | 3단계 1-2-3 카드 | 중간 |
| 05 | hub_spoke | 중앙 허브 + 6 연결 카드 | 높음 |
| 06 | before_after | 색상 전환 + 변환 | 중간 |
| 07 | feature_grid | 2×3 그리드 + 아이콘 + 태그 | 중간 |
| 08 | roadmap | 5 페이즈 교차 | 높음 |
| 09 | layered_stack | 4층 겹침 + 레인보우 | 매우 높음 |
| 10 | stats_hero | 히어로 숫자 + 4 스탯 카드 | 중간 |

#### (B) 38 consulting-style design — 분포 외 일반화 검증
- **생성**: Gemini 3 Pro Image Preview
- **5종 스타일**: McKinsey blue / BCG green / Bain red / Editorial warm / Minimal white
- **8개 layout 유형**:

| layout | N | 특징 |
|---|:---:|---|
| mekko | 5 | Marimekko 차트 + 카테고리 라벨 |
| matrix_2x2 | 5 | 2x2 사분면 + 축 라벨 |
| waterfall | 5 | bridge bars + connector |
| harvey_table | 3 | row × col + harvey ball cell |
| bar_chart | 5 | bar + value labels |
| line_chart | 5 | trend + data points |
| process_flow | 5 | 단계 + arrow connector |
| pyramid | 5 | 3-tier hierarchy |

### 8.2 비교 메서드 (모두 GPT-4o-2024-08-06, seed=0)

| Code | Method | 접근 |
|---|---|---|
| **A** | `single_pass` | 단일 GPT-4o 호출, 전체 이미지 → HTML |
| **B** | `visual_cot` | 시각 분석(자연어) → 코드 생성 (2-stage) |
| **C** | `cot_h_rag` | Visual CoT + CSS 패턴 RAG (글래스모피즘/네온 레시피) |
| **D** | `layeragent` | **본 연구** — multi-agent full pipeline |

### 8.3 Cross-model 비교 (§6.2)
- single-pass GPT-5.4 (Azure)
- single-pass Claude 4.6 Opus (Bedrock)
- LayerAgent (GPT-4o + 분해)

### 8.4 Trivial baseline (§6.3, sanity)
- `single_pass_zexplicit`: single-pass prompt에 z-index 6-band 명시 한 줄만 추가
- prompt engineering으로 같은 효과가 나오는지 점검 (legacy LTED/Recall 기반)

---

## 9. 결과 보고 구조

### 9.1 Table 매핑

| Table | 위치 | 내용 | N |
|:---:|---|---|:---:|
| **Table 1** | §6.1 | Same-model GPT-4o 비교, 8 자동 지표 | 10 dark-glass |
| **Table 1b** | §6.1 | MLLM judge (GPT-5.4, 4 criteria) | 48 main_eval |
| **Table 1c** | §6.1 | Legacy vocabulary-aligned (sanity check) | 48 main_eval |
| **Table 2** | §6.2 | Cross-model cost-efficiency | 10 dark-glass |
| **Table 3** | §6.5 | 9 layout family per-method × 두 축 | 5–10 per layout |
| **Table 4** | §6.6 | 메트릭 분류학 (5 axes 답하는 질문) | — |

### 9.2 RQ ↔ § 매핑

| RQ | 질문 | 답변 위치 |
|---|---|---|
| **RQ1** | Same-model 분해 효과? | **Table 1** §6.1 |
| **RQ2** | Cross-model cost-efficiency? | **Table 2** §6.2 |
| **RQ3** | 메트릭 축 disagreement? | **Table 4** §6.6 |
| **RQ4** | Layout-dependent sweet spot? | §6.4 + **Table 3** §6.5 |

---

## 10. 사전등록 가설 (부록 A)

### 10.1 채택된 가설

#### H-PGG (지각-생성 간극의 보편성, §3.3) — *vocabulary-aligned 보조 가설로 채택*
- **결정 규칙**: 3 VLM에서 baseline single-pass의 평균 (1 − Layer Recall) ≥ 0.50 AND cross-VLM 표준편차 ≤ 0.10
- **측정 결과**: 3 VLM gap = {0.776, 0.700, 0.688}, std 0.039 (≤ 0.10 ✓)
- **caveat**: vocabulary alignment 영향 가능, frontier 간 비교에 한정

#### H-MetricFamilyDisagree (RQ3, §6.6) — *채택*
- **결정 규칙**: SSIM/LTED/MLLM 우승자가 모두 다름 (또는 최소 2개 ranking 차이)
- **측정 결과**: SSIM=single_pass, LTED=layeragent, MLLM=single_pass — disagreement 확인

#### H-AblationTextInserter (Text Inserter 분리, §6.7) — *채택*
- **결정 규칙**: string-CCR(D) − string-CCR(D₂) ≥ 0.30 AND Layer Recall(D) > Layer Recall(D₂)
- **측정 결과 (legacy N=5)**: string-CCR Δ = 0.69 ✓

### 10.2 부분 채택 / caveat 적용

#### H-SweetSpot (다층 디자인 양 축 합의, §6.4) — *부분 채택*
- LTED Δ = +0.27 (✓, vocab-aligned caveat)
- MLLM Δ = +0.12 (✓, vocab-free)
- 한 다리(LTED)에 vocabulary alignment caveat 적용

#### H-LayoutScaling (Per-layout RQ4, §6.5)
- 9 layout family 중 적어도 5개에서 두 축 부호 일치
- 결과: dark-glass + 평면 차트 4개에서 합의, 5개에서 불일치 → 부분 채택

### 10.3 Sanity check로 강등

#### H-LTED, H-Recall — main claim 미사용
- self-vocabulary scoring 위험으로 §6.1c 보조 표에만 보고

### 10.4 측정 미수행

#### H-AblationDesignSpec (DesignSpec cross-agent 합치, §6.7) — *측정 미수행 / 향후 검증*
- **결정 규칙**: 향후 N=48 multi-family framework에서 D₄ vs D 비교
- **현재 상태**: ablation infrastructure 완료, 정식 측정 미수행
- **`later.md` 참고** — 비행 후 우선 측정 권고 항목

---

## 11. Ablation flags

`layeragent/ablations.py`에 9개 flag 정의 (none + 8 변형).

| Flag | Code reference | 효과 | 측정 상태 |
|---|---|---|---|
| `none` | (default) | full pipeline (baseline) | ✓ |
| `no_text_inserter` (D₂) | `text_inserter.py:92` | Text Inserter skip → Card Detail이 텍스트 처리 | ✓ legacy N=5 |
| `no_style_norm` (D₁) | `style_normalizer.py:162` | Style Normalizer skip → 카드 간 CSS 표류 | ✗ 미수행 |
| `no_cv_facts` (D₃) | `card_detail.py:21`, `hero_detail.py:23` | k-means/OCR/HSV 주입 생략 | ✗ 미수행 |
| `no_designspec` (D₄) | `pipeline.py:69` (구조 분기) | Design Director noop → blackboard 부재 | ✗ 미수행 (later.md 우선) |
| `no_library` (D₅) | `icon_agent.py`, `assembler.py`, `chart_agent.py` | Icon/Pattern/Shape/Connector library 생략 | ✗ 미수행 |
| `no_visual_critic` (D₆) | `visual_critic.py:72` | Visual Critic stage 제외 | (default off) |
| `no_overflow_repair` (D₇) | `overflow_repair.py:219` | Overflow Repair stage 제외 | ✗ 미수행 |
| `no_chart_agent` (D₈) | `pipeline.py:82` | chart_agent를 noop으로 | ✗ 미수행 |

### 11.1 D₂ 측정 결과 (legacy N=5)

| 조건 | CCR ↑ | CSS Richness ↑ | Joint Pass ↑ |
|---|:---:|:---:|:---:|
| **D (full)** | 0.78 | 54.4 | 0.6 |
| D₂ (no_text_inserter) | 0.09 | 52.2 | 0.0 |
| Δ | −0.69 | −2.2 | −0.6 |

→ Text Inserter 제거 시 콘텐츠 약 80% 누락. CSS Richness는 거의 동일 → **시각/콘텐츠 단계 분리가 zero-sum 해소에 기여함을 시사** (legacy N=5).

---

## 12. 실험 인프라

### 12.1 4-stage cacheable 파이프라인 (`experiments/main_eval.py`)

```
Stage 1: Generate
   ↓
Stage 2: Render (Playwright)
   ↓
Stage 3: Reference perception (VLM 캐시)
   ↓
Stage 4: Metrics (DOM, visual similarity, MLLM judge)
```

각 stage는 *재시작 가능* (캐싱).

### 12.2 환경
- Python: 3.x
- LangGraph v1.0.5 (StateGraph)
- Playwright 1.58
- GPT-4o-2024-08-06 (Azure)
- skimage, open_clip, torch (LPIPS AlexNet)

### 12.3 전체 실행
- **4 메서드 × 48 슬라이드 = 192 cell**
- **실행 시간**: 82분
- **생성 실패**: 0건
- **결과 파일**:
  - `results/main_eval/eval_results.jsonl` (192 lines)
  - `results/main_eval/eval_summary.csv`
  - `results/main_eval/analysis_report.md`
- **Render guard**: Playwright 정상 렌더링 비율 100% (전 메서드)

### 12.4 단위 테스트
- `tests/test_smoke.py` — end-to-end smoke test
- 모든 메트릭 코드 `experiments/metrics/` 공개

---

## 13. Limitations (paper §8 정리)

1. **Class-name-aligned legacy metric의 self-vocabulary scoring 문제** — Layer Recall/LTED는 main claim 미사용, sanity check 한정.
2. **Holistic 디자인 quality (축 ③)에서의 부정 결과** — MLLM judge 4-criteria 평균에서 LayerAgent (2.59) < single_pass (3.30). LayerAgent는 *Layer Structure 축* + *dark-glass sweet spot* 으로 한정.
3. **Sweet-spot 외 disagreement** — 6개 중간 layout에서 LTED는 LayerAgent를, MLLM judge는 single_pass를 우세로 본다.
4. **N=48 통계 검증력** — paired Wilcoxon p<0.05는 sweet spot subset(N=10)에서만 유의. 30+ seed × 100+ design 확장이 향후 과제.
5. **Cross-VLM probing의 vocabulary alignment + scope 한계** — class-name-aligned 기반, N=10 dark-glass 한정. Gemini 2.5 등 추가 frontier에서의 multi-family 재현은 향후 작업.
6. **Ablation은 D₂만 정량 측정됨** — 나머지 7개 flag (D₁/D₃/D₄/D₅/D₆/D₇/D₈)는 infrastructure 완료, 정식 측정 미수행. (`later.md`에서 D₄ 우선 측정 권고)
7. **OCR-기반 메트릭 무력화** — Block-Match와 Position이 다크 + 글래스모피즘 + 한국어 + opacity blur 도메인에서 0. visual-aware OCR (mPLUG-DocOwl, Florence-2) 교체가 선결 과제.
8. **단일 LLM judge bias + 인간 평가 부재** — GPT-5.4 단일 judge. Claude/Gemini cross-judge 부재 + 인간 anchor 검증(n≥80 pair × 5 raters) 미수행. WebDevJudge (2025)가 권고하는 cross-judge + human anchor 조합은 향후 과제.
9. **지연 시간** — Multi-agent decomposition + library retrieval로 카드 4개 슬라이드 ~60초 vs single-pass ~8초.
10. **Layer band의 디자인 특수성** — 6 layer band는 다크-글래스 + 글래스모피즘 + 아이콘 배지 미학에 정렬. 텍스트 중심 / 사진 중심 슬라이드에서는 layer band 재정의 필요.
11. **String-CCR vs Visual CCR** — CCR 0.99 vs MLLM CC 2.35 → 메트릭 진화 필요. visual-aware OCR이 선결 과제.

---

## 부록 — Reproducibility 갭 정리

본 paper에 *개념 수준 정의는 모두 있지만* algorithm-level detail이 코드 reference로 미루어진 항목:

| 항목 | 현재 paper 상태 | gap |
|---|---|---|
| VEC threshold (가시성 기준) | "비자명 styling" prose | 정확한 threshold (opacity, size 등) 미공개 |
| EDC fingerprint binning | 튜플 구조만 | rgba normalization, border-width quantization 미공개 |
| VLC effective-z 정의 | "explicit z-index OR DOM depth band" | depth band binning algorithm 미공개 |
| CRP property 전체 list | "backdrop-filter, multi-shadow, ... 등" | 전체 list 미공개 |
| MLLM judge prompt 본문 | model + 4 criteria 이름만 | rubric, system prompt 미공개 (가장 큰 gap) |
| 27 canonical layer type list | 언급만 | list 자체 없음 |
| Class name regex 전체 패턴 | 4개 예시 | 전체 regex 미공개 |
| CCR matching rule | "문자열로 등장하는 비율" | exact vs partial, normalization 미공개 |
| Cost estimation 방법 | 가격만 명시 | input/output 분리, prompt cache 적용 여부 미공개 |
| Sweet spot 정량 정의 | "다크 테마 + 글래스모피즘 ... 다층 레이아웃" prose | layer count threshold, complexity score 미공개 |

→ 향후 부록 C (메트릭 정확한 정의), 부록 D (judge prompt) 추가 권고.

---

## 한 문장 요약

> 본 paper의 평가 protocol은 **DOM-based 구조 지표 (VEC/EDC/VLC/CRP/HD/SC) + render-based 시각 유사도 (SSIM/CLIP/LPIPS) + multimodal LLM-as-judge (4 criteria) + content completeness (CCR)** 4축의 multi-family 동반 보고 구조이며, 신규성은 *기존 metric 발명*이 아니라 *class-name-independent 구성과 다축 disagreement 정직 보고*에 있다. PGG는 메트릭 이름이 아니라 *현상*의 이름이고, 측정은 *capacity allocation 가설* 하에서 multi-family로 간접 수행된다.
