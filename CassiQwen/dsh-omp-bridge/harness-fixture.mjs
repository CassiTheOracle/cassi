/**
 * Test fixtures for the DSH→omp bridge: a stub OpenAI-completions model, a
 * throwaway harness home, and a real harness boot. `verify.mjs` uses them for
 * acceptance, and `verify.mjs --keep` leaves the same fixture running for a
 * manual debugging session.
 */
import { spawn, execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync, copyFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const REAL_DSH_HOME = join(process.env.USERPROFILE ?? process.env.HOME ?? "", ".dsh");

export const realDshHome = REAL_DSH_HOME;

/** The text of an OpenAI message content field (string or part array). */
function messageText(content) {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return undefined;
  const parts = content.map((part) => part?.text ?? part?.content).filter((text) => typeof text === "string");
  return parts.length > 0 ? parts.join("\n") : undefined;
}

/** Junction `link` → `target` with a real Windows directory junction. */
function junction(link, target) {
  if (!existsSync(link)) {
    execFileSync("powershell", ["-NoProfile", "-Command", `New-Item -ItemType Junction -Path '${link}' -Target '${target}' | Out-Null`], { stdio: "pipe" });
  }
}

/**
 * A stub OpenAI-completions model that echoes the newest prompt text.
 *
 * `toolCalls` scripts real tool calls for tests that need the harness to *do*
 * something: each entry is `{ when, name, arguments }`, the first whose
 * `when(context)` is true answers the request with that call instead of text.
 * The context carries `{messages, toolNames, toolResults, callIndex}` so a
 * script can react to what the harness sent back (e.g. retry after a denial).
 */
export async function startStubModel({ toolCalls = [] } = {}) {
  const server = createServer(async (request, response) => {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    const body = chunks.length > 0 ? JSON.parse(Buffer.concat(chunks).toString("utf8")) : {};
    if (request.method === "GET") {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ object: "list", data: [{ id: "stub-1", object: "model" }] }));
      return;
    }
    const messages = Array.isArray(body.messages) ? body.messages : [];
    // The harness injects its own runtime context as a trailing user-role
    // message on a session's first turn, so echo every user-role text: the
    // caller's own text is then provably somewhere in the prompt.
    const userText = messages
      .filter((message) => message?.role === "user")
      .map((message) => (typeof message.content === "string" ? message.content : Array.isArray(message.content) ? message.content.map((part) => part?.text ?? "").join(" ") : ""))
      .join(" | ");
    // The harness sends the whole conversation plus its own runtime context as
    // user-role messages, so echo both ends: the caller's newest text sits at
    // the tail, and the harness's injected context shows up in between.
    const joined = userText.replace(/\s+/g, " ");
    const created = Math.floor(Date.now() / 1000);
    const toolResults = messages.filter((message) => message?.role === "tool").map((message) => messageText(message.content) ?? "");
    const context = {
      messages,
      toolNames: (Array.isArray(body.tools) ? body.tools : []).map((tool) => tool?.function?.name).filter((name) => typeof name === "string"),
      toolResults,
      callIndex: messages.filter((message) => Array.isArray(message?.tool_calls) && message.tool_calls.length > 0).length,
    };
    const scripted = toolCalls.find((entry) => entry.when(context));
    if (scripted !== undefined) {
      const call = { id: `call_${context.callIndex + 1}`, type: "function", function: { name: scripted.name, arguments: JSON.stringify(scripted.arguments) } };
      if (body.stream !== true) {
        response.writeHead(200, { "content-type": "application/json" });
        response.end(JSON.stringify({ id: "stub", object: "chat.completion", created, model: body.model, choices: [{ index: 0, message: { role: "assistant", content: null, tool_calls: [call] }, finish_reason: "tool_calls" }], usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 } }));
        return;
      }
      response.writeHead(200, { "content-type": "text/event-stream" });
      const chunk = (delta, finish) => `data: ${JSON.stringify({ id: "stub", object: "chat.completion.chunk", created, model: body.model, choices: [{ index: 0, delta, finish_reason: finish }] })}\n\n`;
      response.write(chunk({ role: "assistant", content: "" }, null));
      response.write(chunk({ tool_calls: [{ index: 0, id: call.id, type: "function", function: { name: call.function.name, arguments: "" } }] }, null));
      for (const piece of call.function.arguments.match(/.{1,64}/g) ?? []) response.write(chunk({ tool_calls: [{ index: 0, function: { arguments: piece } }] }, null));
      response.write(chunk({}, "tool_calls"));
      response.write("data: [DONE]\n\n");
      response.end();
      return;
    }
    const reply = joined.length > 700 ? `bridge-ok:${joined.slice(0, 200)} … ${joined.slice(-300)}` : `bridge-ok:${joined}`;
    if (body.stream !== true) {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ id: "stub", object: "chat.completion", created, model: body.model, choices: [{ index: 0, message: { role: "assistant", content: reply }, finish_reason: "stop" }], usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 } }));
      return;
    }
    response.writeHead(200, { "content-type": "text/event-stream" });
    const chunk = (delta, finish) => `data: ${JSON.stringify({ id: "stub", object: "chat.completion.chunk", created, model: body.model, choices: [{ index: 0, delta, finish_reason: finish }] })}\n\n`;
    response.write(chunk({ role: "assistant", content: "" }, null));
    for (const piece of reply.match(/.{1,12}/g) ?? []) response.write(chunk({ content: piece }, null));
    response.write(chunk({}, "stop"));
    response.write("data: [DONE]\n\n");
    response.end();
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;
  return { url: `http://127.0.0.1:${port}`, close: () => new Promise((resolve) => server.close(resolve)) };
}

