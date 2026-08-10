'use client';
import '@xyflow/react/dist/style.css';
import { Background, Controls, ReactFlow, Edge, Node } from '@xyflow/react';

const nodeClass = 'orbital-chip rounded-full px-4 py-2 border-cyan-300/20 text-cyan-50 shadow-[0_0_28px_rgba(0,229,255,.12)]';
const nodes: Node[] = [
  { id: 'coordinator', position: { x: 0, y: 105 }, data: { label: 'Coordinator' }, className: `${nodeClass} !border-cyan-300/40` },
  { id: 'memory', position: { x: 265, y: 10 }, data: { label: 'Spatial Memory' }, className: nodeClass },
  { id: 'mobile', position: { x: 265, y: 190 }, data: { label: 'ADB Bridge' }, className: nodeClass },
  { id: 'browser', position: { x: 560, y: 105 }, data: { label: 'Browser Search' }, className: nodeClass },
];
const edges: Edge[] = [
  { id: 'e1', source: 'coordinator', target: 'memory', animated: true, label: 'reads / writes', style: { stroke: '#00E5FF', opacity: .55 } },
  { id: 'e2', source: 'coordinator', target: 'mobile', animated: true, label: 'validated ADB', style: { stroke: '#22D3EE', opacity: .45 } },
  { id: 'e3', source: 'coordinator', target: 'browser', animated: true, label: 'safe search', style: { stroke: '#A855F7', opacity: .45 } },
];
export default function AgentGraph() { return <div className="h-[260px] overflow-hidden rounded-[2rem] bg-transparent"><ReactFlow nodes={nodes} edges={edges} fitView proOptions={{ hideAttribution: true }} panOnScroll={false} zoomOnScroll={false}><Background color="#00E5FF" gap={32} size={.7} /><Controls /></ReactFlow></div>; }
