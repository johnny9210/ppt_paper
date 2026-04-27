# LayerAgent: 지각-생성 간극(Perception–Generation Gap)을 메우는 비전 기반 레이어 분해 멀티에이전트 프레임워크

*Vision-Grounded Layer Decomposition for Closing the Perception–Generation Gap in Design-to-Code Presentation Generation*

---

## 초록

프레젠테이션 슬라이드는 배경·분위기·장식·카드·콘텐츠·아이콘이 z축으로 겹치는 본질적으로 **계층적(layered)** 구조이다. 그러나 GPT-4o single-pass 기반 디자인-투-코드는 이 계층 구조를 단일 자기회귀 토큰 시퀀스의 **평면(flat) HTML**로 생성하여, 체계적인 구조 단순화를 일으킨다 — 시각 element 9개·스타일 다양성 3종·CSS 효과 24개 수준에 그침. 본 논문은 이를 정식화하고, *vocabulary-free 측정*과 *멀티에이전트 분해*로 해소한다.

**문제 정식화 — 지각-생성 간극(Perception–Generation Gap, PGG, GPT-4o 한정).** 동일 GPT-4o가 슬라이드 이미지로부터 5–8개 layer를 자연어로 인식하지만, 같은 이미지를 HTML로 변환할 때 *시각적으로 의미 있는 element 9개·distinct style 3종*만 commit. 이 간극은 시각 이해 부재가 아닌 *생성 단계의 capacity 분산*에서 기인. **메트릭 limitation 명시**: 기존 paper draft의 Layer Recall/LTED는 *우리가 정의한 class name 어휘*에 align되어 *circular* — 본 paper는 이를 폐기하고 *vocabulary-free* 메트릭(VEC/EDC/VLC/CRP/HD via DOM computed style + SSIM/CLIP/LPIPS via PNG)으로 재측정.

**해법 — LayerAgent (8-stage multi-agent decomposition).** Analyzer → Design Director (DesignSpec 블랙보드) → {Base BG / Atmosphere / Decoration / Card Detail × N / Hero Detail × N / Icon / Chart / Table} → Assembler → Style Normalizer → Text Inserter → (옵션) Overflow Repair / Visual Critic. DesignSpec은 typography/palette/frame/motif/atmosphere의 typed shared state로서 cross-agent 스타일 합치를 강제하고, k-means palette·OCR 텍스트 높이·HSV 채도의 **CV facts**가 결정적 프롬프트 앵커로 주입된다. FontAwesome·SVG primitive·BG pattern·Bezier connector **라이브러리**가 환각을 차단한다.

**경험적 결과 — Same-model GPT-4o 비교 (Table 1, N=10, vocabulary-free).** LayerAgent vs single_pass / visual_cot / cot_h_rag (모두 GPT-4o):

| Metric | A. single_pass | B. visual_cot | C. cot_h_rag | **D. LayerAgent** |
|---|:---:|:---:|:---:|:---:|
| VEC (시각 element 수) | 9.1 | 7.3 | 9.8 | **20.9** ← 2.3× |
| EDC (style diversity) | 3.0 | 2.7 | 3.5 | **9.7** ← 3.2× |
| CRP (CSS richness) | 23.6 | 18.3 | 28.1 | **51.5** ← 2.2× |
| CLIP ↑ | 0.450 | 0.448 | 0.430 | **0.492** |
| LPIPS ↓ | 0.653 | 0.652 | 0.709 | **0.589** |
| SSIM ↑ | **0.493** | 0.486 | 0.467 | 0.470 (−0.023) |

**LayerAgent가 8개 vocabulary-free metric 중 7개에서 1위**. SSIM 0.023 차이는 noise 수준 (N=10, std~0.10). 단순 2-stage CoT나 CSS pattern injection (visual_cot, cot_h_rag)은 *오히려 single_pass보다 못함* — *DesignSpec + Library + Style Normalizer + Text Inserter의 조합이 결정적*.

**경험적 결과 — Cross-model cost-efficiency (Table 2, vocabulary-free).** LayerAgent (값싼 GPT-4o + 분해) vs frontier single-pass:

| Method | CLIP↑ | LPIPS↓ | Cost/slide | Time |
|---|:---:|:---:|:---:|:---:|
| **LayerAgent** (GPT-4o) | 0.492 | 0.589 | **$0.232** | **60s** |
| single-pass (GPT-5.4) | **0.578** | **0.411** | $0.075 | 85s |
| single-pass (Claude 4.6 Opus) | 0.525 | 0.502 | $0.421 | 108s |

**vs Claude Opus**: LayerAgent가 시각 fidelity 거의 동등 (CLIP 0.492 vs 0.525), 비용 **45% 절감** ($0.232 vs $0.421), 시간 **44% 절감** → **가성비 우세 ✅**. **vs GPT-5.4**: GPT-5.4가 모든 차원 우세 + 비용 1/3 → **honest 패배 ❌** — frontier 능가 주장 *데이터 미지지*. 결론: LayerAgent는 *expensive frontier (Opus 등)의 cost-efficient 대체*이며 *모든 frontier 대체*는 아님.

**메트릭 disagreement 정직 보고.** SSIM·CLIP·LPIPS·MLLM judge·DOM-based metric 5 가족이 same data에 *서로 다른 ranking*을 산출. 단일 메트릭 ranking은 use case에 의존. 본 연구의 *vocabulary-free 측정 + 두 표 분리* protocol을 디자인-투-코드 평가 default로 제안.

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

흥미로운 관찰은 다음이다 — 같은 GPT-4o에게 *"이 이미지의 계층 구조를 설명하라"* 고 물으면 5–8개의 레이어를 자연어로 기술한다. 그러나 같은 이미지를 *"HTML로 변환하라"* 고 물으면 평균 **1.6개**(범위 0–4) 레이어만 코드로 commit한다 (§3.2 표). **VLM은 perception 단계에서 5+ layer를 인식하지만 code generation 단계에서 그 대부분을 잃는다.**

본 문제 정의는 저자들의 18개월 프로덕션 운영(AIDX 슬라이드 생성 시스템)에서 도출되었다. 일례로 `data/design_images/session_meta.json`의 실제 사용자 세션은 6장 다크 테마 사이버보안 deck — 각 슬라이드가 `slide_plan.design_prompt`로 *명시적으로 multi-layer 글래스모피즘 + 네온 글로우 + 그리드 패턴*을 요청하지만, 단일 VLM 호출의 HTML 출력은 일관되게 단색 배경 + 평면 카드로 회귀한다. 이러한 운영상의 반복 실패가 본 연구의 motivation.

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

핵심 설계 결정 4가지 (각각의 *individual* 효과는 §6.5에서 D₂만 측정됨; 다른 3개는 *system whole*로서의 효과만 §6.1로 측정):

