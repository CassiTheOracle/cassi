/**
 * Turn Processing
 * 
 * Simplified turn processing exports
 */

// Turn Handler
export { TurnHandler, createTurnHandler, createSafeTurnHandler } from './TurnHandler.js';
export type { PipelineHooks } from './TurnHandler.js';

// Message Builder
export { MessageBuilder } from './MessageBuilder.js';
export type { MessageBuilderOptions } from './MessageBuilder.js';

// Context Window
export { ContextWindow, createSafeContextWindow } from './ContextWindow.js';
export type { ContextWindowOptions, TrimDebugInfo } from './ContextWindow.js';

// Tool Loop
export { ToolLoop, createSafeToolLoop } from './ToolLoop.js';
export type {
  ToolLoopOptions,
  ToolLoopResult,
  StreamResult
} from './ToolLoop.js';

// Overflow utilities
export {
  ContextOverflowError,
  isOverflowError,
  reclassifyAsOverflow,
  stripToolFiller,
  contentLength,
  hasQuestionResult,
  buildToolUseMapFromMessages,
} from './overflow.js';
