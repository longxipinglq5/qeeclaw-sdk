from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CentaurExpert(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    expert_id: str = Field(alias="id")
    name: str
    title: str
    avatar: str
    category: str
    source_agent_id: str | None = Field(default=None, alias="sourceAgentId")
    source_path: str = Field(alias="sourcePath")
    aliases: list[str] = Field(default_factory=list)
    summary: str
    best_for: list[str] = Field(default_factory=list, alias="bestFor")
    deliverables: list[str] = Field(default_factory=list)
    playbook: list[str] = Field(default_factory=list)
    recommended_tool_ids: list[str] = Field(default_factory=list, alias="recommendedToolIds")
    starter_prompts: list[str] = Field(default_factory=list, alias="starterPrompts")
    scenario_tags: list[str] = Field(default_factory=list, alias="scenarioTags")
    business_segments: list[str] = Field(default_factory=list, alias="businessSegments")
    priority_group: str = Field(default="general", alias="priorityGroup")
    local_life_rank: int = Field(default=999, alias="localLifeRank")
    hermes_skill: str = Field(alias="hermesSkill")
    context_scope: Literal["owner", "conversation"] = Field(default="owner", alias="contextScope")

    @model_validator(mode="after")
    def validate_defaults(self) -> "CentaurExpert":
        expected_source_agent_id = Path(self.source_path).name.removesuffix(".md")
        if self.source_agent_id is None:
            self.source_agent_id = expected_source_agent_id
        if self.source_agent_id != expected_source_agent_id:
            raise ValueError("sourceAgentId must match sourcePath filename")
        if not self.starter_prompts:
            raise ValueError("starterPrompts must not be empty")
        if not isinstance(self.recommended_tool_ids, list):
            raise ValueError("recommendedToolIds must be an array")
        return self

    def to_public_dict(self) -> dict[str, object]:
        return self.model_dump(by_alias=True)


def _data_path():
    return resources.files("bridge").joinpath("data/centaur_experts.json")


@lru_cache(maxsize=1)
def load_centaur_experts() -> list[CentaurExpert]:
    raw = json.loads(_data_path().read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("centaur_experts.json must contain a list")
    experts = [CentaurExpert.model_validate(item) for item in raw]
    if len(experts) != 84:
        raise ValueError(f"expected 84 centaur experts, got {len(experts)}")
    expert_ids = [expert.expert_id for expert in experts]
    hermes_skills = [expert.hermes_skill for expert in experts]
    if len(set(expert_ids)) != len(expert_ids):
        raise ValueError("centaur expert ids must be unique")
    if len(set(hermes_skills)) != len(hermes_skills):
        raise ValueError("centaur expert hermesSkill values must be unique")
    return experts


def get_centaur_expert(expert_id: str) -> CentaurExpert:
    for expert in load_centaur_experts():
        if expert.expert_id == expert_id:
            return expert
    raise KeyError(expert_id)
