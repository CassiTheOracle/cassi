/**
 * run_tests — Narrow-scope test runner tool for triad members.
 *
 * Runs vitest on specified test paths and returns structured JSON results.
 * This tool is intentionally limited: it only runs vitest with fixed arguments
 * in the project root. No arbitrary command execution.
 *
 * Designed to be safe for the Critic to use — it's a verification/read operation
 * even though it executes a subprocess.
 */

import type { ToolDefinition, ToolHandler } from '../types.js'

export const runTestsDefinition: ToolDefinition = {
  name: 'run_tests',
  description:
    'Run vitest tests on specified file paths and return structured results. ' +
    'Returns JSON with pass/fail counts, individual test results, and any error output. ' +
    'Use this to verify that generated or modified code actually works.',
  parameters: {
    type: 'object',
    properties: {
      testPath: {
        type: 'string',
        description:
          'Path to the test file or glob pattern (e.g., "tests/my.test.ts" or "tests/triad-*.test.ts"). ' +
          'Relative to project root.',
      },
      timeout: {
        type: 'number',
        description: 'Timeout in seconds (default: 60, max: 120).',
      },
    },
    required: ['testPath'],
  },
  timeoutMs: 130_000,
  readOnly: true,
}

export interface TestRunResult {
  success: boolean
  passed: number
  failed: number
  total: number
  duration: number
  testFiles: Array<{
    file: string
    passed: number
    failed: number
    tests: Array<{
      name: string
      status: 'pass' | 'fail' | 'skip'
      duration: number
      error?: string
    }>
  }>
  /** Raw stderr/stdout if parsing fails */
  rawOutput?: string
}

export const runTestsHandler: ToolHandler = async (input, ctx) => {
  const testPath = input['testPath'] as string
  const timeoutSec = Math.min(Math.max((input['timeout'] as number) ?? 60, 5), 120)

  if (!testPath || typeof testPath !== 'string') {
    return JSON.stringify({ success: false, error: 'testPath is required' })
  }

  // Sanitize: prevent command injection
  if (testPath.includes(';') || testPath.includes('&&') || testPath.includes('|') ||
      testPath.includes('`') || testPath.includes('$')) {
    return JSON.stringify({ success: false, error: 'Invalid characters in testPath' })
  }

  const workdir = ctx.workingDir
  const { spawn } = await import('node:child_process')
  const { existsSync, statSync } = await import('node:fs')
  const { resolve } = await import('node:path')

  try {
    // Resolve and validate the test path to provide better diagnostics
    const resolvedPath = resolve(workdir, testPath)
    let effectiveTestPath = testPath

    // If testPath is a directory, vitest won't match it as a filename filter.
    // Convert to a path that vitest can use for file matching.
    if (existsSync(resolvedPath) && statSync(resolvedPath).isDirectory()) {
      // vitest uses the argument as a filename filter regex, not a glob.
      // Pass the directory path as-is — vitest will match any test file
      // whose path contains this string.
      effectiveTestPath = testPath.replace(/\/+$/, '')
    }

    const result = await new Promise<{ stdout: string; stderr: string; exitCode: number }>((resolve) => {
      let stdout = ''
      let stderr = ''

      // Run vitest with JSON reporter for structured output.
      // Use shell: true so glob patterns like tests/**/*.test.ts are expanded.
      const cmd = `npx vitest run ${JSON.stringify(effectiveTestPath)} --reporter=json --no-color`
      const proc = spawn(cmd, [], {
        cwd: workdir,
        env: { ...process.env, FORCE_COLOR: '0' },
        shell: true,
      })

      const timer = setTimeout(() => {
        proc.kill('SIGTERM')
        setTimeout(() => proc.kill('SIGKILL'), 5000)
      }, timeoutSec * 1000)

      proc.stdout.on('data', (d: Buffer) => { stdout += d.toString() })
      proc.stderr.on('data', (d: Buffer) => { stderr += d.toString() })
      proc.on('close', (code) => {
        clearTimeout(timer)
        resolve({ stdout, stderr, exitCode: code ?? 1 })
      })
      proc.on('error', (err) => {
        clearTimeout(timer)
        resolve({ stdout, stderr: stderr + '\n' + String(err), exitCode: 1 })
      })
    })

    // Try to parse vitest JSON output
    const parsed = parseVitestJson(result.stdout, result.stderr, result.exitCode)

    // Add diagnostic info when 0 tests are found
    if (parsed.total === 0) {
      parsed.rawOutput = (parsed.rawOutput || '') +
        `\n\nDiagnostic: 0 tests matched for path "${effectiveTestPath}" in ${workdir}. ` +
        `Ensure the path matches a test file (e.g., "tests/my-feature.test.ts") ` +
        `or a directory containing tests (e.g., "tests/flux-team").`
    }

    return JSON.stringify(parsed, null, 2)
  } catch (err) {
    return JSON.stringify({
      success: false,
      passed: 0,
      failed: 0,
      total: 0,
      duration: 0,
      testFiles: [],
      rawOutput: `Error running tests: ${String(err)}`,
    } satisfies TestRunResult)
  }
}

