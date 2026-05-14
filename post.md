# 포스터 초안 (post.md) — 학위 발표 세로 포스터 1장

**대상**: 고려대 학위 포스터 양식 (예시 사진의 김소연·Clustering 포스터와 동일 양식, 세로 배너 타입)
**레이아웃**: 2-column, 상단 빨간 헤더 (고려대 로고), 섹션 헤더 박스/음영 강조
**활용 자료 총 5개**: 그림 3 + 표 2

---

## 상단 헤더 (빨간색 배경, 흰색 글자)

좌측 고려대 로고 + 중앙 정렬:

> # LayerAgent: 프레젠테이션 생성을 위한 멀티에이전트 프레임워크
> ### — 디자인 이미지의 계층 구조 인식을 통한 프레젠테이션 코드 생성 —
>
> **정일균** | 지도교수: **김현철** 교수
> 고려대학교 인공지능융합학과 (Department of Artificial Intelligence Convergence, Korea University)

---

## 활용 자료 인덱스 (paper 원문 번호)

| 종류 | paper # | 파일 / 내용 | 사용 섹션 | 출처 절 |
|---|---|---|---|---|
| 표 | **표 11** | Cross-VLM 프로빙 (3 최첨단 격차) | 좌·서론 | 부록 B.2 |
| 그림 | **그림 1** | `results/figures/layeragent_architecture.png` (아키텍처) | 좌·연구방법 | 3.1절 |
| 표 | **표 4** | GPT-5.4 4 기준 MLLM-as-a-judge (N=50) | 우·결과 부제목 1 | 5.2절 |
| 그림 | **그림 2** | `results/figures/fig6_qualitative.png` (정성 비교) | 우·결과 부제목 2 | 5.2절 |
| 그림 | **그림 3** | `results/figures/fig3_layouts.png` (레이아웃별 효과) | 우·결과 부제목 3 | 5.3절 |

※ 그림 4·5·6, 표 1·2·3·5·6·7·8·9·10·12·13 → 본문에 수치 인라인 인용 또는 발표 답변용 백업.

---

# 좌측 Column

## ▌서론 (Introduction)

프레젠테이션 슬라이드는 배경·카드·차트·텍스트·아이콘 등 여러 시각 층이 정확한 stacking order로 겹쳐 구성되는 **계층적 시각 객체**이다. 단일 VLM 호출은 이 계층 구조를 충분히 반영하지 못한 채 HTML 을 직렬로 생성한다.

### ◆ 핵심 관찰 — 인식-생성 격차

같은 GPT-4o 에게:
- 슬라이드 이미지를 **자연어로 기술** → 평균 **6.6개 레이어** (range 5–10) 인식
- 같은 이미지를 **HTML 변환** → 평균 **1.8개** 만 코드 반영

→ **6.6 → 1.8 격차**, 시각 계층이 통째로 누락. 이를 **슬라이드 도메인의 계층적 요소 누락** 으로 정식화한다.

### ◆ 최첨단 VLM 으로의 일반성

**[표 11 — Cross-VLM 프로빙 (N=10, 부록 B.2)]**

| 모델 | LTED ↓ | Layer Recall ↑ | 격차 (1−Recall) |
|---|:---:|:---:|:---:|
| single_pass (GPT-4o) | 0.823 | 0.224 | 0.776 |
| single_pass (GPT-5.4) | 0.669 | 0.300 | 0.700 |
| single_pass (Claude 4.6 Opus) | 0.693 | 0.312 | 0.688 |
| **LayerAgent (GPT-4o)** | **0.551** | **0.759** | **0.241** |

→ 세 최첨단 모두 격차 0.69~0.78 범위 — **모델 업그레이드 단독으로 해소되지 않음**, 파이프라인 분해의 정당성.

### ◆ 연구 질문
- **RQ1**. 인식-생성 격차가 모델 일반적 현상인가?
- **RQ2**. 동일 GPT-4o 에서 LayerAgent 가 일괄 생성 대비 우수한가?
- **RQ3**. 효과는 레이아웃 유형에 따라 어떻게 달라지는가?

---

## ▌연구 방법 (LayerAgent Framework)

### ◆ 전체 파이프라인

→ **[그림 1 = `results/figures/layeragent_architecture.png`]** (LayerAgent 전체 아키텍처, 3.1절)

단일 VLM 호출을 **8개 전문 에이전트의 레이어 단위 분해**로 재구성. 각 호출이 구조·스타일·콘텐츠를 동시에 짊어지지 않고 **한 가지 책임만** 진다.

**파이프라인 순서:** Chat Parser → Analyzer → Design Director (DesignSpec Blackboard) → 8 전문가 병렬 실행 → Assembler (z-index) → Style Normalizer → Text Inserter

### ◆ 핵심 메커니즘 3가지

