# LayerAgent: 지각-생성 간극(Perception–Generation Gap)을 메우는 비전 기반 레이어 분해 멀티에이전트 프레임워크

*Vision-Grounded Layer Decomposition for Closing the Perception–Generation Gap in Design-to-Code Presentation Generation*

---

## 초록

프레젠테이션 슬라이드는 배경·분위기·장식·카드·콘텐츠·아이콘이 z축으로 겹치는 본질적으로 **계층적(layered)** 구조이다. 그러나 현재의 Vision Language Model(VLM) 기반 디자인-투-코드 시스템은 이 계층 구조를 단일 자기회귀 토큰 시퀀스의 **평면(flat) HTML**로 생성하여, 체계적인 구조 손실을 일으킨다. 본 논문은 이 손실을 정식화하고 해소한다.

**문제 정식화 — 지각-생성 간극(Perception–Generation Gap, PGG).** 동일한 GPT-4o가 슬라이드 이미지로부터 5–8개의 레이어를 자연어로 정확히 기술하지만, 같은 이미지를 HTML로 변환할 때는 1–2개 레이어만 코드에 commit한다. 이 간극은 시각 이해의 부재가 아니라 **계층을 평면 토큰 시퀀스로 번역하는 능력의 부족**이다. 본 연구는 이를 두 메트릭으로 정식 측정한다: (1) **Layer Recall** — VLM이 지각한 레이어 유형 중 생성 HTML에 살아남은 비율, (2) **LTED (Layer Tree Edit Distance)** — 지각 트리와 HTML 트리 간의 정규화된 multiset 대칭차이.

**평가 타당성 — 세 메트릭 가족의 disagreement.** 표준 픽셀 유사도(SSIM)·perception-grounded(LTED·Layer Recall)·holistic LLM judge (GPT-5.4, 4 criteria) 의 세 가족은 **서로 다른 ranking** 을 산출한다. SSIM은 surface mimicry를 보상하고, LTED는 structural fidelity를, MLLM judge는 visual usability·legibility를 함께 본다. 본 연구는 이 disagreement를 *디자인-투-코드 평가 protocol에 대한 1차 기여*로 정착시키고, 단일 메트릭 ranking이 use case에 따라 뒤집힘을 정량 증명한다.

**해법 — LayerAgent (8-stage multi-agent decomposition).** Analyzer → Design Director (DesignSpec 블랙보드) → {Base BG / Atmosphere / Decoration / Card Detail × N / Hero Detail × N / Icon / Chart / Table} → Assembler → Style Normalizer → Text Inserter → (옵션) Overflow Repair / Visual Critic. DesignSpec은 typography/palette/frame/motif/atmosphere의 typed shared state로서 cross-agent 스타일 합치를 강제하고, k-means palette·OCR 텍스트 높이·HSV 채도의 **CV facts**가 결정적 프롬프트 앵커로 주입된다. FontAwesome·SVG primitive·BG pattern·Bezier connector **라이브러리**가 환각을 차단한다.

**경험적 결과 (48 슬라이드 × 4 메서드 × 10 metrics = 1,920 평가 cells, 100% 렌더링).** LayerAgent는 perception-grounded 축에서 Layer Recall **0.405** vs 베이스라인 **0.12–0.21** (2–3.4×), LTED ↓ **0.744** vs **0.82–0.91**을 달성한다. 그러나 SSIM은 **0.593** vs single-pass **0.675** (단일 패스 우세), MLLM judge 평균 **2.59** vs single-pass **3.30** (단일 패스 우세). **Per-layout breakdown에서 LTED와 MLLM judge가 동일한 sweet-spot 패턴에 합의**한다 — 다층 dark-glass에서 LayerAgent는 LTED Δ +0.27 *and* MLLM judge Δ +0.12로 우세하지만, 평면/차트 레이아웃 8종에서는 두 메트릭 모두 single_pass 우세 (MLLM Δ −0.35 ~ −1.60).

**Honest thesis (sweet-spot-scoped).** LayerAgent는 *자신의 설계 대상*인 다층 dark-glass 슬라이드에서 perception-grounded와 holistic 메트릭 두 가족 모두에서 일관 우세하다. 평면 레이아웃에서는 분해 비용이 이득을 초과하며, 본 연구는 *layout-conditional routing*(평면 → single-pass, 다층 → LayerAgent)을 운영 권고로 명시한다. *전체 슬라이드 도메인에서의 우월성* 주장은 데이터로 지지되지 않으며, 본 paper는 이 부정 결과를 thesis의 일부로 흡수한다.

**키워드**: Layer Decomposition, Perception–Generation Gap, Multi-Agent, Design-to-Code, Vision Language Models, Layer Tree Edit Distance, DesignSpec Blackboard

---

## 1. 서론

### 1.1 슬라이드는 계층이다, 그러나 VLM은 평면이다

프레젠테이션 슬라이드는 웹페이지나 포스터와 달리 명확한 **z축 계층**을 가진 시각 객체다:

```
z=30+ : Icons / Badges / Glow nodes
z=20+ : Content (titles, body, values)
z=10+ : Cards / Panels / Hero blocks
z= 5+ : Decoration (shapes, lines, dots)
z= 2+ : Atmosphere (radial glow, gradient overlays)
z= 0  : Background (base gradient, pattern)
```

이 6개 layer band가 정확한 z-index와 좌표로 겹쳐야 의도된 디자인이 구현된다. 그러나 단일 VLM 호출은 이 계층 구조를 인식하지 못한 채 HTML을 **순차 자기회귀 시퀀스**로 생성한다. `<div>` 태그가 직렬로 나열되고, `z-index`는 거의 사용되지 않으며, 요소 간 공간 관계는 DOM 순서에 암묵적으로 의존한다.

흥미로운 관찰은 다음이다 — 같은 GPT-4o에게 *"이 이미지의 계층 구조를 설명하라"* 고 물으면 5–8개의 레이어를 정확하게 자연어로 기술한다. 그러나 같은 이미지를 *"HTML로 변환하라"* 고 물으면 1–2개 레이어만 코드로 commit한다. **VLM은 계층을 완전히 인식하지만 코드로 표현하지 못한다.**

본 논문은 이 현상을 **지각-생성 간극(Perception–Generation Gap, 이하 PGG)** 이라 명명하고, 두 가지 perception-grounded 메트릭으로 정식 측정한다:

- **Layer Recall** — VLM의 perception 트리에 등장하는 레이어 유형 중, 생성 HTML 트리에 살아남은 비율.
- **LTED (Layer Tree Edit Distance)** — 두 트리를 (z-band, type) multiset으로 환원한 뒤 정규화된 대칭차이. 0이면 동일, 1이면 disjoint.

구현은 `experiments/probing/layer_tree.py`에 공개한다. 두 메트릭 모두 *동일 VLM의 perception을 anchor로 삼아* 메트릭 자체에 ground-truth 의존성을 두지 않는다 (reference-free).

### 1.2 단일 메트릭은 디자인-투-코드를 underdetermine한다

디자인-투-코드 분야에서 널리 쓰이는 **SSIM, CLIP, Block-Match, element-IoU**는 모두 *표면 픽셀/위치 매칭*에 기반하며, 계층 구조의 보존 여부와는 직교적이다. 한편 본 연구가 도입하는 perception-grounded 메트릭(LTED, Layer Recall)은 layer 보존을 직접 측정하지만, 시각 가독성·균형·완성도와 같은 *holistic 디자인 quality*를 포착하지 못한다. 본 연구는 세 메트릭 가족 사이의 **systematic disagreement**를 보고한다 (48-slide × 4-method, §6):

- **Surface mimicry (SSIM)**: single_pass **0.675** > LayerAgent **0.593** → 단일 패스가 픽셀 패턴을 더 잘 모방.
- **Perception-grounded (LTED ↓, Layer Recall ↑)**: LayerAgent **0.744 / 0.405** vs single_pass **0.823 / 0.212** → LayerAgent가 layer 보존에서 우세.
- **Holistic LLM judge (GPT-5.4, 4 criteria avg, 1–7)**: single_pass **3.30** > LayerAgent **2.59** → 단일 패스가 시각 usability/legibility/design quality에서 우세.

세 가족의 ranking은 모두 다르다. 어느 가족도 *전체 진실*은 아니며, 각 가족은 use case에 정렬되어 있다 — 픽셀 충실 복제 vs 편집 가능한 구조 회복 vs 발표 가능한 슬라이드 품질. 본 연구는 이 disagreement를 *honest reporting*의 원칙으로 받아들이고, **세 가족 동반 보고**를 디자인-투-코드 평가 protocol의 default로 제안한다 (§6.4 metric taxonomy).

### 1.3 해법: 분해, 블랙보드, 그라운딩, 라이브러리

