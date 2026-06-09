from __future__ import annotations


class SessionIdBuilder:
    @staticmethod
    def supervisor(owner_id: str, conversation_id: str) -> str:
        return f"edge:{owner_id}:supervisor:{conversation_id}"

    @staticmethod
    def expert(owner_id: str, expert_id: str) -> str:
        return f"edge:{owner_id}:expert:{expert_id}"

    @staticmethod
    def channel(owner_id: str, channel_key: str, conversation_key: str) -> str:
        return f"edge:{owner_id}:channel:{channel_key}:{conversation_key}"

    @staticmethod
    def automation(owner_id: str, employee_id: str, goal_id: str) -> str:
        return f"edge:{owner_id}:automation:{employee_id}:{goal_id}"
