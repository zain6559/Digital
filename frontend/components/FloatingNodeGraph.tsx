'use client';
import { useMemo, useState } from 'react';
import { MemoryNode, NoorEvent } from '../lib/types';

const moduleNodes = [
  { id: 'core', label: 'Noor Core', x: 50, y: 48, tone: '#00e5ff' },
  { id: 'agents', label: 'Agents', x: 27, y: 30, tone: '#60a5fa' },
  { id: 'memory', label: 'Memory', x: 70, y: 29, tone: '#a855f7' },
  { id: 'vision', label: 'Vision', x: 76, y: 68, tone: '#f59e0b' },
  { id: 'mobile', label: 'ADB', x: 31, y: 70, tone: '#22d3ee' },
  { id: 'console', label: 'Command Rail', x: 50, y: 82, tone: '#34d399' },
];
const links = [['core', 'agents'], ['core', 'memory'], ['core', 'vision'], ['core', 'mobile'], ['core', 'console'], ['agents', 'memory'], ['vision', 'console']];

export default function FloatingNodeGraph({ memories, events }: { memories: MemoryNode[]; events: NoorEvent[] }) {
  const [active, setActive] = useState<string | null>(null);
  const memoryNodes = useMemo(() => memories.slice(0, 18).map((m, i) => ({ id: m.id, label: m.title || m.realm, x: 18 + ((i * 17) % 65), y: 18 + ((i * 23) % 58), tone: '#c084fc', memory: true })), [memories]);
  const nodes: Array<{ id: string; label: string; x: number; y: number; tone: string; memory?: boolean }> = [...moduleNodes, ...memoryNodes];
  const isLinked = (id: string) => !active || id === active || links.some(([a, b]) => (a === active && b === id) || (b === active && a === id));
  return <div className="relative h-[430px] overflow-hidden rounded-[2rem] border border-cyan-200/10 bg-black/10">
    <svg className="absolute inset-0 h-full w-full" aria-hidden="true">
      <defs><linearGradient id="edgeGlow" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#00e5ff"/><stop offset="1" stopColor="#a855f7"/></linearGradient></defs>
      {links.map(([a, b]) => { const na = moduleNodes.find((n) => n.id === a)!; const nb = moduleNodes.find((n) => n.id === b)!; const on = !active || active === a || active === b; return <line key={`${a}-${b}`} x1={`${na.x}%`} y1={`${na.y}%`} x2={`${nb.x}%`} y2={`${nb.y}%`} stroke="url(#edgeGlow)" strokeWidth={on ? 1.5 : .55} opacity={on ? .72 : .12} />; })}
      {memoryNodes.map((m, i) => <line key={`memory-${m.id}`} x1="70%" y1="29%" x2={`${m.x}%`} y2={`${m.y}%`} stroke="#a855f7" strokeWidth=".6" opacity={active && active !== 'memory' && active !== m.id ? .08 : .24 + (i % 4) * .05} />)}
    </svg>
    <div className="absolute left-1/2 top-1/2 h-44 w-44 -translate-x-1/2 -translate-y-1/2 rounded-full bg-cyan-400/10 blur-2xl" />
    {nodes.map((n) => <button key={n.id} onMouseEnter={() => setActive(n.id)} onMouseLeave={() => setActive(null)} onClick={() => setActive(active === n.id ? null : n.id)} className={`group absolute -translate-x-1/2 -translate-y-1/2 text-left transition duration-300 ${isLinked(n.id) ? 'opacity-100 scale-100' : 'opacity-35 scale-95'}`} style={{ left: `${n.x}%`, top: `${n.y}%` }}>
      <span className="block h-4 w-4 rounded-full border border-white/60 shadow-[0_0_20px_currentColor]" style={{ color: n.tone, backgroundColor: n.tone }} />
      <span className="orbital-chip mt-2 block max-w-36 rounded-2xl px-3 py-2 text-[11px] text-cyan-50">
        <span className="hud-label">{n.memory ? 'memory node' : 'module'}</span>
        <strong className="block truncate">{n.label}</strong>
      </span>
    </button>)}
    <div className="absolute left-4 top-4 orbital-chip rounded-2xl px-3 py-2 text-xs text-cyan-100"><span className="hud-label block">live topology</span>{events.length} events / {memories.length} memories</div>
  </div>;
}
