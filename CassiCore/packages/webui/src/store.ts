import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

import {
  AgentDetails,
  SessionEntry,
  TeamDetails,
  type ChatMessage
} from '@/types/os'

interface Store {
  hydrated: boolean
  setHydrated: () => void
  streamingErrorMessage: string
  setStreamingErrorMessage: (streamingErrorMessage: string) => void
  endpoints: {
    endpoint: string
    id__endpoint: string
  }[]
  setEndpoints: (
    endpoints: {
      endpoint: string
      id__endpoint: string
    }[]
  ) => void
  isStreaming: boolean
  setIsStreaming: (isStreaming: boolean) => void
  isEndpointActive: boolean
  setIsEndpointActive: (isActive: boolean) => void
  isEndpointLoading: boolean
  setIsEndpointLoading: (isLoading: boolean) => void
  messages: ChatMessage[]
  setMessages: (
    messages: ChatMessage[] | ((prevMessages: ChatMessage[]) => ChatMessage[])
  ) => void
  chatInputRef: React.RefObject<HTMLTextAreaElement | null>
  selectedEndpoint: string
  setSelectedEndpoint: (selectedEndpoint: string) => void
  authToken: string
  setAuthToken: (authToken: string) => void
  agents: AgentDetails[]
  setAgents: (agents: AgentDetails[]) => void
  teams: TeamDetails[]
  setTeams: (teams: TeamDetails[]) => void
  selectedModel: string
  setSelectedModel: (model: string) => void
  mode: 'agent' | 'team'
  setMode: (mode: 'agent' | 'team') => void
  sessionsData: SessionEntry[] | null
  setSessionsData: (
    sessionsData:
      | SessionEntry[]
      | ((prevSessions: SessionEntry[] | null) => SessionEntry[] | null)
  ) => void
  isSessionsLoading: boolean
  setIsSessionsLoading: (isSessionsLoading: boolean) => void
  daemonInfo: Record<string, unknown> | null
  setDaemonInfo: (info: Record<string, unknown> | null) => void
  intelligenceActivity: Record<string, unknown> | null
  setIntelligenceActivity: (activity: Record<string, unknown> | null) => void
  providerHealth: Record<string, unknown>[]
  setProviderHealth: (providers: Record<string, unknown>[]) => void
  availableModels: Record<string, unknown>[]
  setAvailableModels: (models: Record<string, unknown>[]) => void
  selectedThinking: 'none' | 'low' | 'medium' | 'high'
  setSelectedThinking: (level: 'none' | 'low' | 'medium' | 'high') => void
  intelPanelOpen: boolean
  setIntelPanelOpen: (open: boolean) => void
  yinCollapsed: boolean
  setYinCollapsed: (collapsed: boolean) => void
  yangCollapsed: boolean
  setYangCollapsed: (collapsed: boolean) => void
  dialecticVisible: boolean
  setDialecticVisible: (visible: boolean) => void
}

export const useStore = create<Store>()(
  persist(
    (set) => ({
      hydrated: false,
      setHydrated: () => set({ hydrated: true }),
      streamingErrorMessage: '',
      setStreamingErrorMessage: (streamingErrorMessage) =>
        set(() => ({ streamingErrorMessage })),
      endpoints: [],
      setEndpoints: (endpoints) => set(() => ({ endpoints })),
      isStreaming: false,
      setIsStreaming: (isStreaming) => set(() => ({ isStreaming })),
      isEndpointActive: false,
      setIsEndpointActive: (isActive) =>
        set(() => ({ isEndpointActive: isActive })),
      isEndpointLoading: true,
      setIsEndpointLoading: (isLoading) =>
        set(() => ({ isEndpointLoading: isLoading })),
      messages: [],
      setMessages: (messages) =>
        set((state) => ({
          messages:
            typeof messages === 'function' ? messages(state.messages) : messages
        })),
      chatInputRef: { current: null },
      // Default to the Next.js BFF (self) which proxies CassiCore's Admin API.
      // Override NEXT_PUBLIC_DEFAULT_ENDPOINT for non-localhost deployments.
      selectedEndpoint: process.env.NEXT_PUBLIC_DEFAULT_ENDPOINT ?? 'http://localhost:3000',
      setSelectedEndpoint: (selectedEndpoint) =>
        set(() => ({ selectedEndpoint })),
      authToken: '',
      setAuthToken: (authToken) => set(() => ({ authToken })),
      agents: [],
      setAgents: (agents) => set({ agents }),
      teams: [],
      setTeams: (teams) => set({ teams }),
      selectedModel: '',
      setSelectedModel: (selectedModel) => set(() => ({ selectedModel })),
      mode: 'agent',
      setMode: (mode) => set(() => ({ mode })),
      sessionsData: null,
      setSessionsData: (sessionsData) =>
        set((state) => ({
          sessionsData:
            typeof sessionsData === 'function'
              ? sessionsData(state.sessionsData)
              : sessionsData
        })),
      isSessionsLoading: false,
      setIsSessionsLoading: (isSessionsLoading) =>
        set(() => ({ isSessionsLoading })),
      daemonInfo: null,
      setDaemonInfo: (info) => set(() => ({ daemonInfo: info })),
      intelligenceActivity: null,
      setIntelligenceActivity: (activity) =>
        set(() => ({ intelligenceActivity: activity })),
      providerHealth: [],
      setProviderHealth: (providers) =>
        set(() => ({ providerHealth: providers })),
      availableModels: [],
      setAvailableModels: (models) =>
        set(() => ({ availableModels: models })),
      selectedThinking: 'medium',
      setSelectedThinking: (level) =>
        set(() => ({ selectedThinking: level })),
      intelPanelOpen: false,
      setIntelPanelOpen: (open: boolean) => set(() => ({ intelPanelOpen: open })),
      yinCollapsed: true,
      setYinCollapsed: (collapsed: boolean) => set(() => ({ yinCollapsed: collapsed })),
      yangCollapsed: true,
      setYangCollapsed: (collapsed: boolean) => set(() => ({ yangCollapsed: collapsed })),
      dialecticVisible: true,
      setDialecticVisible: (visible: boolean) => set(() => ({ dialecticVisible: visible }))
    }),
    {
      name: 'endpoint-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        selectedEndpoint: state.selectedEndpoint,
        selectedThinking: state.selectedThinking
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHydrated?.()
      }
    }
  )
)
