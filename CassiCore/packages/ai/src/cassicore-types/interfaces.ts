/**
 * CassiCore Interface Types (local copy for tight integration)
 */

// Logger interface
export interface ILogger {
  debug(msg: string, meta?: Record<string, unknown>): void;
  info(msg: string, meta?: Record<string, unknown>): void;
  warn(msg: string, meta?: Record<string, unknown>): void;
  error(msg: string, meta?: Record<string, unknown>): void;
  child(component: string): ILogger;
}

// Config interface
export interface IConfig {
  get<T>(key: string, defaultVal?: T): T;
  toJSON(): Record<string, unknown>;
}

// Event bus interface (simplified)
export type Unsubscribe = () => void;

export interface IEventBus {
  emit<T extends { type: string }>(event: T): void;
  on<T extends { type: string }>(type: T['type'], handler: (e: T) => void): Unsubscribe;
  off<T extends { type: string }>(type: T['type'], handler: (e: T) => void): void;
}
