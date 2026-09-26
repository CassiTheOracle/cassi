# Branching Conversations and Decision Trees

## Overview

This document describes the design and implementation of branching conversation support in CassiCore. The system extends the linear conversation model to support tree-based conversation structures with branching, decision points, and alternative paths.

## Problem Statement

The current CassiCore implementation uses a linear conversation history (`Message[]` array). This limits the system to single-path conversations and prevents:

1. **Branching conversations** - Exploring alternative responses or paths
2. **Decision trees** - Tracking choices and their consequences
3. **What-if scenarios** - Testing different conversation flows
4. **Session continuity across branches** - Maintaining context when switching paths

## Solution Architecture

### Core Components

#### 1. Extended Message Schema (`types.ts`)

The `BranchingMessage` interface extends the base `Message` with tree structure fields:

```typescript
export interface BranchingMessage extends BaseMessage {
  turnId: string;              // Unique turn identifier
  parentTurnId: string | null; // Parent turn for tree structure
  timestamp: Date;             // Turn creation time
  branchPath?: string;         // Branch identifier
  branchIndex?: number;        // Index within branch
  continuityMarker?: { ... };  // Session recovery markers
  decisionMetadata?: { ... };  // Decision tracking
}
```

#### 2. Tree Node Structure (`types.ts`)

Each turn is represented as a tree node:

```typescript
export interface TurnNode {
  message: BranchingMessage;
  children: string[];  // Child turn IDs
  depth: number;       // Depth in tree
}
```

#### 3. Branch Management (`types.ts`)

Branches represent alternative conversation paths:

```typescript
export interface ConversationBranch {
  id: string;              // Branch identifier
  rootTurnId: string;      // Root turn of this branch
  currentTurnId: string;   // Current active turn
  turnIds: string[];       // All turns in order
  createdAt: Date;
  lastActiveAt: Date;
  metadata?: { ... };      // Name, description, tags
}
```

#### 4. Branching Session (`types.ts`)

Replaces linear history with tree structure:

```typescript
export interface BranchingSession {
  id: string;
  channelId: string;
  senderId: string;
  turnTree: Map<string, TurnNode>;     // Tree structure
  rootTurnId: string | null;
  branches: Map<string, ConversationBranch>;  // All branches
  activeBranchId: string;              // Currently active branch
  config: SessionConfig;
  createdAt: Date;
  lastActiveAt: Date;
  tokenCount: number;
  decisionTree?: { ... };              // Decision tracking
}
```

### Manager Implementation (`manager.ts`)

The `BranchingConversationManager` class provides:

#### Core Operations

1. **Session Management**
   - `createSession()` - Create new tree-based session
   - `getSession()` - Retrieve session by ID

2. **Turn Management**
   - `addTurn()` - Add turn to active branch
   - Maintains parent-child relationships
   - Updates branch state and token count

3. **Branch Operations**
   - `forkBranch()` - Create new branch from current point
   - `switchBranch()` - Switch active branch
   - `mergeBranch()` - Merge branches (append/replace/integrate)
   - `listBranches()` - List all branches
   - `deleteBranch()` - Remove branch

4. **Tree Traversal**
   - `getBranchTurns()` - Get all turns in a branch
   - `getPathToTurn()` - Path from root to turn
   - `getSiblings()` - Other branches from same parent
   - `findCommonAncestor()` - Lowest common ancestor

5. **Decision Points**
   - `createDecisionPoint()` - Mark decision with alternatives
   - Tracks chosen path and alternatives

6. **Continuity Markers**
   - `createContinuityMarker()` - Create recovery checkpoints
   - Enables session recovery after restarts

7. **Serialization**
   - `serializeSession()` - Convert to JSON for storage
   - `deserializeSession()` - Restore from JSON
   - `getLinearHistory()` - Compatibility with existing code

### Middleware Integration (`middleware.ts`)

Middleware functions integrate branching into the turn pipeline:

#### 1. Branching Conversation Middleware

```typescript
makeBranchingConversationMiddleware(manager)
```

- Tracks each turn in conversation tree
- Maintains branch state automatically
- Adds user and assistant messages to tree

#### 2. Branch Switch Middleware

```typescript
makeBranchSwitchMiddleware(manager)
```

- Allows dynamic branch switching during turns
- Useful for exploring alternatives

#### 3. Decision Point Middleware

```typescript
makeDecisionPointMiddleware(manager)
```

- Automatically creates decision points
- Tracks alternatives and choices

#### 4. Continuity Marker Middleware

```typescript
makeContinuityMarkerMiddleware(manager, interval)
```

- Creates checkpoints every N turns
- Enables recovery after daemon restarts

### Persistence Layer (`session-store.ts`)

Extends `SessionStore` to support tree-based history:

#### Schema Changes

New table `branching_sessions`:

```sql
CREATE TABLE branching_sessions (
  id             TEXT PRIMARY KEY,
  channel_id     TEXT NOT NULL,
  sender_id      TEXT NOT NULL,
  tree_json      TEXT NOT NULL,  -- Serialized tree structure
  config_json    TEXT NOT NULL,
  token_count    INTEGER NOT NULL,
  created_at     INTEGER NOT NULL,
  last_active_at INTEGER NOT NULL
);
```

#### Operations