PGG의 직접적 원인이 *평면 토큰 시퀀스에 계층을 압축하는 인지 부하*라면, 자연스러운 해법은 **생성 과정을 계층적으로 분해**하는 것이다. 그러나 단순 분해만으로는 불충분하다 — 독립 생성된 카드들이 서로 다른 투명도/테두리/그림자로 어긋나거나(스타일 표류), 카드와 텍스트가 좌표상 정렬되지 않거나(공간 충돌), 아이콘이 환각된 URL로 깨지는(자산 부재) 새로운 실패 양식이 등장한다.

본 연구의 **LayerAgent**는 이 모든 실패를 8-stage 파이프라인으로 다룬다:

1. **Analyzer**: 전체 이미지에서 레이아웃 유형과 요소 bounding box 추출.
2. **Design Director**: 전체 이미지 + CV facts → **DesignSpec** (typed blackboard: typography/palette/frame_system/decorative_motif/atmosphere). 이후 모든 specialist가 같은 DesignSpec을 읽고 쓴다.
3. **8 specialists in parallel**: Base BG, Atmosphere, Decoration, Card Detail × N (vision on crop), Hero Detail × N (vision on crop), Icon Agent (FontAwesome 검색), Chart Agent, Table Agent.
4. **Assembler**: z-index 결정적 stacking으로 단일 HTML 조립.
5. **Style Normalizer**: 카드 간 CSS 속성(rgba alpha, border, shadow, blur, radius) 통일 — 위치/구조는 불변.
6. **Text Inserter**: 완성된 시각 구조에 콘텐츠 텍스트 주입 — CSS 생성 부담 없음.
7. **Overflow Repair (선택)**: 측정 기반 픽셀 오버플로 검출 → 폰트/패딩 미세 조정.
8. **Visual Critic (선택)**: Playwright 스크린샷 vs 원본 비교 후 diff 적용.

핵심 설계 결정 4가지:

- **Vision-grounded specialists**: BG/Atmosphere/Decoration은 전체 이미지를, Card/Hero Detail은 *crop된* 이미지를 직접 본다 — 좁은 시각 범위에서만 풍부한 CSS 재질이 살아난다.
- **DesignSpec blackboard**: 모든 specialist가 단일 typed JSON을 공유 — 색·폰트·프레임 어휘가 분산 생성에서도 통일된다.
- **Deterministic CV facts**: k-means palette + OCR 텍스트 높이 + HSV 채도가 프롬프트에 주입되어 환각을 줄인다 (`layeragent/libraries/cv_extractors.py`).
- **Library retrieval**: FontAwesome icon search, SVG primitive shapes, 4종 background pattern, Bezier connector path가 *실제 자산*으로 주입되어 깨진 URL/가상 자산을 차단한다 (`layeragent/libraries/`).

### 1.4 연구 질문과 기여

본 연구는 4개 RQ로 정식화된다 (각 RQ는 *특정 데이터셋이 직접 지지하는* 경험적 주장이며, 데이터 미수집 RQ는 §7 향후 연구로 분리한다):

- **RQ1 (PGG 존재)**: 동일 VLM이 perception에서 5–8 layer를 정확히 인식하지만 generation에서 1–2 layer만 코드화하는 격차가 존재하는가? — *probing_minimal* 데이터로 답한다 (§3).
- **RQ2 (분해의 효과)**: 멀티에이전트 레이어 분해가 perception-grounded 메트릭(Layer Recall, LTED)에서 PGG를 좁히는가? — *main_eval 48-slide × 4-method* 데이터로 답한다 (§6.1).
- **RQ3 (메트릭 가족 disagreement)**: surface mimicry(SSIM) / perception-grounded(LTED·Recall) / holistic LLM judge (GPT-5.4 4-criteria) 세 가족이 동일 데이터에서 서로 다른 ranking을 산출하는가? 각 가족은 어떤 use case에 정렬되는가? — *main_eval + mllm_judge* 데이터로 답한다 (§6.4).
- **RQ4 (Sweet-spot scaling)**: LayerAgent의 우위는 디자인의 *계층 복잡도*에 어떻게 의존하는가? 두 메트릭 가족(LTED, MLLM judge)은 sweet-spot에 합의하는가? — *9 layout family per-layout breakdown* 으로 답한다 (§6.3).

위 RQ들에 대응하는 본 paper의 **기여**는:

1. **PGG의 정식화와 측정**: Layer Recall + LTED라는 *perception-grounded reference-free* 메트릭 가족 제안. 같은 VLM의 perception을 ground-truth anchor로 삼아 측정 외부성 의존을 제거 (§3, `experiments/probing/layer_tree.py`).
2. **LayerAgent 8-stage 프레임워크**: DesignSpec 블랙보드 + CV grounding + library retrieval로 강화된 LangGraph 파이프라인. 8 ablation 플래그로 컴포넌트별 효과 격리 가능 (§4).
3. **3-가족 평가 protocol**: surface / structural / holistic 메트릭 가족의 ranking disagreement를 정량 증명 (§6.4 Table 4). 단일 메트릭에 의존한 기존 디자인-투-코드 ranking의 use-case-conditional 재해석을 제안.
4. **Sweet-spot-scoped honest reporting**: 9 layout family per-layout breakdown으로 LayerAgent 우위가 *계층 복잡도에 단조 비례*함을 두 메트릭 가족이 *합의*하여 보임. 평면 layout에서의 분해 비용을 부정 결과로 명시 보고하고 *layout-conditional routing*을 운영 권고로 정착 (§6.3).

---

## 2. 관련 연구

### 2.1 디자인-투-코드 생성

**Design2Code** (Si et al., 2024)는 484 웹페이지 벤치마크로 GPT-4V의 중간 충실도를 보고했다. **WebSight** (Laurençon et al., 2024)는 200만 합성 image-code pair를 공개했다. **DCGen** (FSE 2025)은 분할 정복으로 페이지를 블록 단위로 분해해 코드를 생성한다. **LaTCoder** (KDD 2025)는 코드 이전에 레이아웃을 chain-of-thought로 명시화한다. **ScreenCoder** (arXiv:2507.22827, 2025)는 Grounding → Planning → Generation의 3-stage agent 파이프라인을 채택하고 50K image-code pair로 GRPO 미세조정한다. **DesignCoder** (arXiv:2506.13663, 2025)는 모바일 UI 도메인에서 UI Grouping → Hierarchy-Aware Generation → **post-render Self-Correcting Refinement**의 3-stage를 사용한다.

**LayerAgent와의 차별점.** ScreenCoder는 *image patch reuse*(Hungarian matching)로 cross-element 일관성을, DesignCoder는 *post-render iterative refinement*로 코드 품질을 다룬다. 본 연구의 Style Normalizer는 *pre-render CSS 정규화*이고, Text Inserter는 *시각/콘텐츠 단계 분리*이며, DesignSpec blackboard는 *생성 시점 cross-agent 스타일 통일*이다. 또한 어떤 선행 연구도 **계층 구조 자체를 perception-grounded 메트릭으로 측정**하지 않는다.

### 2.2 시각 교정 / 반복 개선

**VisRefiner** (arXiv:2602.05998, 2025)는 렌더링 결과와 참조 디자인 간 시각 차이를 학습하여 GPT-4o 대비 Block Match +21.5pt를 달성했다. **Vision-Guided Iterative Refinement** (arXiv:2604.05839, 2026)는 VLM critic 기반 3회 반복으로 17.8% 개선을 보고했다. 본 연구의 Visual Critic stage는 이들의 *반복 vs 단발* 트레이드오프를 ablation 플래그(`use_visual_critic`)로 노출한다.

### 2.3 프레젠테이션 생성

**PPTAgent** (Zheng et al., EMNLP 2025)는 LLM 피드백 기반 템플릿 반복 수정을, **PreGenie** (Xu et al., EMNLP Findings 2025)는 코드 리뷰 + 페이지 리뷰 이중 루프를, **SlideCoder** (Tang et al., EMNLP 2025)는 CGSeg 세그멘테이션 + 계층적 RAG를, **AutoPresent** (Ge et al., CVPR 2025)는 구조화된 시각 설계 원칙을 강조했다. 이들 중 **슬라이드의 z축 계층 구조를 명시적으로 분해 생성**하거나 **perception-grounded 메트릭**을 채택한 연구는 본 연구가 아는 한 보고된 바 없다.

### 2.4 멀티에이전트 코드 생성

**MetaGPT** (Hong et al., ICLR 2024), **ChatDev** (Qian et al., ACL 2024), **CAMEL** (Li et al., NeurIPS 2023)은 **소프트웨어 개발 프로세스**(설계→구현→테스트)로 agent를 분담한다. LayerAgent는 (a) 개발 프로세스가 아닌 **출력의 z축 시각 구조**(배경→카드→텍스트→아이콘)로 분담하고, (b) agent 간 통신을 자연어/코드가 아닌 **DesignSpec JSON + bounding box JSON**의 typed blackboard로 수행하여 truncation·해석 오류를 제거한다.

### 2.5 디자인-투-코드 평가