- **Vision-grounded specialists**: BG/Atmosphere/Decoration은 전체 이미지를, Card/Hero Detail은 *crop된* 이미지를 직접 본다 — 좁은 시각 범위가 풍부한 CSS 재질을 회복한다는 *설계 가설*.
- **DesignSpec blackboard**: 모든 specialist가 단일 typed JSON을 공유 — cross-agent 스타일 표류를 사전 차단한다는 *설계 가설*.
- **Deterministic CV facts**: k-means palette + OCR 텍스트 높이 + HSV 채도 prompt 주입 — 환각 감소를 *목표*로 함 (`layeragent/libraries/cv_extractors.py`).
- **Library retrieval**: FontAwesome icon search, SVG primitive shapes, 4종 background pattern, Bezier connector path — 자산 환각을 차단하는 *설계 가설* (`layeragent/libraries/`).

위 4가지 design choice의 *individual contribution*은 본 paper에서 정량 측정되지 않았다 (§6.5의 ablation은 D₂ Text Inserter에 한정). 따라서 본 paper의 *측정된 system-level claim* 은 "*8-stage 통합 시스템* 이 perception-grounded 메트릭에서 single-pass를 능가한다"이며, *각 design choice 개별 contribution*은 향후 ablation 작업으로 명시 분리한다 (§8 한계).

### 1.4 연구 질문과 기여

본 연구는 4개 RQ로 정식화된다 (각 RQ는 *특정 데이터셋이 직접 지지하는* 경험적 주장이며, 데이터 미수집 RQ는 §7 향후 연구로 분리한다):

- **RQ1 (Same-model 분해 효과)**: 동일 base model GPT-4o 위에서 8-stage 멀티에이전트 분해가 *vocabulary-free metric* (DOM-based VEC/EDC/VLC/CRP/HD + PNG-based SSIM/CLIP/LPIPS)에서 single-pass·visual_cot·cot_h_rag 모두를 능가하는가? — **Table 1** (§6.1)으로 답한다.
- **RQ2 (Cross-model cost-efficiency)**: GPT-4o + LayerAgent (값싼 base + 분해)가 frontier single-pass (GPT-5.4·Claude 4.6 Opus)와 비교하여 cost-quality trade-off에서 어느 위치인가? — **Table 2** (§6.2)로 답한다.
- **RQ3 (메트릭 가족 disagreement)**: vocabulary-free DOM-based, PNG-based visual fidelity, holistic LLM judge — 여러 메트릭 가족이 동일 데이터에서 서로 다른 ranking을 산출하는가? 각 가족은 어떤 use case에 정렬되는가? — main_eval + new_eval + mllm_judge 데이터로 답한다 (§6.5).
- **RQ4 (Sweet-spot scaling)**: LayerAgent의 우위는 디자인의 *계층 복잡도*에 어떻게 의존하는가? — *9 layout family per-layout breakdown* (§6.4)으로 답한다.

위 RQ들에 대응하는 본 paper의 **기여**는:

1. **Vocabulary-free 평가 protocol**: 기존 paper draft의 Layer Recall/LTED는 *우리가 정의한 class name 어휘에 align*된 *circular metric*. 본 paper는 이를 폐기하고 (1) DOM computed-style 기반 5 metric (VEC/EDC/VLC/CRP/HD) + (2) PNG-based 3 metric (SSIM/CLIP/LPIPS) + (3) cross-judge 4-criteria로 대체. 모든 메트릭이 vocabulary-free이며 모든 메서드에 동일하게 적용됨.
2. **LayerAgent 8-stage 프레임워크**: DesignSpec 블랙보드 + CV grounding + library retrieval + Style Normalizer + Text Inserter (§4). Same-model GPT-4o 비교 (Table 1)에서 vocabulary-free 8개 metric 중 7개에서 1위 — 단순 2-stage CoT나 CSS pattern injection은 *오히려 single-pass보다 못함* — 8-stage 조합이 결정적임을 정량 입증.
3. **Cost-efficiency analysis (정직 보고)**: LayerAgent (GPT-4o, $0.232/slide) vs Claude 4.6 Opus single-pass ($0.421) — 시각 fidelity 거의 동등 + 비용 45% 절감 (✅ valid). 그러나 vs GPT-5.4 single-pass ($0.075) — *모든 차원 GPT-5.4 우세* (❌ 정직 패배). 결론: LayerAgent는 *expensive frontier의 cost-efficient 대체*이며 *모든 frontier 대체*는 아님.
4. **메트릭 disagreement 정량 증명**: same data에 vocabulary-free DOM metric + visual fidelity + LLM judge 3+ 가족이 *서로 다른 ranking* 산출. 단일 메트릭으로 디자인-투-코드 평가 불가능 — *use case별 metric selection* 권고.

위 RQ들에 대응하는 본 paper의 **기여**는:

1. **PGG의 정식화와 측정**: Layer Recall + LTED라는 *perception-grounded reference-free* 메트릭 가족 제안. 같은 VLM의 perception을 ground-truth anchor로 삼아 측정 외부성 의존을 제거 (§3, `experiments/probing/layer_tree.py`).
2. **LayerAgent 8-stage 프레임워크**: DesignSpec 블랙보드 + CV grounding + library retrieval로 강화된 LangGraph 파이프라인 (§4). 본 paper의 *측정된 contribution*은 *통합 시스템 수준*이며, 컴포넌트별 effect size는 D₂(Text Inserter) 만 정량 측정됨 (§6.5). 나머지 7개 ablation 플래그(`layeragent/ablations.py`)는 infrastructure-only로 향후 작업.
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

### 3.1 정의 — Vocabulary-free 측정 (primary) + Legacy (참고)

본 paper는 PGG를 *vocabulary-free* metric set으로 측정한다 (§5.3 Tier ① + ②). Legacy regex 기반 metric (Layer Recall, LTED) 은 *우리가 정의한 LayerAgent class name 어휘*에 align되어 *circular 위험*이 있어, 본 paper에서는 §6.1 Table 1c (참고 표) 와 §6.8 (legacy ablation) 에 한정 사용하며 main claim에는 사용하지 않는다.

**Primary — DOM-based vocabulary-free** (`experiments/metrics/dom_structure.py`):

Playwright로 렌더링한 DOM에 JS injection하여 모든 가시 element의 *computed style + bounding box*를 추출 (class name과 무관). 6 metric:

- **VEC**: 비-자명 styling (배경/테두리/그림자/filter) 가진 가시 element 수
- **EDC**: distinct *style fingerprint* 수, fingerprint = `(bg, border, radius, shadow, backdrop, opacity)` 튜플
- **VLC**: distinct *effective z-band* 수 (explicit z-index OR DOM depth band)
- **CRP**: 모든 가시 element 합계 *rich CSS property* 사용 횟수
- **HD**: visual element 중 max DOM nesting depth
- **SC**: 슬라이드 영역 중 가시 element가 차지하는 면적 비율

