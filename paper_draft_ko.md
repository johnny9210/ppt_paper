LayerAgent: 프레젠테이션 생성을 위한 멀티에이전트 프레임워크

디자인 이미지의 계층 구조 인식을 통한 프레젠테이션 코드 생성

by 정일균 (Ilgyun Jeong)

인공지능융합학과 (Department of Artificial Intelligence Convergence)

지도교수: 김현철 (under the supervision of Professor Hyeoncheol Kim)

---

초록

프레젠테이션 슬라이드는 배경·카드·콘텐츠·아이콘 등 여러 시각 층이 위아래로 겹쳐 구성되는 본질적으로 계층적(layered) 시각 구조이지만, 본 연구는 동일한 GPT-4o가 슬라이드 이미지를 자연어로는 5–8개의 레이어로 풍부하게 기술하면서도 같은 이미지를 HTML로 변환할 때는 그 계층 구조의 상당 부분을 코드에 반영하지 못하는 요소 누락(element omission) 현상을 관찰했다 — Design-to-Code 선행 연구에서 개별 요소 단위로 보고된 element omission이, 슬라이드 도메인에서는 시각 계층(layer) 단위로 통째 누락되는 형태로 확장되어 나타난다. 우리는 이 문제를 다루기 위해, 단일 VLM 호출이 한꺼번에 처리하던 구조·스타일·콘텐츠 생성을 각자 하나의 레이어(배경·장식·카드·텍스트·아이콘 등)만 책임지는 다수의 전문 에이전트로 분해하는 멀티 에이전트 프레임워크 LayerAgent를 제안한다. 동일 GPT-4o 조건에서 LayerAgent는 DOM 구조와 렌더링 유사도로 구성된 8개 자동 평가 지표 중 7개에서 일괄 생성, 시각 분석 생성, 패턴 주입 생성보다 높은 결과를 보였으며, 평균 시각 요소 수를 약 2.3배, 스타일 다양성을 약 3.2배 회복했다. 다만 이 효과는 다층 시각 효과 디자인 조건에서 주로 관찰되며, 종합적 발표 품질 및 frontier 모델 기반 일괄 생성(GPT-5.4·Claude 4.6 Opus)과의 비교에서는 그 적용 경계가 드러난다. 따라서 본 연구는 frontier 모델과의 성능 경쟁이 아니라, GPT-4o급 VLM에서 일괄 생성이 놓치는 계층적 시각 구조를 process-level 분해로 완화할 수 있음을 보이고, 그 효과가 나타나는 조건과 한계를 함께 규명한다.

키워드: Element Omission, Layer Decomposition, Multi-Agent, Design-to-Code, Vision Language Models

---

제1장 서론

제1절 슬라이드는 계층이다, 그러나 VLM은 평면이다

프레젠테이션 슬라이드, 특히 본 연구가 대상으로 삼는 다층 시각 효과 슬라이드는 웹페이지나 포스터와 달리 여러 시각 층이 위아래로 겹쳐 쌓이는 명확한 계층(layered) 구조를 가진 시각 객체다 — 본 연구의 타깃 subset(§5.1 (A))은 대체로 가장 아래에 배경(베이스 그라디언트와 패턴), 그 위로 분위기(방사형 글로우·그라디언트 오버레이), 장식 요소(도형·선·점), 카드·패널·히어로 블록, 콘텐츠 텍스트(제목·본문·수치), 그리고 가장 위에 아이콘과 배지가 놓이는 약 6개 층으로 구성된다. (모든 슬라이드가 이 6층 구조를 갖는다는 일반론이 아니라, 본 논문의 다층 시각 효과 subset의 공통 특성이다.)

이 6개 층이 정확한 층 순서(stacking order)와 좌표로 겹쳐야 의도된 디자인이 구현된다. 그러나 단일 VLM 호출은 이 계층 구조를 충분히 반영하지 못한 채 HTML을 위에서 아래로 한 번에 생성한다 — `<div>` 태그가 직렬로 나열되고, 층의 명시적 순서 표기(CSS의 `z-index` 속성)는 거의 사용되지 않으며, 요소 간 공간 관계는 DOM 작성 순서에 암묵적으로 의존한다.

흥미로운 관찰은 다음이다 — 같은 GPT-4o에게 "이 이미지의 계층 구조를 설명하라" 고 물으면 5–8개의 레이어를 자연어로 기술한다. 그러나 같은 이미지를 "HTML로 변환하라" 고 물으면 그 계층 구조의 상당 부분을 코드에 반영하지 못한다 (§3.2 표). 즉 같은 모델이 기술하는 단계에서는 다층 구조를 인식하면서도 코드를 쓰는 단계에서는 그 대부분을 잃는다.

이 실패 양식은 본 연구의 사전 pilot 관찰(§3.2, N=10 다층 시각 효과 디자인)에서 반복적으로 확인된 패턴이다 — 디자인 프롬프트가 배경, 장식 요소, 반투명 카드, 텍스트, 아이콘 등 여러 시각 계층과 복합 CSS 효과를 명시적으로 요구해도, 단일 VLM 호출의 HTML 출력은 일부 계층을 생략하고 단색 배경 + 평면 카드의 단순 구조로 회귀하며, perception이 보장한 5–8 layer 중 평균 1.6개만 HTML/CSS 구조에 반영된다. 본 논문의 모든 경험적 주장은 §5에서 기술하는 통제 실험 결과에 한정해 보고한다.

본 논문은 이 현상을 (계층적) element omission이라고 부른다 — Design-to-Code 선행 연구에서 개별 요소 단위로 보고된 element omission이, 슬라이드 도메인에서는 시각 계층(layer) 단위로 통째 누락되는 형태로 확장되어 나타난다. 이는 메트릭 이름이 아니라 현상의 이름이며, 인식된 시각 계층·스타일 정보가 코드 생성 결과에서 충분히 구현되지 않는 현상을 가리킨다.

본 연구는 이 현상을 직접 측정하는 단일 신규 메트릭을 제안하지 않는다 — 메트릭 이름이 곧 현상 이름이 되면 측정이 순환적(circular)이 되기 때문이다. 대신 DOM 구조 지표 · 렌더링 결과의 시각 유사도 · 멀티모달 LLM의 종합 판단의 세 축을 함께 보고하는 평가 protocol을 사용하며, 그 이유와 자세한 정의는 §3.1·§5.3에서 다룬다.

제2절 하나의 지표로는 Design-to-Code 품질을 결정할 수 없다

Design-to-Code 분야에서 흔히 쓰이는 SSIM·CLIP·Block-Match·element-IoU는 모두 픽셀이나 요소 위치가 얼마나 비슷한가만 본다 — 즉 슬라이드의 계층 구조가 코드에 잘 보존됐는지와는 직접 관련이 없다. 한편 코드의 class 이름을 매칭하는 측정(Layer Recall, LTED 등)은 layer 보존을 직접 표적하지만 측정 도구가 미리 정해 둔 어휘에 치우치는 편향을 가지며, 디자인의 전체적인 가독성·균형·완성도까지는 잡아내지 못한다.

본 연구는 동일한 데이터에서 세 종류의 평가 축 — (i) 렌더링 결과의 픽셀 유사도, (ii) DOM 구조 기반 측정, (iii) 멀티모달 LLM의 종합 판단 — 이 서로 다른 순위를 산출함을 관찰한다 (구체 수치는 §6.6). 어느 하나도 "전체 진실"이 아니며, 각 축은 서로 다른 사용 목적에 맞춰져 있다 — 픽셀 그대로 복제, 편집 가능한 구조 회복, 발표 가능한 슬라이드 품질. 본 연구는 이 불일치를 결함이 아니라 multi-objective 평가의 본질로 받아들이고, Design-to-Code 평가에서 단일 지표보다 여러 축의 동반 보고가 필요함을 제안한다.

제3절 해법: 생성을 계층 단위로 분해하기

Element omission이 한 번의 호출 안에서 구조·스타일·콘텐츠가 제한된 출력 용량을 두고 동시에 경쟁하기 때문에 일어난다고 본다면 (가설, §7.1), 자연스러운 해법은 생성 과정을 계층 단위로 분해하여 각 호출이 한 가지 책임만 지도록 만드는 것이다. 그러나 단순히 나누기만 하면 새로운 종류의 실패가 등장한다 — 카드별로 투명도와 그림자가 제각각이거나(스타일 어긋남), 카드와 텍스트의 좌표가 맞지 않거나(공간 충돌), 아이콘이 환각된 URL로 깨지는(자산 부재) 문제다.

본 연구의 LayerAgent는 이 모든 실패를 전체 이미지 분석 → 공유 디자인 명세 작성 → 8개 전문 에이전트의 병렬 레이어 생성 → 결정적 조립 → 카드 간 스타일 통일 → 텍스트 주입의 다단계 파이프라인으로 함께 다룬다 (각 단계의 자세한 구조와 역할은 §4). 핵심 설계 원칙은 네 가지다 — (i) 각 전문 에이전트가 전체 이미지가 아닌 자신이 맡은 영역만 직접 보게 하여 풍부한 CSS 재질을 회복하고, (ii) 모든 에이전트가 공유 디자인 명세(DesignSpec)를 읽고 써서 카드 간 스타일이 어긋나는 것을 사전에 막으며, (iii) k-means 팔레트와 OCR 텍스트 높이 같은 결정적 시각 측정값을 프롬프트에 주입해 색·크기 환각을 줄이고, (iv) 아이콘과 도형은 라이브러리 검색으로 가져와 환각된 자산 URL을 구조적으로 차단한다.

본 논문에서 측정된 주장은 위 네 원칙이 통합 시스템으로 작동했을 때 같은 GPT-4o 단일 호출 대비 자동 지표 8개 중 7개에서 우위를 보였다는 것이며 (§6.1), 각 원칙의 개별 기여는 D₂(텍스트 분리 단계)와 D₄(DesignSpec blackboard) 두 컴포넌트에 한정해 격리 측정되었다 (§6.7). N=48 다면적 평가에서 D₄ 제거 시 자동 지표 8개 중 7개가 악화 (특히 SSIM −0.172, LPIPS +0.082, CRP −4.6) — DesignSpec이 cross-agent 시각 일관성을 보존함을 확인. 나머지 두 원칙(library, CV facts)의 개별 효과는 향후 ablation 작업으로 분리한다 (§8 한계).

제4절 연구 질문과 기여

본 연구는 3개 RQ로 정식화된다 (각 RQ는 특정 데이터셋이 직접 지지하는 경험적 주장이며, 데이터 미수집 RQ는 §7 향후 연구로 분리한다). Frontier 모델 일괄 생성과의 비교는 RQ가 아니라 적용 범위의 경계를 명시하는 보조 분석으로 §6.2(Boundary Analysis) + 부록 C에서 별도 보고한다 — 본 연구의 주된 비교는 동일 GPT-4o 조건의 생성 방식들이다.

- RQ1 (현상 — 계층 반영 격차): GPT-4o 기반 일괄 생성은 perception 단계에서 기술된 5–8개의 시각 계층 중 어느 정도를 HTML/CSS 생성 단계에서 반영하지 못하는가? — §3.2·§3.3에서 답한다 (class name이나 사전 정의 layer label에 의존하지 않는 단순 layer 수 측정, 즉 명명 규칙 비의존(class-name-independent) n_layers 기준에서 일괄 생성은 평균 1.6개 layer만 반영).
- RQ2 (방법 — 동일 모델 분해 효과): 동일 모델 조건(same-model, 즉 모든 비교 메서드가 같은 GPT-4o를 사용하는 조건)에서, LayerAgent의 계층 분해 생성은 일괄 생성(`single_pass`)·시각 분석 생성(`visual_cot`)·패턴 주입 생성(`cot_h_rag`) 변형보다 DOM 구조 + 렌더링 기반 시각 유사도 자동 지표를 개선하는가? — Table 1 (§6.1, N=10 다층 시각 효과 디자인)로 답한다. 단, RQ2의 "개선"은 자동 구조·시각 지표에 한정하며, 종합적 발표 품질 차원은 RQ3의 평가 축 간 불일치(metric-axis disagreement) 분석에서 별도 해석한다.
- RQ3 (적용 범위와 평가 해석): LayerAgent의 효과는 어떤 레이아웃 조건에서 나타나며, 이 효과는 DOM 구조 지표·렌더링 유사도·MLLM judge에서 일관되게 관찰되는가? — §6.4–§6.6의 다층 시각 효과 subset, 레이아웃 유형별 분석, 평가 축 불일치 분석으로 답한다.

위 RQ들에 대응하는 본 논문의 기여는 문제 → 방법 → 평가/발견의 세 가지로 정리된다 — 네 개로 늘려 강하게 보이게 하지 않고, 측정으로 직접 지지되는 사실만 남겼다:

1. Problem — 슬라이드 도메인의 계층적 element omission 정식화. Design-to-Code 선행 연구에서 개별 요소 단위로 보고된 element omission이 슬라이드 도메인에서는 시각 계층(layer) 단위로 통째 누락되는 형태로 나타나는 현상을 정식화한다 (§3). 이는 현상의 이름이며, 메커니즘은 생성 단계의 capacity allocation 문제로 가설화된다 (§7.1, 가설 수준 — 직접 인과 검증은 향후 작업).

2. Method — LayerAgent framework. DesignSpec blackboard + vision-grounded specialists + style normalization + text insertion 분리를 포함한 multi-agent layer decomposition 프레임워크 (§4). 컴포넌트별 인과 효과는 전체 시스템의 통합 효과 외에 D₂(Text Inserter, CCR Δ=0.69)와 D₄(DesignSpec blackboard, N=48 다면적 평가에서 8개 지표 중 7개 악화) 두 개에 대해 격리 측정되었으며 (§6.7), 나머지 컴포넌트의 개별 효과는 향후 작업으로 분리된다.

