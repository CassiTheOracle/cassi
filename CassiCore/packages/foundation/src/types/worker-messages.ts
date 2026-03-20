/**
 * Shared message types for channel worker threads.
 *
 * These replace the locally-defined types that were duplicated
 * in each worker implementation.
 */


/** Base interface for all messages from host (daemon) to worker */
export interface HostToWorkerMessage {
  type: string
  [key: string]: unknown
}

/** Init message - sent when worker starts */
export interface HostInitMessage extends HostToWorkerMessage {
  type: 'init'
  config: Record<string, unknown>
}

/** Config update message */
export interface HostConfigUpdateMessage extends HostToWorkerMessage {
  type: 'config:update'
  config: Record<string, unknown>
}

/** Message payload from host to worker (streaming responses) */
export interface HostMessagePayload {
  sessionId: string
  content: string
  done?: boolean
  parse_mode?: 'MarkdownV2' | 'HTML'
}

/** Message from host to worker */
export interface HostMessageMessage extends HostToWorkerMessage {
  type: 'message'
  payload: HostMessagePayload
}

/** Status update from host to worker */
export interface HostStatusMessage extends HostToWorkerMessage {
  type: 'status'
  payload: {
    sessionId: string
    text: string
    type?: string
  }
}

/** Shutdown request from host */
export interface HostShutdownMessage extends HostToWorkerMessage {
  type: 'shutdown'
}

/** Discriminated union of all host-to-worker message types */
export type HostMessage =
  | HostInitMessage
  | HostConfigUpdateMessage
  | HostMessageMessage
  | HostStatusMessage
  | HostShutdownMessage


/** Base interface for all messages from worker to host (daemon) */
export interface WorkerToHostMessage {
  type: string
  [key: string]: unknown
}

/** Worker ready announcement */
export interface WorkerReadyMessage extends WorkerToHostMessage {
  type: 'ready'
}

/** Worker message payload (forwarding user input) */
export interface WorkerMessagePayload {
  sessionId: string
  content: string
  attachments?: Array<{
    data: string
    mediaType: string
    label?: string
  }>
}

/** User message from worker to host */
export interface WorkerUserMessage extends WorkerToHostMessage {
  type: 'message'
  payload: WorkerMessagePayload
}

/** Reasoning/thinking signal from worker */
export interface WorkerReasoningMessage extends WorkerToHostMessage {
  type: 'reasoning'
  payload: {
    sessionId: string
    text: string
    model?: string
    timestamp?: number
  }
}

/** Signal detection from worker */
export interface WorkerSignalMessage extends WorkerToHostMessage {
  type: 'signal'
  payload: {
    sessionId: string
    signalType: string
    content: string
  }
}

/** Error from worker */
export interface WorkerErrorMessage extends WorkerToHostMessage {
  type: 'error'
  message: string
}

/** Log message from worker */
export interface WorkerLogMessage extends WorkerToHostMessage {
  type: 'log'
  payload: { level: string; message: string; meta?: Record<string, unknown> }
}

/** Mid-loop injection from worker to host (e.g., mid-turn user messages) */
export interface WorkerInjectMessage extends WorkerToHostMessage {
  type: 'inject'
  payload: {
    sessionId: string
    content: string
    /** Origin of the injection (e.g., 'user', 'opencode-worker') */
    source?: string
  }
}

/** Tool usage event from external agent (e.g., OpenCode) */
export interface WorkerToolUpdateMessage extends WorkerToHostMessage {
  type: 'tool_update'
  payload: {
    sessionId: string
    toolName: string
    status: string
    /** Full part data from the external agent's event stream */
    partData?: Record<string, unknown>
  }
}

export type WorkerMessage =
  | WorkerReadyMessage
  | WorkerUserMessage
  | WorkerReasoningMessage
  | WorkerSignalMessage
  | WorkerInjectMessage
  | WorkerToolUpdateMessage
  | WorkerErrorMessage
  | WorkerLogMessage


/** @deprecated Use HostToWorkerMessage */
export type HostToWorker = HostToWorkerMessage
/** @deprecated Use WorkerToHostMessage */
export type WorkerToHost = WorkerToHostMessage