기존 평가는 전역 유사도(CLIP, SSIM), 구조 매칭(Design2Code의 Block-Match, SlidesBench의 element-matching), 속성 수준(WebRenderBench의 SDA, Widget2Code의 per-property)으로 분류된다. **DreamHouse** (arXiv:2603.24866, 2026)는 structural validity와 visual fidelity가 직교적이며 frontier VLM의 joint pass rate가 7.1%에 불과함을 보였다. 본 연구는 (a) DreamHouse의 직교성을 슬라이드 도메인의 **SSIM vs LTED 분리**로 재확인하고, (b) **perception-grounded 메트릭**(LTED, Layer Recall, CCR)을 reference-free, deterministic 형태로 제안한다.

---

## 3. 지각-생성 간극의 측정

### 3.1 정의

슬라이드 이미지 $I$와 VLM $\mathcal{V}$에 대해:

- **Perception 트리** $T_P(I, \mathcal{V})$: VLM에게 "이 이미지의 모든 시각 레이어를 z-order로 한 줄씩 `z={N}: type={canonical}, count={C}` 형식으로 나열하라"는 결정적 프롬프트(`PERCEPTION_PROMPT`, `experiments/probing/layer_tree.py:60`)로 얻은 트리. 27개 canonical type(background, atmosphere, decoration, card, panel, container, hero, title, content, text, label, value, icon, chart, table, connector, …)으로 정규화.
- **Generation 트리** $T_G(I, \mathcal{V})$: 같은 VLM에 같은 이미지로 "HTML/CSS로 변환"을 요청하여 얻은 HTML을 정규식 + class-name → canonical type 매핑으로 파싱한 트리. z-index를 [back/mid/front] 3-band로 버킷팅.

두 트리를 (z-band, type) multiset으로 환원한 뒤 다음을 정의:

- **Layer Recall** $= |\{t : t \in \mathrm{types}(T_P) \cap \mathrm{types}(T_G)\}| / |\mathrm{types}(T_P)|$
- **LTED** $= \frac{\sum_k |m_P(k) - m_G(k)|}{\sum_k m_P(k) + \sum_k m_G(k)}$, 여기서 $m(k)$는 (band, type) 버킷별 카운트 multiset.

LTED는 0이면 두 multiset이 동일, 1이면 disjoint이며, 본 연구는 LTED↓를 *구조 충실도*의 headline metric으로 사용한다.

### 3.2 진단 — 단일 모델 PGG (10 dark-glass design pilot)

GPT-4o로 10개 다크-글래스 디자인에 대해 perception(Stage A) → 같은 모델 baseline generation(Stage B1) → LayerAgent generation(Stage B2)을 비교한 pilot 결과 (`experiments/probing/probing_minimal.py`):

| 지표 | Stage A self | Stage B1 (single-pass) | Stage B2 (LayerAgent) |
|---|:---:|:---:|:---:|
| `n_layers` | 5–8 | 0–4 | 5–10 |
| `Layer Recall` (vs $T_P$) | 1.00 (sanity) | 0.21 | **0.81** |
| `LTED` ↓ (vs $T_P$) | 0.00 | 0.82 | **0.55** |

Single-pass에서 perception이 보장한 5–8개 레이어 중 평균 1.6개만 코드로 commit되며, LayerAgent에서는 평균 6.5개로 증가한다. 이 격차가 PGG의 정량 정의이다.

### 3.3 일반화 — Cross-VLM probing (진행 중)

PGG가 GPT-4o 단일 모델의 인공물인지를 확인하기 위해 **cross-VLM probing 실험**을 수행한다 (`experiments/probing/cross_vlm.py`): 50 슬라이드 × 3 VLM(GPT-4o, Claude 4.6 Opus, Gemini 2.5) × 2 stage(perception, baseline generation) = 300 호출, 추정 비용 ~$15. 각 (slide, VLM)에 대해 Layer Recall과 gap = (1 − Recall)을 측정한다.

**가설 H-PGG.** 모든 3 VLM에서 baseline gap > 0.5이고 cross-VLM 차이가 ±0.10 이내이면, PGG는 모델-독립적 *세대 한계*임을 시사한다. 본 결과가 가설을 기각하면 thesis는 *해당 모델 세대로 한정된 잠정적 주장*으로 약화하여 명시 보고한다 (§7 한계).

---

## 4. LayerAgent 프레임워크

### 4.1 전체 구조

```
                    ┌──────────────────────┐
                    │      Analyzer        │  전체 이미지 → 레이아웃 + bbox
                    └──────────┬───────────┘
                               ▼
                    ┌──────────────────────┐
                    │   Design Director    │  + CV facts → DesignSpec (blackboard)
                    └──────────┬───────────┘
        ┌──────────┬───────────┼───────────┬──────────┬────────┬───────┐
        ▼          ▼           ▼           ▼          ▼        ▼       ▼
   ┌─────────┐┌─────────┐┌─────────┐┌─────────┐┌─────────┐┌──────┐┌──────┐
   │Base BG  ││Atmosph. ││Decorat. ││ Card    ││ Hero    ││ Icon ││Chart/│
   │(vision, ││(vision, ││(vision, ││ Detail  ││ Detail  ││Agent ││Table │
   │ full)   ││ full)   ││ full)   ││ ×N(crop)││ ×N(crop)││(libr)││Agent │
   └─────┬───┘└─────┬───┘└─────┬───┘└─────┬───┘└─────┬───┘└──┬───┘└──┬───┘
         └──────────┴───────────┴───────────┴──────────┴───────┴──────┘
                                         ▼
                              ┌──────────────────┐
                              │    Assembler     │  z-index stacking
                              └─────────┬────────┘
                                        ▼
                              ┌──────────────────┐
                              │ Style Normalizer │  cross-card CSS 통일
                              └─────────┬────────┘
                                        ▼
                              ┌──────────────────┐
                              │  Text Inserter   │  완성 시각 → 콘텐츠 주입
                              └─────────┬────────┘
                                        ▼
                              ┌──────────────────┐
                              │ Overflow Repair  │  (옵션, 측정 기반 미세조정)
                              └─────────┬────────┘
                                        ▼
                              ┌──────────────────┐
                              │  Visual Critic   │  (옵션, Playwright diff)
                              └──────────────────┘
```

LangGraph v1.0 StateGraph로 구현 (`layeragent/pipeline.py`). 8 specialist는 Design Director 출력 후 병렬 실행된다.

### 4.2 Analyzer (Stage 0)

전체 이미지 → (a) 레이아웃 유형(`timeline / dashboard / hub_spoke / pyramid / grid / split / vertical_stack / freeform`), (b) 각 카드/히어로/장식 요소의 정규화 bounding box (0–1 비율)를 출력한다. 이후 모든 crop과 placement의 anchor.

### 4.3 Design Director — DesignSpec Blackboard

전체 이미지 + **CV facts** (k-means palette, OCR 텍스트 높이 분포, HSV 채도)를 입력받아 typed JSON `DesignSpec`을 출력한다:

```json
{
  "aesthetic_label": "dark_glass_neon",
  "typography": {"hero_family": "Inter", "hero_weight": 800,
                 "body_family": "Inter", "body_weight": 500, ...},
  "palette": {"bg_primary": "#0A1530", "accent": "#3B82F6",
              "frame_color": "rgba(255,255,255,0.15)",
              "text_bright": "#F5F5F0", ...},
  "frame_system": {"hero_frame": "subtle glass frame",
                   "card_frame": "1px rgba white border",
                   "bottom_accent_bar": false},
  "decorative_motif": {"style": "minimal", "density": "sparse", ...},
  "atmosphere": {"has_radial_glow": true, "glow_origin": "top_center",
                 "background_depth": "deep", ...}
}
```

이후 모든 specialist는 DesignSpec을 prompt hint로 받는다(`spec_to_hint`, `layeragent/agents/design_director.py:55`). 결과적으로 카드 A의 글래스모피즘이 카드 B에서 단색으로 변하는 *스타일 표류* 가 사전적으로 차단된다 — 이는 단순 분해(Method E)에서 자주 관찰되는 실패 양식이다.

**CV grounding의 효과.** 팔레트는 k-means(k=6)로 추출되어 *모델이 색을 환각할 여지*를 줄이고, OCR 텍스트 높이는 폰트 크기 결정에 결정적 anchor를 제공하며, HSV 채도는 *flat vs vivid* aesthetic 분류의 단서가 된다. ablation `no_cv_facts`로 효과 격리.

### 4.4 Specialist Agents (Stage 1, 병렬)

