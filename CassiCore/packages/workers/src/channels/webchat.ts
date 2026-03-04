import { createServer, IncomingMessage, ServerResponse } from 'http';
import { parentPort } from 'node:worker_threads';
import { randomUUID } from 'node:crypto';

type HostMessage =
  | { type: 'init'; config: { port?: number } }
  | { type: 'config:update'; config: Record<string, unknown> }
  | { type: 'message'; payload: { sessionId: string; content: string } }
  | { type: 'shutdown' };

type WorkerMessage =
  | { type: 'ready' }
  | { type: 'message'; payload: { sessionId: string; content: string } }
  | { type: 'error'; message: string };

// Map sessionId -> ServerResponse (SSE connection)
const clients = new Map<string, ServerResponse>();
let serverPort = 3000;
let server = createServer(requestListener);
let keepAliveTimers = new Map<string, NodeJS.Timeout>();

function requestListener(req: IncomingMessage, res: ServerResponse) {
  const url = req.url || '/';
  const method = req.method || 'GET';

  if (method === 'GET' && url === '/') {
    serveHtml(res);
    return;
  }

  if (method === 'POST' && url === '/message') {
    collectJson(req)
      .then((body) => {
        const { sessionId, content } = body as { sessionId?: string; content?: string };
        if (!sessionId || !content) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: false, error: 'missing sessionId or content' }));
          return;
        }

        // Send to host
        const msg: WorkerMessage = { type: 'message', payload: { sessionId, content } };
        parentPort?.postMessage(msg);

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true }));
      })
      .catch((err) => {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: false, error: String(err) }));
      });

    return;
  }

  // SSE endpoint
  if (method === 'GET' && url?.startsWith('/stream/')) {
    const parts = url.split('/');
    const sessionId = parts[2];
    if (!sessionId) {
      res.writeHead(400);
      res.end('missing sessionId');
      return;
    }

    // Setup SSE headers
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'Access-Control-Allow-Origin': '*',
    });
    res.write('\n');

    // Store client
    clients.set(sessionId, res);

    // send an initial comment so client sees connection
    res.write(': connected\n\n');

    // keep-alive ping every 15s
    const t = setInterval(() => {
      if (res.destroyed || res.writableEnded) {
        clearInterval(t);
        keepAliveTimers.delete(sessionId);
        return;
      }
      try {
        res.write(': ping\n\n');
      } catch (e) {
        // ignore — will be cleaned on close
      }
    }, 15000);
    keepAliveTimers.set(sessionId, t);

    req.on('close', () => {
      clients.delete(sessionId);
      const timer = keepAliveTimers.get(sessionId);
      if (timer) clearInterval(timer);
      keepAliveTimers.delete(sessionId);
    });

    return;
  }

  // Unknown route
  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ ok: false, error: 'not_found' }));
}

