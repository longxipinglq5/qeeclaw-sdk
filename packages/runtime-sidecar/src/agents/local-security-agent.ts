import type { PolicyDecision } from "../types.js";

const HIGH_RISK_LEVELS = new Set(["high", "critical"]);
const SENSITIVE_CLASSIFICATIONS = new Set(["confidential", "restricted", "secret"]);
const SENSITIVE_OPERATIONS = new Set(["delete", "export"]);
const DANGEROUS_TOOL_KEYWORDS = ["shell", "exec", "command", "terminal", "desktop"];
const DANGEROUS_COMMAND_PATTERNS: Array<[RegExp, string]> = [
  [/\brm\s+-rf\s+\/$/, "detected-root-delete-command"],
  [/\bshutdown\b/, "detected-shutdown-command"],
  [/\breboot\b/, "detected-reboot-command"],
  [/\bmkfs(\.[a-z0-9]+)?\b/, "detected-format-command"],
  [/\bdd\s+if=/, "detected-raw-disk-write"],
  [/:\(\)\s*\{\s*:\|:&\s*\};:/, "detected-fork-bomb"],
];

function nowIso(): string {
  return new Date().toISOString();
}

function decision(
  allowed: boolean,
  reason: string,
  matchedPolicy: string,
  requiresApproval = false,
): PolicyDecision {
  return {
    allowed,
    reason,
    matchedPolicy,
    requiresApproval,
    source: "sidecar-local",
    checkedAt: nowIso(),
  };
}

export class LocalSecurityAgent {
  checkToolAccess(input: { tool_name?: string; risk_level?: string; requires_approval?: boolean }): PolicyDecision {
    const normalizedTool = (input.tool_name || "").trim().toLowerCase();
    const normalizedRisk = (input.risk_level || "medium").trim().toLowerCase();

    if (!normalizedTool) {
      throw new Error("tool_name cannot be empty");
    }
    if (input.requires_approval || HIGH_RISK_LEVELS.has(normalizedRisk)) {
      return decision(false, "tool access requires manual approval", "local-manual-approval", true);
    }
    if (DANGEROUS_TOOL_KEYWORDS.some((keyword) => normalizedTool.includes(keyword))) {
      return decision(false, "dangerous tool requires approval", "local-dangerous-tool", true);
    }
    return decision(true, "tool access allowed by local defaults", "local-default-tool-allow", false);
  }

  checkDataAccess(input: {
    classification?: string;
    operation?: string;
    requires_approval?: boolean;
  }): PolicyDecision {
    const classification = (input.classification || "internal").trim().toLowerCase();
    const operation = (input.operation || "read").trim().toLowerCase();

    if (input.requires_approval) {
      return decision(false, "data access explicitly requires approval", "local-explicit-data-approval", true);
    }
    if (SENSITIVE_CLASSIFICATIONS.has(classification) && SENSITIVE_OPERATIONS.has(operation)) {
      return decision(false, "sensitive data operation requires approval", "local-sensitive-data-approval", true);
    }
    return decision(true, "data access allowed by local defaults", "local-default-data-allow", false);
  }

  checkExecAccess(input: { command?: string; risk_level?: string; requires_approval?: boolean }): PolicyDecision {
    const command = (input.command || "").trim();
    const riskLevel = (input.risk_level || "medium").trim().toLowerCase();

    if (!command) {
      throw new Error("command cannot be empty");
    }
    for (const [pattern, matchedPolicy] of DANGEROUS_COMMAND_PATTERNS) {
      if (pattern.test(command)) {
        return decision(false, "dangerous command blocked", matchedPolicy, true);
      }
    }
    if (input.requires_approval || HIGH_RISK_LEVELS.has(riskLevel)) {
      return decision(false, "high risk execution requires approval", "local-high-risk-exec", true);
    }
    return decision(true, "exec access allowed by local defaults", "local-default-exec-allow", false);
  }
}
