import { createQeeClawClient } from "@qeeclaw/core-sdk";
import { createQeeClawProductSDK } from "@qeeclaw/product-sdk";

async function main() {
  const core = createQeeClawClient({
    baseUrl: "https://your-qeeclaw-host",
    token: "your-bearer-token",
  });

  const product = createQeeClawProductSDK(core);

  const channelHome = await product.channelCenter.loadHome(1);
  console.log("channel home", channelHome.overview);

  const conversationHome = await product.conversationCenter.loadHome(1);
  console.log("conversation home", conversationHome.stats);

  const deviceOverview = await product.deviceCenter.loadOverview();
  console.log("device overview", deviceOverview);

  const governanceHome = await product.governanceCenter.loadHome("mine");
  console.log("governance home", governanceHome.summary);

  const knowledgeHome = await product.knowledgeCenter.loadHome({ teamId: 1 });
  console.log("knowledge home", knowledgeHome.stats);

  const salesCockpit = await product.salesCockpit.loadHome(1, "mine");
  console.log("sales cockpit", salesCockpit.summary);

  const salesKnowledge = await product.salesKnowledge.loadAssistantContext({ teamId: 1 });
  console.log("sales knowledge", salesKnowledge.talkTracks.map((item) => item.title));

  const salesCoaching = await product.salesCoaching.loadTrainingOverview(1, "mine");
  console.log("sales coaching", salesCoaching.trainingTasks.map((item) => item.title));
}

void main();