function serveHtml(res: ServerResponse) {
  const html = `<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>CassiCore Webchat</title>
<style>
  :root{color-scheme: dark light}
  body{background:#0b0f13;color:#cfd8dc;font-family: Inter, ui-sans-serif, system-ui, -apple-system, Roboto, 'Segoe UI', 'Helvetica Neue', Arial;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
  .container{width:720px;max-width:95%;background:#071018;border:1px solid #12232b;padding:18px;border-radius:10px;box-shadow:0 6px 24px rgba(0,0,0,.6)}
  h1{font-size:18px;margin:0 0 12px 0;color:#e6eef3}
  .messages{background:#061017;border:1px solid #0f2730;padding:12px;height:320px;overflow:auto;border-radius:8px;font-family:monospace;font-size:13px}
  .controls{display:flex;gap:8px;margin-top:12px}
  textarea{flex:1;height:72px;background:#041016;color:#dbeef4;border:1px solid #0b2930;padding:8px;border-radius:6px;font-family:inherit}
  button{background:#0f8bff;color:#041016;border:none;padding:10px 14px;border-radius:6px;cursor:pointer}
  .token{color:#dfffe6}
  .meta{font-size:12px;color:#6f8b93;margin-bottom:8px}
</style>
</head>
<body>
<div class="container">
  <h1>CassiCore — Webchat</h1>
  <div class="meta">Session: <span id="sessionId"></span></div>
  <div id="messages" class="messages"></div>
  <div class="controls">
    <textarea id="input" placeholder="Type a message..."></textarea>
    <div style="display:flex;flex-direction:column;gap:8px">
      <button id="send">Send</button>
      <button id="clear">Clear</button>
    </div>
  </div>
</div>
<script>
(function(){
  function uuidv4(){ if(window.crypto && crypto.randomUUID) return crypto.randomUUID(); return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,function(c){var r=Math.random()*16|0,v=c=='x'?r:(r&0x3|0x8);return v.toString(16);}); }
  let sessionId = sessionStorage.getItem('cassicore:webchat:session');
  if(!sessionId){ sessionId = uuidv4(); sessionStorage.setItem('cassicore:webchat:session', sessionId); }
  document.getElementById('sessionId').textContent = sessionId;

  const messagesEl = document.getElementById('messages');
  function appendToken(text){ const span = document.createElement('div'); span.className='token'; span.textContent = text; messagesEl.appendChild(span); messagesEl.scrollTop = messagesEl.scrollHeight; }

  // SSE
  const es = new EventSource('/stream/' + sessionId);
  es.onmessage = function(e){ try{ const parsed = JSON.parse(e.data); if(parsed && parsed.content) appendToken(parsed.content); }catch(err){ appendToken(e.data); } };
  es.onerror = function(){ console.warn('SSE error'); }

  document.getElementById('send').addEventListener('click', send);
  document.getElementById('clear').addEventListener('click', ()=>{ messagesEl.innerHTML=''; });
  document.getElementById('input').addEventListener('keydown', function(e){ if(e.key==='Enter' && (e.ctrlKey||e.metaKey)){ send(); } });

  function send(){ const ta = document.getElementById('input'); const content = ta.value.trim(); if(!content) return; ta.value=''; appendToken('> ' + content); fetch('/message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ sessionId: sessionId, content })}).then(r=>r.json()).then(()=>{}).catch(console.error);
  }
})();
</script>
</body>
</html>`;

  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(html);
}

function collectJson(req: IncomingMessage): Promise<any> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on('data', (c) => chunks.push(Buffer.from(c)));
    req.on('end', () => {
      try {
        const s = Buffer.concat(chunks).toString('utf8');
        resolve(JSON.parse(s));
      } catch (e) {
        reject(e);
      }
    });
    req.on('error', reject);
  });
}

// Handle messages from parent
parentPort?.on('message', (m: HostMessage) => {
  try {
    if (m.type === 'init') {
      if (m.config && typeof m.config.port === 'number') serverPort = m.config.port;

      // Start server here, after config is received
      try {
        server.listen(serverPort, () => {
          parentPort?.postMessage({ type: 'ready' });
          parentPort?.postMessage({ type: 'message', payload: { sessionId: 'system', content: `listening:${serverPort}` } });
        });
      } catch (err: any) {
        if (err.code === 'EADDRINUSE') {
          parentPort?.postMessage({ type: 'error', message: `port ${serverPort} already in use` });
          process.exit(0);
        }
        throw err;
      }
    }

    if (m.type === 'config:update') {
      if (m.config && typeof m.config['port'] === 'number') {
        serverPort = m.config['port'] as number;
      }
    }

    if (m.type === 'message') {
      const payload = m.payload;
      const sse = clients.get(payload.sessionId);
      if (sse && !sse.destroyed) {
        try {
          sse.write('data: ' + JSON.stringify({ content: payload.content }) + '\n\n');
        } catch (e) {
          // ignore write errors
        }
      }
    }

    if (m.type === 'shutdown') {
      // close all SSE connections
      for (const [sid, res] of clients.entries()) {
        try {
          res.end();
        } catch (e) { }
      }
      server.close(() => process.exit(0));
    }
  } catch (err) {
    parentPort?.postMessage({ type: 'error', message: String(err) });
  }
});

// handle listen errors (e.g. port already in use) so the worker doesn't crash repeatedly
server.on('error', (err: any) => {
  if (err.code === 'EADDRINUSE') {
    parentPort?.postMessage({ type: 'error', message: `port ${serverPort} already in use` });
    // exit gracefully with success so plugin host won't keep restarting
    process.exit(0);
  }
  // rethrow other errors
  throw err;
});

// graceful close on process signals
process.on('SIGINT', () => {
  server.close(() => process.exit(0));
});
process.on('SIGTERM', () => {
  server.close(() => process.exit(0));
});
