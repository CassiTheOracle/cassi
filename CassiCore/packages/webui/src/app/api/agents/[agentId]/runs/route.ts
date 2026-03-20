import { NextRequest } from 'next/server'
import { cassiFetch } from '@/lib/cassicore/client'
import { registerSession, updateSession } from '@/lib/cassicore/webui-sessions'
import { randomUUID } from 'crypto'

/**
 * POST /api/agents/[agentId]/runs
 *
 * Implements the Agno streaming run contract for agent-ui.
 * Accepts FormData with { message, stream, session_id }, translates the
 * request to CassiCore's SSE turn stream, and re-emits the events as
 * newline-delimited JSON in Agno's RunEvent format.
 *
 * CassiCore SSE → Agno RunEvent translation:
 *   token       → RunContent (cumulative content)
 *   tool_call   → ToolCallStarted
 *   tool_result → ToolCallCompleted
 *   dialectic   → ReasoningStep (Yang/Yin/Synthesis → title/action/result)
 *   done        → RunCompleted
 *   error       → RunError
 * @dep calls: get, registerSession, cassiFetch, now, errorStream
 * @dep flows: POST → GetRegistry (1/3), POST → Now (1/3)
 * @dep module: Providers
 * @dep risk: LOW | 0 callers, 2 flows, 1 module
 */
