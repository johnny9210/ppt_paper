"""LayerAgent — Multi-agent framework for presentation slide generation.

Quick usage:
    from layeragent import LayerAgent
    agent = LayerAgent(model="gpt-4o")
    html = agent.run("design_10_stats_hero")

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
