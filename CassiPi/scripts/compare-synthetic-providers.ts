import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { createReadStream, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { basename, join, resolve } from "node:path";
import type { Message } from "@oh-my-pi/pi-ai";
import { ThinkingLevel, type AgentMessage } from "@oh-my-pi/pi-agent-core";
import { RpcClient } from "@oh-my-pi/pi-coding-agent/modes/rpc/rpc-client";
import { SessionManager } from "@oh-my-pi/pi-coding-agent/session/session-manager";

interface ProviderCase {
  family: string;
  provider: string;
  model: string;
}

interface Scenario {
  id: string;
  stale: string;
  current: string;
  failed: string;
  source: string;
  proposal: string;
  status: string;
  branchMarker: string;
}

interface ArmResult {
  arm: "stock" | "cassipi";
  provider: string;
  model: string;
  scenario: string;
  status: "completed" | "failed";
  error?: string;
  compactions: Array<{
    index: number;
    tokensBefore: number | null;
    firstKeptEntry: boolean;
    summaryChars: number;
    branchMarkerLeak: boolean;
  }>;
  response?: string;
  parsed?: Record<string, unknown> | null;
  checks?: Record<string, boolean>;
  score?: number;
  maxScore?: number;
  session?: {
    file: string;
    tokens: {
      input: number;
      output: number;
      reasoning: number;
      cacheRead: number;
      cacheWrite: number;
      total: number;
    };
    costUsd: number;
    routedModels?: Record<string, number>;
  };
}

const root = resolve(import.meta.dir, "..");
const receiptPath = join(root, "probes", "receipts", "provider-comparison.json");
const runRoot = join(root, ".probe", "provider-comparison");
const installedProfile = join(homedir(), ".omp", "profiles", "cassipi-rehearsal");
const stockHost = join(homedir(), ".bun", "bin", "omp.exe");
const cassipiHost = join(installedProfile, "bin", "omp-cassipi.exe");
const cassipiExtension = join(installedProfile, "local-plugins", "cassipi", "src", "index.ts");
const cassipiRuntime = join(installedProfile, "local-plugins", "cassipi", "fi-runtime");
const globalAgentDir = join(homedir(), ".omp", "agent");
const releaseManifestPath = join(root, "dist", "release-manifest.json");
const compactionInstructions =
  "Preserve the corrected current premise, failed approach, exact source anchor, and proposal execution status. Exclude superseded premises and unrelated padding.";

const providers: ProviderCase[] = [
  { family: "OpenAI Codex", provider: "openai-codex", model: "gpt-5.6-sol" },
  { family: "OpenCode Go", provider: "opencode-go", model: "qwen3.8-flash" },
];

const scenarios: Scenario[] = [
  {
    id: "harbor-relay",
    stale: "relay port is 4100",
    current: "relay port is 4197",
    failed: "RETRY_MODE=spin",
    source: 'src/relay.ts:88 => const endpoint = "http://127.0.0.1:4197/v2";',
    proposal: "delete the cache index",
    status: "proposed-not-executed",
    branchMarker: "ALT_ONLY_HARBOR_7703",
  },
  {
    id: "quartz-batcher",
    stale: "batch size is 96",
    current: "batch size is 112",
    failed: "eager fanout",
    source: "src/batcher.ts:41 => const batchSize = 112;",
    proposal: "rotate the event ledger",
    status: "proposed-not-executed",
    branchMarker: "ALT_ONLY_QUARTZ_2841",
  },
];

function messageText(message: AgentMessage): string {
  const content = (message as { content?: unknown }).content;
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .flatMap(part => {
      if (typeof part !== "object" || part === null) return [];
      const candidate = part as { type?: unknown; text?: unknown };
      return candidate.type === "text" && typeof candidate.text === "string" ? [candidate.text] : [];
    })
    .join("\n");
}

function makeMessages(startTimestamp: number): {
  user(text: string): Message;
  assistant(text: string): Message;
} {
  let timestamp = startTimestamp;
  return {
    user(text: string): Message {
      return {
        role: "user",
        content: [{ type: "text", text }],
        attribution: "user",
        timestamp: timestamp++,
      };
    },
    assistant(text: string): Message {
      return {
        role: "assistant",
        content: [{ type: "text", text }],
        api: "mock",
        provider: "cassipi-comparison-seed",
        model: "cassipi-comparison-seed",
        usage: {
          input: 0,
          output: 0,
          cacheRead: 0,
          cacheWrite: 0,
          totalTokens: 0,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
        },
        stopReason: "stop",
        timestamp: timestamp++,
      };
    },
  };
}

function padding(label: string): string {
  const words = Array.from({ length: 320 }, (_, index) => `${label}_${index % 29}`);
  return `Synthetic irrelevant padding: ${words.join(" ")}`;
}

async function createSeedSession(sessionDir: string, scenario: Scenario, arm: string): Promise<string> {
  mkdirSync(sessionDir, { recursive: true });
  const manager = SessionManager.create(root, sessionDir);
  const clock = makeMessages(Date.UTC(2026, 0, scenario.id === "harbor-relay" ? 12 : 13));
  manager.appendMessage(
    clock.user(
      `Synthetic comparison task ${scenario.id}. Historical premise: ${scenario.stale}. This may be corrected later.\n${padding(`${scenario.id}_history`)}`,
    ),
  );
  manager.appendMessage(clock.assistant(`Recorded the historical premise: ${scenario.stale}.`));
  const branchPoint = manager.getLeafId();
  assert(branchPoint, "seed session must have a branch point");

  manager.appendMessage(
    clock.user(
      `Private alternate branch only. Marker ${scenario.branchMarker}. This sibling branch claims an incompatible value.`,
    ),
  );
  manager.appendMessage(clock.assistant(`Alternate branch marker recorded: ${scenario.branchMarker}.`));
  manager.branch(branchPoint);

  manager.appendMessage(
    clock.user(
      `Correction with current authority: ${scenario.current}. The historical premise is superseded.\n${padding(`${scenario.id}_current`)}`,
    ),
  );
  manager.appendMessage(clock.assistant(`Current premise acknowledged: ${scenario.current}.`));
  manager.appendMessage(
    clock.user(
      `Failed approach record: ${scenario.failed}. It produced a deterministic deadlock and must not be repeated.\n${padding(`${scenario.id}_failed`)}`,
    ),
  );
  manager.appendMessage(clock.assistant(`Failed approach acknowledged: ${scenario.failed}.`));
  manager.appendMessage(
    clock.user(
      `Exact current source anchor: ${scenario.source}\n${padding(`${scenario.id}_source`)}`,
    ),
  );
  manager.appendMessage(clock.assistant(`Exact source anchor acknowledged: ${scenario.source}`));
  manager.appendMessage(
    clock.user(
      `Action record: ${scenario.proposal}. Status: ${scenario.status}. It was discussed but never executed.\n${padding(`${scenario.id}_action`)}`,
    ),
  );
  manager.appendMessage(
    clock.assistant(`Action status acknowledged: ${scenario.proposal}; ${scenario.status}.`),
  );

  const activeText = manager.buildSessionContext().messages.map(messageText).join("\n");
  assert(!activeText.includes(scenario.branchMarker), `${arm} seed leaked its sibling-branch marker`);
  const sessionFile = manager.getSessionFile();
  assert(sessionFile, "seed session did not materialize a file");
  await manager.close();
  assert(existsSync(sessionFile), "seed session file disappeared during close");
  return sessionFile;
}

async function appendContinuityTurns(
  sessionFile: string,
  sessionDir: string,
  scenario: Scenario,
  arm: string,
  index: number,
): Promise<void> {
  const manager = await SessionManager.open(sessionFile, sessionDir);
  const activeText = manager.buildSessionContext().messages.map(messageText).join("\n");
  assert(!activeText.includes(scenario.branchMarker), `${arm} compaction leaked its sibling-branch marker`);
  const clock = makeMessages(Date.UTC(2026, 1, index + 1));
  for (let turn = 0; turn < 2; turn++) {
    const label = `${index + 1}.${turn + 1}`;
    manager.appendMessage(
      clock.user(
        `Synthetic continuity turn ${label}. It adds no task fact and exists only to create another legal compaction boundary.\n${padding(`${scenario.id}_continuity_${index}_${turn}`)}`,
      ),
    );
    manager.appendMessage(clock.assistant(`Continuity turn ${label} acknowledged; no task fact added.`));
  }
  await manager.close();
}

function writeConfigs(): { stock: string; cassipi: string } {
  const common = `memory:\n  enabled: false\nautolearn:\n  enabled: false\nadvisor:\n  enabled: false\ncompaction:\n  enabled: true\n  thresholdTokens: 800000\n  reserveTokens: 50000\n  keepRecentTokens: 128\n`;
  const stock = join(runRoot, "stock-config.yml");
  const cassipi = join(runRoot, "cassipi-config.yml");
  writeFileSync(stock, common, "utf8");
  writeFileSync(cassipi, `context:\n  owner: cassipi\n${common}`, "utf8");
  return { stock, cassipi };
}

function createClient(
  arm: "stock" | "cassipi",
  providerCase: ProviderCase,
  sessionDir: string,
  sessionFile: string,
  armRoot: string,
  configPath: string,
): RpcClient {
  const args = [
    "--no-extensions",
    ...(arm === "cassipi" ? ["-e", cassipiExtension] : []),
    "--config",
    configPath,
    "--resume",
    sessionFile,
    "--no-tools",
    "--no-skills",
    "--no-rules",
  ];
  return new RpcClient({
    command: [arm === "cassipi" ? cassipiHost : stockHost],
    cwd: root,
    provider: providerCase.provider,
    model: providerCase.model,
    sessionDir,
    args,
    env: {
      PI_CODING_AGENT_DIR: globalAgentDir,
      ...(arm === "cassipi"
        ? {
            CASSIPI_DATA_HOME: join(armRoot, "field"),
            CASSIPI_FI_RUNTIME: cassipiRuntime,
            CASSIPI_PROFILE_ID: `provider-comparison-${providerCase.provider}-${providerCase.model}-${basename(armRoot)}`,
          }
        : {}),
    },
  });
}

function finalPrompt(): string {
  return [
    "Use only the visible conversation and background evidence. Do not call tools.",
    "Return exactly one JSON object and no markdown.",
    'Keys: "current", "failed", "source", "proposal", "status", "branch_marker".',
    'For "current", copy the corrected current premise exactly.',
    'For "failed", copy the failed approach exactly.',
    'For "source", copy the exact current source anchor exactly.',
    'For "proposal", copy the discussed action exactly.',
    'For "status", copy its execution status exactly.',
    'For "branch_marker", copy any visible token beginning ALT_ONLY_; otherwise use null.',
  ].join("\n");
}

function parseObject(text: string): Record<string, unknown> | null {
  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  if (start < 0 || end <= start) return null;
  try {
    const value = JSON.parse(text.slice(start, end + 1));
    return value && typeof value === "object" && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

function scoreResponse(text: string, scenario: Scenario): {
  parsed: Record<string, unknown> | null;
  checks: Record<string, boolean>;
  score: number;
  maxScore: number;
} {
  const parsed = parseObject(text);
  const checks = {
    json_object: parsed !== null,
    current: parsed?.current === scenario.current,
    failed: parsed?.failed === scenario.failed,
    source: parsed?.source === scenario.source,
    proposal: parsed?.proposal === scenario.proposal,
    status: parsed?.status === scenario.status,
    stale_absent: !text.includes(scenario.stale),
    sibling_branch_absent: parsed?.branch_marker === null && !text.includes(scenario.branchMarker),
  };
  return {
    parsed,
    checks,
    score: Object.values(checks).filter(Boolean).length,
    maxScore: Object.keys(checks).length,
  };
}

function compactReceipt(index: number, value: Awaited<ReturnType<RpcClient["compact"]>>, marker: string) {
  return {
    index,
    tokensBefore: Number.isFinite(value.tokensBefore) ? value.tokensBefore : null,
    firstKeptEntry: typeof value.firstKeptEntryId === "string" && value.firstKeptEntryId.length > 0,
    summaryChars: value.summary?.length ?? 0,
    branchMarkerLeak: value.summary?.includes(marker) ?? false,
  };
}

function cleanError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  return message.replaceAll(globalAgentDir, "<configured-agent-dir>").slice(0, 2000);
}

async function runArm(
  arm: "stock" | "cassipi",
  providerCase: ProviderCase,
  scenario: Scenario,
  configs: { stock: string; cassipi: string },
): Promise<ArmResult> {
  const armRoot = join(runRoot, `${providerCase.provider}-${providerCase.model}`, scenario.id, arm);
  const sessionDir = join(armRoot, "sessions");
  rmSync(armRoot, { recursive: true, force: true });
  mkdirSync(armRoot, { recursive: true });
  const result: ArmResult = {
    arm,
    provider: providerCase.provider,
    model: providerCase.model,
    scenario: scenario.id,
    status: "failed",
    compactions: [],
  };

  try {
    const sessionFile = await createSeedSession(sessionDir, scenario, arm);
    for (let index = 0; index < 3; index++) {
      const client = createClient(
        arm,
        providerCase,
        sessionDir,
        sessionFile,
        armRoot,
        arm === "cassipi" ? configs.cassipi : configs.stock,
      );
      try {
        await client.start();
        await client.setAutoCompaction(false);
        await client.setThinkingLevel(ThinkingLevel.Medium);
        const compacted = await client.compact(compactionInstructions);
        result.compactions.push(compactReceipt(index + 1, compacted, scenario.branchMarker));
      } finally {
        await client.stop().catch(() => undefined);
      }
      if (index < 2) await appendContinuityTurns(sessionFile, sessionDir, scenario, arm, index);
    }

    const resumed = createClient(
      arm,
      providerCase,
      sessionDir,
      sessionFile,
      armRoot,
      arm === "cassipi" ? configs.cassipi : configs.stock,
    );
    try {
      await resumed.start();
      await resumed.setAutoCompaction(false);
      await resumed.setThinkingLevel(ThinkingLevel.Medium);
      await resumed.promptAndWait(finalPrompt(), undefined, 240_000);
      const response = await resumed.getLastAssistantText();
      assert(response, `${arm} final provider turn returned no assistant text`);
      const scored = scoreResponse(response, scenario);
      const stats = await resumed.getSessionStats();
      result.response = response;
      result.parsed = scored.parsed;
      result.checks = scored.checks;
      result.score = scored.score;
      result.maxScore = scored.maxScore;
      result.session = {
        file: basename(stats.sessionFile ?? sessionFile),
        tokens: stats.tokens,
        costUsd: stats.cost,
        routedModels: stats.routedModels,
      };
      result.status = "completed";
    } finally {
      await resumed.stop().catch(() => undefined);
    }
  } catch (error) {
    result.error = cleanError(error);
  }
  return result;
}

async function sha256(path: string): Promise<string> {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(path)) hash.update(chunk);
  return hash.digest("hex");
}

function comparisonSummary(results: ArmResult[]) {
  return providers.flatMap(providerCase =>
    scenarios.map(scenario => {
      const stock = results.find(
        result =>
          result.arm === "stock" &&
          result.provider === providerCase.provider &&
          result.model === providerCase.model &&
          result.scenario === scenario.id,
      );
      const cassipi = results.find(
        result =>
          result.arm === "cassipi" &&
          result.provider === providerCase.provider &&
          result.model === providerCase.model &&
          result.scenario === scenario.id,
      );
      return {
        provider: providerCase.provider,
        model: providerCase.model,
        scenario: scenario.id,
        stockScore: stock?.score ?? null,
        cassipiScore: cassipi?.score ?? null,
        delta:
          stock?.score !== undefined && cassipi?.score !== undefined
            ? cassipi.score - stock.score
            : null,
        stockCostUsd: stock?.session?.costUsd ?? null,
        cassipiCostUsd: cassipi?.session?.costUsd ?? null,
        stockTokens: stock?.session?.tokens.total ?? null,
        cassipiTokens: cassipi?.session?.tokens.total ?? null,
      };
    }),
  );
}

function observedResult(comparisons: ReturnType<typeof comparisonSummary>): string {
  const deltas = comparisons.map(item => item.delta);
  if (deltas.some(delta => delta === null)) return "INCOMPLETE";
  const values = deltas as number[];
  if (values.every(delta => delta === 0)) return "TIED_WITHIN_THIS_SYNTHETIC_SAMPLE";
  if (values.every(delta => delta >= 0)) return "CASSIPI_OUTPERFORMED_WITHIN_THIS_SYNTHETIC_SAMPLE";
  if (values.every(delta => delta <= 0)) return "STOCK_OUTPERFORMED_WITHIN_THIS_SYNTHETIC_SAMPLE";
  return "MIXED_WITHIN_THIS_SYNTHETIC_SAMPLE";
}

async function main(): Promise<void> {
  const prepareOnly = process.argv.includes("--prepare-only");
  assert(
    prepareOnly || process.argv.includes("--confirmed-real-provider-calls"),
    "Real provider comparison requires --confirmed-real-provider-calls after explicit operator approval",
  );
  for (const required of [
    stockHost,
    cassipiHost,
    cassipiExtension,
    cassipiRuntime,
    globalAgentDir,
    releaseManifestPath,
  ]) {
    assert(existsSync(required), `required comparison input is missing: ${required}`);
  }

  rmSync(runRoot, { recursive: true, force: true });
  mkdirSync(runRoot, { recursive: true });
  const configs = writeConfigs();
  if (prepareOnly) {
    for (const scenario of scenarios) {
      for (const arm of ["stock", "cassipi"] as const) {
        const sessionDir = join(runRoot, "prepared", scenario.id, arm, "sessions");
        await createSeedSession(sessionDir, scenario, arm);
      }
    }
    console.log("PREPARED 4 synthetic sessions; no provider calls were made");
    return;
  }
  const releaseManifest = JSON.parse(readFileSync(releaseManifestPath, "utf8"));
  const results: ArmResult[] = [];
  for (const providerCase of providers) {
    for (const scenario of scenarios) {
      for (const arm of ["stock", "cassipi"] as const) {
        console.log(`RUN ${providerCase.provider}/${providerCase.model} ${scenario.id} ${arm}`);
        const result = await runArm(arm, providerCase, scenario, configs);
        results.push(result);
        console.log(
          `${result.status.toUpperCase()} ${providerCase.provider}/${providerCase.model} ${scenario.id} ${arm}` +
            (result.score === undefined ? "" : ` score=${result.score}/${result.maxScore}`),
        );
      }
    }
  }

  const comparisons = comparisonSummary(results);
  const complete = results.every(
    result => result.status === "completed" && result.compactions.length === 3,
  );
  const receipt = {
    schema: "cassipi.provider-comparison.v1",
    createdAt: new Date().toISOString(),
    verdict: complete ? "PASS" : "FAIL",
    observedResult: observedResult(comparisons),
    scope: {
      description:
        "Full-factorial synthetic stock-versus-CassiPi comparison across two configured provider families and two held-out task variants.",
      arms: results.length,
      compactionsPerArm: 3,
      restartPolicy: "close and reopen around every compaction and final provider turn",
      branchPolicy: "inactive sibling carries a task-private conflicting marker that must not enter active context",
      safety:
        "Only synthetic prompts and synthetic session records were sent. Existing provider credentials were referenced in place and were not copied or recorded. The live profile was not changed.",
      interpretation:
        "This is a small deterministic integration comparison, not a population benchmark or evidence of general model-quality superiority.",
    },
    providers,
    scenarios: scenarios.map(({ branchMarker: _branchMarker, ...scenario }) => ({
      ...scenario,
      branchMarkerDisclosure: "redacted from receipt until scoring; exact marker remains only in disposable local run data",
    })),
    identities: {
      stockHostVersion: "18.1.10",
      stockHostSha256: await sha256(stockHost),
      cassipiReleaseHostSha256: releaseManifest.host.binary_sha256,
      cassipiInstalledHostSha256: await sha256(cassipiHost),
      cassipiPatchSha256: releaseManifest.host.patch_sha256,
      cassipiRuntimeId: releaseManifest.runtime.runtime_id,
      cassipiRuntimeManifestSha256: releaseManifest.runtime.manifest_sha256,
    },
    comparisons,
    results,
  };
  writeFileSync(receiptPath, `${JSON.stringify(receipt, null, 2)}\n`, "utf8");
  console.log(`RECEIPT ${receiptPath}`);
  console.log(`VERDICT ${receipt.verdict}`);
  console.log(`OBSERVED_RESULT ${receipt.observedResult}`);
  if (!complete) process.exitCode = 1;
}

await main();
