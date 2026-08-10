'use client';
import { useMemo, useState } from 'react';
import { MemoryNode, NoorEvent } from '../lib/types';

const moduleNodes = [
  { id: 'agents', label: 'Agents', x: 25, y: 31, tone: '#60a5fa' },
  { id: 'memory', label: 'Memory', x: 73, y: 27, tone: '#a855f7' },
  { id: 'vision', label: 'Vision', x: 80, y: 67, tone: '#f59e0b' },
  { id: 'mobile', label: 'ADB', x: 24, y: 68, tone: '#22d3ee' },
  { id: 'console', label: 'Command', x: 50, y: 84, tone: '#34d399' },
];
const links = [['agents', 'memory'], ['memory', 'vision'], ['vision', 'console'], ['mobile', 'console'], ['agents', 'mobile'], ['memory', 'console']];

export default function FloatingNodeGraph({ memories, events }: { memories: MemoryNode[]; events: NoorEvent[] }) {
  const [active, setActive] = useState<string | null>(null);
  const memoryNodes = useMemo(() => memories.slice(0, 22).map((m, i) => ({ id: m.id, label: m.title || m.realm, x: 16 + ((i * 19) % 70), y: 15 + ((i * 29) % 66), tone: '#c084fc', memory: true })), [memories]);
  const nodes: Array<{ id: string; label: string; x: number; y: number; tone: string; memory?: boolean }> = [...moduleNodes, ...memoryNodes];
  const isLinked = (id: string) => !active || id === active || links.some(([a, b]) => (a === active && b === id) || (b === active && a === id)) || (active === 'memory' && memoryNodes.some((m) => m.id === id));
  return <div className="pointer-events-none relative h-full w-full overflow-visible">
    <svg className="absolute inset-0 h-full w-full overflow-visible" aria-hidden="true">
      <defs><radialGradient id="nodePulse"><stop offset="0" stopColor="#00e5ff" stopOpacity=".95"/><stop offset="1" stopColor="#00e5ff" stopOpacity="0"/></radialGradient><linearGradient id="edgeGlow" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#00e5ff"/><stop offset="1" stopColor="#a855f7"/></linearGradient></defs>
      {moduleNodes.map((n) => <line key={`core-${n.id}`} x1="50%" y1="50%" x2={`${n.x}%`} y2={`${n.y}%`} stroke="url(#edgeGlow)" strokeWidth=".7" opacity={active && active !== n.id ? .1 : .46} />)}
      {links.map(([a, b]) => { const na = moduleNodes.find((n) => n.id === a)!; const nb = moduleNodes.find((n) => n.id === b)!; const on = !active || active === a || active === b; return <line key={`${a}-${b}`} x1={`${na.x}%`} y1={`${na.y}%`} x2={`${nb.x}%`} y2={`${nb.y}%`} stroke="url(#edgeGlow)" strokeWidth={on ? 1.1 : .4} opacity={on ? .5 : .08} />; })}
      {memoryNodes.map((m, i) => <line key={`memory-${m.id}`} x1="73%" y1="27%" x2={`${m.x}%`} y2={`${m.y}%`} stroke="#a855f7" strokeWidth=".45" opacity={active && active !== 'memory' && active !== m.id ? .05 : .18 + (i % 4) * .04} />)}
      <circle cx="50%" cy="50%" r="28" fill="url(#nodePulse)" opacity=".22" />
    </svg>
    {nodes.map((n) => <button key={n.id} onMouseEnter={() => setActive(n.id)} onMouseLeave={() => setActive(null)} onClick={() => setActive(active === n.id ? null : n.id)} className={`pointer-events-auto absolute -translate-x-1/2 -translate-y-1/2 text-left transition duration-500 ${isLinked(n.id) ? 'opacity-100 scale-100' : 'opacity-25 scale-90'}`} style={{ left: `${n.x}%`, top: `${n.y}%` }}>
      <span className="block h-3 w-3 rounded-full border border-white/70 shadow-[0_0_20px_currentColor,0_0_42px_currentColor]" style={{ color: n.tone, backgroundColor: n.tone }} />
      <span className="orbital-chip mt-2 block max-w-36 rounded-full px-3 py-1.5 text-[10px] text-cyan-50">
        <span className="hud-label mr-1">{n.memory ? 'memory' : 'node'}</span><strong className="truncate align-middle">{n.label}</strong>
      </span>
    </button>)}
    <div className="pointer-events-auto absolute left-[48%] top-[47%] -translate-x-1/2 -translate-y-1/2 rounded-full px-3 py-2 text-center text-[10px] text-cyan-100"><span className="hud-label block">topology</span>{events.length} signals</div>
  </div>;
}