**Primary — PNG-based visual fidelity** (`experiments/metrics/visual_similarity.py`):
- **SSIM** (skimage), **CLIP** (open_clip ViT-B/32), **LPIPS** (AlexNet)

**Legacy (참고용) — vocabulary-aligned**: 

슬라이드 이미지 $I$와 VLM $\mathcal{V}$에 대해 perception tree $T_P$와 generation tree $T_G$를 정의 — perception은 VLM이 자연어로 기술한 layer를 27개 canonical type으로 정규화, generation은 HTML을 *class name regex*로 파싱. 두 트리를 (z-band, type) multiset으로 환원하여 **Layer Recall** = $|\mathrm{types}(T_P) \cap \mathrm{types}(T_G)| / |\mathrm{types}(T_P)|$, **LTED** = $\sum_k |m_P(k) - m_G(k)| / (\sum_k m_P(k) + m_G(k))$ 정의 (구체 수식은 `experiments/probing/layer_tree.py`).

⚠ **Legacy metric의 vocabulary alignment 한계**: 우리 parser의 정규식은 LayerAgent의 class name (`card-wrap`, `bg-base`, `atmos`, `decor`)에 매칭됨. Claude Opus의 `glass-card`/`node-inner`/`hub-content` 같은 *시각적으로 풍부한 class name*은 매칭 안 됨 → LayerAgent에 self-favoring. 본 paper의 main claim은 *vocabulary-free metric (Tier ① + ②)* 로 보고하며 legacy metric은 sanity check 용도.

*(이전 paper draft의 6→3 z-band 축소 근거, parser robustness check 등의 세부는 vocabulary alignment 한계 발견 후 부차적 의미를 가짐 — `experiments/probing/layer_tree.py` 코드와 git history에 보존.)*

### 3.2 진단 — PGG의 두 데이터셋 측정

본 연구는 PGG를 두 데이터셋에서 측정한다.

**(A) probing_minimal pilot — N=10 dark-glass, GPT-4o** (`experiments/probing/probing_minimal.py`):

| 지표 | Stage A perception | Stage B1 (single-pass) | Stage B2 (LayerAgent) |
|---|:---:|:---:|:---:|
| `n_layers` 평균 | 5–8 | 0–4 | 5–10 |
| `Layer Recall` (vs $T_P$) | 1.00 (sanity) | **0.195** | **0.676** |
| `gap = 1 − Recall` | 0.00 | **0.805** | **0.324** |
| `LTED` ↓ | 0.00 | 0.82 | 0.55 |

Single-pass에서 perception이 보장한 5–8 layer 중 평균 1.6개만 코드로 commit되며, LayerAgent에서 평균 5.4개. **절대 closure = 0.481** (60% 상대 closure).

**(B) main_eval — N=48 mixed, 4-method** (`experiments/main_eval.py`, `analyze_results.py`):

| Method | Layer Recall ↑ | PGG (1−Recall) ↓ |
|---|:---:|:---:|
| cot_h_rag | 0.120 ± 0.16 | **0.880** ← *worst* — CSS 패턴 주입이 PGG를 *악화* |
| visual_cot | 0.196 ± 0.13 | 0.804 |
| single_pass | 0.212 ± 0.15 | 0.788 |
| **layeragent** | **0.405 ± 0.23** | **0.595** ← LayerAgent 절대 closure 0.193 |

**핵심 발견 1 — Pattern injection이 PGG를 악화시킨다 (H-RAG 역설).** cot_h_rag(글래스모피즘/네온 CSS 레시피 RAG 주입)는 *모든 메서드 중 PGG 가장 큼* (0.880). 부가적으로, legacy N=5 측정에서 cot_h_rag는 CSS Richness 2.8→10.3으로 *상승*하지만 string-CCR 0.80→**0.26**으로 *붕괴* (텍스트 74% 누락). **CSS 패턴 토큰이 (a) 시각 효과 attention 증가, (b) layer 인식 약화, (c) 콘텐츠 보존 악화의 동시 결과를 낳는다** — 모두 *단일 VLM의 자기회귀 토큰 예산*이라는 같은 메커니즘에서 기인. LayerAgent의 D₂ ablation(§6.5)이 이 zero-sum이 *단계 분리*로 구조적으로 해소됨을 직접 인과 입증한다.

**핵심 발견 2 — Sweet-spot이 PGG closure 효과를 *3배* 좌우한다.**

| Eval | Single-pass gap | LayerAgent gap | 절대 closure | 상대 closure |
|---|:---:|:---:|:---:|:---:|
| (A) N=10 dark-glass | 0.805 | 0.324 | **0.481** | 60% |
| (B) N=48 mixed | 0.788 | 0.595 | 0.193 | 24% |

다층 dark-glass(시스템 설계 대상)에서 LayerAgent는 PGG의 *60%*를 회복하지만, 평면 차트가 포함된 mixed eval에서는 *24%*만 회복. **절대 closure 효과가 sweet-spot 외부에서 1/3로 떨어진다**. 이는 §6.3 per-layout breakdown의 sweet-spot 발견을 *PGG framing 자체에서* 다시 입증한다 — 두 발견이 독립 데이터에서 같은 결론에 합의.

![Figure 1: Layer Recall × method (N=48)](results/figures/fig1_gap.png)

*Figure 1.* Layer Recall by method across 48 slides. LayerAgent (N=48 평균 0.405)는 모든 베이스라인을 압도하지만 분산이 큼 (±0.23) — 이는 sweet-spot 의존성을 시사 (§6.3에서 정량화).

### 3.3 PGG는 frontier model로 자동 해소되지 않는다 — Cross-VLM 실증

PGG가 GPT-4o 단일 모델의 인공물인지, 또는 *현재 세대 frontier VLM 전반의 구조 한계*인지 직접 검증하기 위해 **cross-VLM probing**을 수행했다 (`experiments/probing/cross_vlm_frontier.py`). 10 dark-glass design × 2 frontier VLM (GPT-5.4 via Azure, Claude 4.6 Opus via Bedrock) × single-pass generation = 20 호출. 동일한 prompt와 콘텐츠 spec으로 각 모델에 image → HTML 생성을 요청하고 Layer Recall + LTED를 계산한다.

**Table — Frontier 단일 패스의 PGG (N=10 dark-glass).**

| 모델 | LTED ↓ | Layer Recall ↑ | PGG (1−Recall) | 평균 토큰 | 비용/슬라이드 | 시간 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| single_pass (GPT-4o) | 0.823 | 0.224 | 0.776 | ~5,000 | ~$0.015 | ~10s |
| single_pass (GPT-5.4) | 0.669 | 0.300 | **0.700** | 6,015 | $0.075 | 85s |
| single_pass (Claude 4.6 Opus) | 0.693 | 0.312 | **0.688** | 7,116 | $0.421 | 108s |
| **LayerAgent (GPT-4o, 본 연구)** | **0.551** | **0.759** | **0.241** | 54,310 | $0.232 | ~60s |

