// "Say It" wordmark in deep navy display type; optional leading logo mark.
import { cn } from "../../lib/utils";
import { SayItMark } from "./SayItMark";

export interface SayItWordmarkProps {
  size?: "sm" | "md" | "lg";
  withMark?: boolean;
  className?: string;
}

const TEXT = { sm: "text-lg", md: "text-2xl", lg: "text-3xl" } as const;
const MARK = { sm: 22, md: 28, lg: 36 } as const;
const GAP = { sm: "gap-2", md: "gap-2.5", lg: "gap-3" } as const;

export function SayItWordmark({ size = "md", withMark = false, className }: SayItWordmarkProps) {
  return (
    <span className={cn("inline-flex items-center", GAP[size], className)}>
      {withMark && <SayItMark size={MARK[size]} />}
      <span className={cn("font-display font-bold leading-none tracking-tight text-ink", TEXT[size])}>Say It</span>
    </span>
  );
}
