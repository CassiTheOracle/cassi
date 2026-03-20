import { rootLogger } from '../logger.js'

import type { ILogger } from '../../types/interfaces.js'

const logger: ILogger = rootLogger.child('tool-safety')

/**
 * Tool Safety & Validation System
 * 
 * Provides comprehensive guardrails for tool invocation:
 * - Pre-call input validation
 * - Post-call output validation  
 * - Error containment and sandboxing
 * - Timeout enforcement
 * - Failure isolation
 */

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

export interface SafeResult<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  errorType?: 'timeout' | 'validation' | 'execution' | 'unknown';
  durationMs?: number;
}

export interface ToolGuardrails {
  // Pre-call validation
  validateInput(toolName: string, params: any): ValidationResult;
  
  // Post-call validation
  validateOutput(toolName: string, result: any): ValidationResult;
  
  // Safe execution with timeout and error handling
  executeSafe<T>(
    toolName: string,
    operation: () => Promise<T>,
    timeoutMs?: number
  ): Promise<SafeResult<T>>;
}

/**
 * Default timeout for tool calls (ms)
 */
const DEFAULT_TOOL_TIMEOUT = 30000; // 30 seconds

/**
 * Maximum output size (chars)
 */
const MAX_OUTPUT_SIZE = 1000000; // 1MB

/**
 * Tool-specific validation rules
 */
const TOOL_VALIDATION_RULES: Record<string, {
  requiredParams?: string[];
  paramTypes?: Record<string, string>;
  maxParamLength?: number;
  validateOutput?: (result: any) => ValidationResult;
}> = {
  // File operations
  'read_file': {
    requiredParams: ['path'],
    paramTypes: { path: 'string', offset: 'number', limit: 'number' },
    maxParamLength: 1000,
  },
  'write_file': {
    requiredParams: ['path', 'content'],
    paramTypes: { path: 'string', content: 'string' },
    maxParamLength: 100000,
  },
  'shell_exec': {
    requiredParams: ['command'],
    paramTypes: { command: 'string', cwd: 'string', timeout_ms: 'number' },
    maxParamLength: 10000,
    // Block dangerous commands
    validateOutput: (result: any) => {
      const errors: string[] = [];
      if (result.exitCode !== 0 && result.exitCode !== undefined) {
        errors.push(`Command exited with code ${result.exitCode}`);
      }
      return { valid: errors.length === 0, errors, warnings: [] };
    },
  },
  
  // Web operations
  'web_fetch': {
    requiredParams: ['url'],
    paramTypes: { url: 'string', timeoutMs: 'number' },
    maxParamLength: 2000,
  },
  
  // Search operations
  'grep': {
    requiredParams: ['pattern', 'path'],
    paramTypes: { pattern: 'string', path: 'string' },
    maxParamLength: 5000,
  },
};

/**
 * Validate tool input parameters
 * @dep callers: execute (core/tools/executor.ts), executeToolSafe (core/tools/safety.ts)
 * @dep module: Tools
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function validateToolInput(
  toolName: string,
  params: any
): ValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  
  // Get validation rules for this tool
  const rules = TOOL_VALIDATION_RULES[toolName];
  
  if (!rules) {
    // No specific rules - basic validation only
    if (params && typeof params !== 'object') {
      errors.push('Parameters must be an object');
    }
    return { valid: errors.length === 0, errors, warnings };
  }
  
  // Check required parameters
  if (rules.requiredParams) {
    for (const param of rules.requiredParams) {
      if (!params || !(param in params)) {
        errors.push(`Missing required parameter: ${param}`);
      }
    }
  }
  
  // Check parameter types
  if (rules.paramTypes && params) {
    for (const [param, expectedType] of Object.entries(rules.paramTypes)) {
      if (param in params) {
        const actualType = typeof params[param];
        if (actualType !== expectedType) {
          errors.push(
            `Parameter '${param}' must be ${expectedType}, got ${actualType}`
          );
        }
      }
    }
  }
  
  // Check parameter size
  if (rules.maxParamLength && params) {
    const paramSize = JSON.stringify(params).length;
    if (paramSize > rules.maxParamLength) {
      errors.push(
        `Parameters too large: ${paramSize} chars (max: ${rules.maxParamLength})`
      );
    }
  }
  
  // Check for dangerous patterns
  if (toolName === 'shell_exec' && params?.command) {
    const dangerousPatterns = [
      'rm -rf /',
      'rm -rf /*',
      'dd if=/dev/zero',
      ':(){:|:&};:',  // Fork bomb
      'mkfs',
      'chmod -R 777 /',
    ];
    
    const cmd = params.command.toLowerCase();
    for (const pattern of dangerousPatterns) {
      if (cmd.includes(pattern.toLowerCase())) {
        errors.push(`Dangerous command pattern detected: ${pattern}`);
      }
    }
  }
  
  return { valid: errors.length === 0, errors, warnings };
}

/**
 * Validate tool output
 * @dep callers: execute (core/tools/executor.ts), executeToolSafe (core/tools/safety.ts)
 * @dep module: Tools
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export function validateToolOutput(
  toolName: string,
  result: any
): ValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  
  // Check for null/undefined
  if (result === null || result === undefined) {
    errors.push('Tool returned null or undefined');
    return { valid: false, errors, warnings };
  }
  
  // Check output size
  const resultSize = JSON.stringify(result).length;
  if (resultSize > MAX_OUTPUT_SIZE) {
    errors.push(
      `Output too large: ${resultSize} chars (max: ${MAX_OUTPUT_SIZE})`
    );
  }
  
  // Tool-specific validation
  const rules = TOOL_VALIDATION_RULES[toolName];
  if (rules?.validateOutput) {
    const customResult = rules.validateOutput(result);
    errors.push(...customResult.errors);
    warnings.push(...customResult.warnings);
  }
  
  // Check for error indicators in result
  if (typeof result === 'object') {
    if (result.error) {
      warnings.push(`Tool returned error: ${result.error}`);
    }
    if (result.isError || result.success === false) {
      warnings.push('Tool indicated failure in result');
    }
  }
  
  return { valid: errors.length === 0, errors, warnings };
}

/**
 * Execute tool with timeout and error handling
 */
