"use strict";

const API_ROOT = "/v1/companion";
const PRESENTATION_TTL_MS = 60_000;
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

const state = {
  connected: false,
  connectionPending: false,
  requestPending: false,
  closing: false,
  sessionStarted: false,
  showInvitation: false,
  mode: "watch",
  status: null,
  sources: [],
  selectedKeys: new Set(),
  previewUrls: new Map(),
  currentFrame: null,
  pinned: null,
  annotation: null,
  frameTimer: null,
  frameExpiryTimer: null,
  pinExpiryTimer: null,
  refreshPending: false,
  controller: new AbortController(),
  lastResponse: null,
  dismissedSuggestions: new Set(),
  toastTimer: null,
  embodied: {
    latest: null,
    receivedAt: null,
    error: null,
    requestPending: false,
    visible: false,
    observer: null,
    timer: null,
    ageTimer: null,
    captures: [],
    frozenSnapshot: null,
    replayIndex: null,
    replayTimer: null,
    replayPlaying: false,
    palette: "accessible",
    reduceMotion: Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches),
    observations: [],
    lastObservation: null,
    selectedRegion: "",
    transitions: [],
  },
};
const el = {
  connectForm: $("#connect-form"),
  connectButton: $("#connect-form button[type=submit]"),
  connectionIndicator: $("#connection-indicator"),
  connectionLabel: $("#connection-label"),
  connectionMessage: $("#connection-message"),
  disconnect: $("#disconnect-button"),
  refreshSources: $("#refresh-sources"),
  sourcesMessage: $("#sources-message"),
  sourceGrid: $("#source-grid"),
  purpose: $("#session-purpose"),
  consent: $("#consent-check"),
  agreementScope: $("#agreement-scope"),
  agreementVisual: $("#agreement-visual"),
  agreementProcessing: $("#agreement-processing"),
  agreementRetention: $("#agreement-retention"),
  startButton: $("#start-session"),
  startNote: $("#start-note"),
  invitation: $("#invitation-section"),
  session: $("#session-section"),
  sessionState: $("#session-state"),
  sessionTitle: $("#session-title"),
  sessionSource: $("#session-source"),
  sessionAlert: $("#session-alert"),
  modeToggle: $("#mode-toggle"),
  pauseResume: $("#pause-resume"),
  finish: $("#finish-session"),
  captureAge: $("#capture-age"),
  interpretationAge: $("#interpretation-age"),
  capabilityNote: $("#capability-note"),
  liveFrame: $("#live-frame"),
  liveFrameEmpty: $("#live-frame-empty"),
  liveFrameLabel: $("#live-frame-label"),
  liveSourceLabel: $("#live-source-label"),
  pinMoment: $("#pin-moment"),
  momentPanel: $("#moment-panel"),
  closeMoment: $("#close-moment"),
  pinnedImage: $("#pinned-image"),
  pinnedStage: $("#pinned-stage"),
  pinMetadata: $("#pin-metadata"),
  annotationOverlay: $("#annotation-overlay"),
  pointMark: $("#annotation-point"),
  regionMark: $("#annotation-region"),
  annotationHint: $("#annotation-hint"),
  annotationControls: $(".moment-tools"),
  coordX: $("#coord-x"),
  coordY: $("#coord-y"),
  coordWidth: $("#coord-width"),
  coordHeight: $("#coord-height"),
  momentKind: $("#moment-kind"),
  momentInstruction: $("#moment-instruction"),
  methodDetails: $("#method-details"),
  methodPurpose: $("#method-purpose"),
  methodConditions: $("#method-conditions"),
  methodSteps: $("#method-steps"),
  methodParameters: $("#method-parameters"),
  methodExpected: $("#method-expected"),
  methodStop: $("#method-stop"),
  methodRecovery: $("#method-recovery"),
  sendMoment: $("#send-moment"),
  momentMessage: $("#moment-message"),
  lessons: $("#lessons-list"),
  lessonCount: $("#lesson-count"),
  questions: $("#questions-list"),
  questionCount: $("#question-count"),
  suggestions: $("#suggestions-list"),
  suggestionCount: $("#suggestion-count"),
  suggestionModeNote: $("#suggestion-mode-note"),
  discardRecent: $("#discard-recent"),
  stopProcessing: $("#stop-processing"),
  detailsBindings: $("#details-bindings"),
  detailsPublication: $("#details-publication"),
  detailsProcessing: $("#details-processing"),
  detailsRetention: $("#details-retention"),
  detailsResponse: $("#details-response"),
  advancedCorrections: $("#advanced-corrections"),
  dialog: $("#action-dialog"),
  dialogTitle: $("#dialog-title"),
  dialogContent: $("#dialog-content"),
  dialogActions: $("#dialog-actions"),
  toastRegion: $("#toast-region"),
  embodiedState: $("#embodied-state"),
  embodiedRefresh: $("#embodied-refresh"),
  embodiedCapture: $("#embodied-capture"),
  embodiedFreeze: $("#embodied-freeze"),
  embodiedPalette: $("#embodied-palette"),
  embodiedReducedMotion: $("#embodied-reduced-motion"),
  embodiedMessage: $("#embodied-message"),
  embodiedActivityCount: $("#embodied-activity-count"),
  embodiedActivityNote: $("#embodied-activity-note"),
  embodiedActivityTrace: $("#embodied-activity-trace"),
  embodiedTransitions: $("#embodied-transitions"),
  embodiedGeneration: $("#embodied-generation"),
  embodiedHash: $("#embodied-hash"),
  embodiedLayout: $("#embodied-layout"),
  embodiedCapturedAt: $("#embodied-captured-at"),
  embodiedAge: $("#embodied-age"),
  embodiedFieldTime: $("#embodied-field-time"),
  embodiedCoverage: $("#embodied-coverage"),
  embodiedRegionCount: $("#embodied-region-count"),
  embodiedProjectionNote: $("#embodied-projection-note"),
  embodiedMap: $("#embodied-map"),
  embodiedRegionList: $("#embodied-region-list"),
  embodiedRegionSelect: $("#embodied-region-select"),
  embodiedRegionInspection: $("#embodied-region-inspection"),
  embodiedRoles: $("#embodied-roles"),
  embodiedOrientation: $("#embodied-orientation"),
  embodiedWorkCount: $("#embodied-work-count"),
  embodiedWorkCoverage: $("#embodied-work-coverage"),
  embodiedTopologyNote: $("#embodied-topology-note"),
  embodiedTopology: $("#embodied-topology"),
  embodiedOrganization: $("#embodied-organization"),
  embodiedTimeline: $("#embodied-timeline"),
  embodiedPrevious: $("#embodied-previous"),
  embodiedPlay: $("#embodied-play"),
  embodiedNext: $("#embodied-next"),
  embodiedReplayStatus: $("#embodied-replay-status"),
  embodiedExchange: $("#embodied-exchange"),
  embodiedSemanticsCoverage: $("#embodied-semantics-coverage"),
  embodiedSemantics: $("#embodied-semantics"),
  embodiedMeasurements: $("#embodied-measurements"),
  embodiedCompareBefore: $("#embodied-compare-before"),
  embodiedCompareAfter: $("#embodied-compare-after"),
  embodiedCompare: $("#embodied-compare"),
  embodiedComparison: $("#embodied-comparison"),
  embodiedPayload: $("#embodied-payload"),
};

const SESSION_STATES = new Set([
  "watching", "observing", "active", "capturing", "catching_up", "waiting_for_window",
  "waiting_for_resources", "pausing", "paused", "window_unavailable", "connection_lost",
  "finishing", "processing", "stopping", "unknown_effect",
]);
const COMPLETED_STATES = new Set(["finished", "complete", "completed", "stopped", "expired"]);
const IDLE_STATES = new Set(["idle", "ready"]);
const RETENTION_UNKNOWN = /^(unknown|unavailable|not reported|none|n\/a)$/i;

function text(value, fallback = "", limit = 500) {
  if (value === null || value === undefined) return fallback;
  let result;
  if (typeof value === "string") result = value;
  else if (typeof value === "number" || typeof value === "boolean") result = String(value);
  else {
    try { result = JSON.stringify(value); } catch { result = fallback; }
  }
  result = result.trim();
  if (!result) return fallback;
  return result.length > limit ? `${result.slice(0, limit - 1)}…` : result;
}

function meaningful(value) {
  if (typeof value === "string") return value.trim().length > 0 && !RETENTION_UNKNOWN.test(value.trim());
  if (typeof value === "number" || typeof value === "boolean") return true;
  if (Array.isArray(value)) return value.length > 0;
  if (value && typeof value === "object") return Object.values(value).some(meaningful);
  return false;
}

function readableSummary(value, fallback) {
  if (typeof value === "string") return text(value, fallback, 1200);
  if (Array.isArray(value)) return value.length ? value.map((part) => text(part, "", 240)).filter(Boolean).join(" · ") : fallback;
  if (!value || typeof value !== "object") return fallback;
  const preferred = ["summary", "message", "description", "scope", "policy", "location", "processing_location", "label", "text", "retention_summary"];
  const parts = [];
  for (const key of preferred) {
    const candidate = value[key];
    if (meaningful(candidate)) {
      const candidateText = text(candidate, "", 420);
      if (candidateText && !parts.includes(candidateText)) parts.push(candidateText);
    }
  }
  if (parts.length) return parts.join(" · ");
  const keys = Object.keys(value);
  return keys.length ? "Details are available in the session details below." : fallback;
}

function pretty(value) {
  if (value === null || value === undefined) return "Not available.";
  try {
    const result = JSON.stringify(value, null, 2);
    return result === undefined ? "Not available." : result.slice(0, 12000);
  } catch {
    return text(value, "Not available.", 12000);
  }
}

function make(tag, className = "", content = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== "") node.textContent = content;
  return node;
}

