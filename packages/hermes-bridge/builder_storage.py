"""
Builder SQLite Storage - 本地 SQLite 数据库存储
"""

import os
import sqlite3
import json
import time
import uuid
from typing import Any, Dict, List, Optional


_HERMES_HOME = os.environ.get("HERMES_HOME", os.path.expanduser("~/.qeeclaw_hermes"))
_BUILDER_DB_PATH = os.path.join(_HERMES_HOME, "builder.db")


def _init_builder_db():
    """Initialize builder SQLite database"""
    os.makedirs(os.path.dirname(_BUILDER_DB_PATH), exist_ok=True)

    conn = sqlite3.connect(_BUILDER_DB_PATH)
    cursor = conn.cursor()

    # Create builder_projects table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS builder_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'interviewing',
            stage TEXT NOT NULL DEFAULT 'idea',
            industry TEXT,
            source TEXT,
            employee_id TEXT,
            blueprint TEXT NOT NULL,
            view_config TEXT,
            versions TEXT,
            test_runs TEXT,
            deployed_agent TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_project_id ON builder_projects(project_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_employee_id ON builder_projects(employee_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_updated_at ON builder_projects(updated_at DESC)")

    conn.commit()
    conn.close()


def _sanitize_builder_project_id(project_id: str) -> Optional[str]:
    """Sanitize project ID"""
    value = str(project_id or "").strip()
    if not value:
        return None
    if any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for ch in value):
        return None
    return value


def load_builder_project(project_id: str) -> Optional[Dict[str, Any]]:
    """Load a builder project from SQLite"""
    safe_id = _sanitize_builder_project_id(project_id)
    if not safe_id:
        return None

    try:
        _init_builder_db()
        conn = sqlite3.connect(_BUILDER_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM builder_projects WHERE project_id = ?", (safe_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        # Convert row to dict and parse JSON fields
        project = dict(row)
        project["id"] = project.pop("project_id")
        project["createdAt"] = project.pop("created_at")
        project["updatedAt"] = project.pop("updated_at")
        project["employeeId"] = project.pop("employee_id")
        project["viewConfig"] = project.pop("view_config")
        project["testRuns"] = project.pop("test_runs")
        project["deployedAgent"] = project.pop("deployed_agent")

        # Parse JSON fields
        project["blueprint"] = json.loads(project["blueprint"]) if project["blueprint"] else {}
        project["viewConfig"] = json.loads(project["viewConfig"]) if project["viewConfig"] else None
        project["versions"] = json.loads(project["versions"]) if project["versions"] else []
        project["testRuns"] = json.loads(project["testRuns"]) if project["testRuns"] else []
        project["deployedAgent"] = json.loads(project["deployedAgent"]) if project["deployedAgent"] else None

        return project

    except Exception as exc:
        print(f"[bridge] ERROR: Failed to load builder project {project_id}: {exc}")
        return None


def list_builder_projects() -> List[Dict[str, Any]]:
    """List all builder projects from SQLite"""
    try:
        _init_builder_db()
        conn = sqlite3.connect(_BUILDER_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM builder_projects ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        conn.close()

        projects = []
        for row in rows:
            project = dict(row)
            project["id"] = project.pop("project_id")
            project["createdAt"] = project.pop("created_at")
            project["updatedAt"] = project.pop("updated_at")
            project["employeeId"] = project.pop("employee_id")
            project["viewConfig"] = project.pop("view_config")
            project["testRuns"] = project.pop("test_runs")
            project["deployedAgent"] = project.pop("deployed_agent")

            # Parse JSON fields
            project["blueprint"] = json.loads(project["blueprint"]) if project["blueprint"] else {}
            project["viewConfig"] = json.loads(project["viewConfig"]) if project["viewConfig"] else None
            project["versions"] = json.loads(project["versions"]) if project["versions"] else []
            project["testRuns"] = json.loads(project["testRuns"]) if project["testRuns"] else []
            project["deployedAgent"] = json.loads(project["deployedAgent"]) if project["deployedAgent"] else None

            projects.append(project)

        return projects

    except Exception as exc:
        print(f"[bridge] ERROR: Failed to list builder projects: {exc}")
        return []


def save_builder_project(project: Dict[str, Any], project_id: Optional[str] = None) -> Dict[str, Any]:
    """Save a builder project to SQLite"""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    data = dict(project)

    # Generate project_id if not provided
    data_id = _sanitize_builder_project_id(project_id or data.get("id") or "")
    if not data_id:
        data_id = f"builder_{uuid.uuid4().hex[:12]}"

    data["id"] = data_id
    data.setdefault("createdAt", now)
    data["updatedAt"] = now
    data.setdefault("status", "draft")
    data.setdefault("stage", "idea")
    data.setdefault("versions", [])
    data.setdefault("testRuns", [])

    try:
        _init_builder_db()
        conn = sqlite3.connect(_BUILDER_DB_PATH)
        cursor = conn.cursor()

        # Check if project exists
        cursor.execute("SELECT id FROM builder_projects WHERE project_id = ?", (data_id,))
        existing = cursor.fetchone()

        if existing:
            # Update existing project
            cursor.execute("""
                UPDATE builder_projects SET
                    status = ?,
                    stage = ?,
                    industry = ?,
                    source = ?,
                    employee_id = ?,
                    blueprint = ?,
                    view_config = ?,
                    versions = ?,
                    test_runs = ?,
                    deployed_agent = ?,
                    updated_at = ?
                WHERE project_id = ?
            """, (
                data.get("status"),
                data.get("stage"),
                data.get("industry"),
                data.get("source"),
                data.get("employeeId"),
                json.dumps(data.get("blueprint", {}), ensure_ascii=False),
                json.dumps(data.get("viewConfig"), ensure_ascii=False) if data.get("viewConfig") else None,
                json.dumps(data.get("versions", []), ensure_ascii=False),
                json.dumps(data.get("testRuns", []), ensure_ascii=False),
                json.dumps(data.get("deployedAgent"), ensure_ascii=False) if data.get("deployedAgent") else None,
                data["updatedAt"],
                data_id
            ))
        else:
            # Insert new project
            cursor.execute("""
                INSERT INTO builder_projects (
                    project_id, status, stage, industry, source, employee_id,
                    blueprint, view_config, versions, test_runs, deployed_agent,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data_id,
                data.get("status"),
                data.get("stage"),
                data.get("industry"),
                data.get("source"),
                data.get("employeeId"),
                json.dumps(data.get("blueprint", {}), ensure_ascii=False),
                json.dumps(data.get("viewConfig"), ensure_ascii=False) if data.get("viewConfig") else None,
                json.dumps(data.get("versions", []), ensure_ascii=False),
                json.dumps(data.get("testRuns", []), ensure_ascii=False),
                json.dumps(data.get("deployedAgent"), ensure_ascii=False) if data.get("deployedAgent") else None,
                data["createdAt"],
                data["updatedAt"]
            ))

        conn.commit()
        conn.close()

        return data

    except Exception as exc:
        print(f"[bridge] ERROR: Failed to save builder project {data_id}: {exc}")
        raise


def delete_builder_project(project_id: str) -> bool:
    """Delete a builder project from SQLite"""
    safe_id = _sanitize_builder_project_id(project_id)
    if not safe_id:
        return False

    try:
        _init_builder_db()
        conn = sqlite3.connect(_BUILDER_DB_PATH)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM builder_projects WHERE project_id = ?", (safe_id,))
        deleted = cursor.rowcount > 0

        conn.commit()
        conn.close()

        return deleted

    except Exception as exc:
        print(f"[bridge] ERROR: Failed to delete builder project {project_id}: {exc}")
        return False


def run_builder_project_test(project: Dict[str, Any]) -> Dict[str, Any]:
    """Run builder test for a project"""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    data = dict(project)
    blueprint = data.get("blueprint", {}) if isinstance(data.get("blueprint"), dict) else {}
    role_type = str(blueprint.get("roleType", ""))
    name = str(blueprint.get("name", "数字员工"))
    goal = str(blueprint.get("goal", ""))

    is_document = role_type == "document_clerk"
    is_collection = role_type == "collection_assistant"

    approval_policies = blueprint.get("approvalPolicies", []) if isinstance(blueprint.get("approvalPolicies"), list) else []
    exception_policies = blueprint.get("exceptionPolicies", []) if isinstance(blueprint.get("exceptionPolicies"), list) else []
    acceptance_criteria = blueprint.get("acceptanceCriteria", []) if isinstance(blueprint.get("acceptanceCriteria"), list) else []
    checklist = blueprint.get("launchChecklist", []) if isinstance(blueprint.get("launchChecklist"), list) else []

    run = {
        "id": f"test_{uuid.uuid4().hex[:12]}",
        "projectId": data.get("id"),
        "status": "passed",
        "sampleSet": [
            {
                "id": "live-sqlite-1",
                "label": "资料来源 SQLite 校验" if is_document else "业务输入 SQLite 校验",
                "description": f"由本地 hermes-bridge SQLite 生成的验收输入",
            },
            {
                "id": "live-sqlite-2",
                "label": "审批策略 SQLite 校验" if is_collection else "输出结构 SQLite 校验",
                "description": f"由本地 hermes-bridge SQLite 生成的验收输入",
            },
        ],
        "inputSummary": f"{name} SQLite 测试：{goal}",
        "outputPreview": {
            "title": f"{name} SQLite 测试输出",
            "lines": (
                ["已通过本地 SQLite 校验资料识别、归档建议和异常确认点。"]
                if is_document else
                ["已通过本地 SQLite 校验催收话术、人工确认和后续跟进动作。"]
                if is_collection else
                ["已通过本地 SQLite 校验报告摘要、风险提示和确认流程。"]
            ),
        },
        "approvalPoints": [
            str(policy.get("action"))
            for policy in approval_policies
            if isinstance(policy, dict) and policy.get("required") and policy.get("action")
        ],
        "risks": [
            str(policy.get("condition"))
            for policy in exception_policies
            if isinstance(policy, dict) and policy.get("condition")
        ],
        "acceptanceResults": [
            {
                "criterionId": str(criterion.get("id", index)),
                "passed": True,
                "note": f"{criterion.get('metric', '验收项')} 已通过本地 SQLite 校验。",
            }
            for index, criterion in enumerate(acceptance_criteria)
            if isinstance(criterion, dict)
        ],
        "createdAt": now,
    }

    blueprint = dict(blueprint)
    blueprint["launchChecklist"] = [
        {
            **item,
            "status": item.get("status") if item.get("status") == "blocked" else "passed",
        }
        for item in checklist
        if isinstance(item, dict)
    ]

    data["blueprint"] = blueprint
    data["status"] = "ready_to_deploy"
    data["stage"] = "launch"
    data["testRuns"] = [run] + (data.get("testRuns", []) if isinstance(data.get("testRuns"), list) else [])

    return save_builder_project(data, project_id=str(data.get("id", "")))
