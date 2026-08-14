// Recon analysis for cassi-mind migration. Read-only on repo, writes JSON to out dir.
const fs = require('fs');
const path = require('path');

const ROOT = 'D:/carina/workspaces/cassicore';
const OUT = 'C:/Users/Carina/Workspaces/CassiCore';

// Subsystems to inventory (rel dirs from root). Each maps to a top-level subsystem key.
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
};
// Extra: mind-plugin, tests (root /tests not in list but useful)
const EXTRA_DIRS = ['mind-plugin', 'tests', 'test'];

const EXCLUDE_DIRS = new Set([
  'node_modules', 'dist', 'target', '.git', 'build', 'out', '__pycache__',
  '.next', '.nuxt', 'coverage', '.cache', 'package-lock.json', 'bun.lock',
  'pnpm-lock', '.opencode', '.claude', '.serena', '.hermes', '.gitnexus',
  '.playwright-mcp', '.cassicore-teams', 'data', 'vindexes', 'fractals',
  'tmp', '.github', '.githooks', '.vscode', 'charts', 'assets', 'public',
  'static', 'lib', 'vendor', '.turbo', '.yarn', '.cargo',
]);
// Also skip any dir that is a build/cache target containing huge binary dumps
const EXCLUDE_NAME = /^(target|dist|node_modules|\.git|__pycache__|\.next|coverage|build|out)$/;

const SRC_EXTS = new Set(['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs']);

function collect(dir) {
  const abs = path.join(ROOT, dir);
  const files = [];
  const dirs = [];
  if (!fs.existsSync(abs)) return { files, dirs };
  let entries;
  try { entries = fs.readdirSync(abs, { withFileTypes: true }); }
  catch (e) { return { files, dirs }; }
  for (const ent of entries) {
    if (EXCLUDE_NAME.test(ent.name)) continue;
    const rel = path.join(dir, ent.name);
    try {
      if (ent.isDirectory()) dirs.push(rel);
      else if (SRC_EXTS.has(path.extname(ent.name))) {
        const st = fs.statSync(path.join(ROOT, rel));
        files.push({ abs: path.join(ROOT, rel), rel: rel.replace(/\\/g, '/'), kb: +(st.size / 1024).toFixed(2), ext: path.extname(ent.name).slice(1) });
      }
    } catch (e) {}
  }
  return { files, dirs };
}

function walk(dir, acc) {
  const { files, dirs } = collect(dir);
  acc.files.push(...files);
  for (const d of dirs) {
    // skip excluded nested dir names again (e.g. packages/larql/target)
    walk(d, acc);
  }
}

// Map rel-path -> info for all source files
const allFiles = [];  // {abs, rel, kb, ext, subsys, relativeToRoot}
const subsysFor = {}; // rel -> subsys key
const dirToSubsys = {}; // directory -> subsys (for ext dirs outside root listing)

// Walk each subsystem dir and assign
for (const [d, key] of Object.entries(SUBSYS)) {
  const acc = { files: [] };
  if (fs.existsSync(path.join(ROOT, d))) walk(d, acc);
  for (const f of acc.files) {
    f.subsys = key;
    allFiles.push(f);
    subsysFor[f.rel] = key;
  }
}
// mind-plugin / tests
for (const d of EXTRA_DIRS) {
  const acc = { files: [] };
  if (fs.existsSync(path.join(ROOT, d))) walk(d, acc);
  for (const f of acc.files) {
    f.subsys = 'extra_' + d;
    allFiles.push(f);
    subsysFor[f.rel] = f.subsys;
  }
}

const byRel = new Map();
for (const f of allFiles) byRel.set(f.rel, f);

