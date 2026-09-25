import { useEffect, useMemo, useRef, useState } from "react";

// Shared waveform math for the three mic visualizers (MiniBar, Home, Permissions).
//
// Before: every bar was derived from ONE `level` scalar with a fixed per-bar
// shape, so all bars moved in lockstep. Now we keep a short rolling history of
// the recent `level` samples and map bars across it, so the waveform SCROLLS
// with the voice (newest sample enters at the right, older ones drift left).
//
// Driven ONLY by the existing `status.level` prop, which updates via the gated
// 80ms poll in appContext.tsx. No setInterval / rAF — nothing runs while idle,
// so this adds zero per-frame cost (the freeze fix stays intact).

/** Rolling buffer of the last `size` level samples. Newest is the last element.
 *  One array allocated per level change (~12/s max, gated) — no allocation storm. */
export function useLevelHistory(level: number, size: number): number[] {
  const buf = useRef<number[]>(new Array(size).fill(0));
  const [history, setHistory] = useState<number[]>(buf.current);

  useEffect(() => {
    // Quiet: flatten the whole buffer to zero in one update. The effect is keyed
    // on [level], so a sustained 0 never re-fires — a single pushed zero would
    // leave the earlier speaking samples frozen mid-scroll. Zeroing all at once
    // settles the bars to minH immediately, with no lingering timer.
    const next = level <= 1e-3 ? new Array(size).fill(0) : [...buf.current.slice(1), level];
    buf.current = next;
    setHistory(next);
  }, [level, size]);

  return history;
}

/** OS "reduce motion" preference, live. Used to fall back to a static waveform. */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    if (typeof matchMedia !== "function") return;
    const mq = matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

const amplify = (s: number) => Math.min(1, s * 3.5); // same gain the visualizers used

/** Scrolling waveform: each bar reads its own sample from the rolling history,
 *  so louder speech => taller, livelier bars, and the shape travels over time.
 *  A soft bell keeps the ends tapered so it still reads as a centered waveform. */
function scrollingBars(history: number[], bars: number, minH: number, maxH: number): number[] {
  const start = history.length - bars;
  const out = new Array<number>(bars);
  for (let i = 0; i < bars; i++) {
    const bell = 0.35 + 0.65 * Math.sin(((i + 1) / (bars + 1)) * Math.PI);
    out[i] = Math.round(minH + (maxH - minH) * bell * amplify(history[start + i] ?? 0));
  }
  return out;
}

/** Reduced-motion fallback: the original symmetric static bell, scaled by the
 *  current level (calm/flat when silent). No scrolling. */
function staticBell(level: number, bars: number, minH: number, maxH: number): number[] {
  const amp = amplify(level);
  const speaking = level > 0.01;
  const out = new Array<number>(bars);
  for (let i = 0; i < bars; i++) {
    const bell = Math.sin(((i + 1) / (bars + 1)) * Math.PI);
    out[i] = Math.round(speaking ? minH + (maxH - minH) * bell * amp : minH);
  }
  return out;
}

/** One hook per visualizer: returns `bars` bar heights (px). Scrolls with the
 *  voice normally; falls back to the static bell under prefers-reduced-motion. */
export function useWaveform(level: number, bars: number, minH: number, maxH: number): number[] {
  const reduced = usePrefersReducedMotion();
  const history = useLevelHistory(level, bars);
  return useMemo(
    () => (reduced ? staticBell(level, bars, minH, maxH) : scrollingBars(history, bars, minH, maxH)),
    [reduced, history, level, bars, minH, maxH],
  );
}
