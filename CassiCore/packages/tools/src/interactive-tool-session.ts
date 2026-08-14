/**
 * Interactive Tool Session — State machine for multi-turn Telegram parameter collection.
 *
 * Created when a user invokes /cassi <tool> without all required params.
 */

const ADMIN_BASE = 'http://localhost:7433'
const SESSION_TIMEOUT_MS = 5 * 60 * 1000 // 5 minutes

// WHY: Tools that require explicit /confirm before execution to prevent accidental
// destructive operations
const DANGEROUS_TOOLS = new Set([
  'bash',
  'write',
  'edit',
  'delete',
  'mkdir',
  'memory_delete',
  'memory_kv_del',
  'session_prune',
  'improvement_trigger',
  'system_prompt_update',
  'permissions_respond',
  'config_set',
  'provider_config',
])

export interface ToolDefinition {
  name: string
  description: string
  inputSchema: {
    type: string
    properties?: Record<string, ParamSchema>
    required?: string[]
  }
  category?: string
}

export interface ParamSchema {
  type?: string
  description?: string
  enum?: string[]
  default?: unknown
  items?: unknown
  properties?: Record<string, ParamSchema>
}

type SessionState = 'collecting' | 'confirming' | 'done'

export interface PromptResult { prompt: string }
export interface ExecutionResult { result: string; isError: boolean }

export type SessionResult = PromptResult | ExecutionResult

/**
 * Type guard function that checks if a SessionResult is a PromptResult.
 * 
 * This predicate narrows the type of SessionResult from the union type
 * (PromptResult | ExecutionResult) to specifically PromptResult when true.
 * 
 * @param r - The SessionResult to check
 * @returns true if the result is a PromptResult (has a 'prompt' property), false otherwise
 * @example
 * if (isPrompt(result)) {
 *   // TypeScript now knows result is PromptResult
 *   console.log(result.prompt)
 * } else {
 *   // TypeScript knows result is ExecutionResult
 *   console.log(result.result)
 * }
 */
export function isPrompt(r: SessionResult): r is PromptResult {
  return 'prompt' in r
}

interface QueuedParam {
  name: string
  schema: ParamSchema
  required: boolean
}

export class InteractiveToolSession {
  private readonly toolName: string
  private readonly toolDef: ToolDefinition
  private readonly collectedParams: Record<string, unknown> = {}
  private paramQueue: QueuedParam[] = []
  private currentParam: QueuedParam | null = null
  private state: SessionState = 'collecting'
  private lastActivity = Date.now()

  readonly isDangerous: boolean

  constructor(toolName: string, toolDef: ToolDefinition) {
    this.toolName = toolName
    this.toolDef = toolDef
    this.isDangerous = DANGEROUS_TOOLS.has(toolName)
  }

  get isActive(): boolean {
    return this.state !== 'done' && Date.now() - this.lastActivity < SESSION_TIMEOUT_MS
  }

  get toolNameStr(): string {
    return this.toolName
  }

  async start(inlineParams?: Record<string, unknown>): Promise<SessionResult> {
    this.lastActivity = Date.now()

    const schema = this.toolDef.inputSchema
    const properties = schema.properties ?? {}
    const requiredSet = new Set(schema.required ?? [])

    // Apply inline params
    if (inlineParams) {
      for (const [k, v] of Object.entries(inlineParams)) {
        this.collectedParams[k] = this.coerce(v as string, properties[k] ?? {})
      }
    }

    // Build queue of params not yet collected
    this.paramQueue = Object.entries(properties)
      .filter(([name]) => !(name in this.collectedParams))
      .map(([name, s]) => ({ name, schema: s, required: requiredSet.has(name) })
      )

    // If nothing required is missing, we can execute (or confirm)
    const missingRequired = this.paramQueue.filter(p => p.required)
    if (missingRequired.length === 0) {
      // Skip optional prompts, proceed
      this.paramQueue = []
      this.currentParam = null
      return this.tryFinish()
    }

    // Start collecting — show header + first param
    this.advance()
    return { prompt: this.buildStartPrompt() + '\n\n' + this.buildParamPrompt(this.currentParam!) }
  }

  /** Called when user sends any non-command text reply */
  async receiveInput(text: string): Promise<SessionResult> {
    this.lastActivity = Date.now()
    if (!this.currentParam) return { prompt: 'No active parameter. Use /cancel to abort.' }

    const coerced = this.coerce(text, this.currentParam.schema)
    this.collectedParams[this.currentParam.name] = coerced

    const done = this.advance()
    if (done) return this.tryFinish()
    return { prompt: this.buildParamPrompt(this.currentParam!) }
  }

  /** Called when user sends /skip */
  async skip(): Promise<SessionResult> {
    this.lastActivity = Date.now()
    if (!this.currentParam) return { prompt: 'No active parameter.' }
    if (this.currentParam.required) {
      return { prompt: `Cannot skip required parameter **${this.currentParam.name}**. Please provide a value.` }
    }
    const done = this.advance()
    if (done) return this.tryFinish()
    return { prompt: this.buildParamPrompt(this.currentParam!) }
  }

  /** Called when user sends /confirm */
  async confirm(): Promise<ExecutionResult> {
    this.lastActivity = Date.now()
    if (this.state !== 'confirming') return { result: 'Nothing pending confirmation.', isError: false }
    return this.execute()
  }

