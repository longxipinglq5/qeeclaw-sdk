import assert from "node:assert/strict";

import { createQeeClawClient } from "../dist/index.js";

const calls = [];
const fetch = async (input, init = {}) => {
  calls.push({
    url: String(input),
    method: init.method,
    headers: Object.fromEntries(new Headers(init.headers).entries()),
    body: init.body ? JSON.parse(String(init.body)) : undefined,
  });

  return new Response(JSON.stringify({
    created: 123,
    data: [{
      url: "https://example.test/image.png",
      b64_json: "abc123",
      revised_prompt: "clean prompt",
    }],
  }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
};

const client = createQeeClawClient({
  baseUrl: "https://platform.example.test",
  token: "test-token",
  fetch,
});

assert.equal(typeof client.models.images.generate, "function");
assert.equal(typeof client.models.images.stream, "function");

const image = await client.models.images.generate({
  prompt: "生成一张产品图",
  model: "gpt-image-2",
  size: "16:9",
  responseFormat: "url",
});

assert.equal(calls.length, 1);
assert.equal(calls[0].url, "https://platform.example.test/api/llm/images/generations");
assert.equal(calls[0].method, "POST");
assert.equal(calls[0].headers.authorization, "Bearer test-token");
assert.deepEqual(calls[0].body, {
  prompt: "生成一张产品图",
  model: "gpt-image-2",
  size: "16:9",
  response_format: "url",
});
assert.equal(image.data[0].url, "https://example.test/image.png");
assert.equal(image.data[0].b64Json, "abc123");
assert.equal(image.data[0].revisedPrompt, "clean prompt");

calls.length = 0;
await client.models.generateImage({
  prompt: "兼容旧入口",
  model: "gpt-image-2",
});
assert.equal(calls.length, 1);
assert.equal(calls[0].body.prompt, "兼容旧入口");

calls.length = 0;
await client.models.images.generate({
  prompt: "使用后端默认图片模型",
});
assert.equal(calls.length, 1);
assert.deepEqual(calls[0].body, {
  prompt: "使用后端默认图片模型",
  response_format: "url",
});
assert.equal(Object.hasOwn(calls[0].body, "model"), false);

console.log("models.images API contract ok");