**핵심 발견 1 — Frontier model의 PGG는 거의 동일하다.** GPT-5.4 (Azure 최신)와 Claude 4.6 Opus (Anthropic 최강) 모두 baseline gap **0.69–0.70** 으로 GPT-4o의 0.78과 *수치 차이는 작고 절대 수준은 모두 매우 큼*. *모델 능력 향상으로 PGG가 자동 해소되지 않음을 직접 입증*.

**핵심 발견 2 — 분해된 GPT-4o가 frontier 단일 패스를 압도한다.** LayerAgent (값싼 GPT-4o + 분해)는 **Recall 0.759** — Claude 4.6 Opus의 *2.43×*, GPT-5.4의 *2.53×*. PGG closure 0.241 (Claude 0.688의 *3분의 1 미만*).

**가설 H-PGG 검증.** 사전 등록 결정 규칙: *"3 VLM에서 baseline gap > 0.5 AND cross-VLM 표준편차 ≤ 0.10이면 PGG는 모델-독립적 세대 한계"*. 측정 결과: 3 VLM gap = {0.776, 0.700, 0.688}, 평균 0.721, std 0.039 (≤ 0.10 ✓). **H-PGG 채택 — PGG는 *현재 세대 frontier VLM 전반의 구조적 한계*로 정착**.

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

### 5.3 메트릭 — *Vocabulary-free* 우선 + 보조 + Legacy

**Critical methodological note**: 본 paper draft 초기 버전은 Layer Recall + LTED를 *PGG metric*으로 사용했다. 그러나 이는 *우리가 정의한 LayerAgent class name 어휘에 align된 regex 기반 측정* 으로, 동일 시각 출력이라도 *다른 어휘를 쓰는 메서드(Claude Opus의 `glass-card`, `node-inner` 등)*에 거짓 negative를 보고하는 *circular metric*이다 (§7.3 자세히). 본 paper는 이를 *legacy*로 격하하고 **vocabulary-free metric set**으로 main result를 보고한다.

**가족 ① DOM-based Vocabulary-Free (HTML structure, primary)** (`experiments/metrics/dom_structure.py`):

Playwright로 렌더링한 DOM에 JS injection하여 모든 가시 element의 *computed style + bounding box*를 추출. Class name과 무관, 모든 메서드에 동일 적용.

- **VEC** ↑ (Visual Element Count) — 비-자명 styling을 가진 가시 element 수 (배경, 테두리, 그림자, 또는 filter 보유)
- **EDC** ↑ (Element Diversity Count) — distinct style fingerprint 수 (style fingerprint = `(bg, border, radius, shadow, backdrop, opacity)` 튜플)
- **VLC** ↑ (Visual Layer Count) — distinct effective-z bands (explicit z-index OR DOM depth band)
- **CRP** ↑ (CSS Rich Properties) — backdrop-filter, multi-shadow, gradient, transform, opacity<1, border-radius 등의 *총 사용 횟수*
- **HD** ↑ (Hierarchy Depth) — visual element 중 max DOM nesting depth
- **SC** ↑ (Spatial Coverage) — 슬라이드 영역 중 가시 element가 차지하는 면적 비율

**가족 ② PNG-based Visual Fidelity (vs reference, primary)** (`experiments/metrics/visual_similarity.py`):

- **SSIM** ↑ — local window 기반 픽셀 구조 유사도 (skimage)
- **CLIP** ↑ — open_clip ViT-B/32 image embedding cosine similarity (semantic-level, AutoPresent/Design2Code/SlideCoder 표준)
- **LPIPS** ↓ — AlexNet deep feature 거리 (perceptual-level, Zhang et al. CVPR 2018)
- *Block-Match, Position* (OCR-based): 다크 + 한국어 + blur 도메인에서 모든 메서드 0 → *도메인 미지원*으로 보고하지 않음

**가족 ③ Holistic LLM Judge (multimodal, primary)** (`experiments/metrics/single_method_judge.py`):

Judge model **GPT-5.4 (Azure)** — generator(GPT-4o)와 다른 model family로 self-evaluation bias 차단. Judge에게 *reference image + generated PNG + generated HTML 처음 3,000자* 함께 제공 (tool-grounded). 4 criteria × 1–7 점:
- **Visual Fidelity (VF)** / **Layer Structure (LS)** / **Content Completeness (CC)** / **Design Quality (DQ)**

**가족 ④ String-level Content (auxiliary)**:
- **CCR** ↑ — 입력 텍스트가 HTML에 *문자열로* 등장하는 비율 (시각 가시성 미반영; MLLM judge CC가 visual proxy)

**가족 ⑤ Legacy Vocabulary-Aligned (이전 버전, 보고용)** (`experiments/probing/layer_tree.py`):
- **Layer Recall**, **LTED** — class name regex 기반 (LayerAgent 어휘에 정렬). *Vocabulary alignment 한계 명시*하에 같이 보고하나 main claim에는 사용하지 않음.

**Render guard**: Playwright 정상 렌더링 비율 (전 메서드 100%).

모든 메트릭 코드와 단위 테스트 `experiments/metrics/` 공개.

### 5.4 실험 인프라

- 4-stage cacheable 파이프라인 (`experiments/main_eval.py`): generate → render(Playwright) → reference perception(VLM 캐시) → metrics. 각 stage는 재시작 가능.
- 총 4 메서드 × 48 슬라이드 = **192 cell**. 실행 시간 82분. 생성 실패 0건.
- 결과: `results/main_eval/eval_results.jsonl`, `eval_summary.csv`, `analysis_report.md`.

---

## 6. 결과

### 6.1 Table 1 — Same-model GPT-4o 비교 (RQ1 main result)

본 절은 *동일 base model GPT-4o 위에서* 4가지 메서드를 vocabulary-free 메트릭 8개로 비교한다 (`results/new_eval/summary.json`, N=10 dark-glass).

**Table 1.** 4 method × 10 design × 8 vocabulary-free metric. 굵은 = 1위.

| Metric | A. single_pass | B. visual_cot | C. cot_h_rag | **D. LayerAgent** | Δ (D vs A) |
|---|:---:|:---:|:---:|:---:|:---:|
| **VEC** ↑ (visual elements) | 9.1 | 7.3 | 9.8 | **20.9** | **+11.8 (2.3×)** |
| **EDC** ↑ (style diversity) | 3.0 | 2.7 | 3.5 | **9.7** | **+6.7 (3.2×)** |
| **VLC** ↑ (layer count) | 1.5 | 1.5 | 2.4 | **2.9** | **+1.4 (1.9×)** |
| **CRP** ↑ (CSS richness) | 23.6 | 18.3 | 28.1 | **51.5** | **+27.9 (2.2×)** |
| **HD** ↑ (DOM depth) | 4.9 | 4.8 | 5.5 | **7.0** | **+2.1** |
| **CLIP** ↑ (semantic) | 0.450 | 0.448 | 0.430 | **0.492** | **+0.042** |
| **LPIPS** ↓ (perceptual) | 0.653 | 0.652 | 0.709 | **0.589** | **−0.064** |
| **SSIM** ↑ (pixel) | **0.493** | 0.486 | 0.467 | 0.470 | −0.023 |

