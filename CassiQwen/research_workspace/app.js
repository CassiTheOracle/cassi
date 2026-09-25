"use strict";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const state = {
  connected: false,
  entityId: "cassi",
  programs: [],
  programId: "",
  pendingProgramAdmission: null,
  programAdmissionInFlight: false,
  program: null,
  ownerSha: "",
  workspace: null,
  workspaceOffset: 0,
  workspaceLimit: 24,
  computations: [],
  eventCursor: 0,
  events: [],
  eventAbort: null,
  embodiedField: {
    latest: null,
    latestAt: "",
    error: "",
    loading: false,
    mode: "live",
    frozen: null,
    replayId: "",
    captures: [],
    selectedRegionKey: "",
    selectedExchangeMeaningKey: "",
    zoom: 1,
  },
  surface: {
    descriptor: null,
    descriptorProgramId: "",
    backends: [],
    sources: [],
    binding: null,
    bindingId: "",
    bindingProgramId: "",
    staleBinding: false,
    publication: null,
    grantProgramId: "",
    mode: "disconnected",
    viewerMode: "observing",
    timer: null,
    authorityTimer: null,
    authorityCheckedAt: 0,
    grantTimer: null,
    polling: false,
    captureCurrent: false,
    epoch: 0,
    frameUrl: "",
    frameGeneration: null,
    frameReceivedAt: 0,
    activeOperationId: "",
    operationProgramId: "",
    lastIntent: null,
    annotationMode: "",
    annotations: [],
    drag: null,
    pendingOperationId: "",
    humanAuthorityConfigured: false,
    missionAuthority: null,
  },
  toastTimer: null,
};

class ApiError extends Error {
  constructor(status, body) {
    super(body?.error || `Request failed with HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.kind = body?.kind || "";
    this.body = body;
  }
}

function now() {
  return new Date().toISOString();
}

function requestId(prefix) {
  return `${prefix}:${crypto.randomUUID()}`;
}

function conciseTitle(brief) {
  const normalized = brief.replace(/\s+/gu, " ").trim();
  const firstSentence = normalized.split(/(?<=[.!?])\s+/u, 1)[0] || normalized;
  if (firstSentence.length <= 96) return firstSentence;
  return `${firstSentence.slice(0, 93).trimEnd()}…`;
}

const RESEARCH_SURFACE_PROFILES = {
  "dedicated-linux-desktop": {
    label: "Cassi's dedicated Linux desktop",
    surface_scope: {
      sources: [{
        backend_id: "linux-xvnc-rfb",
        source_id: "cassi-surface-01",
        observation: ["pixels"],
        operations: [
          "keyboard.key",
          "keyboard.text",
          "pointer.absolute",
          "pointer.button",
          "pointer.wheel",
        ],
      }],
    },
  },
};

function programAdmissionForBrief(brief, context, useLinuxDesktop) {
  const profile = useLinuxDesktop
    ? RESEARCH_SURFACE_PROFILES["dedicated-linux-desktop"]
    : null;
  const signature = JSON.stringify([brief, context, profile?.label ?? null]);
  if (state.pendingProgramAdmission?.signature === signature) {
    return state.pendingProgramAdmission;
  }
  const programId = `research-${crypto.randomUUID().replaceAll("-", "")}`;
  const mission = [
    brief,
    context ? `Additional guidance:\n${context}` : "",
    profile
      ? `Working environment: ${profile.label}. Use only this exact source scope; computer input still requires the separate mission approval.`
      : "",
  ].filter(Boolean).join("\n\n");
  const admission = {
    signature,
    programId,
    body: {
      request_id: requestId("create-program"),
      program_id: programId,
      project_id: programId,
      title: conciseTitle(brief),
      mission,
      initial_question: brief,
      observed_at: now(),
      deliverable: {
        artifact: "research-deliverable.json",
        sections_key: "sections",
        sections: [
          "answer",
          "sources",
          "method",
          "reproducible_result",
          "what_the_result_supports",
          "remaining_uncertainty",
          "next_investigation",
        ],
        document_schema: "cassi.research.deliverable.v1",
        identity_key: "program_id",
        identity_value: programId,
      },
      ...(profile ? {surface_scope: profile.surface_scope} : {}),
    },
  };
  state.pendingProgramAdmission = admission;
  return admission;
}


function text(value, fallback = "") {
  return typeof value === "string" ? value : fallback;
}

function csv(value) {
  return String(value || "").split(",").map((item) => item.trim()).filter(Boolean);
}

function parseJson(value, label) {
  try {
    return JSON.parse(value || "null");
  } catch (error) {
    throw new Error(`${label} is not valid JSON: ${error.message}`);
  }
}

function stableJson(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableJson(value[key])}`).join(",")}}`;
}

async function sha256(value) {
  const bytes = typeof value === "string" ? new TextEncoder().encode(value) : value;
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function inlineText(name, content) {
  return {kind: "inline-text", name, sha256: await sha256(content), content};
}

async function inlineJson(name, value) {
  const canonical = stableJson(value);
  return {kind: "inline-json", name, sha256: await sha256(canonical), value};
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("accept", options.accept || "application/json");

  if (options.body !== undefined) headers.set("content-type", "application/json; charset=utf-8");
  const response = await fetch(path, {
    method: options.method || "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    cache: "no-store",
    credentials: "omit",
    referrerPolicy: "no-referrer",
    signal: options.signal,
  });
  const raw = await response.text();
  let body = null;
  if (raw && response.headers.get("content-type")?.includes("application/json")) {
    try { body = JSON.parse(raw); } catch { body = {error: raw}; }
  }
  if (!response.ok) throw new ApiError(response.status, body || {error: raw});
  return options.raw ? raw : body;
}

async function apiBinaryPage(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("accept", "application/octet-stream");

  headers.set("x-cassi-surface-client", "research-workspace");
  const response = await fetch(path, {
    method: "GET",
    headers,
    cache: "no-store",
    credentials: "omit",
    referrerPolicy: "no-referrer",
    signal: options.signal,
  });
  if (!response.ok) {
    const raw = await response.text();
    let body = null;
    if (raw && response.headers.get("content-type")?.includes("application/json")) {
      try { body = JSON.parse(raw); } catch { body = {error: raw}; }
    }
    throw new ApiError(response.status, body || {error: raw});
  }
  if ((response.headers.get("content-type") || "").split(";")[0].trim().toLowerCase() !== "application/octet-stream") {
    throw new Error(`Surface pixel page has an unsupported media type: ${response.headers.get("content-type") || "missing content-type"}`);
  }
  return {bytes: await response.arrayBuffer(), headers: response.headers};
}

function toast(message, tone = "") {
  const node = $("#toast");
  node.textContent = message;
  node.className = `toast visible ${tone}`.trim();
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => { node.className = "toast"; }, 5000);
}

function setConnected(connected, label) {
  state.connected = connected;
  const node = $("#connection-state");
  node.className = `connection-state ${connected ? "online" : "offline"}`;
  $("span", node).textContent = label || (connected ? "Connected" : "Not connected");
}

async function handleError(error, {refresh = true} = {}) {
  if (error?.name === "AbortError") return;
  if (error instanceof ApiError) {
    if (error.status === 409 || /stale/i.test(error.message)) {
      toast("The field advanced before this command. The current revision is being reloaded; review it before retrying.", "warn");
      if (refresh && state.programId) await refreshProgramViews().catch(() => {});
      return;
    }
    if (error.status === 403) {
      toast(`Capability denied: ${error.message}`, "error");
      return;
    }
    if (error.status === 404) {
      toast(`The requested program object is unavailable or inaccessible: ${error.message}`, "error");
      return;
    }
    if (error.status === 503) {
      if (error.kind === "responsibility-admission-wait") {
        toast(`The field has not retained this responsibility. Review program status before trying again: ${error.message}`, "warn");
      } else {
        toast(`The selected execution lane is unavailable: ${error.message}`, "warn");
      }
      return;
    }
  }
  toast(error?.message || String(error), "error");
}

async function action(label, operation, {refresh = true} = {}) {
  try {
    const result = await operation();
    if (result === null) return null;
    updateOwner(result);
    toast(label);
    if (refresh && state.programId) await refreshProgramViews();
    return result;
  } catch (error) {
    await handleError(error, {refresh});
    return null;
  }
}

function updateOwner(value) {
  const owner = value?.owner || value?.result?.owner;
  if (owner?.state_sha256) {
    state.ownerSha = owner.state_sha256;
    renderOwner();
  }
}

function renderOwner() {
  $("#owner-revision").textContent = state.ownerSha ? `owner ${state.ownerSha.slice(0, 12)}` : "owner —";
}

function programValue(row) {
  return row?.program || row?.result?.program || row;
}

function renderPrograms() {
  const list = $("#program-list");
  list.replaceChildren();
  if (!state.programs.length) {
    const empty = document.createElement("p");
    empty.className = "quiet";
    empty.textContent = "No research programs yet. Create one below.";
    list.append(empty);
    return;
  }
  for (const raw of state.programs) {
    const row = programValue(raw);
    const id = text(row.program_id, text(row.id, "unknown"));
    const button = document.createElement("button");
    button.type = "button";
    button.className = `program-button ${id === state.programId ? "active" : ""}`;
    button.dataset.programId = id;
    const title = document.createElement("strong");
    title.textContent = text(row.title, id);
    const detail = document.createElement("small");
    detail.textContent = text(row.status, text(row.phase, "continuing"));
    button.append(title, detail);
    list.append(button);
  }
}

async function loadPrograms() {
  const response = await api("/v1/programs");
  state.programs = Array.isArray(response?.programs) ? response.programs : [];
  renderPrograms();
  const remembered = sessionStorage.getItem("cassi.workspace.program") || "";
  if (!state.programId && remembered && state.programs.some((row) => {
    const value = programValue(row);
    return value?.program_id === remembered || value?.id === remembered;
  })) await selectProgram(remembered);
}

function accountDetails(entries) {
  const details = document.createElement("dl");
  details.className = "account-details";
  for (const [label, value] of entries) {
    const term = document.createElement("dt");
    term.textContent = label;
    const description = document.createElement("dd");
    description.textContent = value;
    details.append(term, description);
  }
  return details;
}

function renderProgramHeader() {
  const row = programValue(state.program || {});
  $("#program-title").textContent = text(row.title, state.programId);
  $("#program-mission").textContent = text(row.mission, text(row.objective, ""));
  $("#program-status").textContent = text(row.status, text(row.phase, "continuing"));
  $("#welcome").classList.add("hidden");
  $("#program-view").classList.remove("hidden");
  renderOwner();
  renderSurfaceProgramContext();
  const responsibility = row.responsibility;
  const account = $("#program-responsibility");
  account.replaceChildren();
  if (!responsibility || typeof responsibility !== "object") {
    account.textContent = "This program predates the responsibility account.";
    return;
  }
  const consequences = Array.isArray(row.consequence_ledger) ? row.consequence_ledger : [];
  const resolvedReports = new Set(consequences
    .map((assessment) => assessment.consequence || {})
    .filter((item) => item.review_of_assessment_id && item.status === "observed" && item.follow_up == null)
    .map((item) => item.review_of_assessment_id));
  const reviewSelect = $("#consequence-form [name=review_of_assessment_id]");
  reviewSelect.replaceChildren(new Option("New consequence report", ""));
  const openReports = consequences.filter((assessment) => {
    const item = assessment.consequence || {};
    return !resolvedReports.has(assessment.assessment_id)
      && (item.status === "reported" || item.status === "disputed" || Boolean(text(item.follow_up).trim()));
  });
  for (const assessment of openReports) {
    const option = document.createElement("option");
    option.value = text(assessment.assessment_id);
    option.textContent = `Review ${text(assessment.assessment_id).slice(-14)} · ${text(assessment.consequence?.affected, "unspecified group")}`;
    reviewSelect.append(option);
  }
  const heading = document.createElement("h3");
  heading.textContent = "Declared purpose and authority";
  account.append(heading, accountDetails([
    ["Affected people", Array.isArray(responsibility.affected) ? responsibility.affected.join(", ") : "unspecified"],
    ["Intended benefit", text(responsibility.intended_benefit, "unassessed")],
    ["Possible burdens", Array.isArray(responsibility.possible_burdens) ? responsibility.possible_burdens.join(", ") : "unassessed"],
    ["Decision owner", text(responsibility.decision_owner, "unspecified")],
    ["Review question", text(responsibility.review_question, "pending")],
  ]));
  const reportsHeading = document.createElement("h3");
  reportsHeading.textContent = "Recorded consequences";
  account.append(reportsHeading);
  if (!consequences.length) {
    const empty = document.createElement("p");
    empty.textContent = "No reports recorded for this program.";
    account.append(empty);
    return;
  }
  const list = document.createElement("ol");
  list.className = "consequence-list";
  for (const assessment of consequences) {
    const item = assessment.consequence || {};
    const entry = document.createElement("li");
    const title = document.createElement("strong");
    const isResolved = resolvedReports.has(assessment.assessment_id);
    title.textContent = `${text(item.status, "reported")} · ${text(item.dimension, "unspecified area").replaceAll("_", " ")} · ${isResolved ? "follow-up answered" : "caller-reported"}`;
    const observation = document.createElement("p");
    observation.textContent = text(item.observation, "No observation recorded");
    entry.append(title, observation, accountDetails([
      ["Report", text(assessment.assessment_id, "unavailable")],
      ["Affected", text(item.affected, "unspecified")],
      ["Source", text(item.evidence, "unspecified")],
      ["Uncertainty", text(item.uncertainty, "unspecified")],
      ["Follow-up", text(item.follow_up, "none declared")],
      ["Review of", text(item.review_of_assessment_id, "new report")],
    ]));
    list.append(entry);
  }
  account.append(list);
}

async function selectProgram(programId) {
  stopEvents();
  state.programId = programId;
  state.workspaceOffset = 0;
  state.events = [];
  state.eventCursor = Number(sessionStorage.getItem(`cassi.workspace.cursor.${programId}`) || 0);
  sessionStorage.setItem("cassi.workspace.program", programId);
  renderPrograms();
  const [program] = await Promise.all([
    api(`/v1/programs/${encodeURIComponent(programId)}`),
    loadComputations(),
    loadWorkspace(),
  ]);
  state.program = program;
  renderProgramHeader();
  renderEvents();
  startEvents();

  if (state.connected) {
    if (state.surface.bindingId) {
      if (state.surface.bindingProgramId !== programId) {
        surfaceMessage(`This source binding belongs to ${JSON.stringify(state.surface.bindingProgramId)}. Observation continues, but program guidance and all effect controls are disabled until that program is selected or the source is released.`, "warn");
      }
      startSurfacePolling();
    } else if (state.surface.descriptorProgramId !== programId) {
      try { await loadSurfaceDescriptor(); } catch (error) { await handleError(error, {refresh: false}); }
    }
  }
}

async function refreshProgramViews() {
  if (!state.programId) return;
  await Promise.all([loadComputations(), loadWorkspace()]);
}

function workspaceUrl() {
  const query = new URLSearchParams({
    category: $("#workspace-category").value,
    offset: String(state.workspaceOffset),
    limit: String(state.workspaceLimit),
  });
  return `/v1/programs/${encodeURIComponent(state.programId)}/workspace?${query}`;
}

async function loadWorkspace() {
  if (!state.programId) return;
  const response = await api(workspaceUrl());
  updateOwner(response);
  state.workspace = response?.view || response;
  renderWorkspace();
}

function compactJson(value, max = 1800) {
  const rendered = JSON.stringify(value, null, 2);
  return rendered.length > max ? `${rendered.slice(0, max)}\n…` : rendered;
}

function renderWorkspace() {
  const view = state.workspace;
  if (!view) return;
  const page = view.page || {offset: 0, returned: 0, total: 0, limit: state.workspaceLimit};
  $("#workspace-phase").textContent = text(view.phase, "unknown");
  $("#workspace-pause").disabled = view.phase === "paused";
  $("#workspace-resume").disabled = view.phase !== "paused";
  $("#workspace-summary").replaceChildren(
    summaryPiece("Revision", String(view.revision ?? "—")),
    summaryPiece("Field", text(view.field_revision).slice(0, 12) || "—"),
    summaryPiece("Category", text(view.category, "objects")),
    summaryPiece("Visible", String(page.total ?? 0)),
  );
  const rows = $("#workspace-rows");
  rows.replaceChildren();
  for (const [index, row] of (view.rows || []).entries()) rows.append(dataCard(row, index));
  if (!(view.rows || []).length) {
    const empty = document.createElement("p");
    empty.className = "quiet";
    empty.textContent = "Nothing is recorded in this view yet.";
    rows.append(empty);
  }
  const start = page.total ? page.offset + 1 : 0;
  const end = page.offset + page.returned;
  $("#workspace-page").textContent = `${start}–${end} of ${page.total}`;
  $("#workspace-prev").disabled = page.offset <= 0;
  $("#workspace-next").disabled = end >= page.total;
}

function summaryPiece(label, value) {
  const span = document.createElement("span");
  const strong = document.createElement("strong");
  strong.textContent = `${label} `;
  span.append(strong, document.createTextNode(value));
  return span;
}

function dataCard(row, index) {
  const card = document.createElement("article");
  card.className = "data-card";
  const header = document.createElement("header");
  const heading = document.createElement("h3");
  heading.textContent = text(row?.key, text(row?.request_id, text(row?.branch_id, text(row?.comparison_id, text(row?.retention_id, `Record ${index + 1}`)))));
  const schema = document.createElement("span");
  schema.className = "schema";
  schema.textContent = text(row?.schema, "record").replace("cassifi.", "");
  header.append(heading, schema);
  const pre = document.createElement("pre");
  pre.textContent = compactJson(row);
  card.append(header, pre);
  return card;
}

async function workspaceCommand(command) {
  if (!state.workspace?.field_revision) throw new Error("Load the workspace before changing it.");
  const payload = {
    request_id: requestId(`workspace-${command.operation}`),
    expected_owner_state_sha256: state.ownerSha,
    command: {...command, expected_field_revision: state.workspace.field_revision},
    observed_at: now(),
  };
  const result = await api(`/v1/programs/${encodeURIComponent(state.programId)}/workspace`, {method: "POST", body: payload});
  updateOwner(result);
  return result;
}

async function loadComputations() {
  if (!state.programId) return;
  const response = await api(`/v1/programs/${encodeURIComponent(state.programId)}/computations`);
  updateOwner(response);
  state.computations = Array.isArray(response?.computations) ? response.computations : [];
  renderComputations(response?.backends);
}

function renderComputations(backends = null) {
  const list = $("#computation-list");
  list.replaceChildren();
  if (!state.computations.length) {
    const empty = document.createElement("p");
    empty.className = "quiet";
    empty.textContent = "No resident computations. Launch one from the proposal form.";
    list.append(empty);
    return;
  }
  for (const row of state.computations) {
    const id = text(row.computation_id, text(row.task_id, "unknown"));
    const card = document.createElement("article");
    card.className = "computation-card";
    card.dataset.computationId = id;
    const header = document.createElement("header");
    const identity = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = id;
    const detail = document.createElement("p");
    detail.textContent = `${text(row.kind, text(row.program_type, "program"))} · ${text(row.status, "resident")} · ${text(row.placement, "logical-cpu")}`;
    identity.append(title, detail);
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = text(row.status, "resident");
    header.append(identity, chip);
    const actions = document.createElement("div");
    actions.className = "computation-actions";
    for (const [label, value] of [["Inspect", "inspect"], ["Step", "step"], ["Run", "run"], ["Optimize", "optimize"], ["Pause", "pause"], ["Resume", "resume"], ["Cancel", "cancel"]]) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.computationAction = value;
      button.textContent = label;
      if (value === "cancel") button.className = "danger";
      actions.append(button);
    }
    const branches = document.createElement("div");
    branches.className = "branch-controls";
    const branchId = document.createElement("input");
    branchId.placeholder = "Branch ID";
    branchId.dataset.branchId = "";
    const base = document.createElement("input");
    base.placeholder = "Expected base SHA for commit";
    base.dataset.branchBase = "";
    branches.append(branchId, base);
    for (const [label, value] of [["Begin branch", "begin"], ["Commit branch", "commit"], ["Roll back", "rollback"]]) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.branchAction = value;
      button.textContent = label;
      branches.append(button);
    }
    card.append(header, actions, branches);
    list.append(card);
  }
  if (backends) list.dataset.backends = JSON.stringify(backends);
}

async function inspectComputation(id) {
  const response = await api(`/v1/programs/${encodeURIComponent(state.programId)}/computations/${encodeURIComponent(id)}`);
  updateOwner(response);
  $("#inspector-title").textContent = id;
  $("#inspector-json").textContent = JSON.stringify(response, null, 2);
  $("#computation-inspector").classList.remove("hidden");
  $("#computation-inspector").scrollIntoView({behavior: "smooth", block: "start"});
}

async function controlComputation(id, actionName, args = {}) {
  const body = {
    request_id: requestId(`computation-${actionName}`),
    expected_owner_state_sha256: state.ownerSha,
    action: actionName,
    arguments: args,
    observed_at: now(),
  };
  const result = await api(`/v1/programs/${encodeURIComponent(state.programId)}/computations/${encodeURIComponent(id)}/control`, {method: "POST", body});
  updateOwner(result);
  return result;
}

async function branchComputation(id, branchId, actionName, args) {
  const body = {
    request_id: requestId(`branch-${actionName}`),
    expected_owner_state_sha256: state.ownerSha,
    action: actionName,
    branch_id: branchId,
    arguments: args,
    observed_at: now(),
  };
  const result = await api(`/v1/programs/${encodeURIComponent(state.programId)}/computations/${encodeURIComponent(id)}/branches`, {method: "POST", body});
  updateOwner(result);
  return result;
}

function parseSse(raw) {
  const events = [];
  for (const block of raw.split(/\r?\n\r?\n/)) {
    if (!block.trim()) continue;
    let id = null;
    let kind = "message";
    const data = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith("id:")) id = Number(line.slice(3).trim());
      else if (line.startsWith("event:")) kind = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (!data.length) continue;
    try { events.push({id, kind, value: JSON.parse(data.join("\n"))}); } catch { /* Ignore malformed event frames. */ }
  }
  return events;
}

function stopEvents() {
  state.eventAbort?.abort();
  state.eventAbort = null;
  $("#events-state").textContent = "disconnected";
}

function startEvents() {
  stopEvents();
  if (!state.connected || !state.programId) return;
  const controller = new AbortController();
  state.eventAbort = controller;
  eventLoop(controller, state.programId);
}

async function eventLoop(controller, programId) {
  let delay = 500;
  $("#events-state").textContent = "connected";
  while (!controller.signal.aborted && state.programId === programId && state.connected) {
    try {
      const raw = await api(`/v1/programs/${encodeURIComponent(programId)}/events/stream?after=${state.eventCursor}&wait=20`, {raw: true, accept: "text/event-stream", signal: controller.signal});
      for (const event of parseSse(raw)) {
        if (event.id !== null && event.id > state.eventCursor) state.eventCursor = event.id;
        state.events.push(event);
      }
      if (state.events.length > 300) state.events.splice(0, state.events.length - 300);
      sessionStorage.setItem(`cassi.workspace.cursor.${programId}`, String(state.eventCursor));
      renderEvents();
      delay = 500;
    } catch (error) {
      if (controller.signal.aborted) return;
      $("#events-state").textContent = "reconnecting";
      await new Promise((resolve) => setTimeout(resolve, delay));
      delay = Math.min(delay * 2, 8000);
    }
  }
}

function renderEvents() {
  const list = $("#event-list");
  list.replaceChildren();
  $("#event-count").textContent = String(state.events.length);
  if (!state.events.length) {
    const empty = document.createElement("p");
    empty.className = "quiet";
    empty.textContent = state.eventCursor ? `Waiting after durable cursor ${state.eventCursor}.` : "Waiting for the first program event.";
    list.append(empty);
    return;
  }
  for (const event of [...state.events].reverse()) {
    const row = document.createElement("article");
    row.className = "event-row";
    const cursor = document.createElement("span");
    cursor.className = "cursor";
    cursor.textContent = `#${event.id ?? "—"}`;
    const kind = document.createElement("strong");
    kind.textContent = event.kind;
    const detail = document.createElement("pre");
    detail.textContent = compactJson(event.value, 1200);
    row.append(cursor, kind, detail);
    list.append(row);
  }
}
function surfaceRecord(value) {
  let current = value;
  for (let depth = 0; depth < 3 && current && typeof current === "object"; depth++) {
    const nested = current.surface || current.binding || current.result;
    if (!nested || typeof nested !== "object" || Array.isArray(nested)) break;
    current = nested;
  }
  return current && typeof current === "object" ? current : {};
}

