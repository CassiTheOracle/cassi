#!/usr/bin/env node
// Serena MCP server — filesystem + TypeScript-powered semantic code tools
// Uses TypeScript Compiler API for accurate symbol extraction and will
// delegate heavier analyses to the SCIP MCP server when available.

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import fs from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import * as ts from 'typescript';

function log(level, msg, data) {
  const timestamp = new Date().toISOString();
  console.error(JSON.stringify({ timestamp, level, msg, data }));
}

// Config
const DEFAULT_IGNORE = new Set(['node_modules', '.git', 'dist', 'build', 'out']);
const CODE_EXTENSIONS = new Set(['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']);

async function walkFiles(root, opts = {}) {
  const ignore = opts.ignore ?? DEFAULT_IGNORE;
  const files = [];
  async function _walk(dir) {
    let entries = [];
    try { entries = await fs.readdir(dir, { withFileTypes: true }); } catch (e) { return }
    for (const e of entries) {
      if (e.name.startsWith('.') && ignore.has(e.name)) continue;
      if (ignore.has(e.name)) continue;
      const full = path.join(dir, e.name);
      if (e.isDirectory()) {
        await _walk(full);
      } else if (e.isFile()) {
        files.push(full);
      }
    }
  }
  await _walk(root);
  return files;
}

