// Shared Telegram helpers for workers/channels/telegram.ts

export interface ImageAttachment {
  data: string
  mediaType: 'image/jpeg' | 'image/png' | 'image/gif' | 'image/webp'
  label?: string
}

let TOKEN = ''

export function setToken(token: string) {
  TOKEN = token || ''
}

function apiUrl(method: string): string {
  return `https://api.telegram.org/bot${TOKEN}/${method}`
}

export async function tgCall<T>(method: string, body?: Record<string, unknown>, timeoutMs = 15_000): Promise<T | null> {
  const ac = new AbortController()
  const timer = setTimeout(() => ac.abort(), timeoutMs)
  try {
    const res = await fetch(apiUrl(method), {
      method: body ? 'POST' : 'GET',
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
      signal: ac.signal,
    })
    clearTimeout(timer)
    const json = await res.json() as { ok: boolean; result: T; description?: string }
    if (!json.ok) {
      // caller should handle logging
      console.warn(`[telegram-common] tg/${method} not ok: ${json.description ?? '?'} `)
      return null
    }
    return json.result
  } catch (err) {
    clearTimeout(timer)
    // Silently swallow AbortError/TimeoutError
    if (err instanceof Error && (err.name === 'AbortError' || err.name === 'TimeoutError')) return null
    console.warn(`[telegram-common] tg/${method} error: ${String(err)}`)
    return null
  }
}

export function sanitizeMarkdown(text: string): string {
  return text.replace(/([_*\[\]\(\)~`>#+\-=|{}.!])/g, '\\$1')
}

export async function sendMessage(chatId: number, text: string, parseMode?: 'MarkdownV2' | 'HTML'): Promise<number | null> {
  const safeText = parseMode === 'HTML' ? (text || '…') : sanitizeMarkdown(text || '…')
  const result = await tgCall<{ message_id: number }>('sendMessage', {
    chat_id: chatId,
    text: safeText,
    parse_mode: parseMode || 'MarkdownV2',
  })
  return result?.message_id ?? null
}

export async function editMessage(chatId: number, msgId: number, text: string): Promise<boolean> {
  const safeText = sanitizeMarkdown(text || '…')
  const result = await tgCall('editMessageText', {
    chat_id: chatId,
    message_id: msgId,
    text: safeText,
    parse_mode: 'MarkdownV2',
  })
  return result !== null
}

export async function sendTyping(chatId: number): Promise<void> {
  await tgCall('sendChatAction', { chat_id: chatId, action: 'typing' })
}

interface FileInfoResult { file_path?: string }

export async function downloadPhoto(fileId: string): Promise<ImageAttachment | null> {
  try {
    const fileInfo = await tgCall<FileInfoResult>('getFile', { file_id: fileId })
    if (!fileInfo?.file_path) return null

    const fileUrl = `https://api.telegram.org/file/bot${TOKEN}/${fileInfo.file_path}`
    const photoAc = new AbortController()
    const photoTimer = setTimeout(() => photoAc.abort(), 20_000)
    const res = await fetch(fileUrl, { signal: photoAc.signal })
    clearTimeout(photoTimer)
    if (!res.ok) return null

    const buf = await res.arrayBuffer()
    const base64 = Buffer.from(buf).toString('base64')

    const ext = fileInfo.file_path.split('.').pop()?.toLowerCase() ?? ''
    const mediaType: ImageAttachment['mediaType'] =
      ext === 'png'  ? 'image/png'  :
      ext === 'gif'  ? 'image/gif'  :
      ext === 'webp' ? 'image/webp' :
      'image/jpeg'

    return { data: base64, mediaType, label: fileId }
  } catch (err) {
    return null
  }
}
