"use client";

import { useEffect, useState } from "react";

/**
 * Counts from 0 to `value` once on mount. Renders the final value on the server and when the
 * user prefers reduced motion, so the number is always correct without JavaScript.
 */
export function CountUp({ value, pad = 0, duration = 1400 }: { value: number; pad?: number; duration?: number }) {
  const [n, setN] = useState(value);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      setN(Math.round(value * (1 - Math.pow(1 - p, 3)))); // ease-out cubic
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);

  return <>{String(n).padStart(pad, "0")}</>;
}
