from __future__ import annotations

from bridge.runtime_facade.models import ExpertManifest


class ExpertRegistry:
    def __init__(self, experts: list[ExpertManifest]) -> None:
        self._experts = {expert.expert_id: expert for expert in experts}

    @classmethod
    def with_builtin_experts(cls) -> "ExpertRegistry":
        return cls(
            [
                ExpertManifest(
                    expert_id="marketing_strategy_expert",
                    title="营销策略专家",
                    description="评估营销内容的转化、语气和渠道适配。",
                    context_scope="owner",
                    hermes_profile="edge_marketing_strategy",
                    permissions=["content.review", "strategy.suggest"],
                ),
                ExpertManifest(
                    expert_id="hr_compliance_expert",
                    title="HR 合规专家",
                    description="评估薪酬、招聘和员工沟通内容的合规风险。",
                    context_scope="conversation",
                    hermes_profile="edge_hr_compliance",
                    permissions=["hr.review", "compliance.suggest"],
                ),
            ]
        )

    def list_experts(self) -> list[ExpertManifest]:
        return list(self._experts.values())

    def get_expert(self, expert_id: str) -> ExpertManifest:
        return self._experts[expert_id]
