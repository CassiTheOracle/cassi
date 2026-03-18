#!/usr/bin/env node
/**
 * Intelligence Tools Module
 * Activity viewer, thinker, subconscious, and other intelligence tools
 */

import { fetchIntelligence, fetchWithTimeout, resolveSessionId } from './helpers.js';
import type { ILogger } from '../../types/interfaces.js';

/**
 * Tool definitions for intelligence tools
 */
export const INTELLIGENCE_TOOLS = [
  {
    name: 'cassi_activity',
    description: 'Dashboard of all CassiCore cognitive modules — status, recent activity, injection counts, session health. Use this for a high-level overview of what the intelligence layer is doing.',
    inputSchema: {
      type: 'object',
      properties: {
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for a short narrative summary (default), "full" for a detailed dashboard with tables',
        },
      },
    },
  },
  {
    name: 'cassi_thinker',
    description: 'View the Thinker module state — adaptive strategy parameters, insight history, ponder/think stats, Phase 3 trigger activity, and self-modification events.',
    inputSchema: {
      type: 'object',
      properties: {
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed dashboard',
        },
      },
    },
  },
  {
    name: 'cassi_subconscious',
    description: 'Conscious Observer state — system-wide mental model (session tracking, provider health, plugin status, active drones/teams, budget tiers), observations from heuristic and LLM sweeps, and detected anomalies. Use this to understand the overall health and awareness state of the intelligence layer.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: {
          type: 'string',
          description: 'Session ID to inspect (optional, defaults to most recent active session)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed dashboard',
        },
      },
    },
  },
  {
    name: 'cassi_consciousness',
    description: "Real-time event stream and observer pipeline — what's flowing through the system right now. Shows event rate, top event types, recent event sequence, heuristic vs LLM observation counts, and last LLM sweep timing. Use this to understand the live pulse of the intelligence layer.",
    inputSchema: {
      type: 'object',
      properties: {
        windowSecs: {
          type: 'number',
          description: 'Look-back window in seconds for stream stats (default 60)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for key metrics (default), "full" for full event type breakdown and LLM observation history',
        },
      },
    },
  },
  {
    name: 'cassi_trace',
    description: 'Forensic trace of a conversation turn — reconstructs what cognitive influences (optimizer, thinker, dialectic, subconscious, session digest) shaped a specific response. Use when asking "why did Cassi say that?"',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: {
          type: 'string',
          description: 'Session ID to trace (optional, defaults to most recent active session)',
        },
        turnIndex: {
          type: 'number',
          description: 'Specific turn index to focus on (optional, shows most recent turns if omitted)',
        },
        limit: {
          type: 'number',
          description: 'Number of turns to include in context (default 5)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed forensic data',
        },
      },
    },
  },
  {
    name: 'cassi_effectiveness',
    description: 'Response quality metrics from implicit feedback signals — "Am I helping?" Shows outcome tracking, feedback detection, per-source quality scores, and per-tool reliability.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: {
          type: 'string',
          description: 'Session ID for feedback lookup (optional, defaults to most recent active session)',
        },
        windowHours: {
          type: 'number',
          description: 'Time window in hours for source/tool stats (default 24)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed metrics',
        },
      },
    },
  },
  {
    name: 'cassi_budget',
    description: 'Token economy and provider usage — "Where does my attention go?" Shows request counts, error rates, per-provider/model aggregates, and hourly trends. No dollar cost calculation.',
    inputSchema: {
      type: 'object',
      properties: {
        providerId: {
          type: 'string',
          description: 'Filter by provider ID (e.g., "anthropic", "github-copilot")',
        },
        model: {
          type: 'string',
          description: 'Filter by model name',
        },
        hours: {
          type: 'number',
          description: 'Hours of hourly trend data to include (default 24)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed dashboard',
        },
      },
    },
  },
  {
    name: 'cassi_evolution',
    description: 'Self-modification timeline — "Am I changing?" Shows strategy snapshots over time, best strategies per module, dialectic effectiveness scores, and parameter evolution.',
    inputSchema: {
      type: 'object',
      properties: {
        module: {
          type: 'string',
          description: 'Intelligence module name to focus on (e.g., "thinker", "dialectic", "optimizer")',
        },
        limit: {
          type: 'number',
          description: 'Number of history entries to show (default 10)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed timeline',
        },
      },
    },
  },
  {
    name: 'cassi_blindspots',
    description: 'Cross-session pattern detection — "What am I systematically missing?" Shows recurring patterns across sessions, error correlations, and unresolved reflection patterns.',
    inputSchema: {
      type: 'object',
      properties: {
        category: {
          type: 'string',
          description: 'Filter patterns by category',
        },
        minConfidence: {
          type: 'number',
          description: 'Minimum confidence threshold (0-1, default 0)',
        },
        limit: {
          type: 'number',
          description: 'Maximum number of patterns to return (default 10)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed patterns',
        },
      },
    },
  },
  {
    name: 'cassi_snapshot',
    description: 'Get a comprehensive snapshot of all running team agents, their goals, progress, recent messages, and current git status. Use this to monitor ongoing parallel work.',
    inputSchema: {
      type: 'object' as const,
      properties: {
        teamId: {
          type: 'string',
          description: 'Optional: focus on a specific team. If omitted, shows all running teams.'
        },
        includeMessages: {
          type: 'boolean',
          description: 'Whether to include recent agent messages (default: true)'
        },
        messageLimit: {
          type: 'number',
          description: 'Max recent messages per agent (default: 5)'
        }
      }
    }
  },
  {
    name: 'cassi_trust',
    description: 'View trust scores across all domains — "How much has the agent earned?" Shows per-domain Bayesian trust scores, autonomy level, evidence counts, and strongest/weakest domains. Trust is earned through demonstrated competence and degrades over time.',
    inputSchema: {
      type: 'object',
      properties: {
        domain: {
          type: 'string',
          description: 'Specific trust domain to inspect (e.g., "file-read", "shell-execution"). If omitted, shows all domains.',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed per-domain breakdown',
        },
      },
    },
  },
  {
    name: 'cassi_consequences',
    description: 'View consequence estimation and permission decision state — "What risks am I assessing?" Shows recent risk assessments, permission decisions (allow/deny/escalate), pending human approvals, and the current trust-adjusted thresholds.',
    inputSchema: {
      type: 'object',
      properties: {
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed decision log',
        },
        limit: {
          type: 'number',
          description: 'Number of recent decisions to show (default 10)',
        },
      },
    },
  },
];

/**
 * Intelligence tool names set for quick lookup
 */
export const INTELLIGENCE_TOOL_NAMES = new Set(INTELLIGENCE_TOOLS.map(t => t.name));

// ═══════════════════════════════════════════════════════════════════════════════
// Formatters
// ═══════════════════════════════════════════════════════════════════════════════

