/**
 * Cognitive Context Builder for Claude Code — Aurora Edition.
 *
 * Pulls serialized mental state from Aurora, which integrates memory (Mnemic
 * Field), model knowledge (LARQL), cortical signals, and affect into a unified
 * cognitive graph. Aurora decides what's salient; StateProjector serializes it
 * into a compact narrative form. We inject that directly.
 *
 * Falls back to the Global Workspace if Aurora isn't available yet.
 */

import * as bridge from "./bridge.js";
import {
  type SessionState,
  type PressureTier,
  classifyTier,
} from "./state.js";

const MAX_CONTEXT_CHARS = 9_500;

/**
 * Build cognitive context — Aurora-first with GWT fallback.
 */
export async function buildCognitiveContext(
  state: SessionState,
  options: { includeRecovery?: boolean; compact?: boolean } = {},
): Promise<string> {
  const parts: string[] = [];
  let charCount = 0;

  const push = (text: string): boolean => {
    if (charCount + text.length > MAX_CONTEXT_CHARS) return false;
    parts.push(text);
    charCount += text.length;
    return true;
  };

  // Aurora: unified mental state (memory + model knowledge + affect + cortex).
  // Prefer the serialized narrative over the raw state object because the
  // narrative is what's tuned for prompt injection and includes coherence,
  // integration, knowledge-landscape gaps, and trending concepts in one block.
  const auroraText = await bridge.auroraSerialized().catch(() => null);
  if (auroraText && auroraText.trim().length > 0) {
    push(`<aurora>\n${auroraText}\n</aurora>`);
  } else {
    // GWT fallback when Aurora isn't wired up yet
    const workspace = await bridge.workspaceContext("*");
    if (workspace?.parts?.length) {
      for (const part of workspace.parts) {
        const content = part.content as string;
        if (!content) continue;
        if (!push(content)) break;
      }
    }
  }

  // Pressure status (comes from transcript size, not workspace)
  const tier = classifyTier(state.estimatedPressure);
  if (tier !== "healthy") {
    push(buildPressureBlock(state, tier));
  }

  // Post-compaction recovery context
  if (options.includeRecovery) {
    const recovery = await buildRecoveryContext(state);
    if (recovery) push(recovery);
  }

  if (parts.length === 0) return "";
  return `<cassicore-context>\n${parts.join("\n\n")}\n</cassicore-context>`;
}

function buildPressureBlock(state: SessionState, tier: PressureTier): string {
  const pct = Math.round(state.estimatedPressure * 100);
  const lines = [`**Context Pressure:** ${pct}% (${tier}) — Turn ${state.turnCount}`];

  if (tier === "elevated") {
    lines.push("Consider collapsing old tool results to free space.");
  } else if (tier === "high") {
    lines.push("Pressure is high. Collapse old file reads and search results.");
  } else if (tier === "critical") {
    lines.push("CRITICAL: Context is nearly full. Remove large old chunks or delegate remaining work:");
    lines.push('`cassi_agent({ type: "constellation", action: "project", goal: "Continue: <task>" })`');
  } else if (tier === "overflow") {
    lines.push("EMERGENCY: Context overflow. Delegate remaining work to Constellation immediately.");
  }

  return lines.join("\n");
}

async function buildRecoveryContext(state: SessionState): Promise<string | null> {
  const sid = state.ccSessionId;

  const handoff = await bridge.kvGet(`handoff:${sid}`);
  if (handoff && typeof handoff === "object") {
    const h = handoff as any;
    return `**Recovery from compaction:**\n` +
      `Focus: ${h.focusTopic ?? "unknown"}\n` +
      `Active files: ${(h.activeFiles ?? []).join(", ") || "none"}\n` +
      `Recent tools: ${(h.usedTools ?? []).slice(-5).join(", ") || "none"}\n` +
      (h.criticalContext?.length ? `Critical:\n${h.criticalContext.map((c: string) => `- ${c}`).join("\n")}` : "");
  }

  const checkpoint = await bridge.kvGet(`checkpoint:${sid}`);
  if (checkpoint && typeof checkpoint === "object") {
    const cp = checkpoint as any;
    return `**Checkpoint recovery:**\n` +
      `Turn: ${cp.turnCount}, Focus: ${cp.focusTopic ?? "unknown"}\n` +
      `Files: ${(cp.activeFiles ?? []).join(", ") || "none"}`;
  }

  return null;
}

/**
 * Build a compact pressure warning for injection after tool calls.
 */
export function buildPressureWarning(state: SessionState): string | null {
  const tier = classifyTier(state.estimatedPressure);
  if (tier === "healthy" || tier === "warming") return null;
  if (tier === state.warnedAtTier) return null;

  state.warnedAtTier = tier;
  state.lastTier = tier;

  const pct = Math.round(state.estimatedPressure * 100);

  if (tier === "elevated") {
    return `Context at ${pct}%. Consider consolidating work — older tool results are consuming space.`;
  }
  if (tier === "high") {
    return `Context at ${pct}% (high). Collapse old results or delegate complex remaining work to Constellation.`;
  }
  if (tier === "critical" || tier === "overflow") {
    return `Context at ${pct}% (${tier}). Save progress to blackboard and delegate remaining work: cassi_agent({ type: "constellation", action: "project", goal: "Continue: ..." })`;
  }

  return null;
}