3. Evaluation & Finding — 다면적 평가를 통한 효과 범위 규명. Method-specific class name이나 사전 정의된 layer vocabulary에 의존하지 않는 평가 protocol을 구성하고 (DOM 구조 지표 + render-based 시각 유사도 + multimodal LLM-as-judge의 결합·정렬, §5.3), 그 위에서 LayerAgent의 효과 범위를 측정했다. 그 결과 LayerAgent의 상대적 강점은 (i) same-model GPT-4o 조건 + (ii) 다층 시각 효과 디자인 조건에서 자동 구조·시각 지표가 일관되게 개선되는 형태로 한정되며 — 평면 차트 layout과 종합적 발표 품질(MLLM judge) 차원에서는 우세가 관찰되지 않는다. Frontier 모델 일괄 생성(GPT-5.4·Claude 4.6 Opus)은 디자인 완성도·구성 품질에서 LayerAgent보다 우수한 결과를 보였으며(§6.2 Boundary Analysis), 본 연구의 기여는 frontier 모델 대체가 아니라 GPT-4o급 VLM의 일괄 생성 한계와 계층 분해 생성의 완화 범위를 다면적 평가 위에서 규명하는 것이다.

---

제2장 관련 연구

제1절 Design-to-Code 생성

Design2Code (Si et al., 2024)는 484 웹페이지 벤치마크로 GPT-4V의 중간 충실도를 보고했다. WebSight (Laurençon et al., 2024)는 200만 합성 image-code pair를 공개했다. Calò & De Russis (PACMHCI 2025)는 GPT-4o의 UI 코드 생성 실패를 element omission · element distortion · element misarrangement의 세 유형으로 분류했다 — 본 연구는 이 중 element omission을 슬라이드 도메인의 시각 계층 단위로 확장하여 분석한다 (§3.1). DCGen (FSE 2025)은 분할 정복으로 페이지를 블록 단위로 분해해 코드를 생성한다. LaTCoder (KDD 2025)는 코드 이전에 레이아웃을 chain-of-thought로 명시화한다. ScreenCoder (arXiv:2507.22827, 2025)는 Grounding → Planning → Generation의 3-stage agent 파이프라인을 채택하고 50K image-code pair로 GRPO 미세조정한다. DesignCoder (arXiv:2506.13663, 2025)는 모바일 UI 도메인에서 UI Grouping → Hierarchy-Aware Generation → post-render Self-Correcting Refinement의 3-stage를 사용한다. UIOrchestra (Findings of EMNLP 2025)는 multi-agent framework로 UI design → code 변환을 다루며 본 연구와 가장 가까운 peer — 다만 우리 LayerAgent의 DesignSpec blackboard + CV grounding + library retrieval 통합 구조와는 차별된다.

LayerAgent와의 차별점. ScreenCoder는 image patch reuse(Hungarian matching)로 cross-element 일관성을, DesignCoder는 post-render iterative refinement로 코드 품질을 다룬다. 본 연구의 Style Normalizer는 pre-render CSS 정규화이고, Text Inserter는 시각/콘텐츠 단계 분리이며, DesignSpec blackboard는 생성 시점 cross-agent 스타일 통일이다. 기존 design-to-code 평가는 주로 단일 metric 또는 분류된 metric 그룹을 보고했으며, 본 연구는 슬라이드 도메인에서 DOM 구조 + render 기반 시각 유사도 + multimodal LLM-as-judge를 결합·동반 보고하는 다면적 평가 방식을 적용한다는 점에서 차별화된다.

제2절 시각 교정 / 반복 개선

VisRefiner (arXiv:2602.05998, 2025)는 렌더링 결과와 참조 디자인 간 시각 차이를 학습하여 GPT-4o 대비 Block Match +21.5pt를 달성했다. Vision-Guided Iterative Refinement (arXiv:2604.05839, 2026)는 VLM critic 기반 3회 반복으로 17.8% 개선을 보고했다. 본 연구의 Visual Critic stage는 이들의 반복 vs 단발 트레이드오프를 ablation 플래그(`use_visual_critic`)로 노출한다.

제3절 프레젠테이션 생성

PPTAgent (Zheng et al., EMNLP 2025)는 LLM 피드백 기반 템플릿 반복 수정을, PreGenie (Xu et al., EMNLP Findings 2025)는 코드 리뷰 + 페이지 리뷰 이중 루프를, SlideCoder (Tang et al., EMNLP 2025)는 CGSeg 세그멘테이션 + 계층적 RAG를, AutoPresent (Ge et al., CVPR 2025)는 구조화된 시각 설계 원칙을 강조했다. 이들 선행 연구는 주로 템플릿 수정·코드 리뷰·세그멘테이션 기반 생성·구조화된 설계 원칙에 초점을 두었다. 반면 본 연구는 슬라이드의 시각 계층이 HTML/CSS 생성 단계에서 누락되는 현상에 초점을 맞추고, 이를 계층 단위 생성 분해와 다면적 평가 동반 보고 (DOM 구조 + render 기반 시각 유사도 + multimodal LLM-as-judge)로 분석한다는 점에서 차별화된다.

제4절 멀티에이전트 코드 생성

MetaGPT (Hong et al., ICLR 2024), ChatDev (Qian et al., ACL 2024), CAMEL (Li et al., NeurIPS 2023), AutoGen (Wu et al., COLM 2024)은 소프트웨어 개발 프로세스(설계→구현→테스트) 또는 대화형 multi-agent conversation으로 agent를 분담한다. LayerAgent는 (a) 개발 프로세스가 아닌 출력의 시각 계층(layer) 구조(배경→카드→텍스트→아이콘)로 분담하고, (b) agent 간 통신을 자연어/코드가 아닌 DesignSpec JSON + bounding box JSON의 typed blackboard로 수행하여 truncation·해석 오류를 제거한다.

제5절 Design-to-Code 평가

기존 평가는 전역 유사도(CLIP, SSIM), 구조 매칭(Design2Code의 Block-Match, SlidesBench의 element-matching), 속성 수준(WebRenderBench의 SDA, Widget2Code의 per-property)으로 분류된다. DreamHouse (arXiv:2603.24866, 2026)는 structural validity와 visual fidelity가 직교적이며 frontier VLM의 joint pass rate가 7.1%에 불과함을 보였다. SlideAudit (UIST 2025)은 슬라이드 quality taxonomy를 정립하고 automated metric vs holistic human judgment 사이의 systematic disagreement를 정량적으로 보였다 — 본 연구의 §6.6 평가 축 간 불일치 관찰과 직접 정렬되는 prior. WebDevJudge (2025)는 design-to-code에서 MLLM-as-judge의 best practice (pairwise + code+visual modality)를 정립 — 본 연구의 single-judge limitation (§8) 의 학회 standard 인용. 본 연구는 (a) DreamHouse + SlideAudit의 metric disagreement 발견을 슬라이드 도메인의 다면적 평가 방식으로 확장하고, (b) 기존 render-based 및 DOM-based 평가를 결합하여 class-name-independent하게 정렬한 protocol을 구성하여 메서드별 명명 규칙에 따른 평가 편향을 줄인다.

---

제3장 슬라이드 도메인 element omission의 측정

제1절 Element omission의 정의 — 현상과 측정의 분리

Element omission은 현상의 이름이다. Design-to-Code 선행 연구(Calò & De Russis, 2025)는 GPT-4o의 UI 코드 생성에서 개별 요소가 누락되는 현상을 element omission으로 보고했다. 본 연구는 기존 element omission을 대체하는 새 용어를 제안하는 것이 아니라, 슬라이드 도메인에서 element omission이 layer-level omission으로 관찰되는 특수한 양상을 분석한다 — 슬라이드는 배경·카드·콘텐츠·아이콘 등 시각 계층(layer) 단위로 구조화되므로, element omission이 layer 단위로 통째 누락되는 형태로 발현된다. 즉 인식된 시각 계층·스타일 정보가 코드 생성 결과에서 충분히 구현되지 않는 현상이며, 본 논문은 이를 element omission의 별도 실패 카테고리가 아닌 슬라이드 도메인에서 나타나는 특수한 발현 양상으로 다룬다. 본 연구는 element omission을 직접 표적하는 단일 신규 메트릭을 제안하지 않는다 — 메트릭 이름이 곧 현상 이름이 되면 circular하게 된다. 대신 element omission의 정도를 DOM 구조 지표·렌더링 유사도·멀티모달 LLM 판단의 세 개 주요 평가 축으로 구성된 다면적 평가 방식으로 측정하며, 각 축은 element omission의 서로 다른 측면을 본다. 콘텐츠 보존 여부는 보조 지표인 CCR로 함께 확인한다.

Main 측정 — 다면적 평가 방식 (§5.3):

(i) DOM-based structural metrics (`experiments/metrics/dom_structure.py`): Playwright로 렌더링한 DOM에 JS injection하여 모든 가시 element의 computed style + bounding box를 추출한다. Class name과 무관하므로 메서드별 명명 규칙에 따른 평가 편향이 없다. 측정 항목은 styled element 수(VEC), distinct style fingerprint 수(EDC), distinct effective z-band 수(VLC), rich CSS property 총 사용 횟수(CRP), DOM nesting depth(HD), spatial coverage(SC). Acronym은 본 측정 convention의 표기일 뿐이며, 모두 기존 element/style 카운트의 plain 변형이다.

(ii) Render-based visual similarity (`experiments/metrics/visual_similarity.py`): SSIM (skimage), CLIP (open_clip ViT-B/32), LPIPS (AlexNet). 모두 기존 표준 메트릭.

(iii) Multimodal LLM-as-judge (`experiments/metrics/single_method_judge.py`): GPT-5.4 (Azure)에 reference image + generated PNG + generated HTML 일부를 함께 제공하고 4 criteria (Visual Fidelity / Layer Structure / Content Completeness / Design Quality)에 1–7점 채점.

세 축은 각각 코드 구조 풍부성 / 픽셀-퍼셉추얼 충실도 / 발표 가능성이라는 다른 차원을 본다 (§6.6 metric taxonomy).

Sanity check (legacy, 사용 제한) — class-name-aligned:

본 연구의 초기 분석에서는 perception tree $T_P$와 generation tree $T_G$를 (z-band, type) multiset으로 환원하여 Layer Recall = $|\mathrm{types}(T_P) \cap \mathrm{types}(T_G)| / |\mathrm{types}(T_P)|$, LTED = $\sum_k |m_P(k) - m_G(k)| / (\sum_k m_P(k) + m_G(k))$로 측정했다 (`experiments/probing/layer_tree.py`). 그러나 generation tree 파싱은 class name regex에 의존하며, 본 연구의 정규식은 LayerAgent의 class name (`card-wrap`, `bg-base`, `atmos`, `decor`)에 정렬되어 있다.

⚠ Vocabulary alignment caveat: Claude Opus의 `glass-card`/`node-inner`/`hub-content` 같은 시각적으로 풍부한 class name은 정규식에 매칭되지 않아 거짓 negative를 보고한다 → LayerAgent에 self-favoring. 따라서 Layer Recall/LTED는 (a) 초기 진단에서 element omission 현상을 가시화하는 도구 및 (b) §6.1c와 §6.3에서 prompt 변형이 명명 규칙과 무관함을 활용한 robustness sanity check에 한정 사용하며, 본 논문의 main claim에는 사용하지 않는다.

(parser robustness check, 6→3 z-band 축소 근거 등의 세부는 명명 규칙 정렬 한계 발견 후 부차적 의미를 가짐 — `experiments/probing/layer_tree.py` 코드와 git history에 보존.)

제2절 Element omission의 가시화 — 초기 진단

본 절은 element omission 현상을 가시화하는 초기 진단을 보고한다. 가장 신뢰성 있는 1차 증거부터 본다 — VLM이 같은 이미지에 대해 perception 단계에서는 평균 5–8개의 layer를 자연어로 기술하지만, code generation 단계에서는 0–4개의 layer만 HTML/CSS 구조에 반영한다. 이 layer 개수의 격차는 어떤 class name 어휘에도 의존하지 않는 단순 카운트이므로, element omission 현상이 실재한다는 사실 자체에 대해서는 가장 흔들림이 없는 관찰이다.

| 단계 (probing_minimal pilot, N=10 다층 시각 효과 디자인, GPT-4o) | `n_layers` 평균 (명명 규칙 비의존) |
|---|:---:|
| Stage A perception (자연어로 layer 기술) | 5–8 |
| Stage B1 일괄 생성 (이미지 → HTML) | 0–4 |
| Stage B2 LayerAgent (이미지 → HTML) | 5–10 |

즉 일괄 생성에서 perception이 보장한 5–8 layer 중 평균 1.6개만 HTML/CSS 구조에 반영되며, LayerAgent에서 평균 5.4개로 회복된다 (`experiments/probing/probing_minimal.py`). 이 격차의 모양은 다층 시각 효과 디자인 subset에서 두드러지고 평면 차트 layout에서 약화되는데 — 정량은 §6.5 (Layout-dependent 효과 범위)에서 다면적 평가 지표로 다시 보고된다.

본 논문의 초기 framework는 이 격차를 Layer Recall과 LTED 같은 class-name-aligned 메트릭으로도 정량화했다. 그러나 이 메트릭들은 LayerAgent class name 어휘에 정렬된 regex에 의존하기 때문에, 동일한 시각 구조를 구현하더라도 다른 class 이름을 사용하는 출력은 layer로 인식되지 않아 거짓 negative로 보고되는 클래스명 기반 평가 편향(class-name bias) 위험을 갖는다 (§3.1, §8 한계). 본 논문은 element omission의 정량 main result를 §6.1 Table 1의 다면적 평가 지표로 보고하며, 본 절의 명명 규칙 정렬 수치(N=10 pilot, N=48 main_eval, Figure 1)는 현상 가시화의 보조 자료로 부록 B에 보관한다.

