# dsh-omp-bridge

DeepSeek Harness sessions as models in oh-my-pi — the reverse of `dsh-omp-acp`,
which puts oh-my-pi sessions inside DeepSeek Harness. With both installed each
window can drive the other, and both directions keep the *session* as the thing
that holds the conversation:

```
dsh-omp-acp      harness model picker → an oh-my-pi session       (ACP)
dsh-omp-bridge   oh-my-pi model picker → a harness session        (HTTP/SSE)
```

Nothing here owns conversation state. One request sends the newest user message
into a harness session and streams the assistant's own answer back out; history,
workspace, tools, approvals and compaction stay with the harness session.

## Run

```bash
# 1. the harness (its own port, e.g. the web profile)
dsh web --no-open --port 8787

# 2. the bridge
node bridge.mjs --dsh http://127.0.0.1:8787 --port 8791
```

Then, in oh-my-pi, pick a model — `--model dsh/<session>` or `--model dsh/new`:

```bash
omp --model dsh/new "…"
omp models ls | grep dsh          # every live session, newest first
```

`GET /v1/models` lists one row per live harness session plus `dsh/new`;
`POST /v1/chat/completions` runs one turn (streaming or not). `dsh/new` creates a
harness session on first use and keeps it for that conversation, named by an
`x-dsh-session` header or the OpenAI `user` field; a client that names no
conversation (oh-my-pi names none) shares the one scratch session.

## Sessions read as their titles

A titled session is advertised under its title, so the picker shows what the
session is about instead of a uuid:

```
dsh/refactor-the-field-solver-9f2c1ab4      ← title, then a short id fragment
dsh/29f0c3d1-…                              ← an untitled session keeps its id
dsh/new
```

oh-my-pi names a discovered model after its **id** — a `name` field on the wire
is overwritten by the id, so the title has to be *in* the id. The trailing
fragment is what resolves it back: a request whose model ends in a session's
fragment is routed to that session, and a bare session id still works (it goes
straight through), so old rows and scripts keep working after a rename. Titles
are read from the session's own log (`session/title`) once per log position and
kept live from the event feed.

A rename reaches the picker when oh-my-pi refetches its catalog
(`omp models refresh`) — its `models.db` otherwise serves the rows it discovered
earlier.

## Tool calls that need consent

The harness asks its clients for approval when a tool call needs it (a sandbox
escalation, a policy `ask`); with a browser closed that request would fail
closed. The bridge answers it instead:

```bash
node bridge.mjs --dsh http://127.0.0.1:8787 --approval ask        # prompt on this console (default)
node bridge.mjs --dsh http://127.0.0.1:8787 --approval allow      # consent for whatever is asked
node bridge.mjs --dsh http://127.0.0.1:8787 --approval reject     # refuse everything
```

The prompt reads `[y]es once / [a]lways for this tool / [N]o`, and a question
nobody answers in `--approval-timeout-ms` (2 min) becomes `--approval-on-timeout`
— `reject` by default: an unanswered question is not a yes. A non-terminal stdin
takes that fallback immediately rather than hanging the turn. Whatever is
decided is logged, posted back against the frame's own `rpcId`, and appended to
the turn's own answer (`[bridge: harness approval allowed-once for pwsh — …]`)
so the decision is visible in the oh-my-pi transcript, not only in the bridge's
log.

By default the bridge answers only sessions it has driven a turn for
(`--approval-scope bridge`); a browser session's questions stay with the browser.
`--approval-scope all` takes over every session on the harness.

## Install in oh-my-pi

