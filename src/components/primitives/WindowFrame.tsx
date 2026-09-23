// Frameless title bar (~44px). Whole bar is a drag region; controls opt out.
// Left: decorative traffic-light dots. Right: functional Minimize + Close.
import type { ReactNode } from "react";
import { Minus, X } from "lucide-react";
import { cn } from "../../lib/utils";

export interface WindowFrameProps {
  title?: string;
  onMinimize?: () => void;
  onClose?: () => void;
  right?: ReactNode;
  className?: string;
}

const DOTS = ["#FF6B60", "#FEBC2E", "#2ACB42"];

export function WindowFrame({ title, onMinimize, onClose, right, className }: WindowFrameProps) {
  return (
    <div className={cn("drag relative flex h-11 shrink-0 items-center justify-between px-4", className)}>
      <div aria-hidden className="flex items-center gap-2">
        {DOTS.map((c) => (
          <span key={c} className="h-3 w-3 rounded-full" style={{ backgroundColor: c }} />
        ))}
      </div>

      {title && (
        <div className="pointer-events-none absolute left-1/2 -translate-x-1/2 text-label font-medium text-ink-secondary">
          {title}
        </div>
      )}

      <div className="no-drag flex items-center gap-1">
        {right}
        <button
          type="button"
          aria-label="Minimize"
          onClick={onMinimize}
          className="inline-flex h-7 w-7 items-center justify-center rounded-md text-ink-tertiary transition-colors hover:bg-ink/5 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <Minus size={15} strokeWidth={2} />
        </button>
        <button
          type="button"
          aria-label="Close"
          onClick={onClose}
          className="inline-flex h-7 w-7 items-center justify-center rounded-md text-ink-tertiary transition-colors hover:bg-destructive/10 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <X size={15} strokeWidth={2} />
        </button>
      </div>
    </div>
  );
}
