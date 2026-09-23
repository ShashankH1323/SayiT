import type { ReactNode } from "react";
import { Minus, X } from "lucide-react";
import { useApp } from "../../lib/appContext";
import { cn } from "../../lib/utils";

export interface WindowFrameProps {
  title?: string;
  onMinimize?: () => void;
  onClose?: () => void;
  right?: ReactNode;
  className?: string;
}

export function WindowFrame({ title, onMinimize, onClose, right, className }: WindowFrameProps) {
  const { actions } = useApp();

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 0 && !(e.target as HTMLElement).closest(".no-drag, button, input, a, select")) {
      actions.windowDrag();
    }
  };

  return (
    <div
      onMouseDown={handleMouseDown}
      className={cn("drag relative flex h-11 shrink-0 select-none items-center justify-between px-4 cursor-default", className)}
    >
      <div className="w-16" />

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