function surfaceText(value, fallback = "—") {
  if (typeof value === "string") return value;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "boolean") return value ? "yes" : "no";
  return fallback;
}

function surfaceModeName(value) {
  const mode = String(value || "").trim().toLowerCase().replaceAll("_", "-");
  return ["observing", "assisting", "delegated", "human-control", "paused", "disconnected"].includes(mode) ? mode : "";
}

function surfaceBindingMode(binding = {}) {
  if (binding.detached === true) return "disconnected";
  if (binding.human_control === true) return "human-control";
  if (binding.inhibited === true) return "paused";
  const state = String(binding.state || "").trim().toLowerCase().replaceAll("_", "-");
  if (state === "observation-only") return "observing";
  const explicit = surfaceModeName(binding.mode || binding.control_mode || state);
  if (explicit) return explicit;
  if (["bound", "live", "ready"].includes(state)
      && binding.human_control === false && binding.inhibited === false) return "observing";
  if (binding.human_control === false && binding.inhibited !== true) return "observing";
  return "";
}

function setSurfaceMode(value) {
  const mode = surfaceModeName(value) || "disconnected";
  state.surface.mode = mode;
  const node = $("#surface-mode");
  node.textContent = mode;
  node.className = `chip surface-mode-${mode}`;
  updateSurfaceControls();
}

function surfaceMessage(message, tone = "") {
  const node = $("#surface-message");
  node.textContent = message;
  node.className = `surface-message quiet ${tone}`.trim();
}

function surfaceRequest(path, body = {}, method = "POST") {
  return api(path, {
    method,
    body,
    headers: {"x-cassi-surface-client": "research-workspace"},
  });
}


function stopSurfacePolling() {
  clearInterval(state.surface.timer);
  state.surface.timer = null;
  state.surface.polling = false;
}

function clearSurfaceFrame() {
  const surface = state.surface;
  if (surface.frameUrl) URL.revokeObjectURL(surface.frameUrl);
  surface.frameUrl = "";
  surface.frameGeneration = null;
  surface.frameReceivedAt = 0;
  const image = $("#surface-frame");
  image.removeAttribute("src");
  image.classList.add("hidden");
  $("#surface-frame-empty").classList.remove("hidden");
  $("#surface-frame-status").textContent = "No frame";
  $("#surface-frame-age").textContent = "—";
  $("#surface-frame-coverage").textContent = "—";
  $("#surface-frame-sequence").textContent = "—";
  $("#surface-frame-geometry").textContent = "—";
  $("#surface-overlay").replaceChildren();
}

function surfaceBackendId(row) {
  return surfaceText(row?.backend_id, surfaceText(row?.id, ""));
}

function surfaceSourceId(row) {
  return surfaceText(row?.source_id, surfaceText(row?.id, ""));
}

function surfaceLabel(row, fallback) {
  return surfaceText(row?.title, surfaceText(row?.label, surfaceText(row?.name, fallback)));
}

function supportedStatus(row) {
  if (row?.supported === true || row?.available === true) return true;
  if (row?.supported === false || row?.available === false) return false;
  const status = String(row?.status || row?.capture_state || "").toLowerCase();
  return ["supported", "available", "ready", "running", "active", "bound"].includes(status);
}

function renderSurfaceBackends() {
  const select = $("#surface-backend");
  const previous = select.value;
  select.replaceChildren();
  for (const [index, row] of state.surface.backends.entries()) {
    const option = document.createElement("option");
    option.value = String(index);
    const id = surfaceBackendId(row);
    const status = surfaceText(row?.status, row?.supported === true || row?.available === true ? "supported" : "unavailable");
    const reason = surfaceText(row?.reason, "");
    option.textContent = `${surfaceLabel(row, id || `Backend ${index + 1}`)} · ${status}${reason ? ` · ${reason}` : ""}`;
    option.disabled = !supportedStatus(row);
    select.append(option);
  }
  if (!state.surface.backends.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No authorized backend";
    select.append(option);
  } else if ([...select.options].some((option) => option.value === previous && !option.disabled)) {
    select.value = previous;
  } else {
    const first = [...select.options].find((option) => !option.disabled);
    if (first) select.value = first.value;
  }
  const descriptor = state.surface.descriptor || {};
  if (descriptor.enabled === false) {
    surfaceMessage(surfaceText(descriptor.reason, "Surface support is disabled by the entity."), "warn");
  } else if (!state.surface.backends.some(supportedStatus)) {
    surfaceMessage("No supported and available backend is reported. Unsupported channels are not approximated.", "warn");
  }
  updateSurfaceControls();
}

function selectedSurfaceBackend() {
  const index = Number($("#surface-backend").value);
  return Number.isInteger(index) ? state.surface.backends[index] || null : null;
}

function renderSurfaceSources() {
  const select = $("#surface-source");
  select.replaceChildren();
  for (const [index, row] of state.surface.sources.entries()) {
    const option = document.createElement("option");
    option.value = String(index);
    const id = surfaceSourceId(row);
    const existing = (state.surface.descriptor?.bindings || []).find(
      (binding) => binding.backend_id === surfaceBackendId(selectedSurfaceBackend()) && binding.source_id === id && !binding.detached
    );
    const status = existing ? "bound" : surfaceText(row?.status, surfaceText(row?.capture_state, row?.supported === true || row?.available === true ? "supported" : "not reported"));
    const reason = surfaceText(row?.reason, "");
    option.textContent = `${surfaceLabel(row, id || `Source ${index + 1}`)} · ${status}${reason ? ` · ${reason}` : ""}`;
    option.disabled = !id || (!existing && !supportedStatus(row));
    select.append(option);
  }
  if (!state.surface.sources.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No source available for this backend";
    select.append(option);
  }
  updateSurfaceControls();
}

function selectedSurfaceSource() {
  const index = Number($("#surface-source").value);
  return Number.isInteger(index) ? state.surface.sources[index] || null : null;
}

function operationRows() {
  const binding = state.surface.binding || {};
  const backend = state.surface.backends.find((row) => surfaceBackendId(row) === surfaceBackendId(binding)) || selectedSurfaceBackend() || {};
  const declared = Array.isArray(binding.operations) ? binding.operations : (Array.isArray(backend.operations) ? backend.operations : []);
  return declared.map((row) => typeof row === "string" ? {operation: row, status: "supported"} : row);
}

function surfaceOperationToken(row) {
  return surfaceText(row?.operation, surfaceText(row?.name, ""));
}

function renderSurfaceOperations() {
  const rows = operationRows();
  const supported = rows.filter((row) => surfaceOperationToken(row) && supportedStatus(row));
  const select = $("#surface-operation");
  const previous = select.value;
  select.replaceChildren();
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = supported.length ? "Choose a supported operation" : "No supported operation";
  select.append(placeholder);
  for (const row of supported) {
    const option = document.createElement("option");
    option.value = surfaceOperationToken(row);
    option.textContent = surfaceOperationToken(row);
    select.append(option);
  }
  if (supported.some((row) => surfaceOperationToken(row) === previous)) select.value = previous;

  const optionList = $("#surface-operation-options");
  optionList.replaceChildren();
  for (const row of supported) {
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = surfaceOperationToken(row);
    checkbox.dataset.surfaceGrantOperation = "";
    const name = document.createElement("span");
    name.textContent = surfaceOperationToken(row);
    label.append(checkbox, name);
    optionList.append(label);
  }
  $("#surface-operations").textContent = rows.length
    ? rows.map((row) => `${surfaceOperationToken(row) || "Unnamed"} (${surfaceText(row?.status, "declared")}${row?.reason ? `: ${surfaceText(row.reason, "")}` : ""})`).join(", ")
    : "Not reported";
  updateSurfaceControls();
}

function surfaceAuthoritySummary(value) {
  const data = value && typeof value === "object" ? value : {};
  const allowed = new Set(["none", "active", "granted", "revoked", "suspended", "expired", "human-control", "delegated", "observing", "paused", "unknown", "unavailable", "denied"]);
  const safeState = (candidate) => {
    const stateName = String(candidate || "").trim().toLowerCase().replaceAll("_", "-");
    return allowed.has(stateName) ? stateName : "";
  };
  if (typeof value === "string") return safeState(value) || (value ? "Authority details withheld" : "No active authority");
  const status = safeState(data.status) || safeState(data.state);
  const active = typeof data.active === "boolean" ? (data.active ? "active" : "inactive") : "";
  const lease = safeState(data.lease_state);
  const expires = Number.isFinite(data.expires_ns) ? `expires ${new Date(Number(data.expires_ns) / 1e6).toISOString()}` : "";
  return [status, active, lease, expires].filter(Boolean).join(" · ") || "No active authority";
}

function surfaceWaitSummary(value) {
  const wait = value?.resource_wait || value?.resourceWait || value?.wait || value?.resource_waits;
  if (wait == null || wait === false || (Array.isArray(wait) && !wait.length)) return "Not reported";
  if (typeof wait === "string") return wait.slice(0, 500);
  const rows = Array.isArray(wait) ? wait : [wait];
  return rows.slice(0, 4).map((row) => {
    if (typeof row === "string") return row.slice(0, 180);
    const parts = ["kind", "resource", "reason", "requested_bytes", "available_bytes", "retry_after_ms"]
      .filter((key) => row?.[key] !== undefined)
      .map((key) => `${key}=${surfaceText(row[key])}`);
    return parts.join(", ") || "Resource wait reported";
  }).join(" · ");
}
function surfaceDeclaredModalitySummary(binding, source) {
  const declared = binding.capture_modalities ?? binding.modalities
    ?? source.capture_modalities ?? source.modalities;
  if (typeof declared === "string") return declared.slice(0, 240) || "Not reported";
  if (Array.isArray(declared)) {
    const rows = declared.slice(0, 8).map((item) => {
      if (typeof item === "string") return item.slice(0, 80);
      if (!item || typeof item !== "object") return "";
      const name = surfaceText(item.name, surfaceText(item.modality, surfaceText(item.type, "")));
      const status = surfaceText(item.status, item.available === true ? "available" : "");
      return name ? `${name}${status ? `: ${status}` : ""}` : "";
    }).filter(Boolean);
    return rows.join(" · ") || "Not reported";
  }
  if (declared && typeof declared === "object") {
    const rows = Object.entries(declared).slice(0, 8)
      .filter(([, value]) => value === true || value === false || typeof value === "string")
      .map(([name, value]) => `${name}: ${typeof value === "boolean" ? (value ? "available" : "unavailable") : surfaceText(value)}`);
    return rows.join(" · ") || "Not reported";
  }
  return "Not reported";
}

function surfaceSupplementalSummary(publication) {
  if (!publication || typeof publication !== "object") return "No capture metadata available";
  const summarize = (label, value) => {
    if (value === undefined || value === null) return "";
    if (value === false) return `${label}: unavailable`;
    if (value === true) return `${label}: available`;
    if (typeof value !== "object") return `${label}: metadata supplied`;
    const status = surfaceText(value.status, value.available === true ? "available" : "metadata supplied").slice(0, 80);
    const facts = [];
    const count = Array.isArray(value.nodes) ? value.nodes.length : Array.isArray(value.items) ? value.items.length : null;
    if (count !== null) facts.push(`${count} entries`);
    for (const key of ["sample_rate_hz", "channels", "duration_ms", "format"]) {
      if (value[key] !== undefined && (typeof value[key] === "number" || typeof value[key] === "string")) {
        facts.push(`${key.replaceAll("_", " ")} ${surfaceText(value[key], "").slice(0, 40)}`);
      }
    }
    return `${label}: ${status}${facts.length ? ` (${facts.join(", ")})` : ""}`;
  };
  const accessibility = publication.structure ?? publication.accessibility ?? publication.accessibility_metadata;
  const audio = publication.audio_metadata ?? publication.audio;
  const parts = [summarize("Accessibility", accessibility), summarize("Audio", audio)].filter(Boolean);
  if (parts.some((part) => part.startsWith("Audio:"))) parts.push("audio payload is not fetched or played by this viewer");
  return parts.join(" · ") || "No accessibility or audio metadata reported";
}

function renderSurfaceBinding() {
  const binding = state.surface.binding;
  if (!binding) {
    $("#surface-source-title").textContent = "No source bound";
    $("#surface-bound-source").textContent = "—";
    $("#surface-instance").textContent = "—";
    $("#surface-environment").textContent = "—";
    $("#surface-epoch").textContent = "—";
    $("#surface-input-state").textContent = "—";
    $("#surface-authority").textContent = "No active authority";
    $("#surface-modalities").textContent = "Not reported";
    $("#surface-supplemental").textContent = "No capture metadata available";
    $("#surface-resource-waits").textContent = "Not reported";
    renderSurfaceOperations();
    return;
  }
  const sourceId = surfaceText(binding.source_id, surfaceSourceId(selectedSurfaceSource()));
  const instance = surfaceText(binding.source_instance, surfaceText(binding.source_instance_id, "Not reported"));
  const source = state.surface.sources.find((row) => surfaceSourceId(row) === sourceId) || {};
  $("#surface-source-title").textContent = surfaceLabel(source, sourceId || "Bound source");
  $("#surface-bound-source").textContent = sourceId;
  $("#surface-instance").textContent = instance;
  $("#surface-environment").textContent = surfaceText(binding.environment_incarnation, "Not reported");
  $("#surface-epoch").textContent = `${surfaceText(binding.source_epoch)} / ${surfaceText(binding.geometry_revision)}`;
  $("#surface-input-state").textContent = surfaceText(binding.input_state, surfaceText(binding.capture_state, "Not reported"));
  const authority = binding.authority ?? binding.authority_state
    ?? (binding.human_control === true ? "human-control" : binding.inhibited === true ? "suspended" : null);
  $("#surface-authority").textContent = surfaceAuthoritySummary(authority);
  $("#surface-resource-waits").textContent = surfaceWaitSummary(binding);
  $("#surface-modalities").textContent = surfaceDeclaredModalitySummary(binding, source);
  $("#surface-supplemental").textContent = surfaceSupplementalSummary(state.surface.publication);
  renderSurfaceOperations();
}
function renderSurfaceVisualCapability() {
  const descriptor = state.surface.descriptor || {};
  const visual = descriptor.brain_visual ?? descriptor.visual_input ?? descriptor.brain?.visual;
  if (visual === undefined || visual === null) {
    $("#surface-brain-visual").textContent = "Unavailable · no accepted visual-payload capability reported";
    return;
  }
  if (typeof visual === "string") {
    const status = visual.trim().toLowerCase();
    const known = ["supported", "available", "ready", "unavailable", "unsupported", "denied", "degraded"];
    $("#surface-brain-visual").textContent = known.includes(status)
      ? status
      : "Unavailable · visual-payload acceptance is not explicitly reported";
    return;
  }
  const supported = visual.supported === true || visual.available === true
    || ["supported", "available", "ready"].includes(String(visual.status || "").toLowerCase());
  const status = supported ? surfaceText(visual.status, "supported")
    : surfaceText(visual.status, "unavailable");
  const reason = surfaceText(visual.reason, "");
  $("#surface-brain-visual").textContent = `${status}${reason ? ` · ${reason}` : ""}`;
}

function renderSurfaceProgramContext() {
  const program = programValue(state.program || {});
  $("#surface-current-objective").textContent = surfaceText(program.mission, surfaceText(program.objective, "No current objective is recorded on this program."));
  if (!state.surface.lastIntent) {
    $("#surface-expected").textContent = surfaceText(program.expected_consequence, "No expected consequence recorded on this program.");
    $("#surface-outcome").textContent = "No operation result yet.";
    $("#surface-uncertainty").textContent = "—";
  }
  if (state.surface.activeGrant && state.surface.grantProgramId !== state.programId) {
    $("#surface-authority").textContent = `Delegated authority remains scoped to prior program ${JSON.stringify(state.surface.grantProgramId)}; no action is enabled here.`;
  }
  updateSurfaceControls();
}

function updateSurfaceControls() {
  const surface = state.surface;
  const hasBinding = Boolean(surface.bindingId);
  const bound = Boolean(state.connected && hasBinding);
  const program = programValue(state.program || {});
  const activeProgram = String(program.status || "").toLowerCase() === "active";
  const operation = $("#surface-operation")?.value || "";
  const operationAllowed = Boolean(operation && surface.activeGrant?.operations?.includes(operation));
  const publication = surface.publication || {};
  const generation = surfaceGeneration(publication);
  const geometryValid = surface.sourceEpochValid === true && surface.geometryValid === true
    && publication.source_epoch !== undefined && publication.geometry_revision !== undefined
    && String(publication.source_epoch) === String(surface.binding?.source_epoch)
    && String(publication.geometry_revision) === String(surface.binding?.geometry_revision);
  const pixelsCurrent = surface.captureCurrent === true && Boolean(surface.frameUrl)
    && generation !== null && String(surface.frameGeneration) === String(generation);
  const programMatchesBinding = !surface.bindingProgramId || surface.bindingProgramId === state.programId;
  const currentObservation = bound && programMatchesBinding && !surface.staleBinding && geometryValid && pixelsCurrent;
  const authorityExpiryNs = Number(surface.missionAuthority?.expires_ns);
  const authorityFresh = surface.missionAuthority?.active === true && Number.isFinite(authorityExpiryNs)
    && authorityExpiryNs > Number(BigInt(Date.now()) * 1_000_000n);
  const canAssist = bound && programMatchesBinding && !surface.staleBinding && !surface.pendingOperationId
    && ["observing", "assisting", "delegated", "human-control"].includes(surface.mode);
  const canDelegate = currentObservation && authorityFresh && !surface.safetyBlocked && activeProgram && !surface.pendingOperationId
    && ["observing", "assisting"].includes(surface.mode);
  let scopeMatches = false;
  if (surface.activeGrant?.scope) {
    try { scopeMatches = stableJson(surfaceMissionScope()) === stableJson(surface.activeGrant.scope); } catch { scopeMatches = false; }
  }
  const expiresNs = Number(surface.activeGrant?.expires_ns);
  const grantFresh = surface.activeGrant && Number.isFinite(expiresNs)
    && expiresNs > Number(BigInt(Date.now()) * 1_000_000n);
  const grantUsable = currentObservation && surface.mode === "delegated" && grantFresh && scopeMatches
    && surface.grantProgramId === state.programId;
  const selectedOperations = selectedSurfaceOperations();
  const grantUpdates = Number($("#surface-grant-updates").value);
  const grantDuration = Number(new FormData($("#surface-intent-form")).get("grant_duration"));
  const approvedUpdates = Number($("#surface-authority-updates").value);
  const approvalDuration = Number($("#surface-authority-duration").value);
  $("#surface-approve-authority").disabled = !currentObservation || !activeProgram || !surface.humanAuthorityConfigured
    || !selectedOperations.length || selectedOperations.length > 16
    || !Number.isInteger(grantUpdates) || grantUpdates < 1 || grantUpdates > approvedUpdates
    || !Number.isInteger(approvedUpdates) || approvedUpdates < 1 || approvedUpdates > 4096
    || !Number.isInteger(approvalDuration) || approvalDuration < 60 || approvalDuration > 86400
    || !Number.isInteger(grantDuration) || grantDuration < 10 || grantDuration > 3600;
  $("#surface-grant-updates").max = String(Math.min(4096, surface.missionAuthority?.max_updates || 4096));
  $("#surface-intent-form input[name='grant_duration']").max = String(
    Math.min(3600, surface.missionAuthority?.max_lease_seconds || 3600)
  );
  $("#surface-refresh-sources").disabled = !state.connected || !state.programId;
  $("#surface-backend").disabled = !state.connected || !state.programId || hasBinding;
  $("#surface-source").disabled = !state.connected || !state.programId || hasBinding;
  $("#surface-bind").disabled = !state.connected || !state.programId || hasBinding || !selectedSurfaceSource() || !supportedStatus(selectedSurfaceBackend());
  $("#surface-grant-operations").disabled = !currentObservation || !activeProgram || Boolean(surface.pendingOperationId);
  const selectedLeaseApproved = selectedOperations.length > 0
    && selectedOperations.every((item) => surface.missionAuthority?.operations?.includes(item));
  const leaseDurationApproved = Number.isInteger(grantDuration) && grantDuration >= 10
    && grantDuration <= Number(surface.missionAuthority?.max_lease_seconds || 0);
  $("#surface-delegate").disabled = !canDelegate || !selectedLeaseApproved
    || !Number.isInteger(grantUpdates) || grantUpdates < 1
    || grantUpdates > Number(surface.missionAuthority?.max_updates || 0)
    || !leaseDurationApproved;
  $("#surface-assist").disabled = !canAssist;
  $("#surface-operation").disabled = !grantUsable || $("#surface-operation").options.length <= 1;
  $("#surface-submit-intent").disabled = !grantUsable || !operationAllowed || !currentObservation || Boolean(surface.pendingOperationId) || surface.safetyBlocked === true;
  $("#surface-take-control").disabled = !currentObservation || !activeProgram || !surface.humanAuthorityConfigured
    || !["observing", "assisting"].includes(surface.mode) || !selectedOperations.length || surface.safetyBlocked === true;
  $("#surface-release-human").disabled = !bound || surface.mode !== "human-control";
  $("#surface-resume").disabled = !bound || surface.mode !== "paused";
  $("#surface-detach").disabled = !bound;
  $("#surface-clear-annotation").disabled = !surface.annotations.length;
  $("#surface-annotate-point").disabled = !currentObservation;
  $("#surface-annotate-region").disabled = !currentObservation;
  $("#surface-reconcile-submit").disabled = !state.connected || !surface.operationProgramId || !surface.pendingOperationId;
  if (surface.pendingOperationId) $("#surface-reconcile").classList.remove("hidden");
  else $("#surface-reconcile").classList.add("hidden");
}

