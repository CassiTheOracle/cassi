#!/usr/bin/env node
/**
 * Flux Tools Module — Unified Team Orchestration Toolset
 * 
 * DESIGN RATIONALE:
 * This module consolidates team orchestration into a minimal, coherent toolset that eliminates
 * the fragmented cassi_* tool design. The flux_* tools follow a clear separation of concerns:
 * 
 * - flux_team: Pure CRUD operations on teams (start, pause, resume, cancel, checkpoint approval)
 * - flux_run: Composite workflow that manages a team's full lifecycle with automated checkpoint handling
 * - flux_inspect: Composite read-only inspection combining status + tree + events + live data
 * - flux_watch: SSE-based blocking wait for significant team events
 * 
 * KEY DESIGN DECISIONS:
 * 
 * 1. **Client-Side Checkpoint Policy (flux_run)**:
 *    Checkpoint approval logic runs in the MCP gateway, not the daemon. This allows:
 *    - Flexible policies without daemon restarts
 *    - Per-run policy selection (auto-approve vs interactive)
 *    - Timeout-based auto-degradation (interactive → auto-approve after N seconds)
 *    
 *    The daemon exposes checkpoints as a passive resource; the client decides when/how to approve.
 * 
 * 2. **No Circular Dependencies**:
 *    This module imports ONLY from helpers.ts and types. It does NOT import from:
 *    - team-tools.ts (legacy CRUD tool)
 *    - composite-tools.ts (legacy composite tools)
 *    
 *    This prevents circular dependency chains and allows flux-tools to be the canonical source.
 * 
 * 3. **FluxTeam vs TriadTeam Compatibility**:
 *    All flux_* tools work with both FluxTeam and TriadTeam backends. The daemon's
 *    /teams/* endpoints abstract the underlying engine. The useFluxTeam parameter
 *    on flux_team start action allows explicit engine selection.
 * 
 * 4. **SSE Heartbeat Pattern**:
 *    flux_watch uses SSE streaming with 15-second heartbeats to prevent MCP client timeouts.
 *    The heartbeat callback resets the client-side inactivity timer, allowing waits up to 600s.
 * 
 * MIGRATION PATH:
 *    - cassi_team → flux_team (direct replacement, same action-param pattern)
 *    - cassi_team_inspect → flux_inspect (enhanced version with live cell data)
 *    - cassi_team_watch → flux_watch (identical behavior, clearer naming)
 *    - cassi_team_start + manual checkpoint loops → flux_run (composite workflow)
 * 
 * @module flux-tools
 */

import { fetchWithTimeout, watchViaSSE } from './helpers.js';
import type { ILogger } from '@cassicore/foundation';

/**
 * Checkpoint approval policy for flux_run composite workflow.
 * 
 * - 'auto-approve': Automatically approve all checkpoints without human intervention.
 *   Best for: Low-risk tasks, trusted agents, CI/CD pipelines.
 * 
 * - 'auto-reject': Automatically reject all checkpoints.
 *   Best for: Dry-run mode, testing, preventing unintended changes.
 * 
 * - 'interactive': Pause and wait for human approval via MCP client.
 *   Best for: High-stakes changes, novel tasks, learning mode.
 *   Requires MCP client to support pending confirmation handling.
 * 
 * - 'timeout': Start in interactive mode, but auto-approve after timeoutSecs.
 *   Best for: Balancing safety with progress guarantees.
 *   Falls back to auto-approve if human doesn't respond in time.
 */
export type CheckpointPolicy = 'auto-approve' | 'auto-reject' | 'interactive' | 'timeout';

/**
 * Configuration for flux_run composite workflow.
 */
export interface FluxRunConfig {
  /** Team goal description (required for start) */
  goal: string;
  /** Optional team name for identification */
  name?: string;
  /** Agent roles to assign (e.g., ['dev-coder', 'code-reviewer', 'test-generator']) */
  roles?: string[];
  /** Resource budget constraints */
  budget?: {
    maxTokens?: number;
    maxIterations?: number;
    maxCells?: number;
  };
  /** Use FluxTeam engine (default: true). Set false for legacy TriadTeam. */
  useFluxTeam?: boolean;
  /** Checkpoint approval policy (default: 'auto-approve') */
  checkpointPolicy?: CheckpointPolicy;
  /** Timeout for 'timeout' policy in seconds (default: 300) */
  checkpointTimeoutSecs?: number;
  /** Maximum total runtime in seconds (default: 3600 = 1 hour) */
  maxRuntimeSecs?: number;
  /** Parent session ID for Phase Zero context distillation */
  parentSessionId?: string;
}

/**
 * Flux tool definitions for MCP registration.
 */
