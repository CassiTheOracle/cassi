# Dialectic Optimization — Fully Parallel Architecture

## Architecture Decision: Always Parallel

The dialectic trio (Yang, Yin, Serenity) now **always runs in parallel** alongside the main agent. The sequential path has been removed entirely.

### Before (Removed)
```
Sequential: Yang → Yin → Serenity (~600ms total)
```

### After (Current)
```
Parallel: Yang + Yin → Serenity (~350ms total)
          │     │
          └─────┘
            │
         Serenity
```

## Execution Model

The dialectic runs **concurrently with the main agent**:

```
Main Agent Processing    │██████████████│
Dialectic (Parallel)     │███████│
                         │       └─ Serenity
                         └─ Yang + Yin (simultaneous)
```

This means:
- No blocking of the main response
- Insights available asynchronously
- Signals can be injected into subsequent turns
- Maximum throughput with minimal latency impact

## Performance

| Mode | Latency | Speedup |
|------|---------|---------|
| Old Sequential | ~600ms | 1x |
| New Parallel | ~350ms | 1.7x |
| Cached Result | ~5ms | 120x |

## Caching Strategy

Results are cached based on Jaccard similarity (85% threshold, 30s TTL):

```typescript
// Repeated/similar queries return cached results
if (similarity(userMessage, cachedQuery) >= 0.85) {
  return cachedResult; // ~5ms
}
```

## Components

### DialecticSystem (`index.ts`)
- Entry point for all dialectic operations
- Manages caching and result persistence
- Wires event bus, provider, memory

### ParallelDialecticProcessor (`parallel-processor.ts`)
- Runs Yang and Yin simultaneously with `Promise.all`
- Performs dual synthesis in Serenity
- Calculates quality metrics (agreement, tension)

### Observers (Yang, Yin, Serenity)
Located in `core/intelligence/{yang,yin,serenity}/`:
- **Yang**: Generates expansive branches (temperature 0.9)
- **Yin**: Generates baseline + self-critique (temperature 0.3)
- **Serenity**: Dual synthesis of Yang + Yin outputs (temperature 0.4)

## Configuration

```typescript
const dialectic = createDialecticSystem(logger, {
  enabled: true,
  yang: { model: 'kimi-coding/k2p5', maxBranches: 5 },
  yin: { model: 'kimi-coding/k2p5' },
  serenity: { model: 'kimi-coding/k2p5' },
  parallel: {
    maxWaitMs: 8000,
    observerTimeoutMs: 6000,
    partialResultsOnFailure: true,
  },
  cache: {
    enabled: true,
    ttlMs: 30000,
    similarityThreshold: 0.85,
  },
});
```

## Migration Notes

- Removed `mode` config option (always parallel now)
- Removed `adaptive` complexity detection
- Removed task guide generation (was sequential-only)
- Return type is always `ParallelDialecticResult`

## Quality Metrics

Each parallel result includes:

```typescript
{
  quality: {
    yangYinAgreement: 0.72,    // 0-1, higher = more alignment
    dialecticTension: 0.28,    // 0-1, higher = more creative diversity
    synthesisConfidence: 0.85, // Serenity's confidence
  },
  timing: {
    yangDuration: 180,
    yinDuration: 165,
    serenityDuration: 85,
    totalParallelTime: 350,
    firstCompletion: 'yin',
  }
}
```

## Signal Injection

When Serenity detects high-confidence, urgent signals:

```typescript
if (signal.confidence >= 0.7 && signal.urgency === 'immediate') {
  eventBus.emit('dialectic:signal', { sessionId, turnId, signal });
}
```

These signals can be consumed by the main agent for the next turn.