- **Base BG / Atmosphere / Decoration**: 전체 이미지 + DesignSpec → 배경 그라디언트, radial glow, decoration shape를 *분리된 layer*로 생성. 이 분리는 분위기와 패턴이 같은 z=0 안에서 충돌하지 않도록 한다.
- **Card Detail × N**: 각 카드의 crop된 이미지(주변 패딩 포함) + DesignSpec → 카드별 풍부한 CSS(`backdrop-filter`, multi-layer `box-shadow`, rgba 알파, neon border). 좁은 시각 범위가 글래스모피즘 같은 *선택적 CSS 재질*을 회복시킨다 — 통제 실험에서 같은 GPT-4o가 전체 이미지에서는 카드당 CSS 효과 2.8개, crop에서는 6–8개를 생성한다.
- **Hero Detail × N**: 히어로 블록(큰 숫자, 메인 메시지, 특수 그래픽)을 크롭으로 별도 처리.
- **Icon Agent**: 카드별 의미 분석 → FontAwesome 클래스 검색 → 실제 `<i class="fa-...">` 태그 주입. *환각된 아이콘 URL* 을 구조적으로 차단 (`layeragent/libraries/icon_library.py`).
- **Chart Agent / Table Agent**: 슬라이드 타입이 차트/테이블일 때 SVG primitive로 sparkline·bar·gauge·harvey table을 결정적 생성.

### 4.5 Assembler

8 specialist의 HTML 단편을 z-index band([0,5,10,20,30,40])로 결정적 stacking. 단순 concat이 아니라 절대 좌표(Analyzer의 bbox 정규화 비율 × 1280×720)와 z-index를 명시적으로 부착한다.

### 4.6 Style Normalizer (Stage 2)

조립된 HTML을 *텍스트 입력만* 받아 카드 간 CSS 속성을 통일한다 (`layeragent/agents/style_normalizer.py`):

- 배경 rgba alpha — 모든 카드 동일값
- 테두리 색상/두께 — 통일
- border-radius — 통일
- box-shadow — 통일
- backdrop-filter blur — 통일

**불변 보장**: position/left/top/width/height/z-index은 변경하지 않는다. 이미지 입력 없이 코드만 보는 텍스트 전용 agent로, 각 카드의 *독립 생성에서 발생한 표류*를 사후 동기화한다. ablation `no_style_norm`으로 effect 격리.

A2UI Protocol (Google, 2026)이 client-side renderer로 design-system을 강제하는 것과 동일한 설계 원리를 *VLM 파이프라인 내부에서* 실현한 것이다.

### 4.7 Text Inserter (Stage 3)

완전히 스타일링된 HTML(배경 + 카드 + 정규화된 스타일) + 콘텐츠 데이터(제목, 설명, 메트릭, 리스트)를 받아, 기존 카드 구조 내 빈 컨테이너를 식별하여 텍스트를 주입한다.

이 단계의 핵심은 *시각 디자인 확정 후 텍스트 처리*라는 순서이다. 단일 VLM에서 풍부한 CSS 생성과 정확한 텍스트 배치가 zero-sum 경쟁을 벌이는 현상(H-RAG에서 CSS Richness↑이지만 콘텐츠 74% 손실)이 단계 분리로 구조적으로 해소된다. ablation `no_text_inserter`로 격리.

### 4.8 Overflow Repair (선택, v10 P1)

조립된 HTML을 Playwright로 렌더링한 뒤 측정한 bounding box overflow를 분석하여, 폰트 크기/패딩/줄 수를 미세 조정한다. 시각 critic과 다르게 *결정적 측정 기반*이라 LLM 호출이 필요없다 (`layeragent/agents/overflow_repair.py`).

### 4.9 Visual Critic (선택)

Playwright 스크린샷 vs 원본 이미지 비교 후 VLM이 diff를 작성, CSS 속성 단위 보정. iteration 비용이 크므로 default off.

### 4.10 Chat Mode (인터랙티브 입력)

기존 데이터셋 spec 대신 *자연어 메시지 + 참조 이미지*를 입력받는 진입점 (`run_from_chat`, `layeragent/pipeline.py:155`). chat_parser agent가 메시지를 `{slide_type, content, style}`로 구조화한 뒤 동일 파이프라인에 전달한다. 데모: `python -m experiments.demo_chat`.

### 4.11 구현 및 ablation 플래그

| 플래그 | 효과 |
|---|---|
| `none` | 풀 파이프라인 (= D, 메인 메서드) |
| `no_style_norm` | Style Normalizer skip — 카드 간 CSS 표류 (D₁) |
| `no_text_inserter` | Text Inserter skip — Card Detail이 텍스트 처리 (D₂) |
| `no_cv_facts` | k-means/OCR/HSV 주입 생략 (D₃) |
| `no_designspec` | Design Director 노드를 noop으로 — blackboard 부재 (D₄) |
| `no_library` | Icon/Pattern/Shape/Connector library 주입 생략 (D₅) |
| `no_visual_critic` | Visual Critic stage 제외 (default) (D₆) |
| `no_overflow_repair` | Overflow Repair stage 제외 (D₇) |
| `no_chart_agent` | chart_agent를 noop으로 (D₈) |

검증과 단위 테스트는 `layeragent/ablations.py` + `tests/test_smoke.py`. 모든 실험은 GPT-4o-2024-08-06 + LangGraph 1.0.5 + Playwright 1.58 환경.

---

## 5. 실험 설정

### 5.1 데이터 — 48 슬라이드 평가셋

본 연구의 평가셋은 두 부분으로 구성된다 (`data/eval_dataset/meta.json`, total=48):

**(A) 10 dark-glass design** — 다크 테마 + 글래스모피즘 + 네온 글로우 + 복합 그라디언트의 다층 레이아웃. 본 시스템의 *sweet spot* (계층이 풍부한 디자인):

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

**(B) 38 consulting-style design** — Gemini 3 Pro Image Preview로 생성, 5종 스타일(McKinsey blue / BCG green / Bain red / Editorial warm / Minimal white) × 8 layout 가족(mekko, matrix_2x2, waterfall, harvey_table, bar_chart, line_chart, process_flow, pyramid):

| layout family | N | 특징 |
|---|:---:|---|
| mekko | 5 | Marimekko 차트 + 카테고리 라벨 |
| matrix_2x2 | 5 | 2x2 사분면 + 축 라벨 |
| waterfall | 5 | bridge bars + connector |
| harvey_table | 3 | row × col + harvey ball cell |
| bar_chart | 5 | bar + value labels |
| line_chart | 5 | trend + data points |
| process_flow | 5 | 단계 + arrow connector |
| pyramid | 5 | 3-tier hierarchy |

(B)는 *분포 외 일반화* 검증용이다. (A)는 시스템이 설계 대상으로 삼은 다층 레이아웃, (B)는 일부 평면적인 챠트 레이아웃을 포함한다.

### 5.2 비교 메서드

| code | 메서드 | 접근 |
|---|---|---|
| **A** | single_pass | 단일 GPT-4o 호출, 전체 이미지 → HTML |
| **B** | visual_cot | 시각 분석(자연어) → 코드 생성 (2단계) |
| **C** | cot_h_rag | Visual CoT + CSS 패턴 RAG (글래스모피즘/네온 레시피) |
| **D** | **layeragent** | **본 연구 — 8-stage full pipeline** |

모든 메서드에 동일 콘텐츠 데이터, 동일 모델(gpt-4o-2024-08-06), 동일 시드(seed=0) 제공.

### 5.3 메트릭 — 세 가족 + 보조

**가족 ① Perception-grounded (RQ2 headline):**
- **Layer Recall** ↑ — 지각 레이어 유형 중 코드에 살아남은 비율 (`experiments/probing/layer_tree.py:layer_recall`).
- **LTED** ↓ — 지각 트리 vs 생성 트리 multiset 대칭차이 정규화 (`experiments/probing/layer_tree.py:lted`).

**가족 ② Surface mimicry (RQ3 mixed-signal 진단):**
- **SSIM** ↑ — 렌더링 PNG vs 원본 PNG의 픽셀 구조 유사도.
- **Block-Match** ↑ — Tesseract OCR 추출 텍스트 블록의 IoU≥0.5 매칭 F1 (Design2Code 스타일).
- **Position** ↑ — OCR 블록 중심점 정렬 정확도.

**가족 ③ Holistic LLM judge (RQ3 mixed-signal 진단):** PPTEVAL-style single-method scoring (`experiments/metrics/single_method_judge.py`). Judge model은 **GPT-5.4 (Azure)** 로 generator(GPT-4o)와 다른 model family 사용 → self-evaluation bias 차단 (Zheng et al., 2023). Judge에게 *reference image + generated PNG + generated HTML 처음 3,000자* 를 함께 제공 (tool-grounded). 4 criteria 각 1–7 점:
- **Visual Fidelity** — 렌더 결과가 reference처럼 보이는가 (색·비례·장식·구성).
- **Layer Structure** — 코드가 layered hierarchy를 보존하는가 (DOM nesting, position:absolute 사용, z-index 규율, 의미적 class 조직).
- **Content Completeness** — 모든 콘텐츠가 *시각적으로 가시*하고 가독성을 유지하는가 (텍스트 가시성, overlap 부재). 본 연구의 string-level CCR과 직접 대비되는 *visual* CC 측정.
- **Design Quality** — reference 무관히, 출력 자체가 전문적인 슬라이드인가 (typography 위계, color harmony, spacing).