export const FLUX_TOOLS = [
  {
    name: 'flux_team',
    description: 'Multi-agent team orchestration — start, monitor, and control autonomous agent teams. Use the "action" parameter to select the operation. Supports both FluxTeam and TriadTeam backends.',
    inputSchema: {
      type: 'object',
      properties: {
        action: {
          type: 'string',
          enum: ['start', 'status', 'tree', 'list', 'pause', 'resume', 'cancel', 'checkpoints', 'approve', 'reject', 'steer', 'change_model'],
          description: 'Team operation to perform',
        },
        goal: {
          type: 'string',
          description: 'Goal description (for action "start")',
        },
        name: {
          type: 'string',
          description: 'Optional team name for identification',
        },
        roles: {
          type: 'array',
          items: { type: 'string' },
          description: 'Agent roles to assign (for action "start")',
        },
        teamId: {
          type: 'string',
          description: 'Team ID (required for status/tree/pause/resume/cancel/change_model)',
        },
        checkpointId: {
          type: 'string',
          description: 'Checkpoint ID (required for approve/reject/steer)',
        },
        feedback: {
          type: 'string',
          description: 'Feedback or steering instructions (for approve/reject/steer)',
        },
        budget: {
          type: 'object',
          description: 'Resource budget constraints (for action "start")',
          properties: {
            maxTokens: { type: 'number' },
            maxIterations: { type: 'number' },
            maxCells: { type: 'number' },
          },
        },
        tier: {
          type: 'string',
          enum: ['minimax', 'qwenPlus', 'glm', 'kimi', 'qwenMax', 'sonnet', 'opus', 'background'],
          description: 'Named model tier (for action "change_model"). Alternative to provider+model.',
        },
        slot: {
          type: 'string',
          description: 'Target a specific posture slot (for action "change_model"). Examples: "lumen.yang", "lumen.yin", "lumen.executive", "dyad.yang", "dyad.yin", "dyad.apex". Omit to change all postures.',
        },
        provider: {
          type: 'string',
          description: 'Provider ID for action "change_model" (use with model).',
        },
        model: {
          type: 'string',
          description: 'Model name for action "change_model" (use with provider).',
        },
        useFluxTeam: {
          type: 'boolean',
          description: 'Use FluxTeam engine (default: true). Set false to use legacy TriadTeam.',
        },
        parentSessionId: {
          type: 'string',
          description: 'Parent session ID for Phase Zero context distillation. When provided, the team will be briefed with context from the parent conversation.',
        },
      },
      required: ['action'],
    },
  },
  {
    name: 'flux_run',
    description: 'Composite workflow — start a team and manage its full lifecycle with automated checkpoint handling. Blocks until team completes, fails, or times out. Supports checkpoint policies: auto-approve, auto-reject, interactive, timeout.',
    inputSchema: {
      type: 'object',
      properties: {
        goal: {
          type: 'string',
          description: 'Team goal description (required)',
        },
        name: {
          type: 'string',
          description: 'Optional team name for identification',
        },
        roles: {
          type: 'array',
          items: { type: 'string' },
          description: 'Agent roles to assign (e.g. ["dev-coder", "code-reviewer"])',
        },
        budget: {
          type: 'object',
          description: 'Resource budget constraints',
          properties: {
            maxTokens: { type: 'number' },
            maxIterations: { type: 'number' },
            maxCells: { type: 'number' },
          },
        },
        useFluxTeam: {
          type: 'boolean',
          description: 'Use FluxTeam engine (default: true)',
        },
        checkpointPolicy: {
          type: 'string',
          enum: ['auto-approve', 'auto-reject', 'interactive', 'timeout'],
          description: 'Checkpoint approval policy (default: auto-approve)',
        },
        checkpointTimeoutSecs: {
          type: 'number',
          description: 'Timeout for interactive checkpoints in seconds (default: 300)',
        },
        maxRuntimeSecs: {
          type: 'number',
          description: 'Maximum total runtime in seconds (default: 3600)',
        },
        parentSessionId: {
          type: 'string',
          description: 'Parent session ID for Phase Zero context distillation. When provided, the team will be briefed with context from the parent conversation.',
        },
      },
      required: ['goal'],
    },
  },
  {
    name: 'flux_inspect',
    description: 'Comprehensive team inspection — combines status, cell hierarchy, budget usage, recent events, and live cell data into a single report. Use this instead of multiple sequential calls.',
    inputSchema: {
      type: 'object',
      properties: {
        teamId: {
          type: 'string',
          description: 'Team ID to inspect (optional, uses most recent active team)',
        },
        includeEvents: {
          type: 'boolean',
          description: 'Include recent event log (default: true)',
        },
        eventLimit: {
          type: 'number',
          description: 'Number of recent events to include (default: 20)',
        },
        includeLive: {
          type: 'boolean',
          description: 'Include live cell status with real-time token totals (default: true)',
        },
      },
    },
  },
  {
    name: 'flux_watch',
    description: 'Block until a team has new activity, then return a status snapshot with events. Uses SSE streaming with 15s heartbeats to prevent client timeout. Returns on significant events (cell completed/failed) or timeout.',
    inputSchema: {
      type: 'object',
      properties: {
        teamId: {
          type: 'string',
          description: 'Team ID to watch (required)',
        },
        timeoutSecs: {
          type: 'number',
          description: 'Maximum seconds to wait (default: 300, max: 600)',
        },
        interestingOnly: {
          type: 'boolean',
          description: 'Only return on significant events like cell completion/failure (default: true)',
        },
      },
      required: ['teamId'],
    },
  },
];

/**
 * Tool names set for quick lookup.
 */
export const FLUX_TOOL_NAMES = new Set(FLUX_TOOLS.map(t => t.name));

