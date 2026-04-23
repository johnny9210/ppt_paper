"""Adapter module — 기존 exp1~4 runner가 모듈-style로 LayerAgent variants를 호출하던
인터페이스를 새 `layeragent.LayerAgent` 클래스 기반으로 포장.

기존 코드:
    from final_test.methods import layeragent_full
    layeragent_full.run(slide_id, seed, model)

새 방식:
    from experiments._adapter import layeragent_full
    layeragent_full.run(slide_id, seed, model)  # 내부에서 LayerAgent(ablation="none") 사용
"""
from __future__ import annotations

from layeragent import LayerAgent


class _Variant:
    def __init__(self, ablation: str = "none", use_visual_critic: bool = False):
        self.ablation = ablation
        self.use_visual_critic = use_visual_critic

    def run(self, slide_id: str, seed: int = 0, model: str = "gpt-4o") -> str:
        agent = LayerAgent(model=model, ablation=self.ablation, use_visual_critic=self.use_visual_critic)
        return agent.run(slide_id, seed=seed)


layeragent_full = _Variant(ablation="none")
layeragent_no_stylenorm = _Variant(ablation="no_style_norm")
layeragent_no_textinserter = _Variant(ablation="no_text_inserter")
layeragent_no_cv_facts = _Variant(ablation="no_cv_facts")
layeragent_no_designspec = _Variant(ablation="no_designspec")
layeragent_no_library = _Variant(ablation="no_library")
layeragent_with_critic = _Variant(ablation="none", use_visual_critic=True)
