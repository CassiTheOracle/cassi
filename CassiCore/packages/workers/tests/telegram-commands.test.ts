import { beforeEach, describe, expect, it, vi } from 'vitest'

import { setMyCommands, setToken } from '../src/channels/telegram-common.js'

describe('Telegram command registration', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    setToken('12345:test-token')
  })

  it('calls Telegram setMyCommands with the provided command list', async () => {
    fetchMock.mockResolvedValue({
      json: async () => ({ ok: true, result: true }),
    })

    await setMyCommands([
      { command: 'cassi', description: 'MCP tools' },
      { command: 'confirm', description: 'Confirm execution' },
    ])

    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/setMyCommands')
    expect(init.method).toBe('POST')
    expect(init.body).toContain('"command":"cassi"')
    expect(init.body).toContain('"command":"confirm"')
  })
})
