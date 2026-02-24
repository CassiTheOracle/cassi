#!/usr/bin/env node
// Minimal Serena MCP shim — exposes simple filesystem tools over the MCP stdio protocol
// Intended for local development and testing only.

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import fs from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';

function log(level, msg, data) {
  const timestamp = new Date().toISOString();
  console.error(JSON.stringify({ timestamp, level, msg, data }));
}

const server = new Server(
  { name: 'serena-mcp-server', version: '0.1.0' },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'create_text_file',
        description: 'Create or overwrite a UTF-8 text file',
        inputSchema: {
          type: 'object',
          properties: {
            filePath: { type: 'string', description: 'Absolute or relative file path' },
            content: { type: 'string', description: 'Text content to write' },
            encoding: { type: 'string', description: 'Encoding', default: 'utf8' },
          },
          required: ['filePath', 'content'],
        },
      },
      {
        name: 'write_file',
        description: 'Write a file (alias for create_text_file)',
        inputSchema: {
          type: 'object',
          properties: {
            filePath: { type: 'string' },
            content: { type: 'string' },
          },
          required: ['filePath', 'content'],
        },
      },
      {
        name: 'read_file',
        description: 'Read a UTF-8 text file',
        inputSchema: {
          type: 'object',
          properties: {
            filePath: { type: 'string' },
            encoding: { type: 'string', default: 'utf8' },
          },
          required: ['filePath'],
        },
      },
      {
        name: 'exists',
        description: 'Check whether a file or directory exists',
        inputSchema: {
          type: 'object',
          properties: { filePath: { type: 'string' } },
          required: ['filePath'],
        },
      },
      {
        name: 'mkdir',
        description: 'Create a directory (recursive)',
        inputSchema: {
          type: 'object',
          properties: { dirPath: { type: 'string' } },
          required: ['dirPath'],
        },
      },
      {
        name: 'delete',
        description: 'Delete a file',
        inputSchema: {
          type: 'object',
          properties: { filePath: { type: 'string' } },
          required: ['filePath'],
        },
      },
      {
        name: 'list_dir',
        description: 'List directory contents',
        inputSchema: {
          type: 'object',
          properties: { dirPath: { type: 'string' } },
          required: ['dirPath'],
        },
      },
    ],
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  log('info', 'tool-call', { tool: name, args });

  try {
    switch (name) {
      case 'create_text_file':
      case 'write_file': {
        const filePath = String(args?.filePath || '');
        const content = String(args?.content || '');
        if (!filePath) throw new Error('filePath required');
        const dir = path.dirname(filePath);
        if (dir && dir !== '.') await fs.mkdir(dir, { recursive: true });
        await fs.writeFile(filePath, content, { encoding: 'utf8' });
        return {
          content: [ { type: 'text', text: JSON.stringify({ success: true, filePath }) } ]
        };
      }

      case 'read_file': {
        const filePath = String(args?.filePath || '');
        if (!filePath) throw new Error('filePath required');
        const data = await fs.readFile(filePath, { encoding: 'utf8' });
        return {
          content: [ { type: 'text', text: data } ]
        };
      }

      case 'exists': {
        const filePath = String(args?.filePath || '');
        if (!filePath) throw new Error('filePath required');
        const ok = existsSync(filePath);
        return { content: [ { type: 'text', text: JSON.stringify({ exists: ok }) } ] };
      }

      case 'mkdir': {
        const dirPath = String(args?.dirPath || '');
        if (!dirPath) throw new Error('dirPath required');
        await fs.mkdir(dirPath, { recursive: true });
        return { content: [ { type: 'text', text: JSON.stringify({ created: true, dirPath }) } ] };
      }

      case 'delete': {
        const filePath = String(args?.filePath || '');
        if (!filePath) throw new Error('filePath required');
        await fs.unlink(filePath).catch(() => {});
        return { content: [ { type: 'text', text: JSON.stringify({ deleted: true, filePath }) } ] };
      }

      case 'list_dir': {
        const dirPath = String(args?.dirPath || '.');
        const entries = await fs.readdir(dirPath, { withFileTypes: true });
        const out = entries.map(e => ({ name: e.name, isDirectory: e.isDirectory() }));
        return { content: [ { type: 'text', text: JSON.stringify(out, null, 2) } ] };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (err) {
    const message = String(err instanceof Error ? err.message : err);
    log('error', 'tool-failed', { tool: name, error: message });
    return { content: [ { type: 'text', text: JSON.stringify({ error: message }) } ], isError: true };
  }
});

async function main() {
  log('info', 'serena-mcp starting');
  const transport = new StdioServerTransport();
  await server.connect(transport);
  log('info', 'serena-mcp connected');
}

main().catch((err) => {
  log('error', 'server-failed', { error: String(err) });
  process.exit(1);
});