function escapeRegExp(s) { return s.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&'); }

function lineColFromIndex(text, index) {
  const prefix = text.slice(0, index);
  const lines = prefix.split('\n');
  return { line: lines.length, column: lines[lines.length - 1].length + 1 };
}

// If future fallback is needed: a safe brace matcher used when replacing bodies
function findMatchingBrace(content, openIndex) {
  let i = openIndex;
  const len = content.length;
  if (content[openIndex] !== '{') return -1;
  let depth = 1;
  i++;
  while (i < len) {
    const ch = content[i];
    if (ch === '"' || ch === "'" ) {
      const quote = ch;
      i++;
      while (i < len) {
        if (content[i] === '\\') { i += 2; continue }
        if (content[i] === quote) { i++; break }
        i++;
      }
      continue;
    }
    if (ch === '`') {
      i++;
      while (i < len) {
        if (content[i] === '\\') { i += 2; continue }
        if (content[i] === '`') { i++; break }
        i++;
      }
      continue;
    }
    if (ch === '/' && content[i+1] === '/') {
      i += 2; while (i < len && content[i] !== '\n') i++; continue;
    }
    if (ch === '/' && content[i+1] === '*') {
      i += 2; while (i < len && !(content[i] === '*' && content[i+1] === '/')) i++; i += 2; continue;
    }
    if (ch === '{') depth++;
    else if (ch === '}') { depth--; if (depth === 0) return i; }
    i++;
  }
  return -1;
}

// TypeScript-based symbol finder
function createSourceFile(filePath, content) {
  const ext = path.extname(filePath).toLowerCase();
  const isTsx = ext === '.tsx' || ext === '.jsx';
  const kind = (ext === '.ts' || ext === '.tsx') ? ts.ScriptKind.TS : ts.ScriptKind.JS;
  try {
    return ts.createSourceFile(filePath, content, ts.ScriptTarget.Latest, true, kind);
  } catch (e) {
    // fallback: parse as JS
    return ts.createSourceFile(filePath, content, ts.ScriptTarget.Latest, true, ts.ScriptKind.JS);
  }
}

function nodeName(n) {
  if (!n) return undefined;
  if (ts.isIdentifier(n)) return n.text;
  if ((n).name && ts.isIdentifier((n).name)) return (n).name.text;
  return undefined;
}

function findDeclarationsAndReferences(sourceFile, symbolName) {
  const decls = [];
  const refs = [];

  function visit(node) {
    // Declarations
    if ((ts.isFunctionDeclaration(node) || ts.isClassDeclaration(node) || ts.isInterfaceDeclaration(node) || ts.isEnumDeclaration(node) || ts.isTypeAliasDeclaration(node)) && node.name && node.name.text === symbolName) {
      decls.push({ node, kind: node.kind });
    }

    // Variable declarations (const Foo = function/arrow/class)
    if (ts.isVariableDeclaration(node) && node.name && ts.isIdentifier(node.name) && node.name.text === symbolName) {
      decls.push({ node, kind: node.kind });
    }

    // Assignment like exports.Foo = function... or Foo = function ...
    if (ts.isBinaryExpression(node) && node.operatorToken && node.operatorToken.kind === ts.SyntaxKind.EqualsToken) {
      try {
        if (ts.isIdentifier(node.left) && node.left.text === symbolName) {
          // treat assignment as potential declaration
          decls.push({ node, kind: node.kind });
        }
      } catch (e) {}
    }

    // References: identifiers that are not the name of a declaration
    if (ts.isIdentifier(node) && node.text === symbolName) {
      const parent = node.parent;
      let isDeclName = false;
      if (ts.isFunctionDeclaration(parent) || ts.isClassDeclaration(parent) || ts.isInterfaceDeclaration(parent) || ts.isEnumDeclaration(parent) || ts.isTypeAliasDeclaration(parent)) {
        if (parent.name === node) isDeclName = true;
      }
      if (ts.isVariableDeclaration(parent) && parent.name === node) isDeclName = true;
      if (!isDeclName) {
        refs.push(node);
      }
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return { decls, refs };
}

async function findSymbolAcrossRepoWithTS(repoRoot, symbolName, maxResults = 50) {
  const files = await walkFiles(repoRoot);
  const matches = [];
  for (const f of files) {
    const ext = path.extname(f).toLowerCase();
    if (!CODE_EXTENSIONS.has(ext)) continue;
    let content = '';
    try { content = await fs.readFile(f, 'utf8'); } catch (e) { continue }
    const sf = createSourceFile(f, content);
    const { decls, refs } = findDeclarationsAndReferences(sf, symbolName);
    if (decls.length > 0) {
      for (const d of decls) {
        const start = d.node.getStart(sf);
        const end = d.node.getEnd();
        const pos = lineColFromIndex(content, start);
        matches.push({ file: path.relative(process.cwd(), f), start, end, line: pos.line, column: pos.column, kind: 'definition', preview: content.slice(start, Math.min(start + 200, content.length)).split('\n')[0] });
        if (matches.length >= maxResults) break;
      }
      if (matches.length >= maxResults) break;
      continue;
    }
    if (refs.length > 0) {
      for (const r of refs) {
        const idx = r.getStart(sf);
        const pos = lineColFromIndex(content, idx);
        matches.push({ file: path.relative(process.cwd(), f), start: idx, end: idx + symbolName.length, line: pos.line, column: pos.column, kind: 'reference', preview: content.slice(Math.max(0, idx - 60), Math.min(content.length, idx + 60)).replace(/\n/g,'\\n') });
        if (matches.length >= maxResults) break;
      }
      if (matches.length >= maxResults) break;
    }
  }
  return matches;
}

async function readSymbolFromFileWithTS(filePath, symbolName) {
  const abs = path.isAbsolute(filePath) ? filePath : path.join(process.cwd(), filePath);
  let content;
  try { content = await fs.readFile(abs, 'utf8'); } catch (e) { throw new Error('file not found') }
  if (!symbolName) {
    return { file: path.relative(process.cwd(), abs), content };
  }
  const sf = createSourceFile(abs, content);
  const { decls } = findDeclarationsAndReferences(sf, symbolName);
  if (!decls || decls.length === 0) throw new Error('symbol not found in file');
  const d = decls[0].node;
  const start = d.getStart(sf);
  const end = d.getEnd();
  const snippet = content.slice(start, end);
  return { file: path.relative(process.cwd(), abs), start, end, snippet };
}

async function replaceSymbolBodyInFileWithTS(filePath, symbolName, newBody, options = { backup: true }) {
  const abs = path.isAbsolute(filePath) ? filePath : path.join(process.cwd(), filePath);
  let content;
  try { content = await fs.readFile(abs, 'utf8'); } catch (e) { throw new Error('file not found') }
  const sf = createSourceFile(abs, content);
  const { decls } = findDeclarationsAndReferences(sf, symbolName);
  if (!decls || decls.length === 0) throw new Error('symbol not found');
  const d = decls[0].node;

  // Attempt to find a block/body start using AST
  let bodyStart = -1;
  let bodyEnd = -1;
  if (d.body && d.body.pos !== undefined) {
    // function or method
    bodyStart = d.body.pos;
    bodyEnd = d.body.end;
  } else if (ts.isVariableDeclaration(d) && d.initializer) {
    // arrow function or function expression
    const init = d.initializer;
    if (init.kind === ts.SyntaxKind.ArrowFunction || init.kind === ts.SyntaxKind.FunctionExpression) {
      const ib = init.body;
      bodyStart = ib.pos;
      bodyEnd = ib.end;
    }
  } else if (d.kind === ts.SyntaxKind.BinaryExpression) {
    // assignment like Foo = function() { ... }
    const be = d;
    // fallback: find first '{' after start
    const idx = content.indexOf('{', d.getStart(sf));
    if (idx !== -1) {
      const close = findMatchingBrace(content, idx);
      if (close !== -1) {
        bodyStart = idx;
        bodyEnd = close + 1;
      }
    }
  }

  if (bodyStart === -1 || bodyEnd === -1) throw new Error('unable to locate body start/end for symbol');

  const before = content.slice(0, bodyStart);
  const after = content.slice(bodyEnd);
  const newInner = '\n' + newBody + '\n';
  const newBlock = '{' + newInner + '}';
  const newContent = before + newBlock + after;

  if (options.backup) await fs.writeFile(abs + '.serena.bak', content, 'utf8').catch(() => {});
  await fs.writeFile(abs, newContent, 'utf8');
  return { file: path.relative(process.cwd(), abs), replaced: true };
}

async function insertAfterSymbolInFileWithTS(filePath, symbolName, insertText) {
  const abs = path.isAbsolute(filePath) ? filePath : path.join(process.cwd(), filePath);
  let content;
  try { content = await fs.readFile(abs, 'utf8'); } catch (e) { throw new Error('file not found') }
  const sf = createSourceFile(abs, content);
  const { decls } = findDeclarationsAndReferences(sf, symbolName);
  if (!decls || decls.length === 0) throw new Error('symbol not found');
  const d = decls[0].node;
  const insertAt = d.getEnd();
  const newContent = content.slice(0, insertAt) + '\n' + insertText + '\n' + content.slice(insertAt);
  await fs.writeFile(abs + '.serena.bak', content, 'utf8').catch(() => {});
  await fs.writeFile(abs, newContent, 'utf8');
  return { file: path.relative(process.cwd(), abs), inserted: true, insertAt };
}

async function deleteSymbolFromFileWithTS(filePath, symbolName) {
  const abs = path.isAbsolute(filePath) ? filePath : path.join(process.cwd(), filePath);
  let content;
  try { content = await fs.readFile(abs, 'utf8'); } catch (e) { throw new Error('file not found') }
  const sf = createSourceFile(abs, content);
  const { decls } = findDeclarationsAndReferences(sf, symbolName);
  if (!decls || decls.length === 0) throw new Error('symbol not found');
  const d = decls[0].node;
  const newContent = content.slice(0, d.getStart(sf)) + content.slice(d.getEnd());
  await fs.writeFile(abs + '.serena.bak', content, 'utf8').catch(() => {});
  await fs.writeFile(abs, newContent, 'utf8');
  return { file: path.relative(process.cwd(), abs), deleted: true };
}

// SCIP client helper — lazily spawn a scip MCP server (tsx) and connect as MCP client.
let scipClient = null;
let scipConnected = false;
let scipConnecting = false;

async function ensureScipClient() {
  if (scipConnected) return scipClient;
  if (scipConnecting) {
    // wait until established (simple spin-wait)
    for (let i = 0; i < 60; i++) {
      if (scipConnected) return scipClient;
      await new Promise(r => setTimeout(r, 200));
    }
    throw new Error('SCIP client connection timed out');
  }

  scipConnecting = true;
  try {
    const transport = new StdioClientTransport({
      // try to run TypeScript implementation via npx tsx
      command: 'npx',
      args: ['tsx', path.join(process.cwd(), 'mcp', 'scip-server.ts')],
      env: process.env,
    });
    const client = new Client({ name: 'serena-scipshim', version: '0.0.1' });
    await client.connect(transport);
    scipClient = client;
    scipConnected = true;
    log('info', 'scip-client connected');
    return scipClient;
  } catch (err) {
    log('warn', 'failed to start scip server via tsx', { error: String(err) });
    scipConnecting = false;
    scipConnected = false;
    scipClient = null;
    throw err;
  }
}

const server = new Server({ name: 'serena-mcp-server', version: '0.3.0' }, { capabilities: { tools: {} } });

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      { name: 'create_text_file', description: 'Create or overwrite a UTF-8 text file', inputSchema: { type: 'object', properties: { filePath: { type: 'string' }, content: { type: 'string' }, encoding: { type: 'string', default: 'utf8' } }, required: ['filePath','content'] } },
      { name: 'write_file', description: 'Alias for create_text_file', inputSchema: { type: 'object', properties: { filePath: { type: 'string' }, content: { type: 'string' } }, required: ['filePath','content'] } },
      { name: 'read_file', description: 'Read a UTF-8 text file', inputSchema: { type: 'object', properties: { filePath: { type: 'string' }, encoding: { type: 'string', default: 'utf8' } }, required: ['filePath'] } },
      { name: 'exists', description: 'Check whether a file or directory exists', inputSchema: { type: 'object', properties: { filePath: { type: 'string' } }, required: ['filePath'] } },
      { name: 'mkdir', description: 'Create a directory (recursive)', inputSchema: { type: 'object', properties: { dirPath: { type: 'string' } }, required: ['dirPath'] } },
      { name: 'delete', description: 'Delete a file', inputSchema: { type: 'object', properties: { filePath: { type: 'string' } }, required: ['filePath'] } },
      { name: 'list_dir', description: 'List directory contents', inputSchema: { type: 'object', properties: { dirPath: { type: 'string' } }, required: ['dirPath'] } },

      // Semantic tools (TypeScript-powered). MCP registry will prefix these as serena__*.
      { name: 'find_symbol', description: 'Find symbol definitions or references in the codebase', inputSchema: { type: 'object', properties: { symbolName: { type: 'string' }, maxResults: { type: 'number', default: 50 }, path: { type: 'string' } }, required: ['symbolName'] } },
      { name: 'find_referencing_symbols', description: 'Find all references to a symbol across the codebase', inputSchema: { type: 'object', properties: { symbolName: { type: 'string' }, path: { type: 'string' } }, required: ['symbolName'] } },
      { name: 'read_symbol', description: 'Read detailed symbol information (definition body)', inputSchema: { type: 'object', properties: { filePath: { type: 'string' }, symbolName: { type: 'string' } }, required: ['filePath'] } },
      { name: 'list_files', description: 'List files in the repository (code files by default)', inputSchema: { type: 'object', properties: { dirPath: { type: 'string' }, extensions: { type: 'array', items: { type: 'string' } } } } },
      { name: 'replace_symbol_body', description: 'Replace the body of a symbol in a file', inputSchema: { type: 'object', properties: { filePath: { type: 'string' }, symbolName: { type: 'string' }, newBody: { type: 'string' }, backup: { type: 'boolean' } }, required: ['filePath','symbolName','newBody'] } },
      { name: 'insert_after_symbol', description: 'Insert text after a given symbol definition in a file', inputSchema: { type: 'object', properties: { filePath: { type: 'string' }, symbolName: { type: 'string' }, insertText: { type: 'string' } }, required: ['filePath','symbolName','insertText'] } },
      { name: 'delete_symbol', description: 'Delete a symbol definition from a file', inputSchema: { type: 'object', properties: { filePath: { type: 'string' }, symbolName: { type: 'string' } }, required: ['filePath','symbolName'] } },
      { name: 'check_lsp_compatibility', description: 'Quick check for LSP/SCIP tool availability (best-effort)', inputSchema: { type: 'object', properties: {}, required: [] } },
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
        return { content: [ { type: 'text', text: JSON.stringify({ success: true, filePath }) } ] };
      }

      case 'read_file': {
        const filePath = String(args?.filePath || '');
        if (!filePath) throw new Error('filePath required');
        const data = await fs.readFile(filePath, { encoding: 'utf8' });
        return { content: [ { type: 'text', text: data } ] };
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

      // Semantic tools
      case 'find_symbol': {
        const symbolName = String(args?.symbolName || '');
        if (!symbolName) throw new Error('symbolName required');
        const p = String(args?.path || process.cwd());
        const max = Number(args?.maxResults ?? 50);

        // If SCIP (heavy) available, delegate to it for cross-repo queries
        try {
          const client = await ensureScipClient();
          const resp = await client.callTool({ name: 'scip__find_references', arguments: { symbolName } }).catch(() => null);
          if (resp && resp.content) {
            // scip server returns JSON text block
            const txt = resp.content.map(c => c.text).join('\n');
            try { const parsed = JSON.parse(txt); return { content: [ { type: 'text', text: JSON.stringify({ symbol: symbolName, matches: parsed }, null, 2) } ] }; } catch (e) { /* fallthrough */ }
          }
        } catch (e) {
          // scip not available — fallback to TS-based search
        }

        const matches = await findSymbolAcrossRepoWithTS(p, symbolName, max);
        return { content: [ { type: 'text', text: JSON.stringify({ symbol: symbolName, matches }, null, 2) } ] };
      }

      case 'find_referencing_symbols': {
        const symbolName = String(args?.symbolName || '');
        if (!symbolName) throw new Error('symbolName required');
        const p = String(args?.path || process.cwd());

        // Prefer SCIP for references if available
        try {
          const client = await ensureScipClient();
          const resp = await client.callTool({ name: 'scip__find_references', arguments: { symbolName } }).catch(() => null);
          if (resp && resp.content) {
            const txt = resp.content.map(c => c.text).join('\n');
            try { const parsed = JSON.parse(txt); return { content: [ { type: 'text', text: JSON.stringify({ symbol: symbolName, references: parsed }, null, 2) } ] }; } catch (e) { /* fallthrough */ }
          }
        } catch (e) {
          // scip not available — fallback
        }

        const matches = await findSymbolAcrossRepoWithTS(p, symbolName, 1000);
        const refs = matches.filter(m => m.kind === 'reference');
        return { content: [ { type: 'text', text: JSON.stringify({ symbol: symbolName, references: refs }, null, 2) } ] };
      }

      case 'read_symbol': {
        const filePath = String(args?.filePath || '');
        if (!filePath) throw new Error('filePath required');
        const symbolName = args?.symbolName ? String(args.symbolName) : undefined;
        const out = await readSymbolFromFileWithTS(filePath, symbolName);
        return { content: [ { type: 'text', text: JSON.stringify(out, null, 2) } ] };
      }

      case 'list_files': {
        const dirPath = String(args?.dirPath || process.cwd());
        const exts = Array.isArray(args?.extensions) ? args.extensions.map(String) : null;
        const files = await walkFiles(dirPath);
        const filtered = files.filter(f => {
          if (!exts) return true;
          return exts.includes(path.extname(f));
        }).map(f => path.relative(process.cwd(), f));
        return { content: [ { type: 'text', text: JSON.stringify(filtered, null, 2) } ] };
      }

      case 'replace_symbol_body': {
        const filePath = String(args?.filePath || '');
        const symbolName = String(args?.symbolName || '');
        const newBody = String(args?.newBody || '');
        const backup = args?.backup !== undefined ? Boolean(args.backup) : true;
        if (!filePath || !symbolName) throw new Error('filePath and symbolName required');
        const res = await replaceSymbolBodyInFileWithTS(filePath, symbolName, newBody, { backup });
        return { content: [ { type: 'text', text: JSON.stringify(res, null, 2) } ] };
      }

      case 'insert_after_symbol': {
        const filePath = String(args?.filePath || '');
        const symbolName = String(args?.symbolName || '');
        const insertText = String(args?.insertText || '');
        if (!filePath || !symbolName || !insertText) throw new Error('filePath, symbolName, insertText required');
        const res = await insertAfterSymbolInFileWithTS(filePath, symbolName, insertText);
        return { content: [ { type: 'text', text: JSON.stringify(res, null, 2) } ] };
      }

      case 'delete_symbol': {
        const filePath = String(args?.filePath || '');
        const symbolName = String(args?.symbolName || '');
        if (!filePath || !symbolName) throw new Error('filePath and symbolName required');
        const res = await deleteSymbolFromFileWithTS(filePath, symbolName);
        return { content: [ { type: 'text', text: JSON.stringify(res, null, 2) } ] };
      }

      case 'check_lsp_compatibility': {
        const scipIndexConfigured = Boolean(process.env.SCIP_INDEX_PATH || false);
        // check if tsx is available via npx
        let tsxAvailable = false;
        try {
          // simple attempt to spawn via client ensureScipClient will surface availability
          await ensureScipClient();
          tsxAvailable = true;
        } catch (e) {
          tsxAvailable = false;
        }
        return { content: [ { type: 'text', text: JSON.stringify({ scipIndexConfigured, tsxAvailable, note: 'This is a best-effort checker.' }) } ] };
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
