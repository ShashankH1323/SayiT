import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

export interface SidebarItemProps {
  icon: ReactNode;
  label: string;
  active?: boolean;
  collapsed?: boolean;
  onClick?: () => void;
}

/** Compact nav item. Active = quiet tinted pill (not a loud filled button). */
export function SidebarItem({ icon, label, active = false, collapsed = false, onClick }: SidebarItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      aria-label={label}
      aria-current={active ? "page" : undefined}
      className={cn(
        "no-drag flex items-center rounded-field transition-all duration-200",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1 focus-visible:ring-offset-canvas",
        collapsed
          ? "h-10 w-10 mx-auto justify-center p-0"
          : "w-full gap-3 px-3 py-2 text-label",
        active ? "bg-accent-soft text-accent font-medium shadow-soft-xs" : "text-ink-secondary hover:bg-black/[.03] hover:text-ink",
      )}
    >
      <span
        className="grid h-5 w-5 shrink-0 place-items-center [&>svg]:h-[18px] [&>svg]:w-[18px]"
        aria-hidden="true"
      >
        {icon}
      </span>
      {!collapsed && <span className="truncate transition-opacity duration-150">{label}</span>}
    </button>
  );
}

