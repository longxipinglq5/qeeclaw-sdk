"""
QeeClaw Session Manager — 多人多轮对话 + 多智体

管理用户会话(session)、对话历史(messages)和智体实例(agent)。

设计目标:
- 每个 session 独立维护 message history，支持多轮对话
- 不同用户通过 session_id 隔离
- 支持多个 agent_profile（基于 hermes-agent 的 profile 机制）
- 内存+磁盘持久化，进程重启后可恢复会话
- 自动过期清理，避免内存泄漏
"""

import json
import os
import time
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 会话数据结构
# ---------------------------------------------------------------------------

class Session:
    """单个会话上下文: 一个用户 + 一个智体 的多轮对话。"""

    __slots__ = (
        "session_id", "user_id", "agent_profile", "messages",
        "created_at", "updated_at", "metadata", "_lock",
    )

    def __init__(
        self,
        session_id: str,
        user_id: str = "anonymous",
        agent_profile: str = "default",
        messages: Optional[List[Dict[str, str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[float] = None,
        updated_at: Optional[float] = None,
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.agent_profile = agent_profile
        self.messages: List[Dict[str, str]] = messages or []
        self.metadata: Dict[str, Any] = metadata or {}
        self.created_at = created_at or time.time()
        self.updated_at = updated_at or time.time()
        self._lock = threading.Lock()

    def add_message(self, role: str, content: str):
        """线程安全地追加一条消息。"""
        with self._lock:
            self.messages.append({"role": role, "content": content})
            self.updated_at = time.time()

    def get_messages(self, max_turns: int = 0) -> List[Dict[str, str]]:
        """获取历史消息，可选截取最近 N 轮。"""
        with self._lock:
            if max_turns <= 0 or len(self.messages) <= max_turns * 2:
                return list(self.messages)
            # 保留最近 max_turns 轮 (每轮 = user + assistant)
            return list(self.messages[-(max_turns * 2):])

    def clear_messages(self):
        """清空对话历史。"""
        with self._lock:
            self.messages.clear()
            self.updated_at = time.time()

    @property
    def turn_count(self) -> int:
        """已完成的对话轮数 (user+assistant 算一轮)。"""
        return sum(1 for m in self.messages if m.get("role") == "assistant")

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "session_id": self.session_id,
                "user_id": self.user_id,
                "agent_profile": self.agent_profile,
                "messages": list(self.messages),
                "metadata": dict(self.metadata),
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        return cls(
            session_id=data["session_id"],
            user_id=data.get("user_id", "anonymous"),
            agent_profile=data.get("agent_profile", "default"),
            messages=data.get("messages", []),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


# ---------------------------------------------------------------------------
# 智体 Profile 配置
# ---------------------------------------------------------------------------

class AgentProfile:
    """智体档案: 定义一个特定角色/能力的 AI 智体。"""

    def __init__(
        self,
        name: str,
        display_name: str = "",
        system_prompt: str = "",
        model: str = "",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools_enabled: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        max_iterations: int = 30,
        enabled_toolsets: Optional[List[str]] = None,
        disabled_toolsets: Optional[List[str]] = None,
        hermes_home: Optional[str] = None,
    ):
        self.name = name
        self.display_name = display_name or name
        self.system_prompt = system_prompt
        self.model = model  # 空 = 使用全局默认
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tools_enabled = tools_enabled
        self.metadata = metadata or {}
        self.max_iterations = max_iterations
        self.enabled_toolsets = enabled_toolsets
        self.disabled_toolsets = disabled_toolsets
        self.hermes_home = hermes_home  # 独立 HERMES_HOME 路径（None = 使用全局默认）

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "name": self.name,
            "display_name": self.display_name,
            "system_prompt": self.system_prompt,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "tools_enabled": self.tools_enabled,
            "metadata": self.metadata,
            "max_iterations": self.max_iterations,
        }
        if self.enabled_toolsets is not None:
            d["enabled_toolsets"] = self.enabled_toolsets
        if self.disabled_toolsets is not None:
            d["disabled_toolsets"] = self.disabled_toolsets
        if self.hermes_home is not None:
            d["hermes_home"] = self.hermes_home
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentProfile":
        return cls(
            name=data["name"],
            display_name=data.get("display_name", ""),
            system_prompt=data.get("system_prompt", ""),
            model=data.get("model", ""),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens"),
            tools_enabled=data.get("tools_enabled", True),
            metadata=data.get("metadata", {}),
            max_iterations=data.get("max_iterations", 30),
            enabled_toolsets=data.get("enabled_toolsets"),
            disabled_toolsets=data.get("disabled_toolsets"),
            hermes_home=data.get("hermes_home"),
        )


# ---------------------------------------------------------------------------
# 内建智体
# ---------------------------------------------------------------------------

_BUILTIN_PROFILES: Dict[str, AgentProfile] = {
    "default": AgentProfile(
        name="default",
        display_name="通用助手",
        system_prompt="你是一个由 QeeClaw 平台部署的 AI 助手，擅长回答各类问题并协助完成任务。",
    ),
    "coder": AgentProfile(
        name="coder",
        display_name="编程助手",
        system_prompt=(
            "你是一个专业的编程助手。请用清晰、简洁的代码和解释来回答技术问题。"
            "优先使用 Python，但也熟练掌握 JavaScript、TypeScript、Go、Rust 等语言。"
        ),
        temperature=0.3,
    ),
    "writer": AgentProfile(
        name="writer",
        display_name="写作助手",
        system_prompt=(
            "你是一个专业的写作助手。擅长撰写各类文档、邮件、报告、营销文案。"
            "注重语言的准确性和专业性，同时保持亲和力。"
        ),
        temperature=0.8,
    ),
    "analyst": AgentProfile(
        name="analyst",
        display_name="分析师",
        system_prompt=(
            "你是一个数据分析师。擅长从数据中提取洞察、制作报表、"
            "分析业务指标。回答时注重数据驱动和逻辑清晰。"
        ),
        temperature=0.4,
    ),
    "wechat": AgentProfile(
        name="wechat",
        display_name="微信客服",
        system_prompt="你是由 QeeClaw 部署在微信内的私域助理，请用简洁亲和的语调回答。",
        temperature=0.6,
    ),
}


# ---------------------------------------------------------------------------
# SessionManager 核心
# ---------------------------------------------------------------------------

# 默认配置
_DEFAULT_SESSION_TTL = 3600 * 24  # 24 小时
_DEFAULT_MAX_SESSIONS = 10000
_DEFAULT_MAX_TURNS_PER_SESSION = 200
_CLEANUP_INTERVAL = 300  # 5 分钟清理一次


class SessionManager:
    """
    会话管理器 — 多人多轮对话 + 多智体

    职责:
    1. 创建/获取/销毁会话
    2. 管理智体 profiles
    3. 会话持久化（磁盘）
    4. 自动过期清理
    """

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        session_ttl: int = _DEFAULT_SESSION_TTL,
        max_sessions: int = _DEFAULT_MAX_SESSIONS,
        max_turns: int = _DEFAULT_MAX_TURNS_PER_SESSION,
    ):
        hermes_home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.qeeclaw_hermes"))
        self._storage_dir = Path(storage_dir or os.path.join(hermes_home, "sessions"))
        self._storage_dir.mkdir(parents=True, exist_ok=True)

        self._session_ttl = session_ttl
        self._max_sessions = max_sessions
        self._max_turns = max_turns

        # 内存缓存: session_id → Session
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()

        # 智体 profiles: name → AgentProfile
        self._profiles: Dict[str, AgentProfile] = dict(_BUILTIN_PROFILES)
        self._load_custom_profiles()

        # 从磁盘恢复活跃会话
        self._restore_sessions()

        # 启动后台清理线程
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

        print(f"[session-manager] Initialized: {len(self._sessions)} sessions restored, "
              f"{len(self._profiles)} agents available")

    # ---- 会话 CRUD ----

    def create_session(
        self,
        user_id: str = "anonymous",
        agent_profile: str = "default",
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Session:
        """创建新会话。"""
        sid = session_id or f"ses_{uuid.uuid4().hex[:16]}"
        profile = self._profiles.get(agent_profile)
        if not profile:
            raise ValueError(f"Unknown agent profile: {agent_profile}")

        session = Session(
            session_id=sid,
            user_id=user_id,
            agent_profile=agent_profile,
            metadata=metadata,
        )

        with self._lock:
            # 如果超限，清理最旧的会话
            if len(self._sessions) >= self._max_sessions:
                self._evict_oldest()
            self._sessions[sid] = session

        self._persist_session(session)
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话，不存在返回 None。"""
        with self._lock:
            session = self._sessions.get(session_id)
        if session and (time.time() - session.updated_at) > self._session_ttl:
            self.delete_session(session_id)
            return None
        return session

    def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        user_id: str = "anonymous",
        agent_profile: str = "default",
    ) -> Session:
        """获取现有会话，或创建新的。"""
        if session_id:
            existing = self.get_session(session_id)
            if existing:
                return existing
        return self.create_session(
            user_id=user_id,
            agent_profile=agent_profile,
            session_id=session_id,
        )

    def delete_session(self, session_id: str) -> bool:
        """删除会话。"""
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session:
            self._remove_session_file(session_id)
            return True
        return False

    def list_sessions(
        self,
        user_id: Optional[str] = None,
        agent_profile: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """列出会话（可按用户/智体过滤）。"""
        now = time.time()
        with self._lock:
            sessions = list(self._sessions.values())
        result = []
        for s in sessions:
            if (now - s.updated_at) > self._session_ttl:
                continue
            if user_id and s.user_id != user_id:
                continue
            if agent_profile and s.agent_profile != agent_profile:
                continue
            result.append({
                "session_id": s.session_id,
                "user_id": s.user_id,
                "agent_profile": s.agent_profile,
                "turn_count": s.turn_count,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
            })
        result.sort(key=lambda x: x["updated_at"], reverse=True)
        return result

    # ---- 对话操作 ----

    def append_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
    ) -> bool:
        """记录一轮对话 (user + assistant)。超过 max_turns 自动截断旧消息。"""
        session = self.get_session(session_id)
        if not session:
            return False
        session.add_message("user", user_message)
        session.add_message("assistant", assistant_message)
        # 截断
        with session._lock:
            max_msgs = self._max_turns * 2
            if len(session.messages) > max_msgs:
                session.messages = session.messages[-max_msgs:]
        self._persist_session(session)
        return True

    def get_context_messages(
        self,
        session_id: str,
        system_prompt: Optional[str] = None,
        max_turns: int = 0,
    ) -> List[Dict[str, str]]:
        """
        构建发送给 LLM 的完整消息列表。

        返回: [system, ...history, user(最新)]
        """
        session = self.get_session(session_id)
        if not session:
            return []

        messages = []

        # System prompt: profile 级别 > 外部传入
        profile = self._profiles.get(session.agent_profile)
        effective_system = system_prompt or (profile.system_prompt if profile else "")
        if effective_system:
            messages.append({"role": "system", "content": effective_system})

        # 历史消息
        history = session.get_messages(max_turns=max_turns)
        messages.extend(history)

        return messages

    # ---- 智体 Profile 管理 ----

    def get_profile(self, name: str) -> Optional[AgentProfile]:
        return self._profiles.get(name)

    def list_profiles(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self._profiles.values()]

    def create_profile(self, profile_data: Dict[str, Any]) -> AgentProfile:
        """创建或更新自定义智体。"""
        name = profile_data.get("name")
        if not name:
            raise ValueError("Profile name is required")
        profile = AgentProfile.from_dict(profile_data)
        self._profiles[name] = profile
        self._save_custom_profiles()
        return profile

    def delete_profile(self, name: str) -> bool:
        """删除自定义智体（内建的不允许删除）。"""
        if name in _BUILTIN_PROFILES:
            return False
        if name in self._profiles:
            del self._profiles[name]
            self._save_custom_profiles()
            return True
        return False

    # ---- 持久化 ----

    def _persist_session(self, session: Session):
        """将会话保存到磁盘。"""
        try:
            filepath = self._storage_dir / f"{session.session_id}.json"
            data = json.dumps(session.to_dict(), ensure_ascii=False, indent=2)
            filepath.write_text(data, encoding="utf-8")
        except Exception as e:
            print(f"[session-manager] WARNING: persist failed for {session.session_id}: {e}")

    def _remove_session_file(self, session_id: str):
        try:
            filepath = self._storage_dir / f"{session_id}.json"
            filepath.unlink(missing_ok=True)
        except Exception:
            pass

    def _restore_sessions(self):
        """启动时从磁盘恢复未过期会话。"""
        now = time.time()
        restored = 0
        for filepath in self._storage_dir.glob("ses_*.json"):
            try:
                data = json.loads(filepath.read_text(encoding="utf-8"))
                session = Session.from_dict(data)
                if (now - session.updated_at) > self._session_ttl:
                    filepath.unlink(missing_ok=True)
                    continue
                self._sessions[session.session_id] = session
                restored += 1
            except Exception:
                pass

    def _load_custom_profiles(self):
        """从磁盘加载自定义智体。"""
        profiles_file = self._storage_dir / "_profiles.json"
        if profiles_file.exists():
            try:
                data = json.loads(profiles_file.read_text(encoding="utf-8"))
                for p in data:
                    profile = AgentProfile.from_dict(p)
                    self._profiles[profile.name] = profile
            except Exception as e:
                print(f"[session-manager] WARNING: Failed to load profiles: {e}")

    def _save_custom_profiles(self):
        """保存自定义智体到磁盘。"""
        custom = [
            p.to_dict() for name, p in self._profiles.items()
            if name not in _BUILTIN_PROFILES
        ]
        profiles_file = self._storage_dir / "_profiles.json"
        try:
            profiles_file.write_text(
                json.dumps(custom, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            print(f"[session-manager] WARNING: Failed to save profiles: {e}")

    # ---- 清理 ----

    def _evict_oldest(self):
        """淘汰最旧的会话（_lock 已持有时调用）。"""
        if not self._sessions:
            return
        oldest_id = min(self._sessions, key=lambda k: self._sessions[k].updated_at)
        self._sessions.pop(oldest_id, None)
        self._remove_session_file(oldest_id)

    def _cleanup_loop(self):
        """后台定时清理过期会话。"""
        while True:
            time.sleep(_CLEANUP_INTERVAL)
            try:
                self._cleanup_expired()
            except Exception:
                pass

    def _cleanup_expired(self):
        now = time.time()
        expired = []
        with self._lock:
            for sid, session in self._sessions.items():
                if (now - session.updated_at) > self._session_ttl:
                    expired.append(sid)
            for sid in expired:
                self._sessions.pop(sid, None)
        for sid in expired:
            self._remove_session_file(sid)
        if expired:
            print(f"[session-manager] Cleaned {len(expired)} expired sessions")

    # ---- 统计 ----

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._sessions)
            users = len(set(s.user_id for s in self._sessions.values()))
        return {
            "total_sessions": total,
            "active_users": users,
            "agent_profiles": len(self._profiles),
            "session_ttl_hours": self._session_ttl / 3600,
            "max_sessions": self._max_sessions,
            "max_turns_per_session": self._max_turns,
        }


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_session_manager: Optional[SessionManager] = None
_sm_lock = threading.Lock()


def get_session_manager() -> SessionManager:
    """获取全局 SessionManager 单例。"""
    global _session_manager
    if _session_manager is None:
        with _sm_lock:
            if _session_manager is None:
                _session_manager = SessionManager()
    return _session_manager