export async function executeWithTimeout<T>(
  operation: () => Promise<T>,
  timeoutMs: number = DEFAULT_TOOL_TIMEOUT
): Promise<SafeResult<T>> {
  const startTime = Date.now();
  
  try {
    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => {
        reject(new Error(`Timeout after ${timeoutMs}ms`));
      }, timeoutMs);
    });
    
    const result = await Promise.race([operation(), timeoutPromise]);
    
    return {
      success: true,
      data: result,
      durationMs: Date.now() - startTime,
    };
  } catch (error) {
    const durationMs = Date.now() - startTime;
    const errorMessage = error instanceof Error ? error.message : String(error);
    
    let errorType: SafeResult['errorType'] = 'execution';
    if (errorMessage.includes('timeout')) {
      errorType = 'timeout';
    } else if (errorMessage.includes('validation')) {
      errorType = 'validation';
    }
    
    return {
      success: false,
      error: errorMessage,
      errorType,
      durationMs,
    };
  }
}

/**
 * Safe tool execution wrapper
 * @dep callers: execute (core/tools/executor.ts), createSafeToolExecutor (core/tools/safety.ts)
 * @dep calls: validateToolInput, validateToolOutput, executeWithTimeout
 * @dep module: Tools
 * @dep risk: LOW | 2 callers, 0 flows, 1 module
 */
export async function executeToolSafe<T>(
  toolName: string,
  operation: () => Promise<T>,
  params?: any,
  timeoutMs?: number
): Promise<SafeResult<T>> {
  // Pre-call validation
  if (params) {
    const inputValidation = validateToolInput(toolName, params);
    if (!inputValidation.valid) {
      return {
        success: false,
        error: `Input validation failed: ${inputValidation.errors.join(', ')}`,
        errorType: 'validation',
        durationMs: 0,
      };
    }
  }
  
  // Execute with timeout
  const result = await executeWithTimeout(operation, timeoutMs);
  
  // Post-call validation (only if successful)
  if (result.success && result.data !== undefined) {
    const outputValidation = validateToolOutput(toolName, result.data);
    if (!outputValidation.valid) {
      return {
        success: false,
        error: `Output validation failed: ${outputValidation.errors.join(', ')}`,
        errorType: 'validation',
        durationMs: result.durationMs,
      };
    }
    
    // Add warnings to result if any
    if (outputValidation.warnings.length > 0) {
      logger.warn(`[${toolName}] Warnings`, { warnings: outputValidation.warnings });
    }
  }
  
  return result;
}

/**
 * Create a safe tool executor
 */
export function createSafeToolExecutor(
  originalExecutor: (toolName: string, params: any) => Promise<any>
) {
  return async function safeExecute(
    toolName: string,
    params: any,
    timeoutMs?: number
  ): Promise<SafeResult> {
    return executeToolSafe(
      toolName,
      () => originalExecutor(toolName, params),
      params,
      timeoutMs
    );
  };
}
