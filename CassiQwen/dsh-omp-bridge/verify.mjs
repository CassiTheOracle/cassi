#!/usr/bin/env node
/**
 * End-to-end acceptance for the DSH→omp bridge, with nothing external in the loop.
 *
 *   stub LLM  ← harness agent →  disposable harness  ← bridge ← OpenAI client
 *
 * A stub OpenAI-completions model answers every harness turn by echoing the
 * prompt back, so a reply containing a fresh token proves the whole path: the
 * OpenAI request reached the bridge, the bridge wrote the text into a real
 * harness session, the harness ran a turn on its own agent, and the answer came
 * back through the session event feed.
 *
 * The harness runs from a throwaway DSH_HOME (with the real profile files and
 * junctioned dependencies), so no live session of the user's is touched. The
 * oh-my-pi side runs under a throwaway *profile* built from the shipped
 * `omp-models.example.yml`, which is exactly what a user installs — so the
 * declarative route is what gets tested, and the default profile is never read.
 *
 * Usage: node verify.mjs [--keep]   (--keep leaves every fixture running)
 */
import { randomUUID } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { startBridge, sessionFragment } from "./bridge.mjs";
import { chat, buildHarnessHome, ompExecutable, runCommand, startHarness, startStubModel } from "./harness-fixture.mjs";
import { DshWire } from "./dsh-wire.mjs";

const REAL_DSH_HOME = join(process.env.USERPROFILE ?? process.env.HOME ?? "", ".dsh");
const OMP_PROFILES = join(process.env.USERPROFILE ?? process.env.HOME ?? "", ".omp", "profiles");
const KEEP = process.argv.includes("--keep");
let passed = 0;
let failed = 0;
const cleanups = [];

/** The advertised row for a session: its bare id, or a title-decorated one. */
const rowFor = (rows, sessionId) => rows.find((row) => row.id === sessionId || row.id.endsWith(`-${sessionFragment(sessionId)}`));

function check(name, ok, detail = "") {
  if (ok) {
    passed += 1;
    process.stdout.write(`PASS  ${name}${detail ? ` — ${detail}` : ""}\n`);
  } else {
    failed += 1;
    process.stdout.write(`FAIL  ${name}${detail ? ` — ${detail}` : ""}\n`);
  }
}

