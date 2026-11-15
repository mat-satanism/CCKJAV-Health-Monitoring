import { useEffect, useState } from 'react'

const reduced = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/** A number that counts up to `target` in `ms` (ease-out). Jumps straight there under reduced motion. */
export function useCountUp(target: number, ms = 700): number {
  const [v, setV] = useState(reduced() ? target : 0)
  useEffect(() => {
    if (reduced()) { setV(target); return }
    let raf = 0
    const t0 = performance.now()
    const from = 0
    const step = (t: number) => {
      const k = Math.min(1, (t - t0) / ms)
      setV(from + (target - from) * (1 - (1 - k) ** 3))
      if (k < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])
  return v
}
