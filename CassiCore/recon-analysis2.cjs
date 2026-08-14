// Recon analysis v2 for cassi-mind migration. Read-only on repo, writes JSON.
const fs = require('fs');
const path = require('path');

const ROOT = 'D:/carina/workspaces/cassicore';
const OUT = 'C:/Users/Carina/Workspaces/CassiCore';

const SUBSYS = {
  'core': 'core',
  'types': 'types',
  'workers': 'workers',
  'mcp': 'mcp',
  'commands': 'commands',
  'integrations': 'integrations',
  'packages/larql': 'packages/larql',
  'cassi-tui': 'cassi-tui',
  'webui': 'webui',
  'prism': 'prism',
  'ai': 'ai',
  'cassi-watch': 'cassi-watch',
  'hermes-tools': 'hermes-tools',
  'bin': 'bin',
  'scripts': 'scripts',
  'mind-plugin': 'mind-plugin',
};
const EXCLUDE_DIR = /^(node_modules|dist|target|\.git|build|out|__pycache__|\.next|\.nuxt|coverage|\.cache|vendor|\.turbo|\.yarn|\.cargo|public|static|assets|lib)$/;
const SRC_EXTS = new Set(['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs']);
const TS_EXTS = new Set(['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs']);

function collectInto(dir, acc) {
  const abs = path.join(ROOT, dir);
  if (!fs.existsSync(abs)) return;
  let entries;
  try { entries = fs.readdirSync(abs, { withFileTypes: true }); } catch (e) { return; }
  for (const ent of entries) {
    if (EXCLUDE_DIR.test(ent.name)) continue;
    const rel = dir + '/' + ent.name;
    try {
      if (ent.isDirectory()) collectInto(rel, acc);
      else if (SRC_EXTS.has(path.extname(ent.name))) {
        const st = fs.statSync(path.join(ROOT, rel));
        acc.push({ rel, kb: +(st.size / 1024).toFixed(2), ext: path.extname(ent.name).slice(1), subsys: null });
      }
    } catch (e) {}
  }
}

// Collect all source files and assign subsystem
const allFiles = [];
for (const d of Object.keys(SUBSYS)) {
  const before = allFiles.length;
  collectInto(d, allFiles);
  for (let i = before; i < allFiles.length; i++) allFiles[i].subsys = SUBSYS[d];
}
// extras
const EXTRA = { 'tests': 'extra_tests', 'test': 'extra_tests' };
for (const [d, sub] of Object.entries(EXTRA)) {
  const before = allFiles.length;
  collectInto(d, allFiles);
  for (let i = before; i < allFiles.length; i++) allFiles[i].subsys = sub;
}
const byRel = new Map(allFiles.map(f => [f.rel, f]));