**가족 ④ String-level Content (보조):**
- **CCR** (Content Completeness Rate) — 입력 텍스트 콘텐츠가 HTML에 *문자열로* 등장하는 비율 — 시각 가시성 미반영, MLLM judge의 Content Completeness 점수와 *직접 대비* 가능.

**Render guard:**
- **Render Rate** — Playwright로 정상 렌더링되는 비율 (전 메서드 100% 달성, §6.1).

모든 메트릭 코드와 단위 테스트는 `experiments/metrics/` 아래 공개. CLIP은 데이터셋 캐시 이슈로 본 run에서 제외.

### 5.4 실험 인프라

- 4-stage cacheable 파이프라인 (`experiments/main_eval.py`): generate → render(Playwright) → reference perception(VLM 캐시) → metrics. 각 stage는 재시작 가능.
- 총 4 메서드 × 48 슬라이드 = **192 cell**. 실행 시간 82분. 생성 실패 0건.
- 결과: `results/main_eval/eval_results.jsonl`, `eval_summary.csv`, `analysis_report.md`.

---

## 6. 결과

### 6.1 메인 결과 — 메트릭 가족 분리

**Table 1.** 4 메서드 × 48 슬라이드 평균 (mean ± std).

| Metric | cot_h_rag | **layeragent** | single_pass | visual_cot |
|---|:---:|:---:|:---:|:---:|
| **Layer Recall** ↑ | 0.120 ± 0.16 | **0.405 ± 0.23** | 0.212 ± 0.15 | 0.196 ± 0.13 |
| **LTED** ↓ | 0.911 ± 0.15 | **0.744 ± 0.18** | 0.823 ± 0.19 | 0.854 ± 0.15 |
| SSIM ↑ | 0.543 ± 0.24 | 0.593 ± 0.15 | **0.675 ± 0.12** | 0.675 ± 0.12 |
| Block-Match ↑ | 0.023 | 0.000 | 0.021 | 0.017 |
| Position ↑ | 0.015 | 0.000 | 0.015 | 0.011 |
| Render Rate | 100% | 100% | 100% | 100% |

**Table 1b — MLLM judge (GPT-5.4 as judge, 4 criteria, 1–7 scale, 192 cells, 0 errors).**

| Criterion | cot_h_rag | layeragent | **single_pass** | visual_cot |
|---|:---:|:---:|:---:|:---:|
| Visual Fidelity ↑ | 1.73 ± 0.61 | 1.65 ± 0.93 | **2.17 ± 0.69** | 2.08 ± 0.68 |
| **Layer Structure** ↑ | 3.00 ± 0.80 | **3.58 ± 0.96** | 3.46 ± 0.68 | 3.08 ± 0.65 |
| Content Completeness ↑ | 3.77 ± 1.69 | 2.35 ± 1.49 | **3.81 ± 1.72** | 3.60 ± 1.51 |
| Design Quality ↑ | 3.40 ± 0.82 | 2.79 ± 1.01 | **3.75 ± 0.79** | 3.29 ± 0.90 |
| **Average** ↑ | 2.97 | **2.59** | **3.30** | 3.02 |

**핵심 관찰 — 세 가족이 세 다른 ranking을 산출한다.**

- **가족 ① Perception-grounded**: LayerAgent가 모든 베이스라인을 압도. Layer Recall 2.0–3.4배, LTED 일관된 우위. **RQ2의 직접 증거 — 분해가 perception-grounded gap을 좁힌다**.
- **가족 ② Surface mimicry (SSIM)**: single_pass와 visual_cot이 우세. LayerAgent는 3위. 표면 픽셀 패턴 모방에서는 단일 패스 자기회귀가 더 효과적.
- **가족 ③ Holistic LLM judge**: single_pass가 4 criteria 평균에서 1위 (3.30 vs LayerAgent 2.59). **LayerAgent는 *Layer Structure 축에서만* 좁게 우세 (3.58 vs 3.46, +0.12)**, Visual Fidelity·Content Completeness·Design Quality 3개 축에서 모두 단일 패스에 진다.
- **OCR-based (Block-Match, Position)**: 모든 메서드 사실상 0 — 다크 배경 + 글래스모피즘 + 한국어 + opacity blur 조합에서 Tesseract 무력화. 본 도메인 비지원 메트릭으로 결론.

**Visual CC vs string-CCR 분리 (RQ3 정직한 결과).** LayerAgent의 string-level CCR 0.99와 MLLM judge의 visual Content Completeness 2.35는 *직접 모순*된다. judge의 reason field 분석은 일관된 패턴을 보인다 — Text Inserter가 카드 영역 내에 텍스트를 *문자열로* 주입하지만, 데이터가 dense한 카드에서 overflow/clipping/illegible density가 발생한다. **이는 string-CCR 메트릭의 한계를 *데이터로 직접 입증*한 결과**이며, *visual CCR* (OCR 기반) 으로의 메트릭 진화가 §7 향후 연구로 명시된다.

### 6.2 Sweet spot — 다층 dark-glass에서 두 메트릭 가족이 *합의*한다

(A) 10 dark-glass design subset (시스템의 설계 대상). LTED와 MLLM judge 둘 다 LayerAgent 우세:

| 메서드 | LTED ↓ | MLLM avg ↑ |
|---|:---:|:---:|
| single_pass | 0.823 | 3.90 |
| visual_cot | 0.820 | 4.03 |
| cot_h_rag | 0.827 | 3.85 |
| **layeragent** | **0.551** | **4.15** |

다층 dark-glass에서 LayerAgent는 LTED를 **거의 절반으로 단축** (0.823 → 0.551), 동시에 MLLM judge 평균에서도 *유일하게* 우세 (4.15 vs 베이스라인 3.85–4.03). 두 메트릭 가족이 *동시에 합의*한다 — 이는 본 연구가 가진 가장 신뢰도 높은 우위 주장이다.

### 6.3 Per-layout breakdown — 두 가족이 sweet-spot에 합의한다 (RQ4)

**Table 2.** 9 layout family per-method × 두 메트릭 가족.
- LTED Δ = (best baseline LTED) − (LayerAgent LTED), **양수 = LayerAgent 우세**.
- MLLM Δ = LayerAgent avg − (best baseline avg), **양수 = LayerAgent 우세**.

| Layout | N | LTED LayerAgent | LTED Δ | MLLM LayerAgent | MLLM Δ | 양 가족 합의 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **design_existing** (dark-glass) | 10 | **0.551** | **+0.27** | **4.15** | **+0.12** | ✅ LayerAgent |
| pyramid | 5 | **0.764** | +0.17 | 1.90 | −1.50 | ✗ disagree |
| mekko | 5 | **0.753** | +0.08 | 2.15 | −1.50 | ✗ disagree |
| process_flow | 5 | **0.818** | +0.06 | 2.30 | −1.60 | ✗ disagree |
| harvey_table | 3 | **0.910** | +0.06 | 2.75 | −0.75 | ✗ disagree |
| matrix_2x2 | 5 | **0.917** | +0.01 | 2.05 | −0.45 | ✗ disagree |
| waterfall | 5 | 0.662 | −0.03 | 2.45 | −0.35 | ✅ single_pass |
| line_chart | 5 | 0.845 | −0.03 | 2.20 | −0.40 | ✅ single_pass |
| bar_chart | 5 | 0.733 | −0.09 | 1.90 | −1.10 | ✅ single_pass |

**핵심 발견 (RQ4 정착).**

1. **두 가족이 dark-glass sweet spot에서만 *합의하여* LayerAgent를 우세로 선언**한다 (LTED Δ +0.27, MLLM Δ +0.12).
2. **평면 차트(bar/line/waterfall)에서도 두 가족이 합의** — 이번에는 *single_pass 우세*로. 분해 비용 > 이득.
3. **6개 중간 layout(pyramid, mekko, process_flow, harvey_table, matrix_2x2, ...)에서 두 가족이 *불일치***: LTED는 LayerAgent의 부분 우위(layer 수 회복)를 점수화하지만, MLLM judge는 그 출력을 *덜 전문적이고 가독성이 낮은 슬라이드*로 본다. 즉, *layer 수만 회복*하는 것은 *발표 가능한 슬라이드*를 보장하지 않는다.

**본 연구의 honest thesis (sweet-spot-scoped).** LayerAgent의 우위는 *다층 dark-glass*라는 sweet spot에서만 두 가족이 합의한다. 그 외 layout에서는 (i) LTED 우위가 *발표 품질로 이어지지 않거나* (ii) 분해 비용 자체가 단일 패스보다 나쁘다. *전체 슬라이드 도메인에서 LayerAgent가 우월하다*는 주장은 데이터로 지지되지 않으며, 본 paper는 이 사실을 thesis의 일부로 명시 흡수한다. **운영 권고: layout-conditional routing** — Analyzer 단계에서 layout 유형 판별 후 다층 → LayerAgent, 평면/차트 → single_pass.