// ---------------- import extraction ----------------
// Returns array of resolved rel paths (or bare module specifiers marked as external)
const importRe = /(?:from\s+|import\s*\(|require\(\s*)['"]([^'"]+)['"]/g;

function extractImports(rel, content) {
  const out = [];
  const seen = new Set();
  let m;
  importRe.lastIndex = 0;
  while ((m = importRe.exec(content)) !== null) {
    const spec = m[1];
    if (seen.has(spec)) continue;
    seen.add(spec);
    if (spec.startsWith('.')) {
      // resolve relative
      const resolved = path.posix.normalize(path.posix.join(path.posix.dirname(rel), spec));
      out.push({ raw: spec, kind: 'rel', target: resolved });
    } else {
      out.push({ raw: spec, kind: 'external', target: spec });
    }
  }
  return out;
}

// ---------------- BFS from entry roots ----------------
const ENTRY_ROOTS = [
  'core/entry/index.ts',
  'core/entry/daemon-main.ts',
  'core/daemon.ts',
  'core/admin-api/index.ts',
  'core/cli/index.ts',
  'mcp/gateway/index.ts',
  'mcp/cassicore-gateway.ts',
  'mcp/scip-server.ts',
  'workers/echo-channel.ts',
  'commands/index.ts',
  'bin/cassicore',
  'bin/cassi-acp',
  'packages/larql/crates/larql-cli/src/main.rs',
  'packages/larql/js/index.ts',
  'packages/larql/src/index.ts',
  'packages/larql/index.ts',
  'ai/src/index.ts',
  'cassi-tui/src/index.ts',
  'cassi-watch/src/index.ts',
  'prism/src/index.ts',
  'webui/src/index.ts',
  'mind-plugin/src/index.ts',
];

// read content cache
const contentCache = new Map();
function getContent(f) {
  if (contentCache.has(f.rel)) return contentCache.get(f.rel);
  let c = '';
  try { c = fs.readFileSync(f.abs, 'utf8'); } catch (e) { c = ''; }
  contentCache.set(f.rel, c);
  return c;
}

// Parse each file's imports
const importsOf = new Map(); // rel -> [{raw,kind,target}]
for (const f of allFiles) {
  importsOf.set(f.rel, extractImports(f.rel, getContent(f)));
}

// BFS reachability
const reached = new Set();
const queue = [];
for (const r of ENTRY_ROOTS) {
  if (byRel.has(r)) { reached.add(r); queue.push(r); }
}
// also add any existing entry root even if not in byRel (e.g .rs, bin) - mark as seed
const seedFiles = [];
for (const r of ENTRY_ROOTS) {
  if (!byRel.has(r)) {
    // maybe it's a bin or rs; attempt to resolve exact path
    if (fs.existsSync(path.join(ROOT, r))) seedFiles.push(r);
  }
}
while (queue.length) {
  const cur = queue.pop();
  const imp = importsOf.get(cur) || [];
  for (const it of imp) {
    if (it.kind !== 'rel') continue;
    let target = it.target;
    // try appending extensions
    let resolved = byRel.get(target);
    if (!resolved) {
      // imports often use .js suffix while source is .ts — try suffix swaps
      for (const cand of [
        target, target + '.ts', target + '.tsx', target + '.js', target + '.jsx',
        target + '.mjs', target + '.cjs',
        target.replace(/\.(?:js|jsx|mjs|cjs)$/, '.ts'),
        target.replace(/\.(?:js|jsx|mjs|cjs)$/, '.tsx'),
        target + '/index.ts', target + '/index.tsx', target + '/index.js',
      ]) {
        if (byRel.has(cand)) { resolved = byRel.get(cand); target = cand; break; }
        // also try dir index variants after suffix swap
        const swapped = cand.replace(/\.(?:js|jsx|mjs|cjs)$/, '');
        if (byRel.has(swapped + '/index.ts')) { resolved = byRel.get(swapped + '/index.ts'); target = swapped + '/index.ts'; break; }
      }
    }
    if (resolved && !reached.has(resolved.rel)) {
      reached.add(resolved.rel);
      queue.push(resolved.rel);
    }
  }
}

// ---------------- classify ----------------
// For each file: check if reached; check if string/comment referenced anywhere (UNCERTAIN)
// Build reverse import map: who imports target rel
const consumers = new Map(); // target rel -> set of importer rels
for (const f of allFiles) {
  for (const it of (importsOf.get(f.rel) || [])) {
    if (it.kind !== 'rel') continue;
    let target = it.target;
    let resolved = byRel.get(target);
    if (!resolved) {
      for (const cand of [
        target, target + '.ts', target + '.tsx', target + '.js', target + '.jsx',
        target + '.mjs', target + '.cjs',
        target.replace(/\.(?:js|jsx|mjs|cjs)$/, '.ts'),
        target.replace(/\.(?:js|jsx|mjs|cjs)$/, '.tsx'),
        target + '/index.ts', target + '/index.tsx', target + '/index.js',
      ]) {
        if (byRel.has(cand)) { resolved = byRel.get(cand); target = cand; break; }
        const swapped = cand.replace(/\.(?:js|jsx|mjs|cjs)$/, '');
        if (byRel.has(swapped + '/index.ts')) { resolved = byRel.get(swapped + '/index.ts'); target = swapped + '/index.ts'; break; }
      }
    }
    if (resolved) {
      if (!consumers.has(resolved.rel)) consumers.set(resolved.rel, new Set());
      consumers.get(resolved.rel).add(f.rel);
    }
  }
}

// String/comment references to a file's basename (without ext) - to find UNCERTAIN
// For UNCERTAIN: file not reached but its module id (basename stem) appears as a string literal in some source
function stem(rel) {
  const b = path.posix.basename(rel).replace(/\.[^.]+$/, '');
  return b;
}

const stemHit = new Map(); // rel -> set of referencing files
const allContent = new Map();
for (const f of allFiles) allContent.set(f.rel, getContent(f));
for (const f of allFiles) {
  const c = allContent.get(f.rel);
  // look for the file's own stem as string/comment ref (avoid matching the file itself's imports by checking, accept noise)
}
// For each unreached file, scan all contents for its stem appearing in string/comment/template
const DEAD_UNSURE = [];
for (const f of allFiles) {
  if (reached.has(f.rel)) continue;
  const s = stem(f.rel);
  if (s.length < 2) continue;
  let referencedAnywhere = false;
  for (const [g, c] of allContent) {
    if (g === f.rel) continue;
    // match stem as a quoted string or in a comment-ish context (heuristic: .includes with quotes or backtick or // or # or path)
    if (c.includes("'" + s + "'") || c.includes('"' + s + '"') || c.includes('`' + s + '`')
        || c.includes(s + '.ts') || c.includes(s + '.js') || c.includes('/' + s) || new RegExp('//[^\\n]*' + s).test(c)
        || new RegExp("#[^\\n]*" + s).test(c)) {
      referencedAnywhere = true;
      if (!stemHit.has(f.rel)) stemHit.set(f.rel, new Set());
      stemHit.get(f.rel).add(g);
    }
    if (referencedAnywhere && (stemHit.get(f.rel)||new Set()).size > 10) break;
  }
}

// ---------------- aggregate report per subsystem ----------------
const result = {
  roots: ENTRY_ROOTS.filter(r=>byRel.has(r)||fs.existsSync(path.join(ROOT,r))),
  subsystems: {},
  deadFiles: [],
  uncertainFiles: [],
  biggest: [],
};

const subsysFiles = {};
for (const f of allFiles) {
  (subsysFiles[f.subsys] = subsysFiles[f.subsys] || []).push(f);
}

for (const key of Object.keys(subsysFiles)) {
  const files = subsysFiles[key].sort((a,b)=>a.rel.localeCompare(b.rel));
  const totalKB = files.reduce((s,f)=>s+f.kb,0);
  let alive = 0, dead = 0, uncertain = 0;
  const aliveList = [], deadList = [], uncertainList = [];
  for (const f of files) {
    if (reached.has(f.rel)) { alive++; aliveList.push(f.rel); }
    else {
      const hasStem = stemHit.has(f.rel) && (stemHit.get(f.rel).size > 0);
      if (hasStem) { uncertain++; uncertainList.push({rel:f.rel,why:'string/comment-ref'}); }
      else { dead++; deadList.push(f.rel); }
    }
  }
  // top consumers of this subsystem's files (who imports into it)
  const consumerCounts = new Map();
  for (const f of files) {
    const cons = consumers.get(f.rel);
    if (cons) for (const c of cons) {
      // count only consumers outside this subsystem
      const cs = subsysFor[c];
      if (cs !== key) consumerCounts.set(cs, (consumerCounts.get(cs)||0)+1);
    }
  }
  const topConsumers = [...consumerCounts.entries()].sort((a,b)=>b[1]-a[1]).slice(0,3).map(([k,v])=>k+'('+v+')');
  // top external deps: import specs that are bare (not relative) across this subsystem's files
  const extDeps = new Map();
  for (const f of files) {
    for (const it of (importsOf.get(f.rel)||[])) {
      if (it.kind==='external') extDeps.set(it.target, (extDeps.get(it.target)||0)+1);
    }
  }
  const topExt = [...extDeps.entries()].sort((a,b)=>b[1]-a[1]).slice(0,3).map(([k,v])=>k+'('+v+')');
  let status;
  if (alive>0 && (dead>0||uncertain>0)) status='MIXED';
  else if (alive>0) status='ALIVE';
  else if (dead>0) status='DEAD';
  else status='UNKNOWN';
  result.subsystems[key] = {
    fileCount: files.length, totalKB: +totalKB.toFixed(1),
    alive, dead, uncertain, status,
    topConsumers, topExt,
  };
  result.deadFiles.push(...deadList.map(r=>({rel:r, kb:byRel.get(r).kb})));
  result.uncertainFiles.push(...uncertainList);
}

// biggest 25 files across whole repo (src files we inventoried)
const biggest = [...allFiles].sort((a,b)=>b.kb-a.kb).slice(0,25);
result.biggest = biggest.map(f=>({path:f.rel, kb:f.kb, subsys:f.subsys}));

// total dead KB
result.totalDeadKB = +result.deadFiles.reduce((s,f)=>s+f.kb,0).toFixed(1);
result.totalUncertainKB = +result.uncertainFiles.reduce((s,u)=>s+byRel.get(u.rel).kb,0).toFixed(1);

// entry/adapter boundary info: for each subsystem find files that are imported by nothing inside but are entry-ish (contain "listen"/"serve"/"start"/register)
result.boundaries = [];
for (const [key, fs_] of Object.entries(subsysFiles)) {
  for (const f of fs_) {
    const c = getContent(f);
    if (/(listen\(|\.serve\(|registerCommands|express|Router\(|app\.(get|post|put|use)|HTTP_SERVER|startServer|listenOn|createServer|\.route\()/i.test(c)) {
      // heuristic entry adapter
    }
  }
}

fs.writeFileSync(path.join(OUT, 'recon-data.json'), JSON.stringify(result, null, 2));
console.log('WROTE', OUT + '/recon-data.json');
console.log('subsys count:', Object.keys(result.subsystems).length);
console.log('total files:', allFiles.length);
console.log('reached files:', reached.size);
console.log('total dead KB:', result.totalDeadKB, 'uncertain KB:', result.totalUncertainKB);
