'use client'

import ChatInput from './ChatInput/index.js'
import MessageArea from './MessageArea.js'

const ChatArea = () => {
  return (
    <main className="relative m-1.5 flex min-w-0 flex-grow flex-col rounded-xl bg-background">
      <MessageArea />
      <div className="sticky bottom-0 ml-9 px-4 pb-2">
        <ChatInput />
      </div>
    </main>
  )
}

export default ChatArea