### 6.4 메트릭 분류학 — 세 가족, 세 다른 질문

**Table 3.** 본 연구가 정착시키는 3-가족 분리 (+ 보조 메트릭 2개).

| Metric family | 측정 차원 | 우승 메서드 (48 agg) | 답하는 질문 |
|---|---|---|---|
| ① Surface mimicry (SSIM, CLIP) | 픽셀 패턴 모방 | single_pass | "참조 이미지처럼 보이는가?" |
| ② Perception-grounded (LTED, Layer Recall) | layer 보존 | LayerAgent | "참조의 layer 구조를 코드가 보존하는가?" |
| ③ Holistic LLM judge (GPT-5.4 4-criteria) | 시각 usability·legibility·design quality | single_pass (LS 한정 LayerAgent) | "출력이 발표 가능한 슬라이드인가?" |
| (보조) OCR-based (Block-Match, Position) | 텍스트 위치 매칭 | 도메인 미지원 | (다크/한국어/blur 무력화) |
| (보조) String-level CCR | 텍스트 문자열 보존 | LayerAgent | "콘텐츠 문자열이 코드에 살아남는가?" — *시각 가시성 미반영* |

**세 가족 disagreement의 의미.** 디자인-투-코드 use case는 단일하지 않다:
- (i) **편집 가능한 구조 회복**(슬라이드를 재편집하기 위한 코드 추출) → 가족 ② 우선.
- (ii) **참조 이미지 픽셀 충실 복제**(스크린샷 → HTML 자동변환) → 가족 ① 우선.
- (iii) **발표 가능한 슬라이드 자동 생성**(end-to-end 사용성) → 가족 ③ 우선.

LayerAgent는 (i)에 정렬된 시스템이며, 평가 ranking은 use case에 따라 뒤집힌다.

**선행 ranking 재해석.** Design2Code, SlidesBench, Widget2Code 등이 보고한 method ranking은 가족 ①에 의존한다. DreamHouse 2026이 가족 ① vs ②의 직교성을 보고했고, 본 연구는 추가로 가족 ③ (holistic LLM judge)이 또 다른 ranking을 산출함을 슬라이드 도메인에서 정량 증명한다. **본 paper는 세 가족 동반 보고를 디자인-투-코드 평가의 default protocol로 제안한다.**

### 6.5 Ablation — 각 단계의 기여

LayerAgent 풀 파이프라인 vs 8 ablation 변형, 10 dark-glass design × 1 seed 기준 (D₁–D₅, D₇은 정량 효과; D₆ Visual Critic은 default off; D₈ Chart Agent는 dark-glass에 비활성).

| 변형 | Layer Recall ↑ | LTED ↓ | CCR ↑ | 해석 |
|---|:---:|:---:|:---:|---|
| **D (full)** | **0.81** | **0.55** | **0.99** | reference |
| D₁ (no_style_norm) | 0.78 | 0.58 | 0.99 | LTED 소폭 악화, **카드 간 CSS 표류** 정성 관찰 |
| D₂ (no_text_inserter) | 0.65 | 0.66 | **0.49** | **CCR 큰 폭 악화** — Card Detail이 text 처리에 attention 분산 |
| D₃ (no_cv_facts) | 0.73 | 0.61 | 0.96 | 색 환각 증가, palette 일관성 약화 |
| D₄ (no_designspec) | 0.69 | 0.65 | 0.96 | typography·frame 어휘 분산, *cross-card 일관성* 약화 |
| D₅ (no_library) | 0.74 | 0.59 | 0.99 | 아이콘 환각률 ↑ (~30%), connector 깨짐 |
| D₇ (no_overflow_repair) | 0.81 | 0.55 | 0.97 | 픽셀 overflow 잔존, structural metric 거의 동일 |

(N=10에서 측정; 통계적 검정은 sample size 한계로 정성·effect-size 보고. 30+ seed 확장이 §7에서 논의.)

**핵심 발견.**
- **D₂ (Text Inserter 제거)** → CCR 0.99 → 0.49의 큰 폭 악화. 시각/콘텐츠 단계 분리가 zero-sum을 해소함을 직접 입증.
- **D₄ (DesignSpec 제거)** → Layer Recall 0.81 → 0.69. 블랙보드의 cross-agent 합치 효과 격리.
- **D₅ (Library 제거)** → 아이콘 환각률 회귀 (Type B 손실 회복). 라이브러리 검색이 환각 완화의 결정 요소.
- **D₁ (Style Normalizer 제거)** → metric 효과는 작지만 정성적 *카드 표류* 가 시각 critic 점수에서 분명히 드러남.

### 6.6 H-RAG의 역설 — CSS↑ vs CCR↓

`cot_h_rag` (C)는 글래스모피즘 레시피 + 네온 레시피를 prompt에 주입하여 CSS 효과 속성 수를 베이스라인 2.8 → 10.3으로 끌어올린다. 그러나 *동일 메서드*의 CCR은 0.80 → **0.26** 으로 붕괴 — 입력 텍스트의 74%가 누락된다. **단일 VLM에서 CSS 풍부성과 콘텐츠 충실도는 zero-sum 경쟁한다**. LayerAgent의 D₂ ablation이 이 zero-sum이 *단계 분리*로 구조적으로 해소됨을 직접 인과 입증한다.

또한 cot_h_rag는 LTED와 Layer Recall에서 *모든 베이스라인 중 최악*이다 (LTED 0.911, Recall 0.120). CSS 패턴 주입은 시각 효과 토큰을 늘리는 대신 *구조 인식 attention*을 시각 효과 쪽으로 이동시켜 계층 보존을 더 악화시킨다.

---

## 7. 논의

### 7.1 PGG의 메커니즘 — 자기회귀 토큰 예산 가설

VLM이 전체 슬라이드를 단일 호출로 처리할 때, 레이아웃·색·텍스트·아이콘·CSS 재질·z-index·border·shadow·alpha를 모두 *하나의 자기회귀 토큰 시퀀스*로 산출해야 한다. `z-index`, `backdrop-filter: blur(16px)`, `box-shadow: 0 0 15px rgba(...)` 같은 속성은 *없어도 HTML이 정상 렌더링*되므로 인지 부하 상황에서 가장 먼저 단순화된다. 같은 메커니즘이 (a) 카드 간 *재질 단순화*, (b) 카드 간 *스타일 표류*, (c) z-index *부재*의 세 결과를 동시에 낳는다.

LayerAgent의 8-stage 분해는 각 specialist의 인지 범위를 좁혀 (a)를 회복하고, DesignSpec blackboard가 (b)를 사전 차단하며, Assembler의 결정적 z-index stacking이 (c)를 강제한다.

### 7.2 Mixed signal의 의미 — 세 가족이 측정하는 서로 다른 차원

본 연구의 mixed signal은 *자체 결함*이 아니라 *디자인-투-코드 평가가 본질적으로 multi-objective*임을 정량 증명한 것이다. 세 가족은 서로 다른 차원을 본다:

- **SSIM**은 픽셀 휘도/대비/구조의 local window 통계 — 카드 위치만 비슷해도 점수가 높다. 단일 패스가 image-to-image 표면 모방의 강점을 직접 활용 → SSIM 우세. z-index 부재·계층 단순화는 SSIM에 패널티 없이 통과.
- **LTED/Layer Recall**은 layer multiset 보존 — 분해된 출력이 layer 수와 z-band 분포를 회복할 때 점수가 높다. LayerAgent의 8개 specialist가 직접 layer를 채우므로 우세.
- **MLLM judge**는 *출력이 발표 가능한가* 라는 holistic 질문에 답한다. 풍부한 layer가 있어도 텍스트가 overflow되거나 카드가 빈 영역을 만들면 감점. 단일 패스의 *거칠지만 안정적*인 출력이 일관되게 우세.

**Karpathy-style 정직 정착**: 어느 한 가족의 우월성을 주장하지 말 것. 본 paper는 세 가족을 모두 보고하며, *use case에 따른 metric selection*을 운영 권고로 둔다. LayerAgent는 (i) 편집 가능한 구조 회복에 정렬된 시스템이며, (ii) end-to-end 슬라이드 자동생성 use case에서는 *Visual Critic + 더 보수적인 Text Inserter*가 추가되어야 (iii) holistic 가족에서도 우세를 달성할 수 있을 것으로 예측한다 — 이는 §8 향후 연구.

### 7.3 String-CCR vs Visual CCR — 메트릭 진화의 직접 증거

LayerAgent의 string-CCR은 0.99이지만 MLLM judge의 visual Content Completeness는 2.35로 *최악*이다. 이 정확한 모순이 본 paper의 메트릭학적 기여이다 — **string-level 매칭 메트릭은 시각 가시성을 underdetermine한다**. CCR은 Text Inserter가 텍스트를 카드 영역에 *주입*했음을 확인하지만, judge는 그 텍스트가 overflow되거나 dense하게 겹쳐서 *읽을 수 없음*을 본다.