/**
 * Significant event types that indicate real progress in team execution.
 * Used by flux_watch to determine when to return.
 */
const SIGNIFICANT_EVENT_TYPES = new Set([
  // TriadTeam events
  'triad-team:cell-completed',
  'triad-team:cell-failed',
  'triad-team:completed',
  'triad-team:failed',
  'triad-team:paused',
  'triad-team:cancelled',
  'triad-team:budget-warning',
  'triad-team:checkpoint',
  'triad-team:cell-spawned',
  'triad-team:cell-completed-without-action',
  // FluxTeam events
  'flux:cell:started',
  'flux:cell:completed',
  'flux:cell:failed',
  'flux:node:started',
  'flux:node:completed',
  'flux:node:failed',
  // Generic team events
  'team:status-change',
  'team:phase-change',
]);

/**
 * Format token data into a concise display string with breakdown.
 * Internal helper for formatting inspection reports.
 */
function formatTokens(tokens: any): string {
  const used = tokens.used ?? 0;
  const budget = tokens.budget ? `/${tokens.budget}` : '';
  const bd = tokens.breakdown;
  if (bd && (bd.input || bd.output)) {
    const parts = [`in:${bd.input}`, `out:${bd.output}`];
    if (bd.cacheRead) parts.push(`cached:${bd.cacheRead}`);
    return `${used}${budget} (${parts.join(' ')})`;
  }
  return `${used}${budget}`;
}

/**
 * Format live cell statuses into a concise, readable structure.
 * Focuses on what's actually happening — active members, recent tool calls, timing.
 * @dep callers: executeFluxInspect (mcp/gateway/flux-tools.ts), buildFluxRunReport (mcp/gateway/flux-tools.ts)
 * @dep calls: formatTokens
 * @dep module: Gateway
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
function formatLiveCells(cells: any[]): any[] {
  return cells.map((cell: any) => {
    const activeMember = cell.members
      ? Object.entries(cell.members).find(([, m]: [string, any]) => m.isRunning)?.[0]
      : undefined;

    const errors = cell.members
      ? Object.entries(cell.members)
          .filter(([, m]: [string, any]) => m.lastError)
          .map(([role, m]: [string, any]) => `${role}: ${m.lastError}`)
      : [];

    const recentTools = (cell.toolCalls?.recent || []).map((t: any) => {
      const duration = t.durationMs ? `${(t.durationMs / 1000).toFixed(1)}s` : '?';
      const status = t.isError ? ' FAILED' : '';
      const params = t.params ? ` ${t.params}` : '';
      return `${t.tool}${params} (${duration}${status})`;
    });

    const elapsed = cell.elapsedMs
      ? cell.elapsedMs > 60000
        ? `${(cell.elapsedMs / 60000).toFixed(1)}m`
        : `${(cell.elapsedMs / 1000).toFixed(0)}s`
      : undefined;

    // Extract current thinking from the active member
    const currentThinking = activeMember && cell.members?.[activeMember]?.currentThinking
      ? cell.members[activeMember].currentThinking
      : undefined;

    return {
      cellId: cell.cellId,
      phase: cell.phase,
      elapsed,
      activeMember: activeMember || 'idle',
      toolCalls: cell.toolCalls?.total ?? 0,
      recentTools,
      tokens: cell.tokens ? formatTokens(cell.tokens) : undefined,
      model: cell.model?.primary,
      errors: errors.length > 0 ? errors : undefined,
      currentThinking: currentThinking ? currentThinking.slice(0, 300) + (currentThinking.length > 300 ? '...' : '') : undefined,
      lastMessage: cell.recentMessages?.[cell.recentMessages.length - 1]?.preview,
    };
  });
}

/**
 * Generate a human-readable summary of the inspection.
 */
function generateInspectionSummary(status: any, tree: any, events: any): string {
  const lines: string[] = [];

  // Status summary
  lines.push(`**Team Status**: ${status.status || 'unknown'}`);
  if (status.name) lines.push(`**Name**: ${status.name}`);

  // Budget summary
  if (status.budget) {
    const budget = status.budget;
    const tokensUsed = budget.tokensUsed || 0;
    const maxTokens = budget.maxTokens || 'unlimited';
    lines.push(`**Tokens**: ${tokensUsed}/${maxTokens}`);
  }

  // Progress summary
  if (tree?.progress) {
    const progress = tree.progress;
    lines.push(`**Progress**: ${progress.completed}/${progress.total} cells (${progress.completionPct}%)`);
    if (progress.failed > 0) lines.push(`⚠️ ${progress.failed} failed cells`);
    if (progress.inProgress > 0) lines.push(`🔄 ${progress.inProgress} cells in progress`);
  }

  // Recent activity
  if (events?.events?.length) {
    const recent = events.events.slice(-3);
    lines.push('**Recent Activity**:');
    for (const event of recent) {
      lines.push(`  - ${event.type || 'event'} at ${new Date(event.timestamp || Date.now()).toLocaleTimeString()}`);
    }
  }

  return lines.join('\n');
}

