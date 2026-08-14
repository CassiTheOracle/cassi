/**
 * B1 Concept Arithmetic DSL parser.
 *
 * Grammar (Section 3.1 of aurora-concept-arithmetic.md), B1.1a subset:
 *   composition := definition | expression
 *   definition  := IDENT "=" expression
 *   expression  := layered ("@" layer_spec)?
 *   layered     := term (("+" | "-") term)*
 *   term        := factor ("*" NUMBER)?
 *   factor      := primary | "(" expression ")" | "-" primary
 *   primary     := gate | affect | reference | live | "(" expression ")"
 *   gate        := "gate(" STRING ")"
 *   affect      := "affect(" STRING ")"
 *   reference   := IDENT
 *   live        := "live(" STRING ")"
 *   layer_spec  := NUMBER | "L" NUMBER ".." "L" NUMBER | "all"
 *
 * Deferred to B1.2: the postfix `| when <predicate>` modulation.
 */

import type {
  AffectExpr,
  AffectPredicate,
  CompositionAst,
  LayerSpec,
} from './types.js'
import type { AffectLabel } from '../../mnemic-field/types.js'

const AFFECT_LABELS: ReadonlySet<AffectLabel> = new Set<AffectLabel>([
  'excited', 'delighted', 'engaged',
  'content', 'warm', 'calm',
  'frustrated', 'alarmed', 'uneasy',
  'melancholy', 'fatigued', 'neutral',
])

export interface ParsedDefinition {
  name: string
  ast: CompositionAst
  layerPolicy: string
}

export class CompositionParseError extends Error {
  constructor(message: string, readonly position: number) {
    super(`Composition parse error at ${position}: ${message}`)
    this.name = 'CompositionParseError'
  }
}

type TokenKind =
  | 'ident' | 'number' | 'string'
  | 'plus' | 'minus' | 'star' | 'eq' | 'eqeq'
  | 'lparen' | 'rparen' | 'comma'
  | 'at' | 'dotdot'
  | 'pipe' | 'lt' | 'gt' | 'approx'
  | 'eof'

interface Token {
  kind: TokenKind
  value: string
  pos: number
}

function tokenize(src: string): Token[] {
  const tokens: Token[] = []
  let i = 0
  while (i < src.length) {
    const ch = src[i]
    if (/\s/.test(ch)) { i++; continue }
    if (ch === '#') {
      while (i < src.length && src[i] !== '\n') i++
      continue
    }
    const start = i
    if (ch === '+') { tokens.push({ kind: 'plus', value: ch, pos: start }); i++; continue }
    if (ch === '-' || ch === '−') { tokens.push({ kind: 'minus', value: '-', pos: start }); i++; continue }
    if (ch === '*' || ch === '×') { tokens.push({ kind: 'star', value: '*', pos: start }); i++; continue }
    if (ch === '=' && src[i + 1] === '=') { tokens.push({ kind: 'eqeq', value: '==', pos: start }); i += 2; continue }
    if (ch === '=') { tokens.push({ kind: 'eq', value: ch, pos: start }); i++; continue }
    if (ch === '|') { tokens.push({ kind: 'pipe', value: ch, pos: start }); i++; continue }
    if (ch === '<') { tokens.push({ kind: 'lt', value: ch, pos: start }); i++; continue }
    if (ch === '>') { tokens.push({ kind: 'gt', value: ch, pos: start }); i++; continue }
    if (ch === '~' || ch === '≈') { tokens.push({ kind: 'approx', value: '~', pos: start }); i++; continue }
    if (ch === '(') { tokens.push({ kind: 'lparen', value: ch, pos: start }); i++; continue }
    if (ch === ')') { tokens.push({ kind: 'rparen', value: ch, pos: start }); i++; continue }
    if (ch === ',') { tokens.push({ kind: 'comma', value: ch, pos: start }); i++; continue }
    if (ch === '@') { tokens.push({ kind: 'at', value: ch, pos: start }); i++; continue }
    if (ch === '.' && src[i + 1] === '.') { tokens.push({ kind: 'dotdot', value: '..', pos: start }); i += 2; continue }
    if (ch === '"' || ch === "'") {
      const quote = ch
      i++
      let buf = ''
      while (i < src.length && src[i] !== quote) {
        if (src[i] === '\\' && i + 1 < src.length) { buf += src[i + 1]; i += 2; continue }
        buf += src[i]; i++
      }
      if (i >= src.length) throw new CompositionParseError('unterminated string', start)
      i++
      tokens.push({ kind: 'string', value: buf, pos: start })
      continue
    }
    if (/[0-9]/.test(ch) || (ch === '.' && /[0-9]/.test(src[i + 1] ?? ''))) {
      let buf = ''
      while (i < src.length && /[0-9.]/.test(src[i])) { buf += src[i]; i++ }
      tokens.push({ kind: 'number', value: buf, pos: start })
      continue
    }
    if (/[A-Za-z_]/.test(ch)) {
      let buf = ''
      while (i < src.length && /[A-Za-z0-9_-]/.test(src[i])) { buf += src[i]; i++ }
      tokens.push({ kind: 'ident', value: buf, pos: start })
      continue
    }
    throw new CompositionParseError(`unexpected character '${ch}'`, start)
  }
  tokens.push({ kind: 'eof', value: '', pos: src.length })
  return tokens
}

