// Team Commands for Universal Processor
// User-facing /team command for managing autonomous team sessions.

import type { CommandContext, CommandResult } from "./universal-processor.js";
import { processor } from "./universal-processor.js";

const ADMIN_BASE = "http://localhost:7433";

processor.register({
  name: "/team",
  aliases: ["/t"],
  category: "intelligence",
  description: "Manage autonomous teams — start, status, stream, pause, resume, cancel, list, tree, checkpoint",
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

      case "help":
      default:
        return {
          text: [
            "Team Management Commands:",
            "",
            "  /team start <goal>          Start a new team with the given goal",
            "  /team status [team_id]      Show team status and progress",
            "  /team list                  List all teams",
            "  /team tree [team_id]        Show goal tree visualization",
            "  /team pause [team_id]       Pause a running team",
            "  /team resume [team_id]      Resume a paused team",
            "  /team cancel [team_id]      Cancel a team",
            "  /team checkpoints [team_id] List pending checkpoints",
            "  /team approve <cp_id> [msg] Approve a checkpoint",
            "  /team reject <cp_id> [msg]  Reject a checkpoint",
            "  /team steer <cp_id> <msg>   Steer a checkpoint with instructions",
            "  /team stream [team_id]      Show live event stream (recent events + SSE URL)",
            "",
            "Options for /team start:",
            "  --budget <tokens>           Max token budget (default: 500000)",
            "  --agents <max>              Max concurrent agents (default: 5)",
            "  --depth <max>               Max goal tree depth (default: 4)",
            "  --timeout <minutes>         Max duration in minutes (default: 60)",
            "  --checkpoint none|cassi     Checkpoint mode (default: cassi)",
            "  --provider <id>             Provider for team agents",
            "  --destructive               Allow destructive file operations",
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
      // --destructive is a boolean flag (no value)
      if (flag === "destructive") {
        flags[flag] = "true";
      } else {
        flags[flag] = args[++i];
      }
    } else if (args[i] === "--destructive") {
      flags["destructive"] = "true";
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

  // Map flags to config
  if (flags.budget) body.maxTokens = parseInt(flags.budget, 10);
  if (flags.agents) body.maxAgents = parseInt(flags.agents, 10);
  if (flags.depth) body.maxDepth = parseInt(flags.depth, 10);
  if (flags.timeout) body.maxDurationMs = parseInt(flags.timeout, 10) * 60_000;
  if (flags.checkpoint) body.checkpointMode = flags.checkpoint;
  if (flags.provider) body.provider = flags.provider;
  if (flags.destructive) body.allowDestructive = true;

  try {
    const response = await fetch(`${ADMIN_BASE}/teams`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const result = await response.json() as { error?: string; teamId?: string; status?: string; coordinatorAgentId?: string };

    if (result.error) return { text: `Failed to start team: ${result.error}` };

    return {
      text: [
        `Team started: ${result.teamId}`,
        `Status: ${result.status}`,
        `Coordinator: ${result.coordinatorAgentId || "(pending)"}`,
        `Goal: ${goal}`,
        "",
        `Use "/team status ${result.teamId}" to monitor progress.`,
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
      const elapsed = t.startedAt ? Math.round((Date.now() - (t.startedAt as number)) / 60000) : 0;
      lines.push(
        `  ${t.id} | ${t.status} | ${elapsed}min | goal: "${(t.goal as string || "").slice(0, 60)}${(t.goal as string || "").length > 60 ? "..." : ""}"`
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
      lines.push(`Progress: ${p.completed}/${p.total} (${p.completionPct}%) | In Progress: ${p.inProgress} | Failed: ${p.failed} | Blocked: ${p.blocked}`);
      lines.push("");
    }
    lines.push(result.tree || "(no goal tree)");

    return { text: lines.join("\n") };
  } catch (err) {
    return { text: `Failed to get goal tree: ${String(err)}` };
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
        lines.push(`    tokens: ${b.tokensUsed}/${b.maxTokens} | agents: ${b.agentsSpawned}/${b.maxAgents}`);
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
    const eventsResp = await fetch(`${ADMIN_BASE}/teams/events${query}&limit=30`);
    const eventsResult = await eventsResp.json() as {
      error?: string;
      teamId?: string;
      total?: number;
      events?: Array<{ type: string; timestamp: number; data?: Record<string, unknown> }>;
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
    lines.push(`Team Event Stream: ${resolvedTeamId}`);
    lines.push("─".repeat(60));

    // Current status summary
    if (!statusResult.error) {
      const team = statusResult.team as Record<string, unknown> | undefined;
      const progress = statusResult.progress as Record<string, unknown> | undefined;
      if (team) {
        lines.push(`Status: ${team.status} | Agents: ${(statusResult.activeAgents as unknown[])?.length || 0} active`);
      }
      if (progress) {
        lines.push(`Progress: ${progress.completed}/${progress.total} goals (${progress.completionPct}%)`);
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
        const detail = formatEventDetail(event);
        lines.push(`  ${ts} ${icon} ${event.type}${detail ? ` — ${detail}` : ""}`);
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
    "team:started": "[START]",
    "team:completed": "[DONE]",
    "team:failed": "[FAIL]",
    "team:cancelled": "[CANCEL]",
    "team:paused": "[PAUSE]",
    "team:resumed": "[RESUME]",
    "team:budget:warning": "[BUDGET]",
    "team:checkpoint": "[CHECK]",
    "agent:spawned": "[+AGENT]",
    "agent:completed": "[AGENT OK]",
    "agent:error": "[AGENT ERR]",
    "autonomy:iteration": "[ITER]",
    "autonomy:loop_started": "[LOOP]",
    "autonomy:loop_stopped": "[STOP]",
    "autonomy:delegation_requested": "[DELEG]",
    "autonomy:blocked": "[BLOCK]",
  };
  return icons[type] || `[${type.split(":").pop()?.toUpperCase() || "?"}]`;
}

function formatEventDetail(event: { type: string; data?: Record<string, unknown>; [key: string]: unknown }): string {
  const d = event.data || event;
  switch (event.type) {
    case "agent:spawned":
      return d.role ? `role=${d.role}` : "";
    case "agent:completed":
      return d.agentId ? `${d.agentId}` : "";
    case "agent:error":
      return d.error ? String(d.error).slice(0, 80) : "";
    case "autonomy:iteration":
      return d.iteration ? `#${d.iteration}` + (d.tokensUsed ? ` (${d.tokensUsed} tokens)` : "") : "";
    case "team:budget:warning":
      return d.percentUsed ? `${d.percentUsed}% used` : "";
    case "team:checkpoint":
      return d.trigger ? `trigger=${d.trigger}` : "";
    case "autonomy:delegation_requested":
      return d.delegateTask ? String(d.delegateTask).slice(0, 60) : "";
    case "autonomy:blocked":
      return d.reason ? String(d.reason).slice(0, 60) : "";
    default:
      return "";
  }
}

// ── Formatting Helpers ─────────────────────────────────────────────────────

function formatTeamStatus(data: Record<string, unknown>): string {
  const team = data.team as Record<string, unknown> | undefined;
  if (!team) return JSON.stringify(data, null, 2);

  const config = team.config as Record<string, unknown> | undefined;
  const budget = team.budget as Record<string, unknown> | undefined;
  const elapsed = team.startedAt ? Math.round((Date.now() - (team.startedAt as number)) / 60000) : 0;

  const lines = [
    `Team: ${config?.name || team.id}`,
    `Status: ${team.status}`,
    `Goal: ${config?.goal || "(unknown)"}`,
    `Elapsed: ${elapsed}min`,
  ];

  if (budget) {
    const tokenPct = Math.round(((budget.tokensUsed as number) / (budget.maxTokens as number)) * 100);
    lines.push("");
    lines.push("Budget:");
    lines.push(`  Tokens: ${(budget.tokensUsed as number).toLocaleString()}/${(budget.maxTokens as number).toLocaleString()} (${tokenPct}%)`);
    lines.push(`  Agents: ${budget.agentsSpawned}/${budget.maxAgents}`);
    lines.push(`  Cost: $${(budget.estimatedCostUsd as number || 0).toFixed(4)}`);
  }

  if (data.goalTree) {
    lines.push("");
    lines.push("Goal Tree:");
    lines.push(data.goalTree as string);
  }

  const progress = data.progress as Record<string, unknown> | undefined;
  if (progress) {
    lines.push("");
    lines.push(`Progress: ${progress.completed}/${progress.total} goals (${progress.completionPct}%)`);
    if ((progress.failed as number) > 0) lines.push(`  Failed: ${progress.failed}`);
    if ((progress.blocked as number) > 0) lines.push(`  Blocked: ${progress.blocked}`);
  }

  const agents = data.activeAgents as Array<Record<string, unknown>> | undefined;
  if (agents && agents.length > 0) {
    lines.push("");
    lines.push(`Active Agents (${agents.length}):`);
    for (const a of agents) {
      lines.push(`  ${a.agentId}: "${a.goalTitle}"`);
    }
  }

  const checkpoints = data.pendingCheckpoints as Array<Record<string, unknown>> | undefined;
  if (checkpoints && checkpoints.length > 0) {
    lines.push("");
    lines.push(`Pending Checkpoints (${checkpoints.length}):`);
    for (const cp of checkpoints) {
      lines.push(`  ${cp.id} (${cp.trigger}): ${cp.progressSummary}`);
    }
  }

  return lines.join("\n");
}
