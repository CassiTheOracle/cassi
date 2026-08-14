import { EffectComposer, Bloom } from '@react-three/postprocessing'

export function PostProcessing() {
  return (
    <EffectComposer multisampling={0}>
      <Bloom
        intensity={0.8}
        luminanceThreshold={0.3}
        luminanceSmoothing={0.5}
      />
    </EffectComposer>
  )
}
