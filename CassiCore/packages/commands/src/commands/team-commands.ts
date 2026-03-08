// Team Commands for Universal Processor
// User-facing /team command for managing autonomous triad-team sessions.

import type { CommandContext, CommandResult } from "./universal-processor.js";
import { processor } from "./universal-processor.js";

const ADMIN_BASE = "http://localhost:7433";

processor.register({
  name: "/team",
  aliases: ["/t"],
  category: "intelligence",
  description: "Manage autonomous triad teams — start, status, stream, pause, resume, cancel, list, tree, checkpoint",
  handler: async (args, ctx): Promise<CommandResult> => {
    const subcmd = (args[0] || "help").toLowerCase();
    const rest = args.slice(1);

    switch (subcmd) {
      case "start":
      case "create":
        return handleTeamStart(rest, ctx);

      case "status":
      case "s":
        return handleTeamStatus(rest, ctx);

      case "list":
      case "ls":
        return handleTeamList(ctx);

      case "tree":
        return handleTeamTree(rest, ctx);

      case "pause":
        return handleTeamAction("pause", rest, ctx);

      case "resume":
        return handleTeamAction("resume", rest, ctx);

      case "cancel":
      case "stop":
        return handleTeamAction("cancel", rest, ctx);

      case "checkpoints":
      case "cp":
        return handleTeamCheckpoints(rest, ctx);

      case "approve":
        return handleTeamCheckpointAction("approve", rest, ctx);

      case "reject":
        return handleTeamCheckpointAction("reject", rest, ctx);

      case "steer":
        return handleTeamCheckpointAction("steer", rest, ctx);

      case "stream":
      case "events":
      case "log":
        return handleTeamStream(rest, ctx);

      case "bench":
      case "benchmark":
        return handleTeamBenchmark(rest, ctx);

      case "help":
      default:
        return {
          text: [
            "Triad Team Management Commands:",
            "",
            "  /team start <goal>          Start a new triad team with the given goal",
            "  /team status [team_id]      Show team status and cell progress",
            "  /team list                  List all teams",
            "  /team tree [team_id]        Show cell hierarchy tree",
            "  /team pause [team_id]       Pause a running team",
            "  /team resume [team_id]      Resume a paused team",
            "  /team cancel [team_id]      Cancel a team",
            "  /team checkpoints [team_id] List pending checkpoints",
            "  /team approve <cp_id> [msg] Approve a checkpoint",
            "  /team reject <cp_id> [msg]  Reject a checkpoint",
            "  /team steer <cp_id> <msg>   Steer a checkpoint with instructions",
             "  /team stream [team_id]      Show live event stream (recent events + SSE URL)",
             "  /team bench <goal>          Run a benchmark: start team, monitor, run tests, report",
            "",
            "Options for /team start:",
            "  --budget <tokens>           Max token budget (default: 2000000)",
            "  --cells <max>               Max cells (default: 20)",
            "  --depth <max>               Max hierarchy depth (default: 3)",
            "  --timeout <minutes>         Max duration in minutes (default: 240)",
            "  --checkpoint none|cassi|human  Checkpoint mode (default: cassi)",
            "  --provider <id>             Provider for team cells",
            "  --model <model>             Model for team cells",
            "",
            "Aliases: /t",
          ].join("\n"),
        };
    }
  },
});

// ── Subcommand Handlers ────────────────────────────────────────────────────

