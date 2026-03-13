'use client'
import Sidebar from '@/components/chat/Sidebar/Sidebar'
import { ChatArea } from '@/components/chat/ChatArea'
import IntelligenceDrawer from '@/components/cassicore/IntelligenceDrawer'
import DialecticColumn from '@/components/cassicore/DialecticColumn'
import MemorySearch from '@/components/cassicore/MemorySearch'
import { useCassiCoreData } from '@/hooks/useCassiCoreData'
import { useStore } from '@/store'
import { Suspense } from 'react'

function CassiCoreApp() {
  // Poll daemon for health, providers, models, intelligence activity
  useCassiCoreData()

  const {
    yinCollapsed, setYinCollapsed,
    yangCollapsed, setYangCollapsed,
    dialecticVisible,
  } = useStore()

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background/80">
      {/* Main area: sidebar + dialectic columns + chat */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <Sidebar />

        {/* Yin column (left) */}
        {dialecticVisible && (
          <DialecticColumn
            voice="yin"
            collapsed={yinCollapsed}
            onToggle={() => setYinCollapsed(!yinCollapsed)}
          />
        )}

        {/* Chat (center, grows to fill) */}
        <ChatArea />

        {/* Yang column (right) */}
        {dialecticVisible && (
          <DialecticColumn
            voice="yang"
            collapsed={yangCollapsed}
            onToggle={() => setYangCollapsed(!yangCollapsed)}
          />
        )}
      </div>

      {/* Intelligence drawer (bottom) */}
      <IntelligenceDrawer />
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
