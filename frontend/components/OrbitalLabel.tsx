import type { ReactNode } from 'react';

export default function OrbitalLabel({ label, value, tone = 'cyan', children }: { label: string; value?: string; tone?: 'cyan' | 'violet' | 'amber' | 'emerald'; children?: ReactNode }) {
  const tones = { cyan: 'text-cyan-200 border-cyan-300/30', violet: 'text-violet-200 border-violet-300/30', amber: 'text-amber-200 border-amber-300/30', emerald: 'text-emerald-200 border-emerald-300/30' };
  return <div className={`orbital-chip rounded-full px-3 py-2 ${tones[tone]}`}>
    <span className="hud-label block leading-none">{label}</span>
    {value && <strong className="mt-1 block text-xs font-semibold">{value}</strong>}
    {children}
  </div>;
}
