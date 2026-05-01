import assert from "node:assert/strict";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { mkdtemp, rm } from "node:fs/promises";

import { AuthStateStore } from "../dist/state/auth-state-store.js";
import { toPublicAuthState } from "../dist/state/auth-state-store.js";
import { HttpSidecarServer } from "../dist/server/http-sidecar-server.js";

function createDeps(config, stateStore) {
  return {
    config,
    stateStore,
    syncService: {
      async sync() {
        return {
          installationId: "inst-sidecar-001",
          authMode: "personal-device",
          hasUserToken: true,
          hasDeviceKey: true,
          bootstrapPerformed: false,
          deviceId: 9,
        };
      },
    },
    gatewayAdapter: {
      async status() {
        return {
          configured: false,
          running: false,
          args: [],
        };
      },
      async start() {
        return {
          configured: true,
          running: true,
          args: [],
        };
      },
      async stop() {
        return {
          configured: false,
          running: false,
          args: [],
        };
      },
    },
    memoryWorker: {
      async store(payload) {
        return payload;
      },
      async search(payload) {
        return payload;
      },
      async delete(entryId) {
        return { deleted: entryId };
      },
      async stats() {
        return { total: 0 };
      },
    },
    knowledgeWorker: {
      async getConfig() {
        return {
          watchDir: "/tmp/knowledge",
          lastSyncedAt: null,
          inventoryCount: 0,
          items: [],
        };
      },
      async updateConfig(payload) {
        return {
          watchDir: payload.watchDir,
          lastSyncedAt: null,
          inventoryCount: 0,
          items: [],
        };
      },
      async sync(limit) {
        return {
          watchDir: "/tmp/knowledge",
          lastSyncedAt: null,
          inventoryCount: limit || 0,
          items: [],
        };
      },
    },
    securityAgent: {
      checkToolAccess() {
        return { allowed: true, reason: "ok", matchedPolicy: "test", requiresApproval: false, source: "sidecar-local", checkedAt: new Date().toISOString() };
      },
      checkDataAccess() {
        return { allowed: true, reason: "ok", matchedPolicy: "test", requiresApproval: false, source: "sidecar-local", checkedAt: new Date().toISOString() };
      },
      checkExecAccess() {
        return { allowed: true, reason: "ok", matchedPolicy: "test", requiresApproval: false, source: "sidecar-local", checkedAt: new Date().toISOString() };
      },
    },
    approvalAgent: {
      async requestApproval() {
        return { approvalId: "apr_test", status: "pending" };
      },
      async listApprovals() {
        return { total: 0, page: 1, pageSize: 50, items: [] };
      },
      async listPendingLocalCache() {
        return [];
      },
    },
    channelManager: {
      getStatus() {
        return { running: false, adapters: [] };
      },
    },
    channelSecretStore: {
      async publicStatus() {
        return [];
      },
      async patch(channel, patch) {
        return { channel, ...patch };
      },
    },
  };
}

test("http sidecar server requires bearer token and masks auth state", async (t) => {
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "qeeclaw-sidecar-http-"));
  t.after(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  const stateStore = new AuthStateStore(path.join(tmpDir, "auth-state.json"));
  await stateStore.patch({
    installationId: "inst-sidecar-001",
    userToken: "user-token-secret",
    deviceKey: "device-key-secret",
    authMode: "personal-device",
    deviceId: 9,
  });

  const config = {
    controlPlaneBaseUrl: "https://control-plane.test",
    localGatewayWsUrl: "ws://127.0.0.1:18789",
    sidecarHost: "127.0.0.1",
    sidecarPort: 21736,
    sidecarAuthToken: "sidecar-auth-secret",
    allowRemoteAccess: false,
    startGatewayOnBoot: false,
    startBridgeOnBoot: false,
    autoBootstrapDevice: false,
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

  const server = new HttpSidecarServer(createDeps(config, stateStore));

  const unauthorizedResponse = {
    statusCode: 200,
    headers: {},
    body: "",
    setHeader(name, value) {
      this.headers[name] = value;
    },
    end(chunk = "") {
      this.body = chunk;
    },
  };
  const unauthorized = await server.ensureRequestAuthorized(
    {
      headers: {},
    },
    unauthorizedResponse,
  );
  assert.equal(unauthorized, false);
  assert.equal(unauthorizedResponse.statusCode, 401);
  assert.match(unauthorizedResponse.body, /Unauthorized sidecar request/);

  const authorizedResponse = {
    statusCode: 200,
    headers: {},
    body: "",
    setHeader(name, value) {
      this.headers[name] = value;
    },
    end(chunk = "") {
      this.body = chunk;
    },
  };
  const authorized = await server.ensureRequestAuthorized(
    {
      headers: {
        authorization: "Bearer sidecar-auth-secret",
      },
    },
    authorizedResponse,
  );
  assert.equal(authorized, true);
  assert.equal(authorizedResponse.body, "");

  const publicState = toPublicAuthState(await stateStore.read(), {
    configuredAuthToken: config.sidecarAuthToken,
  });
  assert.equal(publicState.installationId, "inst-sidecar-001");
  assert.equal(publicState.hasUserToken, true);
  assert.equal(publicState.hasDeviceKey, true);
  assert.equal(publicState.sidecarAuthTokenConfigured, true);
  assert.equal("userToken" in publicState, false);
  assert.equal("deviceKey" in publicState, false);
  assert.equal("sidecarAuthToken" in publicState, false);
});

test("http sidecar server refuses non-loopback bind unless explicitly allowed", async (t) => {
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), "qeeclaw-sidecar-remote-"));
  t.after(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  const stateStore = new AuthStateStore(path.join(tmpDir, "auth-state.json"));
  const config = {
    controlPlaneBaseUrl: "https://control-plane.test",
    localGatewayWsUrl: "ws://127.0.0.1:18789",
    sidecarHost: "0.0.0.0",
    sidecarPort: 21936,
    sidecarAuthToken: "sidecar-auth-secret",
    allowRemoteAccess: false,
    startGatewayOnBoot: false,
    startBridgeOnBoot: false,
    autoBootstrapDevice: false,
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

  const server = new HttpSidecarServer(createDeps(config, stateStore));
  await assert.rejects(
    () => server.start(),
    /Refusing to bind sidecar HTTP server to non-loopback host/,
  );
});
