import type { ChatMessage } from '@/types/os'

import { AgentMessage, UserMessage } from './MessageItem'
import Tooltip from '@/components/ui/tooltip'
import { memo, useState } from 'react'
import {
  ToolCallProps,
  ReasoningStepProps,
  ReasoningProps,
  ReferenceData,
  Reference
} from '@/types/os'
import React, { type FC } from 'react'

import Icon from '@/components/ui/icon'
import ChatBlankState from './ChatBlankState'

interface MessageListProps {
  messages: ChatMessage[]
}

interface MessageWrapperProps {
  message: ChatMessage
  isLastMessage: boolean
}

interface ReferenceProps {
  references: ReferenceData[]
}

interface ReferenceItemProps {
  reference: Reference
}

const ReferenceItem: FC<ReferenceItemProps> = ({ reference }) => (
  <div className="relative flex h-[63px] w-[190px] cursor-default flex-col justify-between overflow-hidden rounded-md bg-background-secondary p-3 transition-colors hover:bg-background-secondary/80">
    <p className="text-sm font-medium text-primary">{reference.name}</p>
    <p className="truncate text-xs text-primary/40">{reference.content}</p>
  </div>
)

const References: FC<ReferenceProps> = ({ references }) => (
  <div className="flex flex-col gap-4">
    {references.map((referenceData, index) => (
      <div
        key={`${referenceData.query}-${index}`}
        className="flex flex-col gap-3"
      >
        <div className="flex flex-wrap gap-3">
          {referenceData.references.map((reference, refIndex) => (
            <ReferenceItem
              key={`${reference.name}-${reference.meta_data.chunk}-${refIndex}`}
              reference={reference}
            />
          ))}
        </div>
      </div>
    ))}
  </div>
)