export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ agentId: string }> }
) {
  await params // agentId is always 'cassi' — ignored

  const form = await req.formData()
  const message = (form.get('message') as string | null) ?? ''
  const incomingSessionId = (form.get('session_id') as string | null) ?? ''
  const model = (form.get('model') as string | null) ?? undefined
  const thinking = (form.get('thinking') as string | null) ?? undefined

  const sessionId = incomingSessionId || `webui-${randomUUID()}`
  const nowMs = Date.now()
  const now = () => Math.floor(nowMs / 1000)

  // Track session so it appears in sidebar even if daemon doesn't persist sessions
  registerSession({
    id: sessionId,
    firstMessage: message.slice(0, 120),
    createdAt: nowMs,
    lastActiveAt: nowMs,
    messageCount: 1,
  })

  const turnBody: Record<string, unknown> = {
    content: message,
    senderId: 'webui-user',
    channelId: 'channel:webui',
  }
  if (model) turnBody.model = model
  if (thinking) turnBody.thinking = thinking

  let cassiRes: Response
  try {
    cassiRes = await cassiFetch(`/sessions/${sessionId}/turn/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(turnBody),
    })
  } catch (err) {
    return errorStream(`CassiCore unreachable: ${String(err)}`)
  }

  if (!cassiRes.body) {
    return errorStream('CassiCore returned no response body')
  }

  const encoder = new TextEncoder()

  const stream = new ReadableStream({
    async start(controller) {
      const emit = (obj: Record<string, unknown>) => {
        controller.enqueue(encoder.encode(JSON.stringify(obj) + '\n'))
      }

      // Signal stream start
      emit({ event: 'RunStarted', session_id: sessionId, created_at: now() })

      const reader = cassiRes.body!.getReader()
      const decoder = new TextDecoder()
      let buf = ''
              let accumulated = ''
              let thinkingAccumulated = ''
      const toolCallMap: Record<string, { tool_name: string; tool_args: Record<string, unknown> }> = {}

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buf += decoder.decode(value, { stream: true })

          // Parse SSE lines
          const lines = buf.split('\n')
          buf = lines.pop() ?? '' // keep last (potentially incomplete) line

          let eventType = ''
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim()
            } else if (line.startsWith('data: ')) {
              const raw = line.slice(6).trim()
              let payload: Record<string, unknown> = {}
              try {
                payload = JSON.parse(raw)
              } catch {
                continue
              }

              switch (eventType) {
                case 'token': {
                  const token = (payload.token as string) ?? ''
                  accumulated += token
                  emit({
                    event: 'RunContent',
                    content: accumulated,
                    session_id: sessionId,
                    created_at: now(),
                  })
                  break
                }

                case 'thinking': {
                  const thinkToken = (payload.token as string) ?? ''
                  thinkingAccumulated += thinkToken
                  // Emit accumulated thinking as a reasoning step that updates in place
                  emit({
                    event: 'ReasoningStep',
                    session_id: sessionId,
                    created_at: now(),
                    extra_data: {
                      reasoning_steps: [
                        {
                          title: 'Thinking',
                          action: 'think',
                          result: thinkingAccumulated,
                          reasoning: thinkingAccumulated,
                        },
                      ],
                    },
                  })
                  break
                }

                case 'tool_call': {
                  const toolCallId = (payload.toolCallId as string) ?? randomUUID()
                  const toolName = (payload.tool as string) ?? 'unknown'
                  const toolArgs = (payload.input as Record<string, unknown>) ?? {}
                  toolCallMap[toolCallId] = { tool_name: toolName, tool_args: toolArgs }
                  emit({
                    event: 'ToolCallStarted',
                    session_id: sessionId,
                    created_at: now(),
                    tool_call_id: toolCallId,
                    tool: {
                      role: 'tool',
                      tool_call_id: toolCallId,
                      tool_name: toolName,
                      tool_args: toolArgs,
                      tool_call_error: false,
                      content: null,
                      metrics: { time: 0 },
                      created_at: now(),
                    },
                  })
                  break
                }

                case 'tool_result': {
                  const tcId = (payload.toolCallId as string) ?? ''
                  const stored = toolCallMap[tcId] ?? { tool_name: 'unknown', tool_args: {} }
                  const isError = !!(payload.isError)
                  const resultContent = (payload.content as string) ?? (isError ? 'error' : 'ok')
                  emit({
                    event: 'ToolCallCompleted',
                    session_id: sessionId,
                    created_at: now(),
                    tool_call_id: tcId,
                    tool: {
                      role: 'tool',
                      tool_call_id: tcId,
                      tool_name: stored.tool_name,
                      tool_args: stored.tool_args,
                      tool_call_error: isError,
                      content: resultContent,
                      metrics: { time: 0 },
                      created_at: now(),
                    },
                  })
                  break
                }

                case 'dialectic': {
                  // Map CassiCore's Yang/Yin/Synthesis to Agno ReasoningStep
                  const stage = (payload.stage as string) ?? ''
                  const label = (payload.label as string) ?? (stage || 'Dialectic')
                  const content = (payload.content as string) ?? JSON.stringify(payload)
                  emit({
                    event: 'ReasoningStep',
                    session_id: sessionId,
                    created_at: now(),
                    extra_data: {
                      reasoning_steps: [
                        {
                          title: label,
                          action: stage,
                          result: content,
                          reasoning: content,
                        },
                      ],
                    },
                  })
                  break
                }

                case 'done': {
                  // CassiCore may send the full response in the done event
                  const finalContent =
                    (payload.content as string) ??
                    (payload.response as string) ??
                    accumulated

                  // Emit tool calls from pipeline result (tool events don't stream individually)
                  const toolOutputs = payload.tool_outputs as Array<{
                    tool_name: string; tool_call_id: string;
                    output: string; is_error: boolean;
                  }> | undefined
                  const toolCallsInfo = payload.toolCalls as Array<{
                    name: string; durationMs: number;
                  }> | undefined

                  if (toolOutputs?.length) {
                    for (const to of toolOutputs) {
                      const tcId = to.tool_call_id ?? randomUUID()
                      // Emit started
                      emit({
                        event: 'ToolCallStarted',
                        session_id: sessionId,
                        created_at: now(),
                        tool_call_id: tcId,
                        tool: {
                          role: 'tool',
                          tool_call_id: tcId,
                          tool_name: to.tool_name,
                          tool_args: {},
                          tool_call_error: false,
                          content: null,
                          metrics: { time: 0 },
                          created_at: now(),
                        },
                      })
                      // Emit completed
                      const durationMs = toolCallsInfo?.find(t => t.name === to.tool_name)?.durationMs ?? 0
                      emit({
                        event: 'ToolCallCompleted',
                        session_id: sessionId,
                        created_at: now(),
                        tool_call_id: tcId,
                        tool: {
                          role: 'tool',
                          tool_call_id: tcId,
                          tool_name: to.tool_name,
                          tool_args: {},
                          tool_call_error: to.is_error,
                          content: to.output?.slice(0, 500) ?? (to.is_error ? 'error' : 'ok'),
                          metrics: { time: durationMs },
                          created_at: now(),
                        },
                      })
                    }
                  }

                  if (!accumulated && finalContent) {
                    emit({
                      event: 'RunContent',
                      content: finalContent,
                      session_id: sessionId,
                      created_at: now(),
                    })
                  }
                  // Update session last-active time
                  updateSession(sessionId, { lastActiveAt: Date.now() })
                  emit({
                    event: 'RunCompleted',
                    content: finalContent,
                    session_id: sessionId,
                    created_at: now(),
                    metrics: {
                      time: (payload.durationMs as number) ?? 0,
                      prompt_tokens: (payload.inputTokens as number) ?? 0,
                      completion_tokens: (payload.outputTokens as number) ?? 0,
                    },
                  })
                  break
                }

                case 'error': {
                  emit({
                    event: 'RunError',
                    session_id: sessionId,
                    created_at: now(),
                    content: String(payload.error ?? payload),
                  })
                  break
                }

                default:
                  break
              }

              eventType = '' // reset after data line
            }
          }
        }
      } catch (err) {
        emit({
          event: 'RunError',
          session_id: sessionId,
          created_at: now(),
          content: `Stream error: ${String(err)}`,
        })
      } finally {
        controller.close()
      }
    },
  })

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Transfer-Encoding': 'chunked',
      'X-Content-Type-Options': 'nosniff',
      'Cache-Control': 'no-cache',
    },
  })
}

/** Helper: emit a RunError response and close the stream immediately. */
/**
 * @dep callers: POST (webui/src/app/api/agents/[agentId]/runs/route.ts)
 * @dep calls: now
 * @dep flows: POST → Now (2/3)
 * @dep module: Providers
 * @dep risk: LOW | 1 caller, 1 flow, 1 module
 */

function errorStream(message: string) {
  const body = JSON.stringify({
    event: 'RunError',
    content: message,
    created_at: Math.floor(Date.now() / 1000),
  })
  return new Response(body + '\n', {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    status: 200,
  })
}
