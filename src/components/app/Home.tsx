import { useEffect, useState, useRef } from "react";
import { Mic, Square, Loader2, AlertTriangle, Copy, Check, ArrowRight, RotateCcw } from "lucide-react";
import { useApp } from "../../lib/appContext";
import { cn } from "../../lib/utils";
import { GlassButton } from "../primitives/GlassButton";
import { IconOrb } from "../primitives/IconOrb";
import { formatHotkeyDisplay, matchesHotkey, parseMouseEvent, normalizeHotkey } from "../../lib/hotkeyUtils";
import type { HistoryItem } from "../../lib/types";
import ideasFlourish from "../../assets/handwritten_ideas_flow_better_spoken.png";

type Phase = "idle" | "recording" | "processing" | "pasted";

function HomeSpeechWaveform({ level }: { level: number }) {
  const BARS = 21;
  const isSpeaking = level > 0.01;
  const amplified = Math.min(1, level * 3.5);

  return (
    <div className="flex h-10 min-w-[220px] items-center justify-center gap-1.5 rounded-full glass px-5 py-2 shadow-soft-sm select-none animate-in fade-in-0 zoom-in-95 duration-200">
      {Array.from({ length: BARS }).map((_, i) => {
        const bell = Math.sin(((i + 1) / (BARS + 1)) * Math.PI);
        const minH = 4;
        const maxH = 26;
        const dynamicH = isSpeaking
          ? minH + (maxH - minH) * bell * amplified * (0.8 + 0.2 * Math.sin(i * 1.6))
          : minH;

        return (
          <span
            key={i}
            className={cn(
              "w-[3px] rounded-full transition-[height,background-color,opacity] duration-75 ease-out",
              isSpeaking
                ? "bg-gradient-to-t from-red-500 to-rose-400 shadow-[0_0_8px_rgba(239,68,68,0.5)] opacity-95"
                : "bg-red-400/30 opacity-40"
            )}
            style={{ height: `${Math.round(dynamicH)}px` }}
          />
        );
      })}
    </div>
  );
}

const COPY: Record<Phase, { title: string; sub: string }> = {
  idle: { title: "Ready when you are", sub: "Press your hotkey and speak — your words land at your cursor." },
  recording: { title: "Listening…", sub: "Speak naturally — stop when you’re done." },
  processing: { title: "Transcribing…", sub: "Turning your speech into text." },
  pasted: { title: "Pasted!", sub: "Dropped in at your cursor. Go again anytime." },
};