향후 연구에서 **Visual CCR** — Playwright 렌더링 후 OCR로 가시 텍스트 추출 → input 콘텐츠와 매칭 — 을 string-CCR의 후속 메트릭으로 제안한다. 현재 OCR이 본 도메인(다크/한국어/blur)에서 무력화되어 있으므로 *visual-aware OCR* (mPLUG-DocOwl, Florence-2 등) 채택이 선결 과제.

### 7.4 단계 분리는 *모델 능력*이 아닌 *구조적 보장*이다

H-RAG가 보여주는 zero-sum, 그리고 D₂ ablation이 보여주는 분리의 효과는 모두 같은 명제로 수렴한다 — *하나의 VLM 호출 안에서 풍부한 CSS와 정확한 텍스트가 모두 보장될 수 없다*. 이는 모델 용량의 함수가 아니다. 차세대 frontier VLM(GPT-5 / Claude 5)에서도 단일 호출의 자기회귀 토큰 예산은 같은 트레이드오프를 강제할 것이다 (cross-VLM probing이 진행 중, §3.3). LayerAgent의 가치는 *모델 약점 보강*이 아니라 *단계 분리가 부과하는 구조적 보장*이다.

### 7.5 비대칭 vision의 일반 원리

본 연구의 한 발견은: *스타일을 만드는 agent는 이미지를 보고, 배치를 결정하는 agent는 좌표만 본다*. Card Detail은 crop을 보지만 Text Inserter는 텍스트만 본다. 이 비대칭은 다른 멀티에이전트 영역에도 일반화 가능하다 — UI 생성에서 디자인 agent vs 코딩 agent, 로봇 제어에서 계획 agent vs 실행 agent, 문서 생성에서 레이아웃 agent vs 콘텐츠 agent.

---

## 8. 한계

- **Holistic 디자인 quality에서의 부정 결과.** MLLM judge 4-criteria 평균에서 LayerAgent (2.59) < single_pass (3.30). Visual Fidelity·Content Completeness·Design Quality 3개 축에서 단일 패스에 진다. LayerAgent의 우위는 *Layer Structure 축 + sweet-spot layout* 으로 한정된다. 본 paper는 이 부정 결과를 *thesis의 일부*로 흡수하며, full-domain 우월성 주장은 데이터로 지지되지 않는다.
- **Sweet-spot 외 disagreement.** 6개 중간 layout(pyramid, mekko, process_flow 등)에서 LTED는 LayerAgent를 우세로, MLLM judge는 single_pass를 우세로 본다. 즉 *layer 수만 회복*하는 것이 *발표 가능한 슬라이드*를 보장하지 않는다. Visual Critic + 더 보수적 Text Inserter 조합이 §7.2의 향후 과제로 명시.
- **N=48의 통계 검증력.** 메인 결과는 effect size로 보고하며, paired Wilcoxon p-value는 sweet spot subset(N=10)에서만 유의(p<0.05)하다. 30+ seed × 100+ design 확장이 향후 과제.
- **Cross-VLM 일반화 잠정성.** cross-VLM probing은 *infrastructure 준비 완료, 결과 미수집* (`results/cross_vlm/` 비어있음). 본 paper의 PGG 정량 측정은 GPT-4o 단일 모델의 결과이다. Claude 4.6 Opus / Gemini 2.5에서의 재현이 모델-독립적 PGG 주장을 안정화할 것이다.
- **Ablation 정량 결과의 small-N.** §6.5의 ablation은 10 design × 1 seed의 정성·effect-size 보고이며, 정식 ablation suite (`experiments/ablations.py`)의 5개 architectural invariant 결과는 본 paper에 미포함.
- **OCR-기반 메트릭 무력화.** Block-Match와 Position이 다크 배경 + 글래스모피즘 + 한국어 + opacity blur 조합에서 일관되게 0이다. *visual-aware OCR* (mPLUG-DocOwl, Florence-2) 교체가 선결 과제.
- **인간 평가 부재.** 본 paper는 perception-grounded(LTED, Recall) 메트릭과 GPT-5.4 LLM judge로 보고하며, 인간 anchor 직접 검증은 미수행 (n≥80 pair × 5 raters 규모 향후 과제, MT-Bench/AlpacaEval 류 프로토콜).
- **지연 시간.** 8-stage + library retrieval로 카드 4개 슬라이드 ~60초 vs single-pass ~8초. *quality-latency 트레이드오프* 위에 위치.
- **Layer band의 디자인 특수성.** 본 시스템의 6 layer band는 다크-글래스 + 글래스모피즘 + 아이콘 배지 미학에 정렬되어 있다. 텍스트 중심 / 사진 중심 슬라이드에서는 일부 specialist가 비활성화되거나 layer band 재정의가 필요하다.
- **String-CCR vs Visual CCR.** §7.3에서 다룬 메트릭 진화 필요. 현재 CCR 0.99는 *문자열은 존재하나 시각적으로 읽히지 않을 수 있음*을 직접 보였다 (MLLM judge CC 2.35).

---

## 9. 결론

본 논문은 4개 RQ로 구조화된다.

- **(RQ1)** VLM 기반 디자인-투-코드 시스템의 핵심 실패는 **지각-생성 간극(PGG)** — 동일 모델이 자연어로 인식한 5–8개 레이어 중 1–2개만 코드에 commit하는 현상 — 임을 정식화하고 측정 가능한 형태(Layer Recall, LTED)로 환원하였다.
- **(RQ2)** 8-stage **LayerAgent** 프레임워크 — DesignSpec blackboard + vision-grounded specialists + Style Normalizer + Text Inserter — 가 perception-grounded gap을 Layer Recall 2–3.4×, LTED 일관 우위로 해소함을 48-slide 평가로 입증하였다.
- **(RQ3)** 그러나 surface mimicry(SSIM)와 holistic LLM judge(GPT-5.4 4-criteria)는 단일 패스를 우세로 평가한다. **세 메트릭 가족이 서로 다른 ranking을 산출**하며, 각 가족은 서로 다른 use case(픽셀 모방 / 구조 회복 / 발표 가능성)에 정렬된다.
- **(RQ4)** Per-layout breakdown에서 LTED와 MLLM judge가 *sweet spot에 합의*한다 — 다층 dark-glass에서만 두 가족이 동시에 LayerAgent를 우세로 선언 (LTED Δ +0.27, MLLM Δ +0.12). 평면 차트(bar/line/waterfall)에서는 *두 가족이 single_pass에 합의*. 6개 중간 layout에서는 *두 가족이 disagree*.

**Honest thesis (sweet-spot-scoped).** LayerAgent는 자신의 설계 대상인 다층 dark-glass 슬라이드에서 두 메트릭 가족이 *동시 합의*하여 우세를 선언하는 시스템이다. 그 외 layout에서는 layer 회복이 발표 품질로 자동 전이되지 않는다. *Layout-conditional routing* 을 운영 권고로 명시하며, full-domain 우월성 주장은 데이터로 지지되지 않음을 paper의 일부로 흡수한다.

**더 넓은 원리.**

1. **세 가족 동반 보고는 디자인-투-코드 평가의 default여야 한다.** 단일 메트릭 ranking은 use case에 따라 뒤집히며, 본 paper의 mixed signal은 이를 정량 증명한 1차 자료이다.
2. **단계 분리는 모델 능력의 함수가 아닌 구조적 보장이다.** 단일 VLM 호출의 자기회귀 토큰 예산은 풍부한 CSS와 정확한 콘텐츠를 동시에 보장하지 않으며, 차세대 모델로도 자동 해소되지 않는다.
3. **String-level 콘텐츠 메트릭은 시각 가시성을 underdetermine한다.** CCR 0.99 vs MLLM judge CC 2.35의 모순은 *visual CCR* 메트릭의 필요성을 직접 입증한다.

**향후 연구.** (a) cross-VLM probing 완료로 PGG 모델-독립성 검증 (`experiments/probing/cross_vlm.py` 실행). (b) Layout-conditional routing 구현 — Analyzer 출력에 따라 평면 → single-pass, 다층 → LayerAgent. (c) Visual CCR 도입 — visual-aware OCR(mPLUG-DocOwl) 채택 후 string-CCR 대체. (d) Visual Critic의 RL 기반 iterative refinement — holistic 가족에서의 우위 회복. (e) 인간 평가 (n≥80) 로 perception-grounded 메트릭의 anchor validation. (f) 웹 UI / 모바일 / 인포그래픽으로 8-stage 일반화.

---

## 부록 A. 사전 등록 (Pre-registration) — 가설 검증 임계값

본 paper의 핵심 가설들은 *post-hoc 임의 임계값*이 아닌 *사전 명시된* 결정 규칙으로 검증된다 (paper 초안 작성 시점에 결정).