- `save()` - Serialize and persist tree
- `load()` - Deserialize and restore tree
- `findBySender()` - Find by channel/sender
- `listAll()` - List all sessions
- `remove()` - Delete session
- `prune()` - Remove old sessions

### Decision Tree Utilities (`decision-tree.ts`)

The `DecisionTreeAnalyzer` class provides analysis functions:

#### Tree Analysis

- `findDecisionPoints()` - All decision points
- `getCurrentPath()` - Active decision path
- `findAllPaths()` - All root-to-leaf paths
- `findShortestPath()` - Path between turns

#### Statistics

- `getTurnDepth()` - Depth of a turn
- `getBranchingFactor()` - Children count
- `findLeafNodes()` - End points
- `findForkPoints()` - Branch points
- `getTreeStats()` - Comprehensive statistics

#### Path Operations

- `findCommonPrefix()` - Shared prefix of branches
- `findDivergencePoint()` - Where branches split
- `getAncestors()` - Parent turns
- `getDescendants()` - Child turns
- `isOnActivePath()` - Check if on active branch
- `findRecentDecisionPoint()` - Most recent decision

## Usage Examples

### Basic Branching

```typescript
const manager = new BranchingConversationManager()

// Create session
const session = manager.createSession('session-1', 'channel', 'user', config)

// Add turns to main branch
manager.addTurn('session-1', { role: 'user', content: 'Hello' })
manager.addTurn('session-1', { role: 'assistant', content: 'Hi there!' })

// Fork a new branch
manager.forkBranch('session-1', 'alternative-1', {
  name: 'Alternative Greeting',
  description: 'Try a different response'
})

// Switch to alternative branch
manager.switchBranch('session-1', 'alternative-1')

// Add turns to alternative branch
manager.addTurn('session-1', { role: 'assistant', content: 'Greetings!' })

// Switch back to main
manager.switchBranch('session-1', 'main')
```

### Decision Points

```typescript
// Create decision point with alternatives
manager.createDecisionPoint(
  'session-1',
  currentTurnId,
  [
    { id: 'branch-a', label: 'Option A', description: 'Choose path A' },
    { id: 'branch-b', label: 'Option B', description: 'Choose path B' },
  ],
  'branch-a'  // Chosen alternative
)

// Each alternative automatically gets a branch
manager.switchBranch('session-1', 'branch-b')
```

### Session Recovery

```typescript
// Create continuity marker
const marker = manager.createContinuityMarker(
  'session-1',
  'Checkpoint before complex operation',
  { operation: 'tool-execution' }
)

// Serialize for persistence
const serialized = manager.serializeSession('session-1')
await store.save(serialized)

// Later: restore session
const restored = manager.deserializeSession('session-1', serialized)
```

### Tree Analysis

```typescript
const analyzer = DecisionTreeAnalyzer

// Get tree statistics
const stats = analyzer.getTreeStats(session)
console.log(`Total turns: ${stats.totalTurns}`)
console.log(`Max depth: ${stats.maxDepth}`)
console.log(`Branches: ${stats.totalBranches}`)

// Find all paths
const paths = analyzer.findAllPaths(session)
paths.forEach((path, i) => {
  console.log(`Path ${i + 1}: ${path.length} turns`)
})

// Find divergence between branches
const divergence = analyzer.findDivergencePoint(
  session,
  'main',
  'alternative-1'
)
```

## Integration with Existing Code

### Backward Compatibility

The `getLinearHistory()` method provides compatibility:

```typescript
// Get active branch as linear array (for existing code)
const linearHistory = manager.getLinearHistory('session-1')
// Returns Message[] compatible with existing APIs
```

### Middleware Registration

Add to turn pipeline:

```typescript
const manager = new BranchingConversationManager()

const pipeline = [
  makeBranchingConversationMiddleware(manager),
  makeContinuityMarkerMiddleware(manager, 10),
  makeDecisionPointMiddleware(manager),
  // ... other middleware
]
```

## Benefits

1. **Branching Support** - Explore alternative conversation paths
2. **Decision Tracking** - Record choices and alternatives
3. **Session Continuity** - Recovery markers for daemon restarts
4. **Tree Analysis** - Rich analytics on conversation structure
5. **Backward Compatible** - Linear history view for existing code
6. **Persistent** - SQLite storage for tree structures

## Future Enhancements

1. **Visual Tree Editor** - UI for exploring and editing conversation trees
2. **Branch Comparison** - Diff tool for comparing alternative paths
3. **Auto-Pruning** - Remove unused branches after timeout
4. **Branch Merging Strategies** - Advanced merge algorithms
5. **Collaborative Branching** - Multiple users on different branches
6. **Branch Export/Import** - Share alternative conversation paths

## Files Created

1. `core/intelligence/branching-conversation/types.ts` - Type definitions
2. `core/intelligence/branching-conversation/manager.ts` - Core manager
3. `core/intelligence/branching-conversation/middleware.ts` - Pipeline middleware
4. `core/intelligence/branching-conversation/session-store.ts` - Persistence
5. `core/intelligence/branching-conversation/decision-tree.ts` - Analysis utilities
6. `core/intelligence/branching-conversation/README.md` - This documentation

## Testing Recommendations

1. Test branch creation and switching
2. Test merge operations with different strategies
3. Test serialization/deserialization round-trip
4. Test tree traversal algorithms
5. Test decision point creation and tracking
6. Test continuity marker recovery
7. Test backward compatibility with linear history
