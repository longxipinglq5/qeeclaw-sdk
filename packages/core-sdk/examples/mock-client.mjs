#!/usr/bin/env node

import { createQeeClawClient } from "../dist/index.js";

const client = createQeeClawClient({
  baseUrl: process.env.QEECLAW_BASE_URL || "http://127.0.0.1:3456",
  token: process.env.QEECLAW_TOKEN || "mock-token",
});
const teamId = Number(process.env.QEECLAW_TEAM_ID || 10001);
const runtimeScope = {
  teamId,
  runtimeType: "openclaw",
  agentId: "sales-copilot",
};

async function main() {
  const [
    models,
    routeProfile,
    modelUsage,
    modelCost,
    modelQuota,
    wallet,
    profile,
    appKeys,
    llmKeys,
    tenantContext,
    documents,
    workflows,
    agentTools,
    deviceOnlineState,
    speech,
    conversationStats,
    knowledgeStats,
    auditSummary,
    channelOverview,
    openclawConfig,
  ] = await Promise.all([
    client.models.listAvailable(),
    client.models.getRouteProfile(),
    client.models.getUsage({ days: 30 }),
    client.models.getCost({ days: 30 }),
    client.models.getQuota(),
    client.billing.getWallet(),
    client.iam.getProfile(),
    client.apikey.list(),
    client.apikey.listLLMKeys(),
    client.tenant.getCurrentContext(),
    client.file.listDocuments({ limit: 3 }),
    client.workflow.list(),
    client.agent.listTools(),
    client.devices.getOnlineState(),
    client.voice.speech({ text: "QeeClaw voice mock demo" }),
    client.conversations.getStats(teamId),
    client.knowledge.stats(runtimeScope),
    client.audit.getSummary({ scope: "mine" }),
    client.channels.getOverview(teamId),
    client.channels.getWechatPersonalOpenClawConfig(teamId),
  ]);

  const storedMemory = await client.memory.store({
    ...runtimeScope,
    content: "Customer prefers quarterly billing.",
    category: "preference",
    importance: 0.9,
    sourceSession: "core-sdk-mock-client",
  });
  const memoryStats = await client.memory.stats(runtimeScope);

  const policyDecision = await client.policy.checkExecAccess({
    command: "python sync_customer_data.py",
    riskLevel: "medium",
    teamId,
  });

  process.stdout.write(
    `${JSON.stringify(
      {
        baseUrl: process.env.QEECLAW_BASE_URL || "http://127.0.0.1:3456",
        teamId,
        models: models.map((item) => item.modelName),
        routeProfile,
        modelUsage: {
          windowDays: modelUsage.windowDays,
          totalCalls: modelUsage.totalCalls,
          totalInputChars: modelUsage.totalInputChars,
          totalOutputChars: modelUsage.totalOutputChars,
        },
        modelCost: {
          totalAmount: modelCost.totalAmount,
          primaryCurrency: modelCost.primaryCurrency,
          breakdown: modelCost.breakdown.map((item) => ({
            productName: item.productName,
            amount: item.amount,
          })),
        },
        modelQuota: {
          walletBalance: modelQuota.walletBalance,
          dailyRemaining: modelQuota.dailyRemaining,
          monthlyRemaining: modelQuota.monthlyRemaining,
        },
        wallet,
        profile: {
          username: profile.username,
          role: profile.role,
        },
        appKeys: appKeys.items.map((item) => item.appKey),
        llmKeys: llmKeys.map((item) => ({
          id: item.id,
          name: item.name,
          isActive: item.isActive,
        })),
        tenantContext,
        documents: documents.map((item) => item.documentTitle),
        workflows: workflows.map((item) => item.id),
        agentTools: agentTools.map((item) => item.name),
        deviceOnlineState,
        speech: {
          bytes: speech.audio.length,
          contentType: speech.contentType,
        },
        conversationStats,
        knowledgeStats,
        storedMemory,
        memoryStats,
        auditSummary,
        channelOverview: {
          supportedCount: channelOverview.supportedCount,
          configuredCount: channelOverview.configuredCount,
          keys: channelOverview.items.map((item) => item.channelKey),
        },
        openclawConfig: {
          gatewayOnline: openclawConfig.gatewayOnline,
          setupStatus: openclawConfig.setupStatus,
          qrSupported: openclawConfig.qrSupported,
        },
        policyDecision,
      },
      null,
      2,
    )}\n`,
  );
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.stack || error.message : String(error)}\n`);
  process.exitCode = 1;
});