/**
 * Execute flux_team operations via the "action" parameter.
 * This is the canonical team CRUD router — all other team tools delegate here.
 * @dep callers: executeFluxAgentTool (mcp/gateway/agent-tools.ts), executeFluxRun (mcp/gateway/flux-tools.ts)
 * @dep calls: json, fetchWithTimeout
 * @dep module: Gateway
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export async function executeFluxTeamTool(
  baseUrl: string,
  args: any,
  logger: ILogger
): Promise<any> {
  const action = args?.action;
  if (!action) throw new Error('flux_team requires an "action" parameter');

  logger.info('Executing flux_team action', { action, teamId: args?.teamId });

  switch (action) {
    case 'start': {
      const providerPayload: Record<string, unknown> = {
        providerId: args.provider ?? 'github-copilot',
        model: args.model ?? 'gpt-4o',
      };
      // Model mixing: add secondary model if specified
      if (args.secondaryModel || args.secondaryProviderId) {
        providerPayload.secondaryModel = args.secondaryModel ?? 'gpt-5-mini';
        providerPayload.secondaryProviderId = args.secondaryProviderId ?? 'github-copilot';
      }

      const res = await fetchWithTimeout(`${baseUrl}/teams`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          goal: args.goal,
          name: args.name,
          budget: args.budget,
          roles: args.roles,
          provider: providerPayload,
          useLumen: args.useLumen,
          useFluxTeam: args.useFluxTeam !== false, // Default to true
          parentSessionId: args.parentSessionId,
        }),
      });
      if (!res.ok) throw new Error(`Team start failed: ${await res.text()}`);
      return await res.json();
    }

    case 'status': {
      const qs = args.teamId ? `?teamId=${encodeURIComponent(args.teamId)}` : '';
      const res = await fetchWithTimeout(`${baseUrl}/teams/status${qs}`);
      if (!res.ok) throw new Error(`Team status failed: ${await res.text()}`);
      return await res.json();
    }

    case 'tree': {
      if (!args.teamId) throw new Error('Team "tree" action requires teamId');
      const res = await fetchWithTimeout(`${baseUrl}/teams/tree?teamId=${encodeURIComponent(args.teamId)}`);
      if (!res.ok) throw new Error(`Team tree failed: ${await res.text()}`);
      return await res.json();
    }

    case 'list': {
      const res = await fetchWithTimeout(`${baseUrl}/teams`);
      if (!res.ok) throw new Error(`Team list failed: ${await res.text()}`);
      return await res.json();
    }

    case 'pause':
    case 'resume':
    case 'cancel': {
      if (!args.teamId) throw new Error(`Team "${action}" action requires teamId`);
      const res = await fetchWithTimeout(`${baseUrl}/teams/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ teamId: args.teamId }),
      });
      if (!res.ok) throw new Error(`Team ${action} failed: ${await res.text()}`);
      return await res.json();
    }

    case 'checkpoints': {
      const params = new URLSearchParams();
      if (args.teamId) params.set('teamId', args.teamId);
      const qs = params.toString();
      const res = await fetchWithTimeout(`${baseUrl}/teams/checkpoints${qs ? '?' + qs : ''}`);
      if (!res.ok) throw new Error(`Team checkpoints failed: ${await res.text()}`);
      return await res.json();
    }

    case 'approve':
    case 'reject': {
      if (!args.checkpointId) throw new Error(`Team "${action}" action requires checkpointId`);
      const res = await fetchWithTimeout(`${baseUrl}/teams/checkpoints/${encodeURIComponent(args.checkpointId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: action,
          message: args.feedback,
        }),
      });
      if (!res.ok) throw new Error(`Team ${action} failed: ${await res.text()}`);
      return await res.json();
    }

    case 'steer': {
      // Steer via checkpoint (backward-compatible) or directly via teamId
      if (args.checkpointId) {
        const res = await fetchWithTimeout(`${baseUrl}/teams/checkpoints/${encodeURIComponent(args.checkpointId)}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action: 'steer',
            message: args.feedback,
          }),
        });
        if (!res.ok) throw new Error(`Team steer (checkpoint) failed: ${await res.text()}`);
        return await res.json();
      }
      // Team-level steering — no checkpoint required
      if (!args.feedback) throw new Error('Team "steer" action requires feedback');
      const teamId = args.teamId || '';
      const steerPath = teamId
        ? `/teams/${encodeURIComponent(teamId)}/steer`
        : '/teams/steer';
      const res = await fetchWithTimeout(`${baseUrl}${steerPath}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback: args.feedback }),
      });
      if (!res.ok) throw new Error(`Team steer failed: ${await res.text()}`);
      return await res.json();
    }

    case 'change_model': {
      if (!args.teamId) throw new Error('Team "change_model" action requires teamId');
      if (!args.tier && !(args.provider && args.model)) {
        throw new Error('Team "change_model" requires either "tier" or both "provider" and "model"');
      }

      // Delegate to the model-directive API with scope=job, using the teamId as the jobId.
      // The running Lumen session will pick up the change on its next inference request.
      const body: Record<string, unknown> = {
        scope: 'job',
        jobId: args.teamId,
      };
      if (args.tier) body.tier = args.tier;
      if (args.provider) body.provider = args.provider;
      if (args.model) body.model = args.model;
      if (args.slot) body.slot = args.slot;

      const res = await fetchWithTimeout(`${baseUrl}/model-directive/set`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`Team change_model failed: ${await res.text()}`);
      const result = await res.json();
      return {
        ...result,
        message: `Model routing updated for team ${args.teamId}. ` +
          `New model: ${result.provider}/${result.model}` +
          (args.slot ? ` (slot: ${args.slot})` : ' (all postures)') +
          '. Takes effect on the next inference request.',
      };
    }

    default:
      throw new Error(`Unknown flux_team action: "${action}". Valid: start, status, tree, list, pause, resume, cancel, checkpoints, approve, reject, steer, change_model`);
  }
}

/**
 * Execute flux_run composite workflow.
 * 
 * This is a CLIENT-SIDE workflow that:
 * 1. Starts a team via flux_team start
 * 2. Polls for checkpoints at regular intervals
 * 3. Applies checkpointPolicy to auto-approve/reject or wait for human
 * 4. Monitors team status until completion/failure/timeout
 * 5. Returns comprehensive final report
 * 
 * CHECKPOINT POLICY BEHAVIOR:
 * 
 * - auto-approve: Immediately approves all checkpoints via API call. Zero human intervention.
 * - auto-reject: Immediately rejects all checkpoints. Team will stall (useful for testing).
 * - interactive: Pauses and returns control to MCP client with pending checkpoint.
 *   Client must call flux_team approve/reject to resume. This function returns early.
 * - timeout: Starts in interactive mode, but auto-approves after checkpointTimeoutSecs.
 *   Falls back to auto-approve if human doesn't respond in time.
 * 
 * @param baseUrl - CassiCore admin API base URL
 * @param config - FluxRunConfig with goal, policy, budget, etc.
 * @param logger - Logger instance
 * @param heartbeat - Optional heartbeat callback to prevent MCP client timeout
 */
