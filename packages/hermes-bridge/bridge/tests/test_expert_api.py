from __future__ import annotations


async def test_get_api_experts_returns_84_public_experts(app_client):
    response = await app_client.get("/api/experts")

    assert response.status_code == 200
    experts = response.json()["experts"]
    assert len(experts) == 84
    assert experts[0]["id"] == "accounting-firm-client-success-advisor"
    assert experts[0]["hermesSkill"] == "accounting-firm-client-success-advisor"


async def test_get_api_expert_returns_detail(app_client):
    response = await app_client.get("/api/experts/professional-service-growth-strategist")

    assert response.status_code == 200
    expert = response.json()["expert"]
    assert expert["id"] == "professional-service-growth-strategist"
    assert expert["name"] == "企业服务获客策略师"
    assert expert["category"] == "sales"
    assert expert["sourceAgentId"] == "professional-service-growth-strategist"
    assert expert["sourcePath"].endswith("/professional-service-growth-strategist.md")
    assert expert["hermesSkill"] == "professional-service-growth-strategist"
    assert expert["contextScope"] == "owner"
    assert expert["recommendedToolIds"]
    assert expert["starterPrompts"]


async def test_get_api_expert_unknown_returns_expert_not_found(app_client):
    response = await app_client.get("/api/experts/unknown-expert")

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "EXPERT_NOT_FOUND",
        "message": "Expert not found",
        "details": {"expert_id": "unknown-expert"},
    }


async def test_public_experts_do_not_include_legacy_test_experts(app_client):
    response = await app_client.get("/api/experts")

    assert response.status_code == 200
    expert_ids = {expert["id"] for expert in response.json()["experts"]}
    assert "marketing_strategy_expert" not in expert_ids
    assert "hr_compliance_expert" not in expert_ids