/**
 * A disposable harness home: the real profile's files, dependencies junctioned,
 * a stub provider as the default agent model.
 */
export function buildHarnessHome({ stubUrl }) {
  const home = mkdtempSync(join(tmpdir(), "dsh-bridge-home-"));
  const profile = join(home, "profiles", "web");
  mkdirSync(profile, { recursive: true });
  for (const file of ["cordis.yml", "cordis.patch.yml", "pnpm-workspace.yaml", "package.json"]) {
    const source = join(REAL_DSH_HOME, "profiles", "web", file);
    if (existsSync(source)) copyFileSync(source, join(profile, file));
  }
  const manifest = JSON.parse(readFileSync(join(profile, "package.json"), "utf8"));
  for (const [name, spec] of Object.entries(manifest.dependencies ?? {})) {
    if (spec.startsWith("file:") && !spec.startsWith("file:/") && !/^file:[A-Za-z]:/.test(spec)) {
      manifest.dependencies[name] = `file:C:/Users/Carina/workspaces/Cassi/CassiQwen/${name.replace(/^@[^/]+\//, "")}`;
    }
  }
  writeFileSync(join(profile, "package.json"), JSON.stringify(manifest, null, 2));
  junction(join(home, "profiles", "node_modules"), join(REAL_DSH_HOME, "profiles", "node_modules"));
  junction(join(profile, "node_modules"), join(REAL_DSH_HOME, "profiles", "web", "node_modules"));

  const settingsPath = join(REAL_DSH_HOME, "settings.yaml");
  const settings = existsSync(settingsPath) ? readFileSync(settingsPath, "utf8") : "";
  const stubProvider = [
    "llm-pi-ai:",
    "  providers:",
    "    bridge-stub:",
    "      displayName: Bridge test stub",
    "      api: openai-completions",
    "      baseURL: " + stubUrl + "/v1",
    "      apiKeyEnv: BRIDGE_TEST_API_KEY",
    "      compat:",
    "        supportsDeveloperRole: false",
    "      models:",
    "        - id: stub-1",
    "          name: Bridge test stub",
    "          contextWindow: 32768",
    "          maxTokens: 2048",
    "          reasoningEfforts: false",
  ].join("\n");
  writeFileSync(join(home, "settings.yaml"), `${stubProvider}\nagent-default-model:\n  provider: bridge-stub\n  model: stub-1\n`);
  const credentials = join(REAL_DSH_HOME, ".credentials.yaml");
  if (existsSync(credentials)) copyFileSync(credentials, join(home, ".credentials.yaml"));
  return home;
}

