'use client'

import ChatInput from './ChatInput'
import MessageArea from './MessageArea'
import { useStore } from '@/store'

const ChatArea = () => {
  const { intelPanelOpen } = useStore()
  return (
    <main className="relative m-1.5 flex flex-grow flex-col rounded-xl bg-background">
      <MessageArea />
      {/* Pad only the input footer away from the Intel panel */}
      <div
        className={`sticky bottom-0 ml-9 px-4 pb-2 transition-all duration-300 ${
          intelPanelOpen ? 'pr-[308px]' : ''
        }`}
      >
        <ChatInput />
      </div>
    </main>
  )
}

export default ChatArea


