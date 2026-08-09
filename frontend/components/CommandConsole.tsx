'use client';
import { useState } from 'react';
import { sendCommand } from '../lib/api';
import { useNoorStore } from '../lib/store';

export default function CommandConsole() {
  const [prompt, setPrompt] = useState('remember Noor OS booted into the Research Nebula');
  const [busy, setBusy] = useState(false);
  const events = useNoorStore((s) => s.events);
  const push = useNoorStore((s) => s.push);
  async function submit() {
    if (!prompt.trim() || busy) return;
    setBusy(true);
    try { await sendCommand(prompt.trim()); setPrompt(''); }
    catch (error) { push({ type: 'command.error', payload: { message: String(error) }, ts: new Date().toISOString() }); }
    finally { setBusy(false); }
  }
  return <div className="module-shell rounded-[2rem] p-4">
    <div className="mb-3 flex items-center justify-between"><div><p className="hud-label">operator rail</p><h2 className="text-cyan-100 text-bloom font-semibold">Command Console</h2></div><span className="text-xs text-cyan-200/70">{events.length} buffered events</span></div>
    <div className="flex flex-col gap-2 sm:flex-row"><input aria-label="Noor command prompt" className="flex-1 rounded-2xl border border-cyan-300/20 bg-black/35 px-4 py-3 text-sm text-cyan-50 outline-none shadow-[inset_0_0_24px_rgba(0,229,255,.05)] placeholder:text-slate-500 focus:border-cyan-300/60" value={prompt} onChange={(e) => setPrompt(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void submit(); }} /><button disabled={busy} className="rounded-2xl border border-cyan-200/30 bg-cyan-300/15 px-5 py-3 text-sm font-semibold text-cyan-100 shadow-[0_0_26px_rgba(0,229,255,.14)] transition hover:bg-cyan-300/25 disabled:opacity-40" onClick={() => void submit()}>{busy ? 'Executing…' : 'Execute'}</button></div>
    <div className="noor-scroll mt-4 h-44 overflow-auto rounded-2xl border border-cyan-200/10 bg-black/25 p-3 font-mono text-[11px] text-slate-300">
      {events.length === 0 && <p className="text-cyan-200/60">Awaiting live events from the Noor event bus…</p>}
      {events.map((e, i) => <div key={`${e.ts}-${i}`} className="mb-2 border-l border-cyan-300/20 pl-3"><span className="text-cyan-300">{e.type}</span> <span className="text-slate-500">{e.ts}</span><br/><span>{JSON.stringify(e.payload).slice(0, 220)}</span></div>)}
    </div>
  </div>;
}
