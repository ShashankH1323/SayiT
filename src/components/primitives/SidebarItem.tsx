import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

export interface SidebarItemProps {
  icon: ReactNode;
  label: string;
  active?: boolean;
  onClick?: () => void;
}

/** Compact nav item. Active = quiet tinted pill (not a loud filled button). */
export function SidebarItem({ icon, label, active = false, onClick }: SidebarItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={cn(
        "no-drag flex w-full items-center gap-3 rounded-field px-3 py-2 text-label transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 focus-visible:ring-offset-canvas",
        active ? "bg-accent-soft text-accent" : "text-ink-secondary hover:bg-black/[.03]",
      )}
    >
      <span
        className="grid h-5 w-5 shrink-0 place-items-center [&>svg]:h-[18px] [&>svg]:w-[18px]"
        aria-hidden="true"
      >
        {icon}
      </span>
      <span className="truncate">{label}</span>
    </button>
  );
}