Declarative — `~/.omp/agent/models.yml` (or a profile's `agent/models.yml`), see
`omp-models.example.yml`:

```yaml
providers:
  dsh:
    baseUrl: http://127.0.0.1:8791/v1
    api: openai-completions
    auth: none
    discovery:
      type: openai-models-list
    modelOverrides:
      new:
        supportsTools: false
        contextWindow: 262144
        maxTokens: 8192
```

Install the same row under a profile (`~/.omp/profiles/<name>/agent/models.yml`)
to try it without touching the default config — a profile resolves its own file
in isolation:

```bash
omp --profile bridge-test models ls
```

## What the harness wire actually is

Measured against harness 0.1.1-rc.2 / oh-my-pi 18.2.8:

| Need | Wire |
|---|---|
| Any call | `POST /api/<method>`, body `{type:"client-request", rpcId, method, payload}` → `{type:"server-response", rpcId, result:{ok:true, value}}` |
| Trust | `Host` must be loopback and `Origin` must be absent or equal — no token exists; Node satisfies this by default |
| Sessions | `session.list` (`{items:[{sessionId, updatedAt, running, blank, cwd, …}]}`), `session.create` (`{cwd}` → `{sessionId}`) |
| One turn | `session.prompt` `{sessionId, mode:"queue"\|"steer", content:[{type:"text", text}]}` — returns `{accepted:true}` immediately, not the answer |
| The answer | WebSocket `GET /api/events.mux`: frames `{type:"server-request", …, payload:{type:"session/event", sessionId, event}}`; text is `assistant/chunk` → `data.chunk.type === "text-delta"` → `.text`, and the turn ends at `turn/end` with the same `data.turn` |
| The transcript | `session.history` — `{events:[{event, view?}], hasMore}`; a session's title is its last `session/title` event (`data.title`) |
| Questions to a client | The same feed carries `payload.type === "approval/requested"` (`{sessionId, approvalId, toolName, callId?, reason?}`) and `question/requested`; they are pushed to every open feed and replayed to a feed that opens while one is pending |
| Answering a question | `POST /api/respond`, body `{type:"client-response", rpcId, result:{ok:true, value:{sessionId, approvalId, outcome}}}` with the frame's own `rpcId` and `outcome` `allowed-once`\|`rejected` → receipt `{accepted:true}` or `{accepted:false, reason:"not-pending"\|"bad-response"}` |

## Traps this bridge is built around

- **A turn's answer is not the prompt's response.** `session.prompt` only
  acknowledges; the answer must be read from the event feed, and only events of
  the turn that *started after* acceptance belong to that prompt.
- **The harness injects its runtime context as a trailing user-role message** on
  a session's first turn. Any model written to echo a prompt must not assume the
  newest user message is the one it was called with.
- **Oh-my-pi caches discovered provider rows for 24 h** in the config
  directory's `models.db`, including an empty result: a listing taken while the
  bridge was down keeps a provider empty until `omp models refresh`. (A profile
  has its own cache, which is how the verification run stays honest.)
- **A piped stdin hides oh-my-pi's prompt.** Spawned with a pipe, `omp -p`
  reads the prompt from stdin and blocks on EOF; drive it with stdin closed.
- **Only the newest user message travels.** System prompts and tool schemas from
  the caller are dropped — the harness session has its own agent, prompt and
  tools, and the bridge does not simulate them.
- **An approval nobody answers fails closed**, and the harness pushes the
  question to *every* connected client — including a browser that is also open.
  The bridge answers only its own sessions by default, and a rejected or
  unanswerable approval is not a silent hang: the tool reports the refusal and
  the turn continues.
- **A question feed that dies turns every later approval into "unavailable".**
  The bridge reconnects, and the harness replays anything still pending.

## Verification

```bash
node verify.mjs          # 41 checks, ~20 s
node verify.mjs --keep   # same fixture, left running for manual poking
```

Self-contained: a stub OpenAI-completions model, a throwaway harness home (real
profile files, junctioned dependencies, its own port and sessions), the bridge,
a throwaway oh-my-pi *profile* holding the shipped `omp-models.example.yml`, and
then real clients — an OpenAI HTTP client and `omp` itself, printing the stub's
answer to prove the whole path. Neither a live session nor the default profile
of the user's is touched. `--keep` prints the fixture's URLs and leaves the
bridge, stub and harness up until Ctrl+C.

The approval checks run against the harness's real sandbox: the stub model is
scripted to write a file the read-only policy denies, retry with a wider mode,
and let that escalation be the question — one bridge allowing it (the file
appears, the session's log records `allowed-once`) and one rejecting it (nothing
is written, the log records `rejected`), with each bridge leaving the other's
session alone.