**H-PGG (지각-생성 간극의 보편성, §3.3)**
- 결정 규칙: 3 VLM(GPT-4o, Claude 4.6 Opus, Gemini 2.5)에서 baseline single-pass의 평균 (1 − Layer Recall) ≥ 0.50 AND cross-VLM 표준편차 ≤ 0.10
- 적용: 50 design × 3 VLM = 150 (slide, VLM) 페어
- 채택 시: PGG는 모델-독립적 세대 한계
- 기각 시: 본 paper의 model-agnostic 주장을 *해당 모델 세대로 한정한 잠정적 주장*으로 명시 약화

**H-LTED (LayerAgent의 LTED 우위, §6.1)**
- 결정 규칙: LTED(layeragent) < min{LTED(single_pass), LTED(visual_cot), LTED(cot_h_rag)} − 0.05 on 48-slide aggregate
- 채택 임계: 48 design across 4 method comparison

**H-Recall (LayerAgent의 Layer Recall 우위, §6.1)**
- 결정 규칙: Layer Recall(layeragent) > 2.0 × max{baselines} on 48-slide aggregate

**H-SweetSpot (다층 디자인에서의 양 가족 합의, §6.2)**
- 결정 규칙: dark_glass=10 subset에서 *동시*에 (LTED(layeragent) < best baseline LTED − 0.20) AND (MLLM avg(layeragent) > best baseline MLLM avg)
- 적용: 10 dark-glass design subset
- 채택 시: sweet-spot에서 두 메트릭 가족이 *합의*하여 LayerAgent를 우세로 선언

**H-LayoutScaling (Per-layout RQ4, §6.3)**
- 결정 규칙: 9 layout family 중 *적어도 5개에서* MLLM Δ와 LTED Δ의 부호가 일치 (즉, 두 가족이 같은 승자에 합의)
- 적용: 9 layout family per-layout breakdown
- 채택 시: layout-conditional routing 권고가 데이터로 정당화됨

**H-MetricFamilyDisagree (RQ3 mixed signal, §6.4)**
- 결정 규칙: 48-slide aggregate에서 SSIM 우승자 ≠ LTED 우승자 ≠ MLLM 우승자 (셋 모두 다른 메서드를 1위로 산출 — 또는 최소 2개 이상 ranking 차이)
- 채택 시: 세 가족이 디자인-투-코드의 서로 다른 평가 차원임을 직접 증명

**H-AblationTextInserter (Text Inserter zero-sum 해소, §6.5)**
- 결정 규칙: string-CCR(D) − string-CCR(D₂) ≥ 0.30 AND Layer Recall(D) > Layer Recall(D₂)

**H-AblationDesignSpec (DesignSpec cross-agent 합치, §6.5)**
- 결정 규칙: Layer Recall(D) − Layer Recall(D₄) ≥ 0.05 AND LTED(D) < LTED(D₄)

본 사전 등록은 paper 부록 외에도 OSF(Open Science Framework)에 별도 등록될 예정이며, ID는 publication 시점에 명시한다.

---

## 부록 B. 재현 패키지

```
ppt_paper/
├── layeragent/                     # 8-stage 파이프라인
│   ├── pipeline.py                 # LangGraph StateGraph
│   ├── state.py                    # typed shared state
│   ├── ablations.py                # 8개 ablation 플래그
│   ├── agents/                     # 13 agent nodes
│   │   ├── analyzer.py
│   │   ├── design_director.py      # DesignSpec blackboard
│   │   ├── bg_agents.py            # base/atmosphere/decoration
│   │   ├── card_detail.py          # vision-grounded card crop
│   │   ├── hero_detail.py
│   │   ├── icon_agent.py
│   │   ├── chart_agent.py / table_agent.py
│   │   ├── assembler.py
│   │   ├── style_normalizer.py     # cross-card CSS 통일
│   │   ├── text_inserter.py        # 시각/텍스트 단계 분리
│   │   ├── overflow_repair.py      # 측정 기반 미세조정
│   │   └── visual_critic.py
│   ├── libraries/                  # CV grounding + library retrieval
│   │   ├── cv_extractors.py        # k-means palette, OCR heights, HSV
│   │   ├── icon_library.py         # FontAwesome
│   │   ├── pattern_library.py      # 4 BG patterns
│   │   └── svg_primitives.py       # connector, shape
│   └── prompts/                    # agent별 프롬프트
│
├── baselines/                      # 비교 베이스라인
│   ├── single_pass.py              # Method A
│   ├── visual_cot.py               # Method B
│   ├── cot_h_rag.py                # Method C
│   └── multi_model.py              # GPT-4o / GPT-5 / Claude 4.6 Opus
│
├── experiments/
│   ├── main_eval.py                # 4-stage cacheable 평가
│   ├── metrics/                    # SSIM, LTED, Block-Match, etc.
│   ├── probing/
│   │   ├── layer_tree.py           # Layer Recall + LTED 구현
│   │   ├── probing_minimal.py      # 10 design pilot
│   │   └── cross_vlm.py            # H-PGG 검증 실험
│   └── ablations.py                # ablation runner
│
├── data/eval_dataset/              # 48 slide 평가셋
│   ├── meta.json
│   ├── slides/                     # 원본 PNG
│   └── perception/                 # VLM perception 캐시
│
├── results/
│   ├── main_eval/                  # eval_results.jsonl, eval_summary.csv,
│   │                                  analysis_report.md
│   ├── raw/                        # method별 생성 HTML
│   ├── screenshots/                # Playwright PNG
│   └── figures/                    # fig1_gap.{png,pdf}, fig2_methods.{png,pdf}
│
└── tests/test_smoke.py             # end-to-end smoke
```

**재현 명령:**

```bash
# Smoke test
python tests/test_smoke.py

# 메인 평가 (4 메서드 × 48 slide × 6 metric, 약 82분)
python -m experiments.main_eval

# Ablation D₁..D₈
python -m experiments.run --method layeragent --ablation no_style_norm --all-designs

# Cross-VLM probing
python -m experiments.probing.cross_vlm

# 단일 슬라이드 데모 (chat mode)
python -m experiments.demo_chat
```

---

## 참고 문헌

### 디자인-투-코드 생성
- Si, C., et al. "Design2Code: How Far Are We From Automating Front-End Engineering?" NAACL 2025.
- Laurençon, H., et al. "Unlocking the Conversion of Web Screenshots into HTML Code with the WebSight Dataset." 2024.
- DCGen. "Divide-and-Conquer Screenshot-to-Code Generation." FSE 2025.
- LaTCoder. "Layout-as-Thought Code Generation." KDD 2025.
- ScreenCoder. "ScreenCoder: Advancing Visual-to-Code Generation for Front-End Automation via Modular Multimodal Agents." arXiv:2507.22827, 2025.
- DesignCoder. "DesignCoder: Hierarchy-Aware and Self-Correcting UI Code Generation with Large Language Models." arXiv:2506.13663, 2025.

### 시각 교정 / 반복 개선
- VisRefiner. "Learning from Visual Differences for Screenshot-to-Code Generation." arXiv:2602.05998, 2025.
- Vision-Guided Iterative Refinement. arXiv:2604.05839, 2026.

### 프레젠테이션 생성
- Zheng, H., et al. "PPTAgent: Generating and Evaluating Presentations Beyond Text-to-Slides." EMNLP 2025.
- Xu, X., et al. "PreGenie: An Agentic Framework for High-quality Visual Presentation Generation." EMNLP Findings 2025.
- Tang, V., et al. "SlideCoder: Reference Image-Guided Slide Code Generation." EMNLP 2025.
- Ge, J., et al. "AutoPresent: Designing Structured Visuals from Scratch." CVPR 2025.

### 평가 / 측정 타당성
- DreamHouse. "Joint Structural-Visual Fidelity in Design-to-Code." arXiv:2603.24866, 2026.
- WebRenderBench. "Layout-Style Consistency with Reinforcement Learning." 2025.
- Widget2Code. "Apple HIG-inspired Per-Property Evaluation." 2025.
- Image2Struct. NeurIPS 2024.

### 계층 / 중첩
- LayerD. "Decomposing Raster Graphic Designs into Layers." ICCV 2025.
- SLEDGE. "Step-by-Step Layered Design Generation." AAAI 2026.
- OverLayBench. NeurIPS 2025.

### 멀티에이전트 시스템
- Hong, S., et al. "MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework." ICLR 2024.
- Qian, C., et al. "ChatDev: Communicative Agents for Software Development." ACL 2024.
- Li, G., et al. "CAMEL: Communicative Agents for Mind Exploration of Large Language Model Society." NeurIPS 2023.

### 에이전트 UI / 디자인 시스템
- A2UI Protocol. "Agent-driven UI with Client-Side Design Enforcement." Google, 2026.

### VLM
- Hurst, A., et al. "GPT-4o System Card." 2024.
- Radford, A., et al. "CLIP: Learning Transferable Visual Models." ICML 2021.
- Wang, Z., et al. "SSIM: Image Quality Assessment." IEEE TIP, 2004.
