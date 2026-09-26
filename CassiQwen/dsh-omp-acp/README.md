# dsh-omp-acp

Your own oh-my-pi sessions, selectable as models in DeepSeek Harness.

The plugin registers one harness `llm` provider route (`omp`, display name
"Oh My Pi"). Every model it advertises is a **durable oh-my-pi session id**, so
the harness model picker becomes a live view of the omp session store, and one
prompt continues exactly that session — same history, same workspace, same file
that omp and the VSCodium ACP client see.

Nothing here owns conversation state: oh-my-pi keeps the transcript, this
plugin only speaks the Agent Client Protocol to it.

The other direction lives in `../dsh-omp-bridge`: a small OpenAI-compatible
server that lists *harness* sessions as oh-my-pi models and drives a turn in
one, so either window can drive the other.

## How a turn maps

| Harness request | oh-my-pi call |
|---|---|
| `listModels("omp")` | `session/list` — newest 25 non-empty sessions |
| `resolveModel("omp", <session id>)` | session title, cwd, last update |
| `stream()` conversation | `session/resume` + `session/prompt` with **only the newest user-authored message** |
| `stream({ purpose: "session-title" \| "compaction" })` | a throwaway `session/new` in `~/.omp/acp-auxiliary`, closed and deleted afterwards |
| `stream()` to the `new-session` model | `session/new` in the harness agent's cwd, remembered per harness conversation |
| `session/request_permission` | answered from the configured policy, or forwarded to the harness approval service when `permission: ask` |
| `abort` | `session/cancel`, then the connection is released if omp does not stop |

Only messages with `source.kind === "user"` (or no source) become prompts.
The harness also carries harness-authored material in user-role messages —
workspace instructions (`agent-instructions`) and plugin runtime snapshots
(`plugin`) — and those must never enter a real session.

Tool steps inside the omp session are surfaced as **text records** —
`omp tool <title> (kind) → <command>`, then `omp tool call: completed` with an
excerpt of the output — never as harness tool-call blocks. The harness executes
every tool call a provider hands it, so re-emitting omp's calls would run them
twice; the visible answer stays the model's own text.

## Configuration

Rows are declared in `cordis.patch.yml`; the same keys are accepted from any
profile patch.

| Key | Default | Meaning |
|---|---|---|
| `provider` | `omp` | harness route name |
| `providerName` | `Oh My Pi` | picker label |
| `executable` | `$OMP_ACP_EXECUTABLE` or `omp` | path to `omp` |
| `args` | `["acp"]` | argv after the executable |
| `cwd` | process cwd | working directory for spawned agents |
| `maxModels` | `25` | sessions advertised, newest first |
| `maxLiveSessions` | `4` | resumed sessions kept warm before LRU release |
| `idleTimeoutMs` | `900000` | idle time before a resumed session's process is released |
| `promptTimeoutMs` | `1800000` | hard deadline for one prompt |
| `auxiliary` | `ephemeral` | `ephemeral` = real throwaway call; `local` = deterministic text, no model call |
| `auxiliaryCwd` | `~/.omp/acp-auxiliary` | workspace for throwaway sessions |
| `cleanupAuxiliarySessions` | `true` | delete throwaway session files after use |
| `permission` | `allow` | answer to `session/request_permission`: `allow`, `reject`, or `ask` |
| `newSession` | `false` | advertise a `new-session` model that starts a fresh omp session |
| `newSessionName` | `New oh-my-pi session` | picker label of that model |
| `toolActivity` | `true` | surface tool steps as text records |

Use forward slashes in YAML paths. A Windows path inside a `!!js` expression is
a JavaScript string literal, so `'C:\Users\...\omp.exe'` loses `\U`, `\.`, and
turns `\b` into a backspace — the failure surfaces as
`ACP agent failed to start: spawn C:UsersCarina.binomp.exe ENOENT`.

## Install into a profile

A host-only plugin needs no client bundle. Mirror how `dsh-cassi-entity` is
installed:

1. Link the package into the profile:

   ```powershell
   New-Item -ItemType Junction `
     -Path  "$env:USERPROFILE\.dsh\profiles\web\node_modules\@cassi\dsh-omp-acp" `
     -Target "C:\Users\Carina\workspaces\Cassi\CassiQwen\dsh-omp-acp"
   ```

2. Add it to the profile manifest `~/.dsh/profiles/<profile>/package.json`:

   ```json
   "dependencies": { "@cassi/dsh-omp-acp": "file:../../../workspaces/Cassi/CassiQwen/dsh-omp-acp" },
   "dsh": { "profile": { "bundles": ["@deepseek-ai/dsh-base", "@deepseek-ai/dsh-web-app", "@cassi/dsh-omp-acp"] } }
   ```

Uninstall = remove both, plus the junction.

The bundle's own `cordis.patch.yml` supplies the host row — it names the
package (`@cassi/dsh-omp-acp`), not a path, so the profile boots from any
working directory — which is why the plugin needs no profile patch of its own.

## Verify

```bash
node smoke.mjs                     # 22 checks against the real omp acp server
dsh --profile web --dump-config    # shows: # == @cassi/dsh-omp-acp
dsh web --port 8321
```

`smoke.mjs` creates its own throwaway session, drives the whole provider
surface (list, resolve, prompt, auxiliary isolation, cancellation), verifies
the session file received exactly the user text, and removes its artifacts.

In the browser: open the model picker; the "Oh My Pi" group lists your sessions
by title, cwd, and last update. Pick one, send a message, and the reply streams
back — while the same session file gains that exchange.

Harness RPC from the page (same envelope the UI uses):

```js
fetch("/api/session.models", { method: "POST", headers: { "content-type": "application/json" },
  body: JSON.stringify({ type: "client-request", rpcId: "probe", method: "session.models", payload: { sessionId } }) });
```

`llm.providers` lists live routes; a provider whose `listModels` throws appears
under `session.models` → `failures` with the adapter's own message.

## Limitations

- Text in, text out: images and harness tool calls are not forwarded.
- A permission question with `permission: ask` needs an open harness turn and a
  reachable approval service; a question that cannot be asked is allowed, and a
  rejected tool fails inside omp rather than in the harness.
- One agent process per resumed session (LRU-capped, idle-released); a prompt
  per session is serialized.
- Empty sessions (`messageCount === 0`) are hidden from the picker. The plugin
  continues existing sessions unless the `new-session` model is used, which
  creates one in the harness agent's own working directory; which conversation
  owns which fresh session is remembered for the life of the bridge, so a
  restart starts fresh sessions again.
- omp's own mode and sandbox govern tool execution; `permission: allow` only
  answers the ACP permission prompt the same way `autoApprovePermissions` does
  in the VSCodium ACP client.
- The picker re-reads the session list each time it opens; the harness caches
  the advisory catalog per adapter generation, so a session created afterwards
  appears on the next open (or after a restart).
