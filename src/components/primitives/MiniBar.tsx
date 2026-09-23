import { Mic, X, Loader2, Check, Maximize2, Square } from "lucide-react";
import { cn } from "../../lib/utils";
import { formatHotkeyParts } from "../../lib/hotkeyUtils";
import { SayItMark } from "./SayItMark";

export type MiniBarState = "idle" | "listening" | "processing" | "pasted";

export interface MiniBarProps {
  state: MiniBarState;
  level?: number; // 0..1 audio level, drives listening bars
  text?: string;
  hotkey?: string;
  onToggle?: () => void;
  onCancel?: () => void;
  onExpand?: () => void;
  isStandalone?: boolean;
  className?: string;
}

const WAVE_WEIGHTS = [0.4, 0.65, 0.85, 1.0, 0.95, 0.7, 0.85, 1.0, 0.9, 0.6, 0.45, 0.35];

export function WaveformDots({
  level = 0,
  animated = false,
  className,
}: {
  level?: number;
  animated?: boolean;
  className?: string;
}) {
  const l = Math.min(1, Math.max(0, level));
  const dynamicLevel = Math.min(1, l * 2.5);

  return (
    <div className={cn("flex h-7 items-center justify-center gap-1 px-1", className)} aria-hidden="true">
      {WAVE_WEIGHTS.map((w, i) => {
        const minHeight = 4;
        const maxHeight = 22;
        const height = animated
          ? undefined
          : Math.max(minHeight, minHeight + dynamicLevel * w * (maxHeight - minHeight));

        return (
          <span
            key={i}
            className={cn(
              "w-[3.5px] rounded-full bg-teal transition-all duration-75 ease-out",
              animated && "animate-wave-bounce",
            )}
            style={{
              height: animated ? undefined : `${height}px`,
              animationDelay: animated ? `${i * 75}ms` : undefined,
              opacity: animated ? 0.85 : Math.max(0.45, Math.min(1, 0.45 + dynamicLevel * 0.55)),
            }}
          />
        );
      })}
    </div>
  );
}

function DottedIndicator() {
  return (
    <span className="flex items-center gap-1" aria-hidden="true">
      {Array.from({ length: 10 }).map((_, i) => (
        <span key={i} className="h-1 w-1 rounded-pill bg-ink/20" />
      ))}
    </span>
  );
}

/** Floating recording HUD matching Final Ui Cards 6-10:
 *  idle -> listening -> processing -> pasted -> idle */
export function MiniBar({
  state,
  level = 0,
  text,
  hotkey,
  onToggle,
  onCancel,
  onExpand,
  isStandalone = false,
  className,
}: MiniBarProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "glass-strong relative inline-flex h-14 min-w-[280px] max-w-[360px] items-center gap-3 rounded-pill px-3.5 shadow-soft-lg select-none",
        isStandalone && "cursor-default",
        className,
      )}
    >
      {/* Brand Logo mark on left slot (from Final Ui cards 6-10) */}
      <div
        onClick={onExpand}
        className={cn(
          "grid h-9 w-9 shrink-0 place-items-center rounded-full transition-transform",
          onExpand && "cursor-pointer hover:scale-105 active:scale-95",
        )}
        title={onExpand ? "Click to open full dashboard" : undefined}
      >
        <SayItMark size={28} />
      </div>

      {/* Center content slot morphs smoothly based on state */}
      <div
        key={state}
        className="flex min-w-0 flex-1 items-center animate-in fade-in-0 duration-200"
      >
        {state === "idle" && (
          hotkey ? (
            <div className="flex items-center gap-1.5 text-caption text-ink-secondary">
              <span>Press</span>
              <span className="inline-flex items-center gap-1">
                {formatHotkeyParts(hotkey).map((part, idx, arr) => (
                  <span key={idx} className="inline-flex items-center gap-1">
                    <kbd className="hairline rounded-md bg-canvas-soft px-1.5 py-0.5 font-ui text-[11px] font-semibold text-ink shadow-soft-xs">
                      {part}
                    </kbd>
                    {idx < arr.length - 1 && <span className="text-[10px] text-ink-tertiary">+</span>}
                  </span>
                ))}
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <DottedIndicator />
              <span className="text-caption text-ink-tertiary">Ready</span>
            </div>
          )
        )}

        {state === "listening" && (
          <div className="flex items-center gap-2">
            <WaveformDots level={level} />
            <span className="text-caption font-semibold text-teal-deep">Listening…</span>
          </div>
        )}

        {state === "processing" && (
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-accent" />
            <span className="text-caption font-medium text-ink-secondary">Transcribing…</span>
          </div>
        )}

        {state === "pasted" && (
          <div className="flex min-w-0 items-center gap-2">
            <span className="grid h-5 w-5 place-items-center rounded-full bg-teal-soft text-teal-deep">
              <Check className="h-3 w-3" strokeWidth={2.5} />
            </span>
            <span className="text-label font-semibold text-teal-deep">Pasted!</span>
            {text && <span className="truncate text-caption text-ink-tertiary max-w-[130px]">{text}</span>}
          </div>
        )}
      </div>

      {/* Trailing action affordances: Toggle/Stop button, Cancel, and Expand */}
      <div className="no-drag flex shrink-0 items-center gap-1.5">
        {state === "listening" && onToggle && (
          <button
            type="button"
            onClick={onToggle}
            aria-label="Stop recording"
            title="Stop recording"
            className="grid h-8 w-8 place-items-center rounded-full bg-teal text-white shadow-soft-xs hover:bg-teal-deep transition-colors"
          >
            <Square className="h-3.5 w-3.5 fill-current" />
          </button>
        )}

        {state === "idle" && onToggle && (
          <button
            type="button"
            onClick={onToggle}
            aria-label="Start recording"
            title="Start recording"
            className="grid h-8 w-8 place-items-center rounded-full bg-accent text-white shadow-soft-xs hover:bg-accent-deep transition-colors"
          >
            <Mic className="h-3.5 w-3.5" />
          </button>
        )}

        {state === "listening" && onCancel && (
          <button
            type="button"
            onClick={onCancel}
            aria-label="Cancel recording"
            title="Cancel"
            className="grid h-8 w-8 place-items-center rounded-full bg-ink/5 text-ink-secondary hover:bg-ink/10 transition-colors"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}

        {onExpand && (
          <button
            type="button"
            onClick={onExpand}
            aria-label="Expand to full dashboard"
            title="Open dashboard"
            className="grid h-8 w-8 place-items-center rounded-full text-ink-tertiary hover:bg-ink/5 hover:text-ink transition-colors"
          >
            <Maximize2 className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}
