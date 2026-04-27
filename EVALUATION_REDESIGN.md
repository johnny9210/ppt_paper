# 평가 메트릭 재설계 — 작업 로드맵

**문서 작성**: 2026-04-27
**상태**: in-progress
**목적**: 현재 paper의 메트릭 circularity 문제를 해결하고 정량 지표 set을 재설계

---

## 1. 현재 상황 — 무엇이 잘못되었나

### 1.1 발견된 critical issue (사용자가 직접 지적)

**LTED와 Layer Recall은 *layer 구조*를 측정하지 않고, *우리가 만든 LayerAgent의 class name 어휘에 alignment*를 측정.**

근거:
- `experiments/probing/layer_tree.py`의 `_HTML_CLASS_TO_TYPE` regex는 LayerAgent class names(`card-wrap`, `bg-base`, `atmos`, `decor`)에 매칭됨
- Claude Opus의 시각적으로 풍부한 class names(`glass-card`, `node-inner`, `corner-glow-tl`)는 매칭 안 됨
- → LayerAgent가 "자기가 만든 어휘로 자기를 평가" → circular

### 1.2 사용자 직접 시각 검증 (10 design)

| Design | 원본 vs Opus | 평가 |
|---|---|:---:|
| 01 timeline | 미감 차이 (3D→2D), layout 일치 | 부분 일치 |
| 02 dashboard | 거의 1:1 시각 일치 | ✅ |
| 03 comparison | 거의 1:1 시각 일치 | ✅ |
| 04 pyramid | layout 일치, 미감 단순화 | 부분 일치 |
| 05 hub_spoke | 거의 1:1 시각 일치 | ✅ |
| 06 before_after | layout 일치, 미감 단순화 | 부분 일치 |
| 07 feature_grid | 거의 1:1 시각 일치 | ✅ |
| 08 roadmap | 거의 1:1 시각 일치 | ✅ |
| 09 layered_stack | 3D→2D, 구조 일치 | 부분 일치 |
| 10 stats_hero | 거의 1:1 시각 일치 | ✅ |

→ **6/10 거의 1:1, 9/10 layout 일치**. Opus는 시각적으로 매우 충실.

그러나 우리 metric:
- Opus Layer Recall = 0.312 (낮음, "못함")
- Opus LTED = 0.693 (높음, "못함")
- LayerAgent Layer Recall = 0.759 (높음, "잘함")

→ **메트릭이 시각 진실과 정반대 방향으로 보고**. 

### 1.3 영향 받는 paper 주장

| paper claim | 실제 measure 한 것 | 판정 |
|---|---|:---:|
| "PGG는 universal VLM 한계" | "VLM이 *우리 어휘*로 표현 안 함" | ❌ |
| "Frontier model로 자동 해소 안 됨" | "Frontier가 *다른 어휘*를 씀" | ❌ |
| "LayerAgent가 PGG closure" | "LayerAgent가 *자기 어휘*로 자기 평가" | ❌ circular |
| "Cost-efficient quality" | "Vocabulary-aligned 비용 효율" | ❌ |
| "단계 분해는 모델 능력 함수 아님" | measurement artifact 위에 세움 | ❌ |

---

## 2. 외부 paper 평가 방법 조사 결과

### 2.1 PPTAgent / PPTEVAL (EMNLP 2025)
- **3 dim**: Content / Design / Coherence (1-5 scale, GPT-4o judge)
- 인간 평가: 4 명, 250 presentation, **Fleiss κ=0.59**, **Pearson r=0.71**
- vs ROUGE-L (weak), PPL (poor), FID (inadequate)

### 2.2 AutoPresent / SlidesBench (CVPR 2025)
- **Reference-based**: Element matching (max-matching), Content (CLIP), Color (CIEDE2000), Position (Manhattan)
- **Reference-free**: Text/Image/Layout/Color 0-5 scale (GPT-4o)
- 인간 ICC = 73.8–85.3%
- 7K train / 585 test / 310 deck / 10 domain
- *layout divergence 한계 명시 인정*

### 2.3 SlideCoder (EMNLP 2025)
- Execution Success / Local Structural / Global Visual (CLIP+SSIM) / Overall
- 인간 4명, 50 slide each, **Pearson r=0.873, ICC=0.726**

### 2.4 PreGenie (EMNLP Findings 2025)
- Page Design / Page Consistency / Content
- *인간 평가 직접 강조*

### 2.5 Design2Code (NAACL 2025)
- Block-Match, Text, Position, Color, **CLIP**
- 인간 평가 보조

### 2.6 SlideAudit (UIST 2025)
- *automated metric vs holistic human judgment* systematic disagreement 명시
- 우리 paper §6.4 mixed signal과 동일 발견

### 2.7 공통 패턴
1. CLIP score가 표준 시각 fidelity metric
2. 인간 평가 + Pearson/ICC 상관 표준
3. Multi-judge (GPT + Claude + Gemini) 추세 (2025-2026)
4. AutoPresent의 reference-based + reference-free 이중 구조 표준
5. Element matching = bounding box max-matching (vocabulary-free)

→ **우리만 vocabulary regex 사용**. 다른 어떤 paper와도 다른 방식.

