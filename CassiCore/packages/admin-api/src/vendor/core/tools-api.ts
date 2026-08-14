import { spawn } from "node:child_process"
import fs from "node:fs"
import path from "node:path"

import type { ILogger } from "@cassicore/foundation"
import type http from "node:http"

export function createToolsApi(logger: ILogger) {
  function sendJSON(res: http.ServerResponse, code: number, obj: unknown) {
    const s = JSON.stringify(obj)
    res.writeHead(code, { "Content-Type": "application/json" })
    res.end(s)
  }

  function parseBody(req: http.IncomingMessage): Promise<any> {
    return new Promise((resolve, reject) => {
      const chunks: Buffer[] = []
      req.on("data", (c) => chunks.push(Buffer.from(c)))
      req.on("end", () => {
        if (chunks.length === 0) return resolve(undefined)
        try {
          const s = Buffer.concat(chunks).toString("utf8")
          resolve(JSON.parse(s))
        } catch (err) {
          reject(err)
        }
      })
      req.on("error", reject)
    })
  }

  const MAX_OUTPUT = 1024 * 1024  // 1MB

  async function handleBash(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    if (req.method !== "POST") {
      return sendJSON(res, 405, { error: "Method not allowed" })
    }

    let body: { command?: string; cwd?: string; timeout?: number }
    try { body = await parseBody(req) } catch (err) {
      return sendJSON(res, 400, { error: "Invalid JSON" })
    }

    const command = body.command
    if (!command) {
      return sendJSON(res, 400, { error: "Missing required field: command" })
    }

    const cwd = body.cwd ?? process.cwd()
    const timeout = Math.min(body.timeout ?? 30000, 120000)
    let output = ""
    let killed = false

    const proc = spawn("bash", ["-c", command], {
      cwd,
      env: { ...process.env, HOME: process.env.HOME ?? "/home/valerie" },
    })

    const killTimer = setTimeout(() => {
      killed = true
      proc.kill("SIGTERM")
      setTimeout(() => proc.kill("SIGKILL"), 5000)
    }, timeout)

    proc.stdout.on("data", (d: Buffer) => {
      output += d.toString()
      if (output.length > MAX_OUTPUT) output = `${output.slice(0, MAX_OUTPUT)  }\n[output truncated]`
    })
    proc.stderr.on("data", (d: Buffer) => {
      output += d.toString()
      if (output.length > MAX_OUTPUT) output = `${output.slice(0, MAX_OUTPUT)  }\n[output truncated]`
    })

    proc.on("close", (code) => {
      clearTimeout(killTimer)
      sendJSON(res, 200, {
        output: killed ? `[timed out after ${timeout}ms]\n${output}` : (output || "(no output)"),
        exitCode: killed ? null : code,
        truncated: output.includes("[output truncated]"),
      })
    })
    proc.on("error", (err) => {
      clearTimeout(killTimer)
      sendJSON(res, 500, { error: String(err) })
    })
  }

  async function handleRead(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    if (req.method !== "GET") return sendJSON(res, 405, { error: "Method not allowed" })
    const url = new URL(req.url || "", "http://localhost")
    const filePath = url.searchParams.get("path")
    if (!filePath) return sendJSON(res, 400, { error: "Missing required parameter: path" })
    try {
      const absolutePath = path.isAbsolute(filePath) ? filePath : path.join(process.cwd(), filePath)
      const content = await fs.promises.readFile(absolutePath, "utf8")
      const stats = await fs.promises.stat(absolutePath)
      sendJSON(res, 200, { content, size: stats.size, exists: true, isFile: stats.isFile() })
    } catch (err: any) {
      sendJSON(res, 404, { error: err.message, exists: false })
    }
  }

  async function handleWrite(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    if (req.method !== "POST") return sendJSON(res, 405, { error: "Method not allowed" })
    let body: { path?: string; content?: string }
    try { body = await parseBody(req) } catch (err) {
      return sendJSON(res, 400, { error: "Invalid JSON" })
    }
    if (!body.path) return sendJSON(res, 400, { error: "Missing required field: path" })
    if (body.content === undefined) return sendJSON(res, 400, { error: "Missing required field: content" })
    try {
      const absolutePath = path.isAbsolute(body.path) ? body.path : path.join(process.cwd(), body.path)
      await fs.promises.mkdir(path.dirname(absolutePath), { recursive: true })
      await fs.promises.writeFile(absolutePath, body.content, "utf8")
      sendJSON(res, 200, { success: true, bytesWritten: Buffer.byteLength(body.content, "utf8"), path: absolutePath })
    } catch (err: any) {
      sendJSON(res, 500, { error: err.message })
    }
  }

  async function handleExists(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    if (req.method !== "GET") return sendJSON(res, 405, { error: "Method not allowed" })
    const url = new URL(req.url || "", "http://localhost")
    const filePath = url.searchParams.get("path")
    if (!filePath) return sendJSON(res, 400, { error: "Missing required parameter: path" })
    try {
      const absolutePath = path.isAbsolute(filePath) ? filePath : path.join(process.cwd(), filePath)
      const exists = await fs.promises.access(absolutePath).then(() => true).catch(() => false)
      const stats = exists ? await fs.promises.stat(absolutePath) : null
      sendJSON(res, 200, { exists, isFile: stats?.isFile() ?? false, isDirectory: stats?.isDirectory() ?? false, path: absolutePath })
    } catch (err: any) {
      sendJSON(res, 200, { exists: false, isFile: false, isDirectory: false, error: err.message })
    }
  }

  async function handleMkdir(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    if (req.method !== "POST") return sendJSON(res, 405, { error: "Method not allowed" })
    let body: { path?: string }
    try { body = await parseBody(req) } catch (err) {
      return sendJSON(res, 400, { error: "Invalid JSON" })
    }
    if (!body.path) return sendJSON(res, 400, { error: "Missing required field: path" })
    try {
      const absolutePath = path.isAbsolute(body.path) ? body.path : path.join(process.cwd(), body.path)
      await fs.promises.mkdir(absolutePath, { recursive: true })
      sendJSON(res, 200, { success: true, path: absolutePath })
    } catch (err: any) {
      sendJSON(res, 500, { error: err.message })
    }
  }

  async function handleDelete(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    if (req.method !== "DELETE") return sendJSON(res, 405, { error: "Method not allowed" })
    const url = new URL(req.url || "", "http://localhost")
    const filePath = url.searchParams.get("path")
    if (!filePath) return sendJSON(res, 400, { error: "Missing required parameter: path" })
    try {
      const absolutePath = path.isAbsolute(filePath) ? filePath : path.join(process.cwd(), filePath)
      await fs.promises.rm(absolutePath, { recursive: true, force: true })
      sendJSON(res, 200, { success: true, path: absolutePath })
    } catch (err: any) {
      sendJSON(res, 500, { error: err.message })
    }
  }

  const handler = async (req: http.IncomingMessage, res: http.ServerResponse): Promise<void> => {
    const url = new URL(req.url || "", "http://localhost")
    const parts = url.pathname.split("/").filter(Boolean)

    if (parts[0] === "tools" && parts[1] === "bash") return handleBash(req, res)
    if (parts[0] === "tools" && parts[1] === "read") return handleRead(req, res)
    if (parts[0] === "tools" && parts[1] === "write") return handleWrite(req, res)
    if (parts[0] === "tools" && parts[1] === "mkdir") return handleMkdir(req, res)
    if (parts[0] === "tools" && parts[1] === "delete") return handleDelete(req, res)
    if (parts[0] === "fs" && parts[1] === "exists") return handleExists(req, res)

    sendJSON(res, 404, { error: "Not found" })
  }

  return { handler }
}