export async function executeFluxRun(
  baseUrl: string,
  config: FluxRunConfig,
  logger: ILogger,
  heartbeat?: () => void
): Promise<any> {
  const {
    goal,
    name,
    roles,
    budget,
    useFluxTeam,
    parentSessionId,
    checkpointPolicy = 'auto-approve',
    checkpointTimeoutSecs = 300,
    maxRuntimeSecs = 3600,
  } = config;

  logger.info('Starting flux_run workflow', {
    goal: goal.slice(0, 100),
    checkpointPolicy,
    maxRuntimeSecs,
  });

  const startTime = Date.now();
  const maxRuntimeMs = maxRuntimeSecs * 1000;

  // Step 1: Start the team
  const startArgs = {
    action: 'start' as const,
    goal,
    name,
    roles,
    budget,
    useFluxTeam,
    parentSessionId,
  };

  const startResult = await executeFluxTeamTool(baseUrl, startArgs, logger);
  const teamId = startResult.id || startResult.teamId;

  if (!teamId) {
    throw new Error('Team start did not return a teamId');
  }

  logger.info('Team started', { teamId, checkpointPolicy });

  // Step 2: Monitor and handle checkpoints
  const checkpointTimeouts = new Map<string, number>(); // checkpointId → timeout timestamp
  let lastStatus = 'running';

  const checkInterval = setInterval(async () => {
    // Check runtime timeout
    const elapsed = Date.now() - startTime;
    if (elapsed > maxRuntimeMs) {
      logger.warn('flux_run max runtime exceeded', { teamId, elapsed });
      clearInterval(checkInterval);
      try {
        await fetchWithTimeout(`${baseUrl}/teams/cancel`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ teamId }),
        });
      } catch (err) {
        logger.error('Failed to cancel team on timeout', { error: String(err) });
      }
      lastStatus = 'timeout';
      return;
    }

    // Send heartbeat if provided
    if (heartbeat) heartbeat();

    try {
      // Get pending checkpoints
      const checkpointsRes = await fetchWithTimeout(
        `${baseUrl}/teams/checkpoints?teamId=${encodeURIComponent(teamId)}`
      );
      if (!checkpointsRes.ok) return; // Ignore transient errors

      const checkpointsData = await checkpointsRes.json();
      const pending = checkpointsData.checkpoints?.filter((c: any) => c.status === 'pending') || [];

      for (const checkpoint of pending) {
        const cpId = checkpoint.id;

        // Skip if already processing
        if (checkpointTimeouts.has(cpId)) continue;

        logger.info('Checkpoint pending', { checkpointId: cpId, policy: checkpointPolicy });

        switch (checkpointPolicy) {
          case 'auto-approve': {
            // Immediately approve
            try {
              await fetchWithTimeout(`${baseUrl}/teams/checkpoints/${encodeURIComponent(cpId)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'approve', message: 'Auto-approved by flux_run' }),
              });
              logger.info('Checkpoint auto-approved', { checkpointId: cpId });
            } catch (err) {
              logger.error('Failed to auto-approve checkpoint', { checkpointId: cpId, error: String(err) });
            }
            break;
          }

          case 'auto-reject': {
            // Immediately reject
            try {
              await fetchWithTimeout(`${baseUrl}/teams/checkpoints/${encodeURIComponent(cpId)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'reject', message: 'Auto-rejected by flux_run (auto-reject policy)' }),
              });
              logger.info('Checkpoint auto-rejected', { checkpointId: cpId });
            } catch (err) {
              logger.error('Failed to auto-reject checkpoint', { checkpointId: cpId, error: String(err) });
            }
            break;
          }

          case 'interactive': {
            // Return control to client with pending checkpoint
            clearInterval(checkInterval);
            logger.info('Interactive checkpoint - returning to client', { checkpointId: cpId });
            lastStatus = 'waiting-approval';
            return;
          }

          case 'timeout': {
            // Start timeout timer, auto-approve if not handled
            const timeoutAt = Date.now() + (checkpointTimeoutSecs * 1000);
            checkpointTimeouts.set(cpId, timeoutAt);

            // Set up timeout handler
            setTimeout(async () => {
              // Check if still pending
              const stillPending = checkpointTimeouts.get(cpId);
              if (!stillPending) return; // Already handled

              logger.info('Checkpoint timeout - auto-approving', { checkpointId: cpId });
              checkpointTimeouts.delete(cpId);

              try {
                await fetchWithTimeout(`${baseUrl}/teams/checkpoints/${encodeURIComponent(cpId)}`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ action: 'approve', message: `Auto-approved after ${checkpointTimeoutSecs}s timeout` }),
                });
              } catch (err) {
                logger.error('Failed to timeout-approve checkpoint', { checkpointId: cpId, error: String(err) });
              }
            }, checkpointTimeoutSecs * 1000);

            // Return to client for potential interactive approval
            clearInterval(checkInterval);
            logger.info('Interactive checkpoint with timeout', { checkpointId: cpId, timeoutSecs: checkpointTimeoutSecs });
            lastStatus = 'waiting-approval';
            return;
          }
        }
      }

      // Clean up handled checkpoints from timeout map
      const checkpointIds = Array.from(checkpointTimeouts.keys());
      for (const cpId of checkpointIds) {
        const stillPending = pending.find((c: any) => c.id === cpId);
        if (!stillPending) {
          checkpointTimeouts.delete(cpId);
        }
      }

      // Check team status
      const statusRes = await fetchWithTimeout(`${baseUrl}/teams/status?teamId=${encodeURIComponent(teamId)}`);
      if (statusRes.ok) {
        const status = await statusRes.json();
        lastStatus = status.status;

        if (['completed', 'failed', 'cancelled'].includes(status.status)) {
          clearInterval(checkInterval);
        }
      }
    } catch (err) {
      logger.warn('Checkpoint monitoring error', { error: String(err) });
    }
  }, 5000); // Poll every 5 seconds

  // Step 3: Wait for completion
  return new Promise((resolve) => {
    const completionCheck = setInterval(async () => {
      try {
        const statusRes = await fetchWithTimeout(`${baseUrl}/teams/status?teamId=${encodeURIComponent(teamId)}`);
        if (!statusRes.ok) return;

        const status = await statusRes.json();
        if (['completed', 'failed', 'cancelled', 'timeout'].includes(status.status)) {
          clearInterval(completionCheck);
          clearInterval(checkInterval);

          // Fetch final comprehensive report
          const report = await buildFluxRunReport(baseUrl, teamId, logger, startTime, status);
          resolve(report);
        }
      } catch (err) {
        logger.warn('Completion check error', { error: String(err) });
      }
    }, 3000);

    // Safety timeout
    setTimeout(() => {
      clearInterval(completionCheck);
      clearInterval(checkInterval);
      resolve({
        teamId,
        status: 'timeout',
        error: `flux_run exceeded max runtime of ${maxRuntimeSecs}s`,
        runtimeMs: maxRuntimeMs,
      });
    }, maxRuntimeMs + 10000);
  });
}