class TokenStream {
  private idx = 0
  constructor(private readonly tokens: Token[]) {}

  peek(offset = 0): Token { return this.tokens[this.idx + offset] ?? this.tokens[this.tokens.length - 1] }

  next(): Token { return this.tokens[this.idx++] ?? this.tokens[this.tokens.length - 1] }

  expect(kind: TokenKind, value?: string): Token {
    const t = this.next()
    if (t.kind !== kind || (value !== undefined && t.value !== value)) {
      throw new CompositionParseError(
        `expected ${kind}${value !== undefined ? ` '${value}'` : ''}, got ${t.kind} '${t.value}'`,
        t.pos,
      )
    }
    return t
  }

  match(kind: TokenKind, value?: string): boolean {
    const t = this.peek()
    return t.kind === kind && (value === undefined || t.value === value)
  }
}

function parseFunctionCall(s: TokenStream, expectedName: string): string {
  s.expect('ident', expectedName)
  s.expect('lparen')
  const arg = s.expect('string')
  s.expect('rparen')
  return arg.value
}

function parsePrimary(s: TokenStream): CompositionAst {
  const t = s.peek()
  if (t.kind === 'lparen') {
    s.next()
    const expr = parseExpression(s)
    s.expect('rparen')
    return expr
  }
  if (t.kind === 'minus') {
    s.next()
    const inner = parsePrimary(s)
    return inner.kind === 'scaled'
      ? { kind: 'scaled', operand: inner.operand, factor: -inner.factor }
      : { kind: 'scaled', operand: inner, factor: -1 }
  }
  if (t.kind !== 'ident') {
    throw new CompositionParseError(`expected primary, got ${t.kind} '${t.value}'`, t.pos)
  }
  if (t.value === 'gate' && s.peek(1).kind === 'lparen') {
    return { kind: 'gate', label: parseFunctionCall(s, 'gate') }
  }
  if (t.value === 'affect' && s.peek(1).kind === 'lparen') {
    const label = parseFunctionCall(s, 'affect')
    if (!AFFECT_LABELS.has(label as AffectLabel)) {
      throw new CompositionParseError(`unknown affect label '${label}'`, t.pos)
    }
    return { kind: 'affect', label: label as AffectLabel }
  }
  if (t.value === 'live' && s.peek(1).kind === 'lparen') {
    return { kind: 'live', selector: parseFunctionCall(s, 'live') }
  }
  s.next()
  return { kind: 'reference', name: t.value }
}

function parseTerm(s: TokenStream): CompositionAst {
  const left = parsePrimary(s)
  if (s.match('star')) {
    s.next()
    const negate = s.match('minus')
    if (negate) s.next()
    const numTok = s.expect('number')
    const factor = (negate ? -1 : 1) * Number(numTok.value)
    if (!Number.isFinite(factor)) {
      throw new CompositionParseError(`invalid scalar '${numTok.value}'`, numTok.pos)
    }
    if (left.kind === 'scaled') {
      return { kind: 'scaled', operand: left.operand, factor: left.factor * factor }
    }
    return { kind: 'scaled', operand: left, factor }
  }
  return left
}

function negate(ast: CompositionAst): CompositionAst {
  if (ast.kind === 'scaled') {
    return { kind: 'scaled', operand: ast.operand, factor: -ast.factor }
  }
  return { kind: 'scaled', operand: ast, factor: -1 }
}