async function handleTeamStart(args: string[], ctx: CommandContext): Promise<CommandResult> {
  // Parse flags from args
  const flags: Record<string, string> = {};
  const goalParts: string[] = [];

  for (let i = 0; i < args.length; i++) {
    if (args[i].startsWith("--") && i + 1 < args.length) {
      const flag = args[i].slice(2);
      flags[flag] = args[++i];
    } else {
      goalParts.push(args[i]);
    }
  }

  const goal = goalParts.join(" ");
  if (!goal) {
    return { text: "Usage: /team start <goal description>\nExample: /team start Refactor the auth module to use JWT tokens" };
  }

  const body: Record<string, unknown> = {
    goal,
    sessionId: ctx.sessionId,
  };

  // Map flags to triad-team config
  if (flags.budget) body.maxTokens = parseInt(flags.budget, 10);
  if (flags.cells) body.maxCells = parseInt(flags.cells, 10);
  if (flags.agents) body.maxCells = parseInt(flags.agents, 10); // backward compat alias
  if (flags.depth) body.maxDepth = parseInt(flags.depth, 10);
  if (flags.timeout) body.maxDurationMs = parseInt(flags.timeout, 10) * 60_000;
  if (flags.checkpoint) body.checkpointMode = flags.checkpoint;
  if (flags.provider) body.provider = flags.provider;
  if (flags.model) body.model = flags.model;

  try {
    const response = await fetch(`${ADMIN_BASE}/teams`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const result = await response.json() as { error?: string; teamId?: string; status?: string };

    if (result.error) return { text: `Failed to start team: ${result.error}` };

    return {
      text: [
        `Triad team started: ${result.teamId}`,
        `Status: ${result.status}`,
        `Goal: ${goal}`,
        "",
        `Use "/team status ${result.teamId}" to monitor progress.`,
        `Use "/team tree ${result.teamId}" to see cell hierarchy.`,
      ].join("\n"),
    };
  } catch (err) {
    return { text: `Failed to start team: ${String(err)}` };
  }
}

async function handleTeamStatus(args: string[], ctx: CommandContext): Promise<CommandResult> {
  const teamId = args[0] || "";
  const query = teamId ? `?teamId=${encodeURIComponent(teamId)}` : "";

  try {
    const response = await fetch(`${ADMIN_BASE}/teams/status${query}`);
    const result = await response.json() as { error?: string; [key: string]: unknown };

    if (result.error) return { text: `Error: ${result.error}` };

    return { text: formatTeamStatus(result) };
  } catch (err) {
    return { text: `Failed to get team status: ${String(err)}` };
  }
}

async function handleTeamList(ctx: CommandContext): Promise<CommandResult> {
  try {
    const response = await fetch(`${ADMIN_BASE}/teams`);
    const result = await response.json() as { error?: string; teams?: Array<Record<string, unknown>> };

    if (result.error) return { text: `Error: ${result.error}` };

    const teams = result.teams || [];
    if (teams.length === 0) return { text: "No teams found." };

    const lines = [`Teams (${teams.length}):`];
    for (const t of teams) {
      const elapsed = t.createdAt ? Math.round((Date.now() - (t.createdAt as number)) / 60000) : 0;
      lines.push(
        `  ${t.id} | ${t.status} | ${t.cellCount || 0} cells | ${elapsed}min | ${t.name || "(unnamed)"}`
      );
    }

    return { text: lines.join("\n") };
  } catch (err) {
    return { text: `Failed to list teams: ${String(err)}` };
  }
}

async function handleTeamTree(args: string[], ctx: CommandContext): Promise<CommandResult> {
  const teamId = args[0] || "";
  const query = teamId ? `?teamId=${encodeURIComponent(teamId)}` : "";

  try {
    const response = await fetch(`${ADMIN_BASE}/teams/tree${query}`);
    const result = await response.json() as { error?: string; tree?: string; progress?: Record<string, unknown> };

    if (result.error) return { text: `Error: ${result.error}` };

    const lines: string[] = [];
    if (result.progress) {
      const p = result.progress;
      lines.push(`Progress: ${p.completed}/${p.total} cells (${p.completionPct}%) | In Progress: ${p.inProgress} | Failed: ${p.failed} | Blocked: ${p.blocked}`);
      lines.push("");
    }
    lines.push(result.tree || "(no cell tree)");

    return { text: lines.join("\n") };
  } catch (err) {
    return { text: `Failed to get cell tree: ${String(err)}` };
  }
}

async function handleTeamAction(
  action: "pause" | "resume" | "cancel",
  args: string[],
  ctx: CommandContext,
): Promise<CommandResult> {
  const teamId = args[0] || "";

  try {
    const response = await fetch(`${ADMIN_BASE}/teams/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ teamId }),
    });
    const result = await response.json() as { error?: string; status?: string };

    if (result.error) return { text: `Error: ${result.error}` };

    const verb = action === "pause" ? "paused" : action === "resume" ? "resumed" : "cancelled";
    return { text: `Team ${teamId || "(latest)"} ${verb}. Status: ${result.status || verb}` };
  } catch (err) {
    return { text: `Failed to ${action} team: ${String(err)}` };
  }
}

async function handleTeamCheckpoints(args: string[], ctx: CommandContext): Promise<CommandResult> {
  const teamId = args[0] || "";
  const query = teamId ? `?teamId=${encodeURIComponent(teamId)}` : "";

  try {
    const response = await fetch(`${ADMIN_BASE}/teams/checkpoints${query}`);
    const result = await response.json() as { error?: string; checkpoints?: Array<Record<string, unknown>> };

    if (result.error) return { text: `Error: ${result.error}` };

    const cps = result.checkpoints || [];
    if (cps.length === 0) return { text: "No pending checkpoints." };

    const lines = [`Pending Checkpoints (${cps.length}):`];
    for (const cp of cps) {
      lines.push(`  ${cp.id} | trigger: ${cp.trigger} | progress: ${cp.progressSummary}`);
      if (cp.budgetSnapshot) {
        const b = cp.budgetSnapshot as Record<string, unknown>;
        lines.push(`    tokens: ${b.tokensUsed}/${b.maxTokens} | cells: ${b.cellsSpawned}/${b.maxCells}`);
      }
    }
    lines.push("");
    lines.push('Use "/team approve <cp_id>" or "/team reject <cp_id> [reason]" to respond.');

    return { text: lines.join("\n") };
  } catch (err) {
    return { text: `Failed to get checkpoints: ${String(err)}` };
  }
}

async function handleTeamCheckpointAction(
  action: "approve" | "reject" | "steer",
  args: string[],
  ctx: CommandContext,
): Promise<CommandResult> {
  const checkpointId = args[0];
  if (!checkpointId) {
    return { text: `Usage: /team ${action} <checkpoint_id>${action === "steer" ? " <instructions>" : " [message]"}` };
  }

  const message = args.slice(1).join(" ") || undefined;

  if (action === "steer" && !message) {
    return { text: "Usage: /team steer <checkpoint_id> <steering instructions>" };
  }

  try {
    const response = await fetch(`${ADMIN_BASE}/teams/checkpoints/${encodeURIComponent(checkpointId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, message }),
    });
    const result = await response.json() as { error?: string };

    if (result.error) return { text: `Error: ${result.error}` };

    const verb = action === "approve" ? "Approved" : action === "reject" ? "Rejected" : "Steered";
    return { text: `${verb} checkpoint ${checkpointId}${message ? `: ${message}` : ""}` };
  } catch (err) {
    return { text: `Failed to ${action} checkpoint: ${String(err)}` };
  }
}

