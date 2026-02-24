#!/usr/bin/env node
// Serena MCP server — filesystem + TypeScript Language Service–powered semantic code tools
// Intended for local development/testing only. Not production-grade.

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import fs from 'node:fs/promises';
import fsSync from 'node:fs';
import path from 'node:path';
import * as ts from 'typescript';

function log(level, msg, data) {
  const timestamp = new Date().toISOString();
  console.error(JSON.stringify({ timestamp, level, msg, data }));
}

// Lightweight file walker (skip node_modules, .git, dist)
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

function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&');
}

function lineColFromIndex(text, index) {
  const prefix = text.slice(0, index);
  const lines = prefix.split('\n');
  return { line: lines.length, column: lines[lines.length - 1].length + 1 };
}

// Find matching '}' for a '{' at openIndex. Naive but handles strings and comments.
function findMatchingBrace(content, openIndex) {
  let i = openIndex;
  const len = content.length;
  if (content[openIndex] !== '{') return -1;
  let depth = 1;
  i++;
  while (i < len) {
    const ch = content[i];
    // skip strings
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
      // template literal — skip until matching backtick (naive)
      i++;
      while (i < len) {
        if (content[i] === '\\') { i += 2; continue }
        if (content[i] === '`') { i++; break }
        i++;
      }
      continue;
    }
    // skip line comment
    if (ch === '/' && content[i+1] === '/') {
      i += 2;
      while (i < len && content[i] !== '\n') i++;
      continue;
    }
    // skip block comment
    if (ch === '/' && content[i+1] === '*') {
      i += 2;
      while (i < len && !(content[i] === '*' && content[i+1] === '/')) i++;
      i += 2;
      continue;
    }
    if (ch === '{') depth++;
    else if (ch === '}') {
      depth--;
      if (depth === 0) return i;
    }
    i++;
  }
  return -1;
}

// ── TypeScript Language Service integration ─────────────────────────────────
let lsCache = null; // { root, service, host, fileList, builtAt }

async function buildLanguageService(root) {
  const files = await walkFiles(root);
  const scriptFiles = files.filter(f => {
    const ext = path.extname(f).toLowerCase();
    if (!CODE_EXTENSIONS.has(ext)) return false;
    if (f.includes(`${path.sep}node_modules${path.sep}`)) return false;
    return true;
  }).map(f => path.resolve(f));

  const compilerOptions = {
    allowJs: true,
    jsx: ts.JsxEmit.React,
    target: ts.ScriptTarget.ES2020,
    module: ts.ModuleKind.CommonJS,
    moduleResolution: ts.ModuleResolutionKind.NodeJs,
    allowSyntheticDefaultImports: true,
    esModuleInterop: true,
    skipLibCheck: true,
    noImplicitAny: false,
  };

  const fileVersions = new Map();

  const host = {
    getScriptFileNames: () => scriptFiles,
    getScriptVersion: (fileName) => fileVersions.get(fileName) ?? '0',
    getScriptSnapshot: (fileName) => {
      try {
        if (!fsSync.existsSync(fileName)) return undefined;
        const text = fsSync.readFileSync(fileName, 'utf8');
        fileVersions.set(fileName, String(Date.now()));
        return ts.ScriptSnapshot.fromString(text);
      } catch (e) {
        return undefined;
      }
    },
    getCurrentDirectory: () => process.cwd(),
    getCompilationSettings: () => compilerOptions,
    getDefaultLibFileName: (opts) => ts.getDefaultLibFilePath(opts),
    fileExists: fsSync.existsSync,
    readFile: (fileName) => fsSync.existsSync(fileName) ? fsSync.readFileSync(fileName, 'utf8') : undefined,
    directoryExists: (dir) => fsSync.existsSync(dir) && fsSync.statSync(dir).isDirectory(),
    getDirectories: (dir) => fsSync.existsSync(dir) ? fsSync.readdirSync(dir).filter(n => fsSync.statSync(path.join(dir, n)).isDirectory()) : [],
  };

  const service = ts.createLanguageService(host, ts.createDocumentRegistry());
  lsCache = { root, service, host, fileList: scriptFiles, builtAt: Date.now() };
  return service;
}

async function ensureLanguageService(root) {
  if (lsCache && lsCache.root === root) return lsCache.service;
  return await buildLanguageService(root);
}

function invalidateLanguageService() {
  lsCache = null;
}

