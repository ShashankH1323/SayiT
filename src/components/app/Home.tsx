// Home.tsx — Screen 05: the main hub. A calm, centered dictation control that
// morphs with recording state. Renders inside the app shell (the shell owns the
// window frame, sidebar, status bar and the window-level blob background).
import { Mic, AlertTriangle } from "lucide-react";
import { useApp } from "../../lib/appContext";
import { cn } from "../../lib/utils";
import { MiniBar } from "../primitives/MiniBar";
import { IconOrb } from "../primitives/IconOrb";
import { StatusPill } from "../primitives/StatusPill";
import { GlassButton } from "../primitives/GlassButton";

type Phase = "idle" | "recording" | "processing" | "pasted";

const COPY: Record<Phase, { title: string; sub: string }> = {
  idle: { title: "Ready when you are", sub: "Press your hotkey and speak — your words land at your cursor." },
  recording: { title: "Listening…", sub: "Speak naturally — stop when you’re done." },
  processing: { title: "Transcribing…", sub: "Turning your speech into text." },
  pasted: { title: "Pasted!", sub: "Dropped in at your cursor. Go again anytime." },
};

export function Home() {
  const { status, settings, pastedToast, actions } = useApp();

  // Error takes over the whole hub with a clear, dismissible card.
  if (status.state === "error") {
    return (
      <div className="no-drag h-full w-full flex-1 overflow-y-auto">
        <div className="mx-auto flex min-h-full max-w-sm flex-col items-center justify-center gap-5 px-8 py-10 text-center animate-in fade-in-0 duration-300">
          <IconOrb
            icon={<AlertTriangle className="h-7 w-7 text-destructive" strokeWidth={1.75} aria-hidden="true" />}
            tone="neutral"
            size={72}
          />
          <StatusPill tone="error" label="Something went wrong" />
          <p className="text-body text-ink-secondary">
            {status.last_error || "Recording failed. Please try again."}
          </p>
          <GlassButton variant="secondary" onClick={actions.cancel}>
            Dismiss
          </GlassButton>
        </div>
      </div>
    );
  }

  const hotkey = settings?.hotkey;
  const listening = status.state === "recording";
  const processing = status.state === "processing";
  // The just-pasted toast shows while the backend has already returned to idle,
  // so it drives the HUD/copy but leaves the orb clickable for the next take.
  const phase: Phase = pastedToast ? "pasted" : status.state;
  const title = COPY[phase].title;
  const sub =
    phase === "idle" && hotkey
      ? `Press ${hotkey} and speak — your words land at your cursor.`
      : COPY[phase].sub;

  return (
    <div className="no-drag h-full w-full flex-1 overflow-y-auto">
      <div className="mx-auto flex min-h-full max-w-md flex-col items-center justify-center gap-7 px-8 py-10 text-center animate-in fade-in-0 duration-300">
        {/* Greeting / state title */}
        <div className="space-y-2">
          <h1 key={title} className="font-display text-display text-ink animate-in fade-in-0 duration-200">
            {title}
          </h1>
          <p className="mx-auto max-w-xs text-body text-ink-secondary">{sub}</p>
        </div>

        {/* Big, inviting mic — the primary action and focal point. */}
        <button
          type="button"
          onClick={actions.toggle}
          disabled={processing}
          aria-label={listening ? "Stop recording" : "Start recording"}
          className={cn(
            "no-drag relative rounded-full transition-transform",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-4 focus-visible:ring-offset-canvas-soft",
            processing ? "cursor-default opacity-90" : "hover:scale-[1.03] active:scale-95",
          )}
        >
          <IconOrb
            icon={<Mic className="h-10 w-10" strokeWidth={1.75} aria-hidden="true" />}
            tone={listening ? "teal" : "accent"}
            size={112}
            className="relative shadow-soft-lg"
          />
        </button>

        {/* Live recording HUD — one MiniBar, state-mapped per the contract. */}
        {pastedToast ? (
          <MiniBar state="pasted" text={pastedToast} />
        ) : listening ? (
          <MiniBar state="listening" level={status.level} onToggle={actions.toggle} onCancel={actions.cancel} />
        ) : processing ? (
          <MiniBar state="processing" />
        ) : (
          <MiniBar state="idle" hotkey={hotkey} onToggle={actions.toggle} />
        )}

        {/* Most recent transcription, quietly, when idle. */}
        {phase === "idle" && status.last_text && (
          <p className="max-w-xs truncate text-caption text-ink-tertiary" title={status.last_text}>
            Last: {status.last_text}
          </p>
        )}
      </div>
    </div>
  );
}
