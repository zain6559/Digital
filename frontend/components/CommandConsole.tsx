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
    try {
      await sendCommand(prompt.trim());
      setPrompt('');
    } catch (error) {
      push({ type: 'command.error', payload: { message: String(error) }, ts: new Date().toISOString() });
    } finally {
      setBusy(false);
    }
  }
  return <div className="glass rounded-2xl p-4"><div className="flex gap-2"><input className="flex-1 bg-black/40 border border-cyan-300/20 rounded px-3 py-2" value={prompt} onChange={(e) => setPrompt(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void submit(); }} /><button disabled={busy} className="px-4 py-2 rounded bg-cyan-400/20 text-cyan-200 disabled:opacity-40" onClick={() => void submit()}>{busy ? 'Running' : 'Execute'}</button></div><div className="mt-3 h-36 overflow-auto font-mono text-xs text-slate-300">{events.map((e, i) => <div key={`${e.ts}-${i}`}><span className="text-cyan-300">{e.type}</span> {JSON.stringify(e.payload).slice(0, 180)}</div>)}</div></div>;
}