function scalarId(value) {
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

function statusKey(status = state.status) {
  return text(status?.state, "", 100).toLowerCase().replace(/[\s-]+/g, "_");
}

function hasSession() {
  if (state.showInvitation) return false;
  const key = statusKey();
  return state.sessionStarted || SESSION_STATES.has(key) || COMPLETED_STATES.has(key);
}

function isSessionActive() {
  if (state.showInvitation) return false;
  const key = statusKey();
  return SESSION_STATES.has(key) || (state.sessionStarted && !COMPLETED_STATES.has(key) && !IDLE_STATES.has(key));
}

function isSessionPaused() {
  return statusKey() === "paused";
}

function isSessionComplete() {
  return COMPLETED_STATES.has(statusKey());
}

function setInlineMessage(node, message, tone = "") {
  node.textContent = message;
  if (tone) node.dataset.tone = tone;
  else delete node.dataset.tone;
}

function connectionLabel(label, className = "") {
  el.connectionLabel.textContent = label;
  el.connectionIndicator.classList.toggle("connected", className === "connected");
  el.connectionIndicator.classList.toggle("failed", className === "failed");
  el.disconnect.classList.toggle("hidden", !state.connected || isSessionActive());
}

function revokeUrl(url) {
  if (url && url.startsWith("blob:")) URL.revokeObjectURL(url);
}

function revokeAllPreviews() {
  for (const url of state.previewUrls.values()) revokeUrl(url);
  state.previewUrls.clear();
}

function revokeCurrentFrame() {
  clearTimeout(state.frameExpiryTimer);
  state.frameExpiryTimer = null;
  if (state.currentFrame?.url) revokeUrl(state.currentFrame.url);
  state.currentFrame = null;
  el.liveFrame.removeAttribute("src");
  el.liveFrame.classList.add("hidden");
  el.liveFrameEmpty.classList.remove("hidden");
  el.liveFrameLabel.classList.add("hidden");
  el.pinMoment.disabled = true;
}

function revokePinned() {
  clearTimeout(state.pinExpiryTimer);
  state.pinExpiryTimer = null;
  if (state.pinned?.url) revokeUrl(state.pinned.url);
  state.pinned = null;
  state.annotation = null;
  el.pinnedImage.removeAttribute("src");
  el.momentPanel.classList.add("hidden");
  el.pointMark.hidden = true;
  el.regionMark.hidden = true;
}

async function request(path, options = {}) {
  if (state.closing) throw new Error("The companion page is closing.");
  const headers = new Headers(options.headers || {});
  headers.set("accept", options.accept || "application/json");
  if (options.body !== undefined) headers.set("content-type", "application/json; charset=utf-8");
  let response;
  try {
    response = await fetch(path, {
      method: options.method || "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      credentials: "omit",
      cache: "no-store",
      redirect: "error",
      keepalive: Boolean(options.keepalive),
      signal: state.controller.signal,
    });
  } catch (error) {
    if (state.closing || error?.name === "AbortError") throw new Error("The companion connection ended.");
    throw new Error("Could not reach the Cassi entity. Check that it is running and try again.");
  }
  if (!response.ok) {
    let detail = "";
    let body = null;
    try {
      body = await response.json();
      detail = text(body?.error || body?.message, "", 300);
    } catch {
      try { detail = text(await response.text(), "", 300); } catch { /* No response detail. */ }
    }
    const error = new Error(detail || `The entity returned HTTP ${response.status}.`);
    error.status = response.status;
    error.kind = body?.kind;
    error.details = body?.details;
    throw error;
  }
  return response;
}
 
async function requestJson(path, options = {}) {
  const response = await request(path, { ...options, accept: "application/json" });
  try { return await response.json(); }
  catch { throw new Error("The entity returned a response that was not readable JSON."); }
}
 
async function requestPng(path) {
  const response = await request(path, { accept: "image/png" });
  const contentType = (response.headers.get("content-type") || "").split(";")[0].trim().toLowerCase();
  if (contentType !== "image/png") throw new Error("The entity did not return a PNG image.");
  const blob = await response.blob();
  if (!blob.size) throw new Error("The entity returned an empty image.");
  return blob;
}


function resetConnection() {
  const active = isSessionActive();
  state.connected = false;
  state.connectionPending = false;
  el.connectButton.disabled = false;
  el.connectButton.textContent = "Connect";
  revokeAllPreviews();
  revokeCurrentFrame();
  revokePinned();
  clearFrameTimer();
  if (active) {
    state.status = { ...(state.status || {}), state: "connection_lost", message: "The companion cannot confirm current collection status. Reconnect and inspect the entity's stop state." };
    state.showInvitation = false;
  } else {
    state.status = null;
    state.sessionStarted = false;
    state.showInvitation = true;
    el.purpose.value = "";
  }
  connectionLabel("Not connected");
  el.connectionMessage.textContent = "Disconnected from the local entity.";
  el.refreshSources.disabled = true;
  el.sourcesMessage.textContent = "Connect to discover available desktop sources.";
  state.sources = [];
  state.selectedKeys.clear();
  state.dismissedSuggestions.clear();
  el.consent.checked = false;
  renderSources();
  updateAgreement();
  renderSession();
}

function sourceKey(source) {
  return JSON.stringify([source?.backend_id ?? null, source?.source_id ?? null, source?.source_instance ?? null]);
}

function isSourceSelectable(source) {
  return Boolean(source && source.available === true && scalarId(source.backend_id).trim() && scalarId(source.source_id).trim() && scalarId(source.source_instance).trim());
}

function getSelectedSources() {
  return state.sources.filter((source) => state.selectedKeys.has(sourceKey(source)) && isSourceSelectable(source));
}

function formatKind(source) {
  return text(source?.kind, "Desktop source", 80).replace(/[_-]+/g, " ");
}

function renderSources() {
  el.sourceGrid.replaceChildren();
  if (!state.connected) return;
  if (!state.sources.length) {
    const empty = make("div", "empty-sources", "No desktop sources are available right now.");
    el.sourceGrid.append(empty);
    return;
  }
  for (const source of state.sources) {
    const key = sourceKey(source);
    const card = make("article", "source-card");
    card.classList.toggle("selected", state.selectedKeys.has(key));
    card.classList.toggle("unavailable", !isSourceSelectable(source));

    const preview = make("div", "source-preview");
    preview.setAttribute("aria-label", `Preview for ${text(source.label, "desktop source", 120)}`);
    const kind = make("span", "source-kind", formatKind(source));
    preview.append(kind);
    const objectUrl = state.previewUrls.get(key);
    if (objectUrl) {
      const image = make("img");
      image.src = objectUrl;
      image.alt = `Read-only preview of ${text(source.label, "desktop source", 120)}`;
      preview.append(image);
      if (source.available !== false) {
        const refresh = make("button", "button button-secondary preview-refresh", "Refresh preview");
        refresh.type = "button";
        refresh.dataset.action = "load-preview";
        refresh.dataset.sourceKey = key;
        preview.append(refresh);
      }
    } else {
      const placeholder = make("div", "preview-placeholder");
      placeholder.append(make("strong", "", source.available === false ? "Source unavailable" : source.previewError ? "Preview unavailable" : "Private source preview"));
      placeholder.append(document.createTextNode(source.available === false ? "Choose another source or refresh the list." : source.previewError ? text(source.previewError, "Preview unavailable.", 220) : "Load a read-only preview here only when you choose to inspect this source."));
      preview.append(placeholder);
      if (source.available !== false) {
        const load = make("button", "button button-secondary preview-refresh", "Load preview");
        load.type = "button";
        load.dataset.action = "load-preview";
        load.dataset.sourceKey = key;
        preview.append(load);
      }
    }

    const content = make("div", "source-card-content");
    const label = make("label", "source-choice");
    const checkbox = make("input");
    checkbox.type = "checkbox";
    checkbox.checked = state.selectedKeys.has(key);
    checkbox.disabled = !isSourceSelectable(source);
    checkbox.dataset.sourceKey = key;
    checkbox.setAttribute("aria-label", `Include ${text(source.label, "desktop source", 120)} in this observation session`);
    const copy = make("span");
    copy.append(make("strong", "", text(source.label, "Unlabelled source", 180)));
    copy.append(make("small", "", source.available === false ? "Unavailable" : isSourceSelectable(source) ? "Explicit selection required" : "Source identity is not available"));
    label.append(checkbox, copy);
    content.append(label);

    const chips = make("div", "source-meta");
    const modalities = Array.isArray(source.modalities) ? source.modalities : [];
    for (const modality of modalities.slice(0, 4)) chips.append(make("span", "meta-chip", text(modality, "", 50)));
    if (source.source_instance !== undefined && source.source_instance !== null) {
      chips.append(make("span", "meta-chip", `Source version · ${text(source.source_instance, "unknown", 46)}`));
    } else {
      chips.append(make("span", "meta-chip uncertain", "Identity not confirmed"));
    }
    content.append(chips);
    card.append(preview, content);
    el.sourceGrid.append(card);
  }
}

function visualDisclosure(status = state.status) {
  if (!status || !Object.prototype.hasOwnProperty.call(status, "visual_capability")) return "The connected entity has not reported visual capability.";
  const capability = status.visual_capability;
  if (capability === false || capability === null || capability === "unavailable" || capability === "none") return "Image understanding is unavailable; local selected-window previews may still be available.";
  if (typeof capability === "string") return capability.trim() || "Visual capability was reported without details.";
  if (typeof capability === "object") {
    if (capability.status === "supported") return "The resident Qwen brain interprets approved-window images inside Cassi's native, owner-field-coupled graph. Check each description before treating it as a lesson.";
    if (capability.status === "unsupported" || capability.status === "unavailable" || capability.available === false) {
      const reason = capability.reason || capability.reason_code;
      return `Image understanding is unavailable${reason ? `: ${text(reason, "", 220)}` : ""}. Approved-window previews stay local to this companion.`;
    }
    const summary = readableSummary(capability, "");
    if (summary) return summary;
    return "Visual capability is reported in Details.";
  }
  if (capability === true) return "Visual capability is available according to the connected entity.";
  return "Visual capability was reported without details.";
}

function processingDisclosure(status = state.status) {
  if (!status) return "Not reported by the connected entity.";
  const processing = status.processing;
  if (processing && typeof processing === "object" && !Array.isArray(processing)) {
    const parts = [];
    const processingState = text(processing.status, "", 80).toLowerCase();
    if (processingState === "supported") parts.push("Processing capability is supported by the entity.");
    else if (processingState === "unavailable") parts.push("Processing is unavailable.");
    else if (processingState === "unknown") parts.push("Processing capability is not verified.");
    if (processing.local === true) parts.push("Local processing: verified.");
    else if (processing.local === false) parts.push("Local processing: false.");
    else parts.push("Local processing: not verified.");
    let location;
    if (Object.prototype.hasOwnProperty.call(processing, "location")) location = processing.location;
    else if (Object.prototype.hasOwnProperty.call(processing, "processing_location")) location = processing.processing_location;
    else if (Object.prototype.hasOwnProperty.call(status, "processing_location")) location = status.processing_location;
    if (location !== undefined) parts.push(`Processing location: ${text(location, "not reported", 420)}.`);
    if (Object.prototype.hasOwnProperty.call(processing, "visual_inference")) {
      parts.push(`Visual inference: ${text(processing.visual_inference, "not reported", 600)}.`);
    }
    if (Object.prototype.hasOwnProperty.call(processing, "reason")) {
      parts.push(`Details: ${text(processing.reason, "not reported", 420)}.`);
    }
    if (parts.length) return parts.join(" ");
    const summary = readableSummary(processing, "");
    if (summary && summary !== "Details are available in the session details below.") return summary;
  }
  for (const key of ["processing_location", "inference_location"]) {
    const value = status[key];
    if (!Object.prototype.hasOwnProperty.call(status, key) || !meaningful(value)) continue;
    if (typeof value === "string" || typeof value === "number") return text(value, "Not reported by the connected entity.", 600);
  }
  return "Not reported by the connected entity.";
}

function hasProcessingDisclosure(status = state.status) {
  if (!status) return false;
  const processing = status.processing;
  if (processing && typeof processing === "object" && !Array.isArray(processing)) {
    const processingState = text(processing.status, "", 80).toLowerCase();
    if (processingState === "unknown" || processingState === "unavailable") return false;
    if (processingState === "supported") {
      const location = processing.location ?? processing.processing_location ?? status.processing_location;
      return processing.local === true || processing.remote === true || meaningful(location);
    }
  }
  for (const key of ["processing_location", "processing", "inference_location"]) {
    const value = status[key];
    if (!Object.prototype.hasOwnProperty.call(status, key) || !meaningful(value)) continue;
    if (typeof value === "string" || typeof value === "number") return true;
    if (value && typeof value === "object" && (value.local === true || value.remote === true || ["location", "processing_location", "summary", "description"].some((name) => meaningful(value[name])))) return true;
  }
}

function hasVerifiedLocalProcessing(status = state.status) {
  const processing = status?.processing;
  return Boolean(processing && typeof processing === "object" && !Array.isArray(processing) && processing.local === true);
}

function hasRetentionDisclosure(status = state.status) {
  if (meaningful(status?.retention_summary)) return true;
  const retention = status?.retention;
  if (typeof retention === "string") return meaningful(retention);
  if (Array.isArray(retention)) return retention.some(meaningful);
  if (!retention || typeof retention !== "object") return false;
  return ["summary", "retention_summary", "description", "scope", "policy", "message"].some((key) => meaningful(retention[key]));
}

function retentionDisclosure(status = state.status) {
  if (meaningful(status?.retention_summary)) return text(status.retention_summary, "The entity has not supplied a readable retention summary.", 1200);
  if (!hasRetentionDisclosure(status)) return "The entity has not supplied a readable retention summary.";
  return readableSummary(status.retention, "The entity has not supplied a readable retention summary.");
}

function resetConsent() {
  el.consent.checked = false;
  updateAgreement();
}

function updateAgreement() {
  const selected = getSelectedSources();
  const mode = $("input[name=session-mode]:checked")?.value || "watch";
  state.mode = mode;
  el.agreementScope.textContent = selected.length ? selected.map((source) => text(source.label, "Desktop source", 100)).join(" · ") : "No windows selected.";
  el.agreementVisual.textContent = visualDisclosure();
  el.agreementProcessing.textContent = processingDisclosure();
  el.agreementRetention.textContent = retentionDisclosure();
  const status = state.status;
  const processingKnown = hasProcessingDisclosure(status);
  const visualKnown = Boolean(status && Object.prototype.hasOwnProperty.call(status, "visual_capability"));
  const retentionKnown = hasRetentionDisclosure(status);
  const safeSources = selected.length > 0 && selected.every(isSourceSelectable);
  const disclosureReady = processingKnown && visualKnown && retentionKnown;
  const canStart = state.connected && !state.connectionPending && safeSources && disclosureReady && hasVerifiedLocalProcessing(status) && el.consent.checked && !state.requestPending && !state.sessionStarted;
  el.startButton.disabled = !canStart;
  el.startButton.textContent = mode === "suggest" ? "Start in Suggest mode" : "Watch with me";
  if (!state.connected) el.startNote.textContent = "Connect to your entity to review the current scope and retention summary.";
  else if (!safeSources) el.startNote.textContent = "Select at least one available source with a confirmed source identity.";
  else if (!disclosureReady) el.startNote.textContent = "Starting stays unavailable until the entity reports processing, visual capability, and retention details.";
  else if (!hasVerifiedLocalProcessing(status)) el.startNote.textContent = "Starting is unavailable until the entity verifies local processing. Location, visual inference, and the reported reason are shown above.";
  else if (!el.consent.checked) el.startNote.textContent = "Review the summary above, then choose to begin.";
  else el.startNote.textContent = "Only the selected source identities are included in this request.";
}

function setSelected(key, selected, checkbox) {
  if (selected) state.selectedKeys.add(key);
  else {
    state.selectedKeys.delete(key);
    revokeUrl(state.previewUrls.get(key));
    state.previewUrls.delete(key);
    renderSources();
  }
  checkbox?.closest(".source-card")?.classList.toggle("selected", selected);
  resetConsent();
}

async function connect(event) {
  event.preventDefault();
  if (state.connected || state.connectionPending) return;
  state.connectionPending = true;
  resetConsent();
  el.connectButton.disabled = true;
  el.connectButton.textContent = "Connecting…";
  connectionLabel("Connecting…");
  el.connectionMessage.textContent = "Checking the local entity and loading the source list.";
  try {
    const [status, sourceResult] = await Promise.all([
      requestJson(API_ROOT),
      requestJson(`${API_ROOT}/sources`),
    ]);
    state.connected = true;
    state.connectionPending = false;
    applyStatus(status);
    state.sources = Array.isArray(sourceResult?.sources) ? sourceResult.sources : [];
    const availableKeys = new Set(state.sources.map(sourceKey));
    state.selectedKeys = new Set(Array.from(state.selectedKeys).filter((key) => availableKeys.has(key)));
    const radio = $(`input[name="session-mode"][value="${state.mode}"]`);
    if (radio) radio.checked = true;
    connectionLabel("Connected", "connected");
    el.connectionMessage.textContent = "Connected to the local entity. No API credentials are used or stored.";
    el.refreshSources.disabled = false;
    setInlineMessage(el.sourcesMessage, state.sources.length ? "Choose exact source windows. Previews are read-only and do not start a session." : "The entity returned no desktop sources.", state.sources.length ? "" : "warn");
    renderSources();
    updateAgreement();
    renderSession();
    renderDetails();
    if (isSessionActive()) {
      await refreshSession();
      startFrameTimer();
    }
  } catch (error) {
    state.connectionPending = false;
    state.connected = false;
    connectionLabel("Connection failed", "failed");
    el.connectionMessage.textContent = error.message;
    setInlineMessage(el.sourcesMessage, "The source list could not be loaded. Check the entity connection and try again.", "error");
    revokeAllPreviews();
    renderSources();
  } finally {
    el.connectButton.disabled = state.connected;
    el.connectButton.textContent = state.connected ? "Connected" : "Connect";
    updateAgreement();
  }
}

async function refreshSources() {
  if (!state.connected || state.requestPending) return;
  el.refreshSources.disabled = true;
  setInlineMessage(el.sourcesMessage, "Refreshing available source identities…");
  try {
    const sourceResult = await requestJson(`${API_ROOT}/sources`);
    const nextSources = Array.isArray(sourceResult?.sources) ? sourceResult.sources : [];
    const nextKeys = new Set(nextSources.map(sourceKey));
    revokeAllPreviews();
    state.selectedKeys = new Set(Array.from(state.selectedKeys).filter((key) => nextKeys.has(key)));
    state.sources = nextSources;
    renderSources();
    resetConsent();
    setInlineMessage(el.sourcesMessage, nextSources.length ? "Source list refreshed. Confirm every selected source again before starting." : "No desktop sources are available right now.", nextSources.length ? "" : "warn");
  } catch (error) {
    setInlineMessage(el.sourcesMessage, error.message, "error");
  } finally {
    el.refreshSources.disabled = !state.connected;
  }
}


async function reloadSourcePreview(key) {
  const source = state.sources.find((candidate) => sourceKey(candidate) === key);
  if (!source || source.available === false || !state.connected) return;
  const button = $$('[data-action="load-preview"]', el.sourceGrid).find((candidate) => candidate.dataset.sourceKey === key);
  if (button) button.disabled = true;
  try {
    const query = new URLSearchParams({ backend_id: String(source.backend_id), source_id: String(source.source_id) });
    const blob = await requestPng(`${API_ROOT}/preview?${query.toString()}`);
    const prior = state.previewUrls.get(key);
    revokeUrl(prior);
    state.previewUrls.set(key, URL.createObjectURL(blob));
  } catch (error) {
    source.previewError = error.message;
    setInlineMessage(el.sourcesMessage, `Preview unavailable for ${text(source.label, "this source", 100)}: ${error.message}`, "warn");
  }
  renderSources();
}

function selectedMode() {
  return $("input[name=session-mode]:checked")?.value === "suggest" ? "suggest" : "watch";
}

async function startSession() {
  if (el.startButton.disabled || state.requestPending) return;
  if (!hasVerifiedLocalProcessing()) {
    setInlineMessage(el.sourcesMessage, "The entity has not verified local processing; no observation session was requested.", "warn");
    updateAgreement();
    return;
  }
  const sources = getSelectedSources().map((source) => ({
    backend_id: source.backend_id,
    source_id: source.source_id,
    source_instance: source.source_instance,
  }));
  if (!sources.length) return;
  state.requestPending = true;
  el.startButton.disabled = true;
  el.startButton.textContent = "Starting…";
  const body = { sources, mode: selectedMode() };
  const purpose = el.purpose.value.trim();
  if (purpose) body.purpose = purpose;
  try {
    const result = await requestJson(`${API_ROOT}/sessions`, { method: "POST", body });
    revokeAllPreviews();
    state.lastResponse = result;
    state.dismissedSuggestions.clear();
    state.sessionStarted = true;
    state.showInvitation = false;
    state.mode = body.mode;
    state.status = { ...(state.status || {}), state: "unknown_effect", frame_available: false, message: "The session request was accepted. Checking the entity's current status." };
    renderSession();
    renderDetails();
    try {
      await loadStatus();
    } catch (statusError) {
      if (statusError.status === 401 || !state.connected || state.closing) {
        showToast(statusError.message, "error");
        return;
      }
      markUnknownEffect("The session request was accepted, but the current status could not be confirmed. Waiting for fresh status before retrying.");
      showToast(statusError.message, "warn");
      return;
    }
    if (!state.showInvitation) el.session.scrollIntoView({ behavior: "smooth", block: "start" });
    if (state.showInvitation) showToast("The entity reports that it is ready. Review the current scope before starting.", "warn");
    else announceResult(result, "Session request received. Reading the entity's current status.");
    if (isSessionActive()) {
      await refreshSession();
      startFrameTimer();
    } else clearFrameTimer();
  } catch (error) {
    if (isAmbiguousFailure(error) && state.connected && !state.closing) {
      markUnknownEffect("The session request may have reached the entity, but its result could not be confirmed. Waiting for fresh status before retrying.");
      showToast(error.message, "warn");
    } else {
      setInlineMessage(el.sourcesMessage, error.message, "error");
      if (state.connected && error.status !== 401 && !state.closing) {
        try { await loadStatus(); } catch { /* Keep the explicit session rejection visible. */ }
      }
    }
  }
  finally {
    state.requestPending = false;
    updateAgreement();
    updateSessionControls();
  }
}

function applyStatus(status) {
  const previousKey = statusKey();
  const nextKey = statusKey(status);
  state.status = status;
  if (status?.frame_available === false) {
    revokeCurrentFrame();
    revokePinned();
  }
  if (!state.showInvitation && (SESSION_STATES.has(nextKey) || COMPLETED_STATES.has(nextKey))) state.sessionStarted = true;
  if (SESSION_STATES.has(nextKey)) {
    state.sessionStarted = true;
    state.showInvitation = false;
  } else if (!state.showInvitation && state.sessionStarted && IDLE_STATES.has(nextKey)) {
    state.sessionStarted = false;
    state.showInvitation = true;
    el.consent.checked = false;
    revokeAllPreviews();
    state.sources = [];
    state.selectedKeys.clear();
    el.refreshSources.disabled = !state.connected;
    setInlineMessage(el.sourcesMessage, "The prior session is no longer active. Refresh source identities and choose again before starting.");
    renderSources();
  }
  if (status?.mode === "watch" || status?.mode === "suggest") state.mode = status.mode;
}

async function loadStatus() {
  const status = await requestJson(API_ROOT);
  applyStatus(status);
  updateAgreement();
  renderSession();
  renderDetails();
  return status;
}

function isAmbiguousFailure(error) {
  if (error?.kind === "surface-wait" && error?.details?.kind === "volatile-frame-stale") return false;
  return !Number.isFinite(Number(error?.status)) || Number(error.status) >= 500;
}

function markUnknownEffect(message) {
  state.sessionStarted = true;
  state.showInvitation = false;
  state.status = { ...(state.status || {}), state: "unknown_effect", frame_available: false, message };
  renderSession();
  renderDetails();
  updateSessionControls();
  startFrameTimer();
}

function bindingForPublication(status) {
  const bindings = Array.isArray(status?.bindings) ? status.bindings : [];
  const provided = status?.publication;
  const publications = Array.isArray(provided) ? provided : provided && typeof provided === "object" ? [provided] : [];
  const candidates = publications.map((publication) => ({
    publication,
    binding: bindings.find((entry) => entry?.binding_id === publication?.binding_id) || null,
  }));
  for (const binding of bindings) {
    const value = binding?.publication;
    const boundPublications = Array.isArray(value) ? value : value && typeof value === "object" ? [value] : [];
    for (const publication of boundPublications) candidates.push({ publication, binding });
  }
  if (!candidates.length) return { publication: null, binding: null };
  const selected = candidates.find(({ publication }) => publication?.is_latest === true)
    || candidates.find(({ publication }) => publication?.visual_available === true)
    || candidates[0];
  const candidate = selected.publication;
  let binding = selected.binding || bindings.find((entry) => entry?.binding_id === candidate?.binding_id) || null;
  if (!binding && bindings.length === 1) binding = bindings[0];
  if (!binding && candidate?.binding_id) binding = { binding_id: candidate.binding_id, source_instance: candidate.source_instance, source_id: candidate.source_id };
  return { publication: candidate, binding };
}

function publicationIdentity(publication, binding) {
  if (!publication || !binding) return "";
  const bindingId = publication.binding_id ?? binding.binding_id;
  const generation = publication.publication_generation ?? publication.generation;
  const sourceEpoch = publication.source_epoch;
  const geometryRevision = publication.geometry_revision;
  const sourceInstance = publication.source_instance ?? binding.source_instance;
  const sourceId = publication.source_id ?? binding.source_id;
  const sampleTimeNs = publication.sample_time_ns;
  const captureId = publication.capture_id;
  if (!captureId || bindingId === undefined || generation === undefined || sourceEpoch === undefined || geometryRevision === undefined) return "";
  return JSON.stringify([bindingId, captureId, generation, sourceEpoch, geometryRevision, sampleTimeNs ?? null, sourceInstance ?? null, sourceId ?? null]);
}

function visualAvailable(status, publication) {
  if (status?.frame_available === false) return false;
  if (publication?.visual_available === false) return false;
  const capability = status?.visual_capability;
  if (capability === false || capability === null || capability === "unavailable" || capability === "none") return false;
  if (capability && typeof capability === "object" && capability.available === false) return false;
  return status?.frame_available === true || publication?.visual_available === true || capability === true || capability?.available === true;
}

function activeSourceLabel(status, binding, publication) {
  return text(status?.source_label, text(binding?.label, text(publication?.source_label, "Selected source", 120), 120), 160);
}

function captureMeta(status, publication, binding) {
  return {
    binding_id: publication?.binding_id ?? binding?.binding_id,
    capture_id: publication?.capture_id,
    publication_generation: publication?.publication_generation ?? publication?.generation,
    source_epoch: publication?.source_epoch,
    geometry_revision: publication?.geometry_revision,
    sample_time_ns: publication?.sample_time_ns,
    source_instance: publication?.source_instance ?? binding?.source_instance,
    source_id: publication?.source_id ?? binding?.source_id,
    backend_id: binding?.backend_id,
    width: publication?.width,
    height: publication?.height,
    capture_age_ms: publication?.capture_age_ms ?? status?.capture_age_ms,
    source_label: activeSourceLabel(status, binding, publication),
    is_latest: publication?.is_latest,
  };
}

function sameCapture(first, second) {
  return Boolean(first && second && first.binding_id === second.binding_id && first.capture_id === second.capture_id && first.publication_generation === second.publication_generation && first.source_epoch === second.source_epoch && first.geometry_revision === second.geometry_revision && first.sample_time_ns === second.sample_time_ns && first.source_instance === second.source_instance && first.source_id === second.source_id);
}

function ageLabel(milliseconds) {
  if (milliseconds === null || milliseconds === undefined || milliseconds === "") return "Not available";
  const age = Number(milliseconds);
  if (!Number.isFinite(age) || age < 0) return "Not available";
  if (age < 1000) return "just now";
  if (age < 60_000) return `${Math.round(age / 1000)} sec ago`;
  if (age < 3_600_000) return `${Math.floor(age / 60_000)} min ${Math.round((age % 60_000) / 1000)} sec ago`;
  return `${Math.floor(age / 3_600_000)} hr ${Math.floor((age % 3_600_000) / 60_000)} min ago`;
}

function niceState(status) {
  const key = statusKey(status);
  const labels = {
    ready: "Ready",
    watching: "Watching",
    observing: "Watching",
    active: "Watching",
    catching_up: "Catching up",
    waiting_for_window: "Waiting for your window",
    waiting_for_resources: "Waiting for resources",
    pausing: "Pausing…",
    paused: "Paused",
    window_unavailable: "Window unavailable",
    connection_lost: "Connection lost",
    finishing: "Finishing this session",
    processing: "Processing this session",
    stopping: "Stopping collection",
    finished: "Finished",
    complete: "Finished",
    completed: "Finished",
    stopped: "Finished",
    expired: "Watching stopped · resume when ready",
    unknown_effect: "I couldn't confirm what happened",
  };
  return labels[key] || (key ? key.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase()) : "Status unavailable");
}