async function findSymbolAcrossRepoWithLS(repoRoot, symbolName, maxResults = 50) {
  try {
    const ls = await ensureLanguageService(repoRoot);
    const program = ls.getProgram();
    if (!program) return [];
    const checker = program.getTypeChecker();

    const matches = [];
    const sourceFiles = program.getSourceFiles().filter(sf => !sf.isDeclarationFile && !sf.fileName.includes(`${path.sep}node_modules${path.sep}`));

    // First pass: find declarations
    for (const sf of sourceFiles) {
      const text = sf.getFullText();
      let stop = false;
      function visit(node) {
        if (stop) return;
        // Common declaration kinds
        if ((ts.isFunctionDeclaration(node) || ts.isClassDeclaration(node) || ts.isInterfaceDeclaration(node) || ts.isEnumDeclaration(node) || ts.isTypeAliasDeclaration(node) || ts.isVariableDeclaration(node))) {
          const nameNode = (node.name && ts.isIdentifier(node.name)) ? node.name : (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) ? node.name : undefined);
          if (nameNode && nameNode.text === symbolName) {
            const start = nameNode.getStart(sf);
            const end = nameNode.getEnd();
            const pos = lineColFromIndex(text, start);
            matches.push({ file: path.relative(process.cwd(), sf.fileName), start, end, line: pos.line, column: pos.column, kind: 'definition', preview: text.slice(start, Math.min(start + 200, text.length)).split('\n')[0] });
            if (matches.length >= maxResults) { stop = true; return; }
          }
        }
        ts.forEachChild(node, visit);
      }
      visit(sf);
      if (matches.length >= maxResults) break;
    }

    // If declarations found, expand to references using languageService.findReferences
    if (matches.length > 0) {
      const out = [];
      for (const m of matches) {
        try {
          const abs = path.resolve(m.file);
          const refs = ls.findReferences(abs, m.start) || [];
          for (const refEntry of refs) {
            if (refEntry.references) {
              for (const r of refEntry.references) {
                try {
                  const content = fsSync.readFileSync(r.fileName, 'utf8');
                  const pos = lineColFromIndex(content, r.textSpan.start);
                  out.push({ file: path.relative(process.cwd(), r.fileName), start: r.textSpan.start, end: r.textSpan.start + r.textSpan.length, line: pos.line, column: pos.column, kind: r.isDefinition ? 'definition' : 'reference', preview: content.slice(Math.max(0, r.textSpan.start - 60), Math.min(content.length, r.textSpan.start + Math.min(120, r.textSpan.length))).replace(/\n/g,'\\n') });
                } catch (e) { /* best-effort per reference */ }
                if (out.length >= maxResults) break;
              }
            }
            if (out.length >= maxResults) break;
          }
        } catch (e) {
          // fallback: include original declaration
          out.push(m);
        }
        if (out.length >= maxResults) break;
      }
      return out.slice(0, maxResults);
    }

    // No top-level declarations found — find identifier occurrences
    const refsOut = [];
    for (const sf of sourceFiles) {
      const text = sf.getFullText();
      let stop = false;
      function visit(node) {
        if (stop) return;
        if (ts.isIdentifier(node) && node.text === symbolName) {
          const start = node.getStart(sf);
          const pos = lineColFromIndex(text, start);
          refsOut.push({ file: path.relative(process.cwd(), sf.fileName), start, end: start + symbolName.length, line: pos.line, column: pos.column, kind: 'reference', preview: text.slice(Math.max(0, start - 60), Math.min(text.length, start + 60)).replace(/\n/g,'\\n') });
          if (refsOut.length >= maxResults) { stop = true; return; }
        }
        ts.forEachChild(node, visit);
      }
      visit(sf);
      if (refsOut.length >= maxResults) break;
    }
    return refsOut.slice(0, maxResults);
  } catch (err) {
    log('warn', 'findSymbolAcrossRepoWithLS failed', { error: String(err) });
    return [];
  }
}

