/**
 * QUARANTINED — exercises modules excluded from / deferred at P7.
 *
 * These two smoke cases were part of the original tests/provider-interface-
 * compliance.test.ts but reference modules that are NOT in the P7 providers
 * package:
 *   - `@cassicore/ai`      → the whole `ai/` tree stays in D: until P8
 *                            (`@cassicore/ai`). P8-deferred.
 *   - `qwen-coder.js`      → DEAD module (excluded per P7 table §1g/§2.E).
 *
 * Quarantined to tests/host-wired/ so the live compliance file stays green.
 * Revive / re-point these cases when @cassicore/ai lands (P8) or a qwen-coder
 * replacement ships. Assertions are UNCHANGED (never weakened).
 */
describe('Real Provider Interface Compliance (Smoke Tests)', () => {
  it('QwenProvider implements IProvider with the correct interface shape', async () => {
    const { QwenProvider } = await import('@cassicore/ai')
    const provider = new QwenProvider('test-api-key')

    expect(provider.id).toBe('qwen')
    expect(Array.isArray(provider.models)).toBe(true)
    expect(typeof provider.complete).toBe('function')
    expect(typeof provider.countTokens).toBe('function')
    expect(typeof provider.ping).toBe('function')
  })

  it('QwenCoderProvider implements IProvider with the correct interface shape', async () => {
    const { QwenCoderProvider } = await import('../core/providers/qwen-coder.js')
    const provider = new QwenCoderProvider({
      apiKey: 'test-api-key',
      model: 'qwen2.5-coder-14b',
    })

    expect(provider.id).toBe('qwen-coder')
    expect(Array.isArray(provider.models)).toBe(true)
    expect(typeof provider.complete).toBe('function')
    expect(typeof provider.countTokens).toBe('function')
    expect(typeof provider.ping).toBe('function')
  })
})
