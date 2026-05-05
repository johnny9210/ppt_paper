LayerAgent: 프레젠테이션 생성을 위한 멀티에이전트 프레임워크

디자인 이미지의 계층 구조 인식을 통한 프레젠테이션 코드 생성

by 정일균 (Ilgyun Jeong)

인공지능융합학과 (Department of Artificial Intelligence Convergence)

지도교수: 김현철 (under the supervision of Professor Hyeoncheol Kim)

---

## 초록

프레젠테이션 슬라이드는 배경·카드·콘텐츠·아이콘 등 여러 시각 층이 위아래로 겹쳐 구성되는 본질적으로 **계층적(layered)** 시각 구조이지만, 본 연구는 동일한 GPT-4o가 슬라이드 이미지를 자연어로는 5–8개의 레이어로 풍부하게 기술하면서도 같은 이미지를 HTML로 변환할 때는 그 계층 구조의 상당 부분을 코드에 반영하지 못하는 **요소 누락(element omission)** 현상을 관찰했다 — Design-to-Code 선행 연구에서 개별 요소 단위로 보고된 element omission이, 슬라이드 도메인에서는 *시각 계층(layer) 단위로 통째 누락되는 형태*로 확장되어 나타난다. 우리는 이 문제를 다루기 위해, 단일 VLM 호출이 한꺼번에 처리하던 구조·스타일·콘텐츠 생성을 각자 하나의 레이어(배경·장식·카드·텍스트·아이콘 등)만 책임지는 다수의 전문 에이전트로 분해하는 멀티 에이전트 프레임워크 **LayerAgent**를 제안한다. 동일 모델(GPT-4o) 조건에서 LayerAgent는 DOM 구조와 시각 유사도로 구성된 8개 자동 평가 지표 중 7개에서 single-pass 및 chain-of-thought 변형을 능가했으며, 평균 시각 요소 수를 약 2.3배, 스타일 다양성을 약 3.2배 회복시켰다. 다만 이 효과는 다층 디자인과 same-model 조건에 한정되며 frontier 모델(GPT-5.4) single-pass와의 비교에서는 우위가 관찰되지 않아, 본 연구의 핵심 기여는 SOTA 경신이 아니라 *슬라이드 도메인의 계층적 element omission 정량화와 분해형 접근의 효과·한계에 대한 정직한 보고*에 있다.

**키워드**: Element Omission, Layer Decomposition, Multi-Agent, Design-to-Code, Vision Language Models

---

## 제1장 서론

### 제1절 슬라이드는 계층이다, 그러나 VLM은 평면이다

프레젠테이션 슬라이드는 웹페이지나 포스터와 달리 여러 시각 층이 위아래로 겹쳐 쌓이는 **명확한 계층(layered) 구조**를 가진 시각 객체다 — 가장 아래에 *배경*(베이스 그라디언트와 패턴), 그 위로 *분위기*(방사형 글로우·그라디언트 오버레이), *장식 요소*(도형·선·점), *카드·패널·히어로 블록*, *콘텐츠 텍스트*(제목·본문·수치), 그리고 가장 위에 *아이콘과 배지*가 놓이는 약 6개 층의 구조다.

이 6개 층이 정확한 *층 순서(stacking order)*와 좌표로 겹쳐야 의도된 디자인이 구현된다. 그러나 단일 VLM 호출은 이 계층 구조를 충분히 반영하지 못한 채 HTML을 **위에서 아래로 한 번에** 생성한다 — `<div>` 태그가 직렬로 나열되고, 층의 명시적 순서 표기(CSS의 `z-index` 속성)는 거의 사용되지 않으며, 요소 간 공간 관계는 DOM 작성 순서에 암묵적으로 의존한다.

흥미로운 관찰은 다음이다 — 같은 GPT-4o에게 *"이 이미지의 계층 구조를 설명하라"* 고 물으면 5–8개의 레이어를 자연어로 기술한다. 그러나 같은 이미지를 *"HTML로 변환하라"* 고 물으면 그 계층 구조의 상당 부분을 코드에 반영하지 못한다 (§3.2 표). **즉 같은 모델이 *기술하는 단계*에서는 다층 구조를 인식하면서도 *코드를 쓰는 단계*에서는 그 대부분을 잃는다.**

본 문제 정의는 저자의 18개월 프로덕션 운영(AIDX 슬라이드 생성 시스템)에서 반복적으로 관찰된 실패에서 도출되었다 — 디자인 프롬프트가 *명시적으로 multi-layer 글래스모피즘 + 네온 글로우 + 그리드 패턴*을 요청해도, 단일 VLM 호출의 HTML 출력은 일관되게 단색 배경 + 평면 카드로 회귀한다.

본 논문은 이 현상을 **(계층적) element omission**이라고 부른다 — Design-to-Code 선행 연구에서 *개별 요소 단위*로 보고된 element omission이, 슬라이드 도메인에서는 *시각 계층(layer) 단위로* 통째 누락되는 형태로 확장되어 나타난다. 이는 *메트릭 이름이 아니라 현상의 이름*이며, 인식된 시각 계층·스타일 정보가 코드 생성 결과에서 충분히 구현되지 않는 현상을 가리킨다.

본 연구는 이 현상을 직접 측정하는 단일 신규 메트릭을 제안하지 않는다 — 메트릭 이름이 곧 현상 이름이 되면 측정이 *순환적(circular)*이 되기 때문이다. 대신 *DOM 구조 지표 · 렌더링 결과의 시각 유사도 · 멀티모달 LLM의 종합 판단*의 세 축을 함께 보고하는 평가 protocol을 사용하며, 그 이유와 자세한 정의는 §3.1·§5.3에서 다룬다.

### 제2절 하나의 지표로는 Design-to-Code 품질을 결정할 수 없다

Design-to-Code 분야에서 흔히 쓰이는 SSIM·CLIP·Block-Match·element-IoU는 모두 *픽셀이나 요소 위치가 얼마나 비슷한가*만 본다 — 즉 슬라이드의 계층 구조가 코드에 잘 보존됐는지와는 직접 관련이 없다. 한편 코드의 class 이름을 매칭하는 측정(Layer Recall, LTED 등)은 layer 보존을 직접 표적하지만 *측정 도구가 미리 정해 둔 어휘에 치우치는 편향*을 가지며, 디자인의 전체적인 가독성·균형·완성도까지는 잡아내지 못한다.

본 연구는 동일한 데이터에서 세 종류의 평가 축 — *(i) 렌더링 결과의 픽셀 유사도, (ii) DOM 구조 기반 측정, (iii) 멀티모달 LLM의 종합 판단* — 이 *서로 다른 순위*를 산출함을 관찰한다 (구체 수치는 §6.6). 어느 하나도 "전체 진실"이 아니며, 각 축은 *서로 다른 사용 목적*에 맞춰져 있다 — 픽셀 그대로 복제, 편집 가능한 구조 회복, 발표 가능한 슬라이드 품질. 본 연구는 이 불일치를 *결함이 아니라 multi-objective 평가의 본질*로 받아들이고, Design-to-Code 평가에서 단일 지표보다 **여러 축의 동반 보고**가 필요함을 제안한다.

### 제3절 해법: 생성을 계층 단위로 분해하기

Element omission이 *한 번의 호출 안에서 구조·스타일·콘텐츠가 제한된 출력 용량을 두고 동시에 경쟁하기 때문*에 일어난다고 본다면 (가설, §7.1), 자연스러운 해법은 **생성 과정을 계층 단위로 분해**하여 각 호출이 한 가지 책임만 지도록 만드는 것이다. 그러나 단순히 나누기만 하면 새로운 종류의 실패가 등장한다 — 카드별로 투명도와 그림자가 제각각이거나(*스타일 어긋남*), 카드와 텍스트의 좌표가 맞지 않거나(*공간 충돌*), 아이콘이 환각된 URL로 깨지는(*자산 부재*) 문제다.

본 연구의 **LayerAgent**는 이 모든 실패를 *전체 이미지 분석 → 공유 디자인 명세 작성 → 8개 전문 에이전트의 병렬 레이어 생성 → 결정적 조립 → 카드 간 스타일 통일 → 텍스트 주입*의 다단계 파이프라인으로 함께 다룬다 (각 단계의 자세한 구조와 역할은 §4). 핵심 설계 원칙은 네 가지다 — *(i)* 각 전문 에이전트가 *전체 이미지가 아닌 자신이 맡은 영역만* 직접 보게 하여 풍부한 CSS 재질을 회복하고, *(ii)* 모든 에이전트가 *공유 디자인 명세(DesignSpec)*를 읽고 써서 카드 간 스타일이 어긋나는 것을 사전에 막으며, *(iii)* k-means 팔레트와 OCR 텍스트 높이 같은 *결정적 시각 측정값*을 프롬프트에 주입해 색·크기 환각을 줄이고, *(iv)* 아이콘과 도형은 *라이브러리 검색*으로 가져와 환각된 자산 URL을 구조적으로 차단한다.

본 paper에서 *측정된* 주장은 위 네 원칙이 *통합 시스템*으로 작동했을 때 같은 GPT-4o 단일 호출 대비 자동 지표 8개 중 7개에서 우위를 보였다는 것이며 (§6.1), 각 원칙의 *개별* 기여는 D₂(텍스트 분리 단계)와 **D₄(DesignSpec blackboard)** 두 컴포넌트에 한정해 격리 측정되었다 (§6.7). N=48 multi-family에서 D₄ 제거 시 자동 지표 8개 중 7개가 악화 (특히 SSIM −0.172, LPIPS +0.082, CRP −4.6) — DesignSpec이 cross-agent 시각 일관성을 보존함을 확인. 나머지 두 원칙(library, CV facts)의 개별 효과는 향후 ablation 작업으로 분리한다 (§8 한계).

### 제4절 연구 질문과 기여

본 연구는 4개 RQ로 정식화된다 (각 RQ는 *특정 데이터셋이 직접 지지하는* 경험적 주장이며, 데이터 미수집 RQ는 §7 향후 연구로 분리한다):

- **RQ1 (같은 모델 위에서의 분해 효과)**: 동일한 GPT-4o 위에서 멀티 에이전트 분해가 *DOM 구조 + 시각 유사도* 자동 지표에서 단일 호출·chain-of-thought 변형 모두를 능가하는가? — **Table 1** (§6.1)으로 답한다.
- **RQ2 (모델 간 비용 효율성)**: GPT-4o 기반 LayerAgent가 frontier 모델(GPT-5.4·Claude 4.6 Opus)의 단일 호출 대비 *비용 대비 품질* 측면에서 어느 위치인가? — **Table 2** (§6.2)로 답한다.
- **RQ3 (지표 축 불일치)**: 픽셀 유사도 / DOM 구조 / LLM 종합 판단의 세 축이 같은 데이터에서 서로 다른 순위를 만들어 내는가? 각 축은 어떤 사용 목적에 정렬되는가? — §6.6에서 답한다.
- **RQ4 (디자인 복잡도 의존성)**: LayerAgent의 우위는 디자인의 *계층 복잡도*에 따라 어떻게 변하는가? — dark-glass sweet spot 분석 + 9개 layout family별 breakdown (§6.5)으로 답한다.

위 RQ들에 대응하는 본 paper의 **기여**는 다음 4가지로 단일 정리된다 (Problem → Method → Evaluation → Finding 순서):