async function loadSurfaceDescriptor() {
  if (!state.programId) {
    surfaceMessage("Select an existing program before loading mission-scoped surface capabilities.", "warn");
    return null;
  }
  const query = new URLSearchParams({program_id: state.programId});
  const response = await api(`/v1/surface?${query}`);
  const descriptor = surfaceRecord(response);
  state.surface.descriptor = descriptor;
  state.surface.descriptorProgramId = state.programId;
  state.surface.backends = Array.isArray(descriptor.backends) ? descriptor.backends
    : (Array.isArray(descriptor.environments) ? descriptor.environments : []);
  renderSurfaceVisualCapability();
  renderSurfaceBackends();
  if (state.surface.backends.length && !$("#surface-backend").disabled) await loadSurfaceSources();
  if (!state.surface.bindingId) {
    const attached = Array.isArray(descriptor.bindings)
      ? descriptor.bindings.filter((binding) => binding && !binding.detached) : [];
    if (attached.length === 1) adoptSurfaceBinding(attached[0], {reconnecting: true});
  }
  return descriptor;
}

async function loadSurfaceSources() {
  const backend = selectedSurfaceBackend();
  state.surface.sources = [];
  renderSurfaceSources();
  if (!backend || !state.connected || !state.programId) return;
  const backendId = surfaceBackendId(backend);
  if (!backendId) throw new Error("The entity did not provide a backend identifier.");
  const query = new URLSearchParams({backend_id: backendId, program_id: state.programId});
  const response = await api(`/v1/surface/sources?${query}`);
  state.surface.sources = Array.isArray(response?.sources) ? response.sources : [];
  renderSurfaceSources();
  if (!state.surface.sources.length) {
    surfaceMessage(surfaceText(response?.reason, "No source is currently available for this backend."), "warn");
  } else {
    surfaceMessage("Sources discovered. Binding starts in observing mode and does not send application input.");
  }
}

async function bindSurfaceSource() {
  const surface = state.surface;
  if (surface.bindingId) throw new Error("Release the current source binding before binding another; an existing source is never silently abandoned.");
  if (surface.pendingOperationId) throw new Error("Reconcile the previous operation before binding another source; unresolved effects remain pinned to their evidence.");
  if (!state.programId) throw new Error("Select an existing program before binding a mission-scoped source.");
  const backend = selectedSurfaceBackend();
  const source = selectedSurfaceSource();
  if (!backend || !source) throw new Error("Choose an available backend and source before binding.");
  const backendId = surfaceBackendId(backend);
  const sourceId = surfaceSourceId(source);
  if (!backendId || !sourceId) throw new Error("The source descriptor is missing a stable identifier.");
  const existing = (surface.descriptor?.bindings || []).find(
    (binding) => binding.backend_id === backendId && binding.source_id === sourceId && !binding.detached
  );
  const binding = existing || surfaceRecord(await surfaceRequest(
    "/v1/surface/bind", {program_id: state.programId, backend_id: backendId, source_id: sourceId}
  ));
  adoptSurfaceBinding(binding, {reconnecting: Boolean(existing)});
  return binding;
}

function adoptSurfaceBinding(binding, {reconnecting = false} = {}) {
  const surface = state.surface;
  const sourceId = surfaceText(binding.source_id, "");
  if (!sourceId) throw new Error("The entity returned a binding without a source identifier.");
  const bindingId = surfaceText(binding.binding_id, surfaceText(binding.id, ""));
  if (!bindingId) throw new Error("The entity returned no binding identifier. The source scope cannot be safely adopted or controlled.");
  const bindingMode = surfaceBindingMode(binding);
  const observing = bindingMode === "observing";
  const metadataValid = String(binding.source_id || "") === sourceId
    && binding.source_epoch !== undefined && binding.source_epoch !== null
    && binding.geometry_revision !== undefined && binding.geometry_revision !== null
    && Boolean(surfaceText(binding.source_instance, surfaceText(binding.source_instance_id, "")))
    && Boolean(surfaceText(binding.environment_incarnation, ""))
    && Number.isInteger(Number(binding.width)) && Number(binding.width) > 0
    && Number.isInteger(Number(binding.height)) && Number(binding.height) > 0
    && binding.capture_state !== undefined && binding.input_state !== undefined
    && Array.isArray(binding.operations);
  stopSurfacePolling();
  surface.epoch += 1;
  clearSurfaceFrame();
  surface.binding = binding;
  surface.bindingId = bindingId;
  surface.bindingProgramId = state.programId;
  surface.staleBinding = !metadataValid || !bindingMode || bindingMode === "disconnected";
  surface.publication = null;
  surface.captureCurrent = false;
  clearSurfaceGrant(surface);
  surface.sourceEpochValid = metadataValid;
  surface.geometryValid = metadataValid;
  surface.safetyBlocked = !metadataValid || !bindingMode || binding.inhibited === true
    || ["human-control", "delegated"].includes(bindingMode);
  surface.staleBinding = !metadataValid || !bindingMode || bindingMode === "disconnected";
  surface.publication = null;
  surface.captureCurrent = false;
  clearTimeout(surface.authorityTimer);
  surface.authorityTimer = null;
  surface.humanAuthorityConfigured = false;
  surface.missionAuthority = null;
  $("#surface-human-authority-status").textContent = "Checking host mission approval for this source binding.";
  renderSurfaceAnnotations();
  if (!reconnecting && (!observing || !metadataValid)) {
    surfaceMessage("The entity returned a binding without complete source identity or confirmed observing mode. Control is disabled; inspect or release this binding.", "error");
    updateSurfaceControls();
    throw new Error("The returned binding is incomplete or not observe-only; it remains visible so it can be inspected or safely released.");
  }
  surfaceMessage(reconnecting
    ? "Attached to the existing source without rebinding or interrupting the environment."
    : "Source bound in observing mode. No application input is enabled.");
  if (metadataValid) startSurfacePolling();
  return binding;
}

function startSurfacePolling() {
  stopSurfacePolling();
  if (!state.connected || !state.surface.bindingId) return;
  state.surface.authorityCheckedAt = Date.now();
  void refreshSurfaceStatus().catch((error) => handleError(error, {refresh: false}));
  state.surface.timer = setInterval(() => {
    if (document.hidden) return;
    void refreshSurfaceCapture({quiet: true});
    if (Date.now() - state.surface.authorityCheckedAt >= 5000) {
      state.surface.authorityCheckedAt = Date.now();
      void refreshSurfaceAuthorityStatus().catch((error) => handleError(error, {refresh: false}));
    }
  }, 1200);
}


function cleanSurfaceValue(value) {
  return String(value ?? "").trim();
}

function validateBoundedJson(value) {
  let nodes = 0;
  function visit(item, depth) {
    nodes += 1;
    if (nodes > 128 || depth > 8) throw new Error("The JSON payload exceeds the entity's 128-node or 8-level bound.");
    if (typeof item === "string") {
      if (item.length > 512) throw new Error("JSON strings must be at most 512 characters.");
    } else if (typeof item === "number") {
      if (!Number.isFinite(item)) throw new Error("JSON numbers must be finite.");
    } else if (Array.isArray(item)) {
      for (const child of item) visit(child, depth + 1);
    } else if (item && typeof item === "object") {
      if (Object.getPrototypeOf(item) !== Object.prototype && Object.getPrototypeOf(item) !== null) throw new Error("JSON objects must be plain objects.");
      for (const [key, child] of Object.entries(item)) {
        if (key.length > 64) throw new Error("JSON object keys must be at most 64 characters.");
        visit(child, depth + 1);
      }
    } else if (item !== null && typeof item !== "boolean") {
      throw new Error("The JSON payload contains an unsupported value.");
    }
  }
  visit(value, 0);
  if (new TextEncoder().encode(JSON.stringify(value)).byteLength > 8192) throw new Error("The JSON payload must be at most 8 KiB.");
  return value;
}
function surfaceGeneration(publication) {
  return publication?.generation ?? publication?.publication_generation ?? publication?.id ?? null;
}

function surfacePixelLength(publication) {
  const value = publication?.byte_length ?? publication?.pixels_byte_length ?? publication?.total_byte_length;
  const length = Number(value);
  return Number.isSafeInteger(length) && length > 0 ? length : 0;
}


async function readSurfacePixels(bindingId, publication, generation) {
  const total = surfacePixelLength(publication);
  if (!total) throw new Error("The publication did not declare its total pixel byte length.");
  const format = String(publication.pixel_format || "").toLowerCase().trim();
  const channels = format === "rgba8" || format === "bgra8" ? 4 : format === "rgb8" ? 3 : format === "gray8" ? 1 : 0;
  const width = Number(publication.width);
  const height = Number(publication.height);
  const rowStride = Number(publication.row_stride ?? publication.stride ?? width * channels);
  if (!channels || !Number.isInteger(width) || !Number.isInteger(height) || width < 1 || height < 1
      || width * height > 16_777_216 || !Number.isInteger(rowStride) || rowStride < width * channels
      || !Number.isSafeInteger(rowStride * height) || total !== rowStride * height) {
    throw new Error(`The publication pixel format, dimensions, stride, or byte length is unsupported: ${format || "unspecified"} ${width}×${height}.`);
  }
  const declaredLimit = Number(state.surface.binding?.limits?.max_capture_bytes
    ?? state.surface.descriptor?.limits?.max_capture_bytes ?? 64 * 1024 * 1024);
  const maximum = Number.isSafeInteger(declaredLimit) && declaredLimit > 0 ? Math.min(declaredLimit, 64 * 1024 * 1024) : 64 * 1024 * 1024;
  if (total > maximum) throw new Error(`The ${total.toLocaleString()}-byte surface exceeds the viewer's declared ${maximum.toLocaleString()}-byte frame bound.`);
  const chunks = [];
  const pageSize = 1024 * 1024;
  for (let offset = 0; offset < total; offset += pageSize) {
    const length = Math.min(pageSize, total - offset);
    const query = new URLSearchParams({program_id: state.surface.bindingProgramId, offset: String(offset), length: String(length)});
    const path = `/v1/surface/bindings/${encodeURIComponent(bindingId)}/publications/${encodeURIComponent(String(generation))}/pixels?${query}`;
    const page = await apiBinaryPage(path);
    const bytes = new Uint8Array(page.bytes);
    const pageGeneration = page.headers.get("x-surface-generation");
    const pageOffset = Number(page.headers.get("x-surface-offset"));
    const pageLength = Number(page.headers.get("x-surface-page-length"));
    const totalLength = Number(page.headers.get("x-surface-total-byte-length"));
    const pageFormat = page.headers.get("x-surface-pixel-format");
    if (pageGeneration !== String(generation) || pageOffset !== offset || pageLength !== bytes.byteLength
        || totalLength !== total || pageFormat?.toLowerCase() !== format || bytes.byteLength !== length) {
      throw new Error("The pixel page headers or bytes do not match the requested publication generation, range, format, and total extent.");
    }
    chunks.push(bytes);
  }
  return chunks;
}

async function surfaceFrameBlob(publication, chunks) {
  const format = String(publication.pixel_format || "").toLowerCase().trim();
  const channels = format === "rgba8" || format === "bgra8" ? 4
    : format === "rgb8" ? 3
      : format === "gray8" ? 1 : 0;
  if (!channels) throw new Error(`The source pixel format "${format || "unspecified"}" is not a supported raw browser frame format.`);
  const width = Number(publication.width);
  const height = Number(publication.height);
  const rowStride = Number(publication.row_stride ?? publication.stride ?? width * channels);
  if (!Number.isInteger(width) || !Number.isInteger(height) || width < 1 || height < 1 || width * height > 16_777_216) {
    throw new Error("The raw pixel frame has invalid or excessive dimensions.");
  }
  if (!Number.isInteger(rowStride) || rowStride < width * channels) throw new Error("The raw pixel row stride is invalid.");
  const total = surfacePixelLength(publication);
  const source = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    source.set(chunk, offset);
    offset += chunk.byteLength;
  }
  if (offset !== total || source.byteLength !== rowStride * height) throw new Error("Raw pixel bytes do not match their declared geometry and stride.");

  let rgba;
  if (format === "rgba8" && rowStride === width * 4) {
    rgba = new Uint8ClampedArray(source.buffer);
  } else {
    rgba = new Uint8ClampedArray(width * height * 4);
    for (let y = 0; y < height; y++) {
      const row = y * rowStride;
      const target = y * width * 4;
      for (let x = 0; x < width; x++) {
        const sourceIndex = row + x * channels;
        const targetIndex = target + x * 4;
        if (format === "bgra8") {
          rgba[targetIndex] = source[sourceIndex + 2];
          rgba[targetIndex + 1] = source[sourceIndex + 1];
          rgba[targetIndex + 2] = source[sourceIndex];
          rgba[targetIndex + 3] = source[sourceIndex + 3];
        } else if (format === "rgb8") {
          rgba[targetIndex] = source[sourceIndex];
          rgba[targetIndex + 1] = source[sourceIndex + 1];
          rgba[targetIndex + 2] = source[sourceIndex + 2];
          rgba[targetIndex + 3] = 255;
        } else {
          const gray = source[sourceIndex];
          rgba[targetIndex] = gray;
          rgba[targetIndex + 1] = gray;
          rgba[targetIndex + 2] = gray;
          rgba[targetIndex + 3] = 255;
        }
      }
    }
  }
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", {alpha: false});
  if (!context) throw new Error("This browser cannot render the source pixel format.");
  context.putImageData(new ImageData(rgba, width, height), 0, 0);
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
  if (!blob) throw new Error("The browser could not encode the captured frame for display.");
  return blob;
}

function formatSurfaceAge(publication, receivedAt) {
  const age = publication.age_ms != null ? Number(publication.age_ms)
    : (publication.age_ns != null ? Number(publication.age_ns) / 1e6 : NaN);
  if (Number.isFinite(age) && age >= 0) return `${Math.round(age + Date.now() - receivedAt)} ms`;
  const sample = publication.sample_time_ns != null ? Number(publication.sample_time_ns) : NaN;
  const receipt = publication.receipt_time_ns != null ? Number(publication.receipt_time_ns) : NaN;
  const sampleDomain = String(publication.sample_clock_domain || publication.clock_domain || "");
  const receiptDomain = String(publication.receipt_clock_domain || publication.clock_domain || "");
  if (Number.isFinite(sample) && Number.isFinite(receipt) && sampleDomain && sampleDomain === receiptDomain && receipt >= sample) {
    const elapsed = (receipt - sample) / 1e6 + Date.now() - receivedAt;
    if (Number.isFinite(elapsed) && elapsed >= 0) return `${Math.round(elapsed)} ms`;
  }
  return sampleDomain ? `Unknown · ${sampleDomain} clock` : "Unknown · no comparable source clock";
}

function formatSurfaceCoverage(coverage) {
  if (coverage === null || coverage === undefined) return "Not reported";
  if (typeof coverage === "string" || typeof coverage === "number") return String(coverage);
  if (typeof coverage !== "object") return "Not reported";
  const keys = ["coverage_percent", "fraction", "complete", "skipped_intervals", "coalesced_updates", "truncated_nodes", "dropped_events", "unknown_regions", "stale_channels"];
  const parts = keys.filter((key) => coverage[key] !== undefined).map((key) => {
    const value = coverage[key];
    const detail = Array.isArray(value)
      ? `${value.length}${value.length && key === "skipped_intervals"
        ? ` (${value.slice(0, 2).map((row) => surfaceText(row?.reason, "unclassified")).join(", ")})` : ""}`
      : surfaceText(value, compactJson(value, 100));
    return `${key.replaceAll("_", " ")}: ${detail}`;
  });
  return parts.length ? parts.join(" · ") : compactJson(coverage, 260);
}

function validateSurfacePublication(publication) {
  const surface = state.surface;
  const binding = surface.binding || {};
  const sourceEpoch = publication?.source_epoch;
  const geometry = publication?.geometry_revision;
  const epochValid = sourceEpoch !== undefined && sourceEpoch !== null
    && binding.source_epoch !== undefined && binding.source_epoch !== null
    && String(sourceEpoch) === String(binding.source_epoch);
  const geometryValid = geometry !== undefined && geometry !== null
    && binding.geometry_revision !== undefined && binding.geometry_revision !== null
    && String(geometry) === String(binding.geometry_revision);
  surface.sourceEpochValid = epochValid;
  surface.geometryValid = geometryValid;
  if (!epochValid || !geometryValid) {
    surface.staleBinding = true;
    surface.captureCurrent = false;
    clearSurfaceGrant(surface);
    surface.annotations = surface.annotations.filter((annotation) => Boolean(annotation.request_id && annotation.program_id));
    surface.annotationMode = "";
    surface.drag = null;
    clearSurfaceFrame();
    renderSurfaceAnnotations();
    surfaceMessage(!epochValid
      ? "Source epoch is missing or changed. This binding is stale; rebind before annotation or control."
      : "Geometry revision is missing or changed. Rebind before annotation or control.", "warn");
    updateSurfaceControls();
    return false;
  }
  surface.captureCurrent = true;
  return true;
}

async function refreshSurfaceCapture({quiet = false, retryPixels = false} = {}) {
  const surface = state.surface;
  const bindingId = surface.bindingId;
  const token = surface.epoch;
  if (!bindingId || !state.connected || surface.polling || document.hidden) return;
  surface.polling = true;
  try {
    const query = new URLSearchParams({program_id: surface.bindingProgramId});
    const response = await api(`/v1/surface/bindings/${encodeURIComponent(bindingId)}/capture?${query}`);
    if (surface.epoch !== token || surface.bindingId !== bindingId || document.hidden) return;
    const publication = response?.publication && typeof response.publication === "object" ? response.publication : surfaceRecord(response);
    surface.publication = publication;
    if (!validateSurfacePublication(publication)) return;
    $("#surface-supplemental").textContent = surfaceSupplementalSummary(publication);
    const generation = surfaceGeneration(publication);
    if (generation === null || generation === undefined) throw new Error("The capture endpoint returned no immutable publication generation.");
    const receivedAt = Date.now();
    surface.frameReceivedAt = receivedAt;
    $("#surface-frame-age").textContent = formatSurfaceAge(publication, receivedAt);
    $("#surface-frame-coverage").textContent = formatSurfaceCoverage(publication.coverage);
    $("#surface-frame-sequence").textContent = surfaceText(publication.sequence, "—");
    $("#surface-frame-geometry").textContent = surfaceText(publication.geometry_revision, "—");
    $("#surface-resource-waits").textContent = surfaceWaitSummary(publication);
    const nextGeneration = String(generation);
    if (surface.frameGeneration === nextGeneration && surface.frameUrl) {
      $("#surface-frame-status").textContent = "Live publication · pixels unchanged";
      updateSurfaceControls();
      renderSurfaceAnnotations();
      return;
    }
    if (surface.failedGeneration === nextGeneration && !retryPixels) {
      $("#surface-frame-status").textContent = "Frame unavailable";
      updateSurfaceControls();
      return;
    }
    if (surface.frameGeneration !== null && surface.frameGeneration !== nextGeneration) {
      if (surface.frameUrl) URL.revokeObjectURL(surface.frameUrl);
      surface.frameUrl = "";
      surface.frameGeneration = null;
      surface.annotations = surface.annotations.filter((annotation) => Boolean(annotation.request_id && annotation.program_id));
      const image = $("#surface-frame");
      image.removeAttribute("src");
      image.classList.add("hidden");
      $("#surface-frame-empty").classList.remove("hidden");
      renderSurfaceAnnotations();
    }
    surface.failedGeneration = "";
    $("#surface-frame-status").textContent = "Loading current publication pixels…";
    updateSurfaceControls();
    const chunks = await readSurfacePixels(bindingId, publication, generation);
    if (surface.epoch !== token || surface.bindingId !== bindingId || document.hidden) return;
    const blob = await surfaceFrameBlob(publication, chunks);
    if (surface.epoch !== token || surface.bindingId !== bindingId || document.hidden) return;
    const nextUrl = URL.createObjectURL(blob);
    const oldUrl = surface.frameUrl;
    const image = $("#surface-frame");
    image.onload = () => {
      if (surface.epoch !== token || surface.bindingId !== bindingId || surface.frameUrl !== nextUrl) return;
      image.classList.remove("hidden");
      $("#surface-frame-empty").classList.add("hidden");
      if (document.hidden) surface.captureCurrent = false;
      $("#surface-frame-status").textContent = document.hidden
        ? `Generation ${nextGeneration} loaded while the viewer was hidden; refresh on return.`
        : `Generation ${nextGeneration} · ${publication.width || image.naturalWidth}×${publication.height || image.naturalHeight}`;
      if (oldUrl) URL.revokeObjectURL(oldUrl);
      renderSurfaceAnnotations();
      updateSurfaceControls();
    };
    image.onerror = () => {
      if (surface.frameUrl === nextUrl) {
        surface.frameUrl = "";
        URL.revokeObjectURL(nextUrl);
        surface.failedGeneration = nextGeneration;
        image.classList.add("hidden");
        $("#surface-frame-empty").classList.remove("hidden");
        $("#surface-frame-status").textContent = "Frame unavailable";
        surfaceMessage("The publication bytes were received but the browser could not decode this pixel format.", "warn");
        updateSurfaceControls();
      }
    };
    surface.frameUrl = nextUrl;
    surface.frameGeneration = nextGeneration;
    image.src = nextUrl;
  } catch (error) {
    if (surface.epoch !== token || surface.bindingId !== bindingId) return;
    if (surface.publication && surfaceGeneration(surface.publication) !== null) {
      surface.failedGeneration = String(surfaceGeneration(surface.publication));
    }
    surface.captureCurrent = false;
    surface.annotationMode = "";
    surface.drag = null;
    $("#surface-frame-status").textContent = "Latest capture unavailable";
    $("#surface-frame-age").textContent = "Unknown · latest capture unavailable";
    updateSurfaceControls();
    if (!quiet || (error instanceof ApiError && error.status === 401)) {
      surfaceMessage(`Capture unavailable: ${error?.message || String(error)}`, "warn");
      await handleError(error, {refresh: false});
    }
  } finally {
    surface.polling = false;
  }
}

