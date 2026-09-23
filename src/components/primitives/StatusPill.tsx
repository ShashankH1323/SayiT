import { cn } from "../../lib/utils";

export type StatusTone = "idle" | "recording" | "processing" | "ready" | "error";

export interface StatusPillProps {
  tone: StatusTone;
  label?: string;
  className?: string;
}

const DOT: Record<StatusTone, string> = {
  idle: "bg-ink-tertiary",
  recording: "bg-accent animate-pulse",
  processing: "bg-accent",
  ready: "bg-teal",
  error: "bg-destructive",
};

const DEFAULT_LABEL: Record<StatusTone, string> = {
  idle: "Idle",
  recording: "Recording",
  processing: "Processing",
  ready: "Ready",
  error: "Error",
};

/** Status indicator: colored dot + optional label. recording pulses; ready is teal. */
export function StatusPill({ tone, label, className }: StatusPillProps) {
  return (
    <span
      role="status"
      aria-label={label ?? DEFAULT_LABEL[tone]}
      className={cn("inline-flex items-center gap-2", className)}
    >
      <span className={cn("h-2 w-2 shrink-0 rounded-pill", DOT[tone])} aria-hidden="true" />
      {label && <span className="text-label text-ink-secondary">{label}</span>}
    </span>
  );
}