/**
 * Build comprehensive flux_run final report.
 */
async function buildFluxRunReport(
  baseUrl: string,
  teamId: string,
  logger: ILogger,
  startTime: number,
  finalStatus: any
): Promise<any> {
  try {
    // Fetch tree for progress summary
    let tree = null;
    try {
      const treeRes = await fetchWithTimeout(`${baseUrl}/teams/tree?teamId=${encodeURIComponent(teamId)}`);
      if (treeRes.ok) tree = await treeRes.json();
    } catch { /* ignore */ }

    // Fetch events for activity log
    let events = null;
    try {
      const eventsRes = await fetchWithTimeout(`${baseUrl}/teams/events?teamId=${encodeURIComponent(teamId)}&limit=50`);
      if (eventsRes.ok) events = await eventsRes.json();
    } catch { /* ignore */ }

    // Fetch live cell data
    let liveCells = null;
    try {
      const liveRes = await fetchWithTimeout(`${baseUrl}/teams/live?teamId=${encodeURIComponent(teamId)}`);
      if (liveRes.ok) {
        const liveData = await liveRes.json();
        liveCells = liveData.cells;
      }
    } catch { /* ignore */ }

    return {
      teamId,
      status: finalStatus.status,
      runtimeMs: Date.now() - startTime,
      runtimeFormatted: formatDuration(Date.now() - startTime),
      budget: finalStatus.budget,
      progress: (tree as any)?.progress,
      cells: Object.values(finalStatus.cells || {}).map((c: any) => ({
        cellId: c.cellId,
        status: c.status,
        phase: c.phase,
        depth: c.depth,
        goalTitle: c.goalTitle,
        tokensUsed: c.tokensUsed,
        error: c.error,
      })),
      liveCells: liveCells ? formatLiveCells(liveCells) : null,
      recentEvents: (events as any)?.events?.slice(-20),
      summary: generateRunSummary(finalStatus, tree, events),
    };
  } catch (err) {
    logger.error('Failed to build final report', { error: String(err) });
    return {
      teamId,
      status: finalStatus.status,
      runtimeMs: Date.now() - startTime,
      error: `Failed to build comprehensive report: ${err}`,
    };
  }
}

