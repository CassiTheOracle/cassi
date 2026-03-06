/**
 * Background Processor
 * 
 * Queue-based background job processor for intelligence tasks
 */

import type {
  TurnData,
  ProcessorResult,
  ILogger
} from '../session/types.js';

export interface IntelligenceProcessor {
  /** Processor name for logging */
  readonly name: string;
  
  /** Process turn data and return insights */
  process(sessionId: string, turnData: TurnData): Promise<ProcessorResult | null>;
}

export interface BackgroundProcessorOptions {
  /** Max concurrent jobs */
  concurrency: number;
  
  /** Min time between job starts (ms) */
  intervalMs: number;
  
  /** Max queue size before dropping */
  maxQueueSize?: number;
  
  /** Auto-start processing */
  autoStart?: boolean;
}

export type OnCompleteCallback = (
  sessionId: string,
  results: ProcessorResult[]
) => Promise<void>;

/**
 * Simple in-memory queue for background processing
 * 
 * In production, consider using a proper job queue like Bull, Bee, or pg-boss
 */
export class BackgroundProcessor {
  private processors: IntelligenceProcessor[];
  private options: BackgroundProcessorOptions;
  private logger: ILogger;
  private onComplete?: OnCompleteCallback;
  
  // Queue state
  private queue: Array<{
    sessionId: string;
    turnData: TurnData;
    enqueuedAt: number;
  }> = [];
  private running = false;
  private activeJobs = 0;
  private intervalId?: NodeJS.Timeout;
  
  // Metrics
  private metrics = {
    processed: 0,
    failed: 0,
    dropped: 0,
    avgDuration: 0
  };
  
  constructor(
    processors: IntelligenceProcessor[],
    options: BackgroundProcessorOptions,
    logger: ILogger
  ) {
    this.processors = processors;
    this.options = options;
    this.logger = logger;
    
    if (options.autoStart !== false) {
      this.start();
    }
  }
  
  /**
   * Set completion callback
   */
  setOnComplete(callback: OnCompleteCallback): void {
    this.onComplete = callback;
  }
  
  /**
   * Start processing
   */
  start(): void {
    if (this.running) return;
    
    this.running = true;
    this.logger.info('Background processor started', {
      processors: this.processors.map(p => p.name),
      concurrency: this.options.concurrency
    });
    
    // Start processing loop
    this.intervalId = setInterval(() => {
      this.processQueue();
    }, this.options.intervalMs);
  }
  
  /**
   * Stop processing
   */
  stop(): void {
    this.running = false;
    
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = undefined;
    }
    
    this.logger.info('Background processor stopped', {
      queueSize: this.queue.length,
      activeJobs: this.activeJobs,
      metrics: this.metrics
    });
  }
  
  /**
   * Enqueue a job for processing
   */
  async enqueue(sessionId: string, turnData: TurnData): Promise<void> {
    const maxSize = this.options.maxQueueSize ?? 1000;
    
    // Check if queue is full
    if (this.queue.length >= maxSize) {
      this.metrics.dropped++;
      this.logger.warn('Queue full - dropping job', { sessionId });
      return;
    }
    
    // Add to queue
    this.queue.push({
      sessionId,
      turnData,
      enqueuedAt: Date.now()
    });
    
    this.logger.debug('Job enqueued', {
      sessionId,
      queueSize: this.queue.length
    });
  }
  
  /**
   * Get queue stats
   */
  getStats(): {
    queueSize: number;
    activeJobs: number;
    processed: number;
    failed: number;
    dropped: number;
    avgDuration: number;
  } {
    return {
      queueSize: this.queue.length,
      activeJobs: this.activeJobs,
      ...this.metrics
    };
  }
  
  /**
   * Clear the queue
   */
  clearQueue(): number {
    const cleared = this.queue.length;
    this.queue = [];
    return cleared;
  }
  
  // ============================================================================
  // Private Methods
  // ============================================================================
  
  private async processQueue(): Promise<void> {
    // Check capacity
    if (this.activeJobs >= this.options.concurrency) {
      return;
    }
    
    // Get next job
    const job = this.queue.shift();
    if (!job) return;
    
    // Process
    this.activeJobs++;
    
    try {
      await this.processJob(job);
    } finally {
      this.activeJobs--;
    }
  }
  
  private async processJob(job: {
    sessionId: string;
    turnData: TurnData;
    enqueuedAt: number;
  }): Promise<void> {
    const start = Date.now();
    const waitTime = start - job.enqueuedAt;
    
    this.logger.debug('Processing job', {
      sessionId: job.sessionId,
      waitTime,
      processors: this.processors.length
    });
    
    try {
      // Run all processors in parallel
      const results = await Promise.all(
        this.processors.map(async processor => {
          const procStart = Date.now();
          
          try {
            const result = await processor.process(job.sessionId, job.turnData);
            
            this.logger.debug(`${processor.name} completed`, {
              sessionId: job.sessionId,
              duration: Date.now() - procStart,
              hasResult: !!result
            });
            
            return result;
          } catch (error) {
            this.logger.warn(`${processor.name} failed`, {
              sessionId: job.sessionId,
              error: String(error)
            });
            return null;
          }
        })
      );
      
      // Filter successful results
      const successful = results.filter((r): r is ProcessorResult => r !== null);
      
      // Update metrics
      const duration = Date.now() - start;
      this.metrics.processed++;
      this.metrics.avgDuration = this.updateAvgDuration(duration);
      
      // Call completion handler
      if (this.onComplete && successful.length > 0) {
        try {
          await this.onComplete(job.sessionId, successful);
        } catch (error) {
          this.logger.error('OnComplete callback failed', {
            sessionId: job.sessionId,
            error: String(error)
          });
        }
      }
      
      this.logger.debug('Job completed', {
        sessionId: job.sessionId,
        duration,
        waitTime,
        results: successful.length
      });
      
    } catch (error) {
      this.metrics.failed++;
      this.logger.error('Job failed', {
        sessionId: job.sessionId,
        error: String(error)
      });
    }
  }
  
  private updateAvgDuration(newDuration: number): number {
    const total = this.metrics.avgDuration * (this.metrics.processed - 1) + newDuration;
    return total / this.metrics.processed;
  }
}

/**
 * Create processor with safe defaults
 */
export function createSafeBackgroundProcessor(
  processors: IntelligenceProcessor[],
  logger: ILogger
): BackgroundProcessor {
  return new BackgroundProcessor(
    processors,
    {
      concurrency: 3,
      intervalMs: 100,
      maxQueueSize: 1000,
      autoStart: true
    },
    logger
  );
}