async function handleTeamStream(args: string[], ctx: CommandContext): Promise<CommandResult> {
  const teamId = args[0] || "";
  const query = teamId ? `?teamId=${encodeURIComponent(teamId)}` : "";

  try {
    // Fetch recent events
    const separator = query ? "&" : "?";
    const eventsResp = await fetch(`${ADMIN_BASE}/teams/events${query}${separator}limit=30`);
    const eventsResult = await eventsResp.json() as {
      error?: string;
      teamId?: string;
      total?: number;
      events?: Array<{ type: string; timestamp: number; message?: string; entityId?: string; data?: Record<string, unknown> }>;
    };

    if (eventsResult.error) return { text: `Error: ${eventsResult.error}` };

    const resolvedTeamId = eventsResult.teamId || teamId || "(unknown)";
    const events = eventsResult.events || [];
    const total = eventsResult.total || 0;

    // Also fetch current status
    const statusResp = await fetch(`${ADMIN_BASE}/teams/status?teamId=${encodeURIComponent(resolvedTeamId)}`);
    const statusResult = await statusResp.json() as { error?: string; [key: string]: unknown };

    const lines: string[] = [];

    // Header
    lines.push(`Triad Team Event Stream: ${resolvedTeamId}`);
    lines.push("─".repeat(60));

    // Current status summary
    if (!statusResult.error) {
      lines.push(`Status: ${statusResult.status || "unknown"}`);
      const cells = statusResult.cells as Record<string, unknown> | undefined;
      if (cells) {
        const cellCount = Object.keys(cells).length;
        lines.push(`Cells: ${cellCount}`);
      }
      lines.push("");
    }

    // Recent events
    if (events.length === 0) {
      lines.push("No events recorded yet.");
    } else {
      const showing = total > events.length ? `(showing last ${events.length} of ${total})` : `(${events.length} total)`;
      lines.push(`Recent Events ${showing}:`);
      lines.push("");

      for (const event of events) {
        const ts = event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "??:??";
        const icon = getEventIcon(event.type);
        const detail = event.message || "";
        lines.push(`  ${ts} ${icon} ${detail}`);
      }
    }

    // SSE URL for real-time monitoring
    lines.push("");
    lines.push("─".repeat(60));
    lines.push(`SSE endpoint: ${ADMIN_BASE}/teams/stream?teamId=${encodeURIComponent(resolvedTeamId)}`);
    lines.push("Connect with: curl -N <url> for real-time updates");

    return { text: lines.join("\n") };
  } catch (err) {
    return { text: `Failed to fetch team stream: ${String(err)}` };
  }
}

