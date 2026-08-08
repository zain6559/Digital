'use client';
import { useRef, useState } from 'react';
import { mobileDevices, sendVisionFrame } from '../lib/api';

export default function MobileMirror() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [out, setOut] = useState('No device telemetry loaded.');
  async function captureVision() {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.fillStyle = '#020617';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = '#00E5FF';
    ctx.strokeRect(18, 18, canvas.width - 36, canvas.height - 36);
    ctx.fillStyle = '#EAF6FF';
    ctx.font = '20px monospace';
    ctx.fillText('Noor mobile visual context frame', 28, 52);
    setOut(JSON.stringify(await sendVisionFrame('mobile', canvas), null, 2));
  }
  return <div className="glass rounded-2xl p-4 h-full"><div className="flex flex-wrap gap-2 justify-between"><h2 className="text-cyan-300 font-semibold">Wireless Mobile Mirror</h2><div className="flex gap-2"><button className="px-3 py-1 rounded bg-cyan-400/20" onClick={async () => setOut(JSON.stringify(await mobileDevices(), null, 2))}>Scan ADB</button><button className="px-3 py-1 rounded bg-violet-400/20" onClick={captureVision}>Vision Frame</button></div></div><canvas ref={canvasRef} width={360} height={640} className="mt-4 aspect-[9/16] max-h-[420px] mx-auto rounded-3xl border border-cyan-300/30 bg-black block" /><pre className="mt-3 text-xs whitespace-pre-wrap text-slate-300 max-h-40 overflow-auto">{out}</pre></div>;
}
