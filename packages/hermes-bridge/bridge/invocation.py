from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillDispatch:
    user_text: str
    skill_command: str | None = None
    skill_command_resolved: str | None = None
    error: dict | None = None


def split_slash_skill_prompt(prompt: str) -> tuple[str | None, str]:
    text = str(prompt or "").strip()
    if not text.startswith("/"):
        return None, text
    first, _, rest = text.partition(" ")
    command = first[1:].strip()
    if not command:
        return None, text
    return command, rest.strip()


def resolve_skill_dispatch(
    prompt: str,
    *,
    skill_command: str | None = None,
    task_id: str | None = None,
    runtime_note: str | None = None,
) -> SkillDispatch:
    explicit_command = str(skill_command or "").strip().lstrip("/")
    slash_command, slash_instruction = split_slash_skill_prompt(prompt)
    command = explicit_command or slash_command
    if not command:
        return SkillDispatch(user_text=prompt)

    try:
        from agent.skill_commands import (
            build_skill_invocation_message,
            resolve_skill_command_key,
        )
    except Exception as exc:
        return SkillDispatch(
            user_text=prompt,
            error={
                "code": "skill_command_dispatch_unavailable",
                "message": f"Hermes skill command dispatch is unavailable: {exc}",
                "skill_command": command,
            },
        )

    cmd_key = resolve_skill_command_key(command)
    if cmd_key is None:
        return SkillDispatch(
            user_text=prompt,
            error={
                "code": "unknown_skill_command",
                "message": f"Unknown skill command: /{command}",
                "skill_command": command,
            },
        )

    user_instruction = str(prompt or "").strip() if explicit_command else slash_instruction
    invocation_message = build_skill_invocation_message(
        cmd_key,
        user_instruction,
        task_id=task_id,
        runtime_note=str(runtime_note or ""),
    )
    if not invocation_message:
        return SkillDispatch(
            user_text=prompt,
            error={
                "code": "skill_invocation_build_failed",
                "message": f"Failed to build invocation message for skill command: /{command}",
                "skill_command": command,
            },
        )

    return SkillDispatch(
        user_text=invocation_message,
        skill_command=command,
        skill_command_resolved=cmd_key,
    )