async function readSymbolFromFileWithLS(filePath, symbolName) {
  const abs = path.isAbsolute(filePath) ? filePath : path.join(process.cwd(), filePath);
  let content;
  try { content = await fs.readFile(abs, 'utf8'); } catch (e) { throw new Error('file not found') }
  if (!symbolName) {
    return { file: path.relative(process.cwd(), abs), content };
  }

  // Use language service if available for this repo
  try {
    const ls = await ensureLanguageService(process.cwd());
    const sf = ls.getProgram()?.getSourceFile(abs);
    if (sf) {
      let declNode = undefined;
      function visit(node) {
        if (declNode) return;
        if ((ts.isFunctionDeclaration(node) || ts.isClassDeclaration(node) || ts.isInterfaceDeclaration(node) || ts.isEnumDeclaration(node) || ts.isTypeAliasDeclaration(node) || ts.isVariableDeclaration(node))) {
          const nameNode = (node.name && ts.isIdentifier(node.name)) ? node.name : (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) ? node.name : undefined);
          if (nameNode && nameNode.text === symbolName) { declNode = node; return; }
        }
        ts.forEachChild(node, visit);
      }
      visit(sf);
      if (declNode) {
        const start = declNode.getStart(sf);
        const end = declNode.getEnd();
        const snippet = content.slice(start, end);
        return { file: path.relative(process.cwd(), abs), start, end, snippet };
      }
    }
  } catch (e) {
    // fallthrough to simple parse
  }

  // Fallback naive search: regex for definition
  const def = findSymbolDefinitionNaive(content, symbolName);
  if (!def) throw new Error('symbol not found in file');
  const snippet = content.slice(def.start, def.end);
  return { file: path.relative(process.cwd(), abs), start: def.start, end: def.end, snippet };
}

function findSymbolDefinitionNaive(content, name) {
  const patterns = [
    new RegExp(`(^|\\n)\\s*(export\\s+)?function\\s+${escapeRegExp(name)}\\s*\\(`, 'm'),
    new RegExp(`(^|\\n)\\s*(export\\s+)?class\\s+${escapeRegExp(name)}\\b`, 'm'),
    new RegExp(`(^|\\n)\\s*(export\\s+)?(const|let|var)\\s+${escapeRegExp(name)}\\s*=`, 'm'),
    new RegExp(`(^|\\n)\\s*(?:module\\.|exports\\.)?${escapeRegExp(name)}\\s*=\\s*function\\s*\\(`, 'm'),
    new RegExp(`(^|\\n)\\s*(?:const|let|var)?\\s*${escapeRegExp(name)}\\s*=\\s*(?:async\\s*)?\\([^)]*\\)\\s*=>\\s*{`, 'm'),
  ];
  for (const pat of patterns) {
    const m = pat.exec(content);
    if (m && typeof m.index === 'number') {
      const start = m.index;
      const braceIdx = content.indexOf('{', m.index);
      if (braceIdx !== -1) {
        const endIdx = findMatchingBrace(content, braceIdx);
        if (endIdx !== -1) return { start: m.index, end: endIdx + 1 };
      }
      const arrowIdx = content.indexOf('=>', m.index);
      if (arrowIdx !== -1) {
        const semi = content.indexOf(';', arrowIdx);
        const nl = content.indexOf('\n', arrowIdx);
        const end = semi !== -1 ? semi + 1 : (nl !== -1 ? nl + 1 : Math.min(content.length, arrowIdx + 200));
        return { start: m.index, end };
      }
      const approxEnd = Math.min(content.length, m.index + 400);
      return { start: m.index, end: approxEnd };
    }
  }
  return null;
}

