import { access, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const Q4_MODEL = process.env.CASSI_QWEN_Q4_MODEL ?? resolve(process.cwd(), 'Qwen3.8-27B-Q4_K_M.gguf')
const Q6_MODEL = process.env.CASSI_QWEN_Q6_MODEL ?? resolve(process.cwd(), 'Qwen3.8-27B-Q6_K.gguf')
const OUTPUT = resolve(process.cwd(), 'q4-q6-escalation.json')

const BOARD = [
  { id: 'arithmetic', prompt: 'What is 17 multiplied by 6? Reply with only the integer.', validate: (text) => text.trim() === '102' },
  { id: 'modular', prompt: 'What is the remainder when 7 to the power of 4 is divided by 10? Reply with only the integer.', validate: (text) => text.trim() === '1' },
  { id: 'sequence', prompt: 'Complete the sequence: 2, 6, 12, 20, 30, ?. Reply with only the integer.', validate: (text) => text.trim() === '42' },
  { id: 'logic', prompt: 'Nora is older than Ivo. Ivo is older than Pia. Who is youngest? Reply with only the name.', validate: (text) => text.trim() === 'Pia' },
  { id: 'json', prompt: 'Return exactly this JSON object and nothing else: {"cassi":true,"rungs":3}', validate: (text) => { try { return JSON.stringify(JSON.parse(text)) === '{"cassi":true,"rungs":3}' } catch { return false } } },
  { id: 'loopback', prompt: 'In one sentence, define a loopback network address and include the common IPv4 address.', validate: (text) => text.includes('127.0.0.1') },
]

async function exists(path) {
  try { await access(path); return true } catch { return false }
}

const q4Present = await exists(Q4_MODEL)
const q6Present = await exists(Q6_MODEL)
const report = {
  protocol: 'CassiQwen L13 Q4-to-Q6 escalation receipt',
  q4Model: Q4_MODEL,
  q6Model: Q6_MODEL,
  q4Present,
  q6Present,
  verdict: q6Present ? 'READY-TO-RUN' : 'BLOCKED-PREREQUISITE',
  reason: q6Present ? null : 'No same-model Q6 GGUF is present; no Q4/Q6 behavioral comparison was run.',
  boardSize: BOARD.length,
}
await writeFile(OUTPUT, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
if (!q6Present) process.exitCode = 2
