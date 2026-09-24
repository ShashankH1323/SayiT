import { Mic, Loader2, Check, Square } from "lucide-react";
import { cn } from "../../lib/utils";
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

/**
 * Compact responsive waveform dots/bars for the MiniBar.
 * In idle: stationary dots.
 * In listening: stays at resting dot height when silent; animates into waveform directly responding to mic audio level when speaking.
 */
export function WaveformDots({
  state,
  level = 0,
}: {
  state: MiniBarState;
  level?: number;
}) {
  const BARS = 5;
  const isSpeaking = state === "listening" && level > 0.01;
  const amplified = Math.min(1, level * 3.5);

  return (
    <div className="flex h-5 items-center justify-center gap-1 px-1 select-none" aria-hidden="true">
      {Array.from({ length: BARS }).map((_, i) => {
        const bell = Math.sin(((i + 1) / (BARS + 1)) * Math.PI);
        const minHeight = 2.5;
        const maxHeight = 15;
        const dynamicHeight = isSpeaking
          ? minHeight + (maxHeight - minHeight) * bell * amplified * (0.8 + 0.2 * Math.sin(i * 1.8))
          : minHeight;

        return (
          <span
            key={i}
            className={cn(
              "w-[2.5px] rounded-full transition-all duration-75 ease-out",
              state === "listening"
                ? isSpeaking
                  ? "bg-gradient-to-t from-red-500 to-rose-400 shadow-[0_0_6px_rgba(239,68,68,0.5)]"
                  : "bg-red-400/40"
                : state === "processing"
                ? "bg-accent animate-pulse"
                : "bg-ink/30"
            )}
            style={{
              height: `${Math.round(dynamicHeight)}px`,
              opacity: isSpeaking ? 1 : state === "listening" ? 0.6 : 0.45,
            }}
          />
        );
      })}
    </div>
  );
}

/**
 * Half-sized, ultra-compact glassmorphic Mini Bar.
 * - Reduced to half size (116px width x 28px height)
 * - Transparent background (no square white background)
 * - Real-time microphone audio waveform detection on speech
 * - Dynamic action button: Mic (idle) -> Stop (recording) -> Spinning Loading Logo (processing) -> Idle
 */
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
        "drag pywebview-drag-region relative inline-flex h-7 w-[116px] items-center justify-between rounded-full px-1.5 py-0.5 select-none",
        "backdrop-blur-xl bg-white/92",
        "border border-white/80 shadow-[0_2px_10px_rgba(15,23,42,0.12),0_1px_2px_rgba(15,23,42,0.06)]",
        isStandalone && "cursor-default",
        className,
      )}
    >
      {/* Elevated App Logo Button: compact h-5 w-5, click opens Say It dashboard */}
      <button
        type="button"
        onClick={onExpand}
        onMouseDown={(e) => e.stopPropagation()}
        title="Open Say It dashboard"
        aria-label="Open Say It dashboard"
        className={cn(
          "group relative grid h-5 w-5 shrink-0 place-items-center rounded-full bg-white",
          "shadow-[0_1px_3px_rgba(0,0,0,0.1),0_0_0_1px_rgba(0,0,0,0.04)]",
          "hover:scale-105 active:scale-95 transition-all duration-150 cursor-pointer focus:outline-none"
        )}
      >
        <SayItMark size={14} className="transition-transform duration-150 group-hover:scale-105" />
      </button>

      {/* Center content: Animated real-time waveform dots responding directly to mic loudness */}
      <div className="flex min-w-0 flex-1 items-center justify-center">
        {state === "pasted" ? (
          <span className="text-[10px] font-semibold text-teal-deep animate-in zoom-in-75 duration-150">
            Pasted!
          </span>
        ) : (
          <WaveformDots state={state} level={level} />
        )}
      </div>

      {/* Dynamic Action Button: Mic -> Stop -> Spinning Loading Logo -> Pasted Check */}
      <div className="no-drag flex shrink-0 items-center" onMouseDown={(e) => e.stopPropagation()}>
        {state === "idle" && (
          <button
            type="button"
            onClick={onToggle}
            aria-label="Start recording"
            title="Start recording"
            className="grid h-5 w-5 place-items-center rounded-full bg-accent text-white shadow-xs hover:bg-accent-deep active:scale-95 transition-all duration-150 cursor-pointer"
          >
            <Mic className="h-2.5 w-2.5" />
          </button>
        )}

        {state === "listening" && (
          <button
            type="button"
            onClick={onToggle}
            aria-label="Stop recording"
            title="Stop recording"
            className="grid h-5 w-5 place-items-center rounded-full bg-red-500 text-white shadow-xs hover:bg-red-600 active:scale-95 transition-all duration-150 cursor-pointer animate-pulse"
          >
            <Square className="h-2 w-2 fill-white text-white" />
          </button>
        )}

        {state === "processing" && (
          <div className="grid h-5 w-5 place-items-center" title="Processing transcription…">
            <Loader2 className="h-3 w-3 animate-spin text-accent" />
          </div>
        )}

        {state === "pasted" && (
          <div className="grid h-5 w-5 place-items-center rounded-full bg-teal-soft text-teal-deep shadow-xs animate-in zoom-in-75 duration-150">
            <Check className="h-2.5 w-2.5 stroke-[2.5]" />
          </div>
        )}
      </div>
    </div>
  );
}