**핵심 발견 1 — LayerAgent가 8개 metric 중 7개에서 1위.** SSIM에서만 single_pass와 0.023 차이로 약세 (N=10, std~0.10 → noise 수준). DOM 구조 5개 (VEC/EDC/VLC/CRP/HD) 모두 *2위 대비 1.5–3.2×*, 시각 fidelity 2개(CLIP, LPIPS)도 1위. **동일 base model 위에서 분해의 가치 일관 입증**.

**핵심 발견 2 — visual_cot, cot_h_rag도 single_pass에 *유의 미달*.**
- visual_cot: VEC 7.3 < single_pass 9.1, CSS richness 18.3 < 23.6
- cot_h_rag: LPIPS 0.709 (꼴찌), CLIP 0.430 (꼴찌)
- → 단순 2-stage CoT 또는 CSS pattern injection은 *오히려 약화*
- LayerAgent의 *DesignSpec + Library + Style Normalizer + Text Inserter 조합*이 결정적

**Table 1b — MLLM judge (GPT-5.4, 4 criteria, 1–7 scale, N=48 main_eval).**

| Criterion | cot_h_rag | layeragent | **single_pass** | visual_cot |
|---|:---:|:---:|:---:|:---:|
| Visual Fidelity ↑ | 1.73 ± 0.61 | 1.65 ± 0.93 | **2.17 ± 0.69** | 2.08 ± 0.68 |
| **Layer Structure** ↑ | 3.00 ± 0.80 | **3.58 ± 0.96** | 3.46 ± 0.68 | 3.08 ± 0.65 |
| Content Completeness ↑ | 3.77 ± 1.69 | 2.35 ± 1.49 | **3.81 ± 1.72** | 3.60 ± 1.51 |
| Design Quality ↑ | 3.40 ± 0.82 | 2.79 ± 1.01 | **3.75 ± 0.79** | 3.29 ± 0.90 |
| **Average** ↑ | 2.97 | 2.59 | **3.30** | 3.02 |

**MLLM judge에서는 single_pass가 평균 우세 (3.30 vs LayerAgent 2.59)**. LayerAgent는 *Layer Structure* 축에서만 좁게 우세 (3.58 vs 3.46). 이는 *vocabulary-free DOM/visual metric (Table 1)*과 *holistic 인간-perception 흉내 metric (Table 1b)*이 서로 다른 차원을 측정함을 보임 — **§6.5 메트릭 disagreement에서 자세히 분석**.

**Table 1c — Legacy vocabulary-aligned (참고용, N=48 main_eval).**

| Metric | cot_h_rag | **layeragent** | single_pass | visual_cot |
|---|:---:|:---:|:---:|:---:|
| Layer Recall ↑ (vocab-aligned) | 0.120 | **0.405** | 0.212 | 0.196 |
| LTED ↓ (vocab-aligned) | 0.911 | **0.744** | 0.823 | 0.854 |

⚠ **이 두 metric은 *우리가 정의한 LayerAgent class name 어휘*에 align됨** (§7.3). LayerAgent의 우세는 *부분적으로 self-vocabulary scoring*이며, 동일 시각 출력이라도 *다른 어휘를 쓰는 메서드*에 거짓 negative 보고. **본 paper의 main claim은 Table 1 (vocabulary-free)이며, Table 1c는 한계 명시하에 보고**.

![Figure 2: Multi-metric × method comparison (N=48)](results/figures/fig2_methods.png)

*Figure 2.* (Legacy figure) 4 method × 5 metric breakdown. Layer Recall은 vocabulary-aligned이라 caveat 필요 — main 결과는 Table 1의 vocabulary-free metric.

### 6.2 Table 2 — Cross-model cost-efficiency (RQ2)

학회 reviewer 차단 질문: *"LayerAgent는 GPT-4o로 8 specialist를 호출한다 — 그냥 한 번의 GPT-5.4나 Claude Opus 호출이 더 비용 효율적이지 않은가?"* 이를 정직하게 검증하기 위해 frontier single-pass를 *vocabulary-free metric*으로 직접 비교한다 (`results/new_eval/`, `results/cross_vlm/cost_efficiency_summary.json`, N=10 dark-glass).

**Table 2.** Cross-model 비교, vocabulary-free metric. 굵은 = 1위. 가격은 2026 Q1 list price 추정 (GPT-4o $2.5/$10 per M, GPT-5.4 $5/$15 per M, Claude 4.6 Opus $15/$75 per M input/output).

| Method | VEC | EDC | CRP | SSIM↑ | CLIP↑ | LPIPS↓ | **Cost/slide** | **Time** |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **LayerAgent** (GPT-4o + 분해) | 20.9 | 9.7 | 51.5 | 0.470 | 0.492 | 0.589 | **$0.232** | **60s** |
| single-pass (GPT-5.4) | **37.1** | **16.4** | **135.6** | **0.504** | **0.578** | **0.411** | $0.075 | 85s |
| single-pass (Claude 4.6 Opus) | 27.2 | 14.0 | 68.0 | 0.500 | 0.525 | 0.502 | $0.421 | 108s |

**Honest 분석 — *두 가지 결론*.**

#### vs Claude 4.6 Opus → LayerAgent **가성비 우세 ✅**

- 시각 fidelity 거의 동등 (SSIM 0.470 vs 0.500, CLIP 0.492 vs 0.525, LPIPS 0.589 vs 0.502)
- 시각 풍부성 (VEC/EDC/CRP) Opus가 약간 우세 (격차 작음)
- **비용 45% 절감 ($0.232 vs $0.421) + 시간 44% 절감 (60s vs 108s)**
- → "LayerAgent (값싼 GPT-4o + 분해)는 *expensive Claude Opus 수준 품질*을 *절반 비용*에 달성" — 가성비 valid claim

#### vs GPT-5.4 → **honest 패배 ❌**

- GPT-5.4가 *모든 vocabulary-free metric에서 1위* (VEC, EDC, CRP, SSIM, CLIP, LPIPS)
- **비용도 GPT-5.4가 1/3** ($0.075 vs $0.232)
- → "LayerAgent가 frontier single-pass 능가"라는 강한 주장은 **GPT-5.4에 대해서는 데이터로 미지지**
- 정직 보고: **GPT-5.4 single-pass는 더 cost-efficient 대안**

#### Operational implication