  /** Called when user sends /cancel */
  cancel(): string {
    this.state = 'done'
    return `Cancelled **${this.toolName}** invocation.`
  }

  /** Advance to next param. Returns true when queue is exhausted. */
  private advance(): boolean {
    if (this.paramQueue.length === 0) {
      this.currentParam = null
      return true
    }
    this.currentParam = this.paramQueue.shift()!
    return false
  }

  private async tryFinish(): Promise<SessionResult> {
    if (this.isDangerous) {
      this.state = 'confirming'
      return { prompt: this.buildConfirmPrompt() }
    }
    return this.execute()
  }

  private async execute(): Promise<ExecutionResult> {
    this.state = 'done'
    try {
      const res = await fetch(`${ADMIN_BASE}/tools/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool: this.toolName, input: this.collectedParams }),
      })
      if (!res.ok) {
        const txt = await res.text()
        return { result: `Tool execution failed (${res.status}): ${txt}`, isError: true }
      }
      const data = await res.json() as any
      const text = extractText(data)
      return { result: text, isError: data?.isError === true }
    } catch (err) {
      return { result: `Error executing ${this.toolName}: ${String(err)}`, isError: true }
    }
  }

  private coerce(text: string, schema: ParamSchema): unknown {
    const t = schema?.type
    if (t === 'number' || t === 'integer') {
      const n = Number(text)
      return isNaN(n) ? text : n
    }
    if (t === 'boolean') {
      return text === 'true' || text === '1' || text === 'yes' || text === 'y'
    }
    if (t === 'object' || t === 'array') {
      try { return JSON.parse(text) } catch { return text }
    }
    return text
  }

  private buildStartPrompt(): string {
    const props = this.toolDef.inputSchema.properties ?? {}
    const required = new Set(this.toolDef.inputSchema.required ?? [])
    const paramLines = Object.entries(props).map(([name, s]) => {
      const req = required.has(name) ? '(required)' : '(optional)'
      const desc = s.description ? ` — ${s.description}` : ''
      return `  • ${name} ${req}${desc}`
    })
    return [
      `🔧 **${this.toolName}**`,
      this.toolDef.description,
      '',
      paramLines.length ? 'Parameters:\n' + paramLines.join('\n') : 'No parameters required.',
    ].join('\n')
  }

  private buildParamPrompt(param: QueuedParam): string {
    const req = param.required
      ? '(required)'
      : `(optional${param.schema.default !== undefined ? `, default: ${param.schema.default}` : ''})`
    const enumHint = param.schema.enum ? `\nOptions: ${param.schema.enum.join(', ')}` : ''
    const skipHint = param.required ? '' : '\nOr /skip to use default'
    return `Reply with value for **${param.name}** ${req}${enumHint}${skipHint}`
  }

  private buildConfirmPrompt(): string {
    const params = Object.entries(this.collectedParams)
      .map(([k, v]) => `  ${k}: ${JSON.stringify(v)}`)
      .join('\n')
    return [
      `⚠️ **${this.toolName}** is a potentially destructive operation.`,
      '',
      params ? `Parameters:\n${params}` : 'No parameters.',
      '',
      'Type /confirm to execute or /cancel to abort.',
    ].join('\n')
  }
}

/**
 * Extracts text content from MCP-style tool response objects.
 * 
 * Handles multiple response formats:
 * - Plain string responses
 * - Objects with a 'content' array containing text blocks
 * - Objects with a 'text' property
 * - Any other data (converted to JSON string)
 * 
 * @param data - The tool response data to extract text from
 * @returns Extracted text content as a string, or JSON representation if no text found
 * @example
 * // String response
 * extractText("Hello world") // "Hello world"
 * 
 * // Content array with text blocks
 * extractText({ content: [{ type: "text", text: "First" }, { type: "text", text: "Second" }] })
 * // "First\nSecond"
 * 
 * // Object with text property
 * extractText({ text: "Result" }) // "Result"
 */
export function extractText(data: unknown): string {
  if (typeof data === 'string') return data
  if (Array.isArray((data as any)?.content)) {
    return (data as any).content
      .filter((c: any) => c?.type === 'text')
      .map((c: any) => c.text as string)
      .join('\n')
  }
  if (typeof (data as any)?.text === 'string') return (data as any).text
  return JSON.stringify(data, null, 2)
}

/**
 * Splits long text into chunks suitable for Telegram's message size limit.
 * 
 * Telegram has a 4096 character limit per message. This function:
 * - Splits text into chunks of specified maximum length
 * - Prefixes each chunk with its position (e.g., "[1/3]", "[2/3]")
 * - Uses a default max length of 3800 to leave room for the prefix
 * 
 * @param text - The text to split into chunks
 * @param maxLen - Maximum length per chunk (default: 3800)
 * @returns Array of chunked strings with position prefixes
 * @example
 * const longText = "a".repeat(10000)
 * const chunks = splitForTelegram(longText)
 * // Returns: ["[1/3]\naaa...", "[2/3]\naaa...", "[3/3]\naaa..."]
 */
export function splitForTelegram(text: string, maxLen = 3800): string[] {
  if (text.length <= maxLen) return [text]
  const chunks: string[] = []
  for (let i = 0; i < text.length; i += maxLen) {
    chunks.push(text.slice(i, i + maxLen))
  }
  return chunks.map((c, i) => `[${i + 1}/${chunks.length}]\n${c}`)
}