/**
 * Format duration in milliseconds to human-readable string.
 */
function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.floor((ms % 60000) / 1000);
  return `${minutes}m ${seconds}s`;
}

/**
 * Generate human-readable run summary.
 */
function generateRunSummary(status: any, tree: any, events: any): string {
  const lines: string[] = [];

  lines.push(`**Final Status**: ${status.status}`);

  if (tree?.progress) {
    const p = tree.progress;
    lines.push(`**Progress**: ${p.completed}/${p.total} cells completed (${p.completionPct}%)`);
    if (p.failed > 0) lines.push(`⚠️ ${p.failed} failed`);
  }

  if (status.budget) {
    const b = status.budget;
    lines.push(`**Tokens**: ${b.tokensUsed?.toLocaleString() || 0}${b.maxTokens ? `/${b.maxTokens}` : ''}`);
    lines.push(`**Cells spawned**: ${b.cellsSpawned || 0}`);
  }

  if (status.finalResult) {
    lines.push(`\n**Result**: ${status.finalResult.slice(0, 300)}${status.finalResult.length > 300 ? '...' : ''}`);
  }

  return lines.join('\n');
}

/**
 * Execute flux_inspect composite workflow.
 * Combines status + tree + events + live data into single report.
 */
export async function executeFluxInspect(
  baseUrl: string,
  args: any,
  logger: ILogger
): Promise<any> {
  const teamId = args?.teamId;
  const includeEvents = args?.includeEvents !== false;
  const eventLimit = args?.eventLimit || 20;
  const includeLive = args?.includeLive !== false;

  logger.info('Executing flux_inspect', { teamId, includeEvents, includeLive });

  // Step 1: Get team status
  const statusQs = teamId ? `?teamId=${encodeURIComponent(teamId)}` : '';
  const statusRes = await fetchWithTimeout(`${baseUrl}/teams/status${statusQs}`);
  if (!statusRes.ok) {
    throw new Error(`Team status failed: ${await statusRes.text()}`);
  }
  const status = await statusRes.json();

  const resolvedTeamId = status.id || teamId;

  // Step 2: Get team tree
  const treeRes = await fetchWithTimeout(`${baseUrl}/teams/tree?teamId=${encodeURIComponent(resolvedTeamId)}`);
  let tree = null;
  if (treeRes.ok) {
    tree = await treeRes.json();
  }

  // Step 3: Get recent events
  let events = null;
  if (includeEvents) {
    const eventsRes = await fetchWithTimeout(`${baseUrl}/teams/events?teamId=${encodeURIComponent(resolvedTeamId)}&limit=${eventLimit}`);
    if (eventsRes.ok) {
      events = await eventsRes.json();
    }
  }

  // Step 4: Get live cell statuses
  let liveCells = null;
  if (includeLive) {
    try {
      const liveRes = await fetchWithTimeout(`${baseUrl}/teams/live?teamId=${encodeURIComponent(resolvedTeamId)}`);
      if (liveRes.ok) {
        const liveData = await liveRes.json();
        liveCells = liveData.cells;
      }
    } catch {
      // Live status is optional
    }
  }

  // Step 5: Build comprehensive report
  const report = {
    teamId: resolvedTeamId,
    inspectedAt: new Date().toISOString(),
    status: {
      state: status.status,
      name: status.name,
      budget: status.budget,
      activeCells: status.activeAgents || [],
      createdAt: status.createdAt,
      startedAt: status.startedAt,
      completedAt: status.completedAt,
    },
    hierarchy: tree ? {
      tree: (tree as any).tree,
      progress: (tree as any).progress,
    } : null,
    events: events ? {
      total: (events as any).total,
      recent: (events as any).events,
    } : null,
    liveCells: liveCells ? formatLiveCells(liveCells) : null,
    summary: generateInspectionSummary(status, tree, events),
  };

  return report;
}

/**
 * Execute flux_watch via shared SSE utility.
 * Blocks until a significant team event fires or the timeout is reached.
 * Returns an MCP-format response directly: { content: [{ type: 'text', text: '...' }] }
 */
