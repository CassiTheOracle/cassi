'use client'
import { useState } from 'react'
import { toast } from 'sonner'
import { TextArea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { useStore } from '@/store'
import useAIChatStreamHandler from '@/hooks/useAIStreamHandler'
import { useQueryState } from 'nuqs'
import Icon from '@/components/ui/icon'

const THINKING_LEVELS = ['none', 'low', 'medium', 'high'] as const

const ThinkingSelector = () => {
  const { selectedThinking, setSelectedThinking } = useStore()
  const cycleThinking = () => {
    const idx = THINKING_LEVELS.indexOf(selectedThinking)
    setSelectedThinking(THINKING_LEVELS[(idx + 1) % THINKING_LEVELS.length])
  }
  const colors: Record<string, string> = {
    none: 'text-muted/40',
    low: 'text-muted',
    medium: 'text-positive',
    high: 'text-brand'
  }
  return (
    <button
      onClick={cycleThinking}
      className={`flex items-center gap-1 rounded-lg px-2 py-1 text-[10px] font-medium uppercase transition-colors hover:bg-accent ${colors[selectedThinking] ?? 'text-muted'}`}
      title={`Thinking: ${selectedThinking}`}
      type="button"
    >
      <Icon type="reasoning" size="xxs" />
      <span className="font-dmmono">{selectedThinking}</span>
    </button>
  )
}

const ChatInput = () => {
  const { chatInputRef, selectedEndpoint, setMessages } = useStore()
  const { handleStreamResponse } = useAIChatStreamHandler()
  const [selectedAgent] = useQueryState('agent')
  const [teamId] = useQueryState('team')
  const [sessionId] = useQueryState('session')
  const [inputMessage, setInputMessage] = useState('')
  const isStreaming = useStore((state) => state.isStreaming)

  const handleSlashCommand = async (command: string) => {
    if (!sessionId) {
      toast.error('No active session for slash command')
      return
    }
    try {
      const res = await fetch(`${selectedEndpoint}/api/cassicore/sessions/${sessionId}/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command })
      })
      const data = await res.json()
      if (data.text) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'user' as const,
            content: command,
            created_at: Math.floor(Date.now() / 1000)
          },
          {
            role: 'agent' as const,
            content: data.text,
            created_at: Math.floor(Date.now() / 1000)
          }
        ])
      }
    } catch (error) {
      toast.error(`Command failed: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  const handleSubmit = async () => {
    if (!inputMessage.trim()) return
    const currentMessage = inputMessage
    setInputMessage('')

    if (currentMessage.startsWith('/')) {
      await handleSlashCommand(currentMessage)
      return
    }

    try {
      await handleStreamResponse(currentMessage)
    } catch (error) {
      toast.error(
        `Error: ${error instanceof Error ? error.message : String(error)}`
      )
    }
  }

  return (
    <div className="relative mx-auto mb-1 flex w-full max-w-2xl flex-col gap-1 font-geist">
      <div className="flex items-center gap-1 px-1">
        <ThinkingSelector />
      </div>
      <div className="flex items-end justify-center gap-x-2">
        <TextArea
          placeholder={inputMessage.startsWith('/') ? 'Slash command...' : 'Ask anything'}
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyDown={(e) => {
            if (
              e.key === 'Enter' &&
              !e.nativeEvent.isComposing &&
              !e.shiftKey &&
              !isStreaming
            ) {
              e.preventDefault()
              handleSubmit()
            }
          }}
          className={`w-full border px-4 text-sm text-primary focus:border-accent ${
            inputMessage.startsWith('/')
              ? 'border-brand/30 bg-primaryAccent'
              : 'border-accent bg-primaryAccent'
          }`}
          disabled={!(selectedAgent || teamId)}
          ref={chatInputRef}
        />
        <Button
          onClick={handleSubmit}
          disabled={
            !(selectedAgent || teamId) || !inputMessage.trim() || isStreaming
          }
          size="icon"
          className="rounded-xl bg-primary p-5 text-primaryAccent"
        >
          <Icon type="send" color="primaryAccent" />
        </Button>
      </div>
    </div>
  )
}

export default ChatInput