async function replaceSymbolBodyInFileWithLS(filePath, symbolName, newBody, options = { backup: true }) {
  const abs = path.isAbsolute(filePath) ? filePath : path.join(process.cwd(), filePath);
  let content;
  try { content = await fs.readFile(abs, 'utf8'); } catch (e) { throw new Error('file not found') }

  try {
    const ls = await ensureLanguageService(process.cwd());
    const sf = ls.getProgram()?.getSourceFile(abs);
    if (sf) {
      let declNode = undefined;
      function visit(node) {
        if (declNode) return;
        if ((ts.isFunctionDeclaration(node) || ts.isClassDeclaration(node) || ts.isMethodDeclaration(node) || ts.isVariableDeclaration(node))) {
          const nameNode = (node.name && ts.isIdentifier(node.name)) ? node.name : (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) ? node.name : undefined);
          if (nameNode && nameNode.text === symbolName) { declNode = node; return; }
        }
        ts.forEachChild(node, visit);
      }
      visit(sf);
      if (!declNode) throw new Error('symbol not found');

      // Find body start/end
      let bodyStart = -1;
      let bodyEnd = -1;
      if (declNode.body && declNode.body.pos !== undefined) {
        bodyStart = declNode.body.pos;
        bodyEnd = declNode.body.end;
      } else if (ts.isVariableDeclaration(declNode) && declNode.initializer) {
        const init = declNode.initializer;
        if (ts.isArrowFunction(init) || ts.isFunctionExpression(init)) {
          const ib = init.body;
          bodyStart = ib.pos;
          bodyEnd = ib.end;
        }
      }

      if (bodyStart === -1 || bodyEnd === -1) {
        // fallback: find first '{' after decl start
        const idx = content.indexOf('{', declNode.getStart(sf));
        if (idx !== -1) {
          const close = findMatchingBrace(content, idx);
          if (close !== -1) { bodyStart = idx; bodyEnd = close + 1; }
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
      invalidateLanguageService();
      return { file: path.relative(process.cwd(), abs), replaced: true };
    }
  } catch (e) {
    // fallthrough to naive approach
  }

  // Fallback naive approach
  const def = findSymbolDefinitionNaive(content, symbolName);
  if (!def) throw new Error('symbol not found');
  const braceIdx = content.indexOf('{', def.start);
  if (braceIdx === -1) throw new Error('unable to locate body start');
  const closeIdx = findMatchingBrace(content, braceIdx);
  if (closeIdx === -1) throw new Error('unable to locate body end');
  const before = content.slice(0, braceIdx + 1);
  const after = content.slice(closeIdx);
  const newInner = '\n' + newBody + '\n';
  const newContent = before + newInner + after;
  if (options.backup) await fs.writeFile(abs + '.serena.bak', content, 'utf8').catch(() => {});
  await fs.writeFile(abs, newContent, 'utf8');
  invalidateLanguageService();
  return { file: path.relative(process.cwd(), abs), replaced: true };
}

async function insertAfterSymbolInFileWithLS(filePath, symbolName, insertText) {
  const abs = path.isAbsolute(filePath) ? filePath : path.join(process.cwd(), filePath);
  let content;
  try { content = await fs.readFile(abs, 'utf8'); } catch (e) { throw new Error('file not found') }

  try {
    const ls = await ensureLanguageService(process.cwd());
    const sf = ls.getProgram()?.getSourceFile(abs);
    if (sf) {
      let declNode = undefined;
      function visit(node) {
        if (declNode) return;
        if ((ts.isFunctionDeclaration(node) || ts.isClassDeclaration(node) || ts.isVariableDeclaration(node))) {
          const nameNode = (node.name && ts.isIdentifier(node.name)) ? node.name : (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) ? node.name : undefined);
          if (nameNode && nameNode.text === symbolName) { declNode = node; return; }
        }
        ts.forEachChild(node, visit);
      }
      visit(sf);
      if (!declNode) throw new Error('symbol not found');
      const insertAt = declNode.getEnd();
      const newContent = content.slice(0, insertAt) + '\n' + insertText + '\n' + content.slice(insertAt);
      await fs.writeFile(abs + '.serena.bak', content, 'utf8').catch(() => {});
      await fs.writeFile(abs, newContent, 'utf8');
      invalidateLanguageService();
      return { file: path.relative(process.cwd(), abs), inserted: true, insertAt };
    }
  } catch (e) {
    // fallthrough
  }

  // Fallback naive: use definition end
  const def = findSymbolDefinitionNaive(content, symbolName);
  if (!def) throw new Error('symbol not found');
  const insertAt = def.end;
  const newContent = content.slice(0, insertAt) + '\n' + insertText + '\n' + content.slice(insertAt);
  await fs.writeFile(abs + '.serena.bak', content, 'utf8').catch(() => {});
  await fs.writeFile(abs, newContent, 'utf8');
  invalidateLanguageService();
  return { file: path.relative(process.cwd(), abs), inserted: true, insertAt };
}

