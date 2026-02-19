import { BaseProvider } from './base.js'
import type { Message, CompletionOpts, CompletionChunk } from '../../types/runtime.js'

export class GitHubCopilotProvider extends BaseProvider {
  readonly id = 'github-copilot'
  readonly models = ['claude-sonnet-4-5', 'claude-sonnet-4-6', 'gpt-5-mini', 'claude-opus-4-6']

  constructor(private token: string) { super() }

  async *complete(messages: Message[], opts: CompletionOpts): AsyncIterable<CompletionChunk> {
    const url = 'https://api.githubcopilot.com/chat/completions'
    const body: Record<string, unknown> = {
      model: opts.model || this.models[0],
      messages: messages.map(m => ({ role: m.role, content: m.content, name: m.name })),
      stream: true,
      max_tokens: opts.maxTokens ?? 8192,
      temperature: opts.temperature ?? 0.2,
    }

    let res: Response
    try {
      res = await fetch(url, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${this.token}`,
          'Copilot-Integration-Id': 'vscode-chat',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      yield { type: 'error', error: `network error: ${message}` }
      return
    }

    if (!res.ok) {
      const text = await res.text().catch(() => '')
      yield { type: 'error', error: `http ${res.status}: ${text}` }
      return
    }

    const reader = res.body?.getReader()
    if (!reader) {
      yield { type: 'error', error: 'no response body' }
      return
    }

    const decoder = new TextDecoder()
    let buf = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        let idx: number
        while ((idx = buf.indexOf('\n')) !== -1) {
          const line = buf.slice(0, idx).trim()
          buf = buf.slice(idx + 1)
          if (!line) continue
          if (line.startsWith('data:')) {
            const payload = line.slice(5).trim()
            if (payload === '[DONE]') {
              yield { type: 'done' }
              return
            }
            let obj: unknown
            try {
              obj = JSON.parse(payload)
            } catch {
              continue
            }
            // OpenAI-style: choices[0].delta.content
            const choices = (obj as any).choices as any[] | undefined
            const content = choices?.[0]?.delta?.content as string | undefined
            if (typeof content === 'string') {
              yield { type: 'token', text: content }
            }
          }
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      yield { type: 'error', error: `stream error: ${message}` }
      return
    }

    yield { type: 'done' }
  }

  async countTokens(messages: Message[]): Promise<number> {
    return this.estimateTokens(messages)
  }

  async ping(): Promise<boolean> {
    try {
      const res = await fetch('https://api.githubcopilot.com/models', {
        headers: { Authorization: `Bearer ${this.token}` },
      })
      return res.ok
    } catch {
      return false
    }
  }
}
