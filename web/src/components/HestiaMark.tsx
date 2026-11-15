/** Hestia logo mark: an ember flame inside a thin ring. */
export function HestiaMark({ size = 36, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 36 36" fill="none" aria-hidden className={className}>
      <circle cx="18" cy="18" r="17.25" className="stroke-line-strong" strokeWidth="1.5" />
      <path
        d="M18 8.5c.6 3-1.9 4.6-3.3 6.6-1.2 1.7-1.7 3.2-1.7 4.8a5 5 0 0 0 10 0c0-2.4-1.3-4.4-2.6-5.7.1 1.6-.5 2.8-1.6 3.4.5-3.2-.3-6.4-.8-9.1Z"
        className="fill-ember"
      />
      <path d="M18 23.6a1.9 1.9 0 0 1-1.9-1.9c0-1.3 1-2.2 1.9-3.3.9 1.1 1.9 2 1.9 3.3a1.9 1.9 0 0 1-1.9 1.9Z" className="fill-bg-canvas" />
    </svg>
  );
}