function statusTone(status) {
  const key = statusKey(status);
  if (["paused", "finished", "complete", "completed", "stopped", "ready"].includes(key)) return "";
  if (["window_unavailable", "connection_lost", "unknown_effect", "expired"].includes(key)) return "danger";
  if (["catching_up", "waiting_for_window", "waiting_for_resources", "pausing", "finishing", "processing", "stopping"].includes(key)) return "warn";
  return "";
}

function renderSession() {
  const visible = hasSession();
  el.session.classList.toggle("hidden", !visible);
  el.invitation.classList.toggle("hidden", visible);
  if (!visible) {
    updateAgreement();
    return;
  }
  const status = state.status || {};
  el.sessionState.textContent = niceState(status);
  const tone = statusTone(status);
  if (tone) el.sessionState.dataset.tone = tone;
  else delete el.sessionState.dataset.tone;
  const { publication, binding } = bindingForPublication(status);
  const sourceLabel = activeSourceLabel(status, binding, publication);
  el.sessionTitle.textContent = state.mode === "suggest" ? "Cassi can offer supported suggestions" : "Cassi is watching with you";
  el.sessionSource.textContent = sourceLabel;
  el.captureAge.textContent = ageLabel(status.capture_age_ms ?? publication?.capture_age_ms);
  el.interpretationAge.textContent = ageLabel(status.interpretation_age_ms);
  el.liveSourceLabel.textContent = sourceLabel;
  el.capabilityNote.textContent = visualDisclosure(status);
  renderSessionAlert(status);
  renderLessons(status.lessons);
  renderQuestions(status.questions);
  renderSuggestions(state.mode === "suggest" ? status.suggestions : []);
  updateSessionControls();
  ensureNewSessionButton();
}

function renderSessionAlert(status) {
  const key = statusKey(status);
  const messages = {
    catching_up: "Capture is current while interpretation is behind. Both ages stay visible here.",
    waiting_for_window: "The foreground is outside your selected set. New collection is suspended until an approved source is current.",
    pausing: "The stop fence is requested. Cassi will show Paused only after the entity confirms collection has stopped.",
    paused: "New collection is paused. Existing retained learning has not been removed.",
    window_unavailable: "This source is unavailable. Any last image is historical; choose a source again when you are ready.",
    connection_lost: "The companion cannot confirm current collection status. Reconnect and inspect the entity's stop state.",
    finishing: "Collection is stopping. Already authorized work may still be settling.",
    processing: "Capture has stopped; permitted remaining work is still settling.",
    unknown_effect: "The entity could not confirm the effect. Open Details before choosing what to do next.",
    expired: "The observation lease has expired. Resume only after the source and authority are confirmed again.",
  };
  const message = text(status?.message, messages[key] || "", 500);
  if (message) {
    setInlineMessage(el.sessionAlert, message, statusTone(status) || "");
    el.sessionAlert.classList.remove("hidden");
  } else {
    el.sessionAlert.textContent = "";
    el.sessionAlert.classList.add("hidden");
  }
}

function updateSessionControls() {
  const connected = state.connected;
  const active = isSessionActive();
  const paused = isSessionPaused();
  const complete = isSessionComplete();
  const key = statusKey();
  const uncertain = key === "unknown_effect";
  const settling = ["pausing", "finishing", "processing", "stopping"].includes(key);
  const locked = settling || uncertain;
  el.modeToggle.textContent = `Mode: ${state.mode === "suggest" ? "Suggest" : "Watch"}`;
  el.modeToggle.disabled = !connected || !active || state.requestPending || locked || key === "window_unavailable";
  el.pauseResume.textContent = paused ? "Resume" : "Pause";
  el.pauseResume.disabled = !connected || !active || state.requestPending || locked;
  el.pauseResume.setAttribute("aria-label", paused ? "Resume observation on the selected sources" : "Pause all observation on the selected sources");
  el.finish.disabled = !connected || !active || state.requestPending || complete || locked;
  el.finish.classList.toggle("hidden", complete);
  el.stopProcessing.disabled = !connected || !active || state.requestPending || complete || uncertain;
  el.discardRecent.disabled = !connected || !active || state.requestPending || uncertain || !getUnsavedIntervals(state.status).length;
  const currentPair = bindingForPublication(state.status);
  const latestIdentity = publicationIdentity(currentPair.publication, currentPair.binding);
  const currentMatches = Boolean(state.currentFrame && latestIdentity && state.currentFrame.identity === latestIdentity && currentPair.publication?.is_latest !== false);
  el.pinMoment.disabled = !state.currentFrame || !currentMatches || !active || uncertain || !visualAvailable(state.status, currentPair.publication);
  if (state.currentFrame) {
    const historical = !currentMatches || !active || uncertain || !visualAvailable(state.status, currentPair.publication);
    el.liveFrameLabel.textContent = historical ? "Historical view · collection unavailable" : "Current approved view";
    el.liveFrameLabel.classList.toggle("hidden", !state.currentFrame);
  }
  const newButton = $("#new-session");
  if (newButton) newButton.classList.toggle("hidden", !complete);
  updateMomentEnabled();
}

function ensureNewSessionButton() {
  if ($("#new-session")) return;
  const button = make("button", "button button-quiet hidden", "Choose sources for another session");
  button.type = "button";
  button.id = "new-session";
  button.addEventListener("click", async () => {
    state.sessionStarted = false;
    state.showInvitation = true;
    state.status = null;
    state.mode = "watch";
    el.purpose.value = "";
    revokeCurrentFrame();
    revokePinned();
    clearFrameTimer();
    revokeAllPreviews();
    state.sources = [];
    state.dismissedSuggestions.clear();
    state.selectedKeys.clear();
    el.consent.checked = false;
    const watch = $("input[name=session-mode][value=watch]");
    if (watch) watch.checked = true;
    renderSources();
    renderSession();
    try {
      await loadStatus();
      await refreshSources();
    } catch (error) { showToast(error.message, "warn"); }
    el.invitation.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  $(".session-controls").append(button);
}

async function refreshSession() {
  if (!state.connected || !isSessionActive() || state.refreshPending || state.closing) return;
  state.refreshPending = true;
  try {
    const before = await requestJson(API_ROOT);
    if (document.visibilityState === "hidden" || state.closing) return;
    applyStatus(before);
    renderSession();
    if (!isSessionActive()) {
      clearFrameTimer();
      return;
    }
    const beforePair = bindingForPublication(before);
    const beforeMeta = captureMeta(before, beforePair.publication, beforePair.binding);
    if (!visualAvailable(before, beforePair.publication)) {
      markFrameHistorical("No current visual publication is available for this source.");
      return;
    }
    const identityBefore = publicationIdentity(beforePair.publication, beforePair.binding);
    if (!identityBefore) {
      markFrameHistorical("The entity has not supplied exact publication geometry for the current view.");
      return;
    }
    const blob = await requestPng(`${API_ROOT}/frame`);
    if (document.visibilityState === "hidden" || state.closing) return;
    const after = await requestJson(API_ROOT);
    if (document.visibilityState === "hidden" || state.closing) return;
    applyStatus(after);
    if (!isSessionActive()) clearFrameTimer();
    const afterPair = bindingForPublication(after);
    const afterMeta = captureMeta(after, afterPair.publication, afterPair.binding);
    const identityAfter = publicationIdentity(afterPair.publication, afterPair.binding);
    if (!identityAfter || identityBefore !== identityAfter || !sameCapture(beforeMeta, afterMeta) || !visualAvailable(after, afterPair.publication)) {
      renderSession();
      markFrameHistorical("The source changed while this image was loading. Waiting for an image with a matching publication record.");
      return;
    }
    const age = afterMeta.capture_age_ms;
    if (!Number.isFinite(age) || age < 0 || age >= PRESENTATION_TTL_MS) {
      markFrameHistorical("This image has left the short-lived buffer. Waiting for a fresh view.");
      return;
    }
    revokeCurrentFrame();
    const url = URL.createObjectURL(blob);
    const frame = { blob, url, meta: afterMeta, identity: identityAfter, capturedAt: Date.now(), expiresAt: Date.now() + PRESENTATION_TTL_MS - age };
    state.currentFrame = frame;
    state.frameExpiryTimer = setTimeout(() => {
      if (state.currentFrame !== frame) return;
      revokeCurrentFrame();
      el.liveFrameEmpty.querySelector("p").textContent = "The recent image expired. Waiting for a fresh view.";
    }, Math.max(0, frame.expiresAt - Date.now()));
    el.liveFrame.src = url;
    el.liveFrame.alt = `Current read-only view of ${afterMeta.source_label || "the approved desktop source"}`;
    el.liveFrame.classList.remove("hidden");
    el.liveFrameEmpty.classList.add("hidden");
    el.liveFrameLabel.textContent = "Current approved view";
    el.liveFrameLabel.classList.remove("hidden");
    renderSession();
    updateSessionControls();
  } catch (error) {
    if (error.status === 401 || state.closing) return;
    const message = error.message || "The current view could not be refreshed.";
    markFrameHistorical(message);
    if (state.connected) setInlineMessage(el.sessionAlert, message, "warn");
  } finally {
    state.refreshPending = false;
  }
}

function markFrameHistorical(message) {
  if (state.currentFrame) {
    el.liveFrameLabel.textContent = "Historical view · not a live frame";
    el.liveFrameLabel.classList.remove("hidden");
    el.pinMoment.disabled = true;
  } else {
    el.liveFrame.classList.add("hidden");
    el.liveFrameEmpty.classList.remove("hidden");
    el.liveFrameEmpty.querySelector("p").textContent = message;
    el.pinMoment.disabled = true;
  }
}

function clearFrameTimer() {
  if (state.frameTimer) clearInterval(state.frameTimer);
  state.frameTimer = null;
}

function startFrameTimer() {
  clearFrameTimer();
  if (!state.connected || !isSessionActive() || document.visibilityState === "hidden" || state.closing) return;
  state.frameTimer = setInterval(() => { void refreshSession(); }, 2600);
  void refreshSession();
}

function renderDetails() {
  const status = state.status;
  el.detailsBindings.textContent = pretty(status?.bindings);
  el.detailsPublication.textContent = pretty({ publication: status?.publication, visual_capability: status?.visual_capability });
  const processing = status?.processing;
  const processingDetails = processing && typeof processing === "object"
    ? { status: processing.status, local: processing.local, location: processing.location ?? processing.processing_location ?? status?.processing_location, visual_inference: processing.visual_inference, reason: processing.reason }
    : processing ?? status?.processing_location ?? status?.inference_location;
  el.detailsProcessing.textContent = pretty(processingDetails);
  const retentionSummary = meaningful(status?.retention_summary) ? text(status.retention_summary, "", 1200) : "";
  const retentionDetails = pretty(status?.retention);
  el.detailsRetention.textContent = retentionSummary ? `${retentionSummary}\n\n${retentionDetails}` : retentionDetails;
  el.detailsResponse.textContent = pretty(state.lastResponse);
  renderRetentionActions(status);
}

function renderRetentionActions(status) {
  el.advancedCorrections.replaceChildren();
  const corrections = status?.retention?.correction_controls;
  if (!corrections || typeof corrections !== "object") return;
  for (const [key, value] of Object.entries(corrections)) {
    const item = make("p", "field-note", `${key.replace(/_/g, " ")}: ${text(value, "", 400)}`);
    el.advancedCorrections.append(item);
  }
}

function items(value) {
  if (Array.isArray(value)) return value.filter((item) => item && typeof item === "object");
  if (value && typeof value === "object") return Object.values(value).filter((item) => item && typeof item === "object");
  return [];
}

function firstText(item, keys, fallback, limit = 420) {
  for (const key of keys) {
    const value = item?.[key];
    if (value !== null && value !== undefined && text(value, "", limit)) return text(value, "", limit);
  }
  return fallback;
}

function lessonSupport(lesson) {
  const source = lesson?.source;
  if (!source || typeof source !== "object") return firstText(lesson, ["observed", "support", "evidence"], "", 700);
  const binding = Array.isArray(state.status?.bindings)
    ? state.status.bindings.find((entry) => entry?.binding_id === source.binding_id && entry?.source_instance === source.source_instance)
    : null;
  const name = text(binding?.label, text(source.source_label, text(source.source_id, "the selected window", 120), 120), 120);
  const generation = source.publication_generation ?? source.source_generation;
  const mark = source.annotation;
  const location = mark?.kind === "point" ? `point (${mark.x}, ${mark.y}) px`
    : mark?.kind === "region" ? `region (${mark.x}, ${mark.y}) · ${mark.width} × ${mark.height} px` : "";
  return [name, generation !== undefined ? `publication ${text(generation, "", 24)}` : "", location].filter(Boolean).join(" · ");
}

function renderLessons(rawLessons) {
  const lessons = items(rawLessons);
  el.lessonCount.textContent = String(lessons.length);
  el.lessonCount.setAttribute("aria-label", `${lessons.length} lessons or interpretations`);
  el.lessons.replaceChildren();
  if (!lessons.length) {
    el.lessons.append(make("p", "empty-note", "Nothing has been shared in this session yet."));
    return;
  }
  for (const lesson of lessons) {
    const id = scalarId(lesson.id ?? lesson.lesson_id);
    const status = text(lesson.status, "open", 50).toLowerCase();
    const title = firstText(lesson, ["title", "label", "name"], lesson.kind === "method" ? "A method for this work" : "Your marked moment", 180);
    const summary = firstText(lesson, ["summary", "understanding", "interpretation", "text", "content"], "Cassi has not supplied a short summary for this item.", 1000);
    const card = make("article", "lesson-card");
    card.dataset.status = status;
    const heading = make("div", "item-heading");
    heading.append(make("h4", "", title));
    const statusLabel = make("span", `item-status${["pending", "open", "field-admitted-unconfirmed"].includes(status) ? " pending" : ""}`, ({
      "field-admitted-unconfirmed": "Awaiting your read",
      "human-confirmed": "Confirmed by you",
      "field-supported": "Field-supported",
      "retired-from-suggestions": "Retired from suggestions",
      "left-out": "Left out",
    })[status] || status.replace(/[_-]+/g, " "));
    heading.append(statusLabel);
    card.append(heading, make("p", "lesson-summary", summary));
    const method = lesson.method && typeof lesson.method === "object" ? lesson.method : null;
    if (method) {
      const facts = make("dl", "method-facts");
      for (const [label, key] of [["Use when", "conditions"], ["Steps", "steps"], ["Expect", "expected_result"], ["Stop", "stop_when"], ["If it fails", "recovery"]]) {
        const value = text(method[key], "", 800);
        if (value) {
          const row = make("div");
          row.append(make("dt", "", label), make("dd", "", value));
          facts.append(row);
        }
      }
      if (facts.childElementCount) card.append(facts);
    }
    const interpretations = items(lesson.visual_interpretation);
    for (const interpretation of interpretations.slice(0, 2)) {
      const possibleRead = firstText(interpretation, ["summary", "description", "text"], "", 650);
      if (possibleRead) card.append(make("p", "lesson-uncertainty", `Possible visual read · ${possibleRead}`));
    }
    const uncertainty = firstText(lesson, ["uncertainty", "open_question", "caveat"], "", 700);
    if (uncertainty) card.append(make("p", "lesson-uncertainty", `Still uncertain: ${uncertainty}`));
    const support = lessonSupport(lesson);
    const possibleUse = firstText(lesson, ["possible_use", "applicability", "use_when"], "", 600);
    if (support) card.append(make("p", "lesson-support", `Support: ${support}`));
    if (possibleUse) card.append(make("p", "lesson-support", `May help when: ${possibleUse}`));
    if (id) {
      const actions = make("div", "lesson-actions");
      const addAction = (label, action, className = "button button-secondary") => {
        const button = make("button", className, label);
        button.type = "button";
        button.dataset.action = action;
        button.dataset.lessonId = id;
        actions.append(button);
      };
      const pending = ["pending", "open", "proposed", "unconfirmed", "field-admitted-unconfirmed"].includes(status);
      const retained = ["retained", "confirmed", "human-confirmed", "learned", "active", "field-supported", "clarified"].includes(status);
      if (pending) {
        addAction("That’s right", "confirm-lesson");
        addAction("Let me clarify", "clarify-lesson");
        addAction("Leave this out", "leave-out", "button button-quiet");
      } else if (retained) {
        addAction("Let me clarify", "clarify-lesson");
        addAction("Stop using this lesson", "stop-using", "button button-quiet");
        const removalPreview = lesson.removal_preview ?? lesson.retention_preview ?? null;
        const remove = make("button", "button button-danger", "Remove retained material…");
        remove.type = "button";
        remove.dataset.action = "remove-lesson";
        remove.dataset.lessonId = id;
        remove.disabled = !meaningful(removalPreview);
        if (remove.disabled) remove.title = "The entity has not supplied an exact removal preview for this item.";
        actions.append(remove);
      }
      if (actions.childElementCount) card.append(actions);
    }
    el.lessons.append(card);
  }
}

function renderQuestions(rawQuestions) {
  const questions = items(rawQuestions);
  el.questionCount.textContent = String(questions.length);
  el.questionCount.setAttribute("aria-label", `${questions.length} open questions`);
  el.questions.replaceChildren();
  if (!questions.length) {
    el.questions.append(make("p", "empty-note", "No open questions to show."));
    return;
  }
  for (const question of questions) {
    const card = make("article", "inbox-card");
    const heading = make("div", "item-heading");
    heading.append(make("h4", "", firstText(question, ["question", "prompt", "text", "title", "content"], "An open question", 700)));
    heading.append(make("span", "question-mark", "?"));
    card.append(heading);
    const context = firstText(question, ["context", "why", "source"], "", 400);
    if (context) card.append(make("p", "question-meta", context));
    el.questions.append(card);
  }
}

function suggestionKey(suggestion) {
  const id = scalarId(suggestion.id ?? suggestion.suggestion_id);
  if (id) return `id:${id}`;
  return JSON.stringify([
    firstText(suggestion, ["title", "name", "method", "candidate"], "A possible next step", 220),
    firstText(suggestion, ["summary", "description", "text", "possible_use", "rationale"], "", 850),
    firstText(suggestion, ["support", "source", "evidence", "conditions"], "", 650),
  ]);
}

function renderSuggestions(rawSuggestions) {
  const allSuggestions = items(rawSuggestions);
  const showSuggestions = state.mode === "suggest";
  const suggestions = showSuggestions ? allSuggestions.filter((suggestion) => !state.dismissedSuggestions.has(suggestionKey(suggestion))) : [];
  el.suggestionCount.textContent = String(suggestions.length);
  el.suggestionCount.setAttribute("aria-label", `${suggestions.length} suggestions`);
  el.suggestions.replaceChildren();
  el.suggestionModeNote.textContent = showSuggestions ? "Ideas are optional; Cassi cannot act on them from this page." : "Switch to Suggest when you want relevant, supported ideas here.";
  if (!showSuggestions) {
    el.suggestions.append(make("p", "empty-note", "Suggestions stay quiet in Watch mode."));
    return;
  }
  if (!suggestions.length) {
    el.suggestions.append(make("p", "empty-note", allSuggestions.length ? "You hid these suggestions for this session. The underlying learning is unchanged." : "No supported suggestion is available right now."));
    return;
  }
  for (const suggestion of suggestions) {
    const card = make("article", "suggestion-card");
    const heading = make("div", "item-heading");
    const title = firstText(suggestion, ["title", "name", "method", "candidate"], "A possible next step", 220);
    heading.append(make("h4", "", title));
    const body = firstText(suggestion, ["summary", "description", "text", "possible_use", "rationale"], "Details are available from Cassi.", 850);
    const support = firstText(suggestion, ["support", "source", "evidence", "conditions"], "", 650);
    card.append(heading, make("p", "item-copy", body));
    if (support) card.append(make("p", "suggestion-support", `Support: ${support}`));
    const actions = make("div", "suggestion-actions");
    const method = suggestion.method && typeof suggestion.method === "object" ? suggestion.method : null;
    if (method) {
      const facts = make("dl", "method-facts");
      for (const [label, key] of [["Use when", "conditions"], ["Expect", "expected_result"], ["Stop", "stop_when"], ["If it fails", "recovery"]]) {
        const value = text(method[key], "", 600);
        if (value) {
          const row = make("div");
          row.append(make("dt", "", label), make("dd", "", value));
          facts.append(row);
        }
      }
      if (facts.childElementCount) card.append(facts);
    }
    const accept = make("button", "button button-secondary", "Do this with me");
    accept.type = "button";
    accept.dataset.action = "delegated-task";
    accept.dataset.suggestionTitle = title;
    const dismiss = make("button", "button button-quiet", "Not now");
    dismiss.type = "button";
    dismiss.dataset.action = "dismiss-suggestion";
    dismiss.dataset.suggestionKey = suggestionKey(suggestion);
    dismiss.setAttribute("aria-label", `Hide ${title} for this session`);
    actions.append(accept, dismiss);
    card.append(actions);
    el.suggestions.append(card);
  }
}

function pinCurrentFrame() {
  const frame = state.currentFrame;
  const currentPair = bindingForPublication(state.status);
  const currentIdentity = publicationIdentity(currentPair.publication, currentPair.binding);
  if (!frame?.blob || !frame.meta || !frame.identity || frame.identity !== currentIdentity || currentPair.publication?.is_latest === false || !isSessionActive() || Date.now() >= frame.expiresAt) return;
  if (!visualAvailable(state.status, currentPair.publication)) {
    showToast("A current visual publication is not available to pin.", "warn");
    return;
  }
  revokePinned();
  const url = URL.createObjectURL(frame.blob);
  const pinned = { blob: frame.blob, url, meta: { ...frame.meta }, identity: frame.identity, capturedAt: frame.capturedAt, expiresAt: frame.expiresAt };
  state.pinned = pinned;
  state.pinExpiryTimer = setTimeout(() => {
    if (state.pinned !== pinned) return;
    revokePinned();
    el.momentMessage.textContent = "This image has left the short-lived buffer. Pin a fresh view to share a moment.";
  }, Math.max(0, pinned.expiresAt - Date.now()));
  el.pinnedImage.src = url;
  const sourceWidth = Number(frame.meta.width);
  const sourceHeight = Number(frame.meta.height);
  const heightLimit = Math.min(window.innerHeight * 0.63, 704);
  el.pinnedImage.style.width = sourceWidth > 0 && sourceHeight > 0 && sourceWidth < 360
    ? `${Math.max(sourceWidth, Math.min(640, heightLimit * sourceWidth / sourceHeight))}px` : "";
  el.pinMetadata.textContent = `${frame.meta.source_label} · source version ${text(frame.meta.source_instance, "not reported", 70)} · publication ${text(frame.meta.publication_generation, "not reported", 70)} · ${text(frame.meta.width, "?", 24)} × ${text(frame.meta.height, "?", 24)}`;
  el.momentMessage.textContent = "The mark will stay attached to this image version.";
  el.momentInstruction.value = "";
  el.pointMark.hidden = true;
  el.regionMark.hidden = true;
  state.annotation = null;
  const pointMode = $("input[name=annotation-kind][value=point]");
  if (pointMode) pointMode.checked = true;
  el.annotationControls.dataset.annotation = "point";
  el.annotationHint.textContent = "Click the pinned image to place a point, or use the coordinate fields below.";
  el.momentPanel.classList.remove("hidden");
  updateAnnotationFromInputs();
  el.momentPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function annotationKind() {
  return $("input[name=annotation-kind]:checked")?.value === "region" ? "region" : "point";
}

function validPercent(input) {
  const value = Number(input.value);
  return Number.isFinite(value) && value >= 0 && value <= 100;
}

function updateAnnotationFromInputs() {
  if (!state.pinned || !validPercent(el.coordX) || !validPercent(el.coordY)) {
    state.annotation = null;
    updateMomentEnabled();
    return;
  }
  const kind = annotationKind();
  const x = Number(el.coordX.value) / 100;
  const y = Number(el.coordY.value) / 100;
  if (kind === "point") {
    state.annotation = { kind, x, y };
    el.pointMark.setAttribute("cx", String(x * 1000));
    el.pointMark.setAttribute("cy", String(y * 1000));
    el.pointMark.hidden = false;
    el.regionMark.hidden = true;
  } else {
    const width = Number(el.coordWidth.value) / 100;
    const height = Number(el.coordHeight.value) / 100;
    if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0 || x + width > 1 || y + height > 1) {
      state.annotation = null;
      el.regionMark.hidden = true;
      updateMomentEnabled();
      return;
    }
    state.annotation = { kind, x, y, width, height };
    el.regionMark.setAttribute("x", String(x * 1000));
    el.regionMark.setAttribute("y", String(y * 1000));
    el.regionMark.setAttribute("width", String(width * 1000));
    el.regionMark.setAttribute("height", String(height * 1000));
    el.regionMark.hidden = false;
    el.pointMark.hidden = true;
  }
  updateMomentEnabled();
}

function methodInputs() {
  return [el.methodPurpose, el.methodConditions, el.methodSteps, el.methodExpected, el.methodStop, el.methodRecovery];
}

function toggleMethodFields() {
  const isMethod = el.momentKind.value === "method";
  el.methodDetails.classList.toggle("hidden", !isMethod);
  for (const input of methodInputs()) input.required = isMethod;
  updateMomentEnabled();
}

function updateMomentEnabled() {
  const instruction = el.momentInstruction.value.trim();
  const meta = state.pinned?.meta;
  const geometryKnown = meta && meta.binding_id !== undefined && Boolean(meta.capture_id) && meta.publication_generation !== undefined && meta.source_epoch !== undefined && meta.geometry_revision !== undefined && Number.isSafeInteger(meta.width) && meta.width > 0 && Number.isSafeInteger(meta.height) && meta.height > 0;
  const sessionUsable = state.connected && isSessionActive() && statusKey() !== "unknown_effect";
  const methodReady = el.momentKind.value !== "method" || methodInputs().every((input) => input.value.trim());
  el.sendMoment.disabled = !sessionUsable || !state.pinned || Date.now() >= state.pinned.expiresAt || !geometryKnown || !state.annotation || !instruction || !methodReady || state.requestPending;
}

function pointFromPointer(event) {
  const rect = el.pinnedImage.getBoundingClientRect();
  if (!rect.width || !rect.height) return null;
  return {
    x: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)),
    y: Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height)),
  };
}

