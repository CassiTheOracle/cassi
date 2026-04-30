import type { SignalType } from './types.js'
import type { CortexSession } from './session.js'
import type { BrainstemContextSources } from '../helix/brainstem-types.js'

type PostChannel = 'findings' | 'concerns' | 'bugs'
type ReadChannel = 'findings' | 'concerns' | 'decisions' | 'artifacts' | 'requests' | 'bugs'

interface ChannelMapping {
  region: string
  type: SignalType
}

const CHANNEL_MAP: Record<string, ChannelMapping> = {
  findings:  { region: 'sensory',   type: 'perception' },
  concerns:  { region: 'limbic',    type: 'concern' },
  decisions: { region: 'executive', type: 'decision' },
  requests:  { region: 'executive', type: 'request' },
  bugs:      { region: 'limbic',    type: 'anomaly' },
  artifacts: { region: 'motor',     type: 'action' },
}

function priorityToSalience(priority?: number): number {
  if (priority === undefined || priority === 0) return 0.5
  if (priority === 1) return 0.8
  if (priority >= 2) return 0.95
  return 0.3
}

function salienceToPriority(salience: number): number {
  if (salience >= 0.9) return 2
  if (salience >= 0.7) return 1
  return 0
}

/**
 * REMOVED: CortexSessionBlackboardAdapter — Blackboard deprecated.
 *
 * Replacement: CortexContextSourcesAdapter implements BrainstemContextSources.
 * Adapts a CortexSession into the new context sources interface:
 *   - globalWorkspace: broadcasts cortex signals
 *   - cortex: reads active signals from regions
 */
export class CortexContextSourcesAdapter implements BrainstemContextSources {
  constructor(private session: CortexSession) {}

  get globalWorkspace() {
    return {
      broadcast: (signal: { type: string; content: string; author: string; salience: number }) => {
        const mapping = CHANNEL_MAP[signal.type as string]
        if (!mapping) return
        this.session.signal(mapping.region, {
          type: mapping.type,
          content: signal.content,
          author: signal.author,
          salience: signal.salience,
          tags: [],
        })
      },
      getRecentSignals: (limit = 10) => {
        return this.session.read('sensory', { limit })
          .map(s => ({
            type: s.type,
            content: s.content,
            author: s.author,
            timestamp: s.createdAt,
          }))
      },
    }
  }

  get cortex() {
    return {
      getActiveSignals: (region?: string) => {
        return this.session.read(region ?? 'association', { limit: 10 })
          .map(s => ({
            type: s.type,
            content: s.content,
            salience: s.salience,
          }))
      },
    }
  }

  // Lamina not supported via cortex adapter
  get lamina() { return undefined }
}

export { CHANNEL_MAP, priorityToSalience, salienceToPriority }