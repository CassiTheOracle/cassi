import { useRef, useEffect } from 'react'
import { useThree, useFrame } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'

const LAUNCH_DURATION = 4.0
const HELIX_TURNS = 1.5
const START_Z = -30
const END_DISTANCE = 50

export function Camera() {
  const controlsRef = useRef<any>(null)
  const { camera } = useThree()
  const launchProgress = useRef(0)
  const launching = useRef(true)

  useEffect(() => {
    camera.position.set(0, 0, START_Z)
    camera.lookAt(0, 0, 0)
  }, [camera])

  useFrame((_state, delta) => {
    if (!launching.current) return

    launchProgress.current += delta / LAUNCH_DURATION
    const t = Math.min(launchProgress.current, 1)

    // ease-out cubic
    const ease = 1 - Math.pow(1 - t, 3)

    // helix spiral: ascend through timeline, spiral outward, settle at orbit distance
    const angle = ease * Math.PI * 2 * HELIX_TURNS
    const radius = ease * END_DISTANCE * 0.6
    const z = THREE.MathUtils.lerp(START_Z, END_DISTANCE * 0.4, ease)

    camera.position.set(
      Math.sin(angle) * radius,
      Math.cos(angle) * radius * 0.3,
      z,
    )
    camera.lookAt(0, 0, 0)

    if (t >= 1) {
      launching.current = false
      if (controlsRef.current) controlsRef.current.enabled = true
    } else {
      if (controlsRef.current) controlsRef.current.enabled = false
    }
  })

  return (
    <OrbitControls
      ref={controlsRef}
      enableDamping
      dampingFactor={0.08}
      minDistance={0.1}
      maxDistance={100000}
      rotateSpeed={1.2}
      zoomSpeed={3.0}
      panSpeed={1.5}
    />
  )
}