let regionStart = null;
function startRegion(event) {
  if (!state.pinned || annotationKind() !== "region") return;
  const point = pointFromPointer(event);
  if (!point) return;
  event.preventDefault();
  regionStart = point;
  el.annotationOverlay.setPointerCapture(event.pointerId);
  el.coordX.value = String(Math.round(point.x * 1000) / 10);
  el.coordY.value = String(Math.round(point.y * 1000) / 10);
  el.coordWidth.value = "0.5";
  el.coordHeight.value = "0.5";
  updateAnnotationFromInputs();
}

function moveRegion(event) {
  if (!regionStart || annotationKind() !== "region") return;
  const point = pointFromPointer(event);
  if (!point) return;
  const left = Math.min(regionStart.x, point.x);
  const top = Math.min(regionStart.y, point.y);
  const width = Math.abs(point.x - regionStart.x);
  const height = Math.abs(point.y - regionStart.y);
  el.coordX.value = String(Math.round(left * 1000) / 10);
  el.coordY.value = String(Math.round(top * 1000) / 10);
  el.coordWidth.value = String(Math.max(0, Math.round(width * 1000) / 10));
  el.coordHeight.value = String(Math.max(0, Math.round(height * 1000) / 10));
  updateAnnotationFromInputs();
}

function finishRegion(event) {
  if (!regionStart) return;
  moveRegion(event);
  regionStart = null;
  if (!state.annotation || state.annotation.kind !== "region" || state.annotation.width <= 0 || state.annotation.height <= 0) {
    state.annotation = null;
    el.regionMark.hidden = true;
    el.momentMessage.textContent = "Drag across a non-empty region, or enter width and height with the keyboard.";
    updateMomentEnabled();
  }
}

function markPoint(event) {
  if (!state.pinned || annotationKind() !== "point") return;
  const point = pointFromPointer(event);
  if (!point) return;
  el.coordX.value = String(Math.round(point.x * 1000) / 10);
  el.coordY.value = String(Math.round(point.y * 1000) / 10);
  updateAnnotationFromInputs();
}

function sourcePixelAnnotation(annotation, meta) {
  const width = Number(meta.width);
  const height = Number(meta.height);
  if (!Number.isSafeInteger(width) || width < 1 || !Number.isSafeInteger(height) || height < 1) {
    throw new Error("The pinned image has no usable source dimensions.");
  }
  const x = Math.min(width - 1, Math.floor(annotation.x * width));
  const y = Math.min(height - 1, Math.floor(annotation.y * height));
  if (annotation.kind === "point") return { kind: "point", x, y };
  const right = Math.max(x + 1, Math.min(width, Math.ceil((annotation.x + annotation.width) * width)));
  const bottom = Math.max(y + 1, Math.min(height, Math.ceil((annotation.y + annotation.height) * height)));
  return { kind: "region", x, y, width: right - x, height: bottom - y };
}

async function submitMoment() {
  updateMomentEnabled();
  if (el.sendMoment.disabled || !state.pinned) return;
  const meta = state.pinned.meta;
  const body = {
    binding_id: meta.binding_id,
    capture_id: meta.capture_id,
    publication_generation: meta.publication_generation,
    source_epoch: meta.source_epoch,
    geometry_revision: meta.geometry_revision,
    annotation: sourcePixelAnnotation(state.annotation, meta),
    instruction: el.momentInstruction.value.trim(),
    kind: el.momentKind.value,
  };
  if (body.kind === "method") {
    body.method = {
      purpose: el.methodPurpose.value.trim(),
      conditions: el.methodConditions.value.trim(),
      steps: el.methodSteps.value.trim(),
      parameters: el.methodParameters.value.trim(),
      expected_result: el.methodExpected.value.trim(),
      stop_when: el.methodStop.value.trim(),
      recovery: el.methodRecovery.value.trim(),
    };
  }
  state.requestPending = true;
  updateMomentEnabled();
  el.momentMessage.textContent = "Sending this source-linked moment to the entity…";
  let accepted = false;
  try {
    const result = await requestJson(`${API_ROOT}/moments`, { method: "POST", body });
    accepted = true;
    state.lastResponse = result;
    el.momentMessage.textContent = "Moment request received. Checking Cassi’s source-linked record.";
    announceResult(result, "Moment request received. Checking Cassi’s source-linked record.");
    await loadStatus();
    renderDetails();
  } catch (error) {
    if (error?.kind === "surface-wait" && error?.details?.kind === "volatile-frame-stale") {
      revokePinned();
      el.momentMessage.textContent = "This image has left the short-lived buffer. Pin a current view to share a new moment.";
      showToast(error.message, "warn");
      return;
    }
    const uncertain = (accepted || isAmbiguousFailure(error)) && state.connected && !state.closing;
    if (uncertain) {
      markUnknownEffect("The shared moment's result could not be confirmed. Wait for the entity's record before sending it again.");
      el.momentMessage.textContent = "The request outcome is uncertain. Do not resend until the session status is checked.";
    } else {
      el.momentMessage.textContent = error.message;
    }
    showToast(error.message, uncertain ? "warn" : "error");
  } finally {
    state.requestPending = false;
    updateMomentEnabled();
  }
}

function addDialogAction(label, handler, className = "button button-secondary") {
  const button = make("button", className, label);
  button.type = "button";
  button.addEventListener("click", handler);
  el.dialogActions.append(button);
  return button;
}

function openDialog(title, contentNodes, actions) {
  el.dialogTitle.textContent = title;
  el.dialogContent.replaceChildren(...contentNodes);
  el.dialogActions.replaceChildren();
  for (const action of actions) addDialogAction(action.label, action.onClick, action.className);
  if (!el.dialog.open) el.dialog.showModal();
}

function closeDialog() {
  if (el.dialog.open) el.dialog.close();
}

function delegatedTask(title) {
  const safeTitle = text(title, "this suggestion", 220);
  const prompt = make("p", "", `Open separate task authority for “${safeTitle}”? This page will not grant keyboard or mouse access, and no task or permission is sent from here.`);
  const boundary = make("p", "", "Review the exact task and permissions in the existing Surface controls. You can return here without changing this observation session.");
  const cancel = { label: "Stay here", onClick: closeDialog, className: "button button-secondary" };
  const go = {
    label: "Open task controls",
    onClick: () => { window.location.assign("/workspace"); },
    className: "button button-primary",
  };
  openDialog("A separate task, with its own authority", [prompt, boundary], [cancel, go]);
}

function lessonById(id) {
  return items(state.status?.lessons).find((lesson) => scalarId(lesson.id ?? lesson.lesson_id) === String(id));
}

function correctionMessage(result, fallback) {
  const message = firstText(result, ["message", "status", "summary"], fallback, 500);
  return message;
}

async function sendCorrection(lessonId, action, extra = {}) {
  if (!lessonId || state.requestPending) return;
  state.requestPending = true;
  updateSessionControls();
  let accepted = false;
  try {
    const result = await requestJson(`${API_ROOT}/corrections`, {
      method: "POST",
      body: { lesson_id: lessonId, action, ...extra },
    });
    accepted = true;
    state.lastResponse = result;
    showToast(correctionMessage(result, "Correction request received. Refreshing the recorded interpretation."));
    await loadStatus();
  } catch (error) {
    const uncertain = (accepted || isAmbiguousFailure(error)) && state.connected && !state.closing;
    if (uncertain) {
      markUnknownEffect("The correction request's result could not be confirmed. Wait for the entity's record before repeating it.");
    } else if (state.connected && error.status !== 401 && !state.closing) {
      try { await loadStatus(); } catch { /* Preserve the correction error and last known status. */ }
    }
    showToast(error.message, uncertain ? "warn" : "error");
  } finally {
    state.requestPending = false;
    updateSessionControls();
    renderDetails();
  }
}

function clarifyLesson(id) {
  const lesson = lessonById(id);
  const title = firstText(lesson, ["title", "label", "name"], "this interpretation", 180);
  const explanation = make("p", "", `Add a correction linked to “${title}”. Cassi will keep the source observation separate from your explanation.`);
  const field = make("label", "field");
  field.append(make("span", "", "What should Cassi revise?"));
  const input = make("textarea");
  input.rows = 4;
  input.maxLength = 1000;
  input.required = true;
  input.placeholder = "Describe what was missing or misunderstood";
  field.append(input);
  const cancel = { label: "Cancel", onClick: closeDialog, className: "button button-secondary" };
  const clarify = {
    label: "Send clarification",
    className: "button button-primary",
    onClick: async () => {
      const value = input.value.trim();
      if (!value) { input.focus(); return; }
      closeDialog();
      await sendCorrection(id, "clarify", { text: value });
    },
  };
  openDialog("Let me clarify", [explanation, field], [cancel, clarify]);
  input.focus();
}

function removeLesson(id) {
  const lesson = lessonById(id);
  const preview = lesson?.removal_preview ?? lesson?.retention_preview;
  if (!meaningful(preview)) {
    showToast("The entity has not supplied an exact removal preview. Nothing was removed.", "warn");
    return;
  }
  const title = firstText(lesson, ["title", "label", "name"], "this retained item", 180);
  const disclosure = make("p", "", `Review the entity’s exact removal scope for “${title}” before continuing. The preview is not a claim that related evidence has already been deleted.`);
  const exact = make("div", "exact-preview", readableSummary(preview, pretty(preview)));
  const confirm = { label: "Cancel", onClick: closeDialog, className: "button button-secondary" };
  const remove = {
    label: "Request removal of this item",
    onClick: async () => {
      closeDialog();
      await sendCorrection(id, "remove");
    },
    className: "button button-danger",
  };
  openDialog("Review retained-material removal", [disclosure, exact], [confirm, remove]);
}

