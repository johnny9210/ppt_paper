# LayerAgent

**Multi-agent framework for presentation slide generation via image → HTML/CSS.**

GPT-4o 기반 멀티에이전트 파이프라인이 single-pass frontier VLM (GPT-5.4) 을 시각 충실도에서 능가함을 보이는 연구 프로젝트.

## ✨ Key Features

- **8-stage multi-agent pipeline**: Analyzer → Design Director → (Base BG / Atmosphere / Decoration / Card Detail × N / Hero Detail × N / Icon Agent) → Assembler → Style Normalizer → Text Inserter → (optional Visual Critic)
- **DesignSpec blackboard**: Typed shared state (typography/palette/frame/motif) for cross-agent coordination
- **Library retrieval**: FontAwesome icons + Shape primitives + Background patterns (circuit/topographic/hex/dot) + Bezier connection lines for hub-spoke layouts
- **CV-grounded generation**: k-means palette, OCR text heights, HSV saturation injected as deterministic facts
- **Ablation-ready**: Single flag controls Style Normalizer, Text Inserter, CV facts, DesignSpec, Library, Visual Critic

## 📁 Project Structure

```
ppt_paper/
├── layeragent/              # Main framework
│   ├── __init__.py         # exports LayerAgent
│   ├── pipeline.py         # LangGraph pipeline + LayerAgent class
│   ├── state.py            # shared TypedDict State
│   ├── ablations.py        # ablation flag validation
│   ├── agents/             # 10 agent nodes
│   ├── libraries/          # icon_library, pattern_library, cv_extractors
│   ├── prompts/            # 9 prompt modules per agent
│   └── utils/              # common.py, bbox.py, llm.py
│
├── baselines/              # Comparison baselines
│   ├── single_pass.py      # A: single-pass GPT-4o
│   ├── visual_cot.py       # B: 2-stage Visual CoT
│   ├── cot_h_rag.py        # C: Visual CoT + CSS pattern RAG
│   └── multi_model.py      # GPT-4o / GPT-5.4 / Claude 4.6 Opus
│
├── experiments/
│   ├── run.py              # unified runner
│   └── configs/
│
├── data/
│   ├── experiment_designs/ # 10 slide PNGs + meta.json
│   └── slide_specs.jsonl   # 5 active designs
│
├── tests/test_smoke.py     # end-to-end smoke test
├── final_test/             # LEGACY (archived)
├── src/                    # LEGACY (original crop_layer_agent)
├── paper_draft_ko.md       # paper manuscript
└── README.md
```

## 🚀 Quick Start

### Install

```bash
pip install -r requirements.txt
playwright install chromium
brew install tesseract   # macOS; apt-get install tesseract-ocr on Linux
```

### Set up `.env`

```bash
OPENAI_API_KEY=sk-...

# Optional for multi-model baseline
APIM_AOAI_ENDPOINT=...
APIM_AOAI_API_KEY=...
GPT_MODEL=gpt-5.4
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-west-2
BEDROCK_CLAUDE_OPUS_MODEL_ID=us.anthropic.claude-opus-4-6-v1
```

### Run

```bash
# Smoke test (no API calls for most)
python3 tests/test_smoke.py

# LayerAgent full on one design
python3 -m experiments.run --method layeragent --design design_10_stats_hero

# Ablation (Style Normalizer removed)
python3 -m experiments.run --method layeragent --ablation no_style_norm --design design_10_stats_hero

# GPT-5.4 single-pass baseline
python3 -m experiments.run --method multi_model --model gpt-5.4 --design design_10_stats_hero

# All 5 designs, full pipeline
python3 -m experiments.run --method layeragent --all-designs
```

### Programmatic

```python
from layeragent import LayerAgent

agent = LayerAgent(model="gpt-4o", ablation="none", use_visual_critic=False)
html = agent.run("design_10_stats_hero")
```

## 🧪 Ablations

| Flag | Paper label | Effect |
|---|---|---|
| `none` | D (full) | Complete pipeline |
| `no_style_norm` | D₁ | Remove Style Normalizer → RQ1 ablation |
| `no_text_inserter` | D₂ | Remove Text Inserter → RQ2 ablation |
| `no_cv_facts` | D₃ | Remove CV palette/OCR/HSV injection |
| `no_designspec` | D₄ | Remove Design Director blackboard |
| `no_library` | D₅ | Remove FontAwesome/Shape/Pattern/Connection library |
| `use_visual_critic=True` | D+VC | Add Visual Critic stage (render-compare-fix 1-iter) |

## 📊 Results (design_10_stats_hero reference)

| Method | Visual Fidelity (est.) |
|---|---:|
| A: single-pass GPT-4o | ~40% |
| B: Visual CoT (GPT-4o) | ~50% |
| C: CoT + H-RAG (GPT-4o) | ~60% |
| **D: LayerAgent full (GPT-4o)** | **~85%** |
| GPT-5.4 single-pass | ~80% |

## 📖 Paper

See `paper_draft_ko.md`. Three RQs:
- **RQ1** Cross-Element Visual Consistency
- **RQ2** Joint Content-Visual Fidelity
- **RQ3** Measurement Validity

## 🔁 Reproducibility

```bash
python3 tests/test_smoke.py
python3 -m experiments.run --method layeragent --all-designs --n-seeds 3
python3 -m experiments.run --method single_pass --all-designs --n-seeds 3
python3 -m experiments.run --method cot_h_rag --all-designs --n-seeds 3
```

## 📝 License

MIT
