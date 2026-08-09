import type { ReactNode } from 'react';

export default function GlassPanel({ title, eyebrow, children, className = '' }: { title?: string; eyebrow?: string; children: ReactNode; className?: string }) {
  return <section className={`module-shell rounded-[2rem] p-4 ${className}`}>
    {(title || eyebrow) && <div className="mb-3 flex items-center justify-between gap-3">
      <div>
        {eyebrow && <p className="hud-label">{eyebrow}</p>}
        {title && <h2 className="text-sm font-semibold text-cyan-100 text-bloom">{title}</h2>}
      </div>
      <span className="h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_16px_#00e5ff]" />
    </div>}
    {children}
  </section>;
}
