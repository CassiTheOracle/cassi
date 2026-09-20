import assert from "node:assert/strict";
import { CassiEntityClient, stableRequestId } from "./entity-client.js";
import { CassiEntityAdapter } from "./adapter.js";
import { apply as applyClient, createCassiRpc } from "./client.js";


const calls = [];
const seenMessages = new Set();
const typedTurnEvents = new Map();
const fetchImpl = async (url, init) => {
  calls.push({ url: String(url), init });
  const parsed = new URL(url);
  const path = parsed.pathname;
  let body;
  if (path === "/v1/turns") {
    const request = JSON.parse(init.body);
    if (request.content === "Use the fixture tool, then summarize it.") {
      const pending = {
        call_id: "call-fixture-1",
        name: "fixture_tool",
        arguments: { value: 7 },
      };
      const turn = {
        schema: "cassi.field-brain.turn.v1",
        turn_id: request.turn_id,
        request_id: request.request_id,
        conversation_id: request.conversation_id,
        project_id: request.project_id,
        status: "awaiting-tool",
        pending_tool: pending,
        model: { id: "test-brain", sha256: "test" },
        usage: { prompt_tokens: 3, completion_tokens: 4 },
        field_state_sha256: "field-rev",
      };
      typedTurnEvents.set(request.turn_id, [
        { id: "1", kind: "turn-accepted", payload: { turn_id: request.turn_id, request_id: request.request_id } },
        { id: "2", kind: "turn-tool-proposed", payload: pending },
      ]);
      body = { ...turn, idempotent_replay: false };
    } else {
      const turn = {
        schema: "cassi.field-brain.turn.v1",
        turn_id: request.turn_id,
        request_id: request.request_id,
        conversation_id: request.conversation_id,
        project_id: request.project_id,
        status: "committed",
        response: "The typed continuing entity received this turn.",
        model: { id: "test-brain", sha256: "test" },
        usage: { prompt_tokens: 3, completion_tokens: 4 },
        field_state_sha256: "field-rev",
      };
      typedTurnEvents.set(request.turn_id, [
        { id: "1", kind: "turn-accepted", payload: { turn_id: request.turn_id, request_id: request.request_id } },
        { id: "2", kind: "turn-committed", payload: turn },
      ]);
      body = { ...turn, idempotent_replay: false };
    }
  } else if (path === "/v1/auxiliary") {
    const request = JSON.parse(init.body);
    assert.equal(request.purpose, "session-title");
    body = {
      schema: "cassi.field-brain.auxiliary.v1",
      request_id: request.request_id,
      purpose: request.purpose,
      response: "Auxiliary title from the continuing entity.",
      model: { id: "test-brain", sha256: "test" },
      usage: { prompt_tokens: 2, completion_tokens: 3 },
      learning: false,
    };
  } else if (/^\/v1\/turns\/[^/]+\/tool-results$/.test(path)) {
    const request = JSON.parse(init.body);
    const turnId = decodeURIComponent(path.split("/")[3]);
    assert.equal(request.results.length, 1);
    assert.equal(request.results[0].call_id, "call-fixture-1");
    const turn = {
      schema: "cassi.field-brain.turn.v1",
      turn_id: turnId,
      request_id: "fixture-request",
      status: "committed",
      response: "The fixture tool result was incorporated.",
      model: { id: "test-brain", sha256: "test" },
      usage: { prompt_tokens: 5, completion_tokens: 6 },
      field_state_sha256: "field-rev-2",
    };
    typedTurnEvents.set(turnId, [
      { id: "1", kind: "turn-accepted", payload: { turn_id: turnId } },
      { id: "2", kind: "turn-tool-proposed", payload: { call_id: "call-fixture-1", name: "fixture_tool" } },
      { id: "3", kind: "turn-tool-result-admitted", payload: { turn_id: turnId } },
      { id: "4", kind: "turn-committed", payload: turn },
    ]);
    body = { ...turn, idempotent_replay: false };
  } else if (/^\/v1\/turns\/[^/]+\/events$/.test(path)) {
    const turnId = decodeURIComponent(path.split("/")[3]);
    const events = typedTurnEvents.get(turnId) ?? [];
    const stream = events
      .filter((event) => Number(event.id) > Number(parsed.searchParams.get("after") ?? "0"))
      .map((event) => `id: ${event.id}\nevent: ${event.kind}\ndata: ${JSON.stringify({ id: event.id, kind: event.kind, payload: event.payload })}\n\n`)
      .join("");
    return new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } });
  } else if (path === "/v1/messages") {
    const request = JSON.parse(init.body);
    const replay = seenMessages.has(request.request_id);
    seenMessages.add(request.request_id);
    body = {
      response: "The continuing entity received this turn.",
      model: { id: "test-brain", sha256: "test" },
      request_id: request.request_id,
      idempotent_replay: replay,
    };
  } else if (path === "/v1/state") {
    body = { entity_id: "cassi", field_state_sha256: "field-rev" };
  } else {
    body = { programs: [] };
  }
  return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
};