function getUnsavedIntervals(status) {
  const retention = status?.retention;
  if (!retention || typeof retention !== "object") return [];
  for (const key of ["unsaved_intervals", "recent_unsaved_intervals", "recent_intervals", "discardable_intervals"]) {
    if (Array.isArray(retention[key])) return retention[key].filter((interval) => interval && typeof interval === "object");
  }
  return [];
}

function discardRecentDialog() {
  const intervals = getUnsavedIntervals(state.status);
  if (!intervals.length) {
    showToast("The entity has not reported a selectable unsaved interval. Nothing was discarded.", "warn");
    return;
  }
  const explanation = make("p", "", "Choose one exact unsaved interval. This action stops pending use and releases that interval only if the entity confirms it.");
  const field = make("label", "field");
  field.append(make("span", "", "Unsaved interval"));
  const select = make("select");
  for (const interval of intervals) {
    const option = make("option", "", firstText(interval, ["label", "summary", "start", "from", "id"], "Unsaved interval", 240));
    const intervalId = scalarId(interval.id ?? interval.interval_id);
    option.value = intervalId || JSON.stringify(interval);
    select.append(option);
  }
  field.append(select);
  const cancel = { label: "Keep this interval", onClick: closeDialog, className: "button button-secondary" };
  const discard = {
    label: "Discard this interval",
    className: "button button-danger",
    onClick: async () => {
      const chosen = intervals.find((interval) => (scalarId(interval.id ?? interval.interval_id) || JSON.stringify(interval)) === select.value);
      if (!chosen) return;
      closeDialog();
      await sendControl({ action: "discard_recent", interval: chosen }, "Discard request received. Checking the entity’s recorded result.");
    },
  };
  openDialog("Discard recent unsaved moments", [explanation, field], [cancel, discard]);
}

function stopProcessingDialog() {
  const explanation = make("p", "", "Stop remaining processing for this session. This does not claim to remove earlier confirmed or retained learning.");
  const cancel = { label: "Keep processing", onClick: closeDialog, className: "button button-secondary" };
  const stop = {
    label: "Stop processing this session",
    className: "button button-danger",
    onClick: async () => {
      closeDialog();
      await sendControl({ action: "stop_processing" }, "Stop request received. Checking the entity’s stop status.");
    },
  };
  openDialog("Stop this session’s remaining work?", [explanation], [cancel, stop]);
}

async function sendControl(body, fallback) {
  if (!state.connected || state.requestPending) return;
  state.requestPending = true;
  updateSessionControls();
  let accepted = false;
  try {
    const result = await requestJson(`${API_ROOT}/control`, { method: "POST", body });
    accepted = true;
    state.lastResponse = result;
    await loadStatus();
    showToast(correctionMessage(result, fallback));
    if (!isSessionActive()) clearFrameTimer();
    else startFrameTimer();
  } catch (error) {
    const uncertain = (accepted || isAmbiguousFailure(error)) && state.connected && !state.closing;
    if (uncertain) {
      markUnknownEffect("The control request's effect could not be confirmed. Waiting for fresh status before another action.");
    } else if (state.connected && error.status !== 401 && !state.closing) {
      try { await loadStatus(); } catch { /* Preserve the control error and last known status. */ }
    }
    showToast(error.message, uncertain ? "warn" : "error");
  } finally {
    state.requestPending = false;
    updateSessionControls();
    updateAgreement();
  }
}

function askFinish() {
  const explanation = make("p", "", "Finish stops new collection. The entity may settle already authorized work, but finishing is not a request to remove anything previously retained.");
  const cancel = { label: "Keep session open", onClick: closeDialog, className: "button button-secondary" };
  const finish = {
    label: "Finish session",
    className: "button button-primary",
    onClick: async () => {
      closeDialog();
      await sendControl({ action: "finish" }, "Finish request received. Checking the entity’s recorded status.");
    },
  };
  openDialog("Finish this observation session?", [explanation], [cancel, finish]);
}

async function togglePause() {
  if (!state.connected || state.requestPending) return;
  await sendControl({ action: isSessionPaused() ? "resume" : "pause" }, isSessionPaused() ? "Resume request received. The entity will revalidate the selected source." : "Pause requested. Waiting for the entity to confirm its stop fence.");
}

async function toggleMode() {
  if (!state.connected || state.requestPending || !isSessionActive()) return;
  const next = state.mode === "suggest" ? "watch" : "suggest";
  await sendControl({ action: "mode", mode: next }, `Mode change to ${next === "suggest" ? "Suggest" : "Watch"} requested.`);
}

function showToast(message, tone = "") {
  const toast = make("div", "toast", text(message, "Cassi has no new message.", 800));
  if (tone) toast.dataset.tone = tone;
  el.toastRegion.replaceChildren(toast);
  if (state.toastTimer) clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => toast.remove(), 6000);
}

function announceResult(result, fallback) {
  if (result && typeof result === "object") state.lastResponse = result;
  showToast(correctionMessage(result, fallback));
}

function clickAction(event) {
  const button = event.target.closest("[data-action]");
  if (!button || button.disabled) return;
  const action = button.dataset.action;
  if (action === "load-preview") void reloadSourcePreview(button.dataset.sourceKey);
  else if (action === "confirm-lesson") void sendCorrection(button.dataset.lessonId, "confirm");
  else if (action === "clarify-lesson") clarifyLesson(button.dataset.lessonId);
  else if (action === "leave-out") void sendCorrection(button.dataset.lessonId, "leave_out");
  else if (action === "stop-using") void sendCorrection(button.dataset.lessonId, "stop_using");
  else if (action === "remove-lesson") removeLesson(button.dataset.lessonId);
  else if (action === "delegated-task") delegatedTask(button.dataset.suggestionTitle);
  else if (action === "dismiss-suggestion") {
    state.dismissedSuggestions.add(button.dataset.suggestionKey);
    renderSuggestions(state.status?.suggestions);
    el.suggestions.setAttribute("tabindex", "-1");
    el.suggestions.focus();
    showToast("Suggestion hidden for this session. The underlying learning is unchanged.");
  }
}

function handleSourceChange(event) {
  const checkbox = event.target.closest("input[data-source-key]");
  if (!checkbox) return;
  setSelected(checkbox.dataset.sourceKey, checkbox.checked, checkbox);
}

function handleModeChange() {
  resetConsent();
}

const EMBODIED_POLL_MS = 10_000;
const EMBODIED_CAPTURE_LIMIT = 32;
const SVG_NS = "http://www.w3.org/2000/svg";
const EMBODIED_MEASURE_KEYS = new Set([
  "signed_current", "current_energy", "field_ticks", "evidence_tick", "field_time_step",
  "energy", "activity", "counterflow_rail_power", "common_rail_power", "cycle_power",
  "semantic_residual_norm", "overlap", "effective_weight", "progress", "before_shift",
  "after_shift", "frequency", "magnitude", "real", "imag",
]);

function sectionItems(section) {
  if (Array.isArray(section)) return section;
  if (Array.isArray(section?.items)) return section.items;
  if (Array.isArray(section?.value?.items)) return section.value.items;
  if (Array.isArray(section?.bindings)) return section.bindings;
  if (Array.isArray(section?.roles)) return section.roles;
  return [];
}
// Presentation history holds only bounded summaries, never a second copy of owner state.
const EMBODIED_HISTORY_LIMIT = 24;
function observedField(snapshot) {
  const workspace = snapshot?.circulation?.value?.workspace;
  const metrics = new Map();
  for (const key of ["energy", "activity", "field_ticks", "evidence_tick"]) {
    if (Number.isFinite(workspace?.[key])) metrics.set(`workspace.${key}`, workspace[key]);
  }
  for (const region of sectionItems(snapshot?.regions).slice(0, 12)) {
    if (typeof region?.region_id !== "string") continue;
    if (Number.isFinite(region.signed_current) && !region.stale) {
      metrics.set(`region.${region.region_id}.signed_current`, region.signed_current);
    }
  }
  const programs = new Map();
  for (const item of sectionItems(snapshot?.working_organization).slice(0, 32)) {
    const key = programReferenceKey(item.program_ref);
    if (key) programs.set(key, {
      label: text(item.program_ref.id, "Program", 90),
      status: text(item.status, "unknown", 80),
      contribution: text(item.contribution ?? item.projection?.contribution, "", 140),
      reopen: text(item.reopen_condition ?? item.projection?.reopen_condition, "", 140),
    });
  }
  return {
    identity: embodiedIdentity(snapshot),
    metrics,
    programs,
    at: embodiedTimestamp(snapshot),
    fieldTicks: Number.isFinite(workspace?.field_ticks) ? workspace.field_ticks : null,
    generation: snapshot.generation,
    coverage: snapshot?.working_organization?.capture_matches_owner,
  };
}

function admitFieldObservation(snapshot) {
  const current = observedField(snapshot);
  const previous = state.embodied.lastObservation;
  const changes = [...current.metrics].filter(([key, value]) => previous?.metrics.has(key) && previous.metrics.get(key) !== value);
  const programChanges = [];
  if (previous) {
    for (const [key, item] of current.programs) {
      const before = previous.programs.get(key);
      if (!before) {
        programChanges.push(`${item.label}: first returned with recorded status ${item.status}.`);
      } else if (before.status !== item.status || before.contribution !== item.contribution || before.reopen !== item.reopen) {
        const detail = [
          before.status !== item.status ? `status ${before.status} → ${item.status}` : null,
          before.contribution !== item.contribution ? `contribution ${item.contribution || "not reported"}` : null,
          before.reopen !== item.reopen ? `reopen condition ${item.reopen || "not reported"}` : null,
        ].filter(Boolean).join("; ");
        programChanges.push(`${item.label}: ${detail}.`);
      }
    }
  }
  const distinct = !previous || current.identity !== previous.identity || changes.length > 0 || programChanges.length > 0;
  if (!distinct) return false;
  const observation = {
    at: current.at, fieldTicks: current.fieldTicks, generation: current.generation,
    metrics: current.metrics, changes, coverage: current.coverage,
  };
  state.embodied.observations.push(observation);
  if (state.embodied.observations.length > EMBODIED_HISTORY_LIMIT) state.embodied.observations.shift();
  for (const description of programChanges.slice(0, 8)) {
    state.embodied.transitions.unshift({ at: current.at, description });
  }
  state.embodied.transitions.length = Math.min(state.embodied.transitions.length, 8);
  state.embodied.lastObservation = current;
  return true;
}

function renderFieldActivity() {
  const observations = state.embodied.observations;
  const last = observations.at(-1);
  const previous = observations.at(-2);
  el.embodiedActivityTrace.replaceChildren();
  el.embodiedTransitions.replaceChildren();
  el.embodiedActivityCount.textContent = `${observations.length} distinct observed states · max ${EMBODIED_HISTORY_LIMIT}`;
  if (!last || !last.metrics.size) {
    el.embodiedActivityNote.textContent = "No finite numerical measurements were returned. Layout, status and recorded meanings remain inspectable; no activity is inferred.";
    el.embodiedActivityTrace.setAttribute("aria-label", "Numerical movement unavailable");
  } else {
    const gap = previous && last.at !== null && previous.at !== null && last.at > previous.at
      ? ` · captures ${((last.at - previous.at) / 1000).toFixed(1)} s apart`
      : " · capture interval unavailable";
    const ticks = previous && last.fieldTicks !== null && previous.fieldTicks !== null
      ? ` · field ticks ${previous.fieldTicks} → ${last.fieldTicks}`
      : " · numerical elapsed time unavailable";
    el.embodiedActivityNote.textContent = previous
      ? `${last.changes.length} shared measured quantities changed${gap}${ticks}. Bars compare magnitudes within each reported key only; they are not transport or speed.`
      : "One admitted state: waiting for another distinct state. Bars show reported values, not inferred motion.";
    const keys = [...last.metrics.keys()].slice(0, 8);
    for (const key of keys) {
      const samples = observations.map((sample) => sample.metrics.get(key));
      const finite = samples.filter(Number.isFinite);
      const maximum = Math.max(0, ...finite.map(Math.abs));
      const row = make("div", "embodied-trace-row");
      row.append(make("code", "", key));
      const bars = make("div", "embodied-trace-bars");
      for (const value of samples) {
        const bar = make("span", `embodied-trace-bar${Number.isFinite(value) && value < 0 ? " negative" : ""}`);
        bar.style.height = Number.isFinite(value) ? `${Math.max(3, maximum ? Math.abs(value) / maximum * 100 : 3)}%` : "2px";
        bar.title = `${key}: ${Number.isFinite(value) ? value : "not reported"} · unit not supplied`;
        bars.append(bar);
      }
      row.append(bars, make("strong", "", `${last.metrics.get(key)} · unit not supplied`));
      el.embodiedActivityTrace.append(row);
    }
    el.embodiedActivityTrace.setAttribute("aria-label", `${observations.length} distinct states. ${el.embodiedActivityNote.textContent}`);
  }
  if (!state.embodied.transitions.length) {
    emptyEmbodiedList(el.embodiedTransitions, "No recorded Program status, contribution, or reopen-condition transition was observed in this viewer session.");
  } else {
    for (const event of state.embodied.transitions) {
      el.embodiedTransitions.append(make("p", "embodied-transition", `${event.at === null ? "Capture time unknown" : dateLabel(event.at)} · ${event.description}`));
    }
  }
}

function sectionStatus(section) {
  if (typeof section?.status === "string") return section.status;
  return sectionItems(section).length ? "known" : "unavailable";
}

function sectionCoverage(section, label) {
  const items = sectionItems(section);
  const status = sectionStatus(section);
  if (status === "unavailable" || status === "unknown") {
    const coverage = section?.truncated ? ` Results are truncated${Number.isFinite(section?.limit) ? ` at ${section.limit}` : ""}.` : "";
    return `${label}: ${status}${section?.reason ? ` — ${text(section.reason, "", 280)}` : ""}.${coverage}`;
  }
  if (section?.schema === "cassifi.embodied-role-bindings.v1") {
    const names = ["core", "mantle", "fringe"];
    const roles = names.map((name) => `${name}: ${section[name]?.status ?? "unavailable"}`);
    const regions = [...new Set(names.flatMap((name) => roleRegionIds(section[name])))];
    const unknowns = Array.isArray(section.unknowns) ? section.unknowns.length : 0;
    return `${label}: ${status}; ${roles.join(", ")}; ${regions.length} qualified region references; ${unknowns} declared unknowns.`;
  }
  if (Array.isArray(section?.current_concerns) || Array.isArray(section?.continuations)) {
    return `${label}: ${status}; ${(section.current_concerns || []).length} current concerns and ${(section.continuations || []).length} continuations; ${section.truncated ? "truncated" : "not reported as truncated"}.`;
  }
  const total = section?.total_count ?? section?.declared_count ?? section?.count ?? section?.value?.declared_variable_count;
  const limit = section?.limit ?? section?.value?.limit;
  let result = Number.isFinite(total)
    ? `Showing ${items.length} of ${total} ${label.toLowerCase()}.`
    : items.length
      ? `${items.length} ${label.toLowerCase()} returned; declared total unavailable.`
      : section?.value !== undefined
        ? `${label}: ${status}; projected value fields are present, but item coverage is unavailable.`
        : `${label}: ${status}; no item coverage count was supplied.`;
  if (Number.isFinite(limit)) result += ` Limit ${limit}.`;
  if (section?.truncated) result += " Results are truncated.";
  return result;
}

function embodiedFieldValue(value, limit = 800) {
  if (value === null) return "null";
  if (value === undefined) return "Not reported.";
  return text(value, "Not reported.", limit);
}

function embodiedTimestamp(snapshot) {
  const raw = snapshot?.captured_at_ns;
  if (raw === undefined || raw === null) return null;
  let milliseconds;
  try {
    const nanoseconds = typeof raw === "string" ? BigInt(raw) : BigInt(Math.trunc(raw));
    milliseconds = Number(nanoseconds / 1_000_000n);
  } catch {
    return null;
  }
  return Number.isFinite(milliseconds) ? milliseconds : null;
}

function embodiedReplayDelay(previous, next) {
  const previousTime = embodiedTimestamp(previous?.snapshot);
  const nextTime = embodiedTimestamp(next?.snapshot);
  return previousTime !== null && nextTime !== null && nextTime > previousTime
    ? nextTime - previousTime
    : null;
}

function embodiedReplayHasTiming(captures) {
  if (captures.length < 2) return false;
  return captures.every((capture, index) => (
    embodiedTimestamp(capture.snapshot) !== null
    && (index === 0 || embodiedReplayDelay(captures[index - 1], capture) !== null)
  ));
}

function shortHash(value) {
  if (typeof value !== "string" || !value) return "Unknown";
  return value.length > 22 ? `${value.slice(0, 12)}…${value.slice(-8)}` : value;
}

function dateLabel(timestamp) {
  if (!Number.isFinite(timestamp)) return "Not reported.";
  try { return new Date(timestamp).toLocaleString(); }
  catch { return "Not reported."; }
}

function ageLabel(milliseconds) {
  if (!Number.isFinite(milliseconds) || milliseconds < 0) return "Unknown";
  if (milliseconds < 1000) return "less than 1 s";
  if (milliseconds < 60_000) return `${Math.floor(milliseconds / 1000)} s`;
  if (milliseconds < 3_600_000) return `${Math.floor(milliseconds / 60_000)} min`;
  return `${Math.floor(milliseconds / 3_600_000)} h`;
}

function embodiedLayoutIdentity(snapshot) {
  return snapshot?.layout?.value?.coordinate_layout?.layout_identity
    ?? snapshot?.layout?.coordinate_layout?.layout_identity
    ?? null;
}

function embodiedIdentity(snapshot) {
  const organization = snapshot?.working_organization;
  return JSON.stringify([
    snapshot?.schema ?? null,
    snapshot?.generation ?? null,
    snapshot?.state_sha256 ?? null,
    organization?.generation ?? null,
    organization?.owner_state_sha256 ?? null,
  ]);
}

function displayedEmbodiedRecord() {
  if (Number.isInteger(state.embodied.replayIndex)) {
    return state.embodied.captures[state.embodied.replayIndex] || null;
  }
  if (state.embodied.frozenSnapshot) return state.embodied.frozenSnapshot;
  if (!state.embodied.latest) return null;
  return {
    snapshot: state.embodied.latest,
    receivedAt: state.embodied.receivedAt,
    capturedAt: null,
    identity: embodiedIdentity(state.embodied.latest),
    live: true,
  };
}

function setEmbodiedMessage(message, tone = "") {
  el.embodiedMessage.textContent = message;
  if (tone) el.embodiedMessage.dataset.tone = tone;
  else delete el.embodiedMessage.dataset.tone;
}

function embodiedSvgNode(tag, attributes = {}, value = "") {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, attribute] of Object.entries(attributes)) {
    if (attribute !== null && attribute !== undefined) node.setAttribute(key, String(attribute));
  }
  if (value) node.textContent = value;
  return node;
}

function emptyEmbodiedList(container, message) {
  container.replaceChildren(make("p", "empty-note", message));
}