// content cache + import extraction
const contentCache = new Map();
function getContent(rel) {
  if (contentCache.has(rel)) return contentCache.get(rel);
  let c = '';
  try { c = fs.readFileSync(path.join(ROOT, rel), 'utf8'); } catch (e) { c = ''; }
  contentCache.set(rel, c);
  return c;
}
const importRe = /(?:from\s+|import\s*\(|require\(\s*)['"]([^'"]+)['"]/g;
function extractImports(rel, content) {
  const out = [];
  const seen = new Set();
  let m; importRe.lastIndex = 0;
  while ((m = importRe.exec(content)) !== null) {
    const spec = m[1];
    if (seen.has(spec)) continue;
    seen.add(spec);
    if (spec.startsWith('.')) out.push({ raw: spec, kind: 'rel', target: path.posix.normalize(path.posix.join(path.posix.dirname(rel), spec)) });
    else { const slash = spec.indexOf('/'); const bare = slash > 0 ? spec.slice(0, slash) : spec; out.push({ raw: spec, kind: 'external', target: bare }); }
  }
  return out;
}
const importsOf = new Map();
for (const f of allFiles) importsOf.set(f.rel, extractImports(f.rel, getContent(f.rel)));

// build reverse consumers map
function resolveRel(target) {
  let resolved = byRel.get(target);
  if (resolved) return { resolved, target };
  const cands = [
    target, target + '.ts', target + '.tsx', target + '.js', target + '.jsx',
    target + '.mjs', target + '.cjs',
    target.replace(/\.(?:js|jsx|mjs|cjs)$/, '.ts'),
    target.replace(/\.(?:js|jsx|mjs|cjs)$/, '.tsx'),
  ];
  for (const cand of cands) {
    if (byRel.has(cand)) return { resolved: byRel.get(cand), target: cand };
    const swapped = cand.replace(/\.(?:js|jsx|mjs|cjs)$/, '');
    if (byRel.has(swapped + '/index.ts')) return { resolved: byRel.get(swapped + '/index.ts'), target: swapped + '/index.ts' };
    if (byRel.has(swapped + '/index.tsx')) return { resolved: byRel.get(swapped + '/index.tsx'), target: swapped + '/index.tsx' };
  }
  return null;
}
const consumers = new Map();
for (const f of allFiles) {
  for (const it of importsOf.get(f.rel) || []) {
    if (it.kind !== 'rel') continue;
    const r = resolveRel(it.target);
    if (r) {
      if (!consumers.has(r.resolved.rel)) consumers.set(r.resolved.rel, new Set());
      consumers.get(r.resolved.rel).add(f.rel);
    }
  }
}

// ---------------- Entry roots & per-package seeds ----------------
// Runtimes of interest (daemon + standalone packages), each with its own seed root(s).
// Seeds: actual entry files. Returns list of {seeds:[{rel, via}], via: package-name}
const runtimes = [
  { key: 'core', via: 'daemon/CLI/bin', seeds: [
      'core/entry/index.ts', 'core/entry/daemon-main.ts', 'core/entry/supervisor.ts',
      'core/daemon.ts', 'core/admin-api.ts', 'core/admin-api/index.ts',
      'core/cli/index.ts', 'core/cli/cassicore.ts', 'core/commands.ts',
    ] },
  { key: 'commands', via: 'commands/index.ts + root bin', seeds: ['commands/index.ts'] },
  { key: 'workers', via: 'worker entry', seeds: [] }, // filled below
  { key: 'mcp', via: 'mcp gateway', seeds: ['mcp/cassicore-gateway.ts', 'mcp/scip-server.ts', 'mcp/gitnexus-server.js', 'mcp/serena-server.js'] },
  { key: 'ai', via: 'npm package ai (main dist/index.js)', seeds: ['ai/src/index.ts', 'ai/src/cli.ts'] },
  { key: 'cassi-tui', via: 'npm package cassi (bin cassi)', seeds: ['cassi-tui/src/index.tsx', 'cassi-tui/src/index.ts'] },
  { key: 'cassi-watch', via: 'npm package cassicore-watch', seeds: ['cassi-watch/src/index.tsx', 'cassi-watch/src/index.ts'] },
  { key: 'webui', via: 'next app webui', seeds: ['webui/src/app/layout.tsx', 'webui/src/app/page.tsx'] },
  { key: 'prism', via: 'vite app prism', seeds: ['prism/src/main.tsx', 'prism/src/index.ts'] },
  { key: 'mind-plugin', via: 'new migration plugin', seeds: [] }, // discover
];

// discover worker/mind-plugin/channel seeds, and resolve which seeds actually exist
for (const w of ['workers/echo-channel.ts', 'workers/channels/index.ts', 'workers/channels/echo.ts', 'workers/index.ts']) {
  if (byRel.has(w)) runtimes.find(r => r.key === 'workers').seeds.push(w);
}
// find mind-plugin seeds
for (const f of allFiles) {
  if (f.subsys === 'mind-plugin') { runtimes.find(r => r.key === 'mind-plugin').seeds.push(f.rel); }
}
// discover mcp gateway/* files (task says gateway dir is a root)
for (const f of allFiles) {
  if (f.rel.startsWith('mcp/gateway/') && /(index|server|main|gateway|agent-tools)\.(ts|js)$/.test(f.rel)) {
    const rt = runtimes.find(r => r.key === 'mcp');
    if (!rt.seeds.includes(f.rel)) rt.seeds.push(f.rel);
  }
}
// commands sub-files are all roots (they register commands)
for (const f of allFiles) {
  if (f.subsys === 'commands') { const rt = runtimes.find(r => r.key === 'commands'); if (!rt.seeds.includes(f.rel)) rt.seeds.push(f.rel); }
}

// Resolve actual existing seed rels
for (const rt of runtimes) {
  rt.seeds = rt.seeds.filter(s => byRel.has(s) || fs.existsSync(path.join(ROOT, s)));
}

// ---------------- BFS reachability per runtime (union for global ALIVE) ----------------
const reached = new Set();               // global: reachable from any runtime root
const runtimeReach = {};                 // runtime key -> Set of rels reached starting from its seeds
let allLiveOutside = new Set();          // same as reached

for (const rt of runtimes) {
  const seen = new Set();
  const q = [];
  for (const s of rt.seeds) { if (byRel.has(s) && !seen.has(s)) { seen.add(s); q.push(s); } }
  while (q.length) {
    const cur = q.pop();
    for (const it of importsOf.get(cur) || []) {
      if (it.kind !== 'rel') continue;
      const r = resolveRel(it.target);
      if (r && !seen.has(r.resolved.rel)) { seen.add(r.resolved.rel); q.push(r.resolved.rel); }
    }
  }
  runtimeReach[rt.key] = seen;
  for (const s of seen) reached.add(s);
}

// ---------------- Mechanism-aware ALIVE overrides ----------------
// (1) IntelligenceRegistry auto-discovers BaseCognitiveModule subclass index.ts files
//     under core/intelligence/<dir>/ (single level), excluding the explicit skip set.
const INTEL_SKIP = new Set([
  'base', 'memory', 'continuity', 'recover', 'reflect', 'thinker', 'optimizer',
  'dialectic', 'ai-scientist', 'rule-enforcer', 'subconscious', 'team-orchestrator',
  'triad-team', 'embeddings', 'yang', 'yin', 'synthesizer', 'serenity', 'self-healer',
  'heart', 'dreamer', 'smart-rules', 'reflex', 'consequence-estimator', 'trust-ledger',
  'permission-oracle',
]);
function isModuleIndex(rel, content) {
  // only core/intelligence/<dir>/index.ts (single level)
  const mm = /^core\/intelligence\/([^/]+)\/index\.ts$/.exec(rel);
  if (!mm) return false;
  if (INTEL_SKIP.has(mm[1])) return false;
  // exported class extends BaseCognitiveModule OR MODULE_CLASS export
  if (/MODULE_CLASS/.test(content)) return true;
  if (/extends\s+BaseCognitiveModule/.test(content)) return true;
  return false;
}
const mechanismAlive = new Set();
const mechanismQueue = [];
for (const rel of byRel.keys()) {
  const c = getContent(rel);
  if (isModuleIndex(rel, c)) { if (!mechanismAlive.has(rel)) { mechanismAlive.add(rel); mechanismQueue.push(rel); } }
}
// propagate transitive closure over imports
while (mechanismQueue.length) {
  const cur = mechanismQueue.pop();
  for (const it of importsOf.get(cur) || []) {
    if (it.kind !== 'rel') continue;
    const r = resolveRel(it.target);
    if (r && !mechanismAlive.has(r.resolved.rel)) { mechanismAlive.add(r.resolved.rel); mechanismQueue.push(r.resolved.rel); }
  }
}

// (2) Standalone process entries / worker channel loads by path via resolveWorker at runtime
const PROCESS_ENTRY_SEEDS = [
  'core/entry/vindex-loader.ts',        // standalone sidecar (HTTP :7434), launched by systemd/manual
  'core/bridge/acp/bin.ts',             // standalone ACP bridge CLI
  'core/cli/runtime/background-launcher.cjs', // helper spawned by CLI
  'workers/channels/cli.ts',            // daemon channel worker (resolveWorker)
  'workers/channels/webchat.ts',
  'workers/channels/telegram.ts',
  'core/intelligence/mnemic-field/umap-worker.cjs', // spawned by umap.ts
  'core/intelligence/mnemic-field/backfill-worker.ts', // spawned by backfill-runner
];
const mechanismSeedsQueue = [];
for (const s of PROCESS_ENTRY_SEEDS) {
  if (reached.has(s) || mechanismAlive.has(s)) continue;
  if (byRel.has(s)) { mechanismAlive.add(s); mechanismSeedsQueue.push(s); }
}
while (mechanismSeedsQueue.length) {
  const cur = mechanismSeedsQueue.pop();
  for (const it of importsOf.get(cur) || []) {
    if (it.kind !== 'rel') continue;
    const r = resolveRel(it.target);
    if (r && !mechanismAlive.has(r.resolved.rel)) { mechanismAlive.add(r.resolved.rel); mechanismSeedsQueue.push(r.resolved.rel); }
  }
}

// merge into reached, recording mechanism reason for classification
const mechanismReasons = new Map(); // rel -> 'registry-auto-discovery'|'standalone-process-entry'|'mechanism-transitive'
for (const rel of mechanismAlive) mechanismReasons.set(rel, mechanismWhy(rel));
for (const s of mechanismAlive) reached.add(s);
const mechanismWhyCache = new Map();
function mechanismWhy(rel) {
  if (isModuleIndex(rel, getContent(rel))) return 'registry-auto-discovery';
  if (PROCESS_ENTRY_SEEDS.includes(rel)) return 'standalone-process-entry';
  return 'mechanism-transitive';
}
// A non-reached file is UNCERTAIN if a path-like reference to it appears anywhere (string/dynamic/comment).
// Compute string-paths list: all import-like string literals, dynamic import() with any string, and path-ish literals.
function pathLikeSpecs(content) {
  const out = new Set();
  const re1 = /(?:from\s+|import\s*\(|require\(\s*|await\s+import\s*\(|new URL\()\s*['"`]([^'"`]+)['"`]/g;
  let m;
  while ((m = re1.exec(content)) !== null) out.add(m[1]);
  // generic string literals that look like module-relative paths
  const re2 = /['"`]((?:\.{1,2}\/|core\/|types\/|workers\/|mcp\/|commands\/|ai\/|webui\/|prism\/|cassi-tui\/|cassi-watch\/|integrations\/|packages\/)[^'"`]*\.(?:ts|tsx|js|jsx|mjs|cjs))['"`]/g;
  while ((m = re2.exec(content)) !== null) out.add(m[1]);
  return out;
}
const allPathSpecs = new Map(); // rel -> set of specs
for (const f of allFiles) allPathSpecs.set(f.rel, pathLikeSpecs(getContent(f.rel)));

// For a non-reached file, gather referencing files (by rel) via ANY quoted/template string
// that resolves to it (with or without extension, incl. index resolution, and .js->.ts swap).
const refs = new Map(); // rel -> Set<referencer rel>
// Build a reversed lookup: rel -> set of string-forms that resolve to it
const resolversByRel = new Map();
for (const f of allFiles) {
  const forms = resolversByRel.get(f.rel) || new Set();
  resolversByRel.set(f.rel, forms);
  const relNoExt = f.rel.replace(/\.(ts|tsx|js|jsx|mjs|cjs)$/, '');
  forms.add(f.rel);
  forms.add(relNoExt);
  // also index-swapped forms handled by resolveRel at scan time
}
const ALL_STRING_RE = /(['"`])((?:\.{1,2}\/|core\/|types\/|workers\/|mcp\/|commands\/|ai\/|webui\/|prism\/|cassi-tui\/|cassi-watch\/|integrations\/|packages\/|\.\.\/)[^'"`]+)\1/g;
for (const g of allFiles) {
  const c = getContent(g.rel);
  let m; ALL_STRING_RE.lastIndex = 0;
  while ((m = ALL_STRING_RE.exec(c)) !== null) {
    let spec = m[2];
    // normalize whitespace
    if (/[\s;{}\[\]()<>=]/.test(spec)) continue;
    const resolved = resolveRel(path.posix.normalize(path.posix.join(path.posix.dirname(g.rel), spec)));
    if (resolved) {
      if (!refs.has(resolved.resolved.rel)) refs.set(resolved.resolved.rel, new Set());
      refs.get(resolved.resolved.rel).add(g.rel);
    }
  }
}
// ALSO: match bare filenames appearing in spawn/fork/resolveWorker paths without ../ prefix but as worker refs
for (const g of allFiles) {
  const c = getContent(g.rel);
  const m2 = /\bresolveWorker\(\s*['"]([^'"]+)['"]\)/g; let mm;
  while ((mm = m2.exec(c)) !== null) {
    const spec = mm[1];
    const resolved = resolveRel(path.posix.normalize(path.posix.join(path.posix.dirname(g.rel), spec)));
    if (resolved) {
      if (!refs.has(resolved.resolved.rel)) refs.set(resolved.resolved.rel, new Set());
      refs.get(resolved.resolved.rel).add(g.rel);
    }
  }
}

// Exported top-level identifier names per file (function/class/const/variable exports)
function exportedNames(content) {
  const names = new Set();
  // export function name / export class name / export const name= / export async function name
  const re = /export\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)|export\s+(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)|export\s+(?:async\s+)?(?:function|const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?:=|:|\()/g;
  let m;
  while ((m = re.exec(content)) !== null) { const n = m[1] || m[2] || m[3]; if (n) names.add(n); }
  // named export list: export { a, b }
  const re2 = /export\s*\{([^}]+)\}/g;
  while ((m = re2.exec(content)) !== null) {
    for (const part of m[1].split(',')) {
      const n = part.trim().split(/\s+as\s+/)[0].trim();
      if (/^[A-Za-z_$][\w$]*$/.test(n)) names.add(n);
    }
  }
  return names;
}
const exportedOf = new Map(); // rel -> Set<string>
for (const f of allFiles) exportedOf.set(f.rel, exportedNames(getContent(f.rel)));

// nameRef: rel -> Set<referencer rel> where an exported name appears as a whole token in another file
const nameWord = {};
const nameRefs = new Map();
// build set of files mentioning each exported name (whole-word, ignoring the defining file)
const mentionCache = new Map(); // rel -> {name, refs} not used; simpler: two passes
// Precompute per-file content once (already in getContent). For each file g, extract distinct identifiers token set for matching is heavy;
// Instead: for each exported name, scan all other files for \bname\b occurrence (skip if it's the defining file). Cache word index cheap: iterate files.
for (const f of allFiles) {
  const names = exportedOf.get(f.rel);
  if (!names.size) continue;
  for (const n of names) {
    if (n.length < 3) continue;
    for (const g of allFiles) {
      if (g === f) continue;
      const c = getContent(g.rel);
      if (new RegExp('\\b' + n + '\\b').test(c)) {
        if (!nameRefs.has(f.rel)) nameRefs.set(f.rel, new Set());
        nameRefs.get(f.rel).add(g.rel);
      }
    }
  }
}

const isTestFile = (rel) => /\.(test|spec)\.(ts|tsx|js|jsx)$/.test(rel) || /\/(__tests__|test|tests)\//.test(rel);

const classification = new Map(); // rel -> {status, why}
// only a referencer that is itself LIVE counts toward UNCERTAIN (ignore test-file & dead-only refs)
const liveRefCount = (m) => m && [...m].filter(g => reached.has(g)).length;
for (const f of allFiles) {
  if (reached.has(f.rel)) {
    classification.set(f.rel, { status: 'ALIVE', why: mechanismReasons.get(f.rel) || 'import-reachable' });
    continue;
  }
  if (isTestFile(f.rel)) { classification.set(f.rel, { status: 'TEST', why: 'test-file' }); continue; }
  const rc = liveRefCount(refs.get(f.rel));
  if (rc > 0) { classification.set(f.rel, { status: 'UNCERTAIN', why: 'live-string-ref:' + rc }); continue; }
  const nc = liveRefCount(nameRefs.get(f.rel));
  if (nc > 0) { classification.set(f.rel, { status: 'UNCERTAIN', why: 'live-name-ref:' + nc }); continue; }
  classification.set(f.rel, { status: 'DEAD', why: 'unreferenced' });
}

// ---------------- Subsystem aggregation ----------------
const subsysFiles = {};
for (const f of allFiles) (subsysFiles[f.subsys] = subsysFiles[f.subsys] || []).push(f);

const result = { subsystems: {}, deadFiles: [], uncertainFiles: [], biggest: [], runtimeReachSizes: {}, runtimeStats: {}, boundaries: [] };

for (const key of Object.keys(subsysFiles)) {
  const files = subsysFiles[key].slice().sort((a, b) => a.rel.localeCompare(b.rel));
  const totalKB = files.reduce((s, f) => s + f.kb, 0);
  let alive = 0, dead = 0, uncertain = 0, testC = 0;
  const deadList = [], uncertainList = [], aliveList = [];
  for (const f of files) {
    const cl = classification.get(f.rel);
    if (cl.status === 'ALIVE') { alive++; aliveList.push(f.rel); }
    else if (cl.status === 'UNCERTAIN') { uncertain++; uncertainList.push({ rel: f.rel, why: cl.why, kb: f.kb }); }
    else if (cl.status === 'TEST') { testC++; }
    else { dead++; deadList.push({ rel: f.rel, kb: f.kb }); }
  }
  // top consumers outside this subsys
  const consumerCounts = new Map();
  for (const f of files) {
    const cons = consumers.get(f.rel);
    if (cons) for (const c of cons) { const cs = byRel.get(c)?.subsys; if (cs && cs !== key && !cs.startsWith('extra_tests')) consumerCounts.set(cs, (consumerCounts.get(cs) || 0) + 1); }
  }
  const topConsumers = [...consumerCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k, v]) => k + '(' + v + ')');
  const extDeps = new Map();
  for (const f of files) for (const it of importsOf.get(f.rel) || []) if (it.kind === 'external') extDeps.set(it.target, (extDeps.get(it.target) || 0) + 1);
  const topExt = [...extDeps.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k, v]) => k + '(' + v + ')');
  let status;
  if (alive && (dead || uncertain)) status = 'MIXED';
  else if (alive) status = 'ALIVE';
  else if (dead && !uncertain) status = 'DEAD';
  else if (uncertain && !dead) status = 'UNCERTAIN-PKG';
  else if (dead && uncertain) status = 'MIXED-DEAD';
  else if (testC && !alive && !dead && !uncertain) status = 'TEST-ONLY';
  else status = 'EMPTY';
  // wired-in status for standalone: has runtime entry seed?
  const hasRuntimeSeed = (runtimes.find(r => r.key === key)?.seeds.length) || 0;
  const wired = hasRuntimeSeed > 0 ? 'wired-entry' : (reachedSubsysCheck(key) ? 'core-reached' : 'not-core-reached');
  result.subsystems[key] = {
    fileCount: files.length, totalKB: +totalKB.toFixed(1), alive, dead, uncertain, testFiles: testC, status,
    topConsumers, topExt, runtimeSeedCount: hasRuntimeSeed,
    wired,
  };
  result.deadFiles.push(...deadList);
  result.uncertainFiles.push(...uncertainList);
}
function reachedSubsysCheck(key) {
  for (const f of allFiles) if (f.subsys === key && reached.has(f.rel)) return true;
  return false;
}

// biggest 25
result.biggest = allFiles.slice().sort((a, b) => b.kb - a.kb).slice(0, 25).map(f => ({ rel: f.rel, kb: f.kb, subsys: f.subsys }));
result.totalDeadKB = +result.deadFiles.reduce((s, f) => s + f.kb, 0).toFixed(1);
result.totalUncertainKB = +result.uncertainFiles.reduce((s, u) => s + u.kb, 0).toFixed(1);
for (const rt of runtimes) result.runtimeReachSizes[rt.key] = runtimeReach[rt.key] ? runtimeReach[rt.key].size : 0;

// Entry/adapter boundary detection: per subsystem, files that look like entry/adapters
const entryHeuristic = /(createServer|\.listen\(|http\.createServer|Router\(|app\.(get|post|put|delete|use|route)|export\s+\w+\s*=\s*\{|createCommand|registerCommands|bin:|process\.(stdin|argv)|startServer|fetch\()/i;
for (const [key, files] of Object.entries(subsysFiles)) {
  const cands = files.filter(f => {
    const c = getContent(f.rel);
    return /(createServer|\.listen\(|http\.createServer|Router\(|registerCommands|dispatch|handleRequest|fastify|express|nextAdapter|bridge)/i.test(c) && f.rel.includes('index') || /(gateway|server|main|entry|bridge|adapter|client)\.(ts|js)$/.test(f.rel);
  });
  result.boundaries.push({ subsys: key, entries: cands.slice(0, 8).map(f => f.rel) });
}

fs.writeFileSync(path.join(OUT, 'recon-data.json'), JSON.stringify(result, null, 2));
// also dump runtime info + runtime reach separately for readability
fs.writeFileSync(path.join(OUT, 'recon-runtimes.json'), JSON.stringify({ runtimes: runtimes.map(r => ({ key: r.key, via: r.via, seeds: r.seeds, reachSize: runtimeReach[r.key]?.size })), noop: 0 }, null, 2));
console.log('OK reached=', reached.size, 'total=', allFiles.length);
console.log('totalDeadKB=', result.totalDeadKB, 'totalUncertainKB=', result.totalUncertainKB);
console.log('runtimeReach=', JSON.stringify(result.runtimeReachSizes));