function parseSum(s: TokenStream): CompositionAst {
  const acc = parseTerm(s)
  const operands: CompositionAst[] = [acc]
  while (s.match('plus') || s.match('minus')) {
    const op = s.next()
    const next = parseTerm(s)
    operands.push(op.kind === 'minus' ? negate(next) : next)
  }
  if (operands.length === 1) return acc
  return { kind: 'sum', operands }
}

function parseLayerSpec(s: TokenStream): LayerSpec {
  if (s.match('ident', 'all')) { s.next(); return { all: true } }
  // L<n>..L<m> form
  if (s.match('ident') && /^L\d+$/.test(s.peek().value)) {
    const lo = Number(s.next().value.slice(1))
    s.expect('dotdot')
    const hiTok = s.expect('ident')
    if (!/^L\d+$/.test(hiTok.value)) {
      throw new CompositionParseError(`expected layer name like L20, got '${hiTok.value}'`, hiTok.pos)
    }
    const hi = Number(hiTok.value.slice(1))
    return { range: [lo, hi] }
  }
  if (s.match('number')) {
    const n = Number(s.next().value)
    return { layer: n }
  }
  const t = s.peek()
  throw new CompositionParseError(`expected layer spec, got ${t.kind} '${t.value}'`, t.pos)
}

function parseExpression(s: TokenStream): CompositionAst {
  let result: CompositionAst = parseSum(s)
  if (s.match('at')) {
    s.next()
    const layers = parseLayerSpec(s)
    result = { kind: 'layered', operand: result, layers }
  }
  if (s.match('pipe')) {
    s.next()
    const kw = s.expect('ident')
    if (kw.value === 'when') {
      const predicate = parseAffectPredicate(s)
      result = { kind: 'modulated', operand: result, predicate }
    } else if (kw.value === 'scaled_by') {
      s.expect('lparen')
      const expression = parseAffectExpr(s)
      s.expect('rparen')
      result = { kind: 'scaledModulated', operand: result, expression }
    } else {
      throw new CompositionParseError(`expected 'when' or 'scaled_by' after '|', got '${kw.value}'`, kw.pos)
    }
  }
  return result
}

/**
 * Parse the optional B2.2 postfix `with retrieval(<mode>[, <strength>])`.
 *
 *   <mode> ∈ { consonant, complementary }
 *   <strength> ∈ [0, 1] (numeric, default 0.3)
 *
 * Returns null if no `with` keyword is present at the current position.
 * Throws a CompositionParseError on malformed clauses.
 */
function parseRetrievalPostfix(s: TokenStream): import('./types.js').RetrievalPolicySpec | null {
  if (!s.match('ident', 'with')) return null
  s.next()
  const fnTok = s.expect('ident', 'retrieval')
  s.expect('lparen')
  const modeTok = s.expect('ident')
  if (modeTok.value !== 'consonant' && modeTok.value !== 'complementary') {
    throw new CompositionParseError(
      `expected 'consonant' or 'complementary' for retrieval mode, got '${modeTok.value}'`,
      modeTok.pos,
    )
  }
  let strength = 0.3
  if (s.match('comma')) {
    s.next()
    const numTok = s.expect('number')
    const parsed = Number(numTok.value)
    if (!Number.isFinite(parsed) || parsed < 0 || parsed > 1) {
      throw new CompositionParseError(
        `retrieval strength must be in [0,1], got ${numTok.value}`,
        numTok.pos,
      )
    }
    strength = parsed
  }
  s.expect('rparen')
  void fnTok
  return { mode: modeTok.value as 'consonant' | 'complementary', strength }
}

function parseAffectPredicate(s: TokenStream): AffectPredicate {
  let left = parseAffectComparison(s)
  while (s.match('ident', 'and') || s.match('ident', 'or')) {
    const op = s.next().value as 'and' | 'or'
    const right = parseAffectComparison(s)
    if (left.kind === op) {
      left.preds.push(right)
    } else {
      left = { kind: op, preds: [left, right] }
    }
  }
  return left
}