function imagePosition(clientX, clientY) {
  const image = $("#surface-frame");
  if (image.classList.contains("hidden") || !image.naturalWidth || !image.naturalHeight) return null;
  const rect = image.getBoundingClientRect();
  if (clientX < rect.left || clientX > rect.right || clientY < rect.top || clientY > rect.bottom || !rect.width || !rect.height) return null;
  const publication = state.surface.publication || {};
  const width = Number(publication.width || image.naturalWidth);
  const height = Number(publication.height || image.naturalHeight);
  return {
    x: Math.max(0, Math.min(width - 1, Math.round((clientX - rect.left) / rect.width * width))),
    y: Math.max(0, Math.min(height - 1, Math.round((clientY - rect.top) / rect.height * height))),
    width,
    height,
    nx: (clientX - rect.left) / rect.width,
    ny: (clientY - rect.top) / rect.height,
  };
}

function sourceAnnotation(kind, start, end = start) {
  const surface = state.surface;
  const publication = surface.publication || {};
  if (!surface.captureCurrent || !surface.bindingId || !["observing", "assisting"].includes(surface.mode)
      || surface.sourceEpochValid !== true || surface.geometryValid !== true
      || String(surface.frameGeneration) !== String(surfaceGeneration(publication))
      || !start.width || !start.height) {
    $("#surface-annotation-status").textContent = "Annotations require a current displayed frame with matching source epoch and geometry.";
    return;
  }
  if (surface.annotations.length >= 8) {
    const removable = surface.annotations.findIndex((item) => !item.request_id);
    if (removable < 0) {
      surface.annotationMode = "";
      surface.drag = null;
      $("#surface-annotate-point").classList.remove("active");
      $("#surface-annotate-region").classList.remove("active");
      $("#surface-annotation-status").textContent = "All annotation slots contain submitted guidance; inspect those events before adding more.";
      renderSurfaceAnnotations();
      updateSurfaceControls();
      return;
    }
    surface.annotations.splice(removable, 1);
  }
  const left = Math.min(start.x, end.x);
  const top = Math.min(start.y, end.y);
  const right = Math.max(start.x, end.x);
  const bottom = Math.max(start.y, end.y);
  const regionWidth = right - left + 1;
  const regionHeight = bottom - top + 1;
  const annotation = {
    id: crypto.randomUUID(),
    program_id: surface.bindingProgramId,
    binding_id: surface.bindingId,
    source_id: surface.binding?.source_id,
    kind,
    x: left,
    y: top,
    ...(kind === "region" ? {width: regionWidth, height: regionHeight} : {}),
    normalized: {
      x: left / start.width,
      y: top / start.height,
      width: kind === "region" ? regionWidth / start.width : 0,
      height: kind === "region" ? regionHeight / start.height : 0,
    },
    widthPx: start.width,
    heightPx: start.height,
    source_epoch: publication.source_epoch,
    geometry_revision: publication.geometry_revision,
    publication_generation: surfaceGeneration(publication),
    sequence: publication.sequence ?? null,
    sample_time_ns: publication.sample_time_ns ?? null,
    receipt_time_ns: publication.receipt_time_ns ?? null,
    clock_domain: publication.sample_clock_domain ?? publication.clock_domain ?? null,
    request_id: "",
    requestState: "",
  };
  surface.annotations.push(annotation);
  surface.annotationMode = "";
  surface.drag = null;
  $("#surface-annotate-point").classList.remove("active");
  $("#surface-annotate-region").classList.remove("active");
  $("#surface-annotation-status").textContent = `${kind === "point" ? "Point" : "Region"} recorded against source pixels ${start.width}×${start.height}; no application input was sent.`;
  renderSurfaceAnnotations();
  updateSurfaceControls();
}

function renderSurfaceAnnotations() {
  const overlay = $("#surface-overlay");
  overlay.replaceChildren();
  const stage = $("#surface-frame-stage");
  const image = $("#surface-frame");
  const imageRect = image.getBoundingClientRect();
  const stageRect = stage.getBoundingClientRect();
  const currentGeneration = surfaceGeneration(state.surface.publication || {});
  if (!image.classList.contains("hidden") && state.surface.captureCurrent === true
      && imageRect.width && imageRect.height) {
    for (const [index, annotation] of state.surface.annotations.entries()) {
      if (annotation.binding_id !== state.surface.bindingId
          || String(annotation.source_id) !== String(state.surface.binding?.source_id)
          || String(annotation.publication_generation) !== String(currentGeneration)
          || String(annotation.source_epoch) !== String(state.surface.publication?.source_epoch)
          || String(annotation.geometry_revision) !== String(state.surface.publication?.geometry_revision)) continue;
      const marker = document.createElement("div");
      marker.className = `surface-marker surface-marker-${annotation.kind}`;
      marker.style.left = `${imageRect.left - stageRect.left + annotation.normalized.x * imageRect.width}px`;
      marker.style.top = `${imageRect.top - stageRect.top + annotation.normalized.y * imageRect.height}px`;
      if (annotation.kind === "region") {
        marker.style.width = `${annotation.normalized.width * imageRect.width}px`;
        marker.style.height = `${annotation.normalized.height * imageRect.height}px`;
      }
      overlay.append(marker);
      const tag = document.createElement("span");
      tag.className = "surface-marker-label";
      tag.textContent = `${annotation.kind === "point" ? "P" : "R"}${index + 1}`;
      tag.style.left = `${imageRect.left - stageRect.left + annotation.normalized.x * imageRect.width}px`;
      tag.style.top = `${Math.max(0, imageRect.top - stageRect.top + annotation.normalized.y * imageRect.height - 21)}px`;
      overlay.append(tag);
    }
    if (state.surface.drag) {
      const drag = state.surface.drag;
      const marker = document.createElement("div");
      marker.className = "surface-marker surface-marker-region";
      const left = Math.min(drag.start.nx, drag.end.nx);
      const top = Math.min(drag.start.ny, drag.end.ny);
      marker.style.left = `${imageRect.left - stageRect.left + left * imageRect.width}px`;
      marker.style.top = `${imageRect.top - stageRect.top + top * imageRect.height}px`;
      marker.style.width = `${Math.abs(drag.end.nx - drag.start.nx) * imageRect.width}px`;
      marker.style.height = `${Math.abs(drag.end.ny - drag.start.ny) * imageRect.height}px`;
      overlay.append(marker);
    }
  }

  const list = $("#surface-annotation-list");
  list.replaceChildren();
  for (const [index, annotation] of state.surface.annotations.entries()) {
    const row = document.createElement("div");
    row.className = "surface-annotation";
    const rect = annotation.kind === "point" ? `(${annotation.x}, ${annotation.y})` : `(${annotation.x}, ${annotation.y}, ${annotation.width}×${annotation.height})`;
    const details = document.createElement("span");
    const source = `${annotation.kind} ${rect} px · epoch ${surfaceText(annotation.source_epoch)} · geometry ${surfaceText(annotation.geometry_revision)} · generation ${surfaceText(annotation.publication_generation)} · sequence ${surfaceText(annotation.sequence)} · sample ${surfaceText(annotation.sample_time_ns, "unknown")} ${surfaceText(annotation.clock_domain, "")} · receipt ${surfaceText(annotation.receipt_time_ns, "unknown")}`;
    const guidance = annotation.request_id
      ? ` · guidance request ${annotation.request_id} · event ${surfaceText(annotation.guidanceEventId, "pending/unknown")} · semantic admission ${surfaceText(annotation.guidanceStatus, "not yet inspected")}`
      : "";
    details.textContent = source + guidance;
    const send = document.createElement("button");
    send.type = "button";
    send.dataset.surfaceAnnotation = String(index);
    send.textContent = annotation.request_id ? "Inspect guidance delivery" : "Ask Cassi about this";
    const canInspect = Boolean(annotation.request_id && annotation.program_id);
    const activeProgram = String(programValue(state.program || {}).status || "").toLowerCase() === "active";
    const canSubmit = !annotation.request_id && annotation.program_id === state.programId
      && state.surface.bindingProgramId === state.programId && activeProgram;
    send.disabled = !state.connected || (!canInspect && !canSubmit) || annotation.requestState === "submitting" || annotation.guidanceAdmitted === true;
    row.append(details, send);
    if (annotation.request_id && !annotation.guidanceAdmitted) {
      const retry = document.createElement("button");
      retry.type = "button";
      retry.dataset.surfaceGuidanceReconcile = String(index);
      retry.textContent = "Retry field admission";
      retry.disabled = !state.connected || !annotation.program_id || !annotation.guidanceEventId || annotation.requestState === "submitting";
      row.append(retry);
    }
    list.append(row);
  }
  updateSurfaceControls();
}

function applySurfaceGuidanceResult(annotation, response) {
  updateOwner(response);
  const guidanceEvent = response?.guidance_event || surfaceRecord(response).guidance_event || {};
  const eventId = surfaceText(guidanceEvent.id, "");
  const semantic = response?.semantic_admission || surfaceRecord(response).semantic_admission || {};
  const experience = response?.experience ?? surfaceRecord(response).experience ?? null;
  annotation.guidanceEventId = eventId || annotation.guidanceEventId || "";
  annotation.guidanceStatus = surfaceText(semantic.status, experience ? "admitted" : "not confirmed");
  annotation.guidanceAdmitted = Boolean(experience);
  annotation.requestState = "inspected";
  const status = experience
    ? `Guidance Event ${annotation.guidanceEventId || "(ID unavailable)"} recorded; field-semantic experience admitted.`
    : `Guidance Event ${annotation.guidanceEventId || "(pending or unavailable)"}; field-semantic admission ${annotation.guidanceStatus}.`;
  $("#surface-annotation-status").textContent = status;
  surfaceMessage(`${status} No authority was granted and no application input was sent.`);
  renderSurfaceAnnotations();
}

async function submitSurfaceAnnotation(index) {
  const annotation = state.surface.annotations[index];
  if (!annotation || !state.surface.bindingId || !state.programId
      || state.surface.bindingProgramId !== state.programId
      || String(programValue(state.program || {}).status || "").toLowerCase() !== "active") {
    throw new Error("A current source annotation and active existing program that owns the source binding are required.");
  }
  if (annotation.request_id) throw new Error("This annotation already has a durable request ID. Inspect it instead of submitting another guidance Event.");
  const publication = state.surface.publication || {};
  const generation = surfaceGeneration(publication);
  if (annotation.binding_id !== state.surface.bindingId
      || String(annotation.source_id) !== String(state.surface.binding?.source_id)
      || state.surface.captureCurrent !== true || String(annotation.publication_generation) !== String(generation)
      || String(annotation.source_epoch) !== String(publication.source_epoch)
      || String(annotation.geometry_revision) !== String(publication.geometry_revision)) {
    throw new Error("The annotation belongs to another source binding or is no longer the current displayed publication. Capture a fresh frame and mark it again.");
  }
  const instruction = cleanSurfaceValue($("#surface-annotation-instruction").value);
  if (!instruction || instruction.length > 512) throw new Error("Enter a focused question of at most 512 characters.");
  const annotationPayload = annotation.kind === "point"
    ? {kind: "point", x: annotation.x, y: annotation.y}
    : {kind: "region", x: annotation.x, y: annotation.y, width: annotation.width, height: annotation.height};
  const request = {
    request_id: crypto.randomUUID(),
    program_id: state.programId,
    binding_id: state.surface.bindingId,
    publication_generation: annotation.publication_generation,
    source_epoch: annotation.source_epoch,
    geometry_revision: annotation.geometry_revision,
    instruction,
    annotation: annotationPayload,
  };
  const confirmation = `Send this focused point/region annotation as program guidance for the existing program ${JSON.stringify(state.programId)}?\n\nIt records the shown source epoch, geometry, publication generation and integer pixel coordinates. This creates no new mission, grants no authority and sends no application input.`;
  if (!window.confirm(confirmation)) return null;
  annotation.request_id = request.request_id;
  annotation.requestState = "submitting";
  renderSurfaceAnnotations();
  try {
    const response = await surfaceRequest("/v1/surface/guidance", request);
    applySurfaceGuidanceResult(annotation, response);
    return response;
  } catch (error) {
    annotation.requestState = "unknown";
    annotation.guidanceStatus = "outcome unknown; inspect the same request ID";
    renderSurfaceAnnotations();
    surfaceMessage(`Guidance response is inconclusive for request ${annotation.request_id}. Inspect the existing request; do not submit a new event.`, "warn");
    throw error;
  }
}

async function inspectSurfaceGuidance(index) {
  const annotation = state.surface.annotations[index];
  if (!annotation?.request_id) throw new Error("This annotation has no guidance request to inspect.");
  annotation.requestState = "submitting";
  renderSurfaceAnnotations();
  try {
    if (!annotation.program_id) throw new Error("This guidance request has no recoverable program scope.");
    const query = new URLSearchParams({program_id: annotation.program_id});
    const response = await api(`/v1/surface/guidance/${encodeURIComponent(annotation.request_id)}?${query}`);
    applySurfaceGuidanceResult(annotation, response);
    return response;
  } catch (error) {
    annotation.requestState = "unknown";
    renderSurfaceAnnotations();
    throw error;
  }
}

async function reconcileSurfaceGuidance(index) {
  const annotation = state.surface.annotations[index];
  if (!annotation?.request_id || !annotation.guidanceEventId) throw new Error("Inspect the durable guidance Event before retrying semantic admission.");
  if (!window.confirm(`Retry only field-semantic admission for guidance request ${JSON.stringify(annotation.request_id)}?\n\nThe existing researcher Event is reused. No second guidance Event, grant, or application input is created.`)) return null;
  annotation.requestState = "submitting";
  renderSurfaceAnnotations();
  try {
    if (!annotation.program_id) throw new Error("This guidance request has no recoverable program scope.");
    const query = new URLSearchParams({program_id: annotation.program_id});
    const response = await surfaceRequest(`/v1/surface/guidance/${encodeURIComponent(annotation.request_id)}/reconcile?${query}`, {});
    applySurfaceGuidanceResult(annotation, response);
    return response;
  } catch (error) {
    annotation.requestState = "unknown";
    renderSurfaceAnnotations();
    throw error;
  }
}




function surfaceMissionScope() {
  const form = new FormData($("#surface-intent-form"));
  return {
    target: cleanSurfaceValue(form.get("target")),
    objective: cleanSurfaceValue(form.get("objective")),
    attention: cleanSurfaceValue(form.get("attention")),
    expected_consequence: cleanSurfaceValue(form.get("expected_consequence")),
    uncertainty: cleanSurfaceValue(form.get("uncertainty")),
    max_updates: Number(form.get("grant_updates")),
  };
}

function clearSurfaceGrant(surface = state.surface) {
  clearTimeout(surface.grantTimer);
  surface.grantTimer = null;
  surface.activeGrant = null;
  surface.grantProgramId = "";
}

function selectedSurfaceOperations() {
  return $$("[data-surface-grant-operation]:checked", $("#surface-operation-options")).map((input) => input.value);
}

function surfaceExpiryNs(durationSeconds) {
  return Number(BigInt(Date.now() + Math.round(durationSeconds * 1000)) * 1_000_000n);
}
async function surfaceMissionIdentity() {
  const program = programValue(state.program || {});
  if (!state.programId || String(program.status || "").toLowerCase() !== "active") {
    throw new Error("Surface approval requires the selected existing active program.");
  }
  const generation = Number(program.generation);
  if (!Number.isSafeInteger(generation) || generation < 0) throw new Error("The active program has no valid generation.");
  const binding = state.surface.binding || {};
  const identity = {
    program_id: state.programId,
    program_generation: generation,
    mission_sha256: await sha256(stableJson({
      title: String(program.title || ""),
      mission: String(program.mission || ""),
      generation,
    })),
    binding_id: state.surface.bindingId,
    backend_id: surfaceBackendId(binding),
    source_id: surfaceSourceId(binding),
    source_instance: binding.source_instance,
    source_epoch: binding.source_epoch,
    environment_incarnation: binding.environment_incarnation,
    geometry_revision: binding.geometry_revision,
  };
  if (!identity.binding_id || !identity.backend_id || !identity.source_id
      || !identity.source_instance || identity.source_epoch === undefined || identity.source_epoch === null
      || !identity.environment_incarnation || identity.geometry_revision === undefined || identity.geometry_revision === null) {
    throw new Error("The current source binding has no complete dynamic identity to approve.");
  }
  return identity;
}

async function refreshSurfaceAuthorityStatus() {
  const surface = state.surface;
  if (!state.connected || !surface.bindingId || surface.bindingProgramId !== state.programId) {
    clearTimeout(surface.authorityTimer);
    surface.authorityTimer = null;
    surface.humanAuthorityConfigured = false;
    surface.missionAuthority = null;
    $("#surface-human-authority-status").textContent = "Select the program that owns a current source binding.";
    updateSurfaceControls();
    return null;
  }
  const programId = state.programId;
  const bindingId = surface.bindingId;
  const query = new URLSearchParams({program_id: programId, binding_id: bindingId});
  const result = await api(`/v1/surface/mission-authority/status?${query}`);
  if (state.programId !== programId || surface.bindingId !== bindingId) return null;
  clearTimeout(surface.authorityTimer);
  surface.authorityTimer = null;
  surface.authorityCheckedAt = Date.now();
  surface.humanAuthorityConfigured = result?.configured === true;
  let currentIdentity = null;
  if (result?.active === true) {
    try { currentIdentity = await surfaceMissionIdentity(); } catch { /* A non-active or incomplete program cannot match a mission window. */ }
  }
  const authorityFields = ["program_id", "program_generation", "mission_sha256",
    "backend_id", "source_id", "source_instance", "environment_incarnation"];
  const identityMatches = currentIdentity && authorityFields.every((field) =>
    String(result[field]) === String(currentIdentity[field]));
  surface.missionAuthority = result?.active === true && identityMatches ? result : null;
  if (!surface.humanAuthorityConfigured) {
    $("#surface-human-authority-status").textContent = "Mission authority is unavailable in this local entity process.";
  } else if (surface.missionAuthority) {
    const expires = new Date(Number(result.expires_ns) / 1e6).toLocaleString();
    $("#surface-human-authority-status").textContent = `Locally approved for ${JSON.stringify(result.program_id)} generation ${result.program_generation} · source ${JSON.stringify(result.backend_id)}/${JSON.stringify(result.source_id)} (instance ${JSON.stringify(result.source_instance)}, epoch ${result.source_epoch}, geometry ${result.geometry_revision}) · operations ${result.operations.join(", ")} · max ${result.max_lease_seconds}s / ${result.max_updates} updates per lease · expires ${expires}.`;
  } else if (result?.active === true) {
    $("#surface-human-authority-status").textContent = "A prior approval exists but no longer matches the current mission or exact source binding.";
  } else {
    $("#surface-human-authority-status").textContent = "No locally approved mission window is active for this exact program and source.";
  }
  if (surface.missionAuthority) {
    const approved = surface.missionAuthority;
    const delay = Math.max(0, Number(approved.expires_ns) / 1e6 - Date.now());
    surface.authorityTimer = setTimeout(() => {
      if (surface.missionAuthority !== approved) return;
      surface.missionAuthority = null;
      $("#surface-human-authority-status").textContent = "The host mission approval window has expired.";
      updateSurfaceControls();
    }, delay);
  }
  updateSurfaceControls();
  return result;
}

async function approveSurfaceMission() {
  const surface = state.surface;
  if (surface.bindingProgramId !== state.programId || surface.staleBinding) throw new Error("Approval requires a current source bound to the selected program.");
  if (surface.humanAuthorityConfigured !== true) throw new Error("This entity has no configured host Surface authority.");
  const operations = selectedSurfaceOperations();
  if (!operations.length || operations.length > 16) throw new Error("Select 1–16 exact supported operations for the mission approval.");
  const form = new FormData($("#surface-intent-form"));
  const duration = Number(form.get("authority_duration"));
  const maxUpdates = Number(form.get("authority_max_updates"));
  const grantDuration = Number(form.get("grant_duration"));
  if (!Number.isInteger(duration) || duration < 60 || duration > 86400) throw new Error("Mission approval window must be 60–86400 seconds.");
  if (!Number.isInteger(maxUpdates) || maxUpdates < 1 || maxUpdates > 4096) throw new Error("Approved broker update limit must be 1–4096.");
  if (!Number.isInteger(grantDuration) || grantDuration < 10 || grantDuration > 3600) throw new Error("Broker lease duration must be 10–3600 seconds.");
  const identity = await surfaceMissionIdentity();
  const expiresNs = surfaceExpiryNs(duration);
  const program = programValue(state.program || {});
  const expiryText = new Date(expiresNs / 1e6).toLocaleString();
  const detail = [
    `Program: ${JSON.stringify(identity.program_id)} · ${JSON.stringify(String(program.title || ""))}`,
    `Mission: ${JSON.stringify(String(program.mission || ""))}`,
    `Generation: ${identity.program_generation} · SHA-256: ${identity.mission_sha256}`,
    `Backend/source: ${JSON.stringify(identity.backend_id)} / ${JSON.stringify(identity.source_id)}`,
    `Instance: ${JSON.stringify(identity.source_instance)} · epoch: ${identity.source_epoch}`,
    `Environment: ${JSON.stringify(identity.environment_incarnation)} · geometry: ${identity.geometry_revision}`,
    `Exact operations: ${operations.join(", ")}`,
    `Approval window: ${duration} seconds, until ${expiryText}`,
    `Maximum broker lease: ${grantDuration} seconds and ${maxUpdates} updates.`,
    "This approval authorizes repeat bounded broker grants only for this unchanged mission and exact source identity. Revoke remains available.",
  ].join("\n");
  if (!window.confirm(`Approve this scoped Surface mission window locally?\n\n${detail}`)) return null;
  const result = await surfaceRequest("/v1/surface/mission-authority/approve", {
    ...identity,
    operations,
    expires_ns: expiresNs,
    max_updates: maxUpdates,
    max_lease_seconds: grantDuration,
  });
  surface.humanAuthorityConfigured = true;
  surface.missionAuthority = null;
  $("#surface-human-authority-status").textContent = "Local consent recorded; checking the active mission window.";
  updateSurfaceControls();
  await refreshSurfaceAuthorityStatus();
  surfaceMessage("The exact mission/source/operation window is locally approved. Bounded grants may renew until expiry; no actuator token is exposed to the field.");
  return result;
}

function boundSurfaceConfirmation(action, detail = "") {
  const source = JSON.stringify(state.surface.binding?.source_id || "currently bound source");
  return `Confirm ${action} for ${source}?${detail ? `\n\n${detail}` : ""}`;
}

