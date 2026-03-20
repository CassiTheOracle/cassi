/**
 * Telegram-specific HTML renderer.
 *
 * Ported from OpenClaw's src/telegram/format.ts.
 * Converts GFM markdown to Telegram-compatible HTML using the
 * markdown IR pipeline (ir.ts → render.ts → format.ts).
 */

import type { MarkdownTableMode } from './ir.js'
import {
  chunkMarkdownIR,
  markdownToIR,
  type MarkdownLinkSpan,
  type MarkdownIR,
} from './ir.js'
import { renderMarkdownWithMarkers } from './render.js'

export type TelegramFormattedChunk = {
  html: string
  text: string
}

/**
 * @dep callers: wrapFileReferencesInHtml (workers/channels/markdown/format.ts), wrapSegmentFileRefs (workers/channels/markdown/format.ts), wrapStandaloneFileRef (workers/channels/markdown/format.ts), escapeHtmlAttr (workers/channels/markdown/format.ts)
 * @dep module: Markdown
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
 */

function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function escapeHtmlAttr(text: string): string {
  return escapeHtml(text).replace(/"/g, '&quot;')
}

/**
 * File extensions that share TLDs and commonly appear in code/documentation.
 * These are wrapped in <code> tags to prevent Telegram from generating
 * spurious domain registrar previews.
 */
const FILE_EXTENSIONS_WITH_TLD = new Set([
  'md',  // Markdown (Moldova)
  'go',  // Go language
  'py',  // Python (Paraguay)
  'pl',  // Perl (Poland)
  'sh',  // Shell (Saint Helena)
  'am',  // Automake files (Armenia)
  'at',  // Assembly (Austria)
  'be',  // Backend files (Belgium)
  'cc',  // C++ source (Cocos Islands)
])

/** Detects when markdown-it linkify auto-generated a link from a bare filename */
/**
 * @dep callers: wrapFileReferencesInHtml (workers/channels/markdown/format.ts), buildTelegramLink (workers/channels/markdown/format.ts)
 * @dep calls: has
 * @dep module: Markdown
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function isAutoLinkedFileRef(href: string, label: string): boolean {
  const stripped = href.replace(/^https?:\/\//i, '')
  if (stripped !== label) {
    return false
  }
  const dotIndex = label.lastIndexOf('.')
  if (dotIndex < 1) {
    return false
  }
  const ext = label.slice(dotIndex + 1).toLowerCase()
  if (!FILE_EXTENSIONS_WITH_TLD.has(ext)) {
    return false
  }
  // Reject if any path segment before the filename contains a dot (looks like a domain)
  const segments = label.split('/')
  if (segments.length > 1) {
    for (let i = 0; i < segments.length - 1; i++) {
      if (segments[i].includes('.')) {
        return false
      }
    }
  }
  return true
}

function buildTelegramLink(link: MarkdownLinkSpan, text: string) {
  const href = link.href.trim()
  if (!href) {
    return null
  }
  if (link.start === link.end) {
    return null
  }
  const label = text.slice(link.start, link.end)
  if (isAutoLinkedFileRef(href, label)) {
    return null
  }
  const safeHref = escapeHtmlAttr(href)
  return {
    start: link.start,
    end: link.end,
    open: `<a href="${safeHref}">`,
    close: '</a>',
  }
}

/**
 * @dep callers: markdownToTelegramChunks (workers/channels/markdown/format.ts), markdownToTelegramHtml (workers/channels/markdown/format.ts)
 * @dep calls: renderMarkdownWithMarkers
 * @dep module: Markdown
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

function renderTelegramHtml(ir: MarkdownIR): string {
  return renderMarkdownWithMarkers(ir, {
    styleMarkers: {
      bold: { open: '<b>', close: '</b>' },
      italic: { open: '<i>', close: '</i>' },
      strikethrough: { open: '<s>', close: '</s>' },
      code: { open: '<code>', close: '</code>' },
      code_block: { open: '<pre><code>', close: '</code></pre>' },
      spoiler: { open: '<tg-spoiler>', close: '</tg-spoiler>' },
      blockquote: { open: '<blockquote>', close: '</blockquote>' },
    },
    escapeText: escapeHtml,
    buildLink: buildTelegramLink,
  })
}


function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

const FILE_EXTENSIONS_PATTERN = Array.from(FILE_EXTENSIONS_WITH_TLD).map(escapeRegex).join('|')
const AUTO_LINKED_ANCHOR_PATTERN = /<a\s+href="https?:\/\/([^"]+)"[^>]*>\1<\/a>/gi
const FILE_REFERENCE_PATTERN = new RegExp(
  `(^|[^a-zA-Z0-9_\\-/])([a-zA-Z0-9_.\\-./]+\\.(?:${FILE_EXTENSIONS_PATTERN}))(?=$|[^a-zA-Z0-9_\\-/])`,
  'gi',
)
const ORPHANED_TLD_PATTERN = new RegExp(
  `([^a-zA-Z0-9]|^)([A-Za-z]\\.(?:${FILE_EXTENSIONS_PATTERN}))(?=[^a-zA-Z0-9/]|$)`,
  'g',
)
const HTML_TAG_PATTERN = /(<\/?)([a-zA-Z][a-zA-Z0-9-]*)\b[^>]*?>/gi

function wrapStandaloneFileRef(match: string, prefix: string, filename: string): string {
  if (filename.startsWith('//')) {
    return match
  }
  if (/https?:\/\/$/i.test(prefix)) {
    return match
  }
  return `${prefix}<code>${escapeHtml(filename)}</code>`
}

function wrapSegmentFileRefs(
  text: string,
  codeDepth: number,
  preDepth: number,
  anchorDepth: number,
): string {
  if (!text || codeDepth > 0 || preDepth > 0 || anchorDepth > 0) {
    return text
  }
  const wrappedStandalone = text.replace(FILE_REFERENCE_PATTERN, wrapStandaloneFileRef)
  return wrappedStandalone.replace(ORPHANED_TLD_PATTERN, (match, prefix: string, tld: string) =>
    prefix === '>' ? match : `${prefix}<code>${escapeHtml(tld)}</code>`,
  )
}

/**
 * @dep callers: markdownToTelegramChunks (workers/channels/markdown/format.ts), markdownToTelegramHtml (workers/channels/markdown/format.ts)
 * @dep calls: exec, escapeHtml, isAutoLinkedFileRef, wrapSegmentFileRefs
 * @dep module: Markdown
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */

export function wrapFileReferencesInHtml(html: string): string {
  // De-linkify auto-generated anchors where href="http://<label>"
  AUTO_LINKED_ANCHOR_PATTERN.lastIndex = 0
  const deLinkified = html.replace(AUTO_LINKED_ANCHOR_PATTERN, (_match, label: string) => {
    if (!isAutoLinkedFileRef(`http://${label}`, label)) {
      return _match
    }
    return `<code>${escapeHtml(label)}</code>`
  })

  // Track nesting depth for tags that should not be modified
  let codeDepth = 0
  let preDepth = 0
  let anchorDepth = 0
  let result = ''
  let lastIndex = 0

  HTML_TAG_PATTERN.lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = HTML_TAG_PATTERN.exec(deLinkified)) !== null) {
    const tagStart = match.index
    const tagEnd = HTML_TAG_PATTERN.lastIndex
    const isClosing = match[1] === '</'
    const tagName = match[2].toLowerCase()

    const textBefore = deLinkified.slice(lastIndex, tagStart)
    result += wrapSegmentFileRefs(textBefore, codeDepth, preDepth, anchorDepth)

    if (tagName === 'code') {
      codeDepth = isClosing ? Math.max(0, codeDepth - 1) : codeDepth + 1
    } else if (tagName === 'pre') {
      preDepth = isClosing ? Math.max(0, preDepth - 1) : preDepth + 1
    } else if (tagName === 'a') {
      anchorDepth = isClosing ? Math.max(0, anchorDepth - 1) : anchorDepth + 1
    }

    result += deLinkified.slice(tagStart, tagEnd)
    lastIndex = tagEnd
  }

  const remainingText = deLinkified.slice(lastIndex)
  result += wrapSegmentFileRefs(remainingText, codeDepth, preDepth, anchorDepth)

  return result
}