/**
 * Parse vitest JSON reporter output into structured TestRunResult.
 */
function parseVitestJson(stdout: string, stderr: string, exitCode: number): TestRunResult {
  // vitest --reporter=json outputs JSON to stdout
  // Try to extract JSON from stdout (there may be non-JSON preamble)
  let jsonData: any = null

  // Find the JSON object in stdout
  const jsonStart = stdout.indexOf('{')
  if (jsonStart >= 0) {
    try {
      jsonData = JSON.parse(stdout.slice(jsonStart))
    } catch {
      // Try to find the last complete JSON object
      const lastBrace = stdout.lastIndexOf('}')
      if (lastBrace > jsonStart) {
        try {
          jsonData = JSON.parse(stdout.slice(jsonStart, lastBrace + 1))
        } catch {
          // Fall through to raw output
        }
      }
    }
  }

  if (jsonData && jsonData.testResults) {
    // vitest JSON format
    let passed = 0
    let failed = 0
    let total = 0
    const testFiles: TestRunResult['testFiles'] = []

    for (const file of jsonData.testResults) {
      const fileResult: TestRunResult['testFiles'][0] = {
        file: file.name || file.file || 'unknown',
        passed: 0,
        failed: 0,
        tests: [],
      }

      const suites = file.assertionResults || file.testResults || []
      for (const test of suites) {
        const status = test.status === 'passed' ? 'pass' as const
          : test.status === 'failed' ? 'fail' as const
          : 'skip' as const

        if (status === 'pass') { passed++; fileResult.passed++ }
        else if (status === 'fail') { failed++; fileResult.failed++ }
        total++

        fileResult.tests.push({
          name: test.fullName || test.title || test.ancestorTitles?.join(' > ') || 'unnamed',
          status,
          duration: test.duration || 0,
          error: test.failureMessages?.join('\n') || undefined,
        })
      }

      testFiles.push(fileResult)
    }

    return {
      success: failed === 0 && exitCode === 0,
      passed,
      failed,
      total,
      duration: jsonData.startTime
        ? Date.now() - jsonData.startTime
        : 0,
      testFiles,
    }
  }

  // Fallback: couldn't parse JSON — try to extract from verbose output
  return parseVerboseOutput(stdout, stderr, exitCode)
}

/**
 * Fallback parser for non-JSON vitest output.
 */
function parseVerboseOutput(stdout: string, stderr: string, exitCode: number): TestRunResult {
  const combined = stdout + '\n' + stderr
  const passMatch = combined.match(/(\d+)\s+passed/)
  const failMatch = combined.match(/(\d+)\s+failed/)
  const totalMatch = combined.match(/Tests\s+(\d+)/)

  const passed = passMatch ? parseInt(passMatch[1]) : 0
  const failed = failMatch ? parseInt(failMatch[1]) : 0
  const total = totalMatch ? parseInt(totalMatch[1]) : passed + failed

  return {
    success: failed === 0 && exitCode === 0,
    passed,
    failed,
    total,
    duration: 0,
    testFiles: [],
    rawOutput: combined.slice(0, 4000),
  }
}
