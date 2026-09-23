import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { CassiEntityClient, stableRequestId } from "./entity-client.js";
import { CassiEntityAdapter } from "./adapter.js";
import { apply as applyHost } from "./index.js";
import { apply as applyClient, createCassiRpc } from "./client.js";


const calls = [];
const seenMessages = new Set();
const typedTurnEvents = new Map();
let sourceToolResult;
function brokerContext({ nestedResult, approval } = {}) {
  const definitions = new Map();
  const nestedCalls = [];
  definitions.set("fixture_tool", {
    name: "fixture_tool",
    async execute(args) {
      return { echoed: args.value };
    },
  });
  const context = {
    connection: { rpc: { handle() {} } },
    llm: { registerAdapter() {} },
    get(name) {
      return name === "approval" ? approval : undefined;
    },
    tools: {
      register(definition) {
        definitions.set(definition.name, definition);
      },
      get(name) {
        return definitions.get(name);
      },
      async execute(input) {
        nestedCalls.push(input);
        if (nestedResult) return nestedResult(input);
        const definition = definitions.get(input.name);
        assert.ok(definition);
        const value = await definition.execute(input.arguments, input);
        return { isError: false, value, content: [{ type: "text", text: JSON.stringify(value) }] };
      },
    },
  };
  return { context, definitions, nestedCalls };
}

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
    } else if (request.content === "Read the exact fixture source, then summarize it.") {
      const pending = {
        call_id: "call-source-1",
        name: "cassi_read_source",
        arguments: { path: "source.md", max_bytes: 8_192 },
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
        field_state_sha256: "field-source-rev",
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
    const result = request.results[0];
    const pending = result.call_id === "call-fixture-1"
      ? { call_id: "call-fixture-1", name: "fixture_tool", arguments: { value: 7 } }
      : { call_id: "call-source-1", name: "cassi_read_source", arguments: { path: "source.md", max_bytes: 8_192 } };
    assert.deepEqual(
      { call_id: result.call_id, name: result.name, arguments: result.arguments },
      pending,
    );
    if (result.call_id === "call-source-1") sourceToolResult = result;
    const turn = {
      schema: "cassi.field-brain.turn.v1",
      turn_id: turnId,
      request_id: result.call_id === "call-source-1" ? "source-request" : "fixture-request",
      status: "committed",
      response: result.call_id === "call-source-1"
        ? "The exact source bytes were admitted and interpreted."
        : "The fixture tool result was incorporated.",
      model: { id: "test-brain", sha256: "test" },
      usage: { prompt_tokens: 5, completion_tokens: 6 },
      field_state_sha256: result.call_id === "call-source-1" ? "field-source-rev-2" : "field-rev-2",
    };
    typedTurnEvents.set(turnId, [
      { id: "1", kind: "turn-accepted", payload: { turn_id: turnId } },
      { id: "2", kind: "turn-tool-proposed", payload: pending },
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
const staleContinuationMessages = [
  ...toolContinuationMessages,
  {
    role: "user",
    content: [{ type: "text", text: "Now answer a new question without reusing the previous tool result." }],
    source: { kind: "user" },
  },
];
const staleContinuationChunks = [];
for await (const chunk of adapter.stream({
  provider: "cassi-entity",
  model: "cassi-entity",
  sessionId: "session-tool",
  tools: toolSchema,
  messages: staleContinuationMessages,
})) staleContinuationChunks.push(chunk);
assert.equal(staleContinuationChunks.at(-1).reason.kind, "stop");
assert.equal(
  staleContinuationChunks.find((chunk) => chunk.type === "text-delta")?.text,
  "The typed continuing entity received this turn.",
);
const sourceHome = await mkdtemp(join(tmpdir(), "cassi-dsh-source-"));
const alternateHome = await mkdtemp(join(tmpdir(), "cassi-dsh-source-alt-"));
const workOrderHome = await mkdtemp(join(tmpdir(), "cassi-dsh-work-order-"));
try {
  const sourceBytes = Buffer.from("A source line.\nA second source line.\n", "utf8");
  await writeFile(join(sourceHome, "source.md"), sourceBytes);
  await writeFile(join(alternateHome, "source.md"), Buffer.from("A different source.\n", "utf8"));
  const registeredTools = [];
  applyHost({
    connection: { rpc: { handle() {} } },
    llm: { registerAdapter() {} },
    tools: { register(definition) { registeredTools.push(definition); } },
  }, {
    token: "x".repeat(32),
    sourceRoots: [sourceHome],
  });
  const sourceTool = registeredTools.find((definition) => definition.name === "cassi_read_source");
  assert.ok(sourceTool);
  const sourceResult = await sourceTool.execute(
    { path: "source.md", start_byte: 0, max_bytes: 8_192 },
    { callId: "source-call", signal: new AbortController().signal },
  );
  assert.equal(sourceResult.source_path, "source.md");
  assert.equal(sourceResult.source_byte_length, sourceBytes.byteLength);
  assert.equal(sourceResult.source_sha256, createHash("sha256").update(sourceBytes).digest("hex"));
  assert.deepEqual(Buffer.from(sourceResult.content_base64, "base64"), sourceBytes);
  const previousConfiguredRoots = process.env.CASSI_SOURCE_ROOTS;
  try {
    process.env.CASSI_SOURCE_ROOTS = alternateHome;
    const configuredTools = [];
    applyHost({
      connection: { rpc: { handle() {} } },
      llm: { registerAdapter() {} },
      tools: { register(definition) { configuredTools.push(definition); } },
    }, { token: "x".repeat(32), sourceRoots: [sourceHome] });
    const configuredSourceTool = configuredTools.find((definition) => definition.name === "cassi_read_source");
    assert.ok(configuredSourceTool);
    const configuredResult = await configuredSourceTool.execute(
      { path: "source.md", max_bytes: 8_192 },
      { callId: "source-configured", signal: new AbortController().signal },
    );
    assert.equal(configuredResult.source_sha256, sourceResult.source_sha256);
  } finally {
    if (previousConfiguredRoots === undefined) delete process.env.CASSI_SOURCE_ROOTS;
    else process.env.CASSI_SOURCE_ROOTS = previousConfiguredRoots;
  }

  await assert.rejects(
    sourceTool.execute(
      { path: "../source.md", max_bytes: 8_192 },
      { callId: "source-escape", signal: new AbortController().signal },
    ),
    /unavailable|outside/,
  );
  const previousSourceRoots = process.env.CASSI_SOURCE_ROOTS;
  try {
    delete process.env.CASSI_SOURCE_ROOTS;
    const noRootTools = [];
    applyHost({
      connection: { rpc: { handle() {} } },
      llm: { registerAdapter() {} },
      tools: { register(definition) { noRootTools.push(definition); } },
    }, { token: "x".repeat(32), sourceRoots: [] });
    assert.equal(noRootTools.find((definition) => definition.name === "cassi_read_source"), undefined);

    process.env.CASSI_SOURCE_ROOTS = sourceHome;
    const environmentTools = [];
    applyHost({
      connection: { rpc: { handle() {} } },
      llm: { registerAdapter() {} },
      tools: { register(definition) { environmentTools.push(definition); } },
    }, { token: "x".repeat(32) });
    const environmentSourceTool = environmentTools.find((definition) => definition.name === "cassi_read_source");
    assert.ok(environmentSourceTool);
    const environmentResult = await environmentSourceTool.execute(
      { path: "source.md", max_bytes: 8_192 },
      { callId: "source-environment", signal: new AbortController().signal },
    );
    assert.equal(environmentResult.source_sha256, sourceResult.source_sha256);
  } finally {
    if (previousSourceRoots === undefined) delete process.env.CASSI_SOURCE_ROOTS;
    else process.env.CASSI_SOURCE_ROOTS = previousSourceRoots;
  }

  const ledgerPath = join(workOrderHome, "ledger.jsonl");
  const firstBrokerHost = brokerContext();
  applyHost(firstBrokerHost.context, {
    token: "x".repeat(32),
    workOrderTools: ["fixture_tool"],
    workOrderLedgerFile: ledgerPath,
  });
  const workOrderTool = firstBrokerHost.definitions.get("cassi_execute_work_order");
  assert.ok(workOrderTool);
  const workOrder = {
    operation_id: "op-fixture-1",
    program_id: "program-fixture",
    operation: "read the fixture value",
    tool_name: "fixture_tool",
    arguments: { value: 7 },
    effect_class: "read-only",
    field_predecessor: "field-rev-1",
    authority: { scope: "fixture" },
    budget: { calls: 1 },
    expected_output: { kind: "echo" },
  };
  const parentToken = Symbol("parent-token");
  const workOrderExec = {
    callId: "outer-call-1",
    token: parentToken,
    agent: "agent-fixture",
    signal: new AbortController().signal,
    deferContext() {},
  };
  const workOrderResult = await workOrderTool.execute(workOrder, workOrderExec);
  assert.equal(workOrderResult.status, "succeeded");
  assert.equal(workOrderResult.effect_disposition, "completed");
  assert.equal(firstBrokerHost.nestedCalls.length, 1);
  assert.equal(firstBrokerHost.nestedCalls[0].parent, parentToken);
  assert.deepEqual(firstBrokerHost.nestedCalls[0].arguments, { value: 7 });
  const inProcessReplay = await workOrderTool.execute(workOrder, workOrderExec);
  assert.deepEqual(inProcessReplay, workOrderResult);
  assert.equal(firstBrokerHost.nestedCalls.length, 1);

  const restartedBrokerHost = brokerContext();
  applyHost(restartedBrokerHost.context, {
    token: "x".repeat(32),
    workOrderTools: ["fixture_tool"],
    workOrderLedgerFile: ledgerPath,
  });
  const restartedResult = await restartedBrokerHost.definitions.get("cassi_execute_work_order").execute(
    workOrder,
    { ...workOrderExec, callId: "outer-call-after-restart" },
  );
  assert.deepEqual(restartedResult, workOrderResult);
  assert.equal(restartedBrokerHost.nestedCalls.length, 0);
  await assert.rejects(
    workOrderTool.execute({ ...workOrder, arguments: { value: 8 } }, workOrderExec),
    /different content/,
  );
  await assert.rejects(
    workOrderTool.execute({ ...workOrder, operation_id: "op-outside", tool_name: "not_configured" }, workOrderExec),
    /outside the configured Harness scope/,
  );

  let approvalRequest;
  const approvalHost = brokerContext({
    approval: {
      async request(request) {
        approvalRequest = request;
        return "rejected";
      },
    },
  });
  applyHost(approvalHost.context, {
    token: "x".repeat(32),
    workOrderTools: ["fixture_tool"],
    approvalRequiredTools: ["fixture_tool"],
    workOrderLedgerFile: join(workOrderHome, "approval-ledger.jsonl"),
  });
  const approvalResult = await approvalHost.definitions.get("cassi_execute_work_order").execute(
    { ...workOrder, operation_id: "op-approval", effect_class: "workspace-write" },
    workOrderExec,
  );
  assert.equal(approvalResult.status, "approval-rejected");
  assert.equal(approvalRequest.toolName, "fixture_tool");
  assert.equal(approvalHost.nestedCalls.length, 0);

  const unavailableHost = brokerContext();
  applyHost(unavailableHost.context, {
    token: "x".repeat(32),
    workOrderTools: ["fixture_tool"],
    workOrderLedgerFile: join(workOrderHome, "unavailable-ledger.jsonl"),
  });
  const unavailableResult = await unavailableHost.definitions.get("cassi_execute_work_order").execute(
    { ...workOrder, operation_id: "op-approval-unavailable", effect_class: "external" },
    workOrderExec,
  );
  assert.equal(unavailableResult.status, "approval-unavailable");
  assert.equal(unavailableHost.nestedCalls.length, 0);

  const cancellation = new AbortController();
  const cancellationHost = brokerContext({
    nestedResult: async () => {
      cancellation.abort();
      return { isError: true, error: { code: "ABORTED", message: "fixture cancellation" } };
    },
  });
  applyHost(cancellationHost.context, {
    token: "x".repeat(32),
    workOrderTools: ["fixture_tool"],
    workOrderLedgerFile: join(workOrderHome, "cancellation-ledger.jsonl"),
  });
  const cancelledResult = await cancellationHost.definitions.get("cassi_execute_work_order").execute(
    { ...workOrder, operation_id: "op-cancelled" },
    { ...workOrderExec, signal: cancellation.signal },
  );
  assert.equal(cancelledResult.status, "unknown-effect");
  assert.equal(cancelledResult.effect_disposition, "unknown");


  const sourceUser = {
    id: "user-source-1",
    role: "user",
    content: [{ type: "text", text: "Read the exact fixture source, then summarize it." }],
  };
  const sourceSchema = [{
    name: "cassi_read_source",
    description: "Read exact bounded source bytes from the configured Cassi source scope.",
    parameters: {
      path: { type: "string", required: true },
      start_byte: { type: "integer" },
      max_bytes: { type: "integer" },
    },
  }];
  const sourceChunks = [];
  for await (const chunk of adapter.stream({
    provider: "cassi-entity",
    model: "cassi-entity",
    sessionId: "session-source",
    tools: sourceSchema,
    messages: [sourceUser],
  })) sourceChunks.push(chunk);
  const sourceCall = sourceChunks.find((chunk) => chunk.type === "block-end" && chunk.block?.type === "tool-call");
  const sourceFinish = sourceChunks.at(-1);
  assert.equal(sourceFinish.reason.kind, "tool-calls");
  assert.equal(sourceCall.block.id, "call-source-1");
  const sourceContent = sourceTool.output.render(
    JSON.parse(sourceCall.block.arguments),
    sourceResult,
  );
  const sourceContinuationMessages = [
    sourceUser,
    {
      role: "assistant",
      content: [sourceCall.block],
      source: {
        provider: "cassi-entity",
        model: "cassi-entity",
        replayState: sourceFinish.replayState,
      },
    },
    {
      role: "user",
      content: [{
        type: "tool-result",
        toolCallId: "call-source-1",
        content: sourceContent,
        isError: false,
      }],
      source: { kind: "tool", callId: "call-source-1" },
    },
  ];
  const sourceContinuedChunks = [];
  for await (const chunk of adapter.stream({
    provider: "cassi-entity",
    model: "cassi-entity",
    sessionId: "session-source",
    tools: sourceSchema,
    messages: sourceContinuationMessages,
  })) sourceContinuedChunks.push(chunk);
  assert.equal(sourceContinuedChunks.at(-1).reason.kind, "stop");
  assert.equal(
    sourceContinuedChunks.find((chunk) => chunk.type === "text-delta")?.text,
    "The exact source bytes were admitted and interpreted.",
  );
  assert.deepEqual(sourceToolResult.content, sourceContent);
  assert.ok(sourceToolResult.content[0].text.includes(sourceResult.source_sha256));
  assert.ok(sourceToolResult.content[0].text.includes(sourceResult.content_base64));
} finally {
  await rm(sourceHome, { recursive: true, force: true });
  await rm(alternateHome, { recursive: true, force: true });
  await rm(workOrderHome, { recursive: true, force: true });
}
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