function parseAffectComparison(s: TokenStream): AffectPredicate {
  if (s.match('lparen')) {
    s.next()
    const inner = parseAffectPredicate(s)
    s.expect('rparen')
    return inner
  }
  const tok = s.expect('ident')
  if (tok.value === 'valence' || tok.value === 'arousal') {
    const opTok = s.next()
    let op: '<' | '>' | '~'
    if (opTok.kind === 'lt') op = '<'
    else if (opTok.kind === 'gt') op = '>'
    else if (opTok.kind === 'approx') op = '~'
    else throw new CompositionParseError(`expected '<', '>', or '~', got ${opTok.kind} '${opTok.value}'`, opTok.pos)
    const negate = s.match('minus')
    if (negate) s.next()
    const numTok = s.expect('number')
    const threshold = (negate ? -1 : 1) * Number(numTok.value)
    if (!Number.isFinite(threshold)) {
      throw new CompositionParseError(`invalid threshold '${numTok.value}'`, numTok.pos)
    }
    return { kind: tok.value, op, threshold }
  }
  if (tok.value === 'label') {
    s.expect('eqeq')
    const labelTok = s.expect('string')
    if (!AFFECT_LABELS.has(labelTok.value as AffectLabel)) {
      throw new CompositionParseError(`unknown affect label '${labelTok.value}'`, labelTok.pos)
    }
    return { kind: 'label', equals: labelTok.value as AffectLabel }
  }
  throw new CompositionParseError(`expected 'valence', 'arousal', or 'label', got '${tok.value}'`, tok.pos)
}

function parseAffectExpr(s: TokenStream): AffectExpr {
  let left = parseAffectTerm(s)
  while (s.match('plus') || s.match('minus')) {
    const op = s.next().kind === 'minus' ? 'sub' : 'add'
    const right = parseAffectTerm(s)
    left = { kind: op, left, right } as AffectExpr
  }
  return left
}

function parseAffectTerm(s: TokenStream): AffectExpr {
  if (s.match('lparen')) {
    s.next()
    const inner = parseAffectExpr(s)
    s.expect('rparen')
    return inner
  }
  if (s.match('number')) {
    return { kind: 'number', value: Number(s.next().value) }
  }
  if (s.match('minus')) {
    s.next()
    const inner = parseAffectTerm(s)
    return { kind: 'sub', left: { kind: 'number', value: 0 }, right: inner }
  }
  const t = s.expect('ident')
  if (t.value !== 'valence' && t.value !== 'arousal') {
    throw new CompositionParseError(`expected number, 'valence', or 'arousal', got '${t.value}'`, t.pos)
  }
  return { kind: 'var', name: t.value }
}

export interface ParseResult {
  name: string | null
  ast: CompositionAst
  layerPolicy: string
  /** B2.2: optional retrieval policy from the `with retrieval(...)` postfix. */
  retrievalPolicy: import('./types.js').RetrievalPolicySpec | null
}

/**
 * Parse a definition `name = expr` or a bare expression.
 * Returns `name: null` for a bare expression.
 */
export function parseComposition(src: string): ParseResult {
  const tokens = tokenize(src)
  const stream = new TokenStream(tokens)
  let name: string | null = null
  if (stream.peek().kind === 'ident' && stream.peek(1).kind === 'eq') {
    name = stream.next().value
    stream.next()
  }
  const ast = parseExpression(stream)
  const retrievalPolicy = parseRetrievalPostfix(stream)
  if (!stream.match('eof')) {
    const t = stream.peek()
    throw new CompositionParseError(`unexpected trailing token ${t.kind} '${t.value}'`, t.pos)
  }
  const layerPolicy = ast.kind === 'layered' ? layerSpecToString(ast.layers) : 'all'
  return { name, ast, layerPolicy, retrievalPolicy }
}

export function layerSpecToString(spec: LayerSpec): string {
  if ('all' in spec) return 'all'
  if ('range' in spec) return `L${spec.range[0]}..L${spec.range[1]}`
  return `L${spec.layer}`
}

/**
 * Welfare guard (Section 10.2 #2): walk the AST and report whether any
 * suppressive-affect label is subtracted (negative scalar). Suppressive
 * compositions require explicit operator opt-in.
 */
import { SUPPRESSIVE_AFFECT_LABELS } from './types.js'

export function detectSuppressive(ast: CompositionAst, sign = 1): boolean {
  switch (ast.kind) {
    case 'affect':
      return sign < 0 && SUPPRESSIVE_AFFECT_LABELS.has(ast.label)
    case 'gate':
      return sign < 0 && SUPPRESSIVE_AFFECT_LABELS.has(ast.label as AffectLabel)
    case 'reference':
    case 'live':
      return false
    case 'scaled':
      return detectSuppressive(ast.operand, sign * Math.sign(ast.factor || 1))
    case 'sum':
      return ast.operands.some(o => detectSuppressive(o, sign))
    case 'layered':
    case 'modulated':
    case 'scaledModulated':
      return detectSuppressive(ast.operand, sign)
  }
}
