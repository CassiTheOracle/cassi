/**
 * Tool Risk Table — Static risk profiles for known tools.
 *
 * This is the heuristic knowledge base. Each tool gets a baseline risk profile
 * that the Consequence Estimator uses as a starting point before examining
 * specific inputs. Input-sensitive rules adjust dimensions up or down based
 * on what's actually being passed to the tool.
 *
 * Design principle: baselines are deliberately conservative.
 * A tool's true risk may be lower for specific inputs, but the baseline
 * represents a "typical worst case" for that tool class.
 */

import type { ToolRiskProfile, RiskDimensions, Reversibility } from './types.js'


/**
 * @dep callers: tool-risk-table.ts (core/intelligence/consequence-estimator/tool-risk-table.ts), getToolRiskProfile (core/intelligence/consequence-estimator/tool-risk-table.ts)
 * @dep module: Consequence-estimator
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function profile(
  toolName: string,
  baselineDimensions: RiskDimensions,
  defaultReversibility: Reversibility,
  inputSensitivity: ToolRiskProfile['inputSensitivity'] = {},
  hardCeiling?: Partial<RiskDimensions>,
): ToolRiskProfile {
  return { toolName, baselineDimensions, defaultReversibility, inputSensitivity, hardCeiling }
}

/**
 * Static risk profiles for known tools.
 * Key = tool name (base name without MCP prefix).
 */
export const TOOL_RISK_TABLE: Record<string, ToolRiskProfile> = {
  'read': profile('read', {
    dataLoss: 0.0, systemStability: 0.0, externalImpact: 0.0, resourceCost: 0.05, privacyRisk: 0.1,
  }, 'fully'),

  'read_file': profile('read_file', {
    dataLoss: 0.0, systemStability: 0.0, externalImpact: 0.0, resourceCost: 0.05, privacyRisk: 0.1,
  }, 'fully', {
    privacyRisk: [
      { description: 'Reading .env or credential files', pattern: /\.env|credentials|secret|\.pem|\.key|password/i, paramKey: 'path', adjustment: 0.7, reason: 'May expose secrets' },
    ],
  }),

  'grep': profile('grep', {
    dataLoss: 0.0, systemStability: 0.0, externalImpact: 0.0, resourceCost: 0.05, privacyRisk: 0.05,
  }, 'fully'),

  'glob': profile('glob', {
    dataLoss: 0.0, systemStability: 0.0, externalImpact: 0.0, resourceCost: 0.02, privacyRisk: 0.0,
  }, 'fully'),

  'write': profile('write', {
    dataLoss: 0.3, systemStability: 0.1, externalImpact: 0.0, resourceCost: 0.05, privacyRisk: 0.05,
  }, 'partially', {
    dataLoss: [
      { description: 'Overwriting existing file', pattern: /.*/, paramKey: 'path', adjustment: 0.0, reason: 'All writes have some data loss risk (overwrite)' },
    ],
    systemStability: [
      { description: 'Writing to config files', pattern: /config|\.json$|\.yaml$|\.yml$|\.toml$/i, paramKey: 'path', adjustment: 0.4, reason: 'Config changes can destabilize system' },
      { description: 'Writing to source code', pattern: /\.ts$|\.js$|\.go$|\.py$/i, paramKey: 'path', adjustment: 0.2, reason: 'Code changes affect system behavior' },
    ],
  }),

  'write_file': profile('write_file', {
    dataLoss: 0.3, systemStability: 0.1, externalImpact: 0.0, resourceCost: 0.05, privacyRisk: 0.05,
  }, 'partially', {
    dataLoss: [
      // WHY: Short content written to source files is a strong signal of truncation.
      // A legitimate full-file rewrite has substantial content; a truncation typically
      // replaces hundreds of lines with a stub or empty file.
      { description: 'Suspiciously short content for source files', pattern: /^.{0,200}$/s, paramKey: 'content', adjustment: 0.4, reason: 'Very short content may indicate file truncation' },
    ],
    systemStability: [
      { description: 'Writing to config files', pattern: /config|\.json$|\.yaml$|\.yml$|\.toml$/i, paramKey: 'path', adjustment: 0.4, reason: 'Config changes can destabilize system' },
      { description: 'Writing to source code', pattern: /\.ts$|\.js$|\.go$|\.py$/i, paramKey: 'path', adjustment: 0.2, reason: 'Code changes affect system behavior' },
    ],
  }),

  'edit': profile('edit', {
    dataLoss: 0.2, systemStability: 0.1, externalImpact: 0.0, resourceCost: 0.05, privacyRisk: 0.05,
  }, 'partially'), // Edits are targeted, lower risk than full writes

  'delete': profile('delete', {
    dataLoss: 0.7, systemStability: 0.3, externalImpact: 0.0, resourceCost: 0.05, privacyRisk: 0.0,
  }, 'irreversible', {
    dataLoss: [
      { description: 'Deleting directories', pattern: /\/$/i, paramKey: 'path', adjustment: 0.2, reason: 'Directory deletion affects multiple files' },
    ],
  }),

  'bash': profile('bash', {
    dataLoss: 0.4, systemStability: 0.5, externalImpact: 0.2, resourceCost: 0.3, privacyRisk: 0.2,
  }, 'partially', {
    dataLoss: [
      { description: 'rm commands', pattern: /\brm\s/i, paramKey: 'command', adjustment: 0.4, reason: 'File deletion command' },
      { description: 'Force delete', pattern: /rm\s+-rf?\s/i, paramKey: 'command', adjustment: 0.5, reason: 'Recursive forced deletion' },
    ],
    systemStability: [
      { description: 'Kill/stop process', pattern: /\b(?:kill|pkill|killall|systemctl\s+stop)\b/i, paramKey: 'command', adjustment: 0.3, reason: 'Process termination' },
      { description: 'System service commands', pattern: /\b(?:systemctl|service)\b/i, paramKey: 'command', adjustment: 0.3, reason: 'System service management' },
      { description: 'npm/pip install', pattern: /\b(?:npm\s+install|pip\s+install|apt\s+install)\b/i, paramKey: 'command', adjustment: 0.2, reason: 'Package installation modifies system' },
    ],
    externalImpact: [
      { description: 'git push', pattern: /\bgit\s+push\b/i, paramKey: 'command', adjustment: 0.5, reason: 'Pushes code to remote' },
      { description: 'curl/wget POST', pattern: /\b(?:curl|wget)\b.*\b(?:POST|PUT|DELETE)\b/i, paramKey: 'command', adjustment: 0.4, reason: 'Outbound HTTP mutation' },
      { description: 'Deploy commands', pattern: /\b(?:deploy|publish|release)\b/i, paramKey: 'command', adjustment: 0.6, reason: 'Deployment to external systems' },
    ],
    privacyRisk: [
      { description: 'Environment variable access', pattern: /\$\{?\w*(?:KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL)\w*\}?/i, paramKey: 'command', adjustment: 0.5, reason: 'Accesses sensitive env vars' },
    ],
  }, {
    // Hard ceiling: even "safe" bash commands should never be rated as zero-risk
    systemStability: 0.9,
    externalImpact: 0.9,
  }),

  'web_fetch': profile('web_fetch', {
    dataLoss: 0.0, systemStability: 0.05, externalImpact: 0.2, resourceCost: 0.1, privacyRisk: 0.15,
  }, 'fully', {
    externalImpact: [
      { description: 'POST/PUT/DELETE requests', pattern: /method.*(?:POST|PUT|DELETE)/i, paramKey: 'url', adjustment: 0.4, reason: 'Mutating HTTP method' },
    ],
    privacyRisk: [
      { description: 'Internal network access', pattern: /(?:localhost|127\.0\.0\.1|10\.\d|192\.168|172\.(?:1[6-9]|2\d|3[01]))/i, paramKey: 'url', adjustment: 0.3, reason: 'Internal network access' },
    ],
  }),

  'memory_store': profile('memory_store', {
    dataLoss: 0.0, systemStability: 0.0, externalImpact: 0.0, resourceCost: 0.05, privacyRisk: 0.1,
  }, 'fully'),

  'memory_delete': profile('memory_delete', {
    dataLoss: 0.3, systemStability: 0.0, externalImpact: 0.0, resourceCost: 0.05, privacyRisk: 0.0,
  }, 'irreversible'),

  'git': profile('git', {
    dataLoss: 0.2, systemStability: 0.1, externalImpact: 0.3, resourceCost: 0.05, privacyRisk: 0.05,
  }, 'partially'),
}

