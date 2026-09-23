// Onboarding 01 — brand splash. Purely visual; appContext auto-advances after
// SPLASH_MS (1200ms). No buttons, no actions. Full-window (no frame/sidebar).
import { SoftBlobBackground } from "../primitives/SoftBlobBackground";
import { SayItMark } from "../primitives/SayItMark";
import { SayItWordmark } from "../primitives/SayItWordmark";

export function Splash() {
  return (
    <div className="relative flex h-full w-full flex-col items-center justify-center overflow-hidden bg-canvas-soft">
      <SoftBlobBackground variant="full" />

      <div className="flex flex-col items-center gap-6 duration-700 animate-in fade-in-0 zoom-in-95">
        <div className="relative flex items-center justify-center">
          {/* soft accent glow behind the mark — the "shimmer" cue */}
          <div
            aria-hidden
            className="absolute h-44 w-44 rounded-full bg-accent-soft opacity-70 blur-2xl animate-pulse"
          />
          <SayItMark size={96} className="relative" />
        </div>

        <SayItWordmark size="lg" />

        <div className="mt-1 flex flex-col items-center gap-3" role="status" aria-live="polite">
          <div className="h-1.5 w-40 overflow-hidden rounded-pill bg-accent-soft">
            <div className="h-full w-2/5 rounded-pill bg-accent animate-pulse" />
          </div>
          <span className="text-caption text-ink-tertiary">Starting up…</span>
          <span className="sr-only">Loading Say It</span>
        </div>
      </div>
    </div>
  );
}
