import { Canvas } from '@react-three/fiber'
import { useEffect } from 'react'
import { api } from './api/client.js'
import { useStore } from './store.js'
import { FieldCloud } from './scene/FieldCloud.js'
import { Camera } from './scene/Camera.js'
import { PostProcessing } from './scene/PostProcessing.js'
import { Environment } from './scene/Environment.js'
import { DetailPanel } from './ui/DetailPanel.js'
import { SearchBar } from './ui/SearchBar.js'
import { ViewSwitcher } from './ui/ViewSwitcher.js'
import { StatsOverlay } from './ui/StatsOverlay.js'

export function App() {
  const setPositions = useStore((s) => s.setPositions)
  const setStats = useStore((s) => s.setStats)

  useEffect(() => {
    api.getPositions().then((r) => setPositions(r.positions))
    api.getStats().then((r) => setStats(r.stats))
  }, [setPositions, setStats])

  return (
    <div className="relative w-full h-full">
      <Canvas
        gl={{ antialias: false, alpha: false }}
        camera={{ position: [0, 0, 50], fov: 60, near: 0.01, far: 200000 }}
        style={{ background: '#000' }}
      >
        <Camera />
        <Environment />
        <FieldCloud />
        <PostProcessing />
      </Canvas>
      <DetailPanel />
      <SearchBar />
      <ViewSwitcher />
      <StatsOverlay />
    </div>
  )
}
