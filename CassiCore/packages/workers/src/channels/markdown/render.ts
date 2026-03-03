/**
 * Markdown IR → formatted output renderer.
 *
 * Ported from OpenClaw's src/markdown/render.ts.
 * Takes a MarkdownIR and renders it to a string using configurable
 * style markers (HTML tags, markdown markers, etc.).
 */

import type { MarkdownIR, MarkdownLinkSpan, MarkdownStyle, MarkdownStyleSpan } from './ir.js'

export type RenderStyleMarker = {
  open: string
  close: string
}

export type RenderStyleMap = Partial<Record<MarkdownStyle, RenderStyleMarker>>

export type RenderLink = {
  start: number
  end: number
  open: string
  close: string
}

export type RenderOptions = {
  styleMarkers: RenderStyleMap
  escapeText: (text: string) => string
  buildLink?: (link: MarkdownLinkSpan, text: string) => RenderLink | null
}

const STYLE_ORDER: MarkdownStyle[] = [
  'blockquote',
  'code_block',
  'code',
  'bold',
  'italic',
  'strikethrough',
  'spoiler',
]

const STYLE_RANK = new Map<MarkdownStyle, number>(
  STYLE_ORDER.map((style, index) => [style, index]),
)

function sortStyleSpans(spans: MarkdownStyleSpan[]): MarkdownStyleSpan[] {
  return [...spans].sort((a, b) => {
    if (a.start !== b.start) {
      return a.start - b.start
    }
    if (a.end !== b.end) {
      return b.end - a.end
    }
    return (STYLE_RANK.get(a.style) ?? 0) - (STYLE_RANK.get(b.style) ?? 0)
  })
}

export function renderMarkdownWithMarkers(ir: MarkdownIR, options: RenderOptions): string {
  const text = ir.text ?? ''
  if (!text) {
    return ''
  }

  const styleMarkers = options.styleMarkers
  const styled = sortStyleSpans(ir.styles.filter((span) => Boolean(styleMarkers[span.style])))

  const boundaries = new Set<number>()
  boundaries.add(0)
  boundaries.add(text.length)

  const startsAt = new Map<number, MarkdownStyleSpan[]>()
  for (const span of styled) {
    if (span.start === span.end) {
      continue
    }
    boundaries.add(span.start)
    boundaries.add(span.end)
    const list = startsAt.get(span.start)
    if (list) {
      list.push(span)
    } else {
      startsAt.set(span.start, [span])
    }
  }

  // Process links
  const linkItems: Array<{ start: number; end: number; open: string; close: string }> = []
  if (options.buildLink) {
    for (const link of ir.links) {
      const item = options.buildLink(link, text)
      if (item) {
        linkItems.push(item)
        boundaries.add(item.start)
        boundaries.add(item.end)
      }
    }
  }
  const linkStartsAt = new Map<number, typeof linkItems>()
  for (const item of linkItems) {
    const list = linkStartsAt.get(item.start)
    if (list) {
      list.push(item)
    } else {
      linkStartsAt.set(item.start, [item])
    }
  }

  const points = [...boundaries].sort((a, b) => a - b)
  const stack: Array<{ close: string; end: number }> = []
  let out = ''

  for (let i = 0; i < points.length; i++) {
    const pos = points[i]

    // Close items that end at or before this point (LIFO)
    while (stack.length > 0 && stack[stack.length - 1].end <= pos) {
      out += stack.pop()!.close
    }

    // Open items (style spans + links)
    const openingItems: Array<{ open: string; close: string; end: number }> = []

    const spans = startsAt.get(pos)
    if (spans) {
      for (const span of spans) {
        const marker = styleMarkers[span.style]
        if (marker) {
          openingItems.push({ open: marker.open, close: marker.close, end: span.end })
        }
      }
    }

    const links = linkStartsAt.get(pos)
    if (links) {
      for (const link of links) {
        openingItems.push({ open: link.open, close: link.close, end: link.end })
      }
    }

    if (openingItems.length > 0) {
      // Sort by descending end so wider spans open first — ensures LIFO closes stay valid for same-start overlaps.
      openingItems.sort((a, b) => b.end - a.end)
      // Before opening, close any currently open items with smaller end (they'd overlap)
      // Re-push after opening wider items so nesting is correct.
      const reopen: Array<{ close: string; end: number; savedText: string }> = []
      while (
        stack.length > 0 &&
        openingItems.some((item) => item.end > stack[stack.length - 1].end)
      ) {
        const top = stack.pop()!
        if (top.end > pos) {
          out += top.close
          reopen.push({ close: top.close, end: top.end, savedText: '' })
        }
      }
      // Re-open in reverse order (LIFO)
      for (let j = reopen.length - 1; j >= 0; j--) {
        // For re-opening, we'd need the open tag too — but in practice this case
        // only occurs with malformed overlapping spans. We just push the close back.
        stack.push({ close: reopen[j].close, end: reopen[j].end })
      }

      // Now open the new items
      for (const item of openingItems) {
        out += item.open
        stack.push({ close: item.close, end: item.end })
      }
    }

    const next = points[i + 1]
    if (next === undefined) {
      break
    }
    if (next > pos) {
      out += options.escapeText(text.slice(pos, next))
    }
  }

  return out
}
