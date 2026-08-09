'use client';
import { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import CommandConsole from '../components/CommandConsole';
import CosmicBackground from '../components/CosmicBackground';
import FloatingNodeGraph from '../components/FloatingNodeGraph';
import MobileMirror from '../components/MobileMirror';
import OrbitalLabel from '../components/OrbitalLabel';
const AgentGraph = dynamic(() => import('../components/AgentGraph'), { ssr: false });
const MemoryWorlds = dynamic(() => import('../components/MemoryWorlds'), { ssr: false });
const NoorSphere = dynamic(() => import('../components/NoorSphere'), { ssr: false });
import { API, loadHealth, loadRealms } from '../lib/api';
import { useNoorStore } from '../lib/store';
import { MemoryNode, NoorEvent } from '../lib/types';

function flagValue(health: Record<string, unknown> | null, key: string) {
  const flags = health?.safe_defaults as Record<string, unknown> | undefined;
  const value = flags?.[key];
  return typeof value === 'boolean' ? (value ? 'enabled' : 'disabled') : 'unknown';
}
const safeFlags = [['browser_automation', 'Browser'], ['mobile_bridge', 'Mobile'], ['cloud_fallback', 'Cloud'], ['public_posting', 'Posting']];

export default function Home() {
  const push = useNoorStore((s) => s.push);
  const status = useNoorStore((s) => s.status);
  const memories = useNoorStore((s) => s.memories);
  const events = useNoorStore((s) => s.events);
  const setMemories = useNoorStore((s) => s.setMemories);
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [wsState, setWsState] = useState('connecting');
  const realms = useMemo(() => [...new Set(memories.map((m) => m.realm))], [memories]);
  const recentTypes = useMemo(() => [...new Set(events.slice(0, 8).map((e) => e.type))], [events]);

  useEffect(() => {
    let cancelled = false;
    const refresh = () => loadHealth().then((data) => { if (!cancelled) setHealth(data); }).catch((error) => push({ type: 'health.error', payload: { message: String(error) }, ts: new Date().toISOString() }));
    refresh();
    const interval = window.setInterval(refresh, 15000);
    return () => { cancelled = true; window.clearInterval(interval); };
  }, [push]);

  useEffect(() => {
    let ws: WebSocket | undefined;
    let closed = false;
    let retry = 0;
    loadRealms().then((loadedRealms) => setMemories(Object.values(loadedRealms).flat() as MemoryNode[])).catch((error) => push({ type: 'ui.error', payload: { message: String(error) }, ts: new Date().toISOString() }));
    function connect() {
      setWsState('connecting');
      ws = new WebSocket(`${API.replace(/^http/, 'ws')}/ws`);
      ws.onopen = () => { retry = 0; setWsState('online'); push({ type: 'ws.connected', payload: {}, ts: new Date().toISOString() }); };
      ws.onmessage = (event) => { try { push(JSON.parse(event.data) as NoorEvent); } catch { push({ type: 'ws.bad_message', payload: { raw: event.data }, ts: new Date().toISOString() }); } };
      ws.onerror = () => { setWsState('warning'); push({ type: 'ws.error', payload: {}, ts: new Date().toISOString() }); };
      ws.onclose = () => { setWsState('offline'); if (!closed) window.setTimeout(connect, Math.min(10000, 500 * 2 ** retry++)); };
    }
    connect();
    return () => { closed = true; ws?.close(); };
  }, [push, setMemories]);

  return <main className="relative min-h-screen overflow-hidden px-3 py-3 text-slate-100 sm:px-5">
    <CosmicBackground />
    <section className="cosmos-stage relative z-10 mx-auto max-w-[1900px]">
      <div className="cosmos-orbit left-1/2 top-1/2 hidden h-[84vh] w-[84vh] -translate-x-1/2 -translate-y-1/2 lg:block" />
      <div className="cosmos-orbit left-1/2 top-1/2 hidden h-[62vh] w-[62vh] -translate-x-1/2 -translate-y-1/2 rotate-12 lg:block" />
      <div className="cosmos-orbit left-1/2 top-1/2 hidden h-[44vh] w-[44vh] -translate-x-1/2 -translate-y-1/2 -rotate-12 lg:block" />

      <header className="cosmos-layer top-hud floating-hud rounded-[2rem] px-4 py-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div><p className="hud-label">live cognitive field</p><h1 className="text-3xl font-black tracking-tight text-cyan-50 text-bloom md:text-5xl">Noor OS</h1></div>
          <div className="flex flex-wrap gap-2">
            <OrbitalLabel label="state" value={status} tone={status === 'error' ? 'amber' : status === 'executing' ? 'cyan' : 'emerald'} />
            <OrbitalLabel label="backend" value={String(health?.status ?? 'probing')} tone={health?.status === 'ok' ? 'emerald' : 'amber'} />
            <OrbitalLabel label="websocket" value={wsState} tone={wsState === 'online' ? 'emerald' : wsState === 'warning' ? 'amber' : 'cyan'} />
            <OrbitalLabel label="api" value={API.replace(/^https?:\/\//, '')} tone="violet" />
          </div>
        </div>
      </header>

      <section className="cosmos-layer core-zone portal-glow scanline overflow-hidden rounded-full">
        <div className="absolute inset-0 rounded-full bg-[radial-gradient(circle_at_center,rgba(0,229,255,.22),transparent_30%),radial-gradient(circle_at_50%_50%,rgba(168,85,247,.12),transparent_54%)]" />
        <NoorSphere status={status} />
      </section>

      <section className="cosmos-layer inset-x-[8vw] top-[17vh] z-20 hidden h-[58vh] lg:block">
        <FloatingNodeGraph memories={memories} events={events} />
      </section>

      <aside className="cosmos-layer flags-hud floating-hud rounded-[1.6rem] p-3 animate-drift">
        <p className="hud-label mb-2">runtime flags</p>
        <div className="flex flex-wrap gap-2 text-[11px]">{safeFlags.map(([key, label]) => <span key={key} className="orbital-chip rounded-full px-3 py-2"><span className="text-slate-300">{label}</span> <strong className="text-cyan-100">{flagValue(health, key)}</strong></span>)}</div>
      </aside>

      <aside className="cosmos-layer agent-hud constellation-panel rounded-[2rem] p-2 opacity-80 transition hover:opacity-100">
        <div className="mb-2 ml-3"><p className="hud-label">faint agent topology</p><h2 className="text-sm font-semibold text-cyan-100 text-bloom">AgentGraph</h2></div>
        <AgentGraph />
      </aside>

      <aside className="cosmos-layer memory-hud constellation-panel rounded-[2rem] p-2 opacity-90 transition hover:opacity-100">
        <div className="mb-2 ml-3 flex items-end justify-between gap-2"><div><p className="hud-label">memory nebula</p><h2 className="text-sm font-semibold text-violet-100 text-bloom">MemoryWorlds</h2></div><span className="orbital-chip rounded-full px-3 py-1 text-[11px] text-violet-100">{realms.length} realms</span></div>
        <MemoryWorlds memories={memories} />
      </aside>

      <aside className="cosmos-layer mobile-hud portal-glow">
        <MobileMirror />
      </aside>

      <aside className="cosmos-layer telemetry-hud floating-hud rounded-[1.7rem] p-3">
        <p className="hud-label mb-2">live signal stream</p>
        <div className="grid grid-cols-3 gap-2 text-center text-xs"><span className="orbital-chip rounded-2xl px-2 py-2"><strong className="block text-violet-200">{memories.length}</strong>mem</span><span className="orbital-chip rounded-2xl px-2 py-2"><strong className="block text-cyan-200">{realms.length}</strong>realms</span><span className="orbital-chip rounded-2xl px-2 py-2"><strong className="block text-emerald-200">{events.length}</strong>events</span></div>
        <div className="mt-3 flex flex-wrap gap-2">{recentTypes.length ? recentTypes.map((type) => <span key={type} className="rounded-full bg-cyan-300/10 px-2 py-1 text-[10px] text-cyan-100">{type}</span>) : <span className="text-xs text-slate-400">Awaiting bus activity</span>}</div>
      </aside>

      <section className="cosmos-layer command-hud portal-glow">
        <CommandConsole />
      </section>
    </section>
  </main>;
}