function surfaceControlResult(response, action) {
  const record = surfaceRecord(response);
  const neutralization = response?.neutralization || response?.neutralize || record.neutralization || record.neutralize;
  const confirmed = neutralization?.confirmed ?? record.neutralization_confirmed ?? record.neutralized;
  const detail = surfaceText(neutralization?.detail, surfaceText(record.detail, ""));
  if (["revoke", "pause", "take-control", "release", "release-human"].includes(action)) {
    if (confirmed === true) state.surface.safetyBlocked = false;
    else {
      state.surface.safetyBlocked = true;
      $("#surface-authority").textContent = confirmed === false
        ? `Neutralization not confirmed${detail ? ` · ${detail}` : ""}`
        : "Neutralization status unknown; further input is blocked";
    }
  }
  if (!state.surface.safetyBlocked && (record.authority !== undefined || record.authority_state !== undefined)) {
    $("#surface-authority").textContent = surfaceAuthoritySummary(record.authority || record.authority_state);
  }
  $("#surface-resource-waits").textContent = surfaceWaitSummary(record);
  return {record, confirmed, detail};
}

function showSurfaceControlStatus(action, result) {
  if (result.confirmed === false) {
    surfaceMessage(`${action} completed, but neutralization was not confirmed: ${result.detail || "provider gave no detail"}. No further control will be sent.`, "error");
  } else if (result.confirmed !== true && ["revoke", "pause", "take-control", "release", "release-human"].includes(action)) {
    surfaceMessage(`${action} response did not confirm neutralization. Control is blocked until the broker's safety state is verified.`, "warn");
  } else {
    surfaceMessage(`${action} completed through the entity broker.`, "quiet");
  }
}

async function requestSurfaceControl(action, {revokeMissionApproval = true} = {}) {
  const surface = state.surface;
  if (!surface.bindingId) throw new Error("Bind a surface source first.");
  const bindingId = surface.bindingId;
  const revokeMission = action === "revoke" && revokeMissionApproval;
  if (!surface.bindingProgramId) throw new Error("The binding has no recoverable program scope; do not issue source controls.");
  let path = `/v1/surface/bindings/${encodeURIComponent(bindingId)}/${action}`;
  if (revokeMission) {
    path = "/v1/surface/mission-authority/revoke";
  } else if (action !== "take-control") {
    const query = new URLSearchParams({program_id: surface.bindingProgramId});
    path += `?${query}`;
  }
  let body = revokeMission
    ? {program_id: surface.bindingProgramId, binding_id: bindingId}
    : {};

  let result;
  try {
    if (action === "take-control") {
      const program = programValue(state.program || {});
      if (surface.humanAuthorityConfigured !== true) throw new Error("Local Surface mission authority is unavailable.");
      const operations = selectedSurfaceOperations();
      if (String(program.status || "").toLowerCase() !== "active") throw new Error("Human control requires the active existing program mission.");
      if (surface.bindingProgramId !== state.programId) throw new Error("Human control requires the same program that owns this source binding.");
      if (surface.staleBinding) throw new Error("This source binding is stale; human control is blocked.");
      const publication = surface.publication || {};
      const generation = surfaceGeneration(publication);
      if (surface.safetyBlocked || !["observing", "assisting"].includes(surface.mode)
          || surface.captureCurrent !== true || !surface.frameUrl || surface.sourceEpochValid !== true
          || surface.geometryValid !== true || generation === null
          || String(surface.frameGeneration) !== String(generation)) {
        throw new Error("Human control requires a safe, current source publication in an observing or assisting mode.");
      }
      if (!operations.length || operations.length > 16) throw new Error("Select 1–16 exact supported operations for the human-control lease.");
      const duration = Number(new FormData($("#surface-intent-form")).get("grant_duration"));
      if (!Number.isInteger(duration) || duration < 10 || duration > 3600) throw new Error("Human-control duration must be 10–3600 seconds.");
      const expiresNs = surfaceExpiryNs(duration);
      const identity = await surfaceMissionIdentity();
      body = {...identity, operations, expires_ns: expiresNs};
      const mission = [
        `Program: ${JSON.stringify(identity.program_id)} · ${JSON.stringify(String(program.title || ""))}`,
        `Mission: ${JSON.stringify(String(program.mission || ""))}`,
        `Generation: ${identity.program_generation} · SHA-256: ${identity.mission_sha256}`,
        `Backend/source: ${JSON.stringify(identity.backend_id)} / ${JSON.stringify(identity.source_id)}`,
        `Instance: ${JSON.stringify(identity.source_instance)} · epoch: ${identity.source_epoch}`,
        `Environment: ${JSON.stringify(identity.environment_incarnation)} · geometry: ${identity.geometry_revision}`,
        `Exact operations: ${operations.join(", ")}`,
        `Human-control lease: ${duration} seconds, until ${new Date(expiresNs / 1e6).toLocaleString()}`,
      ].join("\n");
      if (!window.confirm(`Approve this one-time human-control request?\n\n${mission}`)) return null;
      result = await surfaceRequest("/v1/surface/mission-authority/take-control", body);
    } else {
      const descriptions = {
        pause: "Pause brokered control and neutralize broker-owned inputs. The environment itself remains running.",
        revoke: revokeMission
          ? "Revoke the mission approval and current control authority, then attempt emergency neutralization. The environment remains running."
          : "Revoke only the current broker grant and neutralize broker-owned input. The host-approved mission window remains active.",
        "release-human": "End the human-control lease. No previous delegated grant will be restored.",
        resume: "Resume observation only. A fresh host-approved mission window is required before any new delegated operation.",
      };
      if (!window.confirm(boundSurfaceConfirmation(descriptions[action] || action))) return null;
      if (action === "revoke") {
        clearSurfaceGrant(surface);
        surface.safetyBlocked = true;
        setSurfaceMode("paused");
        if (revokeMission) {
          clearTimeout(surface.authorityTimer);
          surface.authorityTimer = null;
          surface.missionAuthority = null;
          $("#surface-human-authority-status").textContent = "Mission approval revoked; checking broker neutralization.";
        }
        updateSurfaceControls();
      }
      result = await surfaceRequest(path, body);
    }
  } catch (error) {
    if (revokeMission) updateSurfaceControls();
    throw error;
  }
  const status = surfaceControlResult(result, action);
  const authoritativeMode = surfaceBindingMode(status.record);
  if (action === "pause") {
    clearSurfaceGrant(surface);
    setSurfaceMode("paused");
  } else if (action === "revoke") {
    clearSurfaceGrant(surface);
    if (revokeMission) {
      clearTimeout(surface.authorityTimer);
      surface.authorityTimer = null;
      surface.missionAuthority = null;
      $("#surface-human-authority-status").textContent = "No host-authorized mission window is active for this exact program and source.";
    }
    setSurfaceMode(status.confirmed === true ? "observing" : "paused");
  } else if (action === "take-control") {
    clearSurfaceGrant(surface);
    if (status.confirmed === true) setSurfaceMode("human-control");
    else setSurfaceMode("paused");
  } else if (action === "release-human" || action === "resume") {
    clearSurfaceGrant(surface);
    const safelyObserving = authoritativeMode === "observing" && status.record.detached !== true
      && status.record.inhibited !== true && status.record.human_control !== true;
    if (safelyObserving) {
      surface.safetyBlocked = false;
      setSurfaceMode("observing");
    } else {
      surface.safetyBlocked = true;
      setSurfaceMode(authoritativeMode === "disconnected" ? "disconnected" : "paused");
    }
  }
  if (authoritativeMode && action !== "release-human" && action !== "resume" && status.confirmed === true) setSurfaceMode(authoritativeMode);
  showSurfaceControlStatus(action, status);
  return result;
}

async function enterSurfaceAssisting() {
  const surface = state.surface;
  if (!surface.bindingId) throw new Error("Bind a surface source first.");
  if (surface.bindingProgramId !== state.programId || surface.staleBinding) throw new Error("The selected program does not own a current source binding.");
  if (surface.mode === "paused") throw new Error("Resume through the entity broker before entering assisting mode.");
  if (surface.mode === "human-control") {
    const result = await requestSurfaceControl("release-human");
    if (!result || surface.safetyBlocked) return;
  } else if (surface.activeGrant || surface.mode === "delegated") {
    const result = await requestSurfaceControl("revoke", {revokeMissionApproval: false});
    if (!result || surface.safetyBlocked) return;
  }
  if (!["observing", "assisting"].includes(surface.mode)) throw new Error("The current control mode must be safely released before assisting.");
  surface.viewerMode = "assisting";
  setSurfaceMode("assisting");
  surfaceMessage("Assisting mode is active for context and inspection only. It grants no application input; submit remains unavailable without a separately authorized delegated lease.");
}
async function enterSurfaceDelegated() {
  const surface = state.surface;
  const program = programValue(state.program || {});
  if (!surface.bindingId) throw new Error("Bind a supported source before requesting a delegated lease.");
  if (surface.bindingProgramId !== state.programId || surface.staleBinding) throw new Error("The selected program does not own a current source binding.");
  if (String(program.status || "").toLowerCase() !== "active") throw new Error("Delegated operation requires an active existing program.");
  if (surface.safetyBlocked) throw new Error("Source authority is inhibited; request a safe observing state before delegation.");
  const publication = surface.publication || {};
  const generation = surfaceGeneration(publication);
  if (!publication || surface.captureCurrent !== true || !surface.frameUrl || surface.sourceEpochValid !== true || surface.geometryValid !== true
      || generation === null || String(surface.frameGeneration) !== String(generation)) {
    throw new Error("A current displayed publication with matching source epoch and geometry is required.");
  }
  if (surface.activeGrant) throw new Error("A delegated grant is already active. Revoke it before requesting another.");
  const approval = surface.missionAuthority;
  if (!approval || approval.active !== true) throw new Error("Approve this exact mission and source with the host before requesting a delegated lease.");
  const identity = await surfaceMissionIdentity();
  const identityFields = ["program_id", "program_generation", "mission_sha256",
    "backend_id", "source_id", "source_instance", "environment_incarnation"];
  if (!identityFields.every((field) => String(approval[field]) === String(identity[field]))) {
    surface.missionAuthority = null;
    updateSurfaceControls();
    throw new Error("The approved mission or exact source identity has changed; inspect and approve its current identity again.");
  }
  const approvalExpiresNs = Number(approval.expires_ns);
  const remainingSeconds = Math.floor((approvalExpiresNs / 1e6 - Date.now()) / 1000);
  if (!Number.isFinite(approvalExpiresNs) || remainingSeconds < 10) {
    surface.missionAuthority = null;
    $("#surface-human-authority-status").textContent = "The host mission approval window has expired or has less than ten seconds remaining.";
    updateSurfaceControls();
    throw new Error("The host mission approval has expired or cannot fit another bounded lease.");
  }
  const operations = selectedSurfaceOperations();
  if (!operations.length || operations.length > 16) throw new Error("Select 1–16 exact supported operation tokens; grants never default to all operations.");
  if (!operations.every((operation) => approval.operations.includes(operation))) {
    throw new Error("Selected lease operations must be a subset of the operations approved for this mission window.");
  }
  const form = new FormData($("#surface-intent-form"));
  const requestedDuration = Number(form.get("grant_duration"));
  if (!Number.isInteger(requestedDuration) || requestedDuration < 10 || requestedDuration > 3600) throw new Error("Grant duration must be 10–3600 seconds.");
  const duration = Math.min(requestedDuration, remainingSeconds);
  const scope = validateBoundedJson(surfaceMissionScope());
  if (!scope.target || !scope.objective || !scope.expected_consequence) throw new Error("Target, objective, and expected consequence must be explicit before delegation.");
  if (!Number.isInteger(scope.max_updates) || scope.max_updates < 1 || scope.max_updates > approval.max_updates) {
    throw new Error(`Updates per lease must be 1–${approval.max_updates}, the host-approved bound.`);
  }
  const expiresNs = surfaceExpiryNs(duration);
  const request = {binding_id: surface.bindingId, operations, expires_ns: expiresNs, scope};
  const response = await surfaceRequest(`/v1/surface/mission/${encodeURIComponent(state.programId)}/grant`, request);
  const record = surfaceRecord(response);
  const grant = response?.grant || record.grant || record;
  const grantId = surfaceText(grant.grant_id, surfaceText(grant.id, surfaceText(response?.grant_id, "")));
  if (!grantId) {
    clearSurfaceGrant(surface);
    setSurfaceMode("observing");
    $("#surface-authority").textContent = "Grant response had no usable receipt ID; no intent can be submitted.";
    surfaceMessage("The host-approved grant response did not include a usable grant ID. No action was submitted; inspect or revoke authority before proceeding.", "error");
    return response;
  }
  clearSurfaceGrant(surface);
  surface.activeGrant = {grant_id: grantId, operations, expires_ns: expiresNs, scope};
  surface.grantProgramId = state.programId;
  surface.viewerMode = "delegated";
  surface.safetyBlocked = false;
  surface.grantTimer = setTimeout(() => {
    if (surface.activeGrant?.grant_id !== grantId) return;
    clearSurfaceGrant(surface);
    if (surface.bindingId) setSurfaceMode("observing");
    surfaceMessage("The delegated lease expired. No further operation will be submitted; the host-approved mission window remains available for another bounded lease.", "warn");
  }, Math.max(0, expiresNs / 1e6 - Date.now()));
  $("#surface-authority").textContent = `Delegated lease · ${operations.length} approved operation(s) · ${scope.max_updates} updates · expires ${new Date(expiresNs / 1e6).toLocaleTimeString()}`;
  setSurfaceMode("delegated");
  surfaceMessage(`A ${duration}-second bounded lease was issued under the existing host-approved mission window. Further leases remain constrained to the approved operations and update cap.`);
  return response;
}


async function submitSurfaceIntent() {
  const surface = state.surface;
  const program = programValue(state.program || {});
  if (surface.bindingProgramId !== state.programId || surface.staleBinding) throw new Error("The selected program does not own a current source binding.");
  const scope = surfaceMissionScope();
  const operation = $("#surface-operation").value;
  if (surface.mode !== "delegated" || !surface.activeGrant || surface.grantProgramId !== state.programId) {
    throw new Error("Observation and assisting modes send no application input. Request a bounded broker lease under the current host-approved mission window first.");
  }
  const expiresNs = Number(surface.activeGrant.expires_ns);
  if (!Number.isFinite(expiresNs) || expiresNs <= Number(BigInt(Date.now()) * 1_000_000n)) {
    clearSurfaceGrant(surface);
    setSurfaceMode("observing");
    throw new Error("The delegated lease is expired or has no valid expiry. Request another bounded broker lease under the current host approval.");
  }
  if (String(program.status || "").toLowerCase() !== "active") throw new Error("The current program is no longer active.");
  if (surface.safetyBlocked) throw new Error("Control is blocked because neutralization was not confirmed.");
  if (stableJson(scope) !== stableJson(surface.activeGrant.scope)) throw new Error("Mission context changed after the grant. Revoke and request a new exact scope.");
  if (!surface.activeGrant.operations.includes(operation)) throw new Error("This operation is not part of the current grant.");
  if (surface.pendingOperationId) throw new Error("A prior operation has an unresolved outcome. Inspect or reconcile it; never replay it.");
  const publication = surface.publication || {};
  const generation = surfaceGeneration(publication);
  if (surface.captureCurrent !== true || !surface.frameUrl || generation === null || String(surface.frameGeneration) !== String(generation)
      || surface.sourceEpochValid !== true || surface.geometryValid !== true
      || String(publication.source_epoch) !== String(surface.binding?.source_epoch)
      || String(publication.geometry_revision) !== String(surface.binding?.geometry_revision)) {
    throw new Error("No current displayed source-epoch and geometry-bound publication is available.");
  }
  const payload = validateBoundedJson(parseJson($("#surface-payload").value, "Operation payload"));
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) throw new Error("Operation payload must be a JSON object.");
  const operationDescriptor = operationRows().find((row) => surfaceOperationToken(row) === operation);
  if (!operationDescriptor || !supportedStatus(operationDescriptor)) throw new Error("Choose an operation explicitly reported as supported by this bound source.");
  const operationId = crypto.randomUUID();
  const request = {
    operation_id: operationId,
    program_id: state.programId,
    binding_id: surface.bindingId,
    grant_id: surface.activeGrant.grant_id,
    operation,
    payload,
    expected_source_epoch: publication.source_epoch,
    expected_geometry_revision: publication.geometry_revision,
  };
  surface.pendingOperationId = operationId;
  surface.activeOperationId = operationId;
  surface.operationProgramId = state.programId;
  surface.lastIntent = {operation, target: scope.target, expected_consequence: scope.expected_consequence, uncertainty: scope.uncertainty};
  $("#surface-expected").textContent = scope.expected_consequence;
  $("#surface-uncertainty").textContent = scope.uncertainty || "No uncertainty note supplied.";
  $("#surface-disposition").textContent = "Submitting through broker…";
  $("#surface-outcome").textContent = "Awaiting an inspected operation result.";
  $("#surface-reconcile").classList.remove("hidden");
  surfaceMessage(`Submitting operation ${operationId}. If the response is lost, inspect this ID; do not resubmit.`);
  updateSurfaceControls();
  try {
    const response = await surfaceRequest("/v1/surface/intents", request);
    updateSurfaceOutcome(response);
    return response;
  } catch (error) {
    surfaceMessage(`The submission response was not conclusive for operation ${operationId}: ${error?.message || String(error)}. Inspect or reconcile this same ID; do not retry the effect.`, "warn");
    if (error instanceof ApiError && error.status === 401) await handleError(error, {refresh: false});
    else if (error instanceof ApiError && error.status < 500) {
      $("#surface-disposition").textContent = "Rejected by entity; inspect the reserved operation before any new intent.";
    }
    return null;
  }
}

function updateSurfaceOutcome(response, reconciled = false) {
  const record = surfaceRecord(response);
  const nested = record.operation || record.effect || record.result || record;
  const disposition = surfaceText(nested.disposition, surfaceText(nested.delivery_disposition, surfaceText(record.disposition, "")));
  const status = surfaceText(nested.status, surfaceText(record.status, "Result received"));
  const operationId = surfaceText(nested.operation_id, surfaceText(record.operation_id, state.surface.activeOperationId));
  if (operationId) state.surface.activeOperationId = operationId;
  if (disposition) $("#surface-disposition").textContent = disposition;
  else $("#surface-disposition").textContent = status;
  const outcome = nested.outcome ?? nested.application_observation ?? nested.assessment ?? record.outcome ?? record.application_observation;
  $("#surface-outcome").textContent = outcome === undefined ? status : typeof outcome === "string" ? outcome : compactJson(outcome, 900);
  if (nested.uncertainty !== undefined || record.uncertainty !== undefined) {
    $("#surface-uncertainty").textContent = surfaceText(nested.uncertainty, surfaceText(record.uncertainty, "Uncertainty reported."));
  } else if (["unknown", "partially-delivered"].includes(disposition)) {
    $("#surface-uncertainty").textContent = "Delivery is unresolved or partial; no replay is permitted until this operation is reconciled.";
  }
  $("#surface-resource-waits").textContent = surfaceWaitSummary(record);
  const authority = record.authority || record.authority_state;
  if (authority) $("#surface-authority").textContent = surfaceAuthoritySummary(authority);
  if (state.surface.pendingOperationId && operationId === state.surface.pendingOperationId) {
    if (reconciled || ["rejected", "not-started", "delivered"].includes(disposition)) state.surface.pendingOperationId = "";
  }
  if (["unknown", "partially-delivered"].includes(disposition) && !state.surface.pendingOperationId) {
    state.surface.pendingOperationId = operationId;
  }
  if (state.surface.pendingOperationId) {
    $("#surface-reconcile").classList.remove("hidden");
    surfaceMessage(`Operation ${state.surface.pendingOperationId} remains unresolved. Reconcile actual evidence; it will not be replayed.`, "warn");
  } else {
    surfaceMessage(`Operation ${operationId || "—"} inspected: ${disposition || status}.`);
  }
  updateSurfaceControls();
}

async function inspectSurfaceOperation() {
  const operationId = state.surface.activeOperationId || state.surface.pendingOperationId;
  if (!operationId) throw new Error("No surface operation has been submitted yet.");
  const query = new URLSearchParams({program_id: state.surface.operationProgramId || state.surface.bindingProgramId || state.programId});
  const response = await api(`/v1/surface/operations/${encodeURIComponent(operationId)}?${query}`);
  updateSurfaceOutcome(response);
  return response;
}

async function refreshSurfaceBinding() {
  const surface = state.surface;
  const bindingId = surface.bindingId;
  if (!bindingId) return null;
  const bindingProgramId = surface.bindingProgramId;
  if (!bindingProgramId) throw new Error("The existing binding has no recoverable program scope; do not issue source controls.");
  const epoch = surface.epoch;
  const query = new URLSearchParams({program_id: bindingProgramId});
  const response = await api(`/v1/surface/bindings/${encodeURIComponent(bindingId)}?${query}`);
  if (surface.epoch !== epoch || surface.bindingId !== bindingId) return null;
  const latest = surfaceRecord(response);
  const current = surface.binding || {};
  const identity = [
    [current.source_id, latest.source_id],
    [current.source_instance ?? current.source_instance_id, latest.source_instance ?? latest.source_instance_id],
    [current.environment_incarnation, latest.environment_incarnation],
    [current.source_epoch, latest.source_epoch],
    [current.geometry_revision, latest.geometry_revision],
  ];
  if (latest.detached === true || identity.some(([expected, actual]) => expected == null || actual == null || String(expected) !== String(actual))) {
    surface.staleBinding = true;
    surface.safetyBlocked = true;
    surface.captureCurrent = false;
    clearSurfaceGrant(surface);
    clearSurfaceFrame();
    surfaceMessage("The entity binding no longer matches its bound source identity or epoch. Release it before rebinding; no intent is enabled.", "warn");
    updateSurfaceControls();
    return response;
  }
  surface.binding = {...current, ...latest};
  const neutralization = latest.neutralization || latest.neutralize;
  if (neutralization?.confirmed === true || latest.neutralization_confirmed === true) surface.safetyBlocked = false;
  if (neutralization?.confirmed === false || latest.inhibited === true) surface.safetyBlocked = true;
  const mode = surfaceBindingMode(latest);
  if (mode === "observing" && latest.human_control !== true && latest.inhibited !== true
      && latest.detached !== true) surface.safetyBlocked = false;
  if (mode) setSurfaceMode(mode);
  renderSurfaceBinding();
  updateSurfaceControls();
  return response;
}

async function refreshSurfaceStatus() {
  const tasks = [];
  if (state.surface.bindingId) {
    await refreshSurfaceBinding();
    tasks.push(refreshSurfaceAuthorityStatus());
    if (state.surface.activeOperationId) tasks.push(inspectSurfaceOperation());
    state.surface.failedGeneration = "";
    tasks.push(refreshSurfaceCapture({quiet: false, retryPixels: true}));
  } else if (state.surface.activeOperationId) {
    tasks.push(inspectSurfaceOperation());
  } else {
    await loadSurfaceDescriptor();
  }
  await Promise.all(tasks);
}

