'use client';
import { useRef, useState } from 'react';
import { mobileDevices, sendVisionFrame } from '../lib/api';

export default function MobileMirror() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [out, setOut] = useState('No device telemetry loaded. ADB and browser/vision automation remain governed by backend config.');
  async function captureVision() {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.fillStyle = '#020617'; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = '#00E5FF'; ctx.lineWidth = 4; ctx.strokeRect(18, 18, canvas.width - 36, canvas.height - 36);
    ctx.fillStyle = '#EAF6FF'; ctx.font = '20px monospace'; ctx.fillText('Synthetic test frame', 32, 56); ctx.fillText('Vision fallback portal', 32, 92);
    setOut(JSON.stringify(await sendVisionFrame('mobile', canvas), null, 2));
  }
  return <div className="relative overflow-visible rounded-[2.4rem] p-2">
    <div className="absolute -inset-6 rounded-full bg-cyan-400/10 blur-3xl" />
    <div className="floating-hud relative rounded-[2rem] p-3">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="hud-label">telemetry portal</p><h2 className="text-cyan-100 text-bloom text-sm font-semibold">ADB + Vision</h2></div><div className="flex gap-2"><button className="rounded-full border border-cyan-300/15 bg-cyan-400/10 px-3 py-1 text-xs text-cyan-100 hover:bg-cyan-300/20" onClick={async () => setOut(JSON.stringify(await mobileDevices(), null, 2))}>Scan ADB</button><button className="rounded-full border border-violet-300/15 bg-violet-400/10 px-3 py-1 text-xs text-violet-100 hover:bg-violet-300/20" onClick={captureVision}>Vision Frame</button></div></div>
      <div className="relative mx-auto mt-3 max-w-[220px]"><canvas ref={canvasRef} width={360} height={640} className="relative aspect-[9/16] max-h-[330px] w-full rounded-[2rem] border border-cyan-300/20 bg-[radial-gradient(circle_at_top,#10203f,#020617_62%)] shadow-[0_0_55px_rgba(0,229,255,.14)]" /></div>
      <pre className="noor-scroll mt-3 max-h-24 overflow-auto whitespace-pre-wrap rounded-2xl bg-black/20 p-3 text-[10px] text-slate-300">{out}</pre>
    </div>
  </div>;
}