function formatRelativeTime(ts: string): string {
  const t = new Date(ts).getTime();
  if (Number.isNaN(t)) return "Recent";
  const diff = Date.now() - t;
  const min = Math.floor(diff / 60000);
  if (min < 1) return "Just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return new Date(ts).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function Home() {
  const { status, settings, pastedToast, actions } = useApp();
  const hotkey = settings?.hotkey || "ctrl+space";
  const [recentItem, setRecentItem] = useState<HistoryItem | null>(null);
  const [copiedRecent, setCopiedRecent] = useState(false);
  const copyTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // Load the most recent transaction
  useEffect(() => {
    let alive = true;
    actions.historyLoad(1).then((items) => {
      if (alive && items && items.length > 0) {
        setRecentItem(items[0]);
      }
    });
    return () => { alive = false; };
  }, [status.last_text, pastedToast, actions]);

  // Listen for the hotkey inside the window when focused
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
        return;
      }
      if (matchesHotkey(e, hotkey)) {
        e.preventDefault();
        actions.toggle();
      }
    };

    const handleMouseDown = (e: MouseEvent) => {
      const mouseHot = parseMouseEvent(e);
      if (mouseHot && normalizeHotkey(mouseHot) === normalizeHotkey(hotkey)) {
        e.preventDefault();
        actions.toggle();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("mousedown", handleMouseDown);
    window.addEventListener("auxclick", handleMouseDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("mousedown", handleMouseDown);
      window.removeEventListener("auxclick", handleMouseDown);
    };
  }, [hotkey, actions]);

  const handleCopyRecent = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!recentItem?.text) return;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(recentItem.text);
      } else {
        const ta = document.createElement("textarea");
        ta.value = recentItem.text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      setCopiedRecent(true);
      if (copyTimer.current) clearTimeout(copyTimer.current);
      copyTimer.current = setTimeout(() => setCopiedRecent(false), 1600);
    } catch {
      // ignore
    }
  };

  const handleTryAgain = async () => {
    await actions.cancel();
    setTimeout(() => {
      actions.toggle();
    }, 150);
  };

  // Error Card takes over with a clear explanation and "Try Again" + "Dismiss"
  if (status.state === "error") {
    return (
      <div className="no-drag h-full w-full flex-1 overflow-y-auto">
        <div className="mx-auto flex min-h-full max-w-sm flex-col items-center justify-center gap-5 px-8 py-10 text-center animate-in fade-in-0 duration-300">
          <IconOrb
            icon={<AlertTriangle className="h-7 w-7 text-destructive" strokeWidth={2} aria-hidden="true" />}
            tone="neutral"
            size={76}
            className="shadow-soft-md"
          />
          <div className="space-y-1">
            <h2 className="text-display font-display font-bold text-ink">Transcription Failed</h2>
            <p className="text-body text-ink-secondary leading-relaxed">
              {status.last_error || "We couldn't hear or process your speech. Please check your mic connection and try again."}
            </p>
          </div>
          <div className="flex items-center gap-3 pt-2">
            <GlassButton
              variant="primary"
              size="md"
              icon={<RotateCcw className="h-4 w-4" />}
              onClick={handleTryAgain}
            >
              Try Again
            </GlassButton>
            <GlassButton variant="secondary" size="md" onClick={actions.cancel}>
              Dismiss
            </GlassButton>
          </div>
        </div>
      </div>
    );
  }

  const listening = status.state === "recording";
  const processing = status.state === "processing";
  const phase: Phase = pastedToast ? "pasted" : status.state;
  const title = COPY[phase].title;
  const sub =
    phase === "idle" && hotkey
      ? `Press ${formatHotkeyDisplay(hotkey)} and speak — your words land at your cursor.`
      : COPY[phase].sub;

  return (
    <div className="no-drag relative flex h-full w-full flex-col justify-between overflow-x-hidden p-6 select-none">
      {/* Top Flourish Badge: "Ideas flow better spoken." from Final Ui */}
      <div className="absolute top-4 right-6 pointer-events-none opacity-80 select-none">
        <img
          src={ideasFlourish}
          alt="Ideas flow better spoken"
          className="h-10 w-auto object-contain"
          draggable={false}
        />
      </div>

      {/* Main Center Hero Area */}
      <div className="my-auto mx-auto flex max-w-md flex-col items-center justify-center gap-6 text-center animate-in fade-in-0 duration-300">
        <div className="space-y-1.5">
          <h1 key={title} className="font-display text-display font-bold text-ink animate-in fade-in-0 duration-200">
            {title}
          </h1>
          <p className="mx-auto max-w-xs text-body text-ink-secondary">{sub}</p>
        </div>

        {/* Big tactile interactive state button */}
        <button
          type="button"
          onClick={actions.toggle}
          disabled={processing}
          aria-label={listening ? "Stop recording" : "Start recording"}
          className={cn(
            "no-drag relative flex h-28 w-28 items-center justify-center rounded-full transition-all duration-300 cursor-pointer",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-4 focus-visible:ring-offset-canvas-soft",
            listening
              ? "bg-gradient-to-tr from-red-500 to-rose-600 shadow-[0_0_36px_rgba(239,68,68,0.55)] scale-105 animate-pulse"
              : processing
              ? "bg-accent/90 shadow-soft-lg cursor-wait opacity-90"
              : phase === "pasted"
              ? "bg-gradient-to-tr from-teal to-teal-deep shadow-[0_0_28px_rgba(16,185,129,0.45)] scale-105"
              : "bg-gradient-to-tr from-accent to-accent-deep shadow-soft-lg hover:scale-105 active:scale-95 text-white"
          )}
        >
          {listening ? (
            <Square className="h-10 w-10 fill-white text-white drop-shadow-md" />
          ) : processing ? (
            <Loader2 className="h-12 w-12 text-white animate-spin drop-shadow-md" />
          ) : phase === "pasted" ? (
            <Check className="h-12 w-12 text-white stroke-[2.5] drop-shadow-md" />
          ) : (
            <Mic className="h-12 w-12 text-white drop-shadow-md" strokeWidth={2.2} />
          )}
        </button>

        {/* Dynamic status waveform bar (shown only during active recording/transcription) */}
        {listening ? (
          <HomeSpeechWaveform level={status.level} />
        ) : processing ? (
          <div className="flex h-10 items-center justify-center gap-2 rounded-full glass px-5 py-2 shadow-soft-sm text-caption text-ink-secondary animate-in fade-in-0 duration-200">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-accent" />
            <span className="font-medium">Transcribing speech…</span>
          </div>
        ) : pastedToast ? (
          <div className="flex h-10 items-center justify-center gap-2 rounded-full bg-teal-soft border border-teal/20 px-5 py-2 text-caption font-semibold text-teal-deep shadow-soft-xs animate-in zoom-in-95 duration-200">
            <Check className="h-3.5 w-3.5 stroke-[2.5]" />
            <span>Pasted!</span>
            <span className="max-w-[120px] truncate font-normal text-teal-deep/80">"{pastedToast}"</span>
          </div>
        ) : null}
      </div>

      {/* Redesigned Bottom Bar: Left: Ready status | Right: Single Recent History Card with Copy */}
      <div className="no-drag flex items-center justify-between gap-4 pt-4 border-t border-hairline/60">
        {/* Left: Status Indicator */}
        <div className="flex items-center gap-2">
          <span className="flex h-2.5 w-2.5 relative">
            <span className={cn(
              "absolute inline-flex h-full w-full rounded-full opacity-75",
              listening ? "animate-ping bg-teal" : processing ? "animate-pulse bg-accent" : "bg-teal"
            )} />
            <span className={cn(
              "relative inline-flex rounded-full h-2.5 w-2.5",
              listening ? "bg-teal" : processing ? "bg-accent" : "bg-teal"
            )} />
          </span>
          <span className="text-caption font-semibold text-ink-secondary">
            {listening ? "Recording" : processing ? "Transcribing" : "Ready"}
          </span>
        </div>

        {/* Right: Rectangular Last Recent History Card */}
        {recentItem ? (
          <div
            onClick={() => actions.navigate("history")}
            title="Click to view all in History"
            className="group flex items-center gap-3 rounded-card border border-hairline bg-white/80 backdrop-blur-md px-3 py-1.5 shadow-soft-xs hover:border-accent/30 hover:bg-white hover:shadow-soft-sm transition-all cursor-pointer max-w-sm"
          >
            <div className="min-w-0 flex-1 text-left">
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-tertiary">
                  Last dictate • {formatRelativeTime(recentItem.ts)}
                </span>
              </div>
              <p className="truncate text-caption font-medium text-ink max-w-[210px]">
                {recentItem.text}
              </p>
            </div>

            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={handleCopyRecent}
                title={copiedRecent ? "Copied" : "Copy recent transcript"}
                aria-label="Copy transcript"
                className={cn(
                  "grid h-7 w-7 place-items-center rounded-field border transition-colors",
                  copiedRecent
                    ? "border-teal/30 bg-teal-soft text-teal-deep"
                    : "border-hairline bg-canvas-soft text-ink-secondary hover:bg-ink/5 hover:text-ink"
                )}
              >
                {copiedRecent ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
              <span className="grid h-7 w-7 place-items-center rounded-field text-ink-tertiary group-hover:text-accent group-hover:translate-x-0.5 transition-all">
                <ArrowRight className="h-3.5 w-3.5" />
              </span>
            </div>
          </div>
        ) : (
          <div className="text-caption text-ink-tertiary">
            Dictate anything to see recent history
          </div>
        )}
      </div>
    </div>
  );
}
