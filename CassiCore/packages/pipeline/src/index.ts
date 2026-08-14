/**
 * CassiCore Session Pipeline
 * 
 * A clean, maintainable architecture for session management
 */

// Session Management
export {
  // Core classes
  SessionManager,
  SQLiteSessionStore,
  MemorySessionStore,
  
  // Factory functions
  createSessionManager,
  createDefaultSQLiteStore,
  createTestStore,
  
  // Errors
  SessionError,
  SessionNotFoundError,
  StoreError,
  TurnProcessingError,
  ProviderNotFoundError
} from './session/index.js';

export type {
  // Core types
  SessionState,
  Message,
  ToolCall,
  ToolResult,
  TurnRequest,
  TurnResult,
  TurnMetadata,
  ToolExecution,
  SessionFilter,
  TurnData,
  ProcessorResult,
  IntelligenceContext,
  ISessionStore,
  ILogger,
  IToolExecutor,
  ToolContext,
  GetOrCreateOptions,
  StreamEventType,
  StreamEventCallback
} from './session/index.js';

// Turn Processing
export {
  TurnHandler,
  MessageBuilder,
  ContextWindow,
  ToolLoop,
  createTurnHandler,
  createSafeTurnHandler,
  createSafeContextWindow,
  createSafeToolLoop,
  hasQuestionResult,
  buildToolUseMapFromMessages,
  contentLength,
  stripToolFiller,
  isOverflowError,
  ContextOverflowError,
} from './turn/index.js';

export type {
  MessageBuilderOptions,
  ContextWindowOptions,
  ToolLoopOptions,
  ToolLoopResult,
  StreamResult
} from './turn/index.js';

// Intelligence Layer
export {
  IntelligenceLayer,
  BackgroundProcessor,
  createIntelligenceLayer,
  createSafeBackgroundProcessor
} from './intelligence/index.js';

export type {
  IntelligenceLayerOptions,
  DialecticSystem,
  ThinkerModule,
  SubconsciousModule,
  IntelligenceProcessor,
  BackgroundProcessorOptions,
  OnCompleteCallback
} from './intelligence/index.js';

// Pipeline Integration
export {
  SessionPipeline,
  createSessionPipeline
} from './adapter/index.js';

export type { SessionPipelineOptions } from './adapter/index.js';