---

## 3. 재설계 정량 지표 — 4 Tier

### Tier A — Visual Fidelity (3 metric)
- **A-1. SSIM** ↑ (existing, pixel-level)
- **A-2. CLIP Score** ↑ (NEW, semantic-level, ViT-B/32)
- **A-3. LPIPS** ↓ (NEW, perceptual deep-feature)

### Tier B — Visual Structure (vocabulary-free, replaces LTED/Recall)
- **B-1. VEC** (Visual Element Count) — SAM-based segment count on rendered PNG
- **B-2. EM-IoU** (Element Matching IoU) — AutoPresent style, SAM segments + Hungarian matching
- ~~B-3. VLC (computed z-index)~~ ← reviewer panel: *vocabulary 2.0 위험*, SAM으로 통합

### Tier C — Reference-free Design Quality (NEW)
AutoPresent 4 metric 차용:
- **C-1. Text quality** (legibility, hierarchy)
- **C-2. Image quality** (resolution, proportion)
- **C-3. Layout quality** (alignment, spacing, no overlap)
- **C-4. Color quality** (contrast, harmony)
- 0-5 scale, GPT-4o judge (or cross-judge)

### Tier D — Holistic LLM Judge (cross-judge)
기존 GPT-5.4 4-criteria + Claude 4.6 Opus + Gemini 2.5 추가
- **VF / LS / CC / DQ** × 3 judges
- ICC, Cohen's κ inter-rater
- Position swap debias

### Tier E — Content
- **CCR (string)** existing
- ⚠ visual CCR 별도 필요 (visual-aware OCR)

### Tier F — Efficiency (existing)
- Token, USD cost, latency, render rate

---

## 4. 작업 항목 (priority + cost + time)

### 🔴 Critical (Master's 최소)

#### Item 1 — SAM-based visual element extraction
**목적**: VEC + EM-IoU 구현, vocabulary-free layer count
**산출**:
- `experiments/metrics/sam_segments.py` — SAM 모델 wrapper
- `experiments/metrics/visual_element_count.py` — segment count metric
- `experiments/metrics/em_iou.py` — bbox max-matching IoU
- 기존 PNG 사용 (ref + 4 method × 48 = 240 PNG)

**비용**: 무료 (로컬 SAM)
**시간**: 4-6h
**필수도**: 🔴 reviewer panel 만장일치 critical

#### Item 2 — CLIP + LPIPS 측정
**목적**: 시각 fidelity 표준 metric
**산출**:
- `experiments/metrics/clip_score.py`
- `experiments/metrics/lpips_score.py`
- 4 method × 48 design = 192 pair × 2 metric

**비용**: 무료 (로컬 model)
**시간**: 30분 구현 + 30분 측정
**필수도**: 🔴

#### Item 3 — Multi-seed (3 seed × 4 method × 48)
**목적**: variance 측정, 통계 검증
**산출**:
- 추가 generation: 2 seed × 4 method × 48 = 384 추가
- 모든 metric 재계산

**비용**: ~$25 (LayerAgent 비용 큼)
**시간**: 5h (대부분 generation 시간)
**필수도**: 🔴 reviewer 2 (statistician) 만장일치

#### Item 4 — 통계 검증
**목적**: Bonferroni correction + bootstrap CI + Cohen's d
**산출**:
- `experiments/stats.py` 확장
- 모든 main result 표에 95% CI + p-value

**비용**: 무료
**시간**: 2h
**필수도**: 🔴

### 🟡 Strong (Master's 권장)

#### Item 5 — Reference-free design quality (Tier C)
**목적**: AutoPresent 4 metric 차용
**산출**:
- `experiments/metrics/refree_quality.py`
- 4 method × 48 = 192 cells × 4 criteria = 768 LLM call
- GPT-4o or GPT-5.4 judge

**비용**: ~$5 (judge cost)
**시간**: 3h
**필수도**: 🟡

#### Item 6 — Cross-judge (Claude + Gemini)
**목적**: single-judge bias 제거
**산출**:
- 기존 MLLM judge에 Claude 4.6 Opus + Gemini 2.5 추가
- 192 cells × 2 judge × 4 criteria = 1536 추가 call
- ICC, Cohen's κ 계산

**비용**: ~$10
**시간**: 1h
**필수도**: 🟡

#### Item 7 — 인간 평가 (User confirmed: B는 할거야)
**목적**: 모든 metric의 ground truth anchor
**설계**:
- N=8-10 인간 평가자
- 5-10 design × 4 method = 20-40 pair
- 각 pair: "어느 게 원본과 더 비슷?" + 1-7 score 4 axes (VF/LS/CC/DQ)
- ICC, Krippendorff's α
- Pearson r vs 모든 quantitative metric

**비용**: 무료 (학과 동료)
**시간**: 1-2일 (설계 + 모집 + 실시 + 분석)
**필수도**: 🟡 — *user confirmed*

### 🟢 Standard (탑티어 standard, optional)

#### Item 8 — PPTAgent baseline 직접 실행
**목적**: published system과의 직접 비교
**산출**:
- PPTAgent 실행 (icip-cas/PPTAgent)
- 우리 48 design에서 출력 생성
- 모든 metric으로 측정