/**
 * Look up a tool's risk profile, falling back to a default high-risk profile
 * for unknown tools. This is intentionally conservative — unknown tools
 * are treated as potential shell commands until proven otherwise.
 * @dep callers: consequence-estimator.test.ts (tests/consequence-estimator.test.ts), heuristicAssess (core/intelligence/consequence-estimator/index.ts), start (core/intelligence/consequence-estimator/index.ts)
 * @dep calls: profile
 * @dep module: Consequence-estimator
 * @dep risk: LOW | 3 callers, 0 flows, 1 module
 */
export function getToolRiskProfile(toolName: string): ToolRiskProfile {
  // Direct match
  if (TOOL_RISK_TABLE[toolName]) return TOOL_RISK_TABLE[toolName]

  // Strip MCP prefix (e.g., 'serena__find_file' → 'find_file')
  if (toolName.includes('__')) {
    const baseName = toolName.split('__').pop()!
    if (TOOL_RISK_TABLE[baseName]) return TOOL_RISK_TABLE[baseName]
  }

  // Strip 'cassi_' prefix
  if (toolName.startsWith('cassi_')) {
    const baseName = toolName.replace(/^cassi_/, '')
    if (TOOL_RISK_TABLE[baseName]) return TOOL_RISK_TABLE[baseName]
  }

  // Heuristic classification by name pattern
  if (toolName.includes('read') || toolName.includes('search') || toolName.includes('find') || toolName.includes('list') || toolName.includes('get') || toolName.includes('overview') || toolName.includes('snapshot')) {
    return profile(toolName, {
      dataLoss: 0.0, systemStability: 0.0, externalImpact: 0.0, resourceCost: 0.05, privacyRisk: 0.1,
    }, 'fully')
  }

  if (toolName.includes('write') || toolName.includes('edit') || toolName.includes('replace') || toolName.includes('insert') || toolName.includes('create')) {
    return profile(toolName, {
      dataLoss: 0.3, systemStability: 0.15, externalImpact: 0.0, resourceCost: 0.05, privacyRisk: 0.05,
    }, 'partially')
  }

  if (toolName.includes('delete') || toolName.includes('remove')) {
    return profile(toolName, {
      dataLoss: 0.6, systemStability: 0.2, externalImpact: 0.0, resourceCost: 0.05, privacyRisk: 0.0,
    }, 'irreversible')
  }

  // Unknown tool — conservative default
  return profile(toolName, {
    dataLoss: 0.3, systemStability: 0.3, externalImpact: 0.2, resourceCost: 0.2, privacyRisk: 0.2,
  }, 'partially')
}
