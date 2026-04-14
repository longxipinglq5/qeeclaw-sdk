import { createQeeClawClient } from "@qeeclaw/core-sdk";

async function main(): Promise<void> {
  const baseUrl = process.env.QEECLAW_BASE_URL;
  const token = process.env.QEECLAW_TOKEN;
  const teamId = Number(process.env.QEECLAW_TEAM_ID ?? "0");

  if (!baseUrl || !token) {
    throw new Error("Missing QEECLAW_BASE_URL or QEECLAW_TOKEN");
  }

  const client = createQeeClawClient({
    baseUrl,
    token,
    userAgent: "@qeeclaw/core-sdk-example",
  });

  const models = await client.models.listAvailable();
  console.log("models", models.slice(0, 3));

  const runtimes = await client.models.listRuntimes();
  console.log("runtimes", runtimes.map((item) => ({
    runtimeType: item.runtimeType,
    runtimeStatus: item.runtimeStatus,
    isDefault: item.isDefault,
  })));

  const routeProfile = await client.models.getRouteProfile();
  console.log("modelRoute", {
    preferredModel: routeProfile.preferredModel,
    resolvedModel: routeProfile.resolvedModel,
    provider: routeProfile.resolvedProviderName,
  });

  const usage = await client.models.getUsage({ days: 30 });
  const cost = await client.models.getCost({ days: 30 });
  const quota = await client.models.getQuota();
  console.log("modelUsage", {
    windowDays: usage.windowDays,
    totalCalls: usage.totalCalls,
    totalInputChars: usage.totalInputChars,
    totalOutputChars: usage.totalOutputChars,
  });
  console.log("modelCost", {
    totalAmount: cost.totalAmount,
    primaryCurrency: cost.primaryCurrency,
    topGroup: cost.breakdown[0]?.productName,
  });
  console.log("modelQuota", {
    walletBalance: quota.walletBalance,
    dailyRemaining: quota.dailyRemaining,
    monthlyRemaining: quota.monthlyRemaining,
  });

  const wallet = await client.billing.getWallet();
  console.log("wallet", wallet);

  const profile = await client.iam.getProfile();
  console.log("me", {
    id: profile.id,
    username: profile.username,
    teams: profile.teams.map((item) => item.name),
  });

  const documents = await client.file.listDocuments({ limit: 2 });
  console.log("documents", documents.map((item) => item.documentTitle));

  const workflows = await client.workflow.list();
  console.log("workflows", workflows.map((item) => item.id));

  const tools = await client.agent.listTools();
  console.log("agentTools", tools.map((item) => item.name));

  const deviceOnlineState = await client.devices.getOnlineState();
  console.log("deviceOnlineState", {
    runtimeType: deviceOnlineState.runtimeType,
    runtimeStatus: deviceOnlineState.runtimeStatus,
    runtimeStage: deviceOnlineState.runtimeStage,
    onlineTeamIds: deviceOnlineState.onlineTeamIds,
  });

  if (teamId > 0) {
    const runtimeScope = {
      teamId,
      runtimeType: "openclaw",
      agentId: "sales-copilot",
    };

    const storedMemory = await client.memory.store({
      ...runtimeScope,
      content: "Customer prefers quarterly billing.",
      category: "preference",
      importance: 0.9,
      sourceSession: "core-sdk-basic-usage",
    });
    console.log("storedMemory", storedMemory);

    const memoryStats = await client.memory.stats(runtimeScope);
    console.log("memoryStats", memoryStats);

    const knowledgeStats = await client.knowledge.stats(runtimeScope);
    console.log("knowledgeStats", knowledgeStats);

    const channelOverview = await client.channels.getOverview(teamId);
    console.log("channels", {
      supportedCount: channelOverview.supportedCount,
      activeCount: channelOverview.activeCount,
      personalChannels: channelOverview.items
        .filter((item) => item.channelGroup === "personal_reach")
        .map((item) => item.channelKey),
    });

    const openclawConfig = await client.channels.getWechatPersonalOpenClawConfig(teamId);
    console.log("openclawWechat", {
      gatewayOnline: openclawConfig.gatewayOnline,
      setupStatus: openclawConfig.setupStatus,
      channelMode: openclawConfig.channelMode,
    });
  }

  const decision = await client.policy.checkExecAccess({
    command: "rm -rf /",
    riskLevel: "critical",
  });
  console.log("execDecision", decision);

  if (decision.requiresApproval) {
    const approval = await client.approval.request({
      approvalType: "exec_access",
      title: "Dangerous command execution",
      reason: decision.reason ?? "Manual approval required",
      riskLevel: "critical",
      payload: { command: "rm -rf /" },
    });
    console.log("approval", approval.approvalId);
  }

  const appToken = await client.apikey.issueDefaultToken();
  console.log("defaultAppToken", appToken.appKey);

  const llmKeys = await client.apikey.listLLMKeys();
  console.log("llmKeys", llmKeys.map((item) => ({
    id: item.id,
    name: item.name,
    isActive: item.isActive,
  })));

  const speech = await client.voice.speech({
    text: "欢迎使用 QeeClaw Core SDK",
  });
  console.log("speechBytes", speech.audio.length);

  await client.audit.record({
    actionType: "SDK_DEMO",
    title: "Run @qeeclaw/core-sdk basic example",
    module: "SDK_EXAMPLE",
    path: "/examples/basic-usage.ts",
  });
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
