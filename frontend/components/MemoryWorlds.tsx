'use client';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Text } from '@react-three/drei';
import { useEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';
import { MemoryNode } from '../lib/types';

function MemoryStar({ memory, index }: { memory: MemoryNode; index: number }) {
  const ref = useRef<THREE.Mesh>(null);
  const geometry = useMemo(() => new THREE.SphereGeometry(0.05 + 0.1 * Math.max(0.2, memory.brightness), 18, 18), [memory.brightness]);
  const material = useMemo(() => new THREE.MeshStandardMaterial({ color: '#A855F7', emissive: '#A855F7', emissiveIntensity: Math.max(0.2, memory.brightness) * 2.4 }), [memory.brightness]);
  useEffect(() => () => { geometry.dispose(); material.dispose(); }, [geometry, material]);
  const mass = Math.max(0.2, memory.brightness);
  useFrame(({ clock }) => {
    if (!ref.current) return;
    const t = clock.elapsedTime * (0.2 + mass * 0.3) + index;
    ref.current.position.x = memory.position.x / 34 + Math.cos(t) * mass * 0.18;
    ref.current.position.y = memory.position.y / 34 + Math.sin(t) * mass * 0.18;
    ref.current.position.z = memory.position.z / 34;
  });
  return <mesh ref={ref} geometry={geometry} material={material} />;
}

function EnergyBeam({ a, b }: { a: MemoryNode; b: MemoryNode }) {
  const geometry = useMemo(() => new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(a.position.x / 34, a.position.y / 34, a.position.z / 34), new THREE.Vector3(b.position.x / 34, b.position.y / 34, b.position.z / 34)]), [a, b]);
  const material = useMemo(() => new THREE.LineBasicMaterial({ color: '#00E5FF', transparent: true, opacity: 0.28 }), []);
  useEffect(() => () => { geometry.dispose(); material.dispose(); }, [geometry, material]);
  return <line geometry={geometry} material={material} />;
}

export default function MemoryWorlds({ memories }: { memories: MemoryNode[] }) {
  const bounded = memories.slice(0, 240);
  const realms = [...new Set(bounded.map((m) => m.realm))];
  return <div className="h-full min-h-[360px]"><Canvas camera={{ position: [0, 0, 7] }}><ambientLight intensity={0.75} />{realms.map((realm, realmIndex) => { const realmMemories = bounded.filter((m) => m.realm === realm).slice(0, 36); return <group key={realm} position={[Math.cos(realmIndex) * 2.35, Math.sin(realmIndex) * 1.25, 0]}><Text fontSize={0.16} position={[0, 0.62, 0]} color="#EAF6FF">{realm}</Text><mesh><sphereGeometry args={[0.42 + realmMemories.length * 0.006, 32, 32]} /><meshStandardMaterial color="#00E5FF" wireframe transparent opacity={0.32} /></mesh>{realmMemories.length > 1 && realmMemories.slice(1).map((m) => <EnergyBeam key={`beam-${realm}-${m.id}`} a={realmMemories[0]} b={m} />)}{realmMemories.map((m, i) => <MemoryStar key={m.id} memory={m} index={i} />)}</group>; })}<OrbitControls /></Canvas><p className="px-3 pb-3 text-xs text-violet-200">Memory gravity: node mass is derived from importance/query brightness; beams synthesize semantic bridges inside each realm.</p></div>;
}
