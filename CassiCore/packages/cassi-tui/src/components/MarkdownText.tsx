/**
 * MarkdownText — renders markdown as styled terminal text.
 *
 * Uses `marked` for parsing and `marked-terminal` for ANSI rendering.
 * Handles code blocks with syntax highlighting via `cli-highlight`.
 *
 * Includes a post-processing step to fix inline formatting (bold, italic,
 * code, links) inside list items, which marked-terminal doesn't handle.
 *
 * Usage:
 *   <MarkdownText content="# Hello\n\n**bold** text" />
 *   <MarkdownText content={partialMarkdown} streaming />
 */

import React, { useMemo } from 'react'
import { Text, Box } from 'ink'
import { Marked } from 'marked'
import { markedTerminal } from 'marked-terminal'

interface Props {
  /** The markdown content to render. */
  content: string
  /** Whether the content is still being streamed (partial markdown). */
  streaming?: boolean
  /** Terminal width for wrapping. Defaults to 80. */
  width?: number
}

// ── ANSI escape helpers ─────────────────────────────────────────────────────

const BOLD_ON = '\x1b[1m'
const BOLD_OFF = '\x1b[22m'
const YELLOW = '\x1b[33m'
const BLUE = '\x1b[34m'
const RESET = '\x1b[39m'

/**
 * Post-process rendered text to fix inline formatting that marked-terminal
 * misses inside list items. Handles:
 *   **bold**, *italic*, `code`, [text](url)
 *
 * Only processes lines that contain literal markdown markers (i.e., lines
 * where marked-terminal didn't already render the formatting).
 */
function fixInlineFormatting(text: string): string {
  return text
    // Bold: **text** → ANSI bold
    .replace(/\*\*([^*\n]+)\*\*/g, `${BOLD_ON}$1${BOLD_OFF}`)
    // Inline code: `text` → yellow (matching marked-terminal's code style, same line only)
    .replace(/`([^`\n]+)`/g, `${YELLOW}$1${RESET}`)
    // Links: [text](url) → blue text (same line only)
    .replace(/\[([^\]\n]+)\]\([^)\n]+\)/g, `${BLUE}$1${RESET}`)
}

// ── Marked instance cache ───────────────────────────────────────────────────

function createMarked(width: number): Marked {
  const md = new Marked()
  md.use(
    markedTerminal({
      width: width,
      reflowText: true,
      showSectionPrefix: false,
      tab: 2,
    }) as Parameters<typeof md.use>[0],
  )
  return md
}

const markedCache = new Map<number, Marked>()

function getMarked(width: number): Marked {
  const cached = markedCache.get(width)
  if (cached) return cached
  const md = createMarked(width)
  markedCache.set(width, md)
  return md
}

// ── Component ───────────────────────────────────────────────────────────────

/**
 * Render markdown content as styled terminal text.
 *
 * For completed messages, renders the full markdown.
 * For streaming messages, renders what we have so far (partial markdown
 * may not parse perfectly but degrades gracefully to plain text).
 */
export function MarkdownText({
  content,
  streaming = false,
  width = 80,
}: Props): React.ReactElement | null {
  const rendered = useMemo(() => {
    if (!content) return ''

    try {
      const md = getMarked(width)
      let result = md.parse(content) as string

      // Fix inline formatting that marked-terminal misses in list items
      result = fixInlineFormatting(result)

      // marked-terminal adds trailing newlines; strip them
      result = result.replace(/\n+$/, '')

      return result
    } catch {
      // If markdown parsing fails (e.g., during streaming with broken syntax),
      // fall back to plain text
      return content
    }
  }, [content, width])

  if (!rendered) return null

  return (
    <Box flexDirection="column">
      <Text>{rendered}</Text>
    </Box>
  )
}