function appendFacts(container, values) {
  const facts = values.filter(([, value]) => value !== undefined);
  if (!facts.length) return;
  const list = make("dl", "embodied-facts");
  for (const [label, value] of facts) {
    const row = make("div");
    row.append(make("dt", "", label), make("dd", "", embodiedFieldValue(value)));
    list.append(row);
  }
  container.append(list);
}

function appendRawDetails(container, title, value) {
  const details = make("details", "embodied-details");
  const summary = make("summary", "", title);
  const raw = make("pre", "", JSON.stringify(value, null, 2));
  details.append(summary, raw);
  container.append(details);
}

function roleRegionIds(role) {
  const values = role?.region_ids
    ?? role?.participating_region_ids
    ?? role?.regions
    ?? role?.region_refs
    ?? [];
  const ids = Array.isArray(values)
    ? values.map((value) => typeof value === "string" ? value : value?.region_id ?? value?.id).filter((value) => typeof value === "string")
    : [];
  if (typeof role?.region_id === "string") ids.push(role.region_id);
  return ids;
}
function regionHasRoleBinding(region, roleIds) {
  const candidates = [region?.region_id, region?.source_region_id];
  if (typeof region?.computer_id === "string" && typeof region?.region_id === "string") {
    candidates.push(`computer:${region.computer_id}:region:${region.region_id}`);
  }
  if (region?.kind === "resonant-workspace" && typeof region?.region_id === "string") {
    candidates.push(`owner:${region.region_id}`);
  }
  return candidates.some((candidate) => typeof candidate === "string" && roleIds.has(candidate));
}

function rolesForSnapshot(snapshot) {
  const section = snapshot?.roles;
  const listed = sectionItems(section);
  if (listed.length) return listed;
  return ["core", "mantle", "fringe"]
    .filter((name) => section?.[name] && typeof section[name] === "object")
    .map((name) => ({ ...section[name], role: name }));
}

