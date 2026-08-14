import { useRef, useMemo, useEffect, useCallback } from 'react'
import { useFrame, useThree, type ThreeEvent } from '@react-three/fiber'
import * as THREE from 'three'
import { useStore } from '../store.js'
import { ENGRAM_TYPES, getViewMode } from './view-utils.js'
import { api } from '../api/client.js'

import engramVert from '../shaders/engram.vert.glsl?raw'
import engramFrag from '../shaders/engram.frag.glsl?raw'

export function FieldCloud() {
  const pointsRef = useRef<THREE.Points>(null)
  const positions = useStore((s) => s.positions)
  const viewMode = useStore((s) => s.viewMode)
  const kindleState = useStore((s) => s.kindle)
  const { raycaster } = useThree()

  const geoRef = useRef<THREE.BufferGeometry | null>(null)
  const matRef = useRef<THREE.ShaderMaterial | null>(null)
  const hoverThrottleRef = useRef(0)

  useEffect(() => {
    if (raycaster.params.Points) {
      raycaster.params.Points.threshold = 0.8
    }
  }, [raycaster])

  const count = positions.length

  const { geometry, material, idMap } = useMemo(() => {
    if (geoRef.current) geoRef.current.dispose()
    if (matRef.current) matRef.current.dispose()

    if (count === 0) {
      const emptyGeo = new THREE.BufferGeometry()
      const emptyMat = new THREE.ShaderMaterial()
      geoRef.current = emptyGeo
      matRef.current = emptyMat
      return {
        geometry: emptyGeo,
        material: emptyMat,
        idMap: new Map<number, string>(),
      }
    }

    const vm = getViewMode(viewMode)
    const posArr = vm.compute(positions)
    const potArr = new Float32Array(count)
    const typeArr = new Float32Array(count)
    const kindleArr = new Float32Array(count)
    const ids = new Map<number, string>()

    let potMax = 0
    for (let i = 0; i < count; i++) {
      if (positions[i].potentiation > potMax) potMax = positions[i].potentiation
    }
    const potScale = potMax || 1

    for (let i = 0; i < count; i++) {
      potArr[i] = positions[i].potentiation / potScale
      typeArr[i] = ENGRAM_TYPES.indexOf(positions[i].nodeType)
      kindleArr[i] = 0
      ids.set(i, positions[i].id)
    }

    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.Float32BufferAttribute(posArr, 3))
    geo.setAttribute('a_potentiation', new THREE.Float32BufferAttribute(potArr, 1))
    geo.setAttribute('a_typeIndex', new THREE.Float32BufferAttribute(typeArr, 1))
    geo.setAttribute('a_kindleCharge', new THREE.Float32BufferAttribute(kindleArr, 1))
    geo.computeBoundingSphere()

    const mat = new THREE.ShaderMaterial({
      vertexShader: engramVert,
      fragmentShader: engramFrag,
      uniforms: {
        uPointScale: { value: 1.0 },
        uHoveredIndex: { value: -1.0 },
      },
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })

    geoRef.current = geo
    matRef.current = mat

    return { geometry: geo, material: mat, idMap: ids }
  }, [positions, viewMode, count])

  useEffect(() => {
    return () => {
      if (geoRef.current) geoRef.current.dispose()
      if (matRef.current) matRef.current.dispose()
    }
  }, [])

  useEffect(() => {
    if (count === 0) return
    const vm = getViewMode(viewMode)
    const posArr = vm.compute(positions)
    const attr = geometry.getAttribute('position') as THREE.Float32BufferAttribute
    if (attr && attr.array.length === posArr.length) {
      attr.array.set(posArr)
      attr.needsUpdate = true
      geometry.computeBoundingSphere()
    }
  }, [viewMode, positions, count, geometry])

  useFrame((_state, delta) => {
    if (!kindleState.playing || !kindleState.luminalSet?.trace) return
    const trace = kindleState.luminalSet.trace
    const store = useStore.getState()
    const frame = store.kindle.frame + delta * store.kindle.speed * 2

    const frameIdx = Math.floor(frame)
    if (frameIdx >= trace.length - 1) {
      useStore.getState().setKindle({ playing: false, frame: trace.length - 1 })
      return
    }

    const frac = frame - frameIdx
    const curr = trace[frameIdx].charges
    const next = trace[Math.min(frameIdx + 1, trace.length - 1)].charges

    const kindleAttr = geometry.getAttribute('a_kindleCharge') as THREE.Float32BufferAttribute
    if (!kindleAttr) return

    for (let i = 0; i < count; i++) {
      const id = idMap.get(i)!
      const c0 = curr[id] ?? 0
      const c1 = next[id] ?? 0
      kindleAttr.array[i] = c0 + (c1 - c0) * frac
    }
    kindleAttr.needsUpdate = true
    useStore.getState().setKindle({ frame })
  })

  const handleClick = useCallback((e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation()
    if (e.index === undefined) return
    const id = idMap.get(e.index)
    if (!id) return
    useStore.getState().setSelectedEngram(id)
    api.getNeighbors(id).then((d) => useStore.getState().setDetailData(d))
  }, [idMap])

  const handlePointerMove = useCallback((e: ThreeEvent<PointerEvent>) => {
    const now = performance.now()
    if (now - hoverThrottleRef.current < 50) return
    hoverThrottleRef.current = now

    e.stopPropagation()
    if (e.index === undefined) return
    useStore.getState().setHoveredEngram(idMap.get(e.index) ?? null)
    material.uniforms.uHoveredIndex.value = e.index
  }, [idMap, material])

  const handlePointerLeave = useCallback(() => {
    useStore.getState().setHoveredEngram(null)
    material.uniforms.uHoveredIndex.value = -1
  }, [material])

  if (count === 0) return null

  return (
    <points
      ref={pointsRef}
      geometry={geometry}
      material={material}
      onClick={handleClick}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
    />
  )
}
