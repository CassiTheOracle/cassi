# CassiCore WebUI

CassiCore's web interface, based on [agno-agi/agent-ui](https://github.com/agno-agi/agent-ui).

## Stack

- **Next.js 15** (App Router) — UI and Backend-for-Frontend (BFF)
- **Tailwind CSS + shadcn/ui** — styling
- **CassiCore Admin API** — daemon connection (HTTP on port 7432)

## How it works

agent-ui talks to a BFF layer (`src/app/api/`) that translates
Agno's API contract to CassiCore's Admin API:

| Agno route | BFF → CassiCore |
|---|---|
| `GET /health` | `GET :7432/health` (pass-through) |
| `GET /agents` | Synthesized from daemon config |
| `GET /sessions` | `GET :7432/sessions` |
| `GET /sessions/:id/runs` | `GET :7432/sessions/:id/messages` |
| `DELETE /sessions/:id` | `DELETE :7432/sessions/:id` |
| `POST /agents/:id/runs` | `POST :7432/sessions/:id/turn/stream` + SSE translation |
| `GET /cassicore/dialectic/:id` | `GET :7432/dialectic/:id/history` |

### SSE event translation

CassiCore emits `event: token/tool_call/tool_result/dialectic/done/error`.
The BFF translates these to Agno `RunEvent` format:
`RunStarted → RunContent → ToolCallStarted → ToolCallCompleted → RunCompleted`.

Dialectic events (`yang`/`yin`/`synthesis`) map to `ReasoningStep`, rendering
inline in each message's reasoning panel.

## Dev

```bash
# Start CassiCore daemon first
./bin/cassicore

# Then start the webui
cd webui
npm run dev       # → http://localhost:3000
```

## Config

Copy `.env.example` to `.env.local`:

```env
CASSICORE_API_URL=http://localhost:7432     # daemon Admin API
NEXT_PUBLIC_DEFAULT_ENDPOINT=http://localhost:3000  # BFF (this app)
```

For production, set `NEXT_PUBLIC_DEFAULT_ENDPOINT` to the deployed URL and
ensure `CASSICORE_API_URL` is reachable server-side from the Next.js process.