1. **DesignSpec Blackboard** — CV facts (k-means 팔레트 / OCR 텍스트 높이 / HSV 채도) 그라운딩으로 작성된 타입드 JSON 스타일 사양. 에이전트 간 스타일 표류를 사전 차단.
2. **chart_templates 7 renderer** — bar / line / waterfall / matrix_2x2 / mekko / harvey_table / tree. VLM 은 데이터 추출만, 시각은 결정적 SVG/HTML 프리미티브로 산출 → **자기회귀 zero-sum 회피**.
3. **Text Inserter** — 시각 디자인 완성 후 텍스트 주입. 풍부한 CSS 생성과 정확한 텍스트 배치의 단계 분리로 zero-sum 경쟁 완화.

### ◆ 4 메서드 비교 설정 (4.2절)

A. 일괄 생성 (sp) · B. 시각 분석 (cot) · C. 패턴 주입 (rag) · **D. LayerAgent**
모두 동일 GPT-4o, 동일 콘텐츠 데이터, seed=0. 평가셋 N=50 (고밀도 시각 효과 10 + 차트·다이어그램 40, Gemini 3 Pro Image Preview 생성).

---

# 우측 Column

## ▌연구 결과 (Results)

### ◆ 부제목 1: 동일 GPT-4o 4 메서드 다면적 평가 (RQ2)

**[표 4 — 종합적 발표 품질 MLLM-as-a-judge, GPT-5.4 1–7 scale, N=50, 5.2절]**

| Criterion | sp | cot | rag | **LayerAgent** |
|---|:---:|:---:|:---:|:---:|
| Visual Fidelity ↑ | 2.24 | 2.08 | 1.74 | **2.94** |
| Layer Structure ↑ | 3.52 | 3.08 | 3.00 | **4.62** |
| Content Completeness ↑ | 3.92 | 3.70 | 3.76 | **4.62** |
| Design Quality ↑ | 3.78 | 3.30 | 3.36 | **3.90** |
| **Average ↑** | 3.37 | 3.04 | 2.96 | **4.02** |

→ **4 기준 모두 1위**, 평균 4.02 vs 차순위 3.37 (**+0.65**).
→ 객관 충실도 (표 2 백업): **Element-IoU 0.372 vs sp 0.314 = +18%**.

### ◆ 부제목 2: 정성적 구조 충실도 비교

→ **[그림 2 = `results/figures/fig6_qualitative.png`]** (4개 chart·표 디자인, Reference / single_pass / LayerAgent 3-column, 5.2절)

mekko · line_chart · matrix_2x2 · harvey_table 4 레이아웃에서 single_pass 가 chart 구조를 와해시키는 반면 LayerAgent 는 chart_templates 결정적 렌더링으로 **시각 충실도 + 콘텐츠 보존 동시 달성**.

### ◆ 부제목 3: 레이아웃 유형별 효과 (RQ3)

→ **[그림 3 = `results/figures/fig3_layouts.png`]** (Per-layout 효과 range, MLLM Δ 주축 + LTED Δ 보조축, 5.3절)

핵심 수치:
- **chart·표 6종** (matrix_2x2, line_chart, waterfall, bar_chart, mekko, harvey_table): MLLM Δ **+0.15 ~ +1.90** 큰 폭 우세 — chart_templates 결정적 렌더링이 자기회귀 zero-sum 회피
- **pyramid**: Δ +0.05 (tree_diagram renderer)
- **process_flow**: Δ −0.65 (chart_templates 미적용)
- **고밀도 시각 효과** (dark_glass, N=10): MLLM Δ **−0.80** — 분위기 레이어 단순화 패널티 (객관 충실도는 1위지만 종합 judge 는 분기 양상)

---

## ▌결론 (Conclusion)

### ◆ 본 논문의 기여
1. **슬라이드 도메인 계층적 요소 누락 정식화** — GPT-4o 6.6 → 1.8 격차, 최첨단 VLM 에서도 0.69~0.78 범위 지속 (RQ1, H-EO 채택).
2. **멀티에이전트 레이어 분해 프레임워크 LayerAgent** — DesignSpec blackboard (color_0_5 Δ +0.96 인과 효과 격리), Text Inserter, chart_templates 결정적 렌더링.
3. **Design2Code 다면적 평가** — 객관 충실도 + VLM 루브릭 + 교차 모델 judge 병행으로 평가 축 간 불일치 가시화.

### ◆ 핵심 성과 (동일 GPT-4o)
- Element-IoU **0.372 vs 0.314 (+18%)**
- GPT-5.4 MLLM 평균 **4.02 vs 3.37 (4 기준 모두 1위)**
- chart·표 7종에서 MLLM Δ **+0.05 ~ +1.90** 큰 폭 우세

### ◆ 향후 연구
Claude·Gemini 교차 judge · 인간 앵커 검증 (n ≥ 80) · multi-seed N=100+ · 시각 OCR CCR · 최첨단 백본 + LayerAgent 결합

---

## 하단 Footer

**고려대학교 인공지능융합학과** | Department of Artificial Intelligence Convergence, Korea University
정일균 · jik9210@gmail.com · 지도교수: 김현철 교수
