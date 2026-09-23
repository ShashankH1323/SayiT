import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

export interface SettingRowProps {
  label: string;
  description?: string;
  icon?: ReactNode;
  children?: ReactNode; // right-aligned control
  className?: string;
}

/** Label/description (left) + control slot (right). Hairline divider between rows;
 *  the last row drops it via `last:border-b-0`. Override with `className`. */
export function SettingRow({ label, description, icon, children, className }: SettingRowProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-3 border-b border-hairline py-3.5 last:border-b-0",
        className,
      )}
    >
      {icon && (
        <span
          className="grid h-9 w-9 shrink-0 place-items-center rounded-field bg-canvas-soft text-ink-secondary [&>svg]:h-[18px] [&>svg]:w-[18px]"
          aria-hidden="true"
        >
          {icon}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <div className="text-label text-ink">{label}</div>
        {description && <div className="text-caption text-ink-secondary">{description}</div>}
      </div>
      {children && <div className="no-drag ml-auto flex shrink-0 items-center">{children}</div>}
    </div>
  );
}
