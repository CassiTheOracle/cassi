import { describe, it, expect, vi, beforeEach } from 'vitest'

import { GitHubCopilotLoadBalancer, type GitHubCopilotAccount } from '../src/github-copilot-loadbalancer.js'
import { GitHubCopilotProvider } from '../src/github-copilot.js'

// Mock provider to avoid network
class MockProvider extends GitHubCopilotProvider {
  private responses: Array<any>
  constructor(token: string, profileId?: string, responses: Array<any> = []) {
    super(token, profileId)
    this.responses = responses
  }

  async *complete(messages: any[], opts: any, attachments?: any[], signal?: AbortSignal) {
    for (const r of this.responses) {
      if (r.type === 'token') yield r
      else if (r.type === 'error') yield { type: 'error', error: r.error }
      else if (r.type === 'done') yield { type: 'done', tokensUsed: 1, model: 'gpt' }
    }
  }

  async ping() { return true }
}

// Replace GitHubCopilotProvider construction inside LB by monkeypatching
vi.stubGlobal('GitHubCopilotProvider', GitHubCopilotProvider)

describe('GitHubCopilotLoadBalancer', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('round-robin distributes and fails over on 502', async () => {
    const accounts: GitHubCopilotAccount[] = [
      { profileId: 'a', oauthToken: 't1' },
      { profileId: 'b', oauthToken: 't2' },
    ]

    const lb = new GitHubCopilotLoadBalancer({ accounts, strategy: 'round-robin', maxRetries: 2 })

    // Inject mock providers: first will 502, second will succeed
    // @ts-ignore
    lb['providers'] = [new MockProvider('t1', 'a', [{ type: 'error', error: 'http 502: bad gateway' }]), new MockProvider('t2', 'b', [{ type: 'token', text: 'hi' }, { type: 'done' }])]

    const chunks: any[] = []
    for await (const c of lb.complete([], { model: 'gpt' })) {
      chunks.push(c)
    }

    expect(chunks.some(c => c.type === 'token' && c.text === 'hi')).toBe(true)
    // stats: first should have an error, second should have a success
    const stats = lb.getStats()
    expect(stats.find(s => s.profileId === 'a')!.errors).toBe(1)
    expect(stats.find(s => s.profileId === 'b')!.requests).toBe(1)
  })

  it('sets cooldown on 429', async () => {
    const accounts: GitHubCopilotAccount[] = [
      { profileId: 'a', oauthToken: 't1' },
      { profileId: 'b', oauthToken: 't2' },
    ]
    const lb = new GitHubCopilotLoadBalancer({ accounts, strategy: 'round-robin', cooldownMs: 1000, maxRetries: 2 })
    // @ts-ignore
    lb['providers'] = [new MockProvider('t1', 'a', [{ type: 'error', error: 'http 429: rate limit' }]), new MockProvider('t2', 'b', [{ type: 'token', text: 'ok' }, { type: 'done' }])]

    const chunks: any[] = []
    for await (const c of lb.complete([], { model: 'gpt' })) chunks.push(c)

    const stats = lb.getStats()
    expect(stats.find(s => s.profileId === 'a')!.onCooldown).toBe(true)
    expect(stats.find(s => s.profileId === 'b')!.requests).toBe(1)
  })
})