/** Boot `dsh web` on a disposable home and return its origin. */
export async function startHarness({ home, permissionMode, timeoutMs = 120_000 }) {
  const child = spawn(process.env.ComSpec ?? "cmd.exe", ["/d", "/s", "/c", "dsh web --no-open --port 0"], {
    cwd: home,
    env: { ...process.env, DSH_HOME: home, BRIDGE_TEST_API_KEY: "bridge-test-key", ...(permissionMode === undefined ? {} : { DSH_PERMISSION_MODE: permissionMode }) },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let output = "";
  const url = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`the harness did not print a URL within ${timeoutMs} ms; output so far:\n${output}`)), timeoutMs);
    const scan = (buffer) => {
      output += buffer.toString();
      const match = /dsh web: (http:\/\/[^\s]+)/.exec(output);
      if (match !== null) {
        clearTimeout(timer);
        resolve(match[1].replace(/\/$/, ""));
      }
    };
    child.stdout.on("data", scan);
    child.stderr.on("data", scan);
    child.on("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`the harness exited with code ${code}:\n${output}`));
    });
  });
  return {
    url,
    output: () => output,
    stop: () => {
      try {
        execFileSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], { stdio: "pipe" });
      } catch {
        child.kill();
      }
    },
  };
}

/** POST a chat-completions request and collect the streamed answer. */
export async function chat({ url, body, headers = {} }) {
  const response = await fetch(`${url}/v1/chat/completions`, { method: "POST", headers: { "content-type": "application/json", ...headers }, body: JSON.stringify(body) });
  if (body.stream === false) return { status: response.status, json: await response.json() };
  const text = await response.text();
  const events = text.split("\n\n").map((block) => block.replace(/^data: /, "").trim()).filter((block) => block.length > 0);
  const json = events.filter((event) => event !== "[DONE]").map((event) => JSON.parse(event));
  const content = json.flatMap((chunk) => chunk.choices?.[0]?.delta?.content ?? []).join("");
  return { status: response.status, json, content, raw: text, done: events.at(-1) === "[DONE]", first: json[0], last: json.at(-1) };
}


/**
 * The oh-my-pi executable to drive the bridge with. Spawned directly (never
 * through a shell) so an absolute `-e` path survives quoting.
 */
export function ompExecutable() {
  if (process.env.OMP_EXECUTABLE) return process.env.OMP_EXECUTABLE;
  try {
    const found = execFileSync("where", ["omp"], { encoding: "utf8" })
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    const exe = found.find((path) => path.toLowerCase().endsWith(".exe")) ?? found[0];
    if (exe) return exe;
  } catch {
    /* fall through to PATH lookup */
  }
  return "omp";
}

/** Kill a child and its tree; on Windows a launcher spawns the real process. */
function killTree(child) {
  try {
    execFileSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], { stdio: "pipe" });
  } catch {
    child.kill();
  }
}

/**
 * Run a command and resolve with its stdout.
 *
 * Asynchronous on purpose — a test that spawns oh-my-pi while an in-process
 * bridge serves it would deadlock the event loop with a synchronous spawn.
 * stdin is ignored, not piped: given a pipe, oh-my-pi decides the prompt comes
 * from stdin and blocks on EOF instead of running the prompt it was given.
 *
 * @param {string} command @param {string[]} args @param {object} [options]
 * @returns {Promise<string>}
 */
export function runCommand(command, args, { cwd, env, timeoutMs = 300_000, maxBuffer = 32 * 1024 * 1024 } = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd, env, stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    let settled = false;
    const finish = (error, killed = false) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (killed) killTree(child);
      if (error === undefined) {
        resolve(stdout);
        return;
      }
      error.stdout = stdout;
      error.stderr = stderr;
      error.killed = killed;
      reject(error);
    };
    const timer = setTimeout(() => finish(new Error(`${command} did not finish within ${timeoutMs} ms`), true), timeoutMs);
    timer.unref?.();
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
      if (stdout.length > maxBuffer) finish(new Error(`${command} wrote more than ${maxBuffer} bytes to stdout`));
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
      if (stderr.length > maxBuffer) finish(new Error(`${command} wrote more than ${maxBuffer} bytes to stderr`));
    });
    child.on("error", (error) => finish(error));
    child.on("close", (code) => finish(code === 0 ? undefined : new Error(`${command} exited with code ${code}`)));
  });
}