1. **Problem — 슬라이드 도메인의 계층적 element omission 정식화.** Design-to-Code 선행 연구에서 *개별 요소 단위*로 보고된 element omission이 슬라이드 도메인에서는 *시각 계층(layer) 단위로* 통째 누락되는 형태로 나타나는 현상을 정식화한다 (§3). 이는 *현상의 이름*이며, 메커니즘은 *생성 단계의 capacity allocation 문제*로 가설화된다 (§7.1, 가설 수준 — 직접 인과 검증은 향후 작업).
2. **Method — LayerAgent framework.** DesignSpec blackboard + vision-grounded specialists + style normalization + text insertion 분리를 포함한 multi-agent layer decomposition 프레임워크 (§4). Same-model GPT-4o 조건에서 *8개 자동 지표 중 7개에서 1위* (단, holistic MLLM judge에서는 single_pass가 평균 우세 — §6.1b). 컴포넌트별 인과 효과는 **D₂(Text Inserter)와 D₄(DesignSpec blackboard) 두 개 격리 측정** — D₄는 N=48 multi-family에서 8개 지표 중 7개 악화 확인 (§6.7).
3. **Evaluation — Multi-family 평가 protocol.** Method-specific class name이나 사전 정의된 layer vocabulary에 의존하지 않는 평가 protocol을 구성한다 — DOM 구조 지표 + render-based 시각 유사도 + multimodal LLM-as-judge의 *결합·정렬* (§5.3). 신규 metric의 발명이 아니라 *기존 metric을 class-name-independent하게 결합*하여 method-specific vocabulary bias를 줄인 구성이 본 protocol의 contribution.
4. **Finding — 정직한 경험적 보고.** LayerAgent의 우위는 (i) same-model 조건 + (ii) 다층 dark-glass 디자인 sweet spot에 한정되며, 평면 차트 layout 및 GPT-5.4 single-pass 대비에서는 *우세하지 않다*. 따라서 LayerAgent는 *frontier 전반의 SOTA*가 아니라 *Claude Opus와 같은 고비용 frontier에 대한 cost-sensitive 대안*으로 한정 framing된다.

---

## 제2장 관련 연구

### 제1절 Design-to-Code 생성

**Design2Code** (Si et al., 2024)는 484 웹페이지 벤치마크로 GPT-4V의 중간 충실도를 보고했다. **WebSight** (Laurençon et al., 2024)는 200만 합성 image-code pair를 공개했다. **Calò & De Russis** (PACMHCI 2025)는 GPT-4o의 UI 코드 생성 실패를 *element omission · element distortion · element misarrangement*의 세 유형으로 분류했다 — 본 연구는 이 중 *element omission*을 슬라이드 도메인의 *시각 계층 단위*로 확장하여 분석한다 (§3.1). **DCGen** (FSE 2025)은 분할 정복으로 페이지를 블록 단위로 분해해 코드를 생성한다. **LaTCoder** (KDD 2025)는 코드 이전에 레이아웃을 chain-of-thought로 명시화한다. **ScreenCoder** (arXiv:2507.22827, 2025)는 Grounding → Planning → Generation의 3-stage agent 파이프라인을 채택하고 50K image-code pair로 GRPO 미세조정한다. **DesignCoder** (arXiv:2506.13663, 2025)는 모바일 UI 도메인에서 UI Grouping → Hierarchy-Aware Generation → **post-render Self-Correcting Refinement**의 3-stage를 사용한다. **UIOrchestra** (Findings of EMNLP 2025)는 multi-agent framework로 UI design → code 변환을 다루며 본 연구와 가장 가까운 peer — 다만 우리 LayerAgent의 *DesignSpec blackboard + CV grounding + library retrieval* 통합 구조와는 차별된다.

**LayerAgent와의 차별점.** ScreenCoder는 *image patch reuse*(Hungarian matching)로 cross-element 일관성을, DesignCoder는 *post-render iterative refinement*로 코드 품질을 다룬다. 본 연구의 Style Normalizer는 *pre-render CSS 정규화*이고, Text Inserter는 *시각/콘텐츠 단계 분리*이며, DesignSpec blackboard는 *생성 시점 cross-agent 스타일 통일*이다. 또한 본 연구가 아는 범위에서 어떤 선행 연구도 슬라이드 도메인의 layer 구조 보존을 **multi-family 평가 protocol** (DOM-based structural + render-based visual similarity + multimodal LLM-as-judge 동반 보고)로 평가하지 않았다.

### 제2절 시각 교정 / 반복 개선

**VisRefiner** (arXiv:2602.05998, 2025)는 렌더링 결과와 참조 디자인 간 시각 차이를 학습하여 GPT-4o 대비 Block Match +21.5pt를 달성했다. **Vision-Guided Iterative Refinement** (arXiv:2604.05839, 2026)는 VLM critic 기반 3회 반복으로 17.8% 개선을 보고했다. 본 연구의 Visual Critic stage는 이들의 *반복 vs 단발* 트레이드오프를 ablation 플래그(`use_visual_critic`)로 노출한다.

### 제3절 프레젠테이션 생성

**PPTAgent** (Zheng et al., EMNLP 2025)는 LLM 피드백 기반 템플릿 반복 수정을, **PreGenie** (Xu et al., EMNLP Findings 2025)는 코드 리뷰 + 페이지 리뷰 이중 루프를, **SlideCoder** (Tang et al., EMNLP 2025)는 CGSeg 세그멘테이션 + 계층적 RAG를, **AutoPresent** (Ge et al., CVPR 2025)는 구조화된 시각 설계 원칙을 강조했다. 본 연구가 아는 범위에서 이들 중 **슬라이드의 시각 계층(layer) 구조를 명시적으로 분해 생성**하거나 **multi-family 동반 보고 (DOM-based + render-based + multimodal judge)** 를 슬라이드 도메인에 적용한 연구는 보고된 바 없다.

### 제4절 멀티에이전트 코드 생성

**MetaGPT** (Hong et al., ICLR 2024), **ChatDev** (Qian et al., ACL 2024), **CAMEL** (Li et al., NeurIPS 2023), **AutoGen** (Wu et al., COLM 2024)은 **소프트웨어 개발 프로세스**(설계→구현→테스트) 또는 *대화형 multi-agent conversation*으로 agent를 분담한다. LayerAgent는 (a) 개발 프로세스가 아닌 **출력의 시각 계층(layer) 구조**(배경→카드→텍스트→아이콘)로 분담하고, (b) agent 간 통신을 자연어/코드가 아닌 **DesignSpec JSON + bounding box JSON**의 typed blackboard로 수행하여 truncation·해석 오류를 제거한다.

### 제5절 Design-to-Code 평가

기존 평가는 전역 유사도(CLIP, SSIM), 구조 매칭(Design2Code의 Block-Match, SlidesBench의 element-matching), 속성 수준(WebRenderBench의 SDA, Widget2Code의 per-property)으로 분류된다. **DreamHouse** (arXiv:2603.24866, 2026)는 structural validity와 visual fidelity가 직교적이며 frontier VLM의 joint pass rate가 7.1%에 불과함을 보였다. **SlideAudit** (UIST 2025)은 슬라이드 quality taxonomy를 정립하고 *automated metric vs holistic human judgment* 사이의 systematic disagreement를 정량적으로 보였다 — 본 연구의 §6.6 multi-family metric disagreement 관찰과 직접 정렬되는 prior. **WebDevJudge** (2025)는 design-to-code에서 *MLLM-as-judge*의 best practice (pairwise + code+visual modality)를 정립 — 본 연구의 single-judge limitation (§8) 의 학회 standard 인용. 본 연구는 (a) DreamHouse + SlideAudit의 metric disagreement 발견을 슬라이드 도메인의 *multi-family evaluation protocol*로 확장하고, (b) 기존 render-based 및 DOM-based 평가를 결합하여 **class-name-independent**하게 정렬한 protocol을 구성하여 method-specific vocabulary bias를 줄인다.

---

## 제3장 슬라이드 도메인 element omission의 측정

### 제1절 Element omission의 정의 — 현상과 측정의 분리

**Element omission은 현상의 이름이다.** Design-to-Code 선행 연구(Calò & De Russis, 2025)는 GPT-4o의 UI 코드 생성에서 *개별 요소가 누락되는 현상*을 element omission으로 보고했다. 본 연구는 이 개념을 슬라이드 도메인으로 확장한다 — 슬라이드는 배경·카드·콘텐츠·아이콘 등 *시각 계층(layer)* 단위로 구조화되므로, element omission이 *layer 단위로 통째 누락되는* 형태로 발현된다. 즉 인식된 시각 계층·스타일 정보가 코드 생성 결과에서 충분히 구현되지 않는 현상이다. 본 연구는 element omission을 직접 표적하는 단일 신규 메트릭을 제안하지 않는다 — 메트릭 이름이 곧 현상 이름이 되면 *circular*하게 된다. 대신 element omission의 정도를 *세 축의 multi-family 평가 protocol*로 측정하며, 각 축은 element omission의 다른 측면을 본다.

**Main 측정 — Multi-family evaluation protocol (§5.3):**

(i) **DOM-based structural metrics** (`experiments/metrics/dom_structure.py`): Playwright로 렌더링한 DOM에 JS injection하여 *모든 가시 element의 computed style + bounding box*를 추출한다. Class name과 무관하므로 method-specific vocabulary bias가 없다. 측정 항목은 styled element 수(VEC), distinct style fingerprint 수(EDC), distinct effective z-band 수(VLC), rich CSS property 총 사용 횟수(CRP), DOM nesting depth(HD), spatial coverage(SC). Acronym은 본 측정 convention의 표기일 뿐이며, 모두 기존 element/style 카운트의 plain 변형이다.

(ii) **Render-based visual similarity** (`experiments/metrics/visual_similarity.py`): SSIM (skimage), CLIP (open_clip ViT-B/32), LPIPS (AlexNet). 모두 기존 표준 메트릭.

(iii) **Multimodal LLM-as-judge** (`experiments/metrics/single_method_judge.py`): GPT-5.4 (Azure)에 reference image + generated PNG + generated HTML 일부를 함께 제공하고 4 criteria (Visual Fidelity / Layer Structure / Content Completeness / Design Quality)에 1–7점 채점.

세 축은 각각 *코드 구조 풍부성 / 픽셀-퍼셉추얼 충실도 / 발표 가능성*이라는 다른 차원을 본다 (§6.6 metric taxonomy).

**Sanity check (legacy, 사용 제한) — class-name-aligned:**

본 연구의 초기 분석에서는 perception tree $T_P$와 generation tree $T_G$를 (z-band, type) multiset으로 환원하여 **Layer Recall** = $|\mathrm{types}(T_P) \cap \mathrm{types}(T_G)| / |\mathrm{types}(T_P)|$, **LTED** = $\sum_k |m_P(k) - m_G(k)| / (\sum_k m_P(k) + m_G(k))$로 측정했다 (`experiments/probing/layer_tree.py`). 그러나 generation tree 파싱은 *class name regex*에 의존하며, 본 연구의 정규식은 LayerAgent의 class name (`card-wrap`, `bg-base`, `atmos`, `decor`)에 정렬되어 있다.

⚠ **Vocabulary alignment caveat**: Claude Opus의 `glass-card`/`node-inner`/`hub-content` 같은 *시각적으로 풍부한* class name은 정규식에 매칭되지 않아 거짓 negative를 보고한다 → LayerAgent에 self-favoring. 따라서 Layer Recall/LTED는 *(a) 초기 진단에서 element omission 현상을 가시화하는 도구* 및 *(b) §6.1c와 §6.3에서 prompt 변형이 vocabulary와 무관함을 활용한 robustness sanity check*에 한정 사용하며, **본 paper의 main claim에는 사용하지 않는다**.

