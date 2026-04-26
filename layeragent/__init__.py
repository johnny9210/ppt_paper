"""LayerAgent — Multi-agent framework for presentation slide generation.

Two entry points (both require a reference design image):

(1) Benchmark mode — pre-defined slide_id pulls structured content from meta.json:
    from layeragent import LayerAgent
    agent = LayerAgent(model="gpt-4o")
    html = agent.run("design_10_stats_hero")

(2) Chat mode — user free-form message + reference image → 1 slide:
    agent = LayerAgent(model="gpt-4o")
    html, spec = agent.run_from_chat(
        image_path="data/experiment_designs/design_02_dashboard.png",
        user_message="Q4 매출 대시보드. 매출 128억 +23%, 사용자 240만 +15%, 만족도 4.7/5.0 +0.3",
    )

Ablations:
    agent = LayerAgent(ablation="no_style_norm")    # D₁
    agent = LayerAgent(ablation="no_text_inserter") # D₂
    agent = LayerAgent(ablation="no_cv_facts")      # D₃
    agent = LayerAgent(ablation="no_designspec")    # D₄
    agent = LayerAgent(ablation="no_library")       # D₅
    agent = LayerAgent(use_visual_critic=True)      # D + Visual Critic
"""
from __future__ import annotations

from .pipeline import LayerAgent, build_pipeline
from .ablations import SUPPORTED_ABLATIONS
from .state import State

__version__ = "1.0.0"
__all__ = ["LayerAgent", "build_pipeline", "SUPPORTED_ABLATIONS", "State"]
