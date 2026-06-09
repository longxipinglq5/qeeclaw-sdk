from __future__ import annotations

import json
from importlib import resources

from bridge.expert_catalog import get_centaur_expert, load_centaur_experts


def test_load_centaur_experts_has_84_items() -> None:
    experts = load_centaur_experts()

    assert len(experts) == 84


def test_professional_service_growth_strategist_exists() -> None:
    expert = get_centaur_expert("professional-service-growth-strategist")

    assert expert.name == "企业服务获客策略师"
    assert expert.hermes_skill == "professional-service-growth-strategist"
    assert expert.context_scope == "owner"
    assert expert.source_agent_id == "professional-service-growth-strategist"


def test_exported_experts_include_local_life_metadata() -> None:
    expert = get_centaur_expert("local-business-growth-director")

    assert expert.priority_group == "local_life"
    assert expert.local_life_rank == 1
    assert "本地生活" in expert.scenario_tags
    assert "通用门店" in expert.business_segments


def test_exported_experts_preserve_frontend_priority_order() -> None:
    experts = load_centaur_experts()
    ids = [expert.expert_id for expert in experts]

    assert ids[:5] == [
        "accounting-firm-client-success-advisor",
        "tax-compliance-service-consultant",
        "law-firm-intake-strategist",
        "legal-service-productization-advisor",
        "professional-service-growth-strategist",
    ]
    assert ids.index("growth-hacker") < ids.index("local-business-growth-director")


def test_expert_ids_and_hermes_skills_are_unique() -> None:
    experts = load_centaur_experts()

    assert len({expert.expert_id for expert in experts}) == len(experts)
    assert len({expert.hermes_skill for expert in experts}) == len(experts)


def test_source_agent_id_matches_source_path_filename() -> None:
    for expert in load_centaur_experts():
        assert expert.source_agent_id == expert.source_path.rsplit("/", 1)[-1].removesuffix(".md")


def test_centaur_experts_json_is_package_data_readable() -> None:
    data_path = resources.files("bridge").joinpath("data/centaur_experts.json")

    exported = json.loads(data_path.read_text(encoding="utf-8"))
    assert len(exported) == 84