/**
 * Convert GFM markdown to Telegram-compatible HTML.
 * This is the main entry point for formatting messages.
 * @dep callers: telegram.test.ts (tests/telegram.test.ts), editMessage (workers/channels/telegram-common.ts), sendMessage (workers/channels/telegram-common.ts), sanitizeMarkdown (workers/channels/telegram-common.ts)
 * @dep calls: markdownToIR, renderTelegramHtml, wrapFileReferencesInHtml
 * @dep module: Markdown
 * @dep risk: MEDIUM | 4 callers, 0 flows, 1 module
 */
export function markdownToTelegramHtml(
  markdown: string,
  options: { tableMode?: MarkdownTableMode; wrapFileRefs?: boolean } = {},
): string {
  const ir = markdownToIR(markdown ?? '', {
    linkify: true,
    enableSpoilers: true,
    headingStyle: 'bold',
    blockquotePrefix: '',
    tableMode: options.tableMode ?? 'bullets',
  })
  const html = renderTelegramHtml(ir)
  if (options.wrapFileRefs !== false) {
    return wrapFileReferencesInHtml(html)
  }
  return html
}

/**
 * Convert GFM markdown to chunked Telegram HTML (respecting Telegram's 4096 char limit).
 * Returns array of { html, text } chunks.
 */
export function markdownToTelegramChunks(
  markdown: string,
  limit: number,
  options: { tableMode?: MarkdownTableMode } = {},
): TelegramFormattedChunk[] {
  const ir = markdownToIR(markdown ?? '', {
    linkify: true,
    enableSpoilers: true,
    headingStyle: 'bold',
    blockquotePrefix: '',
    tableMode: options.tableMode ?? 'bullets',
  })
  const chunks = chunkMarkdownIR(ir, limit)
  return chunks.map((chunk) => ({
    html: wrapFileReferencesInHtml(renderTelegramHtml(chunk)),
    text: chunk.text,
  }))
}

/**
 * Convert GFM markdown to chunked Telegram HTML strings.
 */
export function markdownToTelegramHtmlChunks(markdown: string, limit: number): string[] {
  return markdownToTelegramChunks(markdown, limit).map((chunk) => chunk.html)
}