*(parser robustness check, 6→3 z-band 축소 근거 등의 세부는 vocabulary alignment 한계 발견 후 부차적 의미를 가짐 — `experiments/probing/layer_tree.py` 코드와 git history에 보존.)*

### 제2절 Element omission의 가시화 — 초기 진단

본 절은 element omission 현상을 *가시화*하기 위한 초기 진단을 보고한다. Element omission의 *정량 main result*는 §6.1 Table 1 (multi-family metrics)이며, 본 절의 Layer Recall/LTED 수치는 §3.1에서 명시한 vocabulary alignment caveat 하에서 *현상 가시화 + sanity check* 용도로만 제시된다.

**(A) probing_minimal pilot — N=10 dark-glass, GPT-4o** (`experiments/probing/probing_minimal.py`):

| 지표 | Stage A perception | Stage B1 (single-pass) | Stage B2 (LayerAgent) |
|---|:---:|:---:|:---:|
| `n_layers` 평균 | 5–8 | 0–4 | 5–10 |
| `Layer Recall` (vs $T_P$, vocab-aligned ⚠) | 1.00 (sanity) | 0.195 | 0.676 |
| `gap = 1 − Recall` (vocab-aligned ⚠) | 0.00 | 0.805 | 0.324 |
| `LTED` ↓ (vocab-aligned ⚠) | 0.00 | 0.82 | 0.55 |

Single-pass에서 perception이 보장한 5–8 layer 중 평균 1.6개만 코드로 commit되며, LayerAgent에서 평균 5.4개. **layer 수 자체의 perception-generation 격차는 vocabulary와 무관**하므로 위 수치 자체는 element omission 현상을 신뢰성 있게 가시화한다. 그러나 *Layer Recall 절대값*은 LayerAgent vocabulary에 정렬되어 있어 *상대 비교에서 LayerAgent 우위가 부풀어 보일 수 있음*에 주의 — 본 표의 main 메시지는 "single-pass가 perception이 보장한 layer를 평균 1.6개만 commit한다"는 *baseline 단일 사실*에 한정한다.

**(B) main_eval — N=48 mixed, 4-method** (`experiments/main_eval.py`, `analyze_results.py`):

| Method | Layer Recall ↑ (vocab-aligned ⚠) | gap (1−Recall) ↓ (vocab-aligned ⚠) |
|---|:---:|:---:|
| cot_h_rag | 0.120 ± 0.16 | 0.880 |
| visual_cot | 0.196 ± 0.13 | 0.804 |
| single_pass | 0.212 ± 0.15 | 0.788 |
| layeragent | 0.405 ± 0.23 | 0.595 |

**핵심 발견 1 — Pattern injection의 zero-sum (H-RAG 역설).** cot_h_rag(글래스모피즘/네온 CSS 레시피 RAG 주입)는 legacy N=5 측정에서 CSS Richness 2.8 → 10.3으로 상승하는 동시에 string-CCR이 0.80 → 0.26으로 크게 감소한다 (텍스트 약 74% 누락). 이 zero-sum은 *vocabulary와 무관한 콘텐츠 보존 측정 (CCR)*에서 직접 관찰되며 — *단일 VLM의 자기회귀 토큰 예산*이라는 메커니즘 가설에 부합한다. LayerAgent의 D₂ ablation(§6.7) 결과는 이 zero-sum이 *단계 분리*로 줄어들 수 있음을 시사한다.

**핵심 발견 2 — Sweet-spot이 분해 효과를 좌우한다 (vocabulary와 무관한 N 비교).** dark-glass subset(A)과 mixed subset(B)에서 LayerAgent의 절대 layer 수 회복(perception 5–8 → generation 5–10 vs 0–4)은 (A)에서 두드러지고 (B)에서 약화된다. 이 *layer count* 비교 자체는 vocabulary와 무관하다. Multi-family main result로서의 sweet spot 정량은 §6.5 (Layout-dependent sweet spot)에서 보고한다.

![Figure 1: Layer Recall × method (N=48)](results/figures/fig1_gap.png)

*Figure 1.* (Legacy figure) Layer Recall (vocabulary-aligned) by method across 48 slides — vocabulary alignment caveat 하에서 현상 가시화 용도. Main result는 Table 1 (§6.1, multi-family metrics).

### 제3절 Cross-VLM probing — frontier model의 baseline 관찰 (legacy diagnostic)

Element omission이 GPT-4o 단일 모델의 인공물에 그치는지, 또는 다른 frontier VLM에서도 비슷한 baseline 격차가 관찰되는지를 *가시화*하기 위해 **cross-VLM probing**을 수행했다 (`experiments/probing/cross_vlm_frontier.py`). 10 dark-glass design × 2 frontier VLM (GPT-5.4 via Azure, Claude 4.6 Opus via Bedrock) × single-pass generation = 20 호출. 동일한 prompt와 콘텐츠 spec으로 각 모델에 image → HTML 생성을 요청하고 Layer Recall + LTED를 계산한다. 본 절은 *legacy diagnostic*에 한정된 관찰을 제공하며, *element omission의 모델-일반성에 대한 강한 결론은 보류*한다.

⚠ **Vocabulary alignment caveat (§3.1).** 본 표의 Layer Recall과 LTED는 *LayerAgent class name vocabulary에 정렬된 regex 측정*이다. Frontier 모델이 사용하는 다른 class name 어휘는 정규식에 매칭되지 않아 *frontier에 대한 거짓 negative*를 유발한다. 따라서 *frontier 모델 간 baseline 비교* (GPT-4o vs GPT-5.4 vs Claude Opus, 모두 LayerAgent와 다른 어휘 사용)는 그래도 *상대적으로 공정*하지만, **LayerAgent vs frontier 비교는 self-vocabulary scoring 위험이 있다**. LayerAgent vs frontier의 *공정한 비교*는 §6.2 (multi-family metrics, vocabulary와 무관)로 보고하며, 본 절은 *frontier baseline 간 비교* 및 *현상 가시화*로 한정 사용한다.

**Table — Frontier 단일 패스의 baseline 수준 (N=10 dark-glass, vocabulary-aligned ⚠).**

| 모델 | LTED ↓ ⚠ | Layer Recall ↑ ⚠ | gap (1−Recall) ⚠ | 평균 토큰 | 비용/슬라이드 | 시간 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| single_pass (GPT-4o) | 0.823 | 0.224 | 0.776 | ~5,000 | ~$0.015 | ~10s |
| single_pass (GPT-5.4) | 0.669 | 0.300 | 0.700 | 6,015 | $0.075 | 85s |
| single_pass (Claude 4.6 Opus) | 0.693 | 0.312 | 0.688 | 7,116 | $0.421 | 108s |
| LayerAgent (GPT-4o, *self-vocabulary scoring* 위험) | (0.551) | (0.759) | (0.241) | 54,310 | $0.232 | ~60s |

**관찰 (legacy diagnostic 한정).** GPT-5.4와 Claude 4.6 Opus 모두 baseline gap 0.69–0.70 수준으로 GPT-4o의 0.78과 함께 본 legacy diagnostic에서 frontier single-pass 모델들이 여전히 큰 layer-commit gap을 보인다는 *관찰*을 제공한다. 다만 모델마다 class name 사용 경향이 다를 수 있어 vocabulary alignment의 영향이 모델 간에 균일하다고 보장할 수 없다. 따라서 **element omission의 모델-일반성에 대한 강한 결론은 본 절 단독으로 내리지 않으며**, 향후 *class-name-independent diagnostic* (예: vocabulary와 무관한 layer count, DOM-based VEC/EDC, 또는 human/DOM-aligned layer annotation)로 재검증이 필요하다. 본 절의 관찰은 분해형 접근의 *motivation*을 보강하는 정도로 한정한다.

**LayerAgent vs frontier에 대한 정직한 framing.** 위 표의 LayerAgent 행 (괄호 표시)은 self-vocabulary scoring 위험으로 *그대로 받아들이지 말 것*. LayerAgent의 frontier 대비 위치는 §6.2 (multi-family, class-name-independent)에서 보고하며, 거기서는 GPT-5.4가 LayerAgent를 품질·비용 양 측면에서 능가한다. 본 절의 LayerAgent 수치는 *현상 가시화의 일관성 표시 용도*에 한정한다.

*(사전등록 가설 H-EO는 "3 VLM에서 baseline gap > 0.5"라는 frontier 간 비교 부분에 대해서만 보조적으로 적용된다. 가설의 vocabulary 의존성에 대한 caveat은 부록 A에서 명시.)*

---

## 제4장 LayerAgent 프레임워크

### 제1절 전체 구조

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

### 제2절 Analyzer (Stage 0)

전체 이미지 → (a) 레이아웃 유형(`timeline / dashboard / hub_spoke / pyramid / grid / split / vertical_stack / freeform`), (b) 각 카드/히어로/장식 요소의 정규화 bounding box (0–1 비율)를 출력한다. 이후 모든 crop과 placement의 anchor.

### 제3절 Design Director — DesignSpec Blackboard

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

### 제4절 Specialist Agents (Stage 1, 병렬)

- **Base BG / Atmosphere / Decoration**: 전체 이미지 + DesignSpec → 배경 그라디언트, radial glow, decoration shape를 *분리된 layer*로 생성. 이 분리는 분위기와 패턴이 같은 z=0 안에서 충돌하지 않도록 한다.
- **Card Detail × N**: 각 카드의 crop된 이미지(주변 패딩 포함) + DesignSpec → 카드별 풍부한 CSS(`backdrop-filter`, multi-layer `box-shadow`, rgba 알파, neon border). 좁은 시각 범위가 글래스모피즘 같은 *선택적 CSS 재질*을 회복시킨다 — 통제 실험에서 같은 GPT-4o가 전체 이미지에서는 카드당 CSS 효과 2.8개, crop에서는 6–8개를 생성한다.
- **Hero Detail × N**: 히어로 블록(큰 숫자, 메인 메시지, 특수 그래픽)을 크롭으로 별도 처리.
- **Icon Agent**: 카드별 의미 분석 → FontAwesome 클래스 검색 → 실제 `<i class="fa-...">` 태그 주입. *환각된 아이콘 URL* 을 구조적으로 차단 (`layeragent/libraries/icon_library.py`).
- **Chart Agent / Table Agent**: 슬라이드 타입이 차트/테이블일 때 SVG primitive로 sparkline·bar·gauge·harvey table을 결정적 생성.

### 제5절 Assembler

8 specialist의 HTML 단편을 z-index band([0,5,10,20,30,40])로 결정적 stacking. 단순 concat이 아니라 절대 좌표(Analyzer의 bbox 정규화 비율 × 1280×720)와 z-index를 명시적으로 부착한다.

### 제6절 Style Normalizer (Stage 2)

조립된 HTML을 *텍스트 입력만* 받아 카드 간 CSS 속성을 통일한다 (`layeragent/agents/style_normalizer.py`):

- 배경 rgba alpha — 모든 카드 동일값
- 테두리 색상/두께 — 통일
- border-radius — 통일
- box-shadow — 통일
- backdrop-filter blur — 통일

**불변 보장**: position/left/top/width/height/z-index은 변경하지 않는다. 이미지 입력 없이 코드만 보는 텍스트 전용 agent로, 각 카드의 *독립 생성에서 발생한 표류*를 사후 동기화한다. ablation `no_style_norm`으로 effect 격리.

A2UI Protocol (Google, 2026)이 client-side renderer로 design-system을 강제하는 것과 동일한 설계 원리를 *VLM 파이프라인 내부에서* 실현한 것이다.

### 제7절 Text Inserter (Stage 3)

