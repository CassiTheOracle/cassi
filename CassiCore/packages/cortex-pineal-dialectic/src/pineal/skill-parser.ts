import fs from 'node:fs'
import path from 'node:path'

import type { FacetInput } from './types.js'
import type { ILogger } from '@cassicore/foundation'

interface SkillFrontmatter {
  name: string
  description: string
}

/**
 * Parse YAML frontmatter from a SKILL.md file.
 * Handles the simple `---\nkey: value\n---` format.
 */
function parseFrontmatter(content: string): { frontmatter: SkillFrontmatter | null; body: string } {
  if (!content.startsWith('---')) {
    return { frontmatter: null, body: content }
  }

  const endIdx = content.indexOf('---', 3)
  if (endIdx === -1) {
    return { frontmatter: null, body: content }
  }

  const yamlBlock = content.slice(3, endIdx).trim()
  const body = content.slice(endIdx + 3).trim()

  const fm: Record<string, string> = {}
  for (const line of yamlBlock.split('\n')) {
    const colonIdx = line.indexOf(':')
    if (colonIdx > 0) {
      const key = line.slice(0, colonIdx).trim()
      const value = line.slice(colonIdx + 1).trim()
      fm[key] = value
    }
  }

  if (!fm.name) {
    return { frontmatter: null, body: content }
  }

  return {
    frontmatter: { name: fm.name, description: fm.description || '' },
    body,
  }
}

/**
 * Split markdown body into sections by H2 headings.
 * Returns array of { heading, content } pairs.
 */
function splitH2Sections(body: string): Array<{ heading: string; content: string }> {
  const sections: Array<{ heading: string; content: string }> = []
  const lines = body.split('\n')
  let currentHeading = ''
  let currentLines: string[] = []

  for (const line of lines) {
    if (line.startsWith('## ')) {
      if (currentHeading || currentLines.length > 0) {
        const content = currentLines.join('\n').trim()
        if (content) {
          sections.push({ heading: currentHeading || 'overview', content })
        }
      }
      currentHeading = line.slice(3).trim()
      currentLines = []
    } else {
      currentLines.push(line)
    }
  }

  if (currentHeading || currentLines.length > 0) {
    const content = currentLines.join('\n').trim()
    if (content) {
      sections.push({ heading: currentHeading || 'overview', content })
    }
  }

  return sections
}

function headingToTag(heading: string): string {
  const normalized = heading.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')
  const tagMap: Record<string, string> = {
    'use-it-for': 'scope',
    'when-to-use': 'scope',
    'core-pattern': 'procedure',
    'core-loop': 'procedure',
    'workflow': 'procedure',
    'important-rules': 'rules',
    'checklist': 'rules',
    'preferred-tools': 'tools',
    'when-not-to-use': 'anti-scope',
    'related-skills': 'related',
  }
  return tagMap[normalized] || normalized
}

/**
 * Parse a single SKILL.md file into praxis FacetInputs.
 */
export function parseSkillFile(filePath: string): FacetInput[] {
  const raw = fs.readFileSync(filePath, 'utf-8')
  const { frontmatter, body } = parseFrontmatter(raw)

  if (!frontmatter) return []

  const skillName = frontmatter.name
  const sections = splitH2Sections(body)

  return sections
    .filter(s => s.content.length > 10)
    .map(section => ({
      domain: 'praxis' as const,
      category: skillName,
      content: `${section.heading}: ${section.content}`,
      provenance: 'skill-file' as const,
      tags: [`skill:${skillName}`, headingToTag(section.heading)],
    }))
}

/**
 * Scan skill directories and parse all SKILL.md files into praxis facets.
 */
export function parseAllSkillFiles(
  skillDirs: string[],
  logger: ILogger,
): FacetInput[] {
  const allFacets: FacetInput[] = []

  for (const dir of skillDirs) {
    if (!fs.existsSync(dir)) continue

    const entries = scanForSkillFiles(dir)
    for (const filePath of entries) {
      try {
        const facets = parseSkillFile(filePath)
        allFacets.push(...facets)
        logger.debug('[skill-parser] Parsed skill file', {
          path: filePath,
          facets: facets.length,
        })
      } catch (err) {
        logger.warn('[skill-parser] Failed to parse skill file', {
          path: filePath,
          error: String(err),
        })
      }
    }
  }

  logger.info('[skill-parser] Parsed all skill files', {
    dirs: skillDirs.length,
    facets: allFacets.length,
    skills: new Set(allFacets.map(f => f.category)).size,
  })

  return allFacets
}

/**
 * Recursively find all SKILL.md files under a directory.
 */
function scanForSkillFiles(dir: string): string[] {
  const results: string[] = []

  try {
    const entries = fs.readdirSync(dir, { withFileTypes: true })
    for (const entry of entries) {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) {
        results.push(...scanForSkillFiles(full))
      } else if (entry.name === 'SKILL.md') {
        results.push(full)
      }
    }
  } catch { /* skip unreadable dirs */ }

  return results
}