**비용**: ~$10
**시간**: 8h (환경 설정 + 디버깅)
**필수도**: 🟢

#### Item 9 — Background chapter + 재현 패키지
**목적**: thesis 표준 (CLIP/LPIPS/SAM 설명)
**산출**:
- thesis Ch2 Background (10-15p)
- Docker 재현 환경
- 모든 metric unit test

**비용**: 무료
**시간**: 1-2일
**필수도**: 🟢

---

## 5. 실행 순서 (권장)

### Day 1 (오늘)
- Item 1 — SAM 구현 (4-6h) ← 가장 중요
- Item 2 — CLIP + LPIPS 측정 (1h)
- Item 4 — 통계 framework (2h)

### Day 2
- Item 3 — Multi-seed generation (5h, 대부분 wait time)
- Item 6 — Cross-judge (1h)
- 모든 metric 재계산 + 통합 표

### Day 3
- Item 5 — Reference-free quality (3h)
- Item 7 — 인간 평가 설계 + 모집 시작

### Day 4-5
- Item 7 — 인간 평가 실시 + 분석
- 통합 분석: metric × method × seed × layout × judge

### Day 6+
- paper 재작성 (Path X or Y 결정)
- (Optional) Item 8 — PPTAgent baseline
- (Optional) Item 9 — Background chapter

---

## 6. paper thesis 결정 — 두 갈래 (after metric 측정)

### Path X — System contribution 유지
조건: **VEC (SAM-based) + EM-IoU + reference-free DQ**에서 LayerAgent 우세 입증
- 입증 시: "LayerAgent는 *vocabulary-free*로도 layer 풍부성 + layout fidelity 우세"
- 미입증 시: contribution 거의 없음

### Path Y — Evaluation methodology paper로 pivot
- *Single metric 신화 부수기* 가 main contribution
- 7 metric × 4 method × 인간 anchor → metric-human alignment heatmap
- LayerAgent는 *case study*
- 안전, 정직, 어떤 결과 나와도 paper 가능

→ **measurement 결과 후 결정**

---

## 7. 결정된 항목 (사용자 confirmed)

- ✅ **인간 평가는 한다** (Item 7)
- ⏳ **정량 지표 set은 재설계** (Item 1, 2, 5 진행 중 결정)
- ⏳ **Path X vs Y는 측정 결과 후 결정**

---

## 8. 다음 즉시 행동

1. SAM 모델 환경 setup 확인
2. Item 1 (SAM-based VEC + EM-IoU) 구현 시작
3. 병렬로 Item 2 (CLIP + LPIPS) 측정
4. 두 측정 결과 도착 후 Path X/Y 가설 검증

---

## 부록 A — 메트릭별 *측정 가능 여부* 체크리스트

| Metric | 코드 있음? | 데이터 있음? | 즉시 측정 가능? |
|---|:---:|:---:|:---:|
| SSIM | ✅ | ✅ | ✅ 측정 완료 |
| CLIP score | ❌ | ✅ (PNG 240개) | 30분 후 |
| LPIPS | ❌ | ✅ | 30분 후 |
| VEC (SAM) | ❌ | ✅ | 4-6h 후 |
| EM-IoU (SAM) | ❌ | ✅ | 위와 동시 |
| Reference-free DQ | ❌ | ✅ | 3h 후 |
| Cross-judge | ❌ | ✅ | 1h 후 |
| Multi-seed | ❌ | 부분 | 5h 후 |
| String CCR | ✅ | ✅ | ✅ 측정 완료 |
| MLLM judge (GPT-5.4) | ✅ | ✅ | ✅ 측정 완료 |

---

## 부록 B — 폐기 대상

- ❌ **LTED** (vocabulary circular) — paper에서 제거 또는 *vocabulary alignment metric*으로 명시 격하
- ❌ **Layer Recall (class name 기반)** — 동일
- ⚠ **Block-Match, Position** (OCR 기반) — 다크/한국어/blur 도메인 무력 — 한계로 명시
- ⚠ **VLC (computed z-index)** — reviewer panel 지적: *vocabulary alignment 2.0 위험* — SAM-based VEC로 통합

---

## 부록 C — 사전 측정값 (현재까지 확보)

### N=10 dark-glass subset

| Method | SSIM | LTED | Layer Recall | MLLM judge avg | Cost/slide |
|---|:---:|:---:|:---:|:---:|:---:|
| single_pass GPT-4o | 0.499 | 0.823 | 0.224 | 3.30 | $0.015 |
| single_pass GPT-5.4 | 0.511 | 0.669 | 0.300 | (N/A) | $0.075 |
| single_pass Claude Opus | 0.505 | 0.693 | 0.312 | (N/A) | $0.421 |
| LayerAgent (GPT-4o) | 0.457 | 0.551 | 0.759 | 2.59 | $0.232 |

**관찰**: SSIM과 PGG metric이 *반대 ranking* — measurement validity issue.

---

**문서 끝** — 이 로드맵을 따라 단계별 실행. 결과에 따라 thesis Path X/Y 결정.
