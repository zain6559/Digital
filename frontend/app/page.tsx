'use client';
import { useEffect } from 'react';
import AgentGraph from '../components/AgentGraph';
import CommandConsole from '../components/CommandConsole';
import MemoryWorlds from '../components/MemoryWorlds';
import MobileMirror from '../components/MobileMirror';
import NoorSphere from '../components/NoorSphere';
import { API, loadRealms } from '../lib/api';
import { useNoorStore } from '../lib/store';
import { MemoryNode, NoorEvent } from '../lib/types';

export default function Home() {
  const push = useNoorStore((s) => s.push);
  const status = useNoorStore((s) => s.status);
  const memories = useNoorStore((s) => s.memories);
  const setMemories = useNoorStore((s) => s.setMemories);
  useEffect(() => {
    let ws: WebSocket | undefined;
    let closed = false;
    let retry = 0;
    loadRealms().then((realms) => setMemories(Object.values(realms).flat() as MemoryNode[])).catch((error) => push({ type: 'ui.error', payload: { message: String(error) }, ts: new Date().toISOString() }));
    function connect() {
      ws = new WebSocket(`${API.replace(/^http/, 'ws')}/ws`);
      ws.onopen = () => { retry = 0; push({ type: 'ws.connected', payload: {}, ts: new Date().toISOString() }); };
      ws.onmessage = (event) => { try { push(JSON.parse(event.data) as NoorEvent); } catch { push({ type: 'ws.bad_message', payload: { raw: event.data }, ts: new Date().toISOString() }); } };
      ws.onerror = () => push({ type: 'ws.error', payload: {}, ts: new Date().toISOString() });
      ws.onclose = () => { if (!closed) window.setTimeout(connect, Math.min(10000, 500 * 2 ** retry++)); };
    }
    connect();
    return () => { closed = true; ws?.close(); };
  }, [push, setMemories]);
  return <main className="min-h-screen bg-[radial-gradient(circle_at_top,#10203f,#05070D_55%)] p-4"><header className="glass rounded-2xl p-4 flex justify-between"><h1 className="text-2xl font-bold text-cyan-300">Noor OS</h1><span className="text-sm text-slate-300">State: {status}</span></header><section className="grid grid-cols-1 xl:grid-cols-[1.1fr_1fr_.9fr] gap-4 mt-4"><div className="glass rounded-2xl"><NoorSphere status={status} /></div><div className="glass rounded-2xl p-2"><AgentGraph /></div><MobileMirror /></section><section className="grid grid-cols-1 xl:grid-cols-[1fr_1fr] gap-4 mt-4"><div className="glass rounded-2xl p-2"><h2 className="p-2 text-violet-300 font-semibold">Hyper-Dimensional Memory Worlds</h2><MemoryWorlds memories={memories} /></div><CommandConsole /></section></main>;
}