async function deleteSymbolFromFileWithLS(filePath, symbolName) {
  const abs = path.isAbsolute(filePath) ? filePath : path.join(process.cwd(), filePath);
  let content;
  try { content = await fs.readFile(abs, 'utf8'); } catch (e) { throw new Error('file not found') }

  try {
    const ls = await ensureLanguageService(process.cwd());
    const sf = ls.getProgram()?.getSourceFile(abs);
    if (sf) {
      let declNode = undefined;
      function visit(node) {
        if (declNode) return;
        if ((ts.isFunctionDeclaration(node) || ts.isClassDeclaration(node) || ts.isVariableDeclaration(node))) {
          const nameNode = (node.name && ts.isIdentifier(node.name)) ? node.name : (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) ? node.name : undefined);
          if (nameNode && nameNode.text === symbolName) { declNode = node; return; }
        }
        ts.forEachChild(node, visit);
      }
      visit(sf);
      if (!declNode) throw new Error('symbol not found');
      const newContent = content.slice(0, declNode.getStart(sf)) + content.slice(declNode.getEnd());
      await fs.writeFile(abs + '.serena.bak', content, 'utf8').catch(() => {});
      await fs.writeFile(abs, newContent, 'utf8');
      invalidateLanguageService();
      return { file: path.relative(process.cwd(), abs), deleted: true };
    }
  } catch (e) {
    // fallback
  }

  const def = findSymbolDefinitionNaive(content, symbolName);
  if (!def) throw new Error('symbol not found');
  const newContent = content.slice(0, def.start) + content.slice(def.end);
  await fs.writeFile(abs + '.serena.bak', content, 'utf8').catch(() => {});
  await fs.writeFile(abs, newContent, 'utf8');
  invalidateLanguageService();
  return { file: path.relative(process.cwd(), abs), deleted: true };
}

// SCIP client helper — lazily spawn a scip MCP server and connect as MCP client.
let scipClient = null;
let scipConnected = false;
let scipConnecting = false;

async function ensureScipClient() {
  if (scipConnected) return scipClient;
  if (scipConnecting) {
    for (let i = 0; i < 60; i++) {
      if (scipConnected) return scipClient;
      await new Promise(r => setTimeout(r, 200));
    }
    throw new Error('SCIP client connection timed out');
  }

  scipConnecting = true;
  try {
    const transport = new StdioClientTransport({
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

const server = new Server({ name: 'serena-mcp-server', version: '0.4.0' }, { capabilities: { tools: {} } });

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
        invalidateLanguageService();
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
        const ok = fsSync.existsSync(filePath);
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
        invalidateLanguageService();
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
            const txt = resp.content.map(c => c.text).join('\n');
            try { const parsed = JSON.parse(txt); return { content: [ { type: 'text', text: JSON.stringify({ symbol: symbolName, matches: parsed }, null, 2) } ] }; } catch (e) { /* fallthrough */ }
          }
        } catch (e) {
          // scip not available — fallback to LS-based search
        }

        const matches = await findSymbolAcrossRepoWithLS(p, symbolName, max);
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

        const matches = await findSymbolAcrossRepoWithLS(p, symbolName, 1000);
        const refs = matches.filter(m => m.kind === 'reference' || m.kind === 'definition');
        return { content: [ { type: 'text', text: JSON.stringify({ symbol: symbolName, references: refs }, null, 2) } ] };
      }

      case 'read_symbol': {
        const filePath = String(args?.filePath || '');
        if (!filePath) throw new Error('filePath required');
        const symbolName = args?.symbolName ? String(args.symbolName) : undefined;
        const out = await readSymbolFromFileWithLS(filePath, symbolName);
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
        const res = await replaceSymbolBodyInFileWithLS(filePath, symbolName, newBody, { backup });
        return { content: [ { type: 'text', text: JSON.stringify(res, null, 2) } ] };
      }

      case 'insert_after_symbol': {
        const filePath = String(args?.filePath || '');
        const symbolName = String(args?.symbolName || '');
        const insertText = String(args?.insertText || '');
        if (!filePath || !symbolName || !insertText) throw new Error('filePath, symbolName, insertText required');
        const res = await insertAfterSymbolInFileWithLS(filePath, symbolName, insertText);
        return { content: [ { type: 'text', text: JSON.stringify(res, null, 2) } ] };
      }

      case 'delete_symbol': {
        const filePath = String(args?.filePath || '');
        const symbolName = String(args?.symbolName || '');
        if (!filePath || !symbolName) throw new Error('filePath and symbolName required');
        const res = await deleteSymbolFromFileWithLS(filePath, symbolName);
        return { content: [ { type: 'text', text: JSON.stringify(res, null, 2) } ] };
      }

      case 'check_lsp_compatibility': {
        const scipIndexConfigured = Boolean(process.env.SCIP_INDEX_PATH || false);
        let tsxAvailable = false;
        try { await ensureScipClient(); tsxAvailable = true; } catch (e) { tsxAvailable = false; }
        return { content: [ { type: 'text', text: JSON.stringify({ scipIndexConfigured, tsxAvailable, note: 'This is a best-effort checker. For full SCIP/LSP capabilities run scip-typescript indexing and run a scip MCP server.' }) } ] };
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