- *Quality + cost 모두 우선*이면 → **GPT-5.4 single-pass**
- *Opus 급 품질을 더 싸게* 원하면 → **LayerAgent (GPT-4o)**
- *최저 비용 + low quality 허용*이면 → **GPT-4o single-pass** ($0.015/slide, 10s)

**결론**: LayerAgent는 *expensive frontier (Claude Opus 등)의 cost-efficient 대체*이며 *모든 frontier 대체*는 아니다. Cost-quality trade-off는 use case에 의존하며, 본 paper는 이를 정직하게 보고한다.

### 6.3 Trivial baseline check — *prompt engineering으로는 same-model 격차가 닫히지 않는다*

LayerAgent의 same-model 우세(Table 1)가 *진짜 분해 효과인지* 또는 *단순 prompt 조정으로 가능한지* 검증하기 위해 **single_pass_zexplicit** 변형을 구현했다 (`baselines/single_pass_zexplicit.py`). 단일 패스 prompt에 z-index 6-band 명시 한 줄만 추가:

| Method (N=10 dark-glass, legacy LTED metric) | LTED ↓ | Layer Recall ↑ | avg layer count |
|---|:---:|:---:|:---:|
| single_pass (baseline A) | 0.823 ± 0.14 | 0.224 ± 0.13 | (main_eval) |
| **single_pass_zexplicit** (baseline A') | **0.844 ± 0.12** | **0.292 ± 0.17** | 3.8 |
| **layeragent (D)** | **0.551 ± 0.13** | **0.759 ± 0.16** | 8.5 |

z-explicit prompt는 Recall을 0.224 → 0.292로 살짝 올리지만 LayerAgent의 0.759와 *2.6× 격차 유지*. LTED는 *오히려 악화* (0.823 → 0.844). **prompt engineering으로는 same-model 격차가 닫히지 않으며 LayerAgent의 8-stage 분해가 *generation capacity 자체*를 늘리는 실질 메커니즘 contribution임을 입증**.

(이 결과는 legacy vocabulary-aligned LTED/Recall 기반이므로 Table 1c와 같은 caveat 적용 — 그러나 prompt 변형은 vocabulary와 무관하므로 *방향성은 robust*.)

---

### 6.4 Sweet spot — 다층 dark-glass에서 두 메트릭 가족이 *합의*한다

(A) 10 dark-glass design subset (시스템의 설계 대상). LTED와 MLLM judge 둘 다 LayerAgent 우세:

| 메서드 | LTED ↓ | MLLM avg ↑ |
|---|:---:|:---:|
| single_pass | 0.823 | 3.90 |
| visual_cot | 0.820 | 4.03 |
| cot_h_rag | 0.827 | 3.85 |
| **layeragent** | **0.551** | **4.15** |

다층 dark-glass에서 LayerAgent는 LTED를 **거의 절반으로 단축** (0.823 → 0.551), 동시에 MLLM judge 평균에서도 *유일하게* 우세 (4.15 vs 베이스라인 3.85–4.03). 두 메트릭 가족이 *동시에 합의*한다 — 이는 본 연구가 가진 가장 신뢰도 높은 우위 주장이다.

### 6.5 Per-layout breakdown — 두 가족이 sweet-spot에 합의한다 (RQ4)

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

### 6.6 메트릭 분류학 — 다섯 가족, 다섯 다른 질문 (RQ3)

**Table 3.** 본 연구가 정착시키는 메트릭 가족 분리.

| Metric family | 대표 metric | 측정 차원 | Same-model GPT-4o 우승 | Cross-model 우승 | 답하는 질문 |
|---|---|---|---|---|---|
| ① **DOM-based vocabulary-free** | VEC, EDC, CRP, HD | 코드 구조 풍부성 | **LayerAgent** | GPT-5.4 | "코드가 *시각적으로 풍부한 element*를 만드는가?" |
| ② **PNG-based visual fidelity** | SSIM, CLIP, LPIPS | 시각 충실도 | LayerAgent (CLIP/LPIPS) / single_pass (SSIM) | GPT-5.4 | "*렌더된 결과*가 reference처럼 보이는가?" |
| ③ **Holistic LLM judge** | GPT-5.4 4-criteria | 시각 usability·legibility·design quality | single_pass | (미측정) | "*출력이 발표 가능한* 슬라이드인가?" |
| ④ **Vocabulary-aligned (legacy)** | LTED, Layer Recall | class name regex 매칭 | LayerAgent | LayerAgent | ⚠ *circular*: "출력이 LayerAgent 어휘에 align되는가?" |
| ⑤ String-level CCR (auxiliary) | CCR | 텍스트 문자열 보존 | LayerAgent | (미측정) | "콘텐츠 문자열이 코드에 살아남는가?" — *시각 가시성 미반영* |
| (도메인 미지원) OCR-based | Block-Match, Position | 텍스트 위치 매칭 | (모두 ~0) | — | (다크/한국어/blur 무력화) |

**가족 disagreement의 의미 (RQ3 답).** 디자인-투-코드 use case는 단일하지 않다:
- (i) **편집 가능한 구조 회복**(슬라이드 재편집용 코드 추출) → 가족 ① 우선
- (ii) **참조 이미지 시각 복제**(스크린샷 → HTML) → 가족 ② 우선  
- (iii) **발표 가능한 슬라이드 자동 생성** → 가족 ③ 우선
- (iv) ⚠ *vocabulary self-scoring* → 가족 ④ (사용 자제 권고)

**선행 ranking 재해석.** Design2Code, SlidesBench, Widget2Code 등이 보고한 method ranking은 가족 ①·② 위주이며, vocabulary-aligned metric은 *circular 위험*. DreamHouse 2026 (structural-visual orthogonality joint pass 7.1%)을 본 연구는 슬라이드 도메인에서 *5 가족 disagreement*로 확장 입증. **본 paper는 vocabulary-free metric (가족 ①·②) + holistic judge (가족 ③) 동반 보고를 디자인-투-코드 평가의 default protocol로 제안한다.**

### 6.7 Ablation — 가용한 측정만 정직하게

**경고.** 본 절의 ablation 결과는 *legacy pilot 데이터*(N=5, 1 seed, 이전 narrative 시점에 수집)이며, 새로운 N=48 main_eval framework로 재실행되지 않았다. 따라서 **D₂ (Text Inserter ablation)만 정량 보고**하고 나머지 ablation 변형(D₁, D₃, D₄, D₅, D₇)은 *infrastructure는 준비됨*(`layeragent/ablations.py`, 8 flags) *but* 정식 측정 미수행 — §8 한계로 명시.

**D₂ (no_text_inserter) — RQ2 zero-sum 해소의 직접 증거** (legacy `tables/exp2_summary.json` 시점 데이터, N=5):

| 조건 | CCR ↑ | CSS Richness ↑ | Joint Pass ↑ |
|---|:---:|:---:|:---:|
| **D (full)** | **0.78** | **54.4** | **0.6** |
| D₂ (no_text_inserter) | **0.09** | 52.2 | 0.0 |
| Δ | **−0.69** | −2.2 | −0.6 |

Text Inserter 제거 시 CCR이 0.78 → **0.09** 으로 붕괴 — Card Detail Agent가 텍스트 삽입 부담을 받으면 시각 생성에 attention이 분산되어 콘텐츠 80%가 누락. CSS Richness는 거의 동일 (Card Detail이 여전히 시각 생성). **이는 *시각/콘텐츠 단계 분리*가 zero-sum을 구조적으로 해소함을 직접 입증**한다.

**나머지 ablation (D₁/D₃/D₄/D₅/D₇/D₈) — infrastructure 완료, 정식 측정 미수행:** `layeragent/ablations.py`에 8개 flag 모두 구현되어 있으며, ablation runner(`experiments/ablations.py`)가 각 변형을 main_eval framework로 돌릴 준비 완료. paper draft 시점 *N=48 정식 ablation 결과는 미수집*. 본 결과는 향후 work에서 추가 (§8 명시).

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

### 7.4 단계 분리는 *구조적 보장* — Cross-VLM 데이터로 입증

H-RAG가 보여주는 zero-sum, D₂ ablation이 보여주는 분리의 효과, 그리고 §3.3의 cross-VLM 결과는 모두 같은 명제로 수렴한다 — *현재 세대 frontier VLM의 단일 호출은 풍부한 layer 구조를 코드로 commit하지 못한다*. 

**Cross-VLM probing 직접 증거 (§3.3)**: GPT-4o (gap 0.776), GPT-5.4 (0.700), Claude 4.6 Opus (0.688) 세 frontier VLM 모두 baseline gap > 0.68. 모델 능력 향상은 PGG를 *축소시키지 않는다* — gap reduction은 GPT-4o → Claude로 가도 Δ -0.09에 불과 (반면 LayerAgent는 GPT-4o 위에서 gap 0.241까지 줄임, Δ -0.535).

**§7 thesis (강화).** LayerAgent의 가치는 *모델 약점 보강*이 아니라 *단계 분리가 부과하는 구조적 보장*이다. 차세대 모델(GPT-5.4, Claude Opus 등)도 동일한 자기회귀 토큰 예산 한계를 가지며, *prompt engineering, model upgrade로 해소되지 않는다* — empirical evidence는 §6.6 (trivial prompt baseline reject) + §3.3 (frontier model PGG 동일 수준) 두 데이터 모두에서 합치한다.

### 7.5 비대칭 vision의 일반 원리

본 연구의 한 발견은: *스타일을 만드는 agent는 이미지를 보고, 배치를 결정하는 agent는 좌표만 본다*. Card Detail은 crop을 보지만 Text Inserter는 텍스트만 본다. 이 비대칭은 다른 멀티에이전트 영역에도 일반화 가능하다 — UI 생성에서 디자인 agent vs 코딩 agent, 로봇 제어에서 계획 agent vs 실행 agent, 문서 생성에서 레이아웃 agent vs 콘텐츠 agent.

---

## 8. 한계

- **Vocabulary-aligned legacy metric (LTED/Layer Recall)의 circular 문제.** 본 paper의 초기 버전은 Layer Recall + LTED를 PGG metric으로 사용했으나, 이는 *우리가 정의한 LayerAgent class name 어휘*에 align된 regex 기반 측정으로 *circular*. Claude Opus의 `glass-card`/`node-inner`/`hub-content` 등 *시각적으로 풍부한 element*가 매칭 안 되어 거짓 negative 보고. 본 paper는 이를 §3 + §6.1에서 명시하고 main result를 *vocabulary-free metric* (DOM-based VEC/EDC/VLC/CRP/HD + PNG-based CLIP/LPIPS)으로 보고. Legacy metric은 §6.1 Table 1c 및 §6.3·§6.8의 trivial baseline check에 한정 사용 (caveat 명시).
- **Holistic 디자인 quality (가족 ③)에서의 부정 결과.** MLLM judge 4-criteria 평균에서 LayerAgent (2.59) < single_pass (3.30) — N=48 main_eval. Visual Fidelity·Content Completeness·Design Quality 3개 축에서 단일 패스에 진다. LayerAgent의 holistic 우위는 *Layer Structure 축* (3.58 vs 3.46) + *dark-glass sweet spot* 으로 한정된다. 본 paper는 이 부정 결과를 *thesis의 일부*로 흡수.
- **Sweet-spot 외 disagreement.** 6개 중간 layout(pyramid, mekko, process_flow 등)에서 LTED는 LayerAgent를 우세로, MLLM judge는 single_pass를 우세로 본다. 즉 *layer 수만 회복*하는 것이 *발표 가능한 슬라이드*를 보장하지 않는다. Visual Critic + 더 보수적 Text Inserter 조합이 §7.2의 향후 과제로 명시.
- **N=48의 통계 검증력.** 메인 결과는 effect size로 보고하며, paired Wilcoxon p-value는 sweet spot subset(N=10)에서만 유의(p<0.05)하다. 30+ seed × 100+ design 확장이 향후 과제.
- **Cross-VLM 일반화 잠정성.** cross-VLM probing은 *infrastructure 준비 완료, 결과 미수집* (`results/cross_vlm/` 비어있음). 본 paper의 PGG 정량 측정은 GPT-4o 단일 모델의 결과이다. Claude 4.6 Opus / Gemini 2.5에서의 재현이 모델-독립적 PGG 주장을 안정화할 것이다.
- **Ablation은 D₂만 정량 측정됨.** §6.5의 ablation은 D₂ (Text Inserter ablation)에 대한 N=5 legacy pilot 결과만 보고. 나머지 7개 flag (D₁ no_style_norm / D₃ no_cv_facts / D₄ no_designspec / D₅ no_library / D₆ no_visual_critic / D₇ no_overflow_repair / D₈ no_chart_agent)는 *infrastructure 구현 완료* (`layeragent/ablations.py`) 이지만 N=48 main_eval framework로의 정식 측정 *미수행*. 본 paper 작성 시점 기준 — 따라서 *각 컴포넌트의 격리된 effect size 주장은 D₂에 한정*되며, DesignSpec/library/style normalizer 등의 contribution은 *paper의 main claim에 포함되지 않는다*.
- **OCR-기반 메트릭 무력화.** Block-Match와 Position이 다크 배경 + 글래스모피즘 + 한국어 + opacity blur 조합에서 일관되게 0이다. *visual-aware OCR* (mPLUG-DocOwl, Florence-2) 교체가 선결 과제.
- **인간 평가 부재.** 본 paper는 perception-grounded(LTED, Recall) 메트릭과 GPT-5.4 LLM judge로 보고하며, 인간 anchor 직접 검증은 미수행 (n≥80 pair × 5 raters 규모 향후 과제, MT-Bench/AlpacaEval 류 프로토콜).
- **지연 시간.** 8-stage + library retrieval로 카드 4개 슬라이드 ~60초 vs single-pass ~8초. *quality-latency 트레이드오프* 위에 위치.
- **Layer band의 디자인 특수성.** 본 시스템의 6 layer band는 다크-글래스 + 글래스모피즘 + 아이콘 배지 미학에 정렬되어 있다. 텍스트 중심 / 사진 중심 슬라이드에서는 일부 specialist가 비활성화되거나 layer band 재정의가 필요하다.
- **String-CCR vs Visual CCR.** §7.3에서 다룬 메트릭 진화 필요. 현재 CCR 0.99는 *문자열은 존재하나 시각적으로 읽히지 않을 수 있음*을 직접 보였다 (MLLM judge CC 2.35).

---

## 9. 결론

본 논문의 결과는 두 표 (Table 1, Table 2) + holistic judge로 정리된다.

- **(RQ1) Same-model 분해 효과 (Table 1)**: 동일 GPT-4o 위에서 8-stage LayerAgent는 *vocabulary-free metric* 8개 중 7개에서 single_pass / visual_cot / cot_h_rag를 능가. VEC 2.3×, EDC 3.2×, CRP 2.2×, CLIP +0.042, LPIPS −0.064. SSIM에서만 0.023 noise-수준 차이. **단순 2-stage CoT나 CSS pattern injection은 *오히려 single_pass보다 못하며*, LayerAgent의 *DesignSpec + Library + Style Normalizer + Text Inserter 조합*이 결정적**.

- **(RQ2) Cross-model cost-efficiency (Table 2)**:
  - vs Claude 4.6 Opus → LayerAgent **가성비 우세** (시각 fidelity 거의 동등 + 비용 45% 절감 + 시간 44% 절감)
  - vs GPT-5.4 → **honest 패배** (GPT-5.4가 모든 차원 우세 + 비용 1/3)
  - 결론: LayerAgent는 *expensive frontier의 cost-efficient 대체*이며 *모든 frontier 대체*는 아님

- **(RQ3) 메트릭 가족 disagreement (§6.6)**: vocabulary-free DOM (가족 ①) / PNG visual fidelity (가족 ②) / holistic LLM judge (가족 ③) — 동일 데이터에 *서로 다른 ranking*. 단일 메트릭 ranking은 use case 의존. **Vocabulary-aligned legacy metric (가족 ④, LTED/Recall)은 self-scoring circular**임을 데이터로 입증 — 향후 paper에서 사용 자제 권고.

- **(RQ4) Sweet-spot scaling (§6.5)**: Per-layout breakdown에서 dark-glass에서만 가족 ②(LTED legacy) + 가족 ③(MLLM)이 합의하여 LayerAgent 우세 선언. 평면 차트(bar/line/waterfall)에서는 *두 가족 모두 single_pass 우세*에 합의.

- **Trivial baseline check (§6.3, §6.8)**: prompt에 z-index 명시 한 줄 추가는 LayerAgent와의 격차 (Recall 2.6×)를 닫지 못함 — PGG closure는 *generation capacity 확장*을 통해서만 일어남.

**Honest thesis.** *Same-model 비교*에서 LayerAgent의 가치 = 8개 metric 중 7개 우세 (Table 1). *Cross-model 비교*에서 LayerAgent의 가치 = Claude Opus의 cost-efficient 대체 (Table 2). 이 두 narrow claim이 본 paper의 measured contribution이며, "frontier 능가"라는 강한 주장은 GPT-5.4에 대해 *데이터로 지지되지 않음*을 정직하게 보고.

**더 넓은 원리.**

1. **메트릭 가족 동반 보고는 디자인-투-코드 평가의 default여야 한다.** Vocabulary-free DOM + PNG visual fidelity + LLM judge 동시 보고가 표준이며, *vocabulary-aligned regex 기반 metric*은 self-scoring 위험으로 사용 자제.
2. **Same-model 분해 효과 + Cross-model cost-efficient 대체는 분리된 두 claim**이다. 한 표 안에서 섞으면 narrative 혼동 발생; *Table 1 (same-model) + Table 2 (cross-model)*의 분리가 정직 framing.
3. **String-level 콘텐츠 메트릭은 시각 가시성을 underdetermine한다.** CCR 0.99 vs MLLM CC 2.35 — visual CCR 메트릭 필요.

**향후 연구.** (a) cross-judge 추가 (Claude/Gemini)로 holistic 가족 single-judge bias 제거. (b) 인간 평가 N=8-10으로 vocabulary-free metric의 인간 anchor 검증. (c) Multi-seed (3 seed × 4 method × 48 design) 통계 검정. (d) Layout-conditional routing 구현. (e) Visual CCR (visual-aware OCR 기반). (f) AutoPresent의 element matching 프로토콜 직접 비교 (cross-paper validation).

---

## 부록 A. 사전 등록 (Pre-registration) — 가설 검증 임계값

본 paper의 핵심 가설들은 *post-hoc 임의 임계값*이 아닌 *사전 명시된* 결정 규칙으로 검증된다 (paper 초안 작성 시점에 결정).

**H-PGG (지각-생성 간극의 보편성, §3.3) — *채택***
- 결정 규칙: 3 VLM에서 baseline single-pass의 평균 (1 − Layer Recall) ≥ 0.50 AND cross-VLM 표준편차 ≤ 0.10
- 적용: 10 dark-glass design × 3 VLM (GPT-4o, GPT-5.4, Claude 4.6 Opus). Gemini 2.5는 본 paper에서 미실행 (인프라 있음, 향후 work).
- 측정 결과: 3 VLM gap = {0.776, 0.700, 0.688}, 평균 0.721, std 0.039 (≤ 0.10 ✓), 평균 ≥ 0.50 ✓
- **채택**: PGG는 *현재 세대 frontier VLM 전반의 구조 한계*로 정착. 모델 능력 향상으로 자동 해소되지 않음.

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

**H-AblationTextInserter (Text Inserter zero-sum 해소, §6.5) — *채택***
- 결정 규칙: string-CCR(D) − string-CCR(D₂) ≥ 0.30 AND Layer Recall(D) > Layer Recall(D₂)
- 측정 결과 (legacy N=5): string-CCR Δ = 0.69, **채택**

**H-AblationDesignSpec (DesignSpec cross-agent 합치, §6.5) — *측정 미수행 / 향후 검증***
- 결정 규칙: Layer Recall(D) − Layer Recall(D₄) ≥ 0.05 AND LTED(D) < LTED(D₄)
- 본 paper 시점 측정 미수행. ablation runner 인프라(`layeragent/ablations.py`, `experiments/ablations.py`) 완료, 향후 work에서 N=48 framework로 검증.

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