async function detachSurfaceViewer() {
  const surface = state.surface;
  if (!surface.bindingId) throw new Error("There is no active source binding to release.");
  const bindingId = surface.bindingId;
  const programId = surface.bindingProgramId;
  if (!programId) throw new Error("The binding has no recoverable program scope; source release is blocked.");
  if (!window.confirm(boundSurfaceConfirmation("release this source binding",
      `Program: ${JSON.stringify(programId)}\nThe entity broker will detach this viewer and neutralize broker-owned input. The source environment remains running.`))) return null;
  const query = new URLSearchParams({program_id: programId});
  const response = await surfaceRequest(`/v1/surface/bindings/${encodeURIComponent(bindingId)}/release?${query}`, {});
  const result = surfaceControlResult(response, "release");
  showSurfaceControlStatus("release", result);
  if (result.confirmed !== true) {
    throw new Error(`The entity did not confirm safe source release${result.detail ? `: ${result.detail}` : ""}. The binding remains visible for inspection; no further control is sent.`);
  }
  stopSurfacePolling();
  clearTimeout(surface.authorityTimer);
  surface.authorityTimer = null;
  surface.missionAuthority = null;
  $("#surface-human-authority-status").textContent = "Source binding released; no mission approval is active in this viewer.";
  clearSurfaceGrant(surface);
  surface.epoch += 1;
  clearSurfaceFrame();
  surface.binding = null;
  surface.bindingId = "";
  surface.bindingProgramId = "";
  surface.staleBinding = false;
  surface.publication = null;
  surface.captureCurrent = false;
  surface.sourceEpochValid = false;
  surface.geometryValid = false;
  surface.annotationMode = "";
  surface.annotations = surface.annotations.filter((annotation) => Boolean(annotation.request_id && annotation.program_id));
  surface.drag = null;
  setSurfaceMode("disconnected");
  $("#surface-connection").textContent = "Source binding released by the entity broker; environment left running.";
  $("#surface-annotation-list").replaceChildren();
  renderSurfaceBinding();
  renderSurfaceAnnotations();
  updateSurfaceControls();
  return response;
}

async function reconcileSurfaceOperation() {
  const operationId = state.surface.pendingOperationId;
  if (!operationId) throw new Error("There is no unresolved surface operation to reconcile.");
  const outcome = validateBoundedJson(parseJson($("#surface-reconcile-outcome").value, "Observed outcome"));
  if (!outcome || typeof outcome !== "object" || Array.isArray(outcome)) throw new Error("Observed outcome must be a JSON object.");
  if (!window.confirm(`Record this independently observed outcome against operation ${JSON.stringify(operationId)}?\n\nThis records evidence only; it does not replay or compensate for the operation.`)) return null;
  const query = new URLSearchParams({program_id: state.surface.operationProgramId || state.surface.bindingProgramId || state.programId});
  const response = await surfaceRequest(`/v1/surface/operations/${encodeURIComponent(operationId)}/reconcile?${query}`, {outcome});
  updateSurfaceOutcome(response, true);
  return response;
}

function activateAnnotationMode(mode) {
  if (!state.surface.bindingId || !state.surface.frameUrl || state.surface.geometryValid !== true) return;
  state.surface.annotationMode = mode;
  state.surface.drag = null;
  $("#surface-annotate-point").classList.toggle("active", mode === "point");
  $("#surface-annotate-region").classList.toggle("active", mode === "region");
  $("#surface-annotation-status").textContent = mode === "point"
    ? "Select a point on the displayed source. This marks pixels only and sends no application input."
    : "Drag a region on the displayed source. This marks pixels only and sends no application input.";
}

function recordSurfacePoint(event) {
  if (state.surface.annotationMode !== "point") return;
  const position = imagePosition(event.clientX, event.clientY);
  if (!position) return;
  event.preventDefault();
  sourceAnnotation("point", position);
}

function startSurfaceRegion(event) {
  if (state.surface.annotationMode !== "region") return;
  const position = imagePosition(event.clientX, event.clientY);
  if (!position) return;
  event.preventDefault();
  const stage = $("#surface-frame-stage");
  stage.setPointerCapture(event.pointerId);
  state.surface.drag = {pointerId: event.pointerId, start: position, end: position};
  renderSurfaceAnnotations();
}

function moveSurfaceRegion(event) {
  const drag = state.surface.drag;
  if (!drag || drag.pointerId !== event.pointerId) return;
  const position = imagePosition(event.clientX, event.clientY);
  if (!position) return;
  drag.end = position;
  renderSurfaceAnnotations();
}

function finishSurfaceRegion(event) {
  const drag = state.surface.drag;
  if (!drag || drag.pointerId !== event.pointerId) return;
  const end = imagePosition(event.clientX, event.clientY) || drag.end;
  const start = drag.start;
  const widthPx = start.width;
  const heightPx = start.height;
  const endSameImage = end.width === widthPx && end.height === heightPx;
  if (!endSameImage) {
    state.surface.drag = null;
    renderSurfaceAnnotations();
    return;
  }
  sourceAnnotation("region", start, end);
}

$("#surface-backend").addEventListener("change", () => action("Surface sources loaded.", loadSurfaceSources, {refresh: false}));
$("#surface-source").addEventListener("change", updateSurfaceControls);
$("#surface-operation-options").addEventListener("change", updateSurfaceControls);
$("#surface-intent-form").addEventListener("input", updateSurfaceControls);
$("#surface-intent-form").addEventListener("change", updateSurfaceControls);
$("#surface-approve-authority").addEventListener("click", () => action("Host-approved Surface mission window established.", approveSurfaceMission, {refresh: false}));
$("#surface-refresh-sources").addEventListener("click", () => action("Surface sources refreshed.", loadSurfaceSources, {refresh: false}));
$("#surface-bind").addEventListener("click", () => action("Source bound in observing mode.", bindSurfaceSource, {refresh: false}));
$("#surface-refresh-status").addEventListener("click", () => action("Surface status refreshed.", refreshSurfaceStatus, {refresh: false}));
$("#surface-frame-stage").addEventListener("click", recordSurfacePoint);
$("#surface-frame-stage").addEventListener("pointerdown", startSurfaceRegion);
$("#surface-frame-stage").addEventListener("pointermove", moveSurfaceRegion);
$("#surface-frame-stage").addEventListener("pointerup", finishSurfaceRegion);
$("#surface-frame-stage").addEventListener("pointercancel", (event) => {
  if (state.surface.drag?.pointerId !== event.pointerId) return;
  state.surface.drag = null;
  renderSurfaceAnnotations();
});
$("#surface-annotate-point").addEventListener("click", () => activateAnnotationMode("point"));
$("#surface-annotate-region").addEventListener("click", () => activateAnnotationMode("region"));
$("#surface-clear-annotation").addEventListener("click", () => {
  state.surface.annotations = state.surface.annotations.filter((annotation) => Boolean(annotation.request_id && annotation.program_id));
  state.surface.annotationMode = "";
  state.surface.drag = null;
  $("#surface-annotate-point").classList.remove("active");
  $("#surface-annotate-region").classList.remove("active");
  $("#surface-annotation-status").textContent = "Local annotations cleared; durable guidance requests remain available for inspection.";
  renderSurfaceAnnotations();
});
$("#surface-annotation-list").addEventListener("click", (event) => {
  const retry = event.target.closest("[data-surface-guidance-reconcile]");
  if (retry) {
    const index = Number(retry.dataset.surfaceGuidanceReconcile);
    action("Field-semantic admission checked.", () => reconcileSurfaceGuidance(index), {refresh: false});
    return;
  }
  const inspect = event.target.closest("[data-surface-annotation]");
  if (!inspect) return;
  const index = Number(inspect.dataset.surfaceAnnotation);
  const annotation = state.surface.annotations[index];
  action(annotation?.request_id ? "Guidance delivery inspected." : "Program guidance recorded.",
    () => annotation?.request_id ? inspectSurfaceGuidance(index) : submitSurfaceAnnotation(index),
    {refresh: false});
});
$("#surface-intent-form").addEventListener("submit", (event) => {
  event.preventDefault();
  action("Brokered operation intent submitted.", submitSurfaceIntent, {refresh: false});
});
$("#surface-operation").addEventListener("change", updateSurfaceControls);
$("#surface-assist").addEventListener("click", () => action("Assisting mode entered.", enterSurfaceAssisting, {refresh: false}));
$("#surface-delegate").addEventListener("click", () => action("Bounded delegated lease requested.", enterSurfaceDelegated, {refresh: false}));
$("#surface-pause").addEventListener("click", () => action("Surface control paused.", () => requestSurfaceControl("pause"), {refresh: false}));
$("#surface-neutralize").addEventListener("click", () => action("Surface authority revoked.", () => requestSurfaceControl("revoke"), {refresh: false}));
$("#surface-take-control").addEventListener("click", () => action("Human control requested.", () => requestSurfaceControl("take-control"), {refresh: false}));
$("#surface-release-human").addEventListener("click", () => action("Human control released.", () => requestSurfaceControl("release-human"), {refresh: false}));
$("#surface-resume").addEventListener("click", () => action("Surface observation resumed.", () => requestSurfaceControl("resume"), {refresh: false}));
$("#surface-detach").addEventListener("click", () => action("Viewer detached; environment left running.", detachSurfaceViewer, {refresh: false}));
$("#surface-reconcile-submit").addEventListener("click", () => action("Operation outcome reconciled.", reconcileSurfaceOperation, {refresh: false}));

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    state.surface.captureCurrent = false;
    $("#surface-frame-status").textContent = "Viewer hidden · displayed pixels are not current for control.";
    renderSurfaceAnnotations();
    surfaceMessage("Capture is not current while this viewer is hidden; returning will request a fresh publication.", "warn");
    updateSurfaceControls();
  } else if (state.surface.bindingId) {
    void refreshSurfaceCapture({quiet: true});
  }
});


function embodiedFieldView() {
  const field = state.embodiedField;
  if (field.mode === "frozen" && field.frozen) return {...field.frozen, mode: "frozen"};
  if (field.mode === "replay") {
    const record = field.captures.find((item) => item.id === field.replayId);
    if (record) return {snapshot: record.snapshot, sampledAt: record.sampledAt, record, mode: "replay"};
    field.mode = "live";
    field.replayId = "";
  }
  return field.latest ? {snapshot: field.latest, sampledAt: field.latestAt, mode: "live"} : null;
}

function embodiedJson(value, limit = 8_000) {
  if (value === undefined) return "Unavailable";
  let rendered;
  try { rendered = JSON.stringify(value, null, 2); } catch { return "Value unavailable"; }
  if (rendered === undefined) return "Unavailable";
  return rendered.length > limit ? `${rendered.slice(0, limit)}\n… clipped for display` : rendered;
}

function embodiedScalar(value, fallback = "not reported") {
  if (value === null || value === undefined) return fallback;
  if (typeof value === "object") return embodiedJson(value, 800);
  return String(value);
}

function embodiedErrorMessage(error) {
  const message = error?.message || String(error);
  if (/^\s*</u.test(message)) {
    const status = Number.isInteger(error?.status) ? ` (HTTP ${error.status})` : "";
    return `Entity API returned an HTML error page${status}.`;
  }
  return message;
}

function embodiedTime(value) {
  if (!value) return "Unavailable";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? String(value) : date.toLocaleString();
}

function embodiedRegionIdentity(region, index) {
  const id = region?.region_id ?? region?.id ?? region?.name;
  return {
    key: id === undefined || id === null ? `record:${index}` : `id:${String(id)}`,
    id,
    label: id === undefined || id === null ? `Identifier unavailable · record ${index + 1}` : String(id),
  };
}

function embodiedSectionState(section) {
  return typeof section?.status === "string" ? section.status : "unavailable";
}

function embodiedNumbers(value, prefix = "", output = []) {
  if (output.length >= 128) return output;
  if (typeof value === "number" && Number.isFinite(value)) {
    output.push({path: prefix || "value", value});
  } else if (Array.isArray(value)) {
    value.forEach((item, index) => embodiedNumbers(item, `${prefix}[${index}]`, output));
  } else if (value && typeof value === "object") {
    for (const [key, item] of Object.entries(value)) {
      embodiedNumbers(item, prefix ? `${prefix}.${key}` : key, output);
      if (output.length >= 128) break;
    }
  }
  return output;
}

function renderEmbodiedCirculation(section) {
  const note = $("#embodied-circulation-note");
  const signs = $("#embodied-circulation-signs");
  const raw = $("#embodied-circulation");
  const stateName = embodiedSectionState(section);
  $("#embodied-circulation-state").textContent = stateName;
  signs.replaceChildren();
  if (stateName !== "known" || section?.value === null || section?.value === undefined) {
    note.textContent = section?.reason || "Signed circulation is unavailable.";
    raw.textContent = section?.reason || "Unavailable";
    return;
  }

  const value = section.value;
  raw.textContent = embodiedJson(value);
  const conventionEntry = value && typeof value === "object" && !Array.isArray(value)
    ? Object.entries(value).find(([key]) => /sign.?convention|direction.?convention|positive.?direction|orientation/i.test(key))
    : null;
  note.textContent = conventionEntry
    ? `Signed orientation follows the owner-reported ${conventionEntry[0]}: ${embodiedScalar(conventionEntry[1])}.`
    : "Signs are preserved as reported. Positive and negative orientation is shown without inferring unreported source/destination directions.";

  const signed = embodiedNumbers(value).filter(({path}) => /(?:^|\.)(?:signed_current|signed_flow|signed_flux|signed_transport|signed_exchange|outward_current|return_current)$/i.test(path));
  if (!signed.length) {
    const empty = document.createElement("p");
    empty.className = "quiet";
    empty.textContent = "No signed flow/current scalar is identified in this readout; inspect the full owner-reported circulation data below.";
    signs.append(empty);
    return;
  }
  for (const row of signed.slice(0, 48)) {
    const sign = row.value > 0 ? "positive" : row.value < 0 ? "negative" : "zero";
    const item = document.createElement("div");
    item.className = "embodied-sign-row";
    item.dataset.sign = sign;
    const path = document.createElement("code");
    path.textContent = row.path;
    const amount = document.createElement("strong");
    amount.textContent = `${row.value > 0 ? "+" : ""}${String(row.value)} · ${sign} orientation`;
    item.append(path, amount);
    signs.append(item);
  }
}

function embodiedCoordinates(region) {
  const coordinates = region?.current_coordinates;
  if (Array.isArray(coordinates) && coordinates.length >= 2
      && Number.isFinite(coordinates[0]) && Number.isFinite(coordinates[1])) {
    return {x: coordinates[0], y: coordinates[1], axes: ["current_coordinates[0]", "current_coordinates[1]"]};
  }
  const nested = coordinates && typeof coordinates === "object" && !Array.isArray(coordinates)
    ? coordinates.coordinates ?? coordinates.position
    : null;
  if (Array.isArray(nested) && nested.length >= 2
      && Number.isFinite(nested[0]) && Number.isFinite(nested[1])) {
    return {x: nested[0], y: nested[1], axes: ["current_coordinates.coordinates[0]", "current_coordinates.coordinates[1]"]};
  }
  if (coordinates && typeof coordinates === "object" && !Array.isArray(coordinates)) {
    const entries = Object.entries(coordinates).filter(([, value]) => typeof value === "number" && Number.isFinite(value));
    const x = entries.find(([key]) => key.toLowerCase() === "x") || entries[0];
    const y = entries.find(([key]) => key.toLowerCase() === "y") || entries.find((entry) => entry !== x);
    if (x && y) return {x: x[1], y: y[1], axes: [x[0], y[0]]};
  }
  return null;
}

function embodiedSvg(name, attributes = {}, content = "") {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  if (content) node.textContent = content;
  return node;
}

function renderEmbodiedMap(regions, selected, layout) {
  const svg = $("#embodied-map");
  const empty = $("#embodied-map-empty");
  const zoomIn = $("#embodied-zoom-in");
  const zoomOut = $("#embodied-zoom-out");
  const zoomReset = $("#embodied-zoom-reset");
  const points = regions.map((region, index) => ({
    region,
    ...embodiedRegionIdentity(region, index),
    coordinates: embodiedCoordinates(region),
  })).filter((item) => item.coordinates);
  svg.replaceChildren();
  if (!points.length) {
    svg.classList.add("hidden");
    empty.classList.remove("hidden");
    empty.textContent = regions.length
      ? "Owner-reported regions do not include a common pair of numeric current_coordinates; no spatial projection is drawn."
      : "No regional coordinates are available to project.";
    zoomIn.disabled = true;
    zoomOut.disabled = true;
    zoomReset.disabled = true;
    $("#embodied-map-caption").textContent = "No anatomy, connections, or motion are inferred.";
    return;
  }
  svg.classList.remove("hidden");
  empty.classList.add("hidden");
  zoomIn.disabled = false;
  zoomOut.disabled = false;
  zoomReset.disabled = false;

  let lowX = Infinity;
  let highX = -Infinity;
  let lowY = Infinity;
  let highY = -Infinity;
  for (const point of points) {
    lowX = Math.min(lowX, point.coordinates.x);
    highX = Math.max(highX, point.coordinates.x);
    lowY = Math.min(lowY, point.coordinates.y);
    highY = Math.max(highY, point.coordinates.y);
  }
  const baseWidth = (highX - lowX) || 1;
  const baseHeight = (highY - lowY) || 1;
  const zoom = state.embodiedField.zoom;
  const selectedPoint = points.find((point) => point.key === state.embodiedField.selectedRegionKey);
  const centerX = selectedPoint?.coordinates.x ?? (lowX + highX) / 2;
  const centerY = selectedPoint?.coordinates.y ?? (lowY + highY) / 2;
  const width = baseWidth * 1.2 / zoom;
  const height = baseHeight * 1.2 / zoom;
  const minX = centerX - width / 2;
  const minY = centerY - height / 2;
  const plot = {left: 68, top: 28, width: 610, height: 310};
  const mapX = (value) => plot.left + (value - minX) / width * plot.width;
  const mapY = (value) => plot.top + (minY + height - value) / height * plot.height;

  for (let tick = 0; tick <= 4; tick += 1) {
    const x = plot.left + plot.width * tick / 4;
    const y = plot.top + plot.height * tick / 4;
    const xValue = minX + width * tick / 4;
    const yValue = minY + height * (4 - tick) / 4;
    svg.append(
      embodiedSvg("line", {x1: x, y1: plot.top, x2: x, y2: plot.top + plot.height, class: tick === 0 ? "field-axis" : "field-tick"}),
      embodiedSvg("line", {x1: plot.left, y1: y, x2: plot.left + plot.width, y2: y, class: tick === 4 ? "field-axis" : "field-tick"}),
      embodiedSvg("text", {x, y: plot.top + plot.height + 18, "text-anchor": "middle"}, String(Number(xValue.toPrecision(6)))),
      embodiedSvg("text", {x: plot.left - 8, y: y + 4, "text-anchor": "end"}, String(Number(yValue.toPrecision(6)))),
    );
  }
  const firstAxes = points[0].coordinates.axes;
  const declaredAxes = layout?.value?.coordinate_axes ?? layout?.value?.axes;
  const axisName = (index) => Array.isArray(declaredAxes) && declaredAxes[index]
    ? embodiedScalar(declaredAxes[index])
    : firstAxes[index];
  svg.append(
    embodiedSvg("text", {x: plot.left + plot.width / 2, y: 385, "text-anchor": "middle", class: "field-axis-label"}, axisName(0)),
    embodiedSvg("text", {x: 14, y: plot.top + plot.height / 2, "text-anchor": "middle", transform: `rotate(-90 14 ${plot.top + plot.height / 2})`, class: "field-axis-label"}, axisName(1)),
  );
  for (const point of points) {
    const group = embodiedSvg("g", {
      "data-field-map-key": point.key,
      tabindex: "0",
      role: "button",
      "aria-label": `Select owner-reported region ${point.label}, coordinates ${point.coordinates.x}, ${point.coordinates.y}`,
    });
    group.append(
      embodiedSvg("circle", {
        cx: mapX(point.coordinates.x),
        cy: mapY(point.coordinates.y),
        r: point.key === state.embodiedField.selectedRegionKey ? 8 : 6,
        class: `field-region-point${point.key === state.embodiedField.selectedRegionKey ? " selected" : ""}`,
      }),
      embodiedSvg("text", {
        x: mapX(point.coordinates.x) + 9,
        y: mapY(point.coordinates.y) - 8,
        class: "field-region-label",
      }, point.label.slice(0, 28)),
    );
    svg.append(group);
  }
  $("#embodied-map-caption").textContent = `Static projection of the first two numeric values in owner-reported current_coordinates (${axisName(0)}, ${axisName(1)}). Point positions use those values; no anatomy, connections, or motion are inferred.`;
}

function renderEmbodiedRegions(snapshot) {
  const section = snapshot?.regions;
  const list = $("#embodied-regions");
  const select = $("#embodied-region-select");
  const detail = $("#embodied-region-detail");
  const note = $("#embodied-region-note");
  const regions = embodiedSectionState(section) === "known" && Array.isArray(section?.items)
    ? section.items
    : [];
  list.replaceChildren();
  select.replaceChildren();
  $("#embodied-region-count").textContent = section?.truncated === true
    ? `${regions.length}+ regions`
    : `${regions.length} regions`;
  select.disabled = regions.length === 0;
  if (!regions.length) {
    const option = new Option(section?.reason || "No regions reported", "");
    select.append(option);
    detail.textContent = section?.reason || "No regional values were returned by the owner.";
    note.textContent = section?.reason || (embodiedSectionState(section) === "known" ? "No regional records were returned." : "Regional data is unavailable.");
    renderEmbodiedMap([], null, snapshot?.layout);
    return null;
  }
  const entries = regions.map((region, index) => ({region, ...embodiedRegionIdentity(region, index)}));
  if (!entries.some((entry) => entry.key === state.embodiedField.selectedRegionKey)) {
    state.embodiedField.selectedRegionKey = entries[0].key;
  }
  const truncatedNote = section?.truncated === true
    ? `Showing ${regions.length} owner-reported records; the snapshot declares a limit of ${embodiedScalar(section.limit)}.`
    : `Showing ${regions.length} owner-reported regional record${regions.length === 1 ? "" : "s"}.`;
  note.textContent = truncatedNote;

  for (const entry of entries) {
    const option = new Option(entry.label, entry.key);
    select.append(option);
    const card = document.createElement("article");
    card.className = `embodied-region-card${entry.key === state.embodiedField.selectedRegionKey ? " selected" : ""}`;
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.embodiedRegionKey = entry.key;
    button.textContent = entry.label;
    const values = document.createElement("pre");
    values.textContent = embodiedJson(entry.region, 1_800);
    card.append(button, values);
    list.append(card);
  }
  select.value = state.embodiedField.selectedRegionKey;
  const selected = entries.find((entry) => entry.key === state.embodiedField.selectedRegionKey);
  detail.textContent = embodiedJson(selected.region, 12_000);
  renderEmbodiedMap(regions, selected, snapshot?.layout);
  return selected.region;
}