export async function executeFluxWatch(
  baseUrl: string,
  args: any,
  logger: ILogger,
  heartbeat?: () => void
): Promise<{ content: Array<{ type: 'text'; text: string }> }> {
  const teamId = args?.teamId;
  if (!teamId) throw new Error('teamId is required');

  const timeoutSecs = Math.min(Math.max(args?.timeoutSecs ?? 300, 10), 600);
  const interestingOnly = args?.interestingOnly !== false;

  return watchViaSSE({
    sseUrl: `${baseUrl}/teams/stream?teamId=${encodeURIComponent(teamId)}`,
    pollUrl: `${baseUrl}/teams/events?teamId=${encodeURIComponent(teamId)}&limit=10`,
    timeoutSecs,
    interestingOnly,
    heartbeat,
    logger,
    isSignificant: (type) => SIGNIFICANT_EVENT_TYPES.has(type),
    getEventMessage: (type, parsed) => {
      const msg = parsed?.message ?? parsed?.data?.message;
      if (msg) return msg;
      if (parsed?.phase) return `Cell phase: ${parsed.phase}`;
      if (parsed?.status) return `Status: ${parsed.status}`;
      if (parsed?.cellId) return `Cell: ${parsed.cellId.slice(0, 12)}`;
      return type;
    },
    buildSnapshot: async (reason, events) => {
      // Fetch fresh status snapshot
      const statusRes = await fetchWithTimeout(
        `${baseUrl}/teams/${encodeURIComponent(teamId)}`,
        { timeoutMs: 10_000 },
      );
      let status: any = null;
      if (statusRes.ok) status = await statusRes.json();

      const cells = status?.cells ?? {};
      const cellList = Object.values(cells) as any[];
      const completedCount = cellList.filter((c: any) => c.status === 'completed').length;
      const failedCount = cellList.filter((c: any) => c.status === 'failed').length;
      const runningCount = cellList.filter((c: any) =>
        c.status === 'executing' || c.status === 'planning' || c.status === 'synthesizing'
      ).length;
      const waitingCount = cellList.filter((c: any) =>
        c.status === 'waiting' || c.status === 'initializing'
      ).length;

      const lines: string[] = [];
      lines.push(`## Team ${teamId} — ${status?.status ?? 'unknown'}`);
      lines.push(`**Reason returned:** ${reason}`);
      lines.push(
        `**Progress:** ${completedCount}/${cellList.length} cells completed` +
        (failedCount > 0 ? `, ${failedCount} failed` : '') +
        (runningCount > 0 ? `, ${runningCount} running` : '') +
        (waitingCount > 0 ? `, ${waitingCount} waiting` : ''),
      );

      // Fetch live cell data for token breakdowns
      let liveCells: any[] = [];
      try {
        const liveRes = await fetchWithTimeout(
          `${baseUrl}/teams/live?teamId=${encodeURIComponent(teamId)}`,
          { timeoutMs: 5_000 },
        );
        if (liveRes.ok) {
          const liveData = await liveRes.json();
          liveCells = liveData?.cells ?? [];
        }
      } catch { /* live data is optional */ }

      const liveTokenTotal = liveCells.reduce((sum: number, c: any) => sum + (c.tokens?.used ?? 0), 0);
      const teamTokens = liveTokenTotal || (status?.budget?.tokensUsed ?? 0);

      lines.push(`**Tokens:** ${teamTokens.toLocaleString()}`);
      lines.push(`**Cells spawned:** ${status?.budget?.cellsSpawned ?? 0}`);

      if (status?.finalResult) {
        const fr = status.finalResult;
        lines.push(`\n**Final Result:** ${fr.slice(0, 500)}${fr.length > 500 ? '...' : ''}`);
      }

      lines.push(`\n### Cell Status`);
      for (const cell of cellList.sort((a: any, b: any) => a.depth - b.depth)) {
        const icon = cell.status === 'completed' ? '✓' :
          cell.status === 'failed' ? '✗' :
          ['executing', 'planning', 'synthesizing'].includes(cell.status) ? '▶' : '⏳';
        const liveCell = liveCells.find((lc: any) => lc.cellId === cell.cellId);
        const cellTokens = liveCell?.tokens?.used ?? cell.tokensUsed ?? 0;
        const bd = liveCell?.tokens?.breakdown;
        const tokenStr = bd && (bd.input || bd.output)
          ? `${cellTokens.toLocaleString()} (in:${bd.input.toLocaleString()} out:${bd.output.toLocaleString()}${bd.cacheRead ? ` cached:${bd.cacheRead.toLocaleString()}` : ''})`
          : cellTokens.toLocaleString();
        lines.push(`${icon} d${cell.depth} **${cell.status}** (${cell.phase}) tokens=${tokenStr} — ${cell.goalTitle?.slice(0, 60)}`);
        if (cell.error) lines.push(`  Error: ${cell.error.slice(0, 100)}`);
        if (cell.summary) lines.push(`  Summary: ${cell.summary.slice(0, 100)}`);
      }

      if (events.length > 0) {
        lines.push(`\n### Events Since Last Check (${events.length})`);
        for (const evt of events.slice(-20)) {
          if (!evt.type?.trim() && !evt.message?.trim()) continue;
          lines.push(`- **${evt.type}**: ${evt.message}`);
        }
      }

      return { content: [{ type: 'text', text: lines.join('\n') }] };
    },
  });
}

/**
 * Return the registered FLUX_TOOLS array for MCP gateway registration.
 */
export function getFluxTools(): Array<{ name: string; description: string; inputSchema: any }> {
  return [...FLUX_TOOLS];
}
