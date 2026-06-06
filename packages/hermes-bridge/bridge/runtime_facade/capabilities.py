from __future__ import annotations

from bridge.runtime_facade.models import CapabilityManifest


class CapabilityRegistry:
    def __init__(self, capabilities: list[CapabilityManifest]) -> None:
        self._capabilities = {
            capability.capability_id: capability for capability in capabilities
        }

    @classmethod
    def with_builtin_capabilities(cls) -> "CapabilityRegistry":
        return cls(
            [
                CapabilityManifest(
                    capability_id="moments_copywriter",
                    kind="skill_app",
                    title="朋友圈文案",
                    description="生成适合朋友圈的真实、亲切产品文案。",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "product": {"type": "string"},
                            "tone": {"type": "string"},
                        },
                        "required": ["product"],
                    },
                    output_contract="skill_app_card",
                    hermes_profile="edge_supervisor",
                    slash_command="moments-copy-generator",
                    permissions=["content.generate"],
                    approval_policy="preview",
                ),
                CapabilityManifest(
                    capability_id="xiaohongshu_note_writer",
                    kind="skill_app",
                    title="小红书种草文",
                    description="生成小红书风格的产品种草笔记。",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "product": {"type": "string"},
                            "tone": {"type": "string"},
                            "platform": {"type": "string"},
                        },
                        "required": ["product"],
                    },
                    output_contract="skill_app_card",
                    hermes_profile="edge_supervisor",
                    slash_command="xhs-note-generator",
                    permissions=["content.generate"],
                    approval_policy="preview",
                ),
                CapabilityManifest(
                    capability_id="moments_copywriter_with_image",
                    kind="skill_app",
                    title="朋友圈文案配图",
                    description="生成朋友圈文案，并为产品内容生成配图。",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "product": {"type": "string"},
                            "tone": {"type": "string"},
                            "need_image": {"type": "boolean"},
                            "source_artifact_id": {"type": "string"},
                        },
                        "required": ["product"],
                    },
                    output_contract="copy_plus_image_card",
                    hermes_profile="edge_supervisor",
                    slash_command="moments-copy-generator",
                    permissions=["content.generate", "image.generate"],
                    approval_policy="preview",
                ),
            ]
        )

    def list_capabilities(self) -> list[CapabilityManifest]:
        return list(self._capabilities.values())

    def get_capability(self, capability_id: str) -> CapabilityManifest:
        return self._capabilities[capability_id]