const AgentMessageWrapper = ({ message }: MessageWrapperProps) => {
  // Separate Serenity/Synthesis steps from Yang/Yin steps
  // Yang and Yin now live in the side columns; only show non-dialectic + Serenity inline
  const allSteps = message.extra_data?.reasoning_steps ?? []
  const serenitySteps = allSteps.filter(s => {
    const action = (s.action ?? '').toLowerCase()
    return action === 'serenity' || action === 'synthesis' || action === 'synth'
  })
  const otherSteps = allSteps.filter(s => {
    const action = (s.action ?? '').toLowerCase()
    return action !== 'yang' && action !== 'yin' && action !== 'serenity' && action !== 'synthesis' && action !== 'synth'
  })

  return (
    <div className="flex flex-col gap-y-9">
      {/* Serenity synthesis — displayed as a prominent inline block */}
      {serenitySteps.length > 0 && (
        <div className="rounded-lg border border-purple-500/20 bg-purple-500/5 px-4 py-3">
          <div className="mb-2 flex items-center gap-2">
            <div className="size-2 rounded-full bg-purple-400" />
            <span className="text-[10px] font-medium uppercase text-purple-400">Synthesis</span>
            {serenitySteps[0]?.confidence !== undefined && (
              <span className="font-dmmono text-[9px] text-purple-400/60">
                {Math.round(serenitySteps[0].confidence * 100)}% confidence
              </span>
            )}
          </div>
          {serenitySteps.map((step, idx) => (
            <div key={`serenity-${idx}`} className="text-xs leading-relaxed text-primary/80">
              {step.title && <p className="mb-1 font-medium text-purple-300">{step.title}</p>}
              <p className="whitespace-pre-wrap">{step.result || step.reasoning || ''}</p>
            </div>
          ))}
        </div>
      )}

      {/* Other reasoning steps (non-yang/yin, non-serenity — e.g. think steps) */}
      {otherSteps.length > 0 && (
        <div className="flex items-start gap-4">
          <Tooltip
            delayDuration={0}
            content={<p className="text-accent">Reasoning</p>}
            side="top"
          >
            <Icon type="reasoning" size="sm" />
          </Tooltip>
          <div className="flex flex-col gap-3">
            <p className="text-xs uppercase text-amber-400">Reasoning</p>
            <Reasonings reasoning={otherSteps} />
          </div>
        </div>
      )}

      {message.extra_data?.references &&
        message.extra_data.references.length > 0 && (
          <div className="flex items-start gap-4">
            <Tooltip
              delayDuration={0}
              content={<p className="text-accent">References</p>}
              side="top"
            >
              <Icon type="references" size="sm" />
            </Tooltip>
            <div className="flex flex-col gap-3">
              <References references={message.extra_data.references} />
            </div>
          </div>
        )}
      {message.tool_calls && message.tool_calls.length > 0 && (
        <div className="flex items-start gap-3">
          <Tooltip
            delayDuration={0}
            content={<p className="text-accent">Tool Calls</p>}
            side="top"
          >
            <Icon
              type="hammer"
              className="rounded-lg bg-background-secondary p-1"
              size="sm"
              color="secondary"
            />
          </Tooltip>

          <div className="flex flex-wrap gap-2">
            {message.tool_calls.map((toolCall, index) => (
              <ToolComponent
                key={
                  toolCall.tool_call_id ||
                  `${toolCall.tool_name}-${toolCall.created_at}-${index}`
                }
                tools={toolCall}
              />
            ))}
          </div>
        </div>
      )}
      <AgentMessage message={message} />
    </div>
  )
}
const Reasoning: FC<ReasoningStepProps> = ({ index, step }) => {
  const [open, setOpen] = useState(false)
  // Map dialectic stage to visual styles
  const dialecticStyles: Record<string, { label: string; color: string }> = {
    yang: { label: 'YANG', color: 'bg-red-500/20 text-red-400' },
    yin: { label: 'YIN', color: 'bg-blue-500/20 text-blue-400' },
    synthesis: { label: 'SYNTH', color: 'bg-purple-500/20 text-purple-400' },
    serenity: { label: 'SYNTH', color: 'bg-purple-500/20 text-purple-400' },
    think: { label: 'THINK', color: 'bg-amber-500/20 text-amber-400' }
  }
  const stage = (step.action ?? '').toLowerCase()
  const style = dialecticStyles[stage] ?? null
  const content = step.result || step.reasoning || ''

  return (
    <div className="w-full">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 text-secondary hover:text-primary transition-colors cursor-pointer"
      >
        <div className={`flex h-[20px] shrink-0 items-center rounded-md px-2 ${style?.color ?? 'bg-background-secondary'}`}>
          <p className="text-xs font-medium">{style?.label ?? `STEP ${index + 1}`}</p>
        </div>
        <p className="text-xs truncate flex-1 text-left">{step.title}</p>
        <svg
          className={`w-3 h-3 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && content && (
        <div className="mt-2 ml-1 pl-3 border-l border-border text-xs text-secondary whitespace-pre-wrap leading-relaxed max-h-[300px] overflow-y-auto">
          {content}
        </div>
      )}
    </div>
  )
}
const Reasonings: FC<ReasoningProps> = ({ reasoning }) => (
  <div className="flex flex-col items-start justify-center gap-2 w-full">
    {reasoning.map((step, index) => (
      <Reasoning
        key={`${step.title}-${step.action}-${index}`}
        step={step}
        index={index}
      />
    ))}
  </div>
)

const ToolComponent = memo(({ tools }: ToolCallProps) => {
  const isError = tools.tool_call_error
  const duration = tools.metrics?.time
    ? `${Math.round(tools.metrics.time as number)}ms`
    : null

  return (
    <div className={`flex cursor-default items-center gap-1.5 rounded-full px-2.5 py-1.5 text-xs ${
      isError ? 'bg-destructive/10' : 'bg-accent'
    }`}>
      <Icon
        type="hammer"
        size="xxs"
        className={isError ? 'text-destructive' : 'text-primary/60'}
      />
      <p className={`font-dmmono uppercase ${isError ? 'text-destructive' : 'text-primary/80'}`}>
        {tools.tool_name}
      </p>
      {duration && (
        <span className="font-dmmono text-[10px] text-muted/50">{duration}</span>
      )}
    </div>
  )
})
ToolComponent.displayName = 'ToolComponent'
const Messages = ({ messages }: MessageListProps) => {
  if (messages.length === 0) {
    return <ChatBlankState />
  }

  return (
    <>
      {messages.map((message, index) => {
        const key = `${message.role}-${message.created_at}-${index}`
        const isLastMessage = index === messages.length - 1

        if (message.role === 'agent') {
          return (
            <AgentMessageWrapper
              key={key}
              message={message}
              isLastMessage={isLastMessage}
            />
          )
        }
        return <UserMessage key={key} message={message} />
      })}
    </>
  )
}

export default Messages
