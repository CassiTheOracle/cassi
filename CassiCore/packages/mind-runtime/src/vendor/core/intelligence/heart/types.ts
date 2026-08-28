/**
 * Heart Module Types
 *
 * Configuration and type definitions for the Heart intelligence module
 * that performs periodic autonomous agent heartbeats.
 */

export interface HeartConfig {
  enabled: boolean
  /** Interval between heartbeats (default: 30 min = 1800000ms) */
  intervalMs: number
  /** Heartbeat prompt sent as user message */
  prompt: string
  /** Path to HEARTBEAT.md relative to workspace (default: "HEARTBEAT.md") */
  heartbeatFilePath: string
  /** Delivery target: "last" | "none" | channel ID */
  target: string
  /** Optional: channel-specific recipient (e.g., telegram chat ID) */
  to?: string
  /** Max chars after HEARTBEAT_OK before delivery is triggered (default: 300) */
  ackMaxChars: number
  /** Active hours window (skip heartbeats outside this range) */
  activeHours?: {
    start: string   // "HH:MM" (inclusive)
    end: string     // "HH:MM" (exclusive, "24:00" allowed)
    timezone?: string // IANA tz or "local"
  }
  /** Include reasoning message alongside alert delivery */
  includeReasoning: boolean
  /** Model/provider overrides (inherits from module model config) */
  model?: string
  provider?: string
}

export interface HeartbeatResult {
  cycleNumber: number
  response: string
  isOk: boolean          // Parsed as HEARTBEAT_OK
  alertContent?: string  // Non-OK content for delivery
  reasoning?: string     // Optional reasoning if includeReasoning is true
  durationMs: number
  tokensUsed: { input: number; output: number }
  skippedReason?: string // Why heartbeat was skipped (if applicable)
}

export interface HeartState {
  cycleNumber: number
  lastBeatAt?: number
  nextBeatAt?: number
  lastDeliveryAt?: number
  totalDeliveries: number
  totalSkips: number
}

export const DEFAULT_HEART_CONFIG: HeartConfig = {
  enabled: false,
  intervalMs: 30 * 60 * 1000, // 30 minutes
  prompt: 'Read HEARTBEAT.md if it exists (workspace context). Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply HEARTBEAT_OK.',
  heartbeatFilePath: 'HEARTBEAT.md',
  target: 'last',
  ackMaxChars: 300,
  includeReasoning: false,
}
