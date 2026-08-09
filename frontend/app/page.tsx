'use client';
import { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import CommandConsole from '../components/CommandConsole';
import CosmicBackground from '../components/CosmicBackground';
import FloatingNodeGraph from '../components/FloatingNodeGraph';
import GlassPanel from '../components/GlassPanel';
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

  return <main className="relative min-h-screen overflow-hidden px-4 py-4 text-slate-100 sm:px-6 lg:px-8">
    <CosmicBackground />
    <div className="relative z-10 mx-auto flex max-w-[1800px] flex-col gap-4">
      <header className="glass rounded-[2rem] px-4 py-3">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div><p className="hud-label">local-first cognitive operating layer</p><h1 className="text-3xl font-black tracking-tight text-cyan-50 text-bloom md:text-5xl">Noor OS Cognitive Cosmos</h1></div>
          <div className="flex flex-wrap gap-2">
            <OrbitalLabel label="state" value={status} tone={status === 'error' ? 'amber' : status === 'executing' ? 'cyan' : 'emerald'} />
            <OrbitalLabel label="backend" value={String(health?.status ?? 'probing')} tone={health?.status === 'ok' ? 'emerald' : 'amber'} />
            <OrbitalLabel label="websocket" value={wsState} tone={wsState === 'online' ? 'emerald' : wsState === 'warning' ? 'amber' : 'cyan'} />
            <OrbitalLabel label="api" value={API.replace(/^https?:\/\//, '')} tone="violet" />
          </div>
        </div>
      </header>

      <section className="grid gap-4 xl:grid-cols-[minmax(280px,.74fr)_minmax(520px,1.45fr)_minmax(300px,.78fr)]">
        <aside className="flex flex-col gap-4">
          <GlassPanel eyebrow="runtime flags" title="Safe Defaults">
            <div className="grid gap-2 text-xs">
              {[['browser_automation', 'Browser automation'], ['mobile_bridge', 'Mobile bridge'], ['cloud_fallback', 'Cloud fallback'], ['public_posting', 'Public posting']].map(([key, label]) => <div key={key} className="flex items-center justify-between rounded-2xl border border-cyan-200/10 bg-black/20 px-3 py-2"><span>{label}</span><span className="text-cyan-200">{flagValue(health, key)}</span></div>)}
            </div>
          </GlassPanel>
          <GlassPanel eyebrow="agent topology" title="AgentGraph">
            <AgentGraph />
          </GlassPanel>
        </aside>

        <section className="module-shell relative min-h-[720px] overflow-hidden rounded-[2.4rem] p-4">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_45%,rgba(0,229,255,.16),transparent_28%),radial-gradient(circle_at_50%_45%,rgba(168,85,247,.10),transparent_48%)]" />
          <div className="relative z-10 grid gap-4 lg:grid-rows-[1fr_auto]">
            <div className="relative min-h-[430px]"><NoorSphere status={status} /><div className="pointer-events-none absolute inset-8 rounded-full border border-cyan-200/10" /><div className="pointer-events-none absolute inset-20 rounded-full border border-violet-200/10" /></div>
            <FloatingNodeGraph memories={memories} events={events} />
          </div>
        </section>

        <aside className="flex flex-col gap-4">
          <MobileMirror />
          <GlassPanel eyebrow="live telemetry" title="Event Signals">
            <div className="space-y-2 text-xs">
              <div className="flex justify-between rounded-2xl bg-black/20 px-3 py-2"><span>Memories</span><strong className="text-violet-200">{memories.length}</strong></div>
              <div className="flex justify-between rounded-2xl bg-black/20 px-3 py-2"><span>Realms</span><strong className="text-cyan-200">{realms.length}</strong></div>
              <div className="flex justify-between rounded-2xl bg-black/20 px-3 py-2"><span>Events</span><strong className="text-emerald-200">{events.length}</strong></div>
              <div className="pt-2"><p className="hud-label mb-2">recent signal types</p><div className="flex flex-wrap gap-2">{recentTypes.length ? recentTypes.map((type) => <span key={type} className="orbital-chip rounded-full px-2 py-1 text-[10px] text-cyan-100">{type}</span>) : <span className="text-slate-400">Awaiting bus activity</span>}</div></div>
            </div>
          </GlassPanel>
        </aside>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.1fr_.9fr]">
        <GlassPanel eyebrow="memory galaxy" title="MemoryWorlds">
          <MemoryWorlds memories={memories} />
        </GlassPanel>
        <CommandConsole />
      </section>
    </div>
  </main>;
}
