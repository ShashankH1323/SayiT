import { cn } from "../../lib/utils";

export interface PaginationDotsProps {
  count: number;
  active: number;
  className?: string;
}

/** Onboarding step dots. Active dot = wider accent bar; others = faint ink. */
export function PaginationDots({ count, active, className }: PaginationDotsProps) {
  return (
    <div
      className={cn("flex items-center gap-1.5", className)}
      role="group"
      aria-label={`Step ${Math.min(active + 1, count)} of ${count}`}
    >
      {Array.from({ length: Math.max(0, count) }).map((_, i) => (
        <span
          key={i}
          aria-hidden="true"
          className={cn(
            "h-1.5 rounded-pill transition-all duration-300",
            i === active ? "w-5 bg-accent" : "w-1.5 bg-ink/15",
          )}
        />
      ))}
    </div>
  );
}
