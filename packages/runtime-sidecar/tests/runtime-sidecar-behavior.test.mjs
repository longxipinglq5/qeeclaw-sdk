import assert from "node:assert/strict";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { mkdtemp, rm } from "node:fs/promises";

import { JsonHttpClient, JsonHttpError } from "../dist/http/json-http-client.js";
import { createRuntimeSidecar } from "../dist/index.js";
import { AuthStateStore } from "../dist/state/auth-state-store.js";
import { SyncService } from "../dist/sync/sync-service.js";

function createSidecarConfig(tmpDir) {
  return {
    controlPlaneBaseUrl: "https://control-plane.test",
    localGatewayWsUrl: "ws://127.0.0.1:18789",
    sidecarHost: "127.0.0.1",
    sidecarPort: 21736,
    sidecarAuthToken: "sidecar-auth-secret",
    allowRemoteAccess: false,
    startGatewayOnBoot: false,
    startBridgeOnBoot: false,
    autoBootstrapDevice: true,
    stateRootDir: tmpDir,
    stateFilePath: path.join(tmpDir, "auth-state.json"),
    gatewayCommand: undefined,
    gatewayArgs: [],
    gatewayWorkingDir: undefined,
    bridgeEntryPath: undefined,
    gatewayPidFilePath: path.join(tmpDir, "gateway.json"),
    bridgePidFilePath: path.join(tmpDir, "gateway.json"),
    knowledgeConfigFilePath: path.join(tmpDir, "knowledge.json"),
    approvalsCacheFilePath: path.join(tmpDir, "approvals.json"),
    channelSecretsFilePath: path.join(tmpDir, "channel-secrets.json"),
    channelAttachmentDirPath: path.join(tmpDir, "channel-attachments"),
    deviceName: "QeeClaw Test",
    hostname: "localhost",
    osInfo: "test-os",
  };
}

test("sync service self-heals missing device key for current user installation", async (t) => {
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "qeeclaw-sidecar-sync-"));
  t.after(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  const stateStore = new AuthStateStore(path.join(tmpDir, "auth-state.json"));
  await stateStore.patch({
    installationId: "inst-sync-001",
    userToken: "user-token-secret",
    authMode: "account-only",
  });

  let bootstrapCalls = 0;
  const syncService = new SyncService(
    createSidecarConfig(tmpDir),
    stateStore,
    {
      async getAccountDeviceState() {
        return {
          installation_id: "inst-sync-001",
          state: "current_user",
          can_register_current_account: true,
          current_user_device_id: 7,
          current_user_has_devices: true,
        };
      },
      async bootstrapDevice(_token, payload) {
        bootstrapCalls += 1;
        assert.equal(payload.installation_id, "inst-sync-001");
        return {
          api_key: "device-key-recovered",
          base_url: "https://control-plane.test",
          ws_url: "wss://control-plane.test/api/openclaw/ws",
          device_id: 7,
          device_name: "QeeClaw Test",
        };
      },
    },
  );

  const result = await syncService.sync();
  const nextState = await stateStore.read();

  assert.equal(bootstrapCalls, 1);
  assert.equal(result.bootstrapPerformed, true);
  assert.equal(result.deviceId, 7);
  assert.equal(nextState.deviceKey, "device-key-recovered");
  assert.equal(nextState.authMode, "personal-device");
});

test("json http client surfaces non-json upstream errors as JsonHttpError", async () => {
  const client = new JsonHttpClient(
    "https://control-plane.test",
    async () =>
      new Response("<html><body>bad gateway</body></html>", {
        status: 502,
        statusText: "Bad Gateway",
        headers: {
          "content-type": "text/html; charset=utf-8",
        },
      }),
  );

  await assert.rejects(
    () => client.request({ method: "GET", path: "/health" }),
    (error) =>
      error instanceof JsonHttpError &&
      error.status === 502 &&
      error.message.includes("bad gateway"),
  );
});

