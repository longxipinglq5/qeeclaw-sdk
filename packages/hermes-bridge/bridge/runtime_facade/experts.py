from __future__ import annotations

from typing import Any

from bridge.expert_catalog import CentaurExpert, load_centaur_experts
from bridge.runtime_facade.models import ExpertManifest


class ExpertRegistry:
    def __init__(
        self,
        experts: list[ExpertManifest],
        *,
        public_experts: list[dict[str, Any]] | None = None,
    ) -> None:
        self._experts = {expert.expert_id: expert for expert in experts}
        self._public_experts = public_experts or []
        self._public_by_id = {
            str(expert["id"]): expert for expert in self._public_experts
        }

    @classmethod
    def with_builtin_experts(cls) -> "ExpertRegistry":
        centaur_experts = load_centaur_experts()
        experts = [cls._from_centaur_expert(expert) for expert in centaur_experts]
        experts.extend(
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
        return cls(
            experts,
            public_experts=[
                expert.to_public_dict()
                for expert in centaur_experts
            ],
        )

    def list_experts(self) -> list[ExpertManifest]:
        return list(self._experts.values())

    def get_expert(self, expert_id: str) -> ExpertManifest:
        return self._experts[expert_id]

    def list_public_experts(self) -> list[dict[str, Any]]:
        return [dict(expert) for expert in self._public_experts]

    def get_public_expert(self, expert_id: str) -> dict[str, Any]:
        return dict(self._public_by_id[expert_id])

    @staticmethod
    def _from_centaur_expert(expert: CentaurExpert) -> ExpertManifest:
        return ExpertManifest(
            expert_id=expert.expert_id,
            name=expert.name,
            title=expert.title,
            description=expert.summary,
            category=expert.category,
            source_agent_id=expert.source_agent_id or expert.expert_id,
            source_path=expert.source_path,
            hermes_skill=expert.hermes_skill,
            recommended_tool_ids=expert.recommended_tool_ids,
            starter_prompts=expert.starter_prompts,
            ui=expert.to_public_dict(),
            context_scope=expert.context_scope,
            hermes_profile=expert.hermes_skill,
            permissions=[],
        )
