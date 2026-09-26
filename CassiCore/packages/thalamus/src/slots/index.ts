export { UserSlot } from './user-slot.js'
export { ToolCallSlot } from './tool-call-slot.js'
export { ToolResultSlot } from './tool-result-slot.js'
export { AssistantSlot } from './assistant-slot.js'
export { SystemSlot } from './system-slot.js'

import type { MessageSlot } from '../types.js'
import { UserSlot } from './user-slot.js'
import { ToolCallSlot } from './tool-call-slot.js'
import { ToolResultSlot } from './tool-result-slot.js'
import { AssistantSlot } from './assistant-slot.js'
import { SystemSlot } from './system-slot.js'

/**
 * Create all five slot instances. Order matters: more specific matches
 * (tool_call, tool_result) must be checked before generic ones
 * (assistant, user).
 */
export function createSlots(): MessageSlot[] {
  return [
    new SystemSlot(),
    new ToolCallSlot(),
    new ToolResultSlot(),
    new UserSlot(),
    new AssistantSlot(),
  ]
}
