#!/usr/bin/env node

import { createRuntimeSidecar } from "./index.js";
import { toPublicAuthState } from "./state/auth-state-store.js";

async function main(): Promise<void> {
  const sidecar = createRuntimeSidecar();
  const command = process.argv[2] || "run";

  const readPublicAuthState = async () => {
    return toPublicAuthState(await sidecar.stateStore.read(), {
      configuredAuthToken: sidecar.config.sidecarAuthToken,
    });
  };

  if (command === "run") {
    await sidecar.start();
    process.stdout.write(
      `@qeeclaw/runtime-sidecar listening on http://${sidecar.config.sidecarHost}:${sidecar.config.sidecarPort} (Authorization: Bearer <sidecar-token>)\n`,
    );
    return;
  }

  if (command === "sync") {
    process.stdout.write(`${JSON.stringify(await sidecar.syncService.sync(), null, 2)}\n`);
    return;
  }

  if (command === "status") {
    const publicConfig = {
      ...sidecar.config,
      sidecarAuthToken: sidecar.config.sidecarAuthToken ? "<configured>" : undefined,
    };
    process.stdout.write(
      `${JSON.stringify(
        {
          config: publicConfig,
          authState: await readPublicAuthState(),
          gateway: await sidecar.gatewayAdapter.status(),
          knowledge: await sidecar.knowledgeWorker.getConfig(),
        },
        null,
        2,
      )}\n`,
    );
    return;
  }

  if (command === "selfcheck") {
    process.stdout.write(`${JSON.stringify(await sidecar.selfCheck(), null, 2)}\n`);
    return;
  }

  if (command === "gateway:start") {
    process.stdout.write(`${JSON.stringify(await sidecar.gatewayAdapter.start(), null, 2)}\n`);
    return;
  }

  if (command === "gateway:stop") {
    process.stdout.write(`${JSON.stringify(await sidecar.gatewayAdapter.stop(), null, 2)}\n`);
    return;
  }

  throw new Error(`Unsupported command: ${command}`);
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
