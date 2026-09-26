/**
 * Adapter smoke test against the real `omp acp` server.
 *
 * Exercises the whole provider surface end to end without touching any of the
 * user's own sessions: it creates one throwaway session, drives it through the
 * adapter, and removes it from the store afterwards.
 *
 *   node smoke.mjs
 */
import { mkdtempSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { join } from "node:path";
import { AcpConnection } from "./acp-client.js";
import { NEW_SESSION_MODEL, OmpAcpAdapter, harnessUsage, newestUserText, toolRecord, toolUpdateRecord } from "./adapter.js";
import { OmpAcpSessions, permissionToolName, resolvePermission, selectPermission } from "./omp-sessions.js";

const EXECUTABLE = process.env.OMP_ACP_EXECUTABLE ?? "C:\\Users\\Carina\\.bun\\bin\\omp.exe";
const STORE = join(homedir(), ".omp", "agent", "sessions");
const PROVIDER = "omp";
const failures = [];

// A rejection nobody awaited is a defect in whatever left it dangling: name it
// and fail the run, rather than dying without a summary.
process.on("unhandledRejection", (reason) => {
  failures.push(`unhandled rejection (${`${reason?.message ?? reason}`.slice(0, 120)})`);
  process.stdout.write(`\nUNHANDLED REJECTION: ${reason?.stack ?? reason}\n`);
});

const log = (level, message) => process.stdout.write(`  [${level}] ${message}\n`);

function check(label, ok, detail = "") {
  process.stdout.write(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}\n`);
  if (!ok) failures.push(label);
}

/** Every `*.jsonl` in the store, as `directory/file`, for diffing. */
function sessionFileNames() {
  const names = [];
  for (const entry of readdirSync(STORE, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    for (const file of readdirSync(join(STORE, entry.name))) if (file.endsWith(".jsonl")) names.push(`${entry.name}/${file}`);
  }
  return names;
}

function removeSession(sessionId) {
  let removed = 0;
  for (const entry of readdirSync(STORE, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const directory = join(STORE, entry.name);
    for (const file of readdirSync(directory)) {
      if (!file.endsWith(`_${sessionId}.jsonl`)) continue;
      rmSync(join(directory, file), { force: true });
      removed += 1;
    }
  }
  return removed;
}

async function promptOnce(executable, cwd, text) {
  const conn = new AcpConnection({ executable });
  conn.start();
  try {
    await conn.request("initialize", { protocolVersion: 1, clientCapabilities: {} });
    const created = await conn.request("session/new", { cwd, mcpServers: [] });
    await conn.request("session/prompt", { sessionId: created.sessionId, prompt: [{ type: "text", text }] }, { timeoutMs: 300_000 });
    return created.sessionId;
  } finally {
    conn.dispose();
  }
}

/**
 * Remove a scratch directory, waiting out the moment Windows keeps a handle on
 * it after the processes that used it as their working directory exit.
 */
async function removeDirWithRetry(directory, budgetMs = 15_000) {
  const deadline = Date.now() + budgetMs;
  for (;;) {
    try {
      rmSync(directory, { recursive: true, force: true });
      return;
    } catch (error) {
      if (Date.now() >= deadline) throw error;
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
  }
}

async function drain(stream) {
  const chunks = [];
  for await (const chunk of stream) chunks.push(chunk);
  return chunks;
}

function textOf(chunks) {
  return chunks.filter((chunk) => chunk.type === "text-delta").map((chunk) => chunk.text).join("");
}

function messageTextOf(message) {
  return (Array.isArray(message?.content) ? message.content : []).filter((block) => block?.type === "text").map((block) => block.text).join("\n");
}

/** Every user-role text the session file recorded, oldest first. */
function sessionUserTexts(sessionId) {
  for (const entry of readdirSync(STORE, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const directory = join(STORE, entry.name);
    const file = readdirSync(directory).find((name) => name.endsWith(`_${sessionId}.jsonl`));
    if (file === undefined) continue;
    const texts = [];
    for (const line of readFileSync(join(directory, file), "utf8").split("\n")) {
      if (line.trim().length === 0) continue;
      let row;
      try {
        row = JSON.parse(line);
      } catch {
        continue;
      }
      if (row?.message?.role !== "user") continue;
      texts.push(messageTextOf(row.message));
    }
    return texts;
  }
  return [];
}

/** A request shaped like the harness's own: the user's message plus injected context. */
const injectedRequest = [
  { role: "user", source: { kind: "user", rpcId: "r1" }, content: [{ type: "text", text: "Reply with exactly: pong" }] },
  { role: "user", source: { kind: "agent-instructions", form: "instructions" }, content: [{ type: "text", text: "<system-reminder>\nworkspace instructions\n" }] },
  { role: "user", source: { kind: "plugin", plugin: "@deepseek-ai/dsh-system-prompt", form: "snapshot" }, content: [{ type: "text", text: "Current runtime context. This snapshot supersedes earlier runtime-context snapshots." }] },
];

const sessionCwd = mkdtempSync(join(tmpdir(), "omp-acp-smoke-session-"));
const auxiliaryCwd = mkdtempSync(join(tmpdir(), "omp-acp-smoke-aux-"));
const pool = new OmpAcpSessions({ executable: EXECUTABLE, cwd: sessionCwd, auxiliaryCwd, onLog: log });
const adapter = new OmpAcpAdapter(pool, { providerName: "Oh My Pi", newSessionCwd: sessionCwd });
const createdSessions = new Set();
let sessionId;

try {
  process.stdout.write(`creating throwaway omp session in ${sessionCwd}\n`);
  sessionId = await promptOnce(EXECUTABLE, sessionCwd, "Reply with exactly: pong");
  createdSessions.add(sessionId);

  const models = await adapter.listModels(PROVIDER);
  const listed = models.find((model) => model.id === sessionId);
  const freshEntry = models.find((model) => model.id === NEW_SESSION_MODEL);
  check("listModels advertises the live session store", models.length > 0, `${models.length} sessions`);
  check("listModels includes the throwaway session", listed !== undefined);
  check("listed model carries id/name/description", listed !== undefined && listed.provider === PROVIDER && listed.id === sessionId && listed.name.length > 0 && listed.description.includes(sessionCwd), JSON.stringify(listed));
  check("listModels offers a fresh-session entry", freshEntry !== undefined && freshEntry.description.includes(sessionCwd), JSON.stringify(freshEntry));
  check("fresh-session entry is not a session id", NEW_SESSION_MODEL !== sessionId && !models.some((model) => model.id === NEW_SESSION_MODEL && model.id !== NEW_SESSION_MODEL));

  const resolved = await adapter.resolveModel(PROVIDER, sessionId);
  check("resolveModel returns exact identity", resolved.id === sessionId && resolved.provider === PROVIDER && resolved.inputModalities[0] === "text", resolved.name);
  const resolvedFresh = await adapter.resolveModel(PROVIDER, NEW_SESSION_MODEL);
  check("resolveModel describes the fresh-session entry", resolvedFresh.id === NEW_SESSION_MODEL && resolvedFresh.defaultMaxTokens > 0, resolvedFresh.name);

  const chunks = await drain(adapter.stream({
    provider: PROVIDER,
    model: sessionId,
    messages: injectedRequest,
  }));
  const types = [...new Set(chunks.map((chunk) => chunk.type))];
  const answer = textOf(chunks).trim();
  const finish = chunks.at(-1);
  const usage = chunks.find((chunk) => chunk.type === "usage")?.usage;
  check("prompt stream emits block/text/finish chunks", types.includes("block-start") && types.includes("text-delta") && types.includes("block-end") && finish?.type === "finish", types.join(","));
  check("prompt stream carried the session answer", /pong/i.test(answer), JSON.stringify(answer.slice(0, 120)));
  check("prompt stream reported token usage", Number.isFinite(usage?.outputTokens) && usage.outputTokens > 0 && Number.isFinite(usage.inputTokens), JSON.stringify(usage));
  check("prompt stream finished with stop", finish?.reason?.kind === "stop", JSON.stringify(finish?.reason));

  const received = sessionUserTexts(sessionId);
  check("live session received exactly the user text", received.at(-1) === "Reply with exactly: pong", JSON.stringify(received.at(-1)?.slice(0, 120)));
  check("live session received no harness-injected context", !received.some((text) => /system-reminder|runtime context/i.test(text)), `${received.length} user messages in the session`);
  check("selector ignores harness-injected user messages", injectedRequest.some((message) => /system-reminder/.test(messageTextOf(message))) && newestUserText(injectedRequest) === "Reply with exactly: pong", JSON.stringify(newestUserText(injectedRequest)));
  check("selector refuses a request with only harness context", newestUserText(injectedRequest.slice(1)) === "");

  // A fresh-session entry creates exactly one oh-my-pi session for the harness
  // conversation and then continues it — never one session per message.
  const harnessKey = "smoke-conversation-1";
  const freshUser = (text) => [{ role: "user", source: { kind: "user" }, content: [{ type: "text", text }] }];
  const idsBefore = new Set((await adapter.listModels(PROVIDER)).map((model) => model.id));
  const firstFresh = await drain(adapter.stream({ provider: PROVIDER, model: NEW_SESSION_MODEL, sessionId: harnessKey, messages: freshUser("Reply with exactly: fresh-one") }));
  const createdFresh = (await adapter.listModels(PROVIDER)).map((model) => model.id).find((id) => !idsBefore.has(id));
  if (typeof createdFresh === "string") createdSessions.add(createdFresh);
  const secondFresh = await drain(adapter.stream({ provider: PROVIDER, model: NEW_SESSION_MODEL, sessionId: harnessKey, messages: freshUser("Reply with exactly: fresh-two") }));
  const freshTexts = typeof createdFresh === "string" ? sessionUserTexts(createdFresh) : [];
  check("fresh-session entry created one session for the conversation", typeof createdFresh === "string" && createdFresh !== sessionId && createdFresh !== NEW_SESSION_MODEL, String(createdFresh));
  check("fresh-session entry answered the first message", /fresh-one/i.test(textOf(firstFresh).trim()), JSON.stringify(textOf(firstFresh).trim().slice(0, 80)));
  check("fresh-session entry continued the same session on the second message",
    /fresh-two/i.test(textOf(secondFresh).trim()) && freshTexts.some((text) => /fresh-one/.test(text)),
    `${freshTexts.length} user messages: ${JSON.stringify(freshTexts.map((text) => text.slice(0, 40)))}`);
  const otherFresh = await drain(adapter.stream({ provider: PROVIDER, model: NEW_SESSION_MODEL, sessionId: "smoke-conversation-2", messages: freshUser("Reply with exactly: fresh-three") }));
  const createdOther = (await adapter.listModels(PROVIDER)).map((model) => model.id).filter((id) => !idsBefore.has(id) && id !== createdFresh);
  if (createdOther.length === 1) createdSessions.add(createdOther[0]);
  check("a second conversation gets its own fresh session",
    createdOther.length === 1 && /fresh-three/i.test(textOf(otherFresh).trim()) && (typeof createdFresh !== "string" || !sessionUserTexts(createdOther[0]).some((text) => /fresh-one|fresh-two/.test(text))),
    `${createdOther.length} new sessions: ${JSON.stringify(createdOther)}`);

  // Tool activity reaches the harness as transcript records: the loop executes
  // every `tool-call` block an adapter emits, so a record is the honest shape.
  const toolChunks = await drain(adapter.stream({
    provider: PROVIDER,
    model: sessionId,
    messages: freshUser("Use your shell tool to run `echo omp-tool-shaper` and then reply with exactly: shaped"),
  }));
  const reasoning = toolChunks.filter((chunk) => chunk.type === "reasoning-delta").map((chunk) => chunk.text).join("");
  check("tool activity is reported as records, never as executable tool calls",
    toolChunks.every((chunk) => chunk.type !== "tool-call-delta") && /omp tool /.test(reasoning),
    JSON.stringify(reasoning.replace(/\s+/g, " ").slice(0, 160)));
  check("tool records carry the command the agent ran", /omp tool /.test(reasoning) && /echo omp-tool-shaper/.test(reasoning), JSON.stringify(reasoning.slice(0, 200)));

  // The agent process that dies mid-life (crash, restart, the harness killing
  // the tree) must be replaced rather than reused.
  const killedPid = pool.status().liveSessions.find((row) => row.sessionId === sessionId)?.pid;
  process.kill(killedPid, "SIGKILL");
  await new Promise((resolve) => setTimeout(resolve, 750));
  const recovered = await drain(adapter.stream({
    provider: PROVIDER,
    model: sessionId,
    messages: [{ role: "user", content: [{ type: "text", text: "Reply with exactly: recovered" }] }],
  }));
  const replacementPid = pool.status().liveSessions.find((row) => row.sessionId === sessionId)?.pid;
  check("killed agent process is replaced on the next prompt",
    Number.isFinite(killedPid) && Number.isFinite(replacementPid) && replacementPid !== killedPid && /recovered/i.test(textOf(recovered).trim()),
    `pid ${killedPid} → ${replacementPid}`);

  const beforeAux = (await pool.listSessions()).find((session) => session.sessionId === sessionId)?.messageCount;
  const namesBeforeAux = sessionFileNames();
  const auxChunks = await drain(adapter.stream({
    provider: PROVIDER,
    model: sessionId,
    purpose: "session-title",
    system: "Name this session.",
    messages: [{ role: "user", content: [{ type: "text", text: "We debugged the ACP transport." }] }],
  }));
  const afterAux = (await pool.listSessions()).find((session) => session.sessionId === sessionId)?.messageCount;
  const addedByAux = sessionFileNames().filter((name) => !namesBeforeAux.includes(name));
  check("auxiliary call returned text", textOf(auxChunks).trim().length > 0, JSON.stringify(textOf(auxChunks).trim().slice(0, 80)));
  check("auxiliary call left the session history untouched", beforeAux === afterAux, `${beforeAux} → ${afterAux}`);
  check("auxiliary call added and left no session file", addedByAux.length === 0, addedByAux.join(", "));

  const controller = new AbortController();
  let aborted = false;
  const pending = drain(adapter.stream({
    provider: PROVIDER,
    model: sessionId,
    messages: [{ role: "user", content: [{ type: "text", text: "Count slowly from one to forty, one number per line." }] }],
    signal: controller.signal,
  })).then(() => undefined, (error) => {
    aborted = true;
    return error;
  });
  setTimeout(() => controller.abort(), 2_000);
  const abortOutcome = await pending;
  check("cancellation stops the prompt", aborted && abortOutcome instanceof Error, abortOutcome?.message ?? "no error");

  const endNames = sessionFileNames();
  const createdSuffixes = [...createdSessions].map((id) => `_${id}.jsonl`);
  const ownDirs = new Set(endNames.filter((name) => createdSuffixes.some((suffix) => name.endsWith(suffix))).map((name) => name.slice(0, name.indexOf("/"))));
  const foreign = endNames.filter((name) => ownDirs.has(name.slice(0, name.indexOf("/"))) && !createdSuffixes.some((suffix) => name.endsWith(suffix)));
  check("the run's own store directories hold exactly the sessions it created",
    ownDirs.size > 0 && foreign.length === 0 && createdSuffixes.every((suffix) => endNames.some((name) => name.endsWith(suffix))),
    `${ownDirs.size} dirs, ${foreign.length} foreign files: ${foreign.join(", ")}`);

  const permissionParams = {
    toolCall: { title: "Run shell command" },
    options: [{ optionId: "allow-once", kind: "allow_once" }, { optionId: "reject-once", kind: "reject_once" }],
  };
  const kindOnlyOptions = { toolCall: { title: "Run shell command" }, options: [{ optionId: "x1", kind: "allow_always" }, { optionId: "x2", kind: "reject_always" }] };
  const ask = (decision) => async () => decision;
  const human = await resolvePermission(permissionParams, { policy: "ask", ask: ask("allowed-once") });
  const refused = await resolvePermission(permissionParams, { policy: "ask", ask: ask("rejected") });
  const broken = await resolvePermission(permissionParams, { policy: "ask", ask: async () => { throw new Error("no answerer"); } });
  const unavailable = await resolvePermission(permissionParams, { policy: "ask", ask: ask("unavailable") });
  const staticPolicy = await resolvePermission(permissionParams, { policy: "allow", ask: async () => { throw new Error("must not be asked"); } });
  check("selectPermission returns the exact ACP reply envelope", JSON.stringify(selectPermission(permissionParams, "allow")) === JSON.stringify({ outcome: { outcome: "selected", optionId: "allow-once" } }) && JSON.stringify(selectPermission(permissionParams, "reject")) === JSON.stringify({ outcome: { outcome: "selected", optionId: "reject-once" } }), JSON.stringify(selectPermission(permissionParams, "allow")));
  check("every reply the agent receives selects an offered option id", [human, refused, broken, unavailable, staticPolicy].every((decision) => typeof decision.reply?.outcome?.optionId === "string" && decision.reply.outcome.optionId.length > 0));
  check("direction is read from the option kind, not its id", selectPermission(kindOnlyOptions, "allow").outcome.optionId === "x1" && selectPermission(kindOnlyOptions, "reject").outcome.optionId === "x2", JSON.stringify([selectPermission(kindOnlyOptions, "allow"), selectPermission(kindOnlyOptions, "reject")]));
  check("an option-less request is answered as cancelled", selectPermission({ toolCall: {}, options: [] }, "allow").outcome.outcome === "cancelled");
  check("a human grant answers the question", human.reply.outcome.optionId === "allow-once" && human.decidedBy === "human");
  check("a human refusal answers the question", refused.reply.outcome.optionId === "reject-once" && refused.decidedBy === "human");
  check("a failing ask still answers, allowing the tool", broken.reply.outcome.optionId === "allow-once" && broken.decidedBy === "policy" && broken.outcome_ === "allow (unavailable)");
  check("an unanswerable ask still answers, allowing the tool", unavailable.reply.outcome.optionId === "allow-once" && unavailable.decidedBy === "policy");
  check("a static policy never consults the asker", staticPolicy.decidedBy === "policy");
  check("permission questions carry a tool name", permissionToolName(permissionParams) === "Run shell command");

  const announced = toolRecord({ sessionUpdate: "tool_call", title: "Run shell command", kind: "execute", rawInput: { command: "echo hi" } });
  const completed = toolUpdateRecord({ sessionUpdate: "tool_call_update", title: "Run shell command", status: "completed", content: [{ type: "content", content: { type: "text", text: "hi" } }] });
  const failedRecord = toolUpdateRecord({ sessionUpdate: "tool_call_update", title: "Run shell command", status: "failed", content: [{ type: "content", content: { type: "text", text: "boom" } }] });
  check("a tool record names the tool, its kind and its command", /Run shell command/.test(announced) && /execute/.test(announced) && /echo hi/.test(announced), JSON.stringify(announced));
  check("a completed tool record carries the output", /completed/.test(completed) && /hi/.test(completed), JSON.stringify(completed));
  check("a failed tool record says so and keeps the output", /failed/.test(failedRecord) && /boom/.test(failedRecord), JSON.stringify(failedRecord));
  check("an in-progress update emits no record", toolUpdateRecord({ sessionUpdate: "tool_call_update", title: "x", status: "in_progress" }) === "");

  check("harnessUsage subtracts cached input", JSON.stringify(harnessUsage({ inputTokens: 100, outputTokens: 5, cachedReadTokens: 60 })) === JSON.stringify({ inputTokens: 40, outputTokens: 5, cacheReadTokens: 60 }));
  check("newestUserText reads the newest user text", newestUserText([{ role: "user", content: [{ type: "text", text: "one" }] }, { role: "assistant", content: [{ type: "text", text: "x" }] }, { role: "user", content: [{ type: "text", text: "two" }] }]) === "two");
} finally {
  pool.dispose();
  let removed = 0;
  for (const id of createdSessions) removed += removeSession(id);
  try {
    for (const directory of [sessionCwd, auxiliaryCwd]) await removeDirWithRetry(directory);
    process.stdout.write(`\nremoved ${removed} throwaway session file(s) of ${createdSessions.size}, and this run's two scratch directories\n`);
  } catch (error) {
    process.stdout.write(`\ncleanup warning: ${error?.message ?? error}\n`);
  }
}

process.stdout.write(failures.length === 0 ? "\nSMOKE OK\n" : `\nSMOKE FAILED: ${failures.join(", ")}\n`);
process.exit(failures.length === 0 ? 0 : 1);