function getEventIcon(type: string): string {
  const icons: Record<string, string> = {
    "triad-team:created": "[CREATE]",
    "triad-team:started": "[START]",
    "triad-team:planning": "[PLAN]",
    "triad-team:plan-complete": "[PLAN OK]",
    "triad-team:cell-spawned": "[+CELL]",
    "triad-team:cell-phase": "[PHASE]",
    "triad-team:cell-completed": "[CELL OK]",
    "triad-team:cell-failed": "[CELL FAIL]",
    "triad-team:cell-degraded": "[DEGRADE]",
    "triad-team:synthesis": "[SYNTH]",
    "triad-team:completed": "[DONE]",
    "triad-team:failed": "[FAIL]",
    "triad-team:cancelled": "[CANCEL]",
    "triad-team:paused": "[PAUSE]",
    "triad-team:resumed": "[RESUME]",
    "triad-team:checkpoint": "[CHECK]",
    "triad-team:checkpoint:approved": "[APPROVED]",
    "triad-team:checkpoint:rejected": "[REJECTED]",
    "triad-team:budget-warning": "[BUDGET]",
  };
  return icons[type] || `[${type.split(":").pop()?.toUpperCase() || "?"}]`;
}

// ── Formatting Helpers ─────────────────────────────────────────────────────

function formatTeamStatus(data: Record<string, unknown>): string {
  const config = data.config as Record<string, unknown> | undefined;
  const budget = data.budget as Record<string, unknown> | undefined;
  const elapsed = data.startedAt ? Math.round((Date.now() - (data.startedAt as number)) / 60000) : 0;
  const cells = data.cells as Record<string, unknown> | undefined;
  const cellCount = cells ? Object.keys(cells).length : 0;

  const lines = [
    `Team: ${config?.name || data.id || "(unknown)"}`,
    `Status: ${data.status}`,
    `Goal: ${config?.goal || "(unknown)"}`,
    `Elapsed: ${elapsed}min`,
    `Cells: ${cellCount}`,
  ];

  if (budget) {
    const tokensUsed = budget.tokensUsed as number || 0;
    const maxTokens = budget.maxTokens as number || 1;
    const tokenPct = Math.round((tokensUsed / maxTokens) * 100);
    lines.push("");
    lines.push("Budget:");
    lines.push(`  Tokens: ${tokensUsed.toLocaleString()}/${maxTokens.toLocaleString()} (${tokenPct}%)`);
    lines.push(`  Cells: ${budget.cellsSpawned || 0}/${budget.maxCells || "unlimited"}`);
    lines.push(`  Depth: max ${budget.maxDepth || "?"}`);
  }

  if (data.finalResult) {
    lines.push("");
    lines.push("Result:");
    lines.push(`  ${(data.finalResult as string).slice(0, 500)}`);
  }

  return lines.join("\n");
}

// ── Benchmark ────────────────────────────────────────────────────────────────