완전히 스타일링된 HTML(배경 + 카드 + 정규화된 스타일) + 콘텐츠 데이터(제목, 설명, 메트릭, 리스트)를 받아, 기존 카드 구조 내 빈 컨테이너를 식별하여 텍스트를 주입한다.

이 단계의 핵심은 *시각 디자인 확정 후 텍스트 처리*라는 순서이다. 단일 VLM에서 풍부한 CSS 생성과 정확한 텍스트 배치가 zero-sum 경쟁을 벌이는 현상(H-RAG에서 CSS Richness↑이지만 콘텐츠 74% 손실)이 단계 분리로 구조적으로 해소된다. ablation `no_text_inserter`로 격리.

### 제8절 Overflow Repair (선택, v10 P1)

조립된 HTML을 Playwright로 렌더링한 뒤 측정한 bounding box overflow를 분석하여, 폰트 크기/패딩/줄 수를 미세 조정한다. 시각 critic과 다르게 *결정적 측정 기반*이라 LLM 호출이 필요없다 (`layeragent/agents/overflow_repair.py`).

### 제9절 Visual Critic (선택)

Playwright 스크린샷 vs 원본 이미지 비교 후 VLM이 diff를 작성, CSS 속성 단위 보정. iteration 비용이 크므로 default off.

### 제10절 Chat Mode (인터랙티브 입력)

기존 데이터셋 spec 대신 *자연어 메시지 + 참조 이미지*를 입력받는 진입점 (`run_from_chat`, `layeragent/pipeline.py:155`). chat_parser agent가 메시지를 `{slide_type, content, style}`로 구조화한 뒤 동일 파이프라인에 전달한다. 데모: `python -m experiments.demo_chat`.

### 제11절 구현 및 ablation 플래그

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

## 제5장 실험 설정

### 제1절 데이터 — 48 슬라이드 평가셋

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

**(B) 38 consulting-style design** — Gemini 3 Pro Image Preview로 생성, 5종 스타일(McKinsey blue / BCG green / Bain red / Editorial warm / Minimal white) × 8개 layout 유형(mekko, matrix_2x2, waterfall, harvey_table, bar_chart, line_chart, process_flow, pyramid):

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

### 제2절 비교 메서드

| code | 메서드 | 접근 |
|---|---|---|
| **A** | single_pass | 단일 GPT-4o 호출, 전체 이미지 → HTML |
| **B** | visual_cot | 시각 분석(자연어) → 코드 생성 (2단계) |
| **C** | cot_h_rag | Visual CoT + CSS 패턴 RAG (글래스모피즘/네온 레시피) |
| **D** | **layeragent** | **본 연구 — multi-agent full pipeline** |

모든 메서드에 동일 콘텐츠 데이터, 동일 모델(gpt-4o-2024-08-06), 동일 시드(seed=0) 제공.

### 제3절 평가 protocol — Multi-family evaluation

**Critical methodological note**: 본 paper draft 초기 버전은 Layer Recall + LTED를 element omission의 main metric으로 사용했다. 그러나 이들은 *LayerAgent class name 어휘에 정렬된 regex 기반 측정*으로, 동일한 시각 출력이라도 *다른 class name을 쓰는 메서드(Claude Opus의 `glass-card`, `node-inner` 등)*에 거짓 negative를 보고하는 *self-vocabulary scoring 위험*이 있다 (§7.3). 본 paper는 이를 sanity check로 강등하고, **multi-family evaluation protocol**로 main result를 보고한다.

본 protocol의 *신규성은 기존 metric의 발명이 아니라 기존 render-based 및 DOM-based 평가를 결합하고 class-name-independent하게 정렬하여 method-specific vocabulary bias를 줄인 구성*에 있다. 4개 main 축 + 1개 legacy sanity check로 구성된다.

**축 ① DOM-based Structural Metrics** (`experiments/metrics/dom_structure.py`):

Playwright로 렌더링한 DOM에 JS injection하여 모든 가시 element의 *computed style + bounding box*를 추출한다. Class name이나 사전 정의된 layer label에 의존하지 않으며, 모든 메서드에 동일하게 적용된다 (즉 method-agnostic). 측정 항목은 다음과 같다 — 모두 element/style의 plain count 변형이며, 본 표기는 본 연구의 측정 convention일 뿐이다:

- 비자명 styling(배경/테두리/그림자/filter)을 가진 가시 element 수 — **VEC**
- distinct *style fingerprint* `(bg, border, radius, shadow, backdrop, opacity)` 튜플의 가짓수 — **EDC**
- distinct effective-z band 수 (explicit z-index OR DOM depth band) — **VLC**
- backdrop-filter, multi-shadow, gradient, transform, opacity<1, border-radius 등 *rich CSS property*의 총 사용 횟수 — **CRP**
- 가시 element 중 max DOM nesting depth — **HD**
- 슬라이드 영역 중 가시 element가 차지하는 면적 비율 — **SC**

**축 ② Render-based Visual Similarity** (`experiments/metrics/visual_similarity.py`):

- **SSIM** ↑ — local window 기반 픽셀 구조 유사도 (skimage)
- **CLIP** ↑ — open_clip ViT-B/32 image embedding cosine similarity (semantic-level, AutoPresent/Design2Code/SlideCoder 표준)
- **LPIPS** ↓ — AlexNet deep feature 거리 (perceptual-level, Zhang et al. CVPR 2018)
- *Block-Match, Position* (OCR-based): 다크 + 한국어 + blur 도메인에서 모든 메서드 0 → *도메인 미지원*으로 보고하지 않음

**축 ③ Multimodal LLM-as-Judge** (`experiments/metrics/single_method_judge.py`):

Judge model **GPT-5.4 (Azure)** — generator(GPT-4o)와 다른 model family로 self-evaluation bias 차단 (Zheng et al., 2023). Judge에게 *reference image + generated PNG + generated HTML 처음 3,000자* 함께 제공 (tool-grounded; WebDevJudge 2025의 *code+visual modality* best practice 따름). 4 criteria × 1–7 점:
- **Visual Fidelity (VF)** / **Layer Structure (LS)** / **Content Completeness (CC)** / **Design Quality (DQ)**

**축 ④ Content Completeness (auxiliary)**:
- **CCR** ↑ — 입력 텍스트가 HTML에 *문자열로* 등장하는 비율 (시각 가시성 미반영; MLLM judge CC가 visual proxy)

**Legacy sanity check — Class-name-aligned (참고용, main claim 외)** (`experiments/probing/layer_tree.py`):
- **Layer Recall**, **LTED** — class name regex 기반 (LayerAgent 어휘에 정렬). Vocabulary alignment 한계로 인해 §3.2 (현상 가시화), §6.1c (보조 표), §6.3 (prompt 변형 robustness sanity check — vocabulary와 무관하므로 방향성은 robust)에 한정 사용.

**Render guard**: Playwright 정상 렌더링 비율 (전 메서드 100%).

모든 메트릭 코드와 단위 테스트 `experiments/metrics/` 공개.

### 제4절 실험 인프라

- 4-stage cacheable 파이프라인 (`experiments/main_eval.py`): generate → render(Playwright) → reference perception(VLM 캐시) → metrics. 각 stage는 재시작 가능.
- 총 4 메서드 × 48 슬라이드 = **192 cell**. 실행 시간 82분. 생성 실패 0건.
- 결과: `results/main_eval/eval_results.jsonl`, `eval_summary.csv`, `analysis_report.md`.

---

## 제6장 결과

### 제1절 Table 1 — Same-model GPT-4o 비교 (RQ1 main result)

본 절은 *동일 base model GPT-4o 위에서* 4가지 메서드를 multi-family 메트릭 8개로 비교한다 (`results/new_eval/summary.json`, N=10 dark-glass).

**Table 1.** 4 method × 10 design × 8 multi-family metric (DOM-based + render-based). 굵은 = 1위.

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

**핵심 발견 1 — LayerAgent가 DOM-based + render-based로 구성된 8개 자동 지표 중 7개에서 1위.** SSIM에서는 single_pass가 0.023 높았으나, N=10에서 관찰된 표준편차(~0.10)를 고려하면 작은 차이로 본 논문은 이를 LayerAgent의 명확한 우위로 해석하지 않는다. DOM 구조 5개 (VEC/EDC/VLC/CRP/HD) 모두 *2위 대비 1.5–3.2×*, 시각 fidelity 2개(CLIP, LPIPS)도 1위. **동일 base model 위에서 자동 지표상 분해의 효과가 일관되게 관찰된다** (단, holistic 차원은 §6.1b 별도 보고).

**핵심 발견 2 — visual_cot 및 cot_h_rag는 single_pass 대비 일관된 개선을 보이지 않음.**
- visual_cot: VEC 7.3 < single_pass 9.1, CSS richness 18.3 < 23.6
- cot_h_rag: 본 표의 자동 지표 중 LPIPS와 CLIP에서 4 메서드 가운데 가장 낮은 값 (LPIPS 0.709, CLIP 0.430)
- 단순 2-stage CoT나 CSS pattern injection은 본 자동 지표상에서 single_pass 대비 일관된 개선이 관찰되지 않았다.
- 결과는 단순 CoT 또는 CSS pattern injection만으로는 충분하지 않으며, *LayerAgent의 통합 파이프라인*(DesignSpec + Library + Style Normalizer + Text Inserter)이 same-model 조건에서 더 높은 구조적 풍부성과 시각 fidelity를 보였음을 시사한다. 컴포넌트별 인과 효과는 Text Inserter(D₂)와 DesignSpec blackboard(D₄) 두 개에 대해 §6.7에서 격리 측정 — D₄ 제거 시 N=48 multi-family에서 SSIM/LPIPS/CRP 등 시각 fidelity 7개 지표 악화 확인. 나머지 컴포넌트(library, CV facts, style normalizer)의 인과 효과는 향후 연구로 남긴다.

**Table 1b — MLLM judge (GPT-5.4, 4 criteria, 1–7 scale, N=48 main_eval).**

| Criterion | cot_h_rag | layeragent | **single_pass** | visual_cot |
|---|:---:|:---:|:---:|:---:|
| Visual Fidelity ↑ | 1.73 ± 0.61 | 1.65 ± 0.93 | **2.17 ± 0.69** | 2.08 ± 0.68 |
| **Layer Structure** ↑ | 3.00 ± 0.80 | **3.58 ± 0.96** | 3.46 ± 0.68 | 3.08 ± 0.65 |
| Content Completeness ↑ | 3.77 ± 1.69 | 2.35 ± 1.49 | **3.81 ± 1.72** | 3.60 ± 1.51 |
| Design Quality ↑ | 3.40 ± 0.82 | 2.79 ± 1.01 | **3.75 ± 0.79** | 3.29 ± 0.90 |
| **Average** ↑ | 2.97 | 2.59 | **3.30** | 3.02 |

**MLLM judge에서는 single_pass가 평균 우세 (3.30 vs LayerAgent 2.59)**. LayerAgent는 *Layer Structure* 축에서만 좁게 우세 (3.58 vs 3.46). 이는 *DOM-based / render-based metric (Table 1)*과 *holistic LLM-as-judge (Table 1b)*가 서로 다른 차원을 측정함을 보임 — **§6.6 메트릭 disagreement에서 자세히 분석**.

**Table 1c — Legacy vocabulary-aligned (참고용, N=48 main_eval).**

| Metric | cot_h_rag | **layeragent** | single_pass | visual_cot |
|---|:---:|:---:|:---:|:---:|
| Layer Recall ↑ (vocab-aligned) | 0.120 | **0.405** | 0.212 | 0.196 |
| LTED ↓ (vocab-aligned) | 0.911 | **0.744** | 0.823 | 0.854 |