async function formatActivity(baseUrl: string, args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const data = await fetchIntelligence(baseUrl, '/intelligence/activity');

  if (mode === 'brief') {
    const lines: string[] = ['## CassiCore Activity Brief\n'];

    const moduleCount = data.modules?.length || 0;
    lines.push(`**${moduleCount} modules active**`);

    if (data.thinker?.stats) {
      const ts = data.thinker.stats;
      lines.push(`**Thinker**: ${ts.totalInsights || 0} insights generated, ${ts.turnsProcessed || 0} turns processed`);
    }

    if (data.dialectic) {
      const d = data.dialectic;
      lines.push(`**Dialectic**: ${d.totalTurns || 0} turns analyzed, ${d.signalsInjected || 0} signals injected (avg confidence: ${(d.avgConfidence || 0).toFixed(2)})`);
    }

    if (data.archive) {
      lines.push(`**Archive**: ${data.archive.totalEntries || 0} entries (${Object.keys(data.archive.byType || {}).length} types)`);
    }

    if (data.memory) {
      const totalMem = Object.values(data.memory).reduce((sum: number, v: any) => sum + (typeof v === 'number' ? v : 0), 0);
      lines.push(`**Memory**: ${totalMem} items stored`);
    }

    if (data.reflect?.unresolvedPatterns?.length) {
      lines.push(`**Reflect**: ${data.reflect.unresolvedPatterns.length} unresolved patterns`);
    }

    const healthKeys = Object.keys(data.optimizer?.sessionHealth || {});
    if (healthKeys.length > 0) {
      lines.push(`**Optimizer**: tracking ${healthKeys.length} session(s)`);
    }

    const subconData = await fetchIntelligence(baseUrl, '/intelligence/subconscious/stats').catch(() => null);
    const subconSnap = await fetchIntelligence(baseUrl, '/intelligence/subconscious/debug').catch(() => null);
    if (subconData?.stats || subconSnap?.snapshot) {
      const stats = subconData?.stats ?? {};
      const snap = subconSnap?.snapshot ?? {};
      const health = snap.systemHealth ?? 'unknown';
      const badge = ({ healthy: '●', degraded: '◐', critical: '○' } as Record<string, string>)[health] ?? '?';
      const rate = typeof stats?.eventRate === 'number' ? ` | ${stats.eventRate.toFixed(1)} events/min` : '';
      const activeAnoms = stats?.activeAnomalies ?? 0;
      const anomNote = activeAnoms > 0 ? ` | **${activeAnoms} anomaly(ies)**` : '';
      const drones = snap?.activeDrones ?? 0;
      const teams = snap?.activeTeams ?? 0;
      const workNote = (drones > 0 || teams > 0) ? ` | ${drones} drones, ${teams} teams` : '';
      lines.push(`**Consciousness**: ${badge} ${health}${rate}${anomNote}${workNote}`);
    }

    if (data.aiScientist?.recentStudies?.length) {
      lines.push(`**AI Scientist**: ${data.aiScientist.recentStudies.length} recent studies`);
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## CassiCore Activity Dashboard\n'];

  lines.push('### Modules\n');
  lines.push('| Module | Priority | Status |');
  lines.push('|--------|----------|--------|');
  for (const m of (data.modules || [])) {
    lines.push(`| ${m.name} | ${m.priority} | ${m.status} |`);
  }

  if (data.thinker?.stats) {
    lines.push('\n### Thinker\n');
    const ts = data.thinker.stats;
    for (const [k, v] of Object.entries(ts)) {
      lines.push(`- **${k}**: ${v}`);
    }
    if (data.thinker.strategy) {
      lines.push('\n**Current Strategy**:');
      lines.push('```json');
      lines.push(JSON.stringify(data.thinker.strategy, null, 2));
      lines.push('```');
    }
  }

  if (data.dialectic) {
    lines.push('\n### Dialectic (Most Recent Session)\n');
    for (const [k, v] of Object.entries(data.dialectic)) {
      lines.push(`- **${k}**: ${typeof v === 'number' ? (Number.isInteger(v) ? v : (v as number).toFixed(3)) : v}`);
    }
  }

  if (data.archive) {
    lines.push('\n### Archive\n');
    lines.push(`- **Total entries**: ${data.archive.totalEntries || 0}`);
    lines.push(`- **Avg importance**: ${(data.archive.avgImportance || 0).toFixed(3)}`);
    lines.push(`- **Thinking blocks**: ${data.archive.thinkingBlocksCount || 0}`);
    lines.push(`- **Linked entries**: ${data.archive.linkedEntriesCount || 0}`);
    if (data.archive.byType) {
      lines.push('\n**By Type**:');
      for (const [type, count] of Object.entries(data.archive.byType)) {
        lines.push(`  - ${type}: ${count}`);
      }
    }
  }

  if (data.reflect?.unresolvedPatterns?.length) {
    lines.push('\n### Reflect — Unresolved Patterns\n');
    for (const p of data.reflect.unresolvedPatterns) {
      lines.push(`- **${p.pattern || p.category || 'unknown'}**: ${p.occurrences || 1} occurrences`);
    }
  }

  if (Object.keys(data.optimizer?.sessionHealth || {}).length > 0) {
    lines.push('\n### Optimizer — Session Health\n');
    lines.push('| Session | Health Score | Status |');
    lines.push('|---------|-------------|--------|');
    for (const [sid, health] of Object.entries(data.optimizer.sessionHealth)) {
      const h = health as any;
      lines.push(`| ${sid.slice(0, 12)}... | ${h.score?.toFixed(2) ?? 'N/A'} | ${h.status ?? 'unknown'} |`);
    }
  }

  if (data.aiScientist?.recentStudies?.length) {
    lines.push('\n### AI Scientist — Recent Studies\n');
    for (const study of data.aiScientist.recentStudies) {
      lines.push(`- **${study.title || 'Untitled'}** (confidence: ${(study.confidence || 0).toFixed(2)})`);
      if (study.conclusions) lines.push(`  ${study.conclusions.slice(0, 150)}${study.conclusions.length > 150 ? '...' : ''}`);
    }
  }

  if (data.memory) {
    lines.push('\n### Memory\n');
    for (const [k, v] of Object.entries(data.memory)) {
      lines.push(`- **${k}**: ${v}`);
    }
  }

  const subconStats = await fetchIntelligence(baseUrl, '/intelligence/subconscious/stats').catch(() => null);
  const subconDebug = await fetchIntelligence(baseUrl, '/intelligence/subconscious/debug').catch(() => null);
  if (subconStats?.stats || subconDebug?.snapshot) {
    const stats = subconStats?.stats ?? {};
    const snap = subconDebug?.snapshot ?? {};
    lines.push('\n### Consciousness Observer\n');
    const health = snap.systemHealth ?? 'unknown';
    const badge = { healthy: '●', degraded: '◐', critical: '○' }[health] ?? '?';
    lines.push(`**System Health**: ${badge} ${health}`);
    if (stats.totalEvents != null) lines.push(`- **Total events seen**: ${stats.totalEvents}`);
    if (stats.eventRate != null) lines.push(`- **Event rate**: ${typeof stats.eventRate === 'number' ? stats.eventRate.toFixed(1) : stats.eventRate}/min`);
    if (stats.totalObservations != null) lines.push(`- **Observations**: ${stats.totalObservations}`);
    if (stats.activeAnomalies != null) lines.push(`- **Active anomalies**: ${stats.activeAnomalies}`);
    if (snap.activeDrones != null) lines.push(`- **Active drones**: ${snap.activeDrones}`);
    if (snap.activeTeams != null) lines.push(`- **Active teams**: ${snap.activeTeams}`);
    const providerHealth: Record<string, string> = snap.providerHealth ?? {};
    const badProviders = Object.entries(providerHealth).filter(([, s]) => s !== 'healthy');
    if (badProviders.length > 0) {
      lines.push(`- **Provider issues**: ${badProviders.map(([id, s]) => `${id}:${s}`).join(', ')}`);
    }
    const anomData = await fetchIntelligence(baseUrl, '/intelligence/subconscious/anomalies').catch(() => null);
    const anomalies: any[] = anomData?.anomalies ?? [];
    const unacked = anomalies.filter((a: any) => !a.acknowledged);
    if (unacked.length > 0) {
      lines.push(`\n**Unacknowledged anomalies** (${unacked.length}):`);
      for (const a of unacked.slice(0, 5)) {
        lines.push(`  - [${a.severity}] ${(a.description ?? '').slice(0, 80)}`);
      }
    }
  }

  return lines.join('\n');
}

async function formatThinker(baseUrl: string, args: any): Promise<string> {
  const mode = args?.mode || 'brief';

  const [statsData, strategyData, insightData] = await Promise.all([
    fetchIntelligence(baseUrl, '/intelligence/thinker/stats').catch(() => null),
    fetchIntelligence(baseUrl, '/intelligence/thinker/strategy').catch(() => null),
    fetchIntelligence(baseUrl, '/intelligence/thinker/insight-history').catch(() => null),
  ]);

  const stats = statsData?.stats || statsData;
  const strategy = strategyData?.strategy || strategyData;
  const insights = insightData?.history || insightData?.insights || insightData;

  if (mode === 'brief') {
    const lines: string[] = ['## Thinker Brief\n'];

    if (stats) {
      lines.push(`**${stats.totalInsights || stats.insightCount || 0}** insights | **${stats.turnsProcessed || stats.turnCount || 0}** turns processed | enabled: **${stats.enabled ?? 'unknown'}**`);
    } else {
      lines.push('*Thinker stats not available*');
    }

    if (strategy) {
      const s = typeof strategy === 'string' ? JSON.parse(strategy) : strategy;
      lines.push(`\n**Strategy**: ponder interval ${s.ponderIntervalMs || s.ponderInterval || 'default'}ms, trigger sensitivity ${(s.triggerSensitivity || 0).toFixed(2)}`);
    }

    if (Array.isArray(insights) && insights.length > 0) {
      lines.push(`\n**Latest Insight** (${new Date(insights[0].timestamp || insights[0].createdAt || Date.now()).toLocaleString()}):`);
      const content = insights[0].content || insights[0].insight || JSON.stringify(insights[0]);
      lines.push(`> ${content.slice(0, 200)}${content.length > 200 ? '...' : ''}`);
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## Thinker Dashboard\n'];

  if (stats) {
    lines.push('### Runtime Stats\n');
    for (const [k, v] of Object.entries(stats)) {
      lines.push(`- **${k}**: ${v}`);
    }
  }

  if (strategy) {
    lines.push('\n### Adaptive Strategy\n');
    const s = typeof strategy === 'string' ? JSON.parse(strategy) : strategy;
    lines.push('```json');
    lines.push(JSON.stringify(s, null, 2));
    lines.push('```');
  }

  if (Array.isArray(insights) && insights.length > 0) {
    lines.push(`\n### Insight History (${insights.length} entries)\n`);
    for (const insight of insights.slice(0, 10)) {
      const content = insight.content || insight.insight || JSON.stringify(insight);
      const ts = insight.timestamp || insight.createdAt;
      const feedback = insight.feedbackScore ?? insight.feedback;
      lines.push(`#### ${ts ? new Date(ts).toLocaleString() : 'Unknown time'} ${feedback !== undefined ? `(feedback: ${feedback})` : ''}`);
      lines.push(`${content}\n`);
    }
  } else {
    lines.push('\n*No insight history available.*');
  }

  return lines.join('\n');
}

async function formatSubconscious(baseUrl: string, args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const sessionId = await resolveSessionId(baseUrl, args?.sessionId);

  const params: Record<string, string> = {};
  if (sessionId) params.sessionId = sessionId;

  const [debugData, statsData, anomaliesData] = await Promise.all([
    fetchIntelligence(baseUrl, '/intelligence/subconscious/debug', params).catch(() => null),
    fetchIntelligence(baseUrl, '/intelligence/subconscious/stats').catch(() => null),
    fetchIntelligence(baseUrl, '/intelligence/subconscious/anomalies').catch(() => null),
  ]);

  const snap: Record<string, any> = debugData?.snapshot ?? {};
  const stats = statsData?.stats ?? statsData ?? {};
  const anomalies: any[] = anomaliesData?.anomalies ?? anomaliesData ?? [];
  const observations: any[] = debugData?.recentObservations ?? [];

  const healthBadge = (h: string) => ({
    healthy: '● healthy',
    degraded: '◐ degraded',
    critical: '○ critical',
  }[h] ?? `? ${h}`);

  const providerBadge = (s: string) => ({
    healthy: '✓', degraded: '~', error: '✗', rate_limited: '⏸',
  }[s] ?? s);

  if (mode === 'brief') {
    const lines: string[] = ['## Conscious Observer Brief\n'];

    const health = snap.systemHealth ?? 'unknown';
    const sessionCount = snap.sessionCount ?? 0;
    const drones = snap.activeDrones ?? 0;
    const teams = snap.activeTeams ?? 0;
    const totalObs = stats.totalObservations ?? 0;
    const totalAnoms = stats.totalAnomalies ?? 0;
    const eventRate = typeof stats.eventRate === 'number' ? stats.eventRate.toFixed(1) : (stats.eventRate ?? '?');
    lines.push(`**System**: ${healthBadge(health)} | sessions: ${sessionCount} | events/min: ${eventRate}`);
    if (drones > 0 || teams > 0) {
      lines.push(`**Active**: ${drones} drone(s), ${teams} team(s)`);
    }
    lines.push(`**Observations**: ${totalObs} total | **Anomalies**: ${totalAnoms} total`);

    const providerHealth: Record<string, string> = snap.providerHealth ?? {};
    const badProviders = Object.entries(providerHealth).filter(([, s]) => s !== 'healthy');
    if (badProviders.length > 0) {
      lines.push(`\n**Provider Issues**: ${badProviders.map(([id, s]) => `${id}: ${s}`).join(', ')}`);
    }

    const pluginStatus: Record<string, string> = snap.pluginStatus ?? {};
    const crashedPlugins = Object.entries(pluginStatus).filter(([, s]) => s === 'crashed');
    if (crashedPlugins.length > 0) {
      lines.push(`**Plugin Crashes**: ${crashedPlugins.map(([id]) => id).join(', ')}`);
    }

    const budgetTiers: Record<string, string> = snap.budgetTiers ?? {};
    const urgentBudget = Object.entries(budgetTiers).filter(([, t]) => t === 'critical' || t === 'frugal');
    if (urgentBudget.length > 0) {
      lines.push(`**Budget Warnings**: ${urgentBudget.map(([id, t]) => `${id}: ${t}`).join(', ')}`);
    }

    const patterns: string[] = (snap.recentPatterns ?? []).slice(0, 3);
    if (patterns.length > 0) {
      lines.push(`\n**Recent Patterns**: ${patterns.join(' · ')}`);
    }

    if (observations.length > 0) {
      lines.push(`\n**Recent Observations** (${observations.length}):`);
      for (const obs of observations.slice(0, 3)) {
        const src = obs.type ?? obs.source ?? 'observation';
        const conf = obs.confidence != null ? ` (${Math.round(obs.confidence * 100)}%)` : '';
        lines.push(`- [${src}${conf}] ${(obs.summary ?? obs.description ?? '').slice(0, 100)}`);
      }
    }

    const unacked = anomalies.filter((a: any) => !a.acknowledged);
    if (unacked.length > 0) {
      lines.push(`\n**${unacked.length} unacknowledged anomaly(ies)**:`);
      for (const a of unacked.slice(0, 3)) {
        lines.push(`- [${a.severity ?? '?'}] ${(a.description ?? '').slice(0, 80)}`);
      }
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = [`## Conscious Observer Dashboard${sessionId ? ` (session: ${sessionId.slice(0, 12)}...)` : ''}\n`];

  const health = snap.systemHealth ?? 'unknown';
  lines.push(`**System Health**: ${healthBadge(health)}\n`);

  if (Object.keys(stats).length > 0) {
    lines.push('### Statistics\n');
    const totalEvents = stats.totalEvents ?? '?';
    const activeSessions = stats.activeSessions ?? snap.sessionCount ?? '?';
    const eventRate = typeof stats.eventRate === 'number' ? stats.eventRate.toFixed(1) : (stats.eventRate ?? '?');
    const totalObs = stats.totalObservations ?? 0;
    const activeAnoms = stats.activeAnomalies ?? anomalies.filter((a: any) => !a.acknowledged).length;
    const avgConf = typeof stats.averageConfidence === 'number' ? stats.averageConfidence.toFixed(3) : '?';
    lines.push(`| Metric | Value |`);
    lines.push(`|--------|-------|`);
    lines.push(`| Total events seen | ${totalEvents} |`);
    lines.push(`| Active sessions | ${activeSessions} |`);
    lines.push(`| Events/min | ${eventRate} |`);
    lines.push(`| Total observations | ${totalObs} |`);
    lines.push(`| Active anomalies | ${activeAnoms} |`);
    lines.push(`| Avg observation confidence | ${avgConf} |`);
    if (snap.activeDrones != null || snap.activeTeams != null) {
      lines.push(`| Active drones | ${snap.activeDrones ?? 0} |`);
      lines.push(`| Active teams | ${snap.activeTeams ?? 0} |`);
    }
  }

  const providerHealth: Record<string, string> = snap.providerHealth ?? {};
  if (Object.keys(providerHealth).length > 0) {
    lines.push('\n### Provider Health\n');
    lines.push('| Provider | Status |');
    lines.push('|----------|--------|');
    for (const [id, status] of Object.entries(providerHealth)) {
      lines.push(`| ${id} | ${providerBadge(status)} ${status} |`);
    }
  }

  const pluginStatus: Record<string, string> = snap.pluginStatus ?? {};
  if (Object.keys(pluginStatus).length > 0) {
    lines.push('\n### Plugin Status\n');
    lines.push('| Plugin | Status |');
    lines.push('|--------|--------|');
    for (const [id, status] of Object.entries(pluginStatus)) {
      lines.push(`| ${id} | ${status} |`);
    }
  }

  const budgetTiers: Record<string, string> = snap.budgetTiers ?? {};
  if (Object.keys(budgetTiers).length > 0) {
    lines.push('\n### Budget Tiers\n');
    lines.push('| Provider | Tier |');
    lines.push('|----------|------|');
    for (const [id, tier] of Object.entries(budgetTiers)) {
      lines.push(`| ${id} | ${tier} |`);
    }
  }

  if (Array.isArray(stats.topEventTypes) && stats.topEventTypes.length > 0) {
    lines.push('\n### Top Event Types\n');
    lines.push('| Type | Count |');
    lines.push('|------|-------|');
    for (const { type, count } of stats.topEventTypes) {
      lines.push(`| ${type} | ${count} |`);
    }
  }

  if (observations.length > 0) {
    lines.push(`\n### Recent Observations (${observations.length})\n`);
    for (const obs of observations) {
      const src = obs.type ?? obs.source ?? 'observation';
      const conf = obs.confidence != null ? ` (${Math.round(obs.confidence * 100)}%)` : '';
      const patterns = Array.isArray(obs.patterns) && obs.patterns.length > 0
        ? `\n  Patterns: ${obs.patterns.slice(0, 3).join(', ')}`
        : '';
      lines.push(`- **[${src}${conf}]** ${obs.summary ?? obs.description ?? ''}${patterns}`);
    }
  }

  if (anomalies.length > 0) {
    lines.push(`\n### Anomalies (${anomalies.length})\n`);
    lines.push('| ID | Severity | Description | Acked |');
    lines.push('|----|----------|-------------|-------|');
    for (const a of anomalies) {
      const desc = (a.description ?? a.summary ?? '').slice(0, 60);
      lines.push(`| ${(a.id ?? '?').slice(0, 8)} | ${a.severity ?? '?'} | ${desc} | ${a.acknowledged ? 'Yes' : 'No'} |`);
    }
  }

  if (debugData?.context) {
    lines.push('\n### Context Manager (preview)\n');
    lines.push('```json');
    lines.push(JSON.stringify(debugData.context, null, 2).slice(0, 2000));
    lines.push('```');
  }

  return lines.join('\n');
}

async function formatConsciousness(baseUrl: string, args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const windowSecs = args?.windowSecs ?? 60;

  const data = await fetchIntelligence(baseUrl, '/intelligence/subconscious/stream', {
    windowSecs: String(windowSecs),
  }).catch(() => null);

  if (!data?.stream) {
    return '## Consciousness Stream\n\nUnable to reach daemon or subconscious not initialised.';
  }

  const s = data.stream;
  const ratePerMin = typeof s.eventsPerSecond === 'number'
    ? (s.eventsPerSecond * 60).toFixed(1)
    : '?';
  const lastSweepAgo = s.lastLLMSweepAgo != null
    ? `${Math.round(s.lastLLMSweepAgo / 1000)}s ago`
    : s.lastLLMSweepAt > 0 ? 'known' : 'never';

  if (mode === 'brief') {
    const lines: string[] = ['## Consciousness Stream (brief)\n'];
    lines.push(`**Window**: last ${windowSecs}s | **Events**: ${s.totalEvents} | **Rate**: ${ratePerMin}/min`);
    lines.push(`**Active sessions**: ${s.activeSessions} | **Heuristic obs**: ${s.heuristicObservationCount} | **LLM obs**: ${s.llmObservationCount}`);
    lines.push(`**Last LLM sweep**: ${lastSweepAgo}`);

    if (Array.isArray(s.topEventTypes) && s.topEventTypes.length > 0) {
      const top5 = s.topEventTypes.slice(0, 5).map((t: any) => `${t.type}(${t.count})`).join(', ');
      lines.push(`\n**Top types**: ${top5}`);
    }

    if (Array.isArray(s.recentSequence) && s.recentSequence.length > 0) {
      lines.push(`\n**Recent sequence**: \`${s.recentSequence.slice(-8).join(' → ')}\``);
    }

    const recentLLM: any[] = s.recentLLMObservations ?? [];
    if (recentLLM.length > 0) {
      lines.push(`\n**Latest LLM sweep** (confidence: ${Math.round((recentLLM[0].confidence ?? 0) * 100)}%):`);
      lines.push(`> ${(recentLLM[0].summary ?? '').slice(0, 150)}`);
      if (recentLLM[0].concerns?.length > 0) {
        lines.push(`> Concerns: ${recentLLM[0].concerns.slice(0, 2).join('; ')}`);
      }
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = [`## Consciousness Stream (full) — last ${windowSecs}s\n`];
  lines.push(`| Metric | Value |`);
  lines.push(`|--------|-------|`);
  lines.push(`| Total events | ${s.totalEvents} |`);
  lines.push(`| Events/min | ${ratePerMin} |`);
  lines.push(`| Active sessions | ${s.activeSessions} |`);
  lines.push(`| Heuristic observations | ${s.heuristicObservationCount} |`);
  lines.push(`| LLM observations | ${s.llmObservationCount} |`);
  lines.push(`| Last LLM sweep | ${lastSweepAgo} |`);

  if (Array.isArray(s.topEventTypes) && s.topEventTypes.length > 0) {
    lines.push('\n### Event Type Distribution\n');
    lines.push('| Type | Count |');
    lines.push('|------|-------|');
    for (const { type, count } of s.topEventTypes) {
      lines.push(`| ${type} | ${count} |`);
    }
  }

  if (Array.isArray(s.recentSequence) && s.recentSequence.length > 0) {
    lines.push('\n### Recent Event Sequence\n');
    lines.push('```');
    lines.push(s.recentSequence.join(' → '));
    lines.push('```');
  }

  const recentLLM: any[] = s.recentLLMObservations ?? [];
  if (recentLLM.length > 0) {
    lines.push(`\n### LLM Sweep History (last ${recentLLM.length})\n`);
    for (const obs of recentLLM) {
      const ago = obs.timestamp ? `${Math.round((Date.now() - obs.timestamp) / 1000)}s ago` : '';
      lines.push(`#### Sweep ${ago} (${obs.eventCount} events, confidence: ${Math.round((obs.confidence ?? 0) * 100)}%)\n`);
      lines.push(`**Summary**: ${obs.summary ?? ''}`);
      if (obs.patterns?.length > 0) lines.push(`**Patterns**: ${obs.patterns.join(', ')}`);
      if (obs.concerns?.length > 0) lines.push(`**Concerns**: ${obs.concerns.join('; ')}`);
      if (obs.opportunities?.length > 0) lines.push(`**Opportunities**: ${obs.opportunities.join('; ')}`);
    }
  }

  return lines.join('\n');
}

async function formatTrace(baseUrl: string, args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const sessionId = await resolveSessionId(baseUrl, args?.sessionId);
  if (!sessionId) {
    return '## Trace\n\nNo active session found. Provide a sessionId parameter.';
  }

  const params: Record<string, string> = { sessionId };
  if (args?.turnIndex !== undefined) params.turnIndex = String(args.turnIndex);
  if (args?.limit) params.limit = String(args.limit);

  const data = await fetchIntelligence(baseUrl, '/intelligence/trace', params);

  if (mode === 'brief') {
    const lines: string[] = ['## Turn Trace (Brief)\n'];
    lines.push(`**Session**: \`${sessionId.slice(0, 12)}...\`\n`);

    const turns = data.continuity?.turns || [];
    if (turns.length > 0) {
      const latest = turns[turns.length - 1];
      lines.push(`**Latest turn**: ${latest.role} at ${new Date(latest.timestamp).toLocaleTimeString()} (${latest.content?.slice(0, 80)}...)`);
      lines.push(`**Turn context**: ${turns.length} turn(s) in window`);
    } else {
      lines.push('**No turn data** available for this session');
    }

    const injections = data.injections || [];
    if (injections.length > 0) {
      const sources = [...new Set(injections.map((i: any) => i.metadata?.source || i.category || 'unknown'))];
      lines.push(`**Injections**: ${injections.length} from ${sources.join(', ')}`);
    } else {
      lines.push('**Injections**: none recorded (ledger may not have been active)');
    }

    if (data.dialectic && data.dialectic.length > 0) {
      const latest = data.dialectic[data.dialectic.length - 1];
      lines.push(`**Dialectic**: last analysis at ${new Date(latest.timestamp || latest.created_at).toLocaleTimeString()} — ${latest.synthesis?.slice(0, 100) || 'no synthesis'}...`);
    }

    if (data.reflectPatterns?.length) {
      lines.push(`**Active patterns**: ${data.reflectPatterns.length} unresolved reflection pattern(s) may have influenced response`);
    }

    if (data.mentalModel) {
      lines.push(`**Mental model**: active for this session`);
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## Turn Trace (Full Forensic)\n'];
  lines.push(`**Session**: \`${sessionId}\`  `);
  lines.push(`**Timestamp**: ${new Date(data.timestamp).toISOString()}\n`);

  const turns = data.continuity?.turns || [];
  if (turns.length > 0) {
    lines.push('### Conversation Context\n');
    lines.push(`Total turns in window: ${data.continuity?.totalTurns || turns.length}\n`);
    lines.push('| # | Role | Time | Content (preview) |');
    lines.push('|---|------|------|--------------------|');
    turns.forEach((t: any, i: number) => {
      const time = new Date(t.timestamp).toLocaleTimeString();
      const preview = (t.content || '').replace(/\|/g, '\\|').slice(0, 60);
      lines.push(`| ${i} | ${t.role} | ${time} | ${preview}... |`);
    });
  }

  const injections = data.injections || [];
  if (injections.length > 0) {
    lines.push('\n### Injection Ledger\n');
    lines.push('| Source | Time | Content (preview) |');
    lines.push('|--------|------|--------------------|');
    for (const inj of injections) {
      const source = inj.metadata?.source || inj.category || 'unknown';
      const time = inj.metadata?.turnTimestamp ? new Date(inj.metadata.turnTimestamp).toLocaleTimeString() : 'N/A';
      const preview = (inj.content || '').replace(/\|/g, '\\|').slice(0, 80);
      lines.push(`| ${source} | ${time} | ${preview}... |`);
    }
  } else {
    lines.push('\n### Injection Ledger\n');
    lines.push('No injection records found. The injection ledger persists entries from optimizer, thinker, dialectic, subconscious, and session digest modules.');
  }

  if (data.dialectic && data.dialectic.length > 0) {
    lines.push('\n### Dialectic Analysis\n');
    for (const d of data.dialectic) {
      lines.push(`**Turn** at ${new Date(d.timestamp || d.created_at).toLocaleTimeString()}:`);
      if (d.yang) lines.push(`- **Yang**: ${d.yang.slice(0, 150)}...`);
      if (d.yin) lines.push(`- **Yin**: ${d.yin.slice(0, 150)}...`);
      if (d.synthesis) lines.push(`- **Synthesis**: ${d.synthesis.slice(0, 150)}...`);
      if (d.confidence !== undefined) lines.push(`- **Confidence**: ${(d.confidence * 100).toFixed(0)}%`);
      lines.push('');
    }
  }

  if (data.reflectPatterns?.length) {
    lines.push('\n### Active Reflection Patterns\n');
    for (const p of data.reflectPatterns) {
      lines.push(`- **${p.pattern || p.category || 'unknown'}** (${p.occurrences || 1}x): ${p.description || p.evidence || 'no description'}`);
    }
  }

  if (data.archiveContext?.length) {
    lines.push('\n### Archive Context\n');
    for (const a of data.archiveContext) {
      lines.push(`- [${a.type}] ${(a.content || '').slice(0, 120)}...`);
    }
  }

  if (data.mentalModel) {
    lines.push('\n### Mental Model State\n');
    lines.push('```json');
    lines.push(JSON.stringify(data.mentalModel, null, 2).slice(0, 500));
    lines.push('```');
  }

  return lines.join('\n');
}

async function formatEffectiveness(baseUrl: string, args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const sessionId = await resolveSessionId(baseUrl, args?.sessionId);
  const windowMs = ((args?.windowHours || 24) * 60 * 60_000).toString();

  const [statsData, feedbackData] = await Promise.all([
    fetchIntelligence(baseUrl, '/intelligence/outcomes/stats').catch(() => null),
    sessionId
      ? fetchIntelligence(baseUrl, '/intelligence/outcomes/feedback', { sessionId, limit: '10' }).catch(() => null)
      : Promise.resolve(null),
  ]);

  const stats = statsData || {};
  const feedback = feedbackData?.feedback || [];

  if (mode === 'brief') {
    const lines: string[] = ['## Effectiveness Brief\n'];

    if (!statsData) {
      lines.push('OutcomeTracker not initialized or no data available.');
      return lines.join('\n');
    }

    lines.push(`**Total feedback detected**: ${stats.totalFeedbackDetected || 0}`);
    lines.push(`**Outcomes recorded**: ${stats.totalOutcomesRecorded || 0} insights, ${stats.totalToolOutcomesRecorded || 0} tools`);
    lines.push(`**Sessions tracked**: ${stats.trackedSessions || 0}`);
    lines.push(`**Pending**: ${stats.pendingFeedback || 0} feedback, ${stats.pendingToolOutcomes || 0} tool outcomes`);

    if (feedback.length > 0) {
      const positive = feedback.filter((f: any) => f.sentiment === 'positive' || f.score > 0).length;
      const negative = feedback.filter((f: any) => f.sentiment === 'negative' || f.score < 0).length;
      lines.push(`\n**Recent feedback** (${sessionId?.slice(0, 12)}...): ${positive} positive, ${negative} negative out of ${feedback.length}`);
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## Effectiveness Dashboard\n'];

  lines.push('### Aggregate Stats\n');
  lines.push('| Metric | Value |');
  lines.push('|--------|-------|');
  for (const [k, v] of Object.entries(stats)) {
    lines.push(`| ${k} | ${v} |`);
  }

  if (feedback.length > 0) {
    lines.push(`\n### Recent Feedback (${sessionId?.slice(0, 12)}...)\n`);
    lines.push('| Sentiment | Score | Signal | Timestamp |');
    lines.push('|-----------|-------|--------|-----------|');
    for (const f of feedback) {
      const time = f.timestamp ? new Date(f.timestamp).toLocaleTimeString() : 'N/A';
      lines.push(`| ${f.sentiment || 'neutral'} | ${f.score ?? 'N/A'} | ${(f.signal || f.content || '').slice(0, 60)} | ${time} |`);
    }
  }

  const sources = ['thinker', 'dialectic', 'subconscious', 'optimizer'];
  const sourceResults = await Promise.all(
    sources.map(s => fetchIntelligence(baseUrl, `/intelligence/outcomes/sources/${s}`, { windowMs }).catch(() => null))
  );
  const hasSourceData = sourceResults.some(r => r?.stats);
  if (hasSourceData) {
    lines.push('\n### Per-Source Quality\n');
    lines.push('| Source | Total | Avg Score | Positive Rate | Negative Rate |');
    lines.push('|--------|-------|-----------|---------------|---------------|');
    sources.forEach((s, i) => {
      const st = sourceResults[i]?.stats;
      if (st) {
        lines.push(`| ${s} | ${st.totalOutcomes} | ${st.avgScore?.toFixed(2) ?? 'N/A'} | ${(st.positiveRate * 100).toFixed(0)}% | ${(st.negativeRate * 100).toFixed(0)}% |`);
      }
    });
  }

  return lines.join('\n');
}

async function formatBudget(baseUrl: string, args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const opts: Record<string, string> = {};
  if (args?.providerId) opts.providerId = args.providerId;
  if (args?.model) opts.model = args.model;
  const hours = args?.hours || 24;

  const [statsData, aggregateData, hourlyData, budgetData] = await Promise.all([
    fetchIntelligence(baseUrl, '/intelligence/profiler/stats').catch(() => null),
    fetchIntelligence(baseUrl, '/intelligence/profiler/aggregate', opts).catch(() => null),
    fetchIntelligence(baseUrl, '/intelligence/profiler/hourly', { ...opts, hours: String(hours) }).catch(() => null),
    fetchIntelligence(baseUrl, '/intelligence/budget', opts).catch(() => null),
  ]);

  const stats = statsData || {};
  const aggregate = aggregateData?.aggregate || [];
  const hourly = hourlyData?.hourly || [];
  const budgetSnapshots = budgetData?.snapshots || [];
  const budgetTiers = budgetData?.tiers || {};

  if (mode === 'brief') {
    const lines: string[] = ['## Budget Brief\n'];

    if (budgetSnapshots.length > 0) {
      for (const snap of budgetSnapshots) {
        const tier = budgetTiers[snap.providerId] || 'unknown';
        const pct = ((snap.percentUsed || 0) * 100).toFixed(1);
        const exhaustion = snap.projectedExhaustionDay
          ? `projected exhaustion: day ${snap.projectedExhaustionDay}`
          : 'sustainable pace';
        lines.push(`**${snap.providerId}**: ${snap.used}/${snap.monthlyLimit} requests (${pct}%), tier: **${tier}**, ${exhaustion}`);
        lines.push(`  Burn rate: ~${snap.dailyBurnRate?.toFixed(1) || '?'}/day, ${snap.remaining}\n`);
      }
    }

    if (!statsData && budgetSnapshots.length === 0) {
      lines.push('No budget or profiler data available.');
      return lines.join('\n');
    }

    if (statsData) {
      lines.push(`**Total requests**: ${stats.totalRequestsRecorded || 0} (${stats.totalErrors || 0} errors)`);
      lines.push(`**Inflight**: ${stats.inflightRequests || 0} | **Pending records**: ${stats.pendingRecords || 0}`);

      if (aggregate.length > 0) {
        lines.push('\n**Provider breakdown**:');
        for (const a of aggregate.slice(0, 5)) {
          const errPct = a.totalRequests > 0 ? ((a.errorCount / a.totalRequests) * 100).toFixed(1) : '0';
          lines.push(`- **${a.providerId}/${a.model}**: ${a.totalRequests} req, ${a.totalTokens || 0} tokens, ${errPct}% errors, avg ${a.avgDurationMs?.toFixed(0) || '?'}ms`);
        }
      }
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## Budget Dashboard\n'];

  if (budgetSnapshots.length > 0) {
    lines.push('### Monthly Budget\n');
    lines.push('| Provider | Used | Limit | % Used | Tier | Burn Rate | Remaining | Exhaustion |');
    lines.push('|----------|------|-------|--------|------|-----------|-----------|------------|');
    for (const snap of budgetSnapshots) {
      const tier = budgetTiers[snap.providerId] || 'unknown';
      const pct = ((snap.percentUsed || 0) * 100).toFixed(1);
      const exhaustion = snap.projectedExhaustionDay ? `Day ${snap.projectedExhaustionDay}` : 'Sustainable';
      lines.push(`| ${snap.providerId} | ${snap.used} | ${snap.monthlyLimit} | ${pct}% | ${tier} | ${snap.dailyBurnRate?.toFixed(1) || '?'}/day | ${snap.remaining} | ${exhaustion} |`);
    }
  }

  lines.push('\n### Request Overview\n');
  lines.push('| Metric | Value |');
  lines.push('|--------|-------|');
  for (const [k, v] of Object.entries(stats)) {
    lines.push(`| ${k} | ${v} |`);
  }

  if (aggregate.length > 0) {
    lines.push('\n### Provider Aggregate\n');
    lines.push('| Provider | Model | Requests | Tokens | Errors | Avg Duration |');
    lines.push('|----------|-------|----------|--------|--------|-------------|');
    for (const a of aggregate) {
      lines.push(`| ${a.providerId} | ${a.model || 'all'} | ${a.totalRequests} | ${a.totalTokens || 0} | ${a.errorCount || 0} | ${a.avgDurationMs?.toFixed(0) || 'N/A'}ms |`);
    }
  }

  if (hourly.length > 0) {
    lines.push(`\n### Hourly Trends (last ${hours}h)\n`);
    lines.push('| Hour | Requests | Tokens | Errors | Avg Duration |');
    lines.push('|------|----------|--------|--------|-------------|');
    for (const h of hourly.slice(-12)) {
      lines.push(`| ${h.hour || h.hourBucket} | ${h.requests || h.totalRequests} | ${h.tokens || h.totalTokens || 0} | ${h.errors || h.errorCount || 0} | ${h.avgDurationMs?.toFixed(0) || 'N/A'}ms |`);
    }
  }

  return lines.join('\n');
}

async function formatEvolution(baseUrl: string, args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const limit = args?.limit || 10;
  const module = args?.module;

  const [statsData, dialecticEffData] = await Promise.all([
    fetchIntelligence(baseUrl, '/intelligence/strategy/stats').catch(() => null),
    fetchIntelligence(baseUrl, '/intelligence/strategy/dialectic-effectiveness', { limit: String(limit) }).catch(() => null),
  ]);

  let historyData: any = null;
  let bestData: any = null;
  if (module) {
    [historyData, bestData] = await Promise.all([
      fetchIntelligence(baseUrl, '/intelligence/strategy/history', { module, limit: String(limit) }).catch(() => null),
      fetchIntelligence(baseUrl, '/intelligence/strategy/best', { module }).catch(() => null),
    ]);
  }

  const stats = statsData || {};
  const effectiveness = dialecticEffData?.effectiveness || [];

  if (mode === 'brief') {
    const lines: string[] = ['## Evolution Brief\n'];

    if (!statsData) {
      lines.push('StrategyTracker not initialized or no data available.');
      return lines.join('\n');
    }

    lines.push(`**Strategy snapshots**: ${stats.totalSnapshotsRecorded || 0}`);
    lines.push(`**Evaluations**: ${stats.totalEvaluations || 0}`);
    lines.push(`**Pending**: ${stats.pendingChanges || 0} changes, ${stats.pendingSignals || 0} signals`);

    if (bestData?.strategy) {
      const best = bestData.strategy;
      lines.push(`\n**Best strategy for \`${module}\`**: score ${best.score?.toFixed(3) ?? 'N/A'} (${new Date(best.timestamp || best.created_at).toLocaleDateString()})`);
    } else if (module) {
      lines.push(`\nNo best strategy found for \`${module}\`.`);
    } else {
      lines.push('\nProvide a `module` parameter (e.g., "thinker", "dialectic") to see strategy history.');
    }

    if (effectiveness.length > 0) {
      const avgEff = effectiveness.reduce((sum: number, e: any) => sum + (e.effectivenessScore || 0), 0) / effectiveness.length;
      lines.push(`**Dialectic effectiveness**: avg ${(avgEff * 100).toFixed(1)}% across ${effectiveness.length} sessions`);
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## Evolution Dashboard\n'];

  lines.push('### Overview\n');
  lines.push('| Metric | Value |');
  lines.push('|--------|-------|');
  for (const [k, v] of Object.entries(stats)) {
    lines.push(`| ${k} | ${v} |`);
  }

  const history = historyData?.history || [];
  if (history.length > 0) {
    lines.push(`\n### Strategy History: \`${module}\`\n`);
    lines.push('| Date | Score | Config (preview) |');
    lines.push('|------|-------|------------------|');
    for (const h of history) {
      const date = new Date(h.timestamp || h.created_at).toLocaleString();
      const config = (typeof h.configJson === 'string' ? h.configJson : JSON.stringify(h.configJson || {})).slice(0, 80);
      lines.push(`| ${date} | ${h.score?.toFixed(3) ?? 'N/A'} | ${config}... |`);
    }
  } else if (module) {
    lines.push(`\n### Strategy History: \`${module}\`\n`);
    lines.push('No history found for this module.');
  }

  if (bestData?.strategy) {
    lines.push(`\n### Best Strategy: \`${module}\`\n`);
    lines.push('```json');
    lines.push(JSON.stringify(bestData.strategy, null, 2));
    lines.push('```');
  }

  if (effectiveness.length > 0) {
    lines.push('\n### Dialectic Session Effectiveness\n');
    lines.push('| Session | Effectiveness | Turns | Signals Injected |');
    lines.push('|---------|--------------|-------|-----------------|');
    for (const e of effectiveness) {
      lines.push(`| ${(e.sessionId || '').slice(0, 12)}... | ${((e.effectivenessScore || 0) * 100).toFixed(1)}% | ${e.totalTurns || 'N/A'} | ${e.signalsInjected || 'N/A'} |`);
    }
  }

  return lines.join('\n');
}

async function formatBlindspots(baseUrl: string, args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const opts: Record<string, string> = {};
  if (args?.category) opts.category = args.category;
  if (args?.minConfidence !== undefined) opts.minConfidence = String(args.minConfidence);
  opts.limit = String(args?.limit || 10);

  const [statsData, patternsData, reflectData] = await Promise.all([
    fetchIntelligence(baseUrl, '/intelligence/correlator/stats').catch(() => null),
    fetchIntelligence(baseUrl, '/intelligence/correlator/patterns', opts).catch(() => null),
    fetchIntelligence(baseUrl, '/intelligence/activity').then(d => d?.reflect?.unresolvedPatterns).catch(() => null),
  ]);

  const stats = statsData || {};
  const patterns = patternsData?.patterns || [];
  const unresolvedPatterns = reflectData || [];

  if (mode === 'brief') {
    const lines: string[] = ['## Blindspots Brief\n'];

    if (!statsData) {
      lines.push('CrossSessionCorrelator not initialized or no data available.');
      return lines.join('\n');
    }

    lines.push(`**Patterns detected**: ${stats.totalPatternsDetected || 0} (${stats.storedPatterns || 0} stored)`);

    if (stats.byCategory && Object.keys(stats.byCategory).length > 0) {
      const categories = Object.entries(stats.byCategory).sort((a: any, b: any) => b[1] - a[1]);
      lines.push(`**Categories**: ${categories.map(([k, v]) => `${k}(${v})`).join(', ')}`);
    }

    if (patterns.length > 0) {
      lines.push(`\n**Top ${Math.min(patterns.length, 3)} patterns**:`);
      for (const p of patterns.slice(0, 3)) {
        lines.push(`- [${p.category || 'uncategorized'}] ${(p.description || p.pattern || '').slice(0, 100)} (confidence: ${((p.confidence || 0) * 100).toFixed(0)}%)`);
      }
    }

    if (unresolvedPatterns.length > 0) {
      lines.push(`\n**Unresolved reflection patterns**: ${unresolvedPatterns.length}`);
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## Blindspots Dashboard\n'];

  lines.push('### Cross-Session Correlator Stats\n');
  lines.push('| Metric | Value |');
  lines.push('|--------|-------|');
  lines.push(`| Total patterns detected | ${stats.totalPatternsDetected || 0} |`);
  lines.push(`| Stored patterns | ${stats.storedPatterns || 0} |`);
  lines.push(`| Last run | ${stats.lastRunAt ? new Date(stats.lastRunAt).toLocaleString() : 'never'} |`);

  if (stats.byCategory && Object.keys(stats.byCategory).length > 0) {
    lines.push('\n**By Category**:');
    for (const [cat, count] of Object.entries(stats.byCategory)) {
      lines.push(`- ${cat}: ${count}`);
    }
  }

  if (patterns.length > 0) {
    lines.push('\n### Detected Patterns\n');
    lines.push('| Category | Confidence | Description |');
    lines.push('|----------|------------|-------------|');
    for (const p of patterns) {
      lines.push(`| ${p.category || 'uncategorized'} | ${((p.confidence || 0) * 100).toFixed(0)}% | ${(p.description || p.pattern || '').slice(0, 100)} |`);
    }

    lines.push('\n### Pattern Details\n');
    for (const p of patterns.slice(0, 5)) {
      lines.push(`#### ${p.category || 'Pattern'} (${((p.confidence || 0) * 100).toFixed(0)}% confidence)\n`);
      lines.push(`- **Key**: ${p.correlationKey || 'N/A'}`);
      lines.push(`- **Description**: ${p.description || p.pattern || 'N/A'}`);
      if (p.evidence) lines.push(`- **Evidence**: ${typeof p.evidence === 'string' ? p.evidence.slice(0, 200) : JSON.stringify(p.evidence).slice(0, 200)}`);
      if (p.sessionIds) lines.push(`- **Sessions**: ${Array.isArray(p.sessionIds) ? p.sessionIds.length : 'N/A'}`);
      lines.push('');
    }
  }

  if (unresolvedPatterns.length > 0) {
    lines.push('\n### Unresolved Reflection Patterns\n');
    lines.push('These error/concern patterns from the Reflect module remain unresolved:\n');
    for (const p of unresolvedPatterns) {
      lines.push(`- **${p.pattern || p.category || 'unknown'}** (${p.occurrences || 1}x): ${p.description || p.evidence || 'no description'}`);
    }
  }

  return lines.join('\n');
}

async function formatSnapshot(baseUrl: string, args: any): Promise<string> {
  const teamId = args?.teamId;
  const includeMessages = args?.includeMessages !== false;
  const messageLimit = args?.messageLimit || 5;

  const lines: string[] = ['# CassiCore Agent Snapshot\n'];
  lines.push(`*Generated: ${new Date().toISOString()}*\n`);

  try {
    const teamsData = await fetchIntelligence(baseUrl, '/teams');
    let teams = teamsData?.teams || [];

    if (teamId) {
      teams = teams.filter((t: any) => t.id === teamId);
      if (teams.length === 0) {
        return `# CassiCore Agent Snapshot\n\n**Error**: Team "${teamId}" not found.`;
      }
    }

    const activeTeams = teams.filter((t: any) => t.status === 'running' || t.status === 'paused');
    const displayTeams = activeTeams.length > 0 ? activeTeams : teams;

    if (displayTeams.length === 0) {
      lines.push('## No Active Teams\n');
      lines.push('No teams are currently running. Use `cassi_team` with action "list" to see all teams.');
    } else {
      lines.push(`## Active Teams (${displayTeams.length})\n`);

      for (const team of displayTeams) {
        const tid = team.id;

        const statusRes = await fetchWithTimeout(`${baseUrl}/teams/status?teamId=${encodeURIComponent(tid)}`);
        const statusData = statusRes.ok ? await statusRes.json() : null;

        const agentsRes = await fetchWithTimeout(`${baseUrl}/teams/agent/list?teamId=${encodeURIComponent(tid)}`);
        const agentsData = agentsRes.ok ? await agentsRes.json() : null;

        const checkpointsRes = await fetchWithTimeout(`${baseUrl}/teams/checkpoints?teamId=${encodeURIComponent(tid)}`);
        const checkpointsData = checkpointsRes.ok ? await checkpointsRes.json() : null;

        lines.push(`### Team: ${tid}`);
        lines.push(`**Goal:** ${team.goal || 'No goal set'}`);

        const progress = statusData?.progress;
        if (progress) {
          lines.push(`**Progress:** ${progress.completed || 0}/${progress.total || 0} goals (${progress.percentage || 0}%)`);
        }

        lines.push(`**Status:** ${team.status} | **Agents:** ${team.agentCount || 0} | **Started:** ${team.startedAt ? new Date(team.startedAt).toLocaleString() : 'N/A'}`);

        if (statusData?.team?.budget) {
          const b = statusData.team.budget;
          lines.push(`**Budget:** ${b.tokensUsed?.toLocaleString() || 0} tokens used${b.maxTokens ? ` / ${b.maxTokens.toLocaleString()} max` : ''}`);
        }
        lines.push('');

        const agents = agentsData?.agents || [];
        if (agents.length > 0) {
          lines.push('#### Agents\n');

          for (const agent of agents) {
            const role = agent.isCoordinator ? 'coordinator' : (agent.roleHint || 'agent');
            const statusEmoji = agent.goalStatus === 'completed' ? '✓' :
                               agent.goalStatus === 'in_progress' ? '▶' :
                               agent.goalStatus === 'failed' ? '✗' : '○';

            lines.push(`- **${agent.agentId}** (${role}): ${agent.goalTitle || 'No goal'} ${statusEmoji}`);

            if (includeMessages) {
              try {
                const sessionRes = await fetchWithTimeout(`${baseUrl}/sessions?limit=50`);
                if (sessionRes.ok) {
                  const sessionsData = await sessionRes.json();
                  const agentSession = sessionsData?.sessions?.find((s: any) =>
                    s.id?.includes(agent.agentId) || s.agentId === agent.agentId
                  );

                  if (agentSession?.id) {
                    const msgRes = await fetchWithTimeout(`${baseUrl}/sessions/${encodeURIComponent(agentSession.id)}/messages?limit=${messageLimit}`);
                    if (msgRes.ok) {
                      const msgData = await msgRes.json();
                      const recentMsgs = msgData?.messages?.slice(-messageLimit) || [];

                      if (recentMsgs.length > 0) {
                        const lastMsg = recentMsgs[recentMsgs.length - 1];
                        const preview = (lastMsg.content || lastMsg.text || '').slice(0, 100);
                        if (preview) {
                          lines.push(`  > Last: "${preview}${preview.length >= 100 ? '...' : ''}"`);
                        }
                      }
                    }
                  }
                }
              } catch (msgErr) {
                // Silently skip message fetching errors
              }
            }
          }
          lines.push('');
        }

        const checkpoints = checkpointsData?.checkpoints || [];
        if (checkpoints.length > 0) {
          lines.push('#### Pending Checkpoints\n');
          for (const cp of checkpoints) {
            lines.push(`- **${cp.checkpointId}**: ${cp.description || 'No description'} (${cp.status})`);
          }
          lines.push('');
        }

        lines.push('---\n');
      }
    }

    lines.push('## Git Status\n');
    try {
      const { execSync } = await import('child_process');
      const cwd = process.cwd();

      const GIT_MAX_LINES = 40;
      const statusOutput = execSync('git status --short', { cwd, encoding: 'utf-8', timeout: 5000 });
      const diffStatOutput = execSync('git diff --stat', { cwd, encoding: 'utf-8', timeout: 5000 });

      if (statusOutput.trim()) {
        const statusLines = statusOutput.trim().split('\n');
        const statusTruncated = statusLines.length > GIT_MAX_LINES;
        const statusSlice = statusTruncated ? statusLines.slice(0, GIT_MAX_LINES) : statusLines;
        lines.push('```');
        lines.push(statusSlice.join('\n'));
        if (statusTruncated) lines.push(`... and ${statusLines.length - GIT_MAX_LINES} more files (truncated)`);
        lines.push('```\n');

        if (diffStatOutput.trim()) {
          const diffLines = diffStatOutput.trim().split('\n');
          const diffTruncated = diffLines.length > GIT_MAX_LINES + 1; // +1 for summary line
          // Keep the summary line (last line) if truncating
          const diffSlice = diffTruncated
            ? [...diffLines.slice(0, GIT_MAX_LINES), diffLines[diffLines.length - 1]]
            : diffLines;
          lines.push('**Changes:**');
          lines.push('```');
          lines.push(diffSlice.join('\n'));
          if (diffTruncated) lines.push(`... ${diffLines.length - GIT_MAX_LINES - 1} files omitted`);
          lines.push('```');
        }
      } else {
        lines.push('*Working directory clean*');
      }
    } catch (gitErr: any) {
      lines.push(`*Git status unavailable: ${gitErr.message || 'Unknown error'}*`);
    }

    return lines.join('\n');
  } catch (error: any) {
    return `## Error\n\nFailed to generate snapshot: ${error.message}\n\nMake sure the CassiCore daemon is running.`;
  }
}

async function formatTrust(baseUrl: string, args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const domain = args?.domain;

  if (domain) {
    const data = await fetchIntelligence(baseUrl, `/trust/${domain}`).catch(() => null);
    if (!data) {
      return `## Trust: ${domain}\n\nDomain not found. Use cassi_trust without a domain to see all domains.`;
    }
    const lines: string[] = [`## Trust: ${domain}\n`];
    lines.push(`| Metric | Value |`);
    lines.push(`|--------|-------|`);
    lines.push(`| **Score** | ${(data.score || 0.5).toFixed(3)} |`);
    lines.push(`| Alpha (successes) | ${(data.alpha || 1).toFixed(1)} |`);
    lines.push(`| Beta (failures) | ${(data.beta || 1).toFixed(1)} |`);
    lines.push(`| Confidence | ${(data.confidence || 0).toFixed(2)} |`);
    lines.push(`| Evidence count | ${data.evidenceCount || 0} |`);
    lines.push(`| Last updated | ${data.lastUpdatedAt ? new Date(data.lastUpdatedAt).toLocaleString() : 'never'} |`);
    return lines.join('\n');
  }

  const data = await fetchIntelligence(baseUrl, '/trust').catch(() => null);
  if (!data) {
    return '## Trust Summary\n\nTrust Ledger not available. Make sure the CassiCore daemon is running.';
  }

  const lines: string[] = ['## Trust Summary\n'];
  lines.push(`**Overall trust**: ${(data.overallScore || 0.5).toFixed(3)}`);
  lines.push(`**Autonomy level**: ${data.autonomyLevel || 'unknown'}`);
  lines.push(`**Total evidence**: ${data.totalEvidence || 0}`);

  if (data.strongestDomain) {
    lines.push(`**Strongest domain**: ${data.strongestDomain.domain} (${(data.strongestDomain.score || 0).toFixed(3)})`);
  }
  if (data.weakestDomain) {
    lines.push(`**Weakest domain**: ${data.weakestDomain.domain} (${(data.weakestDomain.score || 0).toFixed(3)})`);
  }

  if (mode === 'full' && data.domains) {
    lines.push('\n### Per-Domain Trust Scores\n');
    lines.push('| Domain | Score | Alpha | Beta | Evidence | Confidence |');
    lines.push('|--------|-------|-------|------|----------|------------|');
    const domains = Object.entries(data.domains).sort((a: any, b: any) => (b[1]?.score || 0) - (a[1]?.score || 0));
    for (const [name, d] of domains) {
      const dd = d as any;
      lines.push(`| ${name} | ${(dd.score || 0.5).toFixed(3)} | ${(dd.alpha || 1).toFixed(1)} | ${(dd.beta || 1).toFixed(1)} | ${dd.evidenceCount || 0} | ${(dd.confidence || 0).toFixed(2)} |`);
    }
  }

  if (data.stats) {
    lines.push('\n### Ledger Stats\n');
    lines.push(`- Domains tracked: ${data.stats.domainCount || 0}`);
    lines.push(`- Total evidence ingested: ${data.stats.totalEvidence || 0}`);
    lines.push(`- Total decays applied: ${data.stats.totalDecays || 0}`);
  }

  return lines.join('\n');
}

async function formatConsequences(baseUrl: string, args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const limit = args?.limit || 10;

  const [statsData, permStatsData, logData, pendingData] = await Promise.all([
    fetchIntelligence(baseUrl, '/consequences/stats').catch(() => null),
    fetchIntelligence(baseUrl, '/permissions/stats').catch(() => null),
    fetchIntelligence(baseUrl, `/permissions/log?limit=${limit}`).catch(() => null),
    fetchIntelligence(baseUrl, '/permissions/pending').catch(() => null),
  ]);

  const lines: string[] = ['## Consequences & Permissions\n'];

  const pendingCount = pendingData?.count || 0;
  if (pendingCount > 0) {
    lines.push(`**PENDING APPROVALS: ${pendingCount}** — human decision required\n`);
    for (const p of (pendingData?.pending || [])) {
      const age = ((Date.now() - p.createdAt) / 1000).toFixed(0);
      lines.push(`- **${p.toolName}** [${p.riskLevel}] risk=${(p.riskScore || 0).toFixed(2)}, trust=${(p.trustScore || 0).toFixed(2)} — ${p.reasoning} (${age}s ago, ID: ${p.id})`);
    }
    lines.push('');
  }

  if (statsData) {
    lines.push(`**Risk assessments**: ${statsData.assessments || 0} (${statsData.failures || 0} failures, ${((statsData.failureRate || 0) * 100).toFixed(1)}% failure rate)`);
  }

  if (permStatsData) {
    const ps = permStatsData;
    lines.push(`**Permission decisions**: ${ps.totalDecisions || 0} — ${ps.allowCount || 0} allowed, ${ps.escalateCount || 0} escalated, ${ps.denyCount || 0} denied`);
    lines.push(`**Allow rate**: ${((ps.allowRate || 0) * 100).toFixed(1)}% | **Escalate rate**: ${((ps.escalateRate || 0) * 100).toFixed(1)}%`);
    if (ps.totalApprovals || ps.totalRejections || ps.totalTimeouts) {
      lines.push(`**Human responses**: ${ps.totalApprovals || 0} approved, ${ps.totalRejections || 0} rejected, ${ps.totalTimeouts || 0} timed out`);
    }
  }

  if (mode === 'full' && logData?.decisions?.length > 0) {
    lines.push('\n### Recent Permission Decisions\n');
    lines.push('| Tool | Decision | Risk | Trust | Level | Reasoning |');
    lines.push('|------|----------|------|-------|-------|-----------|');
    for (const d of logData.decisions) {
      lines.push(`| ${d.toolName} | ${d.decision} | ${(d.riskScore || 0).toFixed(2)} (${d.riskLevel}) | ${(d.trustScore || 0).toFixed(2)} | ${d.autonomyLevel} | ${(d.reasoning || '').slice(0, 80)} |`);
    }
  }

  return lines.join('\n');
}

// ═══════════════════════════════════════════════════════════════════════════════
// Execute Intelligence Tool
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Execute an intelligence tool — routes to the appropriate formatter
 */
export async function executeIntelligenceTool(
  baseUrl: string,
  toolName: string,
  args: any,
  logger: ILogger
): Promise<string> {
  logger.info('Executing intelligence tool', { tool: toolName, args });

  const formatters: Record<string, (baseUrl: string, args: any) => Promise<string>> = {
    cassi_activity: formatActivity,
    cassi_thinker: formatThinker,
    cassi_subconscious: formatSubconscious,
    cassi_consciousness: formatConsciousness,
    cassi_trace: formatTrace,
    cassi_effectiveness: formatEffectiveness,
    cassi_budget: formatBudget,
    cassi_evolution: formatEvolution,
    cassi_blindspots: formatBlindspots,
    cassi_snapshot: formatSnapshot,
    cassi_trust: formatTrust,
    cassi_consequences: formatConsequences,
  };

  const formatter = formatters[toolName];
  if (!formatter) {
    throw new Error(`Unknown intelligence tool: ${toolName}`);
  }

  try {
    return await formatter(baseUrl, args);
  } catch (error: any) {
    logger.error('Intelligence tool failed', { tool: toolName, error: String(error) });
    return `## Error\n\nFailed to execute ${toolName}: ${error.message}\n\nMake sure the CassiCore daemon is running.`;
  }
}

/**
 * Get all intelligence tool definitions
 */
export function getIntelligenceTools(): Array<{
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}> {
  return INTELLIGENCE_TOOLS;
}
