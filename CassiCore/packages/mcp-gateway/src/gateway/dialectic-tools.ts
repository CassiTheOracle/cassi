#!/usr/bin/env node
/**
 * Dialectic Tools Module
 * Yang/Yin/Synthesizer dialectic analysis tools
 */

import { fetchIntelligence, resolveSessionId } from './helpers.js';
import type { ILogger } from '../../types/interfaces.js';

/**
 * Tool definitions for dialectic tools
 */
export const DIALECTIC_TOOLS = [
  {
    name: 'dialectic',
    description: "View the Yang/Yin/Synthesizer dialectic analysis — recent turns, signal injection history, confidence scores, and synthesis outcomes. Shows how the dialectic trio processes each conversation turn.",
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: {
          type: 'string',
          description: 'Session ID to inspect (optional, defaults to most recent active session)',
        },
        limit: {
          type: 'number',
          description: 'Number of recent dialectic turns to show (default 5)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed dashboard',
        },
      },
    },
  },
];

/**
 * Dialectic tool names set for quick lookup
 */
export const DIALECTIC_TOOL_NAMES = new Set(DIALECTIC_TOOLS.map(t => t.name));

/**
 * Format cassi_dialectic output
 */
async function formatDialectic(baseUrl: string, args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const limit = args?.limit || 5;
  const sessionId = await resolveSessionId(baseUrl, args?.sessionId);

  if (!sessionId) {
    return '## Dialectic\n\nNo active session found. Provide a `sessionId` parameter or start a conversation first.';
  }

  const [historyData, statsData] = await Promise.all([
    fetchIntelligence(baseUrl, `/dialectic/${sessionId}/history`, { limit: String(limit) }),
    fetchIntelligence(baseUrl, `/dialectic/${sessionId}/stats`).catch(() => null),
  ]);

  const history = historyData?.history || historyData?.turns || historyData || [];
  const stats = statsData?.stats || statsData;

  if (mode === 'brief') {
    const lines: string[] = [`## Dialectic Brief (session: ${sessionId.slice(0, 12)}...)\n`];

    if (stats) {
      lines.push(`**${stats.totalTurns || 0}** turns analyzed | **${stats.signalsInjected || 0}** signals injected | avg confidence: **${(stats.avgConfidence || 0).toFixed(2)}**`);
    }

    const recent = Array.isArray(history) ? history.slice(0, 3) : [];
    if (recent.length > 0) {
      lines.push('\n**Recent Analysis**:');
      for (const turn of recent) {
        const yang = turn.yang || turn.yang_output || turn.yangOutput;
        const synth = turn.serenity || turn.synthesizer_output || turn.synthesizerOutput;
        const injected = turn.signal_injected ?? turn.signalInjected;
        const yangSummary = typeof yang === 'string' ? yang.slice(0, 80) : (yang?.observation || yang?.summary || JSON.stringify(yang)).slice(0, 80);
        lines.push(`- ${injected ? '[INJECTED]' : '[observed]'} ${yangSummary}${yangSummary.length >= 80 ? '...' : ''}`);
      }
    } else {
      lines.push('\nNo dialectic turns recorded for this session yet.');
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = [`## Dialectic Dashboard (session: ${sessionId.slice(0, 12)}...)\n`];

  // Stats table
  if (stats) {
    lines.push('### Statistics\n');
    for (const [k, v] of Object.entries(stats)) {
      lines.push(`- **${k}**: ${typeof v === 'number' ? (Number.isInteger(v) ? v : (v as number).toFixed(3)) : v}`);
    }
  }

  // Turn history
  const turns = Array.isArray(history) ? history : [];
  if (turns.length > 0) {
    lines.push(`\n### Recent Turns (${turns.length})\n`);
    for (let i = 0; i < turns.length; i++) {
      const turn = turns[i];
      const yang = turn.yang || turn.yang_output || turn.yangOutput;
      const yin = turn.yin || turn.yin_output || turn.yinOutput;
      const synth = turn.serenity || turn.synthesizer_output || turn.synthesizerOutput;
      const injected = turn.signal_injected ?? turn.signalInjected;
      const latency = turn.total_latency_ms ?? turn.totalLatencyMs;

      lines.push(`#### Turn ${i + 1} ${injected ? '(SIGNAL INJECTED)' : ''}`);
      if (latency) lines.push(`*Latency: ${latency}ms*\n`);

      // Yang
      lines.push('**Yang (Creative Observer)**:');
      if (typeof yang === 'object' && yang !== null) {
        lines.push('```json');
        lines.push(JSON.stringify(yang, null, 2));
        lines.push('```');
      } else {
        lines.push(`> ${yang || 'N/A'}`);
      }

      // Yin
      lines.push('\n**Yin (Critical Analyst)**:');
      if (typeof yin === 'object' && yin !== null) {
        lines.push('```json');
        lines.push(JSON.stringify(yin, null, 2));
        lines.push('```');
      } else {
        lines.push(`> ${yin || 'N/A'}`);
      }

      // Synthesizer
      lines.push('\n**Synthesizer (Serenity)**:');
      if (typeof synth === 'object' && synth !== null) {
        lines.push('```json');
        lines.push(JSON.stringify(synth, null, 2));
        lines.push('```');
      } else {
        lines.push(`> ${synth || 'N/A'}`);
      }
      lines.push('');
    }
  } else {
    lines.push('\nNo dialectic turns recorded for this session.');
  }

  return lines.join('\n');
}

/**
 * Execute a dialectic tool
 */
export async function executeDialecticTool(
  baseUrl: string,
  toolName: string,
  args: any,
  logger: ILogger
): Promise<string> {
  logger.info('Executing dialectic tool', { tool: toolName, args });

  try {
    switch (toolName) {
      case 'dialectic':
        return await formatDialectic(baseUrl, args);
      default:
        throw new Error(`Unknown dialectic tool: ${toolName}`);
    }
  } catch (error: any) {
    logger.error('Dialectic tool failed', { tool: toolName, error: String(error) });
    return `## Error\n\nFailed to execute ${toolName}: ${error.message}\n\nMake sure the CassiCore daemon is running.`;
  }
}

/**
 * Get all dialectic tool definitions
 * @dep callers: getAllTools (mcp/cassicore-gateway.ts)
 * @dep flows: CreateHierarchyBridge → GetDialecticTools (4/4)
 * @dep module: Gateway
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */
export function getDialecticTools(): Array<{
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}> {
  return DIALECTIC_TOOLS;
}