async function main() {
  const stub = await startStubModel();
  cleanups.push(() => stub.close());
  process.stdout.write(`stub model on ${stub.url}\n`);
  const home = buildHarnessHome({ stubUrl: stub.url });
  cleanups.push(() => (KEEP ? undefined : rmSync(home, { recursive: true, force: true })));
  process.stdout.write(`harness home ${home}\n`);

  const harness = await startHarness({ home });
  cleanups.push(() => harness.stop());
  process.stdout.write(`harness on ${harness.url}\n`);
  const wire = new DshWire({ baseUrl: harness.url });

  const sessions = await wire.listSessions();
  check("the wire client lists harness sessions", Array.isArray(sessions), `${sessions.length} sessions`);

  const created = await wire.createSession({ cwd: home });
  check("the wire client creates a session", typeof created?.sessionId === "string", created?.sessionId);

  const token = `token-${randomUUID().slice(0, 8)}`;
  const turn = await wire.runTurn({ sessionId: created.sessionId, text: `echo ${token}` });
  check("the wire client runs a turn and receives its answer", turn.text.includes(token) && turn.text.startsWith("bridge-ok:"), JSON.stringify(turn.text.slice(0, 90)));

  const debugLines = [];
  const bridge = await startBridge({
    harnessUrl: harness.url,
    cwd: home,
    port: 0,
    log: (kind, message) => {
      if (kind === "debug") debugLines.push(message);
    },
  });
  cleanups.push(() => bridge.close());
  process.stdout.write(`bridge on ${bridge.url}\n`);

  const models = await (await fetch(`${bridge.url}/v1/models`)).json();
  const ids = models.data.map((row) => row.id);
  check("the bridge advertises every session plus a fresh one", ids.includes("new") && rowFor(models.data, created.sessionId) !== undefined, ids.join(", "));
  check("advertised rows are OpenAI model objects", models.object === "list" && models.data.every((row) => row.object === "model" && typeof row.id === "string" && typeof row.created === "number" && row.owned_by === "dsh"));

  const health = await (await fetch(`${bridge.url}/health`)).json();
  check("the bridge reports the harness it serves", health.ok === true && health.harness === harness.url && health.sessions >= 1, JSON.stringify(health));

  const streamed = await chat({ url: bridge.url, body: { model: created.sessionId, stream: true, messages: [{ role: "user", content: `stream ${token}` }] } });
  check("a streamed turn answers from the session", streamed.status === 200 && streamed.content.startsWith("bridge-ok:") && streamed.content.includes(token), JSON.stringify(streamed.content.slice(0, 90)));
  check("the stream is well-formed OpenAI SSE", streamed.done === true && streamed.first?.choices?.[0]?.delta?.role === "assistant" && streamed.last?.choices?.[0]?.finish_reason === "stop" && streamed.json.every((chunk) => chunk.object === "chat.completion.chunk"), `${streamed.json.length} chunks`);
  check("streamed chunks arrive in more than one piece", streamed.json.filter((chunk) => typeof chunk.choices?.[0]?.delta?.content === "string" && chunk.choices[0].delta.content.length > 0).length > 1);

  const answered = await chat({ url: bridge.url, body: { model: created.sessionId, stream: false, messages: [{ role: "system", content: `sys-${token} must not travel` }, { role: "user", content: `plain ${token}` }] } });
  check("a non-streamed turn answers as one completion", answered.status === 200 && answered.json.choices?.[0]?.message?.content?.includes(token) && answered.json.choices[0].finish_reason === "stop", JSON.stringify(answered.json.choices?.[0]?.message?.content?.slice(0, 60)));
  check("only the newest user message is sent", answered.json.choices?.[0]?.message?.content?.includes(`plain ${token}`) === true && answered.json.choices?.[0]?.message?.content?.includes(`sys-${token}`) === false);

  const before = (await wire.listSessions()).length;
  const fresh = await chat({ url: bridge.url, body: { model: "new", stream: false, user: `conversation-${token}`, messages: [{ role: "user", content: `fresh ${token}` }] } });
  const after = await wire.listSessions();
  check("the fresh-session model answers", fresh.status === 200 && fresh.json.choices?.[0]?.message?.content?.includes(token), JSON.stringify(fresh.json.choices?.[0]?.message?.content?.slice(0, 60)));
  check("the fresh-session model creates a harness session", after.length === before + 1 && after.some((session) => session.blank === false), `${before} → ${after.length}`);

  await chat({ url: bridge.url, body: { model: "new", stream: false, user: `conversation-${token}`, messages: [{ role: "user", content: "second turn" }] } });
  check("a fresh conversation keeps its session across turns", (await wire.listSessions()).length === after.length, `${after.length} sessions`);

  const headerA = await chat({ url: bridge.url, body: { model: "new", stream: false, messages: [{ role: "user", content: "named A" }] }, headers: { "x-dsh-session": `header-a-${token}` } });
  const headerB = await chat({ url: bridge.url, body: { model: "new", stream: false, messages: [{ role: "user", content: "named B" }] }, headers: { "x-dsh-session": `header-b-${token}` } });
  check("the x-dsh-session header names a conversation of its own", headerA.status === 200 && headerB.status === 200 && (await wire.listSessions()).length === after.length + 2, `${after.length} → ${(await wire.listSessions()).length}`);

  const missing = await chat({ url: bridge.url, body: { model: "no-such-session", stream: false, messages: [{ role: "user", content: "hello" }] } });
  check("an unknown session is refused as a request error", missing.status >= 400 && typeof missing.json?.error?.message === "string", `${missing.status} ${JSON.stringify(missing.json?.error?.message ?? "").slice(0, 80)}`);

  const noPrompt = await chat({ url: bridge.url, body: { model: created.sessionId, stream: false, messages: [{ role: "system", content: "only a system message" }] } });
  check("a request without user text is refused", noPrompt.status === 400, `${noPrompt.status} ${noPrompt.json?.error?.message ?? ""}`);

  const noModel = await chat({ url: bridge.url, body: { stream: false, messages: [{ role: "user", content: "hello" }] } });
  check("a request without a model is refused", noModel.status === 400, `${noModel.status}`);

  const unknownRoute = await fetch(`${bridge.url}/v1/nope`);
  check("unknown routes are 404", unknownRoute.status === 404);

  const history = await wire.call("session.history", { sessionId: created.sessionId }).catch((error) => ({ error: String(error.message) }));
  const historyText = JSON.stringify(history);
  check("the session itself holds both prompts and answers", !history.error && historyText.includes(token) && historyText.includes("bridge-ok:"), `${historyText.length} chars of history`);

  // ── the oh-my-pi side: the shipped declarative route, in a throwaway profile ──
  const provider = "dsh";
  const profile = `dsh-verify-${token}`;
  const profileAgent = join(OMP_PROFILES, profile, "agent");
  mkdirSync(profileAgent, { recursive: true });
  cleanups.push(() => (KEEP ? undefined : rmSync(join(OMP_PROFILES, profile), { recursive: true, force: true })));
  const example = readFileSync(new URL("./omp-models.example.yml", import.meta.url), "utf8");
  const installed = example.replace(/^\s*baseUrl:.*$/m, `    baseUrl: ${bridge.url}/v1`);
  check("the shipped example names the bridge URL that gets installed", installed !== example && installed.includes(`${bridge.url}/v1`));
  writeFileSync(join(profileAgent, "models.yml"), installed, "utf8");
  const runOmp = (args, timeoutMs = 300_000) => runCommand(ompExecutable(), ["--profile", profile, ...args], { cwd: home, env: process.env, timeoutMs });

  let rows = [];
  try {
    const listed = await runOmp(["models", "ls", "--json", "--no-extensions"]);
    rows = (JSON.parse(listed.slice(listed.indexOf("{"))).models ?? []).filter((row) => row.provider === provider);
  } catch (error) {
    check("oh-my-pi lists the bridge's models", false, `${error?.message ?? error}`.slice(0, 200));
  }
  const sessionRow = rowFor(rows, created.sessionId);
  check("oh-my-pi lists every harness session as a model", sessionRow !== undefined && rows.some((row) => row.id === "new"), `${rows.length} models: ${rows.map((row) => row.selector).join(", ")}`);
  check("omp addresses the bridge as a provider selector", rows.length > 0 && rows.every((row) => row.selector === `${provider}/${row.id}`) && rows.every((row) => (row.input ?? []).includes("text")));

  const promptToken = `driven-${randomUUID().slice(0, 8)}`;
  const advertisedId = sessionRow?.id ?? created.sessionId;
  let printed = "";
  try {
    printed = await runOmp(["-p", "--no-tools", "--model", `${provider}/${advertisedId}`, `echo ${promptToken}`]);
  } catch (error) {
    check("an oh-my-pi turn drives the harness session", false, `${error?.stdout ?? error?.message ?? error}`.slice(0, 300));
  }
  check("an oh-my-pi turn drives the harness session", printed.includes("bridge-ok:") && printed.includes(promptToken), JSON.stringify(printed.trim().slice(0, 120)));
  const driven = debugLines.filter((line) => line.includes(`session=${created.sessionId}`)).at(-1) ?? "";
  check("the driven turn reached the bridge as a request for that session", driven.includes(`model=${advertisedId}`) && driven.includes(`session=${created.sessionId}`) && /chars=[1-9]/.test(driven), driven);
  check("the request body arrives with the OpenAI fields the bridge reads", /model=\S+/.test(driven) && / keys=\S*model/.test(driven), driven);

  // ── titles: a session reads as its title in the picker, and still resolves ──
  // oh-my-pi names a discovered model after its id, so the title has to be in
  // the id; the bridge keeps a resolvable fragment at the end of it.
  const title = `Refactor the field solver ${token}`;
  const renamed = await wire.call("session.rename", { sessionId: created.sessionId, title }).catch((error) => ({ error: String(error.message) }));
  const titled = await (await fetch(`${bridge.url}/v1/models`)).json();
  const titledRow = titled.data.find((row) => row.id !== "new" && row.id.endsWith(`-${sessionFragment(created.sessionId)}`));
  check("a renamed session is advertised under its title", renamed.error === undefined && titledRow?.id.startsWith("refactor-the-field-solver") === true, `${titledRow?.id ?? "no row"}${renamed.error === undefined ? "" : ` (${renamed.error})`}`);

  const byTitle = await chat({ url: bridge.url, body: { model: titledRow?.id ?? "", stream: false, messages: [{ role: "user", content: `titled ${token}` }] } });
  check("a request addressed by the titled id reaches that session", byTitle.status === 200 && byTitle.json?.choices?.[0]?.message?.content?.includes(token), `${byTitle.status}`);
  const titledLine = debugLines.filter((line) => line.includes(`model=${titledRow?.id ?? "\u0000"}`)).at(-1) ?? "";
  check("the titled id resolved to the session's real id", titledLine.includes(`session=${created.sessionId}`), titledLine || "no line");

  let titledRows = [];
  try {
    // oh-my-pi serves discovered rows from its own catalog cache, so a rename
    // shows up when the catalog is refetched — which is what refresh does.
    const listed = await runOmp(["models", "refresh", "--json", "--no-extensions"]);
    titledRows = (JSON.parse(listed.slice(listed.indexOf("{"))).models ?? []).filter((row) => row.provider === provider);
  } catch (error) {
    check("oh-my-pi lists the renamed session", false, `${error?.message ?? error}`.slice(0, 200));
  }
  const pickerRow = rowFor(titledRows, created.sessionId);
  check("oh-my-pi's own list shows the title as the model name", pickerRow !== undefined && /^refactor-the-field-solver/.test(pickerRow.name ?? "") && pickerRow.selector === `${provider}/${pickerRow.id}`, pickerRow?.selector ?? "no row");

  // ── approvals: a tool call that needs consent, decided from the bridge side ──
  // The harness asks, the bridge answers, and the filesystem says which way it
  // went. The stub model is scripted to hit the sandbox: the first write is
  // denied, the retry asks for a wider mode, and that request for consent is
  // the approval the bridge decides — one bridge allowing, one rejecting.
  const approvalScript = [];
  const approvalStub = await startStubModel({ toolCalls: approvalScript });
  cleanups.push(() => approvalStub.close());
  const approvalHome = buildHarnessHome({ stubUrl: approvalStub.url });
  cleanups.push(() => (KEEP ? undefined : rmSync(approvalHome, { recursive: true, force: true })));
  const approvalHarness = await startHarness({ home: approvalHome, permissionMode: "read-only" });
  cleanups.push(() => approvalHarness.stop());
  const approvalWire = new DshWire({ baseUrl: approvalHarness.url });

  const allowLogs = [];
  const rejectLogs = [];
  const allowBridge = await startBridge({ harnessUrl: approvalHarness.url, cwd: approvalHome, port: 0, approval: "allow", log: (kind, message) => allowLogs.push(`${kind}: ${message}`) });
  cleanups.push(() => allowBridge.close());
  const rejectBridge = await startBridge({ harnessUrl: approvalHarness.url, cwd: approvalHome, port: 0, approval: "reject", log: (kind, message) => rejectLogs.push(`${kind}: ${message}`) });
  cleanups.push(() => rejectBridge.close());
  process.stdout.write(`approval harness on ${approvalHarness.url}, bridges ${allowBridge.url} (allow) and ${rejectBridge.url} (reject)\n`);

  const markerAllow = join(approvalHome, `approval-marker-allow-${token}.txt`);
  const markerReject = join(approvalHome, `approval-marker-reject-${token}.txt`);
  const writeCommand = (marker) => `Set-Content -LiteralPath '${marker}' -Value ${token}; Get-Content -LiteralPath '${marker}'`;
  const wasDenied = (context) => /sandbox|denied/i.test(context.toolResults.at(-1) ?? "");
  approvalScript.push(
    { when: (context) => context.callIndex === 0 && context.toolNames.includes("pwsh"), name: "pwsh", arguments: { command: writeCommand(markerAllow), description: "Write the approval marker file" } },
    { when: (context) => context.callIndex === 1 && wasDenied(context), name: "pwsh", arguments: { command: writeCommand(markerAllow), description: "Write the approval marker file", sandbox_permissions: "workspace-write", justification: "The marker file belongs to this session's workspace." } },
  );

  const sessionsBefore = (await approvalWire.listSessions()).map((session) => session.sessionId);
  const allowed = await chat({ url: allowBridge.url, body: { model: "new", stream: false, user: `approval-allow-${token}`, messages: [{ role: "user", content: `write the marker ${token}` }] } });
  const allowSession = (await approvalWire.listSessions()).map((session) => session.sessionId).find((id) => !sessionsBefore.includes(id));
  check("a turn that needs consent still completes", allowed.status === 200 && typeof allowed.json?.choices?.[0]?.message?.content === "string", `${allowed.status} ${JSON.stringify(allowed.json?.choices?.[0]?.message?.content ?? allowed.json?.error?.message ?? "").slice(0, 90)}`);

  const allowHistory = JSON.stringify(await approvalWire.call("session.history", { sessionId: allowSession }).catch((error) => ({ error: String(error.message) })));
  const asked = /"type":"approval\/asked"/.test(allowHistory) || /"type": "approval\/asked"/.test(allowHistory);
  const decidedAllow = /"type": *"approval\/decided"[^}]*"outcome": *"allowed-once"/.test(allowHistory);
  check("the harness denied the first write, so the model asked for a wider mode", /sandbox/i.test(allowHistory) && asked, asked ? "approval/asked recorded" : "no approval/asked in the session history");
  check("the session records the bridge's grant", decidedAllow, allowHistory.length + " chars of history");
  check("the granted write really ran", existsSync(markerAllow), markerAllow);
  check("the bridge logged the decision it posted", allowLogs.some((line) => line.includes(`approval allowed-once for "pwsh" in ${allowSession}`)), allowLogs.filter((line) => line.includes("approval")).slice(-1)[0] ?? "no approval line");
  check("the decision rides out on the turn's answer", typeof allowed.json?.choices?.[0]?.message?.content === "string" && allowed.json.choices[0].message.content.includes("[bridge: harness approval allowed-once for pwsh"), JSON.stringify(String(allowed.json?.choices?.[0]?.message?.content ?? "").slice(-80)));

  const rejectBefore = (await approvalWire.listSessions()).map((session) => session.sessionId);
  const rejectedTurn = await chat({ url: rejectBridge.url, body: { model: "new", stream: false, user: `approval-reject-${token}`, messages: [{ role: "user", content: `write the marker ${token}` }] } });
  const rejectSession = (await approvalWire.listSessions()).map((session) => session.sessionId).find((id) => !rejectBefore.includes(id));
  const rejectHistory = JSON.stringify(await approvalWire.call("session.history", { sessionId: rejectSession }).catch((error) => ({ error: String(error.message) })));
  check("a rejected approval still ends the turn instead of hanging", rejectedTurn.status === 200 && typeof rejectedTurn.json?.choices?.[0]?.message?.content === "string", `${rejectedTurn.status}`);
  check("the session records the refusal", /"type": *"approval\/decided"[^}]*"outcome": *"rejected"/.test(rejectHistory));
  check("a refused write leaves nothing behind", !existsSync(markerReject), markerReject);
  check("the rejecting bridge logged its own decision", rejectLogs.some((line) => line.includes(`approval rejected for "pwsh" in ${rejectSession}`)), rejectLogs.filter((line) => line.includes("approval")).slice(-1)[0] ?? "no approval line");
  check("a bridge leaves another session's questions to the other client", rejectLogs.some((line) => line.includes(`approval for "pwsh" in ${allowSession} is outside this bridge's scope`)), `${allowLogs.length} allow-side lines, ${rejectLogs.length} reject-side lines`);
}

try {
  await main();
} catch (error) {
  failed += 1;
  process.stdout.write(`FAIL  harness — ${error?.stack ?? error}\n`);
} finally {
  if (KEEP) {
    process.stdout.write("\n--keep: every fixture is still running; Ctrl+C stops the bridge and stub.\n");
  } else {
    for (const cleanup of cleanups.reverse()) {
      try {
        await cleanup();
      } catch (error) {
        process.stdout.write(`cleanup warning: ${error?.message ?? error}\n`);
      }
    }
  }
}
process.stdout.write(`\n${failed === 0 ? "VERIFY OK" : "VERIFY FAILED"} — ${passed} passed, ${failed} failed\n`);
if (!KEEP) process.exit(failed === 0 ? 0 : 1);