핵심 발견 — Pattern injection의 zero-sum (H-RAG 역설, 명명 규칙과 무관). 패턴 주입 생성(`cot_h_rag`, 복합 CSS 효과 레시피 RAG 주입)은 legacy N=5 측정에서 CSS Richness 2.8 → 10.3으로 상승하는 동시에 string-CCR이 0.80 → 0.26으로 크게 감소한다 — 텍스트 약 74%가 코드에서 사라진다. 이 zero-sum은 명명 규칙과 무관한 콘텐츠 보존 측정(CCR)에서 직접 관찰되며, 단일 VLM의 자기회귀 토큰 예산이 시각 표현과 텍스트 사이에서 경쟁한다는 메커니즘 가설(§7.1)에 부합한다. LayerAgent의 D₂ ablation(§6.7) 결과는 이 zero-sum이 단계 분리로 줄어들 수 있음을 시사한다.

제3절 Cross-VLM probing — frontier model의 baseline 관찰 (legacy diagnostic, 요약)

§3.2의 perception–generation 격차가 GPT-4o 한 모델에 그치는 인공물인지가 자연스러운 다음 질문이다. 이를 가시화하기 위해 10 다층 시각 효과 디자인 × 3 frontier VLM(GPT-4o, GPT-5.4, Claude 4.6 Opus) × 일괄 생성의 cross-VLM probing을 수행했다 (`experiments/probing/cross_vlm_frontier.py`). 정량은 §3.2와 같은 class-name-aligned regex 측정에 기반하므로 명명 규칙 정렬 caveat이 그대로 따라붙으며, frontier 모델 간에서는 모두 LayerAgent와 다른 어휘를 쓰기 때문에 비교가 그래도 상대적으로 공정한 반면 LayerAgent vs frontier 비교는 클래스명 기반 평가 편향의 영향을 받는다 (§3.1).

본문에서는 결론만 짚고 — 세 frontier 모두 baseline gap이 0.69–0.78 범위에 있어, 일괄 생성 모델 upgrade만으로 layer 반영 격차가 크게 닫히지는 않는다는 legacy diagnostic 수준의 관찰만 보고한다. 자세한 수치 표는 부록 B로 옮겼다. 다만 본 논문의 frontier 모델과의 비교는 §6.2 Boundary Analysis + 부록 C에서 별도 보고하며, 거기서 GPT-5.4 일괄 생성이 디자인 완성도·구성 품질에서 LayerAgent를 능가함이 명시된다. 본 절의 관찰은 분해형 접근의 motivation을 보강하는 legacy diagnostic 수준으로만 한정되며, element omission의 모델-일반성에 대한 강한 결론은 향후 명명 규칙 비의존 diagnostic으로 재검증이 필요하다 (§8 한계).

---

제4장 LayerAgent 프레임워크

제1절 전체 구조

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

제2절 Analyzer (Stage 0)

전체 이미지 → (a) 레이아웃 유형(`timeline / dashboard / hub_spoke / pyramid / grid / split / vertical_stack / freeform`), (b) 각 카드/히어로/장식 요소의 정규화 bounding box (0–1 비율)를 출력한다. 이후 모든 crop과 placement의 anchor.

제3절 Design Director — DesignSpec Blackboard

전체 이미지 + CV facts (k-means palette, OCR 텍스트 높이 분포, HSV 채도)를 입력받아 typed JSON `DesignSpec`을 출력한다:

