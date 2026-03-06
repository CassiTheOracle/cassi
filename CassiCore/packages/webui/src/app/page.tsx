'use client'
import Sidebar from '@/components/chat/Sidebar/Sidebar'
import { ChatArea } from '@/components/chat/ChatArea'
import IntelligencePanel from '@/components/cassicore/IntelligencePanel'
import MemorySearch from '@/components/cassicore/MemorySearch'
import { useCassiCoreData } from '@/hooks/useCassiCoreData'
import { Suspense } from 'react'

function CassiCoreApp() {
  // Poll daemon for health, providers, models, intelligence activity
  useCassiCoreData()

  return (
    <div className="flex h-screen bg-background/80">
      <Sidebar />
      <ChatArea />
      <IntelligencePanel />
      <MemorySearch />
    </div>
  )
}

export default function Home() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <CassiCoreApp />
    </Suspense>
  )
}