function renderEmbodiedSemantics(snapshot, selectedRegion) {
  const section = snapshot?.semantics;
  const list = $("#embodied-meanings");
  const note = $("#embodied-meaning-note");
  const stateName = embodiedSectionState(section);
  $("#embodied-meaning-state").textContent = stateName;
  list.replaceChildren();
  if (stateName !== "known") {
    note.textContent = section?.reason || "Semantic bindings are unavailable.";
    return;
  }
  const items = Array.isArray(section?.items) ? section.items : [];
  if (!items.length) {
    note.textContent = "No semantic bindings were returned for this snapshot.";
    return;
  }
  const regionId = selectedRegion?.region_id ?? selectedRegion?.id ?? selectedRegion?.name;
  const matching = regionId === undefined || regionId === null ? [] : items.filter((item) => {
    const references = [
      item?.region_id, item?.region_ref, item?.region, item?.payload?.region_id,
      item?.payload?.region_ref,
    ].filter((value) => value !== undefined && value !== null);
    return references.some((value) => String(value) === String(regionId));
  });
  const displayItems = matching.length ? matching : items;
  note.textContent = matching.length
    ? `Showing ${matching.length} binding record${matching.length === 1 ? "" : "s"} explicitly linked to this region.`
    : selectedRegion
      ? "No binding declares a link to this region; the returned semantic records are shown without assigning them to it."
      : "No region is selected; returned semantic records are shown without assigning them to a region.";
  for (const item of displayItems) {
    const card = document.createElement("article");
    card.className = "embodied-meaning";
    const heading = document.createElement("h4");
    heading.textContent = [item?.record_id ?? item?.variable_id ?? item?.chart_id ?? item?.id,
      item?.record_kind ?? item?.kind, item?.status]
      .filter((value) => value !== undefined && value !== null)
      .map((value) => embodiedScalar(value)).join(" · ") || "Binding identifier unavailable";
    const payload = item?.payload;
    const meaning = [item?.meaning, item?.label, item?.description, payload?.meaning, payload?.label, payload?.description, payload?.text]
      .find((value) => typeof value === "string" && value.trim());
    const copy = document.createElement("p");
    copy.textContent = meaning
      ? meaning
      : item?.kind === "field-binding"
        ? `${item.epistemic_kind ?? "Unknown epistemic status"} · version ${item.content_version ?? "unavailable"}. Reference metadata only; content stays with the owner.`
        : payload === undefined || payload === null
          ? "Only the declared meaning metadata is available."
          : "No separate meaning text is declared; the reported payload is available below.";
    card.append(heading, copy);
    if (payload !== undefined) {
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = "Reported binding payload";
      const pre = document.createElement("pre");
      pre.textContent = embodiedJson(payload, 5_000);
      details.append(summary, pre);
      card.append(details);
    }
    list.append(card);
  }
  if (section?.truncated === true) {
    const truncation = document.createElement("p");
    truncation.className = "quiet";
    truncation.textContent = `Semantic records are bounded at ${embodiedScalar(section.limit)}; additional records are not shown.`;
    list.append(truncation);
  }
}

function embodiedExchangeMeaningReferenceValid(reference) {
  return Boolean(reference && typeof reference === "object" && !Array.isArray(reference)
    && (typeof reference.id === "string" || typeof reference.id === "number")
    && String(reference.id).trim()
    && typeof reference.kind === "string" && reference.kind.trim()
    && reference.content_version !== null && reference.content_version !== undefined);
}
function embodiedExchangeConcernValid(reference) {
  return Boolean(reference && typeof reference === "object" && !Array.isArray(reference)
    && Object.keys(reference).length === 5
    && typeof reference.concern_id === "string" && reference.concern_id.trim()
    && typeof reference.project_id === "string" && reference.project_id.trim()
    && (reference.question_ref === null || embodiedExchangeMeaningReferenceValid(reference.question_ref))
    && Array.isArray(reference.object_refs)
    && reference.object_refs.every(embodiedExchangeMeaningReferenceValid)
    && (reference.goal_ref === null || embodiedExchangeMeaningReferenceValid(reference.goal_ref)));
}
function embodiedExchangeAppraisalValid(reference) {
  return Boolean(reference && typeof reference === "object" && !Array.isArray(reference)
    && typeof reference.operation_id === "string" && reference.operation_id.trim()
    && typeof reference.assessment_sha256 === "string"
    && /^[a-f0-9]{64}$/iu.test(reference.assessment_sha256));
}


function embodiedExchangeMeaningItemValid(item) {
  const token = (value) => (typeof value === "string" && value.trim()) || (typeof value === "number" && Number.isFinite(value));
  const source = item?.result_source;
  const sourceValid = source === null || Boolean(source && typeof source === "object" && !Array.isArray(source)
    && token(source.revision_id)
    && typeof source.content_sha256 === "string" && /^[a-f0-9]{64}$/iu.test(source.content_sha256)
    && source.status === "active"
    && (source.summary == null || typeof source.summary === "string"));
  const recalledValid = Array.isArray(item?.recalled_memories)
    && item.recalled_memories.every((memory) => embodiedExchangeMeaningReferenceValid(memory?.record_ref)
      && typeof memory.role === "string" && typeof memory.reason === "string"
      && Array.isArray(memory.source_revision_ids)
      && memory.source_revision_ids.every((id) => typeof id === "string")
      && (memory.result_summary === undefined || typeof memory.result_summary === "string")
      && (memory.result_status === undefined || typeof memory.result_status === "string"));
  return Boolean(item && typeof item === "object" && !Array.isArray(item)
    && token(item.computer_id) && typeof item.interface === "string" && item.interface.trim()
    && token(item.emitter_region_id) && token(item.receiver_region_id)
    && item.relation === "assessed-work-tuned-receiver"
    && (embodiedExchangeConcernValid(item.concern_ref) || embodiedExchangeMeaningReferenceValid(item.concern_ref))
    && typeof item.concern_summary === "string" && item.concern_summary.trim()
    && embodiedExchangeMeaningReferenceValid(item.assessment_ref)
    && sourceValid && recalledValid
    && embodiedExchangeAppraisalValid(item.last_appraisal_ref)
    && (item.exchange?.status === "available" || item.exchange?.status === "unavailable")
    && ["before-feedback", "after-feedback", "unverified"].includes(item.exchange.measurement_timing)
    && (item.exchange.status !== "available"
      || embodiedExchangeConcernValid(item.concern_ref)
      || item.exchange.measurement_timing === "before-feedback"));
}

function embodiedExchangeConcernText(reference) {
  return embodiedExchangeConcernValid(reference)
    ? `Concern ${embodiedScalar(reference.concern_id)} · project ${embodiedScalar(reference.project_id)}`
    : embodiedExchangeMeaningReferenceText(reference);
}
function embodiedExchangeMeaningText(value, limit = 2_400) {
  const text = typeof value === "string" ? value : embodiedScalar(value, "not reported");
  return text.length > limit ? `${text.slice(0, limit)}\n… clipped for display` : text;
}

function embodiedExchangeMeaningReferenceText(reference) {
  return `ID ${embodiedScalar(reference.id)} · kind ${embodiedScalar(reference.kind)} · content version ${embodiedScalar(reference.content_version)}`;
}

function appendEmbodiedExchangeMeaningFact(list, label, value) {
  const row = document.createElement("div");
  const term = document.createElement("dt");
  term.textContent = label;
  const detail = document.createElement("dd");
  detail.textContent = embodiedExchangeMeaningText(value);
  row.append(term, detail);
  list.append(row);
}

function appendEmbodiedExchangeMeaningSection(card, title) {
  const section = document.createElement("section");
  section.className = "embodied-exchange-section";
  const heading = document.createElement("h5");
  heading.textContent = title;
  section.append(heading);
  card.append(section);
  return section;
}

function embodiedExchangeMeaningMatchesRegion(item, region) {
  if (!region) return true;
  const id = region.region_id ?? region.id ?? region.name;
  if (id === undefined || id === null) return false;
  return [item.emitter_region_id, item.receiver_region_id].some((regionId) => String(regionId) === String(id));
}
function embodiedExchangeMeaningKey(item, index) {
  return JSON.stringify([
    index, item.computer_id, item.interface, item.emitter_region_id, item.receiver_region_id,
    item.concern_ref.concern_id ?? item.concern_ref.id, item.assessment_ref.id,
    item.assessment_ref.content_version, item.result_source?.revision_id ?? null,
    item.last_appraisal_ref.operation_id,
  ]);
}
function renderEmbodiedExchangeMeaning(snapshot, selectedRegion) {
  const section = snapshot?.exchange_meaning;
  const select = $("#embodied-exchange-meaning-select");
  const detail = $("#embodied-exchange-meaning-detail");
  const note = $("#embodied-exchange-meaning-note");
  const status = embodiedSectionState(section);
  $("#embodied-exchange-meaning-state").textContent = status;
  select.replaceChildren();
  detail.replaceChildren();
  const unavailableOption = (label) => {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = label;
    select.append(option);
    select.disabled = true;
  };

  if (status !== "known" && status !== "partial") {
    unavailableOption("No linked assessed exchange");
    const unavailableNotes = [section?.reason
      ? embodiedExchangeMeaningText(section.reason, 800)
      : "Assessment-linked exchange context is unavailable; no concern, source, recall, tuning, or measurement is inferred."];
    if (section?.truncated === true) {
      unavailableNotes.push(`The owner snapshot is truncated at ${embodiedScalar(section.limit)} exchange records; additional records are not shown.`);
    }
    note.textContent = unavailableNotes.join(" ");
    return;
  }

  const items = Array.isArray(section?.items) ? section.items : [];
  const validItems = items.map((item, index) => ({item, index}))
    .filter((entry) => embodiedExchangeMeaningItemValid(entry.item))
    .map((entry) => ({...entry, key: embodiedExchangeMeaningKey(entry.item, entry.index)}));
  const invalidCount = items.length - validItems.length;
  const matching = validItems.filter(({item}) => embodiedExchangeMeaningMatchesRegion(item, selectedRegion));
  const noteParts = [];
  if (matching.length) {
    noteParts.push(selectedRegion
      ? `Showing ${matching.length} owner-recorded exchange${matching.length === 1 ? "" : "s"} explicitly naming this region as emitter or receiver.`
      : `No region is selected; showing ${matching.length} owner-recorded exchange${matching.length === 1 ? "" : "s"} with their explicit emitter and receiver identifiers.`);
  } else {
    noteParts.push(selectedRegion
      ? "No provenance-bound exchange explicitly names this region as its emitter or receiver. No concern, result source, recalled memory, or tuning is assigned to it."
      : "No valid provenance-bound exchange records are available to select.");
  }
  if (section?.reason) noteParts.push(embodiedExchangeMeaningText(section.reason, 800));
  if (section?.truncated === true) {
    noteParts.push(`The owner snapshot is truncated at ${embodiedScalar(section.limit)} exchange records; additional records are not shown.`);
  }
  if (invalidCount) noteParts.push(`${invalidCount} record${invalidCount === 1 ? " was" : "s were"} omitted because required provenance links or values were missing or malformed.`);
  note.textContent = noteParts.join(" ");

  if (!matching.length) {
    unavailableOption(selectedRegion ? "No exchange linked to selected region" : "No provenance-bound exchange available");
    return;
  }

  for (const entry of matching) {
    const option = document.createElement("option");
    option.value = entry.key;
    const interfaceName = embodiedExchangeMeaningText(entry.item.interface, 48);
    const concern = embodiedExchangeMeaningText(entry.item.concern_summary, 92).replace(/\s+/gu, " ");
    option.textContent = `${interfaceName} · ${concern} · emitter ${embodiedExchangeMeaningText(entry.item.emitter_region_id, 40)} → receiver ${embodiedExchangeMeaningText(entry.item.receiver_region_id, 40)}`;
    select.append(option);
  }
  const chosen = matching.find((entry) => entry.key === state.embodiedField.selectedExchangeMeaningKey) || matching[0];
  state.embodiedField.selectedExchangeMeaningKey = chosen.key;
  select.value = chosen.key;
  select.disabled = false;

  const item = chosen.item;
  const card = document.createElement("article");
  card.className = "embodied-exchange-card";
  const heading = document.createElement("h4");
  heading.textContent = embodiedExchangeMeaningText(item.interface, 240);
  const relation = document.createElement("p");
  relation.textContent = "Current tuning provenance: assessed work tuned the explicitly named receiver. This provenance is separate from the measured circulation values and does not assign semantic content to a signed current.";
  const provenance = document.createElement("dl");
  provenance.className = "embodied-exchange-provenance";
  appendEmbodiedExchangeMeaningFact(provenance, "Computer", item.computer_id);
  appendEmbodiedExchangeMeaningFact(provenance, "Interface", item.interface);
  appendEmbodiedExchangeMeaningFact(provenance, "Emitter region ID", item.emitter_region_id);
  appendEmbodiedExchangeMeaningFact(provenance, "Receiver region ID", item.receiver_region_id);
  appendEmbodiedExchangeMeaningFact(provenance, "Concern identity", embodiedExchangeConcernText(item.concern_ref));
  appendEmbodiedExchangeMeaningFact(provenance, "Assessment reference", embodiedExchangeMeaningReferenceText(item.assessment_ref));
  appendEmbodiedExchangeMeaningFact(provenance, "Last appraisal operation", item.last_appraisal_ref.operation_id);
  appendEmbodiedExchangeMeaningFact(provenance, "Assessment SHA-256 at feedback", item.last_appraisal_ref.assessment_sha256);
  card.append(heading, relation, provenance);

  const concern = appendEmbodiedExchangeMeaningSection(card, "Recorded concern / question");
  const concernCopy = document.createElement("p");
  concernCopy.textContent = embodiedExchangeMeaningText(item.concern_summary);
  concern.append(concernCopy);

  const result = appendEmbodiedExchangeMeaningSection(card, "Archived result source");
  const concernBindings = document.createElement("pre");
  concernBindings.textContent = embodiedExchangeMeaningText(JSON.stringify(item.concern_ref), 1_200);
  concern.append(concernBindings);

  const feedback = appendEmbodiedExchangeMeaningSection(card, "Measured feedback tuning");
  const feedbackFacts = document.createElement("dl");
  feedbackFacts.className = "embodied-exchange-provenance";
  appendEmbodiedExchangeMeaningFact(feedbackFacts, "Feedback status", item.exchange.feedback?.status ?? "not reported");
  appendEmbodiedExchangeMeaningFact(feedbackFacts, "Tuning progress", item.exchange.feedback?.progress ?? "not reported");
  appendEmbodiedExchangeMeaningFact(feedbackFacts, "Tuning direction", item.exchange.feedback?.direction ?? "not reported");
  appendEmbodiedExchangeMeaningFact(feedbackFacts, "Appraisal assessment SHA-256", item.last_appraisal_ref.assessment_sha256);
  feedback.append(feedbackFacts);
  if (item.result_source === null) {
    const missing = document.createElement("p");
    missing.textContent = "No archived result source is linked to this Assessment.";
    result.append(missing);
  } else {
    const sourceFacts = document.createElement("dl");
    sourceFacts.className = "embodied-exchange-provenance";
    appendEmbodiedExchangeMeaningFact(sourceFacts, "Revision ID", item.result_source.revision_id);
    appendEmbodiedExchangeMeaningFact(sourceFacts, "Content SHA-256", item.result_source.content_sha256);
    appendEmbodiedExchangeMeaningFact(sourceFacts, "Source status", item.result_source.status);
    result.append(sourceFacts);
    if (typeof item.result_source.summary === "string" && item.result_source.summary.trim()) {
      const summary = document.createElement("p");
      summary.textContent = embodiedExchangeMeaningText(item.result_source.summary);
      result.append(summary);
    }
  }

  const recall = appendEmbodiedExchangeMeaningSection(card, "Actual recalled memory references");
  if (!item.recalled_memories.length) {
    const none = document.createElement("p");
    none.textContent = "No recalled memory references are linked in these field records. Memory relevance is not inferred.";
    recall.append(none);
  } else {
    const memories = document.createElement("div");
    memories.className = "embodied-exchange-memory-list";
    for (const memory of item.recalled_memories) {
      const memoryCard = document.createElement("article");
      memoryCard.className = "embodied-exchange-memory";
      const memoryRef = document.createElement("p");
      memoryRef.textContent = `Record reference: ${embodiedExchangeMeaningReferenceText(memory.record_ref)}`;
      const role = document.createElement("p");
      role.textContent = `Recorded role: ${embodiedExchangeMeaningText(memory.role, 500)}`;
      const reason = document.createElement("p");
      reason.textContent = `Recorded link reason: ${embodiedExchangeMeaningText(memory.reason, 800)}`;
      memoryCard.append(memoryRef, role, reason);
      if (memory.result_summary) {
        const resultSummary = document.createElement("p");
        resultSummary.textContent = `Recalled result: ${embodiedExchangeMeaningText(memory.result_summary, 500)}`;
        memoryCard.append(resultSummary);
      }
      if (memory.result_status) {
        const resultStatus = document.createElement("p");
        resultStatus.textContent = `Recorded outcome: ${embodiedExchangeMeaningText(memory.result_status, 64)}`;
        memoryCard.append(resultStatus);
      }
      if (memory.source_revision_ids.length) {
        const source = document.createElement("p");
        source.textContent = `Active source revision: ${memory.source_revision_ids.join(", ")}`;
        memoryCard.append(source);
      }
      memories.append(memoryCard);
    }
    recall.append(memories);
  }

  const measurement = appendEmbodiedExchangeMeaningSection(card, "Last measured exchange · field-reported");
  measurement.classList.add("embodied-exchange-measurement");
  const measurementState = document.createElement("p");
  measurementState.textContent = `Measurement status: ${item.exchange.status}.`;
  measurement.append(measurementState);
  if (item.exchange.status === "available") {
    const measurementFacts = document.createElement("dl");
    measurementFacts.className = "embodied-exchange-provenance";
    appendEmbodiedExchangeMeaningFact(measurementFacts, "Last-exchange SHA-256", item.exchange.owner_reported_last_exchange_sha256 ?? "not reported");
    appendEmbodiedExchangeMeaningFact(measurementFacts, "Overlap", item.exchange.overlap ?? "not reported");
    appendEmbodiedExchangeMeaningFact(measurementFacts, "Effective weight", item.exchange.effective_weight ?? "not reported");
    appendEmbodiedExchangeMeaningFact(measurementFacts, "Relative to linked feedback", item.exchange.measurement_timing);
    measurement.append(measurementFacts);
    const timing = document.createElement("p");
    timing.textContent = item.exchange.measurement_timing === "before-feedback"
      ? "This exchange was measured before the linked feedback."
      : item.exchange.measurement_timing === "after-feedback"
        ? "A later circulation pass measured this exchange after the linked feedback."
        : "The recorded history cannot establish this exchange's order relative to feedback.";
    measurement.append(timing);
  } else {
    const unavailable = document.createElement("p");
    unavailable.textContent = typeof item.exchange.reason === "string" && item.exchange.reason.trim()
      ? embodiedExchangeMeaningText(item.exchange.reason, 800)
      : "No last-exchange measurement is available for this interface and Assessment. The signed circulation readout remains separate.";
    measurement.append(unavailable);
  }
  detail.append(card);
}

function renderEmbodiedCaptureControls() {
  const captures = state.embodiedField.captures;
  const fill = (selectId, emptyLabel, preferredId) => {
    const select = $(selectId);
    const previous = select.value;
    select.replaceChildren();
    if (!captures.length) {
      select.append(new Option(emptyLabel, ""));
      select.disabled = true;
      return;
    }
    for (const record of captures) {
      const hash = record.snapshot?.state_sha256;
      const label = `${embodiedTime(record.capturedAt)} · ${typeof hash === "string" ? hash.slice(0, 10) : "state id unavailable"}`;
      select.append(new Option(label, record.id));
    }
    const desired = captures.some((record) => record.id === previous)
      ? previous
      : captures.some((record) => record.id === preferredId)
        ? preferredId
        : captures.at(-1).id;
    select.value = desired;
    select.disabled = false;
  };
  fill("#embodied-replay-select", "No captures yet", state.embodiedField.replayId || captures.at(-1)?.id);
  fill("#embodied-compare-a", "No captures yet", captures[0]?.id);
  fill("#embodied-compare-b", "No captures yet", captures.at(-1)?.id);
  $("#embodied-capture-count").textContent = `${captures.length} captures`;
  const selectedReplayIndex = captures.findIndex((record) => record.id === $("#embodied-replay-select").value);
  $("#embodied-replay-show").disabled = captures.length === 0;
  $("#embodied-replay-previous").disabled = selectedReplayIndex <= 0;
  $("#embodied-replay-next").disabled = selectedReplayIndex < 0 || selectedReplayIndex >= captures.length - 1;
  const compareA = $("#embodied-compare-a").value;
  const compareB = $("#embodied-compare-b").value;
  $("#embodied-compare-run").disabled = captures.length < 2 || !compareA || !compareB || compareA === compareB;
}

