import { useMemo } from 'react'
import * as THREE from 'three'
import { Stars } from '@react-three/drei'

function ReferenceGrid() {
  const gridGeo = useMemo(() => {
    const points: number[] = []
    const EXTENT = 60
    const STEP = 10

    for (let x = -EXTENT; x <= EXTENT; x += STEP) {
      points.push(x, -EXTENT, -20, x, EXTENT, -20)
    }
    for (let y = -EXTENT; y <= EXTENT; y += STEP) {
      points.push(-EXTENT, y, -20, EXTENT, y, -20)
    }

    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.Float32BufferAttribute(points, 3))
    return geo
  }, [])

  return (
    <lineSegments geometry={gridGeo}>
      <lineBasicMaterial color="#1a1a2e" transparent opacity={0.3} />
    </lineSegments>
  )
}

function AxisLines() {
  const geo = useMemo(() => {
    const points = [
      -80, 0, 0, 80, 0, 0,
      0, -80, 0, 0, 80, 0,
      0, 0, -30, 0, 0, 30,
    ]
    const colors = [
      0.3, 0.1, 0.1, 0.3, 0.1, 0.1,
      0.1, 0.3, 0.1, 0.1, 0.3, 0.1,
      0.1, 0.1, 0.3, 0.1, 0.1, 0.3,
    ]
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.Float32BufferAttribute(points, 3))
    g.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3))
    return g
  }, [])

  return (
    <lineSegments geometry={geo}>
      <lineBasicMaterial vertexColors transparent opacity={0.2} />
    </lineSegments>
  )
}

export function Environment() {
  return (
    <>
      <Stars
        radius={300}
        depth={200}
        count={3000}
        factor={2}
        saturation={0.1}
        fade
        speed={0.3}
      />
      <ReferenceGrid />
      <AxisLines />
    </>
  )
}