function renderEmbodiedMap(snapshot) {
  const svg = el.embodiedMap;
  svg.replaceChildren();
  svg.append(embodiedSvgNode("desc", { id: "embodied-map-description" }, "The admitted snapshot has not supplied drawable region coordinates."));
  const regions = sectionItems(snapshot?.regions);
  const nodes = regions.filter((region) => (
    Array.isArray(region?.current_coordinates)
    && region.current_coordinates.length >= 2
    && region.current_coordinates.slice(0, 2).every(Number.isFinite)
  ));
  const roleIds = new Set(rolesForSnapshot(snapshot).flatMap(roleRegionIds));
  el.embodiedRegionCount.textContent = String(regions.length);
  el.embodiedRegionCount.setAttribute("aria-label", `${regions.length} regions returned`);
  if (!nodes.length) {
    svg.querySelector("#embodied-map-description").textContent = "No current region coordinates are present in this admitted snapshot.";
    el.embodiedProjectionNote.textContent = regions.length
      ? "No drawable current_coordinates are available; stale or unlocated regions remain in the measurements list."
      : `Region coordinates unavailable: ${snapshot?.regions?.reason || "the snapshot contains no region records"}.`;
    return;
  }
  const xs = nodes.map((region) => region.current_coordinates[0]);
  const ys = nodes.map((region) => region.current_coordinates[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const pointById = new Map();
  const project = (region) => ({
    x: 48 + ((region.current_coordinates[0] - minX) / (maxX - minX || 1)) * 544,
    y: 42 + ((region.current_coordinates[1] - minY) / (maxY - minY || 1)) * 276,
  });
  for (const region of nodes) pointById.set(region.region_id, project(region));
  svg.querySelector("#embodied-map-description").textContent = "Admitted current_coordinates are scaled linearly into this viewer. Lines show parent_id relationships only when both regions have drawable coordinates; other references remain in the region list. Node fill and shape encode reported signed_current sign. This projection is not asserted anatomy.";
  for (const region of nodes) {
    const parentPoint = pointById.get(region.parent_id);
    const point = pointById.get(region.region_id);
    if (parentPoint && point) {
      svg.append(embodiedSvgNode("line", {
        x1: parentPoint.x, y1: parentPoint.y, x2: point.x, y2: point.y, class: "topology-link",
      }));
    }
  }
  const maxCurrent = Math.max(0, ...nodes.map((region) => Math.abs(Number(region.signed_current) || 0)));
  for (const region of nodes) {
    const point = pointById.get(region.region_id);
    const signedCurrent = Number.isFinite(region.signed_current) ? region.signed_current : null;
    const sign = signedCurrent === null || signedCurrent === 0 ? "neutral" : signedCurrent > 0 ? "flow-positive" : "flow-negative";
    const radius = signedCurrent === null ? 7 : 7 + (maxCurrent ? 11 * Math.abs(signedCurrent) / maxCurrent : 0);
    const hasRole = regionHasRoleBinding(region, roleIds);
    const label = text(region.region_id, "unnamed region", 28);
    const summary = `${region.region_id}; signed_current ${signedCurrent ?? "not reported"}; ${region.stale ? "stale" : "current"}${hasRole ? "; has a recorded role binding" : ""}`;
    const selected = state.embodied.selectedRegion === region.region_id;
    const shape = sign === "flow-negative"
      ? embodiedSvgNode("polygon", {
        points: `${point.x},${point.y - radius} ${point.x + radius},${point.y} ${point.x},${point.y + radius} ${point.x - radius},${point.y}`,
        class: `region-node ${sign}${selected ? " selected" : ""}${hasRole ? " role-bound" : ""}${region.stale ? " stale" : ""}`,
      })
      : embodiedSvgNode("circle", {
        cx: point.x, cy: point.y, r: radius,
        class: `region-node ${sign}${selected ? " selected" : ""}${hasRole ? " role-bound" : ""}${region.stale ? " stale" : ""}`,
      });
    if (typeof region.region_id === "string") {
      shape.dataset.regionId = region.region_id;
      shape.setAttribute("role", "button");
      shape.setAttribute("tabindex", "0");
      shape.setAttribute("aria-label", `Inspect ${summary}`);
      shape.setAttribute("aria-pressed", String(selected));
    }
    shape.append(embodiedSvgNode("title", {}, summary));
    svg.append(shape);
    svg.append(embodiedSvgNode("text", { x: point.x + 10, y: point.y - 10, class: "region-label" }, label));
  }
  el.embodiedProjectionNote.textContent = `${nodes.length} regions plotted from current_coordinates, linearly scaled to fit this panel. Coordinates have no declared display units here. Parent lines are recorded relationships only and are omitted if either region lacks coordinates; signed current does not imply flow between nodes.`;
}

function renderEmbodiedRegions(snapshot) {
  const regions = sectionItems(snapshot?.regions);
  el.embodiedRegionList.replaceChildren();
  if (!regions.length) {
    emptyEmbodiedList(el.embodiedRegionList, `Region measurements unavailable: ${snapshot?.regions?.reason || "no region records were admitted"}.`);
    return;
  }
  for (const region of regions) {
    const card = make("article", "embodied-card");
    const title = region.region_id ?? region.computer_id ?? region.kind ?? "Region";
    card.append(make("h4", "", text(title, "Region", 180)));
    appendFacts(card, [
      ["Kind", region.kind],
      ["Status", region.status],
      ["Parent region", region.parent_id],
      ["Owner-reported signed_current (unit not supplied)", region.signed_current],
      ["Current energy (unit not supplied)", region.current_energy],
      ["Field ticks", region.field_ticks],
      ["Content version", region.content_version],
      ["Stale", region.stale],
      ["Current coordinates", region.current_coordinates],
    ]);
    appendRawDetails(card, "Other admitted region fields", region);
    el.embodiedRegionList.append(card);
  }
}

function renderRegionInspection(snapshot) {
  const regions = sectionItems(snapshot?.regions);
  const select = el.embodiedRegionSelect;
  select.replaceChildren(make("option", "", "Select a returned region"));
  select.firstChild.value = "";
  for (const region of regions) {
    if (typeof region?.region_id !== "string") continue;
    const option = make("option", "", `${region.region_id} · ${text(region.status, region.stale ? "stale" : "status unknown", 40)}`);
    option.value = region.region_id;
    select.append(option);
  }
  select.value = state.embodied.selectedRegion;
  const region = regions.find((item) => item.region_id === state.embodied.selectedRegion);
  el.embodiedRegionInspection.replaceChildren();
  if (!region) {
    emptyEmbodiedList(el.embodiedRegionInspection, state.embodied.selectedRegion
      ? "Selected region is not returned by this capture. It may be outside coverage; no current activity or meaning is inferred."
      : "Select a returned region to inspect owner measurements, roles, and exact source-bound meaning.");
    return;
  }
  const card = make("article", "embodied-card");
  card.append(make("h4", "", `Region · ${region.region_id}`));
  appendFacts(card, [
    ["Kind", region.kind ?? "Unknown"],
    ["Status", region.status ?? "Unknown"],
    ["Signed current (unit not supplied)", region.signed_current ?? "Not reported"],
    ["Stale", region.stale ?? "Not reported"],
    ["Coordinates", region.current_coordinates ?? "Not reported"],
    ["Layout identity", region.layout_identity ?? embodiedLayoutIdentity(snapshot) ?? "Not reported"],
  ]);
  const boundRoles = rolesForSnapshot(snapshot).filter((role) => regionHasRoleBinding(region, new Set(roleRegionIds(role))));
  appendFacts(card, [["Recorded roles", boundRoles.length ? boundRoles.map((role) => role.role ?? role.name ?? "Unlabelled role") : "No matching role binding returned"]]);
  const meaning = sectionItems(snapshot?.semantics).filter((item) => item.region_id === region.region_id).slice(0, 8);
  const exchange = sectionItems(snapshot?.exchange_meaning).filter((item) =>
    item.emitter_region_id === region.region_id || item.receiver_region_id === region.region_id).slice(0, 8);
  card.append(make("h4", "", "Exact matching meaning and source"));
  if (!meaning.length && !exchange.length) {
    card.append(make("p", "empty-note", "No exact region-id meaning or source exchange was returned. Semantic interpretation is unknown."));
  }
  for (const item of meaning) {
    appendFacts(card, [["Meaning record", `${text(item.record_kind ?? item.kind, "kind unknown", 50)} · ${text(item.record_id ?? item.variable_id ?? item.chart_id, "id unknown", 90)}`], ["Unit", item.unit ?? "Not reported"], ["Dependencies", item.dependencies ?? "Not reported"]]);
  }
  for (const item of exchange) {
    appendFacts(card, [
      ["Exchange", `${text(item.emitter_region_id, "unknown", 90)} → ${text(item.receiver_region_id, "unknown", 90)} · ${text(item.relation, "relation unknown", 90)}`],
      ["Concern", item.concern_summary ?? "Not reported"],
      ["Source revision", item.result_source?.revision_id ?? "Not reported"],
      ["Source hash", item.result_source?.content_sha256 ?? "Not reported"],
      ["Result", item.result_source?.summary ?? "Not reported"],
      ["Owner-reported exchange", item.exchange ?? "Not reported"],
    ]);
  }
  if (meaning.length === 8 || exchange.length === 8) card.append(make("p", "field-note", "Inspection shows at most eight matching records per kind; see complete bounded sections below."));
  el.embodiedRegionInspection.append(card);
}

function selectEmbodiedRegion(regionId) {
  state.embodied.selectedRegion = regionId;
  const snapshot = displayedEmbodiedRecord()?.snapshot;
  if (!snapshot) return;
  renderEmbodiedMap(snapshot);
  renderRegionInspection(snapshot);
}

function renderEmbodiedRoles(snapshot) {
  const roles = rolesForSnapshot(snapshot);
  const section = snapshot?.roles;
  el.embodiedRoles.replaceChildren();
  if (!roles.length) {
    emptyEmbodiedList(el.embodiedRoles, `Recorded role bindings unavailable: ${section?.reason || "the owner supplied no role bindings"}.`);
  } else {
    for (const role of roles) {
      const card = make("article", "embodied-card");
      card.append(make("h4", "", text(role.role ?? role.role_id ?? role.name ?? role.binding_id ?? "Recorded role", "Recorded role", 180)));
      appendFacts(card, [
        ["Status", role.status],
        ["State generation", role.state_generation ?? role.generation],
        ["Owner state hash", role.state_sha256],
        ["Qualified region IDs", roleRegionIds(role)],
        ["Actual region layout", role.layout],
        ["Operator rows", role.operator],
        ["Typed semantic references", role.semantic_refs],
        ["Recorded interfaces", role.interfaces],
        ["Unknowns", role.unknowns],
      ]);
      appendRawDetails(card, "Exact role binding", role);
      el.embodiedRoles.append(card);
    }
  }
  const orientation = snapshot?.orientation;
  el.embodiedOrientation.replaceChildren();
  if (!orientation || typeof orientation !== "object") {
    emptyEmbodiedList(el.embodiedOrientation, "Orientation data unavailable.");
    return;
  }
  const summary = make("article", "embodied-card");
  summary.append(make("h4", "", `Working orientation · ${text(orientation.status, "unknown", 80)}`));
  appendFacts(summary, [
    ["State generation", orientation.state_generation],
    ["Mission reference", orientation.mission_ref],
    ["Catalog reference", orientation.catalog_ref],
    ["Declared unknowns", orientation.unknowns],
    ["Coverage", sectionCoverage(orientation, "Orientation")],
  ]);
  el.embodiedOrientation.append(summary);
  for (const concern of orientation.current_concerns || []) {
    const card = make("article", "embodied-card");
    card.append(make("h4", "", `Current concern · ${text(concern.question_id, "question not identified", 120)}`));
    appendFacts(card, [
      ["Summary", concern.summary],
      ["Obligation reference", concern.obligation_ref],
      ["Assessment reference", concern.assessment_ref],
      ["Source identity", concern.source_identity],
      ["Unknowns", concern.unknowns],
    ]);
    appendRawDetails(card, "Exact current concern", concern);
    el.embodiedOrientation.append(card);
  }
  for (const continuation of orientation.continuations || []) {
    const card = make("article", "embodied-card");
    card.append(make("h4", "", "Recorded continuation"));
    appendFacts(card, [
      ["Continuation reference", continuation.continuation_ref],
      ["Source identity", continuation.source_identity],
      ["Unknowns", continuation.unknowns],
    ]);
    appendRawDetails(card, "Exact continuation", continuation);
    el.embodiedOrientation.append(card);
  }
  if (!(orientation.current_concerns?.length || orientation.continuations?.length)) {
    el.embodiedOrientation.append(make("p", "empty-note", `No current concern or continuation items were admitted. ${text(orientation.unknowns, "Unknowns not reported.", 400)}`));
  }
}

function collectRecordedReferences(value, result = [], depth = 0) {
  if (!value || typeof value !== "object" || depth > 5 || result.length >= 16) return result;
  if (typeof value.id === "string" && typeof value.kind === "string" && Number.isInteger(value.content_version)) {
    result.push(`${value.kind}:${value.id}@v${value.content_version}`);
  }
  for (const key of ["revision_id", "source_revision_id"]) {
    if (typeof value[key] === "string") result.push(`source revision ${value[key]}`);
  }
  if (Array.isArray(value)) {
    for (const item of value) collectRecordedReferences(item, result, depth + 1);
  } else {
    for (const [key, child] of Object.entries(value)) {
      if (key === "payload") continue;
      collectRecordedReferences(child, result, depth + 1);
    }
  }
  return [...new Set(result)];
}

function organizationItemFacts(item) {
  const projection = item?.projection && typeof item.projection === "object" ? item.projection : {};
  const source = { ...item, ...projection };
  const keys = [
    "field_id", "program_id", "program_ref", "branch_id", "node_id", "parent_ref",
    "parent_id", "parent_program_id", "child_refs", "child_ids", "status", "generation",
    "purpose", "question", "branch_purpose", "current_question", "current_question_ref",
    "waiting_conditions", "assumptions", "evidence_refs", "provenance_refs",
    "expected_contribution", "contribution", "obstacle", "reopen_condition",
    "continuation", "continuation_ref", "dependencies", "transition", "opportunity_count",
    "branch_ids", "region_ids", "region_refs", "role_refs", "role_bindings",
    "updated_at_ns", "transition_at_ns",
  ];
  return keys.filter((key) => source[key] !== undefined).map((key) => [key.replaceAll("_", " "), source[key]]);
}

function programReferenceKey(reference) {
  if (!reference || typeof reference !== "object"
    || typeof reference.id !== "string"
    || typeof reference.kind !== "string"
    || !Number.isInteger(reference.content_version)) return "";
  return JSON.stringify([reference.kind, reference.id, reference.content_version]);
}

function renderWorkingTopology(section) {
  const svg = el.embodiedTopology;
  const items = sectionItems(section);
  svg.replaceChildren(embodiedSvgNode(
    "desc",
    { id: "embodied-topology-description" },
    "No current typed Program references are available to draw.",
  ));
  const candidates = items.map((item) => ({
    item,
    key: programReferenceKey(item?.program_ref),
  })).filter((row) => row.key);
  const shown = candidates.slice(0, 32);
  const omittedNodes = candidates.length - shown.length;
  const nodes = new Map(shown.map((row) => [row.key, row]));
  const edges = new Map();
  let unresolved = 0;
  for (const { item, key } of candidates) {
    const parent = programReferenceKey(item.parent_ref);
    if (parent && nodes.has(parent) && nodes.has(key)) edges.set(`${parent}\u0000${key}`, [parent, key]);
    else if (parent) unresolved += 1;
    if (Array.isArray(item.child_refs)) {
      for (const childRef of item.child_refs) {
        const child = programReferenceKey(childRef);
        if (child && nodes.has(child) && nodes.has(key)) edges.set(`${key}\u0000${child}`, [key, child]);
        else unresolved += 1;
      }
    }
  }
  if (!shown.length) {
    el.embodiedTopologyNote.textContent = items.length
      ? "Program items were returned, but current typed program_ref identities were not supplied; no topology edges are inferred."
      : `Program relationship graph unavailable: ${section?.reason || "no working-organization items were admitted"}.`;
    return;
  }
  const parentByChild = new Map([...edges.values()].map(([parent, child]) => [child, parent]));
  const depths = new Map();
  const depthOf = (key, seen = new Set()) => {
    if (depths.has(key)) return depths.get(key);
    if (seen.has(key)) return 0;
    seen.add(key);
    const parent = parentByChild.get(key);
    const depth = parent && nodes.has(parent) ? Math.min(12, depthOf(parent, seen) + 1) : 0;
    depths.set(key, depth);
    return depth;
  };
  for (const key of nodes.keys()) depthOf(key);
  const groups = new Map();
  for (const row of shown) {
    const depth = depths.get(row.key) || 0;
    if (!groups.has(depth)) groups.set(depth, []);
    groups.get(depth).push(row);
  }
  const maxDepth = Math.max(...groups.keys());
  const width = Math.max(800, (maxDepth + 1) * 190 + 40);
  const height = Math.max(180, Math.max(...[...groups.values()].map((rows) => rows.length)) * 78 + 56);
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  const positions = new Map();
  for (const [depth, rows] of groups) {
    rows.forEach((row, index) => {
      positions.set(row.key, {
        x: 32 + depth * 190,
        y: 36 + ((index + 1) / (rows.length + 1)) * (height - 56),
      });
    });
  }
  const description = `Nodes are current Programs positioned by recorded parent-child depth for display only. Edges are drawn only for exact current typed references resolved inside this returned set. ${shown.length} of ${candidates.length} current nodes shown (${omittedNodes} omitted by the graph limit); ${unresolved} references do not resolve inside the displayed set.`;
  svg.querySelector("#embodied-topology-description").textContent = description;
  const defs = embodiedSvgNode("defs");
  const marker = embodiedSvgNode("marker", {
    id: "embodied-program-arrow", markerWidth: 8, markerHeight: 8, refX: 7, refY: 3, orient: "auto",
  });
  marker.append(embodiedSvgNode("path", { d: "M0,0 L0,6 L8,3 z", class: "organization-arrowhead" }));
  defs.append(marker);
  svg.append(defs);
  for (const [parent, child] of edges.values()) {
    const from = positions.get(parent), to = positions.get(child);
    if (!from || !to) continue;
    svg.append(embodiedSvgNode("line", {
      x1: from.x + 164, y1: from.y, x2: to.x - 4, y2: to.y,
      class: "organization-edge", "marker-end": "url(#embodied-program-arrow)",
    }));
  }
  for (const row of shown) {
    const point = positions.get(row.key);
    const item = row.item;
    const group = embodiedSvgNode("g", { class: "organization-node" });
    const ref = item.program_ref;
    const label = text(ref.id, "Program", 28);
    const question = text(item.question ?? item.purpose ?? item.branch_purpose, "", 30);
    const status = text(item.status, "status unavailable", 24);
    group.append(embodiedSvgNode("title", {}, `${ref.kind}:${ref.id}@v${ref.content_version}; status ${status}; question or purpose ${question || "not reported"}`));
    group.append(embodiedSvgNode("rect", { x: point.x, y: point.y - 26, width: 166, height: 52, rx: 8 }));
    group.append(embodiedSvgNode("text", { x: point.x + 8, y: point.y - 7, class: "organization-label" }, label));
    group.append(embodiedSvgNode("text", { x: point.x + 8, y: point.y + 13, class: "organization-status" }, status));
    svg.append(group);
  }
  el.embodiedTopologyNote.textContent = `${description} Edges are current parent_ref/child_refs only; node positions encode no physical location. The full admitted organization records remain listed below.`;
}
function renderWorkingOrganization(snapshot) {
  const section = snapshot?.working_organization;
  const items = sectionItems(section);

  el.embodiedWorkCount.textContent = String(items.length);
  el.embodiedWorkCount.setAttribute("aria-label", `${items.length} working organization items returned`);
  el.embodiedWorkCoverage.textContent = sectionCoverage(section, "Working organization items");
  el.embodiedOrganization.replaceChildren();
  renderWorkingTopology(section);
  if (!items.length) {
    emptyEmbodiedList(el.embodiedOrganization, `Working topology unavailable: ${section?.reason || "the entity did not admit organization items"}.`);
    return;
  }
  for (const item of items) {
    const card = make("article", "embodied-card organization-card");
    const identity = item.field_id ?? item.program_id ?? item.branch_id ?? item.node_id ?? item.id ?? item.program_ref?.id ?? item.kind ?? "Organization node";
    const type = item.node_type ?? item.type ?? item.program_ref?.kind ?? (item.program_ref ? "Program" : item.kind ?? "recorded item");
    card.append(make("h4", "", `${text(type, "Organization node", 80)} · ${text(identity, "unidentified", 160)}`));
    appendFacts(card, organizationItemFacts(item));
    const refs = collectRecordedReferences(item);
    if (refs.length) appendFacts(card, [["Resolved source/record references", refs]]);
    appendRawDetails(card, "Exact admitted organization item", item);
    el.embodiedOrganization.append(card);
  }
}

function renderEmbodiedSemantics(snapshot) {
  const section = snapshot?.semantics;
  const items = sectionItems(section);
  el.embodiedSemanticsCoverage.textContent = sectionCoverage(section, "Meaning references");
  el.embodiedSemantics.replaceChildren();
  if (!items.length) {
    emptyEmbodiedList(el.embodiedSemantics, `Meaning references unavailable: ${section?.reason || "no semantic records were admitted"}.`);
    return;
  }
  for (const item of items) {
    const card = make("article", "embodied-card");
    const identity = item.record_id ?? item.variable_id ?? item.chart_id ?? item.id ?? "reference";
    const recordKind = item.record_kind ?? item.kind ?? "meaning";
    const version = item.content_version ?? item.version;
    card.append(make("h4", "", `${text(recordKind, "meaning", 80)} · ${text(identity, "reference", 180)}${version === undefined ? "" : ` · v${version}`}`));
    appendFacts(card, [
      ["Region", item.region_id],
      ["Value kind", item.value_kind],
      ["Unit", item.unit],
      ["Frame", item.frame],
      ["Status", item.status],
      ["Epistemic kind", item.epistemic_kind],
      ["Scope", item.scope],
      ["Dependencies", item.dependencies],
    ]);
    appendRawDetails(card, "Exact admitted meaning record", item);
    el.embodiedSemantics.append(card);
  }
}

function renderEmbodiedExchange(snapshot) {
  const section = snapshot?.exchange_meaning;
  const items = sectionItems(section);
  el.embodiedExchange.replaceChildren();
  if (!items.length) {
    emptyEmbodiedList(el.embodiedExchange, `Source-bound exchange unavailable: ${section?.reason || "no verified exchange references were admitted"}.`);
    return;
  }
  for (const item of items) {
    const card = make("article", "embodied-card exchange-card");
    const interfaceName = item.interface ?? `${item.emitter_region_id ?? "?"} → ${item.receiver_region_id ?? "?"}`;
    card.append(make("h4", "", `${text(item.relation, "Recorded exchange", 100)} · ${text(interfaceName, "interface", 180)}`));
    appendFacts(card, [
      ["Emitter region", item.emitter_region_id],
      ["Receiver region", item.receiver_region_id],
      ["Concern summary", item.concern_summary],
      ["Concern reference", item.concern_ref],
      ["Assessment reference", item.assessment_ref],
      ["Appraisal reference", item.last_appraisal_ref],
      ["Archived result source revision", item.result_source?.revision_id],
      ["Archived result source hash", item.result_source?.content_sha256],
      ["Archived result status", item.result_source?.status],
      ["Result summary", item.result_source?.summary],
      ["Owner-reported exchange", item.exchange],
      ["Recalled memory references", item.recalled_memories?.map((entry) => ({
        record_ref: entry.record_ref,
        role: entry.role,
        source_revision_ids: entry.source_revision_ids,
        result_status: entry.result_status,
        result_summary: entry.result_summary,
      }))],
    ]);
    appendRawDetails(card, "Exact source-bound exchange record", item);
    el.embodiedExchange.append(card);
  }
}

function appendMeasurementRows(container, prefix, object, depth = 0) {
  if (!object || typeof object !== "object" || depth > 4) return;
  for (const [key, value] of Object.entries(object)) {
    if (value && typeof value === "object") {
      appendMeasurementRows(container, `${prefix}.${key}`, value, depth + 1);
    } else if (typeof value === "number" && Number.isFinite(value)) {
      const row = make("div", "measurement-row");
      const unit = typeof object.unit === "string" ? ` ${object.unit}` : " · unit not supplied";
      row.append(make("code", "", `${prefix}.${key}`), make("span", "", `${value}${unit}`));
    }
  }
}

function renderEmbodiedMeasurements(snapshot) {
  const container = el.embodiedMeasurements;
  container.replaceChildren();
  let count = 0;
  const workspace = snapshot?.circulation?.value?.workspace;
  if (workspace && typeof workspace === "object") {
    const group = make("div", "measurement-group");
    group.append(make("h4", "", "Owner resonance workspace"));
    const before = group.childNodes.length;
    appendMeasurementRows(group, "circulation.value.workspace", workspace);
    count += Math.max(0, group.childNodes.length - before);
    container.append(group);
  }
  for (const region of sectionItems(snapshot?.regions)) {
    const values = Object.fromEntries(Object.entries(region).filter(([key, value]) => EMBODIED_MEASURE_KEYS.has(key) && typeof value === "number" && Number.isFinite(value)));
    if (!Object.keys(values).length) continue;
    const group = make("div", "measurement-group");
    group.append(make("h4", "", `Region ${text(region.region_id ?? region.computer_id ?? "unknown", "unknown", 140)}`));
    const before = group.childNodes.length;
    appendMeasurementRows(group, `regions.${region.region_id ?? region.computer_id ?? "unknown"}`, values);
    count += Math.max(0, group.childNodes.length - before);
    container.append(group);
  }
  for (const [regionalIndex, regional] of (snapshot?.circulation?.value?.regional || []).entries()) {
    const spectrum = regional?.spectrum;
    if (!spectrum || typeof spectrum !== "object") continue;
    const group = make("div", "measurement-group");
    group.append(make("h4", "", `Spectrum · ${text(regional.computer_id ?? regionalIndex, "unknown", 100)}`));
    const before = group.childNodes.length;
    appendMeasurementRows(group, `circulation.value.regional.${regional.computer_id ?? regionalIndex}.spectrum`, spectrum);
    count += Math.max(0, group.childNodes.length - before);
    container.append(group);
  }
  if (!count) emptyEmbodiedList(container, `Quantitative measurements unavailable: ${snapshot?.circulation?.reason || "the admitted snapshot contains no finite measurement values"}.`);
}

function collectEmbodiedMetrics(snapshot) {
  const result = new Map();
  const add = (prefix, object, depth = 0) => {
    if (!object || typeof object !== "object" || depth > 5) return;
    for (const [key, value] of Object.entries(object)) {
      const path = `${prefix}.${key}`;
      if (value && typeof value === "object" && !Array.isArray(value)) add(path, value, depth + 1);
      else if (typeof value === "number" && Number.isFinite(value) && !/(^|_)(id|version|generation|time_ns)$/i.test(key)) {
        result.set(path, { value, unit: typeof object.unit === "string" ? object.unit : null });
      }
    }
  };
  for (const region of sectionItems(snapshot?.regions)) {
    for (const key of EMBODIED_MEASURE_KEYS) {
      if (typeof region?.[key] === "number" && Number.isFinite(region[key])) {
        result.set(`regions.${region.region_id ?? "unknown"}.${key}`, { value: region[key], unit: region.unit ?? null });
      }
    }
  }
  add("circulation.value.workspace", snapshot?.circulation?.value?.workspace);
  for (const [index, row] of (snapshot?.circulation?.value?.regional || []).entries()) {
    add(`circulation.value.regional.${row?.computer_id ?? index}.spectrum`, row?.spectrum);
  }
  for (const [index, item] of sectionItems(snapshot?.exchange_meaning).entries()) {
    add(`exchange_meaning.items.${item?.interface ?? index}.exchange`, item?.exchange);
  }
  return result;
}

function renderEmbodiedComparison() {
  const beforeIndex = Number(el.embodiedCompareBefore.value);
  const afterIndex = Number(el.embodiedCompareAfter.value);
  const before = state.embodied.captures[beforeIndex];
  const after = state.embodied.captures[afterIndex];
  const container = el.embodiedComparison;
  container.replaceChildren();
  if (!before || !after) {
    emptyEmbodiedList(container, "Select two captured snapshots to compare.");
    return;
  }
  if (beforeIndex === afterIndex) {
    emptyEmbodiedList(container, "Choose two different captures.");
    return;
  }
  const beforeLayout = embodiedLayoutIdentity(before.snapshot);
  const afterLayout = embodiedLayoutIdentity(after.snapshot);
  if (beforeLayout && afterLayout && beforeLayout !== afterLayout) {
    emptyEmbodiedList(container, "The declared layout identities differ. Numeric deltas are withheld because these captures are not directly comparable.");
    return;
  }
  const qualification = beforeLayout && afterLayout
    ? `Same declared layout identity: ${beforeLayout}.`
    : "A matching declared layout identity could not be confirmed; same-key differences below are raw reports, not a claim of physical comparability.";
  container.append(make("p", "field-note", qualification));
  const earlier = collectEmbodiedMetrics(before.snapshot);
  const later = collectEmbodiedMetrics(after.snapshot);
  const paths = [...new Set([...earlier.keys(), ...later.keys()])].sort().slice(0, 80);
  const table = make("div", "embodied-delta-table");
  table.setAttribute("role", "table");
  table.setAttribute("aria-label", "Reported numeric differences between captured snapshots");
  const header = make("div", "delta-row delta-heading");
  header.setAttribute("role", "row");
  for (const label of ["Reported measurement", "Earlier", "Later", "Delta"]) {
    const cell = make("span", "", label);
    cell.setAttribute("role", "columnheader");
    header.append(cell);
  }
  table.append(header);
  for (const path of paths) {
    const a = earlier.get(path), b = later.get(path);
    const unitsMatch = a && b && a.unit === b.unit;
    const row = make("div", "delta-row");
    row.setAttribute("role", "row");
    const label = make("code", "", path);
    label.setAttribute("role", "cell");
    const earlierValue = make("span", "", a ? `${a.value}${a.unit ? ` ${a.unit}` : " (unit not supplied)"}` : "missing");
    const laterValue = make("span", "", b ? `${b.value}${b.unit ? ` ${b.unit}` : " (unit not supplied)"}` : "missing");
    const delta = make("span", "", a && b
      ? unitsMatch ? `${b.value - a.value}${a.unit ? ` ${a.unit}` : " (unit not supplied)"}`
        : "not comparable — declared units differ"
      : "not comparable — value missing");
    for (const cell of [earlierValue, laterValue, delta]) cell.setAttribute("role", "cell");
    row.append(label, earlierValue, laterValue, delta);
    table.append(row);
  }
  if (!paths.length) table.append(make("p", "empty-note", "No shared finite numeric measurements were captured."));
  container.append(table);
  container.append(make("p", "field-note", `Earlier: generation ${embodiedFieldValue(before.snapshot.generation)} · ${shortHash(before.snapshot.state_sha256)}. Later: generation ${embodiedFieldValue(after.snapshot.generation)} · ${shortHash(after.snapshot.state_sha256)}. Unknown units remain unknown.`));
}

function renderEmbodiedTimeline() {
  const captures = state.embodied.captures;
  const timedReplayAvailable = embodiedReplayHasTiming(captures);
  el.embodiedTimeline.replaceChildren();
  if (!captures.length) {
    emptyEmbodiedList(el.embodiedTimeline, "No snapshots captured in this session.");
  } else {
    for (const [index, capture] of captures.entries()) {
      const button = make("button", "timeline-capture");
      button.type = "button";
      button.dataset.captureIndex = String(index);
      button.setAttribute("aria-current", String(state.embodied.replayIndex === index));
      const entityTime = embodiedTimestamp(capture.snapshot);
      button.textContent = `${index + 1} · generation ${embodiedFieldValue(capture.snapshot.generation)} · entity ${entityTime === null ? "time unknown" : dateLabel(entityTime)} · viewed ${dateLabel(capture.capturedAt)} · ${shortHash(capture.snapshot.state_sha256)}`;
      el.embodiedTimeline.append(button);
    }
  }
  const enough = captures.length > 1;
  el.embodiedPrevious.disabled = !enough;
  el.embodiedNext.disabled = !enough;
  el.embodiedPlay.disabled = !enough || state.embodied.reduceMotion || !timedReplayAvailable;
  el.embodiedPlay.textContent = state.embodied.replayPlaying ? "Stop replay" : "Play replay";
  el.embodiedReplayStatus.textContent = state.embodied.replayPlaying
    ? `Playing successive captured states at entity-capture time gaps · ${Number.isInteger(state.embodied.replayIndex) ? state.embodied.replayIndex + 1 : 1} of ${captures.length} · no interpolation.`
    : Number.isInteger(state.embodied.replayIndex)
      ? `Viewing capture ${state.embodied.replayIndex + 1} of ${captures.length}.`
      : !enough
        ? captures.length
          ? "Capture a second distinct snapshot to enable replay."
          : "No snapshots captured; replay needs two distinct, timestamped snapshots."
        : state.embodied.reduceMotion
          ? "Automatic replay is off while reduced motion is enabled; use Previous and Next."
          : !timedReplayAvailable
            ? "Automatic replay needs strictly increasing entity capture times; use Previous and Next to inspect captures without invented timing."
            : "Replay follows recorded entity-capture time gaps; no state interpolation is applied.";

  const previousBefore = el.embodiedCompareBefore.value;
  const previousAfter = el.embodiedCompareAfter.value;
  const fill = (select, preferred, fallback) => {
    select.replaceChildren();
    for (const [index, capture] of captures.entries()) {
      const option = make("option", "", `${index + 1} · generation ${embodiedFieldValue(capture.snapshot.generation)} · ${dateLabel(capture.capturedAt)}`);
      option.value = String(index);
      select.append(option);
    }
    if (!captures.length) {
      const option = make("option", "", "Capture snapshots first");
      option.value = "";
      select.append(option);
    } else {
      select.value = captures.some((_, index) => String(index) === preferred)
        ? preferred : String(Math.max(0, Math.min(fallback, captures.length - 1)));
    }
    select.disabled = captures.length < 2;
  };
  fill(el.embodiedCompareBefore, previousBefore, 0);
  fill(el.embodiedCompareAfter, previousAfter, captures.length - 1);
  el.embodiedCompare.disabled = captures.length < 2;
  if (captures.length < 2) emptyEmbodiedList(el.embodiedComparison, "Capture at least two distinct admitted states to compare.");
}

function updateEmbodiedAge() {
  const record = displayedEmbodiedRecord();
  if (!record) {
    el.embodiedAge.textContent = state.embodied.error ? "Unavailable" : "Unknown";
    return;
  }
  const timestamp = embodiedTimestamp(record.snapshot);
  if (timestamp !== null) {
    el.embodiedAge.textContent = `${ageLabel(Date.now() - timestamp)} since entity capture`;
  } else if (Number.isFinite(record.receivedAt ?? record.capturedAt)) {
    const at = record.receivedAt ?? record.capturedAt;
    el.embodiedAge.textContent = `Entity age unavailable · viewer received ${ageLabel(Date.now() - at)} ago`;
  } else {
    el.embodiedAge.textContent = "Entity age unavailable";
  }
}

function renderEmbodied() {
  const record = displayedEmbodiedRecord();
  const snapshot = record?.snapshot;
  const latest = state.embodied.latest;
  const frozen = Boolean(state.embodied.frozenSnapshot);
  const replaying = Number.isInteger(state.embodied.replayIndex);
  el.embodiedCapture.disabled = !latest;
  el.embodiedFreeze.disabled = !latest && !frozen;
  el.embodiedFreeze.textContent = frozen ? "Resume live view" : "Freeze live view";
  el.embodiedFreeze.setAttribute("aria-pressed", String(frozen));
  el.embodiedState.dataset.tone = state.embodied.error ? "warn" : "";
  if (!snapshot) {
    el.embodiedState.textContent = state.embodied.error ? "Unavailable" : "Waiting for a snapshot";
    el.embodiedGeneration.textContent = "Unknown";
    el.embodiedHash.textContent = "Unknown";
    el.embodiedLayout.textContent = "Unknown";
    el.embodiedCapturedAt.textContent = "Unknown";
    el.embodiedFieldTime.textContent = "Unknown";
    el.embodiedCoverage.textContent = "Unknown";
    el.embodiedPayload.textContent = "No snapshot is available.";
    emptyEmbodiedList(el.embodiedOrganization, "Working organization unavailable until a snapshot is received.");
    renderWorkingTopology({});
    emptyEmbodiedList(el.embodiedSemantics, "Meaning references unavailable until a snapshot is received.");
    emptyEmbodiedList(el.embodiedExchange, "Source-bound exchange unavailable until a snapshot is received.");
    emptyEmbodiedList(el.embodiedMeasurements, "Quantitative measurements unavailable until a snapshot is received.");
    renderEmbodiedRegions({});
    renderEmbodiedRoles({});
    renderEmbodiedMap({});
    renderRegionInspection({});
    renderFieldActivity();
    renderEmbodiedTimeline();
    updateEmbodiedAge();
    return;
  }
  const status = snapshot.status ?? "unknown";
  el.embodiedState.textContent = replaying ? "Replay snapshot" : frozen ? "Frozen snapshot" : status;
  if (state.embodied.error) el.embodiedState.textContent += " · live refresh unavailable";
  el.embodiedGeneration.textContent = embodiedFieldValue(snapshot.generation);
  el.embodiedHash.textContent = shortHash(snapshot.state_sha256);
  const layout = snapshot?.layout;
  const layoutValue = layout?.value ?? {};
  const coordinateLayout = layoutValue?.coordinate_layout ?? {};
  const layoutParts = [
    `status ${layout?.status ?? "unavailable"}`,
    coordinateLayout.layout_identity === undefined ? null : `identity ${embodiedFieldValue(coordinateLayout.layout_identity, 120)}`,
    layoutValue.declared_variable_count === undefined ? null : `${layoutValue.declared_variable_count} declared variables`,
    coordinateLayout.coordinate_count === undefined ? null : `${coordinateLayout.coordinate_count} coordinate entries`,
    coordinateLayout.pools === undefined ? null : `pools ${embodiedFieldValue(coordinateLayout.pools, 100)}`,
    coordinateLayout.ports_per_pool === undefined ? null : `ports per pool ${embodiedFieldValue(coordinateLayout.ports_per_pool, 100)}`,
    coordinateLayout.topology === undefined ? null : `topology ${embodiedFieldValue(coordinateLayout.topology, 160)}`,
    layout?.reason ? `reason: ${text(layout.reason, "", 160)}` : null,
  ].filter(Boolean);
  el.embodiedLayout.textContent = layoutParts.join(" · ");
  const captureTime = embodiedTimestamp(snapshot);
  el.embodiedCapturedAt.textContent = captureTime === null ? "Not reported by entity." : dateLabel(captureTime);
  const workspace = snapshot?.circulation?.value?.workspace;
  el.embodiedFieldTime.textContent = workspace?.field_time_step === undefined
    ? "Unavailable"
    : embodiedFieldValue(workspace.field_time_step);
  const coverageSections = ["layout", "regions", "roles", "orientation", "semantics", "exchange_meaning", "working_organization", "circulation"];
  el.embodiedCoverage.textContent = coverageSections
    .map((key) => sectionCoverage(snapshot[key], key))
    .join(" ");
  const viewTime = record.capturedAt ? ` Viewing a local capture from ${dateLabel(record.capturedAt)}.` : "";
  const captureMatches = snapshot?.working_organization?.capture_matches_owner;
  const orgNote = captureMatches === false
    ? " Working-organization capture is not hash-matched to the owner state."
    : captureMatches === true
      ? " Working-organization capture reports an owner-state match."
      : " Working-organization atomicity is not reported.";
  setEmbodiedMessage(
    `${frozen ? "View frozen; live source polling continues." : replaying ? "Replaying a captured snapshot; live source polling continues." : "Showing the latest returned snapshot."}${state.embodied.error ? ` Last live refresh failed: ${text(state.embodied.error.message, "unavailable", 260)}` : ""}${orgNote}${viewTime}`,
    state.embodied.error ? "warn" : "",
  );
  el.embodiedPayload.textContent = JSON.stringify(snapshot, null, 2);
  renderEmbodiedMap(snapshot);
  renderEmbodiedRegions(snapshot);
  renderRegionInspection(snapshot);
  renderEmbodiedRoles(snapshot);
  renderEmbodiedSemantics(snapshot);
  renderEmbodiedExchange(snapshot);
  renderEmbodiedMeasurements(snapshot);
  renderFieldActivity();
  renderEmbodiedTimeline();
  updateEmbodiedAge();
}

function scheduleEmbodiedPoll() {
  clearTimeout(state.embodied.timer);
  state.embodied.timer = null;
  if (state.closing || document.visibilityState === "hidden" || !state.embodied.visible) return;
  state.embodied.timer = setTimeout(() => { void refreshEmbodied(); }, EMBODIED_POLL_MS);
}

async function refreshEmbodied() {
  if (state.closing || state.embodied.requestPending) return;
  state.embodied.requestPending = true;
  el.embodiedRefresh.disabled = true;
  try {
    const snapshot = await requestJson("/v1/embodied-field");
    if (!snapshot || typeof snapshot !== "object" || snapshot.schema !== "cassifi.embodied-field.v1") {
      throw new Error("The entity did not return a supported embodied-field snapshot.");
    }
    state.embodied.latest = snapshot;
    state.embodied.receivedAt = Date.now();
    admitFieldObservation(snapshot);
    state.embodied.error = null;
    renderEmbodied();
  } catch (error) {
    state.embodied.error = error;
    renderEmbodied();
    if (!state.embodied.latest) setEmbodiedMessage(`Field snapshot unavailable: ${text(error?.message, "entity did not return a snapshot", 300)}`, "warn");
  } finally {
    state.embodied.requestPending = false;
    el.embodiedRefresh.disabled = false;
    scheduleEmbodiedPoll();
  }
}

function captureEmbodiedSnapshot() {
  const latest = state.embodied.latest;
  if (!latest) return null;
  const identity = embodiedIdentity(latest);
  const previous = state.embodied.captures.findIndex((capture) => capture.identity === identity);
  if (previous >= 0) {
    setEmbodiedMessage("This admitted owner/program generation is already captured in this session; no duplicate snapshot was added.", "warn");
    return state.embodied.captures[previous];
  }
  const capture = {
    snapshot: JSON.parse(JSON.stringify(latest)),
    receivedAt: state.embodied.receivedAt,
    capturedAt: Date.now(),
    identity,
  };
  state.embodied.captures.push(capture);
  if (state.embodied.captures.length > EMBODIED_CAPTURE_LIMIT) state.embodied.captures.shift();
  return capture;
}

function handleEmbodiedCapture() {
  if (state.embodied.replayPlaying) stopEmbodiedReplay();
  const identity = state.embodied.latest ? embodiedIdentity(state.embodied.latest) : null;
  const alreadyCaptured = identity !== null && state.embodied.captures.some((capture) => capture.identity === identity);
  const capture = captureEmbodiedSnapshot();
  if (!capture) {
    setEmbodiedMessage("No admitted snapshot is available to capture.", "warn");
    return;
  }
  state.embodied.replayIndex = null;
  renderEmbodied();
  if (alreadyCaptured) {
    setEmbodiedMessage("This admitted owner/program generation is already captured in this session; no duplicate snapshot was added.", "warn");
    return;
  }
  setEmbodiedMessage(`Captured generation ${embodiedFieldValue(capture.snapshot.generation)} locally at ${dateLabel(capture.capturedAt)}. This capture is session-only and did not write to the owner.`);
}

function toggleEmbodiedFreeze() {
  if (state.embodied.replayPlaying) stopEmbodiedReplay();
  if (state.embodied.frozenSnapshot) {
    state.embodied.frozenSnapshot = null;
    state.embodied.replayIndex = null;
    renderEmbodied();
    return;
  }
  const capture = captureEmbodiedSnapshot();
  if (!capture) {
    setEmbodiedMessage("No admitted snapshot is available to freeze.", "warn");
    return;
  }
  state.embodied.frozenSnapshot = {
    snapshot: JSON.parse(JSON.stringify(capture.snapshot)),
    receivedAt: capture.receivedAt,
    capturedAt: capture.capturedAt,
    identity: capture.identity,
  };
  state.embodied.replayIndex = null;
  renderEmbodied();
}

function setEmbodiedReplayIndex(index) {
  const captures = state.embodied.captures;
  if (captures.length < 2) return;
  const bounded = Math.max(0, Math.min(captures.length - 1, index));
  state.embodied.frozenSnapshot = null;
  state.embodied.replayIndex = bounded;
  renderEmbodied();
}

function stopEmbodiedReplay() {
  clearTimeout(state.embodied.replayTimer);
  state.embodied.replayTimer = null;
  state.embodied.replayPlaying = false;
  renderEmbodiedTimeline();
}

function scheduleEmbodiedReplay() {
  const captures = state.embodied.captures;
  const index = state.embodied.replayIndex;
  if (!state.embodied.replayPlaying || !Number.isInteger(index)) return;
  if (index >= captures.length - 1) {
    stopEmbodiedReplay();
    return;
  }
  const delay = embodiedReplayDelay(captures[index], captures[index + 1]);
  if (delay === null) {
    stopEmbodiedReplay();
    setEmbodiedMessage("Automatic replay stopped because entity capture times are unavailable or out of order.", "warn");
    return;
  }
  state.embodied.replayTimer = setTimeout(() => {
    if (document.visibilityState === "hidden" || state.closing) {
      stopEmbodiedReplay();
      return;
    }
    const next = index + 1;
    setEmbodiedReplayIndex(next);
    if (next >= captures.length - 1) stopEmbodiedReplay();
    else scheduleEmbodiedReplay();
  }, delay);
}

function toggleEmbodiedReplay() {
  if (state.embodied.replayPlaying) {
    stopEmbodiedReplay();
    return;
  }
  if (state.embodied.reduceMotion || !embodiedReplayHasTiming(state.embodied.captures)) return;
  if (!Number.isInteger(state.embodied.replayIndex) || state.embodied.replayIndex >= state.embodied.captures.length - 1) setEmbodiedReplayIndex(0);
  state.embodied.replayPlaying = true;
  renderEmbodiedTimeline();
  scheduleEmbodiedReplay();
}

function handleEmbodiedTimelineClick(event) {
  const button = event.target.closest("button[data-capture-index]");
  if (!button) return;
  stopEmbodiedReplay();
  setEmbodiedReplayIndex(Number(button.dataset.captureIndex));
}

function handleEmbodiedReduceMotion() {
  state.embodied.reduceMotion = el.embodiedReducedMotion.checked;
  document.querySelector("#embodied-field").dataset.reducedMotion = String(state.embodied.reduceMotion);
  if (state.embodied.reduceMotion && state.embodied.replayPlaying) stopEmbodiedReplay();
  renderEmbodiedTimeline();
}


function onVisibilityChange() {
  if (document.visibilityState === "hidden") {
    clearFrameTimer();
    clearInterval(state.embodied.ageTimer);
    state.embodied.ageTimer = null;
    clearTimeout(state.embodied.timer);
    state.embodied.timer = null;
    if (state.embodied.replayPlaying) stopEmbodiedReplay();
  } else {
    if (state.embodied.ageTimer === null) state.embodied.ageTimer = window.setInterval(updateEmbodiedAge, 1000);
    if (isSessionActive()) startFrameTimer();
    if (state.embodied.visible) void refreshEmbodied();
  }
}

function initializeEmbodiedViewer() {
  document.querySelector("#embodied-field").dataset.palette = state.embodied.palette;
  el.embodiedReducedMotion.checked = state.embodied.reduceMotion;
  document.querySelector("#embodied-field").dataset.reducedMotion = String(state.embodied.reduceMotion);
  el.embodiedPalette.addEventListener("change", () => {
    document.querySelector("#embodied-field").dataset.palette = el.embodiedPalette.value;
    state.embodied.palette = el.embodiedPalette.value;
  });
  el.embodiedRefresh.addEventListener("click", () => { void refreshEmbodied(); });
  el.embodiedCapture.addEventListener("click", handleEmbodiedCapture);
  el.embodiedFreeze.addEventListener("click", toggleEmbodiedFreeze);
  el.embodiedReducedMotion.addEventListener("change", handleEmbodiedReduceMotion);
  el.embodiedRegionSelect.addEventListener("change", () => selectEmbodiedRegion(el.embodiedRegionSelect.value));
  const inspectMapRegion = (event) => {
    const regionId = event.target?.dataset?.regionId;
    if (typeof regionId === "string") selectEmbodiedRegion(regionId);
  };
  el.embodiedMap.addEventListener("click", inspectMapRegion);
  el.embodiedMap.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    if (typeof event.target?.dataset?.regionId !== "string") return;
    event.preventDefault();
    inspectMapRegion(event);
  });
  el.embodiedTimeline.addEventListener("click", handleEmbodiedTimelineClick);
  el.embodiedPrevious.addEventListener("click", () => {
    if (state.embodied.replayPlaying) stopEmbodiedReplay();
    setEmbodiedReplayIndex((Number.isInteger(state.embodied.replayIndex) ? state.embodied.replayIndex : state.embodied.captures.length) - 1);
  });
  el.embodiedNext.addEventListener("click", () => {
    if (state.embodied.replayPlaying) stopEmbodiedReplay();
    setEmbodiedReplayIndex((Number.isInteger(state.embodied.replayIndex) ? state.embodied.replayIndex : -1) + 1);
  });
  el.embodiedPlay.addEventListener("click", toggleEmbodiedReplay);
  el.embodiedCompare.addEventListener("click", renderEmbodiedComparison);
  el.embodiedCompareBefore.addEventListener("change", renderEmbodiedComparison);
  el.embodiedCompareAfter.addEventListener("change", renderEmbodiedComparison);
  if (document.visibilityState !== "hidden") state.embodied.ageTimer = window.setInterval(updateEmbodiedAge, 1000);
  if (typeof window.IntersectionObserver === "function") {
    state.embodied.observer = new IntersectionObserver((entries) => {
      state.embodied.visible = entries.some((entry) => entry.isIntersecting);
      if (state.embodied.visible && document.visibilityState !== "hidden") {
        void refreshEmbodied();
      } else if (!state.embodied.visible) {
        clearTimeout(state.embodied.timer);
        state.embodied.timer = null;
      }
    });
    state.embodied.observer.observe(document.querySelector("#embodied-field"));
  } else {
    state.embodied.visible = true;
    if (document.visibilityState !== "hidden") void refreshEmbodied();
  }
}

