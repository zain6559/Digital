'use client';
import { useMemo } from 'react';

export default function CosmicBackground() {
  const stars = useMemo(() => Array.from({ length: 92 }, (_, i) => ({ id: i, left: `${(i * 37) % 101}%`, top: `${(i * 61) % 97}%`, size: 1 + (i % 4), delay: `${(i % 13) * .31}s`, opacity: .22 + (i % 7) * .08 })), []);
  return <div className="pointer-events-none fixed inset-0 overflow-hidden bg-[#02040b] cosmic-noise">
    <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_36%,rgba(0,229,255,.20),transparent_22%),radial-gradient(circle_at_78%_12%,rgba(168,85,247,.22),transparent_28%),radial-gradient(circle_at_18%_82%,rgba(245,158,11,.10),transparent_24%),linear-gradient(180deg,#040814,#02040b_58%,#010208)]" />
    <div className="absolute left-1/2 top-1/2 h-[72rem] w-[72rem] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-300/10 shadow-[0_0_160px_rgba(0,229,255,.18)]" />
    <div className="absolute -left-32 top-20 h-96 w-96 rounded-full bg-cyan-500/10 blur-3xl animate-drift" />
    <div className="absolute right-0 bottom-0 h-[34rem] w-[34rem] rounded-full bg-violet-500/10 blur-3xl animate-drift [animation-delay:-8s]" />
    <svg className="absolute inset-0 h-full w-full opacity-35" aria-hidden="true"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#00e5ff" stopOpacity=".4"/><stop offset="1" stopColor="#a855f7" stopOpacity=".05"/></linearGradient></defs>{Array.from({ length: 18 }, (_, i) => <line key={i} x1={`${(i * 17) % 100}%`} y1={`${(i * 29) % 100}%`} x2={`${(i * 43 + 22) % 100}%`} y2={`${(i * 11 + 44) % 100}%`} stroke="url(#g)" strokeWidth=".6" />)}</svg>
    {stars.map((s) => <span key={s.id} className="absolute rounded-full bg-cyan-100 shadow-[0_0_12px_rgba(0,229,255,.9)]" style={{ left: s.left, top: s.top, width: s.size, height: s.size, opacity: s.opacity, animation: `pulse-ring ${3 + (s.id % 5)}s ease-out infinite`, animationDelay: s.delay }} />)}
  </div>;
}
