#!/usr/bin/env node

async function importFirst(specifiers) {
  let lastError;
  for (const specifier of specifiers) {
    try {
      return await import(specifier);
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
}

async function loadSdkModules() {
  const [{ createQeeClawClient }, { createQeeClawProductSDK }] = await Promise.all([
    importFirst([
      "@qeeclaw/core-sdk",
      "../../qeeclaw-core-sdk/dist/index.js",
      "../../core-sdk/dist/index.js",
    ]),
    importFirst([
      "@qeeclaw/product-sdk",
      "../dist/index.js",
    ]),
  ]);
  return { createQeeClawClient, createQeeClawProductSDK };
}

const baseUrl = process.env.QEECLAW_BASE_URL || "http://127.0.0.1:3456";
const token = process.env.QEECLAW_TOKEN || "mock-token";
const teamId = Number(process.env.QEECLAW_TEAM_ID || 10001);

async function main() {
  const { createQeeClawClient, createQeeClawProductSDK } = await loadSdkModules();
  const core = createQeeClawClient({
    baseUrl,
    token,
  });
  const product = createQeeClawProductSDK(core);

  const [
    channelHome,
    conversationHome,
    deviceOverview,
    governanceHome,
    knowledgeHome,
    salesCockpit,
    salesOpportunityBoard,
    salesKnowledge,
    salesCoaching,
  ] = await Promise.all([
    product.channelCenter.loadHome(teamId),
    product.conversationCenter.loadHome(teamId),
    product.deviceCenter.loadOverview(),
    product.governanceCenter.loadHome("mine"),
    product.knowledgeCenter.loadHome({ teamId }),
    product.salesCockpit.loadHome(teamId, "mine"),
    product.salesCockpit.loadOpportunityBoard(teamId, "mine"),
    product.salesKnowledge.loadAssistantContext({ teamId }),
    product.salesCoaching.loadTrainingOverview(teamId, "mine"),
  ]);

  process.stdout.write(
    `${JSON.stringify(
      {
        baseUrl,
        teamId,
        channels: {
          supportedCount: channelHome.overview.supportedCount,
          configuredCount: channelHome.overview.configuredCount,
          activeCount: channelHome.overview.activeCount,
          configuredChannels: channelHome.overview.items.filter((item) => item.configured).map((item) => item.channelKey),
        },
        conversations: {
          stats: conversationHome.stats,
          firstGroup: conversationHome.groups[0] || null,
          recentHistoryCount: conversationHome.history.length,
        },
        devices: {
          total: deviceOverview.total,
          online: deviceOverview.online,
          firstDevice: deviceOverview.devices[0] || null,
        },
        governance: {
          summary: governanceHome.summary,
          pendingApprovalIds: governanceHome.pendingApprovals.map((item) => item.approvalId),
          recentEventTitles: governanceHome.recentEvents.map((item) => item.title),
        },
        knowledge: {
          stats: knowledgeHome.stats,
          config: knowledgeHome.config,
          assetCount:
            typeof knowledgeHome.assets === "object" &&
            knowledgeHome.assets !== null &&
            "total" in knowledgeHome.assets &&
            typeof knowledgeHome.assets.total === "number"
              ? knowledgeHome.assets.total
              : null,
        },
        salesCockpit: {
          summary: salesCockpit.summary,
          followUps: salesCockpit.followUps.map((item) => item.roomName),
          riskOpportunities: salesCockpit.riskOpportunities.map((item) => item.title),
        },
        salesOpportunityBoard: {
          stageDistribution: salesOpportunityBoard.stageDistribution,
          recommendedActions: salesOpportunityBoard.recommendedActions,
        },
        salesKnowledge: {
          talkTracks: salesKnowledge.talkTracks.map((item) => item.title),
          productKnowledge: salesKnowledge.productKnowledge.map((item) => item.title),
          competitorResponses: salesKnowledge.competitorResponses.map((item) => item.title),
        },
        salesCoaching: {
          trainingTasks: salesCoaching.trainingTasks.map((item) => item.title),
          commonMistakes: salesCoaching.commonMistakes.map((item) => item.title),
          assistantTemplates: salesCoaching.assistantTemplates.map((item) => item.code),
        },
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
