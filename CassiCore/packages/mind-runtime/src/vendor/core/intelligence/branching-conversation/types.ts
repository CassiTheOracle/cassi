/**
 * Extended Message Schema for Branching Conversations
 * 
 * This extends the base Message interface to support:
 * - Turn ordering with explicit IDs and timestamps
 * - Parent-child relationships for conversation trees
 * - Branch tracking and path identification
 * - Session continuity markers
 */

import type { Message as BaseMessage } from '@cassicore/foundation'

/**
 * Extended message with tree structure support.
 * 
 * Each turn in a conversation has:
 * - A unique turnId for identification
 * - A parentTurnId to establish tree relationships
 * - Timestamps for ordering and continuity
 * - Branch path for tracking conversation forks
 */
export interface BranchingMessage extends BaseMessage {
  /** Unique identifier for this turn */
  turnId: string;
  
  /** Parent turn ID - null for root/system messages */
  parentTurnId: string | null;
  
  /** Timestamp when this turn was created */
  timestamp: Date;
  
  /** Optional: Path identifier for branch tracking (e.g., "main", "branch-1", "decision-A") */
  branchPath?: string;
  
  /** Optional: Index within the branch for quick ordering */
  branchIndex?: number;
  
  /** Optional: Continuity marker for session recovery */
  continuityMarker?: {
    /** Session ID this turn belongs to */
    sessionId: string;
    /** Checkpoint ID for recovery points */
    checkpointId?: string;
    /** Whether this is a recovery/continuity injection */
    isContinuity?: boolean;
  };
  
  /** Optional: Metadata for decision tree tracking */
  decisionMetadata?: {
    /** Decision point identifier */
    decisionPoint?: string;
    /** Chosen branch at this decision point */
    chosenBranch?: string;
    /** Alternative branches available */
    alternatives?: string[];
  };
}

/**
 * Tree node representation for conversation turns.
 * 
 * This structure allows efficient tree traversal and branch management.
 */
export interface TurnNode {
  /** The message content */
  message: BranchingMessage;
  
  /** Child turn IDs - represents branches from this turn */
  children: string[];
  
  /** Depth in the conversation tree */
  depth: number;
}

/**
 * Branch state tracking.
 * 
 * Each branch represents an alternative conversation path.
 */
export interface ConversationBranch {
  /** Branch identifier (e.g., "main", "fork-1", "decision-alternative-A") */
  id: string;
  
  /** Root turn ID for this branch */
  rootTurnId: string;
  
  /** Current active turn ID in this branch */
  currentTurnId: string;
  
  /** All turn IDs in this branch (in order) */
  turnIds: string[];

  /** Current index within the branch (= turnIds.length - 1 for latest) */
  branchIndex?: number;
  
  /** Branch creation timestamp */
  createdAt: Date;
  
  /** Last activity timestamp */
  lastActiveAt: Date;
  
  /** Optional: Branch description/metadata */
  metadata?: {
    /** Human-readable name */
    name?: string;
    /** Description of this branch's purpose */
    description?: string;
    /** Tags for categorization */
    tags?: string[];
  };
}

/**
 * Extended session with tree-based history.
 * 
 * Replaces the linear history array with a tree structure.
 */
export interface BranchingSession {
  /** Session identifier */
  id: string;
  
  /** Channel identifier */
  channelId: string;
  
  /** Sender identifier */
  senderId: string;
  
  /** Tree structure: turnId -> TurnNode mapping */
  turnTree: Map<string, TurnNode>;
  
  /** Root turn ID (typically the first system/user message) */
  rootTurnId: string | null;
  
  /** All branches in this session */
  branches: Map<string, ConversationBranch>;
  
  /** Currently active branch ID */
  activeBranchId: string;
  
  /** Session configuration */
  config: SessionConfig;
  
  /** Session creation timestamp */
  createdAt: Date;
  
  /** Last activity timestamp */
  lastActiveAt: Date;
  
  /** Token count (approximate) */
  tokenCount: number;
  
  /** Optional: Decision tree metadata */
  decisionTree?: {
    /** Decision points in the conversation */
    decisionPoints: DecisionPoint[];
    /** Current decision path */
    currentPath: DecisionPath;
  };
}

/**
 * Session configuration (mirrors runtime.ts)
 */
export interface SessionConfig {
  model: string;
  providerId?: string;
  providerModel?: string;
  systemPrompt?: string;
  thinking?: 'none' | 'low' | 'medium' | 'high';
  maxContextTokens?: number;
}

/**
 * Decision point in a conversation tree.
 * 
 * Represents a fork where multiple alternatives were available.
 */