function renderEmbodiedField() {
  const field = state.embodiedField;
  const view = embodiedFieldView();
  const refresh = $("#embodied-field-refresh");
  refresh.disabled = !state.connected || field.loading;
  $("#embodied-field-capture").disabled = !view;
  $("#embodied-field-freeze").disabled = !view;
  $("#embodied-field-freeze").textContent = field.mode === "frozen" ? "Resume live display" : "Freeze current view";
  renderEmbodiedCaptureControls();
  if (!view) {
    $("#embodied-field-status").textContent = field.error
      ? `Snapshot unavailable: ${field.error}`
      : field.loading ? "Reading the canonical owner field…" : "No field snapshot is available yet.";
    $("#embodied-field-hash").textContent = "Unavailable";
    $("#embodied-field-generation").textContent = "Unavailable";
    $("#embodied-field-sample-time").textContent = "Unavailable";
    $("#embodied-layout-state").textContent = "Unavailable";
    $("#embodied-layout-note").textContent = "Layout is unavailable until an owner snapshot is read.";
    $("#embodied-layout").textContent = field.error || "Waiting for owner data…";
    renderEmbodiedCirculation(null);
    $("#embodied-region-count").textContent = "0 regions";
    renderEmbodiedRegions(null);
    renderEmbodiedExchangeMeaning(null, null);
    $("#embodied-meaning-state").textContent = "Unavailable";
    $("#embodied-meaning-note").textContent = "Meaning is unavailable until the owner snapshot is read.";
    $("#embodied-meanings").replaceChildren();
    return;
  }

  const snapshot = view.snapshot;
  const viewLabel = view.mode === "frozen"
    ? `Frozen sample · received ${embodiedTime(view.sampledAt)}`
    : view.mode === "replay"
      ? `Replay · captured ${embodiedTime(view.record.capturedAt)} · sampled ${embodiedTime(view.sampledAt)}`
      : `Live sample · received ${embodiedTime(view.sampledAt)}`;
  const newerLiveSample = view.mode !== "live" && field.latestAt && field.latestAt !== view.sampledAt;
  const pinnedNotice = newerLiveSample
    ? ` A newer live sample was received at ${embodiedTime(field.latestAt)}; the pinned display is unchanged.`
    : "";
  const snapshotStatus = snapshot.status === "partial" ? "Partial snapshot. " : "";
  $("#embodied-field-status").textContent = field.error
    ? `Refresh failed; showing the last ${view.mode} sample. ${field.error}`
    : snapshot.status === "unavailable"
      ? `Canonical owner inspection is unavailable; unavailable sections and reasons are shown below. ${viewLabel}${pinnedNotice}`
      : `${snapshotStatus}${viewLabel}${pinnedNotice}`;
  $("#embodied-field-hash").textContent = embodiedScalar(snapshot.state_sha256, "Unavailable");
  $("#embodied-field-generation").textContent = embodiedScalar(snapshot.generation, "Unavailable");
  $("#embodied-field-sample-time").textContent = viewLabel;

  const layout = snapshot.layout;
  const layoutState = embodiedSectionState(layout);
  $("#embodied-layout-state").textContent = layoutState;
  $("#embodied-layout-note").textContent = layoutState === "known"
    ? "Owner-declared layout and interpretation. Values are not converted into invented anatomy."
    : layout?.reason || "Layout is unavailable.";
  $("#embodied-layout").textContent = layoutState === "known" ? embodiedJson(layout.value, 10_000) : layout?.reason || "Unavailable";
  renderEmbodiedCirculation(snapshot.circulation);
  const selectedRegion = renderEmbodiedRegions(snapshot);
  renderEmbodiedExchangeMeaning(snapshot, selectedRegion);
  renderEmbodiedSemantics(snapshot, selectedRegion);
}

async function refreshEmbodiedField() {
  const field = state.embodiedField;
  if (field.loading) return;
  field.loading = true;
  field.error = "";
  renderEmbodiedField();
  try {
    const snapshot = await api("/v1/embodied-field");
    if (!snapshot || snapshot.schema !== "cassifi.embodied-field.v1") {
      throw new Error("the entity returned an unsupported embodied-field snapshot schema");
    }
    field.latest = snapshot;
    field.latestAt = new Date().toISOString();
    field.error = "";
  } catch (error) {
    field.error = embodiedErrorMessage(error);
  } finally {
    field.loading = false;
    renderEmbodiedField();
  }
}

function toggleEmbodiedFreeze() {
  const field = state.embodiedField;
  if (field.mode === "frozen") {
    field.mode = "live";
    field.frozen = null;
  } else {
    const view = embodiedFieldView();
    if (!view) return;
    field.frozen = {
      snapshot: JSON.parse(JSON.stringify(view.snapshot)),
      sampledAt: view.sampledAt,
    };
    field.mode = "frozen";
    field.replayId = "";
  }
  renderEmbodiedField();
}

function captureEmbodiedView() {
  const view = embodiedFieldView();
  if (!view) return;
  const record = {
    id: crypto.randomUUID(),
    capturedAt: new Date().toISOString(),
    sampledAt: view.sampledAt,
    snapshot: JSON.parse(JSON.stringify(view.snapshot)),
  };
  const captures = state.embodiedField.captures;
  captures.push(record);
  if (captures.length > 24) {
    const removed = captures.shift();
    if (state.embodiedField.replayId === removed.id) {
      state.embodiedField.mode = "live";
      state.embodiedField.replayId = "";
    }
  }
  renderEmbodiedCaptureControls();
  $("#embodied-history-note").textContent = `${captures.length} bounded capture${captures.length === 1 ? "" : "s"} retained in this browser page only. Replay is stepwise and does not interpolate states.`;
}

function showEmbodiedReplay(recordId) {
  const field = state.embodiedField;
  const record = field.captures.find((item) => item.id === recordId);
  if (!record) return;
  field.mode = "replay";
  field.frozen = null;
  field.replayId = record.id;
  $("#embodied-replay-select").value = record.id;
  renderEmbodiedField();
}

function stepEmbodiedReplay(step) {
  const captures = state.embodiedField.captures;
  const currentId = state.embodiedField.mode === "replay"
    ? state.embodiedField.replayId
    : $("#embodied-replay-select").value;
  const currentIndex = captures.findIndex((record) => record.id === currentId);
  const target = captures[currentIndex + step];
  if (target) showEmbodiedReplay(target.id);
}

function embodiedSnapshotQuantities(snapshot) {
  const values = [];
  const skip = /(^|\\.)(id|region_id|generation|content_version|index|timestamp|observed_at|captured_at|time)$/i;
  for (const [index, region] of (Array.isArray(snapshot?.regions?.items) ? snapshot.regions.items : []).entries()) {
    const identity = embodiedRegionIdentity(region, index);
    for (const row of embodiedNumbers(region, `regions.${identity.label}`)) {
      if (!skip.test(row.path)) values.push(row);
      if (values.length >= 128) return values;
    }
  }
  for (const row of embodiedNumbers(snapshot?.circulation?.value, "circulation")) {
    if (!skip.test(row.path)) values.push(row);
    if (values.length >= 128) break;
  }
  return values;
}

function compareEmbodiedSnapshots() {
  const left = state.embodiedField.captures.find((record) => record.id === $("#embodied-compare-a").value);
  const right = state.embodiedField.captures.find((record) => record.id === $("#embodied-compare-b").value);
  const output = $("#embodied-comparison");
  output.replaceChildren();
  if (!left || !right) {
    output.textContent = "Choose two captured snapshots to compare.";
    return;
  }
  if (left.id === right.id) {
    output.textContent = "Choose two different captured snapshots.";
    return;
  }
  const summary = document.createElement("p");
  summary.className = "quiet";
  summary.textContent = `A ${embodiedTime(left.capturedAt)} · ${embodiedScalar(left.snapshot.state_sha256, "state id unavailable")}  |  B ${embodiedTime(right.capturedAt)} · ${embodiedScalar(right.snapshot.state_sha256, "state id unavailable")}`;
  output.append(summary);
  const leftValues = new Map(embodiedSnapshotQuantities(left.snapshot).map((row) => [row.path, row.value]));
  const rightValues = new Map(embodiedSnapshotQuantities(right.snapshot).map((row) => [row.path, row.value]));
  const paths = [...new Set([...leftValues.keys(), ...rightValues.keys()])].slice(0, 128);
  if (paths.length) {
    const table = document.createElement("table");
    const head = document.createElement("thead");
    const header = document.createElement("tr");
    for (const title of ["Owner-reported quantity", "A", "B", "B − A"]) {
      const cell = document.createElement("th");
      cell.textContent = title;
      header.append(cell);
    }
    head.append(header);
    const body = document.createElement("tbody");
    for (const path of paths) {
      const row = document.createElement("tr");
      const pathCell = document.createElement("td");
      pathCell.textContent = path;
      const a = leftValues.get(path);
      const b = rightValues.get(path);
      const aCell = document.createElement("td");
      aCell.textContent = a === undefined ? "not reported" : String(a);
      const bCell = document.createElement("td");
      bCell.textContent = b === undefined ? "not reported" : String(b);
      const delta = document.createElement("td");
      delta.textContent = a === undefined || b === undefined ? "not comparable" : String(b - a);
      row.append(pathCell, aCell, bCell, delta);
      body.append(row);
    }
    table.append(head, body);
    output.append(table);
  } else {
    const empty = document.createElement("p");
    empty.className = "quiet";
    empty.textContent = "Neither capture reports comparable numeric regional or circulation quantities.";
    output.append(empty);
  }
  for (const [label, record] of [["Snapshot A data", left], ["Snapshot B data", right]]) {
    const details = document.createElement("details");
    const summaryNode = document.createElement("summary");
    summaryNode.textContent = label;
    const pre = document.createElement("pre");
    pre.textContent = embodiedJson(record.snapshot, 18_000);
    details.append(summaryNode, pre);
    output.append(details);
  }
}

function chooseEmbodiedRegion(key) {
  state.embodiedField.selectedRegionKey = key;
  renderEmbodiedField();
}

async function connectLocalWorkspace() {
  setConnected(false, "Connecting to local entity");
  try {
    await loadPrograms();
    setConnected(true, "Entity online");
    void refreshEmbodiedField();
    startEvents();
    if (state.surface.bindingId) {
      if (!state.surface.timer) startSurfacePolling();
    } else if (state.programId && state.surface.descriptorProgramId !== state.programId) {
      try { await loadSurfaceDescriptor(); } catch (error) { await handleError(error, {refresh: false}); }
    } else if (!state.programId) {
      surfaceMessage("Connected. Select an existing program to discover its mission-scoped surface sources.", "warn");
    }
  } catch (error) {
    setConnected(false, "Local entity unavailable");
    state.embodiedField.error = `Entity connection unavailable: ${embodiedErrorMessage(error)}`;
    state.embodiedField.loading = false;
    renderEmbodiedField();
    await handleError(error, {refresh: false});
  }
}

void connectLocalWorkspace();

$("#refresh-programs").addEventListener("click", () => action("Program list refreshed.", loadPrograms, {refresh: false}));
$("#program-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-program-id]");
  if (button) action(`Opened ${button.dataset.programId}.`, () => selectProgram(button.dataset.programId), {refresh: false});
});

$("#program-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.programAdmissionInFlight) return;
  const formElement = event.currentTarget;
  const form = new FormData(formElement);
  const brief = String(form.get("brief") || "").trim();
  const context = String(form.get("context") || "").trim();
  const useLinuxDesktop = formElement.elements.linux_desktop.checked;
  if (!brief) {
    toast("Write a short research brief to begin.", "warn");
    return;
  }
  const admission = programAdmissionForBrief(brief, context, useLinuxDesktop);
  const submitButton = $('button[type="submit"]', formElement);
  state.programAdmissionInFlight = true;
  submitButton.disabled = true;
  try {
    await action("Research project opened.", async () => {
      await api("/v1/programs", {method: "POST", body: admission.body});
      await loadPrograms();
      await selectProgram(admission.programId);
      if (state.pendingProgramAdmission === admission) {
        state.pendingProgramAdmission = null;
      }
      if (
        String(formElement.elements.brief.value).trim() === brief
        && String(formElement.elements.context.value).trim() === context
        && formElement.elements.linux_desktop.checked === useLinuxDesktop
      ) {
        formElement.reset();
      }
      return {program_id: admission.programId};
    }, {refresh: false});
  } finally {
    state.programAdmissionInFlight = false;
    submitButton.disabled = false;
  }
});

$("#consequence-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.programId) return;
  const formElement = event.currentTarget;
  const form = new FormData(formElement);
  const consequence = {
    dimension: String(form.get("dimension")),
    affected: String(form.get("affected")).trim(),
    observation: String(form.get("observation")).trim(),
    evidence: String(form.get("evidence")).trim(),
    uncertainty: String(form.get("uncertainty")).trim(),
    status: String(form.get("status")),
    follow_up: String(form.get("follow_up")).trim() || null,
  };
  const reviewOf = String(form.get("review_of_assessment_id") || "").trim();
  if (reviewOf) consequence.review_of_assessment_id = reviewOf;
  await action(reviewOf ? "Review recorded against the selected report." : "Consequence recorded for follow-up.", async () => {
    await api(`/v1/programs/${encodeURIComponent(state.programId)}/consequences`, {
      method: "POST",
      body: {
        request_id: requestId("record-consequence"),
        observed_at: now(),
        consequence,
      },
    });
    formElement.reset();
    state.program = await api(`/v1/programs/${encodeURIComponent(state.programId)}`);
    renderProgramHeader();
  }, {refresh: false});
});

$(".tabs").addEventListener("click", (event) => {
  const tab = event.target.closest("[data-tab]");
  if (!tab) return;
  $$(".tab").forEach((node) => node.classList.toggle("active", node === tab));
  $$(".tab-panel").forEach((node) => node.classList.toggle("active", node.id === `tab-${tab.dataset.tab}`));
  if (tab.dataset.tab === "surface" && state.connected) {
    if (state.surface.bindingId) {
      if (!state.surface.timer) startSurfacePolling();
    } else if (state.programId && (!state.surface.descriptor || state.surface.descriptorProgramId !== state.programId)) {
      action("Mission-scoped surface capabilities loaded.", loadSurfaceDescriptor, {refresh: false});
    }
  }
});

$("#workspace-category").addEventListener("change", () => { state.workspaceOffset = 0; action("Workspace view loaded.", loadWorkspace, {refresh: false}); });
$("#workspace-refresh").addEventListener("click", () => action("Workspace view refreshed.", loadWorkspace, {refresh: false}));
$("#workspace-prev").addEventListener("click", () => { state.workspaceOffset = Math.max(0, state.workspaceOffset - state.workspaceLimit); action("Previous page loaded.", loadWorkspace, {refresh: false}); });
$("#workspace-next").addEventListener("click", () => { state.workspaceOffset += state.workspaceLimit; action("Next page loaded.", loadWorkspace, {refresh: false}); });
$("#workspace-pause").addEventListener("click", () => action("Workspace paused. Read-only inspection remains live.", () => workspaceCommand({operation: "pause"})));
$("#workspace-resume").addEventListener("click", () => action("Workspace resumed.", () => workspaceCommand({operation: "resume"})));

$("#proposal-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await action("Structured guidance proposed.", () => workspaceCommand({
    operation: "propose",
    request_id: String(form.get("request_id")).trim(),
    principal: state.workspace?.principal || state.entityId,
    target_refs: csv(form.get("target_refs")),
    expected_versions: parseJson(form.get("expected_versions"), "Expected versions"),
    intended_role: String(form.get("intended_role")).trim(),
    arguments: parseJson(form.get("arguments"), "Arguments"),
    dependencies: [],
    source_refs: [],
  }));
});

$("#workspace-branch-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitter = event.submitter;
  const disposition = submitter?.dataset.workspaceBranch;
  const form = new FormData(event.currentTarget);
  const request = String(form.get("request_id")).trim();
  const branch = String(form.get("branch_id")).trim();
  if (disposition === "investigate") {
    await action("Investigation branch started.", () => workspaceCommand({
      operation: "investigate", request_id: request, branch_id: branch,
      program_refs: csv(form.get("program_refs")),
      assumptions: parseJson(form.get("assumptions"), "Assumptions"),
      held_fixed: [], readouts: [], effect_policy: "forbid",
    }));
  } else {
    await action(`Investigation branch settled as ${disposition}.`, () => workspaceCommand({
      operation: "settle-branch", branch_id: branch, disposition,
      result: parseJson(form.get("result"), "Branch result"),
      actual_cost: parseJson(form.get("actual_cost"), "Actual cost"),
      successor_refs: [],
    }));
  }
});

$("#compare-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await action("Branch comparison recorded.", () => workspaceCommand({
    operation: "compare",
    comparison_id: String(form.get("comparison_id")).trim(),
    branch_ids: csv(form.get("branch_ids")),
    shared_conditions: parseJson(form.get("shared_conditions"), "Shared conditions"),
    differences: parseJson(form.get("differences"), "Differences"),
    interpretation: parseJson(form.get("interpretation"), "Interpretation"),
    scope: "within-program",
  }));
});

$("#retain-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await action("Reusable method retained in the field workspace.", () => workspaceCommand({
    operation: "retain",
    retention_id: String(form.get("retention_id")).trim(),
    object_refs: csv(form.get("object_refs")),
    comparison_refs: csv(form.get("comparison_refs")),
    applicability: parseJson(form.get("applicability"), "Applicability"),
    exceptions: parseJson(form.get("exceptions"), "Exceptions"),
  }));
});

$("#admit-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  await action("Typed record revision admitted.", () => workspaceCommand({
    operation: "admit-record",
    record: parseJson(form.get("record"), "Record"),
    visibility: String(form.get("visibility")),
    principals: csv(form.get("principals")),
    principal: state.workspace?.principal || state.entityId,
    origin: {kind: "research-workspace-client"},
  }));
});

$("#computation-form [name=language]").addEventListener("change", (event) => {
  const source = $("#computation-form [name=source]");
  if (event.target.value === "model") {
    source.placeholder = '{"schema":"cassifi.model-program.v1", ...}';
  } else {
    source.placeholder = "total = sum(range(11))\nprint(total)";
  }
});

$("#computation-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const formElement = event.currentTarget;
  const form = new FormData(formElement);
  const language = String(form.get("language"));
  const id = String(form.get("computation_id")).trim();
  const sourceRaw = String(form.get("source"));
  const sourceReference = language === "python"
    ? await inlineText(`${id}.py`, sourceRaw)
    : await inlineJson(`${id}.json`, parseJson(sourceRaw, "Model graph"));
  const backend = String(form.get("backend"));
  const proposal = {
    language,
    profile: parseJson(form.get("profile"), "Profile"),
    source_reference: sourceReference,
    input_references: {},
    limits: parseJson(form.get("limits"), "Limits"),
    capability_requirements: csv(form.get("capabilities")),
    backend_policy: {
      preferred: backend,
      allowed: [...new Set([backend, "logical-cpu"])],
      required: backend !== "logical-cpu",
    },
    payload: parseJson(form.get("payload"), "Payload"),
  };
  await action("Computation admitted to the resident swarm.", async () => {
    const result = await api(`/v1/programs/${encodeURIComponent(state.programId)}/computations`, {method: "POST", body: {
      request_id: requestId("propose-computation"),
      computation_id: id,
      expected_owner_state_sha256: state.ownerSha,
      proposal,
      observed_at: now(),
    }});
    updateOwner(result);
    formElement.reset();
    $("#computation-form [name=profile]").value = '{"steps":0}';
    $("#computation-form [name=limits]").value = "{}";
    $("#computation-form [name=payload]").value = "{}";
    return result;
  });
});

$("#refresh-computations").addEventListener("click", () => action("Resident computations refreshed.", loadComputations, {refresh: false}));
$("#close-inspector").addEventListener("click", () => $("#computation-inspector").classList.add("hidden"));

$("#computation-list").addEventListener("click", async (event) => {
  const card = event.target.closest("[data-computation-id]");
  if (!card) return;
  const id = card.dataset.computationId;
  const computationAction = event.target.closest("[data-computation-action]")?.dataset.computationAction;
  if (computationAction) {
    if (computationAction === "inspect") {
      await action(`Inspected ${id}.`, () => inspectComputation(id), {refresh: false});
      return;
    }
    const argumentsByAction = {
      step: {steps: 1}, run: {quantum: 64, max_groups: 1024}, optimize: {kind: "constant-fold", budget: 64},
      pause: {}, resume: {}, cancel: {reason: "cancelled from research workspace"},
    };
    await action(`${computationAction} applied to ${id}.`, () => controlComputation(id, computationAction, argumentsByAction[computationAction]));
    return;
  }
  const branchAction = event.target.closest("[data-branch-action]")?.dataset.branchAction;
  if (!branchAction) return;
  const branchId = $("[data-branch-id]", card).value.trim();
  const base = $("[data-branch-base]", card).value.trim();
  if (!branchId) { toast("Name the branch before changing it.", "warn"); return; }
  const args = branchAction === "begin"
    ? {assumptions: [], effect_policy: "forbid"}
    : branchAction === "commit"
      ? {expected_base_sha256: base, require_no_reference_escape: true}
      : {};
  if (branchAction === "commit" && !base) { toast("Commit requires the exact base SHA returned when the branch began.", "warn"); return; }
  const result = await action(`${branchAction} applied to branch ${branchId}.`, () => branchComputation(id, branchId, branchAction, args));
  if (branchAction === "begin" && result) {
    const candidate = result?.result?.result?.base_state_sha256 || result?.result?.base_state_sha256 || result?.result?.result?.base_sha256;
    if (candidate) $("[data-branch-base]", card).value = candidate;
  }
});

$("#events-reconnect").addEventListener("click", () => { startEvents(); toast(`Reconnected after durable cursor ${state.eventCursor}.`); });
$("#events-clear").addEventListener("click", () => { state.events = []; renderEvents(); });

window.addEventListener("beforeunload", () => {
  stopEvents();
  stopSurfacePolling();
  clearTimeout(state.surface.grantTimer);
  if (state.surface.frameUrl) URL.revokeObjectURL(state.surface.frameUrl);
});
renderEvents();
$("#field-viewer-link").addEventListener("click", () => {
  $("#embodied-field-view").scrollIntoView({behavior: "smooth", block: "start"});
});
$("#embodied-field-refresh").addEventListener("click", () => void refreshEmbodiedField());
$("#embodied-field-freeze").addEventListener("click", toggleEmbodiedFreeze);
$("#embodied-field-capture").addEventListener("click", captureEmbodiedView);
$("#embodied-region-select").addEventListener("change", (event) => chooseEmbodiedRegion(event.currentTarget.value));
$("#embodied-exchange-meaning-select").addEventListener("change", (event) => {
  state.embodiedField.selectedExchangeMeaningKey = event.currentTarget.value;
  renderEmbodiedField();
});
$("#embodied-regions").addEventListener("click", (event) => {
  const button = event.target.closest("[data-embodied-region-key]");
  if (button) chooseEmbodiedRegion(button.dataset.embodiedRegionKey);
});
$("#embodied-map").addEventListener("click", (event) => {
  const point = event.target.closest("[data-field-map-key]");
  if (point) chooseEmbodiedRegion(point.dataset.fieldMapKey);
});
$("#embodied-map").addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  const point = event.target.closest("[data-field-map-key]");
  if (!point) return;
  event.preventDefault();
  chooseEmbodiedRegion(point.dataset.fieldMapKey);
});
$("#embodied-zoom-in").addEventListener("click", () => {
  state.embodiedField.zoom = Math.min(8, state.embodiedField.zoom * 1.5);
  renderEmbodiedField();
});
$("#embodied-zoom-out").addEventListener("click", () => {
  state.embodiedField.zoom = Math.max(.5, state.embodiedField.zoom / 1.5);
  renderEmbodiedField();
});
$("#embodied-zoom-reset").addEventListener("click", () => {
  state.embodiedField.zoom = 1;
  renderEmbodiedField();
});
$("#embodied-replay-show").addEventListener("click", () => showEmbodiedReplay($("#embodied-replay-select").value));
$("#embodied-replay-previous").addEventListener("click", () => stepEmbodiedReplay(-1));
$("#embodied-replay-next").addEventListener("click", () => stepEmbodiedReplay(1));
$("#embodied-compare-run").addEventListener("click", compareEmbodiedSnapshots);
$("#embodied-compare-a").addEventListener("change", renderEmbodiedCaptureControls);
$("#embodied-compare-b").addEventListener("change", renderEmbodiedCaptureControls);