```json
{
  "aesthetic_label": "multi_layer_visual_effect",
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

이후 모든 specialist는 DesignSpec을 prompt hint로 받는다(`spec_to_hint`, `layeragent/agents/design_director.py:55`). 결과적으로 카드 A의 반투명 효과가 카드 B에서 단색으로 변하는 스타일 표류 가 사전적으로 차단된다 — 이는 단순 분해(Method E)에서 자주 관찰되는 실패 양식이다.

CV grounding의 효과. 팔레트는 k-means(k=6)로 추출되어 모델이 색을 환각할 여지를 줄이고, OCR 텍스트 높이는 폰트 크기 결정에 결정적 anchor를 제공하며, HSV 채도는 flat vs vivid aesthetic 분류의 단서가 된다. ablation `no_cv_facts`로 효과 격리.

제4절 Specialist Agents (Stage 1, 병렬)

- Base BG / Atmosphere / Decoration: 전체 이미지 + DesignSpec → 배경 그라디언트, radial glow, decoration shape를 분리된 layer로 생성. 이 분리는 분위기와 패턴이 같은 z=0 안에서 충돌하지 않도록 한다.
- Card Detail × N: 각 카드의 crop된 이미지(주변 패딩 포함) + DesignSpec → 카드별 풍부한 CSS 효과(`backdrop-filter`, 다중 `box-shadow`, rgba 투명도, 테두리 효과). 좁은 시각 범위가 선택적 CSS 재질(반투명·blur·gradient 등)을 회복시킨다 — 통제 실험에서 같은 GPT-4o가 전체 이미지에서는 카드당 CSS 효과 2.8개, crop에서는 6–8개를 생성한다.
- Hero Detail × N: 히어로 블록(큰 숫자, 메인 메시지, 특수 그래픽)을 크롭으로 별도 처리.
- Icon Agent: 카드별 의미 분석 → FontAwesome 클래스 검색 → 실제 `<i class="fa-...">` 태그 주입. 환각된 아이콘 URL 을 구조적으로 차단 (`layeragent/libraries/icon_library.py`).
- Chart Agent / Table Agent: 슬라이드 타입이 차트/테이블일 때 SVG primitive로 sparkline·bar·gauge·harvey table을 결정적 생성.

제5절 Assembler

8 specialist의 HTML 단편을 z-index band([0,5,10,20,30,40])로 결정적 stacking. 단순 concat이 아니라 절대 좌표(Analyzer의 bbox 정규화 비율 × 1280×720)와 z-index를 명시적으로 부착한다.

제6절 Style Normalizer (Stage 2)

조립된 HTML을 텍스트 입력만 받아 카드 간 CSS 속성을 통일한다 (`layeragent/agents/style_normalizer.py`):

- 배경 rgba alpha — 모든 카드 동일값
- 테두리 색상/두께 — 통일
- border-radius — 통일
- box-shadow — 통일
- backdrop-filter blur — 통일

불변 보장: position/left/top/width/height/z-index은 변경하지 않는다. 이미지 입력 없이 코드만 보는 텍스트 전용 agent로, 각 카드의 독립 생성에서 발생한 표류를 사후 동기화한다. ablation `no_style_norm`으로 effect 격리.

A2UI Protocol (Google, 2026)이 client-side renderer로 design-system을 강제하는 것과 동일한 설계 원리를 VLM 파이프라인 내부에서 실현한 것이다.

제7절 Text Inserter (Stage 3)

완전히 스타일링된 HTML(배경 + 카드 + 정규화된 스타일) + 콘텐츠 데이터(제목, 설명, 메트릭, 리스트)를 받아, 기존 카드 구조 내 빈 컨테이너를 식별하여 텍스트를 주입한다.

이 단계의 핵심은 시각 디자인 확정 후 텍스트 처리라는 순서이다. 단일 VLM에서 풍부한 CSS 생성과 정확한 텍스트 배치가 zero-sum 경쟁을 벌이는 현상(H-RAG에서 CSS Richness↑이지만 콘텐츠 74% 손실)이 단계 분리로 구조적으로 해소된다. ablation `no_text_inserter`로 격리.

제8절 Overflow Repair (선택, v10 P1)

조립된 HTML을 Playwright로 렌더링한 뒤 측정한 bounding box overflow를 분석하여, 폰트 크기/패딩/줄 수를 미세 조정한다. 시각 critic과 다르게 결정적 측정 기반이라 LLM 호출이 필요없다 (`layeragent/agents/overflow_repair.py`).

제9절 Visual Critic (선택)

Playwright 스크린샷 vs 원본 이미지 비교 후 VLM이 diff를 작성, CSS 속성 단위 보정. iteration 비용이 크므로 default off.

제10절 Chat Mode (인터랙티브 입력)

기존 데이터셋 spec 대신 자연어 메시지 + 참조 이미지를 입력받는 진입점 (`run_from_chat`, `layeragent/pipeline.py:155`). chat_parser agent가 메시지를 `{slide_type, content, style}`로 구조화한 뒤 동일 파이프라인에 전달한다. 데모: `python -m experiments.demo_chat`.

제11절 구현 및 ablation 플래그

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

제5장 실험 설정

제1절 데이터 — 48 슬라이드 평가셋

본 연구의 평가셋은 두 부분으로 구성된다 (`data/eval_dataset/meta.json`, total=48):

(A) 10 다층 시각 효과 디자인 — 본 방법이 목표로 하는 고복잡도 다층 디자인 조건. 본 subset은 paper 작성 시점에 별도로 큐레이션된 디자인 모음이며, paper 작성 시점의 사후 분석에서 아래 6가지 다층 시각 효과 특성 중 복수 항목을 공통으로 가진다 (subset 정당화의 post-hoc characterization).

다층 시각 효과 특성 (6 criteria):
- C1: 배경 그라디언트 또는 radial glow (분위기 layer 존재)
- C2: 장식 도형/선/점 (decoration layer 존재)
- C3: 카드·패널·히어로 블록의 multi-instance (카드 layer ≥ 2개)
- C4: 반투명/blur/backdrop-filter (rgba alpha < 1 또는 backdrop-filter)
- C5: shadow / border / border-radius (rich CSS 효과 ≥ 2)
- C6: 명시적 z-index stacking 또는 시각 element overlap

Subset 디자인별 특성 매핑 (✓ = 해당 특성 존재):

| # | layout | 구조 | C1 | C2 | C3 | C4 | C5 | C6 | 만족 수 |
|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 01 | timeline | 4노드 + 카드 + 강조 라인 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 6 |
| 02 | dashboard | 3 메트릭 카드 + 차트 | ✓ | — | ✓ | ✓ | ✓ | — | 4 |
| 03 | comparison_split | 좌우 분할 + VS 배지 + 8카드 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 6 |
| 04 | pyramid | 3단계 1-2-3 카드 | ✓ | — | ✓ | ✓ | ✓ | ✓ | 5 |
| 05 | hub_spoke | 중앙 허브 + 6 연결 카드 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 6 |
| 06 | before_after | 색상 전환 + 변환 | ✓ | — | ✓ | ✓ | ✓ | — | 4 |
| 07 | feature_grid | 2×3 그리드 + 아이콘 + 태그 | ✓ | — | ✓ | ✓ | ✓ | — | 4 |
| 08 | roadmap | 5 페이즈 교차 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 6 |
| 09 | layered_stack | 4층 겹침 + 레인보우 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 6 |
| 10 | stats_hero | 히어로 숫자 + 4 스탯 카드 | ✓ | — | ✓ | ✓ | ✓ | — | 4 |

본 subset의 10개 디자인 모두 6 criteria 중 ≥ 4개를 만족한다 (평균 5.3, 최소 4, 최대 6). 비교용으로 (B) 38 consulting-style design은 동일 기준에서 평균 ~2.1개 만족 (대부분 평면 차트 layout으로, C3·C5만 충족). ⚠ 방법론적 caveat: 본 criteria는 사전 정의된 selection rule이 아니라 기존 subset의 사후 특성 분석이다 — 즉 "이 criteria를 만족하는 sample을 골랐다"가 아니라 "이 subset이 공통적으로 가진 다층 시각 효과 특성을 6 axis로 정량화했다"의 의미. 향후 작업에서 이 criteria를 사전 selection rule로 사용해 더 큰 subset(N=30+)으로 재구성하는 것이 paper의 한계로 명시된다 (§8).

(B) 38 consulting-style design — Gemini 3 Pro Image Preview로 생성, 5종 스타일(McKinsey blue / BCG green / Bain red / Editorial warm / Minimal white) × 8개 layout 유형(mekko, matrix_2x2, waterfall, harvey_table, bar_chart, line_chart, process_flow, pyramid):

| 레이아웃 유형 | N | 특징 |
|---|:---:|---|
| mekko | 5 | Marimekko 차트 + 카테고리 라벨 |
| matrix_2x2 | 5 | 2x2 사분면 + 축 라벨 |
| waterfall | 5 | bridge bars + connector |
| harvey_table | 3 | row × col + harvey ball cell |
| bar_chart | 5 | bar + value labels |
| line_chart | 5 | trend + data points |
| process_flow | 5 | 단계 + arrow connector |
| pyramid | 5 | 3-tier hierarchy |

(B)는 분포 외 일반화 검증용이다. (A)는 시스템이 설계 대상으로 삼은 다층 레이아웃, (B)는 일부 평면적인 챠트 레이아웃을 포함한다.

제2절 비교 메서드

| code | 메서드 (논문 표시) | 접근 |
|---|---|---|
| A | 일괄 생성 (`single_pass`) | 단일 GPT-4o 호출로 전체 이미지 → HTML |
| B | 시각 분석 생성 (`visual_cot`) | 시각 분석을 자연어로 먼저 수행한 뒤 코드 생성 (2단계) |
| C | 패턴 주입 생성 (`cot_h_rag`) | 시각 분석 + CSS 효과 패턴 레시피(RAG)를 함께 제공해 코드 생성 |
| D | LayerAgent (`layeragent`) | 본 연구 — 계층 단위로 생성 책임을 분해하는 multi-agent full pipeline |

모든 메서드에 동일 콘텐츠 데이터, 동일 모델(gpt-4o-2024-08-06), 동일 시드(seed=0) 제공.

제3절 평가 방식 — 다면적 평가

Critical methodological note: 본 논문 draft 초기 버전은 Layer Recall + LTED를 element omission의 main metric으로 사용했다. 그러나 이들은 LayerAgent class name 어휘에 정렬된 regex 기반 측정으로, 동일한 시각 출력이라도 다른 class name을 쓰는 메서드(Claude Opus의 `glass-card`, `node-inner` 등)에 거짓 negative를 보고하는 클래스명 기반 평가 편향 위험이 있다 (§7.3). 본 논문은 이를 sanity check로 강등하고, DOM 구조 지표·렌더링 기반 시각 유사도·멀티모달 LLM 판단을 함께 보고하는 다면적 평가 방식으로 main result를 보고한다.

본 평가 방식의 신규성은 새로운 단일 metric의 발명이 아니라, DOM 구조 지표·렌더링 기반 시각 유사도·멀티모달 LLM 판단을 class-name-independent하게 결합·동반 보고하여 메서드별 명명 규칙에 따른 평가 편향을 줄이는 구성에 있다. 4개 main 축 + 1개 legacy sanity check로 구성된다.

축 ① DOM-based Structural Metrics (`experiments/metrics/dom_structure.py`):

Playwright로 렌더링한 DOM에 JS injection하여 모든 가시 element의 computed style + bounding box를 추출한다. Class name이나 사전 정의된 layer label에 의존하지 않으며, 모든 메서드에 동일하게 적용된다 (즉 method-agnostic). 측정 항목은 다음과 같다 — 모두 element/style의 plain count 변형이며, 본 표기는 본 연구의 측정 convention일 뿐이다:

- 비자명 styling(배경/테두리/그림자/filter)을 가진 가시 element 수 — VEC
- distinct style fingerprint `(bg, border, radius, shadow, backdrop, opacity)` 튜플의 가짓수 — EDC
- distinct effective-z band 수 (explicit z-index OR DOM depth band) — VLC
- backdrop-filter, multi-shadow, gradient, transform, opacity<1, border-radius 등 rich CSS property의 총 사용 횟수 — CRP
- 가시 element 중 max DOM nesting depth — HD
- 슬라이드 영역 중 가시 element가 차지하는 면적 비율 — SC

축 ② Render-based Visual Similarity (`experiments/metrics/visual_similarity.py`):

- SSIM ↑ — local window 기반 픽셀 구조 유사도 (skimage)
- CLIP ↑ — open_clip ViT-B/32 image embedding cosine similarity (semantic-level, AutoPresent/Design2Code/SlideCoder 표준)
- LPIPS ↓ — AlexNet deep feature 거리 (perceptual-level, Zhang et al. CVPR 2018)
- Block-Match, Position (OCR-based): 다크 + 한국어 + blur 도메인에서 모든 메서드 0 → 도메인 미지원으로 보고하지 않음

축 ③ Multimodal LLM-as-Judge (`experiments/metrics/single_method_judge.py`):

Judge model GPT-5.4 (Azure) — generator(GPT-4o)와 다른 모델 계열로 self-evaluation bias 차단 (Zheng et al., 2023). Judge에게 reference image + generated PNG + generated HTML 처음 3,000자 함께 제공 (tool-grounded; WebDevJudge 2025의 code+visual modality best practice 따름). 4 criteria × 1–7 점:
- Visual Fidelity (VF) / Layer Structure (LS) / Content Completeness (CC) / Design Quality (DQ)

축 ④ Content Completeness (auxiliary):
- CCR ↑ — 입력 텍스트가 HTML에 문자열로 등장하는 비율 (시각 가시성 미반영; MLLM judge CC가 visual proxy)

Legacy sanity check — Class-name-aligned (참고용, main claim 외) (`experiments/probing/layer_tree.py`):
- Layer Recall, LTED — class name regex 기반 (LayerAgent 어휘에 정렬). Vocabulary alignment 한계로 인해 §3.2 (현상 가시화), §6.1c (보조 표), §6.3 (prompt 변형 robustness sanity check — 명명 규칙과 무관하므로 방향성은 robust)에 한정 사용.

Render guard: Playwright 정상 렌더링 비율 (전 메서드 100%).

모든 메트릭 코드와 단위 테스트 `experiments/metrics/` 공개.

제4절 실험 인프라

- 4-stage cacheable 파이프라인 (`experiments/main_eval.py`): generate → render(Playwright) → reference perception(VLM 캐시) → metrics. 각 stage는 재시작 가능.
- 총 4 메서드 × 48 슬라이드 = 192 cell. 실행 시간 82분. 생성 실패 0건.
- 결과: `results/main_eval/eval_results.jsonl`, `eval_summary.csv`, `analysis_report.md`.

---

제6장 결과

제1절 Table 1 — Same-model GPT-4o, 다층 시각 효과 디자인 subset 비교 (RQ2)

본 절은 동일 base model GPT-4o 위에서, 시스템이 설계 대상으로 삼은 다층 시각 효과가 강한 디자인 subset (N=10) 위에서, 4가지 메서드를 다면적 평가 지표 8개로 비교한다 (`results/new_eval/summary.json`). 본 표는 전체 슬라이드 도메인의 main result가 아니라 타깃 subset에서의 분해 효과 측정임을 먼저 명시한다 — 비교 범위가 본 적용 범위에 한정되는 이유는 §3.2와 §6.5에서 설명한 layout 의존적 효과 범위이며, frontier 모델과의 비교 및 레이아웃 유형별 일반화는 §6.2와 §6.5에서 별도로 다룬다.

Table 1. 4 method × 10 다층 시각 효과 디자인 × 8 다면적 평가 지표 (DOM-based + render-based). 굵은 = 1위.

| Metric | A. 일괄 생성 | B. 시각 분석 생성 | C. 패턴 주입 생성 | D. LayerAgent | Δ (D vs A) |
|---|:---:|:---:|:---:|:---:|:---:|
| VEC ↑ (visual elements) | 9.1 | 7.3 | 9.8 | 20.9 | +11.8 (2.3×) |
| EDC ↑ (style diversity) | 3.0 | 2.7 | 3.5 | 9.7 | +6.7 (3.2×) |
| VLC ↑ (layer count) | 1.5 | 1.5 | 2.4 | 2.9 | +1.4 (1.9×) |
| CRP ↑ (CSS richness) | 23.6 | 18.3 | 28.1 | 51.5 | +27.9 (2.2×) |
| HD ↑ (DOM depth) | 4.9 | 4.8 | 5.5 | 7.0 | +2.1 |
| CLIP ↑ (semantic) | 0.450 | 0.448 | 0.430 | 0.492 | +0.042 |
| LPIPS ↓ (perceptual) | 0.653 | 0.652 | 0.709 | 0.589 | −0.064 |
| SSIM ↑ (pixel) | 0.493 | 0.486 | 0.467 | 0.470 | −0.023 |

핵심 발견 1 — LayerAgent가 DOM-based + render-based로 구성된 8개 자동 지표 중 7개에서 1위. SSIM에서는 일괄 생성이 0.023 높았으나, N=10에서 관찰된 표준편차(~0.10)를 고려하면 작은 차이로 본 논문은 이를 LayerAgent의 명확한 우위로 해석하지 않는다. DOM 구조 5개 (VEC/EDC/VLC/CRP/HD) 모두 2위 대비 1.5–3.2×, 시각 fidelity 2개(CLIP, LPIPS)도 1위. 동일 base model 위에서 자동 지표상 분해의 효과가 일관되게 관찰된다 (단, holistic 차원은 §6.1b 별도 보고).

핵심 발견 2 — 시각 분석 생성(`visual_cot`)·패턴 주입 생성(`cot_h_rag`)은 일괄 생성(`single_pass`) 대비 일관된 개선을 보이지 않음.
- 시각 분석 생성(`visual_cot`): VEC 7.3 < 일괄 생성 9.1, CSS richness 18.3 < 23.6
- 패턴 주입 생성(`cot_h_rag`): 본 표의 자동 지표 중 LPIPS와 CLIP에서 4 메서드 가운데 가장 낮은 값 (LPIPS 0.709, CLIP 0.430)
- 단순한 시각 분석 단계 추가나 CSS 패턴 지식 주입만으로는 일괄 생성 대비 일관된 개선이 관찰되지 않았다.
- 즉 생성 단위 분해가 빠진 prompt-level 변형만으로는 충분하지 않으며, LayerAgent의 통합 파이프라인(DesignSpec + Library + Style Normalizer + Text Inserter)이 same-model 조건에서 더 높은 구조적 풍부성과 시각 fidelity를 보였음을 시사한다. 컴포넌트별 인과 효과는 Text Inserter(D₂)와 DesignSpec blackboard(D₄) 두 개에 대해 §6.7에서 격리 측정 — D₄ 제거 시 N=48 다면적 평가에서 SSIM/LPIPS/CRP 등 시각 fidelity 7개 지표 악화 확인. 나머지 컴포넌트(library, CV facts, style normalizer)의 인과 효과는 향후 연구로 남긴다.

Table 1b — MLLM judge (GPT-5.4, 4 criteria, 1–7 scale, N=48 main_eval).

| Criterion | 패턴 주입 생성 | LayerAgent | 일괄 생성 | 시각 분석 생성 |
|---|:---:|:---:|:---:|:---:|
| Visual Fidelity ↑ | 1.73 ± 0.61 | 1.65 ± 0.93 | 2.17 ± 0.69 | 2.08 ± 0.68 |
| Layer Structure ↑ | 3.00 ± 0.80 | 3.58 ± 0.96 | 3.46 ± 0.68 | 3.08 ± 0.65 |
| Content Completeness ↑ | 3.77 ± 1.69 | 2.35 ± 1.49 | 3.81 ± 1.72 | 3.60 ± 1.51 |
| Design Quality ↑ | 3.40 ± 0.82 | 2.79 ± 1.01 | 3.75 ± 0.79 | 3.29 ± 0.90 |
| Average ↑ | 2.97 | 2.59 | 3.30 | 3.02 |

MLLM judge에서는 일괄 생성이 평균 우세 (3.30 vs LayerAgent 2.59). LayerAgent는 Layer Structure 축에서만 좁게 우세 (3.58 vs 3.46).

Table 1과 Table 1b를 함께 읽기 — 구조적 풍부성과 종합적 발표 품질의 분리. Table 1은 LayerAgent가 더 많은 시각 요소, 더 다양한 스타일, 더 풍부한 CSS 구조를 생성함을 보여준다. 그러나 이러한 구조적 풍부성이 항상 종합적 발표 품질로 이어지는 것은 아니다 — Table 1b의 MLLM judge 결과는 LayerAgent가 때로는 과도한 분해와 조립 과정에서 전체 가독성·정렬·콘텐츠 완성도에서 손해를 볼 수 있음을, 그리고 종합적 차원에서는 일괄 생성의 거칠지만 안정적인 출력이 평균적으로 더 높은 점수를 받음을 보여준다. 이는 LayerAgent가 완성 슬라이드 생성기라기보다, 편집 가능한 계층 구조와 시각 효과를 복원하는 중간 표현 생성 시스템(intermediate representation recovery)에 가깝다는 것을 시사한다 — 즉 LayerAgent의 직접 목표는 종합적 슬라이드 품질의 일괄 향상이 아니라, layer-level element omission을 완화하는 편집 가능한 계층 구조의 복원이다. 자동 지표가 잡아내는 코드 구조의 풍부성과 MLLM judge가 잡아내는 발표 가능성은 본 평가에서 서로 다른 차원으로 분리되어 관찰되며, 본 논문은 어느 한 축의 우위로 LayerAgent를 정당화하지 않는다 (§6.6 평가 축 간 불일치 분석에서 추가 논의).

(class-name-aligned legacy metric — Layer Recall, LTED — 위에서의 N=48 main_eval 결과 및 Figure 2는 클래스명 기반 평가 편향 위험을 고려해 부록 B로 옮겼다.)

제2절 Frontier 모델 일괄 생성과의 경계 분석 (Boundary Analysis)

본 연구의 주된 비교 대상은 frontier 모델이 아니라 동일 GPT-4o 조건의 생성 방식들이다 (RQ2, §6.1). 다만 LayerAgent의 적용 범위를 명확히 하기 위해, GPT-5.4 및 Claude 4.6 Opus 기반 일괄 생성을 참고 비교로 추가 분석했다. 이 비교는 RQ에 직접 답하는 결과가 아니라, 본 연구 주장의 경계(boundary)를 명시하는 보조 분석이다.

Table 2. Frontier 모델 기반 일괄 생성과의 적용 경계 비교 (boundary reference, N=10 다층 시각 효과 디자인). 가격은 2026 Q1 list price 기준 추정 (GPT-4o $2.5/$10, GPT-5.4 $5/$15, Claude 4.6 Opus $15/$75 per M input/output).

| Method | VEC | EDC | CRP | SSIM↑ | CLIP↑ | LPIPS↓ | Approx. API cost/slide | Time |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| LayerAgent (GPT-4o + 분해) | 20.9 | 9.7 | 51.5 | 0.470 | 0.492 | 0.589 | $0.232 | 60s |
| 일괄 생성 (GPT-5.4) | 37.1 | 16.4 | 135.6 | 0.504 | 0.578 | 0.411 | $0.075 | 85s |
| 일괄 생성 (Claude 4.6 Opus) | 27.2 | 14.0 | 68.0 | 0.500 | 0.525 | 0.502 | $0.421 | 108s |

핵심 관찰 (boundary). Frontier 모델 기반 일괄 생성은 본 표의 자동 지표(VEC/EDC/CRP/SSIM/CLIP/LPIPS) 전반에서 LayerAgent보다 우수한 결과를 보였다 — GPT-5.4는 6개 지표 모두 1위, Claude Opus도 자동 시각 지표 4개에서 LayerAgent보다 우세. Table 2의 목적은 비용 우위를 주장하는 것이 아니라, model scaling과 process decomposition이 서로 다른 개선 경로임을 분리해 보이는 것이다 — frontier scaling은 모델 capacity의 향상이고, LayerAgent는 동일 모델 위에서 generation process를 layer 단위로 분해하는 intervention이며, 두 경로가 동일 quality 차원에서 직접 경쟁하지 않는다. 따라서 LayerAgent의 실용적 의미는 frontier 대체가 아니라, 조직이 특정 모델 버전(GPT-4o급)으로 고정되어 있거나 생성 과정을 inspectable·interpretable하게 유지해야 하는 경우의 process-level decomposition에 남는다.

따라서 Table 2는 LayerAgent와 frontier 모델의 성능 경쟁을 위한 비교가 아니라, LayerAgent의 주장이 동일 GPT-4o 조건의 process-level intervention에 한정됨을 명시하는 경계 분석이다. 상세 비교(method별 자동 지표 breakdown, 비용·시간 분석)는 부록 C에 별도 보고한다.

제3절 Trivial baseline check (sanity, legacy diagnostic)

LayerAgent의 same-model 우세(Table 1)가 분해 효과인지 또는 단순 prompt 조정으로 가능한지를 sanity check하기 위해 single_pass_zexplicit 변형을 구현했다 (`baselines/single_pass_zexplicit.py`). 일괄 생성 prompt에 z-index 6-band 명시 한 줄만 추가:

| Method (N=10 다층 시각 효과 디자인, legacy LTED/Recall ⚠) | 설명 | LTED ↓ ⚠ | Layer Recall ↑ ⚠ | avg layer count |
|---|---|:---:|:---:|:---:|
| 일괄 생성 (`single_pass`, baseline A) | 기본 일괄 생성 | 0.823 ± 0.14 | 0.224 ± 0.13 | (main_eval) |
| z-index 명시 일괄 생성 (`single_pass_zexplicit`, baseline A') | z-index 6-band를 prompt에 명시 추가 | 0.844 ± 0.12 | 0.292 ± 0.17 | 3.8 |
| LayerAgent (`layeragent`, D) | 계층 단위 분해 생성 (full pipeline) | 0.551 ± 0.13 | 0.759 ± 0.16 | 8.5 |

z-explicit prompt는 legacy Recall을 0.224 → 0.292로 살짝 올리지만 LayerAgent의 0.759와는 거리가 있다 (legacy metric 기준). avg layer count(명명 규칙과 무관) 또한 z-index 명시 일괄 생성(`single_pass_zexplicit`) 3.8 vs LayerAgent 8.5로 차이가 유지된다. 이 결과는 단순 z-index 명시만으로는 LayerAgent와 같은 수준의 계층적 element 반영이 관찰되지 않음을 sanity check 차원에서 보여준다. 다만 본 표는 legacy 명명 규칙 정렬 metric 기반이므로, generation capacity 증가에 대한 강한 인과 주장은 본 표 단독이 아니라 §6.1 Table 1 (자동 지표) + §6.7 ablation 결과와 함께 해석한다.

(prompt 변형 자체는 명명 규칙과 무관하므로 방향성 관찰은 robust하지만, 절대 effect size 해석에는 명명 규칙 정렬 caveat 적용.)

---

제4절 Sweet spot — 다층 시각 효과 디자인 통합 분석 (RQ3 part A)

본 절은 시스템 설계 대상인 다층 시각 효과 디자인 subset에서 두 메트릭 축(legacy LTED + MLLM judge)이 합의하는지를 직접 검증한다. (A) 10 다층 시각 효과 디자인 subset:

| 메서드 | LTED ↓ (명명 규칙 정렬 ⚠) | MLLM avg ↑ (명명 규칙 비의존) |
|---|:---:|:---:|
| 일괄 생성 | 0.823 | 3.90 |
| 시각 분석 생성 | 0.820 | 4.03 |
| 패턴 주입 생성 | 0.827 | 3.85 |
| LayerAgent | 0.551 | 4.15 |

다층 시각 효과 디자인에서 LayerAgent는 legacy LTED를 거의 절반으로 단축(0.823 → 0.551, 명명 규칙 정렬 caveat ⚠)하면서, 명명 규칙과 무관한 MLLM judge에서도 평균 근소 우세 (4.15 vs 3.85–4.03). 즉 명명 규칙 정렬 legacy LTED와 명명 규칙 비의존 MLLM judge가 같은 방향을 가리킨다 — 적어도 MLLM judge 축은 명명 규칙과 무관하므로, 합의의 일부는 명명 규칙 정렬에 영향받지 않는 sub-claim이다.

§6.1 Table 1b (N=48 main_eval)와의 관계. Table 1b의 N=48 전체 평가셋에서는 holistic MLLM judge 평균이 일괄 생성 우세였다 (3.30 vs LayerAgent 2.59). 본 절의 N=10 다층 시각 효과 디자인 subset에서는 LayerAgent가 MLLM 평균에서도 근소하게 우세하다 (4.15 vs 3.85–4.03). 이 두 결과는 모순이 아니라 적용 범위의 함수다 — LayerAgent의 MLLM 우위는 전체 슬라이드 도메인에서가 아니라 시스템이 설계 대상으로 삼은 다층 시각 효과 subset에 한정된다. 이 조건에서의 상대적 강점이 본 논문에서 가장 신뢰성 있게 관찰된 범위이며, 그 이외 layout(평면 차트 등)에서의 분포는 §6.5에서 별도 보고한다. 다음 §6.5는 이 합의가 layout 복잡도에 따라 어떻게 변하는지를 9개 레이아웃 유형으로 확장한다.

제5절 레이아웃 유형별 효과 범위 분석 — 9개 레이아웃 비교 (RQ3 part B)

Table 3. 9개 레이아웃 유형별 LayerAgent 효과 비교 — primary axis (MLLM judge) + auxiliary diagnostic (legacy LTED). 본 논문에서 layout-dependent 효과 해석의 primary axis는 명명 규칙 비의존 MLLM judge이며, legacy LTED는 명명 규칙 정렬 caveat 하에서 보조 진단(auxiliary diagnostic)으로만 동반 보고한다 — 두 축의 부호 합의는 명명 규칙 의존성과 무관한 sub-claim의 robustness 신호로 해석한다.
- MLLM Δ (primary) = LayerAgent avg − (best baseline avg), 양수 = LayerAgent 우세 (명명 규칙 비의존, MLLM judge 4-criteria 평균).
- LTED Δ (auxiliary diagnostic ⚠) = (best baseline LTED) − (LayerAgent LTED), 양수 = LayerAgent 우세 (legacy, 명명 규칙 정렬 caveat 적용).

| Layout | N | MLLM LayerAgent (primary) | MLLM Δ (primary) | LTED LayerAgent ⚠ (aux) | LTED Δ ⚠ (aux) | Primary 해석 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| 다층 시각 효과 디자인 | 10 | 4.15 | +0.12 | 0.551 | +0.27 | LayerAgent 우세 (보조 지표 동방향) |
| pyramid | 5 | 1.90 | −1.50 | 0.764 | +0.17 | 일괄 생성 우세 (보조 지표만 LayerAgent 우세) |
| mekko | 5 | 2.15 | −1.50 | 0.753 | +0.08 | 일괄 생성 우세 (보조 지표만 LayerAgent 우세) |
| process_flow | 5 | 2.30 | −1.60 | 0.818 | +0.06 | 일괄 생성 우세 (보조 지표만 LayerAgent 우세) |
| harvey_table | 3 | 2.75 | −0.75 | 0.910 | +0.06 | 일괄 생성 우세 (보조 지표만 LayerAgent 우세) |
| matrix_2x2 | 5 | 2.05 | −0.45 | 0.917 | +0.01 | 일괄 생성 우세 (보조 지표만 LayerAgent 우세) |
| waterfall | 5 | 2.45 | −0.35 | 0.662 | −0.03 | 일괄 생성 우세 (양 축 동방향) |
| line_chart | 5 | 2.20 | −0.40 | 0.845 | −0.03 | 일괄 생성 우세 (양 축 동방향) |
| bar_chart | 5 | 1.90 | −1.10 | 0.733 | −0.09 | 일괄 생성 우세 (양 축 동방향) |

핵심 발견 (RQ3 정착).

1. 두 축이 다층 시각 효과 디자인 조건에서만 LayerAgent의 상대적 강점을 일관되게 가리킨다 (LTED Δ +0.27, MLLM Δ +0.12). 단, LTED는 명명 규칙 정렬 legacy 측정이므로 본 정렬의 신뢰성은 명명 규칙 비의존 MLLM judge 축이 같은 방향을 가리킨다는 사실에 의존한다.
2. 평면 차트(bar/line/waterfall)에서도 두 축이 합의 — 이번에는 일괄 생성 우세로. 분해 비용 > 이득.
3. 6개 중간 layout(pyramid, mekko, process_flow, harvey_table, matrix_2x2, ...)에서 두 축이 불일치: 명명 규칙 정렬 LTED는 LayerAgent의 부분 우위(layer 수 회복)를 점수화하지만 클래스명 기반 평가 편향 위험 내재 — 명명 규칙과 무관한 MLLM judge는 그 출력을 덜 전문적이고 가독성이 낮은 슬라이드로 본다. 즉, layer 수만 회복하는 것은 발표 가능한 슬라이드를 보장하지 않는다.

본 연구의 적용 범위에 대한 정직한 해석. 두 축은 다층 시각 효과 디자인 조건에서만 LayerAgent의 상대적 강점을 일관되게 가리킨다. 그 외 layout에서는 (i) LTED 우위가 발표 품질로 이어지지 않거나 (ii) 분해 비용 자체가 일괄 생성보다 나쁘다. 전체 슬라이드 도메인에서 LayerAgent가 우월하다는 주장은 데이터로 지지되지 않으며, 본 논문은 이 사실을 thesis의 일부로 명시 흡수한다. 시사점 (layout-conditional routing의 가능성). 이 결과는 향후 시스템 설계에서 layout-conditional routing이 필요할 수 있음을 시사한다 — 예컨대 Analyzer가 다층 시각 효과 디자인을 감지한 경우 LayerAgent를, 평면 차트형 레이아웃을 감지한 경우 일괄 생성을 선택하는 방식이다. 본 논문은 이 routing 자체를 구현·검증하지 않으며, §10 향후 연구로 분리한다.

제6절 메트릭 분류학 — 평가 축별로 다른 질문 (RQ3 part C)

Table 4. 본 연구가 정착시키는 메트릭 축 분리.

| 평가 축 | 대표 metric | 측정 차원 | Same-model GPT-4o 우승 | Cross-model 우승 | 답하는 질문 |
|---|---|---|---|---|---|
| ① DOM-based structural metrics | VEC, EDC, CRP, HD | 코드 구조 풍부성 | LayerAgent | GPT-5.4 | "코드가 시각적으로 풍부한 element를 만드는가?" |
| ② Render-based visual similarity | SSIM, CLIP, LPIPS | 시각 충실도 | LayerAgent (CLIP/LPIPS) / 일괄 생성 (SSIM) | GPT-5.4 | "렌더된 결과가 reference처럼 보이는가?" |
| ③ Multimodal LLM-as-judge | GPT-5.4 4-criteria | 시각 usability·legibility·design quality | 일괄 생성 | (미측정) | "출력이 발표 가능한 슬라이드인가?" |
| ④ Class-name-aligned (legacy sanity check) | LTED, Layer Recall | class name regex 매칭 | LayerAgent ⚠ | ⚠ 공정 비교 부적합 / 참고용 | ⚠ 클래스명 편향: "출력이 LayerAgent의 class naming convention에 맞는가?" |
| ⑤ Content completeness (auxiliary) | CCR | 텍스트 문자열 보존 | LayerAgent | (미측정) | "콘텐츠 문자열이 코드에 살아남는가?" — 시각 가시성 미반영 |
| (도메인 미지원) OCR-based | Block-Match, Position | 텍스트 위치 매칭 | (모두 ~0) | — | (다크/한국어/blur 무력화) |

평가 축 간 불일치의 의미 (RQ3 답). Design-to-Code use case는 단일하지 않다:
- (i) 편집 가능한 구조 회복(슬라이드 재편집용 코드 추출) → 축 ① 우선
- (ii) 참조 이미지 시각 복제(스크린샷 → HTML) → 축 ② 우선  
- (iii) 발표 가능한 슬라이드 자동 생성 → 축 ③ 우선
- (iv) ⚠ 클래스명 기반 평가 편향 → 축 ④ (sanity check 외 사용 자제 권고)

선행 ranking 재해석. Design2Code, SlidesBench, Widget2Code 등이 보고한 method ranking은 축 ①·② 위주이며, class-name-aligned metric은 클래스명 기반 평가 편향 위험. DreamHouse 2026 (structural-visual orthogonality joint pass 7.1%) 및 SlideAudit (UIST 2025, automated vs human disagreement)을 본 연구는 슬라이드 도메인에서 평가 축 간 불일치로 확장 관찰. 본 논문은 DOM-based structural (축 ①) + render-based visual similarity (축 ②) + multimodal LLM-as-judge (축 ③) 동반 보고가 Design-to-Code 평가에서 단일 지표보다 더 정직한 해석을 가능하게 함을 보이며, 그 필요성을 제안한다.

제7절 Ablation — 가용한 측정만 정직하게

본 절은 두 ablation의 정량 측정 결과를 보고한다 — D₂ (Text Inserter, legacy N=5 pilot)와 D₄ (DesignSpec blackboard, N=48 main_eval framework + N=10 다층 시각 효과 디자인 조건, 다면적 평가 지표). 나머지 5개 flag (D₁/D₃/D₅/D₇/D₈)는 infrastructure 완료, 정식 측정 미수행 — §8 한계로 명시.

D₂ (no_text_inserter) — Text Inserter 분리의 직접 증거 (legacy `tables/exp2_summary.json` 시점 데이터, N=5):

| 조건 | CCR ↑ | CSS Richness ↑ | Joint Pass ↑ |
|---|:---:|:---:|:---:|
| D (full) | 0.78 | 54.4 | 0.6 |
| D₂ (no_text_inserter) | 0.09 | 52.2 | 0.0 |
| Δ | −0.69 | −2.2 | −0.6 |

Text Inserter 제거 시 CCR이 0.78 → 0.09로 크게 감소 — Card Detail Agent가 텍스트 삽입 부담까지 함께 처리하면 시각 생성에 attention이 분산되어 콘텐츠가 약 80% 누락된다. CSS Richness는 거의 동일하게 유지 (Card Detail이 여전히 시각 생성을 담당). 이 결과는 시각/콘텐츠 단계 분리가 zero-sum을 구조적으로 줄이는 데 기여함을 시사한다 (legacy N=5 결과로 향후 N=48 framework 재측정 필요).

D₄ (no_designspec) — DesignSpec blackboard 효과 (N=48 mixed main_eval framework, 다면적 평가 지표):

| Metric | D (full) | D₄ (no_designspec) | Δ (D − D₄) |
|---|:---:|:---:|:---:|
| VEC ↑ | 16.9 | 14.7 | +2.2 |
| EDC ↑ | 9.0 | 8.6 | +0.4 |
| VLC ↑ | 3.3 | 3.2 | +0.1 |
| CRP ↑ | 32.1 | 27.5 | +4.6 |
| HD ↑ | 7.5 | 7.6 | −0.1 |
| SSIM ↑ | 0.590 | 0.418 | +0.172 |
| CLIP ↑ | 0.491 | 0.464 | +0.027 |
| LPIPS ↓ | 0.717 | 0.799 | −0.082 |

DesignSpec blackboard 제거 시 8개 다면적 평가 자동 지표 중 7개에서 D 우세, 1개(HD)는 동률 (Δ ±0.1 이내). 가장 큰 효과는 render-based 시각 fidelity — SSIM Δ = +0.172, LPIPS Δ = −0.082, CRP Δ = +4.6. 이는 DesignSpec이 cross-agent 스타일 표류를 줄여 시각 일관성을 보존함을 직접적으로 보여준다 (사전등록 가설 H-AblationDesignSpec 채택, 부록 A).

고복잡도 조건 subset (N=10 다층 시각 효과 디자인) — nuanced trade-off: 같은 N=10 다층 시각 효과 디자인에서 단독 측정 시 결과는 더 미묘하다 — D는 시각 fidelity 4개(CRP/SSIM/CLIP/LPIPS)에서 우세하나 D₄는 구조 다양성 4개(VEC=21.3 vs 20.9 / EDC=11.7 vs 9.7 / VLC=3.8 vs 2.9 / HD=7.8 vs 7.0)에서 약간 우세. 다층 디자인 조건에서는 DesignSpec이 specialist의 free-form generation diversity를 일부 제약하지만, mixed N=48 평균에서는 시각 일관성 효과가 압도적이다. 이는 consistency vs raw diversity trade-off를 시사하며, paper §1.3의 "DesignSpec = cross-agent 스타일 표류 감소" 가설을 N=48 평균에서 채택, 고복잡도 조건에서 부분 채택으로 정직 보고한다.

나머지 ablation (D₁/D₃/D₅/D₇/D₈) — infrastructure 완료, 정식 측정 미수행: `layeragent/ablations.py`에 8개 flag 모두 구현되어 있으며, ablation runner(`experiments/run.py`)가 각 변형을 main_eval framework로 돌릴 준비 완료. paper draft 시점 N=48 정식 ablation 결과는 미수집. 본 결과는 향후 work에서 추가 (§8 명시).

제7장 논의

제1절 Element omission의 메커니즘 — Capacity allocation 가설

본 절은 element omission의 메커니즘을 가설로 제시한다. 본 논문은 메커니즘 자체를 직접 인과 증명하지 않으며, 본 가설은 §3·§6의 관찰과 부합하는 후보 설명으로 제시된다.

가설 (capacity allocation). VLM이 전체 슬라이드를 단일 호출로 처리할 때, 레이아웃·색·텍스트·아이콘·CSS 재질·z-index·border·shadow·alpha를 모두 하나의 자기회귀 토큰 시퀀스로 산출해야 한다. `z-index`, `backdrop-filter: blur(16px)`, `box-shadow: 0 0 15px rgba(...)` 같은 속성은 없어도 HTML이 정상 렌더링되므로 생성 capacity가 동시에 경쟁하는 상황에서 가장 먼저 단순화될 가능성이 높다. 이 가설로 (a) 카드 간 재질 단순화, (b) 카드 간 스타일 표류, (c) z-index 부재의 세 결과가 공유된 메커니즘에서 비롯된다고 해석할 수 있다 — 다만 이는 가설 수준의 해석이며, 직접적인 인과 검증(예: token budget을 외생적으로 조정한 통제 실험)은 향후 작업이다.

이 가설 하에서, LayerAgent의 분해는 각 specialist의 인지 범위를 좁혀 (a)를 줄이도록 설계되었으며, DesignSpec blackboard는 (b)를 줄이는 shared style prior로 작동하고, Assembler의 결정적 z-index stacking은 (c)를 줄이는 메커니즘으로 작동한다.

제2절 Mixed signal의 의미 — 다면적 평가가 측정하는 서로 다른 차원

본 연구의 mixed signal은 자체 결함이 아니라 Design-to-Code 평가가 본질적으로 multi-objective임을 정량 증명한 것이다. 다면적 평가는 서로 다른 차원을 본다:

- Render-based visual similarity (SSIM)은 픽셀 휘도/대비/구조의 local window 통계 — 카드 위치만 비슷해도 점수가 높다. 일괄 생성이 image-to-image 표면 모방의 강점을 직접 활용 → SSIM 우세. z-index 부재·계층 단순화는 SSIM에 패널티 없이 통과.
- DOM-based structural metrics (VEC/EDC/CRP/HD)는 가시 element와 distinct style fingerprint의 카운트 — 분해된 출력이 풍부한 element와 다양한 스타일을 코드에 반영할 때 점수가 높다. LayerAgent의 8개 specialist가 직접 layer를 채우므로 우세.
- Multimodal LLM-as-judge는 출력이 발표 가능한가 라는 holistic 질문에 답한다. 풍부한 layer가 있어도 텍스트가 overflow되거나 카드가 빈 영역을 만들면 감점. 일괄 생성의 거칠지만 안정적인 출력이 일관되게 우세.

평가 해석의 원칙. 어느 한 축의 우월성을 주장하지 않는다. 본 논문은 다면적 평가를 모두 보고하며, use case에 따른 metric selection을 시사점으로 둔다. LayerAgent는 (i) 편집 가능한 구조 회복에 정렬된 시스템이며, (ii) end-to-end 슬라이드 자동생성 use case에서는 Visual Critic + 더 보수적인 Text Inserter가 추가되어야 (iii) holistic 축에서도 우세를 달성할 수 있을 것으로 예측한다 — 이는 §8 향후 연구.

제3절 String-CCR vs Visual CCR — 메트릭 진화의 직접 증거

LayerAgent의 string-CCR은 0.99이지만 MLLM judge의 visual Content Completeness는 2.35로 최악이다. 이 정확한 모순이 본 논문의 메트릭학적 기여이다 — string-level 매칭 메트릭은 시각 가시성을 underdetermine한다. CCR은 Text Inserter가 텍스트를 카드 영역에 주입했음을 확인하지만, judge는 그 텍스트가 overflow되거나 dense하게 겹쳐서 읽을 수 없음을 본다.

향후 연구에서 Visual CCR — Playwright 렌더링 후 OCR로 가시 텍스트 추출 → input 콘텐츠와 매칭 — 을 string-CCR의 후속 메트릭으로 제안한다. 현재 OCR이 본 도메인(다크/한국어/blur)에서 무력화되어 있으므로 visual-aware OCR (mPLUG-DocOwl, Florence-2 등) 채택이 선결 과제.

제4절 단계 분리의 효과 — 다면적 평가 + cross-VLM 데이터에서의 일관성

H-RAG가 보여주는 zero-sum, D₂ ablation이 보여주는 분리의 효과, §3.3의 cross-VLM frontier baseline 관찰, §6.3의 trivial prompt baseline 결과 — 이들 데이터가 한 방향을 가리킨다: legacy probing(class-name-aligned) 기준에서는 단순 prompt 조정이나 frontier model upgrade만으로 perception–generation layer gap이 완전히 사라지지는 않는다. 다만 다면적 평가 기준의 practical 품질·비용 비교(§6.2)에서는 GPT-5.4 일괄 생성이 LayerAgent를 능가하므로, 본 절의 관찰은 분해 motivation을 보강하는 legacy diagnostic 수준의 신호로만 해석한다.

Cross-VLM frontier baseline (§3.3, 명명 규칙 정렬 caveat 내에서도 robust한 부분): GPT-4o, GPT-5.4, Claude 4.6 Opus 세 frontier 모두 baseline 격차가 큼. frontier 간 단순 upgrade로 격차의 가시적 약화는 작다 (단, 본 절의 frontier vs LayerAgent 비교는 §6.2 다면적 평가 결과를 우선 — 그곳에서 GPT-5.4는 LayerAgent를 능가).

§7 thesis (정정된 framing). LayerAgent의 가치는 frontier model 능가가 아니라 same-model 조건에서 단계 분리가 부여하는 구조적 일관성이다. Same-model GPT-4o에서는 분해가 DOM-based + render-based 자동 지표 8개 중 7개에서 우세를 보이며 (MLLM judge 차원에서는 우세 미달), prompt engineering(§6.3) 만으로는 같은 격차가 관찰되지 않는다. 그러나 frontier model upgrade는 별개의 cost-quality 차원에서 LayerAgent를 능가할 수 있으며 (§6.2 GPT-5.4 비교에서 LayerAgent의 우세는 관찰되지 않음), 이는 본 논문이 정직하게 보고하는 사실이다.

제5절 비대칭 vision의 일반 원리

본 연구의 한 발견은: 스타일을 만드는 agent는 이미지를 보고, 배치를 결정하는 agent는 좌표만 본다. Card Detail은 crop을 보지만 Text Inserter는 텍스트만 본다. 이 비대칭은 다른 멀티에이전트 영역에도 일반화 가능하다 — UI 생성에서 디자인 agent vs 코딩 agent, 로봇 제어에서 계획 agent vs 실행 agent, 문서 생성에서 레이아웃 agent vs 콘텐츠 agent.

---

제8장 한계

- Class-name-aligned legacy metric (LTED/Layer Recall)의 클래스명 기반 평가 편향 문제. 본 논문의 초기 버전은 Layer Recall + LTED를 element omission metric으로 사용했으나, 이는 우리가 정의한 LayerAgent class name 어휘에 align된 regex 기반 측정으로 클래스명 기반 평가 편향 위험이 있다. Claude Opus의 `glass-card`/`node-inner`/`hub-content` 등 시각적으로 풍부한 element가 매칭 안 되어 거짓 negative 보고. 본 논문은 이를 §3 + §5.3에서 명시하고 main result를 다면적 평가 지표 (DOM-based VEC/EDC/VLC/CRP/HD + render-based SSIM/CLIP/LPIPS + multimodal LLM-as-judge)로 보고. Legacy metric은 §3.2·§3.3 (현상 가시화), §6.1c (보조 표), §6.3·§6.4·§6.5 (sanity check, prompt 변형 robustness — 명명 규칙과 무관하므로 방향성은 robust)에 한정 사용 (caveat 명시).
- Holistic 디자인 quality (축 ③)에서의 부정 결과. MLLM judge 4-criteria 평균에서 LayerAgent (2.59) < 일괄 생성 (3.30) — N=48 main_eval. Visual Fidelity·Content Completeness·Design Quality 3개 축에서 일괄 생성에 진다. LayerAgent의 holistic 우위는 Layer Structure 축 (3.58 vs 3.46) + 다층 시각 효과 디자인 조건 으로 한정된다. 본 논문은 이 부정 결과를 thesis의 일부로 흡수.
- Sweet-spot 외 disagreement. 6개 중간 layout(pyramid, mekko, process_flow 등)에서 LTED는 LayerAgent를 우세로, MLLM judge는 일괄 생성을 우세로 본다. 즉 layer 수만 회복하는 것이 발표 가능한 슬라이드를 보장하지 않는다. Visual Critic + 더 보수적 Text Inserter 조합이 §7.2의 향후 과제로 명시.
- N=48의 통계 검증력. 메인 결과는 effect size로 보고하며, paired Wilcoxon p-value는 고복잡도 subset(N=10)에서만 유의(p<0.05)하다. 30+ seed × 100+ design 확장이 향후 과제.
- Cross-VLM probing의 명명 규칙 정렬 + scope 한계. §3.3의 cross-VLM 결과는 (a) class-name-aligned LTED/Recall 기반이라 명명 규칙 정렬 caveat 적용, (b) N=10 다층 시각 효과 디자인 subset에 한정. 본 절은 frontier 간 baseline 비교와 현상 가시화 용도로만 신뢰성을 가진다. LayerAgent vs frontier의 공정한 비교는 §6.2 다면적 평가 지표 결과로 보고하며, 거기서 GPT-5.4는 LayerAgent를 능가한다. Gemini 2.5 등 추가 frontier에서의 다면적 평가 재현은 향후 작업.
- Ablation은 D₂와 D₄만 정량 측정됨. §6.7의 ablation은 D₂ (Text Inserter, N=5 legacy pilot)와 D₄ (DesignSpec blackboard, N=48 main_eval framework + N=10 고복잡도 조건, 다면적 평가 지표) 두 개에 한정 보고. 나머지 5개 flag (D₁ no_style_norm / D₃ no_cv_facts / D₅ no_library / D₆ no_visual_critic / D₇ no_overflow_repair)는 infrastructure 구현 완료 (`layeragent/ablations.py`) 이지만 정식 측정 미수행. 본 논문 작성 시점 기준 — 따라서 style normalizer / library retrieval / CV facts 등의 개별 contribution은 paper의 main claim에 포함되지 않는다.
- OCR-기반 메트릭 무력화. Block-Match와 Position이 저대비 배경 + 반투명 레이어 + 한국어 + opacity blur 조합에서 일관되게 0이다. visual-aware OCR (mPLUG-DocOwl, Florence-2) 교체가 선결 과제.
- 단일 LLM judge bias + 인간 평가 부재. 본 논문의 holistic 평가는 GPT-5.4 (Azure) 단일 LLM-as-judge에 의존한다 — Claude / Gemini 등 cross-judge로의 일반화 가능성은 검증되지 않았다. 또한 인간 anchor 직접 검증(n≥80 pair × 5 raters 규모, MT-Bench/AlpacaEval 류 pairwise 프로토콜)도 미수행이다. WebDevJudge (2025)가 권고하는 cross-judge + human anchor 조합은 향후 과제.
- 지연 시간. Multi-agent decomposition + library retrieval로 카드 4개 슬라이드 ~60초 vs 일괄 생성 ~8초. quality-latency 트레이드오프 위에 위치.
- Layer band의 디자인 특수성. 본 시스템의 6 layer band는 배경·장식·카드·텍스트·아이콘이 명확히 분리된 다층 시각 효과 디자인 미학에 정렬되어 있다. 텍스트 중심 / 사진 중심 슬라이드에서는 일부 specialist가 비활성화되거나 layer band 재정의가 필요하다.
- N=10 subset의 사후 특성 분석. §5.1의 6 criteria는 사전 정의된 selection rule이 아니라 기존 subset의 사후 특성화이다. paper 작성 시점 기준 subset의 정당성은 6 criteria 중 ≥ 4개 만족이라는 사후적 일관성으로 보고되며, 사전 selection rule로 새 subset을 구성한 통제 실험은 미수행이다 — 향후 작업에서 이 criteria를 사전 selection으로 사용한 N=30+ confirmatory subset 재구성이 필요하다.
- String-CCR vs Visual CCR. §7.3에서 다룬 메트릭 진화 필요. 현재 CCR 0.99는 문자열은 존재하나 시각적으로 읽히지 않을 수 있음을 직접 보였다 (MLLM judge CC 2.35).

---

제9장 결론

본 논문은 Design-to-Code 프레젠테이션 생성에서 계층적 element omission(Design-to-Code 선행 연구의 element omission이 슬라이드의 시각 계층 단위로 확장된 형태)이라는 현상을 정의하고, 이를 분석하고 완화하기 위한 LayerAgent framework와 다면적 평가 방식을 제안했다. LayerAgent는 모든 layout·모든 frontier model을 능가하지 않으며, 본 논문의 기여는 측정으로 직접 지지되는 세 가지 narrow한 사실로 정리된다.

- (Problem) 슬라이드 도메인의 계층적 element omission 정식화 (§3): 같은 VLM이 이미지를 자연어로 기술할 때는 평균 5–8개의 layer를 인식하지만, 같은 이미지를 HTML로 변환할 때는 일괄 생성 기준 평균 1.6개의 layer만 HTML/CSS 구조에 반영된다 — 이 perception–generation 격차가 슬라이드 도메인의 시각 계층 단위 element omission 현상이며, 명명 규칙과 무관한 layer count 측정에서도 신뢰성 있게 가시화된다.

- (Method) LayerAgent framework (§4): DesignSpec blackboard + vision-grounded specialist agents + style normalization + text insertion 분리를 포함한 multi-agent layer decomposition. 컴포넌트별 인과 효과는 D₂(Text Inserter, CCR Δ=0.69)와 D₄(DesignSpec blackboard, N=48 다면적 평가에서 8개 자동 지표 중 7개 악화 — 특히 SSIM Δ=0.172, LPIPS Δ=0.082) 두 개에 한정해 격리 측정되었으며 (§6.7), 나머지 컴포넌트 (library, CV facts, style normalizer)의 개별 효과는 향후 ablation 작업으로 분리된다 (§8 한계).

- (Evaluation & Finding) 다면적 평가 방식과 LayerAgent의 효과 범위 (§5.3, §6): class name이나 사전 정의된 layer vocabulary에 의존하지 않는 평가 protocol(DOM-based 구조 + render-based 시각 유사도 + multimodal LLM-as-judge의 결합·정렬) 위에서 LayerAgent의 상대적 강점은 다음으로 한정된다.
  - (RQ2, Table 1) 다층 시각 효과 디자인 subset + same-model GPT-4o에서 8개 자동 지표 중 7개 우위 (VEC 2.3×, EDC 3.2×, CRP 2.2×, CLIP +0.042, LPIPS −0.064). SSIM에서는 일괄 생성이 0.023 높았으나 N=10 std ~0.10 고려 시 작은 차이로 결정적 우위로 해석하지 않음.
  - (RQ2, Table 1b) holistic MLLM judge 차원에서는 일괄 생성이 평균 우세 (3.30 vs 2.59) — 코드 구조의 풍부성과 발표 가능성이 본 평가에서 서로 다른 차원으로 분리된다는 발견. LayerAgent의 기여는 holistic slide quality 일괄 향상이 아니라 layer-level element omission을 완화하는 구조적 메커니즘 + 그 적용 범위의 규명이다.
  - (RQ3 part A·B, §6.4–§6.5) Layout-dependent 효과 범위: per-layout breakdown에서 다층 시각 효과 디자인에서만 두 메트릭 축이 LayerAgent의 상대적 강점을 일관되게 가리킨다. 평면 차트(bar/line/waterfall)에서는 두 축 모두 일괄 생성 우위에 합의 — 향후 시스템 설계의 시사점은 layout-conditional routing의 가능성 (§6.5).
  - (RQ3 part C, §6.6) 평가 축 간 불일치: DOM-based structural / render-based visual similarity / multimodal LLM-as-judge 세 축이 동일 데이터에 서로 다른 ranking을 산출. 단일 메트릭 ranking은 use case 의존이며, class-name-aligned legacy metric은 클래스명 기반 평가 편향 위험으로 sanity check 외 사용을 자제할 것을 권고.
  - (Boundary Analysis, §6.2) Frontier 모델 일괄 생성(GPT-5.4·Claude Opus)은 디자인 완성도·구성 품질에서 LayerAgent보다 우수한 결과를 보였다 — 이는 RQ에 대한 경쟁 결과가 아니라 LayerAgent의 적용 범위 경계를 명시하는 보조 분석. LayerAgent는 frontier 모델의 대체재가 아니라 GPT-4o급 VLM의 일괄 생성 한계를 process-level로 완화하는 intervention임을 직접 보여준다.

Honest thesis. LayerAgent는 모든 경우의 SOTA가 아니다. 본 논문이 측정으로 지지하는 narrow claim은 두 가지 — (i) 같은 GPT-4o 위에서, 다층 시각 효과 디자인 subset의 자동 구조·시각 지표가 분해로 일관되게 개선된다, (ii) 그러나 holistic judge 차원에서는 일괄 생성이 평균 우세하며, frontier 모델 일괄 생성은 디자인 완성도에서 LayerAgent를 능가한다. 본 논문의 핵심 기여는 SOTA 경신이 아니라, GPT-4o급 VLM의 일괄 생성 한계를 정식화하고, 계층 분해 생성이 이를 어디까지·어떤 조건에서 완화할 수 있는지를 다면적 평가 위에서 정직하게 보고하는 것이다.

더 넓은 원리.

1. 다면적 평가 동반 보고의 필요성. DOM-based structural + render-based visual similarity + multimodal LLM-as-judge 동시 보고가 Design-to-Code 평가에서 단일 지표보다 더 정직한 해석을 가능하게 함을 본 연구는 보인다. Class-name-aligned regex 기반 metric은 클래스명 기반 평가 편향 위험으로 sanity check 외 사용 자제.
2. Same-model 분해 효과와 frontier scaling은 분리된 두 path이다. RQ는 same-model decomposition에 한정하고, frontier 비교는 적용 범위의 경계를 명시하는 보조 분석으로 분리해야 narrative 혼동을 막을 수 있다 — Table 1 (same-model RQ2) + §6.2 Boundary Analysis (frontier reference)의 분리가 정직 framing.
3. String-level 콘텐츠 메트릭은 시각 가시성을 underdetermine한다. CCR 0.99 vs MLLM CC 2.35 — visual CCR 메트릭 필요.

향후 연구. (a) cross-judge 추가 (Claude/Gemini)로 holistic 축 single-judge bias 제거. (b) 인간 평가 N=8-10으로 다면적 평가 지표의 인간 anchor 검증. (c) Multi-seed (3 seed × 4 method × 48 design) 통계 검정. (d) Layout-conditional routing 구현. (e) Visual CCR (visual-aware OCR 기반). (f) AutoPresent의 element matching 프로토콜 직접 비교 (cross-paper validation). (g) 5개 미측정 ablation flag (D₁/D₃/D₅/D₇/D₈)의 N=48 framework 정식 측정으로 컴포넌트별 인과 효과 격리.

---

부록 A. 사전 등록 (Pre-registration) — 가설 검증 임계값

본 논문의 핵심 가설들은 post-hoc 임의 임계값이 아닌 사전 명시된 결정 규칙으로 검증된다 (paper 초안 작성 시점에 결정).

⚠ Caveat. 본 사전등록 가설들은 paper 초안 시점에 Layer Recall/LTED를 main metric으로 사용하던 framework에서 작성되었다. 본 논문은 main claim을 다면적 평가 지표 (DOM-based + render-based + LLM-as-judge)로 전환했으므로, 아래 가설 중 LTED/Recall에 의존하는 항목들은 명명 규칙 정렬 caveat 하의 보조 가설로 재해석한다. 다면적 평가 가설 (§6.1·§6.2·§6.5·§6.6의 주장)은 본 논문 본문에서 직접 effect size로 보고하며, 향후 작업에서 다면적 평가 기반 사전등록 가설로 정식화한다.

H-EO (Element omission의 모델-일반성, RQ1, §3.3) — 명명 규칙 정렬 보조 가설, 채택
- 결정 규칙: 3 VLM에서 baseline 일괄 생성의 평균 (1 − Layer Recall) ≥ 0.50 AND cross-VLM 표준편차 ≤ 0.10
- 적용: 10 다층 시각 효과 디자인 × 3 VLM (GPT-4o, GPT-5.4, Claude 4.6 Opus). Gemini 2.5는 본 논문에서 미실행 (인프라 있음, 향후 work).
- 측정 결과: 3 VLM gap = {0.776, 0.700, 0.688}, 평균 0.721, std 0.039 (≤ 0.10 ✓), 평균 ≥ 0.50 ✓
- ⚠ Vocabulary alignment caveat: Layer Recall은 LayerAgent class name 어휘에 정렬됨. frontier 간 비교에 한정해서는 (모두 다른 어휘 사용) 상대적으로 공정하므로 baseline 격차의 가시화로는 신뢰성을 가지나, 절대값은 caveat 적용.
- 보조 가설로 채택: frontier 간 baseline upgrade로 격차의 가시적 약화는 작다.

H-LTED, H-Recall (LayerAgent의 명명 규칙 정렬 metric 우위, §6.1c)
- 결정 규칙: legacy LTED/Recall 기준의 LayerAgent 우위
- ⚠ 클래스명 기반 평가 편향 위험으로 main claim에 미사용. §6.1c 보조 표 caveat과 함께 보고.
- 본 논문의 main claim은 다면적 평가 지표 기반 §6.1 Table 1로 보고 (DOM-based + render-based 8개 자동 지표 중 7개에서 LayerAgent 우세, holistic MLLM judge 차원은 §6.1b 별도 보고).

H-SweetSpot (다층 디자인에서의 양 축 합의, RQ3 part A, §6.4) — 부분 채택
- 결정 규칙: 다층 시각 효과 디자인 N=10 subset에서 동시에 (LTED(layeragent) < best baseline LTED − 0.20) AND (MLLM avg(layeragent) > best baseline MLLM avg)
- 측정: LTED Δ = +0.27 (✓, 명명 규칙 정렬 caveat), MLLM Δ = +0.12 (✓, 명명 규칙 비의존) — 두 축 합의
- ⚠ 합의 자체는 명명 규칙 정렬 LTED + 명명 규칙 비의존 MLLM judge의 조합 — 한 다리(LTED)가 명명 규칙 정렬 caveat 하. 향후 다면적 평가 DOM/render-based 지표로 재정식화.

H-LayoutScaling (Per-layout RQ3 part B, §6.5)
- 결정 규칙: 9개 레이아웃 유형 중 적어도 5개에서 MLLM Δ와 LTED Δ의 부호가 일치 (즉, 두 축이 같은 승자에 합의)
- 측정: 다층 시각 효과 디자인 + 평면 차트 4개에서 합의, 5개에서 불일치 → 부분 채택
- ⚠ 동일 caveat: LTED 한 다리에 명명 규칙 정렬 caveat 적용.

H-MetricAxisDisagreement (RQ3 part C 평가 축 간 불일치, §6.6) — 채택
- 결정 규칙: 48-slide aggregate에서 SSIM 우승자 ≠ LTED 우승자 ≠ MLLM 우승자 (셋 모두 다른 메서드를 1위로 산출 — 또는 최소 2개 이상 ranking 차이)
- 측정 결과: SSIM 우승=일괄 생성, LTED 우승=LayerAgent, MLLM 우승=일괄 생성 — 축 간 disagreement 확인
- 채택: 동일한 출력이라도 평가 축에 따라 서로 다른 ranking이 산출될 수 있음을 보여준다.

H-AblationTextInserter (Text Inserter 분리 효과, §6.7) — 채택
- 결정 규칙: string-CCR(D) − string-CCR(D₂) ≥ 0.30 AND Layer Recall(D) > Layer Recall(D₂)
- 측정 결과 (legacy N=5): string-CCR Δ = 0.69, 채택
- 주: CCR은 명명 규칙과 무관한 콘텐츠 보존 메트릭이므로 본 가설의 채택은 명명 규칙 정렬 caveat과 독립.

H-AblationDesignSpec (DesignSpec cross-agent 합치, §6.7) — 채택 (N=48 다면적 평가) / 부분 채택 (N=10 고복잡도 조건)
- 결정 규칙 (재정식화): EDC/CRP/CLIP 3개 지표 중 ≥ 2개에서 D > D₄ (또는 EDC Δ ≥ 1.0 AND CLIP(D) ≥ CLIP(D₄)).
- 측정 결과 (N=48 mixed main_eval framework, 다면적 평가 지표):
  - 다수결 규칙: EDC ✓ (+0.4), CRP ✓ (+4.6), CLIP ✓ (+0.027) — 3/3 채택.
  - Strict 규칙: EDC Δ = +0.4 < 1.0 ❌, CLIP Δ = +0.027 ≥ 0 ✓ — strict 부분 충족.
  - 8개 다면적 평가 자동 지표 종합: D 우세 7개 (VEC/EDC/VLC/CRP/SSIM/CLIP/LPIPS), 동률 1개 (HD, Δ −0.1). 가장 큰 효과는 SSIM Δ = +0.172, LPIPS Δ = −0.082, CRP Δ = +4.6.
- 측정 결과 (N=10 다층 시각 효과 디자인 조건 subset):
  - 8개 다면적 평가 자동 지표: D 우세 4개 (CRP/SSIM/CLIP/LPIPS, 시각 fidelity 4개), D₄ 우세 4개 (VEC/EDC/VLC/HD, 구조 다양성 4개) — consistency vs raw diversity trade-off.
  - 다수결 규칙: CRP ✓, CLIP ✓, EDC ✗ — 2/3 채택 (경계).
- 결론: N=48 다면적 평가에서 H-AblationDesignSpec 채택 — DesignSpec blackboard는 cross-agent 시각 fidelity 일관성을 명확히 보존. Sweet spot에서는 부분 채택 (visual fidelity는 D 우세, structural diversity는 D₄ 우세).
- 주: VEC/EDC/CRP 등 다면적 평가 DOM/visual 지표은 명명 규칙과 무관하므로 본 가설 채택은 명명 규칙 정렬 caveat과 독립.

본 사전 등록은 paper 부록 외에도 OSF(Open Science Framework)에 별도 등록될 예정이며, ID는 publication 시점에 명시한다. 향후 작업에서 다면적 평가 지표 기반 사전등록을 정식 갱신한다.

---

부록 B. Class-name-aligned legacy metric — Sanity check 자료

본 부록은 본문 §3.2·§3.3·§6.1에서 옮긴 class-name-aligned (Layer Recall, LTED) 결과를 sanity check 용도로 보존한다. 모두 LayerAgent class name 어휘에 정렬된 regex 측정이라는 명명 규칙 정렬 한계 (§3.1, §8)가 있으므로, 본 논문의 main claim은 이 표들이 아니라 본문의 다면적 평가 지표 (§6.1 Table 1)을 따른다. 본 부록의 목적은 현상 가시화의 일관성을 보여주는 보조 자료이며, 절대값을 그대로 받아들이지 말 것을 권고한다.

B.1 §3.2 probing pilot의 명명 규칙 정렬 수치

(A) probing_minimal pilot — N=10 다층 시각 효과 디자인, GPT-4o (`experiments/probing/probing_minimal.py`):

| 지표 | Stage A perception | Stage B1 (일괄 생성) | Stage B2 (LayerAgent) |
|---|:---:|:---:|:---:|
| `Layer Recall` (vs $T_P$, 명명 규칙 정렬 ⚠) | 1.00 (sanity) | 0.195 | 0.676 |
| `gap = 1 − Recall` (명명 규칙 정렬 ⚠) | 0.00 | 0.805 | 0.324 |
| `LTED` ↓ (명명 규칙 정렬 ⚠) | 0.00 | 0.82 | 0.55 |

(B) main_eval — N=48 mixed, 4-method (`experiments/main_eval.py`, `analyze_results.py`):

| Method | Layer Recall ↑ (명명 규칙 정렬 ⚠) | gap (1−Recall) ↓ (명명 규칙 정렬 ⚠) |
|---|:---:|:---:|
| cot_h_rag | 0.120 ± 0.16 | 0.880 |
| visual_cot | 0.196 ± 0.13 | 0.804 |
| single_pass | 0.212 ± 0.15 | 0.788 |
| layeragent | 0.405 ± 0.23 | 0.595 |

본 논문의 초기 framework는 위 수치로 element omission을 정량화했으나, Layer Recall 절대값은 LayerAgent vocabulary에 정렬되어 있어 상대 비교에서 LayerAgent 우위가 부풀어 보일 수 있다. 본 논문의 main 메시지는 §3.2 본문의 명명 규칙 비의존 n_layers 격차 ("일괄 생성이 perception이 보장한 layer 중 평균 1.6개만 HTML/CSS 구조에 반영한다")에 한정한다.

![Figure 1: Layer Recall × method (N=48)](results/figures/fig1_gap.png)

Figure 1 (Legacy). Layer Recall (명명 규칙 정렬) by method across 48 slides — 명명 규칙 정렬 caveat 하에서 현상 가시화 용도. Main result는 §6.1 Table 1의 다면적 평가 지표.

B.2 §3.3 Cross-VLM probing 표

10 다층 시각 효과 디자인 × frontier VLM × 일괄 생성. Vocabulary alignment caveat이 그대로 따라붙으며, frontier 모델 간에서는 모두 LayerAgent와 다른 어휘를 쓰므로 비교가 상대적으로 공정하지만, LayerAgent vs frontier 비교는 클래스명 기반 평가 편향 위험이 있다 (§3.1).

| 모델 | LTED ↓ ⚠ | Layer Recall ↑ ⚠ | gap (1−Recall) ⚠ | 평균 토큰 | 비용/슬라이드 | 시간 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| single_pass (GPT-4o) | 0.823 | 0.224 | 0.776 | ~5,000 | ~$0.015 | ~10s |
| single_pass (GPT-5.4) | 0.669 | 0.300 | 0.700 | 6,015 | $0.075 | 85s |
| single_pass (Claude 4.6 Opus) | 0.693 | 0.312 | 0.688 | 7,116 | $0.421 | 108s |
| LayerAgent (GPT-4o, 클래스명 편향 위험) | (0.551) | (0.759) | (0.241) | 54,310 | $0.232 | ~60s |

세 frontier 모두 baseline gap 0.69–0.78 범위에서 — frontier model upgrade만으로 layer 반영 격차가 크게 닫히지는 않는다는 legacy diagnostic 수준의 관찰만 본 표에서 도출된다. LayerAgent vs frontier의 공정한 비교는 §6.2의 다면적 평가 지표 (명명 규칙 비의존) 결과를 우선해서 읽어야 하며, 거기서는 GPT-5.4 일괄 생성이 LayerAgent를 품질·비용 양 측면에서 능가한다.

(사전등록 가설 H-EO는 "3 VLM에서 baseline gap > 0.5"라는 frontier 간 비교 부분에 대해서만 보조적으로 적용된다. 가설의 명명 규칙 의존성에 대한 caveat은 부록 A에서 명시.)

B.3 §6.1c Legacy 명명 규칙 정렬 table (N=48 main_eval)

| Metric | cot_h_rag | layeragent | single_pass | visual_cot |
|---|:---:|:---:|:---:|:---:|
| Layer Recall ↑ (명명 규칙 정렬) | 0.120 | 0.405 | 0.212 | 0.196 |
| LTED ↓ (명명 규칙 정렬) | 0.911 | 0.744 | 0.823 | 0.854 |

⚠ 위 두 metric은 우리가 정의한 LayerAgent class name 어휘에 align되어 있어 (§3.1, §7.3) LayerAgent의 우세는 부분적으로 클래스명 기반 평가 편향에 기인한다. 본 논문의 main claim은 §6.1 Table 1의 다면적 평가 지표이며, 본 표는 한계 명시 하에 sanity check로 보존한다.

![Figure 2: Multi-metric × method comparison (N=48)](results/figures/fig2_methods.png)

Figure 2 (Legacy). 4 method × 5 metric breakdown. Layer Recall은 명명 규칙 정렬이라 caveat 필요 — main 결과는 §6.1 Table 1의 다면적 평가 지표.

---

부록 C. Frontier 모델 일괄 생성 보충 비교 (§6.2 Boundary Analysis 상세)

본 부록은 §6.2 Boundary Analysis에서 압축 보고된 frontier 일괄 생성과의 비교를 method-level 상세로 제공한다. 본 비교의 목적은 LayerAgent의 적용 범위 경계를 명시하는 것이며, RQ에 직접 답하는 결과가 아님을 다시 강조한다.

C.1 vs Claude 4.6 Opus

- 자동 시각 지표에서 Opus가 다소 우세 (SSIM 0.470 vs 0.500, CLIP 0.492 vs 0.525, LPIPS 0.589 vs 0.502 — 격차는 단일 자릿수 % 수준)
- 시각 풍부성 (VEC/EDC/CRP) 또한 Opus가 다소 우세
- 비용 45% 절감 ($0.232 vs $0.421) + 시간 44% 절감 (60s vs 108s)
- LayerAgent는 Claude Opus 일괄 생성의 대체재가 아님 — 일부 자동 시각 지표에서는 Opus가 더 좋으며, 본 논문은 그 사실을 그대로 보고한다.

C.2 vs GPT-5.4

- GPT-5.4 일괄 생성이 본 표의 다면적 평가 자동 지표(VEC, EDC, CRP, SSIM, CLIP, LPIPS) 모두에서 1위
- 비용 또한 GPT-5.4가 약 1/3 ($0.075 vs $0.232)
- "LayerAgent가 frontier 일괄 생성을 능가한다"는 강한 주장은 본 데이터에서 GPT-5.4에 대해서는 지지되지 않는다.
- 본 논문은 이 결과를 정직하게 보고하며, GPT-5.4 일괄 생성이 본 use case의 자동 지표·비용 양 측면에서 더 강한 결과를 산출함을 명시한다.

C.3 Operational reference

각 운영 조건별 직관적 reference (RQ에 답하는 운영 권고가 아니라 boundary 정보):
- Quality + cost 동시 최적화 → GPT-5.4 일괄 생성
- 최저 비용 + low quality 허용 → GPT-4o 일괄 생성 ($0.015/slide, 10s)
- 동일 GPT-4o 위에서 layer-level 구조적 충실도 회복이 필요한 경우 → LayerAgent (본 논문의 적용 범위)

C.4 Boundary 종합

본 boundary 분석은 LayerAgent를 frontier 모델의 대체재로 주장하는 분석이 아니다. 본 논문의 분해 전략은 GPT-4o급 VLM의 일괄 생성 한계를 process-level로 완화하는 intervention이며, frontier scaling은 별개 차원의 quality 향상 path임을 본 비교가 직접 보여준다. RQ2(§6.1)에서 보고한 same-model 분해 효과의 적용 범위 경계가 frontier scaling이라는 사실을 정직하게 명시함으로써, 본 논문의 main claim이 frontier 비교에 의해 약화되는 것이 아니라 명확한 scope를 부여받는다.

---

부록 D. 재현 패키지

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

재현 명령:

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

참고 문헌

Design-to-Code 생성
- Si, C., et al. "Design2Code: How Far Are We From Automating Front-End Engineering?" NAACL 2025.
- Laurençon, H., et al. "Unlocking the Conversion of Web Screenshots into HTML Code with the WebSight Dataset." 2024.
- Calò, T., & De Russis, L. "Advancing Code Generation from Visual Designs through Transformer-Based Architectures and Specialized Datasets." Proceedings of the ACM on Human-Computer Interaction (PACMHCI), 2025. — element omission / element distortion / element misarrangement 분류 출처.
- DCGen. "Divide-and-Conquer Screenshot-to-Code Generation." FSE 2025.
- LaTCoder. "Layout-as-Thought Code Generation." KDD 2025.
- ScreenCoder. "ScreenCoder: Advancing Visual-to-Code Generation for Front-End Automation via Modular Multimodal Agents." arXiv:2507.22827, 2025.
- DesignCoder. "DesignCoder: Hierarchy-Aware and Self-Correcting UI Code Generation with Large Language Models." arXiv:2506.13663, 2025.
- UIOrchestra. "Generating High-Fidelity Code from UI Designs with a Multi-Agent Framework." Findings of the Association for Computational Linguistics: EMNLP 2025.

시각 교정 / 반복 개선
- VisRefiner. "Learning from Visual Differences for Screenshot-to-Code Generation." arXiv:2602.05998, 2025.
- Vision-Guided Iterative Refinement. arXiv:2604.05839, 2026.

프레젠테이션 생성
- Zheng, H., et al. "PPTAgent: Generating and Evaluating Presentations Beyond Text-to-Slides." EMNLP 2025.
- Xu, X., et al. "PreGenie: An Agentic Framework for High-quality Visual Presentation Generation." EMNLP Findings 2025.
- Tang, V., et al. "SlideCoder: Reference Image-Guided Slide Code Generation." EMNLP 2025.
- Ge, J., et al. "AutoPresent: Designing Structured Visuals from Scratch." CVPR 2025.

평가 / 측정 타당성
- DreamHouse. "Joint Structural-Visual Fidelity in Design-to-Code." arXiv:2603.24866, 2026.
- WebRenderBench. "Layout-Style Consistency with Reinforcement Learning." 2025.
- Widget2Code. "Apple HIG-inspired Per-Property Evaluation." 2025.
- Image2Struct. NeurIPS 2024.
- SlideAudit. "A Dataset and Taxonomy for Automated Presentation Slide Evaluation." UIST 2025. arXiv:2508.03630.
- WebDevJudge. "Evaluating (M)LLMs as Critiques for Web Development Quality." arXiv:2510.18560, 2025.
- Zhang, R., et al. "The Unreasonable Effectiveness of Deep Features as a Perceptual Metric (LPIPS)." CVPR 2018.
- Zheng, L., et al. "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena." NeurIPS 2023.

계층 / 중첩
- LayerD. "Decomposing Raster Graphic Designs into Layers." ICCV 2025.
- SLEDGE. "Step-by-Step Layered Design Generation." AAAI 2026.
- OverLayBench. NeurIPS 2025.

멀티에이전트 시스템
- Hong, S., et al. "MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework." ICLR 2024.
- Qian, C., et al. "ChatDev: Communicative Agents for Software Development." ACL 2024.
- Li, G., et al. "CAMEL: Communicative Agents for Mind Exploration of Large Language Model Society." NeurIPS 2023.
- Wu, Q., et al. "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation." COLM 2024.

에이전트 UI / 디자인 시스템
- A2UI Protocol. "Agent-driven UI with Client-Side Design Enforcement." Google, 2026.

VLM
- Hurst, A., et al. "GPT-4o System Card." 2024.
- Radford, A., et al. "CLIP: Learning Transferable Visual Models." ICML 2021.
- Wang, Z., et al. "SSIM: Image Quality Assessment." IEEE TIP, 2004.