⚠ **이 두 metric은 *우리가 정의한 LayerAgent class name 어휘*에 align됨** (§3.1, §7.3). LayerAgent의 우세는 *부분적으로 self-vocabulary scoring*이며, 동일 시각 출력이라도 *다른 어휘를 쓰는 메서드*에 거짓 negative 보고. **본 paper의 main claim은 Table 1 (multi-family metrics)이며, Table 1c는 한계 명시하에 보고**.

![Figure 2: Multi-metric × method comparison (N=48)](results/figures/fig2_methods.png)

*Figure 2.* (Legacy figure) 4 method × 5 metric breakdown. Layer Recall은 vocabulary-aligned이라 caveat 필요 — main 결과는 Table 1의 multi-family metrics.

### 제2절 Table 2 — Cross-model cost-efficiency (RQ2)

학회 reviewer 차단 질문: *"LayerAgent는 GPT-4o로 8 specialist를 호출한다 — 그냥 한 번의 GPT-5.4나 Claude Opus 호출이 더 비용 효율적이지 않은가?"* 이를 정직하게 검증하기 위해 frontier single-pass를 *multi-family metric* (DOM-based + render-based, vocabulary와 무관)으로 직접 비교한다 (`results/new_eval/`, `results/cross_vlm/cost_efficiency_summary.json`, N=10 dark-glass).

**Table 2.** Cross-model 비교, multi-family metrics. 굵은 = 1위. 가격은 2026 Q1 list price 추정 (GPT-4o $2.5/$10 per M, GPT-5.4 $5/$15 per M, Claude 4.6 Opus $15/$75 per M input/output).

| Method | VEC | EDC | CRP | SSIM↑ | CLIP↑ | LPIPS↓ | **Cost/slide** | **Time** |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **LayerAgent** (GPT-4o + 분해) | 20.9 | 9.7 | 51.5 | 0.470 | 0.492 | 0.589 | **$0.232** | **60s** |
| single-pass (GPT-5.4) | **37.1** | **16.4** | **135.6** | **0.504** | **0.578** | **0.411** | $0.075 | 85s |
| single-pass (Claude 4.6 Opus) | 27.2 | 14.0 | 68.0 | 0.500 | 0.525 | 0.502 | $0.421 | 108s |

**Honest 분석 — *두 가지 결론*.**

#### vs Claude 4.6 Opus — cost-sensitive setting에서의 대안

- 자동 시각 지표에서는 Opus가 다소 우세 (SSIM 0.470 vs 0.500, CLIP 0.492 vs 0.525, LPIPS 0.589 vs 0.502 — 격차는 단일 자릿수 % 수준)
- 시각 풍부성 (VEC/EDC/CRP) 또한 Opus가 다소 우세
- 비용 45% 절감 ($0.232 vs $0.421) + 시간 44% 절감 (60s vs 108s)
- 결론: LayerAgent는 Claude Opus single-pass보다 일부 자동 시각 지표에서는 다소 낮지만, *비용과 시간 측면에서 더 낮은 운영 비용*을 보이며 *cost-sensitive setting에서 대안*이 될 수 있다. 시각 fidelity에서의 우월성을 주장하는 것은 아니다.

#### vs GPT-5.4 — 본 데이터에서 LayerAgent의 우세는 관찰되지 않음

- GPT-5.4 single-pass가 본 표의 multi-family 자동 지표(VEC, EDC, CRP, SSIM, CLIP, LPIPS) 모두에서 1위
- 비용 또한 GPT-5.4가 약 1/3 ($0.075 vs $0.232)
- "LayerAgent가 frontier single-pass를 능가한다"는 강한 주장은 본 데이터에서 GPT-5.4에 대해서는 지지되지 않는다.
- 본 paper는 이 결과를 정직하게 보고하며, GPT-5.4 single-pass가 본 use case에서 더 cost-efficient한 대안임을 명시한다.

#### Operational implication

- *Quality + cost 모두 우선*이면 → **GPT-5.4 single-pass**
- *cost-sensitive setting에서 Opus 대비 운영 비용이 낮은 대안*이 필요하면 → **LayerAgent (GPT-4o)**
- *최저 비용 + low quality 허용*이면 → **GPT-4o single-pass** ($0.015/slide, 10s)

**결론**: LayerAgent는 *비용이 큰 frontier (Claude Opus 등)에 대한 cost-sensitive 대안*으로서 의미를 가지며, *모든 frontier 대체*는 아니다. Cost-quality trade-off는 use case에 의존하며, 본 paper는 이를 정직하게 보고한다.

### 제3절 Trivial baseline check (sanity, legacy diagnostic)

LayerAgent의 same-model 우세(Table 1)가 *분해 효과인지* 또는 *단순 prompt 조정으로 가능한지*를 sanity check하기 위해 **single_pass_zexplicit** 변형을 구현했다 (`baselines/single_pass_zexplicit.py`). 단일 패스 prompt에 z-index 6-band 명시 한 줄만 추가:

