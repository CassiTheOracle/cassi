import { describe, it, expect, beforeEach } from 'vitest'
import { BranchingConversationManager } from './manager.js'
import type { SessionConfig } from './types.js'

describe('BranchingConversationManager', () => {
  let manager: BranchingConversationManager
  let config: SessionConfig

  beforeEach(() => {
    manager = new BranchingConversationManager()
    config = {
      model: 'gpt-5-mini',
      thinking: 'medium',
      maxContextTokens: 200000,
    }
  })

  describe('Session Management', () => {
    it('should create a new session with main branch', () => {
      const session = manager.createSession('test-session', 'test-channel', 'test-user', config)
      
      expect(session).toBeDefined()
      expect(session.id).toBe('test-session')
      expect(session.channelId).toBe('test-channel')
      expect(session.senderId).toBe('test-user')
      expect(session.branches.size).toBe(1)
      expect(session.branches.has('main')).toBe(true)
    })

    it('should retrieve existing session', () => {
      manager.createSession('test-session', 'test-channel', 'test-user', config)
      const retrieved = manager.getSession('test-session')
      
      expect(retrieved).toBeDefined()
      expect(retrieved?.id).toBe('test-session')
    })

    it('should return undefined for non-existent session', () => {
      const retrieved = manager.getSession('non-existent')
      expect(retrieved).toBeUndefined()
    })
  })

  describe('Turn Management', () => {
    beforeEach(() => {
      manager.createSession('test-session', 'test-channel', 'test-user', config)
    })

    it('should add a turn to the active branch', () => {
      const turnId = manager.addTurn('test-session', {
        role: 'user',
        content: 'Hello',
      })

      expect(turnId).toBeDefined()
      const session = manager.getSession('test-session')
      expect(session?.turnTree.size).toBe(1)
      expect(session?.turnTree.has(turnId)).toBe(true)
    })

    it('should maintain parent-child relationships', () => {
      const turn1 = manager.addTurn('test-session', {
        role: 'user',
        content: 'Hello',
      })

      const turn2 = manager.addTurn('test-session', {
        role: 'assistant',
        content: 'Hi there!',
      })

      const session = manager.getSession('test-session')
      const node1 = session?.turnTree.get(turn1)
      const node2 = session?.turnTree.get(turn2)

      expect(node1?.children).toContain(turn2)
      expect(node2?.message.parentTurnId).toBe(turn1)
    })

    it('should update token count', () => {
      manager.addTurn('test-session', {
        role: 'user',
        content: 'Hello World', // 11 chars ≈ 3 tokens
      })

      const session = manager.getSession('test-session')
      expect(session?.tokenCount).toBeGreaterThan(0)
    })
  })

  describe('Branch Operations', () => {
    beforeEach(() => {
      manager.createSession('test-session', 'test-channel', 'test-user', config)
      manager.addTurn('test-session', { role: 'user', content: 'Turn 1' })
      manager.addTurn('test-session', { role: 'assistant', content: 'Response 1' })
    })

    it('should fork a new branch from current point', () => {
      const branch = manager.forkBranch('test-session', 'fork-1', {
        name: 'Fork Test',
        description: 'Test fork',
      })

      expect(branch).toBeDefined()
      expect(branch.id).toBe('fork-1')
      expect(branch.turnIds.length).toBe(2) // Same as parent at fork point
    })

    it('should switch active branch', () => {
      manager.forkBranch('test-session', 'fork-1')
      
      const activeBranch = manager.switchBranch('test-session', 'fork-1')
      
      expect(activeBranch.id).toBe('fork-1')
      const session = manager.getSession('test-session')
      expect(session?.activeBranchId).toBe('fork-1')
    })

    it('should add turns to different branches independently', () => {
      // Add to main branch
      manager.addTurn('test-session', { role: 'user', content: 'Main turn' })
      
      // Fork and switch
      manager.forkBranch('test-session', 'fork-1')
      manager.switchBranch('test-session', 'fork-1')
      
      // Add to fork
      manager.addTurn('test-session', { role: 'user', content: 'Fork turn' })
      
      // Get turns from each branch
      const mainTurns = manager.getBranchTurns('test-session', 'main')
      const forkTurns = manager.getBranchTurns('test-session', 'fork-1')
      
      expect(mainTurns.length).toBe(3) // 2 initial + 1 main
      expect(forkTurns.length).toBe(4) // 2 initial + 1 main (copied at fork) + 1 fork
    })

    it('should list all branches', () => {
      manager.forkBranch('test-session', 'fork-1')
      manager.forkBranch('test-session', 'fork-2')
      
      const branches = manager.listBranches('test-session')
      
      expect(branches.length).toBe(3) // main + 2 forks
      expect(branches.map(b => b.id)).toContain('main')
      expect(branches.map(b => b.id)).toContain('fork-1')
      expect(branches.map(b => b.id)).toContain('fork-2')
    })

    it('should delete a branch', () => {
      manager.forkBranch('test-session', 'fork-1')
      
      const success = manager.deleteBranch('test-session', 'fork-1')
      
      expect(success).toBe(true)
      const branches = manager.listBranches('test-session')
      expect(branches.map(b => b.id)).not.toContain('fork-1')
    })

    it('should not delete active branch', () => {
      expect(() => {
        manager.deleteBranch('test-session', 'main')
      }).toThrow()
    })
  })

  describe('Tree Traversal', () => {
    beforeEach(() => {
      manager.createSession('test-session', 'test-channel', 'test-user', config)
      manager.addTurn('test-session', { role: 'user', content: 'Turn 1' })
      manager.addTurn('test-session', { role: 'assistant', content: 'Response 1' })
      manager.addTurn('test-session', { role: 'user', content: 'Turn 2' })
    })

    it('should get all turns in a branch', () => {
      const turns = manager.getBranchTurns('test-session', 'main')
      
      expect(turns.length).toBe(3)
      expect(turns[0].content).toBe('Turn 1')
      expect(turns[1].content).toBe('Response 1')
      expect(turns[2].content).toBe('Turn 2')
    })

    it('should get path to a turn', () => {
      const session = manager.getSession('test-session')
      const lastTurnId = session?.branches.get('main')?.currentTurnId
      
      if (lastTurnId) {
        const path = manager.getPathToTurn('test-session', lastTurnId)
        
        expect(path.length).toBe(3)
        expect(path[0].content).toBe('Turn 1')
        expect(path[2].content).toBe('Turn 2')
      }
    })

    it('should find siblings of a turn', () => {
      // Create fork to have siblings
      const turn1 = manager.addTurn('test-session', { role: 'user', content: 'Before fork' })
      
      // Fork and add different responses
      manager.forkBranch('test-session', 'fork-1')
      manager.switchBranch('test-session', 'fork-1')
      const forkTurn = manager.addTurn('test-session', { role: 'assistant', content: 'Fork response' })
      
      manager.switchBranch('test-session', 'main')
      const mainTurn = manager.addTurn('test-session', { role: 'assistant', content: 'Main response' })
      
      // Get siblings of main response
      const siblings = manager.getSiblings('test-session', mainTurn)
      
      expect(siblings.length).toBe(1)
      expect(siblings[0].content).toBe('Fork response')
    })

    it('should find common ancestor', () => {
      const turn1 = manager.addTurn('test-session', { role: 'user', content: 'Common ancestor' })
      
      // Fork
      manager.forkBranch('test-session', 'fork-1')
      manager.switchBranch('test-session', 'fork-1')
      const forkTurn = manager.addTurn('test-session', { role: 'assistant', content: 'Fork path' })
      
      manager.switchBranch('test-session', 'main')
      const mainTurn = manager.addTurn('test-session', { role: 'assistant', content: 'Main path' })
      
      const ancestor = manager.findCommonAncestor('test-session', forkTurn, mainTurn)
      
      expect(ancestor).toBeDefined()
      expect(ancestor?.content).toBe('Common ancestor')
    })
  })

  describe('Decision Points', () => {
    beforeEach(() => {
      manager.createSession('test-session', 'test-channel', 'test-user', config)
      manager.addTurn('test-session', { role: 'user', content: 'Decision point' })
    })

    it('should create a decision point with alternatives', () => {
      const session = manager.getSession('test-session')
      const turnId = session?.branches.get('main')?.currentTurnId
      
      if (turnId) {
        const decisionPoint = manager.createDecisionPoint(
          'test-session',
          turnId,
          [
            { id: 'alt-1', label: 'Alternative 1' },
            { id: 'alt-2', label: 'Alternative 2' },
          ],
          'alt-1'
        )

        expect(decisionPoint).toBeDefined()
        expect(decisionPoint.alternatives.length).toBe(2)
        expect(decisionPoint.chosenAlternativeId).toBe('alt-1')
      }
    })

    it('should create branches for alternatives', () => {
      const session = manager.getSession('test-session')
      const turnId = session?.branches.get('main')?.currentTurnId
      
      if (turnId) {
        manager.createDecisionPoint(
          'test-session',
          turnId,
          [
            { id: 'alt-1', label: 'Alternative 1' },
            { id: 'alt-2', label: 'Alternative 2' },
          ],
          'alt-1'
        )

        const branches = manager.listBranches('test-session')
        expect(branches.map(b => b.id)).toContain('alt-1')
        expect(branches.map(b => b.id)).toContain('alt-2')
      }
    })
  })

  describe('Serialization', () => {
    beforeEach(() => {
      manager.createSession('test-session', 'test-channel', 'test-user', config)
      manager.addTurn('test-session', { role: 'user', content: 'Turn 1' })
      manager.addTurn('test-session', { role: 'assistant', content: 'Response 1' })
    })

    it('should serialize session to JSON', () => {
      const serialized = manager.serializeSession('test-session')
      
      expect(serialized).toBeDefined()
      expect(serialized?.schemaVersion).toBe(1)
      expect(serialized?.rootTurnId).toBeDefined()
      expect(serialized?.activeBranchId).toBe('main')
    })

    it('should deserialize session from JSON', () => {
      const serialized = manager.serializeSession('test-session')
      
      if (serialized) {
        // Create new session to deserialize into
        const newManager = new BranchingConversationManager()
        newManager.createSession('test-session', 'test-channel', 'test-user', config)
        
        newManager.deserializeSession('test-session', serialized)
        
        const restored = newManager.getSession('test-session')
        expect(restored?.turnTree.size).toBe(2)
        expect(restored?.branches.size).toBe(1)
      }
    })

    it('should provide linear history for compatibility', () => {
      const linearHistory = manager.getLinearHistory('test-session')
      
      expect(linearHistory.length).toBe(2)
      expect(linearHistory[0].role).toBe('user')
      expect(linearHistory[1].role).toBe('assistant')
    })
  })

  describe('Merge Operations', () => {
    beforeEach(() => {
      manager.createSession('test-session', 'test-channel', 'test-user', config)
      manager.addTurn('test-session', { role: 'user', content: 'Common turn' })
    })

    it('should merge branches with append strategy', () => {
      // Add to main
      manager.addTurn('test-session', { role: 'assistant', content: 'Main response' })
      
      // Create fork with different path
      manager.forkBranch('test-session', 'fork-1')
      manager.switchBranch('test-session', 'fork-1')
      manager.addTurn('test-session', { role: 'assistant', content: 'Fork response' })
      
      // Switch back and merge
      manager.switchBranch('test-session', 'main')
      const success = manager.mergeBranch('test-session', 'fork-1', 'append')
      
      expect(success).toBe(true)
      const turns = manager.getBranchTurns('test-session', 'main')
      expect(turns.length).toBe(3) // common + main + fork
    })

    it('should merge branches with replace strategy', () => {
      // Add to main
      manager.addTurn('test-session', { role: 'assistant', content: 'Main response' })
      
      // Create fork
      manager.forkBranch('test-session', 'fork-1')
      manager.switchBranch('test-session', 'fork-1')
      manager.addTurn('test-session', { role: 'assistant', content: 'Fork response' })
      
      // Merge with replace
      manager.switchBranch('test-session', 'main')
      manager.mergeBranch('test-session', 'fork-1', 'replace')
      
      const turns = manager.getBranchTurns('test-session', 'main')
      expect(turns.length).toBe(3) // common + main response + fork response (fork replaced main)
      expect(turns[2].content).toBe('Fork response')
    })
  })
})