async function handleTeamBenchmark(args: string[], ctx: CommandContext): Promise<CommandResult> {
  // Parse flags from args
  const flags = parseFlags(args);
  const goal = flags.positional.join(" ");

  if (!goal) {
    return {
      text: [
        "Usage: /team bench <goal> [options]",
        "",
        "Options:",
        "  --provider <id>       Provider ID (default: github-copilot)",
        "  --model <model>       Model name (default: gpt-5-mini)",
        "  --budget <tokens>     Max token budget (default: 300000)",
        "  --depth <max>         Max hierarchy depth (default: 1)",
        "  --cells <max>         Max cells (default: 3)",
        "  --test <path>         Test path to verify (e.g., tests/my.test.ts)",
        "  --cleanup             Delete generated files after benchmark",
        "",
        "Example:",
        '  /team bench "Write a deepMerge utility in tests/bench-merge.ts with tests" --test tests/bench-merge.test.ts --cleanup',
      ].join("\n"),
    };
  }

  const provider = flags.get("provider") || "github-copilot";
  const model = flags.get("model") || "gpt-5-mini";
  const budget = parseInt(flags.get("budget") || "300000");
  const depth = parseInt(flags.get("depth") || "1");
  const cells = parseInt(flags.get("cells") || "3");
  const testPath = flags.get("test") || flags.get("tests");
  const cleanup = flags.has("cleanup");

  const requestBody: Record<string, unknown> = {
    goal,
    name: "Benchmark",
    provider: { providerId: provider, model },
    budget: { maxTokens: budget, maxCells: cells, maxDepth: depth, maxDurationMs: 600000, maxToolIterationsPerMember: 50 },
  };

  if (testPath) {
    requestBody.testPaths = [testPath];
  }
  if (cleanup) {
    requestBody.cleanup = true;
  }

  try {
    // Use SSE stream to get live updates
    const res = await fetch(`${ADMIN_BASE}/teams/benchmark`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });

    if (!res.ok) {
      const err = await res.text();
      return { text: `Benchmark failed: ${err}` };
    }

    // Parse SSE stream
    const reader = res.body?.getReader();
    if (!reader) {
      return { text: "No response stream" };
    }

    const lines: string[] = [];
    lines.push(`Benchmark started — goal: ${goal.slice(0, 80)}...`);
    lines.push(`Provider: ${provider}/${model} | Budget: ${budget.toLocaleString()} tokens | Depth: ${depth}`);
    lines.push("");

    const decoder = new TextDecoder();
    let buffer = "";
    let finalReport: Record<string, unknown> | null = null;

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const part of parts) {
          const eventMatch = part.match(/^event: (.+)$/m);
          const dataMatch = part.match(/^data: (.+)$/m);
          if (!eventMatch || !dataMatch) continue;

          const eventType = eventMatch[1];
          let data: any;
          try { data = JSON.parse(dataMatch[1]); } catch { continue; }

          switch (eventType) {
            case "benchmark:team-created":
              lines.push(`Team created: ${data.teamId}`);
              break;
            case "team-event":
              if (data.type === "triad-team:cell-phase") {
                lines.push(`  Phase: ${data.data?.phase || data.phase || "?"}`);
              } else if (data.type === "triad-team:completed" || data.type === "triad-team:failed") {
                lines.push(`  ${data.type.replace("triad-team:", "")}`);
              }
              break;
            case "benchmark:team-complete":
              lines.push("");
              lines.push(`Team ${data.status} in ${(data.duration / 1000).toFixed(1)}s — ${data.tokens?.toLocaleString()} tokens, ${data.cells} cells`);
              break;
            case "benchmark:test-result":
              lines.push("");
              lines.push(`Tests: ${data.passed} passed, ${data.failed} failed`);
              if (data.failed > 0) {
                lines.push(data.output?.slice(0, 500) || "");
              }
              break;
            case "benchmark:cleanup":
              lines.push(`Cleaned up: ${data.files?.join(", ")}`);
              break;
            case "benchmark:complete":
              finalReport = data;
              lines.push("");
              lines.push("─── Final Report ───");
              lines.push(`Status: ${data.status}`);
              lines.push(`Duration: ${(data.duration / 1000).toFixed(1)}s`);
              lines.push(`Tokens: ${data.tokens?.toLocaleString()}`);
              lines.push(`Cells: ${data.cells}`);
              lines.push(`Phases: ${data.phases?.join(" → ") || "?"}`);
              if (data.testResults) {
                lines.push(`Tests: ${data.testResults.passed} passed, ${data.testResults.failed} failed`);
              }
              break;
          }
        }
      }
    } finally {
      reader.releaseLock();
    }

    return { text: lines.join("\n") };
  } catch (err) {
    return { text: `Benchmark error: ${String(err)}` };
  }
}

/** Parse --flag value pairs and collect positional arguments */
function parseFlags(args: string[]): { positional: string[]; get(key: string): string | undefined; has(key: string): boolean } {
  const flags = new Map<string, string>();
  const positional: string[] = [];

  for (let i = 0; i < args.length; i++) {
    if (args[i].startsWith("--")) {
      const key = args[i].slice(2);
      if (i + 1 < args.length && !args[i + 1].startsWith("--")) {
        flags.set(key, args[i + 1]);
        i++;
      } else {
        flags.set(key, "true");
      }
    } else {
      positional.push(args[i]);
    }
  }

  return {
    positional,
    get: (key: string) => flags.get(key),
    has: (key: string) => flags.has(key),
  };
}