const client = new CassiEntityClient({ baseUrl: "http://127.0.0.1:8090", token: "x".repeat(32), fetchImpl });
assert.equal(stableRequestId("test", { a: 1 }), stableRequestId("test", { a: 1 }));
assert.notEqual(stableRequestId("test", { a: 1 }), stableRequestId("test", { a: 2 }));
assert.equal((await client.state()).entity_id, "cassi");
const adapter = new CassiEntityAdapter(client);
const auxiliaryChunks = [];
for await (const chunk of adapter.stream({
  provider: "cassi-entity",
  model: "cassi-entity",
  sessionId: "session-a",
  purpose: "session-title",
  system: "Return a concise title.",
  messages: [{ role: "user", content: [{ type: "text", text: "Hello Cassi" }] }],
})) auxiliaryChunks.push(chunk);
assert.equal(auxiliaryChunks.at(-1).reason.kind, "stop");
assert.equal(
  auxiliaryChunks.find((chunk) => chunk.type === "text-delta")?.text,
  "Auxiliary title from the continuing entity.",
);
const chunks = [];
for await (const chunk of adapter.stream({ provider: "cassi-entity", model: "cassi-entity", sessionId: "session-a", messages: [{ id: "user-1", role: "user", content: [{ type: "text", text: "Hello Cassi" }], source: { kind: "user" } }] })) chunks.push(chunk);
assert.equal(chunks.at(-1).reason.kind, "stop");
assert.deepEqual(chunks.find((chunk) => chunk.type === "usage")?.usage, { inputTokens: 3, outputTokens: 4 });
const turnCalls = calls.filter((call) => new URL(call.url).pathname === "/v1/turns");
assert.equal(turnCalls.length, 1);
const turnEventCalls = calls.filter((call) => new URL(call.url).pathname.endsWith("/events"));
assert.equal(turnEventCalls.length, 1);
const toolUser = {
  id: "user-tool-1",
  role: "user",
  content: [{ type: "text", text: "Use the fixture tool, then summarize it." }],
};
const toolHarnessContext = [
  toolUser,
  {
    role: "user",
    content: [{ type: "text", text: "Injected workspace instructions." }],
    source: { kind: "agent-instructions" },
  },
  {
    role: "user",
    content: [{ type: "text", text: "Injected runtime policy." }],
    source: { kind: "plugin" },
  },
];
const toolSchema = [{
  name: "fixture_tool",
  description: "Return the fixture value.",
  parameters: {},
}];
const toolChunks = [];
for await (const chunk of adapter.stream({
  provider: "cassi-entity",
  model: "cassi-entity",
  sessionId: "session-tool",
  tools: toolSchema,
  messages: toolHarnessContext,
})) toolChunks.push(chunk);
const toolCall = toolChunks.find((chunk) => chunk.type === "block-end" && chunk.block?.type === "tool-call");
const toolFinish = toolChunks.at(-1);
assert.equal(toolFinish.reason.kind, "tool-calls");
assert.deepEqual(toolCall.block, {
  type: "tool-call",
  id: "call-fixture-1",
  name: "fixture_tool",
  arguments: '{"value":7}',
});
const toolContinuationMessages = [
  toolUser,
  {
    role: "assistant",
    content: [toolCall.block],
    source: {
      provider: "cassi-entity",
      model: "cassi-entity",
      replayState: toolFinish.replayState,
    },
  },
  {
    role: "user",
    content: [{
      type: "tool-result",
      toolCallId: "call-fixture-1",
      content: [{ type: "text", text: "fixture value is 7" }],
      isError: false,
    }],
    source: { kind: "tool", callId: "call-fixture-1" },
  },
];
const continuedChunks = [];
for await (const chunk of adapter.stream({
  provider: "cassi-entity",
  model: "cassi-entity",
  sessionId: "session-tool",
  tools: toolSchema,
  messages: toolContinuationMessages,
})) continuedChunks.push(chunk);
assert.equal(continuedChunks.at(-1).reason.kind, "stop");
assert.equal(
  continuedChunks.find((chunk) => chunk.type === "text-delta")?.text,
  "The fixture tool result was incorporated.",
);
assert.equal(calls.filter((call) => new URL(call.url).pathname === "/v1/turns").length, 2);
assert.equal(calls.filter((call) => new URL(call.url).pathname.endsWith("/tool-results")).length, 1);
assert.equal(calls.filter((call) => new URL(call.url).pathname.endsWith("/events")).length, 3);
const replayRequest = {
  requestId: "replay-smoke",
  conversationId: "dsh:replay",
  projectId: "cassi-workspace",
  content: "Replay this exact request.",
  observedAt: "2026-09-19T00:00:00Z",
};
const firstReplay = await client.sendMessage(replayRequest);
const secondReplay = await client.sendMessage(replayRequest);
assert.equal(firstReplay.idempotent_replay, false);
assert.equal(secondReplay.idempotent_replay, true);
const messageCalls = calls.filter((call) => new URL(call.url).pathname === "/v1/messages");
assert.equal(messageCalls.length, 2);
assert.match(messageCalls[0].init.headers.authorization, /^Bearer /);
const rpc = createCassiRpc(async (_url, init) => {
  const request = JSON.parse(init.body);
  return new Response(JSON.stringify({ rpcId: request.rpcId, result: { endpoint: request.method } }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
});
assert.deepEqual(await rpc.call("state"), { endpoint: "state" });
await assert.rejects(rpc.call("../state"), /invalid segment/);
let provided;
applyClient({
  connection: { rpc: { call: async (channel, endpoint) => ({ channel, endpoint }) } },
  provide(name, value) { provided = { name, value }; },
});
assert.equal(provided.name, "cassi");
assert.deepEqual(await provided.value.call("programs"), { channel: "/cassi", endpoint: "programs" });

console.log(JSON.stringify({ ok: true, calls: calls.length, chunks: chunks.length }));