function onPageHide() {
  state.closing = true;
  clearFrameTimer();
  clearTimeout(state.embodied.timer);
  clearInterval(state.embodied.replayTimer);
  clearInterval(state.embodied.ageTimer);
  try { state.controller.abort(); } catch { /* The page is already leaving. */ }
  revokeAllPreviews();
  state.embodied.observer?.disconnect();
  revokeCurrentFrame();
  revokePinned();
}

function initialize() {
  el.connectForm.addEventListener("submit", (event) => { void connect(event); });
  el.disconnect.addEventListener("click", () => {
    if (isSessionActive()) return;
    resetConnection();
    state.status = null;
    state.sessionStarted = false;
    el.connectionMessage.textContent = "Disconnected from the local entity.";
  });
  el.refreshSources.addEventListener("click", () => { void refreshSources(); });
  el.sourceGrid.addEventListener("change", handleSourceChange);
  el.sourceGrid.addEventListener("click", clickAction);
  el.consent.addEventListener("change", updateAgreement);
  el.purpose.addEventListener("input", resetConsent);
  for (const radio of $$('input[name="session-mode"]')) radio.addEventListener("change", handleModeChange);
  el.startButton.addEventListener("click", () => { void startSession(); });
  el.modeToggle.addEventListener("click", () => { void toggleMode(); });
  el.pauseResume.addEventListener("click", () => { void togglePause(); });
  el.finish.addEventListener("click", askFinish);
  el.pinMoment.addEventListener("click", pinCurrentFrame);
  el.closeMoment.addEventListener("click", () => revokePinned());
  el.annotationOverlay.addEventListener("click", markPoint);
  el.annotationOverlay.addEventListener("pointerdown", startRegion);
  el.annotationOverlay.addEventListener("pointermove", moveRegion);
  el.annotationOverlay.addEventListener("pointerup", finishRegion);
  el.annotationOverlay.addEventListener("pointercancel", finishRegion);
  for (const radio of $$('input[name="annotation-kind"]')) {
    radio.addEventListener("change", () => {
      el.annotationControls.dataset.annotation = annotationKind();
      el.annotationHint.textContent = annotationKind() === "point"
        ? "Click the pinned image to place a point, or use the coordinate fields below."
        : "Drag across a region, or enter X, Y, width, and height with the keyboard.";
      updateAnnotationFromInputs();
    });
  }
  [el.coordX, el.coordY, el.coordWidth, el.coordHeight].forEach((input) => input.addEventListener("input", updateAnnotationFromInputs));
  el.momentInstruction.addEventListener("input", updateMomentEnabled);
  el.momentKind.addEventListener("change", toggleMethodFields);
  for (const input of [...methodInputs(), el.methodParameters]) input.addEventListener("input", updateMomentEnabled);
  el.sendMoment.addEventListener("click", () => { void submitMoment(); });
  el.lessons.addEventListener("click", clickAction);
  el.suggestions.addEventListener("click", clickAction);
  el.discardRecent.addEventListener("click", discardRecentDialog);
  el.stopProcessing.addEventListener("click", stopProcessingDialog);
  el.dialog.addEventListener("click", (event) => {
    if (event.target === el.dialog) closeDialog();
  });
  document.addEventListener("visibilitychange", onVisibilityChange);
  window.addEventListener("pagehide", onPageHide, { once: true });
  state.mode = selectedMode();
  initializeEmbodiedViewer();
  updateAgreement();
  renderSources();
  renderSession();
  renderDetails();
}

initialize();