test("runtime sidecar start tolerates startup sync failure and still starts local services", async (t) => {
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "qeeclaw-sidecar-start-"));
  t.after(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  const sidecar = createRuntimeSidecar(createSidecarConfig(tmpDir));

  let syncAttempted = false;
  let serverStarted = false;
  sidecar.syncService.sync = async () => {
    syncAttempted = true;
    throw new Error("control plane offline");
  };
  sidecar.server.start = async () => {
    serverStarted = true;
  };

  const stderrWrites = [];
  const originalWrite = process.stderr.write.bind(process.stderr);
  process.stderr.write = ((chunk, ...args) => {
    stderrWrites.push(String(chunk));
    return originalWrite(chunk, ...args);
  });

  try {
    await sidecar.start();
  } finally {
    process.stderr.write = originalWrite;
  }

  assert.equal(syncAttempted, true);
  assert.equal(serverStarted, true);
  assert.ok(stderrWrites.some((entry) => entry.includes("startup sync skipped")));
  assert.ok(await sidecar.getLocalApiToken());
});

test("runtime sidecar configures and removes local feishu adapter from local secrets", async (t) => {
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "qeeclaw-sidecar-channels-"));
  t.after(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  const sidecar = createRuntimeSidecar(createSidecarConfig(tmpDir));
  const calls = [];
  sidecar.channelManager.replaceAdapter = async (adapter) => {
    calls.push({ op: "replace", channel: adapter.channel });
  };
  sidecar.channelManager.removeAdapter = async (channel) => {
    calls.push({ op: "remove", channel });
    return true;
  };

  await sidecar.channelSecretStore.patch("feishu", {
    enabled: true,
    credentials: {
      appId: "cli_xxx",
      appSecret: "secret",
    },
  });
  await sidecar.configureLocalChannelsFromSecrets();

  await sidecar.channelSecretStore.patch("feishu", {
    enabled: false,
  });
  await sidecar.configureLocalChannelsFromSecrets();

  assert.deepEqual(calls, [
    { op: "remove", channel: "wechat_work" },
    { op: "replace", channel: "feishu" },
    { op: "remove", channel: "wechat_personal" },
    { op: "remove", channel: "wechat_work" },
    { op: "remove", channel: "feishu" },
    { op: "remove", channel: "wechat_personal" },
  ]);
});

test("runtime sidecar configures and removes local wechat work adapter from local secrets", async (t) => {
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "qeeclaw-sidecar-wechat-work-"));
  t.after(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  const sidecar = createRuntimeSidecar(createSidecarConfig(tmpDir));
  const calls = [];
  sidecar.channelManager.replaceAdapter = async (adapter) => {
    calls.push({ op: "replace", channel: adapter.channel });
  };
  sidecar.channelManager.removeAdapter = async (channel) => {
    calls.push({ op: "remove", channel });
    return true;
  };

  await sidecar.channelSecretStore.patch("wechat_work", {
    enabled: true,
    credentials: {
      corpId: "ww_corp",
      corpSecret: "secret",
      agentId: "1000001",
    },
  });
  await sidecar.configureLocalChannelsFromSecrets();

  await sidecar.channelSecretStore.patch("wechat_work", {
    enabled: false,
  });
  await sidecar.configureLocalChannelsFromSecrets();

  assert.deepEqual(calls, [
    { op: "replace", channel: "wechat_work" },
    { op: "remove", channel: "feishu" },
    { op: "remove", channel: "wechat_personal" },
    { op: "remove", channel: "wechat_work" },
    { op: "remove", channel: "feishu" },
    { op: "remove", channel: "wechat_personal" },
  ]);
});

test("runtime sidecar configures and removes local wechat personal adapter from local secrets", async (t) => {
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "qeeclaw-sidecar-wechat-personal-"));
  t.after(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  const sidecar = createRuntimeSidecar(createSidecarConfig(tmpDir));
  const calls = [];
  sidecar.channelManager.replaceAdapter = async (adapter) => {
    calls.push({ op: "replace", channel: adapter.channel });
  };
  sidecar.channelManager.removeAdapter = async (channel) => {
    calls.push({ op: "remove", channel });
    return true;
  };

  await sidecar.channelSecretStore.patch("wechat_personal", {
    enabled: true,
  });
  await sidecar.configureLocalChannelsFromSecrets();

  await sidecar.channelSecretStore.patch("wechat_personal", {
    enabled: false,
  });
  await sidecar.configureLocalChannelsFromSecrets();

  assert.deepEqual(calls, [
    { op: "remove", channel: "wechat_work" },
    { op: "remove", channel: "feishu" },
    { op: "replace", channel: "wechat_personal" },
    { op: "remove", channel: "wechat_work" },
    { op: "remove", channel: "feishu" },
    { op: "remove", channel: "wechat_personal" },
  ]);
});
