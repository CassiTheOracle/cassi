import type { SignalType } from './types.js'
import type { CortexSession } from './session.js'
import type { BrainstemBlackboard } from '../helix/brainstem-types.js'

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

export class CortexSessionBlackboardAdapter implements BrainstemBlackboard {
  constructor(private session: CortexSession) {}

  post(
    channel: PostChannel,
    entry: {
      author: string
      content: string
      structured?: Record<string, unknown>
      priority?: number
      tags?: string[]
    },
  ): unknown {
    const mapping = CHANNEL_MAP[channel]
    if (!mapping) return null

    return this.session.signal(mapping.region, {
      type: mapping.type,
      content: entry.content,
      author: entry.author,
      salience: priorityToSalience(entry.priority),
      tags: entry.tags ?? [],
      structured: entry.structured,
    })
  }

  read(
    channel: ReadChannel,
    limit?: number,
  ): Array<{ id: string; channel: string; content: string; author: string; priority: number; tags: string[]; timestamp: number }> {
    const mapping = CHANNEL_MAP[channel]
    if (!mapping) return []

    return this.session.read(mapping.region, { types: [mapping.type], limit })
      .map(signal => ({
        id: signal.id,
        channel,
        content: signal.content,
        author: signal.author,
        priority: salienceToPriority(signal.salience),
        tags: signal.tags,
        timestamp: signal.createdAt,
      }))
  }

  getPlan() { return null }
  getReport() { return null }
}

export { CHANNEL_MAP, priorityToSalience, salienceToPriority }
