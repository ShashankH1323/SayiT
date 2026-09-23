import { Mic, X, Loader2, Check } from "lucide-react";
import { cn } from "../../lib/utils";

export type MiniBarState = "idle" | "listening" | "processing" | "pasted";

export interface MiniBarProps {
  state: MiniBarState;
  level?: number; // 0..1 audio level, drives listening bars
  text?: string;
  hotkey?: string;
  onToggle?: () => void;
  onCancel?: () => void;
  className?: string;
}

// Symmetric-ish weights so the waveform reads as a live meter, not a flat row.
const BAR_WEIGHTS = [0.45, 0.7, 1, 0.85, 0.55, 0.9, 0.6];

function AudioBars({ level = 0 }: { level?: number }) {
  const l = Math.min(1, Math.max(0, level));
  return (
    <div className="flex h-6 items-center gap-[3px]" aria-hidden="true">
      {BAR_WEIGHTS.map((w, i) => (
        <span
          key={i}
          className="w-[3px] rounded-pill bg-teal transition-[height] duration-100 ease-out"
          style={{ height: `${Math.max(3, l * w * 22)}px` }}
        />
      ))}
    </div>
  );
}

function DottedIndicator() {
  return (
    <span className="flex items-center gap-1" aria-hidden="true">
      {Array.from({ length: 10 }).map((_, i) => (
        <span key={i} className="h-1 w-1 rounded-pill bg-ink/15" />
      ))}
    </span>
  );
}

/** Floating recording HUD. One component, four states; outer pill geometry/position
 *  stay stable — only the interior morphs. idle → listening → processing → pasted → idle. */
export function MiniBar({
  state,
  level = 0,
  text,
  hotkey,
  onToggle,
  onCancel,
  className,
}: MiniBarProps) {
  const active = state === "idle" || state === "listening";
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "glass-strong no-drag inline-flex h-14 min-w-[240px] max-w-[320px] items-center gap-3 rounded-pill px-3 shadow-soft-lg",
        className,
      )}
    >
      {/* leading — stable 40px slot: mic (idle/listening) / spinner / check */}
      {active ? (
        <button
          type="button"
          onClick={onToggle}
          aria-label={state === "listening" ? "Stop recording" : "Start recording"}
          className={cn(
            "no-drag relative grid h-10 w-10 shrink-0 place-items-center rounded-pill transition-colors",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 focus-visible:ring-offset-canvas",
            state === "listening"
              ? "bg-teal-soft text-teal-deep"
              : "bg-accent-soft text-accent hover:bg-accent/15",
          )}
        >
          {state === "listening" && (
            <span
              className="absolute inset-0 rounded-pill bg-teal/30 animate-ping"
              aria-hidden="true"
            />
          )}
          <Mic className="relative h-[18px] w-[18px]" strokeWidth={1.75} aria-hidden="true" />
        </button>
      ) : state === "processing" ? (
        <span
          className="grid h-10 w-10 shrink-0 place-items-center rounded-pill bg-accent-soft text-accent animate-in fade-in-0 duration-200"
          aria-hidden="true"
        >
          <Loader2 className="h-[18px] w-[18px] animate-spin" strokeWidth={1.75} />
        </span>
      ) : (
        <span
          className="grid h-10 w-10 shrink-0 place-items-center rounded-pill bg-teal-soft text-teal-deep animate-in zoom-in-75 duration-200"
          aria-hidden="true"
        >
          <Check className="h-[18px] w-[18px]" strokeWidth={2} />
        </span>
      )}

      {/* center — keyed by state so each transition re-triggers the enter animation */}
      <div
        key={state}
        className="flex min-w-0 flex-1 items-center animate-in fade-in-0 duration-200"
      >
        {state === "idle" &&
          (hotkey ? (
            <span className="flex items-center gap-1.5 text-caption text-ink-tertiary">
              <span>Press</span>
              <kbd className="hairline rounded-md bg-canvas-soft px-1.5 py-0.5 font-ui text-[11px] font-medium text-ink-secondary">
                {hotkey}
              </kbd>
            </span>
          ) : (
            <DottedIndicator />
          ))}
        {state === "listening" && <AudioBars level={level} />}
        {state === "processing" && (
          <span className="text-label text-ink-secondary">Transcribing…</span>
        )}
        {state === "pasted" && (
          <span className="flex min-w-0 items-center gap-2">
            <span className="text-label font-medium text-teal-deep">Pasted</span>
            {text && <span className="truncate text-caption text-ink-tertiary">{text}</span>}
          </span>
        )}
      </div>

      {/* trailing — cancel affordance only while listening */}
      {state === "listening" && onCancel && (
        <button
          type="button"
          onClick={onCancel}
          aria-label="Cancel recording"
          className="no-drag grid h-8 w-8 shrink-0 place-items-center rounded-pill bg-ink/5 text-ink-secondary transition-colors hover:bg-ink/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 focus-visible:ring-offset-canvas"
        >
          <X className="h-4 w-4" strokeWidth={2} aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
