'use client'

import { motion } from 'framer-motion'
import Icon from '@/components/ui/icon'
import React from 'react'
import { useStore } from '@/store'

const StatusBadge = ({ label, status }: { label: string; status: 'active' | 'inactive' }) => (
  <div className="flex items-center gap-2 rounded-lg bg-background-secondary px-3 py-1.5">
    <div className={`size-1.5 rounded-full ${status === 'active' ? 'bg-positive' : 'bg-muted'}`} />
    <span className="font-dmmono text-xs uppercase text-muted">{label}</span>
  </div>
)

interface PromptChip {
  label: string
  prompt: string
}

const QUICK_PROMPTS: PromptChip[] = [
  { label: 'Analyze a bug', prompt: 'Help me debug this issue: ' },
  { label: 'Plan a feature', prompt: 'Help me plan and design a feature: ' },
  { label: 'Review code', prompt: 'Please review this code and suggest improvements:\n\n```\n\n```' },
  { label: 'Think deeply', prompt: '/think What should I focus on in my current project?' },
  { label: 'Search memory', prompt: '/memory ' },
  { label: 'Dialectic analysis', prompt: '/dialectic Analyze the pros and cons of: ' },
]

const ChatBlankState = () => {
  const { chatInputRef } = useStore()

  const fillInput = (text: string) => {
    const el = chatInputRef?.current
    if (!el) return
    // Use native input value setter so React state updates
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLTextAreaElement.prototype, 'value'
    )?.set
    nativeInputValueSetter?.call(el, text)
    el.dispatchEvent(new Event('input', { bubbles: true }))
    el.focus()
    // Position cursor at end
    el.setSelectionRange(text.length, text.length)
  }

  return (
    <section
      className="flex flex-col items-center text-center font-geist"
      aria-label="Welcome message"
    >
      <div className="flex max-w-xl flex-col gap-y-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4, delay: 0.2 }}
          className="flex justify-center"
        >
          <Icon type="reasoning" size="lg" />
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="text-2xl font-semibold tracking-tight text-primary"
        >
          CassiCore
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="text-sm text-muted"
        >
          Cognitive agent daemon with dialectic reasoning, persistent memory,
          and multi-agent orchestration.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.5 }}
          className="flex flex-wrap justify-center gap-2"
        >
          <StatusBadge label="Dialectic" status="active" />
          <StatusBadge label="Memory" status="active" />
          <StatusBadge label="Thinker" status="active" />
          <StatusBadge label="Subconscious" status="active" />
          <StatusBadge label="Teams" status="active" />
        </motion.div>

        {/* Quick-action prompt starters */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.6 }}
          className="grid grid-cols-2 gap-2"
        >
          {QUICK_PROMPTS.map((chip) => (
            <button
              key={chip.label}
              type="button"
              onClick={() => fillInput(chip.prompt)}
              className="rounded-lg border border-primary/10 bg-accent/50 px-3 py-2 text-left text-[11px] text-muted/70 transition-colors hover:border-primary/20 hover:bg-accent hover:text-primary"
            >
              {chip.label}
            </button>
          ))}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.7 }}
          className="flex flex-col items-center gap-2 text-xs text-muted/60"
        >
          <p>
            Type a message or use{' '}
            <span className="font-dmmono text-muted">/think</span>,{' '}
            <span className="font-dmmono text-muted">/memory</span>,{' '}
            <span className="font-dmmono text-muted">/dialectic</span> commands
          </p>
        </motion.div>
      </div>
    </section>
  )
}

export default ChatBlankState