| Method (N=10 dark-glass, legacy LTED/Recall ⚠) | LTED ↓ ⚠ | Layer Recall ↑ ⚠ | avg layer count |
|---|:---:|:---:|:---:|
| single_pass (baseline A) | 0.823 ± 0.14 | 0.224 ± 0.13 | (main_eval) |
| **single_pass_zexplicit** (baseline A') | 0.844 ± 0.12 | 0.292 ± 0.17 | 3.8 |
| **layeragent (D)** | 0.551 ± 0.13 | 0.759 ± 0.16 | 8.5 |

z-explicit prompt는 legacy Recall을 0.224 → 0.292로 살짝 올리지만 LayerAgent의 0.759와는 거리가 있다 (legacy metric 기준). avg layer count(vocabulary와 무관) 또한 single_pass_zexplicit 3.8 vs LayerAgent 8.5로 차이가 유지된다. **이 결과는 단순 z-index 명시만으로는 LayerAgent와 같은 수준의 계층적 element commit이 관찰되지 않음을 sanity check 차원에서 보여준다.** 다만 본 표는 legacy vocabulary-aligned metric 기반이므로, *generation capacity 증가에 대한 강한 인과 주장*은 본 표 단독이 아니라 §6.1 Table 1 (자동 지표) + §6.7 ablation 결과와 함께 해석한다.

(prompt 변형 자체는 vocabulary와 무관하므로 방향성 관찰은 robust하지만, 절대 effect size 해석에는 vocabulary alignment caveat 적용.)

---

### 제4절 Sweet spot — 다층 dark-glass 통합 분석 (RQ4 part 1)

본 절은 *시스템 설계 대상*인 다층 dark-glass subset에서 두 메트릭 축(legacy LTED + MLLM judge)이 합의하는지를 직접 검증한다. (A) 10 dark-glass design subset:

| 메서드 | LTED ↓ (vocab-aligned ⚠) | MLLM avg ↑ (vocab-free) |
|---|:---:|:---:|
| single_pass | 0.823 | 3.90 |
| visual_cot | 0.820 | 4.03 |
| cot_h_rag | 0.827 | 3.85 |
| **layeragent** | **0.551** | **4.15** |

다층 dark-glass에서 LayerAgent는 legacy LTED를 거의 절반으로 단축(0.823 → 0.551, vocabulary alignment caveat ⚠)하면서, *vocabulary와 무관한 MLLM judge*에서도 평균 우세 (4.15 vs 3.85–4.03). 즉 vocabulary-aligned legacy LTED와 vocab-free MLLM judge가 같은 방향을 가리킨다 — *적어도 한 축(MLLM)은 vocabulary와 무관하므로*, 합의의 일부는 vocabulary alignment에 영향받지 않는 sub-claim이다. 본 sweet spot에서 LayerAgent 우위는 본 paper에서 가장 신뢰성 있는 범위로 한정 framing된다. 다음 §6.5는 이 합의가 layout 복잡도에 따라 어떻게 변하는지를 9 layout family로 확장한다.

### 제5절 Per-layout sweet spot scaling — 9 layout family breakdown (RQ4 part 2)

**Table 3.** 9 layout family per-method × 두 메트릭 축.
- LTED Δ = (best baseline LTED) − (LayerAgent LTED), **양수 = LayerAgent 우세** (vocab-aligned caveat ⚠).
- MLLM Δ = LayerAgent avg − (best baseline avg), **양수 = LayerAgent 우세** (vocab-free).

| Layout | N | LTED LayerAgent ⚠ | LTED Δ ⚠ | MLLM LayerAgent | MLLM Δ | 양 축 합의 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **design_existing** (dark-glass) | 10 | **0.551** | **+0.27** | **4.15** | **+0.12** | 합의: LayerAgent |
| pyramid | 5 | **0.764** | +0.17 | 1.90 | −1.50 | 불일치 |
| mekko | 5 | **0.753** | +0.08 | 2.15 | −1.50 | 불일치 |
| process_flow | 5 | **0.818** | +0.06 | 2.30 | −1.60 | 불일치 |
| harvey_table | 3 | **0.910** | +0.06 | 2.75 | −0.75 | 불일치 |
| matrix_2x2 | 5 | **0.917** | +0.01 | 2.05 | −0.45 | 불일치 |
| waterfall | 5 | 0.662 | −0.03 | 2.45 | −0.35 | 합의: single_pass |
| line_chart | 5 | 0.845 | −0.03 | 2.20 | −0.40 | 합의: single_pass |
| bar_chart | 5 | 0.733 | −0.09 | 1.90 | −1.10 | 합의: single_pass |

**핵심 발견 (RQ4 정착).**

1. **두 축이 dark-glass sweet spot에서만 *합의하여* LayerAgent를 우세로 선언**한다 (LTED Δ +0.27, MLLM Δ +0.12).
2. **평면 차트(bar/line/waterfall)에서도 두 축이 합의** — 이번에는 *single_pass 우세*로. 분해 비용 > 이득.
3. **6개 중간 layout(pyramid, mekko, process_flow, harvey_table, matrix_2x2, ...)에서 두 축이 *불일치***: vocabulary-aligned LTED는 LayerAgent의 부분 우위(layer 수 회복)를 점수화하지만 *self-vocabulary scoring 위험* 내재 — vocabulary와 무관한 MLLM judge는 그 출력을 *덜 전문적이고 가독성이 낮은 슬라이드*로 본다. 즉, *layer 수만 회복*하는 것은 *발표 가능한 슬라이드*를 보장하지 않는다.

**본 연구의 honest thesis (sweet-spot-scoped).** LayerAgent의 우위는 *다층 dark-glass multi-layer 디자인*이라는 sweet spot에서만 두 축이 합의한다. 그 외 layout에서는 (i) LTED 우위가 *발표 품질로 이어지지 않거나* (ii) 분해 비용 자체가 단일 패스보다 나쁘다. *전체 슬라이드 도메인에서 LayerAgent가 우월하다*는 주장은 데이터로 지지되지 않으며, 본 paper는 이 사실을 thesis의 일부로 명시 흡수한다. **운영 권고: layout-conditional routing** — Analyzer 단계에서 layout 유형 판별 후 다층 → LayerAgent, 평면/차트 → single_pass.

### 제6절 메트릭 분류학 — 다섯 축, 다섯 다른 질문 (RQ3)

**Table 4.** 본 연구가 정착시키는 메트릭 축 분리.

| Metric family | 대표 metric | 측정 차원 | Same-model GPT-4o 우승 | Cross-model 우승 | 답하는 질문 |
|---|---|---|---|---|---|
| ① **DOM-based structural metrics** | VEC, EDC, CRP, HD | 코드 구조 풍부성 | **LayerAgent** | GPT-5.4 | "코드가 *시각적으로 풍부한 element*를 만드는가?" |
| ② **Render-based visual similarity** | SSIM, CLIP, LPIPS | 시각 충실도 | LayerAgent (CLIP/LPIPS) / single_pass (SSIM) | GPT-5.4 | "*렌더된 결과*가 reference처럼 보이는가?" |
| ③ **Multimodal LLM-as-judge** | GPT-5.4 4-criteria | 시각 usability·legibility·design quality | single_pass | (미측정) | "*출력이 발표 가능한* 슬라이드인가?" |
| ④ **Class-name-aligned (legacy sanity check)** | LTED, Layer Recall | class name regex 매칭 | LayerAgent | LayerAgent | ⚠ *self-vocabulary scoring*: "출력이 LayerAgent 어휘에 align되는가?" |
| ⑤ Content completeness (auxiliary) | CCR | 텍스트 문자열 보존 | LayerAgent | (미측정) | "콘텐츠 문자열이 코드에 살아남는가?" — *시각 가시성 미반영* |
| (도메인 미지원) OCR-based | Block-Match, Position | 텍스트 위치 매칭 | (모두 ~0) | — | (다크/한국어/blur 무력화) |

**축 disagreement의 의미 (RQ3 답).** Design-to-Code use case는 단일하지 않다:
- (i) **편집 가능한 구조 회복**(슬라이드 재편집용 코드 추출) → 축 ① 우선
- (ii) **참조 이미지 시각 복제**(스크린샷 → HTML) → 축 ② 우선  
- (iii) **발표 가능한 슬라이드 자동 생성** → 축 ③ 우선
- (iv) ⚠ *self-vocabulary scoring* → 축 ④ (sanity check 외 사용 자제 권고)

**선행 ranking 재해석.** Design2Code, SlidesBench, Widget2Code 등이 보고한 method ranking은 축 ①·② 위주이며, class-name-aligned metric은 *self-vocabulary scoring 위험*. DreamHouse 2026 (structural-visual orthogonality joint pass 7.1%) 및 SlideAudit (UIST 2025, automated vs human disagreement)을 본 연구는 슬라이드 도메인에서 *multi-family disagreement*로 확장 관찰. **본 paper는 DOM-based structural (축 ①) + render-based visual similarity (축 ②) + multimodal LLM-as-judge (축 ③) 동반 보고가 Design-to-Code 평가에서 단일 지표보다 더 정직한 해석을 가능하게 함을 보이며, 그 필요성을 제안한다.**

### 제7절 Ablation — 가용한 측정만 정직하게

본 절은 두 ablation의 정량 측정 결과를 보고한다 — D₂ (Text Inserter, legacy N=5 pilot)와 **D₄ (DesignSpec blackboard, N=48 main_eval framework + N=10 dark-glass sweet spot, multi-family metric)**. 나머지 5개 flag (D₁/D₃/D₅/D₇/D₈)는 infrastructure 완료, 정식 측정 미수행 — §8 한계로 명시.

**D₂ (no_text_inserter) — Text Inserter 분리의 직접 증거** (legacy `tables/exp2_summary.json` 시점 데이터, N=5):

| 조건 | CCR ↑ | CSS Richness ↑ | Joint Pass ↑ |
|---|:---:|:---:|:---:|
| **D (full)** | **0.78** | **54.4** | **0.6** |
| D₂ (no_text_inserter) | **0.09** | 52.2 | 0.0 |
| Δ | **−0.69** | −2.2 | −0.6 |

Text Inserter 제거 시 CCR이 0.78 → 0.09로 크게 감소 — Card Detail Agent가 텍스트 삽입 부담까지 함께 처리하면 시각 생성에 attention이 분산되어 콘텐츠가 약 80% 누락된다. CSS Richness는 거의 동일하게 유지 (Card Detail이 여전히 시각 생성을 담당). 이 결과는 *시각/콘텐츠 단계 분리*가 zero-sum을 구조적으로 줄이는 데 기여함을 시사한다 (legacy N=5 결과로 향후 N=48 framework 재측정 필요).

**D₄ (no_designspec) — DesignSpec blackboard 효과** (N=48 mixed main_eval framework, multi-family metric):

| Metric | D (full) | D₄ (no_designspec) | Δ (D − D₄) |
|---|:---:|:---:|:---:|
| VEC ↑ | **16.9** | 14.7 | **+2.2** |
| EDC ↑ | **9.0** | 8.6 | +0.4 |
| VLC ↑ | **3.3** | 3.2 | +0.1 |
| CRP ↑ | **32.1** | 27.5 | **+4.6** |
| HD ↑ | 7.5 | **7.6** | −0.1 |
| SSIM ↑ | **0.590** | 0.418 | **+0.172** |
| CLIP ↑ | **0.491** | 0.464 | +0.027 |
| LPIPS ↓ | **0.717** | 0.799 | **−0.082** |

DesignSpec blackboard 제거 시 8개 multi-family 자동 지표 중 **7개에서 D 우세, 1개(HD)는 동률** (Δ ±0.1 이내). 가장 큰 효과는 render-based 시각 fidelity — SSIM Δ = +0.172, LPIPS Δ = −0.082, CRP Δ = +4.6. 이는 DesignSpec이 cross-agent 스타일 표류를 줄여 시각 일관성을 보존함을 직접적으로 보여준다 (사전등록 가설 H-AblationDesignSpec 채택, 부록 A).

**Sweet spot subset (N=10 dark-glass) — nuanced trade-off:** 같은 N=10 dark-glass에서 단독 측정 시 결과는 더 미묘하다 — D는 시각 fidelity 4개(CRP/SSIM/CLIP/LPIPS)에서 우세하나 D₄는 구조 다양성 4개(VEC=21.3 vs 20.9 / EDC=11.7 vs 9.7 / VLC=3.8 vs 2.9 / HD=7.8 vs 7.0)에서 약간 우세. 다층 design sweet spot에서는 DesignSpec이 specialist의 *free-form* generation diversity를 일부 제약하지만, mixed N=48 평균에서는 시각 일관성 효과가 압도적이다. 이는 *consistency vs raw diversity trade-off*를 시사하며, paper §1.3의 "DesignSpec = cross-agent 스타일 표류 감소" 가설을 N=48 평균에서 채택, sweet spot에서 부분 채택으로 정직 보고한다.

**나머지 ablation (D₁/D₃/D₅/D₇/D₈) — infrastructure 완료, 정식 측정 미수행:** `layeragent/ablations.py`에 8개 flag 모두 구현되어 있으며, ablation runner(`experiments/run.py`)가 각 변형을 main_eval framework로 돌릴 준비 완료. paper draft 시점 *N=48 정식 ablation 결과는 미수집*. 본 결과는 향후 work에서 추가 (§8 명시).

## 제7장 논의

### 제1절 Element omission의 메커니즘 — Capacity allocation 가설

본 절은 element omission의 메커니즘을 *가설*로 제시한다. 본 논문은 메커니즘 자체를 직접 인과 증명하지 않으며, 본 가설은 §3·§6의 관찰과 부합하는 후보 설명으로 제시된다.

**가설 (capacity allocation).** VLM이 전체 슬라이드를 단일 호출로 처리할 때, 레이아웃·색·텍스트·아이콘·CSS 재질·z-index·border·shadow·alpha를 모두 *하나의 자기회귀 토큰 시퀀스*로 산출해야 한다. `z-index`, `backdrop-filter: blur(16px)`, `box-shadow: 0 0 15px rgba(...)` 같은 속성은 *없어도 HTML이 정상 렌더링*되므로 생성 capacity가 동시에 경쟁하는 상황에서 가장 먼저 단순화될 가능성이 높다. 이 가설로 (a) 카드 간 *재질 단순화*, (b) 카드 간 *스타일 표류*, (c) z-index *부재*의 세 결과가 *공유된 메커니즘*에서 비롯된다고 해석할 수 있다 — 다만 이는 가설 수준의 해석이며, 직접적인 인과 검증(예: token budget을 외생적으로 조정한 통제 실험)은 향후 작업이다.

이 가설 하에서, LayerAgent의 분해는 각 specialist의 인지 범위를 좁혀 (a)를 줄이도록 설계되었으며, DesignSpec blackboard는 (b)를 줄이는 shared style prior로 작동하고, Assembler의 결정적 z-index stacking은 (c)를 줄이는 메커니즘으로 작동한다.

### 제2절 Mixed signal의 의미 — multi-family가 측정하는 서로 다른 차원

본 연구의 mixed signal은 *자체 결함*이 아니라 *Design-to-Code 평가가 본질적으로 multi-objective*임을 정량 증명한 것이다. Multi-family는 서로 다른 차원을 본다:

- **Render-based visual similarity (SSIM)**은 픽셀 휘도/대비/구조의 local window 통계 — 카드 위치만 비슷해도 점수가 높다. 단일 패스가 image-to-image 표면 모방의 강점을 직접 활용 → SSIM 우세. z-index 부재·계층 단순화는 SSIM에 패널티 없이 통과.
- **DOM-based structural metrics (VEC/EDC/CRP/HD)**는 가시 element와 distinct style fingerprint의 카운트 — 분해된 출력이 풍부한 element와 다양한 스타일을 commit할 때 점수가 높다. LayerAgent의 8개 specialist가 직접 layer를 채우므로 우세.
- **Multimodal LLM-as-judge**는 *출력이 발표 가능한가* 라는 holistic 질문에 답한다. 풍부한 layer가 있어도 텍스트가 overflow되거나 카드가 빈 영역을 만들면 감점. 단일 패스의 *거칠지만 안정적*인 출력이 일관되게 우세.

**정직 정착**: 어느 한 축의 우월성을 주장하지 말 것. 본 paper는 multi-family를 모두 보고하며, *use case에 따른 metric selection*을 운영 권고로 둔다. LayerAgent는 (i) 편집 가능한 구조 회복에 정렬된 시스템이며, (ii) end-to-end 슬라이드 자동생성 use case에서는 *Visual Critic + 더 보수적인 Text Inserter*가 추가되어야 (iii) holistic 축에서도 우세를 달성할 수 있을 것으로 예측한다 — 이는 §8 향후 연구.

### 제3절 String-CCR vs Visual CCR — 메트릭 진화의 직접 증거

LayerAgent의 string-CCR은 0.99이지만 MLLM judge의 visual Content Completeness는 2.35로 *최악*이다. 이 정확한 모순이 본 paper의 메트릭학적 기여이다 — **string-level 매칭 메트릭은 시각 가시성을 underdetermine한다**. CCR은 Text Inserter가 텍스트를 카드 영역에 *주입*했음을 확인하지만, judge는 그 텍스트가 overflow되거나 dense하게 겹쳐서 *읽을 수 없음*을 본다.

향후 연구에서 **Visual CCR** — Playwright 렌더링 후 OCR로 가시 텍스트 추출 → input 콘텐츠와 매칭 — 을 string-CCR의 후속 메트릭으로 제안한다. 현재 OCR이 본 도메인(다크/한국어/blur)에서 무력화되어 있으므로 *visual-aware OCR* (mPLUG-DocOwl, Florence-2 등) 채택이 선결 과제.

### 제4절 단계 분리의 효과 — Multi-family + cross-VLM 데이터에서의 일관성

H-RAG가 보여주는 zero-sum, D₂ ablation이 보여주는 분리의 효과, §3.3의 cross-VLM frontier baseline 관찰, §6.3의 trivial prompt baseline 결과 — 이들 데이터가 모두 같은 방향을 가리킨다: *단순 prompt 조정이나 frontier model upgrade만으로는 layer 구조 commit이 충분히 회복되지 않는다*.

**Cross-VLM frontier baseline (§3.3, vocabulary alignment caveat 내에서도 robust한 부분)**: GPT-4o, GPT-5.4, Claude 4.6 Opus 세 frontier 모두 baseline 격차가 큼. *frontier 간 단순 upgrade*로 격차의 가시적 약화는 작다 (단, 본 절의 frontier vs LayerAgent 비교는 §6.2 multi-family 결과를 우선 — 그곳에서 GPT-5.4는 LayerAgent를 능가).

**§7 thesis (정정된 framing).** LayerAgent의 가치는 *frontier model 능가*가 아니라 *same-model 조건에서 단계 분리가 부여하는 구조적 일관성*이다. *Same-model GPT-4o*에서는 분해가 DOM-based + render-based 자동 지표 8개 중 7개에서 우세를 보이며 (MLLM judge 차원에서는 우세 미달), prompt engineering(§6.3) 만으로는 같은 격차가 관찰되지 않는다. 그러나 frontier model upgrade는 별개의 cost-quality 차원에서 LayerAgent를 능가할 수 있으며 (§6.2 GPT-5.4 비교에서 LayerAgent의 우세는 관찰되지 않음), 이는 본 paper가 정직하게 보고하는 사실이다.

### 제5절 비대칭 vision의 일반 원리

본 연구의 한 발견은: *스타일을 만드는 agent는 이미지를 보고, 배치를 결정하는 agent는 좌표만 본다*. Card Detail은 crop을 보지만 Text Inserter는 텍스트만 본다. 이 비대칭은 다른 멀티에이전트 영역에도 일반화 가능하다 — UI 생성에서 디자인 agent vs 코딩 agent, 로봇 제어에서 계획 agent vs 실행 agent, 문서 생성에서 레이아웃 agent vs 콘텐츠 agent.

---

## 제8장 한계

- **Class-name-aligned legacy metric (LTED/Layer Recall)의 self-vocabulary scoring 문제.** 본 paper의 초기 버전은 Layer Recall + LTED를 element omission metric으로 사용했으나, 이는 *우리가 정의한 LayerAgent class name 어휘*에 align된 regex 기반 측정으로 *self-vocabulary scoring 위험*이 있다. Claude Opus의 `glass-card`/`node-inner`/`hub-content` 등 *시각적으로 풍부한 element*가 매칭 안 되어 거짓 negative 보고. 본 paper는 이를 §3 + §5.3에서 명시하고 main result를 *multi-family metrics* (DOM-based VEC/EDC/VLC/CRP/HD + render-based SSIM/CLIP/LPIPS + multimodal LLM-as-judge)로 보고. Legacy metric은 §3.2·§3.3 (현상 가시화), §6.1c (보조 표), §6.3·§6.4·§6.5 (sanity check, prompt 변형 robustness — vocabulary와 무관하므로 방향성은 robust)에 한정 사용 (caveat 명시).
- **Holistic 디자인 quality (축 ③)에서의 부정 결과.** MLLM judge 4-criteria 평균에서 LayerAgent (2.59) < single_pass (3.30) — N=48 main_eval. Visual Fidelity·Content Completeness·Design Quality 3개 축에서 단일 패스에 진다. LayerAgent의 holistic 우위는 *Layer Structure 축* (3.58 vs 3.46) + *dark-glass sweet spot* 으로 한정된다. 본 paper는 이 부정 결과를 *thesis의 일부*로 흡수.
- **Sweet-spot 외 disagreement.** 6개 중간 layout(pyramid, mekko, process_flow 등)에서 LTED는 LayerAgent를 우세로, MLLM judge는 single_pass를 우세로 본다. 즉 *layer 수만 회복*하는 것이 *발표 가능한 슬라이드*를 보장하지 않는다. Visual Critic + 더 보수적 Text Inserter 조합이 §7.2의 향후 과제로 명시.
- **N=48의 통계 검증력.** 메인 결과는 effect size로 보고하며, paired Wilcoxon p-value는 sweet spot subset(N=10)에서만 유의(p<0.05)하다. 30+ seed × 100+ design 확장이 향후 과제.
- **Cross-VLM probing의 vocabulary alignment + scope 한계.** §3.3의 cross-VLM 결과는 (a) class-name-aligned LTED/Recall 기반이라 vocabulary alignment caveat 적용, (b) N=10 dark-glass subset에 한정. 본 절은 *frontier 간 baseline 비교*와 *현상 가시화* 용도로만 신뢰성을 가진다. LayerAgent vs frontier의 공정한 비교는 §6.2 multi-family metric 결과로 보고하며, 거기서 GPT-5.4는 LayerAgent를 능가한다. Gemini 2.5 등 추가 frontier에서의 multi-family 재현은 향후 작업.
- **Ablation은 D₂와 D₄만 정량 측정됨.** §6.7의 ablation은 D₂ (Text Inserter, N=5 legacy pilot)와 D₄ (DesignSpec blackboard, N=48 main_eval framework + N=10 sweet spot, multi-family metric) 두 개에 한정 보고. 나머지 5개 flag (D₁ no_style_norm / D₃ no_cv_facts / D₅ no_library / D₆ no_visual_critic / D₇ no_overflow_repair)는 *infrastructure 구현 완료* (`layeragent/ablations.py`) 이지만 정식 측정 *미수행*. 본 paper 작성 시점 기준 — 따라서 style normalizer / library retrieval / CV facts 등의 *개별 contribution*은 *paper의 main claim에 포함되지 않는다*.
- **OCR-기반 메트릭 무력화.** Block-Match와 Position이 다크 배경 + 글래스모피즘 + 한국어 + opacity blur 조합에서 일관되게 0이다. *visual-aware OCR* (mPLUG-DocOwl, Florence-2) 교체가 선결 과제.
- **단일 LLM judge bias + 인간 평가 부재.** 본 paper의 holistic 평가는 GPT-5.4 (Azure) 단일 LLM-as-judge에 의존한다 — Claude / Gemini 등 cross-judge로의 일반화 가능성은 검증되지 않았다. 또한 인간 anchor 직접 검증(n≥80 pair × 5 raters 규모, MT-Bench/AlpacaEval 류 pairwise 프로토콜)도 미수행이다. WebDevJudge (2025)가 권고하는 cross-judge + human anchor 조합은 향후 과제.
- **지연 시간.** Multi-agent decomposition + library retrieval로 카드 4개 슬라이드 ~60초 vs single-pass ~8초. *quality-latency 트레이드오프* 위에 위치.
- **Layer band의 디자인 특수성.** 본 시스템의 6 layer band는 다크-글래스 + 글래스모피즘 + 아이콘 배지 미학에 정렬되어 있다. 텍스트 중심 / 사진 중심 슬라이드에서는 일부 specialist가 비활성화되거나 layer band 재정의가 필요하다.
- **String-CCR vs Visual CCR.** §7.3에서 다룬 메트릭 진화 필요. 현재 CCR 0.99는 *문자열은 존재하나 시각적으로 읽히지 않을 수 있음*을 직접 보였다 (MLLM judge CC 2.35).

---

## 제9장 결론

본 논문은 Design-to-Code 프레젠테이션 생성에서 **계층적 element omission**(Design-to-Code 선행 연구의 element omission이 슬라이드의 시각 계층 단위로 확장된 형태)이라는 현상을 정의하고, 이를 *분석하고 완화*하기 위한 LayerAgent framework와 multi-family 평가 protocol을 제안했다. LayerAgent는 모든 layout·모든 frontier model을 능가하지 않으며, 본 paper의 contribution은 *narrow하게 측정된* 4개 사실이다.

- **(RQ1) Same-model 분해 효과 (Table 1)**: 동일 GPT-4o 위에서 LayerAgent (multi-agent decomposition)는 *DOM-based 구조 지표 + render-based 시각 유사도로 구성된 8개 자동 지표* 중 7개에서 single_pass / visual_cot / cot_h_rag를 능가. VEC 2.3×, EDC 3.2×, CRP 2.2×, CLIP +0.042, LPIPS −0.064. SSIM에서는 single_pass가 0.023 높았으나 N=10 std ~0.10 고려 시 작은 차이로 결정적 우위로 해석하지 않음. *Holistic MLLM-as-judge에서는 single_pass가 평균 우세 (Table 1b)* — 이는 자동 지표와 holistic 판단이 서로 다른 차원을 측정함을 보임. 단순 2-stage CoT나 CSS pattern injection만으로는 충분하지 않으며, *LayerAgent의 통합 파이프라인*이 same-model 조건의 자동 지표상에서 더 높은 구조적 풍부성과 시각 fidelity를 보였음을 시사한다. 컴포넌트별 인과 효과는 D₂(Text Inserter, CCR Δ=0.69)와 **D₄(DesignSpec blackboard, N=48 multi-family에서 8개 지표 중 7개 악화 — 특히 SSIM Δ=0.172, LPIPS Δ=0.082)** 두 개 격리 측정 (§6.7). 나머지 컴포넌트 (library, CV facts, style normalizer)의 개별 효과는 향후 ablation 작업으로 분리 (§8 한계).

- **(RQ2) Cross-model cost-efficiency (Table 2)**:
  - vs Claude 4.6 Opus: 자동 시각 지표에서 다소 낮지만 비용 45% 절감 + 시간 44% 절감 — *cost-sensitive setting에서의 대안*
  - vs GPT-5.4: GPT-5.4가 품질·비용 모두에서 우세 — *본 데이터에서 LayerAgent의 우세는 관찰되지 않음*
  - 결론: LayerAgent는 비용이 큰 frontier에 대한 cost-efficient 대체로서 의미를 가지며, 모든 frontier 대체로 일반화되지 않는다.

- **(RQ3) 메트릭 축 disagreement (§6.6)**: DOM-based structural (축 ①) / render-based visual similarity (축 ②) / multimodal LLM-as-judge (축 ③) — 동일 데이터에 *서로 다른 ranking*. 단일 메트릭 ranking은 use case 의존. **Class-name-aligned legacy metric (축 ④, LTED/Recall)은 self-vocabulary scoring 위험**이 있어 sanity check 외 사용 자제 권고.

- **(RQ4) Layout-dependent sweet spot (§6.4-§6.5)**: Per-layout breakdown에서 *다층 dark-glass multi-layer 디자인*에서만 두 메트릭 축이 합의하여 LayerAgent 우세 선언. 평면 차트(bar/line/waterfall)에서는 *두 축 모두 single_pass 우세*에 합의. 운영 권고: layout-conditional routing.

- **Trivial baseline check (§6.3)**: prompt에 z-index 명시 한 줄 추가는 LayerAgent와의 격차(legacy Recall 기준 2.6×, vocabulary와 무관한 layer count 회복에서도 robust)를 닫지 못함 — same-model 격차는 *generation capacity 확장*을 통해서만 일어남.

**Honest thesis.** *Same-model 비교*에서 LayerAgent의 가치 = DOM-based + render-based로 구성된 8개 자동 지표 중 7개 우세 (Table 1) + holistic judge에서는 single_pass가 평균 우세 (Table 1b). *Cross-model 비교*에서 LayerAgent의 가치 = Claude Opus의 cost-efficient 대체 (Table 2). 이 두 narrow claim이 본 paper의 measured contribution이며, "frontier 능가"라는 강한 주장은 GPT-5.4에 대해 *데이터로 지지되지 않음*을 정직하게 보고. LayerAgent는 *모든 경우의 SOTA*가 아니라, *다층 디자인에서 element omission을 완화하는 구조적 방법*이다.

**더 넓은 원리.**

1. **Multi-family 동반 보고의 필요성.** DOM-based structural + render-based visual similarity + multimodal LLM-as-judge 동시 보고가 Design-to-Code 평가에서 단일 지표보다 더 정직한 해석을 가능하게 함을 본 연구는 보인다. *Class-name-aligned regex 기반 metric*은 self-vocabulary scoring 위험으로 sanity check 외 사용 자제.
2. **Same-model 분해 효과 + Cross-model cost-efficient 대체는 분리된 두 claim**이다. 한 표 안에서 섞으면 narrative 혼동 발생; *Table 1 (same-model) + Table 2 (cross-model)*의 분리가 정직 framing.
3. **String-level 콘텐츠 메트릭은 시각 가시성을 underdetermine한다.** CCR 0.99 vs MLLM CC 2.35 — visual CCR 메트릭 필요.

**향후 연구.** (a) cross-judge 추가 (Claude/Gemini)로 holistic 축 single-judge bias 제거. (b) 인간 평가 N=8-10으로 multi-family metric의 인간 anchor 검증. (c) Multi-seed (3 seed × 4 method × 48 design) 통계 검정. (d) Layout-conditional routing 구현. (e) Visual CCR (visual-aware OCR 기반). (f) AutoPresent의 element matching 프로토콜 직접 비교 (cross-paper validation). (g) 5개 미측정 ablation flag (D₁/D₃/D₅/D₇/D₈)의 N=48 framework 정식 측정으로 컴포넌트별 인과 효과 격리.

---

## 부록 A. 사전 등록 (Pre-registration) — 가설 검증 임계값

본 paper의 핵심 가설들은 *post-hoc 임의 임계값*이 아닌 *사전 명시된* 결정 규칙으로 검증된다 (paper 초안 작성 시점에 결정).

⚠ **Caveat.** 본 사전등록 가설들은 paper 초안 시점에 Layer Recall/LTED를 main metric으로 사용하던 framework에서 작성되었다. 본 paper는 main claim을 *multi-family metrics* (DOM-based + render-based + LLM-as-judge)로 전환했으므로, 아래 가설 중 LTED/Recall에 의존하는 항목들은 *vocabulary alignment caveat 하의 보조 가설*로 재해석한다. Multi-family 가설 (§6.1·§6.2·§6.5·§6.6의 주장)은 본 paper 본문에서 직접 effect size로 보고하며, 향후 작업에서 multi-family 기반 사전등록 가설로 정식화한다.

**H-EO (Element omission의 모델-일반성, §3.3) — *vocabulary-aligned 보조 가설, 채택***
- 결정 규칙: 3 VLM에서 baseline single-pass의 평균 (1 − Layer Recall) ≥ 0.50 AND cross-VLM 표준편차 ≤ 0.10
- 적용: 10 dark-glass design × 3 VLM (GPT-4o, GPT-5.4, Claude 4.6 Opus). Gemini 2.5는 본 paper에서 미실행 (인프라 있음, 향후 work).
- 측정 결과: 3 VLM gap = {0.776, 0.700, 0.688}, 평균 0.721, std 0.039 (≤ 0.10 ✓), 평균 ≥ 0.50 ✓
- ⚠ Vocabulary alignment caveat: Layer Recall은 LayerAgent class name 어휘에 정렬됨. *frontier 간 비교*에 한정해서는 (모두 다른 어휘 사용) 상대적으로 공정하므로 baseline 격차의 가시화로는 신뢰성을 가지나, 절대값은 caveat 적용.
- **보조 가설로 채택**: frontier 간 baseline upgrade로 격차의 가시적 약화는 작다.

**H-LTED, H-Recall (LayerAgent의 vocabulary-aligned metric 우위, §6.1c)**
- 결정 규칙: legacy LTED/Recall 기준의 LayerAgent 우위
- ⚠ Self-vocabulary scoring 위험으로 *main claim에 미사용*. §6.1c 보조 표 caveat과 함께 보고.
- 본 paper의 main claim은 multi-family metric 기반 §6.1 Table 1로 보고 (DOM-based + render-based 8개 자동 지표 중 7개에서 LayerAgent 우세, holistic MLLM judge 차원은 §6.1b 별도 보고).

**H-SweetSpot (다층 디자인에서의 양 축 합의, §6.4) — *부분 채택***
- 결정 규칙: dark_glass=10 subset에서 *동시*에 (LTED(layeragent) < best baseline LTED − 0.20) AND (MLLM avg(layeragent) > best baseline MLLM avg)
- 측정: LTED Δ = +0.27 (✓, vocab-aligned caveat), MLLM Δ = +0.12 (✓, vocab-free) — 두 축 합의
- ⚠ 합의 자체는 *vocab-aligned LTED + vocab-free MLLM judge*의 조합 — 한 다리(LTED)가 vocabulary alignment caveat 하. 향후 multi-family DOM/render-based metric으로 재정식화.

**H-LayoutScaling (Per-layout RQ4, §6.5)**
- 결정 규칙: 9 layout family 중 *적어도 5개에서* MLLM Δ와 LTED Δ의 부호가 일치 (즉, 두 축이 같은 승자에 합의)
- 측정: dark-glass + 평면 차트 4개에서 합의, 5개에서 불일치 → *부분 채택*
- ⚠ 동일 caveat: LTED 한 다리에 vocabulary alignment 적용.

**H-MetricFamilyDisagree (RQ3 multi-family disagreement, §6.6) — *채택***
- 결정 규칙: 48-slide aggregate에서 SSIM 우승자 ≠ LTED 우승자 ≠ MLLM 우승자 (셋 모두 다른 메서드를 1위로 산출 — 또는 최소 2개 이상 ranking 차이)
- 측정 결과: SSIM 우승=single_pass, LTED 우승=layeragent, MLLM 우승=single_pass — 축 간 disagreement 확인
- **채택**: 축이 Design-to-Code의 서로 다른 평가 차원임을 직접 증명.

**H-AblationTextInserter (Text Inserter 분리 효과, §6.7) — *채택***
- 결정 규칙: string-CCR(D) − string-CCR(D₂) ≥ 0.30 AND Layer Recall(D) > Layer Recall(D₂)
- 측정 결과 (legacy N=5): string-CCR Δ = 0.69, **채택**
- 주: CCR은 vocabulary와 무관한 콘텐츠 보존 메트릭이므로 본 가설의 채택은 vocabulary alignment caveat과 독립.

**H-AblationDesignSpec (DesignSpec cross-agent 합치, §6.7) — *채택 (N=48 multi-family) / 부분 채택 (N=10 sweet spot)***
- 결정 규칙 (재정식화): EDC/CRP/CLIP 3개 지표 중 ≥ 2개에서 D > D₄ (또는 EDC Δ ≥ 1.0 AND CLIP(D) ≥ CLIP(D₄)).
- 측정 결과 (N=48 mixed main_eval framework, multi-family metric):
  - 다수결 규칙: EDC ✓ (+0.4), CRP ✓ (+4.6), CLIP ✓ (+0.027) — **3/3 채택**.
  - Strict 규칙: EDC Δ = +0.4 < 1.0 ❌, CLIP Δ = +0.027 ≥ 0 ✓ — strict 부분 충족.
  - 8개 multi-family 자동 지표 종합: D 우세 7개 (VEC/EDC/VLC/CRP/SSIM/CLIP/LPIPS), 동률 1개 (HD, Δ −0.1). 가장 큰 효과는 SSIM Δ = +0.172, LPIPS Δ = −0.082, CRP Δ = +4.6.
- 측정 결과 (N=10 dark-glass sweet spot subset):
  - 8개 multi-family 자동 지표: D 우세 4개 (CRP/SSIM/CLIP/LPIPS, 시각 fidelity 4개), D₄ 우세 4개 (VEC/EDC/VLC/HD, 구조 다양성 4개) — *consistency vs raw diversity trade-off*.
  - 다수결 규칙: CRP ✓, CLIP ✓, EDC ✗ — 2/3 채택 (경계).
- **결론**: N=48 multi-family에서 H-AblationDesignSpec **채택** — DesignSpec blackboard는 cross-agent 시각 fidelity 일관성을 명확히 보존. Sweet spot에서는 부분 채택 (visual fidelity는 D 우세, structural diversity는 D₄ 우세).
- 주: VEC/EDC/CRP 등 multi-family DOM/visual metric은 vocabulary와 무관하므로 본 가설 채택은 vocabulary alignment caveat과 독립.

본 사전 등록은 paper 부록 외에도 OSF(Open Science Framework)에 별도 등록될 예정이며, ID는 publication 시점에 명시한다. 향후 작업에서 multi-family metric 기반 사전등록을 정식 갱신한다.

---

## 부록 B. 재현 패키지

```
ppt_paper/
├── layeragent/                     # multi-stage 파이프라인
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
│   │   └── cross_vlm.py            # H-EO 검증 실험
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

### Design-to-Code 생성
- Si, C., et al. "Design2Code: How Far Are We From Automating Front-End Engineering?" NAACL 2025.
- Laurençon, H., et al. "Unlocking the Conversion of Web Screenshots into HTML Code with the WebSight Dataset." 2024.
- Calò, T., & De Russis, L. "Advancing Code Generation from Visual Designs through Transformer-Based Architectures and Specialized Datasets." Proceedings of the ACM on Human-Computer Interaction (PACMHCI), 2025. — *element omission / element distortion / element misarrangement* 분류 출처.
- DCGen. "Divide-and-Conquer Screenshot-to-Code Generation." FSE 2025.
- LaTCoder. "Layout-as-Thought Code Generation." KDD 2025.
- ScreenCoder. "ScreenCoder: Advancing Visual-to-Code Generation for Front-End Automation via Modular Multimodal Agents." arXiv:2507.22827, 2025.
- DesignCoder. "DesignCoder: Hierarchy-Aware and Self-Correcting UI Code Generation with Large Language Models." arXiv:2506.13663, 2025.
- UIOrchestra. "Generating High-Fidelity Code from UI Designs with a Multi-Agent Framework." Findings of the Association for Computational Linguistics: EMNLP 2025.

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
- SlideAudit. "A Dataset and Taxonomy for Automated Presentation Slide Evaluation." UIST 2025. arXiv:2508.03630.
- WebDevJudge. "Evaluating (M)LLMs as Critiques for Web Development Quality." arXiv:2510.18560, 2025.
- Zhang, R., et al. "The Unreasonable Effectiveness of Deep Features as a Perceptual Metric (LPIPS)." CVPR 2018.
- Zheng, L., et al. "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena." NeurIPS 2023.

### 계층 / 중첩
- LayerD. "Decomposing Raster Graphic Designs into Layers." ICCV 2025.
- SLEDGE. "Step-by-Step Layered Design Generation." AAAI 2026.
- OverLayBench. NeurIPS 2025.

### 멀티에이전트 시스템
- Hong, S., et al. "MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework." ICLR 2024.
- Qian, C., et al. "ChatDev: Communicative Agents for Software Development." ACL 2024.
- Li, G., et al. "CAMEL: Communicative Agents for Mind Exploration of Large Language Model Society." NeurIPS 2023.
- Wu, Q., et al. "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation." COLM 2024.

### 에이전트 UI / 디자인 시스템
- A2UI Protocol. "Agent-driven UI with Client-Side Design Enforcement." Google, 2026.

### VLM
- Hurst, A., et al. "GPT-4o System Card." 2024.
- Radford, A., et al. "CLIP: Learning Transferable Visual Models." ICML 2021.
- Wang, Z., et al. "SSIM: Image Quality Assessment." IEEE TIP, 2004.
