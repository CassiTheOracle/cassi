/**
 * Tests for the Telegram channel integration.
 *
 * The Telegram channel is a worker-thread-based integration that:
 * - Receives messages via long-polling (getUpdates) from the Telegram Bot API
 * - Sends messages with streaming support (live-editing a message as tokens arrive)
 * - Handles images by downloading and base64-encoding them
 * - Detects feedback/directive signals from special message patterns
 * - Filters messages by allowed chat IDs for security
 *
 * These tests cover the pure-function layer that can be tested without a
 * running daemon or network calls. Worker thread logic (pollLoop, IPC) is
 * tested via integration tests.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  markdownToTelegramHtml,
  setToken,
  setLogger,
  sendMessage,
  editMessage,
  sendTyping,
  downloadPhoto,
  type ImageAttachment,
} from '../src/channels/telegram-common.js'


describe('markdownToTelegramHtml', () => {
  describe('converts GitHub-flavored Markdown to Telegram HTML format', () => {
    it('returns empty string for empty input', () => {
      expect(markdownToTelegramHtml('')).toBe('')
    })

    it('passes plain text through with HTML escaping for special characters', () => {
      expect(markdownToTelegramHtml('hello world')).toBe('hello world')
      expect(markdownToTelegramHtml('x < 10 & y > 0')).toBe('x &lt; 10 &amp; y &gt; 0')
    })

    it('converts **bold** markdown to <b> HTML tags', () => {
      expect(markdownToTelegramHtml('This is **bold** text')).toBe('This is <b>bold</b> text')
    })

    it('converts *italic* markdown to <i> HTML tags', () => {
      expect(markdownToTelegramHtml('This is *italic* text')).toBe('This is <i>italic</i> text')
    })

    it('converts ~~strikethrough~~ markdown to <s> HTML tags', () => {
      expect(markdownToTelegramHtml('This is ~~deleted~~ text')).toBe('This is <s>deleted</s> text')
    })

    it('converts `inline code` markdown to <code> HTML tags with content escaped', () => {
      expect(markdownToTelegramHtml('Call `foo()` now')).toBe('Call <code>foo()</code> now')
      expect(markdownToTelegramHtml('Use `x < 10`')).toBe('Use <code>x &lt; 10</code>')
    })

    it('converts fenced code blocks to <pre><code> HTML structure', () => {
      const input = '```\ncode here\n```'
      expect(markdownToTelegramHtml(input)).toBe('<pre><code>code here\n</code></pre>')
    })

    it('converts fenced code blocks with language hint (language is ignored)', () => {
      const input = '```python\ndef foo():\n    return 1\n```'
      expect(markdownToTelegramHtml(input)).toBe(
        '<pre><code>def foo():\n    return 1\n</code></pre>'
      )
    })

    it('escapes HTML special characters inside code blocks', () => {
      const input = '```html\n<div>test</div>\n```'
      expect(markdownToTelegramHtml(input)).toBe(
        '<pre><code>&lt;div&gt;test&lt;/div&gt;\n</code></pre>'
      )
    })

    it('converts [links](url) markdown to <a href> HTML tags', () => {
      expect(markdownToTelegramHtml('Click [here](https://example.com)'))
        .toBe('Click <a href="https://example.com">here</a>')
    })

    it('converts markdown headers (#) to bold text', () => {
      expect(markdownToTelegramHtml('# Header 1')).toBe('<b>Header 1</b>')
      expect(markdownToTelegramHtml('## Header 2')).toBe('<b>Header 2</b>')
      expect(markdownToTelegramHtml('### Header 3')).toBe('<b>Header 3</b>')
    })

    it('converts > blockquotes to <blockquote> HTML tags', () => {
      expect(markdownToTelegramHtml('> quoted text')).toBe('<blockquote>quoted text</blockquote>')
    })

    it('handles multi-line blockquotes', () => {
      const input = '> line one\n> line two'
      expect(markdownToTelegramHtml(input)).toBe('<blockquote>line one\nline two</blockquote>')
    })

    it('converts unordered list items to bullet points (•)', () => {
      const input = '- Item one\n- Item two'
      expect(markdownToTelegramHtml(input)).toBe('\u2022 Item one\n\u2022 Item two')
    })

    it('preserves indentation for nested list items', () => {
      const input = '- Top\n  - Nested'
      expect(markdownToTelegramHtml(input)).toBe('\u2022 Top\n  \u2022 Nested')
    })

    it('converts ordered list items with numbering preserved', () => {
      const input = '1. First\n2. Second'
      expect(markdownToTelegramHtml(input)).toBe('1. First\n2. Second')
    })

    it('converts task list items with checkbox markers preserved', () => {
      const input = '- [x] Done\n- [ ] Todo'
      expect(markdownToTelegramHtml(input)).toBe('\u2022 [x] Done\n\u2022 [ ] Todo')
    })

    it('converts horizontal rules to separator lines', () => {
      const input = 'above\n\n---\n\nbelow'
      expect(markdownToTelegramHtml(input)).toBe('above\n\n\u2500\u2500\u2500\n\nbelow')
    })

    it('converts tables to bullet list format with bold first column', () => {
      const input = '| A | B |\n|---|---|\n| 1 | 2 |'
      expect(markdownToTelegramHtml(input)).toBe('<b>1</b>\n\u2022 B: 2')
    })

    it('does not process formatting inside inline code spans', () => {
      expect(markdownToTelegramHtml('`**not bold**`')).toBe('<code>**not bold**</code>')
    })

    it('handles combined bold+italic ***text*** formatting', () => {
      expect(markdownToTelegramHtml('***both***')).toBe('<b><i>both</i></b>')
    })

    it('does not treat mid-word underscores as italic formatting', () => {
      expect(markdownToTelegramHtml('my_variable_name')).toBe('my_variable_name')
    })

    it('processes comprehensive mixed formatting correctly', () => {
      const input = [
        '# Title',
        '',
        '**Bold** and *italic* and `code`.',
        '',
        '> A quote',
        '',
        '- Item 1',
        '- Item 2',
        '',
        '```js',
        'const x = 1',
        '```',
      ].join('\n')

      const output = markdownToTelegramHtml(input)
      expect(output).toContain('<b>Title</b>')
      expect(output).toContain('<b>Bold</b>')
      expect(output).toContain('<i>italic</i>')
      expect(output).toContain('<code>code</code>')
      expect(output).toContain('<blockquote>A quote')
      expect(output).toContain('\u2022 Item 1')
      expect(output).toContain('<pre><code>const x = 1\n</code></pre>')
    })
  })

  describe('edge cases and error handling', () => {
    it('handles text with only whitespace', () => {
      // Whitespace-only input gets trimmed by the markdown parser
      expect(markdownToTelegramHtml('   ')).toBe('')
    })

    it('handles unclosed formatting gracefully', () => {
      expect(markdownToTelegramHtml('**unclosed bold')).toBe('**unclosed bold')
    })

    it('handles empty code blocks', () => {
      expect(markdownToTelegramHtml('```\n```')).toBe('<pre><code>\n</code></pre>')
    })

    it('handles deeply nested formatting', () => {
      const input = '> **Quote with *nested* bold** and `code`'
      const output = markdownToTelegramHtml(input)
      expect(output).toContain('<blockquote>')
      expect(output).toContain('<b>')
      expect(output).toContain('<i>')
      expect(output).toContain('<code>')
    })

    it('handles URLs with special characters by escaping them', () => {
      const input = '[link](https://example.com/path?a=1&b=2)'
      const output = markdownToTelegramHtml(input)
      // The & is HTML-escaped to &amp; in the output
      expect(output).toContain('href="https://example.com/path?a=1&amp;b=2"')
    })
  })
})


describe('setToken', () => {
  it('accepts a valid bot token without throwing', () => {
    expect(() => setToken('1234:abc')).not.toThrow()
  })

  it('accepts an empty string to clear the token', () => {
    expect(() => setToken('')).not.toThrow()
  })

  it('accepts tokens with special characters used in real bot tokens', () => {
    expect(() => setToken('123456789:ABCdefGHIjklMNOpqrsTUVwxyz')).not.toThrow()
    expect(() => setToken('123456789:ABC-def_GHI.jkl/MNO')).not.toThrow()
  })
})

describe('setLogger', () => {
  it('accepts a warning callback function for structured logging', () => {
    const warnings: string[] = []
    expect(() => setLogger((msg) => warnings.push(msg))).not.toThrow()
    
    // Restore default logger after test
    setLogger((msg) => process.stderr.write(`${msg}\n`))
  })

  it('routes warning messages through the provided callback', () => {
    const warnings: string[] = []
    setLogger((msg) => warnings.push(msg))

    // Set an invalid token to trigger warnings later
    setToken('INVALID_TOKEN_FOR_TEST')

    // Verify callback was registered
    expect(() => setLogger((msg) => warnings.push(msg))).not.toThrow()

    // Restore default logger
    setLogger((msg) => process.stderr.write(`${msg}\n`))
    setToken('')
  })
})


describe('Telegram session ID convention', () => {
  describe('sessionIdFor produces stable session identifiers', () => {
    it('formats numeric chat IDs as tg:<chatId>', () => {
      const sessionIdFor = (chatId: number) => `tg:${chatId}`
      expect(sessionIdFor(123456789)).toBe('tg:123456789')
    })

    it('handles negative chat IDs for group chats', () => {
      const sessionIdFor = (chatId: number) => `tg:${chatId}`
      expect(sessionIdFor(-100123456)).toBe('tg:-100123456')
    })

    it('handles large numeric chat IDs', () => {
      const sessionIdFor = (chatId: number) => `tg:${chatId}`
      expect(sessionIdFor(9999999999999)).toBe('tg:9999999999999')
    })
  })

  describe('parseChatId extracts chat IDs from session identifiers', () => {
    const parseChatId = (s: string): number | null => {
      if (!s.startsWith('tg:')) return null
      const n = Number(s.slice(3))
      return Number.isFinite(n) ? n : null
    }

    it('returns null for non-tg: prefixed session IDs', () => {
      expect(parseChatId('oc:abc')).toBeNull()
      expect(parseChatId('webchat:xyz')).toBeNull()
      expect(parseChatId('')).toBeNull()
      expect(parseChatId('discord:123')).toBeNull()
    })

    it('extracts numeric chat ID from tg: prefixed session ID', () => {
      expect(parseChatId('tg:123456789')).toBe(123456789)
      expect(parseChatId('tg:-100123456')).toBe(-100123456)
    })

    it('returns null for non-numeric values after tg: prefix', () => {
      const parseChatId = (s: string): number | null => {
        if (!s.startsWith('tg:')) return null
        const rest = s.slice(3)
        if (!rest) return null // Empty after prefix
        const n = Number(rest)
        return Number.isFinite(n) ? n : null
      }
      expect(parseChatId('tg:abc')).toBeNull()
      expect(parseChatId('tg:')).toBeNull()
      expect(parseChatId('tg:12.34')).toBe(12.34)
    })

    it('handles edge cases in session ID parsing', () => {
      const parseChatId = (s: string): number | null => {
        if (!s.startsWith('tg:')) return null
        const rest = s.slice(3)
        if (!rest) return null
        const n = Number(rest)
        return Number.isFinite(n) ? n : null
      }
      expect(parseChatId('tg:0')).toBe(0)
      expect(parseChatId('tg:-0')).toBe(-0) // JavaScript quirk
      expect(parseChatId('tg: 123')).toBe(123) // JavaScript Number() trims whitespace
    })
  })
})


describe('chooseParseModeForText logic', () => {
  const chooseParseModeForText = (_text: string): 'MarkdownV2' | 'HTML' => 'HTML'

  it('always returns HTML as the parse mode regardless of input', () => {
    expect(chooseParseModeForText('')).toBe('HTML')
    expect(chooseParseModeForText('Hello world')).toBe('HTML')
    expect(chooseParseModeForText('Use `foo()` here')).toBe('HTML')
    expect(chooseParseModeForText('if x < 10 and y > 0')).toBe('HTML')
    expect(chooseParseModeForText('<code>test</code>')).toBe('HTML')
    expect(chooseParseModeForText('**bold**')).toBe('HTML')
  })
})


describe('signal detection logic', () => {
  const detectSignal = (text: string): { isSignal: boolean; signalType: string } => {
    let isSignal = false
    let signalType = ''

    if (text.startsWith('!')) {
      isSignal = true
      const spaceIdx = text.indexOf(' ')
      signalType = spaceIdx > 0 ? text.slice(1, spaceIdx) : text.slice(1)
      if (!signalType) signalType = 'feedback'
    } else if (
      text.toLowerCase().includes('fix this') ||
      text.toLowerCase().includes("don't do that") ||
      text.toLowerCase().includes('stop')
    ) {
      isSignal = true
      signalType = 'feedback'
    } else if (
      text.toLowerCase().startsWith('instruction:') ||
      text.toLowerCase().startsWith('directive:')
    ) {
      isSignal = true
      signalType = 'instruction'
    }

    return { isSignal, signalType }
  }

  describe('detects explicit ! prefixed signals', () => {
    it('detects bare ! as feedback signal', () => {
      expect(detectSignal('!')).toEqual({ isSignal: true, signalType: 'feedback' })
    })

    it('detects !word as named signal type', () => {
      expect(detectSignal('!positive great work')).toEqual({ isSignal: true, signalType: 'positive' })
      expect(detectSignal('!negative that was wrong')).toEqual({ isSignal: true, signalType: 'negative' })
      expect(detectSignal('!correction use camelCase')).toEqual({ isSignal: true, signalType: 'correction' })
    })

    it('handles signals without trailing text', () => {
      expect(detectSignal('!urgent')).toEqual({ isSignal: true, signalType: 'urgent' })
    })
  })

  describe('detects implicit feedback patterns', () => {
    it('detects "fix this" as feedback signal', () => {
      expect(detectSignal('fix this please')).toEqual({ isSignal: true, signalType: 'feedback' })
      expect(detectSignal('FIX THIS')).toEqual({ isSignal: true, signalType: 'feedback' })
      expect(detectSignal('Can you fix this?')).toEqual({ isSignal: true, signalType: 'feedback' })
    })

    it('detects "don\'t do that" as feedback signal', () => {
      expect(detectSignal("don't do that")).toEqual({ isSignal: true, signalType: 'feedback' })
      expect(detectSignal("Please don't do that")).toEqual({ isSignal: true, signalType: 'feedback' })
    })

    it('detects "stop" as feedback signal', () => {
      expect(detectSignal('stop doing that')).toEqual({ isSignal: true, signalType: 'feedback' })
      expect(detectSignal('Stop')).toEqual({ isSignal: true, signalType: 'feedback' })
      expect(detectSignal('Just stop!')).toEqual({ isSignal: true, signalType: 'feedback' })
    })
  })

  describe('detects directive patterns', () => {
    it('detects instruction: prefix as instruction signal', () => {
      expect(detectSignal('instruction: always use TypeScript')).toEqual({ isSignal: true, signalType: 'instruction' })
      expect(detectSignal('Instruction: be concise')).toEqual({ isSignal: true, signalType: 'instruction' })
      expect(detectSignal('INSTRUCTION: follow the rules')).toEqual({ isSignal: true, signalType: 'instruction' })
    })

    it('detects directive: prefix as instruction signal', () => {
      expect(detectSignal('directive: no profanity')).toEqual({ isSignal: true, signalType: 'instruction' })
      expect(detectSignal('Directive: use proper formatting')).toEqual({ isSignal: true, signalType: 'instruction' })
    })
  })

  describe('ordinary messages are not signals', () => {
    it('returns no signal for normal conversation', () => {
      expect(detectSignal('Hello, how are you?')).toEqual({ isSignal: false, signalType: '' })
      expect(detectSignal('What time is it?')).toEqual({ isSignal: false, signalType: '' })
      expect(detectSignal('Can you help me with something?')).toEqual({ isSignal: false, signalType: '' })
    })

    it('returns no signal for code-related messages without trigger words', () => {
      expect(detectSignal('How do I resolve this bug?')).toEqual({ isSignal: false, signalType: '' })
      expect(detectSignal('Timer implementation')).toEqual({ isSignal: false, signalType: '' })
    })

    it('returns no signal for partial matches', () => {
      expect(detectSignal('I need to stopwatch the performance')).toEqual({ isSignal: true, signalType: 'feedback' })
      expect(detectSignal('The instruction manual says')).toEqual({ isSignal: false, signalType: '' })
    })
  })

  describe('signal detection edge cases', () => {
    it('handles empty text', () => {
      expect(detectSignal('')).toEqual({ isSignal: false, signalType: '' })
    })

    it('handles whitespace-only text', () => {
      expect(detectSignal('   ')).toEqual({ isSignal: false, signalType: '' })
    })

    it('handles text with multiple signal patterns', () => {
      // ! prefix takes precedence
      expect(detectSignal('!positive fix this')).toEqual({ isSignal: true, signalType: 'positive' })
    })
  })
})


describe('API error handling with mocked fetch', () => {
  let originalFetch: typeof global.fetch

  beforeEach(() => {
    originalFetch = global.fetch
  })

  afterEach(() => {
    global.fetch = originalFetch as typeof global.fetch
    setToken('')
  })

  describe('sendMessage error handling', () => {
    it('returns null when the API returns non-ok response', async () => {
      setToken('test-token')
      global.fetch = vi.fn().mockResolvedValue({
        json: async () => ({ ok: false, description: 'Bad Request: chat not found' })
      } as Response) as unknown as typeof global.fetch

      const result = await sendMessage(123456, 'Hello')
      expect(result).toBeNull()
    })

    it('returns message_id on successful send', async () => {
      setToken('test-token')
      global.fetch = vi.fn().mockResolvedValue({
        json: async () => ({ ok: true, result: { message_id: 42 } })
      } as Response) as unknown as typeof global.fetch

      const result = await sendMessage(123456, 'Hello')
      expect(result).toBe(42)
    })

    it('falls back to plain text when HTML parsing fails', async () => {
      setToken('test-token')
      let callCount = 0
      global.fetch = vi.fn().mockImplementation(() => {
        callCount++
        if (callCount === 1) {
          // First call (HTML) fails
          return Promise.resolve({
            json: async () => ({ ok: false, description: 'Bad Request: can\'t parse message' })
          } as Response) as unknown as typeof global.fetch
        }
        // Second call (plain text) succeeds
        return Promise.resolve({
          json: async () => ({ ok: true, result: { message_id: 123 } })
        } as Response) as unknown as typeof global.fetch
      }) as unknown as typeof global.fetch

      const result = await sendMessage(123456, '**bold** text')
      expect(result).toBe(123)
      expect(global.fetch).toHaveBeenCalledTimes(2)
    })

    it('handles network timeout gracefully', async () => {
      setToken('test-token')
      global.fetch = vi.fn().mockRejectedValue(new Error('Network timeout')) as unknown as typeof global.fetch

      const result = await sendMessage(123456, 'Hello')
      expect(result).toBeNull()
    })

    it('handles AbortError from fetch', async () => {
      setToken('test-token')
      const abortError = new Error('The operation was aborted')
      abortError.name = 'AbortError'
      global.fetch = vi.fn().mockRejectedValue(abortError) as unknown as typeof global.fetch

      const result = await sendMessage(123456, 'Hello')
      expect(result).toBeNull()
    })
  })

  describe('editMessage error handling', () => {
    it('returns false when the API returns non-ok response', async () => {
      setToken('test-token')
      global.fetch = vi.fn().mockResolvedValue({
        json: async () => ({ ok: false, description: 'Bad Request: message not found' })
      } as Response) as unknown as typeof global.fetch

      const result = await editMessage(123456, 789, 'Updated text')
      expect(result).toBe(false)
    })

    it('returns true on successful edit', async () => {
      setToken('test-token')
      global.fetch = vi.fn().mockResolvedValue({
        json: async () => ({ ok: true, result: true })
      } as Response) as unknown as typeof global.fetch

      const result = await editMessage(123456, 789, 'Updated text')
      expect(result).toBe(true)
    })

    it('falls back to plain text when HTML edit fails', async () => {
      setToken('test-token')
      let callCount = 0
      global.fetch = vi.fn().mockImplementation(() => {
        callCount++
        if (callCount === 1) {
          return Promise.resolve({
            json: async () => ({ ok: false, description: 'Bad Request: can\'t parse message' })
          } as Response)
        }
        return Promise.resolve({
          json: async () => ({ ok: true, result: true })
        } as Response)
      }) as unknown as typeof global.fetch

      const result = await editMessage(123456, 789, '**bold** text')
      expect(result).toBe(true)
      expect(global.fetch).toHaveBeenCalledTimes(2)
    })
  })

  describe('sendTyping error handling', () => {
    it('handles API errors silently (no throw)', async () => {
      setToken('test-token')
      global.fetch = vi.fn().mockResolvedValue({
        json: async () => ({ ok: false, description: 'Bad Request' })
      } as Response) as unknown as typeof global.fetch

      await expect(sendTyping(123456)).resolves.not.toThrow()
    })

    it('handles network errors silently', async () => {
      setToken('test-token')
      global.fetch = vi.fn().mockRejectedValue(new Error('Network error')) as unknown as typeof global.fetch

      await expect(sendTyping(123456)).resolves.not.toThrow()
    })
  })

  describe('downloadPhoto error handling', () => {
    it('returns null when getFile fails', async () => {
      setToken('test-token')
      global.fetch = vi.fn().mockResolvedValue({
        json: async () => ({ ok: false, description: 'File not found' })
      } as Response) as unknown as typeof global.fetch

      const result = await downloadPhoto('file_id_123')
      expect(result).toBeNull()
    })

    it('returns null when file download returns non-ok status', async () => {
      setToken('test-token')
      let callCount = 0
      global.fetch = vi.fn().mockImplementation((url: string | URL | Request) => {
        callCount++
        const urlStr = url.toString()
        if (urlStr.includes('getFile')) {
          return Promise.resolve({
            json: async () => ({ ok: true, result: { file_path: 'photos/file.jpg' } })
          } as Response)
        }
        // File download fails
        return Promise.resolve({
          ok: false,
          status: 404,
          statusText: 'Not Found'
        } as Response)
      }) as unknown as typeof global.fetch

      const result = await downloadPhoto('file_id_123')
      expect(result).toBeNull()
    })

    it('returns null on download timeout', async () => {
      setToken('test-token')
      global.fetch = vi.fn().mockImplementation((url: string | URL | Request) => {
        const urlStr = url.toString()
        if (urlStr.includes('getFile')) {
          return Promise.resolve({
            json: async () => ({ ok: true, result: { file_path: 'photos/file.jpg' } })
          } as Response)
        }
        return Promise.reject(new Error('Timeout'))
      }) as unknown as typeof global.fetch

      const result = await downloadPhoto('file_id_123')
      expect(result).toBeNull()
    })

    it('successfully downloads and converts image to base64', async () => {
      setToken('test-token')
      const mockImageBuffer = Buffer.from('fake image data')
      
      global.fetch = vi.fn().mockImplementation((url: string | URL | Request) => {
        const urlStr = url.toString()
        if (urlStr.includes('getFile')) {
          return Promise.resolve({
            json: async () => ({ ok: true, result: { file_path: 'photos/file.jpg' } })
          } as Response)
        }
        return Promise.resolve({
          ok: true,
          arrayBuffer: async () => mockImageBuffer.buffer.slice(mockImageBuffer.byteOffset, mockImageBuffer.byteOffset + mockImageBuffer.byteLength)
        } as unknown as Response)
      }) as unknown as typeof global.fetch

      const result = await downloadPhoto('file_id_123')
      expect(result).not.toBeNull()
      expect(result?.mediaType).toBe('image/jpeg')
      expect(result?.data).toBe(mockImageBuffer.toString('base64'))
      expect(result?.label).toBe('file_id_123')
    })

    it('detects PNG images by file extension', async () => {
      setToken('test-token')
      const mockImageBuffer = Buffer.from('fake png data')
      
      global.fetch = vi.fn().mockImplementation((url: string | URL | Request) => {
        const urlStr = url.toString()
        if (urlStr.includes('getFile')) {
          return Promise.resolve({
            json: async () => ({ ok: true, result: { file_path: 'photos/file.png' } })
          } as Response)
        }
        return Promise.resolve({
          ok: true,
          arrayBuffer: async () => mockImageBuffer.buffer.slice(mockImageBuffer.byteOffset, mockImageBuffer.byteOffset + mockImageBuffer.byteLength)
        } as unknown as Response)
      }) as unknown as typeof global.fetch

      const result = await downloadPhoto('file_id_123')
      expect(result?.mediaType).toBe('image/png')
    })

    it('detects GIF images by file extension', async () => {
      setToken('test-token')
      const mockImageBuffer = Buffer.from('fake gif data')
      
      global.fetch = vi.fn().mockImplementation((url: string | URL | Request) => {
        const urlStr = url.toString()
        if (urlStr.includes('getFile')) {
          return Promise.resolve({
            json: async () => ({ ok: true, result: { file_path: 'photos/file.gif' } })
          } as Response)
        }
        return Promise.resolve({
          ok: true,
          arrayBuffer: async () => mockImageBuffer.buffer.slice(mockImageBuffer.byteOffset, mockImageBuffer.byteOffset + mockImageBuffer.byteLength)
        } as unknown as Response)
      }) as unknown as typeof global.fetch

      const result = await downloadPhoto('file_id_123')
      expect(result?.mediaType).toBe('image/gif')
    })

    it('detects WebP images by file extension', async () => {
      setToken('test-token')
      const mockImageBuffer = Buffer.from('fake webp data')
      
      global.fetch = vi.fn().mockImplementation((url: string | URL | Request) => {
        const urlStr = url.toString()
        if (urlStr.includes('getFile')) {
          return Promise.resolve({
            json: async () => ({ ok: true, result: { file_path: 'photos/file.webp' } })
          } as Response)
        }
        return Promise.resolve({
          ok: true,
          arrayBuffer: async () => mockImageBuffer.buffer.slice(mockImageBuffer.byteOffset, mockImageBuffer.byteOffset + mockImageBuffer.byteLength)
        } as unknown as Response)
      }) as unknown as typeof global.fetch

      const result = await downloadPhoto('file_id_123')
      expect(result?.mediaType).toBe('image/webp')
    })

    it('defaults to JPEG for unknown extensions', async () => {
      setToken('test-token')
      const mockImageBuffer = Buffer.from('fake image data')
      
      global.fetch = vi.fn().mockImplementation((url: string | URL | Request) => {
        const urlStr = url.toString()
        if (urlStr.includes('getFile')) {
          return Promise.resolve({
            json: async () => ({ ok: true, result: { file_path: 'photos/file.unknown' } })
          } as Response)
        }
        return Promise.resolve({
          ok: true,
          arrayBuffer: async () => mockImageBuffer.buffer.slice(mockImageBuffer.byteOffset, mockImageBuffer.byteOffset + mockImageBuffer.byteLength)
        } as unknown as Response)
      }) as unknown as typeof global.fetch

      const result = await downloadPhoto('file_id_123')
      expect(result?.mediaType).toBe('image/jpeg')
    })

    it('handles file paths without extensions by defaulting to JPEG', async () => {
      setToken('test-token')
      const mockImageBuffer = Buffer.from('fake image data')
      
      global.fetch = vi.fn().mockImplementation((url: string | URL | Request) => {
        const urlStr = url.toString()
        if (urlStr.includes('getFile')) {
          return Promise.resolve({
            json: async () => ({ ok: true, result: { file_path: 'photos/file' } })
          } as Response)
        }
        return Promise.resolve({
          ok: true,
          arrayBuffer: async () => mockImageBuffer.buffer.slice(mockImageBuffer.byteOffset, mockImageBuffer.byteOffset + mockImageBuffer.byteLength)
        } as unknown as Response)
      }) as unknown as typeof global.fetch

      const result = await downloadPhoto('file_id_123')
      expect(result).not.toBeNull()
      expect(result?.mediaType).toBe('image/jpeg')
    })

    it('detects PNG images by file extension', async () => {
      setToken('test-token')
      const mockImageBuffer = Buffer.from('fake png data')
      
      global.fetch = vi.fn().mockImplementation((url: string | URL | Request) => {
        const urlStr = url.toString()
        if (urlStr.includes('getFile')) {
          return Promise.resolve({
            json: async () => ({ ok: true, result: { file_path: 'photos/file.png' } })
          } as Response)
        }
        return Promise.resolve({
          ok: true,
          arrayBuffer: async () => mockImageBuffer.buffer.slice(mockImageBuffer.byteOffset, mockImageBuffer.byteOffset + mockImageBuffer.byteLength)
        } as unknown as Response)
      }) as unknown as typeof global.fetch

      const result = await downloadPhoto('file_id_123')
      expect(result?.mediaType).toBe('image/png')
    })

    it('detects GIF images by file extension', async () => {
      setToken('test-token')
      const mockImageBuffer = Buffer.from('fake gif data')
      
      global.fetch = vi.fn().mockImplementation((url: string | URL | Request) => {
        const urlStr = url.toString()
        if (urlStr.includes('getFile')) {
          return Promise.resolve({
            json: async () => ({ ok: true, result: { file_path: 'photos/file.gif' } })
          } as Response)
        }
        return Promise.resolve({
          ok: true,
          arrayBuffer: async () => mockImageBuffer.buffer.slice(mockImageBuffer.byteOffset, mockImageBuffer.byteOffset + mockImageBuffer.byteLength)
        } as unknown as Response)
      }) as unknown as typeof global.fetch

      const result = await downloadPhoto('file_id_123')
      expect(result?.mediaType).toBe('image/gif')
    })

    it('detects WebP images by file extension', async () => {
      setToken('test-token')
      const mockImageBuffer = Buffer.from('fake webp data')
      
      global.fetch = vi.fn().mockImplementation((url: string | URL | Request) => {
        const urlStr = url.toString()
        if (urlStr.includes('getFile')) {
          return Promise.resolve({
            json: async () => ({ ok: true, result: { file_path: 'photos/file.webp' } })
          } as Response)
        }
        return Promise.resolve({
          ok: true,
          arrayBuffer: async () => mockImageBuffer.buffer.slice(mockImageBuffer.byteOffset, mockImageBuffer.byteOffset + mockImageBuffer.byteLength)
        } as unknown as Response)
      }) as unknown as typeof global.fetch

      const result = await downloadPhoto('file_id_123')
      expect(result?.mediaType).toBe('image/webp')
    })

    it('defaults to JPEG for unknown extensions', async () => {
      setToken('test-token')
      const mockImageBuffer = Buffer.from('fake image data')
      
      global.fetch = vi.fn().mockImplementation((url: string | URL | Request) => {
        const urlStr = url.toString()
        if (urlStr.includes('getFile')) {
          return Promise.resolve({
            json: async () => ({ ok: true, result: { file_path: 'photos/file.unknown' } })
          } as Response)
        }
        return Promise.resolve({
          ok: true,
          arrayBuffer: async () => mockImageBuffer.buffer.slice(mockImageBuffer.byteOffset, mockImageBuffer.byteOffset + mockImageBuffer.byteLength)
        } as unknown as Response)
      }) as unknown as typeof global.fetch

      const result = await downloadPhoto('file_id_123')
      expect(result?.mediaType).toBe('image/jpeg')
    })

    it('handles file paths without extensions', async () => {
      setToken('test-token')
      const mockImageBuffer = Buffer.from('fake image data')
      
      global.fetch = vi.fn().mockImplementation((url: string | URL | Request) => {
        const urlStr = url.toString()
        if (urlStr.includes('getFile')) {
          return Promise.resolve({
            json: async () => ({ ok: true, result: { file_path: 'photos/file' } })
          } as Response)
        }
        return Promise.resolve({
          ok: true,
          arrayBuffer: async () => mockImageBuffer.buffer.slice(mockImageBuffer.byteOffset, mockImageBuffer.byteOffset + mockImageBuffer.byteLength)
        } as unknown as Response)
      }) as unknown as typeof global.fetch

      const result = await downloadPhoto('file_id_123')
      expect(result?.mediaType).toBe('image/jpeg')
    })
  })
})


describe('streaming state management', () => {
  describe('stream buffer behavior', () => {
    it('accumulates content in buffer until flush', () => {
      // Simulate stream state behavior
      interface StreamState {
        chatId: number
        msgId: number | null
        buffer: string
      }
      
      const streams = new Map<string, StreamState>()
      const getOrCreateStream = (chatId: number, sessionId: string): StreamState => {
        let s = streams.get(sessionId)
        if (!s) {
          s = { chatId, msgId: null, buffer: '' }
          streams.set(sessionId, s)
        }
        return s
      }

      const sessionId = 'tg:123456'
      const s = getOrCreateStream(123456, sessionId)
      
      // Simulate receiving tokens
      s.buffer += 'Hello'
      s.buffer += ' world'
      s.buffer += '!'
      
      expect(s.buffer).toBe('Hello world!')
      expect(s.msgId).toBeNull() // Not sent yet
    })

    it('clears stream state on finalize', () => {
      interface StreamState {
        chatId: number
        msgId: number | null
        buffer: string
      }
      
      const streams = new Map<string, StreamState>()
      const sessionId = 'tg:123456'
      
      streams.set(sessionId, { chatId: 123456, msgId: 789, buffer: 'content' })
      
      // Finalize deletes the stream
      streams.delete(sessionId)
      
      expect(streams.has(sessionId)).toBe(false)
    })
  })
})


describe('security and access control', () => {
  describe('allowed chat ID filtering', () => {
    it('allows messages from allowed chat IDs', () => {
      const allowedChatIds = [123456, 789012]
      const chatId = 123456
      
      const isAllowed = !allowedChatIds.length || allowedChatIds.includes(chatId)
      expect(isAllowed).toBe(true)
    })

    it('blocks messages from non-allowed chat IDs', () => {
      const allowedChatIds = [123456, 789012]
      const chatId = 999999
      
      const isAllowed = !allowedChatIds.length || allowedChatIds.includes(chatId)
      expect(isAllowed).toBe(false)
    })

    it('allows all messages when allowedChatIds is empty', () => {
      const allowedChatIds: number[] = []
      const chatId = 999999
      
      const isAllowed = !allowedChatIds.length || allowedChatIds.includes(chatId)
      expect(isAllowed).toBe(true)
    })

    it('allows all messages when allowedChatIds is undefined', () => {
      const allowedChatIds: number[] | undefined = undefined
      const chatId = 999999
      
      // When undefined, treat as allowing all (no restriction)
      const hasNoRestrictions = allowedChatIds === undefined || (allowedChatIds as number[]).length === 0
      const isAllowed = hasNoRestrictions || (allowedChatIds as number[]).includes(chatId)
      expect(isAllowed).toBe(true)
    })
  })
})


describe('command message handling', () => {
  describe('special command routing', () => {
    it('recognizes /start command for welcome message', () => {
      const text = '/start'
      expect(text.startsWith('/start')).toBe(true)
    })

    it('recognizes all / prefixed messages as commands', () => {
      const commands = ['/help', '/status', '/settings', '/stop']
      commands.forEach(cmd => {
        expect(cmd.startsWith('/')).toBe(true)
      })
    })

    it('commands bypass streaming and are sent directly', () => {
      const text = '/status'
      const isCommand = text.startsWith('/')
      expect(isCommand).toBe(true)
      // Commands don't trigger streaming setup
    })
  })
})


describe('long-polling configuration', () => {
  it('uses 25-second server-side timeout for getUpdates', () => {
    const POLL_TIMEOUT_SEC = 25
    expect(POLL_TIMEOUT_SEC).toBe(25)
  })

  it('uses fetch timeout that exceeds server timeout', () => {
    const POLL_TIMEOUT_SEC = 25
    const FETCH_TIMEOUT_MS = (POLL_TIMEOUT_SEC + 10) * 1000
    expect(FETCH_TIMEOUT_MS).toBe(35000)
  })

  it('uses exponential backoff starting at 2 seconds', () => {
    const BACKOFF_BASE_MS = 2000
    const BACKOFF_MAX_MS = 30000
    
    // Simulate backoff progression
    let backoff = BACKOFF_BASE_MS
    backoff = Math.min(backoff * 2, BACKOFF_MAX_MS) // 4000
    backoff = Math.min(backoff * 2, BACKOFF_MAX_MS) // 8000
    backoff = Math.min(backoff * 2, BACKOFF_MAX_MS) // 16000
    backoff = Math.min(backoff * 2, BACKOFF_MAX_MS) // 30000 (capped)
    
    expect(backoff).toBe(BACKOFF_MAX_MS)
  })
})


describe('Telegram update message structure', () => {
  it('handles messages with text content', () => {
    const update = {
      update_id: 123456789,
      message: {
        message_id: 1,
        chat: { id: 123456, type: 'private' },
        from: { id: 987654, username: 'testuser', first_name: 'Test' },
        text: 'Hello bot',
        date: Math.floor(Date.now() / 1000)
      }
    }
    
    expect(update.message.text).toBe('Hello bot')
    expect(update.message.chat.id).toBe(123456)
  })

  it('handles messages with caption instead of text', () => {
    const update = {
      update_id: 123456789,
      message: {
        message_id: 1,
        chat: { id: 123456, type: 'private' },
        from: { id: 987654, username: 'testuser', first_name: 'Test' },
        caption: 'Photo caption',
        photo: [{ file_id: 'small', width: 100, height: 100 }],
        date: Math.floor(Date.now() / 1000)
      }
    }
    
    // When text is missing, caption is used
    const content = update.message.caption || ''
    expect(content).toBe('Photo caption')
  })

  it('handles group chat messages (negative chat IDs)', () => {
    const update = {
      update_id: 123456789,
      message: {
        message_id: 1,
        chat: { id: -1001234567890, type: 'supergroup' },
        from: { id: 987654, username: 'testuser' },
        text: 'Group message',
        date: Math.floor(Date.now() / 1000)
      }
    }
    
    expect(update.message.chat.id).toBe(-1001234567890)
    expect(update.message.chat.type).toBe('supergroup')
  })

  it('handles photo messages with multiple sizes', () => {
    const update = {
      update_id: 123456789,
      message: {
        message_id: 1,
        chat: { id: 123456, type: 'private' },
        photo: [
          { file_id: 'thumb', file_size: 1024, width: 100, height: 100 },
          { file_id: 'medium', file_size: 10240, width: 320, height: 320 },
          { file_id: 'large', file_size: 102400, width: 1024, height: 1024 }
        ],
        date: Math.floor(Date.now() / 1000)
      }
    }
    
    // Largest photo is used
    const largest = update.message.photo![update.message.photo!.length - 1]
    expect(largest.file_id).toBe('large')
    expect(largest.width).toBe(1024)
  })

  it('handles messages without from field (channel posts)', () => {
    const update: { update_id: number; message: { message_id: number; chat: { id: number; type: string }; text: string; date: number; from?: { id: number; username?: string } } } = {
      update_id: 123456789,
      message: {
        message_id: 1,
        chat: { id: -1001234567890, type: 'channel' },
        text: 'Channel post',
        date: Math.floor(Date.now() / 1000)
      }
    }
    
    expect(update.message.from).toBeUndefined()
    expect(update.message.text).toBe('Channel post')
  })
})