export interface DecisionPoint {
  /** Unique decision point identifier */
  id: string;
  
  /** Turn ID where the decision was made */
  turnId: string;
  
  /** Available alternatives */
  alternatives: DecisionAlternative[];
  
  /** Chosen alternative */
  chosenAlternativeId: string;
  
  /** Timestamp */
  timestamp: Date;
}

/**
 * Decision alternative at a decision point.
 */
export interface DecisionAlternative {
  /** Alternative identifier */
  id: string;
  
  /** Human-readable label */
  label: string;
  
  /** Branch ID this alternative leads to */
  branchId: string;
  
  /** Description of this alternative */
  description?: string;
}

/**
 * Decision path through the conversation tree.
 * 
 * Represents the sequence of choices made.
 */
export interface DecisionPath {
  /** Path identifier */
  id: string;
  
  /** Sequence of decision point IDs */
  decisionPointIds: string[];
  
  /** Sequence of chosen alternative IDs */
  chosenAlternativeIds: string[];
  
  /** Branch IDs visited along this path */
  branchIds: string[];
}

/**
 * Branch management operations.
 */
export interface BranchManager {
  /**
   * Create a new branch from the current active turn.
   * @param branchId - Unique branch identifier
   * @param metadata - Optional branch metadata
   * @returns The created branch
   */
  fork(branchId: string, metadata?: { name?: string; description?: string }): ConversationBranch;
  
  /**
   * Switch to a different branch.
   * @param branchId - Branch identifier to switch to
   * @returns The activated branch
   */
  switchBranch(branchId: string): ConversationBranch;
  
  /**
   * Merge a branch back into the active branch.
   * @param sourceBranchId - Branch to merge from
   * @param strategy - Merge strategy ('append', 'replace', 'integrate')
   * @returns Success status
   */
  merge(sourceBranchId: string, strategy?: 'append' | 'replace' | 'integrate'): boolean;
  
  /**
   * List all branches in the session.
   * @returns Array of branches
   */
  listBranches(): ConversationBranch[];
  
  /**
   * Get the current active branch.
   * @returns Active branch
   */
  getActiveBranch(): ConversationBranch;
  
  /**
   * Delete a branch (cannot delete active branch).
   * @param branchId - Branch to delete
   * @returns Success status
   */
  deleteBranch(branchId: string): boolean;
}

/**
 * Tree traversal utilities.
 */
export interface TreeTraversal {
  /**
   * Get all turns in a branch (in order).
   * @param branchId - Branch identifier
   * @returns Ordered array of messages
   */
  getBranchTurns(branchId: string): BranchingMessage[];
  
  /**
   * Get the path from root to a specific turn.
   * @param turnId - Target turn ID
   * @returns Array of turn IDs from root to target
   */
  getPathToTurn(turnId: string): string[];
  
  /**
   * Get siblings of a turn (other branches from the same parent).
   * @param turnId - Turn ID to find siblings for
   * @returns Array of sibling turn IDs
   */
  getSiblings(turnId: string): string[];
  
  /**
   * Find the lowest common ancestor of two turns.
   * @param turnId1 - First turn ID
   * @param turnId2 - Second turn ID
   * @returns Common ancestor turn ID or null
   */
  findCommonAncestor(turnId1: string, turnId2: string): string | null;
  
  /**
   * Serialize the conversation tree to JSON.
   * @returns Serialized tree structure
   */
  serialize(): SerializedConversationTree;
  
  /**
   * Deserialize a conversation tree from JSON.
   * @param data - Serialized tree data
   * @returns Restored tree structure
   */
  deserialize(data: SerializedConversationTree): void;
}

/**
 * Serialized conversation tree for persistence.
 */
export interface SerializedConversationTree {
  /** Turn tree as plain object */
  turnTree: Record<string, TurnNode>;
  
  /** Branches as plain object */
  branches: Record<string, ConversationBranch>;
  
  /** Root turn ID */
  rootTurnId: string | null;
  
  /** Active branch ID */
  activeBranchId: string;
  
  /** Schema version for migration support */
  schemaVersion: number;
}

/**
 * Continuity marker for session recovery.
 * 
 * Used to mark recovery points and ensure continuity across daemon restarts.
 */
export interface ContinuityMarker {
  /** Marker identifier */
  id: string;
  
  /** Session ID */
  sessionId: string;
  
  /** Turn ID at this checkpoint */
  turnId: string;
  
  /** Branch ID at this checkpoint */
  branchId: string;
  
  /** Timestamp */
  timestamp: Date;
  
  /** Optional: Description of this checkpoint */
  description?: string;
  
  /** Optional: Metadata for recovery */
  metadata?: Record<string, unknown>;
}
