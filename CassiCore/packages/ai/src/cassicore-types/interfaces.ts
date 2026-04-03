/**
 * CassiCore Interface Types (local copy for tight integration)
 */

/**
 * Logger interface for CassiCore runtime.
 * @why CassiCore uses structured logging with metadata for observability and debugging.
 */
export interface ILogger {
  debug(msg: string, meta?: Record<string, unknown>): void;
  info(msg: string, meta?: Record<string, unknown>): void;
  warn(msg: string, meta?: Record<string, unknown>): void;
  error(msg: string, meta?: Record<string, unknown>): void;
  child(component: string): ILogger;
}

/**
 * Config interface for CassiCore runtime.
 * @why Centralized configuration management with type safety and default values.
 */
export interface IConfig {
  get<T>(key: string, defaultVal?: T): T;
  toJSON(): Record<string, unknown>;
}

// WHY: Simplified event bus type for unsubscribe operations
export type Unsubscribe = () => void;

/**
 * Event bus interface (simplified).
 * @why CassiCore uses an event-driven architecture for decoupled communication between modules.
 */
export interface IEventBus {
  emit<T extends { type: string }>(event: T): void;
  on<T extends { type: string }>(type: T['type'], handler: (e: T) => void): Unsubscribe;
  off<T extends { type: string }>(type: T['type'], handler: (e: T) => void): void;
}
