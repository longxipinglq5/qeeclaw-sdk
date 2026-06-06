from __future__ import annotations


def test_expert_registry_resolves_owner_scoped_marketing_expert():
    from bridge.runtime_facade.experts import ExpertRegistry

    registry = ExpertRegistry.with_builtin_experts()
    expert = registry.get_expert("marketing_strategy_expert")

    assert expert.expert_id == "marketing_strategy_expert"
    assert expert.context_scope == "owner"
    assert expert.hermes_profile == "edge_marketing_strategy"
    assert expert.session_id_for(
        owner_id="owner_1",
        conversation_id="conv_abc",
    ) == "edge:owner_1:expert:marketing_strategy_expert"


def test_expert_registry_resolves_conversation_scoped_sensitive_expert():
    from bridge.runtime_facade.experts import ExpertRegistry

    registry = ExpertRegistry.with_builtin_experts()
    expert = registry.get_expert("hr_compliance_expert")

    assert expert.expert_id == "hr_compliance_expert"
    assert expert.context_scope == "conversation"
    assert expert.hermes_profile == "edge_hr_compliance"
    assert expert.session_id_for(
        owner_id="owner_1",
        conversation_id="conv_hr_001",
    ) == "edge:owner_1:expert:hr_compliance_expert:conv:conv_hr_001"
    assert expert.session_id_for(
        owner_id="owner_1",
        conversation_id="conv_hr_002",
    ) == "edge:owner_1:expert:hr_compliance_expert:conv:conv_hr_002"


def test_linked_session_keeps_conversation_provenance():
    from bridge.runtime_facade.models import LinkedSession

    link = LinkedSession(
        source_session_id="edge:owner_1:supervisor:conv_abc",
        linked_session_id="edge:owner_1:expert:marketing_strategy_expert",
        expert_id="marketing_strategy_expert",
        metadata={"conversation_id": "conv_abc", "owner_id": "owner_1"},
    )

    assert link.metadata["conversation_id"] == "conv_abc"
    assert link.metadata["owner_id"] == "owner_1"
    assert link.model_dump(mode="json")["linked_session_id"] == (
        "edge:owner_1:expert:marketing_strategy_expert"
    )
