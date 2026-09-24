// Onboarding 01 — brand splash.
// Smoothly animates loading bar from 0% to 100% matching the app loading time.
import { useEffect, useState } from "react";
import { bridgeReady } from "../../lib/api";
import { SoftBlobBackground } from "../primitives/SoftBlobBackground";
import { SayItMark } from "../primitives/SayItMark";
import { SayItWordmark } from "../primitives/SayItWordmark";

export interface SplashProps {
  onComplete?: () => void;
  duration?: number;
}

export function Splash({ onComplete, duration = 1400 }: SplashProps) {
  const [progress, setProgress] = useState(0);
  const [ready, setReady] = useState(false);

  // Real backend readiness: resolves once the Python bridge is live (or the
  // mock, in browser preview), but never before `duration` — the minimum floor.
  useEffect(() => {
    let alive = true;
    const floor = new Promise<void>((r) => setTimeout(r, duration));
    Promise.all([bridgeReady(), floor]).then(() => { if (alive) setReady(true); });
    return () => { alive = false; };
  }, [duration]);

  useEffect(() => {
    let completed = false;
    const interval = setInterval(() => {
      setProgress((prev) => {
        // Hold just shy of full until the backend is actually ready.
        const ceiling = ready ? 100 : 90;
        if (prev >= ceiling) {
          if (ceiling === 100) {
            clearInterval(interval);
            if (!completed) {
              completed = true;
              setTimeout(() => {
                onComplete?.();
              }, 120);
            }
          }
          return ceiling;
        }
        // Smoothly advance progress
        const next = prev + (prev < 70 ? 6 : prev < 90 ? 4 : 2);
        return Math.min(ceiling, next);
      });
    }, 40);

    return () => clearInterval(interval);
  }, [onComplete, ready]);

  return (
    <div className="relative flex h-full w-full flex-col items-center justify-center overflow-hidden bg-canvas-soft select-none">
      <SoftBlobBackground variant="full" />

      <div className="flex flex-col items-center gap-6 duration-700 animate-in fade-in-0 zoom-in-95">
        <div className="relative flex items-center justify-center">
          {/* soft accent glow behind the mark — the "shimmer" cue */}
          <div
            aria-hidden
            className="absolute h-44 w-44 rounded-full bg-accent-soft opacity-70 blur-2xl animate-pulse"
          />
          <SayItMark size={96} className="relative drop-shadow-md" />
        </div>

        <SayItWordmark size="lg" />

        <div className="mt-1 flex flex-col items-center gap-2.5 w-48" role="status" aria-live="polite">
          <div className="h-2 w-full overflow-hidden rounded-pill bg-accent-soft/80 shadow-inner">
            <div
              className="h-full rounded-pill bg-gradient-to-r from-accent to-accent-deep transition-[width] duration-75 ease-out shadow-xs"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex items-center justify-between w-full px-0.5 text-caption font-medium text-ink-tertiary">
            <span>{progress >= 100 ? "Ready!" : "Starting up…"}</span>
            <span className="font-semibold text-accent">{progress}%</span>
          </div>
          <span className="sr-only">Loading Say It: {progress}%</span>
        </div>
      </div>
    </div>
  );
}
